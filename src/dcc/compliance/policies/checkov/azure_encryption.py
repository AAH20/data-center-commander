"""Checkov policy: Azure encryption compliance."""
from checkov.common.models.enums import CheckCategories, CheckResult
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class StorageEncryptionCheck(BaseResourceCheck):
    """Ensure storage accounts have encryption enabled."""

    def __init__(self):
        name = "Ensure storage accounts have encryption enabled"
        id = "CKV_AZURE_3"
        supported_resources = ["azurerm_storage_account"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        encryption = conf.get("encryption_enabled")
        if encryption and encryption[0] is True:
            return CheckResult.PASSED
        return CheckResult.FAILED


class SQLTDECheck(BaseResourceCheck):
    """Ensure SQL databases have TDE enabled."""

    def __init__(self):
        name = "Ensure SQL databases have TDE enabled"
        id = "CKV_AZURE_15"
        supported_resources = ["azurerm_mssql_database"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        tde = conf.get("tde_enabled")
        if tde and tde[0] is True:
            return CheckResult.PASSED
        return CheckResult.FAILED
