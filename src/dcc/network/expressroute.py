"""ExpressRoute automation engine.

Manages Azure ExpressRoute circuits and peering configurations.
Pure stdlib implementation: no external dependencies.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from .models import (
    CloudProvider,
    ExpressRouteCircuit,
    ExpressRoutePeering,
    ExpressRouteState,
    OperationResult,
    validate_asn,
    validate_bandwidth_mbps,
    validate_cidr,
    validate_region,
    validate_resource_id,
    validate_vlan_id,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ExpressRouteError(Exception):
    """Base exception for ExpressRoute errors."""
    pass


class ExpressRouteValidationError(ExpressRouteError):
    """Validation failed for ExpressRoute operation."""
    pass


class ExpressRouteConflictError(ExpressRouteError):
    """ExpressRoute configuration conflict."""
    pass


class ExpressRouteNotFoundError(ExpressRouteError):
    """ExpressRoute circuit not found."""
    pass


class PeeringConfigError(ExpressRouteError):
    """Peering configuration error."""
    pass


# ---------------------------------------------------------------------------
# Request types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ExpressRouteRequest:
    """Request to create an ExpressRoute circuit."""
    tenant_id: str
    service_provider: str = ""
    peering_location: str = ""
    bandwidth_mbps: int = 1000
    sku_tier: str = "Standard"
    sku_family: str = "MeteredData"
    location: str = ""
    name: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExpressRoutePeeringRequest:
    """Request to configure an ExpressRoute peering."""
    circuit_id: str
    tenant_id: str
    peering_type: str = "AzurePrivatePeering"
    peer_asn: int = 65001
    primary_peer_address_prefix: str = ""
    secondary_peer_address_prefix: str = ""
    vlan_id: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ExpressRoute engine
# ---------------------------------------------------------------------------

class ExpressRouteEngine:
    """Engine for managing ExpressRoute circuits and peerings."""

    def __init__(self) -> None:
        self._circuits: dict[str, ExpressRouteCircuit] = {}
        self._peerings: dict[str, ExpressRoutePeering] = {}
        self._listeners: list[Callable[[Any, str], None]] = []

    # -----------------------------------------------------------------------
    # Circuit lifecycle
    # -----------------------------------------------------------------------

    def create_circuit(
        self,
        request: ExpressRouteRequest,
    ) -> OperationResult:
        """Create a new ExpressRoute circuit."""
        try:
            self._validate_circuit_request(request)
        except ExpressRouteValidationError as exc:
            return OperationResult(
                success=False,
                operation="create_circuit",
                resource_id="",
                resource_type="expressroute_circuit",
                message=str(exc),
                error=str(exc),
            )

        circuit_id = f"erc-{uuid.uuid4().hex[:17]}"
        now = datetime.now(timezone.utc).isoformat()

        circuit = ExpressRouteCircuit(
            circuit_id=circuit_id,
            tenant_id=request.tenant_id,
            state=ExpressRouteState.PROVISIONED,
            service_provider=request.service_provider,
            peering_location=request.peering_location,
            bandwidth_mbps=request.bandwidth_mbps,
            sku_tier=request.sku_tier,
            sku_family=request.sku_family,
            location=request.location,
            provider=CloudProvider.AZURE,
            name=request.name,
            tags=request.tags,
            created_at=now,
            metadata=request.metadata,
        )

        self._circuits[circuit_id] = circuit
        self._notify(circuit, "created")

        return OperationResult(
            success=True,
            operation="create_circuit",
            resource_id=circuit_id,
            resource_type="expressroute_circuit",
            message=f"ExpressRoute circuit {circuit_id} created",
            state=circuit.state.value,
            metadata={
                "service_provider": request.service_provider,
                "bandwidth_mbps": request.bandwidth_mbps,
                "peering_location": request.peering_location,
            },
        )

    def modify_circuit(
        self,
        circuit_id: str,
        tenant_id: str,
        **kwargs: Any,
    ) -> OperationResult:
        """Modify an ExpressRoute circuit."""
        circuit = self._circuits.get(circuit_id)
        if not circuit:
            error = f"ExpressRoute circuit {circuit_id} not found"
            return OperationResult(
                success=False,
                operation="modify_circuit",
                resource_id=circuit_id,
                resource_type="expressroute_circuit",
                message=error,
                error=error,
            )

        if circuit.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="modify_circuit",
                resource_id=circuit_id,
                resource_type="expressroute_circuit",
                message=error,
                error=error,
            )

        if "bandwidth_mbps" in kwargs:
            validate_bandwidth_mbps(kwargs["bandwidth_mbps"])
            circuit.bandwidth_mbps = kwargs["bandwidth_mbps"]
        if "sku_tier" in kwargs:
            circuit.sku_tier = kwargs["sku_tier"]
        if "sku_family" in kwargs:
            circuit.sku_family = kwargs["sku_family"]
        if "tags" in kwargs:
            circuit.tags.update(kwargs["tags"])

        self._notify(circuit, "modified")

        return OperationResult(
            success=True,
            operation="modify_circuit",
            resource_id=circuit_id,
            resource_type="expressroute_circuit",
            message=f"ExpressRoute circuit {circuit_id} modified",
            state=circuit.state.value,
        )

    def delete_circuit(
        self,
        circuit_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Delete an ExpressRoute circuit."""
        circuit = self._circuits.get(circuit_id)
        if not circuit:
            error = f"ExpressRoute circuit {circuit_id} not found"
            return OperationResult(
                success=False,
                operation="delete_circuit",
                resource_id=circuit_id,
                resource_type="expressroute_circuit",
                message=error,
                error=error,
            )

        if circuit.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="delete_circuit",
                resource_id=circuit_id,
                resource_type="expressroute_circuit",
                message=error,
                error=error,
            )

        circuit.state = ExpressRouteState.DEPROVISIONED
        del self._circuits[circuit_id]
        self._notify(circuit, "deleted")

        return OperationResult(
            success=True,
            operation="delete_circuit",
            resource_id=circuit_id,
            resource_type="expressroute_circuit",
            message=f"ExpressRoute circuit {circuit_id} deleted",
            state=circuit.state.value,
        )

    # -----------------------------------------------------------------------
    # Peering lifecycle
    # -----------------------------------------------------------------------

    def add_peering(
        self,
        request: ExpressRoutePeeringRequest,
    ) -> OperationResult:
        """Add a peering configuration to an ExpressRoute circuit."""
        try:
            self._validate_peering_request(request)
        except ExpressRouteValidationError as exc:
            return OperationResult(
                success=False,
                operation="add_peering",
                resource_id="",
                resource_type="expressroute_peering",
                message=str(exc),
                error=str(exc),
            )

        circuit = self._circuits.get(request.circuit_id)
        if not circuit:
            error = f"ExpressRoute circuit {request.circuit_id} not found"
            return OperationResult(
                success=False,
                operation="add_peering",
                resource_id="",
                resource_type="expressroute_peering",
                message=error,
                error=error,
            )

        if circuit.tenant_id != request.tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="add_peering",
                resource_id="",
                resource_type="expressroute_peering",
                message=error,
                error=error,
            )

        # Check for duplicate peering type
        for p in circuit.peerings:
            if p.peering_type == request.peering_type and p.state != "deleted":
                error = f"Peering type {request.peering_type} already configured"
                return OperationResult(
                    success=False,
                    operation="add_peering",
                    resource_id=p.peering_id,
                    resource_type="expressroute_peering",
                    message=error,
                    error=error,
                )

        peering_id = f"erp-{uuid.uuid4().hex[:17]}"
        now = datetime.now(timezone.utc).isoformat()

        peering = ExpressRoutePeering(
            peering_id=peering_id,
            circuit_id=request.circuit_id,
            peering_type=request.peering_type,
            peer_asn=request.peer_asn,
            primary_peer_address_prefix=request.primary_peer_address_prefix,
            secondary_peer_address_prefix=request.secondary_peer_address_prefix,
            vlan_id=request.vlan_id,
            state="provisioned",
            metadata=request.metadata,
        )

        self._peerings[peering_id] = peering
        circuit.peerings.append(peering)
        self._notify(peering, "created")

        return OperationResult(
            success=True,
            operation="add_peering",
            resource_id=peering_id,
            resource_type="expressroute_peering",
            message=f"Peering {peering_id} added to circuit {request.circuit_id}",
            state=peering.state,
            metadata={
                "circuit_id": request.circuit_id,
                "peering_type": request.peering_type,
            },
        )

    def remove_peering(
        self,
        peering_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Remove a peering configuration."""
        peering = self._peerings.get(peering_id)
        if not peering:
            error = f"Peering {peering_id} not found"
            return OperationResult(
                success=False,
                operation="remove_peering",
                resource_id=peering_id,
                resource_type="expressroute_peering",
                message=error,
                error=error,
            )

        circuit = self._circuits.get(peering.circuit_id)
        if circuit and circuit.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="remove_peering",
                resource_id=peering_id,
                resource_type="expressroute_peering",
                message=error,
                error=error,
            )

        if circuit:
            circuit.peerings = [p for p in circuit.peerings if p.peering_id != peering_id]

        peering.state = "deleted"
        del self._peerings[peering_id]
        self._notify(peering, "deleted")

        return OperationResult(
            success=True,
            operation="remove_peering",
            resource_id=peering_id,
            resource_type="expressroute_peering",
            message=f"Peering {peering_id} removed",
            state=peering.state,
        )

    # -----------------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------------

    def get_circuit(self, circuit_id: str) -> ExpressRouteCircuit | None:
        """Get an ExpressRoute circuit by ID."""
        return self._circuits.get(circuit_id)

    def list_circuits(
        self,
        tenant_id: str | None = None,
        state: ExpressRouteState | None = None,
    ) -> list[ExpressRouteCircuit]:
        """List ExpressRoute circuits with optional filters."""
        circuits = list(self._circuits.values())
        if tenant_id:
            circuits = [c for c in circuits if c.tenant_id == tenant_id]
        if state:
            circuits = [c for c in circuits if c.state == state]
        return circuits

    def get_peering(self, peering_id: str) -> ExpressRoutePeering | None:
        """Get a peering configuration by ID."""
        return self._peerings.get(peering_id)

    def list_peerings(
        self,
        tenant_id: str | None = None,
        circuit_id: str | None = None,
    ) -> list[ExpressRoutePeering]:
        """List peering configurations with optional filters."""
        peerings = list(self._peerings.values())
        if tenant_id:
            peerings = [p for p in peerings if self._circuit_tenant(p.circuit_id) == tenant_id]
        if circuit_id:
            peerings = [p for p in peerings if p.circuit_id == circuit_id]
        return peerings

    def _circuit_tenant(self, circuit_id: str) -> str | None:
        """Get the tenant ID for a circuit."""
        circuit = self._circuits.get(circuit_id)
        return circuit.tenant_id if circuit else None

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    def _validate_circuit_request(self, request: ExpressRouteRequest) -> None:
        """Validate a circuit creation request."""
        validate_resource_id(request.tenant_id, "t-")
        validate_region(request.location)
        validate_bandwidth_mbps(request.bandwidth_mbps)

        if request.sku_tier not in ("Standard", "Premium", "Local"):
            raise ExpressRouteValidationError(
                "sku_tier must be 'Standard', 'Premium', or 'Local'"
            )
        if request.sku_family not in ("MeteredData", "UnlimitedData"):
            raise ExpressRouteValidationError(
                "sku_family must be 'MeteredData' or 'UnlimitedData'"
            )

    def _validate_peering_request(self, request: ExpressRoutePeeringRequest) -> None:
        """Validate a peering request."""
        validate_resource_id(request.circuit_id, "erc-")
        validate_resource_id(request.tenant_id, "t-")
        validate_asn(request.peer_asn)

        if request.vlan_id:
            validate_vlan_id(request.vlan_id)

        if request.primary_peer_address_prefix:
            validate_cidr(request.primary_peer_address_prefix)
        if request.secondary_peer_address_prefix:
            validate_cidr(request.secondary_peer_address_prefix)

        valid_types = ("AzurePrivatePeering", "AzurePublicPeering", "MicrosoftPeering")
        if request.peering_type not in valid_types:
            raise ExpressRouteValidationError(
                f"peering_type must be one of {valid_types}"
            )

    # -----------------------------------------------------------------------
    # Event listeners
    # -----------------------------------------------------------------------

    def add_listener(self, listener: Callable[[Any, str], None]) -> None:
        """Add an event listener."""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[Any, str], None]) -> None:
        """Remove an event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self, resource: Any, event: str) -> None:
        """Notify all listeners of an event."""
        for listener in self._listeners:
            try:
                listener(resource, event)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_engine: ExpressRouteEngine | None = None


def get_engine() -> ExpressRouteEngine:
    """Return the process-wide default ExpressRoute engine."""
    global _default_engine
    if _default_engine is None:
        _default_engine = ExpressRouteEngine()
    return _default_engine
