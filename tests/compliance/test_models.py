"""Tests for compliance models."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from dcc.compliance.models import (
    ComplianceReport,
    ComplianceStatus,
    ControlDefinition,
    ControlResult,
    Evidence,
    EvidenceType,
    Finding,
    Framework,
    RemediationAction,
    RemediationStatus,
    Severity,
)


class TestEvidence:
    def test_create_evidence(self) -> None:
        ev = Evidence(
            evidence_type=EvidenceType.CONFIG,
            source="test",
            content={"key": "value"},
        )
        assert ev.evidence_type == EvidenceType.CONFIG
        assert ev.source == "test"
        assert ev.content == {"key": "value"}
        assert ev.metadata == {}

    def test_evidence_serialization(self) -> None:
        ev = Evidence(
            evidence_type=EvidenceType.LOG,
            source="/var/log/test.log",
            content="log line",
            metadata={"lines": 1},
        )
        data = ev.to_dict()
        assert data["evidence_type"] == "log"
        assert data["source"] == "/var/log/test.log"
        assert data["content"] == "log line"
        assert data["metadata"] == {"lines": 1}

        restored = Evidence.from_dict(data)
        assert restored.evidence_type == ev.evidence_type
        assert restored.source == ev.source
        assert restored.content == ev.content


class TestFinding:
    def test_create_finding(self) -> None:
        f = Finding(
            control_id="SOC2-CC6.1",
            status=ComplianceStatus.FAIL,
            severity=Severity.HIGH,
            message="Test failure",
        )
        assert f.control_id == "SOC2-CC6.1"
        assert f.status == ComplianceStatus.FAIL
        assert f.severity == Severity.HIGH
        assert f.message == "Test failure"

    def test_finding_with_evidence(self) -> None:
        ev = Evidence(
            evidence_type=EvidenceType.CONFIG,
            source="env",
            content={"auth_enabled": False},
        )
        f = Finding(
            control_id="SOC2-CC6.1",
            status=ComplianceStatus.FAIL,
            severity=Severity.CRITICAL,
            message="Auth disabled",
            evidence=(ev,),
            remediation_hint="Enable auth",
        )
        assert len(f.evidence) == 1
        assert f.evidence[0].source == "env"
        assert f.remediation_hint == "Enable auth"

    def test_finding_serialization(self) -> None:
        f = Finding(
            control_id="TEST-1",
            status=ComplianceStatus.PASS,
            severity=Severity.INFO,
            message="All good",
        )
        data = f.to_dict()
        assert data["control_id"] == "TEST-1"
        assert data["status"] == "pass"

        restored = Finding.from_dict(data)
        assert restored.control_id == f.control_id
        assert restored.status == f.status


class TestControlResult:
    def test_control_result_pass(self) -> None:
        r = ControlResult(
            control_id="TEST-1",
            framework=Framework.SOC2,
            title="Test Control",
            status=ComplianceStatus.PASS,
        )
        assert r.passed
        assert not r.failed

    def test_control_result_fail(self) -> None:
        f = Finding(
            control_id="TEST-1",
            status=ComplianceStatus.FAIL,
            severity=Severity.HIGH,
            message="Failed",
        )
        r = ControlResult(
            control_id="TEST-1",
            framework=Framework.SOC2,
            title="Test Control",
            status=ComplianceStatus.FAIL,
            findings=[f],
        )
        assert r.failed
        assert not r.passed
        assert len(r.findings) == 1

    def test_control_result_serialization(self) -> None:
        r = ControlResult(
            control_id="TEST-1",
            framework=Framework.ISO27001,
            title="Test",
            description="A test control",
            status=ComplianceStatus.PASS,
            tags=["test"],
        )
        data = r.to_dict()
        assert data["control_id"] == "TEST-1"
        assert data["framework"] == "iso27001"

        restored = ControlResult.from_dict(data)
        assert restored.control_id == r.control_id
        assert restored.framework == r.framework


class TestComplianceReport:
    def test_empty_report(self) -> None:
        r = ComplianceReport()
        assert r.total_controls == 0
        assert r.compliance_score == 0.0

    def test_report_with_results(self) -> None:
        results = [
            ControlResult(
                control_id="T1",
                framework=Framework.SOC2,
                title="T1",
                status=ComplianceStatus.PASS,
            ),
            ControlResult(
                control_id="T2",
                framework=Framework.SOC2,
                title="T2",
                status=ComplianceStatus.FAIL,
            ),
            ControlResult(
                control_id="T3",
                framework=Framework.SOC2,
                title="T3",
                status=ComplianceStatus.SKIP,
            ),
        ]
        r = ComplianceReport(results=results)
        assert r.total_controls == 3
        assert r.passed == 1
        assert r.failed == 1
        assert r.skipped == 1
        # SKIP counts as applicable but not failed: (3-1)/3 = 66.67%
        assert r.compliance_score == pytest.approx(66.67, abs=0.1)

    def test_report_serialization(self) -> None:
        r = ComplianceReport(
            framework=Framework.SOC2,
            tenant_id="test-tenant",
            metadata={"version": "1.0"},
        )
        data = r.to_dict()
        assert data["framework"] == "soc2"
        assert data["tenant_id"] == "test-tenant"
        assert data["metadata"] == {"version": "1.0"}
        assert "summary" in data

        restored = ComplianceReport.from_dict(data)
        assert restored.framework == r.framework
        assert restored.tenant_id == r.tenant_id

    def test_report_json_roundtrip(self) -> None:
        r = ComplianceReport(framework=Framework.PCI_DSS)
        json_str = r.to_json()
        data = json.loads(json_str)
        assert data["framework"] == "pci_dss"

    def test_report_save_load(self, tmp_path) -> None:
        r = ComplianceReport(framework=Framework.HIPAA)
        path = tmp_path / "report.json"
        r.save(path)
        assert path.exists()

        loaded = ComplianceReport.load(path)
        assert loaded.framework == Framework.HIPAA


class TestRemediationAction:
    def test_create_action(self) -> None:
        a = RemediationAction(
            control_id="SOC2-CC6.1",
            title="Enable auth",
            description="Enable authentication",
            automated=True,
            command="echo 'done'",
        )
        assert a.control_id == "SOC2-CC6.1"
        assert a.status == RemediationStatus.PENDING
        assert a.automated

    def test_action_serialization(self) -> None:
        a = RemediationAction(
            control_id="TEST-1",
            title="Fix",
            status=RemediationStatus.COMPLETED,
            result="Success",
        )
        data = a.to_dict()
        assert data["control_id"] == "TEST-1"
        assert data["status"] == "completed"

        restored = RemediationAction.from_dict(data)
        assert restored.control_id == a.control_id
        assert restored.status == a.status


class TestControlDefinition:
    def test_create_definition(self) -> None:
        def dummy_evaluator():
            return []

        c = ControlDefinition(
            control_id="TEST-1",
            framework=Framework.CUSTOM,
            title="Test",
            evaluator=dummy_evaluator,
            tags=["test"],
        )
        assert c.control_id == "TEST-1"
        assert c.framework == Framework.CUSTOM
        assert c.evaluator is not None
