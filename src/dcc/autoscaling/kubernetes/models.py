"""Data models for Kubernetes HPA integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ScalingMetricType(str, Enum):
    """Types of metrics used for scaling."""
    CPU = "cpu"
    MEMORY = "memory"
    CUSTOM = "custom"
    EXTERNAL = "external"
    QUEUE_DEPTH = "queue_depth"
    REQUESTS_PER_SECOND = "requests_per_second"
    LATENCY = "latency"


class ScalingPolicy(str, Enum):
    """Scaling policy types."""
    TARGET_AVERAGE = "target_average"
    TARGET_VALUE = "target_value"
    PERCENTAGE = "percentage"


class ScalingDirection(str, Enum):
    """Direction of scaling."""
    UP = "up"
    DOWN = "down"


class HPATargetKind(str, Enum):
    """Kubernetes resource kinds that can be targeted by HPA."""
    DEPLOYMENT = "Deployment"
    STATEFULSET = "StatefulSet"
    REPLICASET = "ReplicaSet"
    DAEMONSET = "DaemonSet"


class ScalingStatus(str, Enum):
    """Status of a scaling operation."""
    PENDING = "pending"
    SCALING = "scaling"
    STABLE = "stable"
    FAILED = "failed"
    COOLDOWN = "cooldown"


class MetricSource(str, Enum):
    """Source of metrics."""
    PROMETHEUS = "prometheus"
    DATADOG = "datadog"
    CLOUDWATCH = "cloudwatch"
    STACKDRIVER = "stackdriver"
    CUSTOM_API = "custom_api"
    KUBERNETES_METRICS = "kubernetes_metrics"


@dataclass
class ScalingMetric:
    """A metric used for autoscaling decisions."""
    name: str
    metric_type: ScalingMetricType
    source: MetricSource
    target_value: float
    target_average: bool = True
    current_value: Optional[float] = None
    unit: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_above_target(self) -> bool:
        """Check if current value is above target."""
        if self.current_value is None:
            return False
        return self.current_value > self.target_value

    @property
    def utilization_percentage(self) -> Optional[float]:
        """Calculate utilization percentage."""
        if self.current_value is None or self.target_value == 0:
            return None
        return (self.current_value / self.target_value) * 100


@dataclass
class ScalingPolicyConfig:
    """Configuration for a scaling policy."""
    policy_type: ScalingPolicy
    direction: ScalingDirection
    value: float
    # Cooldown periods in seconds
    scale_up_cooldown: int = 60
    scale_down_cooldown: int = 300
    # Step limits
    max_step_up: int = 10
    max_step_down: int = 3
    # Stabilization window in seconds
    stabilization_window: int = 300


@dataclass
class HPATarget:
    """Target resource for horizontal pod autoscaling."""
    name: str
    kind: HPATargetKind
    namespace: str
    cluster: str = "default"
    current_replicas: int = 1
    min_replicas: int = 1
    max_replicas: int = 10
    # Resource requests/limits
    cpu_request: Optional[str] = None
    memory_request: Optional[str] = None
    # Labels and annotations
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HPAConfiguration:
    """Complete HPA configuration for a target."""
    target: HPATarget
    metrics: list[ScalingMetric] = field(default_factory=list)
    policies: list[ScalingPolicyConfig] = field(default_factory=list)
    # Behavior
    scale_up_behavior: Optional[ScalingPolicyConfig] = None
    scale_down_behavior: Optional[ScalingPolicyConfig] = None
    # Status
    status: ScalingStatus = ScalingStatus.STABLE
    last_scale_time: Optional[datetime] = None
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScalingRecommendation:
    """A scaling recommendation."""
    target: HPATarget
    current_replicas: int
    recommended_replicas: int
    reason: str
    confidence: float = 0.0  # 0.0 to 1.0
    metrics: list[ScalingMetric] = field(default_factory=list)
    # Risk assessment
    risk_level: str = "low"  # low, medium, high
    # Actions
    actions: list[str] = field(default_factory=list)
    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScalingEvent:
    """A scaling event record."""
    event_id: str
    target: HPATarget
    timestamp: datetime
    direction: ScalingDirection
    from_replicas: int
    to_replicas: int
    reason: str
    metrics: list[ScalingMetric] = field(default_factory=list)
    status: ScalingStatus = ScalingStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AutoscalingReport:
    """Complete autoscaling analysis report."""
    generated_at: str = ""
    # Summary
    total_targets: int = 0
    total_hpas: int = 0
    active_hpas: int = 0
    # Recommendations
    scaling_recommendations: list[ScalingRecommendation] = field(default_factory=list)
    # Events
    scaling_events: list[ScalingEvent] = field(default_factory=list)
    # Metrics
    metrics_summary: dict[str, Any] = field(default_factory=dict)
    # Cost
    estimated_monthly_cost: float = 0.0
    potential_savings: float = 0.0
    # Risk
    risk_summary: dict[str, int] = field(default_factory=dict)
    # Recommendations
    quick_wins: list[str] = field(default_factory=list)
    long_term_recommendations: list[str] = field(default_factory=list)
