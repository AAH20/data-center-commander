"""Tests for the procedures (runbook) endpoint.

The rule that matters: a procedure key can have many versions, and the endpoint must
report the one that is IN FORCE. A runbook is followed during an incident, so reporting
version 1.9 as current when 1.10 exists is a safety defect, not a sorting preference --
and it is exactly what ORDER BY version DESC would do, because text puts "1.9" above
"1.10".

The selection logic is a pure function over rows so it can be tested without a database:
the rule is the part that can be wrong.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dcc.api_async import _select_current_versions, _version_sort_key, app


class TestVersionOrdering:
    def test_double_digit_minor_sorts_above_single(self):
        """The bug this exists to prevent: text ordering puts 1.9 above 1.10."""
        assert _version_sort_key("1.10") > _version_sort_key("1.9")

    def test_numeric_not_lexicographic(self):
        assert _version_sort_key("10") > _version_sort_key("9")

    def test_patch_level_ordering(self):
        assert _version_sort_key("1.10.10") > _version_sort_key("1.10.3")

    def test_ordering_is_total(self):
        """No two distinct versions may compare equal, or selection becomes arbitrary."""
        versions = ["1.0", "1.1", "1.2", "1.9", "1.10", "1.10.1", "2.0"]
        keys = [_version_sort_key(v) for v in versions]
        assert len(set(keys)) == len(versions)
        assert keys == sorted(keys)

    def test_non_numeric_version_does_not_raise(self):
        assert _version_sort_key("v2-beta")
        assert _version_sort_key("") == ()


def _row(key, version, rid=None, **extra):
    return {
        "procedure_key": key,
        "version": version,
        "id": rid or f"{key}-{version}",
        "title": f"{key} runbook",
        **extra,
    }


class TestCurrentVersionSelection:
    def test_collapses_to_one_row_per_key(self):
        rows = [_row("dr-failover", "1.9"), _row("dr-failover", "1.10")]
        selected = _select_current_versions(rows, latest_only=True)
        assert len(selected) == 1
        assert selected[0]["version"] == "1.10"

    def test_current_marker_is_on_the_highest_version(self):
        rows = [_row("dr-failover", "1.9"), _row("dr-failover", "1.10")]
        selected = _select_current_versions(rows, latest_only=False)
        current = [r for r in selected if r["is_current"]]
        assert len(current) == 1
        assert current[0]["version"] == "1.10"

    def test_history_mode_returns_every_version(self):
        rows = [_row("dr-failover", v) for v in ("1.0", "1.9", "1.10")]
        assert len(_select_current_versions(rows, latest_only=False)) == 3

    def test_keys_are_independent(self):
        rows = [
            _row("a", "1.0"), _row("a", "2.0"),
            _row("b", "9.9"), _row("b", "0.1"),
        ]
        selected = _select_current_versions(rows, latest_only=True)
        by_key = {r["procedure_key"]: r["version"] for r in selected}
        assert by_key == {"a": "2.0", "b": "9.9"}

    def test_single_version_still_marked_current(self):
        selected = _select_current_versions([_row("only", "1.0")], latest_only=True)
        assert selected[0]["is_current"] is True

    def test_empty_input(self):
        assert _select_current_versions([], latest_only=True) == []

    def test_output_is_sorted_by_key(self):
        rows = [_row("zeta", "1.0"), _row("alpha", "1.0")]
        selected = _select_current_versions(rows, latest_only=True)
        assert [r["procedure_key"] for r in selected] == ["alpha", "zeta"]


class TestRouteContract:
    def test_route_is_registered(self):
        assert "/v2/procedures" in {getattr(r, "path", "") for r in app.routes}

    def test_requires_a_tenant_id(self, monkeypatch):
        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
        response = TestClient(app).get("/v2/procedures")
        assert response.status_code == 422

    def test_malformed_tenant_id_is_refused(self, monkeypatch):
        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
        response = TestClient(app).get("/v2/procedures?tenant_id=not-a-uuid")
        assert response.status_code == 422
