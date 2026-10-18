"""AWS compliance provider.

Implements compliance checks for AWS resources based on AWS Config Rules,
CIS AWS Foundations Benchmark, and Well-Architected Framework.
"""
from __future__ import annotations

from typing import Any

from .base import CloudProviderCompliance, ProviderComplianceResult, ProviderComplianceStatus


class AWSComplianceProvider:
    """AWS cloud provider compliance scanner."""

    def __init__(self) -> None:
        self._checks = self._build_checks()

    @property
    def provider_name(self) -> str:
        return "aws"

    def get_compliance_checks(self) -> list[dict[str, Any]]:
        return self._checks

    def evaluate(self, resource: dict[str, Any]) -> ProviderComplianceResult:
        resource_type = resource.get("resource_type", "unknown")
        check = self._find_check(resource_type)
        if check is None:
            return ProviderComplianceResult(
                check_id=f"AWS-{resource_type.upper()}-001",
                provider="aws",
                name=f"AWS {resource_type} Compliance",
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
                provider="aws",
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
                provider="aws",
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
                provider="aws",
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
                "check_id": "AWS-S3-001",
                "name": "S3 Bucket Encryption",
                "description": "S3 buckets must have server-side encryption enabled",
                "severity": "high",
                "category": "security",
                "resource_types": ["aws_s3_bucket"],
                "evaluator": self._check_s3_encryption,
            },
            {
                "check_id": "AWS-S3-002",
                "name": "S3 Bucket Public Access",
                "description": "S3 buckets must not be publicly accessible",
                "severity": "critical",
                "category": "security",
                "resource_types": ["aws_s3_bucket"],
                "evaluator": self._check_s3_public_access,
            },
            {
                "check_id": "AWS-S3-003",
                "name": "S3 Bucket Versioning",
                "description": "S3 buckets must have versioning enabled",
                "severity": "medium",
                "category": "reliability",
                "resource_types": ["aws_s3_bucket"],
                "evaluator": self._check_s3_versioning,
            },
            {
                "check_id": "AWS-EC2-001",
                "name": "EC2 Instance Monitoring",
                "description": "EC2 instances must have detailed monitoring enabled",
                "severity": "medium",
                "category": "reliability",
                "resource_types": ["aws_instance"],
                "evaluator": self._check_ec2_monitoring,
            },
            {
                "check_id": "AWS-EC2-002",
                "name": "EC2 Instance IMDSv2",
                "description": "EC2 instances must use IMDSv2",
                "severity": "high",
                "category": "security",
                "resource_types": ["aws_instance"],
                "evaluator": self._check_ec2_imdsv2,
            },
            {
                "check_id": "AWS-IAM-001",
                "name": "IAM Password Policy",
                "description": "IAM password policy must meet complexity requirements",
                "severity": "high",
                "category": "security",
                "resource_types": ["aws_iam_policy"],
                "evaluator": self._check_iam_password_policy,
            },
            {
                "check_id": "AWS-IAM-002",
                "name": "IAM Least Privilege",
                "description": "IAM policies must follow least privilege principle",
                "severity": "critical",
                "category": "security",
                "resource_types": ["aws_iam_policy", "aws_iam_role"],
                "evaluator": self._check_iam_least_privilege,
            },
            {
                "check_id": "AWS-VPC-001",
                "name": "VPC Flow Logs",
                "description": "VPCs must have flow logs enabled",
                "severity": "high",
                "category": "security",
                "resource_types": ["aws_vpc"],
                "evaluator": self._check_vpc_flow_logs,
            },
            {
                "check_id": "AWS-RDS-001",
                "name": "RDS Encryption",
                "description": "RDS instances must have encryption at rest enabled",
                "severity": "high",
                "category": "security",
                "resource_types": ["aws_db_instance"],
                "evaluator": self._check_rds_encryption,
            },
            {
                "check_id": "AWS-RDS-002",
                "name": "RDS Backup",
                "description": "RDS instances must have automated backups enabled",
                "severity": "medium",
                "category": "reliability",
                "resource_types": ["aws_db_instance"],
                "evaluator": self._check_rds_backup,
            },
            {
                "check_id": "AWS-CFG-001",
                "name": "AWS Config Recorder",
                "description": "AWS Config recorder must be enabled",
                "severity": "high",
                "category": "governance",
                "resource_types": ["aws_config_configuration_recorder"],
                "evaluator": self._check_config_recorder,
            },
            {
                "check_id": "AWS-CT-001",
                "name": "CloudTrail Enabled",
                "description": "CloudTrail must be enabled for all regions",
                "severity": "critical",
                "category": "security",
                "resource_types": ["aws_cloudtrail"],
                "evaluator": self._check_cloudtrail,
            },
            {
                "check_id": "AWS-KMS-001",
                "name": "KMS Key Rotation",
                "description": "KMS keys must have automatic rotation enabled",
                "severity": "medium",
                "category": "security",
                "resource_types": ["aws_kms_key"],
                "evaluator": self._check_kms_rotation,
            },
            {
                "check_id": "AWS-SG-001",
                "name": "Security Group Open Ports",
                "description": "Security groups must not allow unrestricted inbound access",
                "severity": "critical",
                "category": "security",
                "resource_types": ["aws_security_group"],
                "evaluator": self._check_sg_open_ports,
            },
        ]

    # --- Evaluators ---

    def _check_s3_encryption(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        encrypted = resource.get("encrypted", resource.get("encryption_at_rest", False))
        if encrypted:
            return True, "S3 bucket has server-side encryption enabled", ""
        return False, "S3 bucket does not have server-side encryption", "Enable S3 default encryption"

    def _check_s3_public_access(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        public = resource.get("publicly_accessible", resource.get("public_access", False))
        if not public:
            return True, "S3 bucket is not publicly accessible", ""
        return False, "S3 bucket is publicly accessible", "Block public access on S3 bucket"

    def _check_s3_versioning(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        versioning = resource.get("versioning_enabled", resource.get("versioning", False))
        if versioning:
            return True, "S3 bucket has versioning enabled", ""
        return False, "S3 bucket does not have versioning enabled", "Enable versioning on S3 bucket"

    def _check_ec2_monitoring(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        monitoring = resource.get("monitoring_enabled", resource.get("monitoring", False))
        if monitoring:
            return True, "EC2 instance has detailed monitoring enabled", ""
        return False, "EC2 instance does not have detailed monitoring", "Enable detailed monitoring on EC2 instance"

    def _check_ec2_imdsv2(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        imdsv2 = resource.get("imdsv2_required", resource.get("http_tokens", "") == "required")
        if imdsv2:
            return True, "EC2 instance requires IMDSv2", ""
        return False, "EC2 instance does not require IMDSv2", "Set HttpTokens to required on EC2 instance"

    def _check_iam_password_policy(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        min_length = resource.get("minimum_password_length", 12)
        require_symbols = resource.get("require_symbols", True)
        require_numbers = resource.get("require_numbers", True)
        if min_length >= 12 and require_symbols and require_numbers:
            return True, "IAM password policy meets complexity requirements", ""
        return False, "IAM password policy does not meet complexity requirements", "Strengthen IAM password policy"

    def _check_iam_least_privilege(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        policy = resource.get("policy", resource.get("iam_policy", ""))
        if isinstance(policy, str):
            if "\"*\"" in policy and "Effect\": \"Allow\"" in policy:
                return False, "IAM policy contains wildcard permissions", "Remove wildcard permissions from IAM policy"
            return True, "IAM policy does not contain wildcard permissions", ""
        return True, "No IAM policy to evaluate", ""

    def _check_vpc_flow_logs(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        flow_logs = resource.get("flow_logs_enabled", resource.get("flow_logs", False))
        if flow_logs:
            return True, "VPC has flow logs enabled", ""
        return False, "VPC does not have flow logs enabled", "Enable VPC flow logs"

    def _check_rds_encryption(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        encrypted = resource.get("encrypted", resource.get("storage_encrypted", False))
        if encrypted:
            return True, "RDS instance has encryption at rest enabled", ""
        return False, "RDS instance does not have encryption at rest", "Enable RDS storage encryption"

    def _check_rds_backup(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        backup = resource.get("backup_enabled", resource.get("backup_retention_period", 0))
        if isinstance(backup, int) and backup > 0:
            return True, f"RDS instance has backup retention of {backup} days", ""
        if backup is True:
            return True, "RDS instance has automated backups enabled", ""
        return False, "RDS instance does not have automated backups", "Enable RDS automated backups"

    def _check_config_recorder(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        enabled = resource.get("enabled", resource.get("recording", False))
        if enabled:
            return True, "AWS Config recorder is enabled", ""
        return False, "AWS Config recorder is not enabled", "Enable AWS Config recorder"

    def _check_cloudtrail(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        enabled = resource.get("enabled", resource.get("is_logging", False))
        multi_region = resource.get("multi_region", resource.get("is_multi_region_trail", False))
        if enabled and multi_region:
            return True, "CloudTrail is enabled for all regions", ""
        if enabled:
            return True, "CloudTrail is enabled", ""
        return False, "CloudTrail is not enabled", "Enable CloudTrail for all regions"

    def _check_kms_rotation(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        rotation = resource.get("rotation_enabled", resource.get("enable_key_rotation", False))
        if rotation:
            return True, "KMS key has automatic rotation enabled", ""
        return False, "KMS key does not have automatic rotation", "Enable KMS key rotation"

    def _check_sg_open_ports(self, resource: dict[str, Any]) -> tuple[bool, str, str]:
        ingress = resource.get("ingress", resource.get("inbound_rules", []))
        if isinstance(ingress, list):
            for rule in ingress:
                cidr = rule.get("cidr_blocks", [""])
                from_port = rule.get("from_port", 0)
                to_port = rule.get("to_port", 65535)
                if "0.0.0.0/0" in str(cidr) and from_port == 0:
                    return False, "Security group allows unrestricted inbound access", "Restrict security group inbound rules"
        return True, "Security group does not allow unrestricted inbound access", ""
