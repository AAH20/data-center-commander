"""The readiness probe must not describe the database to strangers.

/readyz is unauthenticated by design -- a load balancer has no API key, so the probe has
to answer before authentication exists. That makes everything it says publicly readable.

It used to return str(exc) when the connection failed, and a psycopg/asyncpg connection
error routinely embeds the DSN: host, port, database name and role. A probe intended to
answer "can this instance serve traffic" also answered "here is where the database is and
who connects to it" to anyone who could reach the port.

The test asserts the absence of each DSN component rather than the presence of a specific
message, so a future refactor that reintroduces detail under a different key still fails.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client_with_bad_dsn(monkeypatch) -> Iterator[TestClient]:
    """An app configured with a DSN that cannot connect."""
    monkeypatch.setenv(
        "DCC_DATABASE_URL",
        "postgresql://leakuser:leakpass@db.invalid:5999/leakdb",
    )
    monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
    logging.disable(logging.CRITICAL)

    import importlib

    import dcc.api_async as api

    importlib.reload(api)
    yield TestClient(api.app)

    logging.disable(logging.NOTSET)
    importlib.reload(api)


def test_readyz_reports_503_without_echoing_the_dsn(client_with_bad_dsn: TestClient) -> None:
    """Defence in depth, and not the primary guard.

    Whether a driver puts the DSN in its exception text is a property of the driver, not
    of this code -- psycopg happens to say "connection failed" without the host, so
    reintroducing str(exc) does not always fail this assertion. The test that reliably
    reddens is test_readyz_returns_a_stable_shape_on_failure, which forbids the free-form
    error key outright. This one catches the case where a driver does disclose.
    """
    response = client_with_bad_dsn.get("/readyz")

    assert response.status_code == 503
    body = response.text

    for secret in ("leakuser", "leakpass", "db.invalid", "5999", "leakdb", "postgresql"):
        assert secret not in body, (
            f"/readyz disclosed {secret!r} from the connection string. The probe is "
            f"unauthenticated, so this is a public disclosure. Body was: {body[:300]}"
        )


def test_readyz_returns_a_stable_shape_on_failure(client_with_bad_dsn: TestClient) -> None:
    """A caller must be able to branch on the reason without parsing prose."""
    body = client_with_bad_dsn.get("/readyz").json()

    assert body["ready"] is False
    assert body["checks"]["database"] == "unreachable"
    assert "error" not in body, (
        "free-form error text is back; that is how the DSN escaped the first time"
    )


def test_readyz_reports_ready_when_the_database_answers(monkeypatch) -> None:
    """The fix must not be 'always report unreachable'."""
    import os

    dsn = os.environ.get("DCC_TEST_DATABASE_URL") or "postgresql://localhost:5432/dcc_demo_local"
    monkeypatch.setenv("DCC_DATABASE_URL", dsn)
    monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
    logging.disable(logging.CRITICAL)

    import importlib

    import dcc.api_async as api

    importlib.reload(api)
    try:
        response = TestClient(api.app).get("/readyz")
        if response.status_code == 503:
            pytest.skip("local postgres not reachable for the healthy-path assertion")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["checks"]["schema"] == "ok"
    finally:
        logging.disable(logging.NOTSET)
        importlib.reload(api)
