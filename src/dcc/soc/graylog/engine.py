"""Graylog SOC orchestration engine."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .alerts import GraylogAlertManager
from .connectors import GraylogAPIConfig, GraylogConnectorManager
from .dashboards import GraylogDashboardManager
from .events import GraylogEventManager
from .models import (
    GraylogAlert,
    GraylogAlertSeverity,
    GraylogEventStatus,
    GraylogSOCStatus,
)
from .streams import GraylogStreamManager

logger = logging.getLogger(__name__)


class GraylogSOCEngine:
    """Main orchestration engine for Graylog OSS SOC integration."""

    def __init__(self, config: Optional[GraylogAPIConfig] = None) -> None:
        self.config = config or GraylogAPIConfig()
        self.connectors = GraylogConnectorManager(self.config)
        self.streams = GraylogStreamManager()
        self.alerts = GraylogAlertManager()
        self.events = GraylogEventManager()
        self.dashboards = GraylogDashboardManager()
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the SOC engine with default configuration."""
        if self._initialized:
            return

        logger.info("Initializing Graylog SOC engine...")

        # Create default streams
        self._create_default_streams()

        # Create default connectors
        self._create_default_connectors()

        # Create default event definitions
        self._create_default_events()

        # Create default dashboards
        self._create_default_dashboards()

        self._initialized = True
        logger.info("Graylog SOC engine initialized successfully")

    def _create_default_streams(self) -> None:
        """Create default security streams."""
        self.streams.create_security_stream()
        self.streams.create_firewall_stream()
        self.streams.create_ids_stream()
        self.streams.create_auth_stream()
        self.streams.create_web_stream()
        self.streams.create_audit_stream()

    def _create_default_connectors(self) -> None:
        """Create default data connectors."""
        self.connectors.create_syslog_udp_connector(port=514)
        self.connectors.create_syslog_tcp_connector(port=1514)
        self.connectors.create_gelf_connector(port=12201)
        self.connectors.create_beats_connector(port=5044)
        self.connectors.create_cef_connector(port=1514)
        self.connectors.create_netflow_connector(port=2055)

    def _create_default_events(self) -> None:
        """Create default event definitions."""
        self.events.create_brute_force_rule()
        self.events.create_port_scan_rule()
        self.events.create_malware_detection_rule()
        self.events.create_data_exfiltration_rule()
        self.events.create_privilege_escalation_rule()
        self.events.create_lateral_movement_rule()
        self.events.create_web_attack_rule()
        self.events.create_anomaly_detection_rule()

    def _create_default_dashboards(self) -> None:
        """Create default dashboards."""
        self.dashboards.create_security_overview_dashboard()
        self.dashboards.create_threat_hunting_dashboard()
        self.dashboards.create_compliance_dashboard()
        self.dashboards.create_auth_monitoring_dashboard()

    def get_status(self) -> GraylogSOCStatus:
        """Get overall SOC status."""
        return GraylogSOCStatus(
            server_id="graylog-soc",
            cluster_name="graylog-soc-cluster",
            version="5.1.0",
            is_processing=True,
            is_leader=True,
            last_seen=datetime.now(timezone.utc).isoformat(),
            streams_count=len(self.streams.list_streams()),
            connectors_count=len(self.connectors.list_connectors()),
            events_count=len(self.events.list_events()),
            alerts_count=len(self.alerts.list_alerts()),
            dashboards_count=len(self.dashboards.list_dashboards()),
            index_sets_count=1,
            throughput_in=0,
            throughput_out=0,
            journal_size=0,
            journal_age=0,
        )

    def get_open_alerts(
        self, min_severity: GraylogAlertSeverity = GraylogAlertSeverity.LOW
    ) -> list[GraylogAlert]:
        """Get open alerts with severity >= min_severity."""
        return self.alerts.get_open_alerts(min_severity)

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert."""
        return self.alerts.acknowledge_alert(alert_id, acknowledged_by)

    def resolve_alert(self, alert_id: str, notes: str = "") -> bool:
        """Resolve an alert."""
        return self.alerts.resolve_alert(alert_id, notes)

    def get_alert_stats(self) -> dict[str, Any]:
        """Get alert statistics."""
        return self.alerts.get_alert_stats()

    def create_incident_from_alert(self, alert_id: str) -> dict[str, Any]:
        """Create an incident from an alert."""
        alert = self.alerts.get_alert(alert_id)
        if not alert:
            return {}

        return {
            "incident_id": f"INC-{alert_id}",
            "title": alert.event_definition_title,
            "description": alert.message,
            "severity": alert.severity.name,
            "status": "new",
            "source": alert.source,
            "related_alerts": [alert_id],
            "mitre_tactics": alert.mitre_tactics,
            "mitre_techniques": alert.mitre_techniques,
            "compliance_refs": alert.compliance_refs,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def export_configuration(self) -> dict[str, Any]:
        """Export full SOC configuration."""
        return {
            "streams": [
                self.streams.to_api_payload(s) for s in self.streams.list_streams()
            ],
            "connectors": [
                self.connectors.to_api_payload(c) for c in self.connectors.list_connectors()
            ],
            "events": [
                self.events.to_api_payload(e) for e in self.events.list_events()
            ],
            "dashboards": [
                self.dashboards.to_api_payload(d) for d in self.dashboards.list_dashboards()
            ],
            "alerts": [
                self.alerts.to_api_payload(a) for a in self.alerts.list_alerts()
            ],
        }

    def health_check(self) -> dict[str, Any]:
        """Perform health check."""
        status = self.get_status()
        return {
            "healthy": status.is_processing,
            "server_id": status.server_id,
            "version": status.version,
            "is_leader": status.is_leader,
            "streams_count": status.streams_count,
            "connectors_count": status.connectors_count,
            "events_count": status.events_count,
            "alerts_count": status.alerts_count,
            "dashboards_count": status.dashboards_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
