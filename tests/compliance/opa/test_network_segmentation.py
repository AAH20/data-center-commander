"""
OPA/Rego Policy Tests — Network Segmentation
Tests for datacenter.network_segmentation package.
"""

import json
import subprocess
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from helpers import run_opa, make_resource


class TestNetworkSegmentationCompliance:
    """Tests for network segmentation policy compliance."""

    def test_fully_compliant_resource_passes(self):
        """A resource with all network settings should produce no violations."""
        resource = make_resource()
        result = run_opa(resource, "datacenter.network_segmentation")
        assert result.get("result", [{}])[0].get("expressions", [{}])[0].get("value", []) == []

    def test_production_in_public_segment_fails(self):
        """Production resource in public segment should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("public network segment" in d for d in denies)

    def test_production_not_in_isolated_or_restricted_fails(self):
        """Production resource not in isolated or restricted segment should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "dmz"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("isolated or restricted" in d for d in denies)

    def test_sensitive_data_in_public_segment_fails(self):
        """Resource with sensitive data in public segment should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["tags"]["data_classification"] = "sensitive"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("sensitive" in d and "public" in d for d in denies)

    def test_confidential_data_in_public_segment_fails(self):
        """Resource with confidential data in public segment should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["tags"]["data_classification"] = "confidential"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("confidential" in d and "public" in d for d in denies)

    def test_restricted_data_in_public_segment_fails(self):
        """Resource with restricted data in public segment should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["tags"]["data_classification"] = "restricted"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("restricted" in d and "public" in d for d in denies)

    def test_isolated_with_public_access_fails(self):
        """Isolated resource with public access should be denied."""
        resource = make_resource()
        resource["network"]["public_access"] = True
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("public access" in d for d in denies)

    def test_restricted_with_public_access_fails(self):
        """Restricted resource with public access should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "restricted"
        resource["network"]["public_access"] = True
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("public access" in d for d in denies)

    def test_public_without_waf_fails(self):
        """Public resource without WAF should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["waf_enabled"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("WAF" in d for d in denies)

    def test_public_without_ddos_protection_fails(self):
        """Public resource without DDoS protection should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["ddos_protection"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("DDoS" in d for d in denies)

    def test_public_without_cdn_fails(self):
        """Public resource without CDN should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["cdn_enabled"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("CDN" in d for d in denies)

    def test_public_without_load_balancer_fails(self):
        """Public resource without load balancer should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["load_balancer"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("load balancer" in d for d in denies)

    def test_public_without_health_check_fails(self):
        """Public resource without health check should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["health_check"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("health check" in d for d in denies)

    def test_public_without_ssl_fails(self):
        """Public resource without SSL/TLS should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["ssl_enabled"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("SSL/TLS" in d for d in denies)

    def test_public_invalid_ssl_fails(self):
        """Public resource with invalid SSL certificate should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["ssl_valid"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("invalid SSL" in d for d in denies)

    def test_public_ssl_expiring_within_30_days_fails(self):
        """Public resource with SSL expiring within 30 days should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["ssl_expiry_days"] = 15
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("expiring" in d for d in denies)

    def test_public_expired_ssl_fails(self):
        """Public resource with expired SSL certificate should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["ssl_expiry_days"] = 0
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("expired" in d for d in denies)

    def test_public_weak_ssl_fails(self):
        """Public resource with weak SSL configuration should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["ssl_strength"] = "weak"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("weak SSL" in d for d in denies)

    def test_public_tls10_fails(self):
        """Public resource using TLS 1.0 should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["ssl_version"] = "TLSv1.0"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("TLS 1.0" in d for d in denies)

    def test_public_tls11_fails(self):
        """Public resource using TLS 1.1 should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["ssl_version"] = "TLSv1.1"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("TLS 1.1" in d for d in denies)

    def test_public_tls12_fails(self):
        """Public resource using TLS 1.2 should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["ssl_version"] = "TLSv1.2"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("TLS 1.3" in d for d in denies)

    def test_public_without_firewall_fails(self):
        """Public resource without firewall should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["firewall_enabled"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("firewall" in d for d in denies)

    def test_public_without_ids_fails(self):
        """Public resource without intrusion detection should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["ids_enabled"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("intrusion detection" in d for d in denies)

    def test_public_without_nacl_fails(self):
        """Public resource without network ACL should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["nacl_enabled"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("network ACL" in d for d in denies)

    def test_public_without_security_group_fails(self):
        """Public resource without security group should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["security_group"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("security group" in d for d in denies)

    def test_public_without_vpc_fails(self):
        """Public resource without VPC should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["vpc_enabled"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("VPC" in d for d in denies)

    def test_public_not_in_private_subnet_fails(self):
        """Public resource not in private subnet should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["private_subnet"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("private subnet" in d for d in denies)

    def test_public_without_route_table_fails(self):
        """Public resource without route table should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["route_table"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("route table" in d for d in denies)

    def test_public_without_network_interface_fails(self):
        """Public resource without network interface should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["network_interface"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("network interface" in d for d in denies)

    def test_public_without_dns_fails(self):
        """Public resource without DNS should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["dns_enabled"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("DNS" in d for d in denies)

    def test_public_without_syslog_fails(self):
        """Public resource without Syslog should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["syslog_enabled"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("Syslog" in d for d in denies)

    def test_public_without_ntp_fails(self):
        """Public resource without NTP should be denied."""
        resource = make_resource()
        resource["network"]["segment"] = "public"
        resource["network"]["ntp_enabled"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("NTP" in d for d in denies)

    def test_inter_segment_traffic_without_explicit_allow_fails(self):
        """Resource allowing inter-segment traffic without explicit allow should be denied."""
        resource = make_resource()
        resource["network"]["inter_segment_traffic"] = True
        resource["network"]["explicit_allow"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("inter-segment traffic" in d for d in denies)

    def test_all_inbound_traffic_fails(self):
        """Resource allowing all inbound traffic should be denied."""
        resource = make_resource()
        resource["network"]["inbound_traffic"] = "all"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("all inbound traffic" in d for d in denies)

    def test_all_outbound_traffic_fails(self):
        """Resource allowing all outbound traffic should be denied."""
        resource = make_resource()
        resource["network"]["outbound_traffic"] = "all"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("all outbound traffic" in d for d in denies)

    def test_ssh_from_anywhere_fails(self):
        """Resource allowing SSH from anywhere should be denied."""
        resource = make_resource()
        resource["network"]["ssh_cidr"] = "0.0.0.0/0"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("SSH" in d and "0.0.0.0/0" in d for d in denies)

    def test_rdp_from_anywhere_fails(self):
        """Resource allowing RDP from anywhere should be denied."""
        resource = make_resource()
        resource["network"]["rdp_cidr"] = "0.0.0.0/0"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("RDP" in d and "0.0.0.0/0" in d for d in denies)

    def test_database_from_anywhere_fails(self):
        """Resource allowing database access from anywhere should be denied."""
        resource = make_resource()
        resource["network"]["database_cidr"] = "0.0.0.0/0"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("database" in d and "0.0.0.0/0" in d for d in denies)

    def test_icmp_from_anywhere_fails(self):
        """Resource allowing ICMP from anywhere should be denied."""
        resource = make_resource()
        resource["network"]["icmp_cidr"] = "0.0.0.0/0"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("ICMP" in d and "0.0.0.0/0" in d for d in denies)

    def test_telnet_enabled_fails(self):
        """Resource with Telnet enabled should be denied."""
        resource = make_resource()
        resource["network"]["telnet_enabled"] = True
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("Telnet" in d for d in denies)

    def test_ftp_enabled_fails(self):
        """Resource with FTP enabled should be denied."""
        resource = make_resource()
        resource["network"]["ftp_enabled"] = True
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("FTP" in d for d in denies)

    def test_snmp_v1_fails(self):
        """Resource using SNMP v1 should be denied."""
        resource = make_resource()
        resource["network"]["snmp_version"] = "v1"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("SNMP v1" in d for d in denies)

    def test_snmp_v2c_fails(self):
        """Resource using SNMP v2c should be denied."""
        resource = make_resource()
        resource["network"]["snmp_version"] = "v2c"
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("SNMP v2c" in d for d in denies)

    def test_http_without_https_fails(self):
        """Resource allowing HTTP without HTTPS should be denied."""
        resource = make_resource()
        resource["network"]["http_enabled"] = True
        resource["network"]["https_enabled"] = False
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("HTTP" in d and "HTTPS" in d for d in denies)

    def test_sslv3_enabled_fails(self):
        """Resource with SSLv3 enabled should be denied."""
        resource = make_resource()
        resource["network"]["sslv3_enabled"] = True
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("SSLv3" in d for d in denies)

    def test_tls10_enabled_fails(self):
        """Resource with TLS 1.0 enabled should be denied."""
        resource = make_resource()
        resource["network"]["tls_10_enabled"] = True
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("TLS 1.0" in d for d in denies)

    def test_tls11_enabled_fails(self):
        """Resource with TLS 1.1 enabled should be denied."""
        resource = make_resource()
        resource["network"]["tls_11_enabled"] = True
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("TLS 1.1" in d for d in denies)

    def test_open_ports_fails(self):
        """Resource with open ports should be denied."""
        resource = make_resource()
        resource["network"]["open_ports"] = [8080, 9090]
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("open ports" in d for d in denies)

    def test_unused_security_groups_fails(self):
        """Resource with unused security groups should be denied."""
        resource = make_resource()
        resource["network"]["unused_security_groups"] = 2
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused security groups" in d for d in denies)

    def test_unused_nacls_fails(self):
        """Resource with unused network ACLs should be denied."""
        resource = make_resource()
        resource["network"]["unused_nacls"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused network ACLs" in d for d in denies)

    def test_unused_route_tables_fails(self):
        """Resource with unused route tables should be denied."""
        resource = make_resource()
        resource["network"]["unused_route_tables"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused route tables" in d for d in denies)

    def test_unused_network_interfaces_fails(self):
        """Resource with unused network interfaces should be denied."""
        resource = make_resource()
        resource["network"]["unused_network_interfaces"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused network interfaces" in d for d in denies)

    def test_unused_elastic_ips_fails(self):
        """Resource with unused elastic IPs should be denied."""
        resource = make_resource()
        resource["network"]["unused_elastic_ips"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused elastic IPs" in d for d in denies)

    def test_unused_vpcs_fails(self):
        """Resource with unused VPCs should be denied."""
        resource = make_resource()
        resource["network"]["unused_vpcs"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused VPCs" in d for d in denies)

    def test_unused_subnets_fails(self):
        """Resource with unused subnets should be denied."""
        resource = make_resource()
        resource["network"]["unused_subnets"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused subnets" in d for d in denies)

    def test_unused_internet_gateways_fails(self):
        """Resource with unused internet gateways should be denied."""
        resource = make_resource()
        resource["network"]["unused_internet_gateways"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused internet gateways" in d for d in denies)

    def test_unused_nat_gateways_fails(self):
        """Resource with unused NAT gateways should be denied."""
        resource = make_resource()
        resource["network"]["unused_nat_gateways"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused NAT gateways" in d for d in denies)

    def test_unused_vpn_connections_fails(self):
        """Resource with unused VPN connections should be denied."""
        resource = make_resource()
        resource["network"]["unused_vpn_connections"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused VPN connections" in d for d in denies)

    def test_unused_direct_connect_fails(self):
        """Resource with unused direct connect should be denied."""
        resource = make_resource()
        resource["network"]["unused_direct_connect"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused direct connect" in d for d in denies)

    def test_unused_transit_gateways_fails(self):
        """Resource with unused transit gateways should be denied."""
        resource = make_resource()
        resource["network"]["unused_transit_gateways"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused transit gateways" in d for d in denies)

    def test_unused_peering_connections_fails(self):
        """Resource with unused peering connections should be denied."""
        resource = make_resource()
        resource["network"]["unused_peering_connections"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused peering connections" in d for d in denies)

    def test_unused_load_balancers_fails(self):
        """Resource with unused load balancers should be denied."""
        resource = make_resource()
        resource["network"]["unused_load_balancers"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused load balancers" in d for d in denies)

    def test_unused_auto_scaling_groups_fails(self):
        """Resource with unused auto scaling groups should be denied."""
        resource = make_resource()
        resource["network"]["unused_auto_scaling_groups"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused auto scaling groups" in d for d in denies)

    def test_unused_launch_configurations_fails(self):
        """Resource with unused launch configurations should be denied."""
        resource = make_resource()
        resource["network"]["unused_launch_configurations"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused launch configurations" in d for d in denies)

    def test_unused_launch_templates_fails(self):
        """Resource with unused launch templates should be denied."""
        resource = make_resource()
        resource["network"]["unused_launch_templates"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused launch templates" in d for d in denies)

    def test_unused_ebs_volumes_fails(self):
        """Resource with unused EBS volumes should be denied."""
        resource = make_resource()
        resource["network"]["unused_ebs_volumes"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused EBS volumes" in d for d in denies)

    def test_unused_ebs_snapshots_fails(self):
        """Resource with unused EBS snapshots should be denied."""
        resource = make_resource()
        resource["network"]["unused_ebs_snapshots"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused EBS snapshots" in d for d in denies)

    def test_unused_amis_fails(self):
        """Resource with unused AMIs should be denied."""
        resource = make_resource()
        resource["network"]["unused_amis"] = 1
        result = run_opa(resource, "datacenter.network_segmentation")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("unused AMIs" in d for d in denies)
