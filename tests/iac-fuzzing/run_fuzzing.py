#!/usr/bin/env python3
"""
IaC Fuzzing Runner.

Runs all fuzzing tests with various configurations.

Usage:
    python run_fuzzing.py              # Run all tests with default settings
    python run_fuzzing.py --ci         # Run with CI profile (fewer examples)
    python run_fuzzing.py --dev        # Run with dev profile (minimal examples)
    python run_fuzzing.py --atheris    # Run atheris fuzzer
    python run_fuzzing.py --coverage   # Run with coverage
"""

import argparse
import os
import subprocess
import sys


def run_pytest(profile: str, coverage: bool = False, verbose: bool = False):
    """Run pytest with the specified profile."""
    cmd = [sys.executable, "-m", "pytest"]

    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend(["--cov=.", "--cov-report=term-missing", "--cov-report=html"])

    cmd.extend(
        [
            "-m",
            "fuzzing",
            "--hypothesis-profile",
            profile,
            "tests/iac-fuzzing/",
        ]
    )

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


def run_atheris_fuzzer(target: str, runs: int):
    """Run atheris fuzzer."""
    cmd = [
        sys.executable,
        "-m",
        "atheris",
        "tests/iac-fuzzing/fuzz_atheris.py",
        f"-atheris_runs={runs}",
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="IaC Fuzzing Runner")
    parser.add_argument("--ci", action="store_true", help="Run with CI profile")
    parser.add_argument("--dev", action="store_true", help="Run with dev profile")
    parser.add_argument("--atheris", action="store_true", help="Run atheris fuzzer")
    parser.add_argument("--coverage", action="store_true", help="Run with coverage")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--runs", type=int, default=10000, help="Number of atheris runs")

    args = parser.parse_args()

    # Change to project root
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))

    if args.atheris:
        return run_atheris_fuzzer("fuzz_atheris", args.runs)

    profile = "fuzzing"
    if args.ci:
        profile = "ci"
    elif args.dev:
        profile = "dev"

    return run_pytest(profile, args.coverage, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
