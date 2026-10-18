"""Transit Gateway automation engine.

Manages AWS Transit Gateway, Azure Virtual WAN, and GCP Cloud Router
for hub-and-spoke network topologies.
Pure stdlib implementation: no external dependencies.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from .models import (
    CloudProvider,
    OperationResult,
    TransitGatewayState,
    TransitGateway,
    TransitGatewayAttachment,
    VPC,
    validate_asn,
    validate_region,
    validate_resource_id,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class TransitGatewayError(Exception):
    """Base exception for transit gateway errors."""
    pass


class TransitGatewayValidationError(TransitGatewayError):
    """Validation failed for transit gateway operation."""
    pass


class TransitGatewayConflictError(TransitGatewayError):
    """Transit gateway configuration conflict."""
    pass


class TransitGatewayNotFoundError(TransitGatewayError):
    """Transit gateway not found."""
    pass


class AttachmentError(TransitGatewayError):
    """Attachment operation failed."""
    pass


# ---------------------------------------------------------------------------
# Request types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TransitGatewayRequest:
    """Request to create a transit gateway."""
    tenant_id: str
    name: str = ""
    amazon_side_asn: int = 64512
    auto_accept_shared_attachments: str = "disable"
    default_route_table_association: str = "enable"
    default_route_table_propagation: str = "enable"
    dns_support: str = "enable"
    vpn_ecmp_support: str = "enable"
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AttachmentRequest:
    """Request to attach a VPC to a transit gateway."""
    transit_gateway_id: str
    vpc_id: str
    tenant_id: str
    subnet_ids: list[str] = field(default_factory=list)
    attachment_type: str = "vpc"
    name: str = ""
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Transit Gateway engine
# ---------------------------------------------------------------------------

class TransitGatewayEngine:
    """Engine for managing transit gateways and attachments."""

    def __init__(self) -> None:
        self._gateways: dict[str, TransitGateway] = {}
        self._attachments: dict[str, TransitGatewayAttachment] = {}
        self._vpcs: dict[str, VPC] = {}
        self._listeners: list[Callable[[Any, str], None]] = []

    # -----------------------------------------------------------------------
    # VPC management
    # -----------------------------------------------------------------------

    def register_vpc(self, vpc: VPC) -> None:
        """Register a VPC for transit gateway operations."""
        self._vpcs[vpc.vpc_id] = vpc

    def get_vpc(self, vpc_id: str) -> VPC | None:
        """Get a registered VPC by ID."""
        return self._vpcs.get(vpc_id)

    # -----------------------------------------------------------------------
    # Transit Gateway lifecycle
    # -----------------------------------------------------------------------

    def create_gateway(
        self,
        request: TransitGatewayRequest,
    ) -> OperationResult:
        """Create a new transit gateway."""
        try:
            self._validate_gateway_request(request)
        except TransitGatewayValidationError as exc:
            return OperationResult(
                success=False,
                operation="create_gateway",
                resource_id="",
                resource_type="transit_gateway",
                message=str(exc),
                error=str(exc),
            )

        gateway_id = f"tgw-{uuid.uuid4().hex[:17]}"
        now = datetime.now(timezone.utc).isoformat()

        gateway = TransitGateway(
            transit_gateway_id=gateway_id,
            tenant_id=request.tenant_id,
            state=TransitGatewayState.AVAILABLE,
            amazon_side_asn=request.amazon_side_asn,
            auto_accept_shared_attachments=request.auto_accept_shared_attachments,
            default_route_table_association=request.default_route_table_association,
            default_route_table_propagation=request.default_route_table_propagation,
            dns_support=request.dns_support,
            vpn_ecmp_support=request.vpn_ecmp_support,
            region=request.region,
            provider=request.provider,
            name=request.name,
            tags=request.tags,
            created_at=now,
            metadata=request.metadata,
        )

        self._gateways[gateway_id] = gateway
        self._notify(gateway, "created")

        return OperationResult(
            success=True,
            operation="create_gateway",
            resource_id=gateway_id,
            resource_type="transit_gateway",
            message=f"Transit gateway {gateway_id} created",
            state=gateway.state.value,
            metadata={
                "amazon_side_asn": request.amazon_side_asn,
                "region": request.region,
            },
        )

    def modify_gateway(
        self,
        gateway_id: str,
        tenant_id: str,
        **kwargs: Any,
    ) -> OperationResult:
        """Modify a transit gateway configuration."""
        gateway = self._gateways.get(gateway_id)
        if not gateway:
            error = f"Transit gateway {gateway_id} not found"
            return OperationResult(
                success=False,
                operation="modify_gateway",
                resource_id=gateway_id,
                resource_type="transit_gateway",
                message=error,
                error=error,
            )

        if gateway.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="modify_gateway",
                resource_id=gateway_id,
                resource_type="transit_gateway",
                message=error,
                error=error,
            )

        gateway.state = TransitGatewayState.MODIFYING
        now = datetime.now(timezone.utc).isoformat()

        # Apply modifications
        if "auto_accept_shared_attachments" in kwargs:
            gateway.auto_accept_shared_attachments = kwargs["auto_accept_shared_attachments"]
        if "default_route_table_association" in kwargs:
            gateway.default_route_table_association = kwargs["default_route_table_association"]
        if "default_route_table_propagation" in kwargs:
            gateway.default_route_table_propagation = kwargs["default_route_table_propagation"]
        if "dns_support" in kwargs:
            gateway.dns_support = kwargs["dns_support"]
        if "vpn_ecmp_support" in kwargs:
            gateway.vpn_ecmp_support = kwargs["vpn_ecmp_support"]
        if "tags" in kwargs:
            gateway.tags.update(kwargs["tags"])

        gateway.state = TransitGatewayState.AVAILABLE
        self._notify(gateway, "modified")

        return OperationResult(
            success=True,
            operation="modify_gateway",
            resource_id=gateway_id,
            resource_type="transit_gateway",
            message=f"Transit gateway {gateway_id} modified",
            state=gateway.state.value,
        )

    def delete_gateway(
        self,
        gateway_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Delete a transit gateway."""
        gateway = self._gateways.get(gateway_id)
        if not gateway:
            error = f"Transit gateway {gateway_id} not found"
            return OperationResult(
                success=False,
                operation="delete_gateway",
                resource_id=gateway_id,
                resource_type="transit_gateway",
                message=error,
                error=error,
            )

        if gateway.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="delete_gateway",
                resource_id=gateway_id,
                resource_type="transit_gateway",
                message=error,
                error=error,
            )

        # Check for active attachments
        active_attachments = [
            a for a in gateway.attachments
            if a.state == "available"
        ]
        if active_attachments:
            error = f"Cannot delete: {len(active_attachments)} active attachments"
            return OperationResult(
                success=False,
                operation="delete_gateway",
                resource_id=gateway_id,
                resource_type="transit_gateway",
                message=error,
                error=error,
            )

        gateway.state = TransitGatewayState.DELETED
        del self._gateways[gateway_id]
        self._notify(gateway, "deleted")

        return OperationResult(
            success=True,
            operation="delete_gateway",
            resource_id=gateway_id,
            resource_type="transit_gateway",
            message=f"Transit gateway {gateway_id} deleted",
            state=gateway.state.value,
        )

    # -----------------------------------------------------------------------
    # Attachment lifecycle
    # -----------------------------------------------------------------------

    def attach_vpc(
        self,
        request: AttachmentRequest,
    ) -> OperationResult:
        """Attach a VPC to a transit gateway."""
        try:
            self._validate_attachment_request(request)
        except TransitGatewayValidationError as exc:
            return OperationResult(
                success=False,
                operation="attach_vpc",
                resource_id="",
                resource_type="transit_gateway_attachment",
                message=str(exc),
                error=str(exc),
            )

        gateway = self._gateways.get(request.transit_gateway_id)
        if not gateway:
            error = f"Transit gateway {request.transit_gateway_id} not found"
            return OperationResult(
                success=False,
                operation="attach_vpc",
                resource_id="",
                resource_type="transit_gateway_attachment",
                message=error,
                error=error,
            )

        if gateway.tenant_id != request.tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="attach_vpc",
                resource_id="",
                resource_type="transit_gateway_attachment",
                message=error,
                error=error,
            )

        # Check for duplicate attachment
        for att in gateway.attachments:
            if att.vpc_id == request.vpc_id and att.state == "available":
                error = f"VPC {request.vpc_id} already attached to {request.transit_gateway_id}"
                return OperationResult(
                    success=False,
                    operation="attach_vpc",
                    resource_id=att.attachment_id,
                    resource_type="transit_gateway_attachment",
                    message=error,
                    error=error,
                )

        attachment_id = f"tgw-attach-{uuid.uuid4().hex[:17]}"
        now = datetime.now(timezone.utc).isoformat()

        attachment = TransitGatewayAttachment(
            attachment_id=attachment_id,
            transit_gateway_id=request.transit_gateway_id,
            vpc_id=request.vpc_id,
            tenant_id=request.tenant_id,
            state="available",
            attachment_type=request.attachment_type,
            subnet_ids=request.subnet_ids,
            region=request.region,
            provider=request.provider,
            name=request.name,
            tags=request.tags,
            created_at=now,
            metadata=request.metadata,
        )

        self._attachments[attachment_id] = attachment
        gateway.attachments.append(attachment)
        self._notify(attachment, "attached")

        return OperationResult(
            success=True,
            operation="attach_vpc",
            resource_id=attachment_id,
            resource_type="transit_gateway_attachment",
            message=f"VPC {request.vpc_id} attached to {request.transit_gateway_id}",
            state=attachment.state,
            metadata={
                "transit_gateway_id": request.transit_gateway_id,
                "vpc_id": request.vpc_id,
            },
        )

    def detach_vpc(
        self,
        attachment_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Detach a VPC from a transit gateway."""
        attachment = self._attachments.get(attachment_id)
        if not attachment:
            error = f"Attachment {attachment_id} not found"
            return OperationResult(
                success=False,
                operation="detach_vpc",
                resource_id=attachment_id,
                resource_type="transit_gateway_attachment",
                message=error,
                error=error,
            )

        if attachment.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="detach_vpc",
                resource_id=attachment_id,
                resource_type="transit_gateway_attachment",
                message=error,
                error=error,
            )

        gateway = self._gateways.get(attachment.transit_gateway_id)
        if gateway:
            gateway.attachments = [
                a for a in gateway.attachments
                if a.attachment_id != attachment_id
            ]

        attachment.state = "deleted"
        del self._attachments[attachment_id]
        self._notify(attachment, "detached")

        return OperationResult(
            success=True,
            operation="detach_vpc",
            resource_id=attachment_id,
            resource_type="transit_gateway_attachment",
            message=f"Attachment {attachment_id} deleted",
            state=attachment.state,
        )

    # -----------------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------------

    def get_gateway(self, gateway_id: str) -> TransitGateway | None:
        """Get a transit gateway by ID."""
        return self._gateways.get(gateway_id)

    def list_gateways(
        self,
        tenant_id: str | None = None,
        state: TransitGatewayState | None = None,
    ) -> list[TransitGateway]:
        """List transit gateways with optional filters."""
        gateways = list(self._gateways.values())
        if tenant_id:
            gateways = [g for g in gateways if g.tenant_id == tenant_id]
        if state:
            gateways = [g for g in gateways if g.state == state]
        return gateways

    def get_attachment(self, attachment_id: str) -> TransitGatewayAttachment | None:
        """Get an attachment by ID."""
        return self._attachments.get(attachment_id)

    def list_attachments(
        self,
        tenant_id: str | None = None,
        gateway_id: str | None = None,
        vpc_id: str | None = None,
    ) -> list[TransitGatewayAttachment]:
        """List attachments with optional filters."""
        attachments = list(self._attachments.values())
        if tenant_id:
            attachments = [a for a in attachments if a.tenant_id == tenant_id]
        if gateway_id:
            attachments = [a for a in attachments if a.transit_gateway_id == gateway_id]
        if vpc_id:
            attachments = [a for a in attachments if a.vpc_id == vpc_id]
        return attachments

    def get_gateway_topology(
        self,
        gateway_id: str,
    ) -> dict[str, Any]:
        """Get the topology of a transit gateway."""
        gateway = self._gateways.get(gateway_id)
        if not gateway:
            return {}

        return {
            "gateway_id": gateway_id,
            "state": gateway.state.value,
            "asn": gateway.amazon_side_asn,
            "attachments": [
                {
                    "attachment_id": a.attachment_id,
                    "vpc_id": a.vpc_id,
                    "type": a.attachment_type,
                    "state": a.state,
                    "subnets": a.subnet_ids,
                }
                for a in gateway.attachments
                if a.state == "available"
            ],
        }

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    def _validate_gateway_request(self, request: TransitGatewayRequest) -> None:
        """Validate a gateway creation request."""
        validate_resource_id(request.tenant_id, "t-")
        validate_region(request.region)
        validate_asn(request.amazon_side_asn)

        if request.auto_accept_shared_attachments not in ("enable", "disable"):
            raise TransitGatewayValidationError(
                "auto_accept_shared_attachments must be 'enable' or 'disable'"
            )
        if request.default_route_table_association not in ("enable", "disable"):
            raise TransitGatewayValidationError(
                "default_route_table_association must be 'enable' or 'disable'"
            )
        if request.default_route_table_propagation not in ("enable", "disable"):
            raise TransitGatewayValidationError(
                "default_route_table_propagation must be 'enable' or 'disable'"
            )

    def _validate_attachment_request(self, request: AttachmentRequest) -> None:
        """Validate an attachment request."""
        validate_resource_id(request.transit_gateway_id, "tgw-")
        validate_resource_id(request.vpc_id, "vpc-")
        validate_resource_id(request.tenant_id, "t-")
        validate_region(request.region)

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

_default_engine: TransitGatewayEngine | None = None


def get_engine() -> TransitGatewayEngine:
    """Return the process-wide default transit gateway engine."""
    global _default_engine
    if _default_engine is None:
        _default_engine = TransitGatewayEngine()
    return _default_engine
