"""
Checkov policy evaluation utilities for performance testing.
Wraps checkov CLI commands with timing and result capture.
"""

import os
import subprocess
import tempfile
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class CheckovResult:
    """Result of a checkov command execution."""
    command: str
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: float
    success: bool
    parsed_output: Optional[Dict] = None
    passed_checks: int = 0
    failed_checks: int = 0
    skipped_checks: int = 0


class CheckovRunner:
    """Runs Checkov scans with timing and result capture."""

    def __init__(self, checkov_bin: str = "checkov"):
        self.checkov_bin = checkov_bin
        self._check_checkov()

    def _check_checkov(self):
        """Verify checkov is available."""
        try:
            result = subprocess.run(
                [self.checkov_bin, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Checkov not available: {result.stderr}")
        except FileNotFoundError:
            raise RuntimeError(
                f"Checkov binary not found: {self.checkov_bin}. "
                "Install checkov or set CHECKOV_BIN env var."
            )

    def _run(self, args: List[str], timeout: int = 300) -> CheckovResult:
        """Execute a checkov command with timing."""
        cmd = [self.checkov_bin] + args
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
            passed = failed = skipped = 0
            try:
                parsed = json.loads(result.stdout)
                if isinstance(parsed, dict):
                    summary = parsed.get("summary", {})
                    passed = summary.get("passed", 0)
                    failed = summary.get("failed", 0)
                    skipped = summary.get("skipped", 0)
            except json.JSONDecodeError:
                pass

            return CheckovResult(
                command=cmd_str,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                elapsed_ms=elapsed_ms,
                success=result.returncode == 0,
                parsed_output=parsed,
                passed_checks=passed,
                failed_checks=failed,
                skipped_checks=skipped,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return CheckovResult(
                command=cmd_str,
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                elapsed_ms=elapsed_ms,
                success=False,
            )

    def scan_directory(
        self,
        directory: str,
        framework: str = "terraform",
        check: Optional[List[str]] = None,
        skip_check: Optional[List[str]] = None,
        output_format: str = "json",
        timeout: int = 300,
    ) -> CheckovResult:
        """Run checkov scan on a directory."""
        args = [
            "-d", directory,
            "--framework", framework,
            "--output", output_format,
            "--no-guide",
        ]
        if check:
            for c in check:
                args.extend(["--check", c])
        if skip_check:
            for sc in skip_check:
                args.extend(["--skip-check", sc])
        return self._run(args, timeout=timeout)

    def scan_file(
        self,
        file_path: str,
        framework: str = "terraform",
        check: Optional[List[str]] = None,
        skip_check: Optional[List[str]] = None,
        output_format: str = "json",
        timeout: int = 120,
    ) -> CheckovResult:
        """Run checkov scan on a single file."""
        args = [
            "-f", file_path,
            "--framework", framework,
            "--output", output_format,
            "--no-guide",
        ]
        if check:
            for c in check:
                args.extend(["--check", c])
        if skip_check:
            for sc in skip_check:
                args.extend(["--skip-check", sc])
        return self._run(args, timeout=timeout)

    def scan_with_custom_policies(
        self,
        directory: str,
        policy_dir: str,
        framework: str = "terraform",
        output_format: str = "json",
        timeout: int = 300,
    ) -> CheckovResult:
        """Run checkov scan with custom policies."""
        args = [
            "-d", directory,
            "--framework", framework,
            "--output", output_format,
            "--no-guide",
            "--external-checks-dir", policy_dir,
        ]
        return self._run(args, timeout=timeout)


def generate_terraform_file(
    resource_count: int = 10,
    provider: str = "aws",
    compliant: bool = True,
) -> str:
    """
    Generate a Terraform file with a specified number of resources.
    If compliant=True, resources will pass most security checks.
    """
    resources = []

    for i in range(resource_count):
        if provider == "aws":
            if compliant:
                resources.append(
                    'resource "aws_instance" "server_' + str(i) + '" {\n'
                    '  ami           = "ami-12345678"\n'
                    '  instance_type = "t3.micro"\n'
                    '\n'
                    '  root_block_device {\n'
                    '    encrypted = true\n'
                    '  }\n'
                    '\n'
                    '  metadata_options {\n'
                    '    http_tokens = "required"\n'
                    '  }\n'
                    '\n'
                    '  monitoring = true\n'
                    '\n'
                    '  tags = {\n'
                    '    Name        = "server-' + str(i) + '"\n'
                    '    Environment = "production"\n'
                    '    Owner       = "test-team"\n'
                    '    Project     = "perf-test"\n'
                    '    CostCenter  = "cc-1234"\n'
                    '  }\n'
                    '}'
                )
            else:
                resources.append(
                    'resource "aws_instance" "server_' + str(i) + '" {\n'
                    '  ami           = "ami-12345678"\n'
                    '  instance_type = "t2.micro"\n'
                    '  monitoring    = false\n'
                    '  tags = {\n'
                    '    Name = "server-' + str(i) + '"\n'
                    '  }\n'
                    '}'
                )
        elif provider == "azurerm":
            if compliant:
                resources.append(
                    'resource "azurerm_resource_group" "rg_' + str(i) + '" {\n'
                    '  name     = "rg-' + str(i) + '"\n'
                    '  location = "East US"\n'
                    '  tags = {\n'
                    '    Environment = "production"\n'
                    '    Owner       = "test-team"\n'
                    '    Project     = "perf-test"\n'
                    '  }\n'
                    '}'
                )
            else:
                resources.append(
                    'resource "azurerm_resource_group" "rg_' + str(i) + '" {\n'
                    '  name     = "rg-' + str(i) + '"\n'
                    '  location = "East US"\n'
                    '}'
                )

    return "\n".join(resources)


def generate_terraform_module(
    module_name: str = "vpc",
    resource_count: int = 5,
) -> str:
    """Generate a Terraform module with multiple resources."""
    resources = []

    for i in range(resource_count):
        resources.append(
            'resource "aws_subnet" "subnet_' + str(i) + '" {\n'
            '  vpc_id     = aws_vpc.main.id\n'
            '  cidr_block = "10.0.' + str(i) + '.0/24"\n'
            '  tags = {\n'
            '    Name        = "subnet-' + str(i) + '"\n'
            '    Environment = "production"\n'
            '    Owner       = "test-team"\n'
            '  }\n'
            '}'
        )

    return (
        'resource "aws_vpc" "main" {\n'
        '  cidr_block = "10.0.0.0/16"\n'
        '  tags = {\n'
        '    Name        = "' + module_name + '"\n'
        '    Environment = "production"\n'
        '    Owner       = "test-team"\n'
        '  }\n'
        '}\n\n' + '\n'.join(resources) + '\n'
    )
