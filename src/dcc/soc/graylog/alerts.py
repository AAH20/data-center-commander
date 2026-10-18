"""Graylog alert management for SOC integration."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .models import (
    GraylogAlert,
    GraylogAlertSeverity,
    GraylogEventStatus,
)

logger = logging.getLogger(__name__)


class GraylogAlertManager:
    """Manages Graylog alerts and events."""

    def __init__(self) -> None:
        self._alerts: dict[str, GraylogAlert] = {}

    def create_alert(
        self,
        event_definition_id: str,
        event_definition_title: str,
        severity: GraylogAlertSeverity = GraylogAlertSeverity.MEDIUM,
        source: str = "",
        message: str = "",
        stream_ids: Optional[list[str]] = None,
        fields: Optional[dict[str, str]] = None,
        mitre_tactics: Optional[list[str]] = None,
        mitre_techniques: Optional[list[str]] = None,
        compliance_refs: Optional[list[str]] = None,
    ) -> GraylogAlert:
        """Create a new Graylog alert."""
        alert_id = f"alert-{uuid.uuid4().hex[:12]}"
        alert = GraylogAlert(
            alert_id=alert_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_definition_id=event_definition_id,
            event_definition_title=event_definition_title,
            severity=severity,
            status=GraylogEventStatus.OPEN,
            source=source,
            message=message,
            stream_ids=stream_ids or [],
            fields=fields or {},
            mitre_tactics=mitre_tactics or [],
            mitre_techniques=mitre_techniques or [],
            compliance_refs=compliance_refs or [],
        )
        self._alerts[alert_id] = alert
        logger.info("Created Graylog alert: %s (severity: %s)", event_definition_title, severity.name)
        return alert

    def get_alert(self, alert_id: str) -> Optional[GraylogAlert]:
        """Get an alert by ID."""
        return self._alerts.get(alert_id)

    def list_alerts(
        self,
        severity: Optional[GraylogAlertSeverity] = None,
        status: Optional[GraylogEventStatus] = None,
        stream_id: str = "",
        source: str = "",
        limit: int = 100,
    ) -> list[GraylogAlert]:
        """List alerts with optional filters."""
        alerts = list(self._alerts.values())
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if status:
            alerts = [a for a in alerts if a.status == status]
        if stream_id:
            alerts = [a for a in alerts if stream_id in a.stream_ids]
        if source:
            alerts = [a for a in alerts if a.source == source]
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)[:limit]

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.status = GraylogEventStatus.ACKNOWLEDGED
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = datetime.now(timezone.utc).isoformat()
            logger.info("Alert %s acknowledged by %s", alert_id, acknowledged_by)
            return True
        return False

    def resolve_alert(self, alert_id: str, notes: str = "") -> bool:
        """Resolve an alert."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.status = GraylogEventStatus.RESOLVED
            alert.resolved_at = datetime.now(timezone.utc).isoformat()
            if notes:
                alert.notes = notes
            logger.info("Alert %s resolved", alert_id)
            return True
        return False

    def mark_false_positive(self, alert_id: str, notes: str = "") -> bool:
        """Mark an alert as false positive."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.status = GraylogEventStatus.FALSE_POSITIVE
            alert.resolved_at = datetime.now(timezone.utc).isoformat()
            if notes:
                alert.notes = notes
            logger.info("Alert %s marked as false positive", alert_id)
            return True
        return False

    def get_open_alerts(self, min_severity: GraylogAlertSeverity = GraylogAlertSeverity.LOW) -> list[GraylogAlert]:
        """Get all open alerts with severity >= min_severity."""
        return [
            a
            for a in self._alerts.values()
            if a.status == GraylogEventStatus.OPEN and a.severity >= min_severity
        ]

    def get_alert_stats(self) -> dict[str, Any]:
        """Get alert statistics."""
        stats: dict[str, Any] = {
            "total": len(self._alerts),
            "open": 0,
            "acknowledged": 0,
            "resolved": 0,
            "false_positive": 0,
            "by_severity": {s.name: 0 for s in GraylogAlertSeverity},
        }
        for alert in self._alerts.values():
            if alert.status == GraylogEventStatus.OPEN:
                stats["open"] += 1
            elif alert.status == GraylogEventStatus.ACKNOWLEDGED:
                stats["acknowledged"] += 1
            elif alert.status == GraylogEventStatus.RESOLVED:
                stats["resolved"] += 1
            elif alert.status == GraylogEventStatus.FALSE_POSITIVE:
                stats["false_positive"] += 1
            stats["by_severity"][alert.severity.name] += 1
        return stats

    def to_api_payload(self, alert: GraylogAlert) -> dict[str, Any]:
        """Convert alert to Graylog API payload."""
        return {
            "id": alert.alert_id,
            "timestamp": alert.timestamp,
            "event_definition_id": alert.event_definition_id,
            "event_definition_title": alert.event_definition_title,
            "severity": alert.severity.value,
            "status": alert.status.value,
            "stream_ids": alert.stream_ids,
            "source": alert.source,
            "message": alert.message,
            "key": alert.key,
            "key_tuple": alert.key_tuple,
            "priority": alert.priority,
            "fields": alert.fields,
            "group_by_fields": alert.group_by_fields,
            "mitre_tactics": alert.mitre_tactics,
            "mitre_techniques": alert.mitre_techniques,
            "compliance_refs": alert.compliance_refs,
        }
