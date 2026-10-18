"""Azure compliance provider.

Implements compliance checks for Azure resources based on Azure Policy,
CIS Azure Foundations Benchmark, and Microsoft Defender for Cloud.
"""
from __future__ import annotations

from typing import Any

from .base import CloudProviderCompliance, ProviderComplianceResult, ProviderComplianceStatus


class AzureComplianceProvider:
    """Azure cloud provider compliance scanner."""

    def __init__(self) -> None:
        self._checks = self._build_checks()

    @property
    def provider_name(self) -> str:
        return "azure"

    def get_compliance_checks(self) -> list[dict[str, Any]]:
        return self._checks

    def evaluate(self, resource: dict[str, Any]) -> ProviderComplianceResult:
        resource_type = resource.get("resource_type", "unknown")
        check = self._find_check(resource_type)
        if check is None:
            return ProviderComplianceResult(
                check_id=f"AZURE-{resource_type.upper()}-001",
                provider="azure",
                name=f"Azure {resource_type} Compliance",
                status=ProviderComplianceStatus.NOT_APPLICABLE,
                severity="info",
                category="general",
                detail=f"No specific compliance check for resource type: {resource_type}",
                resource_id=resource.get("id", "unknown"),
                resource_type=resource_type,
            )
        return self._run_check(check, resource)

    def evaluate_all(self, resources: list[dict[str, Any]]) -> list[ProviderComplianceResult]:
        return [self.evaluate(r) for r in resources]

    def _find_check(self, resource_type: str) -> dict[str, Any] | None:
        for check in self._checks:
            if resource_type in check.get("resource_types", []):
                return check
        return None

    def _run_check(self, check: dict[str, Any], resource: dict[str, Any]) -> ProviderComplianceResult:
        check_id = check["check_id"]
        name = check["name"]
        severity = check.get("severity", "medium")
        category = check.get("category", "security")
        evaluator = check.get("evaluator")

        if evaluator is None:
            return ProviderComplianceResult(
                check_id=check_id,
                provider="azure",
                name=name,
                status=ProviderComplianceStatus.UNKNOWN,
                severity=severity,
                category=category,
                detail="No evaluator configured",
                resource_id=resource.get("id", "unknown"),
                resource_type=resource.get("resource_type", "unknown"),
            )

        try:
            passed, detail, remediation = evaluator(resource)
            status = ProviderComplianceStatus.PASS if passed else ProviderComplianceStatus.FAIL
            return ProviderComplianceResult(
                check_id=check_id,
                provider="azure",
                name=name,
                status=status,
                severity=severity,
                category=category,
                detail=detail,
                resource_id=resource.get("id", "unknown"),
                resource_type=resource.get("resource_type", "unknown"),
                remediation_hint=remediation,
            )
        except Exception as exc:
            return ProviderComplianceResult(
                check_id=check_id,
                provider="azure",
                name=name,
                status=ProviderComplianceStatus.UNKNOWN,
                severity=severity,
                category=category,
                detail=f"Evaluation error: {exc}",
                resource_id=resource.get("id", "unknown"),
                resource_type=resource.get("resource_type", "unknown"),
            )

    def _build_checks(self) -> list[dict[str, Any]]:
        return [
            {
                "check_id": "AZURE-STORAGE-001",
                "name": "Storage Account Encryption",
                "description": "Storage accounts must have encryption at rest enabled",
                "severity": "high",
                "category": "security",
                "resource_types": ["azurerm_storage_account"],
                "evaluator": self._check_storage_encryption,
            },
            {
                "check_id": "AZURE-STORAGE-002",
                "name": "Storage Account HTTPS Only",
                "description": "Storage accounts must enforce HTTPS-only traffic",
                "severity": "high",
                "category": "security",
                "resource_types": ["azurerm_storage_account"],
                "evaluator": self._check_storage_https,
            },
            {
                "check_id": "AZURE-VM-001",
                "name": "VM Disk Encryption",
                "description": "Virtual machines must have disk encryption enabled",
                "severity": "high",
                "category": "security",
                "resource_types": ["azurerm_linux_virtual_machine", "azurerm_windows_virtual_machine"],
                "evaluator": self._check_vm_disk_encryption,
            },
            {
                "check_id": "AZURE-SQL-001",
                "name": "SQL Database TDE",
                "description": "SQL databases must have Transparent Data Encryption enabled",
                "severity": "high",
                "category": "security",
                "resource_types": ["azurerm_mssql_database"],
                "evaluator": self._check_sql_tde,
            },
            {
                "check_id": "AZURE-NSG-001",
                "name": "NSG Flow Logs",
                "description": "Network security groups must have flow logs enabled",
                "severity": "medium",
                "category": "security",
                "resource_types": ["azurerm_network_security_group"],
                "evaluator": self._check_nsg_flow_logs,
            },
            {
                "check_id": "AZURE-KEYVAULT-001",
                "name": "Key Vault Soft Delete",
                "description": "Key Vaults must have soft delete enabled",
                "severity": "medium",
                "category": "reliability",
                "resource_types": ["azurerm_key_vault"],
                "evaluator": self._check_keyvault_soft_delete,
            },
            {
                "check_id": "AZURE-KEYVAULT-002",
                "name": "Key Vault Purge Protection",
                "description": "Key Vaults must have purge protection enabled",
                "severity": "medium",
                "category": "reliability",
                "resource_types": ["azurerm_key_vault"],
                "evaluator": self._check_keyvault_purge_protection,
            },
            {
                "check_id": "AZURE-POLICY-001",
                "name": "Azure Policy Assignment",
                "description": "Azure Policy must be assigned at the subscription level",
                "severity": "high",
                "category": "governance",
                "resource_types": ["azurerm_subscription_policy_assignment"],
                "evaluator": self._check_policy_assignment,
            },
            {
                "check_id": "AZURE-MONITOR-001",
                "name": "Azure Monitor Diagnostics",
                "description": "Diagnostic settings must be configured for all resources",
                "severity": "medium",
                "category": "reliability",
                "resource_types": ["azurerm_monitor_diagnostic_setting"],
                "evaluator": self._check_monitor_diagnostics,
            },
            {
                "check_id": "AZURE-BACKUP-001",
                "name": "Azure Backup",
                "description": "Virtual machines must have Azure Backup enabled",
                "severity": "high",
                "category": "reliability",
                "resource_types": ["azurerm_backup_protected_vm"],
                "evaluator": self._check_backup_enabled,
            },
        ]

    # --- Evaluators ---

    def _check_storage_encryption(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        encrypted = resource.get("encrypted", resource.get("enable_https_traffic_only", False))
        if encrypted:
            return True, "Storage account has encryption at rest enabled", ""
        return False, "Storage account does not have encryption at rest", "Enable storage account encryption"

    def _check_storage_https(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        https_only = resource.get("https_only", resource.get("enable_https_traffic_only", False))
        if https_only:
            return True, "Storage account enforces HTTPS-only traffic", ""
        return False, "Storage account does not enforce HTTPS-only traffic", "Enable HTTPS-only traffic on storage account"

    def _check_vm_disk_encryption(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        encrypted = resource.get("disk_encryption_enabled", resource.get("encryption_at_host_enabled", False))
        if encrypted:
            return True, "VM has disk encryption enabled", ""
        return False, "VM does not have disk encryption enabled", "Enable VM disk encryption"

    def _check_sql_tde(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        tde = resource.get("tde_enabled", resource.get("transparent_data_encryption_enabled", False))
        if tde:
            return True, "SQL database has TDE enabled", ""
        return False, "SQL database does not have TDE enabled", "Enable TDE on SQL database"

    def _check_nsg_flow_logs(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        flow_logs = resource.get("flow_logs_enabled", resource.get("enable_flow_logs", False))
        if flow_logs:
            return True, "NSG has flow logs enabled", ""
        return False, "NSG does not have flow logs enabled", "Enable NSG flow logs"

    def _check_keyvault_soft_delete(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        soft_delete = resource.get("soft_delete_enabled", resource.get("enable_soft_delete", False))
        if soft_delete:
            return True, "Key Vault has soft delete enabled", ""
        return False, "Key Vault does not have soft delete enabled", "Enable soft delete on Key Vault"

    def _check_keyvault_purge_protection(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        purge_protection = resource.get("purge_protection_enabled", resource.get("enable_purge_protection", False))
        if purge_protection:
            return True, "Key Vault has purge protection enabled", ""
        return False, "Key Vault does not have purge protection enabled", "Enable purge protection on Key Vault"

    def _check_policy_assignment(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        assigned = resource.get("assigned", resource.get("is_assigned", False))
        if assigned:
            return True, "Azure Policy is assigned at subscription level", ""
        return False, "Azure Policy is not assigned at subscription level", "Assign Azure Policy at subscription level"

    def _check_monitor_diagnostics(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        enabled = resource.get("enabled", resource.get("diagnostics_enabled", False))
        if enabled:
            return True, "Diagnostic settings are configured", ""
        return False, "Diagnostic settings are not configured", "Configure diagnostic settings"

    def _check_backup_enabled(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        backup = resource.get("backup_enabled", resource.get("is_protected", False))
        if backup:
            return True, "Azure Backup is enabled for VM", ""
        return False, "Azure Backup is not enabled for VM", "Enable Azure Backup for VM"
