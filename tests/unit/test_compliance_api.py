"""Tests for the compliance endpoints and the authentication control.

The control that matters most here is SOC2-CC6.1. It used to decide "authentication is
enabled" from DCC_AUTH_ENABLED, a variable the served application never reads, defaulting
to "true" -- so it reported authentication as enabled while the API could be accepting
anonymous requests. These tests pin the control to the configuration the app enforces.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import dcc.api_async as api
from dcc.api_async import app
from dcc.compliance.controls import get_builtin_controls
from dcc.compliance.scanner import ComplianceScanner
from dcc.security.posture import auth_posture


def _cc61():
    """Evaluate SOC2-CC6.1 in isolation."""
    control = [c for c in get_builtin_controls() if c.control_id == "SOC2-CC6.1"]
    return ComplianceScanner(control).scan().results[0]


def _messages(result) -> str:
    return " ".join(f.message for f in result.findings)


class TestAuthControlTracksReality:
    def test_anonymous_access_fails_the_control(self, monkeypatch):
        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
        monkeypatch.delenv("DCC_API_KEYS", raising=False)
        result = _cc61()
        assert result.status.value == "fail"
        assert "Anonymous access is enabled" in _messages(result)

    def test_failure_is_critical_not_advisory(self, monkeypatch):
        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
        monkeypatch.delenv("DCC_API_KEYS", raising=False)
        severities = [getattr(f.severity, "value", f.severity) for f in _cc61().findings]
        assert "critical" in severities

    def test_enforced_without_keys_is_reported_as_a_lockout(self, monkeypatch):
        """Enforced auth with no keys rejects everything; that is not access control."""
        monkeypatch.delenv("DCC_ALLOW_ANONYMOUS", raising=False)
        monkeypatch.delenv("DCC_API_KEYS", raising=False)
        result = _cc61()
        assert "lockout" in _messages(result).lower()

    def test_enforced_with_keys_passes_the_auth_check(self, monkeypatch):
        monkeypatch.delenv("DCC_ALLOW_ANONYMOUS", raising=False)
        monkeypatch.setenv("DCC_API_KEYS", "tenant:" + "a" * 64)
        message = _messages(_cc61())
        assert "Authentication is required" in message
        assert "Anonymous" not in message
        assert "lockout" not in message.lower()

    def test_the_old_variable_is_no_longer_consulted(self, monkeypatch):
        """DCC_AUTH_ENABLED was never read by the app; it must not decide the outcome."""
        monkeypatch.delenv("DCC_ALLOW_ANONYMOUS", raising=False)
        monkeypatch.delenv("DCC_API_KEYS", raising=False)
        monkeypatch.setenv("DCC_AUTH_ENABLED", "true")
        assert "lockout" in _messages(_cc61()).lower()


class TestPosture:
    def test_maybe_does_not_mean_yes(self, monkeypatch):
        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "maybe")
        assert auth_posture()["anonymous_allowed"] is False

    def test_counts_configured_keys(self, monkeypatch):
        monkeypatch.setenv("DCC_API_KEYS", f"a:{'x' * 64},b:{'y' * 64}")
        assert auth_posture()["configured_keys"] == 2

    def test_locked_out_requires_enforcement_and_no_keys(self, monkeypatch):
        monkeypatch.delenv("DCC_ALLOW_ANONYMOUS", raising=False)
        monkeypatch.delenv("DCC_API_KEYS", raising=False)
        assert auth_posture()["locked_out"] is True


class TestControlCatalogue:
    @pytest.fixture()
    def client(self):
        return TestClient(app)

    def test_lists_the_catalogue(self, client):
        response = client.get("/v2/compliance/controls")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] >= 10
        first = body["controls"][0]
        for key in ("control_id", "framework", "title", "severity"):
            assert key in first

    def test_filters_by_framework(self, client):
        all_controls = client.get("/v2/compliance/controls").json()["controls"]
        iso = client.get("/v2/compliance/controls?framework=iso27001").json()
        assert all(c["framework"] == "iso27001" for c in iso["controls"])
        assert iso["count"] < len(all_controls)

    def test_unknown_framework_is_rejected_and_named(self, client):
        response = client.get("/v2/compliance/controls?framework=made_up")
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["error"] == "unknown_framework"
        assert "soc2" in detail["accepted"]


class TestScan:
    @pytest.fixture()
    def client(self):
        return TestClient(app)

    def test_scan_returns_a_summary_per_control(self, client):
        response = client.get("/v2/compliance/scan")
        assert response.status_code == 200
        body = response.json()
        summary = body["summary"]
        assert summary["total"] >= 10
        assert sum(summary["by_status"].values()) == summary["total"]

    def test_scan_states_its_evaluation_basis(self, client):
        """A compliance result that does not say what it measured invites over-claiming."""
        body = client.get("/v2/compliance/scan").json()
        assert body["evaluation_basis"] == "declared_configuration"
        assert "not an audit" in body["note"]

    def test_scan_can_be_scoped_to_one_framework(self, client):
        body = client.get("/v2/compliance/scan?framework=iso27001").json()
        assert body["summary"]["total"] < 16
        assert all(r["framework"] == "iso27001" for r in body["results"])

    def test_scan_rejects_unknown_framework(self, client):
        assert client.get("/v2/compliance/scan?framework=nope").status_code == 400


class TestConfigurationGaps:
    """The scan must be able to name controls that read variables the app ignores.

    This mechanism used to report every one of the sixteen controls: each evaluator
    read at least one variable the served application never consulted, so a pass on
    one of them was decorative -- an operator could set it and the running system did
    nothing differently.

    The controls now measure system state instead, so the report is empty. That is
    the assertion below: not "the mechanism exists" but "nothing is left for it to
    find". A regression that reintroduces an unconsumed variable makes this fail with
    the offending control named, which is exactly what it is for.
    """

    def test_scan_finds_no_unconsumed_configuration(self):
        client = TestClient(app)
        gaps = client.get("/v2/compliance/scan").json()["configuration_gaps"]
        assert gaps["affected_controls"] == 0, gaps["detail"]
        assert gaps["detail"] == {}

    def test_the_fixed_control_has_no_gap(self):
        """SOC2-CC6.1 was repointed at the real configuration, so it must be clean.

        This is the test that proves the fix rather than describing it: the same
        mechanism that flags a control must find nothing to flag here.
        """
        client = TestClient(app)
        gaps = client.get("/v2/compliance/scan").json()["configuration_gaps"]
        assert "SOC2-CC6.1" not in gaps["detail"]

    def test_gap_entries_name_an_environment_variable(self):
        client = TestClient(app)
        detail = client.get("/v2/compliance/scan").json()["configuration_gaps"]["detail"]
        for control_id, variables in detail.items():
            assert variables, f"{control_id} listed with no variables"
            for variable in variables:
                assert variable.isupper() and variable.startswith("DCC_"), variable
