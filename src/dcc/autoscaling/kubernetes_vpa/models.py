"""Data models for Kubernetes Vertical Pod Autoscaler (VPA) integration.

Models VPA objects, recommendations, update policies, and resource policies
following the Kubernetes VPA API specification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class UpdateMode(str, Enum):
    """VPA update mode for controlling how recommendations are applied."""

    OFF = "Off"
    INITIAL = "Initial"
    AUTO = "Auto"
    RECREATE = "Recreate"


class ContainerScalingMode(str, Enum):
    """Per-container scaling mode."""

    AUTO = "Auto"
    OFF = "Off"


class TargetRefKind(str, Enum):
    """Kind of target workload."""

    DEPLOYMENT = "Deployment"
    STATEFULSET = "StatefulSet"
    DAEMONSET = "DaemonSet"
    REPLICASET = "ReplicaSet"
    REPLICATION_CONTROLLER = "ReplicationController"
    JOB = "Job"
    CRONJOB = "CronJob"


class RecommendationState(str, Enum):
    """State of a V recommendation."""

    PENDING = "Pending"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    FAILED = "Failed"


class ResourceName(str, Enum):
    """Kubernetes resource names."""

    CPU = "cpu"
    MEMORY = "memory"


@dataclass(frozen=True)
class TargetRef:
    """Reference to the target workload for VPA."""

    api_version: str
    kind: TargetRefKind
    name: str


@dataclass(frozen=True)
class CrossVersionObjectReference:
    """Cross-version object reference for VPA target."""

    api_version: str
    kind: str
    name: str


@dataclass
class ResourcePolicy:
    """Per-container resource policy for VPA."""

    container_name: str
    mode: ContainerScalingMode = ContainerScalingMode.AUTO
    min_allowed_cpu_millicores: Optional[int] = None
    min_allowed_memory_mb: Optional[int] = None
    max_allowed_cpu_millicores: Optional[int] = None
    max_allowed_memory_mb: Optional[int] = None
    controlled_resources: list[str] = field(default_factory=lambda: ["cpu", "memory"])
    controlled_values: str = "RequestsAndLimits"


@dataclass
class PodResourcePolicy:
    """Pod-level resource policy containing per-container policies."""

    container_policies: list[ResourcePolicy] = field(default_factory=list)


@dataclass
class UpdatePolicy:
    """VPA update policy configuration."""

    update_mode: UpdateMode = UpdateMode.OFF
    min_replicas: int = 2


@dataclass
class VPAObject:
    """Represents a VerticalPodAutoscaler custom resource."""

    name: str
    namespace: str
    target_ref: CrossVersionObjectReference
    update_policy: UpdatePolicy = field(default_factory=UpdatePolicy)
    resource_policy: Optional[PodResourcePolicy] = None
    min_replicas: int = 2
    max_replicas: Optional[int] = None
    recommendation: Optional["VPARecommendation"] = None
    conditions: list["VPACondition"] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)


@dataclass
class ResourceQuantity:
    """A resource quantity with value and format."""

    name: str
    quantity: str
    millicores: Optional[int] = None
    megabytes: Optional[int] = None


@dataclass
class RecommendedContainerResources:
    """Recommended resources for a single container."""

    container_name: str
    target: dict[str, ResourceQuantity] = field(default_factory=dict)
    lower_bound: dict[str, ResourceQuantity] = field(default_factory=dict)
    upper_bound: dict[str, ResourceQuantity] = field(default_factory=dict)
    uncapped_target: dict[str, ResourceQuantity] = field(default_factory=dict)


@dataclass
class VPARecommendation:
    """VPA recommendation for pod resource requests."""

    container_recommendations: list[RecommendedContainerResources] = field(
        default_factory=list
    )
    state: RecommendationState = RecommendationState.PENDING
    last_update_time: Optional[str] = None


@dataclass
class VPACondition:
    """Condition of a VPA object."""

    type: str
    status: str
    last_transition_time: Optional[str] = None
    reason: Optional[str] = None
    message: Optional[str] = None


@dataclass
class ContainerUsageSample:
    """A single usage sample for a container."""

    container_name: str
    cpu_usage_millicores: float
    memory_usage_mb: float
    timestamp: str


@dataclass
class PodUsageRecord:
    """Aggregated usage record for a pod."""

    pod_name: str
    namespace: str
    samples: list[ContainerUsageSample] = field(default_factory=list)


@dataclass
class VPAMetricsSummary:
    """Summary of VPA metrics for a workload."""

    workload_name: str
    namespace: str
    container_count: int
    avg_cpu_millicores: float
    avg_memory_mb: float
    p95_cpu_millicores: float
    p95_memory_mb: float
    p99_cpu_millicores: float
    p99_memory_mb: float
    sample_count: int
    time_window_hours: float


@dataclass
class ScalingDecision:
    """A scaling decision derived from VPA recommendations."""

    workload_name: str
    namespace: str
    container_name: str
    current_cpu_millicores: int
    current_memory_mb: int
    recommended_cpu_millicores: int
    recommended_memory_mb: int
    cpu_change_percent: float
    memory_change_percent: float
    action: str  # "scale_up", "scale_down", "no_change"
    reason: str
    confidence: float  # 0.0 - 1.0


@dataclass
class VPAReport:
    """Comprehensive VPA report for a set of workloads."""

    generated_at: str
    total_workloads: int
    total_recommendations: int
    scale_up_count: int
    scale_down_count: int
    no_change_count: int
    decisions: list[ScalingDecision] = field(default_factory=list)
    vpa_objects: list[VPAObject] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
