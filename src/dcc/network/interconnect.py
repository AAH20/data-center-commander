"""Cloud Interconnect automation engine.

Manages GCP Cloud Interconnect, AWS Direct Connect, and Azure
ExpressRoute FastPath for dedicated on-premises connectivity.
Pure stdlib implementation: no external dependencies.
"""
from __future__ import annotations

import ipaddress
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from .models import (
    CloudInterconnect,
    CloudProvider,
    InterconnectAttachment,
    InterconnectState,
    OperationResult,
    validate_bandwidth_mbps,
    validate_cidr,
    validate_region,
    validate_resource_id,
    validate_vlan_id,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class InterconnectError(Exception):
    """Base exception for Cloud Interconnect errors."""
    pass


class InterconnectValidationError(InterconnectError):
    """Validation failed for interconnect operation."""
    pass


class InterconnectConflictError(InterconnectError):
    """Interconnect configuration conflict."""
    pass


class InterconnectNotFoundError(InterconnectError):
    """Interconnect not found."""
    pass


class AttachmentError(InterconnectError):
    """Attachment operation failed."""
    pass


# ---------------------------------------------------------------------------
# Request types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class InterconnectRequest:
    """Request to create a Cloud Interconnect."""
    tenant_id: str
    interconnect_type: str = "DEDICATED"
    link_type: str = "LINK_TYPE_ETHERNET_10G_LR"
    location: str = ""
    bandwidth_mbps: int = 10000
    name: str = ""
    provider: CloudProvider = CloudProvider.GCP
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InterconnectAttachmentRequest:
    """Request to create an interconnect attachment (VLAN)."""
    interconnect_id: str
    tenant_id: str
    vlan_tag: int = 0
    bgp_session_enabled: bool = False
    peer_ip: str = ""
    cloud_router_ip: str = ""
    region: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Cloud Interconnect engine
# ---------------------------------------------------------------------------

class CloudInterconnectEngine:
    """Engine for managing Cloud Interconnects and attachments."""

    def __init__(self) -> None:
        self._interconnects: dict[str, CloudInterconnect] = {}
        self._attachments: dict[str, InterconnectAttachment] = {}
        self._listeners: list[Callable[[Any, str], None]] = []

    # -----------------------------------------------------------------------
    # Interconnect lifecycle
    # -----------------------------------------------------------------------

    def create_interconnect(
        self,
        request: InterconnectRequest,
    ) -> OperationResult:
        """Create a new Cloud Interconnect."""
        try:
            self._validate_interconnect_request(request)
        except InterconnectValidationError as exc:
            return OperationResult(
                success=False,
                operation="create_interconnect",
                resource_id="",
                resource_type="cloud_interconnect",
                message=str(exc),
                error=str(exc),
            )

        interconnect_id = f"ic-{uuid.uuid4().hex[:17]}"
        now = datetime.now(timezone.utc).isoformat()

        interconnect = CloudInterconnect(
            interconnect_id=interconnect_id,
            tenant_id=request.tenant_id,
            state=InterconnectState.ACTIVE,
            interconnect_type=request.interconnect_type,
            link_type=request.link_type,
            location=request.location,
            bandwidth_mbps=request.bandwidth_mbps,
            provider=request.provider,
            name=request.name,
            tags=request.tags,
            created_at=now,
            metadata=request.metadata,
        )

        self._interconnects[interconnect_id] = interconnect
        self._notify(interconnect, "created")

        return OperationResult(
            success=True,
            operation="create_interconnect",
            resource_id=interconnect_id,
            resource_type="cloud_interconnect",
            message=f"Cloud Interconnect {interconnect_id} created",
            state=interconnect.state.value,
            metadata={
                "interconnect_type": request.interconnect_type,
                "bandwidth_mbps": request.bandwidth_mbps,
                "location": request.location,
            },
        )

    def modify_interconnect(
        self,
        interconnect_id: str,
        tenant_id: str,
        **kwargs: Any,
    ) -> OperationResult:
        """Modify a Cloud Interconnect."""
        interconnect = self._interconnects.get(interconnect_id)
        if not interconnect:
            error = f"Cloud Interconnect {interconnect_id} not found"
            return OperationResult(
                success=False,
                operation="modify_interconnect",
                resource_id=interconnect_id,
                resource_type="cloud_interconnect",
                message=error,
                error=error,
            )

        if interconnect.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="modify_interconnect",
                resource_id=interconnect_id,
                resource_type="cloud_interconnect",
                message=error,
                error=error,
            )

        if "bandwidth_mbps" in kwargs:
            validate_bandwidth_mbps(kwargs["bandwidth_mbps"])
            interconnect.bandwidth_mbps = kwargs["bandwidth_mbps"]
        if "tags" in kwargs:
            interconnect.tags.update(kwargs["tags"])

        self._notify(interconnect, "modified")

        return OperationResult(
            success=True,
            operation="modify_interconnect",
            resource_id=interconnect_id,
            resource_type="cloud_interconnect",
            message=f"Cloud Interconnect {interconnect_id} modified",
            state=interconnect.state.value,
        )

    def delete_interconnect(
        self,
        interconnect_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Delete a Cloud Interconnect."""
        interconnect = self._interconnects.get(interconnect_id)
        if not interconnect:
            error = f"Cloud Interconnect {interconnect_id} not found"
            return OperationResult(
                success=False,
                operation="delete_interconnect",
                resource_id=interconnect_id,
                resource_type="cloud_interconnect",
                message=error,
                error=error,
            )

        if interconnect.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="delete_interconnect",
                resource_id=interconnect_id,
                resource_type="cloud_interconnect",
                message=error,
                error=error,
            )

        # Check for active attachments
        active = [a for a in interconnect.attachments if a.state == "active"]
        if active:
            error = f"Cannot delete: {len(active)} active attachments"
            return OperationResult(
                success=False,
                operation="delete_interconnect",
                resource_id=interconnect_id,
                resource_type="cloud_interconnect",
                message=error,
                error=error,
            )

        interconnect.state = InterconnectState.DELETED
        del self._interconnects[interconnect_id]
        self._notify(interconnect, "deleted")

        return OperationResult(
            success=True,
            operation="delete_interconnect",
            resource_id=interconnect_id,
            resource_type="cloud_interconnect",
            message=f"Cloud Interconnect {interconnect_id} deleted",
            state=interconnect.state.value,
        )

    # -----------------------------------------------------------------------
    # Attachment lifecycle
    # -----------------------------------------------------------------------

    def create_attachment(
        self,
        request: InterconnectAttachmentRequest,
    ) -> OperationResult:
        """Create a VLAN attachment on an interconnect."""
        try:
            self._validate_attachment_request(request)
        except InterconnectValidationError as exc:
            return OperationResult(
                success=False,
                operation="create_attachment",
                resource_id="",
                resource_type="interconnect_attachment",
                message=str(exc),
                error=str(exc),
            )

        interconnect = self._interconnects.get(request.interconnect_id)
        if not interconnect:
            error = f"Cloud Interconnect {request.interconnect_id} not found"
            return OperationResult(
                success=False,
                operation="create_attachment",
                resource_id="",
                resource_type="interconnect_attachment",
                message=error,
                error=error,
            )

        if interconnect.tenant_id != request.tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="create_attachment",
                resource_id="",
                resource_type="interconnect_attachment",
                message=error,
                error=error,
            )

        # Check for duplicate VLAN tag
        for att in interconnect.attachments:
            if att.vlan_tag == request.vlan_tag and att.state == "active":
                error = f"VLAN tag {request.vlan_tag} already in use"
                return OperationResult(
                    success=False,
                    operation="create_attachment",
                    resource_id=att.attachment_id,
                    resource_type="interconnect_attachment",
                    message=error,
                    error=error,
                )

        attachment_id = f"ica-{uuid.uuid4().hex[:17]}"
        now = datetime.now(timezone.utc).isoformat()

        attachment = InterconnectAttachment(
            attachment_id=attachment_id,
            interconnect_id=request.interconnect_id,
            tenant_id=request.tenant_id,
            state="active",
            vlan_tag=request.vlan_tag,
            bgp_session_enabled=request.bgp_session_enabled,
            peer_ip=request.peer_ip,
            cloud_router_ip=request.cloud_router_ip,
            region=request.region,
            metadata=request.metadata,
        )

        self._attachments[attachment_id] = attachment
        interconnect.attachments.append(attachment)
        self._notify(attachment, "created")

        return OperationResult(
            success=True,
            operation="create_attachment",
            resource_id=attachment_id,
            resource_type="interconnect_attachment",
            message=f"Attachment {attachment_id} created on {request.interconnect_id}",
            state=attachment.state,
            metadata={
                "interconnect_id": request.interconnect_id,
                "vlan_tag": request.vlan_tag,
            },
        )

    def delete_attachment(
        self,
        attachment_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Delete an interconnect attachment."""
        attachment = self._attachments.get(attachment_id)
        if not attachment:
            error = f"Attachment {attachment_id} not found"
            return OperationResult(
                success=False,
                operation="delete_attachment",
                resource_id=attachment_id,
                resource_type="interconnect_attachment",
                message=error,
                error=error,
            )

        if attachment.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="delete_attachment",
                resource_id=attachment_id,
                resource_type="interconnect_attachment",
                message=error,
                error=error,
            )

        interconnect = self._interconnects.get(attachment.interconnect_id)
        if interconnect:
            interconnect.attachments = [
                a for a in interconnect.attachments
                if a.attachment_id != attachment_id
            ]

        attachment.state = "deleted"
        del self._attachments[attachment_id]
        self._notify(attachment, "deleted")

        return OperationResult(
            success=True,
            operation="delete_attachment",
            resource_id=attachment_id,
            resource_type="interconnect_attachment",
            message=f"Attachment {attachment_id} deleted",
            state=attachment.state,
        )

    # -----------------------------------------------------------------------
    # BGP session management
    # -----------------------------------------------------------------------

    def configure_bgp_session(
        self,
        attachment_id: str,
        tenant_id: str,
        peer_ip: str,
        cloud_router_ip: str,
        peer_asn: int | None = None,
    ) -> OperationResult:
        """Configure BGP session on an attachment."""
        attachment = self._attachments.get(attachment_id)
        if not attachment:
            error = f"Attachment {attachment_id} not found"
            return OperationResult(
                success=False,
                operation="configure_bgp_session",
                resource_id=attachment_id,
                resource_type="bgp_session",
                message=error,
                error=error,
            )

        if attachment.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="configure_bgp_session",
                resource_id=attachment_id,
                resource_type="bgp_session",
                message=error,
                error=error,
            )

        # Validate IP addresses
        try:
            ipaddress.ip_address(peer_ip)
            ipaddress.ip_address(cloud_router_ip)
        except ValueError as exc:
            error = f"Invalid IP address: {exc}"
            return OperationResult(
                success=False,
                operation="configure_bgp_session",
                resource_id=attachment_id,
                resource_type="bgp_session",
                message=error,
                error=error,
            )

        attachment.peer_ip = peer_ip
        attachment.cloud_router_ip = cloud_router_ip
        attachment.bgp_session_enabled = True
        self._notify(attachment, "bgp_configured")

        return OperationResult(
            success=True,
            operation="configure_bgp_session",
            resource_id=attachment_id,
            resource_type="bgp_session",
            message=f"BGP session configured on {attachment_id}",
            state="active",
            metadata={
                "peer_ip": peer_ip,
                "cloud_router_ip": cloud_router_ip,
            },
        )

    # -----------------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------------

    def get_interconnect(self, interconnect_id: str) -> CloudInterconnect | None:
        """Get an interconnect by ID."""
        return self._interconnects.get(interconnect_id)

    def list_interconnects(
        self,
        tenant_id: str | None = None,
        state: InterconnectState | None = None,
    ) -> list[CloudInterconnect]:
        """List interconnects with optional filters."""
        interconnects = list(self._interconnects.values())
        if tenant_id:
            interconnects = [i for i in interconnects if i.tenant_id == tenant_id]
        if state:
            interconnects = [i for i in interconnects if i.state == state]
        return interconnects

    def get_attachment(self, attachment_id: str) -> InterconnectAttachment | None:
        """Get an attachment by ID."""
        return self._attachments.get(attachment_id)

    def list_attachments(
        self,
        tenant_id: str | None = None,
        interconnect_id: str | None = None,
    ) -> list[InterconnectAttachment]:
        """List attachments with optional filters."""
        attachments = list(self._attachments.values())
        if tenant_id:
            attachments = [a for a in attachments if a.tenant_id == tenant_id]
        if interconnect_id:
            attachments = [a for a in attachments if a.interconnect_id == interconnect_id]
        return attachments

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    def _validate_interconnect_request(self, request: InterconnectRequest) -> None:
        """Validate an interconnect creation request."""
        validate_resource_id(request.tenant_id, "t-")
        validate_region(request.location)
        validate_bandwidth_mbps(request.bandwidth_mbps)

        valid_types = ("DEDICATED", "PARTNER")
        if request.interconnect_type not in valid_types:
            raise InterconnectValidationError(
                f"interconnect_type must be one of {valid_types}"
            )

    def _validate_attachment_request(self, request: InterconnectAttachmentRequest) -> None:
        """Validate an attachment request."""
        validate_resource_id(request.interconnect_id, "ic-")
        validate_resource_id(request.tenant_id, "t-")
        validate_region(request.region)

        if request.vlan_tag:
            validate_vlan_id(request.vlan_tag)

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

_default_engine: CloudInterconnectEngine | None = None


def get_engine() -> CloudInterconnectEngine:
    """Return the process-wide default Cloud Interconnect engine."""
    global _default_engine
    if _default_engine is None:
        _default_engine = CloudInterconnectEngine()
    return _default_engine
