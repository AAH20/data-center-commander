"""Configuration for the in-process performance suite.

The suite is split in two, and the split is the point:

* ``test_perf_microbenchmarks.py``, ``test_perf_api_latency.py``,
  ``test_perf_budget_selfcheck.py`` and ``test_perf_scenario_assets.py`` need no
  external tool and no network. They carry real budgets and they are the CI gate.
* ``test_perf_live_scenarios.py`` drives the k6/Artillery scenarios against a live
  server. Those skip unless ``DCC_PERF_LIVE_URL`` is set, naming that capability.

The API latency tests need a database (they exercise the real handler and its SQL),
so the DSN is resolved once, here, and the tests skip with an explicit reason when
Postgres is not reachable. A skip that names the missing capability is honest; a
budget that silently measures a 503 is not.

Nothing here mutates ``os.environ``: the DSN is applied to the app's own settings
object (see ``_dsn_in_use``) rather than exported, so running this directory cannot
change what another test module sees.
"""

from __future__ import annotations

import os

import pytest

#: Fallback used when the environment names no database. Override with
#: DCC_TEST_DATABASE_URL (same variable tests/unit/test_readyz_disclosure.py uses).
DEFAULT_DSN = "postgresql://localhost:5432/dcc_demo_local"
DSN = os.environ.get("DCC_TEST_DATABASE_URL") or DEFAULT_DSN

#: Seeded demo tenant in dcc_demo_local; overridable for another dataset.
TENANT_ID = os.environ.get(
    "DCC_PERF_TENANT_ID", "dcc00000-0000-4000-8000-000000000001"
)

#: Set to a running server (e.g. http://127.0.0.1:8790) to unlock the load tests.
LIVE_URL = os.environ.get("DCC_PERF_LIVE_URL", "").strip()


def _dsn_in_use() -> str:
    """The DSN the app will actually connect with.

    ``Settings`` is a frozen dataclass built at import time from the environment,
    and ``dcc.api_async`` may already have been imported by an earlier module -- in a
    whole-suite run with no DSN configured, the latency tests would then measure a
    503. The value is therefore assigned on the settings object itself, at fixture
    time, rather than exported into the environment where it would leak into every
    other test module in the process.
    """
    import dcc.api_async as api

    configured = getattr(api.settings, "database_url", "") or ""
    if configured:
        return configured
    object.__setattr__(api.settings, "database_url", DSN)  # bypass frozen dataclass
    return DSN


@pytest.fixture(scope="session")
def database_dsn() -> str:
    """DSN of a reachable Postgres, or skip naming the missing capability."""
    dsn = _dsn_in_use()
    try:
        import psycopg

        with psycopg.connect(dsn, connect_timeout=2) as conn:
            conn.execute("SELECT 1")
    except Exception as exc:  # noqa: BLE001 - any failure means "not usable"
        pytest.skip(
            f"performance latency floor needs a live Postgres and none is reachable "
            f"at {dsn} ({type(exc).__name__}); start postgres, or point "
            f"DCC_TEST_DATABASE_URL at a seeded database"
        )
    return dsn


@pytest.fixture(scope="session")
def api_client(database_dsn: str):  # noqa: ARG001 - ordering dependency
    """In-process ASGI client against the real app and the real database.

    ``with`` is deliberate: it runs the app's lifespan, so the connection pool is
    opened once for the whole measure and closed afterwards. Measuring a route that
    rebuilds its pool per call would report connection setup, not handler cost.

    The app's token bucket is widened for the duration. It throttles at
    ``DCC_RATE_LIMIT_RPS`` (default 100/s), and this suite makes ~90 back-to-back
    requests per route; the first run of these tests failed with 429 because the
    limiter -- not the handler -- was the thing being timed. The 429 is fast, so
    without the status assertion in ``_get`` it would have made the numbers look
    *better* while measuring nothing. Restored on teardown.
    """
    from fastapi.testclient import TestClient

    import dcc.api_async as api

    original_rps = api.rate_limiter.rps
    api.rate_limiter.rps = max(original_rps, 1_000_000)
    api.rate_limiter._tokens.clear()  # start from a full bucket
    try:
        with TestClient(api.app) as client:
            yield client
    finally:
        api.rate_limiter.rps = original_rps
        api.rate_limiter._tokens.clear()


@pytest.fixture(scope="session")
def tenant_id() -> str:
    return TENANT_ID


def pytest_sessionstart(session):  # noqa: ARG001 - pytest hook signature
    from . import perf_budgets

    perf_budgets.RECORD.clear()


def pytest_terminal_summary(terminalreporter, exitstatus, config):  # noqa: ARG001
    """Print every measured number, on green runs too.

    A performance gate that only speaks when it fails gives nobody a trend to read,
    and the first thing people do with an unreadable gate is loosen it.
    """
    from . import perf_budgets

    if not perf_budgets.RECORD:
        return
    terminalreporter.write_sep("-", "performance budgets (measured / budget)")
    for label, measured_s, budget_ms in perf_budgets.RECORD:
        measured_ms = measured_s * 1000.0
        pct = (measured_ms / budget_ms * 100.0) if budget_ms else 0.0
        verdict = "ok" if measured_ms <= budget_ms else "OVER"
        terminalreporter.write_line(
            f"  {label:<62} {measured_ms:9.3f} ms / {budget_ms:8.2f} ms "
            f"({pct:5.1f}% of budget)  {verdict}"
        )
