"""DigitalOcean compliance provider.

Implements compliance checks for DigitalOcean resources based on
CIS DigitalOcean Foundations Benchmark and security best practices.
"""
from __future__ import annotations

from typing import Any

from .base import CloudProviderCompliance, ProviderComplianceResult, ProviderComplianceStatus


class DigitalOceanComplianceProvider:
    """DigitalOcean cloud provider compliance scanner."""

    def __init__(self) -> None:
        self._checks = self._build_checks()

    @property
    def provider_name(self) -> str:
        return "digitalocean"

    def get_compliance_checks(self) -> list[dict[str, Any]]:
        return self._checks

    def evaluate(self, resource: dict[str, Any]) -> ProviderComplianceResult:
        resource_type = resource.get("resource_type", "unknown")
        check = self._find_check(resource_type)
        if check is None:
            return ProviderComplianceResult(
                check_id=f"DO-{resource_type.upper()}-001",
                provider="digitalocean",
                name=f"DigitalOcean {resource_type} Compliance",
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
                provider="digitalocean",
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
                provider="digitalocean",
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
                provider="digitalocean",
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
                "check_id": "DO-DROPLET-001",
                "name": "Droplet Backups",
                "description": "Droplets must have backups enabled",
                "severity": "medium",
                "category": "reliability",
                "resource_types": ["digitalocean_droplet"],
                "evaluator": self._check_droplet_backups,
            },
            {
                "check_id": "DO-DROPLET-002",
                "name": "Droplet Monitoring",
                "description": "Droplets must have monitoring enabled",
                "severity": "medium",
                "category": "reliability",
                "resource_types": ["digitalocean_droplet"],
                "evaluator": self._check_droplet_monitoring,
            },
            {
                "check_id": "DO-FIREWALL-001",
                "name": "Firewall Rules",
                "description": "Cloud firewalls must be configured for droplets",
                "severity": "high",
                "category": "security",
                "resource_types": ["digitalocean_firewall"],
                "evaluator": self._check_firewall_rules,
            },
            {
                "check_id": "DO-VPC-001",
                "name": "VPC Peering",
                "description": "VPC peering must use private connections",
                "severity": "medium",
                "category": "security",
                "resource_types": ["digitalocean_vpc"],
                "evaluator": self._check_vpc_peering,
            },
            {
                "check_id": "DO-DB-001",
                "name": "Database Backup",
                "description": "Managed databases must have backups enabled",
                "severity": "high",
                "category": "reliability",
                "resource_types": ["digitalocean_database_cluster"],
                "evaluator": self._check_database_backup,
            },
            {
                "check_id": "DO-DB-002",
                "name": "Database Private Connection",
                "description": "Managed databases must use private connections",
                "severity": "high",
                "category": "security",
                "resource_types": ["digitalocean_database_cluster"],
                "evaluator": self._check_database_private,
            },
            {
                "check_id": "DO-SPACES-001",
                "name": "Spaces Bucket Private",
                "description": "Spaces buckets must not be publicly accessible",
                "severity": "critical",
                "category": "security",
                "resource_types": ["digitalocean_spaces_bucket"],
                "evaluator": self._check_spaces_private,
            },
            {
                "check_id": "DO-SSH-001",
                "name": "SSH Key Authentication",
                "description": "Droplets must use SSH key authentication",
                "severity": "high",
                "category": "security",
                "resource_types": ["digitalocean_droplet"],
                "evaluator": self._check_ssh_auth,
            },
        ]

    # --- Evaluators ---

    def _check_droplet_backups(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        backups = resource.get("backups_enabled", resource.get("backups", False))
        if backups:
            return True, "Droplet has backups enabled", ""
        return False, "Droplet does not have backups enabled", "Enable backups on droplet"

    def _check_droplet_monitoring(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        monitoring = resource.get("monitoring_enabled", resource.get("monitoring", False))
        if monitoring:
            return True, "Droplet has monitoring enabled", ""
        return False, "Droplet does not have monitoring enabled", "Enable monitoring on droplet"

    def _check_firewall_rules(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        rules = resource.get("inbound_rules", resource.get("outbound_rules", []))
        if isinstance(rules, list) and len(rules) > 0:
            return True, "Firewall has rules configured", ""
        return False, "Firewall does not have rules configured", "Configure firewall rules"

    def _check_vpc_peering(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        private = resource.get("private_peering", resource.get("is_private", False))
        if private:
            return True, "VPC peering uses private connections", ""
        return False, "VPC peering does not use private connections", "Use private VPC peering"

    def _check_database_backup(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        backup = resource.get("backup_enabled", resource.get("backup_restore", False))
        if backup:
            return True, "Database has backups enabled", ""
        return False, "Database does not have backups enabled", "Enable database backups"

    def _check_database_private(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        private = resource.get("private_connection", resource.get("private_networking", False))
        if private:
            return True, "Database uses private connections", ""
        return False, "Database does not use private connections", "Enable private networking for database"

    def _check_spaces_private(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        public = resource.get("publicly_accessible", resource.get("acl", "private") == "public-read")
        if not public:
            return True, "Spaces bucket is not publicly accessible", ""
        return False, "Spaces bucket is publicly accessible", "Set Spaces bucket ACL to private"

    def _check_ssh_auth(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        ssh_keys = resource.get("ssh_keys", resource.get("ssh_key_ids", []))
        if isinstance(ssh_keys, list) and len(ssh_keys) > 0:
            return True, "Droplet uses SSH key authentication", ""
        return False, "Droplet does not use SSH key authentication", "Add SSH keys to droplet"
