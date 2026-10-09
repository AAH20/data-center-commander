"""
Terraform command utilities for performance testing.
Wraps terraform CLI commands with timing and error handling.
"""

import os
import subprocess
import tempfile
import shutil
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class TerraformResult:
    """Result of a terraform command execution."""
    command: str
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: float
    success: bool
    parsed_output: Optional[Dict] = None


@dataclass
class TerraformConfig:
    """Represents a Terraform configuration for testing."""
    name: str
    main_tf: str
    variables_tf: Optional[str] = None
    outputs_tf: Optional[str] = None
    terraform_tfvars: Optional[str] = None
    backend_tf: Optional[str] = None
    modules: Dict[str, str] = field(default_factory=dict)


class TerraformRunner:
    """Runs terraform commands with timing and result capture."""

    def __init__(self, working_dir: str, terraform_bin: str = "terraform"):
        self.working_dir = Path(working_dir)
        self.terraform_bin = terraform_bin
        self._check_terraform()

    def _check_terraform(self):
        """Verify terraform binary is available."""
        try:
            result = subprocess.run(
                [self.terraform_bin, "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Terraform not available: {result.stderr}")
        except FileNotFoundError:
            raise RuntimeError(
                f"Terraform binary not found: {self.terraform_bin}. "
                "Install terraform or set TERRAFORM_BIN env var."
            )

    def _run(self, args: List[str], timeout: int = 300) -> TerraformResult:
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
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            parsed = None
            if "-json" in args:
                try:
                    parsed = json.loads(result.stdout)
                except json.JSONDecodeError:
                    pass

            return TerraformResult(
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
            return TerraformResult(
                command=cmd_str,
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                elapsed_ms=elapsed_ms,
                success=False,
            )

    def init(self, backend: bool = True, timeout: int = 120) -> TerraformResult:
        """Run terraform init."""
        args = ["init", "-no-color"]
        if not backend:
            args.append("-backend=false")
        return self._run(args, timeout=timeout)

    def plan(
        self,
        out_file: Optional[str] = None,
        detailed_exitcode: bool = False,
        timeout: int = 300,
    ) -> TerraformResult:
        """Run terraform plan."""
        args = ["plan", "-no-color", "-input=false"]
        if out_file:
            args.extend(["-out", out_file])
        if detailed_exitcode:
            args.append("-detailed-exitcode")
        return self._run(args, timeout=timeout)

    def apply(
        self,
        plan_file: Optional[str] = None,
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
        """Run terraform validate."""
        return self._run(["validate", "-no-color", "-json"], timeout=timeout)

    def output(self, timeout: int = 60) -> TerraformResult:
        """Run terraform output -json."""
        return self._run(["output", "-json"], timeout=timeout)

    def show(self, timeout: int = 60) -> TerraformResult:
        """Run terraform show -json."""
        return self._run(["show", "-json"], timeout=timeout)

    def refresh(self, timeout: int = 300) -> TerraformResult:
        """Run terraform refresh."""
        return self._run(["refresh", "-no-color", "-input=false"], timeout=timeout)

    def state_list(self, timeout: int = 60) -> TerraformResult:
        """Run terraform state list."""
        return self._run(["state", "list"], timeout=timeout)

    def workspace_new(self, name: str, timeout: int = 30) -> TerraformResult:
        """Create a new terraform workspace."""
        return self._run(["workspace", "new", name], timeout=timeout)

    def workspace_select(self, name: str, timeout: int = 30) -> TerraformResult:
        """Select a terraform workspace."""
        return self._run(["workspace", "select", name], timeout=timeout)


def create_terraform_workspace(
    config: TerraformConfig,
    base_dir: Optional[str] = None,
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


def cleanup_workspace(workspace_path: str):
    """Remove a terraform workspace directory."""
    shutil.rmtree(workspace_path, ignore_errors=True)


def generate_terraform_config(
    resource_count: int = 10,
    provider: str = "aws",
    include_variables: bool = True,
    include_outputs: bool = True,
    include_modules: bool = False,
) -> TerraformConfig:
    """
    Generate a Terraform configuration with a specified number of resources.
    Useful for scaling performance tests.
    """
    resources = []
    variables = []
    outputs = []

    for i in range(resource_count):
        if provider == "aws":
            resources.append(
                'resource "aws_instance" "server_' + str(i) + '" {\n'
                '  ami           = "ami-12345678"\n'
                '  instance_type = "t3.micro"\n'
                '  tags = {\n'
                '    Name        = "server-' + str(i) + '"\n'
                '    Environment = "test"\n'
                '    Project     = "perf-test"\n'
                '  }\n'
                '}'
            )
        elif provider == "azurerm":
            resources.append(
                'resource "azurerm_resource_group" "rg_' + str(i) + '" {\n'
                '  name     = "rg-' + str(i) + '"\n'
                '  location = "East US"\n'
                '  tags = {\n'
                '    Environment = "test"\n'
                '    Project     = "perf-test"\n'
                '  }\n'
                '}'
            )
        elif provider == "google":
            resources.append(
                'resource "google_compute_instance" "vm_' + str(i) + '" {\n'
                '  name         = "vm-' + str(i) + '"\n'
                '  machine_type = "e2-micro"\n'
                '  zone         = "us-central1-a"\n'
                '\n'
                '  boot_disk {\n'
                '    initialize_params {\n'
                '      image = "debian-cloud/debian-11"\n'
                '    }\n'
                '  }\n'
                '\n'
                '  network_interface {\n'
                '    network = "default"\n'
                '  }\n'
                '}'
            )

    main_tf = "\n".join(resources)

    if include_variables:
        variables_tf = '''
variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "test"
}
'''
    else:
        variables_tf = None

    if include_outputs:
        outputs_tf = '''
output "instance_count" {
  value = COUNT_PLACEHOLDER
}
'''.replace("COUNT_PLACEHOLDER", str(resource_count))
    else:
        outputs_tf = None

    modules_tf = {}
    if include_modules:
        modules_tf["vpc"] = '''
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
'''

    return TerraformConfig(
        name=f"perf_test_{resource_count}",
        main_tf=main_tf,
        variables_tf=variables_tf,
        outputs_tf=outputs_tf,
        modules=modules_tf,
    )
