"""GCP Cloud Run integration for Data Center Commander.

Provides read-only access to Cloud Run service status, metrics, and
scaling recommendations. Supports autoscaling configuration with
min/max instances and concurrency settings.
"""
from __future__ import annotations

from .adapter import (
    CloudRunAdapter,
    CloudRunAuthError,
    CloudRunError,
    CloudRunNotFoundError,
    CloudRunValidationError,
    get_adapter,
)
from .models import (
    CloudRunCPUAllocation,
    CloudRunDeployment,
    CloudRunIngress,
    CloudRunMetrics,
    CloudRunScalingRecommendation,
    CloudRunServiceConfig,
    CloudRunServiceStatus,
    CloudRunStatus,
)

__all__ = [
    "CloudRunAdapter",
    "CloudRunAuthError",
    "CloudRunCPUAllocation",
    "CloudRunDeployment",
    "CloudRunError",
    "CloudRunIngress",
    "CloudRunMetrics",
    "CloudRunNotFoundError",
    "CloudRunScalingRecommendation",
    "CloudRunServiceConfig",
    "CloudRunServiceStatus",
    "CloudRunStatus",
    "CloudRunValidationError",
    "get_adapter",
]

__version__ = "0.1.0"
