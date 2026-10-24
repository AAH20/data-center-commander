"""Tenant isolation proven as a role that cannot bypass row-level security.

The gap this closes
-------------------
``database/schema.sql`` gives every tenant table::

    ALTER TABLE dcc.<t> ENABLE  ROW LEVEL SECURITY;
    ALTER TABLE dcc.<t> FORCE   ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON dcc.<t>
      USING      (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid)
      WITH CHECK (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid);

``FORCE`` only removes the *table owner's* exemption. It does nothing to a
SUPERUSER or a role with ``BYPASSRLS`` -- those bypass RLS unconditionally, policy
or no policy. On this machine the database owner (``ahmedhassan``) is both
``usesuper`` and ``rolbypassrls``, so every pre-existing "RLS test" would pass just
as happily against a table with no policy at all. This module therefore connects as
``dcc_rls_probe`` (NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS LOGIN), which the
policy must actually filter.

Run ``scripts/verify_rls_isolation.sh`` first; without that role the module skips
with an explicit reason rather than pretending to have coverage.

What is asserted (all against ``dcc.assets``, which carries the standard
``tenant_scope`` policy):

  1. ``dcc.tenant_id`` = tenant A  -> only tenant A's rows come back.
  2. ``dcc.tenant_id`` unset        -> ZERO rows, never "all rows". The policy's
     ``nullif(..., '')::uuid`` makes the comparison NULL, which is not TRUE.
  3. cross-tenant INSERT (row says tenant B while the setting says A) -> rejected
     by ``WITH CHECK`` with SQLSTATE 42501 and a row-level-security message. A
     same-tenant INSERT is performed as a positive control so the rejection cannot
     be a disguised missing grant.
  4. negative control: with RLS disabled on the table *inside a transaction that is
     rolled back*, the same role sees both tenants -- proving assertion 1 is
     measuring RLS and not an accident of the fixture.
"""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest
from psycopg import errors
from psycopg.conninfo import conninfo_to_dict, make_conninfo

ROLE = os.environ.get("DCC_RLS_PROBE_ROLE", "dcc_rls_probe")
PROBE_PASSWORD = os.environ.get("DCC_RLS_PROBE_PASSWORD", "dcc_rls_probe_local_dev_only")

# Owner DSN: used only to seed a second tenant and to read the ground truth.
ADMIN_DSN = (
    os.environ.get("DCC_OWNER_DATABASE_URL")
    or os.environ.get("DCC_DATABASE_URL")
    or "postgresql://localhost:5432/dcc_demo_local"
)

TENANT_A = uuid.UUID("dcc00000-0000-4000-8000-000000000001")  # seeded demo tenant
TENANT_B = uuid.UUID("dcc00000-0000-4000-8000-0000000000b2")  # synthetic, created here
TENANT_B_SLUG = "rls-probe-tenant-b"
PROBE_NAMESPACE = "rls-probe"


def _probe_dsn() -> str:
    """Same server/database as the owner, different login."""
    params = conninfo_to_dict(ADMIN_DSN)
    params["user"] = ROLE
    params["password"] = PROBE_PASSWORD
    params.setdefault("connect_timeout", "5")
    return make_conninfo(**params)


def _probe_role_state() -> tuple[bool, str]:
    """(usable, reason) measured against the live cluster, at import time."""
    try:
        with psycopg.connect(ADMIN_DSN, connect_timeout=5) as conn:
            row = conn.execute(
                "SELECT rolsuper, rolbypassrls, rolcanlogin FROM pg_roles WHERE rolname = %s",
                (ROLE,),
            ).fetchone()
    except Exception as exc:  # noqa: BLE001 - any connect failure means "cannot prove it"
        return False, f"cannot reach {ADMIN_DSN!r} to inspect role {ROLE!r}: {exc}"

    if row is None:
        return False, (
            f"role {ROLE!r} does not exist: run scripts/verify_rls_isolation.sh first "
            "-- only a NOSUPERUSER NOBYPASSRLS login role can prove the tenant_scope "
            "policy is enforced, because a superuser ignores RLS even under FORCE"
        )
    rolsuper, rolbypassrls, rolcanlogin = row
    if rolsuper or rolbypassrls:
        return False, (
            f"role {ROLE!r} has rolsuper={rolsuper} rolbypassrls={rolbypassrls}, so it "
            "ignores row-level security: recreate it with "
            "scripts/verify_rls_isolation.sh first"
        )
    if not rolcanlogin:
        return False, (
            f"role {ROLE!r} cannot log in: recreate it with scripts/verify_rls_isolation.sh first"
        )
    return True, ""


_PROBE_USABLE, _SKIP_REASON = _probe_role_state()

pytestmark = pytest.mark.skipif(
    not _PROBE_USABLE,
    reason=_SKIP_REASON or "RLS probe role unavailable",
)


@pytest.fixture(scope="module")
def owner():
    """Owner/superuser connection -- ground truth and fixture setup only."""
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        yield conn


@pytest.fixture()
def probe():
    """A real login as the unprivileged role. Fresh per test, so no GUC leaks."""
    with psycopg.connect(_probe_dsn(), autocommit=True) as conn:
        yield conn


@pytest.fixture(scope="module")
def fixtures(owner):
    """Guarantee two tenants hold assets, then remove only the synthetic one.

    The demo seed has assets for TENANT_A only, and a one-tenant table cannot
    demonstrate isolation. Tenant B's asset is written AS THE OWNER, which is the
    only way to plant a row the probe must not be able to see.
    """
    existing = owner.execute("SELECT slug FROM dcc.tenants WHERE id = %s", (TENANT_B,)).fetchone()
    if existing is not None and existing[0] != TENANT_B_SLUG:
        pytest.fail(
            f"refusing to touch tenant {TENANT_B}: it exists with slug {existing[0]!r}, "
            f"not the probe fixture slug {TENANT_B_SLUG!r}"
        )

    owner.execute("DELETE FROM dcc.tenants WHERE id = %s", (TENANT_B,))  # cascades to assets
    owner.execute(
        "INSERT INTO dcc.tenants (id, slug, name, status) VALUES (%s, %s, %s, 'active')",
        (TENANT_B, TENANT_B_SLUG, "RLS probe tenant B (synthetic)"),
    )
    owner.execute(
        """
        INSERT INTO dcc.assets (tenant_id, external_id, source_namespace, asset_type, name)
        VALUES (%s, 'probe-b-1', %s, 'synthetic', 'RLS probe tenant B asset')
        ON CONFLICT (tenant_id, source_namespace, external_id) DO NOTHING
        """,
        (TENANT_B, PROBE_NAMESPACE),
    )

    counts = dict(
        owner.execute(
            "SELECT tenant_id, count(*) FROM dcc.assets WHERE tenant_id IN (%s, %s) GROUP BY 1",
            (TENANT_A, TENANT_B),
        ).fetchall()
    )
    if not counts.get(TENANT_A):
        pytest.fail(
            f"tenant A ({TENANT_A}) has no rows in dcc.assets: seed the demo database "
            "with scripts/db-seed-demo.sh before running the RLS isolation proofs"
        )
    if not counts.get(TENANT_B):
        pytest.fail("failed to plant the tenant B asset required for the isolation proofs")

    table = owner.execute(
        "SELECT relrowsecurity, relforcerowsecurity, pg_get_userbyid(relowner)::text "
        "FROM pg_class WHERE oid = 'dcc.assets'::regclass"
    ).fetchone()
    try:
        yield {"count_a": counts[TENANT_A], "count_b": counts[TENANT_B], "table": table}
    finally:
        # Only our synthetic tenant; the demo tenant is never touched.
        owner.execute("DELETE FROM dcc.tenants WHERE id = %s AND slug = %s", (TENANT_B, TENANT_B_SLUG))


def test_probe_role_is_really_restricted(probe, fixtures):
    """The measuring instrument itself: not superuser, not BYPASSRLS, not the owner."""
    current_user, usesuper, rolbypassrls = probe.execute(
        "SELECT current_user,"
        "       (SELECT usesuper FROM pg_user WHERE usename = current_user),"
        "       (SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user)"
    ).fetchone()
    print(
        f"\n[probe connection] current_user={current_user} "
        f"usesuper={usesuper} rolbypassrls={rolbypassrls}"
    )

    assert current_user == ROLE, f"connected as {current_user!r}, not {ROLE!r}"
    assert usesuper is False, "a superuser bypasses RLS entirely -- this proves nothing"
    assert rolbypassrls is False, "BYPASSRLS bypasses every policy -- this proves nothing"

    rls_enabled, rls_forced, table_owner = fixtures["table"]
    print(
        f"[dcc.assets] relrowsecurity={rls_enabled} "
        f"relforcerowsecurity={rls_forced} owner={table_owner}"
    )
    assert rls_enabled is True, "RLS is not enabled on dcc.assets"
    assert rls_forced is True, "FORCE ROW LEVEL SECURITY is off on dcc.assets"
    assert table_owner != ROLE, "the probe must not own the table it is measuring"


def test_tenant_a_setting_returns_only_tenant_a_rows(probe, owner, fixtures):
    """(a) A tenant-scoped SELECT returns tenant A's rows and nothing else."""
    probe.execute("SELECT set_config('dcc.tenant_id', %s, false)", (str(TENANT_A),))

    visible = probe.execute("SELECT count(*) FROM dcc.assets").fetchone()[0]
    tenants_seen = probe.execute("SELECT DISTINCT tenant_id FROM dcc.assets").fetchall()
    total = owner.execute("SELECT count(*) FROM dcc.assets").fetchone()[0]
    a_count = owner.execute(
        "SELECT count(*) FROM dcc.assets WHERE tenant_id = %s", (TENANT_A,)
    ).fetchone()[0]

    print(
        f"\n[tenant A set] probe sees {visible} row(s) across "
        f"{[str(t[0]) for t in tenants_seen]}; owner sees {total} total ({a_count} for A)"
    )

    assert [t[0] for t in tenants_seen] == [TENANT_A], (
        f"probe saw rows belonging to {[str(t[0]) for t in tenants_seen]}"
    )
    assert visible == a_count, f"probe saw {visible} rows but tenant A owns {a_count}"
    assert visible < total, "probe saw every row, so no filtering happened at all"


def test_unset_tenant_setting_returns_no_rows(probe, owner, fixtures):
    """(b) An unbound tenant context must fail closed: zero rows, never all rows."""
    setting = probe.execute("SELECT current_setting('dcc.tenant_id', true)").fetchone()[0]
    visible = probe.execute("SELECT count(*) FROM dcc.assets").fetchone()[0]
    total = owner.execute("SELECT count(*) FROM dcc.assets").fetchone()[0]

    print(f"\n[dcc.tenant_id unset] setting={setting!r} probe sees {visible}; owner sees {total}")

    assert setting in (None, ""), f"tenant context leaked into this session: {setting!r}"
    assert total > 0, "fixture problem: the table is empty, so zero rows proves nothing"
    assert visible == 0, f"unbound tenant context returned {visible} of {total} rows"


def test_cross_tenant_insert_is_rejected(probe, owner, fixtures):
    """(c) WITH CHECK rejects a write that carries another tenant's id."""
    probe.execute("SELECT set_config('dcc.tenant_id', %s, false)", (str(TENANT_A),))

    with pytest.raises(errors.InsufficientPrivilege) as excinfo:
        probe.execute(
            """
            INSERT INTO dcc.assets (tenant_id, external_id, source_namespace, asset_type, name)
            VALUES (%s, 'probe-cross-tenant', %s, 'synthetic', 'cross tenant write')
            """,
            (TENANT_B, PROBE_NAMESPACE),
        )
    print(f"\n[cross-tenant INSERT] rejected: sqlstate={excinfo.value.sqlstate} {excinfo.value}")
    assert excinfo.value.sqlstate == "42501"
    assert "row-level security" in str(excinfo.value).lower(), (
        "rejected, but not by the policy: " + str(excinfo.value)
    )

    assert (
        owner.execute(
            "SELECT count(*) FROM dcc.assets WHERE tenant_id = %s AND external_id = 'probe-cross-tenant'",
            (TENANT_B,),
        ).fetchone()[0]
        == 0
    ), "the rejected row was written anyway"

    # Positive control: the identical statement with tenant A must succeed, which is
    # what distinguishes "policy said no" from "the role has no INSERT privilege".
    try:
        probe.execute(
            """
            INSERT INTO dcc.assets (tenant_id, external_id, source_namespace, asset_type, name)
            VALUES (%s, 'probe-same-tenant', %s, 'synthetic', 'same tenant write')
            """,
            (TENANT_A, PROBE_NAMESPACE),
        )
        written = owner.execute(
            "SELECT count(*) FROM dcc.assets WHERE tenant_id = %s AND external_id = 'probe-same-tenant'",
            (TENANT_A,),
        ).fetchone()[0]
        print(f"[same-tenant INSERT as control] accepted, owner sees {written} row(s)")
        assert written == 1, "INSERT privilege is missing, so the rejection above was not RLS"
    finally:
        owner.execute(
            "DELETE FROM dcc.assets WHERE source_namespace = %s AND external_id = %s",
            (PROBE_NAMESPACE, "probe-same-tenant"),
        )


def test_negative_control_disabling_rls_leaks_cross_tenant_rows(owner, fixtures):
    """If RLS is off, the probe sees both tenants -- so test (a) really measures RLS.

    The ALTER runs inside an explicit transaction that is always rolled back; the
    table's RLS state is re-measured afterwards to prove nothing persisted.
    """
    total = owner.execute("SELECT count(*) FROM dcc.assets").fetchone()[0]
    a_count = owner.execute(
        "SELECT count(*) FROM dcc.assets WHERE tenant_id = %s", (TENANT_A,)
    ).fetchone()[0]
    assert a_count < total, "fixture problem: one tenant holds every row, nothing to leak"

    leaked = tenants_seen = None
    try:
        owner.execute("BEGIN")
        owner.execute("ALTER TABLE dcc.assets DISABLE ROW LEVEL SECURITY")
        owner.execute(f'SET LOCAL ROLE "{ROLE}"')
        owner.execute("SELECT set_config('dcc.tenant_id', %s, true)", (str(TENANT_A),))
        leaked = owner.execute("SELECT count(*) FROM dcc.assets").fetchone()[0]
        tenants_seen = owner.execute("SELECT count(DISTINCT tenant_id) FROM dcc.assets").fetchone()[0]
    finally:
        owner.execute("ROLLBACK")
        owner.execute("RESET ROLE")  # SET LOCAL reverts on ROLLBACK; belt and braces

    print(
        f"\n[negative control] RLS disabled inside a rolled-back txn: role {ROLE} "
        f"with tenant A set saw {leaked}/{total} rows across {tenants_seen} tenant(s)"
    )

    assert leaked == total, (
        "negative control failed: disabling RLS did not widen the visible set, so the "
        "isolation assertions are not measuring row-level security"
    )
    assert tenants_seen == 2

    enabled, forced = owner.execute(
        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = 'dcc.assets'::regclass"
    ).fetchone()
    assert (enabled, forced) == (True, True), "the negative control leaked DDL out of its transaction"


def test_every_tenant_table_has_rls_and_a_policy(owner):
    """No tenant-scoped relation may rely on the absence of a writer for its isolation.

    This was an xfail while 13 relations (the partitioned telemetry parent and its twelve
    monthly partitions) carried no RLS at all. The gap was latent because those partitions
    held no rows, which is exactly why it was worth pinning: the leak appears the moment
    something writes to them, and nothing in the suite would have moved.

    Migration 010 closed it. The assertion is now unconditional, and checks FORCE as well
    as ENABLE -- a table with RLS enabled but not forced is bypassed by its owner, which is
    the configuration a superuser-bound deployment would silently accept.
    """
    rows = owner.execute(
        """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
               EXISTS (SELECT 1 FROM pg_policies p
                        WHERE p.schemaname = 'dcc' AND p.tablename = c.relname) AS has_policy
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'dcc' AND c.relkind IN ('r', 'p')
          AND EXISTS (SELECT 1 FROM information_schema.columns col
                       WHERE col.table_schema = 'dcc' AND col.table_name = c.relname
                         AND col.column_name = 'tenant_id')
        ORDER BY c.relname
        """
    ).fetchall()

    unprotected = [r[0] for r in rows if not r[1] or not r[3]]
    unforced = [r[0] for r in rows if r[1] and not r[2]]

    assert not unprotected, f"{len(unprotected)} tenant table(s) have no RLS or no policy: {unprotected}"
    assert not unforced, (
        f"{len(unforced)} tenant table(s) have RLS enabled but not FORCEd, so the owner "
        f"bypasses the policy: {unforced}"
    )
    assert len(rows) >= 40, f"only {len(rows)} tenant tables found; the query is probably wrong"
