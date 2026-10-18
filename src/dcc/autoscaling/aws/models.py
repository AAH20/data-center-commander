"""Data models for AWS Auto Scaling integration.

Defines the types used throughout the autoscaling engine: launch templates,
auto scaling groups, scaling policies, lifecycle hooks, and warm pools.
All models are serialisable dataclasses so they can be persisted, exported,
and audited.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class HealthStatus(str, Enum):
    """Health status of an instance or resource."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ScalingPolicyType(str, Enum):
    """Type of scaling policy."""
    TARGET_TRACKING = "target_tracking"
    STEP_SCALING = "step_scaling"
    SIMPLE_SCALING = "simple_scaling"
    PREDICTIVE = "predictive"


class ScalingMetricType(str, Enum):
    """Metric type for scaling policies."""
    AVG_CPU_UTILIZATION = "avg_cpu_utilization"
    AVG_NETWORK_IN = "avg_network_in"
    AVG_NETWORK_OUT = "avg_network_out"
    ALB_REQUEST_COUNT_PER_TARGET = "alb_request_count_per_target"
    CUSTOM = "custom"


class LifecycleState(str, Enum):
    """Lifecycle state of an instance in an ASG."""
    PENDING = "pending"
    PENDING_WAIT = "pending_wait"
    PENDING_PROCEED = "pending_proceed"
    QUARANTINED = "quarantined"
    IN_SERVICE = "in_service"
    TERMINATING = "terminating"
    TERMINATING_WAIT = "terminating_wait"
    TERMINATING_PROCEED = "terminating_proceed"
    TERMINATED = "terminated"
    DETACHED = "detached"
    ENTERING_STANDBY = "entering_standby"
    STANDBY = "standby"


class LifecycleTransition(str, Enum):
    """Lifecycle transition type."""
    LAUNCH = "launch"
    TERMINATE = "terminate"


class WarmPoolState(str, Enum):
    """State of a warm pool."""
    RUNNING = "running"
    HIBERNATED = "hiberinated"
    STOPPED = "stopped"
    PENDING = "pending"
    DELETED = "deleted"


class InstanceReusePolicy(str, Enum):
    """Instance reuse policy for warm pools."""
    REUSE = "reuse"
    RETURN_TO_POOL = "return_to_pool"


class TerminationPolicy(str, Enum):
    """Default termination policy for ASG."""
    OLDEST_LAUNCH_TEMPLATE = "OldestLaunchTemplate"
    OLDEST_LAUNCH_CONFIGURATION = "OldestLaunchConfiguration"
    NEWEST_LAUNCH_TEMPLATE = "NewestLaunchTemplate"
    NEWEST_LAUNCH_CONFIGURATION = "NewestLaunchConfiguration"
    OLDEST_INSTANCE = "OldestInstance"
    NEWEST_INSTANCE = "NewestInstance"
    CLOSEST_TO_NEXT_HOUR = "ClosestToNextInstanceHour"
    DEFAULT = "Default"


class CapacityRebalanceStrategy(str, Enum):
    """Capacity rebalance strategy."""
    ENABLED = "enabled"
    DISABLED = "disabled"


# ---------------------------------------------------------------------------
# Launch Template
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LaunchTemplateSpecification:
    """Reference to a launch template."""
    launch_template_id: str
    version: str = "$Latest"

    def to_dict(self) -> dict[str, Any]:
        return {
            "launch_template_id": self.launch_template_id,
            "version": self.version,
        }


@dataclass
class LaunchTemplate:
    """An AWS launch template configuration."""
    launch_template_id: str
    name: str
    version: int = 1
    image_id: str = ""
    instance_type: str = ""
    key_name: str = ""
    security_group_ids: list[str] = field(default_factory=list)
    user_data: str = ""
    iam_instance_profile: str = ""
    block_device_mappings: list[dict[str, Any]] = field(default_factory=list)
    network_interfaces: list[dict[str, Any]] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    metadata_options: dict[str, Any] = field(default_factory=dict)
    monitoring_enabled: bool = False
    ebs_optimized: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "launch_template_id": self.launch_template_id,
            "name": self.name,
            "version": self.version,
            "image_id": self.image_id,
            "instance_type": self.instance_type,
            "key_name": self.key_name,
            "security_group_ids": list(self.security_group_ids),
            "user_data": self.user_data,
            "iam_instance_profile": self.iam_instance_profile,
            "block_device_mappings": list(self.block_device_mappings),
            "network_interfaces": list(self.network_interfaces),
            "tags": dict(self.tags),
            "metadata_options": dict(self.metadata_options),
            "monitoring_enabled": self.monitoring_enabled,
            "ebs_optimized": self.ebs_optimized,
            "created_at": self.created_at.isoformat(),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LaunchTemplate:
        return cls(
            launch_template_id=data["launch_template_id"],
            name=data["name"],
            version=data.get("version", 1),
            image_id=data.get("image_id", ""),
            instance_type=data.get("instance_type", ""),
            key_name=data.get("key_name", ""),
            security_group_ids=list(data.get("security_group_ids", [])),
            user_data=data.get("user_data", ""),
            iam_instance_profile=data.get("iam_instance_profile", ""),
            block_device_mappings=list(data.get("block_device_mappings", [])),
            network_interfaces=list(data.get("network_interfaces", [])),
            tags=dict(data.get("tags", {})),
            metadata_options=dict(data.get("metadata_options", {})),
            monitoring_enabled=data.get("monitoring_enabled", False),
            ebs_optimized=data.get("ebs_optimized", False),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else datetime.now(timezone.utc)
            ),
            description=data.get("description", ""),
        )


# ---------------------------------------------------------------------------
# Auto Scaling Group
# ---------------------------------------------------------------------------


@dataclass
class AutoScalingGroup:
    """An AWS Auto Scaling Group."""
    asg_id: str
    name: str
    launch_template: LaunchTemplateSpecification | None = None
    min_size: int = 0
    max_size: int = 0
    desired_capacity: int = 0
    default_cooldown: int = 300
    availability_zones: list[str] = field(default_factory=list)
    vpc_zone_identifier: list[str] = field(default_factory=list)
    health_check_type: str = "EC2"
    health_check_grace_period: int = 300
    termination_policies: list[str] = field(default_factory=lambda: ["Default"])
    tags: dict[str, str] = field(default_factory=dict)
    capacity_rebalance: bool = False
    instances: list[Instance] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    suspended_processes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def instance_count(self) -> int:
        return len(self.instances)

    @property
    def healthy_count(self) -> int:
        return sum(1 for i in self.instances if i.health_status == HealthStatus.HEALTHY)

    @property
    def utilization(self) -> float:
        if self.desired_capacity <= 0:
            return 0.0
        return self.instance_count / self.desired_capacity

    def to_dict(self) -> dict[str, Any]:
        return {
            "asg_id": self.asg_id,
            "name": self.name,
            "launch_template": self.launch_template.to_dict() if self.launch_template else None,
            "min_size": self.min_size,
            "max_size": self.max_size,
            "desired_capacity": self.desired_capacity,
            "default_cooldown": self.default_cooldown,
            "availability_zones": list(self.availability_zones),
            "vpc_zone_identifier": list(self.vpc_zone_identifier),
            "health_check_type": self.health_check_type,
            "health_check_grace_period": self.health_check_grace_period,
            "termination_policies": list(self.termination_policies),
            "tags": dict(self.tags),
            "capacity_rebalance": self.capacity_rebalance,
            "instances": [i.to_dict() for i in self.instances],
            "created_at": self.created_at.isoformat(),
            "suspended_processes": list(self.suspended_processes),
            "metadata": dict(self.metadata),
            "instance_count": self.instance_count,
            "healthy_count": self.healthy_count,
            "utilization": round(self.utilization, 4),
        }


@dataclass
class Instance:
    """An EC2 instance within an ASG."""
    instance_id: str
    availability_zone: str = ""
    lifecycle_state: LifecycleState = LifecycleState.PENDING
    health_status: HealthStatus = HealthStatus.UNKNOWN
    launch_template_id: str = ""
    protected_from_scale_in: bool = False
    weighted_capacity: str = "1"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "availability_zone": self.availability_zone,
            "lifecycle_state": self.lifecycle_state.value,
            "health_status": self.health_status.value,
            "launch_template_id": self.launch_template_id,
            "protected_from_scale_in": self.protected_from_scale_in,
            "weighted_capacity": self.weighted_capacity,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Scaling Policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepAdjustment:
    """A step adjustment for step scaling policies."""
    metric_interval_lower_bound: float | None = None
    metric_interval_upper_bound: float | None = None
    scaling_adjustment: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_interval_lower_bound": self.metric_interval_lower_bound,
            "metric_interval_upper_bound": self.metric_interval_upper_bound,
            "scaling_adjustment": self.scaling_adjustment,
        }


@dataclass
class ScalingPolicy:
    """An AWS scaling policy."""
    policy_id: str
    name: str
    asg_id: str
    policy_type: ScalingPolicyType
    metric_type: ScalingMetricType = ScalingMetricType.AVG_CPU_UTILIZATION
    target_value: float | None = None
    step_adjustments: list[StepAdjustment] = field(default_factory=list)
    cooldown: int = 300
    min_adjustment_magnitude: int = 1
    estimated_instance_warmup: int = 300
    predictive_scaling_mode: str = "ForecastAndScale"
    tags: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "asg_id": self.asg_id,
            "policy_type": self.policy_type.value,
            "metric_type": self.metric_type.value,
            "target_value": self.target_value,
            "step_adjustments": [sa.to_dict() for sa in self.step_adjustments],
            "cooldown": self.cooldown,
            "min_adjustment_magnitude": self.min_adjustment_magnitude,
            "estimated_instance_warmup": self.estimated_instance_warmup,
            "predictive_scaling_mode": self.predictive_scaling_mode,
            "tags": dict(self.tags),
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Lifecycle Hook
# ---------------------------------------------------------------------------


@dataclass
class LifecycleHook:
    """An AWS lifecycle hook."""
    hook_id: str
    name: str
    asg_id: str
    lifecycle_transition: LifecycleTransition
    heartbeat_timeout: int = 3600
    default_result: str = "ABANDON"
    notification_target_arn: str = ""
    role_arn: str = ""
    notification_metadata: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hook_id": self.hook_id,
            "name": self.name,
            "asg_id": self.asg_id,
            "lifecycle_transition": self.lifecycle_transition.value,
            "heartbeat_timeout": self.heartbeat_timeout,
            "default_result": self.default_result,
            "notification_target_arn": self.notification_target_arn,
            "role_arn": self.role_arn,
            "notification_metadata": self.notification_metadata,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Warm Pool
# ---------------------------------------------------------------------------


@dataclass
class WarmPool:
    """An AWS warm pool configuration."""
    warm_pool_id: str
    asg_id: str
    state: WarmPoolState = WarmPoolState.PENDING
    min_size: int = 0
    max_group_prepared_capacity: int | None = None
    instance_reuse_policy: InstanceReusePolicy = InstanceReusePolicy.REUSE
    instances: list[Instance] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def instance_count(self) -> int:
        return len(self.instances)

    @property
    def healthy_count(self) -> int:
        return sum(1 for i in self.instances if i.health_status == HealthStatus.HEALTHY)

    def to_dict(self) -> dict[str, Any]:
        return {
            "warm_pool_id": self.warm_pool_id,
            "asg_id": self.asg_id,
            "state": self.state.value,
            "min_size": self.min_size,
            "max_group_prepared_capacity": self.max_group_prepared_capacity,
            "instance_reuse_policy": self.instance_reuse_policy.value,
            "instances": [i.to_dict() for i in self.instances],
            "metadata": dict(self.metadata),
            "instance_count": self.instance_count,
            "healthy_count": self.healthy_count,
        }


# ---------------------------------------------------------------------------
# Scaling Activity
# ---------------------------------------------------------------------------


@dataclass
class ScalingActivity:
    """A scaling activity record."""
    activity_id: str
    asg_id: str
    description: str
    cause: str
    start_time: datetime
    end_time: datetime | None = None
    status_code: str = "Pending"
    progress: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "asg_id": self.asg_id,
            "description": self.description,
            "cause": self.cause,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status_code": self.status_code,
            "progress": self.progress,
            "details": dict(self.details),
            "duration_seconds": round(self.duration_seconds, 3),
        }


# ---------------------------------------------------------------------------
# Scaling Recommendation
# ---------------------------------------------------------------------------


@dataclass
class ScalingRecommendation:
    """An advisory scaling recommendation."""
    recommendation_id: UUID = field(default_factory=uuid4)
    asg_id: str = ""
    action: str = ""  # "scale_out", "scale_in", "no_action"
    current_capacity: int = 0
    recommended_capacity: int = 0
    reason: str = ""
    confidence: float = 0.0
    estimated_cost_impact: float = 0.0
    risk_level: str = "low"
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    provenance: dict[str, Any] = field(default_factory=dict)
    execution_permitted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": str(self.recommendation_id),
            "asg_id": self.asg_id,
            "action": self.action,
            "current_capacity": self.current_capacity,
            "recommended_capacity": self.recommended_capacity,
            "reason": self.reason,
            "confidence": round(self.confidence, 4),
            "estimated_cost_impact": round(self.estimated_cost_impact, 4),
            "risk_level": self.risk_level,
            "generated_at": self.generated_at.isoformat(),
            "provenance": self.provenance,
            "execution_permitted": self.execution_permitted,
        }
