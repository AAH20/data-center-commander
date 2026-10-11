"""
Checkov Custom Policies — Network Security for Data Center IaC
Covers: VPC isolation, security groups, NACLs, public exposure, segmentation
"""

from checkov.common.models.enums import CheckCategories, CheckResult
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class RDPPortNotPubliclyAccessible(BaseResourceCheck):
    """Ensure RDP (3389) is not exposed to the internet."""

    def __init__(self):
        name = "Ensure RDP port 3389 is not publicly accessible"
        id = "DC_NET_001"
        supported_resources = [
            "aws_security_group",
            "aws_security_group_rule",
            "azurerm_network_security_group",
            "google_compute_firewall",
        ]
        categories = [CheckCategories.NETWORKING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        # AWS Security Group
        if "ingress" in conf:
            for ingress in conf["ingress"]:
                if isinstance(ingress, dict):
                    from_port = ingress.get("from_port")
                    to_port = ingress.get("to_port")
                    cidr_blocks = ingress.get("cidr_blocks", [])
                    if isinstance(cidr_blocks, list):
                        for cidr in cidr_blocks:
                            if isinstance(cidr, str) and cidr == "0.0.0.0/0":
                                if from_port == 3389 or (
                                    isinstance(from_port, int)
                                    and isinstance(to_port, int)
                                    and from_port <= 3389 <= to_port
                                ):
                                    return CheckResult.FAILED
        # Azure NSG
        if "security_rule" in conf:
            for rule in conf["security_rule"]:
                if isinstance(rule, dict):
                    if rule.get("destination_port_range") == "3389" or "3389" in str(
                        rule.get("destination_port_ranges", [])
                    ):
                        if (
                            "0.0.0.0/0" in str(rule.get("source_address_prefix", ""))
                            or rule.get("source_address_prefix") == "*"
                        ):
                            return CheckResult.FAILED
        # GCP Firewall
        if "source_ranges" in conf:
            if "0.0.0.0/0" in conf.get("source_ranges", []):
                for allow in conf.get("allow", []):
                    if isinstance(allow, dict):
                        ports = allow.get("ports", [])
                        if "3389" in ports:
                            return CheckResult.FAILED
        return CheckResult.PASSED


class SSHPortNotPubliclyAccessible(BaseResourceCheck):
    """Ensure SSH (22) is not exposed to the internet."""

    def __init__(self):
        name = "Ensure SSH port 22 is not publicly accessible"
        id = "DC_NET_002"
        supported_resources = [
            "aws_security_group",
            "aws_security_group_rule",
            "azurerm_network_security_group",
            "google_compute_firewall",
        ]
        categories = [CheckCategories.NETWORKING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        if "ingress" in conf:
            for ingress in conf["ingress"]:
                if isinstance(ingress, dict):
                    from_port = ingress.get("from_port")
                    to_port = ingress.get("to_port")
                    cidr_blocks = ingress.get("cidr_blocks", [])
                    if isinstance(cidr_blocks, list):
                        for cidr in cidr_blocks:
                            if isinstance(cidr, str) and cidr == "0.0.0.0/0":
                                if from_port == 22 or (
                                    isinstance(from_port, int)
                                    and isinstance(to_port, int)
                                    and from_port <= 22 <= to_port
                                ):
                                    return CheckResult.FAILED
        if "security_rule" in conf:
            for rule in conf["security_rule"]:
                if isinstance(rule, dict):
                    if rule.get("destination_port_range") == "22" or "22" in str(
                        rule.get("destination_port_ranges", [])
                    ):
                        if (
                            "0.0.0.0/0" in str(rule.get("source_address_prefix", ""))
                            or rule.get("source_address_prefix") == "*"
                        ):
                            return CheckResult.FAILED
        if "source_ranges" in conf:
            if "0.0.0.0/0" in conf.get("source_ranges", []):
                for allow in conf.get("allow", []):
                    if isinstance(allow, dict):
                        ports = allow.get("ports", [])
                        if "22" in ports:
                            return CheckResult.FAILED
        return CheckResult.PASSED


class DatabasePortNotPubliclyAccessible(BaseResourceCheck):
    """Ensure database ports (1433, 3306, 5432, 27017, 9200) are not publicly accessible."""

    DB_PORTS = [1433, 3306, 5432, 27017, 9200, 5433, 6379, 11211, 1521, 50000]

    def __init__(self):
        name = "Ensure database ports are not publicly accessible"
        id = "DC_NET_003"
        supported_resources = [
            "aws_security_group",
            "aws_security_group_rule",
            "azurerm_network_security_group",
            "google_compute_firewall",
        ]
        categories = [CheckCategories.NETWORKING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        if "ingress" in conf:
            for ingress in conf["ingress"]:
                if isinstance(ingress, dict):
                    from_port = ingress.get("from_port")
                    to_port = ingress.get("to_port")
                    cidr_blocks = ingress.get("cidr_blocks", [])
                    if isinstance(cidr_blocks, list):
                        for cidr in cidr_blocks:
                            if isinstance(cidr, str) and cidr == "0.0.0.0/0":
                                for db_port in self.DB_PORTS:
                                    if from_port == db_port or (
                                        isinstance(from_port, int)
                                        and isinstance(to_port, int)
                                        and from_port <= db_port <= to_port
                                    ):
                                        return CheckResult.FAILED
        if "security_rule" in conf:
            for rule in conf["security_rule"]:
                if isinstance(rule, dict):
                    port_range = str(rule.get("destination_port_range", ""))
                    port_ranges = rule.get("destination_port_ranges", [])
                    for db_port in self.DB_PORTS:
                        if str(db_port) in port_range or str(db_port) in str(port_ranges):
                            if (
                                "0.0.0.0/0" in str(rule.get("source_address_prefix", ""))
                                or rule.get("source_address_prefix") == "*"
                            ):
                                return CheckResult.FAILED
        if "source_ranges" in conf:
            if "0.0.0.0/0" in conf.get("source_ranges", []):
                for allow in conf.get("allow", []):
                    if isinstance(allow, dict):
                        ports = allow.get("ports", [])
                        for db_port in self.DB_PORTS:
                            if str(db_port) in ports:
                                return CheckResult.FAILED
        return CheckResult.PASSED


class VPCFlowLogsEnabled(BaseResourceCheck):
    """Ensure VPC flow logs are enabled for network monitoring."""

    def __init__(self):
        name = "Ensure VPC flow logs are enabled"
        id = "DC_NET_004"
        supported_resources = ["aws_vpc", "aws_vpc_flow_log"]
        categories = [CheckCategories.NETWORKING, CheckCategories.LOGGING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        # If this is a flow log resource, it exists — pass
        if "traffic_type" in conf:
            return CheckResult.PASSED
        # If this is a VPC, check for flow log association
        # In Terraform, flow logs are often separate resources, so we check for tags or other indicators
        tags = conf.get("tags", {})
        if isinstance(tags, dict):
            if tags.get("flow_logs") == "true" or tags.get("flow_logs") == "enabled":
                return CheckResult.PAASSED
        return CheckResult.FAILED


class NetworkACLRestricted(BaseResourceCheck):
    """Ensure NACLs do not allow unrestricted inbound/outbound traffic."""

    def __init__(self):
        name = "Ensure network ACLs do not allow unrestricted traffic"
        id = "DC_NET_005"
        supported_resources = ["aws_network_acl_rule"]
        categories = [CheckCategories.NETWORKING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        cidr_block = conf.get("cidr_block", "")
        rule_action = conf.get("rule_action", "")
        egress = conf.get("egress", False)
        if isinstance(egress, list):
            egress = egress[0] if egress else False
        if cidr_block == "0.0.0.0/0" and rule_action == "allow":
            return CheckResult.FAILED
        return CheckResult.PASSED


class SubnetHasPrivateIP(BaseResourceCheck):
    """Ensure subnets are not auto-assigning public IPs."""

    def __init__(self):
        name = "Ensure subnets do not auto-assign public IPs"
        id = "DC_NET_006"
        supported_resources = ["aws_subnet"]
        categories = [CheckCategories.NETWORKING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        map_public_ip = conf.get("map_public_ip_on_launch", False)
        if isinstance(map_public_ip, list):
            map_public_ip = map_public_ip[0] if map_public_ip else False
        if map_public_ip is True:
            return CheckResult.FAILED
        return CheckResult.PASSED


class VPCEndpointEnabled(BaseResourceCheck):
    """Ensure VPC endpoints are used for AWS services instead of public internet."""

    def __init__(self):
        name = "Ensure VPC endpoints are configured for AWS services"
        id = "DC_NET_007"
        supported_resources = ["aws_vpc_endpoint"]
        categories = [CheckCategories.NETWORKING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        # If a VPC endpoint exists, this is good
        service_name = conf.get("service_name", "")
        if service_name:
            return CheckResult.PASSED
        return CheckResult.FAILED


class SecurityGroupHasDescription(BaseResourceCheck):
    """Ensure all security groups have a description."""

    def __init__(self):
        name = "Ensure security groups have a description"
        id = "DC_NET_008"
        supported_resources = [
            "aws_security_group",
            "aws_security_group_rule",
        ]
        categories = [CheckCategories.NETWORKING, CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        description = conf.get("description", "")
        if isinstance(description, list):
            description = description[0] if description else ""
        if not description or description.strip() == "":
            return CheckResult.FAILED
        return CheckResult.PASSED


class NoWildcardCIDR(BaseResourceCheck):
    """Ensure security group rules do not use 0.0.0.0/0 for non-web ports."""

    WEB_PORTS = [80, 443, 8080, 8443]

    def __init__(self):
        name = "Ensure no wildcard CIDR for non-web ports"
        id = "DC_NET_009"
        supported_resources = [
            "aws_security_group",
            "aws_security_group_rule",
        ]
        categories = [CheckCategories.NETWORKING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        if "ingress" in conf:
            for ingress in conf["ingress"]:
                if isinstance(ingress, dict):
                    from_port = ingress.get("from_port")
                    to_port = ingress.get("to_port")
                    cidr_blocks = ingress.get("cidr_blocks", [])
                    if isinstance(cidr_blocks, list):
                        for cidr in cidr_blocks:
                            if isinstance(cidr, str) and cidr == "0.0.0.0/0":
                                is_web = False
                                for web_port in self.WEB_PORTS:
                                    if from_port == web_port or (
                                        isinstance(from_port, int)
                                        and isinstance(to_port, int)
                                        and from_port <= web_port <= to_port
                                    ):
                                        is_web = True
                                        break
                                if not is_web:
                                    return CheckResult.FAILED
        return CheckResult.PASSED


class TransitGatewayHasAutoAcceptDisabled(BaseResourceCheck):
    """Ensure transit gateway does not auto-accept shared attachments."""

    def __init__(self):
        name = "Ensure transit gateway does not auto-accept shared attachments"
        id = "DC_NET_010"
        supported_resources = ["aws_ec2_transit_gateway"]
        categories = [CheckCategories.NETWORKING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        auto_accept = conf.get("auto_accept_shared_attachments", "disable")
        if isinstance(auto_accept, list):
            auto_accept = auto_accept[0] if auto_accept else "disable"
        if auto_accept == "enable":
            return CheckResult.FAILED
        return CheckResult.PASSED
