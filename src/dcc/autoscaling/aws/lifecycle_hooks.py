"""Lifecycle hook manager for AWS Auto Scaling.

Provides CRUD operations for lifecycle hooks that intercept instance
launch/terminate transitions for custom actions. All operations are
advisory and read-only against the AWS API unless explicitly permitted.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .asg import ASGManager
from .models import LifecycleHook, LifecycleState, LifecycleTransition

# Validation
HOOK_NAME_RE = re.compile(r"^[A-Za-z0-9._/-]{1,255}$")
MAX_HEARTBEAT_TIMEOUT = 86400  # 24 hours
MIN_HEARTBEAT_TIMEOUT = 30
VALID_DEFAULT_RESULTS = ("ABANDON", "CONTINUE")


class LifecycleHookError(Exception):
    """Base exception for lifecycle hook operations."""


class LifecycleHookNotFoundError(LifecycleHookError):
    """Raised when a lifecycle hook is not found."""


class LifecycleHookValidationError(LifecycleHookError):
    """Raised when lifecycle hook validation fails."""


class LifecycleHookManager:
    """Manages AWS lifecycle hooks."""

    def __init__(self, asg_manager: ASGManager | None = None) -> None:
        self._hooks: dict[str, LifecycleHook] = {}
        self._asg_manager = asg_manager

    def create(
        self,
        *,
        name: str,
        asg_id: str,
        lifecycle_transition: LifecycleTransition,
        heartbeat_timeout: int = 3600,
        default_result: str = "ABANDON",
        notification_target_arn: str = "",
        role_arn: str = "",
        notification_metadata: str = "",
    ) -> LifecycleHook:
        """Create a lifecycle hook.

        Args:
            name: Hook name.
            asg_id: ASG ID to attach the hook to.
            lifecycle_transition: LAUNCH or TERMINATE.
            heartbeat_timeout: Heartbeat timeout in seconds (30-86400).
            default_result: ABANDON or CONTINUE.
            notification_target_arn: SNS topic or SQS queue ARN.
            role_arn: IAM role ARN for the hook.
            notification_metadata: Custom notification metadata.

        Returns:
            The created LifecycleHook.
        """
        self._validate_name(name)
        self._validate_heartbeat_timeout(heartbeat_timeout)
        self._validate_default_result(default_result)

        hook_id = self._generate_hook_id(name)
        hook = LifecycleHook(
            hook_id=hook_id,
            name=name,
            asg_id=asg_id,
            lifecycle_transition=lifecycle_transition,
            heartbeat_timeout=heartbeat_timeout,
            default_result=default_result,
            notification_target_arn=notification_target_arn,
            role_arn=role_arn,
            notification_metadata=notification_metadata,
        )
        self._hooks[hook_id] = hook
        return hook

    def get(self, hook_id: str) -> LifecycleHook:
        """Get a lifecycle hook by ID.

        Raises:
            LifecycleHookNotFoundError: If hook not found.
        """
        hook = self._hooks.get(hook_id)
        if hook is None:
            raise LifecycleHookNotFoundError(f"Lifecycle hook not found: {hook_id}")
        return hook

    def list_hooks(
        self,
        *,
        asg_id: str = "",
        transition: LifecycleTransition | None = None,
    ) -> list[LifecycleHook]:
        """List lifecycle hooks, optionally filtered."""
        results = list(self._hooks.values())
        if asg_id:
            results = [h for h in results if h.asg_id == asg_id]
        if transition is not None:
            results = [h for h in results if h.lifecycle_transition == transition]
        return sorted(results, key=lambda h: h.name)

    def update(
        self,
        hook_id: str,
        *,
        heartbeat_timeout: int | None = None,
        default_result: str | None = None,
        notification_target_arn: str | None = None,
        role_arn: str | None = None,
    ) -> LifecycleHook:
        """Update a lifecycle hook.

        Returns:
            The updated LifecycleHook.
        """
        hook = self.get(hook_id)
        if heartbeat_timeout is not None:
            self._validate_heartbeat_timeout(heartbeat_timeout)
            hook.heartbeat_timeout = heartbeat_timeout
        if default_result is not None:
            self._validate_default_result(default_result)
            hook.default_result = default_result
        if notification_target_arn is not None:
            hook.notification_target_arn = notification_target_arn
        if role_arn is not None:
            hook.role_arn = role_arn
        return hook

    def delete(self, hook_id: str) -> bool:
        """Delete a lifecycle hook. Returns True if it existed."""
        return self._hooks.pop(hook_id, None) is not None

    def complete_lifecycle_action(
        self,
        hook_id: str,
        *,
        instance_id: str,
        result: str,
    ) -> dict[str, Any]:
        """Complete a lifecycle action for an instance.

        Args:
            hook_id: The lifecycle hook ID.
            instance_id: The instance ID.
            result: CONTINUE or ABANDON.

        Returns:
            Dict with the completion result.
        """
        hook = self.get(hook_id)
        if result not in VALID_DEFAULT_RESULTS:
            raise LifecycleHookValidationError(
                f"Invalid lifecycle action result: {result!r}. Must be ABANDON or CONTINUE"
            )

        return {
            "hook_id": hook_id,
            "instance_id": instance_id,
            "result": result,
            "lifecycle_transition": hook.lifecycle_transition.value,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "asg_id": hook.asg_id,
        }

    def record_heartbeat(self, hook_id: str, *, instance_id: str) -> dict[str, Any]:
        """Record a lifecycle heartbeat for an instance.

        Args:
            hook_id: The lifecycle hook ID.
            instance_id: The instance ID.

        Returns:
            Dict with the heartbeat result.
        """
        hook = self.get(hook_id)
        return {
            "hook_id": hook_id,
            "instance_id": instance_id,
            "heartbeat_at": datetime.now(timezone.utc).isoformat(),
            "timeout_at": (
                datetime.now(timezone.utc).timestamp() + hook.heartbeat_timeout
            ),
            "lifecycle_transition": hook.lifecycle_transition.value,
        }

    def get_pending_actions(self, asg_id: str) -> list[dict[str, Any]]:
        """Get pending lifecycle actions for an ASG.

        Returns:
            List of pending lifecycle actions.
        """
        hooks = self.list_hooks(asg_id=asg_id)
        pending = []
        for hook in hooks:
            pending.append({
                "hook_id": hook.hook_id,
                "name": hook.name,
                "lifecycle_transition": hook.lifecycle_transition.value,
                "heartbeat_timeout": hook.heartbeat_timeout,
                "default_result": hook.default_result,
            })
        return pending

    # -- Validation helpers --

    def _validate_name(self, name: str) -> None:
        if not name or not HOOK_NAME_RE.fullmatch(name):
            raise LifecycleHookValidationError(
                f"Invalid hook name: {name!r}. Must be 1-255 chars, alphanumeric plus . _ / -"
            )

    def _validate_heartbeat_timeout(self, timeout: int) -> None:
        if not MIN_HEARTBEAT_TIMEOUT <= timeout <= MAX_HEARTBEAT_TIMEOUT:
            raise LifecycleHookValidationError(
                f"heartbeat_timeout must be between {MIN_HEARTBEAT_TIMEOUT} and "
                f"{MAX_HEARTBEAT_TIMEOUT} seconds, got {timeout}"
            )

    def _validate_default_result(self, result: str) -> None:
        if result not in VALID_DEFAULT_RESULTS:
            raise LifecycleHookValidationError(
                f"default_result must be one of {VALID_DEFAULT_RESULTS}, got {result!r}"
            )

    def _generate_hook_id(self, name: str) -> str:
        """Generate a deterministic hook ID from name and timestamp."""
        import hashlib
        ts = datetime.now(timezone.utc).isoformat()
        digest = hashlib.sha256(f"{name}:{ts}".encode()).hexdigest()[:17]
        return f"lh-{digest}"
