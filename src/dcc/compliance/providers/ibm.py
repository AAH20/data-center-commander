"""IBM Cloud compliance provider.

Implements compliance checks for IBM Cloud resources based on
IBM Cloud Security Framework and CIS IBM Cloud Foundations Benchmark.
"""
from __future__ import annotations

from typing import Any

from .base import CloudProviderCompliance, ProviderComplianceResult, ProviderComplianceStatus


class IBMComplianceProvider:
    """IBM Cloud provider compliance scanner."""

    def __init__(self) -> None:
        self._checks = self._build_checks()

    @property
    def provider_name(self) -> str:
        return "ibm"

    def get_compliance_checks(self) -> list[dict[str, Any]]:
        return self._checks

    def evaluate(self, resource: dict[str, Any]) -> ProviderComplianceResult:
        resource_type = resource.get("resource_type", "unknown")
        check = self._find_check(resource_type)
        if check is None:
            return ProviderComplianceResult(
                check_id=f"IBM-{resource_type.upper()}-001",
                provider="ibm",
                name=f"IBM {resource_type} Compliance",
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
                provider="ibm",
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
                provider="ibm",
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
                provider="ibm",
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
                "check_id": "IBM-VPC-001",
                "name": "IBM VPC Flow Logs",
                "description": "IBM VPC must have flow logs enabled",
                "severity": "medium",
                "category": "security",
                "resource_types": ["ibm_is_vpc"],
                "evaluator": self._check_vpc_flow_logs,
            },
            {
                "check_id": "IBM-IKS-001",
                "name": "IKS Cluster Private Endpoint",
                "description": "IKS clusters must have private endpoint enabled",
                "severity": "high",
                "category": "security",
                "resource_types": ["ibm_container_vpc_cluster"],
                "evaluator": self._check_iks_private_endpoint,
            },
            {
                "check_id": "IBM-IKS-002",
                "name": "IKS Cluster Worker Encryption",
                "description": "IKS clusters must have worker node encryption enabled",
                "severity": "high",
                "category": "security",
                "resource_types": ["ibm_container_vpc_cluster"],
                "evaluator": self._check_iks_worker_encryption,
            },
            {
                "check_id": "IBM-COS-001",
                "name": "COS Bucket Encryption",
                "description": "Cloud Object Storage buckets must have encryption enabled",
                "severity": "high",
                "category": "security",
                "resource_types": ["ibm_cos_bucket"],
                "evaluator": self._check_cos_encryption,
            },
            {
                "check_id": "IBM-IAM-001",
                "name": "IBM IAM Access Groups",
                "description": "IBM IAM must use access groups for permission management",
                "severity": "medium",
                "category": "security",
                "resource_types": ["ibm_iam_access_group"],
                "evaluator": self._check_iam_access_groups,
            },
            {
                "check_id": "IBM-SI-001",
                "name": "Security Insights",
                "description": "IBM Security Insights must be enabled",
                "severity": "high",
                "category": "security",
                "resource_types": ["ibm_security_insights"],
                "evaluator": self._check_security_insights,
            },
        ]

    # --- Evaluators ---

    def _check_vpc_flow_logs(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        flow_logs = resource.get("flow_logs_enabled", resource.get("enable_flow_logs", False))
        if flow_logs:
            return True, "IBM VPC has flow logs enabled", ""
        return False, "IBM VPC does not have flow logs enabled", "Enable VPC flow logs"

    def _check_iks_private_endpoint(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        private_endpoint = resource.get("private_endpoint_enabled", resource.get("enable_private_endpoint", False))
        if private_endpoint:
            return True, "IKS cluster has private endpoint enabled", ""
        return False, "IKS cluster does not have private endpoint enabled", "Enable private endpoint on IKS cluster"

    def _check_iks_worker_encryption(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        encryption = resource.get("worker_encryption_enabled", resource.get("enable_worker_encryption", False))
        if encryption:
            return True, "IKS cluster has worker node encryption enabled", ""
        return False, "IKS cluster does not have worker node encryption enabled", "Enable worker node encryption on IKS cluster"

    def _check_cos_encryption(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        encrypted = resource.get("encryption_enabled", resource.get("key_protect_enabled", False))
        if encrypted:
            return True, "COS bucket has encryption enabled", ""
        return False, "COS bucket does not have encryption enabled", "Enable encryption on COS bucket"

    def _check_iam_access_groups(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        access_groups = resource.get("access_groups", resource.get("has_access_groups", False))
        if access_groups:
            return True, "IBM IAM uses access groups for permission management", ""
        return False, "IBM IAM does not use access groups", "Configure IBM IAM access groups"

    def _check_security_insights(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        enabled = resource.get("enabled", resource.get("is_active", False))
        if enabled:
            return True, "IBM Security Insights is enabled", ""
        return False, "IBM Security Insights is not enabled", "Enable IBM Security Insights"
