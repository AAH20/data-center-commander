"""
Compliance Scan Performance Tests.

Tests the performance of compliance scanning using Checkov
with both built-in and custom data center policies.

Checkov is a static analyser: it parses .tf files and needs no credentials, so
these tests run for real in CI. What they cannot do is measure a scan that never
happened -- checkov exits 0 and reports `resource_count: 0` when the directory
or the check IDs it was given match nothing. Three tests here used to assert
only a wall-clock budget against exactly that: `--check DC_NET_001` with no
`--external-checks-dir` selects a check that is not installed, so checkov parsed
no resources and returned success. Every test below now asserts that the scan
examined the resources it was pointed at, and the specific-check tests use check
IDs that exist in checkov's own policy set.

Budgets: a single 25 s ceiling for one scan. Measured cost is 1.1-2.2 s idle and
up to 7.84 s with four test workers competing for the same CPU, so 25 s is ~3x
the worst contended measurement and does not flake; it is a "the scan did not
hang" tripwire, not the scaling guard. The scaling property is asserted as a
ratio (`test_scan_cost_is_sublinear`), which is machine-independent, and the
offline contract (`TestCheckovOfflineContract`) is what stops the 12.6 s Prisma
Cloud round trip from creeping back in.
"""

from __future__ import annotations

import os
import statistics

import pytest
from utils.checkov_utils import (
    checkov_env,
    generate_terraform_file,
    generate_terraform_module,
)

# Ceiling for a single checkov invocation. See the module docstring.
SCAN_BUDGET_MS = 25_000

# Check IDs that exist in checkov's bundled terraform policy set. The previous
# tests used DC_NET_001 / DC_CRYPTO_001 / DC_IAM_001, which are this repo's own
# check IDs in policies/checkov; passed without --external-checks-dir they match
# no installed check, so checkov reported resource_count 0 and the test asserted
# a timestamp on an empty scan. See docs/iac-performance.md.
NETWORK_CHECKS = ["CKV_AWS_79", "CKV_AWS_23"]
ENCRYPTION_CHECKS = ["CKV_AWS_8", "CKV_AWS_19"]
IAM_CHECKS = ["CKV_AWS_290", "CKV_AWS_355"]


def write_config(directory: str, resource_count: int, compliant: bool = True) -> str:
    """Write a main.tf into directory and return its path."""
    tf_file = os.path.join(directory, "main.tf")
    with open(tf_file, "w") as f:
        f.write(generate_terraform_file(resource_count=resource_count, compliant=compliant))
    return tf_file


def assert_scan_examined(result, expected_resources: int, context: str) -> None:
    """The scan must have parsed the resources and evaluated at least one check.

    Without this, a scan that matched no check at all passes on timing alone.
    """
    assert result.parsed_output is not None, (
        f"{context}: checkov produced no parsable JSON. stderr:\n{result.stderr[-800:]}"
    )
    assert result.resource_count == expected_resources, (
        f"{context}: checkov parsed {result.resource_count} resources, "
        f"expected {expected_resources}. A scan that parses nothing cannot fail."
    )
    assert result.checks_evaluated > 0, (
        f"{context}: checkov evaluated 0 checks over {result.resource_count} "
        f"resources; nothing was measured"
    )


@pytest.mark.checkov
class TestComplianceScanPerformance:
    """Test compliance scan performance across different config sizes."""

    @pytest.mark.parametrize("size,resource_count", [("small", 5), ("medium", 25), ("large", 100)])
    def test_scan_built_in(self, checkov_runner, temp_workspace, size, resource_count):
        """Built-in checks over a config of the given size."""
        write_config(temp_workspace, resource_count)
        result = checkov_runner.scan_directory(temp_workspace)

        assert_scan_examined(result, resource_count, f"{size} built-in scan")
        assert result.elapsed_ms < SCAN_BUDGET_MS, (
            f"{size} built-in scan took {result.elapsed_ms:.1f}ms, "
            f"budget: {SCAN_BUDGET_MS}ms"
        )

    @pytest.mark.parametrize("size,resource_count", [("small", 5), ("medium", 25), ("large", 100)])
    def test_scan_custom_policies(
        self, checkov_runner, checkov_policy_dir, temp_workspace, size, resource_count
    ):
        """Custom data centre policies over a config of the given size."""
        write_config(temp_workspace, resource_count)
        result = checkov_runner.scan_with_custom_policies(temp_workspace, checkov_policy_dir)

        assert_scan_examined(result, resource_count, f"{size} custom-policy scan")
        assert result.elapsed_ms < SCAN_BUDGET_MS, (
            f"{size} custom scan took {result.elapsed_ms:.1f}ms, "
            f"budget: {SCAN_BUDGET_MS}ms"
        )


@pytest.mark.checkov
class TestComplianceScanWithNonCompliantResources:
    """Test compliance scan performance with non-compliant resources."""

    @pytest.mark.parametrize("size,resource_count", [("small", 5), ("medium", 25), ("large", 100)])
    def test_scan_non_compliant(self, checkov_runner, temp_workspace, size, resource_count):
        """Non-compliant resources must be scanned AND reported as failing."""
        write_config(temp_workspace, resource_count, compliant=False)
        result = checkov_runner.scan_directory(temp_workspace)

        assert_scan_examined(result, resource_count, f"{size} non-compliant scan")
        assert result.failed_checks > 0, (
            f"{size} non-compliant scan reported no failed checks; the findings "
            "half of this test is vacuous"
        )
        assert result.elapsed_ms < SCAN_BUDGET_MS, (
            f"{size} non-compliant scan took {result.elapsed_ms:.1f}ms, "
            f"budget: {SCAN_BUDGET_MS}ms"
        )


@pytest.mark.checkov
class TestComplianceScanScaling:
    """Test how compliance scan scales with resource count."""

    @pytest.mark.parametrize("resource_count", [1, 5, 10, 25, 50, 100])
    def test_scan_scaling(self, checkov_runner, temp_workspace, resource_count):
        """Scan must examine every resource and finish inside the ceiling."""
        write_config(temp_workspace, resource_count)
        result = checkov_runner.scan_directory(temp_workspace)

        assert_scan_examined(result, resource_count, f"scaling scan n={resource_count}")
        assert result.elapsed_ms < SCAN_BUDGET_MS, (
            f"scan with {resource_count} resources took {result.elapsed_ms:.1f}ms, "
            f"budget: {SCAN_BUDGET_MS}ms"
        )

    def test_scan_cost_is_sublinear(self, checkov_runner, temp_workspace):
        """100x the resources must not cost anything like 100x the time.

        A ratio, not a threshold: the absolute cost of a scan is dominated by
        checkov's framework import and by whatever else the machine is doing, so
        an absolute budget either cannot fail or fails on a busy runner. The
        ratio cancels both. Measured while this machine was busy: 2621 ms for 1
        resource and 2321 ms for 100 (0.9x) -- the cost is the framework import,
        not the resource count. A per-resource blow-up (re-parsing, a
        cross-product graph walk) shows up as a ratio near 100.
        """
        timings = {}
        for count in (1, 100):
            directory = os.path.join(temp_workspace, f"n{count}")
            os.makedirs(directory, exist_ok=True)
            write_config(directory, count)
            samples = []
            for _ in range(2):
                result = checkov_runner.scan_directory(directory)
                assert_scan_examined(result, count, f"sublinear scan n={count}")
                samples.append(result.elapsed_ms)
            timings[count] = statistics.median(samples)

        small, large = timings[1], timings[100]
        assert large < small * 5, (
            f"scan time grew {large / small:.1f}x for 100x the resources "
            f"({small:.0f}ms -> {large:.0f}ms); a scan that is linear in resource "
            "count would be ~100x, and anything above 5x is a regression"
        )


@pytest.mark.checkov
class TestComplianceScanWithModules:
    """Test compliance scan performance with terraform modules."""

    def test_scan_with_modules(self, checkov_runner, temp_workspace):
        """Scan a config that includes a local module."""
        module_dir = os.path.join(temp_workspace, "modules", "vpc")
        os.makedirs(module_dir, exist_ok=True)
        with open(os.path.join(module_dir, "main.tf"), "w") as f:
            f.write(generate_terraform_module("vpc", resource_count=5))

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
        # 1 root resource + 1 vpc + 5 subnets.
        assert_scan_examined(result, 7, "module scan")
        assert result.elapsed_ms < SCAN_BUDGET_MS, (
            f"scan with modules took {result.elapsed_ms:.1f}ms, budget: {SCAN_BUDGET_MS}ms"
        )


@pytest.mark.checkov
class TestComplianceScanSpecificChecks:
    """Test compliance scan performance for specific check categories.

    Each of these selects a named subset of checkov's own checks, so the scan
    parses the config and evaluates exactly those checks. The assertion that the
    named checks actually ran is what distinguishes this from a budget on an
    empty scan.
    """

    def _scan_subset(self, checkov_runner, temp_workspace, checks, resource_count=10):
        write_config(temp_workspace, resource_count)
        return self._assert_subset(checkov_runner.scan_directory(temp_workspace, check=checks), checks, resource_count)

    @staticmethod
    def _assert_subset(result, checks, resource_count):
        assert_scan_examined(result, resource_count, f"subset scan {checks}")
        # Every selected check must have produced at least one verdict. checkov
        # reports one verdict per applicable (check, resource) pair, so the total
        # is >= the number of checks as soon as the config is in scope; a check
        # ID that matches nothing yields 0 verdicts and is the failure this
        # guards against.
        assert result.checks_evaluated >= len(checks), (
            f"expected at least {len(checks)} verdicts from {checks}, "
            f"got {result.checks_evaluated}"
        )
        return result

    def test_scan_network_security_checks(self, checkov_runner, temp_workspace):
        result = self._scan_subset(checkov_runner, temp_workspace, NETWORK_CHECKS)
        assert result.elapsed_ms < SCAN_BUDGET_MS, (
            f"network check subset scan took {result.elapsed_ms:.1f}ms, budget: {SCAN_BUDGET_MS}ms"
        )

    def test_scan_encryption_checks(self, checkov_runner, temp_workspace):
        result = self._scan_subset(checkov_runner, temp_workspace, ENCRYPTION_CHECKS)
        assert result.elapsed_ms < SCAN_BUDGET_MS, (
            f"encryption check subset scan took {result.elapsed_ms:.1f}ms, budget: {SCAN_BUDGET_MS}ms"
        )

    def test_scan_iam_checks(self, checkov_runner, temp_workspace):
        """IAM checks need IAM resources: an instance-only config matches none.

        With aws_instance configs, `--check CKV_AWS_40` parsed zero resources and
        returned success, which is exactly the empty scan the old version of
        this test timed. The config here contains an assume-anything IAM policy
        and three roles, so the checks have something to judge.
        """
        iam_tf = """
resource "aws_iam_policy" "admin" {
  name = "admin"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "*"
      Resource = "*"
    }]
  })
}
"""
        for i in range(3):
            iam_tf += f"""
resource "aws_iam_role" "role_{i}" {{
  name               = "role-{i}"
  assume_role_policy = "{{}}"
}}
"""
        with open(os.path.join(temp_workspace, "main.tf"), "w") as f:
            f.write(iam_tf)

        result = self._assert_subset(
            checkov_runner.scan_directory(temp_workspace, check=IAM_CHECKS),
            IAM_CHECKS,
            resource_count=4,
        )
        assert result.failed_checks > 0, (
            "the wildcard IAM policy was not flagged; the scan produced verdicts "
            "but no finding"
        )
        assert result.elapsed_ms < SCAN_BUDGET_MS, (
            f"IAM check subset scan took {result.elapsed_ms:.1f}ms, budget: {SCAN_BUDGET_MS}ms"
        )


@pytest.mark.checkov
class TestCheckovOfflineContract:
    """A scan must not reach the network.

    checkov calls Prisma Cloud for policy metadata before scanning unless it is
    told not to. Measured on a one-resource config: 16.2 s wall for 2.5 s of user
    CPU with the call, 4.5 s without, identical findings. The call's latency also
    varied from 5 s to 90 s across runs, which is what made this file's timing
    assertions fail intermittently (three real failures, see
    docs/iac-performance.md) before it was disabled.

    This asserts the invocation rather than a duration, so it fails immediately
    and deterministically if `--skip-download` or the no-egress environment is
    dropped, instead of showing up as an occasional 45 s scan.
    """

    def test_scan_does_not_contact_prisma_cloud(self, checkov_runner, temp_workspace):
        write_config(temp_workspace, 1)
        result = checkov_runner.scan_directory(temp_workspace)

        # A scan of one resource must still have happened with egress blocked.
        assert_scan_examined(result, 1, "offline contract")

        assert "--skip-download" in result.command, (
            "scan_directory dropped --skip-download, so every scan pays a "
            f"Prisma Cloud round trip again: {result.command}"
        )
        assert "--skip-download" in checkov_runner.scan_file(
            os.path.join(temp_workspace, "main.tf")
        ).command, "scan_file dropped --skip-download"

        env = checkov_env()
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            value = env.get(key, "")
            assert value.startswith("http://127.0.0.1:"), (
                f"{key} is {value!r}: a checkov process with working egress "
                "can hang for a minute on a remote call instead of failing fast"
            )
        assert "127.0.0.1" in env.get("NO_PROXY", ""), (
            "NO_PROXY must keep loopback reachable for the terraform and OPA "
            f"processes this suite starts, got {env.get('NO_PROXY')!r}"
        )
