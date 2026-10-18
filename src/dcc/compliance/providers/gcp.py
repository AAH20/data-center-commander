"""GCP compliance provider.

Implements compliance checks for GCP resources based on GCP Security Command
Center, CIS GCP Foundations Benchmark, and Organization Policies.
"""
from __future__ import annotations

from typing import Any

from .base import CloudProviderCompliance, ProviderComplianceResult, ProviderComplianceStatus


class GCPComplianceProvider:
    """GCP cloud provider compliance scanner."""

    def __init__(self) -> None:
        self._checks = self._build_checks()

    @property
    def provider_name(self) -> str:
        return "gcp"

    def get_compliance_checks(self) -> list[dict[str, Any]]:
        return self._checks

    def evaluate(self, resource: dict[str, Any]) -> ProviderComplianceResult:
        resource_type = resource.get("resource_type", "unknown")
        check = self._find_check(resource_type)
        if check is None:
            return ProviderComplianceResult(
                check_id=f"GCP-{resource_type.upper()}-001",
                provider="gcp",
                name=f"GCP {resource_type} Compliance",
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
                provider="gcp",
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
                provider="gcp",
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
                provider="gcp",
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
                "check_id": "GCP-GCS-001",
                "name": "GCS Bucket Uniform Access",
                "description": "GCS buckets must use uniform bucket-level access",
                "severity": "medium",
                "category": "security",
                "resource_types": ["google_storage_bucket"],
                "evaluator": self._check_gcs_uniform_access,
            },
            {
                "check_id": "GCP-GCS-002",
                "name": "GCS Bucket Public Access Prevention",
                "description": "GCS buckets must not be publicly accessible",
                "severity": "critical",
                "category": "security",
                "resource_types": ["google_storage_bucket"],
                "evaluator": self._check_gcs_public_access,
            },
            {
                "check_id": "GCP-GCE-001",
                "name": "GCE Instance Shielded VM",
                "description": "GCE instances must use Shielded VM features",
                "severity": "high",
                "category": "security",
                "resource_types": ["google_compute_instance"],
                "evaluator": self._check_gce_shielded_vm,
            },
            {
                "check_id": "GCP-GCE-002",
                "name": "GCE Instance Serial Port",
                "description": "GCE instances must disable serial port access",
                "severity": "medium",
                "category": "security",
                "resource_types": ["google_compute_instance"],
                "evaluator": self._check_gce_serial_port,
            },
            {
                "check_id": "GCP-GKE-001",
                "name": "GKE Cluster Private Endpoint",
                "description": "GKE clusters must have private endpoint enabled",
                "severity": "high",
                "category": "security",
                "resource_types": ["google_container_cluster"],
                "evaluator": self._check_gke_private_endpoint,
            },
            {
                "check_id": "GCP-GKE-002",
                "name": "GKE Cluster Network Policy",
                "description": "GKE clusters must have network policy enabled",
                "severity": "high",
                "category": "security",
                "resource_types": ["google_container_cluster"],
                "evaluator": self._check_gke_network_policy,
            },
            {
                "check_id": "GCP-GKE-003",
                "name": "GKE Cluster Workload Identity",
                "description": "GKE clusters must have Workload Identity enabled",
                "severity": "medium",
                "category": "security",
                "resource_types": ["google_container_cluster"],
                "evaluator": self._check_gke_workload_identity,
            },
            {
                "check_id": "GCP-IAM-001",
                "name": "GCP Service Account Key",
                "description": "Service accounts must not have user-managed keys",
                "severity": "high",
                "category": "security",
                "resource_types": ["google_service_account_key"],
                "evaluator": self._check_service_account_key,
            },
            {
                "check_id": "GCP-VPC-001",
                "name": "GCP VPC Flow Logs",
                "description": "VPC subnets must have flow logs enabled",
                "severity": "medium",
                "category": "security",
                "resource_types": ["google_compute_subnetwork"],
                "evaluator": self._check_vpc_flow_logs,
            },
            {
                "check_id": "GCP-ORG-001",
                "name": "GCP Organization Policy",
                "description": "Organization policies must be enforced",
                "severity": "high",
                "category": "governance",
                "resource_types": ["google_organization_policy"],
                "evaluator": self._check_org_policy,
            },
            {
                "check_id": "GCP-SCC-001",
                "name": "GCP Security Command Center",
                "description": "Security Command Center must be enabled",
                "severity": "critical",
                "category": "security",
                "resource_types": ["google_scc_source"],
                "evaluator": self._check_scc_enabled,
            },
            {
                "check_id": "GCP-AUDIT-001",
                "name": "GCP Audit Logs",
                "description": "Cloud Audit Logs must be enabled for all services",
                "severity": "high",
                "category": "security",
                "resource_types": ["google_project_iam_audit_config"],
                "evaluator": self._check_audit_logs,
            },
        ]

    # --- Evaluators ---

    def _check_gcs_uniform_access(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        uniform = resource.get("uniform_bucket_level_access", resource.get("uniform_access", False))
        if uniform:
            return True, "GCS bucket uses uniform bucket-level access", ""
        return False, "GCS bucket does not use uniform bucket-level access", "Enable uniform bucket-level access on GCS bucket"

    def _check_gcs_public_access(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        public = resource.get("publicly_accessible", resource.get("public_access_prevention", "") == "enforced")
        if not public:
            return True, "GCS bucket is not publicly accessible", ""
        return False, "GCS bucket is publicly accessible", "Enable public access prevention on GCS bucket"

    def _check_gce_shielded_vm(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        shielded = resource.get("shielded_instance_config", resource.get("shielded_vm", False))
        if shielded:
            return True, "GCE instance uses Shielded VM features", ""
        return False, "GCE instance does not use Shielded VM features", "Enable Shielded VM on GCE instance"

    def _check_gce_serial_port(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        serial_port = resource.get("serial_port_enabled", resource.get("enable_serial_port", False))
        if not serial_port:
            return True, "GCE instance has serial port access disabled", ""
        return False, "GCE instance has serial port access enabled", "Disable serial port access on GCE instance"

    def _check_gke_private_endpoint(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        private_endpoint = resource.get("private_endpoint_enabled", resource.get("enable_private_endpoint", False))
        if private_endpoint:
            return True, "GKE cluster has private endpoint enabled", ""
        return False, "GKE cluster does not have private endpoint enabled", "Enable private endpoint on GKE cluster"

    def _check_gke_network_policy(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        network_policy = resource.get("network_policy_enabled", resource.get("enable_network_policy", False))
        if network_policy:
            return True, "GKE cluster has network policy enabled", ""
        return False, "GKE cluster does not have network policy enabled", "Enable network policy on GKE cluster"

    def _check_gke_workload_identity(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        workload_identity = resource.get("workload_identity_enabled", resource.get("enable_workload_identity", False))
        if workload_identity:
            return True, "GKE cluster has Workload Identity enabled", ""
        return False, "GKE cluster does not have Workload Identity enabled", "Enable Workload Identity on GKE cluster"

    def _check_service_account_key(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        key_type = resource.get("key_type", resource.get("private_key_type", ""))
        if key_type == "USER_MANAGED":
            return False, "Service account has user-managed key", "Use auto-managed keys instead of user-managed keys"
        return True, "Service account does not have user-managed key", ""

    def _check_vpc_flow_logs(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        flow_logs = resource.get("flow_logs_enabled", resource.get("enable_flow_logs", False))
        if flow_logs:
            return True, "VPC subnet has flow logs enabled", ""
        return False, "VPC subnet does not have flow logs enabled", "Enable VPC flow logs"

    def _check_org_policy(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        enforced = resource.get("enforced", resource.get("is_enforced", False))
        if enforced:
            return True, "Organization policy is enforced", ""
        return False, "Organization policy is not enforced", "Enforce organization policy"

    def _check_scc_enabled(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        enabled = resource.get("enabled", resource.get("is_active", False))
        if enabled:
            return True, "Security Command Center is enabled", ""
        return False, "Security Command Center is not enabled", "Enable Security Command Center"

    def _check_audit_logs(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        enabled = resource.get("enabled", resource.get("audit_log_config", False))
        if enabled:
            return True, "Cloud Audit Logs are enabled for all services", ""
        return False, "Cloud Audit Logs are not enabled for all services", "Enable Cloud Audit Logs for all services"
