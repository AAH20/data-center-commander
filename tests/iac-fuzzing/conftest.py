"""Shared fixtures for IaC fuzzing tests."""

import os

import pytest
from hypothesis import Verbosity, settings

# Configure hypothesis for fuzzing
settings.register_profile("fuzzing", max_examples=1000, verbosity=Verbosity.quiet)
settings.register_profile("ci", max_examples=100, verbosity=Verbosity.quiet)
settings.register_profile("dev", max_examples=10, verbosity=Verbosity.normal)

# Profile selection, in priority order:
#   1. HYPOTHESIS_PROFILE, if someone set it explicitly -- this is what lets a developer
#      reproduce the CI example count locally. Without it, "the suite is slow" and "the
#      suite is different in CI" are both unfalsifiable, because the two runs differ only
#      by an environment variable nobody documents.
#   2. CI, which GitHub Actions sets automatically, so the bounded profile is the default
#      there (100 examples, ~1.6 min rather than 1000 examples, ~16 min).
#   3. the full fuzzing profile, for a developer machine with time to spare.
_explicit = os.environ.get("HYPOTHESIS_PROFILE")
if _explicit and _explicit in {"fuzzing", "ci", "dev"}:
    settings.load_profile(_explicit)
else:
    settings.load_profile("ci" if os.environ.get("CI") else "fuzzing")


@pytest.fixture(scope="session")
def fuzzing_profile():
    """Return the current fuzzing profile name."""
    return settings._current_profile
