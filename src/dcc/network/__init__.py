"""Network automation engine for Data Center Commander.

Provides unified multi-cloud network automation for:
- VPC peering (AWS, Azure, GCP)
- Transit Gateway (AWS, Azure Virtual WAN, GCP Cloud Router)
- ExpressRoute (Azure)
- Cloud Interconnect (GCP, AWS Direct Connect)
- Network segmentation (VLAN, VXLAN, security groups, route tables)

Pure stdlib implementation: no external dependencies.

Usage:
    from dcc.network import NetworkAutomationEngine, VPCRequest, PeeringRequest

    engine = NetworkAutomationEngine()

    # Create a VPC
    result = engine.create_vpc(VPCRequest(
        tenant_id="t-12345678-1234-1234-1234-123456789012",
        cidr_block="10.0.0.0/16",
        region="us-east-1",
    ))

    # Create a peering connection
    result = engine.create_peering(PeeringRequest(
        requester_vpc_id="vpc-abc123",
        accepter_vpc_id="vpc-def456",
        tenant_id="t-12345678-1234-1234-1234-123456789012",
    ))
"""
from __future__ import annotations

from .models import (
    CloudInterconnect,
    CloudProvider,
    ExpressRouteCircuit,
    ExpressRoutePeering,
    ExpressRouteState,
    InterconnectAttachment,
    InterconnectState,
    NetworkACL,
    NetworkACLRule,
    NetworkSegment,
    OperationResult,
    PeeringState,
    Protocol,
    Route,
    RouteState,
    RouteTable,
    SecurityGroup,
    SecurityGroupRule,
    SegmentationType,
    Subnet,
    TopologyView,
    TransitGateway,
    TransitGatewayAttachment,
    TransitGatewayState,
    ValidationResult,
    VPC,
    VPCCidrBlock,
    VPCPeeringConnection,
)
from .peering import (
    PeeringAcceptance,
    PeeringConflictError,
    PeeringError,
    PeeringNotFoundError,
    PeeringRequest,
    PeeringValidationError,
    VPCPeeringEngine,
    check_cidr_overlap,
    find_cidr_overlaps,
)
from .transit_gateway import (
    AttachmentRequest,
    TransitGatewayConflictError,
    TransitGatewayEngine,
    TransitGatewayError,
    TransitGatewayNotFoundError,
    TransitGatewayRequest,
    TransitGatewayValidationError,
)
from .expressroute import (
    ExpressRouteConflictError,
    ExpressRouteEngine,
    ExpressRouteError,
    ExpressRouteNotFoundError,
    ExpressRoutePeeringRequest,
    ExpressRouteRequest,
    ExpressRouteValidationError,
    PeeringConfigError,
)
from .interconnect import (
    AttachmentError,
    CloudInterconnectEngine,
    InterconnectAttachmentRequest,
    InterconnectConflictError,
    InterconnectError,
    InterconnectNotFoundError,
    InterconnectRequest,
    InterconnectValidationError,
)
from .segmentation import (
    RouteRequest,
    RouteTableRequest,
    SegmentRequest,
    SegmentationConflictError,
    SegmentationEngine,
    SegmentationError,
    SegmentationNotFoundError,
    SegmentationValidationError,
    RouteTableError,
    SecurityGroupError,
    SecurityGroupRequest,
    SecurityGroupRuleRequest,
    SubnetRequest,
)
from .orchestrator import (
    HubSpokeRequest,
    MultiCloudRequest,
    NetworkAutomationEngine,
    NetworkAutomationError,
    NetworkConflictError,
    NetworkValidationError,
    PeeringTopologyRequest,
    VPCRequest,
    get_engine,
)

__all__ = [
    # Models
    "CloudInterconnect",
    "CloudProvider",
    "ExpressRouteCircuit",
    "ExpressRoutePeering",
    "ExpressRouteState",
    "InterconnectAttachment",
    "InterconnectState",
    "NetworkACL",
    "NetworkACLRule",
    "NetworkSegment",
    "OperationResult",
    "PeeringState",
    "Protocol",
    "Route",
    "RouteState",
    "RouteTable",
    "SecurityGroup",
    "SecurityGroupRule",
    "SegmentationType",
    "Subnet",
    "TopologyView",
    "TransitGateway",
    "TransitGatewayAttachment",
    "TransitGatewayState",
    "ValidationResult",
    "VPC",
    "VPCCidrBlock",
    "VPCPeeringConnection",
    # Peering
    "PeeringAcceptance",
    "PeeringConflictError",
    "PeeringError",
    "PeeringNotFoundError",
    "PeeringRequest",
    "PeeringValidationError",
    "VPCPeeringEngine",
    "check_cidr_overlap",
    "find_cidr_overlaps",
    # Transit Gateway
    "AttachmentRequest",
    "TransitGatewayConflictError",
    "TransitGatewayEngine",
    "TransitGatewayError",
    "TransitGatewayNotFoundError",
    "TransitGatewayValidationError",
    # ExpressRoute
    "ExpressRouteConflictError",
    "ExpressRouteEngine",
    "ExpressRouteError",
    "ExpressRouteNotFoundError",
    "ExpressRoutePeeringRequest",
    "ExpressRouteRequest",
    "ExpressRouteValidationError",
    "PeeringConfigError",
    # Interconnect
    "AttachmentError",
    "CloudInterconnectEngine",
    "InterconnectAttachmentRequest",
    "InterconnectConflictError",
    "InterconnectError",
    "InterconnectNotFoundError",
    "InterconnectRequest",
    "InterconnectValidationError",
    # Segmentation
    "RouteRequest",
    "RouteTableRequest",
    "SegmentRequest",
    "SegmentationConflictError",
    "SegmentationEngine",
    "SegmentationError",
    "SegmentationNotFoundError",
    "SegmentationValidationError",
    "SecurityGroupError",
    "SecurityGroupRequest",
    "SecurityGroupRuleRequest",
    "SubnetRequest",
    # Orchestrator
    "HubSpokeRequest",
    "MultiCloudRequest",
    "NetworkAutomationEngine",
    "NetworkAutomationError",
    "NetworkConflictError",
    "NetworkValidationError",
    "PeeringTopologyRequest",
    "VPCRequest",
    "get_engine",
]
