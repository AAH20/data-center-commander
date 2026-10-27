"""
Terraform Drift Detection Performance Tests.

Tests the performance of detecting configuration drift between
the desired state (terraform config) and actual state.

Drift is only meaningful if there IS state to compare against, so every test
here applies the configuration first (against the built-in provider, so state
is local and no cloud resource is created) and then reconciles or plans over
it. The assertion that makes these tests non-vacuous is the pair:

    plan over unchanged state     -> exit 0, changes_present False
    plan over edited configuration -> exit 2, changes_present True

The old suite asserted `result.success` on a `-detailed-exitcode` plan, which
treats exit code 2 -- the documented "changes present" result -- as a failure,
and it never wrote state at all, so every refresh was a no-op over an empty
state file and every drift plan saw "N to add" instead of drift.

Budgets are 30-80x the measured cost of the same operation over real local
state (see docs/iac-performance.md).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from utils.terraform_utils import (
    TerraformRunner,
    generate_terraform_config,
    plan_change_count,
    rewrite_main_tf,
    terraform_workspace,
)

# Measured medians over 5-100 local resources: refresh 31-58 ms, state list
# 25-27 ms, drift plan 29-58 ms. Budgets are sized against the failure mode --
# a refresh or plan that reaches a cloud API waits ~15 s for IMDS to time out --
# rather than against the measurement, so a 50x slower runner still passes and
# the historical failure still fails.
BUDGET_MS = {
    "refresh": 3_000,
    "state_list": 1_500,
    "plan": 3_000,
}

SCALING_FLOOR_MS = 1_000
SCALING_PER_RESOURCE_MS = 15


def budget_for(resource_count: int) -> float:
    return SCALING_FLOOR_MS + resource_count * SCALING_PER_RESOURCE_MS


def _apply_and_verify(runner: TerraformRunner, resource_count: int) -> None:
    """init + apply, and fail loudly if state does not hold resource_count."""
    init_result = runner.init(backend=False)
    assert init_result.success, f"terraform init failed: {init_result.stderr}"
    apply_result = runner.apply()
    assert apply_result.success, f"terraform apply failed: {apply_result.stderr}"
    listed = runner.state_list()
    assert listed.success, f"terraform state list failed: {listed.stderr}"
    addresses = listed.stdout.split()
    assert len(addresses) == resource_count, (
        f"expected {resource_count} resources in state before measuring drift, "
        f"got {len(addresses)}: {addresses[:5]}..."
    )


@pytest.mark.terraform
class TestDriftDetectionPerformance:
    """Test drift detection performance across different config sizes."""

    @pytest.mark.parametrize("size,resource_count", [("small", 5), ("medium", 25), ("large", 100)])
    def test_refresh_config(self, terraform_runner, temp_workspace, size, resource_count):
        """terraform refresh over existing state, within budget."""
        config = generate_terraform_config(resource_count=resource_count)
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            _apply_and_verify(runner, resource_count)

            result = runner.refresh()
            assert result.success, f"terraform refresh failed: {result.stderr}"
            # Structural: refresh must have reloaded the state it was given.
            assert "Refreshing state..." in result.combined_output, (
                "refresh did not report reconciling any state, so it measured "
                f"nothing:\n{result.combined_output[:800]}"
            )
            assert result.elapsed_ms < BUDGET_MS["refresh"], (
                f"{size} refresh took {result.elapsed_ms:.1f}ms, "
                f"budget: {BUDGET_MS['refresh']}ms"
            )

    @pytest.mark.parametrize("size,resource_count", [("small", 5), ("medium", 25), ("large", 100)])
    def test_drift_plan_config(self, terraform_runner, temp_workspace, size, resource_count):
        """plan -detailed-exitcode must report no drift, then drift, in budget."""
        config = generate_terraform_config(resource_count=resource_count)
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            _apply_and_verify(runner, resource_count)

            # No drift: state matches configuration.
            clean = runner.plan(detailed_exitcode=True)
            assert clean.success, f"terraform plan failed: {clean.stderr}"
            assert clean.returncode == 0, (
                f"plan over unchanged state reported changes (exit {clean.returncode}):\n"
                f"{clean.stdout[-1200:]}"
            )
            assert clean.changes_present is False

            # Drift: same addresses, different desired values.
            drifted = generate_terraform_config(resource_count=resource_count, drift=True)
            rewrite_main_tf(workspace, drifted)

            detected = runner.plan(detailed_exitcode=True)
            assert detected.success, f"drift plan failed: {detected.stderr}"
            assert detected.returncode == 2, (
                f"plan did not detect drift after the configuration changed "
                f"(exit {detected.returncode}):\n{detected.stdout[-1200:]}"
            )
            assert detected.changes_present is True
            assert plan_change_count(detected) == resource_count, (
                f"drift plan should report {resource_count} changed resources, "
                f"reported {plan_change_count(detected)}:\n{detected.stdout[-1200:]}"
            )
            assert detected.elapsed_ms < BUDGET_MS["plan"], (
                f"{size} drift plan took {detected.elapsed_ms:.1f}ms, "
                f"budget: {BUDGET_MS['plan']}ms"
            )

    @pytest.mark.parametrize("size,resource_count", [("small", 5), ("medium", 25), ("large", 100)])
    def test_state_list_config(self, terraform_runner, temp_workspace, size, resource_count):
        """terraform state list must return every address, in budget."""
        config = generate_terraform_config(resource_count=resource_count)
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            _apply_and_verify(runner, resource_count)

            result = runner.state_list()
            assert result.success, f"terraform state list failed: {result.stderr}"
            addresses = result.stdout.split()
            assert len(addresses) == resource_count, (
                f"{size} state list returned {len(addresses)} addresses, "
                f"expected {resource_count}"
            )
            assert addresses[0].startswith("terraform_data."), (
                f"unexpected address form in state: {addresses[0]!r}"
            )
            assert result.elapsed_ms < BUDGET_MS["state_list"], (
                f"{size} state list took {result.elapsed_ms:.1f}ms, "
                f"budget: {BUDGET_MS['state_list']}ms"
            )


@pytest.mark.terraform
class TestDriftDetectionScaling:
    """Test how drift detection scales with resource count."""

    @pytest.mark.parametrize("resource_count", [1, 5, 10, 25, 50, 100])
    def test_refresh_scaling(self, terraform_runner, temp_workspace, resource_count):
        """Refresh cost per resource must stay inside the scaling budget."""
        config = generate_terraform_config(resource_count=resource_count)
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            _apply_and_verify(runner, resource_count)

            result = runner.refresh()
            assert result.success, f"terraform refresh failed: {result.stderr}"
            expected_max = budget_for(resource_count)
            assert result.elapsed_ms < expected_max, (
                f"refresh with {resource_count} resources took {result.elapsed_ms:.1f}ms, "
                f"expected < {expected_max}ms"
            )

    @pytest.mark.parametrize("resource_count", [1, 5, 10, 25, 50, 100])
    def test_drift_plan_scaling(self, terraform_runner, temp_workspace, resource_count):
        """Drift plans must scale, and must report every drifted resource."""
        config = generate_terraform_config(resource_count=resource_count)
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            _apply_and_verify(runner, resource_count)

            rewrite_main_tf(workspace, generate_terraform_config(resource_count, drift=True))
            result = runner.plan(detailed_exitcode=True)
            assert result.success, f"drift plan failed: {result.stderr}"
            assert result.returncode == 2, (
                f"drift was not detected for {resource_count} resources:\n"
                f"{result.stdout[-1200:]}"
            )
            assert plan_change_count(result) == resource_count
            expected_max = budget_for(resource_count)
            assert result.elapsed_ms < expected_max, (
                f"drift plan with {resource_count} resources took "
                f"{result.elapsed_ms:.1f}ms, expected < {expected_max}ms"
            )


@pytest.mark.terraform
class TestDriftDetectionWithModules:
    """Test drift detection performance with terraform modules."""

    def test_refresh_with_modules(self, terraform_runner, temp_workspace):
        """Refresh over a configuration that uses a module."""
        config = generate_terraform_config(resource_count=10, include_modules=True)
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            _apply_and_verify(runner, 15)

            result = runner.refresh()
            assert result.success, f"terraform refresh failed: {result.stderr}"
            assert "module.nodes" in runner.state_list().stdout, (
                "module resources are missing from state; the module was not applied"
            )
            assert result.elapsed_ms < BUDGET_MS["refresh"], (
                f"refresh with modules took {result.elapsed_ms:.1f}ms, "
                f"budget: {BUDGET_MS['refresh']}ms"
            )

    def test_drift_plan_with_modules(self, terraform_runner, temp_workspace):
        """Drift inside a module must be detected, not just in the root module."""
        config = generate_terraform_config(resource_count=10, include_modules=True)
        with terraform_workspace(config, temp_workspace) as workspace:
            runner = TerraformRunner(workspace)
            _apply_and_verify(runner, 15)

            # Change only the module's own resources.
            module_main = Path(workspace) / "modules" / "nodes" / "main.tf"
            module_main.write_text(
                "\n".join(
                    'resource "terraform_data" "mod_' + str(i) + '" {\n'
                    f'  input = "drifted-{i}"\n'
                    "}"
                    for i in range(5)
                )
            )

            result = runner.plan(detailed_exitcode=True)
            assert result.success, f"drift plan failed: {result.stderr}"
            assert result.returncode == 2, (
                "drift inside a module was not detected:\n" + result.stdout[-1200:]
            )
            assert plan_change_count(result) == 5, (
                f"expected 5 module resources to change, got {plan_change_count(result)}"
            )
            assert result.elapsed_ms < BUDGET_MS["plan"], (
                f"drift plan with modules took {result.elapsed_ms:.1f}ms, "
                f"budget: {BUDGET_MS['plan']}ms"
            )
