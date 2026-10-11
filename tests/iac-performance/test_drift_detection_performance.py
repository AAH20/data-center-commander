"""
Terraform Drift Detection Performance Tests.

Tests the performance of detecting configuration drift between
the desired state (terraform config) and actual state (cloud resources).
"""

import pytest
from utils.terraform_utils import (
    TerraformRunner,
    cleanup_workspace,
    create_terraform_workspace,
    generate_terraform_config,
)

# Performance thresholds for drift detection (in milliseconds)
DRIFT_THRESHOLDS = {
    "refresh_small": 30_000,  # 30s for small config refresh
    "refresh_medium": 60_000,  # 60s for medium config refresh
    "refresh_large": 120_000,  # 120s for large config refresh
    "plan_drift_small": 15_000,  # 15s for small config drift plan
    "plan_drift_medium": 45_000,  # 45s for medium config drift plan
    "plan_drift_large": 120_000,  # 120s for large config drift plan
    "state_list_small": 5_000,  # 5s for small config state list
    "state_list_medium": 15_000,  # 15s for medium config state list
    "state_list_large": 30_000,  # 30s for large config state list
}


@pytest.mark.terraform
class TestDriftDetectionPerformance:
    """Test drift detection performance across different config sizes."""

    def test_refresh_small_config(self, terraform_runner, small_terraform_config, temp_workspace):
        """Test terraform refresh (drift detection) with a small configuration."""
        workspace = create_terraform_workspace(small_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            result = runner.refresh()
            assert result.success, f"terraform refresh failed: {result.stderr}"
            assert result.elapsed_ms < DRIFT_THRESHOLDS["refresh_small"], (
                f"refresh took {result.elapsed_ms:.1f}ms, "
                f"threshold: {DRIFT_THRESHOLDS['refresh_small']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_refresh_medium_config(self, terraform_runner, medium_terraform_config, temp_workspace):
        """Test terraform refresh with a medium configuration."""
        workspace = create_terraform_workspace(medium_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            result = runner.refresh()
            assert result.success, f"terraform refresh failed: {result.stderr}"
            assert result.elapsed_ms < DRIFT_THRESHOLDS["refresh_medium"], (
                f"refresh took {result.elapsed_ms:.1f}ms, "
                f"threshold: {DRIFT_THRESHOLDS['refresh_medium']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_refresh_large_config(self, terraform_runner, large_terraform_config, temp_workspace):
        """Test terraform refresh with a large configuration."""
        workspace = create_terraform_workspace(large_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            result = runner.refresh()
            assert result.success, f"terraform refresh failed: {result.stderr}"
            assert result.elapsed_ms < DRIFT_THRESHOLDS["refresh_large"], (
                f"refresh took {result.elapsed_ms:.1f}ms, "
                f"threshold: {DRIFT_THRESHOLDS['refresh_large']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_drift_plan_small(self, terraform_runner, small_terraform_config, temp_workspace):
        """Test drift detection via plan with detailed exit code (small config)."""
        workspace = create_terraform_workspace(small_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            # Plan with detailed exit code: 0 = no changes, 1 = error, 2 = changes present
            result = runner.plan(detailed_exitcode=True)
            assert result.success, f"terraform plan failed: {result.stderr}"
            assert result.elapsed_ms < DRIFT_THRESHOLDS["plan_drift_small"], (
                f"drift plan took {result.elapsed_ms:.1f}ms, "
                f"threshold: {DRIFT_THRESHOLDS['plan_drift_small']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_drift_plan_medium(self, terraform_runner, medium_terraform_config, temp_workspace):
        """Test drift detection via plan with detailed exit code (medium config)."""
        workspace = create_terraform_workspace(medium_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            result = runner.plan(detailed_exitcode=True)
            assert result.success, f"terraform plan failed: {result.stderr}"
            assert result.elapsed_ms < DRIFT_THRESHOLDS["plan_drift_medium"], (
                f"drift plan took {result.elapsed_ms:.1f}ms, "
                f"threshold: {DRIFT_THRESHOLDS['plan_drift_medium']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_drift_plan_large(self, terraform_runner, large_terraform_config, temp_workspace):
        """Test drift detection via plan with detailed exit code (large config)."""
        workspace = create_terraform_workspace(large_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            result = runner.plan(detailed_exitcode=True)
            assert result.success, f"terraform plan failed: {result.stderr}"
            assert result.elapsed_ms < DRIFT_THRESHOLDS["plan_drift_large"], (
                f"drift plan took {result.elapsed_ms:.1f}ms, "
                f"threshold: {DRIFT_THRESHOLDS['plan_drift_large']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_state_list_small(self, terraform_runner, small_terraform_config, temp_workspace):
        """Test terraform state list performance (small config)."""
        workspace = create_terraform_workspace(small_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            result = runner.state_list()
            assert result.success, f"terraform state list failed: {result.stderr}"
            assert result.elapsed_ms < DRIFT_THRESHOLDS["state_list_small"], (
                f"state list took {result.elapsed_ms:.1f}ms, "
                f"threshold: {DRIFT_THRESHOLDS['state_list_small']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_state_list_medium(self, terraform_runner, medium_terraform_config, temp_workspace):
        """Test terraform state list performance (medium config)."""
        workspace = create_terraform_workspace(medium_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            result = runner.state_list()
            assert result.success, f"terraform state list failed: {result.stderr}"
            assert result.elapsed_ms < DRIFT_THRESHOLDS["state_list_medium"], (
                f"state list took {result.elapsed_ms:.1f}ms, "
                f"threshold: {DRIFT_THRESHOLDS['state_list_medium']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_state_list_large(self, terraform_runner, large_terraform_config, temp_workspace):
        """Test terraform state list performance (large config)."""
        workspace = create_terraform_workspace(large_terraform_config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            result = runner.state_list()
            assert result.success, f"terraform state list failed: {result.stderr}"
            assert result.elapsed_ms < DRIFT_THRESHOLDS["state_list_large"], (
                f"state list took {result.elapsed_ms:.1f}ms, "
                f"threshold: {DRIFT_THRESHOLDS['state_list_large']}ms"
            )
        finally:
            cleanup_workspace(workspace)


@pytest.mark.terraform
class TestDriftDetectionScaling:
    """Test how drift detection scales with resource count."""

    @pytest.mark.parametrize("resource_count", [1, 5, 10, 25, 50, 100])
    def test_refresh_scaling(self, terraform_runner, temp_workspace, resource_count):
        """Test that refresh time scales reasonably with resource count."""
        config = generate_terraform_config(resource_count=resource_count)
        workspace = create_terraform_workspace(config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            result = runner.refresh()
            assert result.success

            # Rough linear scaling: ~1s per resource + 5s base
            expected_max = 5000 + (resource_count * 1000)
            assert result.elapsed_ms < expected_max, (
                f"refresh with {resource_count} resources took {result.elapsed_ms:.1f}ms, "
                f"expected < {expected_max}ms"
            )
        finally:
            cleanup_workspace(workspace)

    @pytest.mark.parametrize("resource_count", [1, 5, 10, 25, 50, 100])
    def test_drift_plan_scaling(self, terraform_runner, temp_workspace, resource_count):
        """Test that drift plan time scales reasonably with resource count."""
        config = generate_terraform_config(resource_count=resource_count)
        workspace = create_terraform_workspace(config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            result = runner.plan(detailed_exitcode=True)
            assert result.success

            # Rough linear scaling: ~1s per resource + 5s base
            expected_max = 5000 + (resource_count * 1000)
            assert result.elapsed_ms < expected_max, (
                f"drift plan with {resource_count} resources took {result.elapsed_ms:.1f}ms, "
                f"expected < {expected_max}ms"
            )
        finally:
            cleanup_workspace(workspace)


@pytest.mark.terraform
class TestDriftDetectionWithModules:
    """Test drift detection performance with terraform modules."""

    def test_refresh_with_modules(self, terraform_runner, temp_workspace):
        """Test refresh performance when using modules."""
        config = generate_terraform_config(
            resource_count=10,
            include_modules=True,
        )
        workspace = create_terraform_workspace(config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            result = runner.refresh()
            assert result.success
            # Modules add overhead
            assert result.elapsed_ms < 60_000, (
                f"refresh with modules took {result.elapsed_ms:.1f}ms, threshold: 60000ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_drift_plan_with_modules(self, terraform_runner, temp_workspace):
        """Test drift plan performance when using modules."""
        config = generate_terraform_config(
            resource_count=10,
            include_modules=True,
        )
        workspace = create_terraform_workspace(config, temp_workspace)
        try:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            result = runner.plan(detailed_exitcode=True)
            assert result.success
            assert result.elapsed_ms < 60_000, (
                f"drift plan with modules took {result.elapsed_ms:.1f}ms, threshold: 60000ms"
            )
        finally:
            cleanup_workspace(workspace)
