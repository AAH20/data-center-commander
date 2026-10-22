"""Shared test configuration.

The API enforces API-key authentication by default. The existing suite predates
authentication and exercises route logic, not auth, so it runs with anonymity
explicitly enabled -- the same opt-out a developer uses locally.

tests/unit/test_auth_api.py overrides this to run with enforcement ON, so the
authenticated path is tested rather than assumed.
"""

import os

# Must be set before dcc.api_async is imported by any test module.
os.environ.setdefault("DCC_ALLOW_ANONYMOUS", "1")
