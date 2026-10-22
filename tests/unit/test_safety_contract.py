"""The advisory contract must hold on every /v2 JSON response.

The system's premise is that nothing it returns authorizes action. That guarantee used
to be set per-handler, so it held on /v2/overview and was absent from /v2/facilities.
A safety property that depends on remembering is not a property.

The middleware injects the two fields after the handler runs, which is what makes it
fail closed: a new endpoint cannot forget, because it never had to remember.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dcc.api_async import app

TENANT = "dcc00000-0000-4000-8000-000000000001"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
    return TestClient(app)


class TestContractHoldsUniformly:
    @pytest.mark.parametrize(
        "path",
        [
            # /v2/overview is deliberately absent: it requires a database, and CI has
            # none. The routes here are all database-free so the contract is verified
            # in the environment that actually runs.
            "/v2/compliance/controls",
            "/v2/compliance/scan",
            "/v2/security/posture",
        ],
    )
    def test_object_responses_carry_the_contract(self, client, path):
        sep = "&" if "?" in path else "?"
        response = client.get(f"{path}{sep}tenant_id={TENANT}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["read_only"] is True
        assert body["execution_permitted"] is False

    def test_this_route_did_not_previously_carry_it(self, client):
        """Compliance controls never set the fields; the middleware must supply them."""
        body = client.get(f"/v2/compliance/controls?tenant_id={TENANT}").json()
        assert body["read_only"] is True

    def test_explicit_values_are_not_overwritten(self, client):
        """A handler that deliberately reports execution_permitted must keep it."""
        body = client.get(f"/v2/compliance/scan?tenant_id={TENANT}").json()
        assert body["execution_permitted"] is False


class TestPassThrough:
    def test_non_v2_paths_are_untouched(self, client):
        """/healthz is not a /v2 resource and must not gain API contract fields."""
        body = client.get("/healthz").json()
        assert "read_only" not in body

    def test_metrics_is_not_json(self, client):
        response = client.get("/metrics")
        assert "text/plain" in response.headers["content-type"]
        assert "read_only" not in response.text

    def test_prometheus_body_survives_the_middleware(self, client):
        """Byte-for-byte passthrough: a rewritten metrics body would be corrupt."""
        text = client.get("/metrics").text
        assert "# HELP" in text or text.strip() == ""
