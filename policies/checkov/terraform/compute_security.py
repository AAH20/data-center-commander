"""
Checkov Custom Policies — Compute Security for Data Center IaC
Covers: EC2 hardening, instance metadata, key management, auto-scaling
"""

from checkov.common.models.enums import CheckCategories, CheckResult
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class EC2InstanceMetadataOptions(BaseResourceCheck):
    """Ensure EC2 instances require IMDSv2 (metadata service v2)."""

    def __init__(self):
        name = "Ensure EC2 instances require IMDSv2"
        id = "DC_COMPUTE_001"
        supported_resources = ["aws_instance", "aws_launch_template", "aws_launch_configuration"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        metadata_options = conf.get("metadata_options", {})
        if isinstance(metadata_options, list):
            metadata_options = metadata_options[0] if metadata_options else {}
        if isinstance(metadata_options, dict):
            http_tokens = metadata_options.get("http_tokens", "optional")
            if isinstance(http_tokens, list):
                http_tokens = http_tokens[0] if http_tokens else "optional"
            if http_tokens != "required":
                return CheckResult.FAILED
        else:
            return CheckResult.FAILED
        return CheckResult.PASSED


class EC2InstanceDetailedMonitoring(BaseResourceCheck):
    """Ensure EC2 instances have detailed monitoring enabled."""

    def __init__(self):
        name = "Ensure EC2 instances have detailed monitoring enabled"
        id = "DC_COMPUTE_002"
        supported_resources = ["aws_instance"]
        categories = [CheckCategories.LOGGING, CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        monitoring = conf.get("monitoring", False)
        if isinstance(monitoring, list):
            monitoring = monitoring[0] if monitoring else False
        if monitoring is not True:
            return CheckResult.FAILED
        return CheckResult.PASSED


class EC2InstanceNoPublicIP(BaseResourceCheck):
    """Ensure EC2 instances do not have public IPs unless explicitly required."""

    def __init__(self):
        name = "Ensure EC2 instances do not have public IPs"
        id = "DC_COMPUTE_003"
        supported_resources = ["aws_instance"]
        categories = [CheckCategories.NETWORKING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        associate_public_ip = conf.get("associate_public_ip_address", False)
        if isinstance(associate_public_ip, list):
            associate_public_ip = associate_public_ip[0] if associate_public_ip else False
        if associate_public_ip is True:
            return CheckResult.FAILED
        return CheckResult.PASSED


class EC2InstanceEncryptedRootVolume(BaseResourceCheck):
    """Ensure EC2 instances have encrypted root EBS volumes."""

    def __init__(self):
        name = "Ensure EC2 instances have encrypted root EBS volumes"
        id = "DC_COMPUTE_004"
        supported_resources = ["aws_instance", "aws_launch_template", "aws_launch_configuration"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        root_block_device = conf.get("root_block_device", {})
        if isinstance(root_block_device, list):
            root_block_device = root_block_device[0] if root_block_device else {}
        if isinstance(root_block_device, dict):
            encrypted = root_block_device.get("encrypted", False)
            if isinstance(encrypted, list):
                encrypted = encrypted[0] if encrypted else False
            if encrypted is not True:
                return CheckResult.FAILED
        else:
            return CheckResult.FAILED
        return CheckResult.PASSED


class EC2InstanceNoHardcodedCredentials(BaseResourceCheck):
    """Ensure EC2 user data does not contain hardcoded credentials."""

    SENSITIVE_PATTERNS = ["password", "secret", "api_key", "apikey", "access_key", "private_key"]

    def __init__(self):
        name = "Ensure EC2 user data does not contain hardcoded credentials"
        id = "DC_COMPUTE_005"
        supported_resources = ["aws_instance", "aws_launch_template", "aws_launch_configuration"]
        categories = [CheckCategories.SECRETS]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        user_data = conf.get("user_data", "")
        if isinstance(user_data, list):
            user_data = user_data[0] if user_data else ""
        if isinstance(user_data, str):
            user_data_lower = user_data.lower()
            for pattern in self.SENSITIVE_PATTERNS:
                if pattern in user_data_lower:
                    return CheckResult.FAILED
        return CheckResult.PASSED


class AutoScalingGroupHealthCheck(BaseResourceCheck):
    """Ensure Auto Scaling groups have health checks enabled."""

    def __init__(self):
        name = "Ensure Auto Scaling groups have health checks enabled"
        id = "DC_COMPUTE_006"
        supported_resources = ["aws_autoscaling_group"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        health_check_type = conf.get("health_check_type", "")
        if isinstance(health_check_type, list):
            health_check_type = health_check_type[0] if health_check_type else ""
        if not health_check_type or health_check_type == "":
            return CheckResult.FAILED
        return CheckResult.PASSED


class AutoScalingGroupTags(BaseResourceCheck):
    """Ensure Auto Scaling groups have tags for resource tracking."""

    def __init__(self):
        name = "Ensure Auto Scaling groups have tags"
        id = "DC_COMPUTE_007"
        supported_resources = ["aws_autoscaling_group"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        tags = conf.get("tag", [])
        if not tags:
            tags = conf.get("tags", {})
        if isinstance(tags, list):
            if len(tags) == 0:
                return CheckResult.FAILED
        elif isinstance(tags, dict):
            if len(tags) == 0:
                return CheckResult.FAILED
        else:
            return CheckResult.FAILED
        return CheckResult.PASSED


class LaunchTemplateHasSecurityGroups(BaseResourceCheck):
    """Ensure launch templates specify security groups."""

    def __init__(self):
        name = "Ensure launch templates specify security groups"
        id = "DC_COMPUTE_008"
        supported_resources = ["aws_launch_template"]
        categories = [CheckCategories.NETWORKING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        vpc_security_group_ids = conf.get("vpc_security_group_ids", [])
        if isinstance(vpc_security_group_ids, list):
            if len(vpc_security_group_ids) == 0:
                return CheckResult.FAILED
        else:
            return CheckResult.FAILED
        return CheckResult.PASSED


class EC2InstanceTenancy(BaseResourceCheck):
    """Ensure EC2 instances use dedicated tenancy for sensitive workloads."""

    def __init__(self):
        name = "Ensure EC2 instances use dedicated tenancy"
        id = "DC_COMPUTE_009"
        supported_resources = ["aws_instance", "aws_launch_template"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        tenancy = conf.get("tenancy", "default")
        if isinstance(tenancy, list):
            tenancy = tenancy[0] if tenancy else "default"
        if tenancy != "dedicated":
            return CheckResult.FAILED
        return CheckResult.PASSED


class EC2InstanceNoInstanceTypeT2Micro(BaseResourceCheck):
    """Ensure production workloads do not use t2.micro instances."""

    BURSTABLE_TYPES = [
        "t2.nano",
        "t2.micro",
        "t2.small",
        "t2.medium",
        "t3.nano",
        "t3.micro",
        "t3.small",
        "t3.medium",
    ]

    def __init__(self):
        name = "Ensure production workloads do not use burstable instances"
        id = "DC_COMPUTE_010"
        supported_resources = ["aws_instance", "aws_launch_template", "aws_launch_configuration"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        instance_type = conf.get("instance_type", "")
        if isinstance(instance_type, list):
            instance_type = instance_type[0] if instance_type else ""
        if instance_type in self.BURSTABLE_TYPES:
            return CheckResult.FAILED
        return CheckResult.PASSED
