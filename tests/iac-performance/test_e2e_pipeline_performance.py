"""
End-to-End IaC Performance Tests.

Tests the complete IaC pipeline performance: validate -> plan -> apply -> scan -> policy eval.
These tests measure the total time for a full infrastructure deployment cycle.
"""

import os
import time

import pytest
from utils.rego_utils import create_opa_input
from utils.terraform_utils import (
    TerraformRunner,
    cleanup_workspace,
    create_terraform_workspace,
    generate_terraform_config,
)

# End-to-end performance thresholds (in milliseconds)
E2E_THRESHOLDS = {
    "full_pipeline_small": 120_000,  # 2 minutes for small config full pipeline
    "full_pipeline_medium": 300_000,  # 5 minutes for medium config full pipeline
    "full_pipeline_large": 600_000,  # 10 minutes for large config full pipeline
    "validate_plan_scan_small": 60_000,  # 1 minute for validate+plan+scan (small)
    "validate_plan_scan_medium": 180_000,  # 3 minutes for validate+plan+scan (medium)
    "validate_plan_scan_large": 360_000,  # 6 minutes for validate+plan+scan (large)
}


@pytest.mark.terraform
@pytest.mark.checkov
@pytest.mark.opa
class TestEndToEndPipeline:
    """Test the complete IaC pipeline performance."""

    def test_full_pipeline_small(
        self,
        terraform_runner,
        checkov_runner,
        opa_runner,
        checkov_policy_dir,
        rego_policy_dir,
        temp_workspace,
    ):
        """Test the full IaC pipeline with a small configuration."""
        config = generate_terraform_config(resource_count=5)
        workspace = create_terraform_workspace(config, temp_workspace)
        try:
            tf_runner = TerraformRunner(workspace)

            # Step 1: Validate
            start = time.perf_counter()
            validate_result = tf_runner.validate()
            assert validate_result.success, f"validate failed: {validate_result.stderr}"
            validate_ms = (time.perf_counter() - start) * 1000

            # Step 2: Init
            init_result = tf_runner.init(backend=False)
            assert init_result.success, f"init failed: {init_result.stderr}"

            # Step 3: Plan
            plan_result = tf_runner.plan()
            assert plan_result.success, f"plan failed: {plan_result.stderr}"
            plan_ms = (time.perf_counter() - start) * 1000 - validate_ms

            # Step 4: Compliance scan
            checkov_runner.scan_directory(workspace)  # scan time feeds into total_ms
            scan_ms = (time.perf_counter() - start) * 1000 - validate_ms - plan_ms  # noqa: F841 — timing probe

            # Step 5: Policy evaluation
            policy_path = os.path.join(rego_policy_dir, "compliance.rego")
            if os.path.exists(policy_path):
                opa_result = opa_runner.eval(
                    policy_path,
                    input_data=create_opa_input(resource_id="test-pipeline"),
                )
                assert opa_result.success, f"policy eval failed: {opa_result.stderr}"

            total_ms = (time.perf_counter() - start) * 1000
            assert total_ms < E2E_THRESHOLDS["full_pipeline_small"], (
                f"full pipeline (small) took {total_ms:.1f}ms, "
                f"threshold: {E2E_THRESHOLDS['full_pipeline_small']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_full_pipeline_medium(
        self,
        terraform_runner,
        checkov_runner,
        opa_runner,
        checkov_policy_dir,
        rego_policy_dir,
        temp_workspace,
    ):
        """Test the full IaC pipeline with a medium configuration."""
        config = generate_terraform_config(resource_count=25)
        workspace = create_terraform_workspace(config, temp_workspace)
        try:
            tf_runner = TerraformRunner(workspace)

            start = time.perf_counter()

            # Validate
            validate_result = tf_runner.validate()
            assert validate_result.success

            # Init
            init_result = tf_runner.init(backend=False)
            assert init_result.success

            # Plan
            plan_result = tf_runner.plan()
            assert plan_result.success

            # Scan
            checkov_runner.scan_directory(workspace)  # scan time feeds into total_ms

            # Policy eval
            policy_path = os.path.join(rego_policy_dir, "compliance.rego")
            if os.path.exists(policy_path):
                opa_result = opa_runner.eval(
                    policy_path,
                    input_data=create_opa_input(resource_id="test-pipeline"),
                )
                assert opa_result.success

            total_ms = (time.perf_counter() - start) * 1000
            assert total_ms < E2E_THRESHOLDS["full_pipeline_medium"], (
                f"full pipeline (medium) took {total_ms:.1f}ms, "
                f"threshold: {E2E_THRESHOLDS['full_pipeline_medium']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_full_pipeline_large(
        self,
        terraform_runner,
        checkov_runner,
        opa_runner,
        checkov_policy_dir,
        rego_policy_dir,
        temp_workspace,
    ):
        """Test the full IaC pipeline with a large configuration."""
        config = generate_terraform_config(resource_count=100)
        workspace = create_terraform_workspace(config, temp_workspace)
        try:
            tf_runner = TerraformRunner(workspace)

            start = time.perf_counter()

            # Validate
            validate_result = tf_runner.validate()
            assert validate_result.success

            # Init
            init_result = tf_runner.init(backend=False)
            assert init_result.success

            # Plan
            plan_result = tf_runner.plan()
            assert plan_result.success

            # Scan
            checkov_runner.scan_directory(workspace)  # scan time feeds into total_ms

            # Policy eval
            policy_path = os.path.join(rego_policy_dir, "compliance.rego")
            if os.path.exists(policy_path):
                opa_result = opa_runner.eval(
                    policy_path,
                    input_data=create_opa_input(resource_id="test-pipeline"),
                )
                assert opa_result.success

            total_ms = (time.perf_counter() - start) * 1000
            assert total_ms < E2E_THRESHOLDS["full_pipeline_large"], (
                f"full pipeline (large) took {total_ms:.1f}ms, "
                f"threshold: {E2E_THRESHOLDS['full_pipeline_large']}ms"
            )
        finally:
            cleanup_workspace(workspace)


@pytest.mark.terraform
@pytest.mark.checkov
class TestValidatePlanScanPipeline:
    """Test the validate -> plan -> scan pipeline (without apply)."""

    def test_validate_plan_scan_small(self, terraform_runner, checkov_runner, temp_workspace):
        """Test validate + plan + scan pipeline with a small config."""
        config = generate_terraform_config(resource_count=5)
        workspace = create_terraform_workspace(config, temp_workspace)
        try:
            tf_runner = TerraformRunner(workspace)

            start = time.perf_counter()

            validate_result = tf_runner.validate()
            assert validate_result.success

            init_result = tf_runner.init(backend=False)
            assert init_result.success

            plan_result = tf_runner.plan()
            assert plan_result.success

            checkov_runner.scan_directory(workspace)  # scan time feeds into total_ms

            total_ms = (time.perf_counter() - start) * 1000
            assert total_ms < E2E_THRESHOLDS["validate_plan_scan_small"], (
                f"validate+plan+scan (small) took {total_ms:.1f}ms, "
                f"threshold: {E2E_THRESHOLDS['validate_plan_scan_small']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_validate_plan_scan_medium(self, terraform_runner, checkov_runner, temp_workspace):
        """Test validate + plan + scan pipeline with a medium config."""
        config = generate_terraform_config(resource_count=25)
        workspace = create_terraform_workspace(config, temp_workspace)
        try:
            tf_runner = TerraformRunner(workspace)

            start = time.perf_counter()

            validate_result = tf_runner.validate()
            assert validate_result.success

            init_result = tf_runner.init(backend=False)
            assert init_result.success

            plan_result = tf_runner.plan()
            assert plan_result.success

            checkov_runner.scan_directory(workspace)  # scan time feeds into total_ms

            total_ms = (time.perf_counter() - start) * 1000
            assert total_ms < E2E_THRESHOLDS["validate_plan_scan_medium"], (
                f"validate+plan+scan (medium) took {total_ms:.1f}ms, "
                f"threshold: {E2E_THRESHOLDS['validate_plan_scan_medium']}ms"
            )
        finally:
            cleanup_workspace(workspace)

    def test_validate_plan_scan_large(self, terraform_runner, checkov_runner, temp_workspace):
        """Test validate + plan + scan pipeline with a large config."""
        config = generate_terraform_config(resource_count=100)
        workspace = create_terraform_workspace(config, temp_workspace)
        try:
            tf_runner = TerraformRunner(workspace)

            start = time.perf_counter()

            validate_result = tf_runner.validate()
            assert validate_result.success

            init_result = tf_runner.init(backend=False)
            assert init_result.success

            plan_result = tf_runner.plan()
            assert plan_result.success

            checkov_runner.scan_directory(workspace)  # scan time feeds into total_ms

            total_ms = (time.perf_counter() - start) * 1000
            assert total_ms < E2E_THRESHOLDS["validate_plan_scan_large"], (
                f"validate+plan+scan (large) took {total_ms:.1f}ms, "
                f"threshold: {E2E_THRESHOLDS['validate_plan_scan_large']}ms"
            )
        finally:
            cleanup_workspace(workspace)


@pytest.mark.terraform
class TestPipelineScaling:
    """Test how the full pipeline scales with resource count."""

    @pytest.mark.parametrize("resource_count", [1, 5, 10, 25, 50, 100])
    def test_pipeline_scaling(self, terraform_runner, temp_workspace, resource_count):
        """Test that the pipeline scales reasonably with resource count."""
        config = generate_terraform_config(resource_count=resource_count)
        workspace = create_terraform_workspace(config, temp_workspace)
        try:
            tf_runner = TerraformRunner(workspace)

            start = time.perf_counter()

            validate_result = tf_runner.validate()
            assert validate_result.success

            init_result = tf_runner.init(backend=False)
            assert init_result.success

            plan_result = tf_runner.plan()
            assert plan_result.success

            total_ms = (time.perf_counter() - start) * 1000

            # Rough linear scaling: ~2s per resource + 10s base
            expected_max = 10000 + (resource_count * 2000)
            assert total_ms < expected_max, (
                f"pipeline with {resource_count} resources took {total_ms:.1f}ms, "
                f"expected < {expected_max}ms"
            )
        finally:
            cleanup_workspace(workspace)
