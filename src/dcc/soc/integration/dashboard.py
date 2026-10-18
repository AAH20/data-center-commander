"""Unified dashboard aggregator.

Aggregates data from all integration components (events, alerts,
scaling decisions, container sync, correlation results, remediation
actions) into a single unified dashboard snapshot for SOC operators.
"""
from __future__ import annotations

import datetime as dt
import time
from typing import Any
from uuid import uuid4

from .models import (
    DashboardSnapshot,
    EventSeverity,
    IntegrationAlert,
    IntegrationEvent,
    CorrelationResult,
    ScalingDecision,
    ContainerSyncResult,
    RemediationAction,
)


class UnifiedDashboard:
    """Unified dashboard for SOC + Auto Scaling + Container integration.

    Collects and aggregates data from all integration components,
    providing a single view for operators.

    Usage:
        dashboard = UnifiedDashboard()
        dashboard.add_event(event)
        dashboard.add_alert(alert)
        snapshot = dashboard.generate_snapshot()
    """

    def __init__(self, max_items: int = 100) -> None:
        self.max_items = max_items
        self._events: list[IntegrationEvent] = []
        self._alerts: list[IntegrationAlert] = []
        self._scaling_decisions: list[ScalingDecision] = []
        self._container_sync_results: list[ContainerSyncResult] = []
        self._correlation_results: list[CorrelationResult] = []
        self._remediation_actions: list[RemediationAction] = []

    def add_event(self, event: IntegrationEvent) -> None:
        """Add an integration event."""
        self._events.append(event)
        if len(self._events) > self.max_items:
            self._events = self._events[-self.max_items:]

    def add_alert(self, alert: IntegrationAlert) -> None:
        """Add an integration alert."""
        self._alerts.append(alert)
        if len(self._alerts) > self.max_items:
            self._alerts = self._alerts[-self.max_items:]

    def add_scaling_decision(self, decision: ScalingDecision) -> None:
        """Add a scaling decision."""
        self._scaling_decisions.append(decision)
        if len(self._scaling_decisions) > self.max_items:
            self._scaling_decisions = self._scaling_decisions[-self.max_items:]

    def add_container_sync_result(self, result: ContainerSyncResult) -> None:
        """Add a container sync result."""
        self._container_sync_results.append(result)
        if len(self._container_sync_results) > self.max_items:
            self._container_sync_results = self._container_sync_results[-self.max_items:]

    def add_correlation_result(self, result: CorrelationResult) -> None:
        """Add a correlation result."""
        self._correlation_results.append(result)
        if len(self._correlation_results) > self.max_items:
            self._correlation_results = self._correlation_results[-self.max_items:]

    def add_remediation_action(self, action: RemediationAction) -> None:
        """Add a remediation action."""
        self._remediation_actions.append(action)
        if len(self._remediation_actions) > self.max_items:
            self._remediation_actions = self._remediation_actions[-self.max_items:]

    def generate_snapshot(self) -> DashboardSnapshot:
        """Generate a unified dashboard snapshot.

        Returns:
            DashboardSnapshot with all current data and summary.
        """
        now = dt.datetime.now(dt.timezone.utc).isoformat()

        # Calculate summary statistics
        summary = self._calculate_summary()

        return DashboardSnapshot(
            snapshot_id=f"snap-{uuid4().hex[:12]}",
            generated_at=now,
            events=list(self._events),
            alerts=list(self._alerts),
            scaling_decisions=list(self._scaling_decisions),
            container_sync_results=list(self._container_sync_results),
            correlation_results=list(self._correlation_results),
            remediation_actions=list(self._remediation_actions),
            summary=summary,
        )

    def _calculate_summary(self) -> dict[str, Any]:
        """Calculate summary statistics for the dashboard."""
        # Event counts by severity
        event_counts: dict[str, int] = {"info": 0, "warning": 0, "critical": 0, "emergency": 0}
        for event in self._events:
            event_counts[event.severity.value] = event_counts.get(event.severity.value, 0) + 1

        # Alert counts by severity
        alert_counts: dict[str, int] = {"info": 0, "warning": 0, "critical": 0, "emergency": 0}
        for alert in self._alerts:
            alert_counts[alert.severity.value] = alert_counts.get(alert.severity.value, 0) + 1

        # Scaling decision counts
        scaling_counts: dict[str, int] = {"scale_up": 0, "scale_down": 0, "maintain": 0, "emergency_scale": 0}
        for decision in self._scaling_decisions:
            scaling_counts[decision.action.value] = scaling_counts.get(decision.action.value, 0) + 1

        # Container sync status counts
        sync_counts: dict[str, int] = {"success": 0, "partial": 0, "failed": 0, "skipped": 0}
        for result in self._container_sync_results:
            sync_counts[result.status.value] = sync_counts.get(result.status.value, 0) + 1

        # Remediation status counts
        remediation_counts: dict[str, int] = {
            "pending": 0, "in_progress": 0, "completed": 0, "failed": 0, "rolled_back": 0,
        }
        for action in self._remediation_actions:
            remediation_counts[action.status.value] = remediation_counts.get(action.status.value, 0) + 1

        # Active alerts (not resolved)
        active_alerts = sum(
            1 for a in self._alerts
            if a.severity in (EventSeverity.CRITICAL, EventSeverity.EMERGENCY)
        )

        # Auto-remediation triggered count
        auto_remediation_count = sum(
            1 for a in self._alerts if a.auto_remediation_triggered
        )

        return {
            "total_events": len(self._events),
            "total_alerts": len(self._alerts),
            "active_critical_alerts": active_alerts,
            "auto_remediation_triggered": auto_remediation_count,
            "event_counts": event_counts,
            "alert_counts": alert_counts,
            "scaling_counts": scaling_counts,
            "sync_counts": sync_counts,
            "remediation_counts": remediation_counts,
            "correlation_count": len(self._correlation_results),
        }

    def get_recent_events(
        self, severity: EventSeverity | None = None, limit: int = 50
    ) -> list[IntegrationEvent]:
        """Get recent events, optionally filtered by severity."""
        events = self._events
        if severity is not None:
            events = [e for e in events if e.severity == severity]
        return events[-limit:]

    def get_active_alerts(
        self, severity: EventSeverity | None = None
    ) -> list[IntegrationAlert]:
        """Get active alerts, optionally filtered by severity."""
        alerts = self._alerts
        if severity is not None:
            alerts = [a for a in alerts if a.severity == severity]
        return alerts

    def reset(self) -> None:
        """Clear all dashboard data."""
        self._events.clear()
        self._alerts.clear()
        self._scaling_decisions.clear()
        self._container_sync_results.clear()
        self._correlation_results.clear()
        self._remediation_actions.clear()


__all__ = ["UnifiedDashboard"]
