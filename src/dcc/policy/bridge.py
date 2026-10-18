"""Integration between the policy engine and the existing authz system.

This module provides a bridge that allows the policy engine to be used
as a drop-in replacement or complement to the existing
:class:`~dcc.security.authz.Authorizer`.
"""
from __future__ import annotations

from typing import Any, Iterable

from .engine import PolicyEngine

__all__ = ["PolicyAuthzBridge"]


class PolicyAuthzBridge:
    """Bridge between the policy engine and the existing authz system.

    This allows the policy engine to be used as a drop-in replacement
    or complement to the existing :class:`~dcc.security.authz.Authorizer`.

    Usage::

        from dcc.policy import PolicyAuthzBridge, create_default_policy_engine

        bridge = PolicyAuthzBridge(create_default_policy_engine())

        # Use like the existing Authorizer
        allowed = bridge.can(
            subject_roles=["viewer"],
            action="read",
            resource={"type": "asset", "tenant_id": tid},
        )
    """

    def __init__(self, engine: PolicyEngine) -> None:
        self._engine = engine

    def can(
        self,
        subject_roles: Iterable[str],
        action: str,
        resource: str | dict[str, Any],
        *,
        subject: dict[str, Any] | None = None,
        environment: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> bool:
        """Check whether the subject can perform the action on the resource.

        This mirrors the interface of :meth:`~dcc.security.authz.Authorizer.can`.
        """
        subject_attrs: dict[str, Any] = {"roles": list(subject_roles)}
        if subject:
            subject_attrs.update(subject)

        if isinstance(resource, str):
            resource_attrs: dict[str, Any] = {"type": resource}
        else:
            resource_attrs = dict(resource)

        input_doc = {
            "subject": subject_attrs,
            "resource": resource_attrs,
            "action": action,
            "environment": dict(environment or {}),
            "tenant_id": tenant_id,
        }

        decision = self._engine.evaluate(input_doc, tenant_id=tenant_id)
        return decision.allowed

    def authorize(
        self,
        subject_roles: Iterable[str],
        action: str,
        resource: str | dict[str, Any],
        *,
        subject: dict[str, Any] | None = None,
        environment: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """Like :meth:`can` but raises on denial.

        Raises
        ------
        PermissionError
            If access is denied.
        """
        if not self.can(
            subject_roles,
            action,
            resource,
            subject=subject,
            environment=environment,
            tenant_id=tenant_id,
        ):
            raise PermissionError(
                f"access denied: {action} on {resource}"
            )
