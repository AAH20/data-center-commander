"""Auto Scaling Group manager for AWS.

Provides CRUD operations for ASGs with validation, instance management,
and capacity tracking. All operations are advisory and read-only against
the AWS API unless explicitly permitted.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .launch_templates import LaunchTemplateManager
from .models import (
    AutoScalingGroup,
    HealthStatus,
    Instance,
    LaunchTemplateSpecification,
    LifecycleState,
    TerminationPolicy,
)

# Validation
ASG_NAME_RE = re.compile(r"^[A-Za-z0-9._/-]{1,255}$")
AZ_RE = re.compile(r"^[a-z]{2}-[a-z]+-\d[a-z]$")
MAX_INSTANCES_PER_ASG = 500


class ASGError(Exception):
    """Base exception for ASG operations."""


class ASGNotFoundError(ASGError):
    """Raised when an ASG is not found."""


class ASGValidationError(ASGError):
    """Raised when ASG validation fails."""


class ASGManager:
    """Manages AWS Auto Scaling Groups."""

    def __init__(self, template_manager: LaunchTemplateManager | None = None) -> None:
        self._asgs: dict[str, AutoScalingGroup] = {}
        self._template_manager = template_manager or LaunchTemplateManager()

    def create(
        self,
        *,
        name: str,
        min_size: int,
        max_size: int,
        desired_capacity: int | None = None,
        launch_template_id: str | None = None,
        launch_template_version: str = "$Latest",
        default_cooldown: int = 300,
        availability_zones: list[str] | None = None,
        vpc_zone_identifier: list[str] | None = None,
        health_check_type: str = "EC2",
        health_check_grace_period: int = 300,
        termination_policies: list[str] | None = None,
        tags: dict[str, str] | None = None,
        capacity_rebalance: bool = False,
    ) -> AutoScalingGroup:
        """Create a new Auto Scaling Group.

        Args:
            name: ASG name (1-255 chars).
            min_size: Minimum number of instances.
            max_size: Maximum number of instances.
            desired_capacity: Desired number of instances (defaults to min_size).
            launch_template_id: Launch template ID to use.
            launch_template_version: Launch template version.
            default_cooldown: Default cooldown period in seconds.
            availability_zones: List of availability zones.
            vpc_zone_identifier: List of subnet IDs.
            health_check_type: Health check type (EC2 or ELB).
            health_check_grace_period: Health check grace period in seconds.
            termination_policies: Termination policies.
            tags: Resource tags.
            capacity_rebalance: Enable capacity rebalance.

        Returns:
            The created AutoScalingGroup.

        Raises:
            ASGValidationError: If validation fails.
        """
        self._validate_name(name)
        self._validate_capacity(min_size, max_size, desired_capacity)
        self._validate_availability_zones(availability_zones or [])

        if desired_capacity is None:
            desired_capacity = min_size

        template_spec: LaunchTemplateSpecification | None = None
        if launch_template_id:
            template_spec = self._template_manager.get_specification(
                launch_template_id, launch_template_version
            )

        asg_id = self._generate_asg_id(name)
        asg = AutoScalingGroup(
            asg_id=asg_id,
            name=name,
            launch_template=template_spec,
            min_size=min_size,
            max_size=max_size,
            desired_capacity=desired_capacity,
            default_cooldown=default_cooldown,
            availability_zones=list(availability_zones or []),
            vpc_zone_identifier=list(vpc_zone_identifier or []),
            health_check_type=health_check_type,
            health_check_grace_period=health_check_grace_period,
            termination_policies=list(termination_policies or ["Default"]),
            tags=dict(tags or {}),
            capacity_rebalance=capacity_rebalance,
        )
        self._asgs[asg_id] = asg
        return asg

    def get(self, asg_id: str) -> AutoScalingGroup:
        """Get an ASG by ID.

        Raises:
            ASGNotFoundError: If ASG not found.
        """
        asg = self._asgs.get(asg_id)
        if asg is None:
            raise ASGNotFoundError(f"Auto Scaling Group not found: {asg_id}")
        return asg

    def list_asgs(
        self,
        *,
        name_prefix: str = "",
        tags: dict[str, str] | None = None,
    ) -> list[AutoScalingGroup]:
        """List ASGs, optionally filtered by name prefix and tags."""
        results = list(self._asgs.values())
        if name_prefix:
            results = [a for a in results if a.name.startswith(name_prefix)]
        if tags:
            results = [
                a for a in results
                if all(a.tags.get(k) == v for k, v in tags.items())
            ]
        return sorted(results, key=lambda a: a.name)

    def update(
        self,
        asg_id: str,
        *,
        min_size: int | None = None,
        max_size: int | None = None,
        desired_capacity: int | None = None,
        default_cooldown: int | None = None,
        health_check_type: str | None = None,
        health_check_grace_period: int | None = None,
        termination_policies: list[str] | None = None,
        capacity_rebalance: bool | None = None,
    ) -> AutoScalingGroup:
        """Update an ASG's configuration.

        Returns:
            The updated AutoScalingGroup.

        Raises:
            ASGNotFoundError: If ASG not found.
            ASGValidationError: If validation fails.
        """
        asg = self.get(asg_id)

        new_min = min_size if min_size is not None else asg.min_size
        new_max = max_size if max_size is not None else asg.max_size
        new_desired = desired_capacity if desired_capacity is not None else asg.desired_capacity
        self._validate_capacity(new_min, new_max, new_desired)

        asg.min_size = new_min
        asg.max_size = new_max
        asg.desired_capacity = new_desired
        if default_cooldown is not None:
            asg.default_cooldown = default_cooldown
        if health_check_type is not None:
            asg.health_check_type = health_check_type
        if health_check_grace_period is not None:
            asg.health_check_grace_period = health_check_grace_period
        if termination_policies is not None:
            asg.termination_policies = termination_policies
        if capacity_rebalance is not None:
            asg.capacity_rebalance = capacity_rebalance
        return asg

    def delete(self, asg_id: str, *, force: bool = False) -> bool:
        """Delete an ASG. Returns True if it existed.

        Args:
            asg_id: The ASG ID.
            force: If True, delete even with running instances.
        """
        asg = self._asgs.get(asg_id)
        if asg is None:
            return False
        if asg.instances and not force:
            raise ASGValidationError(
                f"ASG {asg_id} has {len(asg.instances)} instances. Use force=True to delete."
            )
        return self._asgs.pop(asg_id, None) is not None

    def attach_instance(
        self,
        asg_id: str,
        *,
        instance_id: str,
        availability_zone: str = "",
        lifecycle_state: LifecycleState = LifecycleState.PENDING,
        health_status: HealthStatus = HealthStatus.UNKNOWN,
        protected_from_scale_in: bool = False,
        weighted_capacity: str = "1",
    ) -> Instance:
        """Attach an instance to an ASG.

        Returns:
            The attached Instance.

        Raises:
            ASGNotFoundError: If ASG not found.
            ASGValidationError: If ASG is at max capacity.
        """
        asg = self.get(asg_id)
        if len(asg.instances) >= asg.max_size:
            raise ASGValidationError(
                f"ASG {asg_id} is at max capacity ({asg.max_size})"
            )
        if len(asg.instances) >= MAX_INSTANCES_PER_ASG:
            raise ASGValidationError(
                f"ASG {asg_id} exceeds maximum instances ({MAX_INSTANCES_PER_ASG})"
            )

        instance = Instance(
            instance_id=instance_id,
            availability_zone=availability_zone,
            lifecycle_state=lifecycle_state,
            health_status=health_status,
            launch_template_id=asg.launch_template.launch_template_id if asg.launch_template else "",
            protected_from_scale_in=protected_from_scale_in,
            weighted_capacity=weighted_capacity,
        )
        asg.instances.append(instance)
        return instance

    def detach_instance(self, asg_id: str, instance_id: str, *, decrement: bool = False) -> bool:
        """Detach an instance from an ASG.

        Args:
            asg_id: The ASG ID.
            instance_id: The instance ID.
            decrement: If True, decrement desired capacity.

        Returns:
            True if the instance was found and detached.
        """
        asg = self.get(asg_id)
        for i, inst in enumerate(asg.instances):
            if inst.instance_id == instance_id:
                asg.instances.pop(i)
                if decrement:
                    asg.desired_capacity = max(asg.min_size, asg.desired_capacity - 1)
                return True
        return False

    def update_instance_state(
        self,
        asg_id: str,
        instance_id: str,
        *,
        lifecycle_state: LifecycleState | None = None,
        health_status: HealthStatus | None = None,
    ) -> Instance:
        """Update an instance's lifecycle state or health status.

        Returns:
            The updated Instance.

        Raises:
            ASGNotFoundError: If ASG not found.
            ASGNotFoundError: If instance not found in ASG.
        """
        asg = self.get(asg_id)
        for inst in asg.instances:
            if inst.instance_id == instance_id:
                if lifecycle_state is not None:
                    inst.lifecycle_state = lifecycle_state
                if health_status is not None:
                    inst.health_status = health_status
                return inst
        raise ASGNotFoundError(f"Instance {instance_id} not found in ASG {asg_id}")

    def set_desired_capacity(self, asg_id: str, desired_capacity: int) -> AutoScalingGroup:
        """Set the desired capacity of an ASG.

        Returns:
            The updated AutoScalingGroup.
        """
        asg = self.get(asg_id)
        if desired_capacity < asg.min_size or desired_capacity > asg.max_size:
            raise ASGValidationError(
                f"Desired capacity {desired_capacity} must be between "
                f"min_size ({asg.min_size}) and max_size ({asg.max_size})"
            )
        asg.desired_capacity = desired_capacity
        return asg

    def suspend_processes(self, asg_id: str, processes: list[str]) -> AutoScalingGroup:
        """Suspend scaling processes for an ASG."""
        asg = self.get(asg_id)
        asg.suspended_processes.extend(p for p in processes if p not in asg.suspended_processes)
        return asg

    def resume_processes(self, asg_id: str, processes: list[str]) -> AutoScalingGroup:
        """Resume scaling processes for an ASG."""
        asg = self.get(asg_id)
        asg.suspended_processes = [p for p in asg.suspended_processes if p not in processes]
        return asg

    def get_instance_health(self, asg_id: str) -> dict[str, Any]:
        """Get health summary for all instances in an ASG."""
        asg = self.get(asg_id)
        healthy = sum(1 for i in asg.instances if i.health_status == HealthStatus.HEALTHY)
        unhealthy = sum(1 for i in asg.instances if i.health_status == HealthStatus.UNHEALTHY)
        unknown = sum(1 for i in asg.instances if i.health_status == HealthStatus.UNKNOWN)
        in_service = sum(1 for i in asg.instances if i.lifecycle_state == LifecycleState.IN_SERVICE)
        return {
            "asg_id": asg_id,
            "total": len(asg.instances),
            "healthy": healthy,
            "unhealthy": unhealthy,
            "unknown": unknown,
            "in_service": in_service,
            "desired_capacity": asg.desired_capacity,
            "utilization": round(asg.utilization, 4),
        }

    # -- Validation helpers --

    def _validate_name(self, name: str) -> None:
        if not name or not ASG_NAME_RE.fullmatch(name):
            raise ASGValidationError(
                f"Invalid ASG name: {name!r}. Must be 1-255 chars, alphanumeric plus . _ / -"
            )

    def _validate_capacity(self, min_size: int, max_size: int, desired: int | None) -> None:
        if min_size < 0:
            raise ASGValidationError(f"min_size must be >= 0, got {min_size}")
        if max_size < min_size:
            raise ASGValidationError(
                f"max_size ({max_size}) must be >= min_size ({min_size})"
            )
        if desired is not None and (desired < min_size or desired > max_size):
            raise ASGValidationError(
                f"desired_capacity ({desired}) must be between "
                f"min_size ({min_size}) and max_size ({max_size})"
            )

    def _validate_availability_zones(self, zones: list[str]) -> None:
        for zone in zones:
            if not AZ_RE.fullmatch(zone):
                raise ASGValidationError(
                    f"Invalid availability zone: {zone!r}. Must match pattern like us-east-1a"
                )

    def _generate_asg_id(self, name: str) -> str:
        """Generate a deterministic ASG ID from name and timestamp."""
        import hashlib
        ts = datetime.now(timezone.utc).isoformat()
        digest = hashlib.sha256(f"{name}:{ts}".encode()).hexdigest()[:17]
        return f"asg-{digest}"
