"""Graylog event definitions and alert rules for SOC integration."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .models import (
    GraylogAlertSeverity,
    GraylogEventDefinition,
    GraylogRuleType,
)

logger = logging.getLogger(__name__)


class GraylogEventManager:
    """Manages Graylog event definitions and alert rules."""

    def __init__(self) -> None:
        self._events: dict[str, GraylogEventDefinition] = {}

    def create_event_definition(
        self,
        title: str,
        description: str = "",
        rule_type: GraylogRuleType = GraylogRuleType.MATCH,
        severity: GraylogAlertSeverity = GraylogAlertSeverity.MEDIUM,
        condition: str = "",
        alert: bool = False,
        streams: Optional[list[str]] = None,
        mitre_tactics: Optional[list[str]] = None,
        mitre_techniques: Optional[list[str]] = None,
        compliance_refs: Optional[list[str]] = None,
        notification_emails: Optional[list[str]] = None,
        notification_webhooks: Optional[list[str]] = None,
    ) -> GraylogEventDefinition:
        """Create a new event definition."""
        event_id = f"event-{title.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
        event = GraylogEventDefinition(
            event_id=event_id,
            title=title,
            description=description,
            rule_type=rule_type,
            severity=severity,
            condition=condition,
            alert=alert,
            streams=streams or [],
            mitre_tactics=mitre_tactics or [],
            mitre_techniques=mitre_techniques or [],
            compliance_refs=compliance_refs or [],
            notification_emails=notification_emails or [],
            notification_webhooks=notification_webhooks or [],
        )
        self._events[event_id] = event
        logger.info("Created Graylog event definition: %s", title)
        return event

    def create_brute_force_rule(
        self,
        title: str = "Brute Force Attack Detection",
        threshold: int = 10,
        time_window: int = 300,
        streams: Optional[list[str]] = None,
    ) -> GraylogEventDefinition:
        """Create a brute force attack detection rule."""
        return self.create_event_definition(
            title=title,
            description=f"Detects brute force attacks ({threshold} failed logins in {time_window}s)",
            rule_type=GraylogRuleType.AGGREGATION,
            severity=GraylogAlertSeverity.HIGH,
            condition=f"count:>{threshold}",
            alert=True,
            streams=streams,
            mitre_tactics=["Credential Access"],
            mitre_techniques=["T1110"],
            compliance_refs=["NIST-800-53-IA-2", "PCI-DSS-8.1.6"],
        )

    def create_port_scan_rule(
        self,
        title: str = "Port Scan Detection",
        threshold: int = 20,
        time_window: int = 60,
        streams: Optional[list[str]] = None,
    ) -> GraylogEventDefinition:
        """Create a port scan detection rule."""
        return self.create_event_definition(
            title=title,
            description=f"Detects port scans ({threshold} ports in {time_window}s)",
            rule_type=GraylogRuleType.AGGREGATION,
            severity=GraylogAlertSeverity.MEDIUM,
            condition=f"count:>{threshold}",
            alert=True,
            streams=streams,
            mitre_tactics=["Discovery"],
            mitre_techniques=["T1046"],
            compliance_refs=["NIST-800-53-SI-4"],
        )

    def create_malware_detection_rule(
        self,
        title: str = "Malware Detection",
        streams: Optional[list[str]] = None,
    ) -> GraylogEventDefinition:
        """Create a malware detection rule."""
        return self.create_event_definition(
            title=title,
            description="Detects malware-related events",
            rule_type=GraylogRuleType.MATCH,
            severity=GraylogAlertSeverity.CRITICAL,
            condition="event_type:malware OR event_type:virus OR event_type:trojan",
            alert=True,
            streams=streams,
            mitre_tactics=["Execution"],
            mitre_techniques=["T1204"],
            compliance_refs=["NIST-800-53-SI-3", "PCI-DSS-5.1"],
        )

    def create_data_exfiltration_rule(
        self,
        title: str = "Data Exfiltration Detection",
        threshold: int = 1000000,
        time_window: int = 3600,
        streams: Optional[list[str]] = None,
    ) -> GraylogEventDefinition:
        """Create a data exfiltration detection rule."""
        return self.create_event_definition(
            title=title,
            description=f"Detects potential data exfiltration ({threshold} bytes in {time_window}s)",
            rule_type=GraylogRuleType.AGGREGATION,
            severity=GraylogAlertSeverity.HIGH,
            condition=f"sum:bytes:>{threshold}",
            alert=True,
            streams=streams,
            mitre_tactics=["Exfiltration"],
            mitre_techniques=["T1041"],
            compliance_refs=["NIST-800-53-SC-8", "PCI-DSS-3.4"],
        )

    def create_privilege_escalation_rule(
        self,
        title: str = "Privilege Escalation Detection",
        streams: Optional[list[str]] = None,
    ) -> GraylogEventDefinition:
        """Create a privilege escalation detection rule."""
        return self.create_event_definition(
            title=title,
            description="Detects privilege escalation attempts",
            rule_type=GraylogRuleType.MATCH,
            severity=GraylogAlertSeverity.HIGH,
            condition="event_type:privilege_escalation OR event_type:sudo_abuse",
            alert=True,
            streams=streams,
            mitre_tactics=["Privilege Escalation"],
            mitre_techniques=["T1068"],
            compliance_refs=["NIST-800-53-AC-6"],
        )

    def create_lateral_movement_rule(
        self,
        title: str = "Lateral Movement Detection",
        streams: Optional[list[str]] = None,
    ) -> GraylogEventDefinition:
        """Create a lateral movement detection rule."""
        return self.create_event_definition(
            title=title,
            description="Detects lateral movement attempts",
            rule_type=GraylogRuleType.MATCH,
            severity=GraylogAlertSeverity.HIGH,
            condition="event_type:lateral_movement OR event_type:psexec OR event_type:wmi",
            alert=True,
            streams=streams,
            mitre_tactics=["Lateral Movement"],
            mitre_techniques=["T1021"],
            compliance_refs=["NIST-800-53-SI-4"],
        )

    def create_web_attack_rule(
        self,
        title: str = "Web Attack Detection",
        streams: Optional[list[str]] = None,
    ) -> GraylogEventDefinition:
        """Create a web attack detection rule."""
        return self.create_event_definition(
            title=title,
            description="Detects web-based attacks (SQLi, XSS, etc.)",
            rule_type=GraylogRuleType.MATCH,
            severity=GraylogAlertSeverity.HIGH,
            condition="event_type:sqli OR event_type:xss OR event_type:rfi OR event_type:lfi",
            alert=True,
            streams=streams,
            mitre_tactics=["Initial Access"],
            mitre_techniques=["T1190"],
            compliance_refs=["NIST-800-53-SI-10", "PCI-DSS-6.5.1"],
        )

    def create_anomaly_detection_rule(
        self,
        title: str = "Anomaly Detection",
        streams: Optional[list[str]] = None,
    ) -> GraylogEventDefinition:
        """Create an anomaly detection rule."""
        return self.create_event_definition(
            title=title,
            description="Detects anomalous behavior patterns",
            rule_type=GraylogRuleType.TRENDS,
            severity=GraylogAlertSeverity.MEDIUM,
            condition="trend:deviation:>2",
            alert=True,
            streams=streams,
            mitre_tactics=["Defense Evasion"],
            mitre_techniques=["T1078"],
        )

    def get_event(self, event_id: str) -> Optional[GraylogEventDefinition]:
        """Get an event definition by ID."""
        return self._events.get(event_id)

    def list_events(
        self,
        rule_type: Optional[GraylogRuleType] = None,
        severity: Optional[GraylogAlertSeverity] = None,
        alert_only: bool = False,
    ) -> list[GraylogEventDefinition]:
        """List event definitions with optional filters."""
        events = list(self._events.values())
        if rule_type:
            events = [e for e in events if e.rule_type == rule_type]
        if severity:
            events = [e for e in events if e.severity == severity]
        if alert_only:
            events = [e for e in events if e.alert]
        return events

    def enable_event(self, event_id: str) -> bool:
        """Enable an event definition."""
        event = self._events.get(event_id)
        if event:
            event.status = "enabled"
            event.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def disable_event(self, event_id: str) -> bool:
        """Disable an event definition."""
        event = self._events.get(event_id)
        if event:
            event.status = "disabled"
            event.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def to_api_payload(self, event: GraylogEventDefinition) -> dict[str, Any]:
        """Convert event definition to Graylog API payload."""
        return {
            "title": event.title,
            "description": event.description,
            "priority": event.priority,
            "alert": event.alert,
            "config": {
                "type": event.rule_type.value,
                "condition": event.condition,
                "group_by": event.group_by,
                "series": event.series,
                "key_spec": event.key_spec,
                "field_spec": event.field_spec,
                "streams": event.streams,
            },
            "notification_emails": event.notification_emails,
            "notification_webhooks": event.notification_webhooks,
            "tags": event.tags,
        }
