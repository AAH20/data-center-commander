"""Kubernetes Vertical Pod Autoscaler (VPA) integration for Data Center Commander.

Provides VPA recommendation analysis, update policy management, and
scaling decision generation for Kubernetes workloads.

Features:
  - VPA recommendation parsing and analysis
  - Update policy evaluation (Off, Initial, Auto, Recreate)
  - Rollout strategy management (Canary, Blue/Green, Rolling)
  - Resource policy constraints (min/max per container)
  - Metrics summary computation (avg, p95, p99)
  - Scaling decision generation with confidence scoring
"""
from __future__ import annotations

from .engine import VPAEngine
from .models import (
    ContainerScalingMode,
    ContainerUsageSample,
    CrossVersionObjectReference,
    PodResourcePolicy,
    PodUsageRecord,
    RecommendedContainerResources,
    RecommendationState,
    ResourceName,
    ResourcePolicy,
    ScalingDecision,
    TargetRef,
    TargetRefKind,
    UpdateMode,
    VPACondition,
    VPAObject,
    VPARecommendation,
    VPAReport,
    VPAMetricsSummary,
)
from .recommendations import VPARecommendationEngine
from .update_policies import (
    RolloutConfig,
    RolloutPhase,
    RolloutState,
    RolloutStrategy,
    UpdatePolicyConfig,
    UpdatePolicyEngine,
)

__all__ = [
    # Engine
    "VPAEngine",
    # Models
    "ContainerScalingMode",
    "ContainerUsageSample",
    "CrossVersionObjectReference",
    "PodResourcePolicy",
    "PodUsageRecord",
    "RecommendedContainerResources",
    "RecommendationState",
    "ResourceName",
    "ResourcePolicy",
    "ScalingDecision",
    "TargetRef",
    "TargetRefKind",
    "UpdateMode",
    "VPACondition",
    "VPAObject",
    "VPARecommendation",
    "VPAReport",
    "VPAMetricsSummary",
    # Recommendations
    "VPARecommendationEngine",
    # Update Policies
    "RolloutConfig",
    "RolloutPhase",
    "RolloutState",
    "RolloutStrategy",
    "UpdatePolicyConfig",
    "UpdatePolicyEngine",
]

__version__ = "0.1.0"
