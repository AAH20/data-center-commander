"""Checkov policy: Multi-cloud compliance."""
from checkov.common.models.enums import CheckCategories, CheckResult
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class ResourceTagsCheck(BaseResourceCheck):
    """Ensure all resources have tags."""

    def __init__(self):
        name = "Ensure all resources have tags"
        id = "CKV_DCC_1"
        supported_resources = ["*"]
        categories = [CheckCategories.GENERAL]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        tags = conf.get("tags")
        if tags:
            return CheckResult.PASSED
        return CheckResult.FAILED


class ResourceEncryptionCheck(BaseResourceCheck):
    """Ensure storage resources have encryption enabled."""

    def __init__(self):
        name = "Ensure storage resources have encryption enabled"
        id = "CKV_DCC_2"
        supported_resources = [
            "aws_s3_bucket", "aws_ebs_volume", "aws_db_instance",
            "azurerm_storage_account", "azurerm_mssql_database",
            "google_storage_bucket", "google_compute_disk",
        ]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        encrypted = (
            conf.get("encrypted") or
            conf.get("encryption_enabled") or
            conf.get("storage_encrypted") or
            conf.get("uniform_bucket_level_access") or
            conf.get("server_side_encryption_configuration")
        )
        if encrypted:
            return CheckResult.PASSED
        return CheckResult.FAILED
