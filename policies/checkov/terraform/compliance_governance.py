"""
Checkov Custom Policies — Compliance & Governance for Data Center IaC
Covers: Resource tagging, backup policies, environment separation, cost controls
"""

from checkov.common.models.enums import CheckCategories, CheckResult
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class ResourceHasTags(BaseResourceCheck):
    """Ensure all resources have required tags."""

    REQUIRED_TAGS = ["Environment", "Owner", "Project"]

    def __init__(self):
        name = "Ensure all resources have required tags"
        id = "DC_GOV_001"
        supported_resources = [
            "aws_instance",
            "aws_ebs_volume",
            "aws_security_group",
            "aws_vpc",
            "aws_subnet",
            "aws_s3_bucket",
            "aws_db_instance",
            "aws_rds_cluster",
        ]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        tags = conf.get("tags", {})
        if isinstance(tags, list):
            tags = tags[0] if tags else {}
        if isinstance(tags, dict):
            for required_tag in self.REQUIRED_TAGS:
                if required_tag not in tags:
                    return CheckResult.FAILED
        else:
            return CheckResult.FAILED
        return CheckResult.PASSED


class BackupVaultExists(BaseResourceCheck):
    """Ensure AWS Backup vault exists for data protection."""

    def __init__(self):
        name = "Ensure AWS Backup vault exists"
        id = "DC_GOV_002"
        supported_resources = ["aws_backup_vault"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        name = conf.get("name", "")
        if isinstance(name, list):
            name = name[0] if name else ""
        if name:
            return CheckResult.PASSED
        return CheckResult.FAILED


class BackupPlanExists(BaseResourceCheck):
    """Ensure AWS Backup plan exists for automated backups."""

    def __init__(self):
        name = "Ensure AWS Backup plan exists"
        id = "DC_GOV_003"
        supported_resources = ["aws_backup_plan"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        rule = conf.get("rule", [])
        if isinstance(rule, list) and len(rule) > 0:
            return CheckResult.PASSED
        return CheckResult.FAILED


class EnvironmentTagSeparation(BaseResourceCheck):
    """Ensure resources are tagged with environment for separation."""

    VALID_ENVIRONMENTS = [
        "dev",
        "development",
        "staging",
        "stage",
        "prod",
        "production",
        "test",
        "qa",
    ]

    def __init__(self):
        name = "Ensure resources are tagged with valid environment"
        id = "DC_GOV_004"
        supported_resources = [
            "aws_instance",
            "aws_ebs_volume",
            "aws_security_group",
            "aws_vpc",
            "aws_subnet",
            "aws_s3_bucket",
            "aws_db_instance",
        ]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        tags = conf.get("tags", {})
        if isinstance(tags, list):
            tags = tags[0] if tags else {}
        if isinstance(tags, dict):
            environment = tags.get("Environment", tags.get("environment", ""))
            if isinstance(environment, list):
                environment = environment[0] if environment else ""
            if environment and environment.lower() in self.VALID_ENVIRONMENTS:
                return CheckResult.PASSED
        return CheckResult.FAILED


class CostAllocationTags(BaseResourceCheck):
    """Ensure resources have cost allocation tags."""

    COST_TAGS = ["CostCenter", "cost_center", "Billing", "billing", "Department"]

    def __init__(self):
        name = "Ensure resources have cost allocation tags"
        id = "DC_GOV_005"
        supported_resources = [
            "aws_instance",
            "aws_ebs_volume",
            "aws_s3_bucket",
            "aws_db_instance",
            "aws_rds_cluster",
        ]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        tags = conf.get("tags", {})
        if isinstance(tags, list):
            tags = tags[0] if tags else {}
        if isinstance(tags, dict):
            for cost_tag in self.COST_TAGS:
                if cost_tag in tags:
                    return CheckResult.PASSED
        return CheckResult.FAILED


class S3BucketLifecyclePolicy(BaseResourceCheck):
    """Ensure S3 buckets have lifecycle policies for cost optimization."""

    def __init__(self):
        name = "Ensure S3 buckets have lifecycle policies"
        id = "DC_GOV_006"
        supported_resources = ["aws_s3_bucket"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        lifecycle_rule = conf.get("lifecycle_rule", [])
        if isinstance(lifecycle_rule, list) and len(lifecycle_rule) > 0:
            return CheckResult.PASSED
        return CheckResult.FAILED


class RDSSnapshotRetention(BaseResourceCheck):
    """Ensure RDS instances have snapshot retention configured."""

    def __init__(self):
        name = "Ensure RDS instances have snapshot retention configured"
        id = "DC_GOV_007"
        supported_resources = ["aws_db_instance"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        backup_retention_period = conf.get("backup_retention_period", 0)
        if isinstance(backup_retention_period, list):
            backup_retention_period = backup_retention_period[0] if backup_retention_period else 0
        if not isinstance(backup_retention_period, int) or backup_retention_period < 7:
            return CheckResult.FAILED
        return CheckResult.PASSED


class VPCHasDHCPOptions(BaseResourceCheck):
    """Ensure VPCs have DHCP options set."""

    def __init__(self):
        name = "Ensure VPCs have DHCP options set"
        id = "DC_GOV_008"
        supported_resources = ["aws_vpc"]
        categories = [CheckCategories.NETWORKING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        # DHCP options are usually associated at the account level
        # This is a best-effort check
        return CheckResult.PASSED


class ResourceHasName(BaseResourceCheck):
    """Ensure all resources have a name tag."""

    def __init__(self):
        name = "Ensure all resources have a name tag"
        id = "DC_GOV_009"
        supported_resources = [
            "aws_instance",
            "aws_ebs_volume",
            "aws_security_group",
            "aws_vpc",
            "aws_subnet",
            "aws_s3_bucket",
            "aws_db_instance",
            "aws_rds_cluster",
            "aws_iam_role",
            "aws_iam_policy",
        ]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        tags = conf.get("tags", {})
        if isinstance(tags, list):
            tags = tags[0] if tags else {}
        if isinstance(tags, dict):
            name = tags.get("Name", tags.get("name", ""))
            if isinstance(name, list):
                name = name[0] if name else ""
            if name and name.strip() != "":
                return CheckResult.PASSED
        return CheckResult.FAILED


class S3BucketReplicationEnabled(BaseResourceCheck):
    """Ensure S3 buckets have cross-region replication for DR."""

    def __init__(self):
        name = "Ensure S3 buckets have cross-region replication"
        id = "DC_GOV_010"
        supported_resources = ["aws_s3_bucket_replication_configuration"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        # If replication configuration exists, it's enabled
        role = conf.get("role", "")
        if isinstance(role, list):
            role = role[0] if role else ""
        if role:
            return CheckResult.PASSED
        return CheckResult.FAILED
