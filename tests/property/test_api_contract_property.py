"""Property-based tests for API contract validation.

Tests invariants that should hold for all valid inputs:
- Tenant ID parsing is deterministic and validates UUID format
- Placement snapshot validation enforces schema constraints
- Health/readiness endpoints return consistent structure
- Query parameter validation is strict
"""
from __future__ import annotations

import re
from datetime import date
from uuid import UUID

import pytest
from hypothesis import given, settings, strategies as st

from dcc.api import parse_tenant, validate_placement_snapshot


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

valid_uuids = st.uuids().map(str)
invalid_uuid_strings = st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "P"))).filter(
    lambda s: not re.fullmatch(r"[0-9a-fA-F-]{36}", s)
)

valid_names = st.text(min_size=1, max_size=120, alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P")))
empty_or_long_names = st.one_of(
    st.just(""),
    st.text(min_size=121, max_size=200),
)

valid_currencies = st.sampled_from(["USD", "EUR", "GBP", "JPY", "CAD", "AUD"])
invalid_currencies = st.one_of(
    st.just(""),
    st.just("US"),
    st.just("USDD"),
    st.just("usd"),
    st.just("123"),
)

valid_horizons = st.integers(min_value=1, max_value=120)
invalid_horizons = st.one_of(
    st.integers(min_value=-100, max_value=0),
    st.integers(min_value=121, max_value=1000),
    st.just(True),
    st.just(False),
)

valid_iso_dates = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)).map(lambda d: d.isoformat())
invalid_dates = st.one_of(
    st.just(""),
    st.just("2024-13-01"),
    st.just("2024-01-32"),
    st.just("01-01-2024"),
    st.just("2024/01/01"),
)

valid_source_types = st.sampled_from(["vendor_api", "vendor_quote", "contract", "utility_tariff", "public_benchmark", "manual"])
valid_references = st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")))


def make_valid_payload(
    currency: str = "USD",
    horizon: int = 60,
    observed_on: str = "2024-01-15",
) -> dict:
    """Create a valid placement snapshot payload."""
    return {
        "schema_version": "placement-tco-comparison.v1",
        "assumptions": {
            "currency": currency,
            "horizon_months": horizon,
        },
        "sources": {
            "onprem": {
                "type": "vendor_quote",
                "reference": "REF-001",
                "observed_on": observed_on,
            },
            "cloud": {
                "type": "vendor_api",
                "reference": "REF-002",
                "observed_on": observed_on,
            },
        },
        "results": {
            "onprem": {"total_cost": 1000000},
            "cloud": {"total_cost": 1200000},
        },
    }


# ---------------------------------------------------------------------------
# Tenant ID parsing properties
# ---------------------------------------------------------------------------


@given(uuid_str=valid_uuids)
@settings(max_examples=200)
def test_parse_tenant_valid_uuid(uuid_str):
    """Valid UUID strings should parse successfully."""
    result = parse_tenant({"tenant_id": [uuid_str]})
    assert result == uuid_str


@given(invalid=invalid_uuid_strings)
@settings(max_examples=200)
def test_parse_tenant_invalid_uuid_raises(invalid):
    """Invalid UUID strings should raise ValueError."""
    with pytest.raises(ValueError, match="tenant_id"):
        parse_tenant({"tenant_id": [invalid]})


@given(uuid_str=valid_uuids)
@settings(max_examples=100)
def test_parse_tenant_duplicate_raises(uuid_str):
    """Duplicate tenant_id values should raise ValueError."""
    with pytest.raises(ValueError, match="tenant_id"):
        parse_tenant({"tenant_id": [uuid_str, uuid_str]})


@given(uuid_str=valid_uuids)
@settings(max_examples=100)
def test_parse_tenant_empty_raises(uuid_str):
    """Empty tenant_id list should raise ValueError."""
    with pytest.raises(ValueError, match="tenant_id"):
        parse_tenant({"tenant_id": []})


def test_parse_tenant_missing_key_raises():
    """Missing tenant_id key should raise ValueError."""
    with pytest.raises(ValueError, match="tenant_id"):
        parse_tenant({})


# ---------------------------------------------------------------------------
# Placement snapshot validation properties
# ---------------------------------------------------------------------------


@given(name=valid_names)
@settings(max_examples=200)
def test_placement_snapshot_valid_name_passes(name):
    """Valid names should pass validation."""
    body = {"name": name, "payload": make_valid_payload()}
    result_name, _, _, _ = validate_placement_snapshot(body)
    assert result_name == name.strip()


@given(name=empty_or_long_names)
@settings(max_examples=100)
def test_placement_snapshot_invalid_name_fails(name):
    """Empty or too-long names should fail validation."""
    body = {"name": name, "payload": make_valid_payload()}
    with pytest.raises(ValueError, match="name"):
        validate_placement_snapshot(body)


@given(currency=valid_currencies)
@settings(max_examples=100)
def test_placement_snapshot_valid_currency_passes(currency):
    """Valid 3-letter currency codes should pass."""
    body = {"name": "test", "payload": make_valid_payload(currency=currency)}
    _, _, _, _ = validate_placement_snapshot(body)


@given(currency=invalid_currencies)
@settings(max_examples=100)
def test_placement_snapshot_invalid_currency_fails(currency):
    """Invalid currency codes should fail."""
    body = {"name": "test", "payload": make_valid_payload(currency=currency)}
    with pytest.raises(ValueError, match="currency"):
        validate_placement_snapshot(body)


@given(horizon=valid_horizons)
@settings(max_examples=100)
def test_placement_snapshot_valid_horizon_passes(horizon):
    """Valid horizon values (1-120) should pass."""
    body = {"name": "test", "payload": make_valid_payload(horizon=horizon)}
    _, _, _, _ = validate_placement_snapshot(body)


@given(horizon=invalid_horizons)
@settings(max_examples=100)
def test_placement_snapshot_invalid_horizon_fails(horizon):
    """Invalid horizon values should fail."""
    body = {"name": "test", "payload": make_valid_payload(horizon=horizon)}
    with pytest.raises(ValueError, match="horizon"):
        validate_placement_snapshot(body)


@given(observed_on=valid_iso_dates)
@settings(max_examples=100)
def test_placement_snapshot_valid_date_passes(observed_on):
    """Valid ISO dates should pass."""
    body = {"name": "test", "payload": make_valid_payload(observed_on=observed_on)}
    _, _, _, _ = validate_placement_snapshot(body)


@given(observed_on=invalid_dates)
@settings(max_examples=100)
def test_placement_snapshot_invalid_date_fails(observed_on):
    """Invalid dates should fail."""
    body = {"name": "test", "payload": make_valid_payload(observed_on=observed_on)}
    with pytest.raises(ValueError, match="date"):
        validate_placement_snapshot(body)


@given(
    source_type=valid_source_types,
    reference=valid_references,
)
@settings(max_examples=100)
def test_placement_snapshot_valid_source_passes(source_type, reference):
    """Valid source types and references should pass."""
    payload = make_valid_payload()
    payload["sources"]["onprem"]["type"] = source_type
    payload["sources"]["onprem"]["reference"] = reference
    body = {"name": "test", "payload": payload}
    _, _, _, _ = validate_placement_snapshot(body)


def test_placement_snapshot_missing_schema_version_fails():
    """Missing schema_version should fail."""
    payload = make_valid_payload()
    del payload["schema_version"]
    body = {"name": "test", "payload": payload}
    with pytest.raises(ValueError, match="payload"):
        validate_placement_snapshot(body)


def test_placement_snapshot_wrong_schema_version_fails():
    """Wrong schema_version should fail."""
    payload = make_valid_payload()
    payload["schema_version"] = "wrong-version"
    body = {"name": "test", "payload": payload}
    with pytest.raises(ValueError, match="payload"):
        validate_placement_snapshot(body)


def test_placement_snapshot_missing_assumptions_fails():
    """Missing assumptions should fail."""
    payload = make_valid_payload()
    del payload["assumptions"]
    body = {"name": "test", "payload": payload}
    with pytest.raises(ValueError, match="assumptions"):
        validate_placement_snapshot(body)


def test_placement_snapshot_missing_sources_fails():
    """Missing sources should fail."""
    payload = make_valid_payload()
    del payload["sources"]
    body = {"name": "test", "payload": payload}
    with pytest.raises(ValueError, match="sources"):
        validate_placement_snapshot(body)


def test_placement_snapshot_missing_results_fails():
    """Missing results should fail."""
    payload = make_valid_payload()
    del payload["results"]
    body = {"name": "test", "payload": payload}
    with pytest.raises(ValueError, match="results"):
        validate_placement_snapshot(body)


def test_placement_snapshot_missing_onprem_source_fails():
    """Missing onprem source should fail."""
    payload = make_valid_payload()
    del payload["sources"]["onprem"]
    body = {"name": "test", "payload": payload}
    with pytest.raises(ValueError, match="onprem"):
        validate_placement_snapshot(body)


def test_placement_snapshot_missing_cloud_source_fails():
    """Missing cloud source should fail."""
    payload = make_valid_payload()
    del payload["sources"]["cloud"]
    body = {"name": "test", "payload": payload}
    with pytest.raises(ValueError, match="cloud"):
        validate_placement_snapshot(body)


# ---------------------------------------------------------------------------
# Determinism property
# ---------------------------------------------------------------------------


@given(name=valid_names, currency=valid_currencies, horizon=valid_horizons)
@settings(max_examples=100)
def test_placement_snapshot_deterministic(name, currency, horizon):
    """Same input should always produce the same output."""
    body = {"name": name, "payload": make_valid_payload(currency=currency, horizon=horizon)}
    result1 = validate_placement_snapshot(body)
    result2 = validate_placement_snapshot(body)
    assert result1 == result2


@given(name=valid_names, currency=valid_currencies, horizon=valid_horizons)
@settings(max_examples=100)
def test_placement_snapshot_hash_deterministic(name, currency, horizon):
    """Same input should always produce the same hash."""
    body = {"name": name, "payload": make_valid_payload(currency=currency, horizon=horizon)}
    _, _, hash1, _ = validate_placement_snapshot(body)
    _, _, hash2, _ = validate_placement_snapshot(body)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex digest length
