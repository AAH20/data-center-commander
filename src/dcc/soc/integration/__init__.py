"""SOC + Auto Scaling + Container unified integration.

Provides a unified dashboard, alert correlation, auto-remediation,
and container platform synchronization for Data Center Commander.

Modules:
    models: Shared data models for the integration layer.
    correlation: Alert correlation and root-cause analysis.
    auto_scaling: Auto-scaling decision engine with safety bounds.
    container_sync: Container platform sync orchestrator.
    dashboard: Unified dashboard aggregator.
    remediation: Auto-remediation workflow management.
"""
from __future__ import annotations

from .models import (
    EventSource,
    EventSeverity,
    ScalingAction,
    SyncStatus,
    RemediationStatus,
    IntegrationEvent,
    IntegrationAlert,
    CorrelationResult,
    ScalingDecision,
    ContainerSyncResult,
    DashboardSnapshot,
    RemediationAction,
)
from .correlation import AlertCorrelator
from .auto_scaling import AutoScalingEngine, ScalingPolicy, ScalingMetrics
from .container_sync import ContainerSyncOrchestrator
from .dashboard import UnifiedDashboard
from .remediation import AutoRemediationEngine

__all__ = [
    # Enums
    "EventSource",
    "EventSeverity",
    "ScalingAction",
    "SyncStatus",
    "RemediationStatus",
    # Models
    "IntegrationEvent",
    "IntegrationAlert",
    "CorrelationResult",
    "ScalingDecision",
    "ContainerSyncResult",
    "DashboardSnapshot",
    "RemediationAction",
    # Engines
    "AlertCorrelator",
    "AutoScalingEngine",
    "ScalingPolicy",
    "ScalingMetrics",
    "ContainerSyncOrchestrator",
    "UnifiedDashboard",
    "AutoRemediationEngine",
]
