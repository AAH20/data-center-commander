"""Main OSSEC SOC engine — orchestrates connectors, rules, dashboards, and active response."""
from __future__ import annotations

from typing import Optional

from .active_response import ActiveResponseEngine
from .connectors import OSSECAPIConnector, OSSECLogConnector, OSSECQueueConnector
from .dashboards import OSSECDashboard
from .models import OSSECAlert, OSSECEvent, OSSECStatus, Severity
from .rules import CorrelationRule, RuleEngine


class OSSECEngine:
    """Main entry point for OSSEC SOC integration.

    Orchestrates data connectors, detection rules, dashboards,
    and active response for OSSEC security operations.
    """

    def __init__(self) -> None:
        self.connectors: list[OSSECLogConnector | OSSECAPIConnector | OSSECQueueConnector] = []
        self.rule_engine = RuleEngine()
        self.dashboard = OSSECDashboard()
        self.active_response = ActiveResponseEngine()
        self._alerts: list[OSSECAlert] = []
        self._agents: list[OSSECStatus] = []

    def add_log_connector(self, log_path: str) -> OSSECLogConnector:
        """Add a file-based log connector."""
        connector = OSSECLogConnector(log_path)
        self.connectors.append(connector)
        return connector

    def add_api_connector(
        self,
        host: str = "localhost",
        port: int = 55000,
        username: str = "wazuh",
        password: str = "",
        use_ssl: bool = True,
    ) -> OSSECAPIConnector:
        """Add an API-based connector."""
        connector = OSSECAPIConnector(
            host=host, port=port, username=username, password=password, use_ssl=use_ssl
        )
        self.connectors.append(connector)
        return connector

    def add_queue_connector(self, queue_path: str = "/var/ossec/queue/alerts") -> OSSECQueueConnector:
        """Add a queue-based connector."""
        connector = OSSECQueueConnector(queue_path)
        self.connectors.append(connector)
        return connector

    def ingest_alerts(self) -> list[OSSECAlert]:
        """Ingest alerts from all configured connectors."""
        alerts: list[OSSECAlert] = []

        for connector in self.connectors:
            if isinstance(connector, OSSECLogConnector):
                alerts.extend(connector.ingest())
            elif isinstance(connector, OSSECAPIConnector):
                alerts.extend(connector.get_agents())
                alerts.extend(connector.get_alerts())

        self._alerts.extend(alerts)
        self.dashboard.load_alerts(self._alerts)
        return alerts

    def ingest_agents(self) -> list[OSSECStatus]:
        """Ingest agent status from API connectors."""
        agents: list[OSSECStatus] = []

        for connector in self.connectors:
            if isinstance(connector, OSSECAPIConnector):
                agents.extend(connector.get_agents())

        self._agents.extend(agents)
        self.dashboard.load_agents(self._agents)
        return agents

    def run_correlation(self) -> list[dict]:
        """Run correlation rules against ingested alerts."""
        return self.rule_engine.correlate(self._alerts)

    def evaluate_active_response(
        self, alert: OSSECAlert, dry_run: bool = True
    ) -> list:
        """Evaluate and optionally execute active responses for an alert."""
        triggered = self.active_response.evaluate_alert(alert)
        executions = []

        for response in triggered:
            execution = self.active_response.execute_response(
                response, alert, dry_run=dry_run
            )
            executions.append(execution)

        return executions

    def generate_dashboard(self, output_path: str, format: str = "json") -> None:
        """Generate dashboard output."""
        if format == "json":
            self.dashboard.export_json(output_path)
        elif format == "html":
            self.dashboard.export_html(output_path)

    def get_summary(self) -> dict:
        """Get SOC summary."""
        return self.dashboard.summary()
