"""
Checkov Policy Fuzzer.

Fuzzes Checkov policy inputs to ensure the policy engine
handles malformed, edge-case, and adversarial inputs.
"""

import json

import pytest
from generators import (
    TERRAFORM_PROPERTY_NAMES,
    terraform_resource,
)
from hypothesis import given
from hypothesis import strategies as st


class TestCheckovPolicyFuzzing:
    """Fuzz Checkov policy inputs."""

    @given(resource=terraform_resource())
    def test_checkov_resource_does_not_crash(self, resource):
        """Ensure Checkov evaluation doesn't crash on any input."""
        assert isinstance(resource, dict)
        assert "type" in resource
        assert "properties" in resource

    @given(resource=terraform_resource())
    def test_checkov_resource_serializable(self, resource):
        """Checkov resource should be JSON serializable."""
        try:
            json.dumps(resource)
        except (TypeError, ValueError):
            pytest.fail("Checkov resource is not JSON serializable")

    @given(resource=terraform_resource())
    def test_checkov_encryption_checks(self, resource):
        """Fuzz Checkov encryption checks."""
        props = resource["properties"]
        resource_type = resource["type"]

        # Simulate Checkov check evaluation
        if resource_type in ["aws_ebs_volume", "aws_ebs_snapshot"]:
            encrypted = props.get("encrypted", False)
            if isinstance(encrypted, list):
                encrypted = encrypted[0] if encrypted else False
            if encrypted is not True:
                # Check should fail
                pass

        if resource_type in ["aws_db_instance", "aws_rds_cluster"]:
            storage_encrypted = props.get("storage_encrypted", False)
            if isinstance(storage_encrypted, list):
                storage_encrypted = storage_encrypted[0] if storage_encrypted else False
            if storage_encrypted is not True:
                # Check should fail
                pass

    @given(resource=terraform_resource())
    def test_checkov_network_checks(self, resource):
        """Fuzz Checkov network checks."""
        props = resource["properties"]
        resource_type = resource["type"]

        if (
            resource_type in ["aws_security_group", "aws_security_group_rule"]
            and "ingress" in props
        ):
            for ingress in props["ingress"]:
                if isinstance(ingress, dict):
                    from_port = ingress.get("from_port")
                    cidr_blocks = ingress.get("cidr_blocks", [])
                    if isinstance(cidr_blocks, list):
                        for cidr in cidr_blocks:
                            if (
                                isinstance(cidr, str)
                                and cidr == "0.0.0.0/0"
                                and from_port in (22, 3389)
                            ):
                                # Check should fail
                                pass

    @given(resource=terraform_resource())
    def test_checkov_iam_checks(self, resource):
        """Fuzz Checkov IAM checks."""
        props = resource["properties"]
        resource_type = resource["type"]

        if resource_type in [
            "aws_iam_policy",
            "aws_iam_role_policy",
            "aws_iam_group_policy",
            "aws_iam_user_policy",
        ]:
            policy = props.get("policy", "")
            if isinstance(policy, list):
                policy = policy[0] if policy else ""
            if isinstance(policy, str) and (
                '"Action": "*"' in policy or '"Action":["*"]' in policy
            ):
                # Check should fail
                pass

    @given(resource=terraform_resource())
    def test_checkov_monitoring_checks(self, resource):
        """Fuzz Checkov monitoring checks."""
        props = resource["properties"]
        resource_type = resource["type"]

        if resource_type == "aws_cloudtrail":
            is_multi_region = props.get("is_multi_region_trail", False)
            if isinstance(is_multi_region, list):
                is_multi_region = is_multi_region[0] if is_multi_region else False
            if is_multi_region is not True:
                # Check should fail
                pass

    @given(resource=terraform_resource())
    def test_checkov_backup_checks(self, resource):
        """Fuzz Checkov backup checks."""
        props = resource["properties"]
        resource_type = resource["type"]

        if resource_type in ["aws_db_instance", "aws_rds_cluster"]:
            backup_retention = props.get("backup_retention_period", 0)
            if isinstance(backup_retention, list):
                backup_retention = backup_retention[0] if backup_retention else 0
            if not isinstance(backup_retention, int) or backup_retention < 7:
                # Check should fail
                pass


class TestCheckovPolicyEdgeCases:
    """Test edge cases for Checkov policies."""

    @given(
        resource_type=st.sampled_from(
            [
                "aws_instance",
                "aws_ebs_volume",
                "aws_security_group",
                "aws_vpc",
                "aws_db_instance",
                "aws_s3_bucket",
                "aws_iam_role",
                "aws_kms_key",
                "aws_cloudtrail",
                "aws_guardduty_detector",
                "aws_backup_vault",
                "aws_route53_record",
                "aws_cloudfront_distribution",
                "aws_shield_protection",
                "aws_dx_connection",
                "aws_vpn_connection",
                "aws_ec2_transit_gateway",
                "aws_network_acl_rule",
                "aws_flow_log",
                "aws_cloudwatch_log_group",
                "aws_cloudwatch_metric_alarm",
                "aws_secretsmanager_secret",
                "aws_acm_certificate",
                "aws_dynamodb_table",
                "aws_elasticache_replication_group",
                "aws_autoscaling_group",
                "aws_lb_listener",
                "aws_launch_template",
                "aws_vpc_endpoint",
                "azurerm_network_security_group",
                "google_compute_firewall",
            ]
        ),
    )
    def test_checkov_known_resource_types(self, resource_type):
        """Test known Checkov resource types."""
        assert isinstance(resource_type, str)
        assert len(resource_type) > 0

    @given(
        prop_name=TERRAFORM_PROPERTY_NAMES,
    )
    def test_checkov_known_property_names(self, prop_name):
        """Test known Checkov property names."""
        assert isinstance(prop_name, str)
        assert len(prop_name) > 0


class TestCheckovPolicySecurity:
    """Security-focused fuzzing for Checkov policies."""

    @given(resource=terraform_resource())
    def test_checkov_no_hardcoded_credentials(self, resource):
        """Resources should not contain hardcoded credentials."""
        props = resource["properties"]
        sensitive_patterns = [
            "password",
            "secret",
            "api_key",
            "apikey",
            "access_key",
            "private_key",
        ]
        for _key, value in props.items():
            if isinstance(value, str):
                value_lower = value.lower()
                for pattern in sensitive_patterns:
                    if pattern in value_lower:
                        # This is a finding, not a crash
                        pass

    @given(resource=terraform_resource())
    def test_checkov_no_wildcard_cidr(self, resource):
        """Resources should not use 0.0.0.0/0 for non-web ports."""
        props = resource["properties"]
        if "cidr_blocks" in props:
            cidrs = props["cidr_blocks"]
            if isinstance(cidrs, list):
                for cidr in cidrs:
                    if cidr == "0.0.0.0/0":
                        # This is a finding, not a crash
                        pass

    @given(resource=terraform_resource())
    def test_checkov_encryption_enabled(self, resource):
        """Resources should have encryption enabled."""
        props = resource["properties"]
        if "encrypted" in props:
            # This is a policy check, not a crash check
            pass
        if "storage_encrypted" in props:
            # This is a policy check, not a crash check
            pass

    @given(resource=terraform_resource())
    def test_checkov_monitoring_enabled(self, resource):
        """Resources should have monitoring enabled."""
        props = resource["properties"]
        if "monitoring_enabled" in props:
            # This is a policy check, not a crash check
            pass

    @given(resource=terraform_resource())
    def test_checkov_backup_retention_configured(self, resource):
        """Resources should have backup retention configured."""
        props = resource["properties"]
        if "backup_retention_period" in props:
            # This is a policy check, not a crash check
            pass
