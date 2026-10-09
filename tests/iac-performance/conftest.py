"""
Pytest configuration for IaC performance tests.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "terraform: marks tests that use terraform CLI"
    )
    config.addinivalue_line(
        "markers", "opa: marks tests that use OPA/Rego evaluation"
    )
    config.addinivalue_line(
        "markers", "checkov: marks tests that use Checkov scanning"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests that are slow (>30s)"
    )
    config.addinivalue_line(
        "markers", "benchmark: marks tests that run benchmarks"
    )
