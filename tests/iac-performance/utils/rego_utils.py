"""
OPA/Rego evaluation utilities for performance testing.

Wraps `opa eval` commands with timing and result capture.

Three defects in the previous wrapper made every policy assertion vacuous, and
they are worth stating because each one produced a *passing* test that measured
nothing:

1. `opa eval <file.rego>` does not load the file -- the last positional
   argument is the *query*. The wrapper passed the policy path as the query, so
   OPA returned a parse error in the JSON body and the wrapper called it success.
2. `--input -` is not stdin for OPA; "-" was opened as a filename
   ("open -: no such file or directory"). Input has to go through `-I/--stdin-input`.
3. OPA exits 0 when the *query* fails to compile -- the error is in the JSON
   body under "errors". `success = returncode == 0` therefore reported a broken
   invocation as a successful evaluation.

The wrapper now builds a real query from the policy's own `package` statement
(`data.<pkg>.deny`), loads the policy plus the sibling `common.rego` that every
policy in this repo imports, feeds input on stdin, and treats a JSON `errors`
array as failure. `violations` is the deny set itself, so tests can assert the
decision and not just the exit status.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*$", re.MULTILINE)


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
    # The evaluated decision, when the query returned a set/array of strings.
    violations: list[str] = field(default_factory=list)
    # OPA reports query/compile failures in the body with exit status 0.
    errors: list[str] = field(default_factory=list)

    @property
    def combined_output(self) -> str:
        return f"{self.stdout}\n{self.stderr}"


def policy_package(policy_path: str) -> str | None:
    """Read the `package` name out of a .rego file."""
    try:
        text = Path(policy_path).read_text()
    except OSError:
        return None
    match = _PACKAGE_RE.search(text)
    return match.group(1) if match else None


def decide_query(policy_path: str, rule: str = "deny") -> str | None:
    """Build `data.<package>.<rule>` for a policy file, or None if unparseable."""
    package = policy_package(policy_path)
    if not package:
        return None
    return f"data.{package}.{rule}"


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

    # -- internals ---------------------------------------------------------

    def _data_args(self, policy_path: str, data_path: str | None) -> list[str]:
        """`-d` args: the policy file plus its sibling common.rego.

        Every policy here does `import data.common`, so evaluating one file in
        isolation fails to compile. Loading the whole directory is not an
        option either: policies/rego/testdata holds several JSON documents and
        OPA refuses to merge them into one data tree ("merge error").
        """
        args = ["-d", policy_path]
        if data_path:
            args.extend(["-d", data_path])
        else:
            sibling = Path(policy_path).parent / "common.rego"
            if sibling.is_file():
                args.extend(["-d", str(sibling)])
        return args

    @staticmethod
    def _parse(stdout: str) -> tuple[dict | None, list[str], list[str]]:
        """Return (parsed, errors, violations) from an opa eval JSON body."""
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            return None, [], []
        if not isinstance(parsed, dict):
            return None, [], []

        errors = [str(e.get("message", e)) for e in parsed.get("errors", []) or []]
        violations: list[str] = []
        try:
            value = parsed["result"][0]["expressions"][0]["value"]
        except (KeyError, IndexError, TypeError):
            value = None
        if isinstance(value, list):
            violations = [v for v in value if isinstance(v, str)]
        elif isinstance(value, str):
            violations = [value]
        return parsed, errors, violations

    def _execute(self, args: list[str], input_json: str | None, timeout: int) -> OpaResult:
        cmd = [self.opa_bin] + args
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
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return OpaResult(
                command=cmd_str,
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                elapsed_ms=elapsed_ms,
                success=False,
                errors=[f"timeout after {timeout}s"],
            )

        parsed, errors, violations = self._parse(result.stdout)
        return OpaResult(
            command=cmd_str,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            elapsed_ms=elapsed_ms,
            success=result.returncode == 0 and not errors,
            parsed_output=parsed,
            violations=violations,
            errors=errors,
        )

    # -- public API --------------------------------------------------------

    def eval(
        self,
        policy_path: str,
        input_data: dict | None = None,
        data_path: str | None = None,
        query: str | None = None,
        rule: str = "deny",
        timeout: int = 60,
    ) -> OpaResult:
        """Evaluate `data.<package>.<rule>` in policy_path against input_data."""
        query = query or decide_query(policy_path, rule=rule)
        if query is None:
            return OpaResult(
                command=f"{self.opa_bin} eval (unparseable policy)",
                returncode=-1,
                stdout="",
                stderr=f"could not read a package declaration from {policy_path}",
                elapsed_ms=0.0,
                success=False,
                errors=[f"no package declaration in {policy_path}"],
            )

        args = ["eval", "--format", "json", *self._data_args(policy_path, data_path)]
        input_json = None
        if input_data is not None:
            args.append("-I")  # --stdin-input; `--input -` is a filename in OPA
            input_json = json.dumps(input_data)
        args.append(query)
        return self._execute(args, input_json, timeout)

    def eval_file(
        self,
        policy_path: str,
        input_path: str,
        data_path: str | None = None,
        query: str | None = None,
        timeout: int = 60,
    ) -> OpaResult:
        """Run `opa eval` with input from a file."""
        query = query or decide_query(policy_path)
        if query is None:
            return OpaResult(
                command=f"{self.opa_bin} eval (unparseable policy)",
                returncode=-1,
                stdout="",
                stderr=f"could not read a package declaration from {policy_path}",
                elapsed_ms=0.0,
                success=False,
                errors=[f"no package declaration in {policy_path}"],
            )
        args = [
            "eval",
            "--format",
            "json",
            "--input",
            input_path,
            *self._data_args(policy_path, data_path),
            query,
        ]
        return self._execute(args, None, timeout)

    def test_policy(
        self,
        policy_dir: str,
        timeout: int = 60,
    ) -> OpaResult:
        """Run `opa test` on a policy directory."""
        return self._execute(["test", policy_dir, "--format", "json"], None, timeout)

    def _bench(
        self,
        policy_path: str,
        input_data: dict | None,
        iterations: int,
        data_path: str | None,
        query: str | None,
        timeout: int,
    ) -> OpaResult:
        query = query or decide_query(policy_path)
        if query is None:
            return OpaResult(
                command=f"{self.opa_bin} eval --bench (unparseable policy)",
                returncode=-1,
                stdout="",
                stderr=f"could not read a package declaration from {policy_path}",
                elapsed_ms=0.0,
                success=False,
                errors=[f"no package declaration in {policy_path}"],
            )
        # OPA 1.x has no `--bench`; the flag is `--metrics` (query metrics), and
        # `--count N` repeats the evaluation N times so the aggregation is
        # meaningful. `--bench` used to fail with "unknown flag", which the old
        # wrapper reported as success because it never inspected the body.
        args = [
            "eval",
            "--metrics",
            "--format",
            "json",
            "--count",
            str(iterations),
            *self._data_args(policy_path, data_path),
        ]
        input_json = None
        if input_data is not None:
            args.append("-I")
            input_json = json.dumps(input_data)
        args.append(query)
        return self._execute(args, input_json, timeout)

    def bench(
        self,
        policy_path: str,
        input_data: dict | None = None,
        iterations: int = 100,
        data_path: str | None = None,
        query: str | None = None,
        timeout: int = 120,
    ) -> OpaResult:
        """Run `opa eval --bench --count N` for a policy."""
        return self._bench(policy_path, input_data, iterations, data_path, query, timeout)

    def bench_ns_per_op(self, result: OpaResult) -> float | None:
        """Median `timer_rego_query_eval_ns` reported by --metrics, or None.

        This is the number that is comparable between machines: OPA's own
        in-process measurement of the query with file loading, module parsing
        and process startup excluded, unlike the wall clock of the CLI.
        """
        parsed = result.parsed_output or {}
        aggregated = parsed.get("aggregated_metrics") or {}
        stats = aggregated.get("timer_rego_query_eval_ns")
        if isinstance(stats, dict) and "median" in stats:
            return float(stats["median"])
        return None


def load_rego_policies(policy_dir: str) -> dict[str, str]:
    """Load all .rego files from a directory."""
    policies = {}
    policy_path = Path(policy_dir)
    for rego_file in sorted(policy_path.glob("*.rego")):
        policies[rego_file.stem] = rego_file.read_text()
    return policies


def write_policy_set(policy_dir: str, destination: str) -> str:
    """Copy the .rego files (only) from policy_dir into destination.

    Used when a test needs a policy directory that does not also contain
    testdata/*.json, which OPA cannot merge into a single data tree.
    """
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    for rego in Path(policy_dir).glob("*.rego"):
        (dest / rego.name).write_text(rego.read_text())
    return str(dest)


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
