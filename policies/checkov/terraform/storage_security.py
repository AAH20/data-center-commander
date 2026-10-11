"""
Checkov Custom Policies — Storage Security for Data Center IaC
Covers: EBS encryption, S3 bucket security, RDS storage, snapshot encryption
"""

from checkov.common.models.enums import CheckCategories, CheckResult
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class EBSEncryptionEnabled(BaseResourceCheck):
    """Ensure EBS volumes are encrypted."""

    def __init__(self):
        name = "Ensure EBS volumes are encrypted"
        id = "DC_STORAGE_001"
        supported_resources = ["aws_ebs_volume", "aws_ebs_snapshot"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        encrypted = conf.get("encrypted", False)
        if isinstance(encrypted, list):
            encrypted = encrypted[0] if encrypted else False
        if encrypted is not True:
            return CheckResult.FAILED
        return CheckResult.PASSED


class EBSSnapshotEncrypted(BaseResourceCheck):
    """Ensure EBS snapshots are encrypted."""

    def __init__(self):
        name = "Ensure EBS snapshots are encrypted"
        id = "DC_STORAGE_002"
        supported_resources = ["aws_ebs_snapshot", "aws_ebs_snapshot_copy"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        encrypted = conf.get("encrypted", False)
        if isinstance(encrypted, list):
            encrypted = encrypted[0] if encrypted else False
        if encrypted is not True:
            return CheckResult.FAILED
        return CheckResult.PASSED


class S3BucketEncryptionEnabled(BaseResourceCheck):
    """Ensure S3 buckets have default encryption enabled."""

    def __init__(self):
        name = "Ensure S3 buckets have default encryption enabled"
        id = "DC_STORAGE_003"
        supported_resources = ["aws_s3_bucket"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        # Check for server_side_encryption_configuration
        sse_config = conf.get("server_side_encryption_configuration", [])
        if isinstance(sse_config, list) and len(sse_config) > 0:
            return CheckResult.PASSED
        # Check for rule
        rule = conf.get("rule", [])
        if isinstance(rule, list) and len(rule) > 0:
            return CheckResult.PASSED
        return CheckResult.FAILED


class S3BucketPublicAccessBlock(BaseResourceCheck):
    """Ensure S3 buckets block public access."""

    def __init__(self):
        name = "Ensure S3 buckets block public access"
        id = "DC_STORAGE_004"
        supported_resources = ["aws_s3_bucket_public_access_block"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        block_public_acls = conf.get("block_public_acls", False)
        block_public_policy = conf.get("block_public_policy", False)
        ignore_public_acls = conf.get("ignore_public_acls", False)
        restrict_public_buckets = conf.get("restrict_public_buckets", False)
        if isinstance(block_public_acls, list):
            block_public_acls = block_public_acls[0] if block_public_acls else False
        if isinstance(block_public_policy, list):
            block_public_policy = block_public_policy[0] if block_public_policy else False
        if isinstance(ignore_public_acls, list):
            ignore_public_acls = ignore_public_acls[0] if ignore_public_acls else False
        if isinstance(restrict_public_buckets, list):
            restrict_public_buckets = (
                restrict_public_buckets[0] if restrict_public_buckets else False
            )
        if not all(
            [block_public_acls, block_public_policy, ignore_public_acls, restrict_public_buckets]
        ):
            return CheckResult.FAILED
        return CheckResult.PASSED


class S3BucketVersioningEnabled(BaseResourceCheck):
    """Ensure S3 buckets have versioning enabled."""

    def __init__(self):
        name = "Ensure S3 buckets have versioning enabled"
        id = "DC_STORAGE_005"
        supported_resources = ["aws_s3_bucket"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        versioning = conf.get("versioning", {})
        if isinstance(versioning, list):
            versioning = versioning[0] if versioning else {}
        if isinstance(versioning, dict):
            enabled = versioning.get("enabled", False)
            if isinstance(enabled, list):
                enabled = enabled[0] if enabled else False
            if enabled is not True:
                return CheckResult.FAILED
        else:
            return CheckResult.FAILED
        return CheckResult.PASSED


class S3BucketLoggingEnabled(BaseResourceCheck):
    """Ensure S3 buckets have logging enabled."""

    def __init__(self):
        name = "Ensure S3 buckets have logging enabled"
        id = "DC_STORAGE_006"
        supported_resources = ["aws_s3_bucket"]
        categories = [CheckCategories.LOGGING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        logging_config = conf.get("logging", {})
        if isinstance(logging_config, list):
            logging_config = logging_config[0] if logging_config else {}
        if isinstance(logging_config, dict) and len(logging_config) > 0:
            return CheckResult.PASSED
        return CheckResult.FAILED


class RDSEncryptionEnabled(BaseResourceCheck):
    """Ensure RDS instances have storage encryption enabled."""

    def __init__(self):
        name = "Ensure RDS instances have storage encryption enabled"
        id = "DC_STORAGE_007"
        supported_resources = ["aws_db_instance", "aws_rds_cluster"]
        categories = [CheckCategories.ENCRYPTION]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        storage_encrypted = conf.get("storage_encrypted", False)
        if isinstance(storage_encrypted, list):
            storage_encrypted = storage_encrypted[0] if storage_encrypted else False
        if storage_encrypted is not True:
            return CheckResult.FAILED
        return CheckResult.PASSED


class RDSBackupRetentionEnabled(BaseResourceCheck):
    """Ensure RDS instances have backup retention configured."""

    def __init__(self):
        name = "Ensure RDS instances have backup retention configured"
        id = "DC_STORAGE_008"
        supported_resources = ["aws_db_instance", "aws_rds_cluster"]
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


class RDSPubliclyAccessible(BaseResourceCheck):
    """Ensure RDS instances are not publicly accessible."""

    def __init__(self):
        name = "Ensure RDS instances are not publicly accessible"
        id = "DC_STORAGE_009"
        supported_resources = ["aws_db_instance", "aws_rds_cluster"]
        categories = [CheckCategories.NETWORKING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        publicly_accessible = conf.get("publicly_accessible", False)
        if isinstance(publicly_accessible, list):
            publicly_accessible = publicly_accessible[0] if publicly_accessible else False
        if publicly_accessible is True:
            return CheckResult.FAILED
        return CheckResult.PASSED


class S3BucketObjectLockEnabled(BaseResourceCheck):
    """Ensure S3 buckets have object lock enabled for compliance."""

    def __init__(self):
        name = "Ensure S3 buckets have object lock enabled"
        id = "DC_STORAGE_010"
        supported_resources = ["aws_s3_bucket"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        object_lock = conf.get("object_lock_enabled", False)
        if isinstance(object_lock, list):
            object_lock = object_lock[0] if object_lock else False
        if object_lock is not True:
            return CheckResult.FAILED
        return CheckResult.PASSED
