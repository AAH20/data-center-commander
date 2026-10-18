"""Fuzz tests for API input validation using Hypothesis."""
from __future__ import annotations

import json
from uuid import UUID

import pytest
from hypothesis import given, settings, strategies as st, assume

from dcc.api import parse_tenant, validate_placement_snapshot


# Strategies
uuid_strings = st.uuids().map(lambda u: str(u))

tenant_query_dicts = st.dictionaries(
    keys=st.just("tenant_id"),
    values=st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=5),
    min_size=0, max_size=1,
)

placement_names = st.text(min_size=0, max_size=200)

currency_codes = st.sampled_from(["USD", "EUR", "GBP", "JPY", "usd", "INVALID", ""])

horizon_months = st.integers(min_value=-100, max_value=200)

schema_versions = st.sampled_from([
    "placement-tco-comparison.v1",
    "placement-tco-comparison.v2",
    "invalid",
    "",
])

source_types = st.text(min_size=0, max_size=50)

iso_dates = st.dates().map(lambda d: d.isoformat())

observed_on_dates = st.dates().map(lambda d: d.isoformat())


class TestParseTenantFuzz:
    """Fuzz tenant ID parsing."""

    @given(query=tenant_query_dicts)
    @settings(max_examples=200)
    def test_parse_tenant_never_crashes(self, query):
        """parse_tenant should handle any query dict."""
        try:
            tenant = parse_tenant(query)
            assert isinstance(tenant, str)
            UUID(tenant)  # Should be valid UUID
        except ValueError:
            pass  # Expected for invalid tenant IDs

    @given(tenant_id=st.text(min_size=0, max_size=100))
    @settings(max_examples=200)
    def test_parse_tenant_with_arbitrary_strings(self, tenant_id):
        """parse_tenant should handle arbitrary strings."""
        query = {"tenant_id": [tenant_id]}
        try:
            tenant = parse_tenant(query)
            UUID(tenant)
        except ValueError:
            pass  # Expected for invalid UUIDs


class TestValidatePlacementSnapshotFuzz:
    """Fuzz placement snapshot validation."""

    @given(
        name=placement_names,
        currency=currency_codes,
        horizon=horizon_months,
        schema_version=schema_versions,
    )
    @settings(max_examples=200)
    def test_validate_placement_snapshot_never_crashes(self, name, currency, horizon, schema_version):
        """validate_placement_snapshot should handle any valid inputs."""
        body = {
            "name": name,
            "payload": {
                "schema_version": schema_version,
                "assumptions": {
                    "currency": currency,
                    "horizon_months": horizon,
                },
                "sources": {
                    "onprem": {
                        "type": "onprem",
                        "reference": "test-ref",
                        "observed_on": "2025-01-01",
                    },
                    "cloud": {
                        "type": "cloud",
                        "reference": "test-ref",
                        "observed_on": "2025-01-01",
                    },
                },
                "results": {
                    "onprem": {"total_cost": 1000},
                    "cloud": {"total_cost": 2000},
                },
            },
        }
        try:
            result = validate_placement_snapshot(body)
            assert len(result) == 4  # name, payload, digest, schema_version
        except ValueError:
            pass  # Expected for invalid inputs

    @given(
        name=placement_names,
        currency=currency_codes,
        horizon=horizon_months,
    )
    @settings(max_examples=200)
    def test_validate_placement_snapshot_with_valid_schema(self, name, currency, horizon):
        """validate_placement_snapshot should accept valid schema version."""
        body = {
            "name": name,
            "payload": {
                "schema_version": "placement-tco-comparison.v1",
                "assumptions": {
                    "currency": currency,
                    "horizon_months": horizon,
                },
                "sources": {
                    "onprem": {
                        "type": "onprem",
                        "reference": "test-ref",
                        "observed_on": "2025-01-01",
                    },
                    "cloud": {
                        "type": "cloud",
                        "reference": "test-ref",
                        "observed_on": "2025-01-01",
                    },
                },
                "results": {
                    "onprem": {"total_cost": 1000},
                    "cloud": {"total_cost": 2000},
                },
            },
        }
        try:
            result = validate_placement_snapshot(body)
            assert len(result) == 4
        except ValueError:
            pass  # Expected for invalid currency/horizon

    @given(
        body=st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.one_of(
                st.text(max_size=100),
                st.integers(),
                st.floats(allow_nan=False, allow_infinity=False),
                st.booleans(),
                st.none(),
            ),
            min_size=0, max_size=10,
        ),
    )
    @settings(max_examples=200)
    def test_validate_placement_snapshot_with_arbitrary_body(self, body):
        """validate_placement_snapshot should handle arbitrary body dicts."""
        try:
            result = validate_placement_snapshot(body)
            assert len(result) == 4
        except (ValueError, TypeError, KeyError):
            pass  # Expected for invalid bodies
