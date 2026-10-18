"""Dashboards for Google Chronicle SOC integration.

Provides pre-built dashboard configurations for visualizing security
events, alerts, detections, and compliance status in Chronicle.

Pure-Python implementation with no external dependencies.
"""
from __future__ import annotations

from typing import Any, Sequence

from .models import (
    ChronicleDashboard,
    DashboardWidget,
    EventSeverity,
    LogType,
)


# ---------------------------------------------------------------------------
# Pre-built dashboards
# ---------------------------------------------------------------------------


def get_builtin_dashboards() -> list[ChronicleDashboard]:
    """Get all pre-built dashboard configurations."""
    return [
        _security_overview_dashboard(),
        _authentication_dashboard(),
        _network_security_dashboard(),
        _cloud_security_dashboard(),
        _compliance_dashboard(),
        _threat_intelligence_dashboard(),
        _incident_response_dashboard(),
        _data_exfiltration_dashboard(),
    ]


def get_dashboard_names() -> list[str]:
    """Get names of all pre-built dashboards."""
    return [d.name for d in get_builtin_dashboards()]


def _security_overview_dashboard() -> ChronicleDashboard:
    """Security overview dashboard."""
    dashboard = ChronicleDashboard(
        name="Security Overview",
        description="High-level security posture and key metrics",
    )
    dashboard.add_widget(DashboardWidget(
        title="Events by Severity",
        widget_type="pie",
        query="severity != '' | group_by [severity], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Events Over Time",
        widget_type="timeseries",
        query="timestamp > now() - 24h | group_by [timestamp], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Top Event Sources",
        widget_type="table",
        query="source != '' | group_by [source], count() | sort count desc | limit 20",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Active Alerts",
        widget_type="table",
        query="alert.state == 'active' | group_by [alert.title, alert.severity], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Detections by Rule",
        widget_type="bar",
        query="detection.status == 'new' | group_by [detection.rule_name], count()",
    ))
    return dashboard


def _authentication_dashboard() -> ChronicleDashboard:
    """Authentication and access dashboard."""
    dashboard = ChronicleDashboard(
        name="Authentication & Access",
        description="Authentication events, failed logins, and access patterns",
    )
    dashboard.add_widget(DashboardWidget(
        title="Login Success vs Failure",
        widget_type="pie",
        query="event_type == 'authentication' | group_by [metadata.outcome], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Failed Logins Over Time",
        widget_type="timeseries",
        query="event_type == 'authentication' and metadata.outcome == 'FAILURE' | group_by [timestamp], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Top Users by Failed Logins",
        widget_type="table",
        query="event_type == 'authentication' and metadata.outcome == 'FAILURE' | group_by [metadata.user_name], count() | sort count desc | limit 20",
    ))
    dashboard.add_widget(DashboardWidget(
        title="MFA Status",
        widget_type="pie",
        query="event_type == 'authentication' | group_by [metadata.mfa_used], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Impossible Travel Alerts",
        widget_type="table",
        query="detection.rule_name == 'Impossible Travel Detection' | group_by [event.metadata.user_name], count()",
    ))
    return dashboard


def _network_security_dashboard() -> ChronicleDashboard:
    """Network security dashboard."""
    dashboard = ChronicleDashboard(
        name="Network Security",
        description="Network traffic, firewall events, and lateral movement",
    )
    dashboard.add_widget(DashboardWidget(
        title="Top Source IPs",
        widget_type="table",
        query="metadata.source_ip != '' | group_by [metadata.source_ip], count() | sort count desc | limit 20",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Top Destination Ports",
        widget_type="bar",
        query="metadata.destination_port != '' | group_by [metadata.destination_port], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Lateral Movement Detections",
        widget_type="table",
        query="detection.rule_name == 'Lateral Movement Detection' | group_by [event.metadata.source_ip, event.metadata.destination_ip], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="DNS Queries Over Time",
        widget_type="timeseries",
        query="metadata.dns_query != '' | group_by [timestamp], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Firewall Blocks",
        widget_type="timeseries",
        query="event_type == 'firewall' and metadata.action == 'block' | group_by [timestamp], count()",
    ))
    return dashboard


def _cloud_security_dashboard() -> ChronicleDashboard:
    """Cloud security dashboard."""
    dashboard = ChronicleDashboard(
        name="Cloud Security",
        description="Cloud API calls, IAM changes, and security group modifications",
    )
    dashboard.add_widget(DashboardWidget(
        title="AWS API Calls by Service",
        widget_type="bar",
        query="source startswith 'aws:' | group_by [metadata.event_source], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="IAM Policy Changes",
        widget_type="table",
        query="detection.rule_name == 'IAM Policy Change Detection' | group_by [event.metadata.user_name, event.metadata.event_name], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Security Group Changes",
        widget_type="table",
        query="detection.rule_name == 'Security Group Change Detection' | group_by [event.metadata.event_name], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="CloudTrail Tampering Attempts",
        widget_type="table",
        query="detection.rule_name == 'CloudTrail Tampering Detection' | group_by [event.metadata.user_name], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Azure Operations by Type",
        widget_type="bar",
        query="source startswith 'azure:' | group_by [metadata.operation], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="GCP API Calls by Method",
        widget_type="bar",
        query="source startswith 'gcp:' | group_by [metadata.method_name], count()",
    ))
    return dashboard


def _compliance_dashboard() -> ChronicleDashboard:
    """Compliance dashboard."""
    dashboard = ChronicleDashboard(
        name="Compliance",
        description="Compliance violations and control status",
    )
    dashboard.add_widget(DashboardWidget(
        title="Compliance Violations by Type",
        widget_type="bar",
        query="detection.rule_name == 'Compliance Violation Detection' | group_by [event.metadata.event_name], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Compliance Violations Over Time",
        widget_type="timeseries",
        query="detection.rule_name == 'Compliance Violation Detection' | group_by [timestamp], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Open Compliance Findings",
        widget_type="table",
        query="detection.status == 'new' and detection.rule_name == 'Compliance Violation Detection' | group_by [event.metadata.user_name], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Defense Evasion Attempts",
        widget_type="table",
        query="detection.rule_name == 'Defense Evasion Detection' | group_by [event.metadata.event_name], count()",
    ))
    return dashboard


def _threat_intelligence_dashboard() -> ChronicleDashboard:
    """Threat intelligence dashboard."""
    dashboard = ChronicleDashboard(
        name="Threat Intelligence",
        description="Malware, phishing, and threat indicators",
    )
    dashboard.add_widget(DashboardWidget(
        title="Malware Detections",
        widget_type="table",
        query="detection.rule_name == 'Malware Detection' | group_by [event.metadata.file_hash], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Phishing Attempts Over Time",
        widget_type="timeseries",
        query="detection.rule_name == 'Phishing Detection' | group_by [timestamp], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Ransomware Indicators",
        widget_type="table",
        query="detection.rule_name == 'Ransomware Detection' | group_by [event.metadata.process_name], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Credential Access Attempts",
        widget_type="table",
        query="detection.rule_name == 'Credential Access Detection' | group_by [event.metadata.event_name], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Suspicious API Calls",
        widget_type="table",
        query="detection.rule_name == 'Suspicious API Call Detection' | group_by [event.metadata.event_name], count()",
    ))
    return dashboard


def _incident_response_dashboard() -> ChronicleDashboard:
    """Incident response dashboard."""
    dashboard = ChronicleDashboard(
        name="Incident Response",
        description="Active incidents, alerts, and response metrics",
    )
    dashboard.add_widget(DashboardWidget(
        title="Active Alerts by Severity",
        widget_type="pie",
        query="alert.state == 'active' | group_by [alert.severity], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Alerts Over Time",
        widget_type="timeseries",
        query="alert.state == 'active' | group_by [timestamp], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Unassigned Alerts",
        widget_type="table",
        query="alert.state == 'active' and alert.assigned_to == '' | group_by [alert.title, alert.severity], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Detections by Status",
        widget_type="pie",
        query="detection.status != '' | group_by [detection.status], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Mean Time to Acknowledge",
        widget_type="metric",
        query="alert.state == 'acknowledged' | group_by [alert.alert_id], duration(alert.acknowledged_at, alert.created_at)",
    ))
    return dashboard


def _data_exfiltration_dashboard() -> ChronicleDashboard:
    """Data exfiltration dashboard."""
    dashboard = ChronicleDashboard(
        name="Data Exfiltration",
        description="Data transfer monitoring and exfiltration detection",
    )
    dashboard.add_widget(DashboardWidget(
        title="Large Data Transfers",
        widget_type="table",
        query="metadata.bytes_transferred > 100000000 | group_by [metadata.source_ip, metadata.destination_ip], sum(metadata.bytes_transferred)",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Data Exfiltration Detections",
        widget_type="table",
        query="detection.rule_name == 'Data Exfiltration Detection' | group_by [event.metadata.source_ip], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="VPC Flow Anomalies",
        widget_type="table",
        query="detection.rule_name == 'VPC Flow Anomaly Detection' | group_by [event.metadata.destination_ip], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="DNS Tunneling Attempts",
        widget_type="table",
        query="detection.rule_name == 'DNS Tunneling Detection' | group_by [event.metadata.dns_query], count()",
    ))
    dashboard.add_widget(DashboardWidget(
        title="Insider Threat Indicators",
        widget_type="table",
        query="detection.rule_name == 'Insider Threat Detection' | group_by [event.metadata.user_name], count()",
    ))
    return dashboard


# ---------------------------------------------------------------------------
# Dashboard builder
# ---------------------------------------------------------------------------


class DashboardBuilder:
    """Builder for custom Chronicle dashboards."""

    def __init__(self, name: str, description: str = "") -> None:
        self._dashboard = ChronicleDashboard(name=name, description=description)

    def add_widget(
        self,
        title: str,
        widget_type: str = "timeseries",
        query: str = "",
        config: dict[str, Any] | None = None,
    ) -> DashboardBuilder:
        """Add a widget to the dashboard."""
        self._dashboard.add_widget(DashboardWidget(
            title=title,
            widget_type=widget_type,
            query=query,
            config=config or {},
        ))
        return self

    def add_severity_widget(self) -> DashboardBuilder:
        """Add a severity breakdown widget."""
        return self.add_widget(
            title="Events by Severity",
            widget_type="pie",
            query="severity != '' | group_by [severity], count()",
        )

    def add_timeseries_widget(self, title: str = "Events Over Time") -> DashboardBuilder:
        """Add a timeseries widget."""
        return self.add_widget(
            title=title,
            widget_type="timeseries",
            query="timestamp > now() - 24h | group_by [timestamp], count()",
        )

    def add_source_widget(self) -> DashboardBuilder:
        """Add a top sources widget."""
        return self.add_widget(
            title="Top Event Sources",
            widget_type="table",
            query="source != '' | group_by [source], count() | sort count desc | limit 20",
        )

    def add_alert_widget(self) -> DashboardBuilder:
        """Add an active alerts widget."""
        return self.add_widget(
            title="Active Alerts",
            widget_type="table",
            query="alert.state == 'active' | group_by [alert.title, alert.severity], count()",
        )

    def build(self) -> ChronicleDashboard:
        """Build and return the dashboard."""
        return self._dashboard


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def create_dashboard(name: str, description: str = "") -> DashboardBuilder:
    """Create a new dashboard builder."""
    return DashboardBuilder(name, description)


def get_dashboard_by_name(name: str) -> ChronicleDashboard | None:
    """Get a pre-built dashboard by name."""
    for dashboard in get_builtin_dashboards():
        if dashboard.name == name:
            return dashboard
    return None
