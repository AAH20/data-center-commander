"""/readyz says whether tenant row-level security is enforced, and a database error is counted.

Two controls that could not act, and what these tests pin.

**1. The RLS panel read 0 forever.** ``monitoring/grafana/dashboards/dcc-dashboard.json``
has a "Tenant RLS" panel fed by ``dcc_database_rls_ok``, which the exporter derives from
``/readyz`` -> ``checks.tenant_rls``. That key did not exist: the probe reported only
``database`` and ``schema``, so ``checks.get("tenant_rls") == "ok"`` was never true. An
always-zero panel is indistinguishable from "row-level security is off everywhere", which
is the state it is supposed to detect. The probe now assesses the catalog and reports
``ok`` / ``missing`` (with counts) / ``not_assessed``.

**2. ``DCCDatabaseUnavailable`` was commented out** for lack of a counter. It now sits on
``api_database_errors_total{operation}``, incremented from two real request-path sites
(an escaped driver error, and a failed readiness probe). A counter nothing increments is
worse than the comment it replaced, so these tests force both failures and assert the
counter moves -- and that it does *not* move for a healthy request or for a 500 that came
from something other than the database.

The RLS tests run against the real local database and toggle the flag inside a
``force_rollback`` transaction: the catalog is genuinely changed for the duration of the
check, and genuinely restored afterwards, without altering the committed schema.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

import dcc.api_async as api
from dcc.api_async import app

TENANT = "dcc00000-0000-4000-8000-000000000001"
OVERVIEW = f"/v2/overview?tenant_id={TENANT}"
DSN = os.environ.get("DCC_TEST_DATABASE_URL") or "postgresql://localhost:5432/dcc_demo_local"
COUNTER = "api_database_errors_total"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _counter(client: TestClient) -> float:
    """Total of every api_database_errors_total series, whatever the label set."""
    body = client.get("/metrics").text
    return sum(float(v) for v in re.findall(rf"{COUNTER}\{{[^}}]*\}}\s+([0-9.]+)", body))


def _operations(client: TestClient) -> set[str]:
    body = client.get("/metrics").text
    return set(re.findall(rf'{COUNTER}\{{operation="([^"]+)"\}}', body))


class _FakeConn:
    """Just enough of a connection for readyz: schema row, RLS catalog, no network."""

    def __init__(self, *, schema_ok: bool = True, rls_raises: bool = False) -> None:
        self._schema_ok = schema_ok
        self._rls_raises = rls_raises

    async def execute(self, sql: str, *params: Any) -> int:
        return 0

    def transaction(self) -> Any:
        @asynccontextmanager
        async def _tx() -> AsyncIterator[None]:
            yield

        return _tx()

    async def fetchrow(self, sql: str, *params: Any) -> dict[str, Any]:
        return {"tenants": True, "assets": self._schema_ok}

    async def fetch(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        if self._rls_raises:
            import psycopg

            raise psycopg.OperationalError("catalog read failed")
        return [
            {"table_name": "assets", "rls_enabled": True, "rls_forced": True},
            {"table_name": "telemetry_readings", "rls_enabled": True, "rls_forced": True},
        ]


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def connection(self) -> Any:
        @asynccontextmanager
        async def _ctx() -> AsyncIterator[_FakeConn]:
            yield self._conn

        return _ctx()


def _install_pool(monkeypatch: pytest.MonkeyPatch, conn: _FakeConn) -> None:
    pool = _FakePool(conn)

    async def _get_pool() -> _FakePool:
        return pool

    monkeypatch.setattr(api, "get_pool", _get_pool)


def _install_pool_failure(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    async def _get_pool() -> Any:
        raise exc

    monkeypatch.setattr(api, "get_pool", _get_pool)


@pytest.fixture()
def client() -> TestClient:
    api._METRICS.reset()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _no_cached_route_responses() -> None:
    """Force the overview route to actually reach the database.

    /v2/overview answers from a process-wide cache keyed on the tenant, and other
    modules in this suite warm it. A cache hit returns 200 without touching the
    database, which would make a "did the failure get counted" test pass or fail for a
    reason unrelated to the counter.
    """
    api.cache.invalidate("overview:")


def _database_available() -> bool:
    import psycopg

    async def _ping() -> None:
        conn = await psycopg.AsyncConnection.connect(DSN, connect_timeout=2)
        await conn.close()

    try:
        asyncio.run(_ping())
        return True
    except Exception:
        return False


needs_database = pytest.mark.skipif(
    not _database_available(), reason="local postgres not reachable for the catalog assertions"
)


@pytest.fixture()
def live_database(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Point the app at the local database for the duration of one test.

    ``settings`` is a frozen dataclass read at import time, so the DSN cannot be set
    by environment variable once this module has imported the app. Swapping the
    settings object and dropping the pool is the same thing the process does at
    startup, without reimporting the module (which would give the test a different
    app object and a different metrics engine than the one under test).
    """
    if not _database_available():
        pytest.skip("local postgres not reachable")

    monkeypatch.setattr(api, "settings", api.Settings(database_url=DSN))
    monkeypatch.setattr(api, "_pool", None)
    yield
    pool = api._pool
    if pool is not None:
        with contextlib.suppress(Exception):
            asyncio.run(pool.close())
        api._pool = None


async def _assess(sql_to_apply: str | None) -> dict[str, Any]:
    """Assess RLS on a connection whose changes are always rolled back."""
    import psycopg
    from psycopg.rows import dict_row

    from dcc.pgcompat import PgConnection

    conn = await psycopg.AsyncConnection.connect(DSN, row_factory=dict_row)
    try:
        async with conn.transaction(force_rollback=True):
            if sql_to_apply is not None:
                await conn.execute(sql_to_apply)
            return await api._assess_tenant_rls(PgConnection(conn))
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# The readiness probe reports tenant RLS
# ---------------------------------------------------------------------------


def test_readyz_reports_the_key_the_dashboard_reads(
    client: TestClient, live_database: Any
) -> None:
    """The panel's input must exist at all; that was the whole defect."""
    body = client.get("/readyz").json()

    assert "tenant_rls" in body["checks"], (
        "checks.tenant_rls is missing again; dcc_database_rls_ok will read 0 forever "
        f"whatever the database says. Body: {body}"
    )
    assert body["checks"]["tenant_rls"] in {"ok", "missing", "not_assessed"}


@needs_database
def test_readyz_reports_ok_against_a_database_that_enforces_rls(
    client: TestClient, live_database: Any
) -> None:
    body = client.get("/readyz").json()

    assert body["ready"] is True
    assert body["checks"]["tenant_rls"] == "ok"
    assert body["checks"]["tenant_rls_unprotected"] == 0
    assert body["checks"]["tenant_rls_tables"] > 0


@needs_database
def test_report_flips_to_missing_when_rls_is_disabled_and_back_after_rollback() -> None:
    """The check has to be able to say "no", or "ok" means nothing."""
    baseline = asyncio.run(_assess(None))
    assert baseline["tenant_rls"] == "ok", f"baseline is not clean: {baseline}"

    disabled = asyncio.run(_assess("ALTER TABLE dcc.assets DISABLE ROW LEVEL SECURITY"))
    assert disabled["tenant_rls"] == "missing", (
        "RLS was disabled on dcc.assets and the check still reported "
        f"{disabled['tenant_rls']!r}"
    )
    assert disabled["tenant_rls_unprotected"] == 1
    assert disabled["tenant_rls_tables"] == baseline["tenant_rls_tables"]

    restored = asyncio.run(_assess(None))
    assert restored["tenant_rls"] == "ok", (
        "the ALTER leaked past the rolled-back transaction: a test that corrupts the "
        f"schema it measures. {restored}"
    )


@needs_database
def test_report_flips_to_missing_when_rls_is_not_forced() -> None:
    """Enabled-but-not-forced leaves the table owner able to read every tenant."""
    unforced = asyncio.run(_assess("ALTER TABLE dcc.assets NO FORCE ROW LEVEL SECURITY"))

    assert unforced["tenant_rls"] == "missing", (
        "NO FORCE ROW LEVEL SECURITY is a tenant-isolation hole -- the owner bypasses "
        f"every policy -- and the check reported {unforced['tenant_rls']!r}"
    )

    assert asyncio.run(_assess(None))["tenant_rls"] == "ok"


# ---------------------------------------------------------------------------
# The RLS check must not become a liveness gate
# ---------------------------------------------------------------------------


def test_a_catalog_failure_is_not_assessed_not_a_failed_probe(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An assurance gap must never pull the instance out of rotation."""
    _install_pool(monkeypatch, _FakeConn(rls_raises=True))

    response = client.get("/readyz")
    body = response.json()

    assert response.status_code == 200, (
        "a failure to assess RLS failed the readiness probe; that is an outage taken "
        f"to fix a report. Status {response.status_code}: {body}"
    )
    assert body["ready"] is True
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["tenant_rls"] == "not_assessed", (
        f"an unreadable catalog must be reported as unknown, not as {body['checks']['tenant_rls']!r}"
    )


def test_schema_incompleteness_still_fails_the_probe(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative control: the existing 503 was not weakened to make room for RLS."""
    _install_pool(monkeypatch, _FakeConn(schema_ok=False))

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["ready"] is False
    assert response.json()["checks"]["schema"] == "incomplete"


# ---------------------------------------------------------------------------
# The database-error counter behind DCCDatabaseUnavailable
# ---------------------------------------------------------------------------


def test_the_counter_family_exists_before_the_first_failure(client: TestClient) -> None:
    """A family that appears only after the first error is a rule that cannot fire."""
    body = client.get("/metrics").text

    assert f"# TYPE {COUNTER} counter" in body, (
        f"{COUNTER} is not registered at import, so the DCCDatabaseUnavailable series "
        "does not exist on a healthy process and the rule is silently inert"
    )


def test_a_healthy_request_does_not_increment_the_counter(
    client: TestClient, live_database: Any
) -> None:
    before = _counter(client)
    client.get("/readyz")
    client.get("/healthz")

    assert _counter(client) == before, "the database-error counter moves on success"


def test_an_escaped_driver_error_increments_the_counter(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The middleware path: a driver error a handler did not catch."""
    import psycopg

    _install_pool_failure(monkeypatch, psycopg.OperationalError("connection failed"))
    api.cache.invalidate("overview:")

    before = _counter(client)
    strict = TestClient(app, raise_server_exceptions=False)
    response = strict.get(OVERVIEW)
    after = _counter(client)

    assert response.status_code == 500
    assert after == before + 1, (
        "a database error escaped a handler and reached the framework's 500 boundary "
        f"without being counted ({before} -> {after}); DCCDatabaseUnavailable stays silent"
    )
    assert "query" in _operations(client)


def test_a_failed_probe_increments_the_counter(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The probe path: get_pool() raising because the pool cannot be built."""
    before = _counter(client)
    _install_pool_failure(monkeypatch, api.HTTPException(status_code=503, detail="database_unavailable"))

    response = client.get("/readyz")
    after = _counter(client)

    assert response.status_code == 503
    assert after == before + 1, f"a failed readiness probe was not counted ({before} -> {after})"
    assert "readiness_probe" in _operations(client)


def test_a_non_database_500_is_not_counted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An alert that fires on the wrong cause is as bad as one that never fires."""
    _install_pool_failure(monkeypatch, RuntimeError("a bug, not a database"))
    api.cache.invalidate("overview:")

    before = _counter(client)
    strict = TestClient(app, raise_server_exceptions=False)
    response = strict.get(OVERVIEW)

    assert response.status_code == 500
    assert _counter(client) == before, (
        "an ordinary 500 was counted as a database fault; DCCDatabaseUnavailable would "
        "page for the wrong reason"
    )


def test_the_operation_label_is_a_closed_set(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bounded cardinality: no route, table or identifier may become a label value."""
    import psycopg

    _install_pool_failure(monkeypatch, psycopg.OperationalError("connection failed"))
    api.cache.invalidate("overview:")
    strict = TestClient(app, raise_server_exceptions=False)
    for tenant in ("dcc00000-0000-4000-8000-000000000001", "dcc00000-0000-4000-8000-000000000002"):
        strict.get(f"/v2/overview?tenant_id={tenant}")

    assert _operations(client) <= {"query", "readiness_probe"}, (
        f"unbounded label values in {COUNTER}: {_operations(client)}"
    )
