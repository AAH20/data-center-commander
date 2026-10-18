"""Auto-remediation workflow management.

Manages automated remediation actions triggered by correlated alerts.
Provides a workflow engine that can execute, track, and roll back
remediation actions with safety checks and approval gates.
"""
from __future__ import annotations

import datetime as dt
import time
from typing import Any, Callable
from uuid import uuid4

from .models import (
    EventSeverity,
    IntegrationAlert,
    RemediationAction,
    RemediationStatus,
)


# Remediation action types
REMEDIATION_SCALE_UP = "scale_up"
REMEDIATION_SCALE_DOWN = "scale_down"
REMEDIATION_RESTART_CONTAINER = "restart_container"
REMEDIATION_ISOLATE_NODE = "isolate_node"
REMEDIATION_ESCALATE_SOC = "escalate_soc"
REMEDIATION_ACKNOWLEDGE_ALERT = "acknowledge_alert"
REMEDIATION_RUN_DIAGNOSTIC = "run_diagnostic"

# All supported action types
ALL_ACTION_TYPES = frozenset({
    REMEDIATION_SCALE_UP,
    REMEDIATION_SCALE_DOWN,
    REMEDIATION_RESTART_CONTAINER,
    REMEDIATION_ISOLATE_NODE,
    REMEDIATION_ESCALATE_SOC,
    REMEDIATION_ACKNOWLEDGE_ALERT,
    REMEDIATION_RUN_DIAGNOSTIC,
})

# Actions that require explicit approval before execution
APPROVAL_REQUIRED_ACTIONS = frozenset({
    REMEDIATION_ISOLATE_NODE,
    REMEDIATION_ESCALATE_SOC,
})


class AutoRemediationEngine:
    """Auto-remediation workflow engine.

    Evaluates alerts and triggers appropriate remediation actions
    based on alert source, severity, and correlation results.
    All actions are tracked and can be rolled back if needed.

    Usage:
        engine = AutoRemediationEngine()
        engine.register_handler(REMEDIATION_SCALE_UP, my_scale_up_func)
        action = engine.evaluate_and_trigger(alert)
    """

    def __init__(self, auto_approve: bool = False) -> None:
        self.auto_approve = auto_approve
        self._handlers: dict[str, Callable[[RemediationAction], bool]] = {}
        self._actions: dict[str, RemediationAction] = {}
        self._action_history: list[RemediationAction] = []

    def register_handler(
        self,
        action_type: str,
        handler: Callable[[RemediationAction], bool],
    ) -> None:
        """Register a handler for a remediation action type.

        Args:
            action_type: The action type to handle.
            handler: Callable that executes the action and returns
                    True on success, False on failure.
        """
        if action_type not in ALL_ACTION_TYPES:
            raise ValueError(f"Unknown action type: {action_type}")
        self._handlers[action_type] = handler

    def evaluate_and_trigger(self, alert: IntegrationAlert) -> RemediationAction | None:
        """Evaluate an alert and trigger appropriate remediation.

        Args:
            alert: The integration alert to evaluate.

        Returns:
            RemediationAction if one was triggered, None otherwise.
        """
        action_type = self._determine_action(alert)
        if action_type is None:
            return None

        # Check if approval is required
        if action_type in APPROVAL_REQUIRED_ACTIONS and not self.auto_approve:
            # Create a pending action that requires approval
            action = RemediationAction(
                action_id=f"rem-{uuid4().hex[:12]}",
                alert_id=alert.alert_id,
                action_type=action_type,
                status=RemediationStatus.PENDING,
                description=f"Pending approval: {action_type} for alert {alert.alert_id}",
                started_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                metadata={"requires_approval": True},
            )
            self._actions[action.action_id] = action
            self._action_history.append(action)
            return action

        # Execute immediately
        return self._execute_action(action_type, alert)

    def _determine_action(self, alert: IntegrationAlert) -> str | None:
        """Determine the appropriate remediation action for an alert."""
        source = alert.source.value
        severity = alert.severity

        # Container-related alerts
        if source == "container":
            if severity in (EventSeverity.CRITICAL, EventSeverity.EMERGENCY):
                return REMEDIATION_RESTART_CONTAINER
            return REMEDIATION_RUN_DIAGNOSTIC

        # Auto-scaling alerts
        if source == "auto_scaling":
            if severity == EventSeverity.EMERGENCY:
                return REMEDIATION_SCALE_UP
            return REMEDIATION_ACKNOWLEDGE_ALERT

        # SOC alerts
        if source == "soc":
            if severity in (EventSeverity.CRITICAL, EventSeverity.EMERGENCY):
                return REMEDIATION_ESCALATE_SOC
            return REMEDIATION_ACKNOWLEDGE_ALERT

        # Observability alerts
        if source == "observability":
            if severity == EventSeverity.CRITICAL:
                return REMEDIATION_RUN_DIAGNOSTIC
            return REMEDIATION_ACKNOWLEDGE_ALERT

        # Security posture alerts
        if source == "security_posture":
            if severity in (EventSeverity.CRITICAL, EventSeverity.EMERGENCY):
                return REMEDIATION_ISOLATE_NODE
            return REMEDIATION_ESCALATE_SOC

        # Forecasting alerts
        if source == "forecasting":
            return REMEDIATION_ACKNOWLEDGE_ALERT

        return None

    def _execute_action(
        self, action_type: str, alert: IntegrationAlert
    ) -> RemediationAction:
        """Execute a remediation action."""
        action_id = f"rem-{uuid4().hex[:12]}"
        started_at = dt.datetime.now(dt.timezone.utc).isoformat()

        action = RemediationAction(
            action_id=action_id,
            alert_id=alert.alert_id,
            action_type=action_type,
            status=RemediationStatus.IN_PROGRESS,
            description=f"Executing {action_type} for alert {alert.alert_id}",
            started_at=started_at,
            metadata={"alert_source": alert.source.value, "alert_severity": alert.severity.value},
        )

        self._actions[action_id] = action
        self._action_history.append(action)

        # Mark alert as having auto-remediation triggered
        alert.auto_remediation_triggered = True

        # Execute handler if registered
        handler = self._handlers.get(action_type)
        if handler:
            try:
                success = handler(action)
                if success:
                    action.status = RemediationStatus.COMPLETED
                    action.result = "Success"
                else:
                    action.status = RemediationStatus.FAILED
                    action.result = "Handler returned False"
            except Exception as exc:
                action.status = RemediationStatus.FAILED
                action.result = f"Handler error: {exc}"
        else:
            # No handler registered — mark as completed (no-op)
            action.status = RemediationStatus.COMPLETED
            action.result = "No handler registered (no-op)"

        action.completed_at = dt.datetime.now(dt.timezone.utc).isoformat()
        return action

    def approve_action(self, action_id: str) -> RemediationAction | None:
        """Approve a pending remediation action.

        Args:
            action_id: ID of the action to approve.

        Returns:
            The approved action, or None if not found.
        """
        action = self._actions.get(action_id)
        if action is None:
            return None
        if action.status != RemediationStatus.PENDING:
            return None

        # Find the associated alert
        # In a real system, we'd look up the alert from a store
        # For now, we create a minimal alert reference
        alert = IntegrationAlert(
            alert_id=action.alert_id,
            source=action.metadata.get("alert_source", "soc") and _str_to_source(action.metadata.get("alert_source", "soc")),
            severity=_str_to_severity(action.metadata.get("alert_severity", "warning")),
            title=f"Approved action: {action.action_type}",
        )

        return self._execute_action(action.action_type, alert)

    def rollback_action(self, action_id: str) -> RemediationAction | None:
        """Roll back a completed remediation action.

        Args:
            action_id: ID of the action to roll back.

        Returns:
            The rolled-back action, or None if not found.
        """
        action = self._actions.get(action_id)
        if action is None:
            return None
        if action.status not in (RemediationStatus.COMPLETED, RemediationStatus.FAILED):
            return None

        action.rolled_back = True
        action.status = RemediationStatus.ROLLED_BACK
        action.completed_at = dt.datetime.now(dt.timezone.utc).isoformat()
        action.result = "Rolled back"
        return action

    def get_action(self, action_id: str) -> RemediationAction | None:
        """Get a remediation action by ID."""
        return self._actions.get(action_id)

    def list_actions(
        self,
        status: RemediationStatus | None = None,
        alert_id: str | None = None,
    ) -> list[RemediationAction]:
        """List remediation actions, optionally filtered."""
        actions = list(self._actions.values())
        if status is not None:
            actions = [a for a in actions if a.status == status]
        if alert_id is not None:
            actions = [a for a in actions if a.alert_id == alert_id]
        return actions

    def get_action_history(self, limit: int = 100) -> list[RemediationAction]:
        """Get remediation action history."""
        return self._action_history[-limit:]

    def reset(self) -> None:
        """Clear all actions and history."""
        self._actions.clear()
        self._action_history.clear()
        self._handlers.clear()


def _str_to_source(source_str: str):
    """Convert string to EventSource enum."""
    from .models import EventSource
    try:
        return EventSource(source_str)
    except ValueError:
        return EventSource.SOC


def _str_to_severity(severity_str: str):
    """Convert string to EventSeverity enum."""
    try:
        return EventSeverity(severity_str)
    except ValueError:
        return EventSeverity.WARNING


__all__ = [
    "AutoRemediationEngine",
    "REMEDIATION_SCALE_UP",
    "REMEDIATION_SCALE_DOWN",
    "REMEDIATION_RESTART_CONTAINER",
    "REMEDIATION_ISOLATE_NODE",
    "REMEDIATION_ESCALATE_SOC",
    "REMEDIATION_ACKNOWLEDGE_ALERT",
    "REMEDIATION_RUN_DIAGNOSTIC",
    "ALL_ACTION_TYPES",
    "APPROVAL_REQUIRED_ACTIONS",
]
