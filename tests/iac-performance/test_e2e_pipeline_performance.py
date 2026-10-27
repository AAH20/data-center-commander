"""
End-to-End IaC Performance Tests.

Tests the complete IaC pipeline performance: validate -> init -> plan -> scan ->
policy eval. These tests measure the total time for a full infrastructure
deployment cycle, minus the apply step that needs a cloud account.

Each stage is asserted to have done its job, because an end-to-end wall clock
over stages that silently did nothing is the easiest green test to write and the
least informative:

    init      -> succeeded
    validate  -> "valid": true in the -json document
    plan      -> "Plan: N to add" matching the configuration
    checkov   -> parsed N resources and evaluated at least one check
    opa       -> a deny set (empty for the compliant input)

The terraform stages run against the built-in provider (offline, no
credentials). The compliance stage runs checkov over a real AWS-resource
configuration in a sibling directory, because checkov is a static analyser: it
needs the resource shapes its checks target, but no credentials. See
docs/iac-performance.md for why the two stages do not share one .tf directory.
"""

from __future__ import annotations

import os
import time

import pytest
from utils.checkov_utils import generate_terraform_file
from utils.rego_utils import create_opa_input
from utils.terraform_utils import (
    TerraformRunner,
    generate_terraform_config,
    plan_add_count,
    terraform_workspace,
)

# Measured end to end on this machine after the checkov Prisma Cloud call was
# disabled: 1.9 s for a 5-resource pipeline and 1.6 s for 100 resources -- the
# checkov scan is the only stage above 300 ms. Budgets are ~8-10x that, so a
# much slower runner passes; the structural assertions are what make the tests
# able to fail.
E2E_BUDGET_MS = {
    "small": 15_000,
    "medium": 18_000,
    "large": 20_000,
}


def write_compliance_config(directory: str, resource_count: int) -> str:
    """Write an AWS-resource config for checkov to scan; return the directory."""
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "main.tf"), "w") as f:
        f.write(generate_terraform_file(resource_count=resource_count, compliant=True))
    return directory


def run_pipeline(
    temp_workspace: str,
    resource_count: int,
    checkov_runner,
    opa_runner,
    rego_policy_dir: str,
    include_scan: bool = True,
    include_policy: bool = True,
) -> dict:
    """Run the pipeline and return the per-stage timings plus results."""
    config = generate_terraform_config(resource_count=resource_count)
    timings: dict[str, float] = {}
    results: dict[str, object] = {}

    start = time.perf_counter()
    with terraform_workspace(config, temp_workspace) as workspace:
        runner = TerraformRunner(workspace)

        stage = time.perf_counter()
        init_result = runner.init(backend=False)
        timings["init_ms"] = (time.perf_counter() - stage) * 1000
        assert init_result.success, f"terraform init failed: {init_result.stderr}"
        results["init"] = init_result

        stage = time.perf_counter()
        validate_result = runner.validate()
        timings["validate_ms"] = (time.perf_counter() - stage) * 1000
        assert validate_result.success, f"terraform validate failed: {validate_result.stderr}"
        assert (validate_result.parsed_output or {}).get("valid") is True, (
            f"validate did not report a valid configuration: {validate_result.stdout[:500]}"
        )
        results["validate"] = validate_result

        stage = time.perf_counter()
        plan_result = runner.plan()
        timings["plan_ms"] = (time.perf_counter() - stage) * 1000
        assert plan_result.success, f"terraform plan failed: {plan_result.stderr}"
        assert plan_add_count(plan_result) == resource_count, (
            f"plan covered {plan_add_count(plan_result)} resources, "
            f"expected {resource_count}"
        )
        results["plan"] = plan_result

        if include_scan:
            scan_dir = write_compliance_config(
                os.path.join(temp_workspace, "compliance"), resource_count
            )
            stage = time.perf_counter()
            scan_result = checkov_runner.scan_directory(scan_dir)
            timings["scan_ms"] = (time.perf_counter() - stage) * 1000
            assert scan_result.parsed_output is not None, (
                f"checkov produced no parsable output: {scan_result.stderr[-600:]}"
            )
            assert scan_result.resource_count == resource_count, (
                f"checkov parsed {scan_result.resource_count} resources, "
                f"expected {resource_count}"
            )
            assert scan_result.checks_evaluated > 0, "checkov evaluated no checks"
            results["scan"] = scan_result

        if include_policy:
            policy = os.path.join(rego_policy_dir, "compliance.rego")
            if os.path.exists(policy):
                stage = time.perf_counter()
                policy_result = opa_runner.eval(
                    policy, input_data=create_opa_input(resource_id="test-pipeline")
                )
                timings["policy_ms"] = (time.perf_counter() - stage) * 1000
                assert policy_result.success, (
                    f"policy eval failed: {policy_result.errors} {policy_result.stderr}"
                )
                assert policy_result.violations == [], (
                    "the compliant pipeline input was rejected: "
                    f"{policy_result.violations[:3]}"
                )
                results["policy"] = policy_result

    timings["total_ms"] = (time.perf_counter() - start) * 1000
    return {"timings": timings, "results": results}


@pytest.mark.terraform
@pytest.mark.checkov
@pytest.mark.opa
class TestEndToEndPipeline:
    """Test the complete IaC pipeline performance."""

    @pytest.mark.parametrize("size,resource_count", [("small", 5), ("medium", 25), ("large", 100)])
    def test_full_pipeline(
        self,
        terraform_runner,
        checkov_runner,
        opa_runner,
        rego_policy_dir,
        temp_workspace,
        size,
        resource_count,
    ):
        """init -> validate -> plan -> scan -> policy eval, end to end."""
        outcome = run_pipeline(
            temp_workspace, resource_count, checkov_runner, opa_runner, rego_policy_dir
        )
        total_ms = outcome["timings"]["total_ms"]
        assert total_ms < E2E_BUDGET_MS[size], (
            f"full pipeline ({size}) took {total_ms:.1f}ms, "
            f"budget: {E2E_BUDGET_MS[size]}ms. Stage timings: {outcome['timings']}"
        )


@pytest.mark.terraform
@pytest.mark.checkov
class TestValidatePlanScanPipeline:
    """Test the validate -> plan -> scan pipeline (without policy eval)."""

    @pytest.mark.parametrize("size,resource_count", [("small", 5), ("medium", 25), ("large", 100)])
    def test_validate_plan_scan(
        self, terraform_runner, checkov_runner, temp_workspace, size, resource_count
    ):
        """validate + plan + scan, with each stage's output checked."""
        outcome = run_pipeline(
            temp_workspace,
            resource_count,
            checkov_runner,
            opa_runner=None,
            rego_policy_dir="",
            include_policy=False,
        )
        total_ms = outcome["timings"]["total_ms"]
        assert total_ms < E2E_BUDGET_MS[size], (
            f"validate+plan+scan ({size}) took {total_ms:.1f}ms, "
            f"budget: {E2E_BUDGET_MS[size]}ms. Stage timings: {outcome['timings']}"
        )


@pytest.mark.terraform
class TestPipelineScaling:
    """Test how the full pipeline scales with resource count."""

    @pytest.mark.parametrize("resource_count", [1, 5, 10, 25, 50, 100])
    def test_pipeline_scaling(self, terraform_runner, temp_workspace, resource_count):
        """validate + init + plan must scale, and must cover the configuration."""
        outcome = run_pipeline(
            temp_workspace,
            resource_count,
            checkov_runner=None,
            opa_runner=None,
            rego_policy_dir="",
            include_scan=False,
            include_policy=False,
        )
        total_ms = outcome["timings"]["total_ms"]
        # Measured 0.10-0.13 s for 1-100 resources: three terraform process
        # starts dominate, so the per-resource term is deliberately small.
        expected_max = 500 + resource_count * 10
        assert total_ms < expected_max, (
            f"pipeline with {resource_count} resources took {total_ms:.1f}ms, "
            f"expected < {expected_max}ms. Stage timings: {outcome['timings']}"
        )
