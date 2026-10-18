"""Network automation orchestrator.

Coordinates VPC peering, transit gateways, ExpressRoute, Cloud Interconnect,
and network segmentation into a unified automation engine.
Pure stdlib implementation: no external dependencies.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from .models import (
    CloudInterconnect,
    CloudProvider,
    ExpressRouteCircuit,
    NetworkSegment,
    OperationResult,
    PeeringState,
    SecurityGroup,
    Subnet,
    TopologyView,
    TransitGateway,
    TransitGatewayState,
    VPC,
    VPCPeeringConnection,
    VPCCidrBlock,
    validate_cidr,
    validate_region,
    validate_resource_id,
)
from .peering import (
    PeeringRequest,
    VPCPeeringEngine,
    get_engine as get_peering_engine,
)
from .transit_gateway import (
    AttachmentRequest,
    TransitGatewayEngine,
    TransitGatewayRequest,
    get_engine as get_tgw_engine,
)
from .expressroute import (
    ExpressRouteEngine,
    ExpressRoutePeeringRequest,
    ExpressRouteRequest,
    get_engine as get_er_engine,
)
from .interconnect import (
    CloudInterconnectEngine,
    InterconnectAttachmentRequest,
    InterconnectRequest,
    get_engine as get_ic_engine,
)
from .segmentation import (
    RouteRequest,
    RouteTableRequest,
    SegmentRequest,
    SecurityGroupRequest,
    SegmentationEngine,
    SubnetRequest,
    get_engine as get_seg_engine,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class NetworkAutomationError(Exception):
    """Base exception for network automation errors."""
    pass


class NetworkValidationError(NetworkAutomationError):
    """Validation failed for network automation operation."""
    pass


class NetworkConflictError(NetworkAutomationError):
    """Network configuration conflict."""
    pass


# ---------------------------------------------------------------------------
# Request types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class VPCRequest:
    """Request to create a VPC."""
    tenant_id: str
    cidr_block: str
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    name: str = ""
    secondary_cidrs: list[str] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PeeringTopologyRequest:
    """Request to set up a full peering topology."""
    tenant_id: str
    hub_vpc_id: str
    spoke_vpc_ids: list[str] = field(default_factory=list)
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    auto_accept: bool = True
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class HubSpokeRequest:
    """Request to set up a hub-and-spoke topology with transit gateway."""
    tenant_id: str
    hub_vpc_id: str
    spoke_vpc_ids: list[str] = field(default_factory=list)
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    transit_gateway_asn: int = 64512
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class MultiCloudRequest:
    """Request to set up multi-cloud connectivity."""
    tenant_id: str
    aws_vpc_id: str = ""
    azure_vnet_id: str = ""
    gcp_vpc_id: str = ""
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    bandwidth_mbps: int = 1000
    tags: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class NetworkAutomationEngine:
    """Unified network automation orchestrator.

    Coordinates all network automation engines to provide a single
    interface for managing multi-cloud network infrastructure.
    """

    def __init__(self) -> None:
        self._peering = get_peering_engine()
        self._transit_gateway = get_tgw_engine()
        self._expressroute = get_er_engine()
        self._interconnect = get_ic_engine()
        self._segmentation = get_seg_engine()
        self._listeners: list[Callable[[str, Any, str], None]] = []

    # -----------------------------------------------------------------------
    # VPC management
    # -----------------------------------------------------------------------

    def create_vpc(
        self,
        request: VPCRequest,
    ) -> OperationResult:
        """Create a new VPC."""
        try:
            validate_resource_id(request.tenant_id, "t-")
            validate_cidr(request.cidr_block)
            validate_region(request.region)
            for cidr in request.secondary_cidrs:
                validate_cidr(cidr)
        except ValueError as exc:
            return OperationResult(
                success=False,
                operation="create_vpc",
                resource_id="",
                resource_type="vpc",
                message=str(exc),
                error=str(exc),
            )

        vpc_id = f"vpc-{uuid.uuid4().hex[:17]}"
        now = datetime.now(timezone.utc).isoformat()

        cidrs = [VPCCidrBlock(cidr_block=request.cidr_block, primary=True)]
        for cidr in request.secondary_cidrs:
            cidrs.append(VPCCidrBlock(cidr_block=cidr, primary=False))

        vpc = VPC(
            vpc_id=vpc_id,
            tenant_id=request.tenant_id,
            cidr_blocks=cidrs,
            region=request.region,
            provider=request.provider,
            name=request.name,
            tags=request.tags,
            created_at=now,
            metadata=request.metadata,
        )

        # Register with all engines
        self._peering.register_vpc(vpc)
        self._transit_gateway.register_vpc(vpc)
        self._segmentation.register_vpc(vpc)

        self._notify("vpc", vpc, "created")

        return OperationResult(
            success=True,
            operation="create_vpc",
            resource_id=vpc_id,
            resource_type="vpc",
            message=f"VPC {vpc_id} created",
            state=vpc.state,
            metadata={
                "cidr_block": request.cidr_block,
                "region": request.region,
                "provider": request.provider.value,
            },
        )

    def get_vpc(self, vpc_id: str) -> VPC | None:
        """Get a VPC by ID."""
        vpc = self._peering.get_vpc(vpc_id)
        if vpc:
            return vpc
        vpc = self._transit_gateway.get_vpc(vpc_id)
        if vpc:
            return vpc
        return self._segmentation.get_vpc(vpc_id)

    def list_vpcs(self, tenant_id: str | None = None) -> list[VPC]:
        """List all VPCs."""
        vpcs = self._peering.list_vpcs(tenant_id)
        # Deduplicate
        seen: set[str] = set()
        unique: list[VPC] = []
        for vpc in vpcs:
            if vpc.vpc_id not in seen:
                seen.add(vpc.vpc_id)
                unique.append(vpc)
        return unique

    # -----------------------------------------------------------------------
    # Peering operations
    # -----------------------------------------------------------------------

    def create_peering(
        self,
        request: PeeringRequest,
    ) -> OperationResult:
        """Create a VPC peering connection."""
        result = self._peering.create_peering(request)
        if result.success:
            self._notify("vpc_peering", result, "created")
        return result

    def accept_peering(
        self,
        peering_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Accept a pending peering connection."""
        from .peering import PeeringAcceptance
        acceptance = PeeringAcceptance(
            peering_id=peering_id,
            tenant_id=tenant_id,
            accepter_vpc_id="",
        )
        result = self._peering.accept_peering(acceptance)
        if result.success:
            self._notify("vpc_peering", result, "accepted")
        return result

    def delete_peering(
        self,
        peering_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Delete a peering connection."""
        result = self._peering.delete_peering(peering_id, tenant_id)
        if result.success:
            self._notify("vpc_peering", result, "deleted")
        return result

    def get_peering(self, peering_id: str) -> VPCPeeringConnection | None:
        """Get a peering connection by ID."""
        return self._peering.get_peering(peering_id)

    def list_peerings(
        self,
        tenant_id: str | None = None,
        vpc_id: str | None = None,
        state: PeeringState | None = None,
    ) -> list[VPCPeeringConnection]:
        """List peering connections."""
        return self._peering.list_peerings(tenant_id, vpc_id, state)

    # -----------------------------------------------------------------------
    # Transit Gateway operations
    # -----------------------------------------------------------------------

    def create_transit_gateway(
        self,
        request: TransitGatewayRequest,
    ) -> OperationResult:
        """Create a transit gateway."""
        result = self._transit_gateway.create_gateway(request)
        if result.success:
            self._notify("transit_gateway", result, "created")
        return result

    def attach_vpc_to_tgw(
        self,
        request: AttachmentRequest,
    ) -> OperationResult:
        """Attach a VPC to a transit gateway."""
        result = self._transit_gateway.attach_vpc(request)
        if result.success:
            self._notify("transit_gateway_attachment", result, "attached")
        return result

    def detach_vpc_from_tgw(
        self,
        attachment_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Detach a VPC from a transit gateway."""
        result = self._transit_gateway.detach_vpc(attachment_id, tenant_id)
        if result.success:
            self._notify("transit_gateway_attachment", result, "detached")
        return result

    def delete_transit_gateway(
        self,
        gateway_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Delete a transit gateway."""
        result = self._transit_gateway.delete_gateway(gateway_id, tenant_id)
        if result.success:
            self._notify("transit_gateway", result, "deleted")
        return result

    def get_transit_gateway(self, gateway_id: str) -> TransitGateway | None:
        """Get a transit gateway by ID."""
        return self._transit_gateway.get_gateway(gateway_id)

    def list_transit_gateways(
        self,
        tenant_id: str | None = None,
        state: TransitGatewayState | None = None,
    ) -> list[TransitGateway]:
        """List transit gateways."""
        return self._transit_gateway.list_gateways(tenant_id, state)

    # -----------------------------------------------------------------------
    # ExpressRoute operations
    # -----------------------------------------------------------------------

    def create_expressroute(
        self,
        request: ExpressRouteRequest,
    ) -> OperationResult:
        """Create an ExpressRoute circuit."""
        result = self._expressroute.create_circuit(request)
        if result.success:
            self._notify("expressroute_circuit", result, "created")
        return result

    def add_expressroute_peering(
        self,
        request: ExpressRoutePeeringRequest,
    ) -> OperationResult:
        """Add peering to an ExpressRoute circuit."""
        result = self._expressroute.add_peering(request)
        if result.success:
            self._notify("expressroute_peering", result, "created")
        return result

    def delete_expressroute(
        self,
        circuit_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Delete an ExpressRoute circuit."""
        result = self._expressroute.delete_circuit(circuit_id, tenant_id)
        if result.success:
            self._notify("expressroute_circuit", result, "deleted")
        return result

    def get_expressroute(self, circuit_id: str) -> ExpressRouteCircuit | None:
        """Get an ExpressRoute circuit by ID."""
        return self._expressroute.get_circuit(circuit_id)

    def list_expressroutes(
        self,
        tenant_id: str | None = None,
    ) -> list[ExpressRouteCircuit]:
        """List ExpressRoute circuits."""
        return self._expressroute.list_circuits(tenant_id)

    # -----------------------------------------------------------------------
    # Cloud Interconnect operations
    # -----------------------------------------------------------------------

    def create_interconnect(
        self,
        request: InterconnectRequest,
    ) -> OperationResult:
        """Create a Cloud Interconnect."""
        result = self._interconnect.create_interconnect(request)
        if result.success:
            self._notify("cloud_interconnect", result, "created")
        return result

    def create_interconnect_attachment(
        self,
        request: InterconnectAttachmentRequest,
    ) -> OperationResult:
        """Create an interconnect attachment."""
        result = self._interconnect.create_attachment(request)
        if result.success:
            self._notify("interconnect_attachment", result, "created")
        return result

    def delete_interconnect(
        self,
        interconnect_id: str,
        tenant_id: str,
    ) -> OperationResult:
        """Delete a Cloud Interconnect."""
        result = self._interconnect.delete_interconnect(interconnect_id, tenant_id)
        if result.success:
            self._notify("cloud_interconnect", result, "deleted")
        return result

    def get_interconnect(self, interconnect_id: str) -> CloudInterconnect | None:
        """Get a Cloud Interconnect by ID."""
        return self._interconnect.get_interconnect(interconnect_id)

    def list_interconnects(
        self,
        tenant_id: str | None = None,
    ) -> list[CloudInterconnect]:
        """List Cloud Interconnects."""
        return self._interconnect.list_interconnects(tenant_id)

    # -----------------------------------------------------------------------
    # Segmentation operations
    # -----------------------------------------------------------------------

    def create_segment(
        self,
        request: SegmentRequest,
    ) -> OperationResult:
        """Create a network segment."""
        result = self._segmentation.create_segment(request)
        if result.success:
            self._notify("network_segment", result, "created")
        return result

    def create_security_group(
        self,
        request: SecurityGroupRequest,
    ) -> OperationResult:
        """Create a security group."""
        result = self._segmentation.create_security_group(request)
        if result.success:
            self._notify("security_group", result, "created")
        return result

    def create_route_table(
        self,
        request: RouteTableRequest,
    ) -> OperationResult:
        """Create a route table."""
        result = self._segmentation.create_route_table(request)
        if result.success:
            self._notify("route_table", result, "created")
        return result

    def add_route(
        self,
        request: RouteRequest,
    ) -> OperationResult:
        """Add a route to a route table."""
        result = self._segmentation.add_route(request)
        if result.success:
            self._notify("route", result, "created")
        return result

    def create_subnet(
        self,
        request: SubnetRequest,
    ) -> OperationResult:
        """Create a subnet."""
        result = self._segmentation.create_subnet(request)
        if result.success:
            self._notify("subnet", result, "created")
        return result

    def get_segment(self, segment_id: str) -> NetworkSegment | None:
        """Get a network segment by ID."""
        return self._segmentation.get_segment(segment_id)

    def list_segments(
        self,
        tenant_id: str | None = None,
    ) -> list[NetworkSegment]:
        """List network segments."""
        return self._segmentation.list_segments(tenant_id)

    def get_security_group(self, group_id: str) -> SecurityGroup | None:
        """Get a security group by ID."""
        return self._segmentation.get_security_group(group_id)

    def list_security_groups(
        self,
        tenant_id: str | None = None,
    ) -> list[SecurityGroup]:
        """List security groups."""
        return self._segmentation.list_security_groups(tenant_id)

    def list_subnets(
        self,
        tenant_id: str | None = None,
    ) -> list[Subnet]:
        """List subnets."""
        return self._segmentation.list_subnets(tenant_id)

    # -----------------------------------------------------------------------
    # Composite operations
    # -----------------------------------------------------------------------

    def setup_peering_topology(
        self,
        request: PeeringTopologyRequest,
    ) -> list[OperationResult]:
        """Set up a full mesh or hub-spoke peering topology."""
        results: list[OperationResult] = []

        for spoke_vpc_id in request.spoke_vpc_ids:
            peering_request = PeeringRequest(
                requester_vpc_id=request.hub_vpc_id,
                accepter_vpc_id=spoke_vpc_id,
                tenant_id=request.tenant_id,
                region=request.region,
                provider=request.provider,
                auto_accept=request.auto_accept,
                tags=request.tags,
            )
            result = self.create_peering(peering_request)
            results.append(result)

        return results

    def setup_hub_spoke_topology(
        self,
        request: HubSpokeRequest,
    ) -> list[OperationResult]:
        """Set up a hub-and-spoke topology with transit gateway."""
        results: list[OperationResult] = []

        # Create transit gateway
        tgw_request = TransitGatewayRequest(
            tenant_id=request.tenant_id,
            amazon_side_asn=request.transit_gateway_asn,
            region=request.region,
            provider=request.provider,
            tags=request.tags,
        )
        tgw_result = self.create_transit_gateway(tgw_request)
        results.append(tgw_result)

        if not tgw_result.success:
            return results

        # Attach hub VPC
        hub_attachment = AttachmentRequest(
            transit_gateway_id=tgw_result.resource_id,
            vpc_id=request.hub_vpc_id,
            tenant_id=request.tenant_id,
            region=request.region,
            provider=request.provider,
            tags=request.tags,
        )
        hub_result = self.attach_vpc_to_tgw(hub_attachment)
        results.append(hub_result)

        # Attach spoke VPCs
        for spoke_vpc_id in request.spoke_vpc_ids:
            spoke_attachment = AttachmentRequest(
                transit_gateway_id=tgw_result.resource_id,
                vpc_id=spoke_vpc_id,
                tenant_id=request.tenant_id,
                region=request.region,
                provider=request.provider,
                tags=request.tags,
            )
            spoke_result = self.attach_vpc_to_tgw(spoke_attachment)
            results.append(spoke_result)

        return results

    def setup_multi_cloud_connectivity(
        self,
        request: MultiCloudRequest,
    ) -> list[OperationResult]:
        """Set up multi-cloud connectivity."""
        results: list[OperationResult] = []

        # Create ExpressRoute circuit for Azure connectivity
        if request.azure_vnet_id:
            er_request = ExpressRouteRequest(
                tenant_id=request.tenant_id,
                bandwidth_mbps=request.bandwidth_mbps,
                location=request.region,
                tags=request.tags,
            )
            er_result = self.create_expressroute(er_request)
            results.append(er_result)

        # Create Cloud Interconnect for GCP connectivity
        if request.gcp_vpc_id:
            ic_request = InterconnectRequest(
                tenant_id=request.tenant_id,
                bandwidth_mbps=request.bandwidth_mbps,
                location=request.region,
                provider=CloudProvider.GCP,
                tags=request.tags,
            )
            ic_result = self.create_interconnect(ic_request)
            results.append(ic_result)

        return results

    # -----------------------------------------------------------------------
    # Topology views
    # -----------------------------------------------------------------------

    def get_topology(self, tenant_id: str) -> TopologyView:
        """Get the full network topology for a tenant."""
        return TopologyView(
            tenant_id=tenant_id,
            vpcs=self.list_vpcs(tenant_id),
            peerings=self.list_peerings(tenant_id),
            transit_gateways=self.list_transit_gateways(tenant_id),
            expressroute_circuits=self.list_expressroutes(tenant_id),
            interconnects=self.list_interconnects(tenant_id),
            segments=self.list_segments(tenant_id),
            route_tables=self._segmentation.list_route_tables(tenant_id),
            security_groups=self.list_security_groups(tenant_id),
        )

    def get_connectivity_matrix(
        self,
        tenant_id: str,
    ) -> dict[str, dict[str, str]]:
        """Get connectivity matrix between all VPCs."""
        vpcs = self.list_vpcs(tenant_id)
        peerings = self.list_peerings(tenant_id, state=PeeringState.ACTIVE)

        matrix: dict[str, dict[str, str]] = {
            vpc.vpc_id: {other.vpc_id: "none" for other in vpcs}
            for vpc in vpcs
        }

        for peering in peerings:
            matrix[peering.requester_vpc_id][peering.accepter_vpc_id] = "peered"
            matrix[peering.accepter_vpc_id][peering.requester_vpc_id] = "peered"

        return matrix

    # -----------------------------------------------------------------------
    # Event listeners
    # -----------------------------------------------------------------------

    def add_listener(
        self,
        listener: Callable[[str, Any, str], None],
    ) -> None:
        """Add an event listener."""
        self._listeners.append(listener)

    def remove_listener(
        self,
        listener: Callable[[str, Any, str], None],
    ) -> None:
        """Remove an event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self, resource_type: str, resource: Any, event: str) -> None:
        """Notify all listeners of an event."""
        for listener in self._listeners:
            try:
                listener(resource_type, resource, event)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_engine: NetworkAutomationEngine | None = None


def get_engine() -> NetworkAutomationEngine:
    """Return the process-wide default network automation engine."""
    global _default_engine
    if _default_engine is None:
        _default_engine = NetworkAutomationEngine()
    return _default_engine
