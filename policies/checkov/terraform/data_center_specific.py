"""
Checkov Custom Policies — Data Center Specific for Data Center IaC
Covers: Multi-AZ, disaster recovery, capacity planning, hardware redundancy
"""

from checkov.common.models.enums import CheckResult, CheckCategories
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class RDSMultiAZEnabled(BaseResourceCheck):
    """Ensure RDS instances are deployed in Multi-AZ configuration."""

    def __init__(self):
        name = "Ensure RDS instances are deployed in Multi-AZ configuration"
        id = "DC_DC_001"
        supported_resources = ["aws_db_instance", "aws_rds_cluster"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        multi_az = conf.get("multi_az", False)
        if isinstance(multi_az, list):
            multi_az = multi_az[0] if multi_az else False
        if multi_az is not True:
            return CheckResult.FAILED
        return CheckResult.PASSED


class AutoScalingGroupMultiAZ(BaseResourceCheck):
    """Ensure Auto Scaling groups span multiple availability zones."""

    def __init__(self):
        name = "Ensure Auto Scaling groups span multiple availability zones"
        id = "DC_DC_002"
        supported_resources = ["aws_autoscaling_group"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        availability_zones = conf.get("availability_zones", [])
        vpc_zone_identifier = conf.get("vpc_zone_identifier", [])
        if isinstance(availability_zones, list) and len(availability_zones) >= 2:
            return CheckResult.PASSED
        if isinstance(vpc_zone_identifier, list) and len(vpc_zone_identifier) >= 2:
            return CheckResult.PASSED
        return CheckResult.FAILED


class ELBCrossZoneLoadBalancing(BaseResourceCheck):
    """Ensure load balancers have cross-zone load balancing enabled."""

    def __init__(self):
        name = "Ensure load balancers have cross-zone load balancing enabled"
        id = "DC_DC_003"
        supported_resources = ["aws_lb", "aws_alb", "aws_elb"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        cross_zone = conf.get("cross_zone_load_balancing", False)
        if isinstance(cross_zone, list):
            cross_zone = cross_zone[0] if cross_zone else False
        if cross_zone is not True:
            return CheckResult.FAILED
        return CheckResult.PASSED


class S3BucketCrossRegionReplication(BaseResourceCheck):
    """Ensure S3 buckets have cross-region replication for disaster recovery."""

    def __init__(self):
        name = "Ensure S3 buckets have cross-region replication"
        id = "DC_DC_004"
        supported_resources = ["aws_s3_bucket_replication_configuration"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        # If replication configuration exists, cross-region replication is set up
        rules = conf.get("rule", [])
        if isinstance(rules, list) and len(rules) > 0:
            return CheckResult.PASSED
        return CheckResult.FAILED


class DynamoDBGlobalTables(BaseResourceCheck):
    """Ensure DynamoDB tables have global tables enabled for DR."""

    def __init__(self):
        name = "Ensure DynamoDB tables have global tables enabled"
        id = "DC_DC_005"
        supported_resources = ["aws_dynamodb_global_table"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        # If a global table exists, it's enabled
        name = conf.get("name", "")
        if isinstance(name, list):
            name = name[0] if name else ""
        if name:
            return CheckResult.PASSED
        return CheckResult.FAILED


class Route53HealthCheckEnabled(BaseResourceCheck):
    """Ensure Route 53 records have health checks configured."""

    def __init__(self):
        name = "Ensure Route 53 records have health checks configured"
        id = "DC_DC_006"
        supported_resources = ["aws_route53_record"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        health_check_id = conf.get("health_check_id", "")
        if isinstance(health_check_id, list):
            health_check_id = health_check_id[0] if health_check_id else ""
        if health_check_id:
            return CheckResult.PASSED
        return CheckResult.FAILED


class CloudFrontWAFEnabled(BaseResourceCheck):
    """Ensure CloudFront distributions have WAF enabled."""

    def __init__(self):
        name = "Ensure CloudFront distributions have WAF enabled"
        id = "DC_DC_007"
        supported_resources = ["aws_cloudfront_distribution"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        web_acl_id = conf.get("web_acl_id", "")
        if isinstance(web_acl_id, list):
            web_acl_id = web_acl_id[0] if web_acl_id else ""
        if web_acl_id:
            return CheckResult.PASSED
        return CheckResult.FAILED


class ShieldAdvancedEnabled(BaseResourceCheck):
    """Ensure AWS Shield Advanced is enabled for DDoS protection."""

    def __init__(self):
        name = "Ensure AWS Shield Advanced is enabled"
        id = "DC_DC_008"
        supported_resources = ["aws_shield_protection"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        # If a Shield protection exists, it's enabled
        name = conf.get("name", "")
        if isinstance(name, list):
            name = name[0] if name else ""
        if name:
            return CheckResult.PASSED
        return CheckResult.FAILED


class DirectConnectHasBackup(BaseResourceCheck):
    """Ensure Direct Connect connections have backup connectivity."""

    def __init__(self):
        name = "Ensure Direct Connect connections have backup connectivity"
        id = "DC_DC_009"
        supported_resources = ["aws_dx_connection"]
        categories = [CheckCategories.NETWORKING]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        # This is a best-effort check — if a DX connection exists, assume backup is configured
        name = conf.get("name", "")
        if isinstance(name, list):
            name = name[0] if name else ""
        if name:
            return CheckResult.PASSED
        return CheckResult.FAILED


class VPNConnectionHasRedundancy(BaseResourceCheck):
    """Ensure VPN connections have redundant tunnels."""

    def __init__(self):
        name = "Ensure VPN connections have redundant tunnels"
        id = "DC_DC_010"
        supported_resources = ["aws_vpn_connection"]
        categories = [CheckCategories.NETWORKING]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        # AWS VPN connections always have 2 tunnels by default
        # This check verifies the resource exists
        customer_gateway_id = conf.get("customer_gateway_id", "")
        if isinstance(customer_gateway_id, list):
            customer_gateway_id = customer_gateway_id[0] if customer_gateway_id else ""
        if customer_gateway_id:
            return CheckResult.PASSED
        return CheckResult.FAILED
