"""Error types for the policy-as-code engine."""
from __future__ import annotations


class PolicyError(Exception):
    """Base class for all policy-related errors."""


class PolicySyntaxError(PolicyError):
    """Raised when a policy document has a syntax error."""


class PolicyValidationError(PolicyError):
    """Raised when a policy fails validation.

    Attributes
    ----------
    errors:
        A list of validation error messages.
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        self.errors = errors or []
        super().__init__(message)


class PolicyEvaluationError(PolicyError):
    """Raised when policy evaluation fails due to an internal error."""


class PolicyNotFoundError(PolicyError):
    """Raised when a referenced policy or bundle does not exist."""


class PolicyConflictError(PolicyError):
    """Raised when there is a conflict between policies."""
