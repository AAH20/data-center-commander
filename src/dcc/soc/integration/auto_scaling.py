"""Auto-scaling decision engine with safety bounds.

Makes scaling decisions based on current utilization, forecasts, and
alerts, with configurable safety bounds to prevent thrashing and
ensure stability. All decisions are advisory and require explicit
execution permission.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from .models import ScalingAction, ScalingDecision


# Default safety bounds
DEFAULT_MIN_REPLICAS = 1
DEFAULT_MAX_REPLICAS = 100
DEFAULT_SCALE_UP_THRESHOLD = 80.0  # CPU/memory %
DEFAULT_SCALE_DOWN_THRESHOLD = 20.0  # CPU/memory %
DEFAULT_SCALE_UP_COOLDOWN = 300.0  # seconds
DEFAULT_SCALE_DOWN_COOLDOWN = 600.0  # seconds
DEFAULT_EMERGENCY_THRESHOLD = 95.0  # CPU/memory %


@dataclass
class ScalingPolicy:
    """Configuration for auto-scaling behavior.

    Attributes:
        min_replicas: Minimum number of replicas.
        max_replicas: Maximum number of replicas.
        scale_up_threshold: CPU/memory % to trigger scale up.
        scale_down_threshold: CPU/memory % to trigger scale down.
        emergency_threshold: CPU/memory % for emergency scaling.
        scale_up_cooldown: Minimum seconds between scale-up actions.
        scale_down_cooldown: Minimum seconds between scale-down actions.
        scale_up_step: Number of replicas to add per scale-up.
        scale_down_step: Number of replicas to remove per scale-down.
    """
    min_replicas: int = DEFAULT_MIN_REPLICAS
    max_replicas: int = DEFAULT_MAX_REPLICAS
    scale_up_threshold: float = DEFAULT_SCALE_UP_THRESHOLD
    scale_down_threshold: float = DEFAULT_SCALE_DOWN_THRESHOLD
    emergency_threshold: float = DEFAULT_EMERGENCY_THRESHOLD
    scale_up_cooldown: float = DEFAULT_SCALE_UP_COOLDOWN
    scale_down_cooldown: float = DEFAULT_SCALE_DOWN_COOLDOWN
    scale_up_step: int = 1
    scale_down_step: int = 1

    def __post_init__(self) -> None:
        if self.min_replicas < 0:
            raise ValueError("min_replicas must be non-negative")
        if self.max_replicas <= self.min_replicas:
            raise ValueError("max_replicas must be > min_replicas")
        if not 0 <= self.scale_down_threshold <= 100:
            raise ValueError("scale_down_threshold must be 0-100")
        if not 0 <= self.scale_up_threshold <= 100:
            raise ValueError("scale_up_threshold must be 0-100")
        if not 0 <= self.emergency_threshold <= 100:
            raise ValueError("emergency_threshold must be 0-100")
        if self.scale_down_threshold >= self.scale_up_threshold:
            raise ValueError("scale_down_threshold must be < scale_up_threshold")
        if self.emergency_threshold < self.scale_up_threshold:
            raise ValueError("emergency_threshold must be >= scale_up_threshold")
        if self.scale_up_step < 1:
            raise ValueError("scale_up_step must be >= 1")
        if self.scale_down_step < 1:
            raise ValueError("scale_down_step must be >= 1")


@dataclass
class ScalingMetrics:
    """Current scaling metrics for a service.

    Attributes:
        current_replicas: Current number of replicas.
        cpu_percent: Current CPU utilization %.
        memory_percent: Current memory utilization %.
        request_rate: Current request rate (requests/sec).
        error_rate: Current error rate (%).
        avg_response_time_ms: Average response time in ms.
    """
    current_replicas: int
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    request_rate: float = 0.0
    error_rate: float = 0.0
    avg_response_time_ms: float = 0.0


class AutoScalingEngine:
    """Auto-scaling decision engine.

    Evaluates current metrics against scaling policies and produces
    scaling decisions with safety bounds applied. All decisions are
    advisory (execution_permitted=False).

    Usage:
        engine = AutoScalingEngine()
        engine.set_policy("web-service", ScalingPolicy(min_replicas=2, max_replicas=20))
        decision = engine.evaluate("web-service", ScalingMetrics(current_replicas=3, cpu_percent=85))
    """

    def __init__(self) -> None:
        self._policies: dict[str, ScalingPolicy] = {}
        self._last_scale_up: dict[str, float] = {}
        self._last_scale_down: dict[str, float] = {}
        self._decision_history: list[ScalingDecision] = []

    def set_policy(self, service_name: str, policy: ScalingPolicy) -> None:
        """Set the scaling policy for a service."""
        self._policies[service_name] = policy

    def get_policy(self, service_name: str) -> ScalingPolicy | None:
        """Get the scaling policy for a service."""
        return self._policies.get(service_name)

    def evaluate(
        self,
        service_name: str,
        metrics: ScalingMetrics,
        *,
        forecast_cpu_percent: float | None = None,
        forecast_memory_percent: float | None = None,
    ) -> ScalingDecision:
        """Evaluate metrics and produce a scaling decision.

        Args:
            service_name: Name of the service to evaluate.
            metrics: Current scaling metrics.
            forecast_cpu_percent: Optional forecasted CPU %.
            forecast_memory_percent: Optional forecasted memory %.

        Returns:
            ScalingDecision with the recommended action.
        """
        policy = self._policies.get(service_name)
        if policy is None:
            policy = ScalingPolicy()

        now = time.time()
        current_replicas = metrics.current_replicas

        # Determine the effective utilization (max of CPU and memory)
        utilization = max(metrics.cpu_percent, metrics.memory_percent)

        # Consider forecast if available
        if forecast_cpu_percent is not None:
            utilization = max(utilization, forecast_cpu_percent)
        if forecast_memory_percent is not None:
            utilization = max(utilization, forecast_memory_percent)

        # Check emergency threshold first
        if utilization >= policy.emergency_threshold:
            return self._make_decision(
                service_name, ScalingAction.EMERGENCY_SCALE, current_replicas,
                policy, now, utilization, "emergency_threshold",
            )

        # Check scale-up threshold
        if utilization >= policy.scale_up_threshold:
            # Check cooldown
            last_up = self._last_scale_up.get(service_name, 0)
            if now - last_up >= policy.scale_up_cooldown:
                return self._make_decision(
                    service_name, ScalingAction.SCALE_UP, current_replicas,
                    policy, now, utilization, "scale_up_threshold",
                )

        # Check scale-down threshold
        if utilization <= policy.scale_down_threshold:
            # Check cooldown
            last_down = self._last_scale_down.get(service_name, 0)
            if now - last_down >= policy.scale_down_cooldown:
                return self._make_decision(
                    service_name, ScalingAction.SCALE_DOWN, current_replicas,
                    policy, now, utilization, "scale_down_threshold",
                )

        # No scaling needed
        return ScalingDecision(
            decision_id=f"dec-{service_name}-{int(now)}",
            action=ScalingAction.MAINTAIN,
            current_replicas=current_replicas,
            target_replicas=current_replicas,
            reason=f"Utilization {utilization:.1f}% within normal range",
            confidence=0.9,
            safety_bounds_applied=False,
            timestamp=now,
            metadata={
                "cpu_percent": metrics.cpu_percent,
                "memory_percent": metrics.memory_percent,
                "utilization": utilization,
            },
        )

    def _make_decision(
        self,
        service_name: str,
        action: ScalingAction,
        current_replicas: int,
        policy: ScalingPolicy,
        now: float,
        utilization: float,
        reason: str,
    ) -> ScalingDecision:
        """Create a scaling decision with safety bounds applied."""
        target = current_replicas
        safety_applied = False

        if action in (ScalingAction.SCALE_UP, ScalingAction.EMERGENCY_SCALE):
            step = policy.scale_up_step
            if action == ScalingAction.EMERGENCY_SCALE:
                step = max(step, 2)  # Emergency scales faster
            target = current_replicas + step
            if target > policy.max_replicas:
                target = policy.max_replicas
                safety_applied = True
            self._last_scale_up[service_name] = now

        elif action == ScalingAction.SCALE_DOWN:
            target = current_replicas - policy.scale_down_step
            if target < policy.min_replicas:
                target = policy.min_replicas
                safety_applied = True
            self._last_scale_down[service_name] = now

        # Calculate confidence based on how far from threshold
        if action == ScalingAction.EMERGENCY_SCALE:
            confidence = min(0.95, 0.7 + (utilization - policy.emergency_threshold) / 100)
        elif action == ScalingAction.SCALE_UP:
            confidence = min(0.9, 0.6 + (utilization - policy.scale_up_threshold) / 100)
        elif action == ScalingAction.SCALE_DOWN:
            confidence = min(0.9, 0.6 + (policy.scale_down_threshold - utilization) / 100)
        else:
            confidence = 0.8

        decision = ScalingDecision(
            decision_id=f"dec-{service_name}-{int(now)}",
            action=action,
            current_replicas=current_replicas,
            target_replicas=target,
            reason=f"{reason}: utilization {utilization:.1f}%",
            confidence=round(confidence, 4),
            safety_bounds_applied=safety_applied,
            timestamp=now,
            metadata={
                "utilization": utilization,
                "policy": {
                    "min_replicas": policy.min_replicas,
                    "max_replicas": policy.max_replicas,
                    "scale_up_threshold": policy.scale_up_threshold,
                    "scale_down_threshold": policy.scale_down_threshold,
                },
            },
        )

        self._decision_history.append(decision)
        return decision

    def get_decision_history(
        self, service_name: str | None = None, limit: int = 100
    ) -> list[ScalingDecision]:
        """Get scaling decision history, optionally filtered by service."""
        history = self._decision_history
        if service_name is not None:
            history = [d for d in history if d.decision_id.startswith(f"dec-{service_name}-")]
        return history[-limit:]

    def reset(self) -> None:
        """Clear all policies and history."""
        self._policies.clear()
        self._last_scale_up.clear()
        self._last_scale_down.clear()
        self._decision_history.clear()


__all__ = [
    "AutoScalingEngine",
    "ScalingPolicy",
    "ScalingMetrics",
    "DEFAULT_MIN_REPLICAS",
    "DEFAULT_MAX_REPLICAS",
    "DEFAULT_SCALE_UP_THRESHOLD",
    "DEFAULT_SCALE_DOWN_THRESHOLD",
    "DEFAULT_EMERGENCY_THRESHOLD",
]
