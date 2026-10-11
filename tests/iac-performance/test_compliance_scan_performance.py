"""
Compliance Scan Performance Tests.

Tests the performance of compliance scanning using Checkov
with both built-in and custom data center policies.
"""

import os

import pytest
from utils.checkov_utils import generate_terraform_file, generate_terraform_module

# Performance thresholds for compliance scanning (in milliseconds)
SCAN_THRESHOLDS = {
    "small_built_in": 30_000,  # 30s for small config with built-in checks
    "medium_built_in": 60_000,  # 60s for medium config with built-in checks
    "large_built_in": 120_000,  # 120s for large config with built-in checks
    "small_custom": 30_000,  # 30s for small config with custom checks
    "medium_custom": 60_000,  # 60s for medium config with custom checks
    "large_custom": 120_000,  # 120s for large config with custom checks
    "small_combined": 45_000,  # 45s for small config with combined checks
    "medium_combined": 90_000,  # 90s for medium config with combined checks
    "large_combined": 180_000,  # 180s for large config with combined checks
}


@pytest.mark.checkov
class TestComplianceScanPerformance:
    """Test compliance scan performance across different config sizes."""

    def test_scan_small_built_in(self, checkov_runner, temp_workspace):
        """Test compliance scan with built-in checks on a small config."""
        tf_file = os.path.join(temp_workspace, "main.tf")
        with open(tf_file, "w") as f:
            f.write(generate_terraform_file(resource_count=5, compliant=True))

        result = checkov_runner.scan_directory(temp_workspace)
        assert result.elapsed_ms < SCAN_THRESHOLDS["small_built_in"], (
            f"small built-in scan took {result.elapsed_ms:.1f}ms, "
            f"threshold: {SCAN_THRESHOLDS['small_built_in']}ms"
        )

    def test_scan_medium_built_in(self, checkov_runner, temp_workspace):
        """Test compliance scan with built-in checks on a medium config."""
        tf_file = os.path.join(temp_workspace, "main.tf")
        with open(tf_file, "w") as f:
            f.write(generate_terraform_file(resource_count=25, compliant=True))

        result = checkov_runner.scan_directory(temp_workspace)
        assert result.elapsed_ms < SCAN_THRESHOLDS["medium_built_in"], (
            f"medium built-in scan took {result.elapsed_ms:.1f}ms, "
            f"threshold: {SCAN_THRESHOLDS['medium_built_in']}ms"
        )

    def test_scan_large_built_in(self, checkov_runner, temp_workspace):
        """Test compliance scan with built-in checks on a large config."""
        tf_file = os.path.join(temp_workspace, "main.tf")
        with open(tf_file, "w") as f:
            f.write(generate_terraform_file(resource_count=100, compliant=True))

        result = checkov_runner.scan_directory(temp_workspace)
        assert result.elapsed_ms < SCAN_THRESHOLDS["large_built_in"], (
            f"large built-in scan took {result.elapsed_ms:.1f}ms, "
            f"threshold: {SCAN_THRESHOLDS['large_built_in']}ms"
        )

    def test_scan_small_custom(self, checkov_runner, checkov_policy_dir, temp_workspace):
        """Test compliance scan with custom data center policies on a small config."""
        tf_file = os.path.join(temp_workspace, "main.tf")
        with open(tf_file, "w") as f:
            f.write(generate_terraform_file(resource_count=5, compliant=True))

        result = checkov_runner.scan_with_custom_policies(
            temp_workspace,
            checkov_policy_dir,
        )
        assert result.elapsed_ms < SCAN_THRESHOLDS["small_custom"], (
            f"small custom scan took {result.elapsed_ms:.1f}ms, "
            f"threshold: {SCAN_THRESHOLDS['small_custom']}ms"
        )

    def test_scan_medium_custom(self, checkov_runner, checkov_policy_dir, temp_workspace):
        """Test compliance scan with custom data center policies on a medium config."""
        tf_file = os.path.join(temp_workspace, "main.tf")
        with open(tf_file, "w") as f:
            f.write(generate_terraform_file(resource_count=25, compliant=True))

        result = checkov_runner.scan_with_custom_policies(
            temp_workspace,
            checkov_policy_dir,
        )
        assert result.elapsed_ms < SCAN_THRESHOLDS["medium_custom"], (
            f"medium custom scan took {result.elapsed_ms:.1f}ms, "
            f"threshold: {SCAN_THRESHOLDS['medium_custom']}ms"
        )

    def test_scan_large_custom(self, checkov_runner, checkov_policy_dir, temp_workspace):
        """Test compliance scan with custom data center policies on a large config."""
        tf_file = os.path.join(temp_workspace, "main.tf")
        with open(tf_file, "w") as f:
            f.write(generate_terraform_file(resource_count=100, compliant=True))

        result = checkov_runner.scan_with_custom_policies(
            temp_workspace,
            checkov_policy_dir,
        )
        assert result.elapsed_ms < SCAN_THRESHOLDS["large_custom"], (
            f"large custom scan took {result.elapsed_ms:.1f}ms, "
            f"threshold: {SCAN_THRESHOLDS['large_custom']}ms"
        )


@pytest.mark.checkov
class TestComplianceScanWithNonCompliantResources:
    """Test compliance scan performance with non-compliant resources."""

    def test_scan_non_compliant_small(self, checkov_runner, temp_workspace):
        """Test scan performance with non-compliant resources (small)."""
        tf_file = os.path.join(temp_workspace, "main.tf")
        with open(tf_file, "w") as f:
            f.write(generate_terraform_file(resource_count=5, compliant=False))

        result = checkov_runner.scan_directory(temp_workspace)
        assert result.elapsed_ms < SCAN_THRESHOLDS["small_built_in"]
        # Non-compliant resources should produce failures
        assert result.failed_checks > 0, "Expected failures for non-compliant config"

    def test_scan_non_compliant_medium(self, checkov_runner, temp_workspace):
        """Test scan performance with non-compliant resources (medium)."""
        tf_file = os.path.join(temp_workspace, "main.tf")
        with open(tf_file, "w") as f:
            f.write(generate_terraform_file(resource_count=25, compliant=False))

        result = checkov_runner.scan_directory(temp_workspace)
        assert result.elapsed_ms < SCAN_THRESHOLDS["medium_built_in"]
        assert result.failed_checks > 0, "Expected failures for non-compliant config"

    def test_scan_non_compliant_large(self, checkov_runner, temp_workspace):
        """Test scan performance with non-compliant resources (large)."""
        tf_file = os.path.join(temp_workspace, "main.tf")
        with open(tf_file, "w") as f:
            f.write(generate_terraform_file(resource_count=100, compliant=False))

        result = checkov_runner.scan_directory(temp_workspace)
        assert result.elapsed_ms < SCAN_THRESHOLDS["large_built_in"]
        assert result.failed_checks > 0, "Expected failures for non-compliant config"


@pytest.mark.checkov
class TestComplianceScanScaling:
    """Test how compliance scan scales with resource count."""

    @pytest.mark.parametrize("resource_count", [1, 5, 10, 25, 50, 100])
    def test_scan_scaling(self, checkov_runner, temp_workspace, resource_count):
        """Test that scan time scales reasonably with resource count."""
        tf_file = os.path.join(temp_workspace, "main.tf")
        with open(tf_file, "w") as f:
            f.write(generate_terraform_file(resource_count=resource_count, compliant=True))

        result = checkov_runner.scan_directory(temp_workspace)

        # Rough linear scaling: ~500ms per resource + 10s base
        expected_max = 10000 + (resource_count * 500)
        assert result.elapsed_ms < expected_max, (
            f"scan with {resource_count} resources took {result.elapsed_ms:.1f}ms, "
            f"expected < {expected_max}ms"
        )


@pytest.mark.checkov
class TestComplianceScanWithModules:
    """Test compliance scan performance with terraform modules."""

    def test_scan_with_modules(self, checkov_runner, temp_workspace):
        """Test scan performance when using terraform modules."""
        # Create module
        module_dir = os.path.join(temp_workspace, "modules", "vpc")
        os.makedirs(module_dir, exist_ok=True)
        with open(os.path.join(module_dir, "main.tf"), "w") as f:
            f.write(generate_terraform_module("vpc", resource_count=5))

        # Create main config that uses the module
        with open(os.path.join(temp_workspace, "main.tf"), "w") as f:
            f.write(
                """
module "vpc" {
  source = "./modules/vpc"
}

resource "aws_instance" "server" {
  ami           = "ami-12345678"
  instance_type = "t3.micro"
  tags = {
    Name        = "server"
    Environment = "production"
    Owner       = "test-team"
  }
}
"""
            )

        result = checkov_runner.scan_directory(temp_workspace)
        # Modules add overhead
        assert (
            result.elapsed_ms < 60_000
        ), f"scan with modules took {result.elapsed_ms:.1f}ms, threshold: 60000ms"


@pytest.mark.checkov
class TestComplianceScanSpecificChecks:
    """Test compliance scan performance for specific check categories."""

    def test_scan_network_security_checks(self, checkov_runner, temp_workspace):
        """Test scan performance for network security checks only."""
        tf_file = os.path.join(temp_workspace, "main.tf")
        with open(tf_file, "w") as f:
            f.write(generate_terraform_file(resource_count=10, compliant=True))

        result = checkov_runner.scan_directory(
            temp_workspace,
            check=["DC_NET_001", "DC_NET_002", "DC_NET_003"],
        )
        assert result.elapsed_ms < 30_000

    def test_scan_encryption_checks(self, checkov_runner, temp_workspace):
        """Test scan performance for encryption checks only."""
        tf_file = os.path.join(temp_workspace, "main.tf")
        with open(tf_file, "w") as f:
            f.write(generate_terraform_file(resource_count=10, compliant=True))

        result = checkov_runner.scan_directory(
            temp_workspace,
            check=["DC_CRYPTO_001", "DC_CRYPTO_002", "DC_CRYPTO_003"],
        )
        assert result.elapsed_ms < 30_000

    def test_scan_iam_checks(self, checkov_runner, temp_workspace):
        """Test scan performance for IAM checks only."""
        tf_file = os.path.join(temp_workspace, "main.tf")
        with open(tf_file, "w") as f:
            f.write(generate_terraform_file(resource_count=10, compliant=True))

        result = checkov_runner.scan_directory(
            temp_workspace,
            check=["DC_IAM_001", "DC_IAM_002", "DC_IAM_003"],
        )
        assert result.elapsed_ms < 30_000
