"""Auto Scaling engine: high-level facade for AWS Auto Scaling operations.

Coordinates launch templates, ASGs, scaling policies, lifecycle hooks,
and warm pools into a single management interface. All operations are
advisory and read-only against the AWS API unless explicitly permitted.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from .asg import ASGManager, ASGNotFoundError, ASGValidationError
from .launch_templates import LaunchTemplateManager, LaunchTemplateNotFoundError, LaunchTemplateValidationError
from .lifecycle_hooks import LifecycleHookManager, LifecycleHookNotFoundError, LifecycleHookValidationError
from .models import (
    AutoScalingGroup,
    HealthStatus,
    Instance,
    InstanceReusePolicy,
    LaunchTemplate,
    LifecycleHook,
    LifecycleState,
    LifecycleTransition,
    ScalingMetricType,
    ScalingPolicy,
    ScalingPolicyType,
    ScalingRecommendation,
    StepAdjustment,
    WarmPool,
    WarmPoolState,
)
from .scaling_policies import ScalingPolicyManager, ScalingPolicyNotFoundError, ScalingPolicyValidationError
from .warm_pools import WarmPoolManager, WarmPoolNotFoundError, WarmPoolValidationError


class AutoScalingEngine:
    """High-level facade for AWS Auto Scaling operations.

    Coordinates launch templates, ASGs, scaling policies, lifecycle hooks,
    and warm pools into a single management interface.
    """

    def __init__(self) -> None:
        self._template_manager = LaunchTemplateManager()
        self._asg_manager = ASGManager(self._template_manager)
        self._policy_manager = ScalingPolicyManager(self._asg_manager)
        self._hook_manager = LifecycleHookManager(self._asg_manager)
        self._warm_pool_manager = WarmPoolManager(self._asg_manager)

    @property
    def templates(self) -> LaunchTemplateManager:
        return self._template_manager

    @property
    def asgs(self) -> ASGManager:
        return self._asg_manager

    @property
    def policies(self) -> ScalingPolicyManager:
        return self._policy_manager

    @property
    def hooks(self) -> LifecycleHookManager:
        return self._hook_manager

    @property
    def warm_pools(self) -> WarmPoolManager:
        return self._warm_pool_manager

    # -- Composite operations --

    def create_asg_with_template(
        self,
        *,
        name: str,
        min_size: int,
        max_size: int,
        desired_capacity: int | None = None,
        image_id: str = "",
        instance_type: str = "",
        key_name: str = "",
        security_group_ids: list[str] | None = None,
        user_data: str = "",
        availability_zones: list[str] | None = None,
        vpc_zone_identifier: list[str] | None = None,
        tags: dict[str, str] | None = None,
        capacity_rebalance: bool = False,
    ) -> tuple[LaunchTemplate, AutoScalingGroup]:
        """Create a launch template and ASG in one operation.

        Returns:
            Tuple of (LaunchTemplate, AutoScalingGroup).
        """
        template = self._template_manager.create(
            name=f"{name}-lt",
            image_id=image_id,
            instance_type=instance_type,
            key_name=key_name,
            security_group_ids=security_group_ids,
            user_data=user_data,
        )
        asg = self._asg_manager.create(
            name=name,
            min_size=min_size,
            max_size=max_size,
            desired_capacity=desired_capacity,
            launch_template_id=template.launch_template_id,
            availability_zones=availability_zones,
            vpc_zone_identifier=vpc_zone_identifier,
            tags=tags,
            capacity_rebalance=capacity_rebalance,
        )
        return template, asg

    def create_asg_with_policies(
        self,
        *,
        name: str,
        min_size: int,
        max_size: int,
        desired_capacity: int | None = None,
        image_id: str = "",
        instance_type: str = "",
        availability_zones: list[str] | None = None,
        target_tracking_policies: list[dict[str, Any]] | None = None,
        step_scaling_policies: list[dict[str, Any]] | None = None,
        tags: dict[str, str] | None = None,
    ) -> tuple[LaunchTemplate, AutoScalingGroup, list[ScalingPolicy]]:
        """Create an ASG with scaling policies in one operation.

        Args:
            target_tracking_policies: List of dicts with keys: name, metric_type, target_value.
            step_scaling_policies: List of dicts with keys: name, metric_type, step_adjustments.

        Returns:
            Tuple of (LaunchTemplate, AutoScalingGroup, list[ScalingPolicy]).
        """
        template, asg = self.create_asg_with_template(
            name=name,
            min_size=min_size,
            max_size=max_size,
            desired_capacity=desired_capacity,
            image_id=image_id,
            instance_type=instance_type,
            availability_zones=availability_zones,
            tags=tags,
        )

        policies: list[ScalingPolicy] = []
        for tp in (target_tracking_policies or []):
            policy = self._policy_manager.create_target_tracking(
                name=tp["name"],
                asg_id=asg.asg_id,
                metric_type=ScalingMetricType(tp.get("metric_type", "avg_cpu_utilization")),
                target_value=tp["target_value"],
                cooldown=tp.get("cooldown", 300),
                estimated_instance_warmup=tp.get("estimated_instance_warmup", 300),
                disable_scale_in=tp.get("disable_scale_in", False),
            )
            policies.append(policy)

        for sp in (step_scaling_policies or []):
            adjustments = [
                StepAdjustment(
                    metric_interval_lower_bound=sa.get("metric_interval_lower_bound"),
                    metric_interval_upper_bound=sa.get("metric_interval_upper_bound"),
                    scaling_adjustment=sa["scaling_adjustment"],
                )
                for sa in sp.get("step_adjustments", [])
            ]
            policy = self._policy_manager.create_step_scaling(
                name=sp["name"],
                asg_id=asg.asg_id,
                metric_type=ScalingMetricType(sp.get("metric_type", "avg_cpu_utilization")),
                step_adjustments=adjustments,
                cooldown=sp.get("cooldown", 300),
                min_adjustment_magnitude=sp.get("min_adjustment_magnitude", 1),
            )
            policies.append(policy)

        return template, asg, policies

    def evaluate_scaling(
        self,
        asg_id: str,
        *,
        current_metric_value: float,
        metric_type: ScalingMetricType = ScalingMetricType.AVG_CPU_UTILIZATION,
    ) -> list[dict[str, Any]]:
        """Evaluate all scaling policies for an ASG against current metrics.

        Returns:
            List of scaling decisions from each policy.
        """
        asg = self._asg_manager.get(asg_id)
        policies = self._policy_manager.list_policies(asg_id=asg_id, enabled_only=True)
        results = []
        for policy in policies:
            if policy.metric_type == metric_type:
                decision = self._policy_manager.evaluate(
                    policy.policy_id,
                    current_metric_value=current_metric_value,
                    current_capacity=asg.instance_count,
                )
                decision["policy_id"] = policy.policy_id
                decision["policy_name"] = policy.name
                decision["policy_type"] = policy.policy_type.value
                results.append(decision)
        return results

    def get_recommendation(
        self,
        asg_id: str,
        *,
        current_metric_value: float,
        metric_type: ScalingMetricType = ScalingMetricType.AVG_CPU_UTILIZATION,
        hourly_cost_per_instance: float = 0.0,
    ) -> ScalingRecommendation:
        """Get a scaling recommendation for an ASG based on current metrics.

        Returns:
            ScalingRecommendation with advisory action.
        """
        asg = self._asg_manager.get(asg_id)
        decisions = self.evaluate_scaling(
            asg_id,
            current_metric_value=current_metric_value,
            metric_type=metric_type,
        )

        if not decisions:
            return ScalingRecommendation(
                asg_id=asg_id,
                action="no_action",
                current_capacity=asg.instance_count,
                recommended_capacity=asg.instance_count,
                reason="no_enabled_policies",
                confidence=0.0,
                risk_level="low",
            )

        # Use the first policy's decision (could be enhanced with multi-policy logic)
        decision = decisions[0]
        action = decision.get("action", "no_action")
        recommended = decision.get("recommended_capacity", asg.instance_count)
        adjustment = decision.get("adjustment", 0)

        # Calculate cost impact
        cost_impact = adjustment * hourly_cost_per_instance * 730  # monthly

        # Assess risk
        risk_level = "low"
        if action == "scale_out" and recommended > asg.max_size:
            risk_level = "high"
        elif action == "scale_in" and recommended < asg.min_size:
            risk_level = "high"
        elif abs(adjustment) > 5:
            risk_level = "medium"

        return ScalingRecommendation(
            asg_id=asg_id,
            action=action,
            current_capacity=asg.instance_count,
            recommended_capacity=recommended,
            reason=decision.get("reason", ""),
            confidence=0.8 if decision.get("reason") else 0.5,
            estimated_cost_impact=cost_impact,
            risk_level=risk_level,
            provenance={
                "source": "scaling_policy_evaluation",
                "metric_type": metric_type.value,
                "current_metric_value": current_metric_value,
                "policies_evaluated": len(decisions),
                "label": "ADVISORY RECOMMENDATION - NOT FOR AUTONOMOUS EXECUTION",
            },
        )

    def get_status(self) -> dict[str, Any]:
        """Get overall Auto Scaling status."""
        asgs = self._asg_manager.list_asgs()
        policies = self._policy_manager.list_policies()
        hooks = self._hook_manager.list_hooks()
        pools = self._warm_pool_manager.list_pools()

        total_instances = sum(a.instance_count for a in asgs)
        total_healthy = sum(a.healthy_count for a in asgs)

        return {
            "asg_count": len(asgs),
            "total_instances": total_instances,
            "total_healthy": total_healthy,
            "policy_count": len(policies),
            "hook_count": len(hooks),
            "warm_pool_count": len(pools),
            "asgs": {a.asg_id: a.to_dict() for a in asgs},
            "policies": {p.policy_id: p.to_dict() for p in policies},
            "hooks": {h.hook_id: h.to_dict() for h in hooks},
            "warm_pools": {p.warm_pool_id: p.to_dict() for p in pools},
        }
