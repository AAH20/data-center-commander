"""Property-based tests for schema validation.

Tests invariants that should hold for all valid inputs:
- Field validators accept valid inputs and reject invalid ones
- Enum validators only accept known values
- Range validators enforce bounds
- Date validators enforce ordering
- Required field validators reject missing values
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st

from dcc.validation.schema import (
    ConstraintViolation,
    ValidationError,
    validate_cost_actual,
    validate_cost_allocation,
    validate_cost_book,
    validate_currency_code,
    validate_estimate_line_item,
    validate_estimate_project,
    validate_price_observation,
    validate_region,
    validate_service_name,
    validate_sku,
    validate_sku_query,
    validate_tenant_id,
    validate_window_days,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

valid_uuids = st.uuids().map(str)
invalid_uuid_strings = st.text(min_size=1, max_size=50).filter(
    lambda s: not isinstance(s, str) or len(s) != 36
)

valid_currencies = st.sampled_from(["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY"])
invalid_currencies = st.one_of(
    st.just(""),
    st.just("US"),
    st.just("USDD"),
    st.just("123"),
    st.just("US1"),
)

valid_service_names = st.from_regex(r"[A-Za-z0-9 ()&._/-]+", fullmatch=True).filter(lambda s: 1 <= len(s.strip()) <= 80)
invalid_service_names = st.one_of(
    st.just(""),
    st.text(min_size=81, max_size=100),
)

valid_regions = st.from_regex(r"[A-Za-z0-9._-]+", fullmatch=True).filter(lambda s: 1 <= len(s) <= 80)
invalid_regions = st.one_of(
    st.just(""),
    st.text(min_size=81, max_size=100),
)

valid_skus = st.from_regex(r"[A-Za-z0-9._-]+", fullmatch=True).filter(lambda s: 1 <= len(s) <= 80)
invalid_skus = st.one_of(
    st.just(""),
    st.text(min_size=81, max_size=100),
)

valid_window_days = st.integers(min_value=1, max_value=90)
invalid_window_days = st.one_of(
    st.integers(min_value=-100, max_value=0),
    st.integers(min_value=91, max_value=1000),
    st.just(True),
    st.just(False),
)

valid_iso_dates = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)).map(lambda d: d.isoformat())

valid_decimals = st.decimals(
    min_value=Decimal("-1e12"),
    max_value=Decimal("1e12"),
    allow_nan=False,
    allow_infinity=False,
    places=6,
)

positive_decimals = st.decimals(
    min_value=Decimal("0.001"),
    max_value=Decimal("1e9"),
    allow_nan=False,
    allow_infinity=False,
    places=6,
)

zero_to_one_decimals = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1"),
    allow_nan=False,
    allow_infinity=False,
    places=6,
)

valid_cost_book_statuses = st.sampled_from(["draft", "approved", "superseded", "archived"])
valid_price_bases = st.sampled_from(["budgetary", "quoted", "contracted", "actual", "benchmark"])
valid_price_categories = st.sampled_from([
    "land", "design", "civil", "electrical", "mechanical", "it_equipment",
    "network", "software", "labor", "energy", "water", "carbon",
    "maintenance", "tax", "finance", "decommissioning", "other",
])
valid_delivery_bases = st.sampled_from(["ex_works", "fob", "cif", "delivered", "installed", "subscription", "metered", "other"])
valid_source_kinds = st.sampled_from(["vendor_api", "vendor_quote", "contract", "utility_tariff", "public_benchmark", "manual", "synthetic_demo"])
valid_quality_statuses = st.sampled_from(["unverified", "reviewed", "approved", "expired", "rejected"])
valid_lifecycle_phases = st.sampled_from(["strategy", "site", "design", "procurement", "build", "commissioning", "operations", "refresh", "decommissioning"])
valid_estimate_statuses = st.sampled_from(["draft", "priced", "review", "approved", "superseded", "closed"])
valid_pricing_statuses = st.sampled_from(["sourced", "allowance", "unpriced", "synthetic"])
valid_cost_behaviors = st.sampled_from(["one_time", "fixed_recurring", "variable", "step_fixed", "capitalized"])
valid_cost_types = st.sampled_from(["capex", "opex", "energy", "carbon", "labor", "tax", "finance", "decommissioning", "other"])
valid_accrual_states = st.sampled_from(["accrued", "invoiced", "paid", "reversed"])
valid_allocation_basis = st.sampled_from(["direct_meter", "measured_usage", "capacity_share", "floor_area", "rack_units", "headcount", "equal_share", "manual_approved"])


def make_valid_cost_book(status: str = "draft") -> dict:
    """Create a valid cost book dict."""
    data = {
        "name": "Test Cost Book",
        "version": "1.0",
        "geography": "US-East",
        "valid_from": "2024-01-01",
        "status": status,
        "currency": "USD",
        "price_basis": "budgetary",
    }
    if status == "approved":
        data["approved_at"] = "2024-01-15"
    return data


def make_valid_price_observation() -> dict:
    """Create a valid price observation dict."""
    return {
        "item_code": "ITEM-001",
        "description": "Test Item",
        "quantity_unit": "each",
        "geography": "US-East",
        "source_name": "Vendor API",
        "source_ref": "REF-001",
        "valid_from": "2024-01-01",
        "currency_basis_date": "2024-01-01",
        "category": "it_equipment",
        "delivery_basis": "delivered",
        "source_kind": "vendor_api",
        "quality_status": "approved",
        "currency": "USD",
        "unit_price": "100.00",
        "normalized_unit_price": "100.00",
        "fx_to_book": "1",
        "confidence": "0.95",
    }


def make_valid_estimate_project() -> dict:
    """Create a valid estimate project dict."""
    return {
        "project_code": "PROJ-001",
        "name": "Test Project",
        "geography": "US-East",
        "price_as_of": "2024-01-01",
        "base_date": "2024-01-01",
        "lifecycle_phase": "design",
        "status": "draft",
        "currency": "USD",
        "horizon_months": 60,
        "discount_rate": "0.08",
        "contingency_pct": "0.10",
    }


def make_valid_estimate_line_item(pricing_status: str = "sourced") -> dict:
    """Create a valid estimate line item dict."""
    data = {
        "line_no": 1,
        "description": "Test Line Item",
        "quantity_unit": "each",
        "phase": "it_equipment",
        "currency": "USD",
        "pricing_status": pricing_status,
        "cost_behavior": "one_time",
        "quantity": "10",
        "waste_factor": "0.05",
        "base_unit_cost": "100.00",
        "escalation_pct": "0.03",
        "start_month": 0,
    }
    if pricing_status == "unpriced":
        data["assumptions"] = {"pricing_basis": "market_rate"}
    return data


def make_valid_cost_actual() -> dict:
    """Create a valid cost actual dict."""
    return {
        "source_system": "ERP",
        "source_ref": "INV-001",
        "accounting_period": "2024-01-01",
        "cost_type": "opex",
        "currency": "USD",
        "amount": "1000.00",
        "accrual_state": "accrued",
    }


def make_valid_cost_allocation() -> dict:
    """Create a valid cost allocation dict."""
    return {
        "method_version": "v1",
        "allocation_basis": "direct_meter",
        "currency": "USD",
        "allocated_amount": "1000.00",
        "allocation_fraction": "0.5",
        "window_start": "2024-01-01T00:00:00+00:00",
        "window_end": "2024-02-01T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Tenant ID validation properties
# ---------------------------------------------------------------------------


@given(uuid_str=valid_uuids)
@settings(max_examples=200)
def test_tenant_id_valid(uuid_str):
    """Valid UUID strings should pass validation."""
    result = validate_tenant_id(uuid_str)
    assert result == uuid_str


@given(invalid=st.text(min_size=1, max_size=50).filter(lambda s: len(s) != 36 or not all(c in "0123456789abcdefABCDEF-" for c in s)))
@settings(max_examples=200)
def test_tenant_id_invalid_raises(invalid):
    """Invalid UUID strings should raise ValidationError."""
    with pytest.raises(ValidationError):
        validate_tenant_id(invalid)


# ---------------------------------------------------------------------------
# Window days validation properties
# ---------------------------------------------------------------------------


@given(days=valid_window_days)
@settings(max_examples=100)
def test_window_days_valid(days):
    """Valid window days (1-90) should pass."""
    result = validate_window_days(days)
    assert result == days


@given(days=invalid_window_days)
@settings(max_examples=100)
def test_window_days_invalid_raises(days):
    """Invalid window days should raise ValidationError."""
    with pytest.raises(ValidationError):
        validate_window_days(days)


# ---------------------------------------------------------------------------
# Currency code validation properties
# ---------------------------------------------------------------------------


@given(currency=valid_currencies)
@settings(max_examples=50)
def test_currency_code_valid(currency):
    """Valid 3-letter currency codes should pass."""
    result = validate_currency_code(currency)
    assert result == currency


@given(currency=invalid_currencies)
@settings(max_examples=100)
def test_currency_code_invalid_raises(currency):
    """Invalid currency codes should raise ValidationError."""
    with pytest.raises(ValidationError):
        validate_currency_code(currency)


# ---------------------------------------------------------------------------
# Service name validation properties
# ---------------------------------------------------------------------------


@given(name=valid_service_names)
@settings(max_examples=200)
def test_service_name_valid(name):
    """Valid service names should pass."""
    result = validate_service_name(name)
    assert result == name.strip()


@given(name=invalid_service_names)
@settings(max_examples=100)
def test_service_name_invalid_raises(name):
    """Invalid service names should raise ValidationError."""
    with pytest.raises(ValidationError):
        validate_service_name(name)


# ---------------------------------------------------------------------------
# Region validation properties
# ---------------------------------------------------------------------------


@given(region=valid_regions)
@settings(max_examples=200)
def test_region_valid(region):
    """Valid regions should pass."""
    result = validate_region(region)
    assert result == region.strip()


@given(region=invalid_regions)
@settings(max_examples=100)
def test_region_invalid_raises(region):
    """Invalid regions should raise ValidationError."""
    with pytest.raises(ValidationError):
        validate_region(region)


# ---------------------------------------------------------------------------
# SKU validation properties
# ---------------------------------------------------------------------------


@given(sku=valid_skus)
@settings(max_examples=200)
def test_sku_valid(sku):
    """Valid SKUs should pass."""
    result = validate_sku(sku)
    assert result == sku.strip()


@given(sku=invalid_skus)
@settings(max_examples=100)
def test_sku_invalid_raises(sku):
    """Invalid SKUs should raise ValidationError."""
    with pytest.raises(ValidationError):
        validate_sku(sku)


# ---------------------------------------------------------------------------
# Cost book validation properties
# ---------------------------------------------------------------------------


@given(status=valid_cost_book_statuses)
@settings(max_examples=50)
def test_cost_book_valid_status_passes(status):
    """Valid cost book statuses should pass."""
    data = make_valid_cost_book(status=status)
    result = validate_cost_book(data)
    assert result["status"] == status


@given(status=st.sampled_from(["invalid", "DRAFT", "Approved", "unknown"]))
@settings(max_examples=50)
def test_cost_book_invalid_status_fails(status):
    """Invalid cost book statuses should fail."""
    data = make_valid_cost_book(status=status)
    with pytest.raises(ConstraintViolation):
        validate_cost_book(data)


@given(currency=valid_currencies)
@settings(max_examples=50)
def test_cost_book_valid_currency_passes(currency):
    """Valid currencies should pass."""
    data = make_valid_cost_book()
    data["currency"] = currency
    result = validate_cost_book(data)
    assert result["currency"] == currency


@given(price_basis=valid_price_bases)
@settings(max_examples=50)
def test_cost_book_valid_price_basis_passes(price_basis):
    """Valid price bases should pass."""
    data = make_valid_cost_book()
    data["price_basis"] = price_basis
    result = validate_cost_book(data)
    assert result["price_basis"] == price_basis


# ---------------------------------------------------------------------------
# Price observation validation properties
# ---------------------------------------------------------------------------


@given(category=valid_price_categories)
@settings(max_examples=50)
def test_price_observation_valid_category_passes(category):
    """Valid categories should pass."""
    data = make_valid_price_observation()
    data["category"] = category
    result = validate_price_observation(data)
    assert result["category"] == category


@given(delivery_basis=valid_delivery_bases)
@settings(max_examples=50)
def test_price_observation_valid_delivery_basis_passes(delivery_basis):
    """Valid delivery bases should pass."""
    data = make_valid_price_observation()
    data["delivery_basis"] = delivery_basis
    result = validate_price_observation(data)
    assert result["delivery_basis"] == delivery_basis


@given(source_kind=valid_source_kinds.filter(lambda x: x != "synthetic_demo"))
@settings(max_examples=50)
def test_price_observation_valid_source_kind_passes(source_kind):
    """Valid source kinds should pass."""
    data = make_valid_price_observation()
    data["source_kind"] = source_kind
    result = validate_price_observation(data)
    assert result["source_kind"] == source_kind


@given(quality_status=valid_quality_statuses)
@settings(max_examples=50)
def test_price_observation_valid_quality_status_passes(quality_status):
    """Valid quality statuses should pass."""
    data = make_valid_price_observation()
    data["quality_status"] = quality_status
    result = validate_price_observation(data)
    assert result["quality_status"] == quality_status


@given(confidence=zero_to_one_decimals)
@settings(max_examples=100)
def test_price_observation_valid_confidence_passes(confidence):
    """Confidence in [0, 1] should pass."""
    data = make_valid_price_observation()
    data["confidence"] = str(confidence)
    result = validate_price_observation(data)
    assert Decimal(result["confidence"]) == confidence


@given(confidence=st.decimals(min_value=Decimal("1.001"), max_value=Decimal("100"), allow_nan=False, allow_infinity=False, places=4))
@settings(max_examples=100)
def test_price_observation_invalid_confidence_fails(confidence):
    """Confidence > 1 should fail."""
    data = make_valid_price_observation()
    data["confidence"] = str(confidence)
    with pytest.raises(ConstraintViolation):
        validate_price_observation(data)


@given(unit_price=positive_decimals)
@settings(max_examples=100)
def test_price_observation_valid_unit_price_passes(unit_price):
    """Positive unit prices should pass."""
    data = make_valid_price_observation()
    data["unit_price"] = str(unit_price)
    data["normalized_unit_price"] = str(unit_price)
    result = validate_price_observation(data)
    assert Decimal(result["unit_price"]) == unit_price


# ---------------------------------------------------------------------------
# Estimate project validation properties
# ---------------------------------------------------------------------------


@given(lifecycle_phase=valid_lifecycle_phases)
@settings(max_examples=50)
def test_estimate_project_valid_lifecycle_phase_passes(lifecycle_phase):
    """Valid lifecycle phases should pass."""
    data = make_valid_estimate_project()
    data["lifecycle_phase"] = lifecycle_phase
    result = validate_estimate_project(data)
    assert result["lifecycle_phase"] == lifecycle_phase


@given(status=valid_estimate_statuses)
@settings(max_examples=50)
def test_estimate_project_valid_status_passes(status):
    """Valid statuses should pass."""
    data = make_valid_estimate_project()
    data["status"] = status
    result = validate_estimate_project(data)
    assert result["status"] == status


@given(horizon=st.integers(min_value=1, max_value=120))
@settings(max_examples=100)
def test_estimate_project_valid_horizon_passes(horizon):
    """Valid horizons (> 0) should pass."""
    data = make_valid_estimate_project()
    data["horizon_months"] = horizon
    result = validate_estimate_project(data)
    assert result["horizon_months"] == horizon


@given(discount_rate=zero_to_one_decimals.filter(lambda x: x < Decimal("1")))
@settings(max_examples=100)
def test_estimate_project_valid_discount_rate_passes(discount_rate):
    """Discount rates in [0, 1) should pass."""
    data = make_valid_estimate_project()
    data["discount_rate"] = str(discount_rate)
    result = validate_estimate_project(data)
    assert Decimal(result["discount_rate"]) == discount_rate


@given(contingency=zero_to_one_decimals)
@settings(max_examples=100)
def test_estimate_project_valid_contingency_passes(contingency):
    """Contingency in [0, 1] should pass."""
    data = make_valid_estimate_project()
    data["contingency_pct"] = str(contingency)
    result = validate_estimate_project(data)
    assert Decimal(result["contingency_pct"]) == contingency


# ---------------------------------------------------------------------------
# Estimate line item validation properties
# ---------------------------------------------------------------------------


@given(phase=valid_price_categories)
@settings(max_examples=50)
def test_estimate_line_item_valid_phase_passes(phase):
    """Valid phases should pass."""
    data = make_valid_estimate_line_item()
    data["phase"] = phase
    result = validate_estimate_line_item(data)
    assert result["phase"] == phase


@given(pricing_status=valid_pricing_statuses)
@settings(max_examples=50)
def test_estimate_line_item_valid_pricing_status_passes(pricing_status):
    """Valid pricing statuses should pass."""
    data = make_valid_estimate_line_item(pricing_status=pricing_status)
    result = validate_estimate_line_item(data)
    assert result["pricing_status"] == pricing_status


@given(cost_behavior=valid_cost_behaviors)
@settings(max_examples=50)
def test_estimate_line_item_valid_cost_behavior_passes(cost_behavior):
    """Valid cost behaviors should pass."""
    data = make_valid_estimate_line_item()
    data["cost_behavior"] = cost_behavior
    result = validate_estimate_line_item(data)
    assert result["cost_behavior"] == cost_behavior


@given(quantity=positive_decimals)
@settings(max_examples=100)
def test_estimate_line_item_valid_quantity_passes(quantity):
    """Positive quantities should pass."""
    data = make_valid_estimate_line_item()
    data["quantity"] = str(quantity)
    result = validate_estimate_line_item(data)
    assert Decimal(result["quantity"]) == quantity


@given(waste_factor=zero_to_one_decimals)
@settings(max_examples=100)
def test_estimate_line_item_valid_waste_factor_passes(waste_factor):
    """Waste factors in [0, 1] should pass."""
    data = make_valid_estimate_line_item()
    data["waste_factor"] = str(waste_factor)
    result = validate_estimate_line_item(data)
    assert Decimal(result["waste_factor"]) == waste_factor


@given(base_cost=positive_decimals)
@settings(max_examples=100)
def test_estimate_line_item_valid_base_cost_passes(base_cost):
    """Positive base costs should pass."""
    data = make_valid_estimate_line_item()
    data["base_unit_cost"] = str(base_cost)
    result = validate_estimate_line_item(data)
    assert Decimal(result["base_unit_cost"]) == base_cost


# ---------------------------------------------------------------------------
# Cost actual validation properties
# ---------------------------------------------------------------------------


@given(cost_type=valid_cost_types)
@settings(max_examples=50)
def test_cost_actual_valid_cost_type_passes(cost_type):
    """Valid cost types should pass."""
    data = make_valid_cost_actual()
    data["cost_type"] = cost_type
    result = validate_cost_actual(data)
    assert result["cost_type"] == cost_type


@given(accrual_state=valid_accrual_states)
@settings(max_examples=50)
def test_cost_actual_valid_accrual_state_passes(accrual_state):
    """Valid accrual states should pass."""
    data = make_valid_cost_actual()
    data["accrual_state"] = accrual_state
    result = validate_cost_actual(data)
    assert result["accrual_state"] == accrual_state


@given(amount=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("1e9"), allow_nan=False, allow_infinity=False, places=6))
@settings(max_examples=100)
def test_cost_actual_valid_amount_passes(amount):
    """Non-zero amounts should pass."""
    data = make_valid_cost_actual()
    data["amount"] = str(amount)
    result = validate_cost_actual(data)
    assert Decimal(result["amount"]) == amount


# ---------------------------------------------------------------------------
# Cost allocation validation properties
# ---------------------------------------------------------------------------


@given(allocation_basis_val=valid_allocation_basis)
@settings(max_examples=50)
def test_cost_allocation_valid_basis_passes(allocation_basis_val):
    """Valid allocation bases should pass."""
    data = make_valid_cost_allocation()
    data["allocation_basis"] = allocation_basis_val
    result = validate_cost_allocation(data)
    assert result["allocation_basis"] == allocation_basis_val


@given(fraction=zero_to_one_decimals)
@settings(max_examples=100)
def test_cost_allocation_valid_fraction_passes(fraction):
    """Fractions in [0, 1] should pass."""
    data = make_valid_cost_allocation()
    data["allocation_fraction"] = str(fraction)
    result = validate_cost_allocation(data)
    assert Decimal(result["allocation_fraction"]) == fraction


@given(amount=positive_decimals)
@settings(max_examples=100)
def test_cost_allocation_valid_amount_passes(amount):
    """Positive amounts should pass."""
    data = make_valid_cost_allocation()
    data["allocated_amount"] = str(amount)
    result = validate_cost_allocation(data)
    assert Decimal(result["allocated_amount"]) == amount


# ---------------------------------------------------------------------------
# Determinism properties
# ---------------------------------------------------------------------------


@given(status=valid_cost_book_statuses)
@settings(max_examples=50)
def test_cost_book_deterministic(status):
    """Same input should always produce the same output."""
    data = make_valid_cost_book(status=status)
    result1 = validate_cost_book(data)
    result2 = validate_cost_book(data)
    assert result1 == result2


@given(category=valid_price_categories)
@settings(max_examples=50)
def test_price_observation_deterministic(category):
    """Same input should always produce the same output."""
    data = make_valid_price_observation()
    data["category"] = category
    result1 = validate_price_observation(data)
    result2 = validate_price_observation(data)
    assert result1 == result2
