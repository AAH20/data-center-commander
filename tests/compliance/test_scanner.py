"""Tests for the compliance scanner engine."""
from __future__ import annotations

import pytest

from dcc.compliance.models import (
    ComplianceStatus,
    ControlDefinition,
    Finding,
    Framework,
    Severity,
)
from dcc.compliance.scanner import (
    ComplianceScanner,
    ControlNotFoundError,
    DuplicateControlError,
)


def _make_control(
    control_id: str,
    framework: Framework = Framework.CUSTOM,
    *,
    evaluator=None,
    tags: list[str] | None = None,
) -> ControlDefinition:
    return ControlDefinition(
        control_id=control_id,
        framework=framework,
        title=f"Test {control_id}",
        evaluator=evaluator,
        tags=tags or [],
    )


def _pass_evaluator():
    return [
        Finding(
            control_id="test",
            status=ComplianceStatus.PASS,
            severity=Severity.INFO,
            message="OK",
        )
    ]


def _fail_evaluator():
    return [
        Finding(
            control_id="test",
            status=ComplianceStatus.FAIL,
            severity=Severity.HIGH,
            message="Failed",
        )
    ]


def _error_evaluator():
    raise RuntimeError("boom")


class TestComplianceScanner:
    def test_register_and_unregister(self) -> None:
        scanner = ComplianceScanner()
        ctrl = _make_control("C1")
        scanner.register(ctrl)
        assert "C1" in scanner.controls

        scanner.unregister("C1")
        assert "C1" not in scanner.controls

    def test_duplicate_registration_raises(self) -> None:
        scanner = ComplianceScanner()
        scanner.register(_make_control("C1"))
        with pytest.raises(DuplicateControlError):
            scanner.register(_make_control("C1"))

    def test_unregister_missing_raises(self) -> None:
        scanner = ComplianceScanner()
        with pytest.raises(ControlNotFoundError):
            scanner.unregister("missing")

    def test_get_control(self) -> None:
        scanner = ComplianceScanner()
        ctrl = _make_control("C1")
        scanner.register(ctrl)
        assert scanner.get_control("C1") is ctrl

    def test_scan_empty(self) -> None:
        scanner = ComplianceScanner()
        report = scanner.scan()
        assert report.total_controls == 0
        assert report.compliance_score == 0.0

    def test_scan_passing_control(self) -> None:
        scanner = ComplianceScanner()
        scanner.register(_make_control("C1", evaluator=_pass_evaluator))
        report = scanner.scan()
        assert report.total_controls == 1
        assert report.passed == 1
        assert report.failed == 0

    def test_scan_failing_control(self) -> None:
        scanner = ComplianceScanner()
        scanner.register(_make_control("C1", evaluator=_fail_evaluator))
        report = scanner.scan()
        assert report.total_controls == 1
        assert report.failed == 1
        assert report.compliance_score == 0.0

    def test_scan_error_control(self) -> None:
        scanner = ComplianceScanner()
        scanner.register(_make_control("C1", evaluator=_error_evaluator))
        report = scanner.scan()
        assert report.errors == 1

    def test_scan_filter_by_framework(self) -> None:
        scanner = ComplianceScanner()
        scanner.register(_make_control("C1", Framework.SOC2, evaluator=_pass_evaluator))
        scanner.register(_make_control("C2", Framework.ISO27001, evaluator=_fail_evaluator))

        report = scanner.scan(framework=Framework.SOC2)
        assert report.total_controls == 1
        assert report.results[0].control_id == "C1"

    def test_scan_filter_by_control_ids(self) -> None:
        scanner = ComplianceScanner()
        scanner.register(_make_control("C1", evaluator=_pass_evaluator))
        scanner.register(_make_control("C2", evaluator=_pass_evaluator))
        scanner.register(_make_control("C3", evaluator=_pass_evaluator))

        report = scanner.scan(control_ids=["C1", "C3"])
        assert report.total_controls == 2

    def test_scan_filter_by_tags(self) -> None:
        scanner = ComplianceScanner()
        scanner.register(_make_control("C1", tags=["security"]))
        scanner.register(_make_control("C2", tags=["network"]))

        report = scanner.scan(tags=["security"])
        assert report.total_controls == 1
        assert report.results[0].control_id == "C1"

    def test_scan_single(self) -> None:
        scanner = ComplianceScanner()
        scanner.register(_make_control("C1", evaluator=_pass_evaluator))
        result = scanner.scan_single("C1")
        assert result.control_id == "C1"
        assert result.passed

    def test_scan_single_missing(self) -> None:
        scanner = ComplianceScanner()
        with pytest.raises(ControlNotFoundError):
            scanner.scan_single("missing")

    def test_fail_fast(self) -> None:
        scanner = ComplianceScanner(fail_fast=True)
        scanner.register(_make_control("C1", evaluator=_error_evaluator))
        scanner.register(_make_control("C2", evaluator=_pass_evaluator))
        report = scanner.scan()
        assert report.total_controls == 1

    def test_pre_post_scan_hooks(self) -> None:
        calls: list[str] = []
        scanner = ComplianceScanner()
        scanner.register(_make_control("C1", evaluator=_pass_evaluator))
        scanner.add_pre_scan_hook(lambda ctx: calls.append("pre"))
        scanner.add_post_scan_hook(lambda ctx: calls.append("post"))
        scanner.scan()
        assert calls == ["pre", "post"]

    def test_scan_with_metadata(self) -> None:
        scanner = ComplianceScanner()
        scanner.register(_make_control("C1", evaluator=_pass_evaluator))
        report = scanner.scan(metadata={"version": "1.0"})
        assert report.metadata["version"] == "1.0"

    def test_scan_with_tenant(self) -> None:
        scanner = ComplianceScanner()
        scanner.register(_make_control("C1", evaluator=_pass_evaluator))
        report = scanner.scan(tenant_id="tenant-1")
        assert report.tenant_id == "tenant-1"
