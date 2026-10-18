"""Tests for report generation."""
from __future__ import annotations

import json

from dcc.compliance.models import (
    ComplianceReport,
    ComplianceStatus,
    ControlResult,
    Finding,
    Framework,
    Severity,
)
from dcc.compliance.report import (
    ReportExporter,
    generate_html_report,
    generate_json_report,
    generate_markdown_report,
)


def _make_report() -> ComplianceReport:
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
        ),
        ControlResult(
            control_id="SOC2-CC6.2",
            framework=Framework.SOC2,
            title="Access Removal",
            status=ComplianceStatus.PASS,
        ),
    ]
    return ComplianceReport(framework=Framework.SOC2, results=results)


class TestJsonReport:
    def test_generate_json(self) -> None:
        report = _make_report()
        output = generate_json_report(report)
        data = json.loads(output)
        assert data["framework"] == "soc2"
        assert data["summary"]["total_controls"] == 2
        assert data["summary"]["failed"] == 1


class TestMarkdownReport:
    def test_generate_markdown(self) -> None:
        report = _make_report()
        output = generate_markdown_report(report)
        assert "# Compliance Report: soc2" in output
        assert "## Summary" in output
        assert "SOC2-CC6.1" in output
        assert "Failed Controls" in output

    def test_markdown_contains_remediation(self) -> None:
        report = _make_report()
        output = generate_markdown_report(report)
        assert "Enable auth" in output


class TestHtmlReport:
    def test_generate_html(self) -> None:
        report = _make_report()
        output = generate_html_report(report)
        assert "<!DOCTYPE html>" in output
        assert "Compliance Report" in output
        assert "SOC2-CC6.1" in output
        assert "50.0%" in output  # compliance score

    def test_html_escapes_content(self) -> None:
        findings = [
            Finding(
                control_id="TEST",
                status=ComplianceStatus.FAIL,
                severity=Severity.HIGH,
                message="<script>alert('xss')</script>",
            )
        ]
        results = [
            ControlResult(
                control_id="TEST",
                framework=Framework.CUSTOM,
                title="Test",
                status=ComplianceStatus.FAIL,
                findings=findings,
            )
        ]
        report = ComplianceReport(framework=Framework.CUSTOM, results=results)
        output = generate_html_report(report)
        assert "<script>" not in output
        assert "&lt;script&gt;" in output


class TestReportExporter:
    def test_export_json(self, tmp_path) -> None:
        exporter = ReportExporter(tmp_path)
        report = _make_report()
        path = exporter.export_json(report)
        assert path.exists()
        assert path.suffix == ".json"

    def test_export_markdown(self, tmp_path) -> None:
        exporter = ReportExporter(tmp_path)
        report = _make_report()
        path = exporter.export_markdown(report)
        assert path.exists()
        assert path.suffix == ".md"

    def test_export_html(self, tmp_path) -> None:
        exporter = ReportExporter(tmp_path)
        report = _make_report()
        path = exporter.export_html(report)
        assert path.exists()
        assert path.suffix == ".html"

    def test_export_all(self, tmp_path) -> None:
        exporter = ReportExporter(tmp_path)
        report = _make_report()
        paths = exporter.export_all(report)
        assert "json" in paths
        assert "markdown" in paths
        assert "html" in paths
        assert all(p.exists() for p in paths.values())
