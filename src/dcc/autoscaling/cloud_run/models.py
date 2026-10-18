"""Data models for GCP Cloud Run integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CloudRunStatus(str, Enum):
    """Status of a Cloud Run service."""
    READY = "ready"
    DEPLOYING = "deploying"
    DELETING = "deleting"
    ERROR = "error"
    UNKNOWN = "unknown"


class CloudRunIngress(str, Enum):
    """Ingress settings for a Cloud Run service."""
    ALL = "all"
    INTERNAL = "internal"
    INTERNAL_AND_CLOUD_LOAD_BALANCING = "internal_and_cloud_load_balancing"


class CloudRunCPUAllocation(str, Enum):
    """CPU allocation type for Cloud Run."""
    CPU_ALLOCATION_ALWAYS = "cpu_allocation_always"
    CPU_ALLOCATION_ONLY_DURING_REQUESTS = "cpu_allocation_only_during_requests"


@dataclass(frozen=True)
class CloudRunServiceConfig:
    """Configuration for a Cloud Run service."""
    name: str
    region: str
    image: str
    # Autoscaling
    min_instances: int = 0
    max_instances: int = 100
    # Concurrency
    concurrency: int = 80
    # Resources
    cpu: str = "1"  # e.g., "1", "2", "500m", "250m"
    memory: str = "512Mi"  # e.g., "128Mi", "256Mi", "512Mi", "1Gi", "2Gi"
    # Timeout
    timeout_seconds: int = 300  # 5 minutes default, max 3600
    # Environment
    env_vars: dict[str, str] = field(default_factory=dict)
    # Service account
    service_account: Optional[str] = None
    # VPC connector
    vpc_connector: Optional[str] = None
    # Ingress
    ingress: CloudRunIngress = CloudRunIngress.ALL
    # CPU allocation
    cpu_allocation: CloudRunCPUAllocation = CloudRunCPUAllocation.CPU_ALLOCATION_ALWAYS
    # Labels
    labels: dict[str, str] = field(default_factory=dict)
    # Annotations
    annotations: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        import re
        if not self.name or len(self.name) > 63:
            raise ValueError("service name must be 1-63 characters")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,61}[a-z0-9]", self.name):
            raise ValueError(
                "service name must start with a letter, contain only lowercase letters, "
                "numbers, and hyphens, and end with a letter or number"
            )
        if not self.region:
            raise ValueError("region is required")
        if not self.image:
            raise ValueError("container image is required")
        if self.min_instances < 0:
            raise ValueError("min_instances must be >= 0")
        if self.max_instances < 1:
            raise ValueError("max_instances must be >= 1")
        if self.min_instances > self.max_instances:
            raise ValueError("min_instances must be <= max_instances")
        if self.concurrency < 1 or self.concurrency > 1000:
            raise ValueError("concurrency must be 1-1000")
        if self.timeout_seconds < 1 or self.timeout_seconds > 3600:
            raise ValueError("timeout_seconds must be 1-3600")


@dataclass(frozen=True)
class CloudRunServiceStatus:
    """Runtime status of a Cloud Run service."""
    name: str
    region: str
    status: CloudRunStatus
    url: Optional[str] = None
    ready: bool = False
    # Observed metrics
    active_instances: int = 0
    desired_instances: int = 0
    # Revision info
    latest_revision: Optional[str] = None
    # Error info
    error_message: Optional[str] = None
    # Timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class CloudRunMetrics:
    """Metrics for a Cloud Run service."""
    service_name: str
    region: str
    timestamp: str
    # Instance metrics
    active_instances: int = 0
    idle_instances: int = 0
    # Request metrics
    request_count: int = 0
    request_latency_ms: float = 0.0
    # Concurrency metrics
    average_concurrency: float = 0.0
    # Error metrics
    error_count: int = 0
    error_rate: float = 0.0
    # CPU/Memory utilization
    cpu_utilization: float = 0.0  # 0.0 - 1.0
    memory_utilization: float = 0.0  # 0.0 - 1.0


@dataclass(frozen=True)
class CloudRunScalingRecommendation:
    """A scaling recommendation for a Cloud Run service."""
    service_name: str
    region: str
    current_min_instances: int
    current_max_instances: int
    current_concurrency: int
    recommended_min_instances: int
    recommended_max_instances: int
    recommended_concurrency: int
    reason: str
    confidence: float  # 0.0 - 1.0
    estimated_cost_impact: float  # monthly cost delta in USD
    risk_level: str  # "low", "medium", "high"


@dataclass(frozen=True)
class CloudRunDeployment:
    """A Cloud Run deployment operation result."""
    service_name: str
    region: str
    revision: str
    status: CloudRunStatus
    url: Optional[str] = None
    message: Optional[str] = None
