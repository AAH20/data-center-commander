"""
OPA/Rego evaluation utilities for performance testing.
Wraps `opa eval` commands with timing and result capture.
"""

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class OpaResult:
    """Result of an `opa eval` command."""

    command: str
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: float
    success: bool
    parsed_output: dict | None = None


class OpaRunner:
    """Runs OPA/Rego policy evaluations with timing."""

    def __init__(self, opa_bin: str = "opa"):
        self.opa_bin = opa_bin
        self._check_opa()

    def _check_opa(self):
        """Verify OPA binary is available."""
        try:
            result = subprocess.run(
                [self.opa_bin, "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError(f"OPA not available: {result.stderr}")
        except FileNotFoundError as e:
            raise RuntimeError(
                f"OPA binary not found: {self.opa_bin}. Install OPA or set OPA_BIN env var."
            ) from e

    def _run(self, args: list[str], timeout: int = 60) -> OpaResult:
        """Execute an opa command with timing."""
        cmd = [self.opa_bin] + args
        cmd_str = " ".join(cmd)

        start = time.perf_counter()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            parsed = None
            try:
                parsed = json.loads(result.stdout)
            except json.JSONDecodeError:
                parsed = None

            return OpaResult(
                command=cmd_str,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                elapsed_ms=elapsed_ms,
                success=result.returncode == 0,
                parsed_output=parsed,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return OpaResult(
                command=cmd_str,
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                elapsed_ms=elapsed_ms,
                success=False,
            )

    def eval(
        self,
        policy_path: str,
        input_data: dict | None = None,
        data_path: str | None = None,
        timeout: int = 60,
    ) -> OpaResult:
        """
        Run `opa eval` on a policy with optional input data.
        """
        args = ["eval", "--format", "json"]

        if data_path:
            args.extend(["--data", data_path])

        if input_data is not None:
            input_json = json.dumps(input_data)
            args.extend(["--input", "-"])
            # We need to pass input via stdin
            cmd = [self.opa_bin] + args + [policy_path]
            cmd_str = " ".join(cmd)

            start = time.perf_counter()
            try:
                result = subprocess.run(
                    cmd,
                    input=input_json,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                elapsed_ms = (time.perf_counter() - start) * 1000

                parsed = None
                try:
                    parsed = json.loads(result.stdout)
                except json.JSONDecodeError:
                    parsed = None

                return OpaResult(
                    command=cmd_str,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    elapsed_ms=elapsed_ms,
                    success=result.returncode == 0,
                    parsed_output=parsed,
                )
            except subprocess.TimeoutExpired:
                elapsed_ms = (time.perf_counter() - start) * 1000
                return OpaResult(
                    command=cmd_str,
                    returncode=-1,
                    stdout="",
                    stderr=f"Command timed out after {timeout}s",
                    elapsed_ms=elapsed_ms,
                    success=False,
                )
        else:
            args.append(policy_path)
            return self._run(args, timeout=timeout)

    def eval_file(
        self,
        policy_path: str,
        input_path: str,
        data_path: str | None = None,
        timeout: int = 60,
    ) -> OpaResult:
        """Run `opa eval` with input from a file."""
        args = ["eval", "--format", "json", "--input", input_path]
        if data_path:
            args.extend(["--data", data_path])
        args.append(policy_path)
        return self._run(args, timeout=timeout)

    def test_policy(
        self,
        policy_dir: str,
        timeout: int = 60,
    ) -> OpaResult:
        """Run `opa test` on a policy directory."""
        return self._run(["test", policy_dir, "--format", "json"], timeout=timeout)

    def bench(
        self,
        policy_path: str,
        input_data: dict | None = None,
        iterations: int = 100,
        timeout: int = 120,
    ) -> OpaResult:
        """Run `opa bench` for benchmarking a policy."""
        args = ["eval", "--bench", "--format", "json", "--count", str(iterations)]

        if input_data is not None:
            input_json = json.dumps(input_data)
            args.extend(["--input", "-"])
            cmd = [self.opa_bin] + args + [policy_path]
            cmd_str = " ".join(cmd)

            start = time.perf_counter()
            try:
                result = subprocess.run(
                    cmd,
                    input=input_json,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                elapsed_ms = (time.perf_counter() - start) * 1000

                return OpaResult(
                    command=cmd_str,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    elapsed_ms=elapsed_ms,
                    success=result.returncode == 0,
                )
            except subprocess.TimeoutExpired:
                elapsed_ms = (time.perf_counter() - start) * 1000
                return OpaResult(
                    command=cmd_str,
                    returncode=-1,
                    stdout="",
                    stderr=f"Command timed out after {timeout}s",
                    elapsed_ms=elapsed_ms,
                    success=False,
                )
        else:
            args.append(policy_path)
            return self._run(args, timeout=timeout)


def load_rego_policies(policy_dir: str) -> dict[str, str]:
    """Load all .rego files from a directory."""
    policies = {}
    policy_path = Path(policy_dir)
    for rego_file in policy_path.glob("*.rego"):
        policies[rego_file.stem] = rego_file.read_text()
    return policies


def create_opa_input(
    resource_id: str = "test-resource",
    environment: str = "production",
    region: str = "us-east-1",
    resource_type: str = "aws_instance",
    tags: dict | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Create a standard OPA input document for testing."""
    if tags is None:
        tags = {"owner": "test-team", "cost_center": "cc-1234"}

    input_doc = {
        "resource_id": resource_id,
        "environment": environment,
        "region": region,
        "resource_type": resource_type,
        "tags": tags,
        "encryption": {"at_rest": True, "in_transit": True},
        "network": {"segment": "restricted"},
        "access": {"mfa": True, "privilege": "least"},
        "retention_days": 30,
        "max_retention_days": 90,
        "last_review_days": 30,
        "backup": {"enabled": True},
        "monitoring": {"enabled": True},
        "logging": {"enabled": True},
        "certificate": {"expiry_days": 365},
        "license": {"expiry_days": 365},
        "support": {"expiry_days": 365},
        "maintenance_window": "sun:02:00-sun:04:00",
        "change_management": "approved",
        "incident_response": "documented",
        "disaster_recovery": "documented",
        "business_continuity": "documented",
        "security_assessment": "completed",
        "risk_assessment": "completed",
        "compliance_assessment": "completed",
        "audit_trail": "enabled",
        "configuration_management": "tracked",
        "asset_inventory": "registered",
        "vulnerability_management": "scanned",
        "patch_management": "current",
        "capacity_management": "monitored",
        "performance_management": "monitored",
        "availability_management": "monitored",
        "service_level_agreement": "defined",
        "operational_level_agreement": "defined",
        "underpinning_contract": "signed",
        "service_catalog": "listed",
        "service_portfolio": "listed",
        "service_design_package": "documented",
        "service_transition_plan": "documented",
        "service_operation_plan": "documented",
        "continual_service_improvement_plan": "documented",
        "service_reporting": "enabled",
        "service_measurement": "enabled",
        "service_level_management": "enabled",
        "service_continuity_management": "enabled",
        "it_service_continuity_management": "enabled",
        "information_security_management": "enabled",
        "supplier_management": "enabled",
        "relationship_management": "enabled",
        "design_coordination": "enabled",
        "service_asset_and_configuration_management": "enabled",
        "release_and_deployment_management": "enabled",
        "service_validation_and_testing": "enabled",
        "knowledge_management": "enabled",
        "incident_management": "enabled",
        "problem_management": "enabled",
        "event_management": "enabled",
        "request_fulfillment": "enabled",
        "access_management": "enabled",
        "service_desk": "enabled",
        "technical_management": "enabled",
        "application_management": "enabled",
        "it_operations_management": "enabled",
        "facilities_management": "enabled",
        "infrastructure_management": "enabled",
        "network_management": "enabled",
        "storage_management": "enabled",
        "database_management": "enabled",
        "middleware_management": "enabled",
        "web_management": "enabled",
        "identity_management": "enabled",
        "entitlement_management": "enabled",
        "role_management": "enabled",
        "privilege_management": "enabled",
        "policy_management": "enabled",
        "compliance_management": "enabled",
        "risk_management": "enabled",
        "audit_management": "enabled",
        "governance": "enabled",
    }
    input_doc.update(kwargs)
    return input_doc
