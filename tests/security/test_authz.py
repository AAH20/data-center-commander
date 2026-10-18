"""Tests for dcc.security.authz — RBAC, ABAC, and tenant-scoped permissions."""
from __future__ import annotations

import pytest
from uuid import uuid4

from dcc.security.authz import (
    AccessDecision,
    AuthorizationContext,
    Authorizer,
    Effect,
    Permission,
    Policy,
    PolicyDecision,
    Role,
    TenantMismatchError,
    UnauthorizedError,
    create_default_authorizer,
    create_default_policies,
    create_default_roles,
)
from dcc.security.tenant import clear_tenant, set_tenant


# ---------------------------------------------------------------------------
# Permission
# ---------------------------------------------------------------------------


class TestPermission:
    def test_exact_match(self):
        p = Permission("read", "assets")
        assert p.matches("read", "assets") is True

    def test_wildcard_action(self):
        p = Permission("*", "assets")
        assert p.matches("read", "assets") is True
        assert p.matches("write", "assets") is True

    def test_wildcard_resource(self):
        p = Permission("read", "*")
        assert p.matches("read", "assets") is True
        assert p.matches("read", "workloads") is True

    def test_wildcard_both(self):
        p = Permission("*", "*")
        assert p.matches("anything", "anything") is True

    def test_no_match_wrong_action(self):
        p = Permission("read", "assets")
        assert p.matches("write", "assets") is False

    def test_no_match_wrong_resource(self):
        p = Permission("read", "assets")
        assert p.matches("read", "workloads") is False

    def test_glob_pattern(self):
        p = Permission("read", "assets:*")
        assert p.matches("read", "assets:server-1") is True
        assert p.matches("read", "workloads:server-1") is False

    def test_empty_action_raises(self):
        with pytest.raises(ValueError):
            Permission("", "assets")

    def test_empty_resource_raises(self):
        with pytest.raises(ValueError):
            Permission("read", "")

    def test_frozen(self):
        p = Permission("read", "assets")
        with pytest.raises(AttributeError):
            p.action = "write"


# ---------------------------------------------------------------------------
# Role
# ---------------------------------------------------------------------------


class TestRole:
    def test_basic_role(self):
        r = Role("viewer", permissions=[Permission("read", "*")])
        assert r.name == "viewer"
        assert len(r.permissions) == 1

    def test_role_with_parent(self):
        parent = Role("viewer", permissions=[Permission("read", "*")])
        child = Role("operator", permissions=[Permission("write", "assets")], parent="viewer")
        roles = {"viewer": parent, "operator": child}
        all_perms = child.all_permissions(roles)
        assert len(all_perms) == 2

    def test_role_hierarchy_three_levels(self):
        grandparent = Role("viewer", permissions=[Permission("read", "*")])
        parent = Role("operator", permissions=[Permission("write", "assets")], parent="viewer")
        child = Role("admin", permissions=[Permission("delete", "*")], parent="operator")
        roles = {"viewer": grandparent, "operator": parent, "admin": child}
        all_perms = child.all_permissions(roles)
        assert len(all_perms) == 3

    def test_unknown_parent_raises(self):
        child = Role("orphan", parent="nonexistent")
        with pytest.raises(ValueError):
            child.all_permissions({})

    def test_cycle_detection(self):
        a = Role("a", parent="b")
        b = Role("b", parent="a")
        roles = {"a": a, "b": b}
        with pytest.raises(ValueError, match="cycle"):
            a.all_permissions(roles)

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            Role("")

    def test_frozen(self):
        r = Role("viewer")
        with pytest.raises(AttributeError):
            r.name = "other"


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class TestPolicy:
    def test_always_allow(self):
        p = Policy(name="allow-all", effect=Effect.ALLOW, actions={"*"}, resources={"*"})
        ctx = AuthorizationContext(action="read", resource={"type": "assets"})
        decision = p.evaluate(ctx)
        assert decision.matched is True
        assert decision.effect == Effect.ALLOW

    def test_always_deny(self):
        p = Policy(name="deny-all", effect=Effect.DENY, actions={"*"}, resources={"*"})
        ctx = AuthorizationContext(action="read", resource={"type": "assets"})
        decision = p.evaluate(ctx)
        assert decision.matched is True
        assert decision.effect == Effect.DENY

    def test_action_filter(self):
        p = Policy(name="no-write", effect=Effect.DENY, actions={"write"}, resources={"*"})
        ctx = AuthorizationContext(action="read", resource={"type": "assets"})
        assert p.evaluate(ctx).matched is False
        ctx2 = AuthorizationContext(action="write", resource={"type": "assets"})
        assert p.evaluate(ctx2).matched is True

    def test_resource_filter(self):
        p = Policy(name="no-assets", effect=Effect.DENY, actions={"*"}, resources={"assets"})
        ctx = AuthorizationContext(action="read", resource={"type": "workloads"})
        assert p.evaluate(ctx).matched is False
        ctx2 = AuthorizationContext(action="read", resource={"type": "assets"})
        assert p.evaluate(ctx2).matched is True

    def test_condition_false(self):
        p = Policy(
            name="cond",
            effect=Effect.ALLOW,
            actions={"*"},
            resources={"*"},
            condition=lambda ctx: False,
        )
        ctx = AuthorizationContext(action="read", resource={"type": "assets"})
        assert p.evaluate(ctx).matched is False

    def test_condition_true(self):
        p = Policy(
            name="cond",
            effect=Effect.ALLOW,
            actions={"*"},
            resources={"*"},
            condition=lambda ctx: True,
        )
        ctx = AuthorizationContext(action="read", resource={"type": "assets"})
        assert p.evaluate(ctx).matched is True

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            Policy(name="", effect=Effect.ALLOW)


# ---------------------------------------------------------------------------
# Authorizer — RBAC
# ---------------------------------------------------------------------------


class TestAuthorizerRBAC:
    def setup_method(self):
        self.authz = Authorizer(
            roles=[
                Role("viewer", permissions=[Permission("read", "*")]),
                Role("operator", permissions=[Permission("write", "assets")], parent="viewer"),
            ]
        )
        self.tenant_id = str(uuid4())

    def test_viewer_can_read(self):
        assert self.authz.can(["viewer"], "read", "assets", tenant_id=self.tenant_id) is True

    def test_viewer_cannot_write(self):
        assert self.authz.can(["viewer"], "write", "assets", tenant_id=self.tenant_id) is False

    def test_operator_inherits_read(self):
        assert self.authz.can(["operator"], "read", "assets", tenant_id=self.tenant_id) is True

    def test_operator_can_write_assets(self):
        assert self.authz.can(["operator"], "write", "assets", tenant_id=self.tenant_id) is True

    def test_operator_cannot_delete(self):
        assert self.authz.can(["operator"], "delete", "assets", tenant_id=self.tenant_id) is False

    def test_multiple_roles(self):
        assert self.authz.can(["viewer", "operator"], "write", "assets", tenant_id=self.tenant_id) is True

    def test_unknown_role_denied(self):
        assert self.authz.can(["nonexistent"], "read", "assets", tenant_id=self.tenant_id) is False

    def test_no_roles_denied(self):
        assert self.authz.can([], "read", "assets", tenant_id=self.tenant_id) is False

    def test_authorize_raises_on_deny(self):
        with pytest.raises(UnauthorizedError):
            self.authz.authorize(["viewer"], "write", "assets", tenant_id=self.tenant_id)

    def test_authorize_passes_on_allow(self):
        # Should not raise
        self.authz.authorize(["viewer"], "read", "assets", tenant_id=self.tenant_id)


# ---------------------------------------------------------------------------
# Authorizer — ABAC
# ---------------------------------------------------------------------------


class TestAuthorizerABAC:
    def setup_method(self):
        self.tenant_id = str(uuid4())
        self.authz = Authorizer(
            roles=[Role("viewer", permissions=[Permission("read", "*")])],
            policies=[
                Policy(
                    name="deny-write-outside-hours",
                    effect=Effect.DENY,
                    actions={"write", "delete"},
                    resources={"*"},
                    condition=lambda ctx: not ctx.environment.get("business_hours", True),
                ),
                Policy(
                    name="allow-owner",
                    effect=Effect.ALLOW,
                    actions={"*"},
                    resources={"*"},
                    condition=lambda ctx: ctx.resource.get("owner") == ctx.subject.get("id"),
                ),
            ],
        )

    def test_deny_policy_blocks_write(self):
        result = self.authz.can(
            ["viewer"], "write", "assets",
            tenant_id=self.tenant_id,
            environment={"business_hours": False},
        )
        assert result is False

    def test_deny_policy_allows_during_business_hours(self):
        result = self.authz.can(
            ["viewer"], "write", "assets",
            tenant_id=self.tenant_id,
            subject={"id": "user-1"},
            environment={"business_hours": True},
        )
        # viewer role doesn't have write permission, so still denied by RBAC
        assert result is False

    def test_allow_policy_grants_access(self):
        # The allow-owner policy should grant access even though viewer can't write
        # Use business_hours=True so the deny policy doesn't match
        result = self.authz.can(
            ["viewer"], "write", {"type": "assets", "owner": "user-1"},
            tenant_id=self.tenant_id,
            subject={"id": "user-1"},
            environment={"business_hours": True},
        )
        assert result is True

    def test_deny_wins_over_allow(self):
        # Even if owner policy matches, deny policy should win
        authz = Authorizer(
            roles=[],
            policies=[
                Policy(
                    name="deny-all-write",
                    effect=Effect.DENY,
                    actions={"write"},
                    resources={"*"},
                ),
                Policy(
                    name="allow-owner",
                    effect=Effect.ALLOW,
                    actions={"*"},
                    resources={"*"},
                    condition=lambda ctx: True,
                ),
            ],
        )
        result = authz.can(
            [], "write", {"type": "assets", "owner": "user-1"},
            tenant_id=self.tenant_id,
            subject={"id": "user-1"},
        )
        assert result is False


# ---------------------------------------------------------------------------
# Authorizer — Tenant scoping
# ---------------------------------------------------------------------------


class TestAuthorizerTenantScoping:
    def setup_method(self):
        self.authz = Authorizer(
            roles=[Role("admin", permissions=[Permission("*", "*")])],
        )
        self.tenant_a = str(uuid4())
        self.tenant_b = str(uuid4())

    def test_same_tenant_allowed(self):
        result = self.authz.can(
            ["admin"], "read", {"type": "assets", "tenant_id": self.tenant_a},
            tenant_id=self.tenant_a,
        )
        assert result is True

    def test_cross_tenant_denied(self):
        result = self.authz.can(
            ["admin"], "read", {"type": "assets", "tenant_id": self.tenant_b},
            tenant_id=self.tenant_a,
        )
        assert result is False

    def test_cross_tenant_write_denied(self):
        result = self.authz.can(
            ["admin"], "write", {"type": "assets", "tenant_id": self.tenant_b},
            tenant_id=self.tenant_a,
        )
        assert result is False

    def test_no_tenant_context_denied(self):
        result = self.authz.can(
            ["admin"], "read", {"type": "assets", "tenant_id": self.tenant_a},
            tenant_id=None,
        )
        assert result is False

    def test_skip_tenant_check(self):
        result = self.authz.can(
            ["admin"], "read", {"type": "assets", "tenant_id": self.tenant_b},
            tenant_id=self.tenant_a,
            skip_tenant_check=True,
        )
        assert result is True

    def test_authorize_cross_tenant_raises_tenant_mismatch(self):
        with pytest.raises(TenantMismatchError):
            self.authz.authorize(
                ["admin"], "read", {"type": "assets", "tenant_id": self.tenant_b},
                tenant_id=self.tenant_a,
            )

    def test_resource_without_tenant_id_read_allowed(self):
        result = self.authz.can(
            ["admin"], "read", {"type": "assets"},
            tenant_id=self.tenant_a,
        )
        assert result is True

    def test_resource_without_tenant_id_write_allowed(self):
        # Resources without tenant_id are treated as global/type-level.
        # With a valid tenant context, access is allowed.
        result = self.authz.can(
            ["admin"], "write", {"type": "assets"},
            tenant_id=self.tenant_a,
        )
        assert result is True


# ---------------------------------------------------------------------------
# Authorizer — Tenant context integration
# ---------------------------------------------------------------------------


class TestAuthorizerTenantContext:
    def setup_method(self):
        self.authz = Authorizer(
            roles=[Role("viewer", permissions=[Permission("read", "*")])],
        )
        self.tenant_id = str(uuid4())

    def teardown_method(self):
        clear_tenant()

    def test_uses_active_tenant_context(self):
        set_tenant(self.tenant_id)
        result = self.authz.can(
            ["viewer"], "read", {"type": "assets", "tenant_id": self.tenant_id},
        )
        assert result is True

    def test_cross_tenant_with_context(self):
        other_tenant = str(uuid4())
        set_tenant(self.tenant_id)
        result = self.authz.can(
            ["viewer"], "read", {"type": "assets", "tenant_id": other_tenant},
        )
        assert result is False


# ---------------------------------------------------------------------------
# Default roles and policies
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_create_default_roles(self):
        roles = create_default_roles()
        assert len(roles) == 4
        names = {r.name for r in roles}
        assert names == {"viewer", "operator", "admin", "superadmin"}

    def test_create_default_policies(self):
        policies = create_default_policies()
        assert len(policies) >= 3

    def test_create_default_authorizer(self):
        authz = create_default_authorizer()
        assert len(authz.roles) == 4
        assert len(authz.policies) >= 3

    def test_default_authorizer_superadmin_can_do_anything(self):
        authz = create_default_authorizer()
        tid = str(uuid4())
        assert authz.can(["superadmin"], "delete", "anything", tenant_id=tid) is True

    def test_default_authorizer_viewer_read_only(self):
        authz = create_default_authorizer()
        tid = str(uuid4())
        assert authz.can(["viewer"], "read", "assets", tenant_id=tid) is True
        assert authz.can(["viewer"], "write", "assets", tenant_id=tid) is False

    def test_default_authorizer_business_hours_policy(self):
        authz = create_default_authorizer()
        tid = str(uuid4())
        # operator has write on assets, but outside business hours should be denied
        result = authz.can(
            ["operator"], "write", "assets",
            tenant_id=tid,
            environment={"business_hours": False},
        )
        assert result is False

    def test_default_authorizer_mfa_policy(self):
        authz = create_default_authorizer()
        tid = str(uuid4())
        # admin has write on everything, but critical resources need MFA
        result = authz.can(
            ["admin"], "write", {"type": "assets", "criticality": "critical"},
            tenant_id=tid,
            environment={"mfa_verified": False},
        )
        assert result is False

    def test_default_authorizer_mfa_verified(self):
        authz = create_default_authorizer()
        tid = str(uuid4())
        result = authz.can(
            ["admin"], "write", {"type": "assets", "criticality": "critical"},
            tenant_id=tid,
            environment={"mfa_verified": True},
        )
        assert result is True


# ---------------------------------------------------------------------------
# Authorizer — Registration
# ---------------------------------------------------------------------------


class TestAuthorizerRegistration:
    def test_add_and_remove_role(self):
        authz = Authorizer()
        authz.add_role(Role("test", permissions=[Permission("read", "*")]))
        assert "test" in authz.roles
        authz.remove_role("test")
        assert "test" not in authz.roles

    def test_add_and_remove_policy(self):
        authz = Authorizer()
        authz.add_policy(Policy(name="test", effect=Effect.ALLOW, actions={"*"}, resources={"*"}))
        assert "test" in authz.policies
        authz.remove_policy("test")
        assert "test" not in authz.policies

    def test_remove_nonexistent_role_raises(self):
        authz = Authorizer()
        with pytest.raises(KeyError):
            authz.remove_role("nonexistent")

    def test_remove_nonexistent_policy_raises(self):
        authz = Authorizer()
        with pytest.raises(KeyError):
            authz.remove_policy("nonexistent")

    def test_replace_existing_role(self):
        authz = Authorizer()
        authz.add_role(Role("test", permissions=[Permission("read", "*")]))
        authz.add_role(Role("test", permissions=[Permission("write", "*")]))
        assert len(authz.roles["test"].permissions) == 1
        perms = list(authz.roles["test"].permissions)
        assert perms[0].action == "write"


# ---------------------------------------------------------------------------
# Authorizer — Default deny behavior
# ---------------------------------------------------------------------------


class TestDefaultDeny:
    def test_default_deny_true(self):
        authz = Authorizer(default_deny=True)
        assert authz.can(["anyone"], "read", "anything", tenant_id=str(uuid4())) is False

    def test_default_deny_false(self):
        authz = Authorizer(default_deny=False)
        assert authz.can(["anyone"], "read", "anything", tenant_id=str(uuid4())) is True


# ---------------------------------------------------------------------------
# AuthorizationContext
# ---------------------------------------------------------------------------


class TestAuthorizationContext:
    def test_auto_tenant_from_context(self):
        tid = str(uuid4())
        set_tenant(tid)
        ctx = AuthorizationContext(action="read", resource={"type": "assets"})
        assert ctx.tenant_id == tid
        clear_tenant()

    def test_explicit_tenant_overrides_context(self):
        tid = str(uuid4())
        set_tenant(str(uuid4()))
        ctx = AuthorizationContext(action="read", resource={"type": "assets"}, tenant_id=tid)
        assert ctx.tenant_id == tid
        clear_tenant()


# ---------------------------------------------------------------------------
# AccessDecision
# ---------------------------------------------------------------------------


class TestAccessDecision:
    def test_create(self):
        d = AccessDecision(allowed=True, reason="ok")
        assert d.allowed is True
        assert d.reason == "ok"

    def test_frozen(self):
        d = AccessDecision(allowed=True)
        with pytest.raises(AttributeError):
            d.allowed = False
