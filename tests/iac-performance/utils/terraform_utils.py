"""
Terraform command utilities for performance testing.

Wraps terraform CLI commands with timing and error handling.

Provider choice is the load-bearing decision in this module. A configuration
made of `aws_*` resources costs a 200-600 MB provider download on the first
`terraform init` in a workspace and then needs real AWS credentials for
`plan`/`apply`/`refresh`, because the provider calls STS and EC2 IMDS before it
will produce a plan. Measured on this machine, one `init` against
registry.terraform.io/hashicorp/aws took 277 s (network bound) and every
`plan` then died with "failed to refresh cached credentials, no EC2 IMDS role
found" after a 15 s IMDS timeout. Neither the download nor the credentials
exist in CI, so those tests could not pass there at all.

The default provider here is therefore the *built-in* Terraform provider
(`terraform.io/builtin/terraform`, resource `terraform_data`). It ships inside
the terraform binary: no registry access, no credentials, no cloud API. Init
takes ~23 ms, and `apply` writes local state, so drift (state vs config),
refresh-over-state and state listing are all measurable offline and for real.
`provider="aws"` is still available and still generates genuine `aws_instance`
resources for anyone who has credentials; see docs/iac-performance.md for what
that path does and does not measure.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

# Terraform reads these from the environment of every invocation.
#   TF_IN_AUTOMATION     stop printing the "run terraform init" advisories
#   CHECKPOINT_DISABLE   no update-check call to checkpoint-api.hashicorp.com
#   TF_INPUT=0           never prompt (a prompt in CI is a hang, not a failure)
#   TF_PLUGIN_CACHE_DIR  share downloaded providers between workspaces, so a
#                        cloud-provider config pays the download once per
#                        machine instead of once per test


def terraform_env() -> dict[str, str]:
    """Environment for terraform subprocesses: deterministic and offline-safe."""
    env = dict(os.environ)
    env["TF_IN_AUTOMATION"] = "1"
    env["CHECKPOINT_DISABLE"] = "1"
    env["TF_INPUT"] = "0"
    cache = env.get("TF_PLUGIN_CACHE_DIR") or str(Path.home() / ".terraform.d" / "plugin-cache")
    try:
        Path(cache).mkdir(parents=True, exist_ok=True)
        env["TF_PLUGIN_CACHE_DIR"] = cache
    except OSError:
        # A read-only HOME must not break the offline path, which downloads nothing.
        env.pop("TF_PLUGIN_CACHE_DIR", None)
    return env


@dataclass
class TerraformResult:
    """Result of a terraform command execution."""

    command: str
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: float
    success: bool
    parsed_output: dict | None = None
    # Only meaningful for `plan -detailed-exitcode`, where 2 means "the plan is
    # non-empty", i.e. drift or pending changes. It is a result, not an error.
    changes_present: bool = False

    @property
    def combined_output(self) -> str:
        return f"{self.stdout}\n{self.stderr}"


@dataclass
class TerraformConfig:
    """Represents a Terraform configuration for testing."""

    name: str
    main_tf: str
    variables_tf: str | None = None
    outputs_tf: str | None = None
    terraform_tfvars: str | None = None
    backend_tf: str | None = None
    modules: dict[str, str] = field(default_factory=dict)


class TerraformRunner:
    """Runs terraform commands with timing and result capture."""

    def __init__(self, working_dir: str, terraform_bin: str = "terraform"):
        self.working_dir = Path(working_dir)
        self.terraform_bin = terraform_bin
        self.env = terraform_env()
        self._check_terraform()

    def _check_terraform(self):
        """Verify terraform binary is available."""
        try:
            result = subprocess.run(
                [self.terraform_bin, "version"],
                capture_output=True,
                text=True,
                timeout=10,
                env=self.env,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Terraform not available: {result.stderr}")
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Terraform binary not found: {self.terraform_bin}. "
                "Install terraform or set TERRAFORM_BIN env var."
            ) from e

    def _run(self, args: list[str], timeout: int = 300, ok_codes: tuple[int, ...] = (0,)):
        """Execute a terraform command with timing."""
        cmd = [self.terraform_bin] + args
        cmd_str = " ".join(cmd)

        start = time.perf_counter()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.working_dir),
                timeout=timeout,
                env=self.env,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            parsed = None
            if "-json" in args:
                try:
                    parsed = json.loads(result.stdout)
                except json.JSONDecodeError:
                    parsed = None

            return TerraformResult(
                command=cmd_str,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                elapsed_ms=elapsed_ms,
                success=result.returncode in ok_codes,
                parsed_output=parsed,
                changes_present=result.returncode == 2 and "-detailed-exitcode" in args,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return TerraformResult(
                command=cmd_str,
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                elapsed_ms=elapsed_ms,
                success=False,
            )

    def init(self, backend: bool = True, timeout: int = 120, upgrade: bool = False) -> TerraformResult:
        """Run terraform init."""
        args = ["init", "-no-color", "-input=false"]
        if not backend:
            args.append("-backend=false")
        if upgrade:
            args.append("-upgrade")
        return self._run(args, timeout=timeout)

    def plan(
        self,
        out_file: str | None = None,
        detailed_exitcode: bool = False,
        refresh_only: bool = False,
        timeout: int = 300,
    ) -> TerraformResult:
        """Run terraform plan.

        With detailed_exitcode, terraform's contract is 0 = no changes,
        1 = error, 2 = changes present. Exit 2 is a successful plan, so both 0
        and 2 are accepted and `changes_present` distinguishes them. Treating 2
        as failure is what made the drift tests unable to report drift.
        """
        args = ["plan", "-no-color", "-input=false"]
        if out_file:
            args.extend(["-out", out_file])
        if detailed_exitcode:
            args.append("-detailed-exitcode")
        if refresh_only:
            args.append("-refresh-only")
        ok = (0, 2) if detailed_exitcode else (0,)
        return self._run(args, timeout=timeout, ok_codes=ok)

    def apply(
        self,
        plan_file: str | None = None,
        auto_approve: bool = True,
        timeout: int = 600,
    ) -> TerraformResult:
        """Run terraform apply."""
        args = ["apply", "-no-color", "-input=false"]
        if auto_approve:
            args.append("-auto-approve")
        if plan_file:
            args.append(plan_file)
        return self._run(args, timeout=timeout)

    def destroy(self, auto_approve: bool = True, timeout: int = 300) -> TerraformResult:
        """Run terraform destroy."""
        args = ["destroy", "-no-color", "-input=false"]
        if auto_approve:
            args.append("-auto-approve")
        return self._run(args, timeout=timeout)

    def validate(self, timeout: int = 60) -> TerraformResult:
        """Run `terraform validate -json`.

        `terraform validate` needs the provider schemas that `init` installs:
        without init it fails with "Missing required provider ... Please run
        terraform init" for any non-builtin provider. Every caller here runs
        `init` first, and `test_validate_rejects_broken_configuration` is the
        negative control that proves this reports `valid: false` rather than
        just exiting nonzero.
        """
        return self._run(["validate", "-no-color", "-json"], timeout=timeout)

    def output(self, timeout: int = 60) -> TerraformResult:
        """Run terraform output -json."""
        return self._run(["output", "-json"], timeout=timeout)

    def show(self, timeout: int = 60) -> TerraformResult:
        """Run terraform show -json."""
        return self._run(["show", "-json"], timeout=timeout)

    def refresh(self, timeout: int = 300) -> TerraformResult:
        """Run terraform refresh (state reconciliation against the provider)."""
        return self._run(["refresh", "-no-color", "-input=false"], timeout=timeout)

    def state_list(self, timeout: int = 60) -> TerraformResult:
        """Run terraform state list."""
        return self._run(["state", "list"], timeout=timeout)

    def fmt(self, check: bool = True, timeout: int = 60) -> TerraformResult:
        """Run terraform fmt; with check=True a nonzero exit means misformatted."""
        args = ["fmt", "-no-color"]
        if check:
            args.append("-check")
        return self._run(args, timeout=timeout, ok_codes=(0,) if check else (0, 3))

    def workspace_new(self, name: str, timeout: int = 30) -> TerraformResult:
        """Create a new terraform workspace."""
        return self._run(["workspace", "new", name], timeout=timeout)

    def workspace_select(self, name: str, timeout: int = 30) -> TerraformResult:
        """Select a terraform workspace."""
        return self._run(["workspace", "select", name], timeout=timeout)


def create_terraform_workspace(
    config: TerraformConfig,
    base_dir: str | None = None,
) -> str:
    """
    Create a temporary terraform workspace from a TerraformConfig.
    Returns the path to the workspace directory.
    """
    if base_dir is None:
        base_dir = tempfile.mkdtemp(prefix="tf_perf_")

    workspace = Path(base_dir) / config.name
    workspace.mkdir(parents=True, exist_ok=True)

    # Write main.tf
    (workspace / "main.tf").write_text(config.main_tf)

    # Write variables.tf
    if config.variables_tf:
        (workspace / "variables.tf").write_text(config.variables_tf)

    # Write outputs.tf
    if config.outputs_tf:
        (workspace / "outputs.tf").write_text(config.outputs_tf)

    # Write terraform.tfvars
    if config.terraform_tfvars:
        (workspace / "terraform.tfvars").write_text(config.terraform_tfvars)

    # Write backend.tf
    if config.backend_tf:
        (workspace / "backend.tf").write_text(config.backend_tf)

    # Write modules
    for module_name, module_content in config.modules.items():
        module_dir = workspace / "modules" / module_name
        module_dir.mkdir(parents=True, exist_ok=True)
        (module_dir / "main.tf").write_text(module_content)

    return str(workspace)


def rewrite_main_tf(workspace: str, config: TerraformConfig) -> None:
    """Replace main.tf in an existing workspace.

    Used by the drift tests: same resources, different desired values, which is
    exactly what "configuration drift" means when the state is unchanged.
    """
    (Path(workspace) / "main.tf").write_text(config.main_tf)


def cleanup_workspace(workspace_path: str):
    """Remove a terraform workspace directory."""
    shutil.rmtree(workspace_path, ignore_errors=True)


@contextmanager
def terraform_workspace(config: TerraformConfig, base_dir: str | None = None):
    """Create a workspace for config, and remove it even when the test fails."""
    workspace = create_terraform_workspace(config, base_dir)
    try:
        yield workspace
    finally:
        cleanup_workspace(workspace)


# Resource generators. "offline" is the built-in provider; the cloud branches
# produce real provider resources that need registry access and credentials.
_OFFLINE = "offline"
_PLANNED_ADD_RE = r"^Plan: (\d+) to add"


def generate_terraform_config(
    resource_count: int = 10,
    provider: str = _OFFLINE,
    include_variables: bool = True,
    include_outputs: bool = True,
    include_modules: bool = False,
    drift: bool = False,
) -> TerraformConfig:
    """
    Generate a Terraform configuration with a specified number of resources.
    Useful for scaling performance tests.

    provider="offline" (default) uses the built-in terraform provider: no
    network, no credentials, real plan/apply/refresh over local state.
    provider in {"aws", "azurerm", "google"} produces cloud resources; those
    need registry access for init and credentials for plan.

    drift=True changes every resource's desired value without changing its
    address, so a plan over existing state reports changes instead of nothing.
    """
    resources = []

    for i in range(resource_count):
        if provider == _OFFLINE:
            marker = f"drifted-{i}" if drift else f"value-{i}"
            resources.append(
                'resource "terraform_data" "node_' + str(i) + '" {\n'
                f'  input = "{marker}"\n'
                "}"
            )
        elif provider == "aws":
            marker = "drifted" if drift else "test"
            resources.append(
                'resource "aws_instance" "server_' + str(i) + '" {\n'
                '  ami           = "ami-12345678"\n'
                '  instance_type = "t3.micro"\n'
                "  tags = {\n"
                '    Name        = "server-' + str(i) + '"\n'
                f'    Environment = "{marker}"\n'
                '    Project     = "perf-test"\n'
                "  }\n"
                "}"
            )
        elif provider == "azurerm":
            resources.append(
                'resource "azurerm_resource_group" "rg_' + str(i) + '" {\n'
                '  name     = "rg-' + str(i) + '"\n'
                '  location = "East US"\n'
                "  tags = {\n"
                '    Environment = "test"\n'
                '    Project     = "perf-test"\n'
                "  }\n"
                "}"
            )
        elif provider == "google":
            resources.append(
                'resource "google_compute_instance" "vm_' + str(i) + '" {\n'
                '  name         = "vm-' + str(i) + '"\n'
                '  machine_type = "e2-micro"\n'
                '  zone         = "us-central1-a"\n'
                "\n"
                "  boot_disk {\n"
                "    initialize_params {\n"
                '      image = "debian-cloud/debian-11"\n'
                "    }\n"
                "  }\n"
                "\n"
                "  network_interface {\n"
                '    network = "default"\n'
                "  }\n"
                "}"
            )
        else:
            raise ValueError(f"unknown provider: {provider}")

    main_tf = "\n".join(resources)

    if include_variables:
        variables_tf = """
variable "region" {
  description = "Deployment region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "test"
}
"""
    else:
        variables_tf = None

    if include_outputs:
        outputs_tf = """
output "instance_count" {
  value = COUNT_PLACEHOLDER
}
""".replace("COUNT_PLACEHOLDER", str(resource_count))
    else:
        outputs_tf = None

    modules_tf = {}
    if include_modules:
        if provider == _OFFLINE:
            modules_tf["nodes"] = "\n".join(
                'resource "terraform_data" "mod_' + str(i) + '" {\n'
                f'  input = "module-value-{i}"\n'
                "}"
                for i in range(5)
            )
        else:
            modules_tf["vpc"] = """
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  tags = {
    Name = "perf-test-vpc"
  }
}

resource "aws_subnet" "public" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
  tags = {
    Name = "perf-test-subnet"
  }
}
"""

    # The module directories are only meaningful if the root module calls them.
    # The previous generator wrote modules/<name>/main.tf and never emitted a
    # `module` block, so the module was dead weight: a plan over a 10-resource
    # config with include_modules=True still planned exactly 10 resources, and
    # both "with modules" tests were timing a plan that never entered a module.
    for module_name in modules_tf:
        main_tf += f'\n\nmodule "{module_name}" {{\n  source = "./modules/{module_name}"\n}}\n'

    return TerraformConfig(
        name=f"perf_test_{resource_count}" + ("_drift" if drift else ""),
        main_tf=main_tf,
        variables_tf=variables_tf,
        outputs_tf=outputs_tf,
        modules=modules_tf,
    )


def plan_add_count(result: TerraformResult) -> int | None:
    """Parse "Plan: N to add, ..." out of plan output; None when absent.

    This is the structural half of the performance assertions: a plan that
    silently planned nothing is fast and would satisfy any time budget, so the
    count is checked before the clock.
    """
    import re

    match = re.search(_PLANNED_ADD_RE, result.stdout, re.MULTILINE)
    if not match:
        return None
    return int(match.group(1))


def plan_change_count(result: TerraformResult) -> int | None:
    """Parse the "N to change" field of the plan summary; None when absent."""
    import re

    match = re.search(r"^Plan: \d+ to add, (\d+) to change", result.stdout, re.MULTILINE)
    if not match:
        return None
    return int(match.group(1))


def resolve_terraform_bin(bin_name: str = "terraform") -> str | None:
    """Return the terraform executable path, or None when it is not installed."""
    return shutil.which(bin_name)
