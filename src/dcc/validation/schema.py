"""Schema validation layer for Data Center Commander.

Validates all incoming data against database schema constraints, types, and ranges.
Mirrors the CHECK constraints, NOT NULL constraints, and type constraints defined
in database/schema.sql and migrations.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
from uuid import UUID


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ValidationError(ValueError):
    """Raised when data fails schema validation."""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        super().__init__(message)


class ConstraintViolation(ValidationError):
    """Raised when a specific constraint is violated."""

    def __init__(self, message: str, field: str, constraint: str) -> None:
        self.constraint = constraint
        super().__init__(message, field=field)


# ---------------------------------------------------------------------------
# Field-level validators
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9 ()&._/-]+$")
_REGION_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_SKU_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_SKU_QUERY_RE = re.compile(r"^[A-Za-z0-9 &()._/-]+$")


def validate_tenant_id(value: Any) -> str:
    """Validate a tenant UUID string."""
    if not isinstance(value, str):
        raise ValidationError("tenant_id must be a string", field="tenant_id")
    if not _UUID_RE.fullmatch(value):
        raise ValidationError("tenant_id must be a valid UUID", field="tenant_id")
    return str(UUID(value))


def validate_window_days(value: Any) -> int:
    """Validate window_days is an integer from 1 to 90."""
    if isinstance(value, bool):
        raise ValidationError("window_days must be an integer from 1 to 90", field="window_days")
    try:
        days = int(value)
    except (TypeError, ValueError):
        raise ValidationError("window_days must be an integer from 1 to 90", field="window_days") from None
    if not 1 <= days <= 90:
        raise ValidationError("window_days must be an integer from 1 to 90", field="window_days")
    return days


def validate_currency_code(value: Any, field: str = "currency") -> str:
    """Validate a three-letter ISO currency code."""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string", field=field)
    value = value.strip().upper()
    if not _CURRENCY_RE.fullmatch(value):
        raise ValidationError(f"{field} must be a three-letter ISO currency code", field=field)
    return value


def validate_service_name(value: Any, field: str = "service_name", max_len: int = 80) -> str:
    """Validate a service name contains only catalog-safe characters."""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string", field=field)
    value = value.strip()
    if not value:
        raise ValidationError(f"{field} is required", field=field)
    if len(value) > max_len:
        raise ValidationError(f"{field} exceeds {max_len} characters", field=field)
    if not _SERVICE_NAME_RE.fullmatch(value):
        raise ValidationError(f"{field} contains unsupported characters", field=field)
    return value


def validate_region(value: Any, field: str = "region", max_len: int = 80) -> str:
    """Validate a region string."""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string", field=field)
    value = value.strip()
    if not value:
        raise ValidationError(f"{field} is required", field=field)
    if len(value) > max_len:
        raise ValidationError(f"{field} exceeds {max_len} characters", field=field)
    if not _REGION_RE.fullmatch(value):
        raise ValidationError(f"{field} contains unsupported characters", field=field)
    return value


def validate_sku(value: Any, field: str = "sku", max_len: int = 80) -> str:
    """Validate an SKU string."""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string", field=field)
    value = value.strip()
    if not value:
        raise ValidationError(f"{field} is required", field=field)
    if len(value) > max_len:
        raise ValidationError(f"{field} exceeds {max_len} characters", field=field)
    if not _SKU_RE.fullmatch(value):
        raise ValidationError(f"{field} contains unsupported characters", field=field)
    return value


def validate_sku_query(value: Any, field: str = "sku_query", max_len: int = 100) -> str:
    """Validate an SKU query string."""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string", field=field)
    value = value.strip()
    if not value:
        raise ValidationError(f"{field} is required", field=field)
    if len(value) > max_len:
        raise ValidationError(f"{field} exceeds {max_len} characters", field=field)
    if not _SKU_QUERY_RE.fullmatch(value):
        raise ValidationError(f"{field} contains unsupported characters", field=field)
    return value


def validate_api_key(value: Any, field: str = "api_key", max_len: int = 512) -> str:
    """Validate an API key string."""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string", field=field)
    value = value.strip()
    if not value:
        raise ValidationError(f"{field} is required", field=field)
    if len(value) > max_len:
        raise ValidationError(f"{field} exceeds {max_len} characters", field=field)
    if any(ch in value for ch in "\r\n\x00"):
        raise ValidationError(f"{field} contains invalid characters", field=field)
    return value


# ---------------------------------------------------------------------------
# Placement snapshot validation
# ---------------------------------------------------------------------------


def validate_placement_snapshot_payload(payload: Any) -> dict[str, Any]:
    """Validate a placement comparison snapshot payload.

    Mirrors the constraints on dcc.placement_comparison_snapshots and the
    validate_placement_snapshot function in api.py.
    """
    if not isinstance(payload, dict):
        raise ValidationError("payload must be an object", field="payload")

    schema_version = payload.get("schema_version")
    if schema_version != "placement-tco-comparison.v1":
        raise ValidationError("unsupported placement comparison payload", field="schema_version")

    assumptions = payload.get("assumptions")
    sources = payload.get("sources")
    results = payload.get("results")

    if not isinstance(assumptions, dict):
        raise ValidationError("comparison assumptions are required", field="assumptions")
    if not isinstance(sources, dict):
        raise ValidationError("comparison sources are required", field="sources")
    if not isinstance(results, dict):
        raise ValidationError("comparison results are required", field="results")

    currency = assumptions.get("currency", "")
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Za-z]{3}", currency):
        raise ValidationError("comparison currency must be a 3-letter code", field="assumptions.currency")

    horizon = assumptions.get("horizon_months")
    if not isinstance(horizon, int) or isinstance(horizon, bool) or not 1 <= horizon <= 120:
        raise ValidationError("comparison horizon must be 1-120 months", field="assumptions.horizon_months")

    for side in ("onprem", "cloud"):
        source = sources.get(side)
        if not isinstance(source, dict):
            raise ValidationError(f"{side} source is required", field=f"sources.{side}")
        for key in ("type", "reference", "observed_on"):
            val = source.get(key)
            if not isinstance(val, str) or not val.strip():
                raise ValidationError(
                    f"{side} source {key} is required", field=f"sources.{side}.{key}"
                )
        try:
            date.fromisoformat(source["observed_on"])
        except (TypeError, ValueError):
            raise ValidationError(
                f"{side} observation date must be YYYY-MM-DD", field=f"sources.{side}.observed_on"
            ) from None
        if side not in results or not isinstance(results[side], dict):
            raise ValidationError(f"{side} calculated result is required", field=f"results.{side}")

    return payload


# ---------------------------------------------------------------------------
# Cost intelligence validators
# ---------------------------------------------------------------------------


_COST_BOOK_STATUSES = {"draft", "approved", "superseded", "archived"}
_PRICE_BASIS = {"budgetary", "quoted", "contracted", "actual", "benchmark"}
_PRICE_CATEGORIES = {
    "land", "design", "civil", "electrical", "mechanical", "it_equipment",
    "network", "software", "labor", "energy", "water", "carbon",
    "maintenance", "tax", "finance", "decommissioning", "other",
}
_DELIVERY_BASIS = {"ex_works", "fob", "cif", "delivered", "installed", "subscription", "metered", "other"}
_SOURCE_KINDS = {"vendor_api", "vendor_quote", "contract", "utility_tariff", "public_benchmark", "manual", "synthetic_demo"}
_QUALITY_STATUSES = {"unverified", "reviewed", "approved", "expired", "rejected"}
_LIFECYCLE_PHASES = {"strategy", "site", "design", "procurement", "build", "commissioning", "operations", "refresh", "decommissioning"}
_ESTIMATE_STATUSES = {"draft", "priced", "review", "approved", "superseded", "closed"}
_PRICING_STATUSES = {"sourced", "allowance", "unpriced", "synthetic"}
_COST_BEHAVIORS = {"one_time", "fixed_recurring", "variable", "step_fixed", "capitalized"}
_COST_TYPES = {"capex", "opex", "energy", "carbon", "labor", "tax", "finance", "decommissioning", "other"}
_ACCRUAL_STATES = {"accrued", "invoiced", "paid", "reversed"}
_ALLOCATION_BASIS = {"direct_meter", "measured_usage", "capacity_share", "floor_area", "rack_units", "headcount", "equal_share", "manual_approved"}


def validate_cost_book(data: dict[str, Any]) -> dict[str, Any]:
    """Validate cost book data against dcc.cost_books constraints."""
    _require_str(data, "name", "cost_book")
    _require_str(data, "version", "cost_book")
    _require_str(data, "geography", "cost_book")
    _require_date(data, "valid_from", "cost_book")

    status = _require_str(data, "status", "cost_book")
    if status not in _COST_BOOK_STATUSES:
        raise ConstraintViolation(
            f"status must be one of {sorted(_COST_BOOK_STATUSES)}", field="status", constraint="status_check"
        )

    currency = _require_str(data, "currency", "cost_book")
    if not _CURRENCY_RE.fullmatch(currency):
        raise ConstraintViolation("currency must be a 3-letter code", field="currency", constraint="currency_check")

    price_basis = _require_str(data, "price_basis", "cost_book")
    if price_basis not in _PRICE_BASIS:
        raise ConstraintViolation(
            f"price_basis must be one of {sorted(_PRICE_BASIS)}", field="price_basis", constraint="price_basis_check"
        )

    valid_to = data.get("valid_to")
    if valid_to is not None:
        _require_date({"valid_to": valid_to}, "valid_to", "cost_book")
        if valid_to <= data["valid_from"]:
            raise ConstraintViolation("valid_to must be after valid_from", field="valid_to", constraint="valid_range_check")

    if status == "approved" and not data.get("approved_at"):
        raise ConstraintViolation("approved cost book requires approved_at", field="approved_at", constraint="approval_check")

    return data


def validate_price_observation(data: dict[str, Any]) -> dict[str, Any]:
    """Validate price observation data against dcc.price_observations constraints."""
    _require_str(data, "item_code", "price_observation")
    _require_str(data, "description", "price_observation")
    _require_str(data, "quantity_unit", "price_observation")
    _require_str(data, "geography", "price_observation")
    _require_str(data, "source_name", "price_observation")
    _require_str(data, "source_ref", "price_observation")
    _require_date(data, "valid_from", "price_observation")
    _require_date(data, "currency_basis_date", "price_observation")

    category = _require_str(data, "category", "price_observation")
    if category not in _PRICE_CATEGORIES:
        raise ConstraintViolation(
            f"category must be one of {sorted(_PRICE_CATEGORIES)}", field="category", constraint="category_check"
        )

    delivery_basis = _require_str(data, "delivery_basis", "price_observation")
    if delivery_basis not in _DELIVERY_BASIS:
        raise ConstraintViolation(
            f"delivery_basis must be one of {sorted(_DELIVERY_BASIS)}", field="delivery_basis", constraint="delivery_basis_check"
        )

    source_kind = _require_str(data, "source_kind", "price_observation")
    if source_kind not in _SOURCE_KINDS:
        raise ConstraintViolation(
            f"source_kind must be one of {sorted(_SOURCE_KINDS)}", field="source_kind", constraint="source_kind_check"
        )

    quality_status = _require_str(data, "quality_status", "price_observation")
    if quality_status not in _QUALITY_STATUSES:
        raise ConstraintViolation(
            f"quality_status must be one of {sorted(_QUALITY_STATUSES)}", field="quality_status", constraint="quality_status_check"
        )

    currency = _require_str(data, "currency", "price_observation")
    if not _CURRENCY_RE.fullmatch(currency):
        raise ConstraintViolation("currency must be a 3-letter code", field="currency", constraint="currency_check")

    unit_price = _require_decimal(data, "unit_price", "price_observation")
    if unit_price < 0:
        raise ConstraintViolation("unit_price must be >= 0", field="unit_price", constraint="unit_price_check")

    normalized_unit_price = _require_decimal(data, "normalized_unit_price", "price_observation")
    if normalized_unit_price < 0:
        raise ConstraintViolation("normalized_unit_price must be >= 0", field="normalized_unit_price", constraint="normalized_unit_price_check")

    fx_to_book = _require_decimal(data, "fx_to_book", "price_observation", default=Decimal("1"))
    if fx_to_book <= 0:
        raise ConstraintViolation("fx_to_book must be > 0", field="fx_to_book", constraint="fx_to_book_check")

    confidence = _require_decimal(data, "confidence", "price_observation")
    if not (Decimal("0") <= confidence <= Decimal("1")):
        raise ConstraintViolation("confidence must be between 0 and 1", field="confidence", constraint="confidence_check")

    valid_to = data.get("valid_to")
    if valid_to is not None:
        _require_date({"valid_to": valid_to}, "valid_to", "price_observation")
        if valid_to <= data["valid_from"]:
            raise ConstraintViolation("valid_to must be after valid_from", field="valid_to", constraint="valid_range_check")

    if source_kind == "synthetic_demo":
        provenance = data.get("provenance", {})
        if not isinstance(provenance, dict) or provenance.get("synthetic") is not True:
            raise ConstraintViolation(
                "synthetic_demo source requires provenance.synthetic=true",
                field="provenance.synthetic",
                constraint="synthetic_provenance_check",
            )

    return data


def validate_estimate_project(data: dict[str, Any]) -> dict[str, Any]:
    """Validate estimate project data against dcc.estimate_projects constraints."""
    _require_str(data, "project_code", "estimate_project")
    _require_str(data, "name", "estimate_project")
    _require_str(data, "geography", "estimate_project")
    _require_date(data, "price_as_of", "estimate_project")
    _require_date(data, "base_date", "estimate_project")

    lifecycle_phase = _require_str(data, "lifecycle_phase", "estimate_project")
    if lifecycle_phase not in _LIFECYCLE_PHASES:
        raise ConstraintViolation(
            f"lifecycle_phase must be one of {sorted(_LIFECYCLE_PHASES)}",
            field="lifecycle_phase",
            constraint="lifecycle_phase_check",
        )

    status = _require_str(data, "status", "estimate_project")
    if status not in _ESTIMATE_STATUSES:
        raise ConstraintViolation(
            f"status must be one of {sorted(_ESTIMATE_STATUSES)}", field="status", constraint="status_check"
        )

    currency = _require_str(data, "currency", "estimate_project")
    if not _CURRENCY_RE.fullmatch(currency):
        raise ConstraintViolation("currency must be a 3-letter code", field="currency", constraint="currency_check")

    horizon_months = _require_int(data, "horizon_months", "estimate_project")
    if horizon_months <= 0:
        raise ConstraintViolation("horizon_months must be > 0", field="horizon_months", constraint="horizon_months_check")

    discount_rate = _require_decimal(data, "discount_rate", "estimate_project", default=Decimal("0"))
    if not (Decimal("0") <= discount_rate < Decimal("1")):
        raise ConstraintViolation(
            "discount_rate must be >= 0 and < 1", field="discount_rate", constraint="discount_rate_check"
        )

    contingency_pct = _require_decimal(data, "contingency_pct", "estimate_project", default=Decimal("0"))
    if not (Decimal("0") <= contingency_pct <= Decimal("1")):
        raise ConstraintViolation(
            "contingency_pct must be between 0 and 1", field="contingency_pct", constraint="contingency_pct_check"
        )

    return data


def validate_estimate_line_item(data: dict[str, Any]) -> dict[str, Any]:
    """Validate estimate line item data against dcc.estimate_line_items constraints."""
    _require_int(data, "line_no", "estimate_line_item")
    _require_str(data, "description", "estimate_line_item")
    _require_str(data, "quantity_unit", "estimate_line_item")

    phase = _require_str(data, "phase", "estimate_line_item")
    if phase not in _PRICE_CATEGORIES:
        raise ConstraintViolation(
            f"phase must be one of {sorted(_PRICE_CATEGORIES)}", field="phase", constraint="phase_check"
        )

    currency = _require_str(data, "currency", "estimate_line_item")
    if not _CURRENCY_RE.fullmatch(currency):
        raise ConstraintViolation("currency must be a 3-letter code", field="currency", constraint="currency_check")

    pricing_status = _require_str(data, "pricing_status", "estimate_line_item")
    if pricing_status not in _PRICING_STATUSES:
        raise ConstraintViolation(
            f"pricing_status must be one of {sorted(_PRICING_STATUSES)}",
            field="pricing_status",
            constraint="pricing_status_check",
        )

    cost_behavior = _require_str(data, "cost_behavior", "estimate_line_item", default="one_time")
    if cost_behavior not in _COST_BEHAVIORS:
        raise ConstraintViolation(
            f"cost_behavior must be one of {sorted(_COST_BEHAVIORS)}",
            field="cost_behavior",
            constraint="cost_behavior_check",
        )

    quantity = _require_decimal(data, "quantity", "estimate_line_item")
    if quantity < 0:
        raise ConstraintViolation("quantity must be >= 0", field="quantity", constraint="quantity_check")

    waste_factor = _require_decimal(data, "waste_factor", "estimate_line_item", default=Decimal("0"))
    if not (Decimal("0") <= waste_factor <= Decimal("1")):
        raise ConstraintViolation(
            "waste_factor must be between 0 and 1", field="waste_factor", constraint="waste_factor_check"
        )

    base_unit_cost = _require_decimal(data, "base_unit_cost", "estimate_line_item")
    if base_unit_cost < 0:
        raise ConstraintViolation("base_unit_cost must be >= 0", field="base_unit_cost", constraint="base_unit_cost_check")

    low_unit_cost = data.get("low_unit_cost")
    if low_unit_cost is not None:
        low_unit_cost = _require_decimal({"low_unit_cost": low_unit_cost}, "low_unit_cost", "estimate_line_item")
        if low_unit_cost > base_unit_cost:
            raise ConstraintViolation(
                "low_unit_cost must be <= base_unit_cost", field="low_unit_cost", constraint="low_cost_check"
            )

    high_unit_cost = data.get("high_unit_cost")
    if high_unit_cost is not None:
        high_unit_cost = _require_decimal({"high_unit_cost": high_unit_cost}, "high_unit_cost", "estimate_line_item")
        if high_unit_cost < base_unit_cost:
            raise ConstraintViolation(
                "high_unit_cost must be >= base_unit_cost", field="high_unit_cost", constraint="high_cost_check"
            )

    escalation_pct = _require_decimal(data, "escalation_pct", "estimate_line_item", default=Decimal("0"))
    if escalation_pct < Decimal("-1"):
        raise ConstraintViolation(
            "escalation_pct must be >= -1", field="escalation_pct", constraint="escalation_pct_check"
        )

    start_month = _require_int(data, "start_month", "estimate_line_item", default=0)
    if start_month < 0:
        raise ConstraintViolation("start_month must be >= 0", field="start_month", constraint="start_month_check")

    recurrence_months = data.get("recurrence_months")
    if recurrence_months is not None:
        recurrence_months = _require_int(
            {"recurrence_months": recurrence_months}, "recurrence_months", "estimate_line_item"
        )
        if cost_behavior in ("fixed_recurring", "variable") and recurrence_months <= 0:
            raise ConstraintViolation(
                f"recurrence_months must be > 0 for {cost_behavior}",
                field="recurrence_months",
                constraint="recurrence_check",
            )
        if cost_behavior not in ("fixed_recurring", "variable") and recurrence_months is not None:
            raise ConstraintViolation(
                f"recurrence_months must be null for {cost_behavior}",
                field="recurrence_months",
                constraint="recurrence_check",
            )

    if pricing_status == "unpriced":
        assumptions = data.get("assumptions", {})
        if not isinstance(assumptions, dict) or "pricing_basis" not in assumptions:
            raise ConstraintViolation(
                "unpriced line requires assumptions.pricing_basis",
                field="assumptions.pricing_basis",
                constraint="unpriced_basis_check",
            )

    return data


def validate_cost_actual(data: dict[str, Any]) -> dict[str, Any]:
    """Validate cost actual data against dcc.cost_actuals constraints."""
    _require_str(data, "source_system", "cost_actual")
    _require_str(data, "source_ref", "cost_actual")
    _require_date(data, "accounting_period", "cost_actual")

    cost_type = _require_str(data, "cost_type", "cost_actual")
    if cost_type not in _COST_TYPES:
        raise ConstraintViolation(
            f"cost_type must be one of {sorted(_COST_TYPES)}", field="cost_type", constraint="cost_type_check"
        )

    currency = _require_str(data, "currency", "cost_actual")
    if not _CURRENCY_RE.fullmatch(currency):
        raise ConstraintViolation("currency must be a 3-letter code", field="currency", constraint="currency_check")

    amount = _require_decimal(data, "amount", "cost_actual")
    if amount == 0:
        raise ConstraintViolation("amount must not be zero", field="amount", constraint="amount_check")

    accrual_state = _require_str(data, "accrual_state", "cost_actual")
    if accrual_state not in _ACCRUAL_STATES:
        raise ConstraintViolation(
            f"accrual_state must be one of {sorted(_ACCRUAL_STATES)}",
            field="accrual_state",
            constraint="accrual_state_check",
        )

    return data


def validate_cost_allocation(data: dict[str, Any]) -> dict[str, Any]:
    """Validate cost allocation data against dcc.cost_allocations constraints."""
    _require_str(data, "method_version", "cost_allocation")

    allocation_basis = _require_str(data, "allocation_basis", "cost_allocation")
    if allocation_basis not in _ALLOCATION_BASIS:
        raise ConstraintViolation(
            f"allocation_basis must be one of {sorted(_ALLOCATION_BASIS)}",
            field="allocation_basis",
            constraint="allocation_basis_check",
        )

    currency = _require_str(data, "currency", "cost_allocation")
    if not _CURRENCY_RE.fullmatch(currency):
        raise ConstraintViolation("currency must be a 3-letter code", field="currency", constraint="currency_check")

    allocated_amount = _require_decimal(data, "allocated_amount", "cost_allocation")

    allocation_fraction = _require_decimal(data, "allocation_fraction", "cost_allocation")
    if not (Decimal("0") <= allocation_fraction <= Decimal("1")):
        raise ConstraintViolation(
            "allocation_fraction must be between 0 and 1",
            field="allocation_fraction",
            constraint="allocation_fraction_check",
        )

    window_start = _require_datetime(data, "window_start", "cost_allocation")
    window_end = _require_datetime(data, "window_end", "cost_allocation")
    if window_end <= window_start:
        raise ConstraintViolation(
            "window_end must be after window_start", field="window_end", constraint="window_check"
        )

    return data


# ---------------------------------------------------------------------------
# Asset topology validators
# ---------------------------------------------------------------------------


_ASSET_LIFECYCLE_STATES = {
    "planned", "procured", "installed", "commissioning", "active",
    "maintenance", "impaired", "retiring", "retired", "disposed", "unknown",
}
_CRITICALITY_LEVELS = {"low", "medium", "high", "critical"}
_FACILITY_TYPES = {"datacenter", "edge", "lab", "other"}
_SPACE_TYPES = {"electrical", "mechanical", "white_space", "room", "row", "zone", "yard", "other"}
_CONNECTOR_STATUSES = {"draft", "testing", "active", "degraded", "disabled"}
_ACCESS_MODES = {"read_only", "draft_write", "disabled"}
_RELATION_TYPES = {"contains", "feeds", "backs_up", "cools", "hosts", "depends_on", "serves", "connects_to", "measures"}
_METER_DIRECTIONS = {"import", "export", "bidirectional", "internal"}
_VALUE_KINDS = {"gauge", "counter", "interval_total", "state"}
_CAPACITY_DIMENSIONS = {"power_kw", "cooling_kw", "rack_u", "network_gbps", "storage_tb", "cpu_cores", "gpu_units", "water_m3_day", "fuel_hours"}
_TENANT_STATUSES = {"active", "suspended", "archived"}
_CARBON_METHODS = {"location_based", "market_based", "supplier_specific", "other"}
_DEPLOYMENT_ALLOCATION_METHODS = {"direct_meter", "device_model", "capacity_share", "shared", "unallocated"}


def validate_site(data: dict[str, Any]) -> dict[str, Any]:
    """Validate site data against dcc.sites constraints."""
    _require_str(data, "code", "site")
    _require_str(data, "name", "site")
    _require_str(data, "timezone", "site")

    country_code = data.get("country_code")
    if country_code is not None:
        if not isinstance(country_code, str) or len(country_code) != 2:
            raise ConstraintViolation("country_code must be 2 characters", field="country_code", constraint="country_code_check")

    latitude = data.get("latitude")
    if latitude is not None:
        lat = _require_decimal({"latitude": latitude}, "latitude", "site")
        if not (Decimal("-90") <= lat <= Decimal("90")):
            raise ConstraintViolation("latitude must be between -90 and 90", field="latitude", constraint="latitude_check")

    longitude = data.get("longitude")
    if longitude is not None:
        lon = _require_decimal({"longitude": longitude}, "longitude", "site")
        if not (Decimal("-180") <= lon <= Decimal("180")):
            raise ConstraintViolation("longitude must be between -180 and 180", field="longitude", constraint="longitude_check")

    return data


def validate_facility(data: dict[str, Any]) -> dict[str, Any]:
    """Validate facility data against dcc.facilities constraints."""
    _require_str(data, "code", "facility")
    _require_str(data, "name", "facility")

    facility_type = _require_str(data, "facility_type", "facility")
    if facility_type not in _FACILITY_TYPES:
        raise ConstraintViolation(
            f"facility_type must be one of {sorted(_FACILITY_TYPES)}",
            field="facility_type",
            constraint="facility_type_check",
        )

    status = data.get("status", "active")
    if status not in {"active", "inactive", "decommissioned"}:
        raise ConstraintViolation("invalid facility status", field="status", constraint="status_check")

    return data


def validate_space(data: dict[str, Any]) -> dict[str, Any]:
    """Validate space data against dcc.spaces constraints."""
    _require_str(data, "code", "space")
    _require_str(data, "name", "space")

    space_type = _require_str(data, "space_type", "space")
    if space_type not in _SPACE_TYPES:
        raise ConstraintViolation(
            f"space_type must be one of {sorted(_SPACE_TYPES)}", field="space_type", constraint="space_type_check"
        )

    rack_units = data.get("rack_units")
    if rack_units is not None:
        _require_int({"rack_units": rack_units}, "rack_units", "space")

    return data


def validate_asset(data: dict[str, Any]) -> dict[str, Any]:
    """Validate asset data against dcc.assets constraints."""
    _require_str(data, "external_id", "asset")
    _require_str(data, "name", "asset")

    asset_type = _require_str(data, "asset_type", "asset")

    lifecycle_state = data.get("lifecycle_state", "planned")
    if lifecycle_state not in _ASSET_LIFECYCLE_STATES:
        raise ConstraintViolation(
            f"lifecycle_state must be one of {sorted(_ASSET_LIFECYCLE_STATES)}",
            field="lifecycle_state",
            constraint="lifecycle_state_check",
        )

    criticality = data.get("criticality", "medium")
    if criticality not in _CRITICALITY_LEVELS:
        raise ConstraintViolation(
            f"criticality must be one of {sorted(_CRITICALITY_LEVELS)}",
            field="criticality",
            constraint="criticality_check",
        )

    return data


def validate_asset_relationship(data: dict[str, Any]) -> dict[str, Any]:
    """Validate asset relationship data against dcc.asset_relationships constraints."""
    relation = _require_str(data, "relation", "asset_relationship")
    if relation not in _RELATION_TYPES:
        raise ConstraintViolation(
            f"relation must be one of {sorted(_RELATION_TYPES)}", field="relation", constraint="relation_check"
        )

    confidence = data.get("confidence")
    if confidence is not None:
        conf = _require_decimal({"confidence": confidence}, "confidence", "asset_relationship")
        if not (Decimal("0") <= conf <= Decimal("1")):
            raise ConstraintViolation(
                "confidence must be between 0 and 1", field="confidence", constraint="confidence_check"
            )

    valid_from = _require_datetime(data, "valid_from", "asset_relationship")
    valid_to = data.get("valid_to")
    if valid_to is not None:
        _require_datetime({"valid_to": valid_to}, "valid_to", "asset_relationship")
        if valid_to <= valid_from:
            raise ConstraintViolation(
                "valid_to must be after valid_from", field="valid_to", constraint="valid_range_check"
            )

    return data


def validate_connector(data: dict[str, Any]) -> dict[str, Any]:
    """Validate connector data against dcc.connectors constraints."""
    _require_str(data, "name", "connector")
    _require_str(data, "adapter_id", "connector")
    _require_str(data, "endpoint_ref", "connector")

    status = data.get("status", "draft")
    if status not in _CONNECTOR_STATUSES:
        raise ConstraintViolation(
            f"status must be one of {sorted(_CONNECTOR_STATUSES)}", field="status", constraint="status_check"
        )

    access_mode = data.get("access_mode", "read_only")
    if access_mode not in _ACCESS_MODES:
        raise ConstraintViolation(
            f"access_mode must be one of {sorted(_ACCESS_MODES)}", field="access_mode", constraint="access_mode_check"
        )

    return data


def validate_connector_run(data: dict[str, Any]) -> dict[str, Any]:
    """Validate connector run data against dcc.connector_runs constraints."""
    outcome = _require_str(data, "outcome", "connector_run")
    if outcome not in {"running", "healthy", "partial", "failed"}:
        raise ConstraintViolation(
            f"outcome must be one of running, healthy, partial, failed",
            field="outcome",
            constraint="outcome_check",
        )

    records_read = _require_int(data, "records_read", "connector_run", default=0)
    if records_read < 0:
        raise ConstraintViolation("records_read must be >= 0", field="records_read", constraint="records_read_check")

    records_rejected = _require_int(data, "records_rejected", "connector_run", default=0)
    if records_rejected < 0:
        raise ConstraintViolation(
            "records_rejected must be >= 0", field="records_rejected", constraint="records_rejected_check"
        )

    return data


# ---------------------------------------------------------------------------
# Telemetry validators
# ---------------------------------------------------------------------------


_QUALITY_STATUSES_TELEMETRY = {
    "good", "estimated", "suspect", "bad", "missing", "stale",
    "late", "replayed", "clock_skew", "out_of_range", "uncalibrated", "superseded",
}


def validate_telemetry_reading(data: dict[str, Any]) -> dict[str, Any]:
    """Validate telemetry reading data against dcc.telemetry_readings constraints."""
    _require_str(data, "source_event_id", "telemetry_reading")
    _require_str(data, "reported_unit", "telemetry_reading")
    _require_datetime(data, "observed_at", "telemetry_reading")

    quality_status = _require_str(data, "quality_status", "telemetry_reading")
    if quality_status not in _QUALITY_STATUSES_TELEMETRY:
        raise ConstraintViolation(
            f"quality_status must be one of {sorted(_QUALITY_STATUSES_TELEMETRY)}",
            field="quality_status",
            constraint="quality_status_check",
        )

    interval_start = data.get("interval_start")
    interval_end = data.get("interval_end")
    if interval_end is not None:
        if interval_start is None:
            raise ConstraintViolation(
                "interval_start is required when interval_end is set",
                field="interval_start",
                constraint="interval_check",
            )
        _require_datetime({"interval_start": interval_start}, "interval_start", "telemetry_reading")
        _require_datetime({"interval_end": interval_end}, "interval_end", "telemetry_reading")
        if interval_end <= interval_start:
            raise ConstraintViolation(
                "interval_end must be after interval_start",
                field="interval_end",
                constraint="interval_check",
            )

    value_numeric = data.get("value_numeric")
    value_text = data.get("value_text")
    if value_numeric is None and value_text is None:
        raise ConstraintViolation(
            "value_numeric or value_text is required",
            field="value_numeric",
            constraint="value_check",
        )

    return data


def validate_meter(data: dict[str, Any]) -> dict[str, Any]:
    """Validate meter data against dcc.meters constraints."""
    _require_str(data, "external_id", "meter")
    _require_str(data, "boundary", "meter")
    _require_str(data, "unit", "meter")

    direction = _require_str(data, "direction", "meter")
    if direction not in _METER_DIRECTIONS:
        raise ConstraintViolation(
            f"direction must be one of {sorted(_METER_DIRECTIONS)}",
            field="direction",
            constraint="direction_check",
        )

    multiplier = _require_decimal(data, "multiplier", "meter", default=Decimal("1"))
    if multiplier <= 0:
        raise ConstraintViolation("multiplier must be > 0", field="multiplier", constraint="multiplier_check")

    return data


def validate_metric_definition(data: dict[str, Any]) -> dict[str, Any]:
    """Validate metric definition data against dcc.metric_definitions constraints."""
    _require_str(data, "metric_key", "metric_definition")
    _require_str(data, "display_name", "metric_definition")
    _require_str(data, "quantity", "metric_definition")
    _require_str(data, "canonical_unit", "metric_definition")

    value_kind = data.get("value_kind", "gauge")
    if value_kind not in _VALUE_KINDS:
        raise ConstraintViolation(
            f"value_kind must be one of {sorted(_VALUE_KINDS)}",
            field="value_kind",
            constraint="value_kind_check",
        )

    return data


# ---------------------------------------------------------------------------
# Energy and carbon validators
# ---------------------------------------------------------------------------


def validate_tariff(data: dict[str, Any]) -> dict[str, Any]:
    """Validate tariff data against dcc.tariffs constraints."""
    _require_str(data, "provider", "tariff")
    _require_str(data, "tariff_code", "tariff")
    _require_str(data, "timezone", "tariff")
    _require_datetime(data, "valid_from", "tariff")
    _require_str(data, "version", "tariff")

    currency = _require_str(data, "currency", "tariff")
    if not _CURRENCY_RE.fullmatch(currency):
        raise ConstraintViolation("currency must be a 3-letter code", field="currency", constraint="currency_check")

    valid_to = data.get("valid_to")
    if valid_to is not None:
        _require_datetime({"valid_to": valid_to}, "valid_to", "tariff")
        if valid_to <= data["valid_from"]:
            raise ConstraintViolation(
                "valid_to must be after valid_from", field="valid_to", constraint="valid_range_check"
            )

    return data


def validate_carbon_factor(data: dict[str, Any]) -> dict[str, Any]:
    """Validate carbon factor data against dcc.carbon_factors constraints."""
    _require_str(data, "geography", "carbon_factor")
    _require_str(data, "source_ref", "carbon_factor")
    _require_str(data, "version", "carbon_factor")
    _require_datetime(data, "valid_from", "carbon_factor")

    method = _require_str(data, "method", "carbon_factor")
    if method not in _CARBON_METHODS:
        raise ConstraintViolation(
            f"method must be one of {sorted(_CARBON_METHODS)}", field="method", constraint="method_check"
        )

    factor = _require_decimal(data, "factor_kg_per_kwh", "carbon_factor")
    if factor < 0:
        raise ConstraintViolation(
            "factor_kg_per_kwh must be >= 0", field="factor_kg_per_kwh", constraint="factor_check"
        )

    valid_to = data.get("valid_to")
    if valid_to is not None:
        _require_datetime({"valid_to": valid_to}, "valid_to", "carbon_factor")
        if valid_to <= data["valid_from"]:
            raise ConstraintViolation(
                "valid_to must be after valid_from", field="valid_to", constraint="valid_range_check"
            )

    return data


def validate_energy_allocation(data: dict[str, Any]) -> dict[str, Any]:
    """Validate energy allocation data against dcc.energy_allocations constraints."""
    _require_str(data, "allocation_method", "energy_allocation")
    _require_datetime(data, "window_start", "energy_allocation")
    _require_datetime(data, "window_end", "energy_allocation")

    if data["window_end"] <= data["window_start"]:
        raise ConstraintViolation(
            "window_end must be after window_start", field="window_end", constraint="window_check"
        )

    coverage = data.get("coverage")
    if coverage is not None:
        cov = _require_decimal({"coverage": coverage}, "coverage", "energy_allocation")
        if not (Decimal("0") <= cov <= Decimal("1")):
            raise ConstraintViolation(
                "coverage must be between 0 and 1", field="coverage", constraint="coverage_check"
            )

    lower = data.get("lower_bound_kwh")
    upper = data.get("upper_bound_kwh")
    if lower is not None and upper is not None:
        lower_d = _require_decimal({"lower": lower}, "lower_bound_kwh", "energy_allocation")
        upper_d = _require_decimal({"upper": upper}, "upper_bound_kwh", "energy_allocation")
        if lower_d > upper_d:
            raise ConstraintViolation(
                "lower_bound_kwh must be <= upper_bound_kwh",
                field="lower_bound_kwh",
                constraint="bound_check",
            )

    return data


# ---------------------------------------------------------------------------
# Capacity and KPI validators
# ---------------------------------------------------------------------------


def validate_capacity_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    """Validate capacity snapshot data against dcc.capacity_snapshots constraints."""
    _require_str(data, "scenario", "capacity_snapshot")
    _require_str(data, "unit", "capacity_snapshot")
    _require_datetime(data, "observed_at", "capacity_snapshot")

    dimension = _require_str(data, "dimension", "capacity_snapshot")
    if dimension not in _CAPACITY_DIMENSIONS:
        raise ConstraintViolation(
            f"dimension must be one of {sorted(_CAPACITY_DIMENSIONS)}",
            field="dimension",
            constraint="dimension_check",
        )

    return data


def validate_kpi_definition(data: dict[str, Any]) -> dict[str, Any]:
    """Validate KPI definition data against dcc.kpi_definitions constraints."""
    _require_str(data, "metric_key", "kpi_definition")
    _require_str(data, "name", "kpi_definition")
    _require_str(data, "unit", "kpi_definition")
    _require_str(data, "formula_version", "kpi_definition")

    return data


def validate_kpi_observation(data: dict[str, Any]) -> dict[str, Any]:
    """Validate KPI observation data against dcc.kpi_observations constraints."""
    _require_datetime(data, "window_start", "kpi_observation")
    _require_datetime(data, "window_end", "kpi_observation")
    _require_datetime(data, "observed_at", "kpi_observation")
    _require_str(data, "quality_status", "kpi_observation")
    _require_str(data, "calculation_hash", "kpi_observation")

    if data["window_end"] <= data["window_start"]:
        raise ConstraintViolation(
            "window_end must be after window_start", field="window_end", constraint="window_check"
        )

    coverage = data.get("coverage")
    if coverage is not None:
        cov = _require_decimal({"coverage": coverage}, "coverage", "kpi_observation")
        if not (Decimal("0") <= cov <= Decimal("1")):
            raise ConstraintViolation(
                "coverage must be between 0 and 1", field="coverage", constraint="coverage_check"
            )

    return data


# ---------------------------------------------------------------------------
# Operations validators
# ---------------------------------------------------------------------------


_WORKFLOW_TYPES = {
    "demand", "site_diligence", "design", "procurement", "build",
    "commissioning", "onboarding", "operations", "capacity", "maintenance",
    "incident", "change", "optimization", "assurance", "refresh", "decommission",
}
_WORKFLOW_STATUSES = {"open", "in_progress", "closed", "cancelled"}
_PRIORITIES = {"low", "normal", "high", "critical"}
_APPROVAL_DECISIONS = {"pending", "approved", "rejected", "revoked", "expired"}


def validate_workflow(data: dict[str, Any]) -> dict[str, Any]:
    """Validate operational workflow data against dcc.operational_workflows constraints."""
    _require_str(data, "stage", "workflow")
    _require_str(data, "title", "workflow")
    _require_str(data, "accountable_owner", "workflow")

    workflow_type = _require_str(data, "workflow_type", "workflow")
    if workflow_type not in _WORKFLOW_TYPES:
        raise ConstraintViolation(
            f"workflow_type must be one of {sorted(_WORKFLOW_TYPES)}",
            field="workflow_type",
            constraint="workflow_type_check",
        )

    status = data.get("status", "open")
    if status not in _WORKFLOW_STATUSES:
        raise ConstraintViolation(
            f"status must be one of {sorted(_WORKFLOW_STATUSES)}", field="status", constraint="status_check"
        )

    priority = data.get("priority", "normal")
    if priority not in _PRIORITIES:
        raise ConstraintViolation(
            f"priority must be one of {sorted(_PRIORITIES)}", field="priority", constraint="priority_check"
        )

    return data


def validate_workflow_task(data: dict[str, Any]) -> dict[str, Any]:
    """Validate workflow task data against dcc.workflow_tasks constraints."""
    _require_int(data, "sequence_no", "workflow_task")
    _require_str(data, "title", "workflow_task")

    status = data.get("status", "pending")
    if status not in {"pending", "in_progress", "completed", "cancelled"}:
        raise ConstraintViolation("invalid task status", field="status", constraint="status_check")

    return data


def validate_approval(data: dict[str, Any]) -> dict[str, Any]:
    """Validate approval data against dcc.approvals constraints."""
    _require_str(data, "approver_ref", "approval")
    _require_str(data, "scope_digest", "approval")
    _require_str(data, "reason", "approval")

    decision = _require_str(data, "decision", "approval")
    if decision not in _APPROVAL_DECISIONS:
        raise ConstraintViolation(
            f"decision must be one of {sorted(_APPROVAL_DECISIONS)}",
            field="decision",
            constraint="decision_check",
        )

    return data


def validate_work_order(data: dict[str, Any]) -> dict[str, Any]:
    """Validate work order data against dcc.work_orders constraints."""
    _require_str(data, "work_type", "work_order")
    _require_str(data, "status", "work_order")
    _require_str(data, "priority", "work_order")

    return data


def validate_incident(data: dict[str, Any]) -> dict[str, Any]:
    """Validate incident data against dcc.incidents constraints."""
    _require_str(data, "severity", "incident")
    _require_str(data, "state", "incident")

    root_cause_confidence = data.get("root_cause_confidence")
    if root_cause_confidence is not None:
        rcc = _require_decimal(
            {"root_cause_confidence": root_cause_confidence}, "root_cause_confidence", "incident"
        )
        if not (Decimal("0") <= rcc <= Decimal("1")):
            raise ConstraintViolation(
                "root_cause_confidence must be between 0 and 1",
                field="root_cause_confidence",
                constraint="root_cause_confidence_check",
            )

    return data


def validate_change_record(data: dict[str, Any]) -> dict[str, Any]:
    """Validate change record data against dcc.change_records constraints."""
    _require_str(data, "risk_class", "change_record")
    _require_str(data, "approval_state", "change_record")

    return data


def validate_procedure(data: dict[str, Any]) -> dict[str, Any]:
    """Validate procedure data against dcc.procedures constraints."""
    _require_str(data, "procedure_key", "procedure")
    _require_str(data, "version", "procedure")
    _require_str(data, "title", "procedure")
    _require_str(data, "domain", "procedure")
    _require_str(data, "risk_class", "procedure")

    status = data.get("status", "draft")
    if status not in {"draft", "active", "retired"}:
        raise ConstraintViolation("invalid procedure status", field="status", constraint="status_check")

    return data


# ---------------------------------------------------------------------------
# Workload validators
# ---------------------------------------------------------------------------


def validate_workload(data: dict[str, Any]) -> dict[str, Any]:
    """Validate workload data against dcc.workloads constraints."""
    _require_str(data, "external_id", "workload")
    _require_str(data, "name", "workload")
    _require_str(data, "service_class", "workload")

    status = data.get("status", "active")
    if status not in {"active", "inactive", "deprecated"}:
        raise ConstraintViolation("invalid workload status", field="status", constraint="status_check")

    return data


def validate_deployment(data: dict[str, Any]) -> dict[str, Any]:
    """Validate deployment data against dcc.deployments constraints."""
    _require_datetime(data, "valid_from", "deployment")

    allocation_method = _require_str(data, "allocation_method", "deployment")
    if allocation_method not in _DEPLOYMENT_ALLOCATION_METHODS:
        raise ConstraintViolation(
            f"allocation_method must be one of {sorted(_DEPLOYMENT_ALLOCATION_METHODS)}",
            field="allocation_method",
            constraint="allocation_method_check",
        )

    allocation_fraction = data.get("allocation_fraction")
    if allocation_fraction is not None:
        af = _require_decimal(
            {"allocation_fraction": allocation_fraction}, "allocation_fraction", "deployment"
        )
        if not (Decimal("0") <= af <= Decimal("1")):
            raise ConstraintViolation(
                "allocation_fraction must be between 0 and 1",
                field="allocation_fraction",
                constraint="allocation_fraction_check",
            )

    valid_to = data.get("valid_to")
    if valid_to is not None:
        _require_datetime({"valid_to": valid_to}, "valid_to", "deployment")
        if valid_to <= data["valid_from"]:
            raise ConstraintViolation(
                "valid_to must be after valid_from", field="valid_to", constraint="valid_range_check"
            )

    return data


# ---------------------------------------------------------------------------
# Evidence validators
# ---------------------------------------------------------------------------


def validate_evidence_event(data: dict[str, Any]) -> dict[str, Any]:
    """Validate evidence event data against dcc.evidence_events constraints."""
    _require_str(data, "event_type", "evidence_event")
    _require_datetime(data, "occurred_at", "evidence_event")
    _require_str(data, "event_hash", "evidence_event")

    return data


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_str(data: dict[str, Any], field: str, entity: str, default: str | None = None) -> str:
    """Require a non-empty string field."""
    value = data.get(field, default)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{entity}.{field} is required and must be a non-empty string", field=field)
    return value


def _require_int(data: dict[str, Any], field: str, entity: str, default: int | None = None) -> int:
    """Require an integer field."""
    value = data.get(field, default)
    if value is None:
        raise ValidationError(f"{entity}.{field} is required", field=field)
    if isinstance(value, bool):
        raise ValidationError(f"{entity}.{field} must be an integer", field=field)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{entity}.{field} must be an integer", field=field) from None


def _require_decimal(
    data: dict[str, Any], field: str, entity: str, default: Decimal | None = None
) -> Decimal:
    """Require a decimal-compatible field."""
    value = data.get(field, default)
    if value is None:
        raise ValidationError(f"{entity}.{field} is required", field=field)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f"{entity}.{field} must be a valid number", field=field) from None


def _require_date(data: dict[str, Any], field: str, entity: str) -> date:
    """Require a date field (YYYY-MM-DD)."""
    value = data.get(field)
    if value is None:
        raise ValidationError(f"{entity}.{field} is required", field=field)
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValidationError(
                f"{entity}.{field} must be a valid date (YYYY-MM-DD)", field=field
            ) from None
    raise ValidationError(f"{entity}.{field} must be a valid date", field=field)


def _require_datetime(data: dict[str, Any], field: str, entity: str) -> datetime:
    """Require a datetime field."""
    value = data.get(field)
    if value is None:
        raise ValidationError(f"{entity}.{field} is required", field=field)
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValidationError(
                f"{entity}.{field} must be a valid datetime", field=field
            ) from None
    raise ValidationError(f"{entity}.{field} must be a valid datetime", field=field)


# ---------------------------------------------------------------------------
# SchemaValidator — generic entity validator
# ---------------------------------------------------------------------------


class SchemaValidator:
    """Generic schema validator that validates entities against field definitions.

    Each field definition is a dict with:
        - type: expected Python type (str, int, float, bool, dict, list)
        - required: whether the field must be present
        - min_length / max_length: for strings
        - min_value / max_value: for numbers
        - pattern: regex pattern for strings
        - enum: set of allowed values
        - validator: custom validation function
    """

    def __init__(self, entity_name: str, fields: dict[str, dict[str, Any]]) -> None:
        self.entity_name = entity_name
        self.fields = fields

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate data against the schema definition."""
        if not isinstance(data, dict):
            raise ValidationError(f"{self.entity_name} data must be an object")

        for field_name, rules in self.fields.items():
            value = data.get(field_name)
            is_required = rules.get("required", False)

            if value is None:
                if is_required:
                    raise ValidationError(
                        f"{self.entity_name}.{field_name} is required", field=field_name
                    )
                continue

            expected_type = rules.get("type")
            if expected_type and not isinstance(value, expected_type):
                raise ValidationError(
                    f"{self.entity_name}.{field_name} must be of type {expected_type.__name__}",
                    field=field_name,
                )

            if isinstance(value, str):
                min_len = rules.get("min_length")
                max_len = rules.get("max_length")
                if min_len is not None and len(value) < min_len:
                    raise ConstraintViolation(
                        f"{self.entity_name}.{field_name} must be at least {min_len} characters",
                        field=field_name,
                        constraint="min_length",
                    )
                if max_len is not None and len(value) > max_len:
                    raise ConstraintViolation(
                        f"{self.entity_name}.{field_name} must be at most {max_len} characters",
                        field=field_name,
                        constraint="max_length",
                    )
                pattern = rules.get("pattern")
                if pattern and not re.fullmatch(pattern, value):
                    raise ConstraintViolation(
                        f"{self.entity_name}.{field_name} does not match required pattern",
                        field=field_name,
                        constraint="pattern",
                    )

            if isinstance(value, (int, float)) and not isinstance(value, bool):
                min_val = rules.get("min_value")
                max_val = rules.get("max_value")
                if min_val is not None and value < min_val:
                    raise ConstraintViolation(
                        f"{self.entity_name}.{field_name} must be >= {min_val}",
                        field=field_name,
                        constraint="min_value",
                    )
                if max_val is not None and value > max_val:
                    raise ConstraintViolation(
                        f"{self.entity_name}.{field_name} must be <= {max_val}",
                        field=field_name,
                        constraint="max_value",
                    )

            enum_values = rules.get("enum")
            if enum_values and value not in enum_values:
                raise ConstraintViolation(
                    f"{self.entity_name}.{field_name} must be one of {sorted(enum_values)}",
                    field=field_name,
                    constraint="enum",
                )

            custom_validator = rules.get("validator")
            if custom_validator:
                custom_validator(value)

        return data


# ---------------------------------------------------------------------------
# Pre-built schema definitions for common entities
# ---------------------------------------------------------------------------

TENANT_SCHEMA = SchemaValidator("tenant", {
    "slug": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "name": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "status": {"type": str, "required": True, "enum": _TENANT_STATUSES},
    "data_region": {"type": str, "required": False, "max_length": 100},
})

ASSET_SCHEMA = SchemaValidator("asset", {
    "external_id": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "asset_type": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "name": {"type": str, "required": True, "min_length": 1, "max_length": 300},
    "manufacturer": {"type": str, "required": False, "max_length": 200},
    "model": {"type": str, "required": False, "max_length": 200},
    "serial_number": {"type": str, "required": False, "max_length": 200},
    "lifecycle_state": {"type": str, "required": True, "enum": _ASSET_LIFECYCLE_STATES},
    "criticality": {"type": str, "required": True, "enum": _CRITICALITY_LEVELS},
})

FACILITY_SCHEMA = SchemaValidator("facility", {
    "code": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "name": {"type": str, "required": True, "min_length": 1, "max_length": 300},
    "facility_type": {"type": str, "required": True, "enum": _FACILITY_TYPES},
    "status": {"type": str, "required": True, "enum": {"active", "inactive", "decommissioned"}},
    "design_it_kw": {"type": (int, float), "required": False, "min_value": 0},
    "design_facility_kw": {"type": (int, float), "required": False, "min_value": 0},
})

CONNECTOR_SCHEMA = SchemaValidator("connector", {
    "name": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "vendor": {"type": str, "required": False, "max_length": 200},
    "product": {"type": str, "required": False, "max_length": 200},
    "adapter_id": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "adapter_version": {"type": str, "required": False, "max_length": 100},
    "endpoint_ref": {"type": str, "required": True, "min_length": 1, "max_length": 500},
    "status": {"type": str, "required": True, "enum": _CONNECTOR_STATUSES},
    "access_mode": {"type": str, "required": True, "enum": _ACCESS_MODES},
})

WORKFLOW_SCHEMA = SchemaValidator("workflow", {
    "workflow_type": {"type": str, "required": True, "enum": _WORKFLOW_TYPES},
    "stage": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "status": {"type": str, "required": True, "enum": _WORKFLOW_STATUSES},
    "priority": {"type": str, "required": True, "enum": _PRIORITIES},
    "title": {"type": str, "required": True, "min_length": 1, "max_length": 500},
    "accountable_owner": {"type": str, "required": True, "min_length": 1, "max_length": 200},
})

ESTIMATE_PROJECT_SCHEMA = SchemaValidator("estimate_project", {
    "project_code": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "name": {"type": str, "required": True, "min_length": 1, "max_length": 300},
    "lifecycle_phase": {"type": str, "required": True, "enum": _LIFECYCLE_PHASES},
    "status": {"type": str, "required": True, "enum": _ESTIMATE_STATUSES},
    "currency": {"type": str, "required": True, "pattern": r"^[A-Z]{3}$"},
    "geography": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "horizon_months": {"type": int, "required": True, "min_value": 1},
    "discount_rate": {"type": (int, float), "required": True, "min_value": 0, "max_value": 0.999999},
    "contingency_pct": {"type": (int, float), "required": True, "min_value": 0, "max_value": 1},
})

PRICE_OBSERVATION_SCHEMA = SchemaValidator("price_observation", {
    "item_code": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "description": {"type": str, "required": True, "min_length": 1, "max_length": 1000},
    "category": {"type": str, "required": True, "enum": _PRICE_CATEGORIES},
    "quantity_unit": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "unit_price": {"type": (int, float), "required": True, "min_value": 0},
    "currency": {"type": str, "required": True, "pattern": r"^[A-Z]{3}$"},
    "geography": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "delivery_basis": {"type": str, "required": True, "enum": _DELIVERY_BASIS},
    "source_kind": {"type": str, "required": True, "enum": _SOURCE_KINDS},
    "source_name": {"type": str, "required": True, "min_length": 1, "max_length": 300},
    "source_ref": {"type": str, "required": True, "min_length": 1, "max_length": 500},
    "confidence": {"type": (int, float), "required": True, "min_value": 0, "max_value": 1},
    "fx_to_book": {"type": (int, float), "required": True, "min_value": 0.0000000001},
    "normalized_unit_price": {"type": (int, float), "required": True, "min_value": 0},
    "quality_status": {"type": str, "required": True, "enum": _QUALITY_STATUSES},
})

COST_BOOK_SCHEMA = SchemaValidator("cost_book", {
    "name": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "version": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "status": {"type": str, "required": True, "enum": _COST_BOOK_STATUSES},
    "currency": {"type": str, "required": True, "pattern": r"^[A-Z]{3}$"},
    "geography": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "price_basis": {"type": str, "required": True, "enum": _PRICE_BASIS},
})

CAPACITY_SNAPSHOT_SCHEMA = SchemaValidator("capacity_snapshot", {
    "scenario": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "dimension": {"type": str, "required": True, "enum": _CAPACITY_DIMENSIONS},
    "unit": {"type": str, "required": True, "min_length": 1, "max_length": 50},
    "quality_status": {"type": str, "required": True, "min_length": 1, "max_length": 50},
})

TELEMETRY_READING_SCHEMA = SchemaValidator("telemetry_reading", {
    "source_event_id": {"type": str, "required": True, "min_length": 1, "max_length": 500},
    "reported_unit": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "quality_status": {"type": str, "required": True, "enum": _QUALITY_STATUSES_TELEMETRY},
})

EVIDENCE_EVENT_SCHEMA = SchemaValidator("evidence_event", {
    "event_type": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "event_hash": {"type": str, "required": True, "min_length": 1, "max_length": 200},
})

COST_ACTUAL_SCHEMA = SchemaValidator("cost_actual", {
    "cost_type": {"type": str, "required": True, "enum": _COST_TYPES},
    "currency": {"type": str, "required": True, "pattern": r"^[A-Z]{3}$"},
    "amount": {"type": (int, float), "required": True},
    "source_system": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "source_ref": {"type": str, "required": True, "min_length": 1, "max_length": 500},
    "accrual_state": {"type": str, "required": True, "enum": _ACCRUAL_STATES},
})

COST_ALLOCATION_SCHEMA = SchemaValidator("cost_allocation", {
    "allocation_basis": {"type": str, "required": True, "enum": _ALLOCATION_BASIS},
    "currency": {"type": str, "required": True, "pattern": r"^[A-Z]{3}$"},
    "allocation_fraction": {"type": (int, float), "required": True, "min_value": 0, "max_value": 1},
    "method_version": {"type": str, "required": True, "min_length": 1, "max_length": 100},
})

ENERGY_ALLOCATION_SCHEMA = SchemaValidator("energy_allocation", {
    "allocation_method": {"type": str, "required": True, "min_length": 1, "max_length": 100},
})

WORKLOAD_SCHEMA = SchemaValidator("workload", {
    "external_id": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "name": {"type": str, "required": True, "min_length": 1, "max_length": 300},
    "service_class": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "status": {"type": str, "required": True, "enum": {"active", "inactive", "deprecated"}},
})

DEPLOYMENT_SCHEMA = SchemaValidator("deployment", {
    "allocation_method": {"type": str, "required": True, "enum": _DEPLOYMENT_ALLOCATION_METHODS},
    "allocation_fraction": {"type": (int, float), "required": False, "min_value": 0, "max_value": 1},
})

INCIDENT_SCHEMA = SchemaValidator("incident", {
    "severity": {"type": str, "required": True, "min_length": 1, "max_length": 50},
    "state": {"type": str, "required": True, "min_length": 1, "max_length": 50},
})

CHANGE_RECORD_SCHEMA = SchemaValidator("change_record", {
    "risk_class": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "approval_state": {"type": str, "required": True, "min_length": 1, "max_length": 100},
})

WORK_ORDER_SCHEMA = SchemaValidator("work_order", {
    "work_type": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "status": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "priority": {"type": str, "required": True, "min_length": 1, "max_length": 50},
})

APPROVAL_SCHEMA = SchemaValidator("approval", {
    "approver_ref": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "decision": {"type": str, "required": True, "enum": _APPROVAL_DECISIONS},
    "scope_digest": {"type": str, "required": True, "min_length": 1, "max_length": 500},
    "reason": {"type": str, "required": True, "min_length": 1, "max_length": 1000},
})

WORKFLOW_TASK_SCHEMA = SchemaValidator("workflow_task", {
    "sequence_no": {"type": int, "required": True, "min_value": 1},
    "title": {"type": str, "required": True, "min_length": 1, "max_length": 500},
    "status": {"type": str, "required": True, "enum": {"pending", "in_progress", "completed", "cancelled"}},
})

PROCEDURE_SCHEMA = SchemaValidator("procedure", {
    "procedure_key": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "version": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "title": {"type": str, "required": True, "min_length": 1, "max_length": 300},
    "domain": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "risk_class": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "status": {"type": str, "required": True, "enum": {"draft", "active", "retired"}},
})

TARIFF_SCHEMA = SchemaValidator("tariff", {
    "provider": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "tariff_code": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "currency": {"type": str, "required": True, "pattern": r"^[A-Z]{3}$"},
    "timezone": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "version": {"type": str, "required": True, "min_length": 1, "max_length": 100},
})

CARBON_FACTOR_SCHEMA = SchemaValidator("carbon_factor", {
    "geography": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "method": {"type": str, "required": True, "enum": _CARBON_METHODS},
    "factor_kg_per_kwh": {"type": (int, float), "required": True, "min_value": 0},
    "source_ref": {"type": str, "required": True, "min_length": 1, "max_length": 500},
    "version": {"type": str, "required": True, "min_length": 1, "max_length": 100},
})

METER_SCHEMA = SchemaValidator("meter", {
    "external_id": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "boundary": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "direction": {"type": str, "required": True, "enum": _METER_DIRECTIONS},
    "unit": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "multiplier": {"type": (int, float), "required": True, "min_value": 0.000000001},
})

METRIC_DEFINITION_SCHEMA = SchemaValidator("metric_definition", {
    "metric_key": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "display_name": {"type": str, "required": True, "min_length": 1, "max_length": 300},
    "quantity": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "canonical_unit": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "value_kind": {"type": str, "required": True, "enum": _VALUE_KINDS},
})

KPI_DEFINITION_SCHEMA = SchemaValidator("kpi_definition", {
    "metric_key": {"type": str, "required": True, "min_length": 1, "max_length": 200},
    "name": {"type": str, "required": True, "min_length": 1, "max_length": 300},
    "unit": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "formula_version": {"type": str, "required": True, "min_length": 1, "max_length": 100},
})

CONNECTOR_RUN_SCHEMA = SchemaValidator("connector_run", {
    "outcome": {"type": str, "required": True, "enum": {"running", "healthy", "partial", "failed"}},
    "records_read": {"type": int, "required": True, "min_value": 0},
    "records_rejected": {"type": int, "required": True, "min_value": 0},
})

SPACE_SCHEMA = SchemaValidator("space", {
    "code": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "name": {"type": str, "required": True, "min_length": 1, "max_length": 300},
    "space_type": {"type": str, "required": True, "enum": _SPACE_TYPES},
    "rack_units": {"type": int, "required": False, "min_value": 0},
})

ASSET_RELATIONSHIP_SCHEMA = SchemaValidator("asset_relationship", {
    "relation": {"type": str, "required": True, "enum": _RELATION_TYPES},
    "confidence": {"type": (int, float), "required": False, "min_value": 0, "max_value": 1},
})

SITE_SCHEMA = SchemaValidator("site", {
    "code": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "name": {"type": str, "required": True, "min_length": 1, "max_length": 300},
    "country_code": {"type": str, "required": False, "pattern": r"^[A-Z]{2}$"},
    "timezone": {"type": str, "required": True, "min_length": 1, "max_length": 100},
    "latitude": {"type": (int, float), "required": False, "min_value": -90, "max_value": 90},
    "longitude": {"type": (int, float), "required": False, "min_value": -180, "max_value": 180},
})
