"""The deployment's authentication posture, as actually configured.

Single source of truth. Both the served application and the compliance controls read
this, because they disagreed before: the app enforced authentication from
DCC_ALLOW_ANONYMOUS and DCC_API_KEYS, while the SOC 2 access-control check read
DCC_AUTH_ENABLED -- a variable the application never consults. That check reported
"Authentication is enabled" from a default while the API could be accepting anonymous
requests, which is a compliance signal that is worse than no signal.

Compliance here measures CONFIGURATION: is this deployment set up to require
authentication? It is not a claim about observed traffic.
"""

from __future__ import annotations

import os
from typing import Any

_TRUTHY = {"1", "true", "yes", "on"}


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in _TRUTHY


def configured_keys() -> int:
    """Number of tenant:hash entries in DCC_API_KEYS."""
    raw = os.getenv("DCC_API_KEYS", "").strip()
    if not raw:
        return 0
    return len([e for e in raw.split(",") if e.strip()])


def anonymous_allowed() -> bool:
    """True only when anonymity was explicitly requested. "maybe" is not yes."""
    return _truthy("DCC_ALLOW_ANONYMOUS")


def authentication_required() -> bool:
    """The deployment rejects unauthenticated requests."""
    return not anonymous_allowed()


def auth_posture() -> dict[str, Any]:
    """Everything a control needs to judge access configuration."""
    keys = configured_keys()
    required = authentication_required()
    return {
        "authentication_required": required,
        "anonymous_allowed": anonymous_allowed(),
        "configured_keys": keys,
        "require_keys_fatal": _truthy("DCC_REQUIRE_KEYS"),
        # Enforced with nothing to authenticate WITH is a lockout, not a control.
        "keys_available": keys > 0,
        "locked_out": required and keys == 0,
    }
