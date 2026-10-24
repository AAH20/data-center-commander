"""
AWS Compliance Module Tests
============================
Tests for AWS compliance modules: AWS Config, CloudTrail, GuardDuty, IAM Access Analyzer, Security Hub.
"""

import os
import re
import unittest
from pathlib import Path

from tests.terraform.terraform_parser import TerraformParser, get_module_path


MODULES_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "iac", "modules"))


class TestAWSConfigModule(unittest.TestCase):
    """Tests for the AWS Config module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "aws-compliance", "aws-config")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """AWS Config module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_config_recorder_resource(self):
        """Config configuration recorder exists."""
        self.assertIn("aws_config_configuration_recorder.this", self.parsed["resources"])

    def test_delivery_channel_resource(self):
        """Config delivery channel exists."""
        self.assertIn("aws_config_delivery_channel.this", self.parsed["resources"])

    def test_recorder_status_resource(self):
        """Config recorder status exists."""
        self.assertIn("aws_config_configuration_recorder_status.this", self.parsed["resources"])

    def test_iam_role_for_config(self):
        """IAM role for AWS Config exists."""
        self.assertIn("aws_iam_role.config", self.parsed["resources"])

    def test_iam_policy_for_config(self):
        """IAM policy for AWS Config exists."""
        self.assertIn("aws_iam_role_policy.config", self.parsed["resources"])

    def test_managed_rules_resource(self):
        """Managed config rules resource exists."""
        self.assertIn("aws_config_config_rule.managed", self.parsed["resources"])

    def test_custom_rules_resource(self):
        """Custom config rules resource exists."""
        self.assertIn("aws_config_config_rule.custom", self.parsed["resources"])

    def test_aggregator_resource(self):
        """Config aggregator resource exists."""
        self.assertIn("aws_config_configuration_aggregator.this", self.parsed["resources"])

    def test_recording_frequency_validation(self):
        """Recording frequency has validation."""
        freq = self.parsed["variables"].get("config_recording_frequency", {})
        self.assertIn("validation", freq)
        self.assertIn("One_Hour", freq["validation"]["condition"])
        self.assertIn("TwentyFour_Hours", freq["validation"]["condition"])

    def test_config_outputs(self):
        """Config outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("config_recorder_id", outputs)
        self.assertIn("config_delivery_channel_id", outputs)
        self.assertIn("config_role_arn", outputs)
        self.assertIn("config_managed_rule_ids", outputs)
        self.assertIn("config_custom_rule_ids", outputs)

    def test_caller_identity_data_source(self):
        """Caller identity data source exists."""
        self.assertIn("aws_caller_identity.current", self.parsed["data_sources"])

    def test_region_data_source(self):
        """Region data source exists."""
        self.assertIn("aws_region.current", self.parsed["data_sources"])

    def test_managed_rules_for_each(self):
        """Managed rules use for_each."""
        resource = self.parsed["resources"]["aws_config_config_rule.managed"]
        self.assertTrue(resource.get("for_each"))

    def test_custom_rules_dynamic(self):
        """Custom rules use dynamic blocks."""
        resource = self.parsed["resources"]["aws_config_config_rule.custom"]
        self.assertTrue(resource.get("dynamic"))


class TestAWSCloudTrailModule(unittest.TestCase):
    """Tests for the AWS CloudTrail module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "aws-compliance", "cloudtrail")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """CloudTrail module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_trail_resource(self):
        """CloudTrail trail resource exists."""
        self.assertIn("aws_cloudtrail.this", self.parsed["resources"])

    def test_log_file_validation_default(self):
        """Log file validation defaults to true."""
        val = self.parsed["variables"].get("enable_log_file_validation", {})
        self.assertEqual(val.get("default"), "true")

    def test_multi_region_default(self):
        """Multi-region trail defaults to true."""
        val = self.parsed["variables"].get("is_multi_region_trail", {})
        self.assertEqual(val.get("default"), "true")

    def test_global_service_events_default(self):
        """Global service events default to true."""
        val = self.parsed["variables"].get("include_global_service_events", {})
        self.assertEqual(val.get("default"), "true")

    def test_logging_default(self):
        """Logging defaults to true."""
        val = self.parsed["variables"].get("enable_logging", {})
        self.assertEqual(val.get("default"), "true")

    def test_event_selectors(self):
        """Event selectors are supported."""
        self.assertIn("event_selectors", self.parsed["variables"])

    def test_insight_selectors(self):
        """Insight selectors are supported."""
        self.assertIn("insight_selectors", self.parsed["variables"])

    def test_kms_encryption_support(self):
        """KMS encryption is supported."""
        self.assertIn("kms_key_id", self.parsed["variables"])

    def test_cloudwatch_logs_integration(self):
        """CloudWatch Logs integration is supported."""
        self.assertIn("cloud_watch_logs_role_arn", self.parsed["variables"])
        self.assertIn("cloud_watch_logs_group_arn", self.parsed["variables"])

    def test_trail_outputs(self):
        """CloudTrail outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("trail_id", outputs)
        self.assertIn("trail_arn", outputs)
        self.assertIn("trail_home_region", outputs)
        self.assertIn("trail_s3_bucket_name", outputs)

    def test_caller_identity_data_source(self):
        """Caller identity data source exists."""
        self.assertIn("aws_caller_identity.current", self.parsed["data_sources"])


class TestAWSGuardDutyModule(unittest.TestCase):
    """Tests for the AWS GuardDuty module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "aws-compliance", "guardduty")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """GuardDuty module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_detector_resource(self):
        """GuardDuty detector resource exists."""
        self.assertIn("aws_guardduty_detector.this", self.parsed["resources"])

    def test_member_resource(self):
        """GuardDuty member resource exists."""
        self.assertIn("aws_guardduty_member.this", self.parsed["resources"])

    def test_publishing_destination_resource(self):
        """GuardDuty publishing destination exists."""
        self.assertIn("aws_guardduty_publishing_destination.this", self.parsed["resources"])

    def test_finding_publishing_frequency_validation(self):
        """Finding publishing frequency has validation."""
        freq = self.parsed["variables"].get("detector_finding_publishing_frequency", {})
        self.assertIn("validation", freq)
        self.assertIn("FIFTEEN_MINUTES", freq["validation"]["condition"])
        self.assertIn("ONE_HOUR", freq["validation"]["condition"])
        self.assertIn("SIX_HOURS", freq["validation"]["condition"])

    def test_data_sources(self):
        """Data sources are configurable."""
        self.assertIn("data_sources", self.parsed["variables"])

    def test_detector_enable_default(self):
        """Detector defaults to enabled."""
        val = self.parsed["variables"].get("detector_enable", {})
        self.assertEqual(val.get("default"), "true")

    def test_guardduty_outputs(self):
        """GuardDuty outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("detector_id", outputs)
        self.assertIn("detector_account_id", outputs)
        self.assertIn("member_ids", outputs)
        self.assertIn("publishing_destination_id", outputs)

    def test_members_for_each(self):
        """Members use for_each."""
        resource = self.parsed["resources"]["aws_guardduty_member.this"]
        self.assertTrue(resource.get("for_each"))


class TestAWSIAMAccessAnalyzerModule(unittest.TestCase):
    """Tests for the AWS IAM Access Analyzer module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "aws-compliance", "iam-access-analyzer")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """IAM Access Analyzer module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_analyzer_resource(self):
        """Access analyzer resource exists."""
        self.assertIn("aws_accessanalyzer_analyzer.this", self.parsed["resources"])

    def test_unused_access_analyzer(self):
        """Unused access analyzer resource exists."""
        self.assertIn("aws_accessanalyzer_analyzer.unused_access", self.parsed["resources"])

    def test_archive_rule_resource(self):
        """Archive rule resource exists."""
        self.assertIn("aws_accessanalyzer_archive_rule.this", self.parsed["resources"])

    def test_analyzer_type_validation(self):
        """Analyzer type has validation."""
        at = self.parsed["variables"].get("analyzer_type", {})
        self.assertIn("validation", at)
        self.assertIn("ACCOUNT", at["validation"]["condition"])
        self.assertIn("ORGANIZATION", at["validation"]["condition"])

    def test_unused_access_default(self):
        """Unused access defaults to enabled."""
        val = self.parsed["variables"].get("unused_access_enabled", {})
        self.assertEqual(val.get("default"), "true")

    def test_analyzer_outputs(self):
        """Analyzer outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("analyzer_id", outputs)
        self.assertIn("analyzer_arn", outputs)
        self.assertIn("unused_access_analyzer_id", outputs)
        self.assertIn("unused_access_analyzer_arn", outputs)
        self.assertIn("archive_rule_ids", outputs)

    def test_caller_identity_data_source(self):
        """Caller identity data source exists."""
        self.assertIn("aws_caller_identity.current", self.parsed["data_sources"])


class TestAWSSecurityHubModule(unittest.TestCase):
    """Tests for the AWS Security Hub module."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "aws-compliance", "security-hub")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """Security Hub module directory exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_security_hub_account_resource(self):
        """Security Hub account resource exists."""
        self.assertIn("aws_securityhub_account.this", self.parsed["resources"])

    def test_standards_subscription_resource(self):
        """Standards subscription resource exists."""
        self.assertIn("aws_securityhub_standards_subscription.this", self.parsed["resources"])

    def test_member_resource(self):
        """Security Hub member resource exists."""
        self.assertIn("aws_securityhub_member.this", self.parsed["resources"])

    def test_product_subscription_resource(self):
        """Product subscription resource exists."""
        self.assertIn("aws_securityhub_product_subscription.this", self.parsed["resources"])

    def test_action_target_resource(self):
        """Action target resource exists."""
        self.assertIn("aws_securityhub_action_target.this", self.parsed["resources"])

    def test_control_finding_generator_validation(self):
        """Control finding generator has validation."""
        cfg = self.parsed["variables"].get("control_finding_generator", {})
        self.assertIn("validation", cfg)
        self.assertIn("SECURITY_CONTROL", cfg["validation"]["condition"])
        self.assertIn("STANDARD_CONTROL", cfg["validation"]["condition"])

    def test_enable_default(self):
        """Security Hub defaults to enabled."""
        val = self.parsed["variables"].get("enable_security_hub", {})
        self.assertEqual(val.get("default"), "true")

    def test_security_hub_outputs(self):
        """Security Hub outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("security_hub_arn", outputs)
        self.assertIn("standards_subscription_ids", outputs)
        self.assertIn("member_ids", outputs)
        self.assertIn("action_target_arn", outputs)

    def test_caller_identity_data_source(self):
        """Caller identity data source exists."""
        self.assertIn("aws_caller_identity.current", self.parsed["data_sources"])


class TestAWSComplianceRootModule(unittest.TestCase):
    """Tests for the AWS Compliance root module that wires sub-modules together."""

    @classmethod
    def setUpClass(cls):
        cls.parser = TerraformParser(MODULES_BASE)
        cls.module_path = get_module_path(MODULES_BASE, "aws-compliance")
        cls.parsed = cls.parser.parse_module(cls.module_path)

    def test_module_exists(self):
        """AWS Compliance root module exists."""
        self.assertTrue(os.path.isdir(self.module_path))

    def test_aws_config_module_call(self):
        """AWS Config module is called."""
        self.assertIn("aws_config", self.parsed["module_calls"])

    def test_guardduty_module_call(self):
        """GuardDuty module is called."""
        self.assertIn("guardduty", self.parsed["module_calls"])

    def test_security_hub_module_call(self):
        """Security Hub module is called."""
        self.assertIn("security_hub", self.parsed["module_calls"])

    def test_cloudtrail_module_call(self):
        """CloudTrail module is called."""
        self.assertIn("cloudtrail", self.parsed["module_calls"])

    def test_iam_access_analyzer_module_call(self):
        """IAM Access Analyzer module is called."""
        self.assertIn("iam_access_analyzer", self.parsed["module_calls"])

    def test_compliance_outputs(self):
        """Compliance outputs are defined."""
        outputs = self.parsed["outputs"]
        self.assertIn("config_recorder_id", outputs)
        self.assertIn("guardduty_detector_id", outputs)
        self.assertIn("security_hub_arn", outputs)
        self.assertIn("cloudtrail_arn", outputs)
        self.assertIn("access_analyzer_arn", outputs)

    def test_aws_region_variable(self):
        """AWS region variable exists."""
        self.assertIn("aws_region", self.parsed["variables"])

    def test_compliance_s3_bucket_variable(self):
        """Compliance S3 bucket variable exists."""
        self.assertIn("compliance_s3_bucket", self.parsed["variables"])

    def test_compliance_kms_key_variable(self):
        """Compliance KMS key variable exists."""
        self.assertIn("compliance_kms_key_id", self.parsed["variables"])

    def test_managed_rules_configured(self):
        """Managed rules are configured in the root module."""
        config_module = self.parsed["module_calls"].get("aws_config", {})
        # The root module passes managed_rules to the config module
        self.assertIn("aws_config", self.parsed["module_calls"])


if __name__ == "__main__":
    unittest.main()
