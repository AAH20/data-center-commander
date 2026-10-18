"""QRadar dashboard definitions for data center security monitoring.

Provides dashboard definitions that can be imported into QRadar to
visualize data center security metrics, offense trends, and threat
landscape. Dashboards are defined as Python data structures that map
to QRadar's dashboard JSON format.

Contract/design only — no live QRadar integration is certified.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Widget types
# ---------------------------------------------------------------------------

class WidgetType(str, Enum):
    """Type of dashboard widget."""
    BAR_CHART = "bar_chart"
    LINE_CHART = "line_chart"
    PIE_CHART = "pie_chart"
    TABLE = "table"
    HEAT_MAP = "heat_map"
    GAUGE = "gauge"
    MAP = "map"
    TEXT = "text"
    LIST = "list"
    TIMELINE = "timeline"
    SCATTER = "scatter"
    DONUT = "donut"
    AREA = "area"


class WidgetDataSource(str, Enum):
    """Data source type for a widget."""
    AQL = "aql"
    REFERENCE_SET = "reference_set"
    RULE = "rule"
    OFFENSE = "offense"
    EVENT = "event"
    FLOW = "flow"
    ASSET = "asset"


# ---------------------------------------------------------------------------
# Widget models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class WidgetConfig:
    """Configuration for a single dashboard widget."""
    widget_id: str
    title: str
    widget_type: WidgetType
    data_source: WidgetDataSource
    query: str
    width: int = 6
    height: int = 4
    refresh_interval_seconds: int = 300
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "title": self.title,
            "widget_type": self.widget_type.value,
            "data_source": self.data_source.value,
            "query": self.query,
            "width": self.width,
            "height": self.height,
            "refresh_interval_seconds": self.refresh_interval_seconds,
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WidgetConfig:
        return cls(
            widget_id=str(data["widget_id"]),
            title=str(data.get("title", "")),
            widget_type=WidgetType(data.get("widget_type", "table")),
            data_source=WidgetDataSource(data.get("data_source", "aql")),
            query=str(data.get("query", "")),
            width=int(data.get("width", 6)),
            height=int(data.get("height", 4)),
            refresh_interval_seconds=int(data.get("refresh_interval_seconds", 300)),
            parameters=dict(data.get("parameters", {})),
        )


@dataclass(slots=True)
class QRadarDashboardDefinition:
    """A complete QRadar dashboard definition."""
    dashboard_id: str
    name: str
    description: str
    widgets: list[WidgetConfig] = field(default_factory=list)
    owner: str = "dcc"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "dashboard_id": self.dashboard_id,
            "name": self.name,
            "description": self.description,
            "widgets": [w.to_dict() for w in self.widgets],
            "owner": self.owner,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    def to_qradar_json(self) -> str:
        """Export as QRadar-compatible dashboard JSON."""
        qradar_format = {
            "name": self.name,
            "description": self.description,
            "owner": self.owner,
            "tags": self.tags,
            "widgets": [
                {
                    "id": w.widget_id,
                    "title": w.title,
                    "type": w.widget_type.value,
                    "data_source": w.data_source.value,
                    "query": w.query,
                    "layout": {
                        "x": 0,
                        "y": 0,
                        "w": w.width,
                        "h": w.height,
                    },
                    "refresh_interval": w.refresh_interval_seconds,
                    "parameters": w.parameters,
                }
                for w in self.widgets
            ],
        }
        return json.dumps(qradar_format, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QRadarDashboardDefinition:
        """Reconstruct from dictionary."""
        return cls(
            dashboard_id=str(data["dashboard_id"]),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            widgets=[WidgetConfig.from_dict(w) for w in data.get("widgets", [])],
            owner=str(data.get("owner", "dcc")),
            tags=list(data.get("tags", [])),
            metadata=dict(data.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Pre-built data center dashboards
# ---------------------------------------------------------------------------

def get_data_center_dashboards() -> list[QRadarDashboardDefinition]:
    """Return the default set of data center security dashboards for QRadar."""
    return [
        # Dashboard 1: Executive Overview
        QRadarDashboardDefinition(
            dashboard_id="dcc-exec-overview",
            name="DCC: Executive Security Overview",
            description="High-level security posture overview for data center operations, including open offenses, critical alerts, and trend analysis.",
            widgets=[
                WidgetConfig(
                    widget_id="exec-open-offenses",
                    title="Open Offenses by Severity",
                    widget_type=WidgetType.BAR_CHART,
                    data_source=WidgetDataSource.OFFENSE,
                    query="SELECT severity, COUNT(*) FROM offenses WHERE status='open' GROUP BY severity",
                    width=6,
                    height=4,
                ),
                WidgetConfig(
                    widget_id="exec-offense-trend",
                    title="Offense Trend (Last 30 Days)",
                    widget_type=WidgetType.LINE_CHART,
                    data_source=WidgetDataSource.OFFENSE,
                    query="SELECT DATE(start_time) as day, COUNT(*) FROM offenses GROUP BY day ORDER BY day",
                    width=6,
                    height=4,
                ),
                WidgetConfig(
                    widget_id="exec-top-rules",
                    title="Top Triggering Rules",
                    widget_type=WidgetType.TABLE,
                    data_source=WidgetDataSource.RULE,
                    query="SELECT rule_name, COUNT(*) as trigger_count FROM events GROUP BY rule_name ORDER BY trigger_count DESC LIMIT 10",
                    width=12,
                    height=4,
                ),
                WidgetConfig(
                    widget_id="exec-critical-assets",
                    title="Critical Assets at Risk",
                    widget_type=WidgetType.TABLE,
                    data_source=WidgetDataSource.ASSET,
                    query="SELECT name, risk_score, vulnerability_count FROM assets WHERE criticality >= 4 ORDER BY risk_score DESC LIMIT 10",
                    width=12,
                    height=4,
                ),
            ],
            tags=["executive", "overview", "dcc"],
        ),
        # Dashboard 2: Threat Detection
        QRadarDashboardDefinition(
            dashboard_id="dcc-threat-detection",
            name="DCC: Threat Detection & Analysis",
            description="Real-time threat detection dashboard showing active threats, MITRE ATT&CK mapping, and threat intelligence matches.",
            widgets=[
                WidgetConfig(
                    widget_id="threat-mitre",
                    title="MITRE ATT&CK Coverage",
                    widget_type=WidgetType.HEAT_MAP,
                    data_source=WidgetDataSource.EVENT,
                    query="SELECT mitre_tactic, mitre_technique, COUNT(*) FROM events WHERE mitre_tactic IS NOT NULL GROUP BY mitre_tactic, mitre_technique",
                    width=8,
                    height=6,
                ),
                WidgetConfig(
                    widget_id="threat-intel-matches",
                    title="Threat Intelligence Matches",
                    widget_type=WidgetType.TABLE,
                    data_source=WidgetDataSource.EVENT,
                    query="SELECT source_ip, destination_ip, threat_intel_source, confidence FROM events WHERE threat_intel_match=true",
                    width=12,
                    height=4,
                ),
                WidgetConfig(
                    widget_id="threat-severity-dist",
                    title="Threat Severity Distribution",
                    widget_type=WidgetType.PIE_CHART,
                    data_source=WidgetDataSource.OFFENSE,
                    query="SELECT severity, COUNT(*) FROM offenses GROUP BY severity",
                    width=4,
                    height=4,
                ),
                WidgetConfig(
                    widget_id="threat-timeline",
                    title="Threat Activity Timeline",
                    widget_type=WidgetType.TIMELINE,
                    data_source=WidgetDataSource.EVENT,
                    query="SELECT start_time, event_name, severity FROM events ORDER BY start_time DESC LIMIT 100",
                    width=12,
                    height=4,
                ),
            ],
            tags=["threat", "detection", "mitre", "dcc"],
        ),
        # Dashboard 3: Network Security
        QRadarDashboardDefinition(
            dashboard_id="dcc-network-security",
            name="DCC: Network Security Monitor",
            description="Network security monitoring dashboard showing traffic anomalies, top talkers, and suspicious connections.",
            widgets=[
                WidgetConfig(
                    widget_id="net-top-talkers",
                    title="Top Talkers by Volume",
                    widget_type=WidgetType.BAR_CHART,
                    data_source=WidgetDataSource.FLOW,
                    query="SELECT source_ip, SUM(bytes) as total_bytes FROM flows GROUP BY source_ip ORDER BY total_bytes DESC LIMIT 10",
                    width=6,
                    height=4,
                ),
                WidgetConfig(
                    widget_id="net-protocol-dist",
                    title="Protocol Distribution",
                    widget_type=WidgetType.DONUT,
                    data_source=WidgetDataSource.FLOW,
                    query="SELECT protocol, COUNT(*) FROM flows GROUP BY protocol",
                    width=4,
                    height=4,
                ),
                WidgetConfig(
                    widget_id="net-suspicious",
                    title="Suspicious Connections",
                    widget_type=WidgetType.TABLE,
                    data_source=WidgetDataSource.FLOW,
                    query="SELECT source_ip, destination_ip, destination_port, bytes FROM flows WHERE destination_port IN (4444, 5555, 6666, 31337) ORDER BY bytes DESC",
                    width=12,
                    height=4,
                ),
                WidgetConfig(
                    widget_id="net-geo",
                    title="Geographic Traffic Distribution",
                    widget_type=WidgetType.MAP,
                    data_source=WidgetDataSource.FLOW,
                    query="SELECT source_country, COUNT(*) as count FROM flows WHERE source_country IS NOT NULL GROUP BY source_country",
                    width=8,
                    height=4,
                ),
            ],
            tags=["network", "traffic", "monitoring", "dcc"],
        ),
        # Dashboard 4: Compliance & Policy
        QRadarDashboardDefinition(
            dashboard_id="dcc-compliance",
            name="DCC: Compliance & Policy Monitor",
            description="Compliance monitoring dashboard showing policy violations, compliance posture, and audit trail.",
            widgets=[
                WidgetConfig(
                    widget_id="comp-violations",
                    title="Policy Violations by Type",
                    widget_type=WidgetType.BAR_CHART,
                    data_source=WidgetDataSource.EVENT,
                    query="SELECT policy_type, COUNT(*) FROM events WHERE violation_type='detected' GROUP BY policy_type",
                    width=6,
                    height=4,
                ),
                WidgetConfig(
                    widget_id="comp-posture",
                    title="Compliance Posture Score",
                    widget_type=WidgetType.GAUGE,
                    data_source=WidgetDataSource.EVENT,
                    query="SELECT AVG(compliance_score) as score FROM events WHERE compliance_score IS NOT NULL",
                    width=4,
                    height=4,
                ),
                WidgetConfig(
                    widget_id="comp-audit",
                    title="Recent Audit Events",
                    widget_type=WidgetType.TABLE,
                    data_source=WidgetDataSource.EVENT,
                    query="SELECT start_time, username, action, resource FROM events WHERE category='audit' ORDER BY start_time DESC LIMIT 20",
                    width=12,
                    height=4,
                ),
                WidgetConfig(
                    widget_id="comp-trend",
                    title="Compliance Trend",
                    widget_type=WidgetType.AREA,
                    data_source=WidgetDataSource.EVENT,
                    query="SELECT DATE(start_time) as day, compliance_score FROM events WHERE compliance_score IS NOT NULL GROUP BY day ORDER BY day",
                    width=12,
                    height=4,
                ),
            ],
            tags=["compliance", "policy", "audit", "dcc"],
        ),
        # Dashboard 5: Incident Response
        QRadarDashboardDefinition(
            dashboard_id="dcc-incident-response",
            name="DCC: Incident Response Tracker",
            description="Incident response dashboard for tracking active incidents, response actions, and resolution status.",
            widgets=[
                WidgetConfig(
                    widget_id="ir-active",
                    title="Active Incidents",
                    widget_type=WidgetType.TABLE,
                    data_source=WidgetDataSource.OFFENSE,
                    query="SELECT offense_id, description, severity, assigned_to, event_count FROM offenses WHERE status='open' ORDER BY severity DESC",
                    width=12,
                    height=4,
                ),
                WidgetConfig(
                    widget_id="ir-severity",
                    title="Incidents by Severity",
                    widget_type=WidgetType.PIE_CHART,
                    data_source=WidgetDataSource.OFFENSE,
                    query="SELECT severity, COUNT(*) FROM offenses WHERE status='open' GROUP BY severity",
                    width=4,
                    height=4,
                ),
                WidgetConfig(
                    widget_id="ir-response-time",
                    title="Average Response Time",
                    widget_type=WidgetType.GAUGE,
                    data_source=WidgetDataSource.OFFENSE,
                    query="SELECT AVG(response_time_hours) as avg_time FROM offenses WHERE status='closed'",
                    width=4,
                    height=4,
                ),
                WidgetConfig(
                    widget_id="ir-recent-closed",
                    title="Recently Closed Incidents",
                    widget_type=WidgetType.LIST,
                    data_source=WidgetDataSource.OFFENSE,
                    query="SELECT offense_id, description, close_reason FROM offenses WHERE status='closed' ORDER BY close_time DESC LIMIT 10",
                    width=12,
                    height=4,
                ),
            ],
            tags=["incident", "response", "tracking", "dcc"],
        ),
    ]


# ---------------------------------------------------------------------------
# Dashboard management
# ---------------------------------------------------------------------------

class QRadarDashboardManager:
    """Manages QRadar dashboard definitions and deployment."""

    def __init__(self) -> None:
        self._dashboards: dict[str, QRadarDashboardDefinition] = {}

    def add_dashboard(self, dashboard: QRadarDashboardDefinition) -> None:
        """Add a dashboard definition."""
        self._dashboards[dashboard.dashboard_id] = dashboard

    def remove_dashboard(self, dashboard_id: str) -> bool:
        """Remove a dashboard definition. Returns True if it existed."""
        return self._dashboards.pop(dashboard_id, None) is not None

    def get_dashboard(self, dashboard_id: str) -> QRadarDashboardDefinition | None:
        """Get a dashboard definition by ID."""
        return self._dashboards.get(dashboard_id)

    def get_dashboards(
        self,
        *,
        tag: str | None = None,
    ) -> list[QRadarDashboardDefinition]:
        """Get dashboards, optionally filtered by tag."""
        results: list[QRadarDashboardDefinition] = []
        for dashboard in self._dashboards.values():
            if tag is not None and tag not in dashboard.tags:
                continue
            results.append(dashboard)
        return results

    def export_to_json(self, *, indent: int = 2) -> str:
        """Export all dashboards as JSON."""
        data = [dashboard.to_dict() for dashboard in self._dashboards.values()]
        return json.dumps(data, indent=indent)

    def export_to_qradar_format(self) -> str:
        """Export all dashboards in QRadar-compatible format."""
        data = [json.loads(dashboard.to_qradar_json()) for dashboard in self._dashboards.values()]
        return json.dumps(data, indent=2)

    def load_defaults(self) -> None:
        """Load the default data center security dashboards."""
        for dashboard in get_data_center_dashboards():
            self.add_dashboard(dashboard)

    @property
    def dashboard_count(self) -> int:
        return len(self._dashboards)
