"""Scaling policy manager for AWS Auto Scaling.

Provides CRUD operations for target tracking, step scaling, simple scaling,
and predictive scaling policies. All operations are advisory and read-only
against the AWS API unless explicitly permitted.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .asg import ASGManager
from .models import (
    ScalingMetricType,
    ScalingPolicy,
    ScalingPolicyType,
    StepAdjustment,
)

# Validation
POLICY_NAME_RE = re.compile(r"^[A-Za-z0-9._/-]{1,255}$")
MAX_STEP_ADJUSTMENTS = 20


class ScalingPolicyError(Exception):
    """Base exception for scaling policy operations."""


class ScalingPolicyNotFoundError(ScalingPolicyError):
    """Raised when a scaling policy is not found."""


class ScalingPolicyValidationError(ScalingPolicyError):
    """Raised when scaling policy validation fails."""


class ScalingPolicyManager:
    """Manages AWS scaling policies."""

    def __init__(self, asg_manager: ASGManager | None = None) -> None:
        self._policies: dict[str, ScalingPolicy] = {}
        self._asg_manager = asg_manager

    def create_target_tracking(
        self,
        *,
        name: str,
        asg_id: str,
        metric_type: ScalingMetricType,
        target_value: float,
        cooldown: int = 300,
        estimated_instance_warmup: int = 300,
        disable_scale_in: bool = False,
        tags: dict[str, str] | None = None,
    ) -> ScalingPolicy:
        """Create a target tracking scaling policy.

        Args:
            name: Policy name.
            asg_id: ASG ID to attach the policy to.
            metric_type: Metric to track.
            target_value: Target value for the metric.
            cooldown: Cooldown period in seconds.
            estimated_instance_warmup: Estimated instance warmup time in seconds.
            disable_scale_in: Whether to disable scale-in.
            tags: Resource tags.

        Returns:
            The created ScalingPolicy.
        """
        self._validate_name(name)
        self._validate_target_value(metric_type, target_value)

        policy_id = self._generate_policy_id(name)
        policy = ScalingPolicy(
            policy_id=policy_id,
            name=name,
            asg_id=asg_id,
            policy_type=ScalingPolicyType.TARGET_TRACKING,
            metric_type=metric_type,
            target_value=target_value,
            cooldown=cooldown,
            estimated_instance_warmup=estimated_instance_warmup,
            tags=dict(tags or {}),
            metadata={"disable_scale_in": disable_scale_in},
        )
        self._policies[policy_id] = policy
        return policy

    def create_step_scaling(
        self,
        *,
        name: str,
        asg_id: str,
        metric_type: ScalingMetricType,
        step_adjustments: list[StepAdjustment],
        cooldown: int = 300,
        min_adjustment_magnitude: int = 1,
        tags: dict[str, str] | None = None,
    ) -> ScalingPolicy:
        """Create a step scaling policy.

        Args:
            name: Policy name.
            asg_id: ASG ID to attach the policy to.
            metric_type: Metric to track.
            step_adjustments: List of step adjustments.
            cooldown: Cooldown period in seconds.
            min_adjustment_magnitude: Minimum adjustment magnitude.
            tags: Resource tags.

        Returns:
            The created ScalingPolicy.
        """
        self._validate_name(name)
        self._validate_step_adjustments(step_adjustments)

        policy_id = self._generate_policy_id(name)
        policy = ScalingPolicy(
            policy_id=policy_id,
            name=name,
            asg_id=asg_id,
            policy_type=ScalingPolicyType.STEP_SCALING,
            metric_type=metric_type,
            step_adjustments=list(step_adjustments),
            cooldown=cooldown,
            min_adjustment_magnitude=min_adjustment_magnitude,
            tags=dict(tags or {}),
        )
        self._policies[policy_id] = policy
        return policy

    def create_simple_scaling(
        self,
        *,
        name: str,
        asg_id: str,
        metric_type: ScalingMetricType,
        scaling_adjustment: int,
        cooldown: int = 300,
        min_adjustment_magnitude: int = 1,
        tags: dict[str, str] | None = None,
    ) -> ScalingPolicy:
        """Create a simple scaling policy.

        Args:
            name: Policy name.
            asg_id: ASG ID to attach the policy to.
            metric_type: Metric to track.
            scaling_adjustment: Number of instances to add/remove.
            cooldown: Cooldown period in seconds.
            min_adjustment_magnitude: Minimum adjustment magnitude.
            tags: Resource tags.

        Returns:
            The created ScalingPolicy.
        """
        self._validate_name(name)
        if scaling_adjustment == 0:
            raise ScalingPolicyValidationError("scaling_adjustment must be non-zero")

        policy_id = self._generate_policy_id(name)
        policy = ScalingPolicy(
            policy_id=policy_id,
            name=name,
            asg_id=asg_id,
            policy_type=ScalingPolicyType.SIMPLE_SCALING,
            metric_type=metric_type,
            step_adjustments=[StepAdjustment(scaling_adjustment=scaling_adjustment)],
            cooldown=cooldown,
            min_adjustment_magnitude=min_adjustment_magnitude,
            tags=dict(tags or {}),
        )
        self._policies[policy_id] = policy
        return policy

    def create_predictive(
        self,
        *,
        name: str,
        asg_id: str,
        metric_type: ScalingMetricType,
        target_value: float,
        predictive_scaling_mode: str = "ForecastAndScale",
        tags: dict[str, str] | None = None,
    ) -> ScalingPolicy:
        """Create a predictive scaling policy.

        Args:
            name: Policy name.
            asg_id: ASG ID to attach the policy to.
            metric_type: Metric to track.
            target_value: Target value for the metric.
            predictive_scaling_mode: ForecastAndScale or ForecastOnly.
            tags: Resource tags.

        Returns:
            The created ScalingPolicy.
        """
        self._validate_name(name)
        self._validate_target_value(metric_type, target_value)
        if predictive_scaling_mode not in ("ForecastAndScale", "ForecastOnly"):
            raise ScalingPolicyValidationError(
                f"Invalid predictive_scaling_mode: {predictive_scaling_mode}"
            )

        policy_id = self._generate_policy_id(name)
        policy = ScalingPolicy(
            policy_id=policy_id,
            name=name,
            asg_id=asg_id,
            policy_type=ScalingPolicyType.PREDICTIVE,
            metric_type=metric_type,
            target_value=target_value,
            predictive_scaling_mode=predictive_scaling_mode,
            tags=dict(tags or {}),
        )
        self._policies[policy_id] = policy
        return policy

    def get(self, policy_id: str) -> ScalingPolicy:
        """Get a scaling policy by ID.

        Raises:
            ScalingPolicyNotFoundError: If policy not found.
        """
        policy = self._policies.get(policy_id)
        if policy is None:
            raise ScalingPolicyNotFoundError(f"Scaling policy not found: {policy_id}")
        return policy

    def list_policies(
        self,
        *,
        asg_id: str = "",
        policy_type: ScalingPolicyType | None = None,
        enabled_only: bool = False,
    ) -> list[ScalingPolicy]:
        """List scaling policies, optionally filtered."""
        results = list(self._policies.values())
        if asg_id:
            results = [p for p in results if p.asg_id == asg_id]
        if policy_type is not None:
            results = [p for p in results if p.policy_type == policy_type]
        if enabled_only:
            results = [p for p in results if p.enabled]
        return sorted(results, key=lambda p: p.name)

    def update(
        self,
        policy_id: str,
        *,
        target_value: float | None = None,
        cooldown: int | None = None,
        enabled: bool | None = None,
    ) -> ScalingPolicy:
        """Update a scaling policy.

        Returns:
            The updated ScalingPolicy.
        """
        policy = self.get(policy_id)
        if target_value is not None:
            self._validate_target_value(policy.metric_type, target_value)
            policy.target_value = target_value
        if cooldown is not None:
            policy.cooldown = cooldown
        if enabled is not None:
            policy.enabled = enabled
        return policy

    def delete(self, policy_id: str) -> bool:
        """Delete a scaling policy. Returns True if it existed."""
        return self._policies.pop(policy_id, None) is not None

    def evaluate(
        self,
        policy_id: str,
        *,
        current_metric_value: float,
        current_capacity: int,
    ) -> dict[str, Any]:
        """Evaluate a scaling policy against current metrics.

        Args:
            policy_id: The scaling policy ID.
            current_metric_value: Current value of the tracked metric.
            current_capacity: Current number of instances.

        Returns:
            Dict with scaling decision (scale_out, scale_in, or no_action).
        """
        policy = self.get(policy_id)
        if not policy.enabled:
            return {
                "action": "no_action",
                "reason": "policy_disabled",
                "current_capacity": current_capacity,
                "recommended_capacity": current_capacity,
            }

        if policy.policy_type == ScalingPolicyType.TARGET_TRACKING:
            return self._evaluate_target_tracking(
                policy, current_metric_value, current_capacity
            )
        elif policy.policy_type == ScalingPolicyType.STEP_SCALING:
            return self._evaluate_step_scaling(
                policy, current_metric_value, current_capacity
            )
        elif policy.policy_type == ScalingPolicyType.SIMPLE_SCALING:
            return self._evaluate_simple_scaling(
                policy, current_metric_value, current_capacity
            )
        elif policy.policy_type == ScalingPolicyType.PREDICTIVE:
            return self._evaluate_predictive(
                policy, current_metric_value, current_capacity
            )
        return {
            "action": "no_action",
            "reason": "unknown_policy_type",
            "current_capacity": current_capacity,
            "recommended_capacity": current_capacity,
        }

    def _evaluate_target_tracking(
        self,
        policy: ScalingPolicy,
        current_value: float,
        current_capacity: int,
    ) -> dict[str, Any]:
        """Evaluate target tracking policy."""
        if policy.target_value is None or policy.target_value <= 0:
            return {
                "action": "no_action",
                "reason": "invalid_target_value",
                "current_capacity": current_capacity,
                "recommended_capacity": current_capacity,
            }

        # Calculate desired capacity to reach target
        ratio = current_value / policy.target_value
        desired = max(1, round(current_capacity * ratio))

        if desired > current_capacity:
            return {
                "action": "scale_out",
                "reason": f"metric_above_target ({current_value:.2f} > {policy.target_value:.2f})",
                "current_capacity": current_capacity,
                "recommended_capacity": desired,
                "adjustment": desired - current_capacity,
            }
        elif desired < current_capacity:
            return {
                "action": "scale_in",
                "reason": f"metric_below_target ({current_value:.2f} < {policy.target_value:.2f})",
                "current_capacity": current_capacity,
                "recommended_capacity": desired,
                "adjustment": desired - current_capacity,
            }
        return {
            "action": "no_action",
            "reason": "at_target",
            "current_capacity": current_capacity,
            "recommended_capacity": current_capacity,
        }

    def _evaluate_step_scaling(
        self,
        policy: ScalingPolicy,
        current_value: float,
        current_capacity: int,
    ) -> dict[str, Any]:
        """Evaluate step scaling policy."""
        # Find applicable step adjustment
        applicable_adjustment = 0
        for adj in policy.step_adjustments:
            lower = adj.metric_interval_lower_bound
            upper = adj.metric_interval_upper_bound
            if (lower is None or current_value >= lower) and (upper is None or current_value < upper):
                applicable_adjustment = adj.scaling_adjustment
                break

        if applicable_adjustment == 0:
            return {
                "action": "no_action",
                "reason": "no_applicable_step",
                "current_capacity": current_capacity,
                "recommended_capacity": current_capacity,
            }

        desired = current_capacity + applicable_adjustment
        action = "scale_out" if applicable_adjustment > 0 else "scale_in"
        return {
            "action": action,
            "reason": f"step_adjustment ({applicable_adjustment:+d})",
            "current_capacity": current_capacity,
            "recommended_capacity": desired,
            "adjustment": applicable_adjustment,
        }

    def _evaluate_simple_scaling(
        self,
        policy: ScalingPolicy,
        current_value: float,
        current_capacity: int,
    ) -> dict[str, Any]:
        """Evaluate simple scaling policy."""
        if not policy.step_adjustments:
            return {
                "action": "no_action",
                "reason": "no_step_adjustments",
                "current_capacity": current_capacity,
                "recommended_capacity": current_capacity,
            }

        adjustment = policy.step_adjustments[0].scaling_adjustment
        desired = current_capacity + adjustment
        action = "scale_out" if adjustment > 0 else "scale_in"
        return {
            "action": action,
            "reason": f"simple_adjustment ({adjustment:+d})",
            "current_capacity": current_capacity,
            "recommended_capacity": desired,
            "adjustment": adjustment,
        }

    def _evaluate_predictive(
        self,
        policy: ScalingPolicy,
        current_value: float,
        current_capacity: int,
    ) -> dict[str, Any]:
        """Evaluate predictive scaling policy."""
        # Predictive scaling uses forecasted metrics
        # For advisory purposes, we use current metrics as a proxy
        if policy.target_value is None:
            return {
                "action": "no_action",
                "reason": "no_target_value",
                "current_capacity": current_capacity,
                "recommended_capacity": current_capacity,
            }

        ratio = current_value / policy.target_value
        desired = max(1, round(current_capacity * ratio))

        if desired > current_capacity:
            return {
                "action": "scale_out",
                "reason": f"predictive_forecast_above_target ({current_value:.2f} > {policy.target_value:.2f})",
                "current_capacity": current_capacity,
                "recommended_capacity": desired,
                "adjustment": desired - current_capacity,
                "mode": policy.predictive_scaling_mode,
            }
        elif desired < current_capacity:
            return {
                "action": "scale_in",
                "reason": f"predictive_forecast_below_target ({current_value:.2f} < {policy.target_value:.2f})",
                "current_capacity": current_capacity,
                "recommended_capacity": desired,
                "adjustment": desired - current_capacity,
                "mode": policy.predictive_scaling_mode,
            }
        return {
            "action": "no_action",
            "reason": "predictive_at_target",
            "current_capacity": current_capacity,
            "recommended_capacity": current_capacity,
            "mode": policy.predictive_scaling_mode,
        }

    # -- Validation helpers --

    def _validate_name(self, name: str) -> None:
        if not name or not POLICY_NAME_RE.fullmatch(name):
            raise ScalingPolicyValidationError(
                f"Invalid policy name: {name!r}. Must be 1-255 chars, alphanumeric plus . _ / -"
            )

    def _validate_target_value(self, metric_type: ScalingMetricType, target_value: float) -> None:
        if target_value <= 0:
            raise ScalingPolicyValidationError(
                f"target_value must be > 0, got {target_value}"
            )
        if metric_type == ScalingMetricType.AVG_CPU_UTILIZATION and target_value > 100:
            raise ScalingPolicyValidationError(
                f"CPU utilization target must be <= 100, got {target_value}"
            )

    def _validate_step_adjustments(self, adjustments: list[StepAdjustment]) -> None:
        if not adjustments:
            raise ScalingPolicyValidationError("At least one step adjustment is required")
        if len(adjustments) > MAX_STEP_ADJUSTMENTS:
            raise ScalingPolicyValidationError(
                f"Maximum {MAX_STEP_ADJUSTMENTS} step adjustments allowed, got {len(adjustments)}"
            )
        for adj in adjustments:
            if adj.scaling_adjustment == 0:
                raise ScalingPolicyValidationError("Step adjustment scaling_adjustment must be non-zero")

    def _generate_policy_id(self, name: str) -> str:
        """Generate a deterministic policy ID from name and timestamp."""
        import hashlib
        ts = datetime.now(timezone.utc).isoformat()
        digest = hashlib.sha256(f"{name}:{ts}".encode()).hexdigest()[:17]
        return f"sp-{digest}"
