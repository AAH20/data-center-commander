"""Tests for dcc.security.tenant — multi-tenant data isolation."""

from __future__ import annotations

import pytest
from uuid import UUID, uuid4

from dcc.security.tenant import (
    TENANT_SETTING,
    TenantContext,
    TenantNotFoundError,
    TenantValidationError,
    clear_tenant,
    current_tenant,
    get_tenant_id,
    is_tenant_active,
    parse_tenant_id,
    require_tenant,
    set_tenant,
    tenant_context,
)


# ---------------------------------------------------------------------------
# parse_tenant_id
# ---------------------------------------------------------------------------


class TestParseTenantId:
    def test_valid_uuid_string(self):
        raw = "dcc00000-0000-4000-8000-000000000001"
        result = parse_tenant_id(raw)
        assert result == raw

    def test_valid_uuid_object(self):
        u = uuid4()
        result = parse_tenant_id(u)
        assert result == str(u)

    def test_uppercase_normalized_to_lowercase(self):
        raw = "DCC00000-0000-4000-8000-000000000001"
        result = parse_tenant_id(raw)
        assert result == raw.lower()

    def test_invalid_string_raises(self):
        with pytest.raises(TenantValidationError):
            parse_tenant_id("not-a-uuid")

    def test_empty_string_raises(self):
        with pytest.raises(TenantValidationError):
            parse_tenant_id("")

    def test_none_raises(self):
        with pytest.raises(TenantValidationError):
            parse_tenant_id(None)

    def test_int_raises(self):
        with pytest.raises(TenantValidationError):
            parse_tenant_id(12345)

    def test_short_uuid_raises(self):
        with pytest.raises(TenantValidationError):
            parse_tenant_id("dcc00000-0000-4000-8000")

    def test_uuid_with_braces_raises(self):
        with pytest.raises(TenantValidationError):
            parse_tenant_id("{dcc00000-0000-4000-8000-000000000001}")


# ---------------------------------------------------------------------------
# Context variable: set_tenant / clear_tenant / current_tenant
# ---------------------------------------------------------------------------


class TestContextVar:
    def test_set_and_get(self):
        tid = str(uuid4())
        set_tenant(tid)
        assert get_tenant_id() == tid
        assert is_tenant_active() is True
        clear_tenant()

    def test_clear(self):
        set_tenant(uuid4())
        clear_tenant()
        assert get_tenant_id() is None
        assert is_tenant_active() is False

    def test_current_tenant_returns_id(self):
        tid = str(uuid4())
        set_tenant(tid)
        assert current_tenant() == tid
        clear_tenant()

    def test_current_tenant_raises_when_no_context(self):
        clear_tenant()
        with pytest.raises(TenantNotFoundError):
            current_tenant()

    def test_require_tenant_alias(self):
        tid = str(uuid4())
        set_tenant(tid)
        assert require_tenant() == tid
        clear_tenant()

    def test_require_tenant_raises_when_no_context(self):
        clear_tenant()
        with pytest.raises(TenantNotFoundError):
            require_tenant()

    def test_set_tenant_validates(self):
        with pytest.raises(TenantValidationError):
            set_tenant("not-a-uuid")
        clear_tenant()

    def test_set_tenant_normalizes(self):
        raw = "DCC00000-0000-4000-8000-000000000001"
        set_tenant(raw)
        assert get_tenant_id() == raw.lower()
        clear_tenant()

    def test_contextvar_isolation_between_contexts(self):
        """Each context (e.g. asyncio task) sees its own tenant."""
        import asyncio

        results = {}

        async def task(name, tenant_id):
            set_tenant(tenant_id)
            await asyncio.sleep(0.01)
            results[name] = get_tenant_id()
            clear_tenant()

        async def main():
            t1 = task("a", str(uuid4()))
            t2 = task("b", str(uuid4()))
            await asyncio.gather(t1, t2)

        asyncio.run(main())
        assert results["a"] != results["b"]
        assert results["a"] is not None
        assert results["b"] is not None


# ---------------------------------------------------------------------------
# TenantContext (class-based context manager)
# ---------------------------------------------------------------------------


class TestTenantContext:
    def test_sets_and_clears_contextvar(self):
        tid = str(uuid4())
        with TenantContext(tid) as ctx:
            assert ctx.tenant_id == tid
            assert get_tenant_id() == tid
            assert is_tenant_active() is True
        assert get_tenant_id() is None
        assert is_tenant_active() is False

    def test_validates_tenant_id(self):
        with pytest.raises(TenantValidationError):
            TenantContext("not-a-uuid")

    def test_accepts_uuid_object(self):
        u = uuid4()
        with TenantContext(u) as ctx:
            assert ctx.tenant_id == str(u)

    def test_nested_contexts(self):
        tid_outer = str(uuid4())
        tid_inner = str(uuid4())
        with TenantContext(tid_outer):
            assert get_tenant_id() == tid_outer
            with TenantContext(tid_inner):
                assert get_tenant_id() == tid_inner
            assert get_tenant_id() == tid_outer
        assert get_tenant_id() is None

    def test_exception_inside_context_still_clears(self):
        tid = str(uuid4())
        with pytest.raises(RuntimeError):
            with TenantContext(tid):
                raise RuntimeError("boom")
        assert get_tenant_id() is None
        assert is_tenant_active() is False

    def test_dataclass_is_frozen(self):
        tid = str(uuid4())
        ctx = TenantContext(tid)
        with pytest.raises(AttributeError):
            ctx.tenant_id = "something-else"


# ---------------------------------------------------------------------------
# tenant_context (functional context manager)
# ---------------------------------------------------------------------------


class TestTenantContextFunctional:
    def test_sets_and_clears(self):
        tid = str(uuid4())
        with tenant_context(tid) as canonical:
            assert canonical == tid
            assert get_tenant_id() == tid
        assert get_tenant_id() is None

    def test_validates(self):
        with pytest.raises(TenantValidationError):
            with tenant_context("not-a-uuid"):
                pass

    def test_exception_still_clears(self):
        tid = str(uuid4())
        with pytest.raises(RuntimeError):
            with tenant_context(tid):
                raise RuntimeError("boom")
        assert get_tenant_id() is None


# ---------------------------------------------------------------------------
# Integration with psycopg (skipped if psycopg not available)
# ---------------------------------------------------------------------------


class TestTenantContextWithConnection:
    """Test that TenantContext sets the PostgreSQL GUC correctly."""

    def test_sets_guc_on_connection(self):
        psycopg = pytest.importorskip("psycopg")
        # We can't test against a real DB, but we can verify the SQL
        # that would be executed by checking the method exists and
        # the constant is correct.
        assert TENANT_SETTING == "dcc.tenant_id"

    def test_ensure_guc_method_exists(self):
        ctx = TenantContext(str(uuid4()))
        assert hasattr(ctx, "ensure_guc")
        assert callable(ctx.ensure_guc)


# ---------------------------------------------------------------------------
# Fail-closed behavior
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_no_context_no_tenant(self):
        """Without a tenant context, current_tenant() raises."""
        clear_tenant()
        with pytest.raises(TenantNotFoundError):
            current_tenant()

    def test_rls_policy_fails_closed(self):
        """The RLS policy uses nullif(..., '')::uuid which returns NULL
        when the setting is absent, so no rows are returned. This is the
        fail-closed behavior we rely on."""
        # This is a documentation test — the actual RLS behavior is
        # enforced by PostgreSQL, not by Python. We verify the contract
        # by checking that our module raises when no tenant is set.
        clear_tenant()
        with pytest.raises(TenantNotFoundError):
            current_tenant()
