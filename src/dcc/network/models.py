"""Data models for network automation resources.

Pure stdlib implementation: no external dependencies.
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CloudProvider(str, Enum):
    """Supported cloud providers."""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"


class PeeringState(str, Enum):
    """State of a VPC peering connection."""
    PENDING_ACCEPTANCE = "pending_acceptance"
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    DELETED = "deleted"
    EXPIRED = "expired"
    REJECTED = "rejected"
    PROVISIONING = "provisioning"


class TransitGatewayState(str, Enum):
    """State of a transit gateway."""
    PENDING = "pending"
    AVAILABLE = "available"
    MODIFYING = "modifying"
    DELETING = "deleting"
    DELETED = "deleted"
    FAILED = "failed"


class ExpressRouteState(str, Enum):
    """State of an ExpressRoute circuit."""
    PROVISIONING = "provisioning"
    PROVISIONED = "provisioned"
    NOT_PROVISIONED = "not_provisioned"
    DEPROVISIONING = "deprovisioning"
    DEPROVISIONED = "deprovisioned"
    FAILED = "failed"


class InterconnectState(str, Enum):
    """State of a Cloud Interconnect."""
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    DELETED = "deleted"


class SegmentationType(str, Enum):
    """Type of network segmentation."""
    VLAN = "vlan"
    VXLAN = "vxlan"
    SUBNET = "subnet"
    SECURITY_GROUP = "security_group"
    NETWORK_ACL = "network_acl"
    ROUTE_TABLE = "route_table"


class RouteState(str, Enum):
    """State of a route."""
    ACTIVE = "active"
    BLACKHOLE = "blackhole"
    PENDING = "pending"
    DELETED = "deleted"


class Protocol(str, Enum):
    """Network protocol."""
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    ANY = "any"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_CIDR_RE = re.compile(
    r"^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$"
    r"|^([0-9a-fA-F:]+)/\d{1,3}$"
)

_VLAN_ID_MIN = 1
_VLAN_ID_MAX = 4094

_VXLAN_VNI_MIN = 1
_VXLAN_VNI_MAX = 16777215


def validate_cidr(cidr: str) -> str:
    """Validate a CIDR notation string."""
    try:
        ipaddress.ip_network(cidr, strict=False)
    except ValueError as exc:
        raise ValueError(f"invalid CIDR: {cidr}") from exc
    return cidr


def validate_vlan_id(vlan_id: int) -> int:
    """Validate a VLAN ID (1-4094)."""
    if not isinstance(vlan_id, int) or isinstance(vlan_id, bool):
        raise ValueError("VLAN ID must be an integer")
    if not _VLAN_ID_MIN <= vlan_id <= _VLAN_ID_MAX:
        raise ValueError(f"VLAN ID must be between {_VLAN_ID_MIN} and {_VLAN_ID_MAX}")
    return vlan_id


def validate_vxlan_vni(vni: int) -> int:
    """Validate a VXLAN VNI (1-16777215)."""
    if not isinstance(vni, int) or isinstance(vni, bool):
        raise ValueError("VXLAN VNI must be an integer")
    if not _VXLAN_VNI_MIN <= vni <= _VXLAN_VNI_MAX:
        raise ValueError(f"VXLAN VNI must be between {_VXLAN_VNI_MIN} and {_VXLAN_VNI_MAX}")
    return vni


def validate_resource_id(resource_id: str, prefix: str = "") -> str:
    """Validate a resource identifier."""
    if not isinstance(resource_id, str) or not resource_id.strip():
        raise ValueError("resource_id must be a non-empty string")
    if len(resource_id) > 256:
        raise ValueError("resource_id must be at most 256 characters")
    if prefix and not resource_id.startswith(prefix):
        raise ValueError(f"resource_id must start with '{prefix}'")
    return resource_id


def validate_region(region: str) -> str:
    """Validate a cloud region string."""
    if not isinstance(region, str) or not region.strip():
        raise ValueError("region must be a non-empty string")
    if len(region) > 64:
        raise ValueError("region must be at most 64 characters")
    return region.strip()


def validate_asn(asn: int) -> int:
    """Validate an Autonomous System Number (1-4294967295)."""
    if not isinstance(asn, int) or isinstance(asn, bool):
        raise ValueError("ASN must be an integer")
    if not 1 <= asn <= 4294967295:
        raise ValueError("ASN must be between 1 and 4294967295")
    return asn


def validate_bandwidth_mbps(bandwidth: int) -> int:
    """Validate bandwidth in Mbps (positive integer)."""
    if not isinstance(bandwidth, int) or isinstance(bandwidth, bool):
        raise ValueError("bandwidth must be an integer")
    if bandwidth <= 0:
        raise ValueError("bandwidth must be positive")
    return bandwidth


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class VPCCidrBlock:
    """A CIDR block associated with a VPC."""
    cidr_block: str
    primary: bool = False
    state: str = "associated"

    def __post_init__(self) -> None:
        validate_cidr(self.cidr_block)


@dataclass(slots=True)
class VPC:
    """Represents a Virtual Private Cloud."""
    vpc_id: str
    tenant_id: str
    cidr_blocks: list[VPCCidrBlock] = field(default_factory=list)
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    name: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    state: str = "available"
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_id(self.vpc_id, "vpc-")
        validate_resource_id(self.tenant_id, "t-")
        validate_region(self.region)

    @property
    def primary_cidr(self) -> str | None:
        """Return the primary CIDR block."""
        for block in self.cidr_blocks:
            if block.primary:
                return block.cidr_block
        return self.cidr_blocks[0].cidr_block if self.cidr_blocks else None


@dataclass(slots=True)
class VPCPeeringConnection:
    """Represents a VPC peering connection."""
    peering_id: str
    requester_vpc_id: str
    accepter_vpc_id: str
    tenant_id: str
    state: PeeringState = PeeringState.PENDING_ACCEPTANCE
    requester_cidr: str = ""
    accepter_cidr: str = ""
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    name: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    accepted_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_id(self.peering_id, "pcx-")
        validate_resource_id(self.requester_vpc_id, "vpc-")
        validate_resource_id(self.accepter_vpc_id, "vpc-")
        validate_resource_id(self.tenant_id, "t-")
        validate_region(self.region)
        if self.requester_cidr:
            validate_cidr(self.requester_cidr)
        if self.accepter_cidr:
            validate_cidr(self.accepter_cidr)


@dataclass(slots=True)
class TransitGatewayAttachment:
    """Represents a transit gateway attachment."""
    attachment_id: str
    transit_gateway_id: str
    vpc_id: str
    tenant_id: str
    state: str = "available"
    attachment_type: str = "vpc"
    subnet_ids: list[str] = field(default_factory=list)
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    name: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_id(self.attachment_id, "tgw-attach-")
        validate_resource_id(self.transit_gateway_id, "tgw-")
        validate_resource_id(self.vpc_id, "vpc-")
        validate_resource_id(self.tenant_id, "t-")
        validate_region(self.region)


@dataclass(slots=True)
class TransitGateway:
    """Represents an AWS Transit Gateway."""
    transit_gateway_id: str
    tenant_id: str
    state: TransitGatewayState = TransitGatewayState.PENDING
    amazon_side_asn: int = 64512
    auto_accept_shared_attachments: str = "disable"
    default_route_table_association: str = "enable"
    default_route_table_propagation: str = "enable"
    dns_support: str = "enable"
    vpn_ecmp_support: str = "enable"
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    name: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    attachments: list[TransitGatewayAttachment] = field(default_factory=list)
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_id(self.transit_gateway_id, "tgw-")
        validate_resource_id(self.tenant_id, "t-")
        validate_region(self.region)
        validate_asn(self.amazon_side_asn)


@dataclass(slots=True)
class ExpressRouteCircuit:
    """Represents an Azure ExpressRoute circuit."""
    circuit_id: str
    tenant_id: str
    state: ExpressRouteState = ExpressRouteState.PROVISIONING
    service_provider: str = ""
    peering_location: str = ""
    bandwidth_mbps: int = 1000
    sku_tier: str = "Standard"
    sku_family: str = "MeteredData"
    location: str = ""
    provider: CloudProvider = CloudProvider.AZURE
    name: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    peerings: list[ExpressRoutePeering] = field(default_factory=list)
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_id(self.circuit_id, "erc-")
        validate_resource_id(self.tenant_id, "t-")
        validate_region(self.location)
        validate_bandwidth_mbps(self.bandwidth_mbps)


@dataclass(slots=True)
class ExpressRoutePeering:
    """Represents an ExpressRoute peering configuration."""
    peering_id: str
    circuit_id: str
    peering_type: str = "AzurePrivatePeering"
    peer_asn: int = 65001
    primary_peer_address_prefix: str = ""
    secondary_peer_address_prefix: str = ""
    vlan_id: int = 0
    state: str = "provisioning"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_id(self.peering_id, "erp-")
        validate_resource_id(self.circuit_id, "erc-")
        validate_asn(self.peer_asn)
        if self.vlan_id:
            validate_vlan_id(self.vlan_id)


@dataclass(slots=True)
class CloudInterconnect:
    """Represents a GCP Cloud Interconnect."""
    interconnect_id: str
    tenant_id: str
    state: InterconnectState = InterconnectState.PENDING
    interconnect_type: str = "DEDICATED"
    link_type: str = "LINK_TYPE_ETHERNET_10G_LR"
    location: str = ""
    bandwidth_mbps: int = 10000
    provider: CloudProvider = CloudProvider.GCP
    name: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    attachments: list[InterconnectAttachment] = field(default_factory=list)
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_id(self.interconnect_id, "ic-")
        validate_resource_id(self.tenant_id, "t-")
        validate_region(self.location)
        validate_bandwidth_mbps(self.bandwidth_mbps)


@dataclass(slots=True)
class InterconnectAttachment:
    """Represents a Cloud Interconnect attachment (VLAN)."""
    attachment_id: str
    interconnect_id: str
    tenant_id: str
    state: str = "pending"
    vlan_tag: int = 0
    bgp_session_enabled: bool = False
    peer_ip: str = ""
    cloud_router_ip: str = ""
    region: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_id(self.attachment_id, "ica-")
        validate_resource_id(self.interconnect_id, "ic-")
        validate_resource_id(self.tenant_id, "t-")
        validate_region(self.region)
        if self.vlan_tag:
            validate_vlan_id(self.vlan_tag)


@dataclass(slots=True)
class SecurityGroupRule:
    """Represents a security group rule."""
    rule_id: str
    protocol: Protocol
    from_port: int
    to_port: int
    cidr_blocks: list[str] = field(default_factory=list)
    source_security_group_ids: list[str] = field(default_factory=list)
    description: str = ""
    direction: str = "ingress"

    def __post_init__(self) -> None:
        validate_resource_id(self.rule_id, "sgr-")
        if not 0 <= self.from_port <= 65535:
            raise ValueError("from_port must be 0-65535")
        if not 0 <= self.to_port <= 65535:
            raise ValueError("to_port must be 0-65535")
        if self.from_port > self.to_port:
            raise ValueError("from_port must be <= to_port")
        for cidr in self.cidr_blocks:
            validate_cidr(cidr)


@dataclass(slots=True)
class SecurityGroup:
    """Represents a network security group."""
    group_id: str
    tenant_id: str
    name: str = ""
    description: str = ""
    vpc_id: str = ""
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    rules: list[SecurityGroupRule] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    state: str = "available"
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_id(self.group_id, "sg-")
        validate_resource_id(self.tenant_id, "t-")
        validate_region(self.region)
        if self.vpc_id:
            validate_resource_id(self.vpc_id, "vpc-")


@dataclass(slots=True)
class NetworkACLRule:
    """Represents a network ACL rule."""
    rule_id: str
    rule_number: int
    protocol: Protocol
    action: str  # "allow" or "deny"
    cidr_block: str
    from_port: int = 0
    to_port: int = 0
    direction: str = "ingress"

    def __post_init__(self) -> None:
        validate_resource_id(self.rule_id, "nacl-")
        if not 1 <= self.rule_number <= 32766:
            raise ValueError("rule_number must be 1-32766")
        validate_cidr(self.cidr_block)
        if self.action not in ("allow", "deny"):
            raise ValueError("action must be 'allow' or 'deny'")


@dataclass(slots=True)
class NetworkACL:
    """Represents a network ACL."""
    acl_id: str
    tenant_id: str
    vpc_id: str = ""
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    rules: list[NetworkACLRule] = field(default_factory=list)
    subnet_ids: list[str] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    state: str = "available"
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_id(self.acl_id, "acl-")
        validate_resource_id(self.tenant_id, "t-")
        validate_region(self.region)
        if self.vpc_id:
            validate_resource_id(self.vpc_id, "vpc-")


@dataclass(slots=True)
class Route:
    """Represents a route in a route table."""
    route_id: str
    destination_cidr: str
    target: str
    state: RouteState = RouteState.ACTIVE
    target_type: str = "transit_gateway"  # transit_gateway, vpc_peering, nat_gateway, internet_gateway, etc.
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_id(self.route_id, "rt-")
        validate_cidr(self.destination_cidr)


@dataclass(slots=True)
class RouteTable:
    """Represents a route table."""
    route_table_id: str
    tenant_id: str
    vpc_id: str = ""
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    routes: list[Route] = field(default_factory=list)
    subnet_ids: list[str] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    state: str = "available"
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_id(self.route_table_id, "rtb-")
        validate_resource_id(self.tenant_id, "t-")
        validate_region(self.region)
        if self.vpc_id:
            validate_resource_id(self.vpc_id, "vpc-")


@dataclass(slots=True)
class Subnet:
    """Represents a network subnet."""
    subnet_id: str
    tenant_id: str
    vpc_id: str
    cidr_block: str
    availability_zone: str = ""
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    name: str = ""
    map_public_ip_on_launch: bool = False
    route_table_id: str = ""
    network_acl_id: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    state: str = "available"
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_id(self.subnet_id, "subnet-")
        validate_resource_id(self.tenant_id, "t-")
        validate_resource_id(self.vpc_id, "vpc-")
        validate_cidr(self.cidr_block)
        validate_region(self.region)


@dataclass(slots=True)
class NetworkSegment:
    """Represents a network segment (VLAN/VXLAN/subnet)."""
    segment_id: str
    tenant_id: str
    segmentation_type: SegmentationType
    name: str = ""
    vlan_id: int | None = None
    vxlan_vni: int | None = None
    cidr_block: str = ""
    vpc_id: str = ""
    region: str = ""
    provider: CloudProvider = CloudProvider.AWS
    security_group_ids: list[str] = field(default_factory=list)
    subnet_ids: list[str] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    state: str = "active"
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_id(self.segment_id, "seg-")
        validate_resource_id(self.tenant_id, "t-")
        validate_region(self.region)
        if self.vlan_id is not None:
            validate_vlan_id(self.vlan_id)
        if self.vxlan_vni is not None:
            validate_vxlan_vni(self.vxlan_vni)
        if self.cidr_block:
            validate_cidr(self.cidr_block)
        if self.vpc_id:
            validate_resource_id(self.vpc_id, "vpc-")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class OperationResult:
    """Result of a network automation operation."""
    success: bool
    operation: str
    resource_id: str
    resource_type: str
    message: str = ""
    state: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    timestamp: str = ""


@dataclass(slots=True)
class ValidationResult:
    """Result of a validation check."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TopologyView:
    """A view of the network topology."""
    tenant_id: str
    vpcs: list[VPC] = field(default_factory=list)
    peerings: list[VPCPeeringConnection] = field(default_factory=list)
    transit_gateways: list[TransitGateway] = field(default_factory=list)
    expressroute_circuits: list[ExpressRouteCircuit] = field(default_factory=list)
    interconnects: list[CloudInterconnect] = field(default_factory=list)
    segments: list[NetworkSegment] = field(default_factory=list)
    route_tables: list[RouteTable] = field(default_factory=list)
    security_groups: list[SecurityGroup] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
