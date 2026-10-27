"""
Policy Evaluation Performance Tests.

Tests the performance of OPA/Rego policy evaluation for
data center governance policies.

These tests assert the *decision*, not just the exit status. OPA exits 0 even
when the query fails to compile and even when the file it was handed is not a
policy, so a test that only checks `returncode == 0` passes against a broken
invocation. Every test here therefore reads `violations` (the deny set) and
checks that a non-compliant input yields strictly more violations than a
compliant one -- a differential property that fails if the policy stops
responding to its input, whatever the machine speed.

`opa eval <file.rego>` also does not load the file; the trailing argument is the
query. The runner builds `data.<package>.deny` from the policy's own package
declaration and passes `-d` for the policy and its sibling common.rego. See
utils/rego_utils.py.

Timing: budgets are 15-30x the measured CLI cost (13.9-33.0 ms, almost all
process startup). The benchmark test does not use the wall clock for the
judgement -- it asserts OPA's own `timer_rego_query_eval_ns` (measured 0.19 ms),
which is comparable between machines.
"""

from __future__ import annotations

import os
import time

import pytest
from utils.rego_utils import create_opa_input, decide_query, load_rego_policies

# Measured: one `opa eval` invocation 13.9-33.0 ms (median 15.2 ms over 10 runs),
# almost all process start; OPA's own query metric for the same evaluation is
# 186,125 ns (0.19 ms). Budgets are 15-30x the wall clock, which is the only part
# that varies with machine speed, and 5x the comparable per-query metric.
EVAL_BUDGET_MS = 500
BATCH_BUDGET_MS = {10: 1_500, 50: 4_000, 100: 8_000}
QUERY_EVAL_NS_BUDGET = 1_000_000  # 1 ms per evaluation, measured 0.19 ms

POLICIES = ("compliance", "resource_tagging", "network_segmentation", "encryption", "access_control")


def policy_path(rego_policy_dir: str, name: str) -> str:
    return os.path.join(rego_policy_dir, f"{name}.rego")


def assert_scored(result, context: str) -> None:
    """The evaluation must have run and produced a deny set."""
    assert result.success, f"{context}: OPA eval failed ({result.errors}): {result.stderr}"
    assert result.parsed_output is not None, f"{context}: no parsable JSON from OPA"
    assert isinstance(result.violations, list), f"{context}: deny set is not a list"
    assert result.elapsed_ms < EVAL_BUDGET_MS, (
        f"{context}: took {result.elapsed_ms:.1f}ms, budget: {EVAL_BUDGET_MS}ms"
    )


@pytest.mark.opa
class TestPolicyEvaluationPerformance:
    """Test OPA/Rego policy evaluation performance."""

    @pytest.mark.parametrize("policy_name", POLICIES)
    def test_eval_policy(self, opa_runner, rego_policy_dir, sample_opa_input, policy_name):
        """Each governance policy must respond to compliant vs non-compliant input."""
        path = policy_path(rego_policy_dir, policy_name)
        if not os.path.exists(path):
            pytest.skip(f"Policy not found: {path}")

        compliant = opa_runner.eval(path, input_data=sample_opa_input)
        assert_scored(compliant, f"{policy_name} (compliant)")

        non_compliant = opa_runner.eval(
            path,
            input_data=create_opa_input(
                tags={},
                encryption={"at_rest": False, "in_transit": False},
                network={"segment": "public"},
                access={"mfa": False, "privilege": "admin"},
                backup={"enabled": False},
                monitoring={"enabled": False},
                logging={"enabled": False},
                security_assessment="",
                risk_assessment="",
                audit_trail="",
            ),
        )
        assert_scored(non_compliant, f"{policy_name} (non-compliant)")

        assert len(non_compliant.violations) > len(compliant.violations), (
            f"{policy_name}: a deliberately non-compliant input produced "
            f"{len(non_compliant.violations)} violations, no more than the "
            f"compliant input's {len(compliant.violations)}. The policy is not "
            "reading its input, so this test would pass on any config."
        )

    def test_eval_compliance_policy_reports_the_named_control(
        self, opa_runner, rego_policy_dir, sample_opa_input
    ):
        """A missing control must be reported by name, not just counted."""
        path = policy_path(rego_policy_dir, "compliance")
        if not os.path.exists(path):
            pytest.skip(f"Policy not found: {path}")

        assert opa_runner.eval(path, input_data=sample_opa_input).violations == [], (
            "the compliant fixture is no longer compliant for the compliance policy"
        )

        result = opa_runner.eval(path, input_data=create_opa_input(audit_trail=""))
        assert_scored(result, "compliance (missing audit trail)")
        assert any("valid audit trail" in v for v in result.violations), (
            f"the audit-trail control did not fire by name: {result.violations[:5]}"
        )

    def test_query_is_derived_from_the_policy_package(self, rego_policy_dir):
        """The query must come from the policy's `package`, not from its filename.

        This is the defect that made every evaluation vacuous: the file path was
        passed where OPA expects a query.
        """
        path = policy_path(rego_policy_dir, "compliance")
        if not os.path.exists(path):
            pytest.skip(f"Policy not found: {path}")
        assert decide_query(path) == "data.datacenter.compliance.deny"


@pytest.mark.opa
class TestPolicyEvaluationNonCompliant:
    """Test policy evaluation performance with non-compliant inputs."""

    @pytest.mark.parametrize("policy_name", ("compliance", "encryption"))
    def test_eval_non_compliant(
        self, opa_runner, rego_policy_dir, non_compliant_opa_input, policy_name
    ):
        """A fully non-compliant input must produce violations for these policies."""
        path = policy_path(rego_policy_dir, policy_name)
        if not os.path.exists(path):
            pytest.skip(f"Policy not found: {path}")

        result = opa_runner.eval(path, input_data=non_compliant_opa_input)
        assert_scored(result, f"{policy_name} (non-compliant)")
        assert result.violations, (
            f"{policy_name}: the non-compliant fixture produced no violations at all"
        )


@pytest.mark.opa
class TestPolicyEvaluationBatch:
    """Test batch policy evaluation performance."""

    @pytest.mark.parametrize("count", [10, 50, 100])
    def test_batch_eval(self, opa_runner, rego_policy_dir, count):
        """count evaluations over distinct resources must all return decisions."""
        path = policy_path(rego_policy_dir, "compliance")
        if not os.path.exists(path):
            pytest.skip(f"Policy not found: {path}")

        decisions = []
        start = time.perf_counter()
        for i in range(count):
            result = opa_runner.eval(
                path, input_data=create_opa_input(resource_id=f"resource-{i}", audit_trail="")
            )
            assert result.success, f"OPA eval {i} failed: {result.errors} {result.stderr}"
            decisions.append(len(result.violations))
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Every one of the `count` resources is missing its audit trail, so every
        # evaluation must have found it. A batch that silently returned nothing
        # would otherwise be fast and green.
        assert all(d > 0 for d in decisions), (
            f"some evaluations returned no violations: {decisions}"
        )
        assert elapsed_ms < BATCH_BUDGET_MS[count], (
            f"batch of {count} evals took {elapsed_ms:.1f}ms, "
            f"budget: {BATCH_BUDGET_MS[count]}ms"
        )


@pytest.mark.opa
class TestPolicyEvaluationAllPolicies:
    """Test evaluation of all policies together."""

    @pytest.mark.parametrize("compliant", [True, False])
    def test_eval_all_policies(self, opa_runner, rego_policy_dir, sample_opa_input, non_compliant_opa_input, compliant):
        """Every policy in the directory must evaluate and return a decision."""
        policies = load_rego_policies(rego_policy_dir)
        if not policies:
            pytest.skip("No rego policies found")

        input_data = sample_opa_input if compliant else non_compliant_opa_input
        total_violations = 0

        start = time.perf_counter()
        for policy_name in sorted(policies):
            path = policy_path(rego_policy_dir, policy_name)
            result = opa_runner.eval(path, input_data=input_data)
            assert result.success, (
                f"Policy {policy_name} eval failed: {result.errors} {result.stderr}"
            )
            total_violations += len(result.violations)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if compliant:
            # The compliant fixture is clean for every policy except tagging,
            # which requires tag keys this fixture does not carry. Assert the
            # whole set stays bounded rather than pretending it is zero.
            assert total_violations < 100, (
                f"the compliant fixture produced {total_violations} violations "
                "across all policies; the fixtures have drifted from the policies"
            )
        else:
            assert total_violations > 100, (
                f"the non-compliant fixture produced only {total_violations} "
                "violations across all policies"
            )
        assert elapsed_ms < 1_500, f"all-policy evaluation took {elapsed_ms:.1f}ms"


@pytest.mark.opa
class TestPolicyEvaluationBenchmark:
    """Benchmark policy evaluation performance.

    Uses OPA's own query metrics (`timer_rego_query_eval_ns`) instead of the CLI
    wall clock: the latter is ~99% process startup, which says nothing about the
    policy. Repeated `--count N` runs give a median per evaluation.
    """

    @pytest.mark.benchmark
    @pytest.mark.parametrize("policy_name", ("compliance", "encryption"))
    def test_bench_policy(self, opa_runner, rego_policy_dir, sample_opa_input, policy_name):
        path = policy_path(rego_policy_dir, policy_name)
        if not os.path.exists(path):
            pytest.skip(f"Policy not found: {path}")

        result = opa_runner.bench(path, input_data=sample_opa_input, iterations=50)
        assert result.success, f"OPA benchmark failed: {result.errors} {result.stderr}"

        ns_per_eval = opa_runner.bench_ns_per_op(result)
        assert ns_per_eval is not None, (
            "OPA returned no query-eval metric, so nothing was benchmarked: "
            f"{result.stdout[:500]}"
        )
        assert ns_per_eval < QUERY_EVAL_NS_BUDGET, (
            f"{policy_name} query evaluation took {ns_per_eval / 1e6:.2f}ms, "
            f"budget: {QUERY_EVAL_NS_BUDGET / 1e6:.0f}ms per evaluation"
        )
        assert result.elapsed_ms < 20_000, (
            f"benchmark wall clock {result.elapsed_ms:.1f}ms exceeded 20s"
        )
