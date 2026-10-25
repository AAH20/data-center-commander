-- 011_api_keys.sql
--
-- Durable, shared API key storage.
--
-- The defect this closes
-- ----------------------
-- ApiKeyStore was an in-memory dict keyed by key hash. Three consequences, in
-- increasing order of nastiness:
--
--   1. Every process restart destroyed every issued key. The deployment that had
--      just been restarted rejected all traffic until keys were reissued.
--   2. Each uvicorn worker had its OWN dict. A key minted on worker 1 was unknown
--      to worker 2, so one in N requests got a 401 with no explanation. Silent
--      multi-worker breakage -- the reason this migration exists.
--   3. Nothing recorded who issued a key, when, or when it was revoked, which is
--      an auditability hole for a product that sells governance.
--
-- dcc.api_keys is the durable record. Only the SHA-256 digest of a key is ever
-- stored; the raw key exists in the response that minted it and nowhere else.
-- created_by / created_at / revoked_at / last_used_at are the audit trail.
--
-- The hard part: RLS vs. authentication
-- -------------------------------------
-- Every tenant table here carries ENABLE + FORCE ROW LEVEL SECURITY with a
-- tenant_scope policy reading dcc.tenant_id. But authentication runs BEFORE any
-- tenant is known -- you look up a key in order to learn its tenant -- so a plain
-- tenant_scope lookup sees zero rows and every request would 401. And FORCE is not
-- a formality: it applies to the TABLE OWNER too, so a SECURITY DEFINER function
-- owned by the migration role also sees zero rows. (Measured, not assumed: with a
-- non-superuser owner, `SELECT count(*)` through an owner-owned definer function
-- returned 0. A superuser owner masks this completely, which is exactly why the
-- naive version ships and then fails in production.)
--
-- The only two escapes from RLS are SUPERUSER and BYPASSRLS. So:
--
--   * dcc.api_keys keeps ENABLE + FORCE RLS and the standard tenant_scope policy.
--     Reads/Writes by the application role (dcc_app) are tenant-scoped exactly like
--     every other table.
--   * The lookup is a small SECURITY DEFINER function, dcc.lookup_api_key(), owned
--     by dcc_api_key_reader: NOLOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE,
--     NOINHERIT, BYPASSRLS. Nothing can log in as it, nothing inherits it, and it
--     owns nothing but these three functions, so its bypass cannot be borrowed by
--     the application role.
--   * The bypass is one indexed single-row read (plus two narrow writes) by digest.
--     That is not a privilege escalation: the caller must already present a digest
--     to look anything up, and a digest is only knowable by holding the key.
--
-- If the migration is run by a role that cannot create a BYPASSRLS role (creating
-- one requires superuser), the migration does NOT fail and does NOT silently
-- produce an unusable lookup. It falls back to a SELECT policy that admits rows
-- only when the query is executing as the owner of the lookup function, and emits
-- a WARNING naming the weaker guarantee. The fallback keeps the lookup working;
-- it does widen SELECT to the table owner. See the DO block at the bottom.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. The table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dcc.api_keys (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES dcc.tenants(id) ON DELETE CASCADE,
    -- SHA-256 hex of the raw key. The digest is the lookup key, so it is UNIQUE;
    -- that constraint also gives the authentication path its index for free.
    key_hash      text NOT NULL UNIQUE CHECK (key_hash ~ '^[0-9a-f]{64}$'),
    label         text,
    scopes        text[] NOT NULL DEFAULT '{}',
    created_at    timestamptz NOT NULL DEFAULT now(),
    -- Who issued it. Free text on purpose: the caller may be an operator, a CLI, or
    -- a future admin API, and pinning this to a users table that does not exist yet
    -- would have to be undone later.
    created_by    text,
    expires_at    timestamptz,
    -- NULL means "live". A timestamp (not a boolean) so the audit trail says when.
    revoked_at    timestamptz,
    last_used_at  timestamptz
);

COMMENT ON TABLE dcc.api_keys IS
    'Durable API keys. Stores the SHA-256 digest only; the raw key is never persisted.';
COMMENT ON COLUMN dcc.api_keys.key_hash IS
    'SHA-256 hex digest of the raw key. The lookup key, and the only copy of the credential.';
COMMENT ON COLUMN dcc.api_keys.created_by IS
    'Who issued the key (operator, CLI, admin API). Audit trail, not a foreign key.';
COMMENT ON COLUMN dcc.api_keys.revoked_at IS
    'NULL = live. Set once, never cleared: revocation is not undoable by a rewrite.';

-- Listing a tenant's keys newest-first is the admin view.
CREATE INDEX IF NOT EXISTS api_keys_tenant_created_idx
    ON dcc.api_keys (tenant_id, created_at DESC);

-- Partial index for the authentication path and for "which keys are live".
-- The predicate cannot mention expires_at: a partial index predicate must be
-- immutable and now() is not, so expiry is a runtime check in lookup_api_key()
-- and in the store, never an index condition.
CREATE INDEX IF NOT EXISTS api_keys_live_idx
    ON dcc.api_keys (tenant_id, key_hash)
    WHERE revoked_at IS NULL;

-- ---------------------------------------------------------------------------
-- 2. Row level security -- same contract as every other tenant table
-- ---------------------------------------------------------------------------

ALTER TABLE dcc.api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE dcc.api_keys FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_scope ON dcc.api_keys;
CREATE POLICY tenant_scope ON dcc.api_keys
    USING (tenant_id = (NULLIF(current_setting('dcc.tenant_id', true), ''))::uuid)
    WITH CHECK (tenant_id = (NULLIF(current_setting('dcc.tenant_id', true), ''))::uuid);

-- ---------------------------------------------------------------------------
-- 3. The pre-tenant lookup path
-- ---------------------------------------------------------------------------
-- SECURITY DEFINER: the function body runs as its owner (dcc_api_key_reader,
-- BYPASSRLS), so the lookup works before dcc.tenant_id is known. search_path is
-- pinned so a caller cannot shadow dcc.api_keys with a temp table.
--
-- Columns returned are the minimum authentication needs. key_hash is returned so
-- the caller can re-assert the match with hmac.compare_digest() instead of trusting
-- that the function filtered correctly -- returning the digest the caller themselves
-- supplied leaks nothing and removes a whole class of "function ignored its
-- argument" bug. id is returned because api_async records request.state.api_key_id
-- for the audit trail. label and created_at are returned so the verified record is
-- the real one rather than the store inventing a name and a creation time. Every one
-- of these is non-secret metadata the caller has already earned by presenting the key.

-- A re-run of this migration must not trip over the previous function shape
-- ("cannot change return type of existing function"). The fallback policy depends on
-- the function it names, so it is dropped first; the DO block below reinstalls it if
-- the BYPASSRLS design is unavailable.
DROP POLICY IF EXISTS api_key_authenticate ON dcc.api_keys;
DROP FUNCTION IF EXISTS dcc.lookup_api_key(text);
DROP FUNCTION IF EXISTS dcc.touch_api_key(text);
DROP FUNCTION IF EXISTS dcc.api_key_tenant(uuid);
DROP FUNCTION IF EXISTS dcc.api_key_count();

CREATE OR REPLACE FUNCTION dcc.lookup_api_key(p_hash text)
RETURNS TABLE (
    key_id      uuid,
    tenant_id   uuid,
    key_hash    text,
    label       text,
    scopes      text[],
    created_at  timestamptz,
    expires_at  timestamptz,
    revoked_at  timestamptz
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, dcc
AS $$
    SELECT k.id, k.tenant_id, k.key_hash, k.label, k.scopes, k.created_at,
           k.expires_at, k.revoked_at
      FROM dcc.api_keys k
     WHERE k.key_hash = p_hash
$$;

-- last_used_at is written on the authentication path, which is the hottest path in
-- the service. The WHERE clause means a key that is already being used does not
-- generate a row write per request: at most one write per key per 5 seconds, even
-- if several processes race. The store additionally throttles in-process so the
-- statement is usually not even sent.
CREATE OR REPLACE FUNCTION dcc.touch_api_key(p_hash text)
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, dcc
AS $$
    UPDATE dcc.api_keys k
       SET last_used_at = now()
     WHERE k.key_hash = p_hash
       AND (k.last_used_at IS NULL OR k.last_used_at < now() - interval '5 seconds')
    RETURNING true
$$;

-- Admin operations (get / revoke / delete) address a key by its id, but RLS needs
-- the tenant to authorise them. This resolves id -> tenant, after which the caller
-- sets dcc.tenant_id and performs the write under the ordinary tenant_scope policy.
-- Knowing a key id (a uuid) reveals its tenant id and nothing else.
CREATE OR REPLACE FUNCTION dcc.api_key_tenant(p_id uuid)
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, dcc
AS $$
    SELECT k.tenant_id FROM dcc.api_keys k WHERE k.id = p_id
$$;

-- How many keys exist, across tenants. One number, no rows, no identifiers.
--
-- This exists for the startup lockout check: it needs to answer "is the store empty?"
-- and that question cannot be answered by listing rows, because listing without a
-- tenant under FORCE RLS correctly returns nothing. Without this the process would
-- announce "no API keys configured" every time it started in a tenant-isolated
-- deployment, and with DCC_REQUIRE_KEYS=true it would refuse to start.
CREATE OR REPLACE FUNCTION dcc.api_key_count()
RETURNS bigint
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, dcc
AS $$
    SELECT count(*) FROM dcc.api_keys
$$;

-- ---------------------------------------------------------------------------
-- 4. Who owns the bypass
-- ---------------------------------------------------------------------------
-- Creating a role with BYPASSRLS requires superuser, so this is best-effort with an
-- explicit, loud fallback rather than a hard failure: a migration that cannot run is
-- better than a lookup that silently returns zero rows, and a lookup that silently
-- returns zero rows is better than neither -- but neither is acceptable silently, so
-- every branch announces itself.

DO $$
DECLARE
    v_bypass boolean := false;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dcc_api_key_reader') THEN
        BEGIN
            CREATE ROLE dcc_api_key_reader
                NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
            -- NOBYPASSRLS above, then set the attribute separately so a role created
            -- by an older revision of this migration (without BYPASSRLS) is repaired
            -- by the ATTRIBUTE statement below rather than skipped.
            ALTER ROLE dcc_api_key_reader BYPASSRLS;
        EXCEPTION WHEN OTHERS THEN
            RAISE WARNING
                'dcc.api_keys: could not create role dcc_api_key_reader (% / %). '
                'The pre-tenant lookup will fall back to a table-owner-keyed SELECT policy.',
                SQLSTATE, SQLERRM;
        END;
    END IF;

    SELECT COALESCE(rolbypassrls, false) INTO v_bypass
      FROM pg_roles WHERE rolname = 'dcc_api_key_reader';
    v_bypass := COALESCE(v_bypass, false);

    -- A role that exists but lacks BYPASSRLS is useless here; try to repair it.
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dcc_api_key_reader') AND NOT v_bypass THEN
        BEGIN
            ALTER ROLE dcc_api_key_reader BYPASSRLS;
            v_bypass := true;
        EXCEPTION WHEN OTHERS THEN
            RAISE WARNING 'dcc.api_keys: cannot grant BYPASSRLS to dcc_api_key_reader (%); '
                          'using the fallback lookup policy', SQLERRM;
        END;
    END IF;

    IF v_bypass THEN
        BEGIN
            EXECUTE 'ALTER FUNCTION dcc.lookup_api_key(text)  OWNER TO dcc_api_key_reader';
            EXECUTE 'ALTER FUNCTION dcc.touch_api_key(text)   OWNER TO dcc_api_key_reader';
            EXECUTE 'ALTER FUNCTION dcc.api_key_tenant(uuid)  OWNER TO dcc_api_key_reader';
            EXECUTE 'ALTER FUNCTION dcc.api_key_count()       OWNER TO dcc_api_key_reader';
            -- The definer body runs with this role's privileges, so it needs the
            -- table rights the functions use -- not the application's rights.
            EXECUTE 'GRANT USAGE ON SCHEMA dcc TO dcc_api_key_reader';
            EXECUTE 'GRANT SELECT, UPDATE ON dcc.api_keys TO dcc_api_key_reader';
        EXCEPTION WHEN OTHERS THEN
            v_bypass := false;
            RAISE WARNING 'dcc.api_keys: could not hand the lookup functions to '
                          'dcc_api_key_reader (%); using the fallback lookup policy', SQLERRM;
        END;
    END IF;

    IF v_bypass THEN
        -- Belt and braces: an older revision may have installed the fallback.
        EXECUTE 'DROP POLICY IF EXISTS api_key_authenticate ON dcc.api_keys';
        RAISE NOTICE
            'dcc.api_keys: pre-tenant lookup runs as dcc_api_key_reader (BYPASSRLS); '
            'tenant_scope still governs every direct read and write';
    ELSE
        -- Fallback: admit rows only to a query executing as the owner of the lookup
        -- function. A SECURITY DEFINER call runs as its owner, so the lookup works;
        -- the application role (not the owner, not a member) is still filtered. The
        -- cost is that the table owner can read all rows -- which it could already do
        -- by dropping this policy, so no privilege is created that did not exist.
        -- It IS weaker than the BYPASSRLS path, which keeps the owner constrained by
        -- FORCE, hence the WARNING.
        EXECUTE 'DROP POLICY IF EXISTS api_key_authenticate ON dcc.api_keys';
        EXECUTE $ddl$
            CREATE POLICY api_key_authenticate ON dcc.api_keys
                FOR SELECT
                USING (current_user = (
                    SELECT pg_get_userbyid(p.proowner) FROM pg_proc p
                     WHERE p.oid = 'dcc.lookup_api_key(text)'::regprocedure
                ))
        $ddl$;
        RAISE WARNING
            'dcc.api_keys: installed the FALLBACK pre-tenant lookup policy. '
            'The table owner can now SELECT dcc.api_keys across tenants. '
            'Run this migration as a superuser to get the BYPASSRLS design instead.';
    END IF;
END $$;

COMMIT;
