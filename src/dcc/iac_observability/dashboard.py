"""IaC observability dashboard: unified dashboard for all monitoring data.

Aggregates drift, compliance, cost anomaly, and security alert data
into a unified dashboard view for infrastructure monitoring.

Pure-Python implementation with no external dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from .compliance import ComplianceReport, build_compliance_dashboard
from .cost_anomaly import CostAnomalyReport, build_cost_dashboard
from .drift import DriftResult, summarize_drift
from .security_alerts import SecurityAlertReport, build_security_dashboard


class DashboardStatus(str, Enum):
    """Overall dashboard health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


@dataclass
class DashboardPanel:
    """A single dashboard panel."""

    name: str
    title: str
    status: str
    summary: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "status": self.status,
            "summary": self.summary,
            "details": self.details,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class DashboardReport:
    """Unified dashboard report."""

    status: DashboardStatus
    panels: list[DashboardPanel] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "generated_at": self.generated_at.isoformat(),
            "metadata": self.metadata,
            "panels": [p.to_dict() for p in self.panels],
        }


class IaCDashboard:
    """Unified IaC observability dashboard.

    Aggregates data from drift detection, compliance checking,
    cost anomaly detection, and security alerting into a single
    dashboard view.
    """

    def __init__(self) -> None:
        self._drift_result: DriftResult | None = None
        self._compliance_report: ComplianceReport | None = None
        self._cost_report: CostAnomalyReport | None = None
        self._security_report: SecurityAlertReport | None = None

    def set_drift_result(self, result: DriftResult) -> None:
        """Set drift detection results."""
        self._drift_result = result

    def set_compliance_report(self, report: ComplianceReport) -> None:
        """Set compliance report."""
        self._compliance_report = report

    def set_cost_report(self, report: CostAnomalyReport) -> None:
        """Set cost anomaly report."""
        self._cost_report = report

    def set_security_report(self, report: SecurityAlertReport) -> None:
        """Set security alert report."""
        self._security_report = report

    def build(self) -> DashboardReport:
        """Build the unified dashboard report."""
        panels: list[DashboardPanel] = []
        statuses: list[str] = []

        # Drift panel
        if self._drift_result:
            drift_summary = summarize_drift(self._drift_result)
            drift_status = "healthy" if not self._drift_result.has_drift else (
                "critical" if drift_summary["severity_counts"].get("critical", 0) > 0 else
                "degraded" if drift_summary["severity_counts"].get("high", 0) > 0 else
                "warning"
            )
            panels.append(DashboardPanel(
                name="drift",
                title="Configuration Drift",
                status=drift_status,
                summary={
                    "total_drifted": self._drift_result.total_drifted,
                    "drift_rate": round(self._drift_result.drift_rate * 100, 2),
                    "severity_counts": self._drift_result.severity_counts,
                },
                details=drift_summary,
            ))
            statuses.append(drift_status)

        # Compliance panel
        if self._compliance_report:
            compliance_dashboard = build_compliance_dashboard(self._compliance_report)
            compliance_status = "healthy" if self._compliance_report.overall_status.value == "pass" else (
                "critical" if self._compliance_report.severity_summary.get("critical", 0) > 0 else
                "degraded" if self._compliance_report.failed > 0 else
                "warning"
            )
            panels.append(DashboardPanel(
                name="compliance",
                title="Compliance",
                status=compliance_status,
                summary={
                    "compliance_rate": compliance_dashboard["compliance_rate"],
                    "total_checks": self._compliance_report.total_checks,
                    "passed": self._compliance_report.passed,
                    "failed": self._compliance_report.failed,
                },
                details=compliance_dashboard,
            ))
            statuses.append(compliance_status)

        # Cost panel
        if self._cost_report:
            cost_dashboard = build_cost_dashboard(self._cost_report)
            cost_status = "healthy" if not self._cost_report.has_anomalies else (
                "critical" if self._cost_report.severity_counts.get("critical", 0) > 0 else
                "degraded" if self._cost_report.severity_counts.get("high", 0) > 0 else
                "warning"
            )
            panels.append(DashboardPanel(
                name="cost",
                title="Cost Anomalies",
                status=cost_status,
                summary={
                    "total_anomalies": self._cost_report.total_anomalies,
                    "total_variance": round(self._cost_report.total_variance, 2),
                    "variance_pct": round(self._cost_report.variance_pct, 2),
                    "severity_counts": self._cost_report.severity_counts,
                },
                details=cost_dashboard,
            ))
            statuses.append(cost_status)

        # Security panel
        if self._security_report:
            security_dashboard = build_security_dashboard(self._security_report)
            security_status = "healthy" if self._security_report.open_alerts == 0 else (
                "critical" if self._security_report.has_critical else
                "degraded" if self._security_report.severity_counts.get("high", 0) > 0 else
                "warning"
            )
            panels.append(DashboardPanel(
                name="security",
                title="Security Alerts",
                status=security_status,
                summary={
                    "total_alerts": self._security_report.total_alerts,
                    "open_alerts": self._security_report.open_alerts,
                    "critical_count": self._security_report.critical_count,
                    "severity_counts": self._security_report.severity_counts,
                },
                details=security_dashboard,
            ))
            statuses.append(security_status)

        # Determine overall status
        overall = self._compute_overall_status(statuses)

        return DashboardReport(
            status=overall,
            panels=panels,
            metadata={
                "panel_count": len(panels),
                "statuses": statuses,
            },
        )

    def _compute_overall_status(self, statuses: list[str]) -> DashboardStatus:
        """Compute overall dashboard status from panel statuses."""
        if not statuses:
            return DashboardStatus.HEALTHY
        if "critical" in statuses:
            return DashboardStatus.CRITICAL
        if "unhealthy" in statuses:
            return DashboardStatus.UNHEALTHY
        if "degraded" in statuses:
            return DashboardStatus.DEGRADED
        if "warning" in statuses:
            return DashboardStatus.DEGRADED
        return DashboardStatus.HEALTHY


def build_dashboard(
    drift_result: DriftResult | None = None,
    compliance_report: ComplianceReport | None = None,
    cost_report: CostAnomalyReport | None = None,
    security_report: SecurityAlertReport | None = None,
) -> DashboardReport:
    """Convenience function to build a unified dashboard."""
    dashboard = IaCDashboard()
    if drift_result:
        dashboard.set_drift_result(drift_result)
    if compliance_report:
        dashboard.set_compliance_report(compliance_report)
    if cost_report:
        dashboard.set_cost_report(cost_report)
    if security_report:
        dashboard.set_security_report(security_report)
    return dashboard.build()
