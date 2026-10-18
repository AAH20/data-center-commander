"""Data Center Commander — Kubernetes Autoscaling Engine.

Provides horizontal pod autoscaler (HPA) management, custom metrics,
external metrics, scaling recommendations, and cost optimization
across Kubernetes clusters.
"""

from .engine import AutoscalingEngine
from .hpa import HPAEngine
from .metrics import MetricsCollector
from .models import (
    AutoscalingReport,
    HPAConfiguration,
    HPATarget,
    HPATargetKind,
    MetricSource,
    ScalingDirection,
    ScalingEvent,
    ScalingMetric,
    ScalingMetricType,
    ScalingPolicy,
    ScalingPolicyConfig,
    ScalingRecommendation,
    ScalingStatus,
)

__all__ = [
    # Enums
    "HPATargetKind",
    "MetricSource",
    "ScalingDirection",
    "ScalingMetricType",
    "ScalingPolicy",
    "ScalingStatus",
    # Models
    "AutoscalingReport",
    "HPAConfiguration",
    "HPATarget",
    "ScalingEvent",
    "ScalingMetric",
    "ScalingPolicyConfig",
    "ScalingRecommendation",
    # Engines
    "AutoscalingEngine",
    "HPAEngine",
    "MetricsCollector",
]

__version__ = "0.1.0"
