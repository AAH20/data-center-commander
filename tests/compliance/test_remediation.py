"""Tests for the remediation engine."""
from __future__ import annotations

import pytest

from dcc.compliance.models import (
    ComplianceReport,
    ComplianceStatus,
    ControlResult,
    Finding,
    Framework,
    RemediationStatus,
    Severity,
)
from dcc.compliance.remediation import (
    RemediationEngine,
    RemediationError,
    RemediationPlaybook,
    get_builtin_playbooks,
)


def _make_failing_report() -> ComplianceReport:
    findings = [
        Finding(
            control_id="SOC2-CC6.1",
            status=ComplianceStatus.FAIL,
            severity=Severity.CRITICAL,
            message="Auth disabled",
            remediation_hint="Enable auth",
        )
    ]
    results = [
        ControlResult(
            control_id="SOC2-CC6.1",
            framework=Framework.SOC2,
            title="Logical Access Controls",
            status=ComplianceStatus.FAIL,
            findings=findings,
        )
    ]
    return ComplianceReport(framework=Framework.SOC2, results=results)


class TestRemediationEngine:
    def test_create_from_report(self) -> None:
        engine = RemediationEngine()
        report = _make_failing_report()
        actions = engine.create_from_report(report)
        assert len(actions) > 0
        assert all(a.control_id == "SOC2-CC6.1" for a in actions)

    def test_create_from_finding(self) -> None:
        engine = RemediationEngine()
        finding = Finding(
            control_id="SOC2-CC6.1",
            status=ComplianceStatus.FAIL,
            severity=Severity.HIGH,
            message="Test",
        )
        action = engine.create_from_finding(finding)
        assert action is not None
        assert action.control_id == "SOC2-CC6.1"

    def test_execute_manual_action(self) -> None:
        engine = RemediationEngine()
        finding = Finding(
            control_id="SOC2-CC6.1",
            status=ComplianceStatus.FAIL,
            severity=Severity.HIGH,
            message="Test",
        )
        action = engine.create_from_finding(finding)
        assert action is not None

        result = engine.execute(str(action.action_id))
        assert result.status == RemediationStatus.PENDING
        assert "Manual" in result.result

    def test_execute_automated_action(self, tmp_path, monkeypatch) -> None:
        """Run the real command, against a throwaway HOME.

        The action appends to ~/.dcc/env. That directory did not exist on a fresh
        machine, so the redirect failed with ENOENT and the action reported FAILED --
        which is what broke CI while passing locally, where ~/.dcc had been created by
        an earlier run. The command now creates the directory, and this test points HOME
        at tmp_path so it exercises the fresh-machine path every time instead of
        depending on whatever the host happens to have.
        """
        monkeypatch.setenv("HOME", str(tmp_path))
        engine = RemediationEngine()
        finding = Finding(
            control_id="SOC2-CC6.2",
            status=ComplianceStatus.FAIL,
            severity=Severity.MEDIUM,
            message="Session timeout too long",
        )
        action = engine.create_from_finding(finding)
        assert action is not None
        assert action.automated

        result = engine.execute(str(action.action_id))
        assert result.status == RemediationStatus.COMPLETED, result.result

        # The command must have actually written somewhere, not merely returned 0.
        env_file = tmp_path / ".dcc" / "env"
        assert env_file.is_file(), "the action reported success without writing ~/.dcc/env"
        assert "DCC_SESSION_TIMEOUT_MINUTES=240" in env_file.read_text()

    def test_execute_dry_run(self) -> None:
        engine = RemediationEngine(dry_run=True)
        finding = Finding(
            control_id="SOC2-CC6.2",
            status=ComplianceStatus.FAIL,
            severity=Severity.MEDIUM,
            message="Test",
        )
        action = engine.create_from_finding(finding)
        assert action is not None

        result = engine.execute(str(action.action_id))
        assert result.status == RemediationStatus.COMPLETED
        assert "[DRY RUN]" in result.result

    def test_execute_missing_action(self) -> None:
        engine = RemediationEngine()
        with pytest.raises(RemediationError):
            engine.execute("nonexistent-id")

    def test_get_actions(self) -> None:
        engine = RemediationEngine()
        report = _make_failing_report()
        engine.create_from_report(report)
        assert len(engine.get_actions()) > 0

    def test_to_report(self) -> None:
        engine = RemediationEngine()
        report = _make_failing_report()
        engine.create_from_report(report)
        data = engine.to_report()
        assert data["total"] > 0
        assert "actions" in data

    def test_save_report(self, tmp_path) -> None:
        engine = RemediationEngine()
        report = _make_failing_report()
        engine.create_from_report(report)
        path = tmp_path / "remediation.json"
        engine.save_report(path)
        assert path.exists()


class TestPlaybooks:
    def test_builtin_playbooks_exist(self) -> None:
        playbooks = get_builtin_playbooks()
        assert len(playbooks) > 0

    def test_playbook_matching(self) -> None:
        playbooks = get_builtin_playbooks()
        auth_pb = next((p for p in playbooks if p.name == "enable-authentication"), None)
        assert auth_pb is not None
        assert auth_pb.matches("SOC2-CC6.1")
        assert auth_pb.matches("ISO27001-A.9.4.1")
        assert not auth_pb.matches("PCI-3.4")

    def test_playbook_steps(self) -> None:
        for pb in get_builtin_playbooks():
            assert len(pb.steps) > 0, f"{pb.name} has no steps"
