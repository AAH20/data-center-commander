"""
Pytest configuration for IaC performance tests.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

# The runner fixtures live in fixtures/conftest.py, which pytest does not load for
# this directory (a sibling conftest is not collected). Re-export them here so
# checkov_runner / terraform_runner / opa_runner resolve for every test below.
from fixtures.conftest import (  # noqa: E402,F401
    checkov_bin,
    checkov_policy_dir,
    checkov_runner,
    large_terraform_config,
    medium_terraform_config,
    non_compliant_opa_input,
    opa_bin,
    opa_runner,
    rego_policy_dir,
    sample_opa_input,
    small_terraform_config,
    temp_workspace,
    terraform_bin,
    terraform_runner,
)


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "terraform: marks tests that use terraform CLI")
    config.addinivalue_line("markers", "opa: marks tests that use OPA/Rego evaluation")
    config.addinivalue_line("markers", "checkov: marks tests that use Checkov scanning")
    config.addinivalue_line("markers", "slow: marks tests that are slow (>30s)")
    config.addinivalue_line("markers", "benchmark: marks tests that run benchmarks")
