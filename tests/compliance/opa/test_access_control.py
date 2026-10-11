"""
OPA/Rego Policy Tests — Access Control
Tests for datacenter.access_control package.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from helpers import make_resource, run_opa


class TestAccessControlCompliance:
    """Tests for access control policy compliance."""

    def test_fully_compliant_resource_passes(self):
        """A resource with all access control settings should produce no violations."""
        resource = make_resource()
        result = run_opa(resource, "datacenter.access_control")
        assert result.get("result", [{}])[0].get("expressions", [{}])[0].get("value", []) == []

    def test_production_without_mfa_fails(self):
        """Production resource without MFA should be denied."""
        resource = make_resource()
        resource["access"]["mfa"] = False
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("MFA" in d for d in denies)

    def test_staging_without_mfa_fails(self):
        """Staging resource without MFA should be denied."""
        resource = make_resource(environment="staging")
        resource["access"]["mfa"] = False
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("MFA" in d for d in denies)

    def test_not_least_privilege_fails(self):
        """Resource not using least privilege should be denied."""
        resource = make_resource()
        resource["access"]["privilege"] = "admin"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("least privilege" in d for d in denies)

    def test_production_admin_access_fails(self):
        """Production resource with admin access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "admin"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("admin" in d for d in denies)

    def test_production_root_access_fails(self):
        """Production resource with root access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "root"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("root" in d for d in denies)

    def test_production_superuser_access_fails(self):
        """Production resource with superuser access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "superuser"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("superuser" in d for d in denies)

    def test_production_owner_access_fails(self):
        """Production resource with owner access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "owner"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("owner" in d for d in denies)

    def test_production_full_access_fails(self):
        """Production resource with full access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "full"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("full" in d for d in denies)

    def test_production_write_access_fails(self):
        """Production resource with write access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "write"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("write" in d for d in denies)

    def test_production_read_write_access_fails(self):
        """Production resource with read-write access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "read-write"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("read-write" in d for d in denies)

    def test_production_read_only_access_fails(self):
        """Production resource with read-only access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "read-only"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("read-only" in d for d in denies)

    def test_production_read_access_fails(self):
        """Production resource with read access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "read"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("read" in d for d in denies)

    def test_production_custom_access_fails(self):
        """Production resource with custom access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "custom"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("custom" in d for d in denies)

    def test_production_default_access_fails(self):
        """Production resource with default access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "default"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("default" in d for d in denies)

    def test_production_guest_access_fails(self):
        """Production resource with guest access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "guest"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("guest" in d for d in denies)

    def test_production_anonymous_access_fails(self):
        """Production resource with anonymous access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "anonymous"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("anonymous" in d for d in denies)

    def test_production_public_access_fails(self):
        """Production resource with public access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "public"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("public" in d for d in denies)

    def test_production_external_access_fails(self):
        """Production resource with external access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "external"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("external" in d for d in denies)

    def test_production_partner_access_fails(self):
        """Production resource with partner access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "partner"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("partner" in d for d in denies)

    def test_production_vendor_access_fails(self):
        """Production resource with vendor access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "vendor"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("vendor" in d for d in denies)

    def test_production_contractor_access_fails(self):
        """Production resource with contractor access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "contractor"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("contractor" in d for d in denies)

    def test_production_temp_access_fails(self):
        """Production resource with temp access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "temp"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("temp" in d for d in denies)

    def test_production_service_account_access_fails(self):
        """Production resource with service account access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "service-account"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("service account" in d for d in denies)

    def test_production_api_access_fails(self):
        """Production resource with API access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "api"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("API" in d for d in denies)

    def test_production_webhook_access_fails(self):
        """Production resource with webhook access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "webhook"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("webhook" in d for d in denies)

    def test_production_callback_access_fails(self):
        """Production resource with callback access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "callback"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("callback" in d for d in denies)

    def test_production_redirect_access_fails(self):
        """Production resource with redirect access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "redirect"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("redirect" in d for d in denies)

    def test_production_proxy_access_fails(self):
        """Production resource with proxy access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "proxy"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("proxy" in d for d in denies)

    def test_production_tunnel_access_fails(self):
        """Production resource with tunnel access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "tunnel"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("tunnel" in d for d in denies)

    def test_production_vpn_access_fails(self):
        """Production resource with VPN access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "vpn"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("VPN" in d for d in denies)

    def test_production_ssh_access_fails(self):
        """Production resource with SSH access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "ssh"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("SSH" in d for d in denies)

    def test_production_rdp_access_fails(self):
        """Production resource with RDP access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "rdp"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("RDP" in d for d in denies)

    def test_production_ftp_access_fails(self):
        """Production resource with FTP access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "ftp"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("FTP" in d for d in denies)

    def test_production_sftp_access_fails(self):
        """Production resource with SFTP access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "sftp"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("SFTP" in d for d in denies)

    def test_production_scp_access_fails(self):
        """Production resource with SCP access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "scp"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("SCP" in d for d in denies)

    def test_production_tftp_access_fails(self):
        """Production resource with TFTP access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "tftp"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("TFTP" in d for d in denies)

    def test_production_telnet_access_fails(self):
        """Production resource with Telnet access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "telnet"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("Telnet" in d for d in denies)

    def test_production_snmp_access_fails(self):
        """Production resource with SNMP access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "snmp"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("SNMP" in d for d in denies)

    def test_production_icmp_access_fails(self):
        """Production resource with ICMP access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "icmp"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("ICMP" in d for d in denies)

    def test_production_dns_access_fails(self):
        """Production resource with DNS access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "dns"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("DNS" in d for d in denies)

    def test_production_dhcp_access_fails(self):
        """Production resource with DHCP access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "dhcp"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("DHCP" in d for d in denies)

    def test_production_ntp_access_fails(self):
        """Production resource with NTP access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "ntp"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("NTP" in d for d in denies)

    def test_production_syslog_access_fails(self):
        """Production resource with Syslog access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "syslog"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("Syslog" in d for d in denies)

    def test_production_netflow_access_fails(self):
        """Production resource with NetFlow access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "netflow"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("NetFlow" in d for d in denies)

    def test_production_sflow_access_fails(self):
        """Production resource with sFlow access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "sflow"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("sFlow" in d for d in denies)

    def test_production_ipfix_access_fails(self):
        """Production resource with IPFIX access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "ipfix"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("IPFIX" in d for d in denies)

    def test_production_gre_tunnel_access_fails(self):
        """Production resource with GRE tunnel access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "gre-tunnel"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("GRE tunnel" in d for d in denies)

    def test_production_ipsec_tunnel_access_fails(self):
        """Production resource with IPsec tunnel access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "ipsec-tunnel"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("IPsec tunnel" in d for d in denies)

    def test_production_vxlan_access_fails(self):
        """Production resource with VXLAN access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "vxlan"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("VXLAN" in d for d in denies)

    def test_production_geneve_access_fails(self):
        """Production resource with Geneve access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "geneve"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("Geneve" in d for d in denies)

    def test_production_stt_access_fails(self):
        """Production resource with STT access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "stt"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("STT" in d for d in denies)

    def test_production_nvgre_access_fails(self):
        """Production resource with NVGRE access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "nvgre"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("NVGRE" in d for d in denies)

    def test_production_mpls_access_fails(self):
        """Production resource with MPLS access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "mpls"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("MPLS" in d for d in denies)

    def test_production_sdwan_access_fails(self):
        """Production resource with SD-WAN access should be denied."""
        resource = make_resource()
        resource["access"]["role"] = "sd-wan"
        result = run_opa(resource, "datacenter.access_control")
        denies = result["result"][0]["expressions"][0]["value"]
        assert any("SD-WAN" in d for d in denies)
