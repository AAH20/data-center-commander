-- ---------------------------------------------------------------------------
-- Backup run persistence.
--
-- dcc/operations/backup.py (~1,660 lines) is a working backup engine: it shells
-- out to a real pg_dump, writes a metadata document and a data file per backup,
-- and can verify a backup against its recorded checksum. None of it was reachable
-- from the API, so the product could not take, list or verify a backup over HTTP --
-- the capability existed and nothing could call it.
--
-- This table is the durable record of what backups exist. The bytes and the
-- metadata document stay on the backup volume, where the engine already puts them;
-- duplicating file paths into the database would let the two disagree about which
-- backup a row describes. What this table holds is the operator-visible state:
-- which run, for which tenant, of what type, in what status, with which checksum.
--
-- checksum            -- what the engine recorded when it wrote the backup.
-- checksum_observed   -- what an out-of-band verification pass computed from the
--                        file on disk. NULL means "not yet verified", which is NOT
--                        the same as "verified and matching". The verify endpoint
--                        reports null rather than true in that case, because a
--                        missing check is not a passing check. The CHECK constraint
--                        below refuses a row that claims status 'verified' without
--                        an observed checksum, so the two cannot drift apart.
--
-- RLS matches the convention used by every other tenant table in this schema:
-- ENABLE + FORCE, with a tenant_scope policy reading dcc.tenant_id. FORCE matters:
-- without it the table owner bypasses the policy and a bug in tenant binding shows
-- up only in production.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dcc.backup_runs (
    run_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid NOT NULL REFERENCES dcc.tenants(id) ON DELETE CASCADE,
    -- The engine generates backup ids with uuid4(), and validate_backup_id()
    -- rejects anything that is not a UUID, so this column is uuid rather than text.
    backup_id         uuid NOT NULL,
    backup_type       text NOT NULL DEFAULT 'full'
                      CHECK (backup_type IN ('full','incremental','differential')),
    status            text NOT NULL DEFAULT 'completed'
                      CHECK (status IN ('pending','running','completed','failed','verified','expired','deleted')),
    compression       text NOT NULL DEFAULT 'none'
                      CHECK (compression IN ('none','gzip')),
    -- Who asked for this run. 'api' rows were recorded through the endpoint,
    -- 'scheduler' and 'engine' rows are written by the worker that actually ran
    -- pg_dump. The distinction is how an operator tells a recorded intent from a
    -- reported result.
    source            text NOT NULL DEFAULT 'api'
                      CHECK (source IN ('api','scheduler','engine')),
    size_bytes        bigint NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
    checksum          text NOT NULL DEFAULT '',
    checksum_observed text,
    verified_at       timestamptz,
    parent_backup_id  uuid,
    wal_start         text,
    wal_end           text,
    point_in_time     timestamptz,
    error_message     text NOT NULL DEFAULT '',
    tags              jsonb NOT NULL DEFAULT '{}',
    metadata          jsonb NOT NULL DEFAULT '{}',
    started_at        timestamptz,
    completed_at      timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, backup_id),
    -- A run cannot be 'verified' without an independent checksum. This is the
    -- constraint that stops the API from being able to assert a verification it
    -- did not perform.
    CONSTRAINT backup_runs_verified_needs_observed
        CHECK (status <> 'verified' OR checksum_observed IS NOT NULL),
    CONSTRAINT backup_runs_observed_needs_timestamp
        CHECK (checksum_observed IS NULL OR verified_at IS NOT NULL)
);

-- "Show me this tenant's recent backups" is the list endpoint's only access path.
CREATE INDEX IF NOT EXISTS backup_runs_tenant_time_idx
    ON dcc.backup_runs (tenant_id, created_at DESC);

-- --- row level security -----------------------------------------------------
DO $$
DECLARE
    t record;
BEGIN
    FOR t IN
        SELECT c.relname AS table_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'dcc'
          AND c.relname IN ('backup_runs')
    LOOP
        EXECUTE format('ALTER TABLE dcc.%I ENABLE ROW LEVEL SECURITY', t.table_name);
        EXECUTE format('ALTER TABLE dcc.%I FORCE ROW LEVEL SECURITY', t.table_name);
        EXECUTE format('DROP POLICY IF EXISTS tenant_scope ON dcc.%I', t.table_name);
        EXECUTE format(
            'CREATE POLICY tenant_scope ON dcc.%I USING (tenant_id = nullif(current_setting(''dcc.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id = nullif(current_setting(''dcc.tenant_id'',true),'''')::uuid)',
            t.table_name
        );
    END LOOP;
END $$;

COMMENT ON TABLE dcc.backup_runs IS
    'Durable record of backup runs per tenant. Backup bytes and metadata documents '
    'stay on the backup volume; this table records operator-visible state only. '
    'Execution is never driven from an HTTP request.';
COMMENT ON COLUMN dcc.backup_runs.checksum IS
    'Checksum recorded by the engine when the backup was written.';
COMMENT ON COLUMN dcc.backup_runs.checksum_observed IS
    'Checksum computed by an out-of-band verification pass. NULL means unverified, '
    'which must not be reported as a match.';
