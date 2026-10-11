"""
Policy Evaluation Performance Tests.

Tests the performance of OPA/Rego policy evaluation for
data center governance policies.
"""

import os
import tempfile
import time

import pytest
from utils.rego_utils import create_opa_input, load_rego_policies

# Performance thresholds for policy evaluation (in milliseconds)
POLICY_THRESHOLDS = {
    "single_eval_small": 1_000,  # 1s for single policy evaluation
    "single_eval_medium": 2_000,  # 2s for single policy evaluation
    "single_eval_large": 5_000,  # 5s for single policy evaluation
    "full_compliance_small": 5_000,  # 5s for full compliance check (small)
    "full_compliance_medium": 10_000,  # 10s for full compliance check (medium)
    "full_compliance_large": 30_000,  # 30s for full compliance check (large)
    "batch_10": 10_000,  # 10s for batch of 10 evaluations
    "batch_50": 30_000,  # 30s for batch of 50 evaluations
    "batch_100": 60_000,  # 60s for batch of 100 evaluations
}


@pytest.mark.opa
class TestPolicyEvaluationPerformance:
    """Test OPA/Rego policy evaluation performance."""

    def test_eval_compliance_policy(self, opa_runner, rego_policy_dir, sample_opa_input):
        """Test evaluation of the compliance.rego policy."""
        policy_path = os.path.join(rego_policy_dir, "compliance.rego")
        if not os.path.exists(policy_path):
            pytest.skip(f"Policy not found: {policy_path}")

        result = opa_runner.eval(policy_path, input_data=sample_opa_input)
        assert result.success, f"OPA eval failed: {result.stderr}"
        assert result.elapsed_ms < POLICY_THRESHOLDS["single_eval_small"], (
            f"compliance policy eval took {result.elapsed_ms:.1f}ms, "
            f"threshold: {POLICY_THRESHOLDS['single_eval_small']}ms"
        )

    def test_eval_resource_tagging_policy(self, opa_runner, rego_policy_dir, sample_opa_input):
        """Test evaluation of the resource_tagging.rego policy."""
        policy_path = os.path.join(rego_policy_dir, "resource_tagging.rego")
        if not os.path.exists(policy_path):
            pytest.skip(f"Policy not found: {policy_path}")

        result = opa_runner.eval(policy_path, input_data=sample_opa_input)
        assert result.success, f"OPA eval failed: {result.stderr}"
        assert result.elapsed_ms < POLICY_THRESHOLDS["single_eval_small"], (
            f"resource tagging policy eval took {result.elapsed_ms:.1f}ms, "
            f"threshold: {POLICY_THRESHOLDS['single_eval_small']}ms"
        )

    def test_eval_network_segmentation_policy(self, opa_runner, rego_policy_dir, sample_opa_input):
        """Test evaluation of the network_segmentation.rego policy."""
        policy_path = os.path.join(rego_policy_dir, "network_segmentation.rego")
        if not os.path.exists(policy_path):
            pytest.skip(f"Policy not found: {policy_path}")

        result = opa_runner.eval(policy_path, input_data=sample_opa_input)
        assert result.success, f"OPA eval failed: {result.stderr}"
        assert result.elapsed_ms < POLICY_THRESHOLDS["single_eval_small"], (
            f"network segmentation policy eval took {result.elapsed_ms:.1f}ms, "
            f"threshold: {POLICY_THRESHOLDS['single_eval_small']}ms"
        )

    def test_eval_encryption_policy(self, opa_runner, rego_policy_dir, sample_opa_input):
        """Test evaluation of the encryption.rego policy."""
        policy_path = os.path.join(rego_policy_dir, "encryption.rego")
        if not os.path.exists(policy_path):
            pytest.skip(f"Policy not found: {policy_path}")

        result = opa_runner.eval(policy_path, input_data=sample_opa_input)
        assert result.success, f"OPA eval failed: {result.stderr}"
        assert result.elapsed_ms < POLICY_THRESHOLDS["single_eval_small"], (
            f"encryption policy eval took {result.elapsed_ms:.1f}ms, "
            f"threshold: {POLICY_THRESHOLDS['single_eval_small']}ms"
        )

    def test_eval_access_control_policy(self, opa_runner, rego_policy_dir, sample_opa_input):
        """Test evaluation of the access_control.rego policy."""
        policy_path = os.path.join(rego_policy_dir, "access_control.rego")
        if not os.path.exists(policy_path):
            pytest.skip(f"Policy not found: {policy_path}")

        result = opa_runner.eval(policy_path, input_data=sample_opa_input)
        assert result.success, f"OPA eval failed: {result.stderr}"
        assert result.elapsed_ms < POLICY_THRESHOLDS["single_eval_small"], (
            f"access control policy eval took {result.elapsed_ms:.1f}ms, "
            f"threshold: {POLICY_THRESHOLDS['single_eval_small']}ms"
        )


@pytest.mark.opa
class TestPolicyEvaluationNonCompliant:
    """Test policy evaluation performance with non-compliant inputs."""

    def test_eval_non_compliant_compliance(
        self, opa_runner, rego_policy_dir, non_compliant_opa_input
    ):
        """Test evaluation of compliance policy with non-compliant input."""
        policy_path = os.path.join(rego_policy_dir, "compliance.rego")
        if not os.path.exists(policy_path):
            pytest.skip(f"Policy not found: {policy_path}")

        result = opa_runner.eval(policy_path, input_data=non_compliant_opa_input)
        assert result.success, f"OPA eval failed: {result.stderr}"
        assert result.elapsed_ms < POLICY_THRESHOLDS["single_eval_medium"], (
            f"non-compliant compliance eval took {result.elapsed_ms:.1f}ms, "
            f"threshold: {POLICY_THRESHOLDS['single_eval_medium']}ms"
        )

    def test_eval_non_compliant_encryption(
        self, opa_runner, rego_policy_dir, non_compliant_opa_input
    ):
        """Test evaluation of encryption policy with non-compliant input."""
        policy_path = os.path.join(rego_policy_dir, "encryption.rego")
        if not os.path.exists(policy_path):
            pytest.skip(f"Policy not found: {policy_path}")

        result = opa_runner.eval(policy_path, input_data=non_compliant_opa_input)
        assert result.success, f"OPA eval failed: {result.stderr}"
        assert result.elapsed_ms < POLICY_THRESHOLDS["single_eval_medium"], (
            f"non-compliant encryption eval took {result.elapsed_ms:.1f}ms, "
            f"threshold: {POLICY_THRESHOLDS['single_eval_medium']}ms"
        )


@pytest.mark.opa
class TestPolicyEvaluationBatch:
    """Test batch policy evaluation performance."""

    def test_batch_eval_10_resources(self, opa_runner, rego_policy_dir, sample_opa_input):
        """Test batch evaluation of 10 resources against compliance policy."""
        policy_path = os.path.join(rego_policy_dir, "compliance.rego")
        if not os.path.exists(policy_path):
            pytest.skip(f"Policy not found: {policy_path}")

        start = time.perf_counter()
        for i in range(10):
            input_data = create_opa_input(resource_id=f"resource-{i}")
            result = opa_runner.eval(policy_path, input_data=input_data)
            assert result.success, f"OPA eval {i} failed: {result.stderr}"
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < POLICY_THRESHOLDS["batch_10"], (
            f"batch of 10 evals took {elapsed_ms:.1f}ms, "
            f"threshold: {POLICY_THRESHOLDS['batch_10']}ms"
        )

    def test_batch_eval_50_resources(self, opa_runner, rego_policy_dir, sample_opa_input):
        """Test batch evaluation of 50 resources against compliance policy."""
        policy_path = os.path.join(rego_policy_dir, "compliance.rego")
        if not os.path.exists(policy_path):
            pytest.skip(f"Policy not found: {policy_path}")

        start = time.perf_counter()
        for i in range(50):
            input_data = create_opa_input(resource_id=f"resource-{i}")
            result = opa_runner.eval(policy_path, input_data=input_data)
            assert result.success, f"OPA eval {i} failed: {result.stderr}"
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < POLICY_THRESHOLDS["batch_50"], (
            f"batch of 50 evals took {elapsed_ms:.1f}ms, "
            f"threshold: {POLICY_THRESHOLDS['batch_50']}ms"
        )

    def test_batch_eval_100_resources(self, opa_runner, rego_policy_dir, sample_opa_input):
        """Test batch evaluation of 100 resources against compliance policy."""
        policy_path = os.path.join(rego_policy_dir, "compliance.rego")
        if not os.path.exists(policy_path):
            pytest.skip(f"Policy not found: {policy_path}")

        start = time.perf_counter()
        for i in range(100):
            input_data = create_opa_input(resource_id=f"resource-{i}")
            result = opa_runner.eval(policy_path, input_data=input_data)
            assert result.success, f"OPA eval {i} failed: {result.stderr}"
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < POLICY_THRESHOLDS["batch_100"], (
            f"batch of 100 evals took {elapsed_ms:.1f}ms, "
            f"threshold: {POLICY_THRESHOLDS['batch_100']}ms"
        )


@pytest.mark.opa
class TestPolicyEvaluationAllPolicies:
    """Test evaluation of all policies together."""

    def test_eval_all_policies_compliant(self, opa_runner, rego_policy_dir, sample_opa_input):
        """Test evaluation of all policies with a compliant input."""
        policies = load_rego_policies(rego_policy_dir)
        if not policies:
            pytest.skip("No rego policies found")

        start = time.perf_counter()
        for policy_name, policy_content in policies.items():
            # Write policy to temp file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".rego", delete=False) as f:
                f.write(policy_content)
                policy_path = f.name

            try:
                result = opa_runner.eval(policy_path, input_data=sample_opa_input)
                assert result.success, f"Policy {policy_name} eval failed: {result.stderr}"
            finally:
                os.unlink(policy_path)

        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < POLICY_THRESHOLDS["full_compliance_small"], (
            f"all policies eval took {elapsed_ms:.1f}ms, "
            f"threshold: {POLICY_THRESHOLDS['full_compliance_small']}ms"
        )

    def test_eval_all_policies_non_compliant(
        self, opa_runner, rego_policy_dir, non_compliant_opa_input
    ):
        """Test evaluation of all policies with a non-compliant input."""
        policies = load_rego_policies(rego_policy_dir)
        if not policies:
            pytest.skip("No rego policies found")

        start = time.perf_counter()
        for policy_name, policy_content in policies.items():
            with tempfile.NamedTemporaryFile(mode="w", suffix=".rego", delete=False) as f:
                f.write(policy_content)
                policy_path = f.name

            try:
                result = opa_runner.eval(policy_path, input_data=non_compliant_opa_input)
                assert result.success, f"Policy {policy_name} eval failed: {result.stderr}"
            finally:
                os.unlink(policy_path)

        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < POLICY_THRESHOLDS["full_compliance_medium"], (
            f"all policies non-compliant eval took {elapsed_ms:.1f}ms, "
            f"threshold: {POLICY_THRESHOLDS['full_compliance_medium']}ms"
        )


@pytest.mark.opa
class TestPolicyEvaluationBenchmark:
    """Benchmark policy evaluation performance."""

    @pytest.mark.benchmark
    def test_bench_compliance_policy(self, opa_runner, rego_policy_dir, sample_opa_input):
        """Benchmark the compliance policy evaluation."""
        policy_path = os.path.join(rego_policy_dir, "compliance.rego")
        if not os.path.exists(policy_path):
            pytest.skip(f"Policy not found: {policy_path}")

        result = opa_runner.bench(policy_path, input_data=sample_opa_input, iterations=100)
        assert result.success, f"OPA bench failed: {result.stderr}"
        # Benchmark should complete within 60 seconds
        assert (
            result.elapsed_ms < 60_000
        ), f"benchmark took {result.elapsed_ms:.1f}ms, threshold: 60000ms"

    @pytest.mark.benchmark
    def test_bench_encryption_policy(self, opa_runner, rego_policy_dir, sample_opa_input):
        """Benchmark the encryption policy evaluation."""
        policy_path = os.path.join(rego_policy_dir, "encryption.rego")
        if not os.path.exists(policy_path):
            pytest.skip(f"Policy not found: {policy_path}")

        result = opa_runner.bench(policy_path, input_data=sample_opa_input, iterations=100)
        assert result.success, f"OPA bench failed: {result.stderr}"
        assert (
            result.elapsed_ms < 60_000
        ), f"benchmark took {result.elapsed_ms:.1f}ms, threshold: 60000ms"
