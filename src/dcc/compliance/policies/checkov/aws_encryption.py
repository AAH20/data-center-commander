"""Checkov policy: AWS encryption compliance."""
from checkov.common.models.enums import CheckCategories, CheckResult
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class S3EncryptionCheck(BaseResourceCheck):
    """Ensure S3 buckets have server-side encryption enabled."""

    def __init__(self):
        name = "Ensure S3 buckets have server-side encryption enabled"
        id = "CKV_AWS_19"
        supported_resources = ["aws_s3_bucket"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        encryption = conf.get("server_side_encryption_configuration")
        if encryption:
            return CheckResult.PASSED
        return CheckResult.FAILED


class RDSEncryptionCheck(BaseResourceCheck):
    """Ensure RDS instances have storage encryption enabled."""

    def __init__(self):
        name = "Ensure RDS instances have storage encryption enabled"
        id = "CKV_AWS_16"
        supported_resources = ["aws_db_instance"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        encrypted = conf.get("storage_encrypted")
        if encrypted and encrypted[0] is True:
            return CheckResult.PASSED
        return CheckResult.FAILED


class EBSEncryptionCheck(BaseResourceCheck):
    """Ensure EBS volumes are encrypted."""

    def __init__(self):
        name = "Ensure EBS volumes are encrypted"
        id = "CKV_AWS_3"
        supported_resources = ["aws_ebs_volume"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        encrypted = conf.get("encrypted")
        if encrypted and encrypted[0] is True:
            return CheckResult.PASSED
        return CheckResult.FAILED
