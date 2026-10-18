"""AWS Auto Scaling integration for Data Center Commander."""
from __future__ import annotations

from .asg import ASGError, ASGManager, ASGNotFoundError, ASGValidationError
from .engine import AutoScalingEngine
from .launch_templates import (
    LaunchTemplateError,
    LaunchTemplateManager,
    LaunchTemplateNotFoundError,
    LaunchTemplateValidationError,
)
from .lifecycle_hooks import (
    LifecycleHookError,
    LifecycleHookManager,
    LifecycleHookNotFoundError,
    LifecycleHookValidationError,
)
from .models import (
    AutoScalingGroup,
    CapacityRebalanceStrategy,
    HealthStatus,
    Instance,
    InstanceReusePolicy,
    LaunchTemplate,
    LaunchTemplateSpecification,
    LifecycleHook,
    LifecycleState,
    LifecycleTransition,
    ScalingActivity,
    ScalingMetricType,
    ScalingPolicy,
    ScalingPolicyType,
    ScalingRecommendation,
    StepAdjustment,
    TerminationPolicy,
    WarmPool,
    WarmPoolState,
)
from .scaling_policies import (
    ScalingPolicyError,
    ScalingPolicyManager,
    ScalingPolicyNotFoundError,
    ScalingPolicyValidationError,
)
from .warm_pools import (
    WarmPoolError,
    WarmPoolManager,
    WarmPoolNotFoundError,
    WarmPoolValidationError,
)

__all__ = [
    "ASGError",
    "ASGManager",
    "ASGNotFoundError",
    "ASGValidationError",
    "AutoScalingEngine",
    "AutoScalingGroup",
    "CapacityRebalanceStrategy",
    "HealthStatus",
    "Instance",
    "InstanceReusePolicy",
    "LaunchTemplate",
    "LaunchTemplateError",
    "LaunchTemplateManager",
    "LaunchTemplateNotFoundError",
    "LaunchTemplateSpecification",
    "LaunchTemplateValidationError",
    "LifecycleHook",
    "LifecycleHookError",
    "LifecycleHookManager",
    "LifecycleHookNotFoundError",
    "LifecycleHookValidationError",
    "LifecycleState",
    "LifecycleTransition",
    "ScalingActivity",
    "ScalingMetricType",
    "ScalingPolicy",
    "ScalingPolicyError",
    "ScalingPolicyManager",
    "ScalingPolicyNotFoundError",
    "ScalingPolicyType",
    "ScalingPolicyValidationError",
    "ScalingRecommendation",
    "StepAdjustment",
    "TerminationPolicy",
    "WarmPool",
    "WarmPoolError",
    "WarmPoolManager",
    "WarmPoolNotFoundError",
    "WarmPoolState",
    "WarmPoolValidationError",
]
