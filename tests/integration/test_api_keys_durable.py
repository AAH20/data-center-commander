"""The API key store against a real PostgreSQL database.

What this suite is for
----------------------
``ApiKeyStore`` was a dict. Two consequences that no unit test could see:

  1. every restart destroyed every key, and
  2. **every uvicorn worker had its own dict**, so a key minted by worker 1 was
     unknown to worker 2 and roughly one request in N came back 401 for no reason.

The headline test below, ``test_key_created_in_one_store_is_verified_by_a_second_store``,
is that defect in one assertion: two independently constructed stores -- each with its
own connection pool, like two worker processes -- and a key that only exists in the
database. It fails against the old implementation by construction, because the old one
had nowhere to put the key.

The rest of the module covers the parts that only a database can demonstrate: RLS is
still in force on the table, the pre-tenant lookup works for a role that RLS actually
filters, revocation and expiry are enforced from a second process, ``last_used_at``
advances, and the raw key is nowhere in the database.

Requires ``DCC_DATABASE_URL`` pointing at a database with ``database/schema.sql`` and
migrations 001-011 applied. The fixtures create and drop their own tenant, so the
database needs no seed data.

Run::

    DCC_DATABASE_URL=postgresql://localhost:5432/dcc_demo_local \\
        pytest tests/integration/test_api_keys_durable.py -v
"""

from __future__ import annotations

import os
import time
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

from dcc.security.api_keys import (  # noqa: E402
    ApiKeyExpiredError,
    ApiKeyInvalidError,
    ApiKeyRevokedError,
    ApiKeyStore,
    generate_api_key,
    hash_api_key,
)

DSN = os.environ.get("DCC_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not DSN,
    reason=(
        "DCC_DATABASE_URL is not set: there is no database to prove durability, "
        "cross-process sharing or RLS behaviour against. Point it at a database with "
        "database/schema.sql plus migrations 001-011 applied."
    ),
)

#: NOLOGIN role used to prove the lookup works for a role RLS actually filters.
PROBE_ROLE = "dcc_api_keys_probe"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tenant_id():
    """A tenant of our own, removed at the end (API keys cascade with it)."""
    owner = uuid.uuid4()
    tenant = str(uuid.uuid4())
    with psycopg.connect(DSN) as conn:
        conn.execute(
            "INSERT INTO dcc.tenants (id, slug, name) VALUES (%s, %s, %s)",
            (tenant, f"api-key-test-{str(owner)[:8]}", "API key durability test"),
        )
    try:
        yield tenant
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute("DELETE FROM dcc.tenants WHERE id = %s", (tenant,))
            conn.commit()


@pytest.fixture()
def store(tenant_id):
    """The first store instance ("worker 1")."""
    instance = ApiKeyStore(DSN)
    assert instance.backend == "postgres", "DCC_DATABASE_URL did not select the durable backend"
    try:
        yield instance
    finally:
        instance.close()


@pytest.fixture()
def other_store():
    """A SECOND, independent store ("worker 2"): its own pool, own process state."""
    instance = ApiKeyStore(DSN)
    try:
        yield instance
    finally:
        instance.close()


def _row_for(digest):
    with psycopg.connect(DSN) as conn:
        return conn.execute(
            "SELECT id, tenant_id, key_hash, label, scopes, created_at, created_by, "
            "expires_at, revoked_at, last_used_at "
            "FROM dcc.api_keys WHERE key_hash = %s",
            (digest,),
        ).fetchone()


def _wait_for(predicate, timeout=5.0, interval=0.05):
    """Poll until ``predicate()`` is truthy. Returns the last value either way."""
    deadline = time.time() + timeout
    value = predicate()
    while not value and time.time() < deadline:
        time.sleep(interval)
        value = predicate()
    return value


# ---------------------------------------------------------------------------
# The defect: a key issued by one process must be valid in another
# ---------------------------------------------------------------------------


class TestCrossProcessDurability:
    def test_key_created_in_one_store_is_verified_by_a_second_store(
        self, store, other_store, tenant_id
    ):
        """THE headline test.

        A key minted through one store instance, with its own connection pool, must
        authenticate against a second instance that has never seen it. This is exactly
        what two uvicorn workers do, and exactly what the in-memory dict could not do:
        it returned 401 for any request that landed on the other worker.
        """
        raw, record = store.create(name="shared", tenant_id=tenant_id, scopes=["read"])

        # The second store knows nothing in-process. If it can verify the key, the
        # answer came from the database and nowhere else.
        assert other_store._hash_to_id == {}
        assert other_store._keys == {}

        verified = other_store.verify(raw)

        assert verified.tenant_id == tenant_id
        assert verified.id == record.id
        assert verified.scopes == ["read"]

    def test_a_key_survives_a_store_that_is_closed_and_reopened(self, tenant_id):
        """The restart case: the process goes away, the key does not."""
        first = ApiKeyStore(DSN)
        raw, record = first.create(name="restart", tenant_id=tenant_id)
        first.close()

        second = ApiKeyStore(DSN)
        try:
            assert second.verify(raw).id == record.id
        finally:
            second.close()

    def test_a_key_registered_from_configuration_is_durable(self, tenant_id):
        """The DCC_API_KEYS bootstrap path must also land in the database."""
        raw = generate_api_key()
        digest = hash_api_key(raw)

        first = ApiKeyStore(DSN)
        try:
            first.register_hash(tenant_id=tenant_id, key_hash=digest, name="bootstrap")
            # Registration is replayed on every process start; it must be idempotent.
            again = first.register_hash(tenant_id=tenant_id, key_hash=digest)
            assert again.key_hash == digest
        finally:
            first.close()

        second = ApiKeyStore(DSN)
        try:
            verified = second.verify(raw)
            assert verified.tenant_id == tenant_id
            assert verified.name == "bootstrap"
        finally:
            second.close()

    def test_registration_does_not_revive_a_revoked_key(self, tenant_id):
        """A restart replays DCC_API_KEYS. That must not resurrect a revoked key."""
        raw = generate_api_key()
        digest = hash_api_key(raw)

        first = ApiKeyStore(DSN)
        try:
            record = first.register_hash(tenant_id=tenant_id, key_hash=digest)
            assert first.revoke(record.id) is True
        finally:
            first.close()

        second = ApiKeyStore(DSN)
        try:
            second.register_hash(tenant_id=tenant_id, key_hash=digest)
            with pytest.raises(ApiKeyRevokedError):
                second.verify(raw)
        finally:
            second.close()


# ---------------------------------------------------------------------------
# Enforcement, from the other side of a process boundary
# ---------------------------------------------------------------------------


class TestEnforcementAcrossProcesses:
    def test_revocation_in_one_store_is_seen_by_another(
        self, store, other_store, tenant_id
    ):
        """Revocation must be authoritative immediately, not per-process."""
        raw, record = store.create(name="to-revoke", tenant_id=tenant_id)
        assert other_store.verify(raw) is not None

        assert store.revoke(record.id) is True

        with pytest.raises(ApiKeyRevokedError):
            other_store.verify(raw)

    def test_expired_key_is_rejected(self, store, other_store, tenant_id):
        raw, _ = store.create(
            name="expired", tenant_id=tenant_id, expires_at=time.time() - 60
        )
        with pytest.raises(ApiKeyExpiredError):
            other_store.verify(raw)

    def test_key_with_a_future_expiry_is_accepted(self, store, other_store, tenant_id):
        raw, _ = store.create(
            name="still-valid", tenant_id=tenant_id, expires_at=time.time() + 3600
        )
        assert other_store.verify(raw).tenant_id == tenant_id

    def test_unknown_key_is_rejected(self, other_store):
        with pytest.raises(ApiKeyInvalidError):
            other_store.verify(generate_api_key())

    def test_deleted_key_stops_working(self, store, other_store, tenant_id):
        raw, record = store.create(name="to-delete", tenant_id=tenant_id)
        assert store.delete(record.id) is True
        with pytest.raises(ApiKeyInvalidError):
            other_store.verify(raw)

    def test_deleting_a_missing_key_reports_false(self, store):
        assert store.delete(str(uuid.uuid4())) is False


# ---------------------------------------------------------------------------
# The audit trail
# ---------------------------------------------------------------------------


class TestAuditTrail:
    def test_who_issued_the_key_is_recorded(self, store, tenant_id):
        _, record = store.create(
            name="attributed", tenant_id=tenant_id, created_by="ops@example.test"
        )
        row = _row_for(record.key_hash)

        assert row[6] == "ops@example.test", "created_by was not persisted"
        assert row[5] is not None, "created_at was not persisted"
        assert row[3] == "attributed", "label was not persisted"

    def test_last_used_at_advances_after_verification(self, store, other_store, tenant_id):
        raw, record = store.create(name="used", tenant_id=tenant_id)
        assert _row_for(record.key_hash)[9] is None

        other_store.verify(raw)

        # The write is deliberately asynchronous and best effort, so poll rather than
        # assert synchronously -- a synchronous write is the design that was rejected.
        stamp = _wait_for(lambda: _row_for(record.key_hash)[9])
        assert stamp is not None, "verification did not record last_used_at"

    def test_verification_succeeds_when_the_audit_write_fails(
        self, store, tenant_id, monkeypatch
    ):
        """An audit failure must never turn into a 401 for a valid key."""
        raw, _ = store.create(name="audit-broken", tenant_id=tenant_id)

        def explode(_digest):
            raise RuntimeError("last_used_at update failed")

        monkeypatch.setattr(store._backend, "touch", explode)

        assert store.verify(raw).tenant_id == tenant_id
        time.sleep(0.2)  # let the background thread swallow the failure

    def test_raw_key_is_never_persisted(self, store, tenant_id):
        raw, record = store.create(name="no-secret", tenant_id=tenant_id)
        row = _row_for(record.key_hash)

        assert row[2] == hash_api_key(raw)
        assert raw not in repr(row), "the raw key leaked into a database column"
        assert all(raw != value for value in row)

    def test_scopes_round_trip_through_the_database(self, store, other_store, tenant_id):
        raw, _ = store.create(
            name="scoped", tenant_id=tenant_id, scopes=["read", "write"]
        )
        assert _row_for(hash_api_key(raw))[4] == ["read", "write"]
        assert other_store.verify(raw).scopes == ["read", "write"]


# ---------------------------------------------------------------------------
# Listing and counting under RLS
# ---------------------------------------------------------------------------


class TestListing:
    def test_list_keys_is_scoped_to_its_tenant(self, store, tenant_id):
        store.create(name="listed", tenant_id=tenant_id)
        rows = store.list_keys(tenant_id)
        assert rows, "the tenant's own keys should be listed"
        assert {r.tenant_id for r in rows} == {tenant_id}

    def test_listing_another_tenant_returns_nothing(self, store):
        assert store.list_keys(str(uuid.uuid4())) == []

    def test_count_sees_the_store_as_a_whole(self, store, tenant_id):
        """The lockout guard's question: is the store empty?

        Answered without a tenant, which ``list_keys()`` cannot do under FORCE RLS.
        """
        before = store.count()
        store.create(name="counted", tenant_id=tenant_id)
        assert store.count() == before + 1


# ---------------------------------------------------------------------------
# The migration actually did what it claims
# ---------------------------------------------------------------------------


class TestMigrationInvariants:
    def test_rls_is_enabled_and_forced(self):
        with psycopg.connect(DSN) as conn:
            row = conn.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE oid = 'dcc.api_keys'::regclass"
            ).fetchone()
        assert row == (True, True), (
            "dcc.api_keys must have ENABLE + FORCE row level security; without FORCE "
            "the table owner silently sees every tenant"
        )

    def test_tenant_scope_policy_matches_the_schema_convention(self):
        with psycopg.connect(DSN) as conn:
            row = conn.execute(
                "SELECT qual, with_check FROM pg_policies "
                "WHERE schemaname = 'dcc' AND tablename = 'api_keys' "
                "AND policyname = 'tenant_scope'"
            ).fetchone()
        assert row is not None, "the tenant_scope policy is missing"
        qual, with_check = row
        assert "dcc.tenant_id" in qual and "tenant_id" in qual
        assert with_check and "dcc.tenant_id" in with_check

    def test_lookup_function_is_security_definer_with_a_pinned_search_path(self):
        with psycopg.connect(DSN) as conn:
            rows = conn.execute(
                "SELECT proname, prosecdef, proconfig FROM pg_proc "
                "WHERE proname IN ('lookup_api_key','touch_api_key','api_key_tenant',"
                "'api_key_count')"
            ).fetchall()
        assert len(rows) == 4, f"expected four helper functions, found {len(rows)}"
        for name, secdef, config in rows:
            assert secdef is True, f"{name} must be SECURITY DEFINER"
            assert config and any("search_path" in c for c in config), (
                f"{name} must pin search_path; a definer function that inherits the "
                "caller's path can be tricked into reading a shadow table"
            )

    def test_the_lookup_runs_as_a_role_that_cannot_log_in(self):
        """The bypass must belong to a role nobody can authenticate as."""
        with psycopg.connect(DSN) as conn:
            row = conn.execute(
                "SELECT r.rolcanlogin, r.rolsuper, r.rolbypassrls "
                "FROM pg_proc p JOIN pg_roles r ON r.oid = p.proowner "
                "WHERE p.oid = 'dcc.lookup_api_key(text)'::regprocedure"
            ).fetchone()
        assert row is not None
        can_login, is_super, bypasses = row
        assert is_super is False
        assert can_login is False, "the definer owner must not be a login role"
        # Either the owner bypasses RLS (the BYPASSRLS design) or the fallback policy
        # is in place; both leave tenant_scope governing direct access. Asserting the
        # stronger one here documents which design this database actually got.
        assert bypasses is True, (
            "the lookup function is not owned by a BYPASSRLS role: migration 011 took "
            "the fallback path, which lets the table owner read across tenants"
        )

    def test_a_role_that_rls_filters_cannot_list_keys_but_can_authenticate(
        self, store, tenant_id
    ):
        """The whole point of the SECURITY DEFINER lookup, measured.

        A NOLOGIN, NOSUPERUSER, NOBYPASSRLS role sees ZERO rows in dcc.api_keys with no
        tenant bound -- that is tenant_scope working -- and yet the pre-tenant lookup
        returns the row, because authentication cannot have a tenant yet.

        Skipped, with a reason, when this database is not reached as a superuser: only a
        superuser can provision the probe role, and a half-provisioned role would make
        the assertions meaningless rather than false.
        """
        with psycopg.connect(DSN) as admin:
            is_super = admin.execute(
                "SELECT usesuper FROM pg_user WHERE usename = current_user"
            ).fetchone()[0]
            if not is_super:
                pytest.skip(
                    "provisioning a NOSUPERUSER probe role needs a superuser DSN; "
                    "this database is reached as a non-superuser"
                )
            admin.execute(
                f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
                f"'{PROBE_ROLE}') THEN CREATE ROLE {PROBE_ROLE} NOLOGIN NOSUPERUSER "
                f"NOBYPASSRLS; END IF; END $$;"
            )
            admin.execute(f"GRANT USAGE ON SCHEMA dcc TO {PROBE_ROLE}")
            admin.execute(f"GRANT SELECT ON dcc.api_keys TO {PROBE_ROLE}")
            admin.commit()

        raw, record = store.create(name="probe-target", tenant_id=tenant_id)
        digest = hash_api_key(raw)

        with psycopg.connect(DSN) as conn:
            with conn.transaction(force_rollback=True):
                conn.execute(f"SET LOCAL ROLE {PROBE_ROLE}")
                visible = conn.execute("SELECT count(*) FROM dcc.api_keys").fetchone()[0]
                assert visible == 0, (
                    "a NOBYPASSRLS role with no dcc.tenant_id set must see zero rows; "
                    f"it saw {visible}"
                )
                found = conn.execute(
                    "SELECT tenant_id, key_hash FROM dcc.lookup_api_key(%s)", (digest,)
                ).fetchone()
                assert found is not None, (
                    "the pre-tenant lookup returned nothing for a role RLS filters, so "
                    "authentication is impossible for the application role"
                )
                assert str(found[0]) == tenant_id
                assert found[1] == digest

    def test_the_table_cannot_hold_a_non_digest(self, tenant_id):
        """Defence against storing a raw key by accident."""
        with pytest.raises(psycopg.errors.CheckViolation):
            with psycopg.connect(DSN) as conn:
                conn.execute(
                    "INSERT INTO dcc.api_keys (tenant_id, key_hash) VALUES (%s, %s)",
                    (tenant_id, "dcc_" + "a" * 60),
                )
