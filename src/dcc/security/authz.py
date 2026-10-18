"""Authorization engine: RBAC, ABAC, and tenant-scoped permissions.

This module provides a layered authorization system for Data Center Commander:

1. **RBAC** — Role-based access control with a role hierarchy. Users are
   assigned roles; roles grant permissions on resources.

2. **ABAC** — Attribute-based access control. Policies evaluate attributes
   of the subject (user), resource, and environment to make decisions.

3. **Tenant scoping** — Every permission check is implicitly scoped to the
   active tenant context. Cross-tenant access is denied by default.

Architecture
------------
- :class:`Permission` — immutable grant of an action on a resource pattern.
- :class:`Role` — named collection of permissions with an optional parent
  role (hierarchy).
- :class:`Policy` — ABAC rule that evaluates a predicate against subject,
  resource, and environment attributes.
- :class:`Authorizer` — the main entry point. Combines RBAC roles and ABAC
  policies, always enforcing tenant isolation.

Usage
-----
.. code-block:: python

    from dcc.security.authz import Authorizer, Role, Permission, Policy

    authz = Authorizer()
    authz.add_role(Role("viewer", permissions=[Permission("read", "assets")]))
    authz.add_role(Role("operator", permissions=[Permission("write", "assets")],
                         parent="viewer"))

    # RBAC check
    assert authz.can("viewer", "read", "assets", tenant_id=tid)

    # ABAC policy
    authz.add_policy(Policy(
        name="business-hours-only",
        effect="deny",
        actions={"write"},
        resources={"assets"},
        condition=lambda ctx: not ctx.environment.get("business_hours", True),
    ))
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Optional, Set

from .tenant import current_tenant, get_tenant_id, parse_tenant_id

__all__ = [
    "AccessDecision",
    "AuthorizationContext",
    "Authorizer",
    "Effect",
    "Permission",
    "Policy",
    "PolicyDecision",
    "Role",
    "TenantMismatchError",
    "UnauthorizedError",
]


@dataclass(frozen=True)
class AccessDecision:
    """The final outcome of an authorization check.

    Attributes
    ----------
    allowed:
        Whether access was granted.
    reason:
        Human-readable explanation of the decision.
    policy_name:
        Name of the policy that produced the decision, if any.
    """

    allowed: bool
    reason: str = ""
    policy_name: str = ""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UnauthorizedError(PermissionError):
    """Raised when an authorization check fails and the caller wants an
    exception instead of a boolean."""


class TenantMismatchError(UnauthorizedError):
    """Raised when a resource belongs to a different tenant than the
    active tenant context."""


# ---------------------------------------------------------------------------
# Core value types
# ---------------------------------------------------------------------------


class Effect(str, Enum):
    """Whether a policy allows or denies access."""

    ALLOW = "allow"
    DENY = "DENY"


@dataclass(frozen=True)
class Permission:
    """A single grant of *action* on *resource*.

    Both *action* and *resource* are glob patterns. ``"*"`` matches
    everything. ``"assets:*"`` matches any action on the ``assets`` resource.

    Parameters
    ----------
    action:
        Glob pattern for the action (e.g. ``"read"``, ``"write"``, ``"*"``).
    resource:
        Glob pattern for the resource (e.g. ``"assets"``, ``"*:read"``).
    """

    action: str
    resource: str

    def __post_init__(self) -> None:
        if not self.action:
            raise ValueError("action must be non-empty")
        if not self.resource:
            raise ValueError("resource must be non-empty")

    def matches(self, action: str, resource: str) -> bool:
        """Return True if this permission covers *action* on *resource*."""
        return fnmatch.fnmatchcase(action, self.action) and fnmatch.fnmatchcase(
            resource, self.resource
        )


@dataclass(frozen=True)
class Role:
    """A named collection of permissions with an optional parent role.

    Permissions are inherited from the parent role. Child roles can add
    additional permissions but cannot revoke parent permissions (there is
    no deny in pure RBAC; use ABAC policies for deny rules).

    Parameters
    ----------
    name:
        Unique role name.
    permissions:
        Permissions granted by this role.
    parent:
        Name of the parent role whose permissions are inherited.
    description:
        Human-readable description.
    """

    name: str
    permissions: frozenset[Permission] = frozenset()
    parent: Optional[str] = None
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("role name must be non-empty")
        # Coerce list/tuple to frozenset
        if not isinstance(self.permissions, frozenset):
            object.__setattr__(self, "permissions", frozenset(self.permissions))

    def all_permissions(self, roles: Mapping[str, Role]) -> frozenset[Permission]:
        """Return all permissions including those inherited from parents.

        Parameters
        ----------
        roles:
            Mapping of all defined roles (needed to walk the hierarchy).
        """
        result = set(self.permissions)
        visited: set[str] = {self.name}
        current = self
        while current.parent is not None:
            if current.parent in visited:
                raise ValueError(
                    f"role hierarchy cycle detected at {current.parent!r}"
                )
            visited.add(current.parent)
            parent = roles.get(current.parent)
            if parent is None:
                raise ValueError(
                    f"role {self.name!r} references unknown parent {current.parent!r}"
                )
            result.update(parent.permissions)
            current = parent
        return frozenset(result)


@dataclass(frozen=True)
class PolicyDecision:
    """The outcome of evaluating a single ABAC policy."""

    effect: Effect
    policy_name: str
    matched: bool


@dataclass
class AuthorizationContext:
    """The full context for an authorization decision.

    Attributes
    ----------
    subject:
        Attributes of the caller (user). Must include ``roles`` (a list of
        role names) and may include ``id``, ``email``, ``department``, etc.
    resource:
        Attributes of the target resource. Must include ``tenant_id`` and
        may include ``owner``, ``classification``, ``criticality``, etc.
    action:
        The action being attempted (e.g. ``"read"``, ``"write"``).
    environment:
        Environmental attributes such as ``time``, ``ip_address``,
        ``business_hours``, ``mfa_verified``, etc.
    tenant_id:
        The tenant ID extracted from the active tenant context. If None,
        the check will fail unless the caller explicitly passes
        ``skip_tenant_check=True`` to :meth:`Authorizer.can`.
    """

    subject: dict[str, Any] = field(default_factory=dict)
    resource: dict[str, Any] = field(default_factory=dict)
    action: str = ""
    environment: dict[str, Any] = field(default_factory=dict)
    tenant_id: Optional[str] = None

    def __post_init__(self) -> None:
        # Auto-populate tenant_id from the active context if not set
        if self.tenant_id is None:
            try:
                self.tenant_id = current_tenant()
            except Exception:
                pass


# Type alias for policy condition functions
ConditionFunc = Callable[[AuthorizationContext], bool]


@dataclass(frozen=True)
class Policy:
    """An ABAC policy rule.

    A policy has an effect (ALLOW or DENY), a set of actions and resources
    it applies to, and a condition that must evaluate to True for the
    policy to match. If the condition is None, the policy always matches
    the given actions/resources.

    Evaluation order: explicit DENY policies are checked first, then ALLOW
    policies. If no policy matches, the default is DENY (fail-closed).

    Parameters
    ----------
    name:
        Unique policy name for auditing.
    effect:
        Whether to allow or deny when the policy matches.
    actions:
        Set of action patterns this policy applies to (glob patterns).
    resources:
        Set of resource patterns this policy applies to (glob patterns).
    condition:
        Optional predicate. Receives the full :class:`AuthorizationContext`
        and must return True for the policy to match.
    description:
        Human-readable description.
    """

    name: str
    effect: Effect
    actions: frozenset[str] = frozenset()
    resources: frozenset[str] = frozenset()
    condition: Optional[ConditionFunc] = None
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("policy name must be non-empty")
        if not isinstance(self.actions, frozenset):
            object.__setattr__(self, "actions", frozenset(self.actions))
        if not isinstance(self.resources, frozenset):
            object.__setattr__(self, "resources", frozenset(self.resources))

    def matches(self, action: str, resource: str) -> bool:
        """Return True if this policy applies to *action* on *resource*."""
        action_match = any(
            fnmatch.fnmatchcase(action, pattern) for pattern in self.actions
        )
        resource_match = any(
            fnmatch.fnmatchcase(resource, pattern) for pattern in self.resources
        )
        return action_match and resource_match

    def evaluate(self, ctx: AuthorizationContext) -> PolicyDecision:
        """Evaluate this policy against the given context."""
        if not self.matches(ctx.action, _resource_name(ctx)):
            return PolicyDecision(effect=self.effect, policy_name=self.name, matched=False)
        if self.condition is not None and not self.condition(ctx):
            return PolicyDecision(effect=self.effect, policy_name=self.name, matched=False)
        return PolicyDecision(effect=self.effect, policy_name=self.name, matched=True)


def _resource_name(ctx: AuthorizationContext) -> str:
    """Extract the resource name from the context.

    Uses ``resource['type']`` if available, otherwise ``resource['name']``,
    falling back to the ``resource`` field on the context if it's a string.
    """
    if isinstance(ctx.resource, str):
        return ctx.resource
    return str(ctx.resource.get("type", ctx.resource.get("name", "")))


# ---------------------------------------------------------------------------
# Authorizer
# ---------------------------------------------------------------------------


class Authorizer:
    """Main authorization engine combining RBAC and ABAC.

    The authorizer maintains a registry of roles and policies. The
    :meth:`can` method evaluates both layers:

    1. **Tenant check** — If the resource has a ``tenant_id`` that differs
       from the active tenant context, access is denied immediately.
    2. **ABAC deny** — Any matching DENY policy denies access.
    3. **ABAC allow** — Any matching ALLOW policy grants access.
    4. **RBAC** — If the subject has a role that grants a matching
       permission, access is granted.
    5. **Default deny** — If nothing matched, access is denied.

    Parameters
    ----------
    roles:
        Initial set of roles to register.
    policies:
        Initial set of policies to register.
    default_deny:
        If True (default), unmatched requests are denied. If False,
        unmatched requests are allowed (useful for testing).
    """

    def __init__(
        self,
        roles: Optional[Iterable[Role]] = None,
        policies: Optional[Iterable[Policy]] = None,
        *,
        default_deny: bool = True,
    ) -> None:
        self._roles: dict[str, Role] = {}
        self._policies: dict[str, Policy] = {}
        self._default_deny = default_deny

        if roles:
            for role in roles:
                self.add_role(role)
        if policies:
            for policy in policies:
                self.add_policy(policy)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def add_role(self, role: Role) -> None:
        """Register a role. Replaces any existing role with the same name."""
        self._roles[role.name] = role

    def remove_role(self, name: str) -> None:
        """Remove a role. Raises KeyError if the role does not exist."""
        del self._roles[name]

    def add_policy(self, policy: Policy) -> None:
        """Register a policy. Replaces any existing policy with the same name."""
        self._policies[policy.name] = policy

    def remove_policy(self, name: str) -> None:
        """Remove a policy. Raises KeyError if the policy does not exist."""
        del self._policies[name]

    @property
    def roles(self) -> Mapping[str, Role]:
        """Return a read-only view of registered roles."""
        return dict(self._roles)

    @property
    def policies(self) -> Mapping[str, Policy]:
        """Return a read-only view of registered policies."""
        return dict(self._policies)

    # ------------------------------------------------------------------
    # Core check
    # ------------------------------------------------------------------

    def can(
        self,
        subject_roles: Iterable[str],
        action: str,
        resource: str | dict[str, Any],
        *,
        subject: Optional[dict[str, Any]] = None,
        environment: Optional[dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        skip_tenant_check: bool = False,
    ) -> bool:
        """Check whether the subject can perform *action* on *resource*.

        Parameters
        ----------
        subject_roles:
            Role names assigned to the subject.
        action:
            The action being attempted.
        resource:
            The target resource. Can be a string (resource name/type) or
            a dict with at least ``type`` or ``name`` and optionally
            ``tenant_id``.
        subject:
            Additional subject attributes (merged with ``subject_roles``
            into the context's ``subject`` dict).
        environment:
            Environmental attributes for ABAC evaluation.
        tenant_id:
            Explicit tenant ID. If None, the active tenant context is used.
        skip_tenant_check:
            If True, skip the tenant isolation check. Useful for
            cross-tenant administrative operations. Use with caution.

        Returns
        -------
        bool
            True if access is granted, False otherwise.
        """
        ctx = self._build_context(
            subject_roles=subject_roles,
            action=action,
            resource=resource,
            subject=subject,
            environment=environment,
            tenant_id=tenant_id,
        )
        return self._evaluate(ctx, skip_tenant_check=skip_tenant_check)

    def authorize(
        self,
        subject_roles: Iterable[str],
        action: str,
        resource: str | dict[str, Any],
        *,
        subject: Optional[dict[str, Any]] = None,
        environment: Optional[dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        skip_tenant_check: bool = False,
    ) -> None:
        """Like :meth:`can` but raises :class:`UnauthorizedError` on denial.

        Raises
        ------
        UnauthorizedError
            If access is denied.
        TenantMismatchError
            If the resource belongs to a different tenant.
        """
        ctx = self._build_context(
            subject_roles=subject_roles,
            action=action,
            resource=resource,
            subject=subject,
            environment=environment,
            tenant_id=tenant_id,
        )
        if not self._evaluate(ctx, skip_tenant_check=skip_tenant_check):
            if (
                not skip_tenant_check
                and ctx.tenant_id is not None
                and isinstance(ctx.resource, dict)
                and ctx.resource.get("tenant_id") is not None
                and str(ctx.resource["tenant_id"]) != ctx.tenant_id
            ):
                raise TenantMismatchError(
                    f"resource tenant {ctx.resource['tenant_id']} does not match "
                    f"active tenant {ctx.tenant_id}"
                )
            raise UnauthorizedError(
                f"access denied: {action} on {_resource_name(ctx)}"
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_context(
        self,
        *,
        subject_roles: Iterable[str],
        action: str,
        resource: str | dict[str, Any],
        subject: Optional[dict[str, Any]],
        environment: Optional[dict[str, Any]],
        tenant_id: Optional[str],
    ) -> AuthorizationContext:
        """Construct an AuthorizationContext from the given parameters."""
        # Resolve tenant
        resolved_tenant = tenant_id
        if resolved_tenant is None:
            resolved_tenant = get_tenant_id()

        # Build subject dict
        subject_attrs: dict[str, Any] = {"roles": list(subject_roles)}
        if subject:
            subject_attrs.update(subject)

        # Build resource dict
        if isinstance(resource, str):
            resource_attrs: dict[str, Any] = {"type": resource}
        else:
            resource_attrs = dict(resource)

        return AuthorizationContext(
            subject=subject_attrs,
            resource=resource_attrs,
            action=action,
            environment=dict(environment or {}),
            tenant_id=resolved_tenant,
        )

    def _evaluate(self, ctx: AuthorizationContext, *, skip_tenant_check: bool) -> bool:
        """Run the full authorization pipeline."""
        # 1. Tenant isolation check
        if not skip_tenant_check and not self._check_tenant(ctx):
            return False

        # 2. ABAC deny (explicit deny always wins)
        for policy in self._policies.values():
            decision = policy.evaluate(ctx)
            if decision.matched and decision.effect == Effect.DENY:
                return False

        # 3. ABAC allow
        for policy in self._policies.values():
            decision = policy.evaluate(ctx)
            if decision.matched and decision.effect == Effect.ALLOW:
                return True

        # 4. RBAC
        if self._check_rbac(ctx):
            return True

        # 5. Default
        return not self._default_deny

    def _check_tenant(self, ctx: AuthorizationContext) -> bool:
        """Verify the resource belongs to the active tenant."""
        if ctx.tenant_id is None:
            # No active tenant context — fail closed
            return False
        resource_tenant = ctx.resource.get("tenant_id")
        if resource_tenant is None:
            # Resource has no tenant_id — it's either a global resource
            # or a type-level resource (e.g. "assets" as a string).
            # Allow access since the caller has a valid tenant context.
            return True
        return str(resource_tenant) == ctx.tenant_id

    def _check_rbac(self, ctx: AuthorizationContext) -> bool:
        """Check if any of the subject's roles grant the required permission."""
        resource_name = _resource_name(ctx)
        roles: list[str] = list(ctx.subject.get("roles", []))

        for role_name in roles:
            role = self._roles.get(role_name)
            if role is None:
                continue
            try:
                all_perms = role.all_permissions(self._roles)
            except ValueError:
                # Broken hierarchy — skip this role
                continue
            for perm in all_perms:
                if perm.matches(ctx.action, resource_name):
                    return True
        return False


# ---------------------------------------------------------------------------
# Convenience: pre-built roles and policies
# ---------------------------------------------------------------------------


def create_default_roles() -> list[Role]:
    """Create a sensible default role hierarchy.

    Returns
    -------
    list[Role]
        A list of roles: viewer, operator, admin, superadmin.
    """
    return [
        Role(
            name="viewer",
            permissions=frozenset({
                Permission("read", "*"),
                Permission("list", "*"),
                Permission("get", "*"),
            }),
            description="Read-only access to all resources",
        ),
        Role(
            name="operator",
            permissions=frozenset({
                Permission("write", "assets"),
                Permission("write", "workloads"),
                Permission("write", "deployments"),
                Permission("execute", "workflows"),
            }),
            parent="viewer",
            description="Can modify operational resources",
        ),
        Role(
            name="admin",
            permissions=frozenset({
                Permission("write", "*"),
                Permission("delete", "*"),
                Permission("execute", "*"),
                Permission("approve", "*"),
            }),
            parent="operator",
            description="Full administrative access",
        ),
        Role(
            name="superadmin",
            permissions=frozenset({
                Permission("*", "*"),
            }),
            parent="admin",
            description="Unrestricted access including tenant management",
        ),
    ]


def create_default_policies() -> list[Policy]:
    """Create sensible default ABAC policies.

    Returns
    -------
    list[Policy]
        Policies for business-hours restriction, MFA requirement, and
        classification-based access.
    """
    return [
        Policy(
            name="deny-write-outside-business-hours",
            effect=Effect.DENY,
            actions=frozenset({"write", "delete", "execute"}),
            resources=frozenset({"*"}),
            condition=lambda ctx: not ctx.environment.get("business_hours", True),
            description="Deny write/delete/execute outside business hours",
        ),
        Policy(
            name="deny-critical-without-mfa",
            effect=Effect.DENY,
            actions=frozenset({"write", "delete"}),
            resources=frozenset({"*"}),
            condition=lambda ctx: (
                ctx.resource.get("criticality") == "critical"
                and not ctx.environment.get("mfa_verified", False)
            ),
            description="Deny write/delete on critical resources without MFA",
        ),
        Policy(
            name="allow-owner-full-access",
            effect=Effect.ALLOW,
            actions=frozenset({"*"}),
            resources=frozenset({"*"}),
            condition=lambda ctx: (
                ctx.resource.get("owner") is not None
                and ctx.resource.get("owner") == ctx.subject.get("id")
            ),
            description="Resource owners have full access to their resources",
        ),
    ]


def create_default_authorizer() -> Authorizer:
    """Create an authorizer pre-populated with default roles and policies."""
    return Authorizer(
        roles=create_default_roles(),
        policies=create_default_policies(),
    )
