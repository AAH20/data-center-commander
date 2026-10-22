"""Tests for the psycopg3 compatibility layer.

The queries in dcc.api_async are asyncpg-style; the pool is psycopg3. The adapter is
the only thing standing between the two, so its placeholder translation is tested
directly: a wrong translation binds the wrong value silently, which is worse than an
exception.
"""

from __future__ import annotations

import pytest

from dcc.pgcompat import translate, PgConnection, PgPool


class TestPlaceholderTranslation:
    def test_single_placeholder(self):
        sql, params = translate("SELECT set_config('dcc.tenant_id', $1, true)", ("t",))
        assert sql == "SELECT set_config('dcc.tenant_id', %s, true)"
        assert params == ["t"]

    def test_multiple_placeholders_in_order(self):
        sql, params = translate("WHERE tenant_id=$1::uuid LIMIT $2 OFFSET $3", ("t", 10, 0))
        assert sql.count("%s") == 3
        assert params == ["t", 10, 0]

    def test_placeholders_out_of_order_are_reordered(self):
        """$2 before $1 must bind the second param first, not the first."""
        sql, params = translate("SELECT $2, $1", ("first", "second"))
        assert sql == "SELECT %s, %s"
        assert params == ["second", "first"]

    def test_reused_placeholder_duplicates_the_argument(self):
        """asyncpg allows $1 twice; psycopg3 needs the value at each occurrence."""
        sql, params = translate("SELECT $1, $1 WHERE x=$2", ("a", "b"))
        assert sql == "SELECT %s, %s WHERE x=%s"
        assert params == ["a", "a", "b"]

    def test_percent_is_escaped(self):
        sql, _ = translate("SELECT '50%' || $1", ("x",))
        assert "%%" in sql

    def test_no_placeholders(self):
        sql, params = translate("SELECT 1", ())
        assert sql == "SELECT 1"
        assert params == []


class TestGuards:
    def test_missing_parameter_is_an_error_not_a_guess(self):
        with pytest.raises(ValueError):
            translate("SELECT $2", ("only-one",))

    def test_bare_string_params_are_refused(self):
        """Indexing a str yields characters; that would bind one letter silently."""
        with pytest.raises(TypeError):
            translate("SELECT $1", "tenant-id")

    def test_zero_index_placeholder_is_refused(self):
        with pytest.raises(ValueError):
            translate("SELECT $0", ("a",))


class TestWrappers:
    def test_pool_delegates_unknown_attributes(self):
        class FakePool:
            marker = "real"

        assert PgPool(FakePool()).marker == "real"

    def test_connection_delegates_transaction(self):
        class FakeConn:
            def transaction(self):
                return "tx"

        assert PgConnection(FakeConn()).transaction() == "tx"


class TestPoolIsWrapped:
    def test_get_pool_returns_the_compat_pool(self, monkeypatch):
        """A regression here re-breaks every database route at once."""
        import inspect

        import dcc.api_async as api

        source = inspect.getsource(api.get_pool)
        assert "PgPool" in source, "get_pool must wrap psycopg3 in the asyncpg adapter"
