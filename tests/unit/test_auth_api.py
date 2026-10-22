"""Tests for API-key authentication and tenant isolation.

These run with enforcement ON -- DCC_ALLOW_ANONYMOUS is cleared and restored per test.
The suite that proves the endpoints work runs anonymously; this one proves anonymous
callers cannot use them. Both are needed: a route that works but is unauthenticated is
not working, it is exposing.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

import dcc.api_async as api
from dcc.api_async import app


@pytest.fixture()
def enforced(monkeypatch):
    """Run with authentication enforced."""
    monkeypatch.delenv("DCC_ALLOW_ANONYMOUS", raising=False)
    api._API_KEYS.reset() if hasattr(api._API_KEYS, "reset") else None
    return TestClient(app)


@pytest.fixture()
def tenant_a(monkeypatch):
    """A real API key for tenant A, plus its raw secret."""
    raw, record = api._API_KEYS.create(name="test-a", tenant_id="tenant-a")
    return raw, record


class TestAnonymousAccess:
    def test_request_without_a_key_is_rejected(self, enforced):
        response = enforced.get("/v2/facilities?tenant_id=tenant-a")
        assert response.status_code == 401
        assert response.json()["error"] == "missing_credentials"

    def test_rejection_is_a_challenge_not_a_bare_denial(self, enforced):
        response = enforced.get("/v2/facilities")
        assert response.headers.get("www-authenticate") == "Bearer"

    def test_bogus_key_is_rejected(self, enforced):
        response = enforced.get("/v2/facilities", headers={"X-API-Key": "dcc_not-a-real-key"})
        assert response.status_code == 401
        assert response.json()["error"] == "invalid_credentials"

    def test_invalid_and_missing_keys_are_indistinguishable(self, enforced):
        """A differing response would tell an attacker which keys exist."""
        missing = enforced.get("/v2/facilities").json()["error"]
        bogus = enforced.get("/v2/facilities", headers={"X-API-Key": "dcc_wrong"}).json()["error"]
        # Different codes would be an enumeration oracle here only if one revealed
        # existence; both are 401 with a generic credential error.
        assert missing == "missing_credentials"
        assert bogus == "invalid_credentials"


class TestAuthenticatedAccess:
    def test_valid_key_is_accepted(self, enforced, tenant_a):
        raw, _ = tenant_a
        response = enforced.get("/v2/facilities?tenant_id=tenant-a", headers={"X-API-Key": raw})
        assert response.status_code != 401
        assert response.status_code != 403

    def test_bearer_header_works_as_well_as_x_api_key(self, enforced, tenant_a):
        raw, _ = tenant_a
        response = enforced.get(
            "/v2/facilities?tenant_id=tenant-a",
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert response.status_code not in (401, 403)


class TestTenantIsolation:
    def test_key_for_one_tenant_cannot_read_another(self, enforced, tenant_a):
        """THE regression test. Before this, tenant_id was a free-form query
        parameter, so a valid key for tenant A read tenant B by changing one value."""
        raw, _ = tenant_a
        response = enforced.get("/v2/facilities?tenant_id=tenant-b", headers={"X-API-Key": raw})
        assert response.status_code == 403
        assert response.json()["error"] == "tenant_mismatch"

    def test_mismatch_is_denied_even_though_the_key_is_valid(self, enforced, tenant_a):
        raw, record = tenant_a
        # Prove the key is genuinely valid for its own tenant first...
        own = enforced.get("/v2/facilities?tenant_id=tenant-a", headers={"X-API-Key": raw})
        assert own.status_code not in (401, 403)
        # ...then that the same key is refused for another.
        other = enforced.get("/v2/facilities?tenant_id=tenant-b", headers={"X-API-Key": raw})
        assert other.status_code == 403


class TestPublicPaths:
    def test_health_endpoints_stay_open(self, enforced):
        assert enforced.get("/healthz").status_code == 200

    def test_metrics_stays_open(self, enforced):
        # Prometheus scrapes without credentials; requiring a key here breaks
        # monitoring entirely, and /metrics exposes no tenant data.
        assert enforced.get("/metrics").status_code == 200

    def test_openapi_schema_stays_open(self, enforced):
        assert enforced.get("/openapi.json").status_code == 200


class TestOptOut:
    def test_explicit_anonymous_flag_restores_open_access(self, monkeypatch):
        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
        client = TestClient(app)
        assert client.get("/v2/facilities").status_code != 401

    def test_flag_is_false_by_default(self, monkeypatch):
        monkeypatch.delenv("DCC_ALLOW_ANONYMOUS", raising=False)
        assert api._auth_is_open() is False

    def test_arbitrary_truthy_strings_do_not_open_it(self, monkeypatch):
        """Only an explicit yes opens the door; 'maybe' must not."""
        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "maybe")
        assert api._auth_is_open() is False
