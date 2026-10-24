"""Authentication failures must be visible in metrics.

Middleware order is the opposite of reading order: Starlette wraps the app from the end
of ``user_middleware`` inwards, so index 0 is outermost, and ``add_middleware`` inserts
at index 0 -- the middleware registered LAST runs FIRST.

``auth_middleware`` is registered after ``metrics_middleware``, so auth landed outside
metrics and rejected a request before metrics could record it. Its docstring claimed the
reverse, so an operator reading the code would expect 401s on the dashboard while a
flood of authentication failures was invisible.

``_promote_metrics_middleware()`` moves metrics to the outermost position. These tests
pin the resulting behaviour, not the mechanism: a rejected request must move a counter.

The first test is the one that matters. It measures a delta across a single request, so
it fails whether the middleware is misordered or metrics stops recording entirely -- the
two ways this can regress.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from dcc.api_async import app

TENANT = "dcc00000-0000-4000-8000-000000000001"


def _total_requests(client: TestClient) -> float:
    body = client.get("/metrics").text
    return sum(float(value) for value in re.findall(r"api_requests_total\{[^}]*\}\s+([0-9.]+)", body))


@pytest.fixture()
def enforced(monkeypatch):
    """Enforced auth with one live key, so an anonymous request is genuinely rejected.

    The key is registered in the live store rather than by setting DCC_API_KEYS: the
    store is populated from that variable at import time, so setting it here would be
    too late. The key is deleted afterwards because the security-posture scorer counts
    live keys -- leaving one behind would shift the identity_access score that
    tests/unit/test_compliance_api.py asserts on.
    """
    from dcc import api_async
    from dcc.security.api_keys import generate_api_key, hash_api_key

    raw = generate_api_key()
    key = api_async._API_KEYS.register_hash(tenant_id=TENANT, key_hash=hash_api_key(raw))
    monkeypatch.delenv("DCC_ALLOW_ANONYMOUS", raising=False)
    try:
        yield raw
    finally:
        api_async._API_KEYS.delete(key.id)


def test_rejected_request_is_recorded(enforced) -> None:
    """A 401 must move the request counter -- otherwise auth failures are invisible."""
    client = TestClient(app)

    before = _total_requests(client)
    response = client.get(f"/v2/overview?tenant_id={TENANT}")
    after = _total_requests(client)

    assert response.status_code == 401, f"expected a rejection, got {response.status_code}"
    assert after > before, (
        "a rejected request did not increment api_requests_total; metrics is running "
        "inside auth_middleware instead of outside it"
    )


def test_successful_request_is_recorded(enforced) -> None:
    """Negative control: the counter must also move for an accepted request."""
    client = TestClient(app)

    before = _total_requests(client)
    response = client.get(f"/v2/compliance/controls?tenant_id={TENANT}", headers={"X-API-Key": enforced})
    after = _total_requests(client)

    assert response.status_code == 200, f"expected 200, got {response.status_code}: {response.text[:120]}"
    assert after > before


def test_metrics_is_the_outermost_layer() -> None:
    """The property that makes the two tests above true, asserted directly."""
    entries = list(app.user_middleware)
    names = []
    for entry in entries:
        dispatch = getattr(entry, "dispatch", None) or entry.kwargs.get("dispatch")
        names.append(getattr(dispatch, "__name__", None) or entry.cls.__name__)

    assert names and names[0] == "metrics_middleware", (
        f"metrics is not outermost; current order is {names}"
    )
    assert "auth_middleware" in names, f"auth middleware missing from the stack: {names}"


def test_auth_is_inside_metrics() -> None:
    """Auth must still run *before* routing, just inside the metrics layer."""
    entries = list(app.user_middleware)
    names = []
    for entry in entries:
        dispatch = getattr(entry, "dispatch", None) or entry.kwargs.get("dispatch")
        names.append(getattr(dispatch, "__name__", None) or entry.cls.__name__)

    assert names.index("metrics_middleware") < names.index("auth_middleware"), (
        f"metrics must wrap auth; current order is {names}"
    )
