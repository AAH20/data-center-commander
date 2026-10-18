"""Google Chronicle SOC integration for Data Center Commander.

Provides data connectors, rule engine, dashboards, and YARA-L rules
for integrating with Google Chronicle's security operations platform.

Usage
-----

.. code-block:: python

    from dcc.soc.chronicle import ChronicleIntegration

    integration = ChronicleIntegration()
    integration.load_builtin_rules()
    integration.load_builtin_dashboards()

    # Ingest security events
    events = integration.ingest_cloudtrail(raw_data)

    # Evaluate rules
    detections = integration.evaluate_events(events)

    # Get dashboards
    dashboards = integration.dashboards
"""
from __future__ import annotations

from .models import (
    AlertState,
    ChronicleDashboard,
    DashboardWidget,
    DataSource,
    DataSourceType,
    Detection,
    DetectionStatus,
    EventSeverity,
    EventStatus,
    LogType,
    RuleSeverity,
    RuleStatus,
    SOCReport,
    SecurityEvent,
    YaraRule,
)
from .connectors import (
    AWSCloudTrailConnector,
    AzureActivityConnector,
    ChronicleConnector,
    ConnectorError,
    ConnectorRegistry,
    GCPAuditConnector,
    OktaConnector,
    SyslogConnector,
    create_connector,
    ingest_azure_activity,
    ingest_cloudtrail,
    ingest_gcp_audit,
    ingest_okta,
    ingest_syslog,
)
from .rule_engine import (
    RuleEngine,
    RuleEngineError,
    RuleManager,
    RuleMatch,
    RuleNotFoundError,
    RuleValidationError,
    RuleValidator,
    create_rule_engine,
    create_rule_manager,
    evaluate_event,
)
from .rules import (
    find_rule_by_name,
    get_builtin_rules,
    get_rule_count,
    get_rule_names,
    get_rules_by_severity,
    get_rules_by_tag,
)
from .dashboards import (
    DashboardBuilder,
    create_dashboard,
    get_builtin_dashboards,
    get_dashboard_by_name,
    get_dashboard_names,
)


class ChronicleIntegration:
    """Main facade for Google Chronicle SOC integration.

    Provides a unified interface for data ingestion, rule evaluation,
    alert management, and dashboard configuration.

    Attributes
    ----------
    engine:
        The rule engine for evaluating YARA-L rules.
    rule_manager:
        The rule manager for CRUD operations on rules.
    dashboards:
        List of configured dashboards.
    data_sources:
        List of configured data sources.
    """

    def __init__(self) -> None:
        self._engine = RuleEngine()
        self._rule_manager = RuleManager()
        self._dashboards: list[ChronicleDashboard] = []
        self._data_sources: list[DataSource] = []
        self._alerts: list = []
        self._detections: list[Detection] = []
        self._events: list[SecurityEvent] = []

    @property
    def engine(self) -> RuleEngine:
        """Get the rule engine."""
        return self._engine

    @property
    def rule_manager(self) -> RuleManager:
        """Get the rule manager."""
        return self._rule_manager

    @property
    def dashboards(self) -> list[ChronicleDashboard]:
        """Get all configured dashboards."""
        return list(self._dashboards)

    @property
    def data_sources(self) -> list[DataSource]:
        """Get all configured data sources."""
        return list(self._data_sources)

    @property
    def alerts(self) -> list:
        """Get all alerts."""
        return list(self._alerts)

    @property
    def detections(self) -> list[Detection]:
        """Get all detections."""
        return list(self._detections)

    @property
    def events(self) -> list[SecurityEvent]:
        """Get all events."""
        return list(self._events)

    def load_builtin_rules(self) -> int:
        """Load all built-in YARA-L rules into the engine.

        Returns
        -------
        int
            Number of rules loaded.
        """
        count = 0
        for rule in get_builtin_rules():
            try:
                self._engine.register(rule)
                self._rule_manager._rules[rule.rule_id] = rule
                count += 1
            except Exception:
                continue
        return count

    def load_builtin_dashboards(self) -> int:
        """Load all pre-built dashboards.

        Returns
        -------
        int
            Number of dashboards loaded.
        """
        self._dashboards = get_builtin_dashboards()
        return len(self._dashboards)

    def add_data_source(self, source: DataSource) -> None:
        """Add a data source configuration."""
        self._data_sources.append(source)

    def ingest_cloudtrail(self, raw_data: str | bytes | dict) -> list[SecurityEvent]:
        """Ingest AWS CloudTrail data."""
        events = ingest_cloudtrail(raw_data)
        self._events.extend(events)
        return events

    def ingest_azure_activity(self, raw_data: str | bytes | dict) -> list[SecurityEvent]:
        """Ingest Azure Activity data."""
        events = ingest_azure_activity(raw_data)
        self._events.extend(events)
        return events

    def ingest_gcp_audit(self, raw_data: str | bytes | dict) -> list[SecurityEvent]:
        """Ingest GCP Audit data."""
        events = ingest_gcp_audit(raw_data)
        self._events.extend(events)
        return events

    def ingest_syslog(self, raw_data: str | bytes) -> list[SecurityEvent]:
        """Ingest syslog data."""
        events = ingest_syslog(raw_data)
        self._events.extend(events)
        return events

    def ingest_okta(self, raw_data: str | bytes | dict) -> list[SecurityEvent]:
        """Ingest Okta data."""
        events = ingest_okta(raw_data)
        self._events.extend(events)
        return events

    def evaluate_events(self, events: list[SecurityEvent] | None = None) -> list[Detection]:
        """Evaluate rules against events and return detections.

        Parameters
        ----------
        events:
            Events to evaluate. If None, uses all ingested events.

        Returns
        -------
        list[Detection]
            Detections produced by rule matches.
        """
        if events is None:
            events = self._events
        detections = self._engine.evaluate_batch_and_create(events)
        self._detections.extend(detections)
        return detections

    def create_alert(
        self,
        title: str,
        description: str = "",
        severity: EventSeverity = EventSeverity.MEDIUM,
        events: list[SecurityEvent] | None = None,
    ):
        """Create a new alert."""
        from .models import ChronicleAlert
        alert = ChronicleAlert(
            title=title,
            description=description,
            severity=severity,
            events=events or [],
        )
        self._alerts.append(alert)
        return alert

    def get_report(self) -> SOCReport:
        """Generate a SOC report from all collected data."""
        severity_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}

        for event in self._events:
            sev = event.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            src = event.source
            source_counts[src] = source_counts.get(src, 0) + 1

        return SOCReport(
            total_events=len(self._events),
            total_alerts=len(self._alerts),
            total_detections=len(self._detections),
            events=list(self._events),
            alerts=list(self._alerts),
            detections=list(self._detections),
            severity_counts=severity_counts,
            source_counts=source_counts,
        )

    def reset(self) -> None:
        """Reset all collected data."""
        self._events.clear()
        self._alerts.clear()
        self._detections.clear()


__all__ = [
    # Models
    "AlertState",
    "ChronicleDashboard",
    "DashboardWidget",
    "DataSource",
    "DataSourceType",
    "Detection",
    "DetectionStatus",
    "EventSeverity",
    "EventStatus",
    "LogType",
    "RuleSeverity",
    "RuleStatus",
    "SOCReport",
    "SecurityEvent",
    "YaraRule",
    # Connectors
    "AWSCloudTrailConnector",
    "AzureActivityConnector",
    "ChronicleConnector",
    "ConnectorError",
    "ConnectorRegistry",
    "GCPAuditConnector",
    "OktaConnector",
    "SyslogConnector",
    "create_connector",
    "ingest_azure_activity",
    "ingest_cloudtrail",
    "ingest_gcp_audit",
    "ingest_okta",
    "ingest_syslog",
    # Rule engine
    "RuleEngine",
    "RuleEngineError",
    "RuleManager",
    "RuleMatch",
    "RuleNotFoundError",
    "RuleValidationError",
    "RuleValidator",
    "create_rule_engine",
    "create_rule_manager",
    "evaluate_event",
    # Rules
    "find_rule_by_name",
    "get_builtin_rules",
    "get_rule_count",
    "get_rule_names",
    "get_rules_by_severity",
    "get_rules_by_tag",
    # Dashboards
    "DashboardBuilder",
    "create_dashboard",
    "get_builtin_dashboards",
    "get_dashboard_by_name",
    "get_dashboard_names",
    # Integration
    "ChronicleIntegration",
]
