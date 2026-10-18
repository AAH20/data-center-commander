"""VPC peering automation engine.

Manages VPC peering connections across AWS, Azure, and GCP.
Pure stdlib implementation: no external dependencies.
"""
from __future__ import annotations

import ipaddress
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from .models import (
    CloudProvider,
    OperationResult,
    PeeringState,
    ValidationResult,
    VPC,
    VPCPeeringConnection,
    VPCCidrBlock,
    validate_cidr,
    validate_region,
    validate_resource_id,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class PeeringError(Exception):
    """Base exception for VPC peering errors."""
    pass


class PeeringValidationError(PeeringError):
    """Validation failed for peering operation."""
    pass


class PeeringConflictError(PeeringError):
    """Peering connection conflicts with existing configuration."""
    pass


class PeeringNotFoundError(PeeringError):
    """Peering connection not found."""
    pass


class CidrOverlapError(PeeringError):
    """CIDR blocks overlap between peered VPCs."""
    pass


# ---------------------------------------------------------------------------
# CIDR overlap detection
# ---------------------------------------------------------------------------

def check_cidr_overlap(cidr1: str, cidr2: str) -> bool:
    """Check if two CIDR blocks overlap."""
    net1 = ipaddress.ip_network(cidr1, strict=False)
    net2 = ipaddress.ip_network(cidr2, strict=False)
    return net1.overlaps(net2)


def find_cidr_overlaps(
    cidrs1: Sequence[str],
    cidrs2: Sequence[str],
) -> list[tuple[str, str]]:
    """Find all overlapping CIDR pairs between two lists."""
    overlaps: list[tuple[str, str]] = []
    for c1 in cidrs1:
        for c2 in cidrs2:
            if check_cidr_overlap(c1, c2):
                overlaps.append((c1, c2))
    return overlaps


# ---------------------------------------------------------------------------
# Peering engine
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PeeringRequest:
    """Request to create a VPC peering connection."""
    requester_vpc_id: str
    accepter_vpc_id: str
    tenant_id: str
    name: str = ""
    requester_cidr: str = ""
    accepter_cidr: str = ""
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    tags: dict[str, str] = field(default_factory=dict)
    auto_accept: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PeeringAcceptance:
    """Acceptance of a pending peering connection."""
    peering_id: str
    tenant_id: str
    accepter_vpc_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


class VPCPeeringEngine:
    """Engine for managing VPC peering connections."""

    def __init__(self) -> None:
        self._peerings: dict[str, VPCPeeringConnection] = {}
        self._vpcs: dict[str, VPC] = {}
        self._listeners: list[Callable[[VPCPeeringConnection, str], None]] = []

    # -----------------------------------------------------------------------
    # VPC management
    # -----------------------------------------------------------------------

    def register_vpc(self, vpc: VPC) -> None:
        """Register a VPC for peering operations."""
        self._vpcs[vpc.vpc_id] = vpc

    def get_vpc(self, vpc_id: str) -> VPC | None:
        """Get a registered VPC by ID."""
        return self._vpcs.get(vpc_id)

    def list_vpcs(self, tenant_id: str | None = None) -> list[VPC]:
        """List registered VPCs, optionally filtered by tenant."""
        vpcs = list(self._vpcs.values())
        if tenant_id:
            vpcs = [v for v in vpcs if v.tenant_id == tenant_id]
        return vpcs

    # -----------------------------------------------------------------------
    # Peering lifecycle
    # -----------------------------------------------------------------------

    def create_peering(
        self,
        request: PeeringRequest,
    ) -> OperationResult:
        """Create a new VPC peering connection."""
        try:
            self._validate_peering_request(request)
        except PeeringValidationError as exc:
            return OperationResult(
                success=False,
                operation="create_peering",
                resource_id="",
                resource_type="vpc_peering",
                message=str(exc),
                error=str(exc),
            )

        # Check for CIDR overlaps
        requester_vpc = self._vpcs.get(request.requester_vpc_id)
        accepter_vpc = self._vpcs.get(request.accepter_vpc_id)

        if requester_vpc and accepter_vpc:
            requester_cidrs = [b.cidr_block for b in requester_vpc.cidr_blocks]
            accepter_cidrs = [b.cidr_block for b in accepter_vpc.cidr_blocks]
            overlaps = find_cidr_overlaps(requester_cidrs, accepter_cidrs)
            if overlaps:
                error_msg = f"CIDR overlap detected: {overlaps}"
                return OperationResult(
                    success=False,
                    operation="create_peering",
                    resource_id="",
                    resource_type="vpc_peering",
                    message=error_msg,
                    error=error_msg,
                )

        peering_id = f"pcx-{uuid.uuid4().hex[:17]}"
        now = datetime.now(timezone.utc).isoformat()

        peering = VPCPeeringConnection(
            peering_id=peering_id,
            requester_vpc_id=request.requester_vpc_id,
            accepter_vpc_id=request.accepter_vpc_id,
            tenant_id=request.tenant_id,
            state=PeeringState.ACTIVE if request.auto_accept else PeeringState.PENDING_ACCEPTANCE,
            requester_cidr=request.requester_cidr or (
                requester_vpc.primary_cidr or "" if requester_vpc else ""
            ),
            accepter_cidr=request.accepter_cidr or (
                accepter_vpc.primary_cidr or "" if accepter_vpc else ""
            ),
            region=request.region,
            provider=request.provider,
            name=request.name,
            tags=request.tags,
            created_at=now,
            accepted_at=now if request.auto_accept else None,
            metadata=request.metadata,
        )

        self._peerings[peering_id] = peering
        self._notify(peering, "created")

        return OperationResult(
            success=True,
            operation="create_peering",
            resource_id=peering_id,
            resource_type="vpc_peering",
            message=f"Peering connection {peering_id} created",
            state=peering.state.value,
            metadata={
                "requester_vpc_id": request.requester_vpc_id,
                "accepter_vpc_id": request.accepter_vpc_id,
            },
        )

    def accept_peering(
        self,
        acceptance: PeeringAcceptance,
    ) -> OperationResult:
        """Accept a pending peering connection."""
        peering = self._peerings.get(acceptance.peering_id)
        if not peering:
            error = f"Peering {acceptance.peering_id} not found"
            return OperationResult(
                success=False,
                operation="accept_peering",
                resource_id=acceptance.peering_id,
                resource_type="vpc_peering",
                message=error,
                error=error,
            )

        if peering.tenant_id != acceptance.tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="accept_peering",
                resource_id=acceptance.peering_id,
                resource_type="vpc_peering",
                message=error,
                error=error,
            )

        if peering.state != PeeringState.PENDING_ACCEPTANCE:
            error = f"Peering is not pending acceptance (state: {peering.state.value})"
            return OperationResult(
                success=False,
                operation="accept_peering",
                resource_id=acceptance.peering_id,
                resource_type="vpc_peering",
                message=error,
                error=error,
            )

        now = datetime.now(timezone.utc).isoformat()
        peering.state = PeeringState.ACTIVE
        peering.accepted_at = now
        self._notify(peering, "accepted")

        return OperationResult(
            success=True,
            operation="accept_peering",
            resource_id=peering.peering_id,
            resource_type="vpc_peering",
            message=f"Peering {peering.peering_id} accepted",
            state=peering.state.value,
        )

    def reject_peering(
        self,
        peering_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Reject a pending peering connection."""
        peering = self._peerings.get(peering_id)
        if not peering:
            error = f"Peering {peering_id} not found"
            return OperationResult(
                success=False,
                operation="reject_peering",
                resource_id=peering_id,
                resource_type="vpc_peering",
                message=error,
                error=error,
            )

        if peering.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="reject_peering",
                resource_id=peering_id,
                resource_type="vpc_peering",
                message=error,
                error=error,
            )

        peering.state = PeeringState.REJECTED
        self._notify(peering, "rejected")

        return OperationResult(
            success=True,
            operation="reject_peering",
            resource_id=peering_id,
            resource_type="vpc_peering",
            message=f"Peering {peering_id} rejected",
            state=peering.state.value,
        )

    def delete_peering(
        self,
        peering_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Delete a peering connection."""
        peering = self._peerings.get(peering_id)
        if not peering:
            error = f"Peering {peering_id} not found"
            return OperationResult(
                success=False,
                operation="delete_peering",
                resource_id=peering_id,
                resource_type="vpc_peering",
                message=error,
                error=error,
            )

        if peering.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="delete_peering",
                resource_id=peering_id,
                resource_type="vpc_peering",
                message=error,
                error=error,
            )

        peering.state = PeeringState.DELETED
        del self._peerings[peering_id]
        self._notify(peering, "deleted")

        return OperationResult(
            success=True,
            operation="delete_peering",
            resource_id=peering_id,
            resource_type="vpc_peering",
            message=f"Peering {peering_id} deleted",
            state=peering.state.value,
        )

    # -----------------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------------

    def get_peering(self, peering_id: str) -> VPCPeeringConnection | None:
        """Get a peering connection by ID."""
        return self._peerings.get(peering_id)

    def list_peerings(
        self,
        tenant_id: str | None = None,
        vpc_id: str | None = None,
        state: PeeringState | None = None,
    ) -> list[VPCPeeringConnection]:
        """List peering connections with optional filters."""
        peerings = list(self._peerings.values())
        if tenant_id:
            peerings = [p for p in peerings if p.tenant_id == tenant_id]
        if vpc_id:
            peerings = [
                p for p in peerings
                if p.requester_vpc_id == vpc_id or p.accepter_vpc_id == vpc_id
            ]
        if state:
            peerings = [p for p in peerings if p.state == state]
        return peerings

    def get_peering_topology(
        self,
        tenant_id: str,
    ) -> dict[str, list[str]]:
        """Get peering topology as adjacency list."""
        peerings = self.list_peerings(tenant_id=tenant_id, state=PeeringState.ACTIVE)
        topology: dict[str, list[str]] = {}
        for p in peerings:
            topology.setdefault(p.requester_vpc_id, []).append(p.accepter_vpc_id)
            topology.setdefault(p.accepter_vpc_id, []).append(p.requester_vpc_id)
        return topology

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    def validate_peering(
        self,
        request: PeeringRequest,
    ) -> ValidationResult:
        """Validate a peering request without creating it."""
        errors: list[str] = []
        warnings: list[str] = []

        try:
            self._validate_peering_request(request)
        except PeeringValidationError as exc:
            errors.append(str(exc))

        # Check CIDR overlaps
        requester_vpc = self._vpcs.get(request.requester_vpc_id)
        accepter_vpc = self._vpcs.get(request.accepter_vpc_id)

        if requester_vpc and accepter_vpc:
            requester_cidrs = [b.cidr_block for b in requester_vpc.cidr_blocks]
            accepter_cidrs = [b.cidr_block for b in accepter_vpc.cidr_blocks]
            overlaps = find_cidr_overlaps(requester_cidrs, accepter_cidrs)
            if overlaps:
                errors.append(f"CIDR overlap detected: {overlaps}")

        # Check for existing peering between same VPCs
        existing = self.list_peerings(tenant_id=request.tenant_id)
        for p in existing:
            if p.state in (PeeringState.ACTIVE, PeeringState.PENDING_ACCEPTANCE):
                if (
                    (p.requester_vpc_id == request.requester_vpc_id
                     and p.accepter_vpc_id == request.accepter_vpc_id)
                    or (p.requester_vpc_id == request.accepter_vpc_id
                        and p.accepter_vpc_id == request.requester_vpc_id)
                ):
                    errors.append(
                        f"Peering already exists between {request.requester_vpc_id} "
                        f"and {request.accepter_vpc_id}: {p.peering_id}"
                    )
                    break

        if not request.region:
            warnings.append("No region specified")

        return ValidationResult(valid=not errors, errors=errors, warnings=warnings)

    def _validate_peering_request(self, request: PeeringRequest) -> None:
        """Validate a peering request, raising on failure."""
        validate_resource_id(request.requester_vpc_id, "vpc-")
        validate_resource_id(request.accepter_vpc_id, "vpc-")
        validate_resource_id(request.tenant_id, "t-")
        validate_region(request.region)

        if request.requester_vpc_id == request.accepter_vpc_id:
            raise PeeringValidationError("Cannot peer a VPC with itself")

        if request.requester_cidr:
            validate_cidr(request.requester_cidr)
        if request.accepter_cidr:
            validate_cidr(request.accepter_cidr)

    # -----------------------------------------------------------------------
    # Event listeners
    # -----------------------------------------------------------------------

    def add_listener(
        self,
        listener: Callable[[VPCPeeringConnection, str], None],
    ) -> None:
        """Add a peering event listener."""
        self._listeners.append(listener)

    def remove_listener(
        self,
        listener: Callable[[VPCPeeringConnection, str], None],
    ) -> None:
        """Remove a peering event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self, peering: VPCPeeringConnection, event: str) -> None:
        """Notify all listeners of a peering event."""
        for listener in self._listeners:
            try:
                listener(peering, event)
            except Exception:
                pass  # Don't let listeners break the engine


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_engine: VPCPeeringEngine | None = None


def get_engine() -> VPCPeeringEngine:
    """Return the process-wide default peering engine."""
    global _default_engine
    if _default_engine is None:
        _default_engine = VPCPeeringEngine()
    return _default_engine
