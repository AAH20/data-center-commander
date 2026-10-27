"""
Terraform Plan Performance Tests.

Tests the performance of terraform plan operations with varying
configuration sizes and complexity levels.

WHAT THESE TESTS MEASURE
------------------------
They drive the real `terraform` binary (plan/validate/init/apply engine) over
configurations generated in a temp directory, using the *built-in* provider
(`terraform_data`). That choice is what makes the numbers real in CI: a
configuration of `aws_instance` resources needs a 200-600 MB provider download
on every fresh `init` and then cloud credentials before `plan` will run at all.
Measured here: aws `init` 277 s per workspace, and `plan` failed after a 15 s
IMDS timeout with "no EC2 IMDS role found". Neither is available on a CI runner,
so a suite written that way cannot pass there and was excluded from the gate.

WHY THE ASSERTIONS LOOK THE WAY THEY DO
---------------------------------------
A wall-clock threshold on a 30-60 ms operation is decided by the machine, not
by the code: set it at 15 s and nothing can fail; set it at the measured value
and it flakes on a loaded runner. So each test asserts two things:

  * a structural property read out of terraform's own output -- "Plan: N to
    add", the exact set of addresses in `state list`, `"valid": true` from
    `validate -json`, exit code 2 from `plan -detailed-exitcode` when the
    configuration has drifted. These fail the moment terraform stops doing the
    work, regardless of machine speed;
  * a budget with enough headroom for a slow runner but far below the failure
    mode this suite exists to catch (a provider download reappearing inside
    `init` costs ~280 s, which any budget here rejects).

The budgets are derived from measurement on this machine, recorded in
docs/iac-performance.md, and each one is demonstrably able to fail -- see the
"Proving the assertions can fail" section there.
"""

from __future__ import annotations

import statistics

import pytest
from utils.terraform_utils import (
    TerraformRunner,
    generate_terraform_config,
    plan_add_count,
    terraform_workspace,
)

# Operating budgets in milliseconds. Each is sized against the failure mode it
# exists to catch, not against the fastest measurement:
#
#   * a registry provider reappearing inside `init` costs 277,850 ms (measured,
#     hashicorp/aws over the network) -- any budget here rejects it;
#   * a plan that talks to a cloud API waits ~15 s for EC2 IMDS to fail;
#   * a plan/refresh over local state measures 29-58 ms for 5-100 resources
#     (medians, see docs/iac-performance.md), so 3000 ms leaves a shared CI
#     runner ~50x headroom and still fails on either failure mode above.
#
# Timers are the secondary assertion in every test below: the structural checks
# (plan resource count, `"valid": true`, exit code 2 on drift) are what fail when
# terraform stops doing the work.
BUDGET_MS = {
    "init": 3_000,
    "plan": 3_000,
    "validate": 2_000,
    "apply": 10_000,
}

# Per-resource allowance for the scaling tests, on top of a fixed floor that
# absorbs terraform's process start. Measured: a 100-resource plan takes 50 ms.
SCALING_FLOOR_MS = 1_000
SCALING_PER_RESOURCE_MS = 15


def budget_for(resource_count: int) -> float:
    """Time budget for an operation over resource_count resources."""
    return SCALING_FLOOR_MS + resource_count * SCALING_PER_RESOURCE_MS


@pytest.mark.terraform
class TestTerraformPlanPerformance:
    """Test terraform plan performance across different config sizes."""

    @pytest.mark.parametrize("size,resource_count", [("small", 5), ("medium", 25), ("large", 100)])
    def test_init_config(self, terraform_runner, temp_workspace, size, resource_count):
        """terraform init must initialise without downloading a provider."""
        config = generate_terraform_config(resource_count=resource_count)
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            result = runner.init(backend=False)
            assert result.success, f"terraform init failed: {result.stderr}"

            # Structural: the built-in provider is compiled into the binary.
            # A registry provider would print "Installing hashicorp/aws..." and
            # this is the assertion that catches the suite going back online.
            assert "Installing" not in result.combined_output, (
                f"{size} init downloaded a provider, which CI cannot rely on:\n"
                f"{result.combined_output[:800]}"
            )
            assert result.elapsed_ms < BUDGET_MS["init"], (
                f"{size} init took {result.elapsed_ms:.1f}ms, budget: {BUDGET_MS['init']}ms"
            )

    @pytest.mark.parametrize("size,resource_count", [("small", 5), ("medium", 25), ("large", 100)])
    def test_plan_config(self, terraform_runner, temp_workspace, size, resource_count):
        """A plan must cover every resource in the configuration, in budget."""
        config = generate_terraform_config(resource_count=resource_count)
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success, f"terraform init failed: {init_result.stderr}"

            result = runner.plan()
            assert result.success, f"terraform plan failed: {result.stderr}"

            # Structural: a plan that silently planned nothing is fast and would
            # satisfy any time budget, so the resource count is checked first.
            assert plan_add_count(result) == resource_count, (
                f"{size} plan did not cover the configuration; "
                f"expected {resource_count} to add, output:\n{result.stdout[-1500:]}"
            )
            assert result.elapsed_ms < BUDGET_MS["plan"], (
                f"{size} plan took {result.elapsed_ms:.1f}ms, budget: {BUDGET_MS['plan']}ms"
            )

    def test_plan_with_modules(self, terraform_runner, temp_workspace):
        """Test terraform plan performance with module usage."""
        config = generate_terraform_config(resource_count=10, include_modules=True)
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success, f"terraform init failed: {init_result.stderr}"

            result = runner.plan()
            assert result.success, f"terraform plan failed: {result.stderr}"
            # The root module's 10 resources plus the module's 5.
            assert plan_add_count(result) == 15, (
                f"plan with modules covered the wrong resource count:\n{result.stdout[-1500:]}"
            )
            assert result.elapsed_ms < BUDGET_MS["plan"], (
                f"plan with modules took {result.elapsed_ms:.1f}ms, budget: {BUDGET_MS['plan']}ms"
            )

    def test_plan_idempotent(self, terraform_runner, temp_workspace):
        """Repeated plans of an unchanged configuration must be identical."""
        config = generate_terraform_config(resource_count=5)
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success

            results = []
            for i in range(3):
                result = runner.plan()
                assert result.success, f"plan {i} failed: {result.stderr}"
                results.append(result)

            counts = [plan_add_count(r) for r in results]
            assert counts == [5, 5, 5], f"plan output changed between runs: {counts}"

            # Same decision every time: a plan that flips between "5 to add" and
            # "0 to add" on unchanged config is a correctness bug, and this is
            # what "idempotent" has to mean -- not merely "3 plans ran".
            summaries = {
                line
                for r in results
                for line in r.stdout.splitlines()
                if line.startswith("Plan:")
            }
            assert len(summaries) == 1, f"plan summary is not deterministic: {summaries}"

            timings = [r.elapsed_ms for r in results]
            median = statistics.median(timings)
            for i, t in enumerate(timings):
                assert t < median * 3, (
                    f"plan {i} took {t:.1f}ms, median was {median:.1f}ms "
                    f"(>{median * 3:.1f}ms threshold)"
                )


@pytest.mark.terraform
class TestTerraformValidatePerformance:
    """Test terraform validate performance."""

    @pytest.mark.parametrize("size,resource_count", [("small", 5), ("medium", 25), ("large", 100)])
    def test_validate_config(self, terraform_runner, temp_workspace, size, resource_count):
        """terraform validate must validate the real configuration, in budget.

        `validate` needs the provider schemas that `init` installs. The previous
        version ran `validate` first on a provider-backed config, which fails
        with "Missing required provider -- Please run terraform init"; the
        ordering here is init -> validate, and the result is asserted against
        the parsed document rather than only the exit code.
        """
        config = generate_terraform_config(resource_count=resource_count)
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success, f"terraform init failed: {init_result.stderr}"

            result = runner.validate()
            assert result.success, f"terraform validate failed: {result.stderr}"
            assert result.parsed_output is not None, (
                f"validate -json produced no parsable document: {result.stdout[:500]}"
            )
            assert result.parsed_output.get("valid") is True, (
                f"validate reported invalid: {result.stdout[:800]}"
            )
            assert result.elapsed_ms < BUDGET_MS["validate"], (
                f"{size} validate took {result.elapsed_ms:.1f}ms, "
                f"budget: {BUDGET_MS['validate']}ms"
            )

    def test_validate_rejects_broken_configuration(self, terraform_runner, temp_workspace):
        """Negative control: validate must report invalid for an invalid config.

        Without this, a `validate` that always answered valid=true would make
        the whole class pass while asserting nothing. This is the check that can
        fail if the validate plumbing silently stops reporting.
        """
        broken = generate_terraform_config(resource_count=2)
        broken.main_tf += '\nresource "terraform_data" "broken" {\n  input = \n}\n'
        with terraform_workspace(broken, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            runner.init(backend=False)
            result = runner.validate()
            assert not result.success, (
                "validate accepted a syntactically invalid configuration: "
                f"{result.stdout[:800]}"
            )
            assert result.parsed_output is not None
            assert result.parsed_output.get("valid") is False
            assert result.parsed_output.get("diagnostics"), (
                "validate reported invalid without any diagnostic detail"
            )


@pytest.mark.terraform
class TestTerraformApplyPerformance:
    """Test terraform apply performance.

    Apply runs against the built-in provider, so it writes local state and
    creates nothing in any cloud. The cloud variant below it is the only test
    here that still needs credentials, and it skips without them.
    """

    def test_apply_small_config(self, terraform_runner, temp_workspace):
        """Test terraform apply with a small configuration."""
        config = generate_terraform_config(resource_count=5)
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success, f"terraform init failed: {init_result.stderr}"

            result = runner.apply()
            assert result.success, f"terraform apply failed: {result.stderr}"
            assert "Apply complete! Resources: 5 added" in result.stdout, (
                f"apply did not report creating 5 resources:\n{result.stdout[-1000:]}"
            )
            assert result.elapsed_ms < BUDGET_MS["apply"], (
                f"apply took {result.elapsed_ms:.1f}ms, budget: {BUDGET_MS['apply']}ms"
            )

            listed = runner.state_list()
            assert listed.success, f"state list failed: {listed.stderr}"
            assert len(listed.stdout.split()) == 5, (
                f"expected 5 addresses in state, got: {listed.stdout!r}"
            )

    @pytest.mark.slow
    def test_apply_aws_config_requires_credentials(self, terraform_runner, temp_workspace):
        """Plan against the real AWS provider -- NOT measured without credentials.

        This is the one capability this file cannot exercise in CI: a plan of
        `aws_instance` resources makes the provider call STS/EC2 IMDS, and there
        are no AWS credentials on the runner. Opt in with TF_PERF_TEST_CLOUD=1
        on a machine that has them (and a warm plugin cache; the first init
        downloads the provider).
        """
        import os

        if not os.environ.get("TF_PERF_TEST_CLOUD"):
            pytest.skip(
                "AWS credentials + registry access are not available in CI; "
                "set TF_PERF_TEST_CLOUD=1 on a credentialed machine to measure "
                "aws provider init/plan cost"
            )

        config = generate_terraform_config(resource_count=3, provider="aws")
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success, f"terraform init failed: {init_result.stderr}"
            result = runner.plan()
            assert result.success, f"terraform plan failed: {result.stderr}"
            assert plan_add_count(result) == 3


@pytest.mark.terraform
class TestTerraformPlanScaling:
    """Test how terraform plan scales with resource count."""

    @pytest.mark.parametrize("resource_count", [1, 5, 10, 25, 50, 100])
    def test_plan_scaling(self, terraform_runner, temp_workspace, resource_count):
        """Plan must cover the whole configuration and stay inside budget."""
        config = generate_terraform_config(resource_count=resource_count)
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            init_result = runner.init(backend=False)
            assert init_result.success, f"terraform init failed: {init_result.stderr}"

            result = runner.plan()
            assert result.success, f"terraform plan failed: {result.stderr}"
            assert plan_add_count(result) == resource_count, (
                f"plan with {resource_count} resources reported "
                f"{plan_add_count(result)} to add:\n{result.stdout[-1500:]}"
            )
            expected_max = budget_for(resource_count)
            assert result.elapsed_ms < expected_max, (
                f"plan with {resource_count} resources took {result.elapsed_ms:.1f}ms, "
                f"expected < {expected_max}ms"
            )

    def test_plan_cost_does_not_explode_with_resource_count(self, terraform_runner, temp_workspace):
        """Plan cost must not grow super-linearly between 5 and 100 resources.

        This is the scaling property, expressed as a ratio so it survives being
        run on a machine of any speed: 20x the resources must not cost 20x the
        time. Median of 3 runs each, because a single 30 ms sample is noise.
        Measured on this machine: 5 resources ~32 ms, 100 resources ~59 ms
        (ratio ~1.8). A quadratic blow-up would put the ratio near 20.
        """
        timings = {}
        for resource_count in (5, 100):
            config = generate_terraform_config(resource_count=resource_count)
            with terraform_workspace(config, temp_workspace) as workspace:
                runner = TerraformRunner(workspace)
                assert runner.init(backend=False).success
                samples = []
                for _ in range(3):
                    result = runner.plan()
                    assert result.success, f"terraform plan failed: {result.stderr}"
                    samples.append(result.elapsed_ms)
                timings[resource_count] = statistics.median(samples)

        small, large = timings[5], timings[100]
        assert large < small * 10, (
            f"plan time grew {large / small:.1f}x for 20x the resources "
            f"({small:.1f}ms -> {large:.1f}ms); expected sub-linear growth"
        )
        assert large - small < 2_000, (
            f"100-resource plan cost {large - small:.1f}ms more than a 5-resource "
            "plan; expected well under 2s of growth"
        )
