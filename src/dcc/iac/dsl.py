"""IaC DSL: declarative infrastructure definition.

Python-native, type-safe infrastructure definition that surpasses Terraform HCL
with compile-time validation, deterministic fingerprints, and real-time drift detection.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ValidationError(ValueError):
    """Raised when infrastructure definition is invalid."""

    pass


class ResourceType(StrEnum):
    """Supported infrastructure resource types."""

    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    COOLING = "cooling"
    POWER = "power"


@dataclass(frozen=True, slots=True)
class Resource:
    """A single infrastructure resource."""

    name: str
    resource_type: ResourceType
    region: str
    cpu_cores: float = 0.0
    memory_gb: float = 0.0
    gpu_units: float = 0.0
    storage_tb: float = 0.0
    bandwidth_gbps: float = 0.0
    cooling_kw: float = 0.0
    power_kw: float = 0.0
    power_capacity_kw: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate resource after creation."""
        if not self.name or not self.name.strip():
            raise ValidationError("resource name must not be empty")
        if not self.region or not self.region.strip():
            raise ValidationError("resource region must not be empty")
        if self.cpu_cores < 0:
            raise ValidationError("cpu_cores must be non-negative")
        if self.memory_gb < 0:
            raise ValidationError("memory_gb must be non-negative")
        if self.gpu_units < 0:
            raise ValidationError("gpu_units must be non-negative")
        if self.storage_tb < 0:
            raise ValidationError("storage_tb must be non-negative")
        if self.bandwidth_gbps < 0:
            raise ValidationError("bandwidth_gbps must be non-negative")
        if self.cooling_kw < 0:
            raise ValidationError("cooling_kw must be non-negative")
        if self.power_kw < 0:
            raise ValidationError("power_kw must be non-negative")
        if self.power_capacity_kw < 0:
            raise ValidationError("power_capacity_kw must be non-negative")

    @property
    def fingerprint(self) -> str:
        """Deterministic fingerprint for drift detection."""
        data = json.dumps(
            {
                "name": self.name,
                "type": self.resource_type.value,
                "region": self.region,
                "cpu_cores": self.cpu_cores,
                "memory_gb": self.memory_gb,
                "gpu_units": self.gpu_units,
                "storage_tb": self.storage_tb,
                "bandwidth_gbps": self.bandwidth_gbps,
                "cooling_kw": self.cooling_kw,
                "power_kw": self.power_kw,
                "power_capacity_kw": self.power_capacity_kw,
                "metadata": self.metadata,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass(slots=True)
class InfrastructureDefinition:
    """A complete infrastructure definition for a tenant."""

    name: str
    region: str
    resources: list[Resource] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate infrastructure definition."""
        if not self.name or not self.name.strip():
            raise ValidationError("tenant name must not be empty")
        if not self.region or not self.region.strip():
            raise ValidationError("tenant region must not be empty")

    @property
    def total_cpu_cores(self) -> float:
        """Total CPU cores across all compute resources."""
        return sum(r.cpu_cores for r in self.resources)

    @property
    def total_memory_gb(self) -> float:
        """Total memory across all compute resources."""
        return sum(r.memory_gb for r in self.resources)

    @property
    def total_gpu_units(self) -> float:
        """Total GPU units across all compute resources."""
        return sum(r.gpu_units for r in self.resources)

    @property
    def total_storage_tb(self) -> float:
        """Total storage across all storage resources."""
        return sum(r.storage_tb for r in self.resources)

    @property
    def total_bandwidth_gbps(self) -> float:
        """Total bandwidth across all network resources."""
        return sum(r.bandwidth_gbps for r in self.resources)

    @property
    def total_cooling_kw(self) -> float:
        """Total cooling capacity across all cooling resources."""
        return sum(r.cooling_kw for r in self.resources)

    @property
    def total_power_kw(self) -> float:
        """Total power capacity across all power resources."""
        return sum(r.power_capacity_kw for r in self.resources)

    @property
    def fingerprint(self) -> str:
        """Deterministic fingerprint for the entire infrastructure."""
        resource_fingerprints = sorted(r.fingerprint for r in self.resources)
        data = json.dumps(
            {
                "name": self.name,
                "region": self.region,
                "resources": resource_fingerprints,
                "metadata": self.metadata,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(data.encode()).hexdigest()

    def has_drift(self, actual: InfrastructureDefinition) -> bool:
        """Check if actual state differs from desired state."""
        return self.fingerprint != actual.fingerprint

    def drift_details(self, actual: InfrastructureDefinition) -> dict[str, Any]:
        """Get detailed drift information."""
        desired_resources = {r.name: r for r in self.resources}
        actual_resources = {r.name: r for r in actual.resources}

        added = set(actual_resources) - set(desired_resources)
        removed = set(desired_resources) - set(actual_resources)
        changed = {
            name
            for name in set(desired_resources) & set(actual_resources)
            if desired_resources[name].fingerprint != actual_resources[name].fingerprint
        }

        return {
            "added": sorted(added),
            "removed": sorted(removed),
            "changed": sorted(changed),
            "desired_fingerprint": self.fingerprint,
            "actual_fingerprint": actual.fingerprint,
        }


def define_resource(
    name: str,
    resource_type: ResourceType | str,
    region: str,
    cpu_cores: float = 0.0,
    memory_gb: float = 0.0,
    gpu_units: float = 0.0,
    storage_tb: float = 0.0,
    bandwidth_gbps: float = 0.0,
    cooling_kw: float = 0.0,
    power_kw: float = 0.0,
    power_capacity_kw: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> Resource:
    """Define a single infrastructure resource.

    Args:
        name: Unique resource name
        resource_type: Type of resource (compute, storage, network, cooling, power)
        region: Deployment region
        cpu_cores: CPU cores (for compute resources)
        memory_gb: Memory in GB (for compute resources)
        gpu_units: GPU units (for compute resources)
        storage_tb: Storage in TB (for storage resources)
        bandwidth_gbps: Bandwidth in Gbps (for network resources)
        cooling_kw: Cooling capacity in kW (for cooling resources)
        power_kw: Power consumption in kW (for compute resources)
        power_capacity_kw: Power capacity in kW (for power resources)
        metadata: Additional metadata

    Returns:
        Validated Resource instance

    Raises:
        ValidationError: If resource definition is invalid
    """
    if isinstance(resource_type, str):
        try:
            resource_type = ResourceType(resource_type)
        except ValueError as exc:
            raise ValidationError(f"invalid resource type: {resource_type}") from exc

    return Resource(
        name=name,
        resource_type=resource_type,
        region=region,
        cpu_cores=cpu_cores,
        memory_gb=memory_gb,
        gpu_units=gpu_units,
        storage_tb=storage_tb,
        bandwidth_gbps=bandwidth_gbps,
        cooling_kw=cooling_kw,
        power_kw=power_kw,
        power_capacity_kw=power_capacity_kw,
        metadata=metadata or {},
    )


def define_tenant(
    name: str,
    region: str,
    resources: list[Resource] | None = None,
    metadata: dict[str, Any] | None = None,
) -> InfrastructureDefinition:
    """Define a complete tenant infrastructure.

    Args:
        name: Tenant name
        region: Primary deployment region
        resources: List of resources
        metadata: Additional metadata

    Returns:
        Validated InfrastructureDefinition instance

    Raises:
        ValidationError: If tenant definition is invalid
    """
    return InfrastructureDefinition(
        name=name,
        region=region,
        resources=resources or [],
        metadata=metadata or {},
    )
