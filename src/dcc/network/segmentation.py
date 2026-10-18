"""Network segmentation automation engine.

Manages VLANs, VXLANs, subnets, security groups, network ACLs,
and route tables for network isolation and micro-segmentation.
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
    NetworkACL,
    NetworkACLRule,
    OperationResult,
    Protocol,
    Route,
    RouteState,
    RouteTable,
    SecurityGroup,
    SecurityGroupRule,
    SegmentationType,
    Subnet,
    ValidationResult,
    NetworkSegment,
    VPC,
    validate_cidr,
    validate_region,
    validate_resource_id,
    validate_vlan_id,
    validate_vxlan_vni,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class SegmentationError(Exception):
    """Base exception for segmentation errors."""
    pass


class SegmentationValidationError(SegmentationError):
    """Validation failed for segmentation operation."""
    pass


class SegmentationConflictError(SegmentationError):
    """Segmentation configuration conflict."""
    pass


class SegmentationNotFoundError(SegmentationError):
    """Segmentation resource not found."""
    pass


class SecurityGroupError(SegmentationError):
    """Security group operation failed."""
    pass


class RouteTableError(SegmentationError):
    """Route table operation failed."""
    pass


# ---------------------------------------------------------------------------
# Request types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SegmentRequest:
    """Request to create a network segment."""
    tenant_id: str
    segmentation_type: SegmentationType
    name: str = ""
    vlan_id: int | None = None
    vxlan_vni: int | None = None
    cidr_block: str = ""
    vpc_id: str = ""
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SecurityGroupRequest:
    """Request to create a security group."""
    tenant_id: str
    name: str = ""
    description: str = ""
    vpc_id: str = ""
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SecurityGroupRuleRequest:
    """Request to add a rule to a security group."""
    group_id: str
    tenant_id: str
    protocol: Protocol
    from_port: int
    to_port: int
    cidr_blocks: list[str] = field(default_factory=list)
    source_security_group_ids: list[str] = field(default_factory=list)
    description: str = ""
    direction: str = "ingress"


@dataclass(slots=True)
class RouteTableRequest:
    """Request to create a route table."""
    tenant_id: str
    vpc_id: str = ""
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RouteRequest:
    """Request to add a route to a route table."""
    route_table_id: str
    tenant_id: str
    destination_cidr: str
    target: str
    target_type: str = "transit_gateway"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SubnetRequest:
    """Request to create a subnet."""
    tenant_id: str
    vpc_id: str
    cidr_block: str
    availability_zone: str = ""
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    name: str = ""
    map_public_ip_on_launch: bool = False
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Segmentation engine
# ---------------------------------------------------------------------------

class SegmentationEngine:
    """Engine for managing network segmentation resources."""

    def __init__(self) -> None:
        self._segments: dict[str, NetworkSegment] = {}
        self._security_groups: dict[str, SecurityGroup] = {}
        self._route_tables: dict[str, RouteTable] = {}
        self._subnets: dict[str, Subnet] = {}
        self._vpcs: dict[str, VPC] = {}
        self._listeners: list[Callable[[Any, str], None]] = []

    # -----------------------------------------------------------------------
    # VPC management
    # -----------------------------------------------------------------------

    def register_vpc(self, vpc: VPC) -> None:
        """Register a VPC for segmentation operations."""
        self._vpcs[vpc.vpc_id] = vpc

    def get_vpc(self, vpc_id: str) -> VPC | None:
        """Get a registered VPC by ID."""
        return self._vpcs.get(vpc_id)

    # -----------------------------------------------------------------------
    # Segment lifecycle
    # -----------------------------------------------------------------------

    def create_segment(
        self,
        request: SegmentRequest,
    ) -> OperationResult:
        """Create a new network segment."""
        try:
            self._validate_segment_request(request)
        except SegmentationValidationError as exc:
            return OperationResult(
                success=False,
                operation="create_segment",
                resource_id="",
                resource_type="network_segment",
                message=str(exc),
                error=str(exc),
            )

        segment_id = f"seg-{uuid.uuid4().hex[:17]}"
        now = datetime.now(timezone.utc).isoformat()

        segment = NetworkSegment(
            segment_id=segment_id,
            tenant_id=request.tenant_id,
            segmentation_type=request.segmentation_type,
            name=request.name,
            vlan_id=request.vlan_id,
            vxlan_vni=request.vxlan_vni,
            cidr_block=request.cidr_block,
            vpc_id=request.vpc_id,
            region=request.region,
            provider=request.provider,
            tags=request.tags,
            created_at=now,
            metadata=request.metadata,
        )

        self._segments[segment_id] = segment
        self._notify(segment, "created")

        return OperationResult(
            success=True,
            operation="create_segment",
            resource_id=segment_id,
            resource_type="network_segment",
            message=f"Network segment {segment_id} created",
            state=segment.state,
            metadata={
                "segmentation_type": request.segmentation_type.value,
                "vlan_id": request.vlan_id,
                "vxlan_vni": request.vxlan_vni,
            },
        )

    def delete_segment(
        self,
        segment_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Delete a network segment."""
        segment = self._segments.get(segment_id)
        if not segment:
            error = f"Segment {segment_id} not found"
            return OperationResult(
                success=False,
                operation="delete_segment",
                resource_id=segment_id,
                resource_type="network_segment",
                message=error,
                error=error,
            )

        if segment.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="delete_segment",
                resource_id=segment_id,
                resource_type="network_segment",
                message=error,
                error=error,
            )

        segment.state = "deleted"
        del self._segments[segment_id]
        self._notify(segment, "deleted")

        return OperationResult(
            success=True,
            operation="delete_segment",
            resource_id=segment_id,
            resource_type="network_segment",
            message=f"Segment {segment_id} deleted",
            state=segment.state,
        )

    # -----------------------------------------------------------------------
    # Security group lifecycle
    # -----------------------------------------------------------------------

    def create_security_group(
        self,
        request: SecurityGroupRequest,
    ) -> OperationResult:
        """Create a new security group."""
        try:
            self._validate_sg_request(request)
        except SegmentationValidationError as exc:
            return OperationResult(
                success=False,
                operation="create_security_group",
                resource_id="",
                resource_type="security_group",
                message=str(exc),
                error=str(exc),
            )

        group_id = f"sg-{uuid.uuid4().hex[:17]}"
        now = datetime.now(timezone.utc).isoformat()

        sg = SecurityGroup(
            group_id=group_id,
            tenant_id=request.tenant_id,
            name=request.name,
            description=request.description,
            vpc_id=request.vpc_id,
            region=request.region,
            provider=request.provider,
            tags=request.tags,
            created_at=now,
            metadata=request.metadata,
        )

        self._security_groups[group_id] = sg
        self._notify(sg, "created")

        return OperationResult(
            success=True,
            operation="create_security_group",
            resource_id=group_id,
            resource_type="security_group",
            message=f"Security group {group_id} created",
            state=sg.state,
        )

    def add_security_group_rule(
        self,
        request: SecurityGroupRuleRequest,
    ) -> OperationResult:
        """Add a rule to a security group."""
        sg = self._security_groups.get(request.group_id)
        if not sg:
            error = f"Security group {request.group_id} not found"
            return OperationResult(
                success=False,
                operation="add_security_group_rule",
                resource_id="",
                resource_type="security_group_rule",
                message=error,
                error=error,
            )

        if sg.tenant_id != request.tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="add_security_group_rule",
                resource_id="",
                resource_type="security_group_rule",
                message=error,
                error=error,
            )

        rule_id = f"sgr-{uuid.uuid4().hex[:17]}"
        rule = SecurityGroupRule(
            rule_id=rule_id,
            protocol=request.protocol,
            from_port=request.from_port,
            to_port=request.to_port,
            cidr_blocks=request.cidr_blocks,
            source_security_group_ids=request.source_security_group_ids,
            description=request.description,
            direction=request.direction,
        )

        sg.rules.append(rule)
        self._notify(sg, "rule_added")

        return OperationResult(
            success=True,
            operation="add_security_group_rule",
            resource_id=rule_id,
            resource_type="security_group_rule",
            message=f"Rule {rule_id} added to {request.group_id}",
            state="active",
        )

    def remove_security_group_rule(
        self,
        group_id: str,
        rule_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Remove a rule from a security group."""
        sg = self._security_groups.get(group_id)
        if not sg:
            error = f"Security group {group_id} not found"
            return OperationResult(
                success=False,
                operation="remove_security_group_rule",
                resource_id=rule_id,
                resource_type="security_group_rule",
                message=error,
                error=error,
            )

        if sg.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="remove_security_group_rule",
                resource_id=rule_id,
                resource_type="security_group_rule",
                message=error,
                error=error,
            )

        sg.rules = [r for r in sg.rules if r.rule_id != rule_id]
        self._notify(sg, "rule_removed")

        return OperationResult(
            success=True,
            operation="remove_security_group_rule",
            resource_id=rule_id,
            resource_type="security_group_rule",
            message=f"Rule {rule_id} removed from {group_id}",
            state="deleted",
        )

    def delete_security_group(
        self,
        group_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Delete a security group."""
        sg = self._security_groups.get(group_id)
        if not sg:
            error = f"Security group {group_id} not found"
            return OperationResult(
                success=False,
                operation="delete_security_group",
                resource_id=group_id,
                resource_type="security_group",
                message=error,
                error=error,
            )

        if sg.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="delete_security_group",
                resource_id=group_id,
                resource_type="security_group",
                message=error,
                error=error,
            )

        del self._security_groups[group_id]
        self._notify(sg, "deleted")

        return OperationResult(
            success=True,
            operation="delete_security_group",
            resource_id=group_id,
            resource_type="security_group",
            message=f"Security group {group_id} deleted",
            state="deleted",
        )

    # -----------------------------------------------------------------------
    # Route table lifecycle
    # -----------------------------------------------------------------------

    def create_route_table(
        self,
        request: RouteTableRequest,
    ) -> OperationResult:
        """Create a new route table."""
        try:
            validate_resource_id(request.tenant_id, "t-")
            validate_region(request.region)
            if request.vpc_id:
                validate_resource_id(request.vpc_id, "vpc-")
        except SegmentationValidationError as exc:
            return OperationResult(
                success=False,
                operation="create_route_table",
                resource_id="",
                resource_type="route_table",
                message=str(exc),
                error=str(exc),
            )

        route_table_id = f"rtb-{uuid.uuid4().hex[:17]}"
        now = datetime.now(timezone.utc).isoformat()

        rt = RouteTable(
            route_table_id=route_table_id,
            tenant_id=request.tenant_id,
            vpc_id=request.vpc_id,
            region=request.region,
            provider=request.provider,
            tags=request.tags,
            created_at=now,
            metadata=request.metadata,
        )

        self._route_tables[route_table_id] = rt
        self._notify(rt, "created")

        return OperationResult(
            success=True,
            operation="create_route_table",
            resource_id=route_table_id,
            resource_type="route_table",
            message=f"Route table {route_table_id} created",
            state=rt.state,
        )

    def add_route(
        self,
        request: RouteRequest,
    ) -> OperationResult:
        """Add a route to a route table."""
        rt = self._route_tables.get(request.route_table_id)
        if not rt:
            error = f"Route table {request.route_table_id} not found"
            return OperationResult(
                success=False,
                operation="add_route",
                resource_id="",
                resource_type="route",
                message=error,
                error=error,
            )

        if rt.tenant_id != request.tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="add_route",
                resource_id="",
                resource_type="route",
                message=error,
                error=error,
            )

        route_id = f"rt-{uuid.uuid4().hex[:17]}"
        route = Route(
            route_id=route_id,
            destination_cidr=request.destination_cidr,
            target=request.target,
            state=RouteState.ACTIVE,
            target_type=request.target_type,
            metadata=request.metadata,
        )

        rt.routes.append(route)
        self._notify(rt, "route_added")

        return OperationResult(
            success=True,
            operation="add_route",
            resource_id=route_id,
            resource_type="route",
            message=f"Route {route_id} added to {request.route_table_id}",
            state=route.state.value,
        )

    def remove_route(
        self,
        route_table_id: str,
        route_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Remove a route from a route table."""
        rt = self._route_tables.get(route_table_id)
        if not rt:
            error = f"Route table {route_table_id} not found"
            return OperationResult(
                success=False,
                operation="remove_route",
                resource_id=route_id,
                resource_type="route",
                message=error,
                error=error,
            )

        if rt.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="remove_route",
                resource_id=route_id,
                resource_type="route",
                message=error,
                error=error,
            )

        rt.routes = [r for r in rt.routes if r.route_id != route_id]
        self._notify(rt, "route_removed")

        return OperationResult(
            success=True,
            operation="remove_route",
            resource_id=route_id,
            resource_type="route",
            message=f"Route {route_id} removed from {route_table_id}",
            state="deleted",
        )

    def delete_route_table(
        self,
        route_table_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Delete a route table."""
        rt = self._route_tables.get(route_table_id)
        if not rt:
            error = f"Route table {route_table_id} not found"
            return OperationResult(
                success=False,
                operation="delete_route_table",
                resource_id=route_table_id,
                resource_type="route_table",
                message=error,
                error=error,
            )

        if rt.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="delete_route_table",
                resource_id=route_table_id,
                resource_type="route_table",
                message=error,
                error=error,
            )

        del self._route_tables[route_table_id]
        self._notify(rt, "deleted")

        return OperationResult(
            success=True,
            operation="delete_route_table",
            resource_id=route_table_id,
            resource_type="route_table",
            message=f"Route table {route_table_id} deleted",
            state="deleted",
        )

    # -----------------------------------------------------------------------
    # Subnet lifecycle
    # -----------------------------------------------------------------------

    def create_subnet(
        self,
        request: SubnetRequest,
    ) -> OperationResult:
        """Create a new subnet."""
        try:
            self._validate_subnet_request(request)
        except SegmentationValidationError as exc:
            return OperationResult(
                success=False,
                operation="create_subnet",
                resource_id="",
                resource_type="subnet",
                message=str(exc),
                error=str(exc),
            )

        subnet_id = f"subnet-{uuid.uuid4().hex[:17]}"
        now = datetime.now(timezone.utc).isoformat()

        subnet = Subnet(
            subnet_id=subnet_id,
            tenant_id=request.tenant_id,
            vpc_id=request.vpc_id,
            cidr_block=request.cidr_block,
            availability_zone=request.availability_zone,
            region=request.region,
            provider=request.provider,
            name=request.name,
            map_public_ip_on_launch=request.map_public_ip_on_launch,
            tags=request.tags,
            created_at=now,
            metadata=request.metadata,
        )

        self._subnets[subnet_id] = subnet
        self._notify(subnet, "created")

        return OperationResult(
            success=True,
            operation="create_subnet",
            resource_id=subnet_id,
            resource_type="subnet",
            message=f"Subnet {subnet_id} created",
            state=subnet.state,
        )

    def delete_subnet(
        self,
        subnet_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Delete a subnet."""
        subnet = self._subnets.get(subnet_id)
        if not subnet:
            error = f"Subnet {subnet_id} not found"
            return OperationResult(
                success=False,
                operation="delete_subnet",
                resource_id=subnet_id,
                resource_type="subnet",
                message=error,
                error=error,
            )

        if subnet.tenant_id != tenant_id:
            error = "Tenant mismatch"
            return OperationResult(
                success=False,
                operation="delete_subnet",
                resource_id=subnet_id,
                resource_type="subnet",
                message=error,
                error=error,
            )

        del self._subnets[subnet_id]
        self._notify(subnet, "deleted")

        return OperationResult(
            success=True,
            operation="delete_subnet",
            resource_id=subnet_id,
            resource_type="subnet",
            message=f"Subnet {subnet_id} deleted",
            state="deleted",
        )

    # -----------------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------------

    def get_segment(self, segment_id: str) -> NetworkSegment | None:
        """Get a segment by ID."""
        return self._segments.get(segment_id)

    def list_segments(
        self,
        tenant_id: str | None = None,
        segmentation_type: SegmentationType | None = None,
    ) -> list[NetworkSegment]:
        """List segments with optional filters."""
        segments = list(self._segments.values())
        if tenant_id:
            segments = [s for s in segments if s.tenant_id == tenant_id]
        if segmentation_type:
            segments = [s for s in segments if s.segmentation_type == segmentation_type]
        return segments

    def get_security_group(self, group_id: str) -> SecurityGroup | None:
        """Get a security group by ID."""
        return self._security_groups.get(group_id)

    def list_security_groups(
        self,
        tenant_id: str | None = None,
        vpc_id: str | None = None,
    ) -> list[SecurityGroup]:
        """List security groups with optional filters."""
        sgs = list(self._security_groups.values())
        if tenant_id:
            sgs = [sg for sg in sgs if sg.tenant_id == tenant_id]
        if vpc_id:
            sgs = [sg for sg in sgs if sg.vpc_id == vpc_id]
        return sgs

    def get_route_table(self, route_table_id: str) -> RouteTable | None:
        """Get a route table by ID."""
        return self._route_tables.get(route_table_id)

    def list_route_tables(
        self,
        tenant_id: str | None = None,
        vpc_id: str | None = None,
    ) -> list[RouteTable]:
        """List route tables with optional filters."""
        rts = list(self._route_tables.values())
        if tenant_id:
            rts = [rt for rt in rts if rt.tenant_id == tenant_id]
        if vpc_id:
            rts = [rt for rt in rts if rt.vpc_id == vpc_id]
        return rts

    def get_subnet(self, subnet_id: str) -> Subnet | None:
        """Get a subnet by ID."""
        return self._subnets.get(subnet_id)

    def list_subnets(
        self,
        tenant_id: str | None = None,
        vpc_id: str | None = None,
    ) -> list[Subnet]:
        """List subnets with optional filters."""
        subnets = list(self._subnets.values())
        if tenant_id:
            subnets = [s for s in subnets if s.tenant_id == tenant_id]
        if vpc_id:
            subnets = [s for s in subnets if s.vpc_id == vpc_id]
        return subnets

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    def _validate_segment_request(self, request: SegmentRequest) -> None:
        """Validate a segment creation request."""
        validate_resource_id(request.tenant_id, "t-")
        validate_region(request.region)

        if request.vlan_id is not None:
            validate_vlan_id(request.vlan_id)
        if request.vxlan_vni is not None:
            validate_vxlan_vni(request.vxlan_vni)
        if request.cidr_block:
            validate_cidr(request.cidr_block)
        if request.vpc_id:
            validate_resource_id(request.vpc_id, "vpc-")

    def _validate_sg_request(self, request: SecurityGroupRequest) -> None:
        """Validate a security group request."""
        validate_resource_id(request.tenant_id, "t-")
        validate_region(request.region)
        if request.vpc_id:
            validate_resource_id(request.vpc_id, "vpc-")

    def _validate_subnet_request(self, request: SubnetRequest) -> None:
        """Validate a subnet request."""
        validate_resource_id(request.tenant_id, "t-")
        validate_resource_id(request.vpc_id, "vpc-")
        validate_cidr(request.cidr_block)
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

_default_engine: SegmentationEngine | None = None


def get_engine() -> SegmentationEngine:
    """Return the process-wide default segmentation engine."""
    global _default_engine
    if _default_engine is None:
        _default_engine = SegmentationEngine()
    return _default_engine
