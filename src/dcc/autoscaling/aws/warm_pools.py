"""Warm pool manager for AWS Auto Scaling.

Provides CRUD operations for warm pools that maintain a pool of pre-initialized
instances ready to be added to the ASG. All operations are advisory and
read-only against the AWS API unless explicitly permitted.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .asg import ASGManager
from .models import (
    HealthStatus,
    Instance,
    InstanceReusePolicy,
    WarmPool,
    WarmPoolState,
)

# Validation
MAX_WARM_POOL_SIZE = 500
MIN_WARM_POOL_SIZE = 0


class WarmPoolError(Exception):
    """Base exception for warm pool operations."""


class WarmPoolNotFoundError(WarmPoolError):
    """Raised when a warm pool is not found."""


class WarmPoolValidationError(WarmPoolError):
    """Raised when warm pool validation fails."""


class WarmPoolManager:
    """Manages AWS warm pools."""

    def __init__(self, asg_manager: ASGManager | None = None) -> None:
        self._pools: dict[str, WarmPool] = {}
        self._asg_manager = asg_manager

    def create(
        self,
        *,
        asg_id: str,
        min_size: int = 0,
        max_group_prepared_capacity: int | None = None,
        instance_reuse_policy: InstanceReusePolicy = InstanceReusePolicy.REUSE,
    ) -> WarmPool:
        """Create a warm pool for an ASG.

        Args:
            asg_id: ASG ID to attach the warm pool to.
            min_size: Minimum number of instances in the warm pool.
            max_group_prepared_capacity: Maximum number of prepared instances.
            instance_reuse_policy: REUSE or RETURN_TO_POOL.

        Returns:
            The created WarmPool.
        """
        self._validate_min_size(min_size)
        if max_group_prepared_capacity is not None:
            self._validate_max_capacity(max_group_prepared_capacity)

        pool_id = self._generate_pool_id(asg_id)
        pool = WarmPool(
            warm_pool_id=pool_id,
            asg_id=asg_id,
            state=WarmPoolState.PENDING,
            min_size=min_size,
            max_group_prepared_capacity=max_group_prepared_capacity,
            instance_reuse_policy=instance_reuse_policy,
        )
        self._pools[pool_id] = pool
        return pool

    def get(self, pool_id: str) -> WarmPool:
        """Get a warm pool by ID.

        Raises:
            WarmPoolNotFoundError: If pool not found.
        """
        pool = self._pools.get(pool_id)
        if pool is None:
            raise WarmPoolNotFoundError(f"Warm pool not found: {pool_id}")
        return pool

    def list_pools(
        self,
        *,
        asg_id: str = "",
        state: WarmPoolState | None = None,
    ) -> list[WarmPool]:
        """List warm pools, optionally filtered."""
        results = list(self._pools.values())
        if asg_id:
            results = [p for p in results if p.asg_id == asg_id]
        if state is not None:
            results = [p for p in results if p.state == state]
        return sorted(results, key=lambda p: p.warm_pool_id)

    def update(
        self,
        pool_id: str,
        *,
        min_size: int | None = None,
        max_group_prepared_capacity: int | None = None,
        instance_reuse_policy: InstanceReusePolicy | None = None,
    ) -> WarmPool:
        """Update a warm pool.

        Returns:
            The updated WarmPool.
        """
        pool = self.get(pool_id)
        if min_size is not None:
            self._validate_min_size(min_size)
            pool.min_size = min_size
        if max_group_prepared_capacity is not None:
            self._validate_max_capacity(max_group_prepared_capacity)
            pool.max_group_prepared_capacity = max_group_prepared_capacity
        if instance_reuse_policy is not None:
            pool.instance_reuse_policy = instance_reuse_policy
        return pool

    def delete(self, pool_id: str) -> bool:
        """Delete a warm pool. Returns True if it existed."""
        return self._pools.pop(pool_id, None) is not None

    def start(self, pool_id: str) -> WarmPool:
        """Start a warm pool."""
        pool = self.get(pool_id)
        pool.state = WarmPoolState.RUNNING
        return pool

    def stop(self, pool_id: str) -> WarmPool:
        """Stop a warm pool."""
        pool = self.get(pool_id)
        pool.state = WarmPoolState.STOPPED
        return pool

    def hibernate(self, pool_id: str) -> WarmPool:
        """Hibernate a warm pool (stop instances but keep state)."""
        pool = self.get(pool_id)
        pool.state = WarmPoolState.HIBERNATED
        return pool

    def add_instance(
        self,
        pool_id: str,
        *,
        instance_id: str,
        availability_zone: str = "",
        health_status: HealthStatus = HealthStatus.HEALTHY,
    ) -> Instance:
        """Add an instance to the warm pool.

        Returns:
            The added Instance.
        """
        pool = self.get(pool_id)
        if pool.max_group_prepared_capacity is not None:
            if len(pool.instances) >= pool.max_group_prepared_capacity:
                raise WarmPoolValidationError(
                    f"Warm pool {pool_id} is at max prepared capacity "
                    f"({pool.max_group_prepared_capacity})"
                )
        if len(pool.instances) >= MAX_WARM_POOL_SIZE:
            raise WarmPoolValidationError(
                f"Warm pool {pool_id} exceeds maximum size ({MAX_WARM_POOL_SIZE})"
            )

        instance = Instance(
            instance_id=instance_id,
            availability_zone=availability_zone,
            health_status=health_status,
        )
        pool.instances.append(instance)
        return instance

    def remove_instance(self, pool_id: str, instance_id: str) -> bool:
        """Remove an instance from the warm pool. Returns True if found."""
        pool = self.get(pool_id)
        for i, inst in enumerate(pool.instances):
            if inst.instance_id == instance_id:
                pool.instances.pop(i)
                return True
        return False

    def get_stats(self, pool_id: str) -> dict[str, Any]:
        """Get statistics for a warm pool."""
        pool = self.get(pool_id)
        healthy = sum(1 for i in pool.instances if i.health_status == HealthStatus.HEALTHY)
        unhealthy = sum(1 for i in pool.instances if i.health_status == HealthStatus.UNHEALTHY)
        return {
            "warm_pool_id": pool_id,
            "asg_id": pool.asg_id,
            "state": pool.state.value,
            "total_instances": len(pool.instances),
            "healthy": healthy,
            "unhealthy": unhealthy,
            "min_size": pool.min_size,
            "max_group_prepared_capacity": pool.max_group_prepared_capacity,
            "instance_reuse_policy": pool.instance_reuse_policy.value,
        }

    # -- Validation helpers --

    def _validate_min_size(self, min_size: int) -> None:
        if not MIN_WARM_POOL_SIZE <= min_size <= MAX_WARM_POOL_SIZE:
            raise WarmPoolValidationError(
                f"min_size must be between {MIN_WARM_POOL_SIZE} and {MAX_WARM_POOL_SIZE}, "
                f"got {min_size}"
            )

    def _validate_max_capacity(self, max_capacity: int) -> None:
        if max_capacity < 0:
            raise WarmPoolValidationError(
                f"max_group_prepared_capacity must be >= 0, got {max_capacity}"
            )
        if max_capacity > MAX_WARM_POOL_SIZE:
            raise WarmPoolValidationError(
                f"max_group_prepared_capacity must be <= {MAX_WARM_POOL_SIZE}, got {max_capacity}"
            )

    def _generate_pool_id(self, asg_id: str) -> str:
        """Generate a deterministic pool ID from ASG ID and timestamp."""
        import hashlib
        ts = datetime.now(timezone.utc).isoformat()
        digest = hashlib.sha256(f"{asg_id}:{ts}".encode()).hexdigest()[:17]
        return f"wp-{digest}"
