"""Tests for the network automation engine."""
from __future__ import annotations

import unittest

from dcc.network import (
    AttachmentError,
    CloudInterconnectEngine,
    CloudProvider,
    ExpressRouteEngine,
    ExpressRoutePeeringRequest,
    ExpressRouteRequest,
    ExpressRouteState,
    HubSpokeRequest,
    InterconnectAttachmentRequest,
    InterconnectRequest,
    InterconnectState,
    MultiCloudRequest,
    NetworkAutomationEngine,
    NetworkValidationError,
    OperationResult,
    PeeringConflictError,
    PeeringNotFoundError,
    PeeringRequest,
    PeeringState,
    PeeringTopologyRequest,
    PeeringValidationError,
    RouteRequest,
    RouteState,
    RouteTableRequest,
    SecurityGroupRequest,
    SegmentRequest,
    SegmentationConflictError,
    SegmentationEngine,
    SegmentationNotFoundError,
    SegmentationType,
    SegmentationValidationError,
    SubnetRequest,
    TopologyView,
    TransitGatewayEngine,
    TransitGatewayNotFoundError,
    TransitGatewayRequest,
    TransitGatewayState,
    TransitGatewayValidationError,
    VPCPeeringConnection,
    VPCPeeringEngine,
    VPCRequest,
    VPCCidrBlock,
    VPC,
    check_cidr_overlap,
    find_cidr_overlaps,
    get_engine,
)


class TestCidrOverlap(unittest.TestCase):
    """Test CIDR overlap detection."""

    def test_overlapping_cidrs(self) -> None:
        self.assertTrue(check_cidr_overlap("10.0.0.0/16", "10.0.1.0/24"))
        self.assertTrue(check_cidr_overlap("10.0.0.0/8", "10.0.0.0/16"))

    def test_non_overlapping_cidrs(self) -> None:
        self.assertFalse(check_cidr_overlap("10.0.0.0/16", "10.1.0.0/16"))
        self.assertFalse(check_cidr_overlap("192.168.0.0/24", "10.0.0.0/8"))

    def test_find_overlaps(self) -> None:
        overlaps = find_cidr_overlaps(
            ["10.0.0.0/16", "192.168.0.0/24"],
            ["10.0.1.0/24", "172.16.0.0/12"],
        )
        self.assertEqual(len(overlaps), 1)
        self.assertEqual(overlaps[0], ("10.0.0.0/16", "10.0.1.0/24"))


class TestVPCPeeringEngine(unittest.TestCase):
    """Test VPC peering engine."""

    def setUp(self) -> None:
        self.engine = VPCPeeringEngine()
        self.tid = "t-12345678-1234-1234-1234-123456789012"
        self.vpc1 = VPC(
            vpc_id="vpc-aaa111",
            tenant_id=self.tid,
            cidr_blocks=[VPCCidrBlock(cidr_block="10.0.0.0/16", primary=True)],
            region="us-east-1",
        )
        self.vpc2 = VPC(
            vpc_id="vpc-bbb222",
            tenant_id=self.tid,
            cidr_blocks=[VPCCidrBlock(cidr_block="10.1.0.0/16", primary=True)],
            region="us-east-1",
        )
        self.engine.register_vpc(self.vpc1)
        self.engine.register_vpc(self.vpc2)

    def test_create_peering(self) -> None:
        result = self.engine.create_peering(PeeringRequest(
            requester_vpc_id="vpc-aaa111",
            accepter_vpc_id="vpc-bbb222",
            tenant_id=self.tid,
            region="us-east-1",
            auto_accept=True,
        ))
        self.assertTrue(result.success)
        self.assertEqual(result.state, PeeringState.ACTIVE.value)
        self.assertTrue(result.resource_id.startswith("pcx-"))

    def test_create_peering_cidr_overlap(self) -> None:
        vpc3 = VPC(
            vpc_id="vpc-ccc333",
            tenant_id=self.tid,
            cidr_blocks=[VPCCidrBlock(cidr_block="10.0.0.0/16", primary=True)],
            region="us-east-1",
        )
        self.engine.register_vpc(vpc3)
        result = self.engine.create_peering(PeeringRequest(
            requester_vpc_id="vpc-aaa111",
            accepter_vpc_id="vpc-ccc333",
            tenant_id=self.tid,
            region="us-east-1",
        ))
        self.assertFalse(result.success)
        self.assertIn("CIDR overlap", result.error)

    def test_create_peering_self(self) -> None:
        result = self.engine.create_peering(PeeringRequest(
            requester_vpc_id="vpc-aaa111",
            accepter_vpc_id="vpc-aaa111",
            tenant_id=self.tid,
            region="us-east-1",
        ))
        self.assertFalse(result.success)

    def test_accept_peering(self) -> None:
        created = self.engine.create_peering(PeeringRequest(
            requester_vpc_id="vpc-aaa111",
            accepter_vpc_id="vpc-bbb222",
            tenant_id=self.tid,
            region="us-east-1",
            auto_accept=False,
        ))
        self.assertEqual(created.state, PeeringState.PENDING_ACCEPTANCE.value)

        from dcc.network import PeeringAcceptance
        result = self.engine.accept_peering(PeeringAcceptance(
            peering_id=created.resource_id,
            tenant_id=self.tid,
            accepter_vpc_id="vpc-bbb222",
        ))
        self.assertTrue(result.success)
        self.assertEqual(result.state, PeeringState.ACTIVE.value)

    def test_delete_peering(self) -> None:
        created = self.engine.create_peering(PeeringRequest(
            requester_vpc_id="vpc-aaa111",
            accepter_vpc_id="vpc-bbb222",
            tenant_id=self.tid,
            region="us-east-1",
            auto_accept=True,
        ))
        result = self.engine.delete_peering(created.resource_id, self.tid)
        self.assertTrue(result.success)
        self.assertIsNone(self.engine.get_peering(created.resource_id))

    def test_list_peerings(self) -> None:
        self.engine.create_peering(PeeringRequest(
            requester_vpc_id="vpc-aaa111",
            accepter_vpc_id="vpc-bbb222",
            tenant_id=self.tid,
            region="us-east-1",
            auto_accept=True,
        ))
        peerings = self.engine.list_peerings(tenant_id=self.tid)
        self.assertEqual(len(peerings), 1)

    def test_get_peering_topology(self) -> None:
        self.engine.create_peering(PeeringRequest(
            requester_vpc_id="vpc-aaa111",
            accepter_vpc_id="vpc-bbb222",
            tenant_id=self.tid,
            region="us-east-1",
            auto_accept=True,
        ))
        topology = self.engine.get_peering_topology(self.tid)
        self.assertIn("vpc-aaa111", topology)
        self.assertIn("vpc-bbb222", topology["vpc-aaa111"])

    def test_tenant_isolation(self) -> None:
        created = self.engine.create_peering(PeeringRequest(
            requester_vpc_id="vpc-aaa111",
            accepter_vpc_id="vpc-bbb222",
            tenant_id=self.tid,
            region="us-east-1",
            auto_accept=True,
        ))
        other_tid = "t-99999999-9999-9999-9999-999999999999"
        result = self.engine.delete_peering(created.resource_id, other_tid)
        self.assertFalse(result.success)
        self.assertIn("Tenant mismatch", result.error)


class TestTransitGatewayEngine(unittest.TestCase):
    """Test transit gateway engine."""

    def setUp(self) -> None:
        self.engine = TransitGatewayEngine()
        self.tid = "t-12345678-1234-1234-1234-123456789012"

    def test_create_gateway(self) -> None:
        result = self.engine.create_gateway(TransitGatewayRequest(
            tenant_id=self.tid,
            region="us-east-1",
            amazon_side_asn=64512,
        ))
        self.assertTrue(result.success)
        self.assertEqual(result.state, TransitGatewayState.AVAILABLE.value)
        self.assertTrue(result.resource_id.startswith("tgw-"))

    def test_attach_vpc(self) -> None:
        tgw = self.engine.create_gateway(TransitGatewayRequest(
            tenant_id=self.tid,
            region="us-east-1",
        ))
        from dcc.network import AttachmentRequest
        result = self.engine.attach_vpc(AttachmentRequest(
            transit_gateway_id=tgw.resource_id,
            vpc_id="vpc-aaa111",
            tenant_id=self.tid,
            region="us-east-1",
        ))
        self.assertTrue(result.success)
        self.assertTrue(result.resource_id.startswith("tgw-attach-"))

    def test_delete_gateway_with_attachments(self) -> None:
        tgw = self.engine.create_gateway(TransitGatewayRequest(
            tenant_id=self.tid,
            region="us-east-1",
        ))
        from dcc.network import AttachmentRequest
        self.engine.attach_vpc(AttachmentRequest(
            transit_gateway_id=tgw.resource_id,
            vpc_id="vpc-aaa111",
            tenant_id=self.tid,
            region="us-east-1",
        ))
        result = self.engine.delete_gateway(tgw.resource_id, self.tid)
        self.assertFalse(result.success)
        self.assertIn("active attachments", result.error)

    def test_get_gateway_topology(self) -> None:
        tgw = self.engine.create_gateway(TransitGatewayRequest(
            tenant_id=self.tid,
            region="us-east-1",
        ))
        from dcc.network import AttachmentRequest
        self.engine.attach_vpc(AttachmentRequest(
            transit_gateway_id=tgw.resource_id,
            vpc_id="vpc-aaa111",
            tenant_id=self.tid,
            region="us-east-1",
        ))
        topology = self.engine.get_gateway_topology(tgw.resource_id)
        self.assertEqual(topology["gateway_id"], tgw.resource_id)
        self.assertEqual(len(topology["attachments"]), 1)


class TestExpressRouteEngine(unittest.TestCase):
    """Test ExpressRoute engine."""

    def setUp(self) -> None:
        self.engine = ExpressRouteEngine()
        self.tid = "t-12345678-1234-1234-1234-123456789012"

    def test_create_circuit(self) -> None:
        result = self.engine.create_circuit(ExpressRouteRequest(
            tenant_id=self.tid,
            bandwidth_mbps=1000,
            location="eastus",
        ))
        self.assertTrue(result.success)
        self.assertEqual(result.state, ExpressRouteState.PROVISIONED.value)
        self.assertTrue(result.resource_id.startswith("erc-"))

    def test_add_peering(self) -> None:
        circuit = self.engine.create_circuit(ExpressRouteRequest(
            tenant_id=self.tid,
            bandwidth_mbps=1000,
            location="eastus",
        ))
        result = self.engine.add_peering(ExpressRoutePeeringRequest(
            circuit_id=circuit.resource_id,
            tenant_id=self.tid,
            peering_type="AzurePrivatePeering",
            peer_asn=65001,
            vlan_id=100,
        ))
        self.assertTrue(result.success)
        self.assertTrue(result.resource_id.startswith("erp-"))

    def test_delete_circuit(self) -> None:
        circuit = self.engine.create_circuit(ExpressRouteRequest(
            tenant_id=self.tid,
            bandwidth_mbps=1000,
            location="eastus",
        ))
        result = self.engine.delete_circuit(circuit.resource_id, self.tid)
        self.assertTrue(result.success)
        self.assertIsNone(self.engine.get_circuit(circuit.resource_id))


class TestCloudInterconnectEngine(unittest.TestCase):
    """Test Cloud Interconnect engine."""

    def setUp(self) -> None:
        self.engine = CloudInterconnectEngine()
        self.tid = "t-12345678-1234-1234-1234-123456789012"

    def test_create_interconnect(self) -> None:
        result = self.engine.create_interconnect(InterconnectRequest(
            tenant_id=self.tid,
            bandwidth_mbps=10000,
            location="us-central1",
            provider=CloudProvider.GCP,
        ))
        self.assertTrue(result.success)
        self.assertEqual(result.state, InterconnectState.ACTIVE.value)
        self.assertTrue(result.resource_id.startswith("ic-"))

    def test_create_attachment(self) -> None:
        ic = self.engine.create_interconnect(InterconnectRequest(
            tenant_id=self.tid,
            bandwidth_mbps=10000,
            location="us-central1",
        ))
        result = self.engine.create_attachment(InterconnectAttachmentRequest(
            interconnect_id=ic.resource_id,
            tenant_id=self.tid,
            vlan_tag=200,
            bgp_session_enabled=True,
            region="us-central1",
        ))
        self.assertTrue(result.success)
        self.assertTrue(result.resource_id.startswith("ica-"))

    def test_configure_bgp_session(self) -> None:
        ic = self.engine.create_interconnect(InterconnectRequest(
            tenant_id=self.tid,
            bandwidth_mbps=10000,
            location="us-central1",
        ))
        att = self.engine.create_attachment(InterconnectAttachmentRequest(
            interconnect_id=ic.resource_id,
            tenant_id=self.tid,
            vlan_tag=200,
            region="us-central1",
        ))
        result = self.engine.configure_bgp_session(
            attachment_id=att.resource_id,
            tenant_id=self.tid,
            peer_ip="169.254.0.1",
            cloud_router_ip="169.254.0.2",
        )
        self.assertTrue(result.success)


class TestSegmentationEngine(unittest.TestCase):
    """Test segmentation engine."""

    def setUp(self) -> None:
        self.engine = SegmentationEngine()
        self.tid = "t-12345678-1234-1234-1234-123456789012"

    def test_create_segment(self) -> None:
        result = self.engine.create_segment(SegmentRequest(
            tenant_id=self.tid,
            segmentation_type=SegmentationType.VXLAN,
            vxlan_vni=1001,
            cidr_block="10.0.0.0/24",
            region="us-east-1",
        ))
        self.assertTrue(result.success)
        self.assertTrue(result.resource_id.startswith("seg-"))

    def test_create_security_group(self) -> None:
        result = self.engine.create_security_group(SecurityGroupRequest(
            tenant_id=self.tid,
            vpc_id="vpc-aaa111",
            name="web-tier-sg",
            region="us-east-1",
        ))
        self.assertTrue(result.success)
        self.assertTrue(result.resource_id.startswith("sg-"))

    def test_create_route_table(self) -> None:
        result = self.engine.create_route_table(RouteTableRequest(
            tenant_id=self.tid,
            vpc_id="vpc-aaa111",
            region="us-east-1",
        ))
        self.assertTrue(result.success)
        self.assertTrue(result.resource_id.startswith("rtb-"))

    def test_add_route(self) -> None:
        rt = self.engine.create_route_table(RouteTableRequest(
            tenant_id=self.tid,
            vpc_id="vpc-aaa111",
            region="us-east-1",
        ))
        result = self.engine.add_route(RouteRequest(
            route_table_id=rt.resource_id,
            tenant_id=self.tid,
            destination_cidr="10.1.0.0/16",
            target="tgw-aaa111",
            target_type="transit_gateway",
        ))
        self.assertTrue(result.success)
        self.assertEqual(result.state, RouteState.ACTIVE.value)

    def test_create_subnet(self) -> None:
        result = self.engine.create_subnet(SubnetRequest(
            tenant_id=self.tid,
            vpc_id="vpc-aaa111",
            cidr_block="10.0.1.0/24",
            region="us-east-1",
            availability_zone="us-east-1a",
        ))
        self.assertTrue(result.success)
        self.assertTrue(result.resource_id.startswith("subnet-"))


class TestNetworkAutomationEngine(unittest.TestCase):
    """Test the unified network automation engine."""

    def setUp(self) -> None:
        self.engine = NetworkAutomationEngine()
        self.tid = "t-12345678-1234-1234-1234-123456789012"

    def test_create_vpc(self) -> None:
        result = self.engine.create_vpc(VPCRequest(
            tenant_id=self.tid,
            cidr_block="10.0.0.0/16",
            region="us-east-1",
            name="prod-vpc",
        ))
        self.assertTrue(result.success)
        self.assertTrue(result.resource_id.startswith("vpc-"))

    def test_full_workflow(self) -> None:
        """Test a complete network automation workflow."""
        # Use unique tenant_id to avoid singleton state from other tests
        wf_tid = "t-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        # Create VPCs
        vpc1 = self.engine.create_vpc(VPCRequest(
            tenant_id=wf_tid,
            cidr_block="10.0.0.0/16",
            region="us-east-1",
            name="prod-vpc",
        ))
        vpc2 = self.engine.create_vpc(VPCRequest(
            tenant_id=wf_tid,
            cidr_block="10.1.0.0/16",
            region="us-east-1",
            name="staging-vpc",
        ))
        self.assertTrue(vpc1.success)
        self.assertTrue(vpc2.success)

        # Create peering
        peering = self.engine.create_peering(PeeringRequest(
            requester_vpc_id=vpc1.resource_id,
            accepter_vpc_id=vpc2.resource_id,
            tenant_id=wf_tid,
            region="us-east-1",
            auto_accept=True,
        ))
        self.assertTrue(peering.success)

        # Create transit gateway
        tgw = self.engine.create_transit_gateway(TransitGatewayRequest(
            tenant_id=wf_tid,
            region="us-east-1",
        ))
        self.assertTrue(tgw.success)

        # Attach VPC to TGW
        att = self.engine.attach_vpc_to_tgw(
            __import__("dcc.network", fromlist=["AttachmentRequest"]).AttachmentRequest(
                transit_gateway_id=tgw.resource_id,
                vpc_id=vpc1.resource_id,
                tenant_id=wf_tid,
                region="us-east-1",
            )
        )
        self.assertTrue(att.success)

        # Create ExpressRoute
        er = self.engine.create_expressroute(ExpressRouteRequest(
            tenant_id=wf_tid,
            bandwidth_mbps=1000,
            location="eastus",
        ))
        self.assertTrue(er.success)

        # Create Cloud Interconnect
        ic = self.engine.create_interconnect(InterconnectRequest(
            tenant_id=wf_tid,
            bandwidth_mbps=10000,
            location="us-central1",
            provider=CloudProvider.GCP,
        ))
        self.assertTrue(ic.success)

        # Create segment
        seg = self.engine.create_segment(SegmentRequest(
            tenant_id=wf_tid,
            segmentation_type=SegmentationType.VXLAN,
            vxlan_vni=1001,
            cidr_block="10.0.0.0/24",
            vpc_id=vpc1.resource_id,
            region="us-east-1",
        ))
        self.assertTrue(seg.success)

        # Create security group
        sg = self.engine.create_security_group(SecurityGroupRequest(
            tenant_id=wf_tid,
            vpc_id=vpc1.resource_id,
            name="web-tier-sg",
            region="us-east-1",
        ))
        self.assertTrue(sg.success)

        # Create route table
        rt = self.engine.create_route_table(RouteTableRequest(
            tenant_id=wf_tid,
            vpc_id=vpc1.resource_id,
            region="us-east-1",
        ))
        self.assertTrue(rt.success)

        # Add route
        route = self.engine.add_route(RouteRequest(
            route_table_id=rt.resource_id,
            tenant_id=wf_tid,
            destination_cidr="10.1.0.0/16",
            target=tgw.resource_id,
            target_type="transit_gateway",
        ))
        self.assertTrue(route.success)

        # Create subnet
        subnet = self.engine.create_subnet(SubnetRequest(
            tenant_id=wf_tid,
            vpc_id=vpc1.resource_id,
            cidr_block="10.0.1.0/24",
            region="us-east-1",
            availability_zone="us-east-1a",
        ))
        self.assertTrue(subnet.success)

        # Get topology
        topo = self.engine.get_topology(wf_tid)
        self.assertEqual(len(topo.vpcs), 2)
        self.assertEqual(len(topo.peerings), 1)
        self.assertEqual(len(topo.transit_gateways), 1)

        # Get connectivity matrix
        matrix = self.engine.get_connectivity_matrix(wf_tid)
        self.assertEqual(matrix[vpc1.resource_id][vpc2.resource_id], "peered")

    def test_setup_peering_topology(self) -> None:
        pt_tid = "t-11111111-1111-1111-1111-111111111111"
        vpc1 = self.engine.create_vpc(VPCRequest(
            tenant_id=pt_tid,
            cidr_block="10.0.0.0/16",
            region="us-east-1",
        ))
        vpc2 = self.engine.create_vpc(VPCRequest(
            tenant_id=pt_tid,
            cidr_block="10.1.0.0/16",
            region="us-east-1",
        ))
        vpc3 = self.engine.create_vpc(VPCRequest(
            tenant_id=pt_tid,
            cidr_block="10.2.0.0/16",
            region="us-east-1",
        ))
        results = self.engine.setup_peering_topology(PeeringTopologyRequest(
            tenant_id=pt_tid,
            hub_vpc_id=vpc1.resource_id,
            spoke_vpc_ids=[vpc2.resource_id, vpc3.resource_id],
            region="us-east-1",
            auto_accept=True,
        ))
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.success for r in results))

    def test_setup_hub_spoke_topology(self) -> None:
        hs_tid = "t-22222222-2222-2222-2222-222222222222"
        vpc1 = self.engine.create_vpc(VPCRequest(
            tenant_id=hs_tid,
            cidr_block="10.0.0.0/16",
            region="us-east-1",
        ))
        vpc2 = self.engine.create_vpc(VPCRequest(
            tenant_id=hs_tid,
            cidr_block="10.1.0.0/16",
            region="us-east-1",
        ))
        results = self.engine.setup_hub_spoke_topology(HubSpokeRequest(
            tenant_id=hs_tid,
            hub_vpc_id=vpc1.resource_id,
            spoke_vpc_ids=[vpc2.resource_id],
            region="us-east-1",
        ))
        self.assertEqual(len(results), 3)  # TGW + hub attachment + spoke attachment
        self.assertTrue(all(r.success for r in results))

    def test_setup_multi_cloud_connectivity(self) -> None:
        mc_tid = "t-33333333-3333-3333-3333-333333333333"
        results = self.engine.setup_multi_cloud_connectivity(MultiCloudRequest(
            tenant_id=mc_tid,
            azure_vnet_id="vnet-123",
            gcp_vpc_id="vpc-456",
            region="us-east-1",
            bandwidth_mbps=1000,
        ))
        self.assertEqual(len(results), 2)  # ExpressRoute + Interconnect
        self.assertTrue(all(r.success for r in results))

    def test_tenant_isolation(self) -> None:
        ti_tid = "t-44444444-4444-4444-4444-444444444444"
        self.engine.create_vpc(VPCRequest(
            tenant_id=ti_tid,
            cidr_block="10.0.0.0/16",
            region="us-east-1",
        ))
        other_tid = "t-99999999-9999-9999-9999-999999999999"
        peerings = self.engine.list_peerings(tenant_id=other_tid)
        self.assertEqual(len(peerings), 0)

    def test_singleton(self) -> None:
        engine1 = get_engine()
        engine2 = get_engine()
        self.assertIs(engine1, engine2)


if __name__ == "__main__":
    unittest.main()
