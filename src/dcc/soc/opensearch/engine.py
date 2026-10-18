"""OpenSearch SOC orchestration engine."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .connectors import OpenSearchAPIConfig, OpenSearchConnectorManager
from .models import (
    OpenSearchAlert,
    OpenSearchAlertSeverity,
    OpenSearchEvent,
    OpenSearchEventStatus,
    OpenSearchIndex,
    OpenSearchSOCStatus,
)
from .rules import OpenSearchRuleEngine

logger = logging.getLogger(__name__)


class OpenSearchSOCEngine:
    """Main orchestration engine for OpenSearch OSS SOC integration."""

    def __init__(self, config: Optional[OpenSearchAPIConfig] = None) -> None:
        self.config = config or OpenSearchAPIConfig()
        self.connectors = OpenSearchConnectorManager(self.config)
        self.rules = OpenSearchRuleEngine()
        self._indices: dict[str, OpenSearchIndex] = {}
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the SOC engine with default configuration."""
        if self._initialized:
            return

        logger.info("Initializing OpenSearch SOC engine...")

        # Create default indices
        self._create_default_indices()

        # Create default connectors
        self._create_default_connectors()

        # Create default rules
        self._create_default_rules()

        self._initialized = True
        logger.info("OpenSearch SOC engine initialized successfully")

    def _create_default_indices(self) -> None:
        """Create default security indices."""
        self._indices["security-syslog"] = OpenSearchIndex(
            index_name="security-syslog",
            description="Security syslog events",
            index_pattern="security-syslog-*",
            shards=3,
            replicas=1,
            retention_days=30,
            tags={"category": "security", "soc": "true"},
        )
        self._indices["security-beats"] = OpenSearchIndex(
            index_name="security-beats",
            description="Beats security events",
            index_pattern="security-beats-*",
            shards=3,
            replicas=1,
            retention_days=30,
            tags={"category": "security", "soc": "true"},
        )
        self._indices["security-firewall"] = OpenSearchIndex(
            index_name="security-firewall",
            description="Firewall and network security events",
            index_pattern="security-firewall-*",
            shards=3,
            replicas=1,
            retention_days=30,
            tags={"category": "network", "soc": "true"},
        )
        self._indices["security-auth"] = OpenSearchIndex(
            index_name="security-auth",
            description="Authentication and authorization events",
            index_pattern="security-auth-*",
            shards=3,
            replicas=1,
            retention_days=30,
            tags={"category": "auth", "soc": "true"},
        )
        self._indices["security-web"] = OpenSearchIndex(
            index_name="security-web",
            description="Web server security events",
            index_pattern="security-web-*",
            shards=3,
            replicas=1,
            retention_days=30,
            tags={"category": "web", "soc": "true"},
        )
        self._indices["security-audit"] = OpenSearchIndex(
            index_name="security-audit",
            description="Audit and compliance events",
            index_pattern="security-audit-*",
            shards=3,
            replicas=1,
            retention_days=90,
            tags={"category": "audit", "soc": "true"},
        )

    def _create_default_connectors(self) -> None:
        """Create default data connectors."""
        self.connectors.create_syslog_udp_connector(port=514)
        self.connectors.create_syslog_tcp_connector(port=1514)
        self.connectors.create_beats_connector(port=5044)
        self.connectors.create_kafka_connector(port=9092)
        self.connectors.create_s3_connector()
        self.connectors.create_cloudtrail_connector()
        self.connectors.create_cef_connector(port=514)
        self.connectors.create_netflow_connector(port=2055)

    def _create_default_rules(self) -> None:
        """Create default detection rules."""
        self.rules.create_brute_force_rule()
        self.rules.create_port_scan_rule()
        self.rules.create_malware_detection_rule()
        self.rules.create_data_exfiltration_rule()
        self.rules.create_privilege_escalation_rule()
        self.rules.create_lateral_movement_rule()
        self.rules.create_web_attack_rule()
        self.rules.create_anomaly_detection_rule()
        self.rules.create_ddos_detection_rule()
        self.rules.create_account_lockout_rule()

    def get_status(self) -> OpenSearchSOCStatus:
        """Get overall SOC status."""
        return OpenSearchSOCStatus(
            cluster_name="opensearch-soc",
            cluster_health="green",
            version="2.11.0",
            is_processing=True,
            last_seen=datetime.now(timezone.utc).isoformat(),
            indices_count=len(self._indices),
            connectors_count=len(self.connectors.list_connectors()),
            rules_count=len(self.rules.list_rules()),
            alerts_count=len(self.rules.list_alerts()),
            docs_count=0,
            store_size=0,
        )

    def get_open_alerts(
        self, min_severity: OpenSearchAlertSeverity = OpenSearchAlertSeverity.LOW
    ) -> list[OpenSearchAlert]:
        """Get open alerts with severity >= min_severity."""
        return self.rules.get_open_alerts(min_severity)

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert."""
        return self.rules.acknowledge_alert(alert_id, acknowledged_by)

    def resolve_alert(self, alert_id: str, notes: str = "") -> bool:
        """Resolve an alert."""
        return self.rules.resolve_alert(alert_id, notes)

    def get_alert_stats(self) -> dict[str, Any]:
        """Get alert statistics."""
        return self.rules.get_alert_stats()

    def create_incident_from_alert(self, alert_id: str) -> dict[str, Any]:
        """Create an incident from an alert."""
        alert = self.rules.get_alert(alert_id)
        if not alert:
            return {}

        return {
            "incident_id": f"INC-{alert_id}",
            "title": alert.rule_name,
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
            "indices": [
                {
                    "index_name": idx.index_name,
                    "description": idx.description,
                    "index_pattern": idx.index_pattern,
                    "shards": idx.shards,
                    "replicas": idx.replicas,
                    "retention_days": idx.retention_days,
                    "tags": idx.tags,
                }
                for idx in self._indices.values()
            ],
            "connectors": [
                self.connectors.to_api_payload(c) for c in self.connectors.list_connectors()
            ],
            "rules": [
                self.rules.to_api_payload(r) for r in self.rules.list_rules()
            ],
            "alerts": [
                {
                    "alert_id": a.alert_id,
                    "timestamp": a.timestamp,
                    "rule_id": a.rule_id,
                    "rule_name": a.rule_name,
                    "severity": a.severity.value,
                    "status": a.status.value,
                    "source": a.source,
                    "message": a.message,
                    "mitre_tactics": a.mitre_tactics,
                    "mitre_techniques": a.mitre_techniques,
                    "compliance_refs": a.compliance_refs,
                }
                for a in self.rules.list_alerts()
            ],
        }

    def health_check(self) -> dict[str, Any]:
        """Perform health check."""
        status = self.get_status()
        return {
            "healthy": status.is_processing and status.cluster_health == "green",
            "cluster_name": status.cluster_name,
            "cluster_health": status.cluster_health,
            "version": status.version,
            "indices_count": status.indices_count,
            "connectors_count": status.connectors_count,
            "rules_count": status.rules_count,
            "alerts_count": status.alerts_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
