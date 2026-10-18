"""Shared fixtures for IaC fuzzing tests."""

import os

import pytest
from hypothesis import Verbosity, settings

# Configure hypothesis for fuzzing
settings.register_profile("fuzzing", max_examples=1000, verbosity=Verbosity.quiet)
settings.register_profile("ci", max_examples=100, verbosity=Verbosity.quiet)
settings.register_profile("dev", max_examples=10, verbosity=Verbosity.normal)

# CI runners are slower than a dev machine and the pipeline applies a per-test
# timeout, so keep the example count bounded there.
settings.load_profile("ci" if os.environ.get("CI") else "fuzzing")


@pytest.fixture(scope="session")
def fuzzing_profile():
    """Return the current fuzzing profile name."""
    return settings._current_profile
