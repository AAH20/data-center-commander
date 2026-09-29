"""Energy price forecasting from tariff structures.

Supports flat-rate, time-of-use (TOU), tiered, and demand-charge tariff models.
All monetary values use Decimal for precision. Forecasts are deterministic
projections of tariff-defined prices — not market predictions.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ZERO = Decimal("0")
ONE = Decimal("1")
HOURS_PER_DAY = 24
DAYS_PER_MONTH = 30
MONTHS_PER_YEAR = 12

# Time-of-use period definitions: (name, start_hour, end_hour)
# end_hour is exclusive
TOU_PERIODS: tuple[tuple[str, int, int], ...] = (
    ("off_peak", 0, 6),
    ("shoulder", 6, 12),
    ("on_peak", 12, 18),
    ("shoulder_evening", 18, 22),
    ("off_peak_night", 22, 24),
)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TariffSpec:
    """Validated tariff specification for energy price forecasting.

    All rates are in the tariff currency per kWh (energy) or per kW (demand).
    """

    currency: str
    timezone: str
    energy_rates: dict[str, Decimal] = field(default_factory=dict)
    demand_rate: Decimal | None = None
    fixed_monthly_charge: Decimal = ZERO
    tier_thresholds: list[Decimal] = field(default_factory=list)
    tier_rates: list[Decimal] = field(default_factory=list)
    tou_schedule: dict[int, str] = field(default_factory=dict)
    valid_from: dt.datetime | None = None
    valid_to: dt.datetime | None = None
    source_ref: str = ""
    version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "currency": self.currency,
            "timezone": self.timezone,
            "energy_rates": {k: str(v) for k, v in self.energy_rates.items()},
            "demand_rate": str(self.demand_rate) if self.demand_rate is not None else None,
            "fixed_monthly_charge": str(self.fixed_monthly_charge),
            "tier_thresholds": [str(t) for t in self.tier_thresholds],
            "tier_rates": [str(r) for r in self.tier_rates],
            "tou_schedule": {str(k): v for k, v in self.tou_schedule.items()},
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "source_ref": self.source_ref,
            "version": self.version,
        }


@dataclass(frozen=True)
class PricePoint:
    """A single forecast price point."""

    timestamp: dt.datetime
    period: str
    energy_rate: Decimal
    demand_rate: Decimal | None
    estimated_cost: Decimal
    currency: str
    is_peak: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "period": self.period,
            "energy_rate": str(self.energy_rate),
            "demand_rate": str(self.demand_rate) if self.demand_rate is not None else None,
            "estimated_cost": str(self.estimated_cost),
            "currency": self.currency,
            "is_peak": self.is_peak,
        }


@dataclass
class ForecastResult:
    """Aggregated forecast result."""

    tariff: TariffSpec
    points: list[PricePoint]
    total_energy_kwh: Decimal
    total_cost: Decimal
    average_rate: Decimal
    peak_rate: Decimal
    off_peak_rate: Decimal
    monthly_fixed_cost: Decimal
    annual_projected_cost: Decimal
    currency: str
    generated_at: dt.datetime
    method: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tariff": self.tariff.to_dict(),
            "points": [p.to_dict() for p in self.points],
            "total_energy_kwh": str(self.total_energy_kwh),
            "total_cost": str(self.total_cost),
            "average_rate": str(self.average_rate),
            "peak_rate": str(self.peak_rate),
            "off_peak_rate": str(self.off_peak_rate),
            "monthly_fixed_cost": str(self.monthly_fixed_cost),
            "annual_projected_cost": str(self.annual_projected_cost),
            "currency": self.currency,
            "generated_at": self.generated_at.isoformat(),
            "method": self.method,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _parse_decimal(value: Any, field_name: str) -> Decimal:
    """Parse a value into a non-negative Decimal."""
    if value is None:
        raise ValueError(f"{field_name} is required")
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number, not a boolean")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{field_name} must be a valid number") from None
    if not d.is_finite():
        raise ValueError(f"{field_name} must be finite")
    if d < ZERO:
        raise ValueError(f"{field_name} must be non-negative")
    return d


def _parse_optional_decimal(value: Any, field_name: str) -> Decimal | None:
    """Parse an optional value into a non-negative Decimal, or None."""
    if value is None:
        return None
    return _parse_decimal(value, field_name)


def validate_tariff_spec(spec: dict[str, Any]) -> TariffSpec:
    """Validate and parse a raw tariff specification dict into a TariffSpec.

    Expected spec format::

        {
            "currency": "USD",
            "timezone": "America/New_York",
            "energy_rates": {"flat": "0.12", "on_peak": "0.25", "off_peak": "0.08"},
            "demand_rate": "15.00",           # per kW, optional
            "fixed_monthly_charge": "50.00",  # optional
            "tier_thresholds": ["500", "1000"],  # kWh thresholds
            "tier_rates": ["0.10", "0.12", "0.15"],  # rate per tier
            "tou_schedule": {"0": "off_peak", "6": "shoulder", ...},
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2026-12-31T23:59:59Z",
            "source_ref": "utility-tariff-2026",
            "version": "1",
        }
    """
    if not isinstance(spec, dict):
        raise ValueError("tariff spec must be a dict")

    currency = str(spec.get("currency", "")).strip().upper()
    if not currency or len(currency) != 3:
        raise ValueError("currency must be a 3-letter ISO code")

    timezone = str(spec.get("timezone", "")).strip()
    if not timezone or len(timezone) > 64:
        raise ValueError("timezone is required and must be at most 64 characters")

    # Energy rates
    raw_rates = spec.get("energy_rates", {})
    if not isinstance(raw_rates, dict) or not raw_rates:
        raise ValueError("energy_rates must be a non-empty dict")
    energy_rates: dict[str, Decimal] = {}
    for key, val in raw_rates.items():
        key = str(key).strip()
        if not key or len(key) > 32:
            raise ValueError(f"energy rate key must be 1-32 characters: {key!r}")
        energy_rates[key] = _parse_decimal(val, f"energy_rates[{key}]")

    # Demand rate
    demand_rate = _parse_optional_decimal(spec.get("demand_rate"), "demand_rate")

    # Fixed monthly charge
    fixed_monthly = _parse_decimal(
        spec.get("fixed_monthly_charge", "0"), "fixed_monthly_charge"
    )

    # Tiered rates
    raw_thresholds = spec.get("tier_thresholds", [])
    raw_tier_rates = spec.get("tier_rates", [])
    if not isinstance(raw_thresholds, list) or not isinstance(raw_tier_rates, list):
        raise ValueError("tier_thresholds and tier_rates must be lists")
    tier_thresholds: list[Decimal] = []
    for i, t in enumerate(raw_thresholds):
        tier_thresholds.append(_parse_decimal(t, f"tier_thresholds[{i}]"))
    tier_rates: list[Decimal] = []
    for i, r in enumerate(raw_tier_rates):
        tier_rates.append(_parse_decimal(r, f"tier_rates[{i}]"))
    if tier_thresholds or tier_rates:
        if len(tier_rates) != len(tier_thresholds) + 1:
            raise ValueError(
                f"tier_rates must have exactly one more entry than tier_thresholds "
                f"({len(tier_rates)} rates vs {len(tier_thresholds)} thresholds)"
            )
    # Thresholds must be strictly increasing
    for i in range(1, len(tier_thresholds)):
        if tier_thresholds[i] <= tier_thresholds[i - 1]:
            raise ValueError("tier_thresholds must be strictly increasing")

    # TOU schedule
    raw_tou = spec.get("tou_schedule", {})
    tou_schedule: dict[int, str] = {}
    if isinstance(raw_tou, dict) and raw_tou:
        for hour_str, period in raw_tou.items():
            try:
                hour = int(hour_str)
            except (ValueError, TypeError):
                raise ValueError(f"tou_schedule keys must be integer hours: {hour_str!r}") from None
            if not 0 <= hour < HOURS_PER_DAY:
                raise ValueError(f"tou_schedule hour must be 0-23: {hour}")
            period = str(period).strip()
            if not period or len(period) > 32:
                raise ValueError(f"tou_schedule period must be 1-32 characters: {period!r}")
            tou_schedule[hour] = period

    # Validity window
    valid_from = _parse_datetime(spec.get("valid_from"), "valid_from")
    valid_to = _parse_datetime(spec.get("valid_to"), "valid_to")
    if valid_from and valid_to and valid_to <= valid_from:
        raise ValueError("valid_to must be after valid_from")

    source_ref = str(spec.get("source_ref", "")).strip()
    if len(source_ref) > 256:
        raise ValueError("source_ref must be at most 256 characters")

    version = str(spec.get("version", "1")).strip()
    if not version or len(version) > 32:
        raise ValueError("version must be 1-32 characters")

    return TariffSpec(
        currency=currency,
        timezone=timezone,
        energy_rates=energy_rates,
        demand_rate=demand_rate,
        fixed_monthly_charge=fixed_monthly,
        tier_thresholds=tier_thresholds,
        tier_rates=tier_rates,
        tou_schedule=tou_schedule,
        valid_from=valid_from,
        valid_to=valid_to,
        source_ref=source_ref,
        version=version,
    )


def _parse_datetime(value: Any, field_name: str) -> dt.datetime | None:
    """Parse an ISO datetime string or return None."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO datetime string")
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{field_name} must be a valid ISO datetime") from None


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------


def _get_period_for_hour(hour: int, tou_schedule: dict[int, str]) -> str:
    """Look up the TOU period for a given hour."""
    if hour in tou_schedule:
        return tou_schedule[hour]
    # Default TOU mapping
    for name, start, end in TOU_PERIODS:
        if start <= hour < end:
            return name
    return "flat"


def _get_rate_for_period(
    period: str,
    energy_rates: dict[str, Decimal],
    tier_rates: list[Decimal],
    cumulative_kwh: Decimal,
    tier_thresholds: list[Decimal],
) -> Decimal:
    """Get the applicable energy rate for a period, considering tiered rates."""
    # If tiered rates are defined, use cumulative consumption to pick the tier
    if tier_rates:
        tier_idx = 0
        for i, threshold in enumerate(tier_thresholds):
            if cumulative_kwh >= threshold:
                tier_idx = i + 1
        return tier_rates[tier_idx]
    # Otherwise use the period-specific rate, falling back to flat
    if period in energy_rates:
        return energy_rates[period]
    if period == "off_peak_night" and "off_peak" in energy_rates:
        return energy_rates["off_peak"]
    if period == "shoulder_evening" and "shoulder" in energy_rates:
        return energy_rates["shoulder"]
    return energy_rates.get("flat", ZERO)


def _estimate_hourly_kwh(
    hour: int,
    period: str,
    daily_kwh: Decimal,
) -> Decimal:
    """Estimate hourly energy consumption based on period type.

    Uses a simple load curve model:
    - on_peak: 1.5x average
    - shoulder: 1.0x average
    - off_peak: 0.5x average
    """
    avg_hourly = daily_kwh / HOURS_PER_DAY
    multipliers = {
        "on_peak": Decimal("1.5"),
        "shoulder": Decimal("1.0"),
        "shoulder_evening": Decimal("1.0"),
        "off_peak": Decimal("0.5"),
        "off_peak_night": Decimal("0.5"),
        "flat": Decimal("1.0"),
    }
    multiplier = multipliers.get(period, ONE)
    return (avg_hourly * multiplier).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def forecast_prices(
    tariff: TariffSpec,
    *,
    daily_kwh: Decimal | str | float,
    start: dt.datetime | None = None,
    days: int = 30,
    include_demand: bool = False,
    peak_demand_kw: Decimal | str | float | None = None,
) -> ForecastResult:
    """Generate an energy price forecast from a tariff specification.

    Args:
        tariff: Validated TariffSpec.
        daily_kwh: Estimated daily energy consumption in kWh.
        start: Start datetime for the forecast. Defaults to now (UTC).
        days: Number of days to forecast (1-365).
        include_demand: Whether to include demand charges in the cost estimate.
        peak_demand_kw: Peak demand in kW (required if include_demand is True).

    Returns:
        ForecastResult with hourly price points and aggregated totals.
    """
    if not 1 <= days <= 365:
        raise ValueError("forecast days must be 1-365")

    daily_kwh_dec = _parse_decimal(daily_kwh, "daily_kwh")
    if daily_kwh_dec == ZERO:
        raise ValueError("daily_kwh must be greater than zero")

    if start is None:
        start = dt.datetime.now(dt.timezone.utc)
    elif start.tzinfo is None:
        start = start.replace(tzinfo=dt.timezone.utc)

    demand_rate = ZERO
    if include_demand:
        if tariff.demand_rate is None:
            raise ValueError("tariff has no demand_rate but include_demand is True")
        if peak_demand_kw is None:
            raise ValueError("peak_demand_kw is required when include_demand is True")
        peak_kw = _parse_decimal(peak_demand_kw, "peak_demand_kw")
        demand_rate = tariff.demand_rate * peak_kw

    points: list[PricePoint] = []
    total_energy = ZERO
    total_energy_cost = ZERO
    cumulative_kwh = ZERO

    # Generate hourly price points
    for day_offset in range(days):
        for hour in range(HOURS_PER_DAY):
            ts = start + dt.timedelta(days=day_offset, hours=hour)
            period = _get_period_for_hour(hour, tariff.tou_schedule)
            rate = _get_rate_for_period(
                period, tariff.energy_rates, tariff.tier_rates, cumulative_kwh, tariff.tier_thresholds
            )
            hourly_kwh = _estimate_hourly_kwh(hour, period, daily_kwh_dec)
            energy_cost = (hourly_kwh * rate).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

            points.append(
                PricePoint(
                    timestamp=ts,
                    period=period,
                    energy_rate=rate,
                    demand_rate=demand_rate if include_demand else None,
                    estimated_cost=energy_cost,
                    currency=tariff.currency,
                    is_peak=period == "on_peak",
                )
            )
            total_energy += hourly_kwh
            total_energy_cost += energy_cost
            cumulative_kwh += hourly_kwh

    # Add fixed monthly charge (prorated for the forecast period)
    months = Decimal(days) / Decimal(DAYS_PER_MONTH)
    fixed_cost = (tariff.fixed_monthly_charge * months).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # Demand charges (monthly)
    demand_cost = ZERO
    if include_demand and demand_rate > ZERO:
        demand_cost = (demand_rate * months).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    total_cost = total_energy_cost + fixed_cost + demand_cost

    # Compute summary statistics
    rates = [p.energy_rate for p in points]
    peak_rates = [p.energy_rate for p in points if p.is_peak]
    off_peak_rates = [
        p.energy_rate for p in points if p.period in ("off_peak", "off_peak_night")
    ]

    avg_rate = (total_energy_cost / total_energy).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    ) if total_energy > ZERO else ZERO
    peak_rate = max(peak_rates) if peak_rates else max(rates)
    off_peak_rate = min(off_peak_rates) if off_peak_rates else min(rates)

    # Annual projection
    annual_factor = Decimal(365) / Decimal(days)
    annual_cost = (total_cost * annual_factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Build notes
    notes: list[str] = []
    if tariff.tier_rates:
        notes.append("Tiered rates applied based on cumulative consumption")
    if tariff.tou_schedule:
        notes.append("Time-of-use schedule applied")
    if include_demand:
        notes.append(f"Demand charges included at {tariff.demand_rate}/kW/month")
    if tariff.fixed_monthly_charge > ZERO:
        notes.append(f"Fixed monthly charge of {tariff.fixed_monthly_charge} included")
    notes.append("Forecast is a tariff-structure projection, not a market prediction")

    has_tou_rates = len(tariff.energy_rates) > 1 or (
        len(tariff.energy_rates) == 1 and "flat" not in tariff.energy_rates
    )
    method = "tiered" if tariff.tier_rates else ("tou" if has_tou_rates else "flat")

    return ForecastResult(
        tariff=tariff,
        points=points,
        total_energy_kwh=total_energy.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP),
        total_cost=total_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        average_rate=avg_rate,
        peak_rate=peak_rate,
        off_peak_rate=off_peak_rate,
        monthly_fixed_cost=tariff.fixed_monthly_charge,
        annual_projected_cost=annual_cost,
        currency=tariff.currency,
        generated_at=dt.datetime.now(dt.timezone.utc),
        method=method,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Convenience: build TariffSpec from common tariff formats
# ---------------------------------------------------------------------------


def build_flat_tariff(
    *,
    currency: str,
    timezone: str,
    rate: Decimal | str | float,
    demand_rate: Decimal | str | float | None = None,
    fixed_monthly_charge: Decimal | str | float = ZERO,
    source_ref: str = "",
    version: str = "1",
) -> TariffSpec:
    """Build a simple flat-rate tariff."""
    rate_dec = _parse_decimal(rate, "rate")
    demand_dec = _parse_optional_decimal(demand_rate, "demand_rate")
    fixed_dec = _parse_decimal(fixed_monthly_charge, "fixed_monthly_charge")
    return TariffSpec(
        currency=currency.upper(),
        timezone=timezone,
        energy_rates={"flat": rate_dec},
        demand_rate=demand_dec,
        fixed_monthly_charge=fixed_dec,
        source_ref=source_ref,
        version=version,
    )


def build_tou_tariff(
    *,
    currency: str,
    timezone: str,
    rates: dict[str, Decimal | str | float],
    demand_rate: Decimal | str | float | None = None,
    fixed_monthly_charge: Decimal | str | float = ZERO,
    source_ref: str = "",
    version: str = "1",
) -> TariffSpec:
    """Build a time-of-use tariff with explicit period rates."""
    parsed_rates: dict[str, Decimal] = {}
    for key, val in rates.items():
        parsed_rates[key] = _parse_decimal(val, f"rates[{key}]")
    demand_dec = _parse_optional_decimal(demand_rate, "demand_rate")
    fixed_dec = _parse_decimal(fixed_monthly_charge, "fixed_monthly_charge")
    return TariffSpec(
        currency=currency.upper(),
        timezone=timezone,
        energy_rates=parsed_rates,
        demand_rate=demand_dec,
        fixed_monthly_charge=fixed_dec,
        source_ref=source_ref,
        version=version,
    )


def build_tiered_tariff(
    *,
    currency: str,
    timezone: str,
    tier_thresholds: list[Decimal | str | float],
    tier_rates: list[Decimal | str | float],
    demand_rate: Decimal | str | float | None = None,
    fixed_monthly_charge: Decimal | str | float = ZERO,
    source_ref: str = "",
    version: str = "1",
) -> TariffSpec:
    """Build a tiered-rate tariff."""
    thresholds: list[Decimal] = []
    for i, t in enumerate(tier_thresholds):
        thresholds.append(_parse_decimal(t, f"tier_thresholds[{i}]"))
    rates: list[Decimal] = []
    for i, r in enumerate(tier_rates):
        rates.append(_parse_decimal(r, f"tier_rates[{i}]"))
    if len(rates) != len(thresholds) + 1:
        raise ValueError("tier_rates must have exactly one more entry than tier_thresholds")
    for i in range(1, len(thresholds)):
        if thresholds[i] <= thresholds[i - 1]:
            raise ValueError("tier_thresholds must be strictly increasing")
    demand_dec = _parse_optional_decimal(demand_rate, "demand_rate")
    fixed_dec = _parse_decimal(fixed_monthly_charge, "fixed_monthly_charge")
    return TariffSpec(
        currency=currency.upper(),
        timezone=timezone,
        energy_rates={"tiered": rates[0]},
        demand_rate=demand_dec,
        fixed_monthly_charge=fixed_dec,
        tier_thresholds=thresholds,
        tier_rates=rates,
        source_ref=source_ref,
        version=version,
    )
