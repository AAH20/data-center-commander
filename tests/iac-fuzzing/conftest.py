"""Shared fixtures for IaC fuzzing tests."""

import pytest
from hypothesis import settings, Verbosity

# Configure hypothesis for fuzzing
settings.register_profile("fuzzing", max_examples=1000, verbosity=Verbosity.quiet)
settings.register_profile("ci", max_examples=100, verbosity=Verbosity.quiet)
settings.register_profile("dev", max_examples=10, verbosity=Verbosity.normal)

# Load fuzzing profile by default
settings.load_profile("fuzzing")


@pytest.fixture(scope="session")
def fuzzing_profile():
    """Return the current fuzzing profile name."""
    return settings._current_profile
