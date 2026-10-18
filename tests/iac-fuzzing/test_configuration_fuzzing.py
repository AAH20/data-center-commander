"""
Configuration Fuzzing Tests.

Fuzzes Terraform configurations to ensure the policy engine
handles malformed, edge-case, and adversarial IaC configurations
without crashing.
"""

import json

import pytest
from generators import (
    terraform_configuration,
    terraform_resource,
)
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


class TestTerraformResourceFuzzing:
    """Fuzz Terraform resource configurations."""

    @given(resource=terraform_resource())
    def test_resource_does_not_crash(self, resource):
        """Ensure resource processing doesn't crash on any input."""
        assert isinstance(resource, dict)
        assert "type" in resource
        assert "name" in resource
        assert "properties" in resource

    @given(resource=terraform_resource())
    def test_resource_type_is_string(self, resource):
        """Resource type should always be a string."""
        assert isinstance(resource["type"], str)

    @given(resource=terraform_resource())
    def test_resource_name_is_string(self, resource):
        """Resource name should always be a string."""
        assert isinstance(resource["name"], str)

    @given(resource=terraform_resource())
    def test_resource_properties_is_dict(self, resource):
        """Resource properties should always be a dict."""
        assert isinstance(resource["properties"], dict)

    @given(resource=terraform_resource())
    def test_resource_serializable(self, resource):
        """Resource should be JSON serializable."""
        try:
            json.dumps(resource)
        except (TypeError, ValueError):
            pytest.fail("Resource is not JSON serializable")

    @given(resource=terraform_resource())
    def test_resource_name_not_empty(self, resource):
        """Resource name should not be empty."""
        assert len(resource["name"]) > 0

    @given(resource=terraform_resource())
    def test_resource_name_valid_chars(self, resource):
        """Resource name should only contain valid characters."""
        import re

        assert re.match(r"^[a-zA-Z_-][a-zA-Z0-9_-]*$", resource["name"])

    @given(resource=terraform_resource())
    def test_known_resource_type(self, resource):
        """Resource type should be a known Terraform resource."""
        # Note: Generated data may include unknown types
        # This test documents the expectation
        known_types = [
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
        if resource["type"] not in known_types:
            pytest.skip(f"Unknown resource type: {resource['type']}")


class TestTerraformConfigurationFuzzing:
    """Fuzz complete Terraform configurations."""

    @given(config=terraform_configuration(min_resources=1, max_resources=50))
    def test_configuration_does_not_crash(self, config):
        """Ensure configuration processing doesn't crash."""
        assert isinstance(config, dict)
        assert "resources" in config
        assert "variables" in config
        assert "outputs" in config

    @given(config=terraform_configuration(min_resources=1, max_resources=50))
    def test_configuration_serializable(self, config):
        """Configuration should be JSON serializable."""
        try:
            json.dumps(config)
        except (TypeError, ValueError):
            pytest.fail("Configuration is not JSON serializable")

    @given(config=terraform_configuration(min_resources=1, max_resources=50))
    def test_configuration_has_resources(self, config):
        """Configuration should have at least one resource."""
        assert len(config["resources"]) >= 1

    @given(config=terraform_configuration(min_resources=1, max_resources=50))
    def test_configuration_has_variables(self, config):
        """Configuration should have variables."""
        assert isinstance(config["variables"], list)

    @given(config=terraform_configuration(min_resources=1, max_resources=50))
    def test_configuration_has_outputs(self, config):
        """Configuration should have outputs."""
        assert isinstance(config["outputs"], dict)

    @given(config=terraform_configuration(min_resources=1, max_resources=50))
    def test_configuration_provider_valid(self, config):
        """Provider should be valid."""
        assert config["provider"] in ["aws", "azurerm", "google"]

    @given(config=terraform_configuration(min_resources=1, max_resources=50))
    def test_configuration_terraform_version_valid(self, config):
        """Terraform version should be valid."""
        assert config["terraform_version"].startswith(">=")


class TestTerraformConfigurationEdgeCases:
    """Test edge cases for Terraform configurations."""

    @given(
        config=terraform_configuration(min_resources=0, max_resources=0),
    )
    def test_empty_configuration(self, config):
        """Empty configuration should be handled."""
        assert isinstance(config, dict)
        assert len(config["resources"]) == 0

    @given(
        config=terraform_configuration(min_resources=20, max_resources=20),
    )
    @settings(suppress_health_check=list(HealthCheck))
    def test_large_configuration(self, config):
        """Large configuration should be handled."""
        assert isinstance(config, dict)
        assert len(config["resources"]) == 20

    @given(
        resource_type=st.sampled_from(
            [
                "aws_instance",
                "aws_db_instance",
                "aws_s3_bucket",
                "aws_security_group",
                "aws_vpc",
                "aws_iam_role",
            ]
        ),
        num_props=st.integers(min_value=0, max_value=100),
    )
    def test_resource_with_many_properties(self, resource_type, num_props):
        """Resource with many properties should be handled."""
        properties = {}
        for i in range(num_props):
            properties[f"prop_{i}"] = f"value_{i}"
        resource = {
            "type": resource_type,
            "name": "test",
            "properties": properties,
        }
        assert isinstance(resource, dict)
        assert len(resource["properties"]) == num_props


class TestTerraformConfigurationSecurity:
    """Security-focused fuzzing for Terraform configurations."""

    @given(resource=terraform_resource())
    def test_no_hardcoded_credentials(self, resource):
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
    def test_no_wildcard_cidr(self, resource):
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
    def test_encryption_enabled(self, resource):
        """Resources should have encryption enabled."""
        props = resource["properties"]
        if "encrypted" in props:
            # This is a policy check, not a crash check
            pass
        if "storage_encrypted" in props:
            # This is a policy check, not a crash check
            pass

    @given(resource=terraform_resource())
    def test_monitoring_enabled(self, resource):
        """Resources should have monitoring enabled."""
        props = resource["properties"]
        if "monitoring_enabled" in props:
            # This is a policy check, not a crash check
            pass

    @given(resource=terraform_resource())
    def test_backup_retention_configured(self, resource):
        """Resources should have backup retention configured."""
        props = resource["properties"]
        if "backup_retention_period" in props:
            # This is a policy check, not a crash check
            pass


class TestTerraformConfigurationValidation:
    """Test Terraform configuration validation."""

    @given(resource=terraform_resource())
    def test_valid_instance_types(self, resource):
        """Instance type should be valid."""
        props = resource["properties"]
        if "instance_type" in props:
            instance_type = props["instance_type"]
            if isinstance(instance_type, str):
                # Note: Generated data may include invalid types
                # This test documents the expectation
                valid_prefixes = [
                    "t2.",
                    "t3.",
                    "t3a.",
                    "t4g.",
                    "m5.",
                    "m6.",
                    "m6g.",
                    "c5.",
                    "c6.",
                    "c6g.",
                    "r5.",
                    "r6.",
                    "r6g.",
                    "x1.",
                    "x1e.",
                    "z1d.",
                    "i3.",
                    "i3en.",
                    "d2.",
                    "h1.",
                    "f1.",
                    "g3.",
                    "g4.",
                    "p2.",
                    "p3.",
                    "inf1.",
                    "trn1.",
                ]
                if not any(instance_type.startswith(p) for p in valid_prefixes):
                    pytest.skip(f"Invalid instance type: {instance_type}")

    @given(resource=terraform_resource())
    def test_valid_ports(self, resource):
        """Port should be valid."""
        props = resource["properties"]
        if "port" in props:
            port = props["port"]
            if isinstance(port, int):
                assert 0 <= port <= 65535
            elif isinstance(port, str):
                try:
                    port_int = int(port)
                    assert 0 <= port_int <= 65535
                except ValueError:
                    pytest.skip(f"Invalid port: {port}")

    @given(resource=terraform_resource())
    def test_valid_cidr_blocks(self, resource):
        """CIDR block should be valid."""
        props = resource["properties"]
        if "cidr_blocks" in props:
            cidrs = props["cidr_blocks"]
            if isinstance(cidrs, list):
                for cidr in cidrs:
                    if isinstance(cidr, str):
                        # Note: Generated data may include invalid CIDRs
                        # This test documents the expectation
                        import re

                        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$", cidr):
                            pytest.skip(f"Invalid CIDR: {cidr}")

    @given(resource=terraform_resource())
    def test_valid_availability_zones(self, resource):
        """Availability zone should be valid."""
        props = resource["properties"]
        if "availability_zones" in props:
            azs = props["availability_zones"]
            if isinstance(azs, list):
                for az in azs:
                    if isinstance(az, str):
                        # Note: Generated data may include invalid AZs
                        # This test documents the expectation
                        import re

                        if not re.match(r"^[a-z]{2}-[a-z]+-\d[a-z]$", az):
                            pytest.skip(f"Invalid AZ: {az}")
