"""
Terraform Plan Performance Tests.

Tests the performance of terraform plan operations with varying
configuration sizes and complexity levels.
"""

import os
from contextlib import suppress

import pytest
from utils.terraform_utils import (
    TerraformRunner,
    cleanup_workspace,
    create_terraform_workspace,
    generate_terraform_config,
)

# Performance thresholds (in milliseconds)
THRESHOLDS = {
    "init_small": 30_000,  # 30s for small config init
    "init_medium": 60_000,  # 60s for medium config init
    "init_large": 120_000,  # 120s for large config init
    "plan_small": 15_000,  # 15s for small config plan
    "plan_medium": 45_000,  # 45s for medium config plan
    "plan_large": 120_000,  # 120s for large config plan
    "validate_small": 5_000,  # 5s for small config validate
    "validate_medium": 15_000,  # 15s for medium config validate
    "validate_large": 30_000,  # 30s for large config validate
}


@pytest.mark.terraform
class TestTerraformPlanPerformance:
    """Test terraform plan performance across different config sizes."""

    def test_init_small_config(self, terraform_runner, small_terraform_config, temp_workspace):
        """Test terraform init performance with a small configuration."""
        workspace = create_terraform_workspace(small_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            result = runner.init(backend=False)
            assert result.success, f"terraform init failed: {result.stderr}"
            assert result.elapsed_ms < THRESHOLDS["init_small"], (
                f"init took {result.elapsed_ms:.1f}ms, threshold: {THRESHOLDS['init_small']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_init_medium_config(self, terraform_runner, medium_terraform_config, temp_workspace):
        """Test terraform init performance with a medium configuration."""
        workspace = create_terraform_workspace(medium_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            result = runner.init(backend=False)
            assert result.success, f"terraform init failed: {result.stderr}"
            assert result.elapsed_ms < THRESHOLDS["init_medium"], (
                f"init took {result.elapsed_ms:.1f}ms, threshold: {THRESHOLDS['init_medium']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_init_large_config(self, terraform_runner, large_terraform_config, temp_workspace):
        """Test terraform init performance with a large configuration."""
        workspace = create_terraform_workspace(large_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            result = runner.init(backend=False)
            assert result.success, f"terraform init failed: {result.stderr}"
            assert result.elapsed_ms < THRESHOLDS["init_large"], (
                f"init took {result.elapsed_ms:.1f}ms, threshold: {THRESHOLDS['init_large']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_plan_small_config(self, terraform_runner, small_terraform_config, temp_workspace):
        """Test terraform plan performance with a small configuration."""
        workspace = create_terraform_workspace(small_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success, f"terraform init failed: {init_result.stderr}"

            result = runner.plan()
            assert result.success, f"terraform plan failed: {result.stderr}"
            assert result.elapsed_ms < THRESHOLDS["plan_small"], (
                f"plan took {result.elapsed_ms:.1f}ms, threshold: {THRESHOLDS['plan_small']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_plan_medium_config(self, terraform_runner, medium_terraform_config, temp_workspace):
        """Test terraform plan performance with a medium configuration."""
        workspace = create_terraform_workspace(medium_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success, f"terraform init failed: {init_result.stderr}"

            result = runner.plan()
            assert result.success, f"terraform plan failed: {result.stderr}"
            assert result.elapsed_ms < THRESHOLDS["plan_medium"], (
                f"plan took {result.elapsed_ms:.1f}ms, threshold: {THRESHOLDS['plan_medium']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_plan_large_config(self, terraform_runner, large_terraform_config, temp_workspace):
        """Test terraform plan performance with a large configuration."""
        workspace = create_terraform_workspace(large_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success, f"terraform init failed: {init_result.stderr}"

            result = runner.plan()
            assert result.success, f"terraform plan failed: {result.stderr}"
            assert result.elapsed_ms < THRESHOLDS["plan_large"], (
                f"plan took {result.elapsed_ms:.1f}ms, threshold: {THRESHOLDS['plan_large']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_plan_with_modules(self, terraform_runner, temp_workspace):
        """Test terraform plan performance with module usage."""
        config = generate_terraform_config(
            resource_count=10,
            include_modules=True,
        )
        workspace = create_terraform_workspace(config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success, f"terraform init failed: {init_result.stderr}"

            result = runner.plan()
            assert result.success, f"terraform plan failed: {result.stderr}"
            # Modules add overhead, so threshold is higher
            assert result.elapsed_ms < 60_000, (
                f"plan with modules took {result.elapsed_ms:.1f}ms, threshold: 60000ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_plan_idempotent(self, terraform_runner, small_terraform_config, temp_workspace):
        """Test that repeated plans are idempotent and perform consistently."""
        workspace = create_terraform_workspace(small_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            # Run plan multiple times
            timings = []
            for i in range(3):
                result = runner.plan()
                assert result.success, f"plan {i} failed: {result.stderr}"
                timings.append(result.elapsed_ms)

            # Check that timings are reasonably consistent (within 50% of median)
            import statistics

            median = statistics.median(timings)
            for i, t in enumerate(timings):
                assert t < median * 1.5, (
                    f"plan {i} took {t:.1f}ms, median was {median:.1f}ms "
                    f"(>{median * 1.5:.1f}ms threshold)"
                )
        finally:
            cleanup_workspace(workspace)


@pytest.mark.terraform
class TestTerraformValidatePerformance:
    """Test terraform validate performance."""

    def test_validate_small_config(self, terraform_runner, small_terraform_config, temp_workspace):
        """Test terraform validate with a small configuration."""
        workspace = create_terraform_workspace(small_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            result = runner.validate()
            assert result.success, f"terraform validate failed: {result.stderr}"
            assert result.elapsed_ms < THRESHOLDS["validate_small"], (
                f"validate took {result.elapsed_ms:.1f}ms, "
                f"threshold: {THRESHOLDS['validate_small']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_validate_medium_config(
        self, terraform_runner, medium_terraform_config, temp_workspace
    ):
        """Test terraform validate with a medium configuration."""
        workspace = create_terraform_workspace(medium_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            result = runner.validate()
            assert result.success, f"terraform validate failed: {result.stderr}"
            assert result.elapsed_ms < THRESHOLDS["validate_medium"], (
                f"validate took {result.elapsed_ms:.1f}ms, "
                f"threshold: {THRESHOLDS['validate_medium']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_validate_large_config(self, terraform_runner, large_terraform_config, temp_workspace):
        """Test terraform validate with a large configuration."""
        workspace = create_terraform_workspace(large_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            result = runner.validate()
            assert result.success, f"terraform validate failed: {result.stderr}"
            assert result.elapsed_ms < THRESHOLDS["validate_large"], (
                f"validate took {result.elapsed_ms:.1f}ms, "
                f"threshold: {THRESHOLDS['validate_large']}ms"
            )
        finally:
            cleanup_workspace(workspace)


@pytest.mark.terraform
class TestTerraformApplyPerformance:
    """Test terraform apply performance (requires cloud credentials)."""

    @pytest.mark.slow
    def test_apply_small_config(self, terraform_runner, small_terraform_config, temp_workspace):
        """Test terraform apply with a small configuration.
        NOTE: This test requires valid cloud credentials and will create real resources.
        Skip in CI without credentials.
        """
        if not os.environ.get("TF_PERF_TEST_APPLY"):
            pytest.skip("Set TF_PERF_TEST_APPLY=1 to run apply tests")

        workspace = create_terraform_workspace(small_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            plan_result = runner.plan()
            assert plan_result.success

            result = runner.apply()
            assert result.success, f"terraform apply failed: {result.stderr}"
            # Apply threshold: 5 minutes for small config
            assert result.elapsed_ms < 300_000, (
                f"apply took {result.elapsed_ms:.1f}ms, threshold: 300000ms"
            )
        finally:
            # Always cleanup
            with suppress(Exception):
                runner.destroy()
            cleanup_workspace(workspace)


@pytest.mark.terraform
class TestTerraformPlanScaling:
    """Test how terraform plan scales with resource count."""

    @pytest.mark.parametrize("resource_count", [1, 5, 10, 25, 50, 100])
    def test_plan_scaling(self, terraform_runner, temp_workspace, resource_count):
        """Test that plan time scales reasonably with resource count."""
        config = generate_terraform_config(resource_count=resource_count)
        workspace = create_terraform_workspace(config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            result = runner.plan()
            assert result.success

            # Rough linear scaling expectation: ~1s per resource + 5s base
            expected_max = 5000 + (resource_count * 1000)
            assert result.elapsed_ms < expected_max, (
                f"plan with {resource_count} resources took {result.elapsed_ms:.1f}ms, "
                f"expected < {expected_max}ms"
            )
        finally:
            cleanup_workspace(workspace)
