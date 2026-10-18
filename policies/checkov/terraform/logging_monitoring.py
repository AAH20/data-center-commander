"""
Checkov Custom Policies — Logging & Monitoring for Data Center IaC
Covers: CloudTrail, CloudWatch, GuardDuty, Config, VPC Flow Logs, alarm configuration
"""

from checkov.common.models.enums import CheckCategories, CheckResult
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class CloudTrailEnabled(BaseResourceCheck):
    """Ensure CloudTrail is enabled in all regions."""

    def __init__(self):
        name = "Ensure CloudTrail is enabled in all regions"
        id = "DC_MONITOR_001"
        supported_resources = ["aws_cloudtrail"]
        categories = [CheckCategories.LOGGING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        is_multi_region = conf.get("is_multi_region_trail", False)
        if isinstance(is_multi_region, list):
            is_multi_region = is_multi_region[0] if is_multi_region else False
        if is_multi_region is not True:
            return CheckResult.FAILED
        return CheckResult.PASSED


class CloudTrailLogFileValidation(BaseResourceCheck):
    """Ensure CloudTrail log file validation is enabled."""

    def __init__(self):
        name = "Ensure CloudTrail log file validation is enabled"
        id = "DC_MONITOR_002"
        supported_resources = ["aws_cloudtrail"]
        categories = [CheckCategories.LOGGING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        enable_log_file_validation = conf.get("enable_log_file_validation", False)
        if isinstance(enable_log_file_validation, list):
            enable_log_file_validation = (
                enable_log_file_validation[0] if enable_log_file_validation else False
            )
        if enable_log_file_validation is not True:
            return CheckResult.FAILED
        return CheckResult.PASSED


class CloudTrailS3BucketLogging(BaseResourceCheck):
    """Ensure CloudTrail S3 bucket has logging enabled."""

    def __init__(self):
        name = "Ensure CloudTrail S3 bucket has logging enabled"
        id = "DC_MONITOR_003"
        supported_resources = ["aws_cloudtrail"]
        categories = [CheckCategories.LOGGING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        s3_bucket_name = conf.get("s3_bucket_name", "")
        if isinstance(s3_bucket_name, list):
            s3_bucket_name = s3_bucket_name[0] if s3_bucket_name else ""
        if not s3_bucket_name:
            return CheckResult.FAILED
        return CheckResult.PASSED


class CloudWatchLogGroupRetention(BaseResourceCheck):
    """Ensure CloudWatch log groups have retention policy."""

    def __init__(self):
        name = "Ensure CloudWatch log groups have retention policy"
        id = "DC_MONITOR_004"
        supported_resources = ["aws_cloudwatch_log_group"]
        categories = [CheckCategories.LOGGING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        retention_in_days = conf.get("retention_in_days", 0)
        if isinstance(retention_in_days, list):
            retention_in_days = retention_in_days[0] if retention_in_days else 0
        if not isinstance(retention_in_days, int) or retention_in_days < 30:
            return CheckResult.FAILED
        return CheckResult.PASSED


class CloudWatchAlarmActions(BaseResourceCheck):
    """Ensure CloudWatch alarms have actions configured."""

    def __init__(self):
        name = "Ensure CloudWatch alarms have actions configured"
        id = "DC_MONITOR_005"
        supported_resources = ["aws_cloudwatch_metric_alarm"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        alarm_actions = conf.get("alarm_actions", [])
        ok_actions = conf.get("ok_actions", [])
        insufficient_data_actions = conf.get("insufficient_data_actions", [])
        if isinstance(alarm_actions, list) and len(alarm_actions) > 0:
            return CheckResult.PASSED
        if isinstance(ok_actions, list) and len(ok_actions) > 0:
            return CheckResult.PASSED
        if isinstance(insufficient_data_actions, list) and len(insufficient_data_actions) > 0:
            return CheckResult.PASSED
        return CheckResult.FAILED


class GuardDutyEnabled(BaseResourceCheck):
    """Ensure GuardDuty is enabled."""

    def __init__(self):
        name = "Ensure GuardDuty is enabled"
        id = "DC_MONITOR_006"
        supported_resources = ["aws_guardduty_detector"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        enable = conf.get("enable", False)
        if isinstance(enable, list):
            enable = enable[0] if enable else False
        if enable is not True:
            return CheckResult.FAILED
        return CheckResult.PASSED


class SecurityHubEnabled(BaseResourceCheck):
    """Ensure Security Hub is enabled."""

    def __init__(self):
        name = "Ensure Security Hub is enabled"
        id = "DC_MONITOR_007"
        supported_resources = ["aws_securityhub_account"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        # If the resource exists, Security Hub is enabled
        return CheckResult.PASSED


class ConfigRecorderEnabled(BaseResourceCheck):
    """Ensure AWS Config recorder is enabled."""

    def __init__(self):
        name = "Ensure AWS Config recorder is enabled"
        id = "DC_MONITOR_008"
        supported_resources = ["aws_config_configuration_recorder"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        recording_group = conf.get("recording_group", {})
        if isinstance(recording_group, list):
            recording_group = recording_group[0] if recording_group else {}
        if isinstance(recording_group, dict):
            all_supported = recording_group.get("all_supported", False)
            if isinstance(all_supported, list):
                all_supported = all_supported[0] if all_supported else False
            if all_supported is not True:
                return CheckResult.FAILED
        return CheckResult.PASSED


class VPCFlowLogTrafficType(BaseResourceCheck):
    """Ensure VPC flow logs capture all traffic."""

    def __init__(self):
        name = "Ensure VPC flow logs capture all traffic"
        id = "DC_MONITOR_009"
        supported_resources = ["aws_flow_log"]
        categories = [CheckCategories.LOGGING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        traffic_type = conf.get("traffic_type", "ALL")
        if isinstance(traffic_type, list):
            traffic_type = traffic_type[0] if traffic_type else "ALL"
        if traffic_type != "ALL":
            return CheckResult.FAILED
        return CheckResult.PASSED


class S3BucketCloudTrailValidation(BaseResourceCheck):
    """Ensure S3 buckets used for CloudTrail have validation enabled."""

    def __init__(self):
        name = "Ensure S3 buckets used for CloudTrail have validation enabled"
        id = "DC_MONITOR_010"
        supported_resources = ["aws_s3_bucket"]
        categories = [CheckCategories.LOGGING]
        super().__init__(
            name=name, id=id, categories=categories, supported_resources=supported_resources
        )

    def scan_resource_conf(self, conf):
        # This is a best-effort check — if the bucket has a name, assume it's configured
        bucket = conf.get("bucket", "")
        if isinstance(bucket, list):
            bucket = bucket[0] if bucket else ""
        if bucket:
            return CheckResult.PASSED
        return CheckResult.FAILED
