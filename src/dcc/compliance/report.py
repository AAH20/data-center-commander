"""Report generation for compliance scans.

Generates human-readable and machine-readable compliance reports
in multiple formats: JSON, Markdown, and HTML.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ComplianceReport, ComplianceStatus, Severity


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------


def generate_json_report(report: ComplianceReport, *, indent: int = 2) -> str:
    """Generate a JSON compliance report."""
    return report.to_json(indent=indent)


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def generate_markdown_report(report: ComplianceReport) -> str:
    """Generate a Markdown compliance report."""
    lines: list[str] = []

    # Header
    lines.append(f"# Compliance Report: {report.framework.value}")
    lines.append("")
    lines.append(f"**Report ID:** `{report.report_id}`")
    lines.append(f"**Started:** {report.started_at.isoformat()}")
    lines.append(f"**Completed:** {report.completed_at.isoformat() if report.completed_at else 'N/A'}")
    lines.append(f"**Duration:** {report.duration_seconds:.2f}s")
    if report.tenant_id:
        lines.append(f"**Tenant:** `{report.tenant_id}`")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total Controls | {report.total_controls} |")
    lines.append(f"| Passed | {report.passed} |")
    lines.append(f"| Failed | {report.failed} |")
    lines.append(f"| Skipped | {report.skipped} |")
    lines.append(f"| Errors | {report.errors} |")
    lines.append(f"| **Compliance Score** | **{report.compliance_score:.1f}%** |")
    lines.append("")

    # Results by status
    _append_status_section(lines, report, ComplianceStatus.FAIL, "Failed Controls")
    _append_status_section(lines, report, ComplianceStatus.ERROR, "Errors")
    _append_status_section(lines, report, ComplianceStatus.PASS, "Passed Controls")

    # Detailed findings
    lines.append("## Detailed Findings")
    lines.append("")

    for result in report.results:
        if result.status == ComplianceStatus.PASS:
            continue

        lines.append(f"### {result.control_id}: {result.title}")
        lines.append("")
        lines.append(f"**Status:** {result.status.value}")
        lines.append(f"**Framework:** {result.framework.value}")
        lines.append(f"**Duration:** {result.duration_ms:.1f}ms")
        lines.append("")

        if result.description:
            lines.append(f"{result.description}")
            lines.append("")

        for finding in result.findings:
            lines.append(f"#### {finding.severity.value.upper()}: {finding.message}")
            lines.append("")

            if finding.remediation_hint:
                lines.append(f"**Remediation:** {finding.remediation_hint}")
                lines.append("")

            if finding.evidence:
                lines.append("<details>")
                lines.append("<summary>Evidence</summary>")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(
                    [e.to_dict() for e in finding.evidence],
                    indent=2,
                    default=str,
                ))
                lines.append("```")
                lines.append("")
                lines.append("</details>")
                lines.append("")

    return "\n".join(lines)


def _append_status_section(
    lines: list[str],
    report: ComplianceReport,
    status: ComplianceStatus,
    title: str,
) -> None:
    """Append a section for controls with a specific status."""
    matching = [r for r in report.results if r.status == status]
    if not matching:
        return

    lines.append(f"## {title}")
    lines.append("")

    for result in matching:
        lines.append(f"- **{result.control_id}**: {result.title}")

    lines.append("")


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------


def generate_html_report(report: ComplianceReport) -> str:
    """Generate an HTML compliance report."""
    score = report.compliance_score
    score_color = "#22c55e" if score >= 90 else "#eab308" if score >= 70 else "#ef4444"

    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append("<html lang=\"en\">")
    parts.append("<head>")
    parts.append("  <meta charset=\"UTF-8\">")
    parts.append("  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">")
    parts.append(f"  <title>Compliance Report - {html.escape(report.framework.value)}</title>")
    parts.append("  <style>")
    parts.append(_HTML_CSS)
    parts.append("  </style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append("  <div class=\"container\">")

    # Header
    parts.append("    <header>")
    parts.append(f"      <h1>Compliance Report: {html.escape(report.framework.value)}</h1>")
    parts.append(f"      <p class=\"meta\">Report ID: <code>{report.report_id}</code></p>")
    parts.append(f"      <p class=\"meta\">Generated: {datetime.now(timezone.utc).isoformat()}</p>")
    parts.append("    </header>")

    # Summary cards
    parts.append("    <section class=\"summary\">")
    parts.append("      <div class=\"cards\">")
    parts.append(f"        <div class=\"card score\" style=\"border-color: {score_color}\">")
    parts.append(f"          <div class=\"card-value\" style=\"color: {score_color}\">{score:.1f}%</div>")
    parts.append("          <div class=\"card-label\">Compliance Score</div>")
    parts.append("        </div>")
    parts.append(f"        <div class=\"card\">")
    parts.append(f"          <div class=\"card-value\">{report.total_controls}</div>")
    parts.append("          <div class=\"card-label\">Total Controls</div>")
    parts.append("        </div>")
    parts.append(f"        <div class=\"card pass\">")
    parts.append(f"          <div class=\"card-value\">{report.passed}</div>")
    parts.append("          <div class=\"card-label\">Passed</div>")
    parts.append("        </div>")
    parts.append(f"        <div class=\"card fail\">")
    parts.append(f"          <div class=\"card-value\">{report.failed}</div>")
    parts.append("          <div class=\"card-label\">Failed</div>")
    parts.append("        </div>")
    parts.append(f"        <div class=\"card\">")
    parts.append(f"          <div class=\"card-value\">{report.skipped}</div>")
    parts.append("          <div class=\"card-label\">Skipped</div>")
    parts.append("        </div>")
    parts.append("      </div>")
    parts.append("    </section>")

    # Results table
    parts.append("    <section>")
    parts.append("      <h2>Control Results</h2>")
    parts.append("      <table>")
    parts.append("        <thead>")
    parts.append("          <tr>")
    parts.append("            <th>Control</th>")
    parts.append("            <th>Title</th>")
    parts.append("            <th>Status</th>")
    parts.append("            <th>Severity</th>")
    parts.append("            <th>Duration</th>")
    parts.append("          </tr>")
    parts.append("        </thead>")
    parts.append("        <tbody>")

    for result in report.results:
        status_class = result.status.value
        max_severity = Severity.INFO
        for f in result.findings:
            if _severity_rank(f.severity) > _severity_rank(max_severity):
                max_severity = f.severity

        parts.append("          <tr>")
        parts.append(f"            <td><code>{html.escape(result.control_id)}</code></td>")
        parts.append(f"            <td>{html.escape(result.title)}</td>")
        parts.append(f"            <td><span class=\"badge {status_class}\">{result.status.value}</span></td>")
        parts.append(f"            <td><span class=\"badge {max_severity.value}\">{max_severity.value}</span></td>")
        parts.append(f"            <td>{result.duration_ms:.1f}ms</td>")
        parts.append("          </tr>")

    parts.append("        </tbody>")
    parts.append("      </table>")
    parts.append("    </section>")

    # Detailed findings for failed controls
    failed_results = [r for r in report.results if r.status == ComplianceStatus.FAIL]
    if failed_results:
        parts.append("    <section>")
        parts.append("      <h2>Failed Controls - Details</h2>")

        for result in failed_results:
            parts.append(f"      <div class=\"finding\">")
            parts.append(f"        <h3>{html.escape(result.control_id)}: {html.escape(result.title)}</h3>")

            for finding in result.findings:
                if finding.status != ComplianceStatus.FAIL:
                    continue
                parts.append(f"        <div class=\"finding-detail {finding.severity.value}\">")
                parts.append(f"          <p><strong>{html.escape(finding.message)}</strong></p>")
                if finding.remediation_hint:
                    parts.append(f"          <p><strong>Remediation:</strong> {html.escape(finding.remediation_hint)}</p>")
                parts.append("        </div>")

            parts.append("      </div>")

        parts.append("    </section>")

    parts.append("  </div>")
    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts)


_HTML_CSS = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; color: #1e293b; line-height: 1.6; }
    .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
    header { margin-bottom: 2rem; }
    h1 { font-size: 1.875rem; font-weight: 700; margin-bottom: 0.5rem; }
    h2 { font-size: 1.5rem; font-weight: 600; margin: 2rem 0 1rem; }
    h3 { font-size: 1.125rem; font-weight: 600; margin: 1rem 0 0.5rem; }
    .meta { color: #64748b; font-size: 0.875rem; }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin: 1.5rem 0; }
    .card { background: white; border: 2px solid #e2e8f0; border-radius: 0.75rem; padding: 1.25rem; text-align: center; }
    .card-value { font-size: 2rem; font-weight: 700; }
    .card-label { font-size: 0.875rem; color: #64748b; margin-top: 0.25rem; }
    .card.pass .card-value { color: #22c55e; }
    .card.fail .card-value { color: #ef4444; }
    table { width: 100%; border-collapse: collapse; background: white; border-radius: 0.75rem; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
    th { background: #f1f5f9; font-weight: 600; font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.05em; }
    tr:last-child td { border-bottom: none; }
    .badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
    .badge.pass { background: #dcfce7; color: #166534; }
    .badge.fail { background: #fee2e2; color: #991b1b; }
    .badge.error { background: #fef3c7; color: #92400e; }
    .badge.skip { background: #e2e8f0; color: #475569; }
    .badge.critical { background: #fee2e2; color: #991b1b; }
    .badge.high { background: #ffedd5; color: #9a3412; }
    .badge.medium { background: #fef3c7; color: #92400e; }
    .badge.low { background: #e0f2fe; color: #075985; }
    .badge.info { background: #e2e8f0; color: #475569; }
    .finding { background: white; border-radius: 0.75rem; padding: 1.5rem; margin: 1rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .finding-detail { border-left: 4px solid #e2e8f0; padding-left: 1rem; margin: 0.75rem 0; }
    .finding-detail.critical { border-left-color: #ef4444; }
    .finding-detail.high { border-left-color: #f97316; }
    .finding-detail.medium { border-left-color: #eab308; }
    .finding-detail.low { border-left-color: #3b82f6; }
    code { background: #f1f5f9; padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-size: 0.875rem; }
"""


def _severity_rank(severity: Severity) -> int:
    """Return a numeric rank for severity comparison."""
    ranks = {
        Severity.INFO: 0,
        Severity.LOW: 1,
        Severity.MEDIUM: 2,
        Severity.HIGH: 3,
        Severity.CRITICAL: 4,
    }
    return ranks.get(severity, 0)


# ---------------------------------------------------------------------------
# Report exporter
# ---------------------------------------------------------------------------


class ReportExporter:
    """Exports compliance reports to various formats.

    Parameters
    ----------
    output_dir:
        Directory where reports will be saved.
    """

    def __init__(self, output_dir: str | Path) -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    def export_json(self, report: ComplianceReport, filename: str | None = None) -> Path:
        """Export report as JSON."""
        filename = filename or f"compliance-{report.framework.value}-{report.report_id}.json"
        path = self._output_dir / filename
        path.write_text(generate_json_report(report), encoding="utf-8")
        return path

    def export_markdown(self, report: ComplianceReport, filename: str | None = None) -> Path:
        """Export report as Markdown."""
        filename = filename or f"compliance-{report.framework.value}-{report.report_id}.md"
        path = self._output_dir / filename
        path.write_text(generate_markdown_report(report), encoding="utf-8")
        return path

    def export_html(self, report: ComplianceReport, filename: str | None = None) -> Path:
        """Export report as HTML."""
        filename = filename or f"compliance-{report.framework.value}-{report.report_id}.html"
        path = self._output_dir / filename
        path.write_text(generate_html_report(report), encoding="utf-8")
        return path

    def export_all(self, report: ComplianceReport) -> dict[str, Path]:
        """Export report in all formats."""
        return {
            "json": self.export_json(report),
            "markdown": self.export_markdown(report),
            "html": self.export_html(report),
        }
