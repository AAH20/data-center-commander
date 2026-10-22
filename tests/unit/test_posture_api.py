"""Tests for the security posture score.

This endpoint is deliberately different from /v2/compliance/scan. The compliance scan
reports on declared configuration for an audit framework; this reports on what can be
observed about the running process. The property that makes it trustworthy is that the
score MOVES when the deployment's security posture changes -- a score that cannot move
is decoration.

Each test sets the environment it needs explicitly. tests/conftest.py sets
DCC_ALLOW_ANONYMOUS for the legacy suite, so a test that asserts on enforced behaviour
must clear it, and two fixtures that both touch the same variable must not be combined
in one test or their monkeypatches fight.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import dcc.api_async as api
from dcc.api_async import app
from dcc.security.api_keys import generate_api_key, hash_api_key

TENANT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _enforce(monkeypatch):
    """Enforced auth with one registered key. Returns (client, raw_key)."""
    monkeypatch.delenv("DCC_ALLOW_ANONYMOUS", raising=False)
    raw = generate_api_key()
    api._API_KEYS.register_hash(tenant_id=TENANT, key_hash=hash_api_key(raw))
    return TestClient(app), raw


def _posture(client, raw=None):
    headers = {"X-API-Key": raw} if raw else {}
    response = client.get(f"/v2/security/posture?tenant_id={TENANT}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


class TestScoreTracksPosture:
    def test_anonymous_scores_lower_than_enforced(self, monkeypatch):
        """THE test. A score that cannot move is decoration."""
        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
        low = _posture(TestClient(app))["overall_score"]

        monkeypatch.delenv("DCC_ALLOW_ANONYMOUS", raising=False)
        raw = generate_api_key()
        api._API_KEYS.register_hash(tenant_id=TENANT, key_hash=hash_api_key(raw))
        high = _posture(TestClient(app), raw)["overall_score"]

        assert high > low, f"enforced ({high}) must score above anonymous ({low})"

    def test_anonymous_fails_identity_access(self, monkeypatch):
        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
        identity = _posture(TestClient(app))["dimensions"]["identity_access"]
        assert identity["failed"] > 0
        assert identity["score"] < 1.0

    def test_enforced_with_key_passes_identity_access(self, monkeypatch):
        client, raw = _enforce(monkeypatch)
        identity = _posture(client, raw)["dimensions"]["identity_access"]
        assert identity["failed"] == 0, identity["controls"]
        assert identity["score"] == 1.0

    def test_anonymous_sets_infrastructure_failure(self, monkeypatch):
        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
        infra = _posture(TestClient(app))["dimensions"]["infrastructure_security"]
        assert infra["failed"] > 0


class TestHonesty:
    def test_unassessable_control_is_not_a_pass(self, monkeypatch):
        """encryption_at_rest cannot be decided from inside the process. It must be
        reported NOT_ASSESSED rather than assumed, and it must cost score."""
        client, raw = _enforce(monkeypatch)
        data = _posture(client, raw)["dimensions"]["data_protection"]
        assert data["not_assessed"] >= 1
        assert data["score"] < 1.0, "an unassessable control must not score as passing"

    def test_result_declares_its_basis(self, monkeypatch):
        client, raw = _enforce(monkeypatch)
        assert _posture(client, raw)["evaluation_basis"] == "observed_process_state"

    def test_every_dimension_is_reported(self, monkeypatch):
        client, raw = _enforce(monkeypatch)
        body = _posture(client, raw)
        for dim in ("identity_access", "data_protection", "network_security",
                    "logging_monitoring", "infrastructure_security"):
            assert dim in body["dimensions"]
            assert 0.0 <= body["dimensions"][dim]["score"] <= 1.0

    def test_overall_is_within_range(self, monkeypatch):
        client, raw = _enforce(monkeypatch)
        assert 0.0 <= _posture(client, raw)["overall_score"] <= 100.0


class TestAccess:
    def test_posture_requires_authentication(self, monkeypatch):
        """A posture report enumerates weaknesses; it must not be readable anonymously."""
        client, _ = _enforce(monkeypatch)
        response = client.get(f"/v2/security/posture?tenant_id={TENANT}")
        assert response.status_code == 401
