"""Checkov policy: AWS network security compliance."""
from checkov.common.models.enums import CheckCategories, CheckResult
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class SecurityGroupUnrestrictedCheck(BaseResourceCheck):
    """Ensure security groups do not allow unrestricted inbound access."""

    def __init__(self):
        name = "Ensure security groups do not allow unrestricted inbound access"
        id = "CKV_AWS_24"
        supported_resources = ["aws_security_group"]
        categories = [CheckCategories.NETWORKING]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        ingress = conf.get("ingress")
        if ingress:
            for rule in ingress:
                if isinstance(rule, dict):
                    cidr_blocks = rule.get("cidr_blocks", [])
                    if "0.0.0.0/0" in str(cidr_blocks):
                        return CheckResult.FAILED
        return CheckResult.PASSED


class VPCFlowLogsCheck(BaseResourceCheck):
    """Ensure VPCs have flow logs enabled."""

    def __init__(self):
        name = "Ensure VPCs have flow logs enabled"
        id = "CKV_AWS_123"
        supported_resources = ["aws_vpc"]
        categories = [CheckCategories.NETWORKING]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        flow_logs = conf.get("flow_logs_enabled")
        if flow_logs and flow_logs[0] is True:
            return CheckResult.PASSED
        return CheckResult.FAILED
