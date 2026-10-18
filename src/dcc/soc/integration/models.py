"""Shared data models for the SOC + Auto Scaling + Container integration.

Defines the core data structures used across the integration layer:
events, alerts, correlation results, scaling decisions, container sync
results, dashboard snapshots, and remediation actions.
"""
from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventSource(str, Enum):
    """Source system for an integration event."""
    SOC = "soc"
    AUTO_SCALING = "auto_scaling"
    CONTAINER = "container"
    OBSERVABILITY = "observability"
    SECURITY_POSTURE = "security_posture"
    FORECASTING = "forecasting"


class EventSeverity(str, Enum):
    """Severity levels for integration events."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class ScalingAction(str, Enum):
    """Auto-scaling action types."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    MAINTAIN = "maintain"
    EMERGENCY_SCALE = "emergency_scale"


class SyncStatus(str, Enum):
    """Container sync status."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class RemediationStatus(str, Enum):
    """Auto-remediation action status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class IntegrationEvent:
    """A unified integration event.

    Attributes:
        event_id: Unique event identifier.
        source: Source system.
        severity: Event severity.
        title: Short event title.
        description: Detailed description.
        timestamp: Unix timestamp.
        metadata: Additional context.
        correlation_id: ID for correlating related events.
    """
    event_id: str
    source: EventSource
    severity: EventSeverity
    title: str
    description: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source": self.source.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "correlation_id": self.correlation_id,
        }


@dataclass
class IntegrationAlert:
    """A unified integration alert.

    Attributes:
        alert_id: Unique alert identifier.
        source: Source system.
        severity: Alert severity.
        title: Short alert title.
        description: Detailed description.
        timestamp: Unix timestamp.
        correlated_alert_ids: IDs of correlated alerts.
        root_cause: Identified root cause (if any).
        auto_remediation_triggered: Whether auto-remediation was triggered.
        metadata: Additional context.
    """
    alert_id: str
    source: EventSource
    severity: EventSeverity
    title: str
    description: str = ""
    timestamp: float = field(default_factory=time.time)
    correlated_alert_ids: list[str] = field(default_factory=list)
    root_cause: str | None = None
    auto_remediation_triggered: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "source": self.source.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "timestamp": self.timestamp,
            "correlated_alert_ids": self.correlated_alert_ids,
            "root_cause": self.root_cause,
            "auto_remediation_triggered": self.auto_remediation_triggered,
            "metadata": self.metadata,
        }


@dataclass
class CorrelationResult:
    """Result of alert correlation analysis.

    Attributes:
        correlation_id: Unique correlation ID.
        primary_alert_id: The primary (root cause) alert.
        correlated_alert_ids: IDs of correlated alerts.
        confidence: Correlation confidence (0.0-1.0).
        root_cause: Identified root cause description.
        recommended_action: Recommended remediation action.
        metadata: Additional context.
    """
    correlation_id: str
    primary_alert_id: str
    correlated_alert_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0
    root_cause: str = ""
    recommended_action: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "primary_alert_id": self.primary_alert_id,
            "correlated_alert_ids": self.correlated_alert_ids,
            "confidence": round(self.confidence, 4),
            "root_cause": self.root_cause,
            "recommended_action": self.recommended_action,
            "metadata": self.metadata,
        }


@dataclass
class ScalingDecision:
    """An auto-scaling decision.

    Attributes:
        decision_id: Unique decision identifier.
        action: Scaling action to take.
        current_replicas: Current replica count.
        target_replicas: Target replica count.
        reason: Reason for the decision.
        confidence: Decision confidence (0.0-1.0).
        safety_bounds_applied: Whether safety bounds were applied.
        timestamp: Unix timestamp.
        metadata: Additional context.
    """
    decision_id: str
    action: ScalingAction
    current_replicas: int
    target_replicas: int
    reason: str = ""
    confidence: float = 0.0
    safety_bounds_applied: bool = False
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "action": self.action.value,
            "current_replicas": self.current_replicas,
            "target_replicas": self.target_replicas,
            "reason": self.reason,
            "confidence": round(self.confidence, 4),
            "safety_bounds_applied": self.safety_bounds_applied,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ContainerSyncResult:
    """Result of a container platform sync operation.

    Attributes:
        sync_id: Unique sync identifier.
        platform: Container platform (docker, kubernetes, etc.).
        status: Sync status.
        containers_synced: Number of containers synced.
        pods_synced: Number of pods synced.
        nodes_synced: Number of nodes synced.
        errors: List of error messages.
        started_at: ISO timestamp when sync started.
        completed_at: ISO timestamp when sync completed.
        metadata: Additional context.
    """
    sync_id: str
    platform: str
    status: SyncStatus
    containers_synced: int = 0
    pods_synced: int = 0
    nodes_synced: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sync_id": self.sync_id,
            "platform": self.platform,
            "status": self.status.value,
            "containers_synced": self.containers_synced,
            "pods_synced": self.pods_synced,
            "nodes_synced": self.nodes_synced,
            "errors": self.errors,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }


@dataclass
class DashboardSnapshot:
    """Unified dashboard snapshot.

    Attributes:
        snapshot_id: Unique snapshot identifier.
        generated_at: ISO timestamp when snapshot was generated.
        events: Recent integration events.
        alerts: Active integration alerts.
        scaling_decisions: Recent scaling decisions.
        container_sync_results: Recent container sync results.
        correlation_results: Recent correlation results.
        remediation_actions: Recent remediation actions.
        summary: Summary statistics.
    """
    snapshot_id: str
    generated_at: str = ""
    events: list[IntegrationEvent] = field(default_factory=list)
    alerts: list[IntegrationAlert] = field(default_factory=list)
    scaling_decisions: list[ScalingDecision] = field(default_factory=list)
    container_sync_results: list[ContainerSyncResult] = field(default_factory=list)
    correlation_results: list[CorrelationResult] = field(default_factory=list)
    remediation_actions: list[RemediationAction] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "generated_at": self.generated_at,
            "events": [e.to_dict() for e in self.events],
            "alerts": [a.to_dict() for a in self.alerts],
            "scaling_decisions": [d.to_dict() for d in self.scaling_decisions],
            "container_sync_results": [r.to_dict() for r in self.container_sync_results],
            "correlation_results": [r.to_dict() for r in self.correlation_results],
            "remediation_actions": [a.to_dict() for a in self.remediation_actions],
            "summary": self.summary,
        }


@dataclass
class RemediationAction:
    """An auto-remediation action.

    Attributes:
        action_id: Unique action identifier.
        alert_id: ID of the alert that triggered this action.
        action_type: Type of remediation action.
        status: Current status.
        description: Description of the action.
        started_at: ISO timestamp when action started.
        completed_at: ISO timestamp when action completed.
        result: Result of the action.
        rolled_back: Whether the action was rolled back.
        metadata: Additional context.
    """
    action_id: str
    alert_id: str
    action_type: str
    status: RemediationStatus = RemediationStatus.PENDING
    description: str = ""
    started_at: str = ""
    completed_at: str = ""
    result: str = ""
    rolled_back: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "alert_id": self.alert_id,
            "action_type": self.action_type,
            "status": self.status.value,
            "description": self.description,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "rolled_back": self.rolled_back,
            "metadata": self.metadata,
        }


__all__ = [
    "EventSource",
    "EventSeverity",
    "ScalingAction",
    "SyncStatus",
    "RemediationStatus",
    "IntegrationEvent",
    "IntegrationAlert",
    "CorrelationResult",
    "ScalingDecision",
    "ContainerSyncResult",
    "DashboardSnapshot",
    "RemediationAction",
]
