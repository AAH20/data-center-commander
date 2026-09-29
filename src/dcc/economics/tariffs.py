"""Tariff structure modeling engine for Data Center Commander.

Implements electricity tariff calculations for data center energy cost modeling:
- Time-of-use (TOU) rates: different prices by time of day and day of week
- Demand charges: charges based on peak demand (kW) in a billing period
- Tiered rates: different prices for different consumption levels
- Fixed charges: flat service fees and other recurring charges

All calculations use Decimal for financial precision and are deterministic.
The tariff_spec JSON schema matches the dcc.tariffs table column.

Tariff spec schema (tariff.v1):
{
    "schema_version": "tariff.v1",
    "currency": "USD",
    "timezone": "America/New_York",
    "billing_period": "monthly",
    "tou_periods": [
        {
            "name": "peak",
            "days_of_week": [1, 2, 3, 4, 5],  # 1=Monday, 7=Sunday
            "start_time": "12:00",
            "end_time": "18:00",
            "rate_per_kwh": "0.25"
        }
    ],
    "demand_charges": [
        {
            "name": "peak_demand",
            "rate_per_kw": "15.00",
            "billing_demand_basis": "peak_kw_in_period"
        }
    ],
    "tiered_rates": [
        {
            "name": "energy_tiers",
            "tiers": [
                {"upper_limit_kwh": "1000", "rate_per_kwh": "0.10"},
                {"upper_limit_kwh": "5000", "rate_per_kwh": "0.08"},
                {"upper_limit_kwh": null, "rate_per_kwh": "0.06"}
            ]
        }
    ],
    "fixed_charges": [
        {"name": "service_fee", "amount": "50.00", "frequency": "monthly"}
    ]
}
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TOUPeriod:
    """A time-of-use period definition.

    Attributes:
        name: Human-readable period name (e.g., "peak", "off_peak").
        days_of_week: List of weekdays (1=Monday, 7=Sunday) when this period applies.
        start_time: Start time as "HH:MM" 24-hour string.
        end_time: End time as "HH:MM" 24-hour string.
        rate_per_kwh: Energy rate per kWh during this period.
    """

    name: str
    days_of_week: tuple[int, ...]
    start_time: str
    end_time: str
    rate_per_kwh: Decimal

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TOUPeriod:
        """Create a TOUPeriod from a dict (tariff_spec JSON)."""
        return cls(
            name=str(data["name"]),
            days_of_week=tuple(int(d) for d in data["days_of_week"]),
            start_time=str(data["start_time"]),
            end_time=str(data["end_time"]),
            rate_per_kwh=_decimal(data["rate_per_kwh"]),
        )


@dataclass(frozen=True)
class DemandCharge:
    """A demand charge definition.

    Attributes:
        name: Human-readable charge name.
        rate_per_kw: Charge per kW of billing demand.
        billing_demand_basis: How billing demand is determined
            (e.g., "peak_kw_in_period", "peak_kw_monthly", "contract_demand").
    """

    name: str
    rate_per_kw: Decimal
    billing_demand_basis: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DemandCharge:
        """Create a DemandCharge from a dict."""
        return cls(
            name=str(data["name"]),
            rate_per_kw=_decimal(data["rate_per_kw"]),
            billing_demand_basis=str(data.get("billing_demand_basis", "peak_kw_monthly")),
        )


@dataclass(frozen=True)
class Tier:
    """A single tier in a tiered rate structure.

    Attributes:
        upper_limit_kwh: Upper bound of this tier in kWh (None = unlimited).
        rate_per_kwh: Rate per kWh within this tier.
    """

    upper_limit_kwh: Optional[Decimal]
    rate_per_kwh: Decimal

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Tier:
        """Create a Tier from a dict."""
        limit = data.get("upper_limit_kwh")
        return cls(
            upper_limit_kwh=_decimal(limit) if limit is not None else None,
            rate_per_kwh=_decimal(data["rate_per_kwh"]),
        )


@dataclass(frozen=True)
class TieredRate:
    """A tiered rate structure for energy charges.

    Attributes:
        name: Human-readable name.
        tiers: Ordered list of tiers (must be in ascending order).
    """

    name: str
    tiers: tuple[Tier, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TieredRate:
        """Create a TieredRate from a dict."""
        tiers = tuple(Tier.from_dict(t) for t in data["tiers"])
        return cls(name=str(data["name"]), tiers=tiers)


@dataclass(frozen=True)
class FixedCharge:
    """A fixed recurring charge.

    Attributes:
        name: Human-readable charge name.
        amount: Charge amount.
        frequency: Billing frequency ("monthly", "quarterly", "annual").
    """

    name: str
    amount: Decimal
    frequency: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FixedCharge:
        """Create a FixedCharge from a dict."""
        return cls(
            name=str(data["name"]),
            amount=_decimal(data["amount"]),
            frequency=str(data.get("frequency", "monthly")),
        )


@dataclass(frozen=True)
class TariffSpec:
    """Complete tariff specification.

    Attributes:
        schema_version: Schema version string.
        currency: ISO 4217 currency code.
        timezone: IANA timezone name.
        billing_period: Billing period ("monthly", "quarterly", "annual").
        tou_periods: Time-of-use period definitions.
        demand_charges: Demand charge definitions.
        tiered_rates: Tiered rate structures.
        fixed_charges: Fixed recurring charges.
    """

    schema_version: str
    currency: str
    timezone: str
    billing_period: str
    tou_periods: tuple[TOUPeriod, ...]
    demand_charges: tuple[DemandCharge, ...]
    tiered_rates: tuple[TieredRate, ...]
    fixed_charges: tuple[FixedCharge, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TariffSpec:
        """Create a TariffSpec from a dict (tariff_spec JSONB)."""
        return cls(
            schema_version=str(data.get("schema_version", "tariff.v1")),
            currency=str(data.get("currency", "USD")),
            timezone=str(data.get("timezone", "UTC")),
            billing_period=str(data.get("billing_period", "monthly")),
            tou_periods=tuple(
                TOUPeriod.from_dict(p) for p in data.get("tou_periods", [])
            ),
            demand_charges=tuple(
                DemandCharge.from_dict(d) for d in data.get("demand_charges", [])
            ),
            tiered_rates=tuple(
                TieredRate.from_dict(t) for t in data.get("tiered_rates", [])
            ),
            fixed_charges=tuple(
                FixedCharge.from_dict(f) for f in data.get("fixed_charges", [])
            ),
        )

    @classmethod
    def from_json(cls, json_str: str) -> TariffSpec:
        """Create a TariffSpec from a JSON string."""
        import json
        return cls.from_dict(json.loads(json_str))


@dataclass
class TOUChargeResult:
    """Result of a time-of-use energy charge calculation."""

    period_name: str
    energy_kwh: Decimal
    rate_per_kwh: Decimal
    charge: Decimal


@dataclass
class DemandChargeResult:
    """Result of a demand charge calculation."""

    charge_name: str
    billing_demand_kw: Decimal
    rate_per_kw: Decimal
    charge: Decimal


@dataclass
class TieredChargeResult:
    """Result of a tiered rate calculation."""

    rate_name: str
    total_energy_kwh: Decimal
    charge: Decimal
    tier_breakdown: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FixedChargeResult:
    """Result of a fixed charge calculation."""

    charge_name: str
    amount: Decimal
    frequency: str


@dataclass
class TariffCalculationResult:
    """Complete tariff calculation result.

    Attributes:
        total_energy_charges: Sum of all energy-related charges.
        total_demand_charges: Sum of all demand charges.
        total_fixed_charges: Sum of all fixed charges.
        total: Grand total of all charges.
        energy_kwh: Total energy consumed in kWh.
        peak_demand_kw: Peak demand in kW.
        tou_charges: Breakdown of TOU energy charges.
        demand_charges: Breakdown of demand charges.
        tiered_charges: Breakdown of tiered rate charges.
        fixed_charges: Breakdown of fixed charges.
        currency: Currency code.
        billing_period: Billing period.
    """

    total_energy_charges: Decimal
    total_demand_charges: Decimal
    total_fixed_charges: Decimal
    total: Decimal
    energy_kwh: Decimal
    peak_demand_kw: Decimal
    tou_charges: list[TOUChargeResult]
    demand_charges: list[DemandChargeResult]
    tiered_charges: list[TieredChargeResult]
    fixed_charges: list[FixedChargeResult]
    currency: str
    billing_period: str


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------


def _decimal(value: Any, default: Decimal | None = None) -> Decimal:
    """Safely convert a value to Decimal."""
    if value is None:
        if default is not None:
            return default
        raise ValueError("required numeric value is missing")
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"invalid numeric value: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"non-finite numeric value: {value!r}")
    return result


def _round_decimal(value: Decimal | int, places: int = 2) -> Decimal:
    """Round a Decimal to the specified number of decimal places."""
    quantize_str = "0." + "0" * places
    return Decimal(str(value)).quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)


def _validate_tariff_spec(spec: TariffSpec) -> None:
    """Validate a tariff specification for internal consistency."""
    if spec.billing_period not in ("monthly", "quarterly", "annual"):
        raise ValueError(f"unsupported billing_period: {spec.billing_period}")

    # Validate TOU periods
    for period in spec.tou_periods:
        if not period.days_of_week:
            raise ValueError(f"TOU period '{period.name}' has no days_of_week")
        for d in period.days_of_week:
            if not 1 <= d <= 7:
                raise ValueError(f"TOU period '{period.name}' has invalid day_of_week: {d}")
        if period.rate_per_kwh < 0:
            raise ValueError(f"TOU period '{period.name}' has negative rate")
        _validate_time_range(period.start_time, period.end_time, period.name)

    # Validate demand charges
    for charge in spec.demand_charges:
        if charge.rate_per_kw < 0:
            raise ValueError(f"demand charge '{charge.name}' has negative rate")

    # Validate tiered rates
    for rate in spec.tiered_rates:
        if not rate.tiers:
            raise ValueError(f"tiered rate '{rate.name}' has no tiers")
        prev_limit: Optional[Decimal] = None
        for i, tier in enumerate(rate.tiers):
            if tier.rate_per_kwh < 0:
                raise ValueError(f"tiered rate '{rate.name}' tier {i} has negative rate")
            if tier.upper_limit_kwh is not None and tier.upper_limit_kwh <= 0:
                raise ValueError(f"tiered rate '{rate.name}' tier {i} has non-positive limit")
            if prev_limit is not None and tier.upper_limit_kwh is not None:
                if tier.upper_limit_kwh <= prev_limit:
                    raise ValueError(
                        f"tiered rate '{rate.name}' tiers must be in ascending order"
                    )
            if tier.upper_limit_kwh is not None:
                prev_limit = tier.upper_limit_kwh
        # Last tier should have no upper limit (unlimited)
        if rate.tiers[-1].upper_limit_kwh is not None:
            raise ValueError(
                f"tiered rate '{rate.name}' last tier must have null upper_limit_kwh"
            )

    # Validate fixed charges
    for charge in spec.fixed_charges:
        if charge.amount < 0:
            raise ValueError(f"fixed charge '{charge.name}' has negative amount")
        if charge.frequency not in ("monthly", "quarterly", "annual"):
            raise ValueError(f"fixed charge '{charge.name}' has invalid frequency")


def _validate_time_range(start: str, end: str, name: str) -> None:
    """Validate a time range in HH:MM format.

    Allows wrapping ranges where end_time < start_time (e.g., 18:00-12:00
    means 6 PM to noon next day, common for off-peak utility periods).
    """
    import re
    time_re = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
    if not time_re.fullmatch(start):
        raise ValueError(f"TOU period '{name}' has invalid start_time: {start}")
    if not time_re.fullmatch(end):
        raise ValueError(f"TOU period '{name}' has invalid end_time: {end}")
    # Allow wrapping ranges (end < start means crosses midnight)
    # Only reject if start == end (zero-length period)
    if start == end:
        raise ValueError(f"TOU period '{name}' start_time and end_time must differ")


# ---------------------------------------------------------------------------
# Core calculation functions
# ---------------------------------------------------------------------------


def calculate_tou_charges(
    *,
    tou_periods: list[TOUPeriod] | tuple[TOUPeriod, ...],
    energy_by_period: dict[str, Decimal | float | int],
) -> list[TOUChargeResult]:
    """Calculate time-of-use energy charges.

    Args:
        tou_periods: List of TOU period definitions.
        energy_by_period: Mapping of period name to energy consumed in kWh.

    Returns:
        List of TOUChargeResult, one per period with non-zero energy.
    """
    results: list[TOUChargeResult] = []
    for period in tou_periods:
        energy = _decimal(energy_by_period.get(period.name, 0))
        if energy < 0:
            raise ValueError(f"energy for period '{period.name}' must be non-negative")
        if energy == 0:
            continue
        charge = energy * period.rate_per_kwh
        results.append(TOUChargeResult(
            period_name=period.name,
            energy_kwh=energy,
            rate_per_kwh=period.rate_per_kwh,
            charge=charge,
        ))
    return results


def calculate_demand_charges(
    *,
    demand_charges: list[DemandCharge] | tuple[DemandCharge, ...],
    billing_demand_kw: Decimal | float | int,
) -> list[DemandChargeResult]:
    """Calculate demand charges.

    Args:
        demand_charges: List of demand charge definitions.
        billing_demand_kw: Billing demand in kW (peak demand for the period).

    Returns:
        List of DemandChargeResult, one per charge definition.
    """
    demand = _decimal(billing_demand_kw)
    if demand < 0:
        raise ValueError("billing_demand_kw must be non-negative")

    results: list[DemandChargeResult] = []
    for charge_def in demand_charges:
        charge = demand * charge_def.rate_per_kw
        results.append(DemandChargeResult(
            charge_name=charge_def.name,
            billing_demand_kw=demand,
            rate_per_kw=charge_def.rate_per_kw,
            charge=charge,
        ))
    return results


def calculate_tiered_charges(
    *,
    tiered_rates: list[TieredRate] | tuple[TieredRate, ...],
    total_energy_kwh: Decimal | float | int,
) -> list[TieredChargeResult]:
    """Calculate tiered rate charges.

    Args:
        tiered_rates: List of tiered rate structures.
        total_energy_kwh: Total energy consumed in kWh.

    Returns:
        List of TieredChargeResult, one per tiered rate structure.
    """
    energy = _decimal(total_energy_kwh)
    if energy < 0:
        raise ValueError("total_energy_kwh must be non-negative")

    results: list[TieredChargeResult] = []
    for rate_def in tiered_rates:
        remaining = energy
        total_charge = Decimal("0")
        tier_breakdown: list[dict[str, Any]] = []

        for i, tier in enumerate(rate_def.tiers):
            if remaining <= 0:
                break

            if tier.upper_limit_kwh is None:
                # Unlimited tier: all remaining energy
                tier_energy = remaining
            else:
                # Calculate energy in this tier
                prev_limit = rate_def.tiers[i - 1].upper_limit_kwh if i > 0 else Decimal("0")
                if prev_limit is None:
                    prev_limit = Decimal("0")
                tier_capacity = tier.upper_limit_kwh - prev_limit
                tier_energy = min(remaining, tier_capacity)

            tier_charge = tier_energy * tier.rate_per_kwh
            total_charge += tier_charge
            remaining -= tier_energy

            tier_breakdown.append({
                "tier": i + 1,
                "energy_kwh": _round_decimal(tier_energy),
                "rate_per_kwh": _round_decimal(tier.rate_per_kwh),
                "charge": _round_decimal(tier_charge),
            })

        results.append(TieredChargeResult(
            rate_name=rate_def.name,
            total_energy_kwh=energy,
            charge=total_charge,
            tier_breakdown=tier_breakdown,
        ))
    return results


def calculate_fixed_charges(
    *,
    fixed_charges: list[FixedCharge] | tuple[FixedCharge, ...],
    billing_period: str = "monthly",
) -> list[FixedChargeResult]:
    """Calculate fixed charges for a billing period.

    Args:
        fixed_charges: List of fixed charge definitions.
        billing_period: The billing period ("monthly", "quarterly", "annual").

    Returns:
        List of FixedChargeResult, one per fixed charge.
    """
    if billing_period not in ("monthly", "quarterly", "annual"):
        raise ValueError(f"unsupported billing_period: {billing_period}")

    # Determine multiplier based on billing period
    multiplier = {
        "monthly": 1,
        "quarterly": 3,
        "annual": 12,
    }[billing_period]

    results: list[FixedChargeResult] = []
    for charge_def in fixed_charges:
        # Adjust amount based on frequency vs billing period
        if charge_def.frequency == billing_period:
            amount = charge_def.amount
        elif charge_def.frequency == "monthly" and billing_period == "quarterly":
            amount = charge_def.amount * 3
        elif charge_def.frequency == "monthly" and billing_period == "annual":
            amount = charge_def.amount * 12
        elif charge_def.frequency == "quarterly" and billing_period == "annual":
            amount = charge_def.amount * 4
        elif charge_def.frequency == "annual" and billing_period == "monthly":
            amount = charge_def.amount / 12
        elif charge_def.frequency == "annual" and billing_period == "quarterly":
            amount = charge_def.amount / 4
        elif charge_def.frequency == "quarterly" and billing_period == "monthly":
            amount = charge_def.amount / 3
        else:
            amount = charge_def.amount * multiplier

        results.append(FixedChargeResult(
            charge_name=charge_def.name,
            amount=amount,
            frequency=charge_def.frequency,
        ))
    return results


def calculate_tariff(
    *,
    spec: TariffSpec,
    energy_kwh: Decimal | float | int,
    peak_demand_kw: Decimal | float | int,
    energy_by_period: Optional[dict[str, Decimal | float | int]] = None,
) -> TariffCalculationResult:
    """Calculate total tariff charges for a billing period.

    This is the main entry point for tariff calculation. It computes:
    - Time-of-use energy charges (if TOU periods are defined)
    - Tiered rate charges (if tiered rates are defined)
    - Demand charges (if demand charges are defined)
    - Fixed charges (if fixed charges are defined)

    Args:
        spec: The tariff specification.
        energy_kwh: Total energy consumed in kWh for the billing period.
        peak_demand_kw: Peak demand in kW for the billing period.
        energy_by_period: Optional mapping of TOU period name to energy in kWh.
            If not provided, all energy is charged at the highest TOU rate
            or the first tiered rate.

    Returns:
        TariffCalculationResult with full breakdown.
    """
    _validate_tariff_spec(spec)

    energy = _decimal(energy_kwh)
    peak = _decimal(peak_demand_kw)

    if energy < 0:
        raise ValueError("energy_kwh must be non-negative")
    if peak < 0:
        raise ValueError("peak_demand_kw must be non-negative")

    # Calculate TOU charges
    tou_results: list[TOUChargeResult] = []
    if spec.tou_periods:
        if energy_by_period is not None:
            tou_results = calculate_tou_charges(
                tou_periods=spec.tou_periods,
                energy_by_period=energy_by_period,
            )
        else:
            # No breakdown provided: charge all energy at the highest TOU rate
            highest_rate = max(p.rate_per_kwh for p in spec.tou_periods)
            tou_results = [TOUChargeResult(
                period_name="default",
                energy_kwh=energy,
                rate_per_kwh=highest_rate,
                charge=energy * highest_rate,
            )]

    # Calculate tiered charges
    tiered_results: list[TieredChargeResult] = []
    if spec.tiered_rates:
        tiered_results = calculate_tiered_charges(
            tiered_rates=spec.tiered_rates,
            total_energy_kwh=energy,
        )

    # Calculate demand charges
    demand_results: list[DemandChargeResult] = []
    if spec.demand_charges:
        demand_results = calculate_demand_charges(
            demand_charges=spec.demand_charges,
            billing_demand_kw=peak,
        )

    # Calculate fixed charges
    fixed_results: list[FixedChargeResult] = []
    if spec.fixed_charges:
        fixed_results = calculate_fixed_charges(
            fixed_charges=spec.fixed_charges,
            billing_period=spec.billing_period,
        )

    # Sum up totals
    zero = Decimal("0")
    total_energy = sum((r.charge for r in tou_results), zero) + sum((r.charge for r in tiered_results), zero)
    total_demand = sum((r.charge for r in demand_results), zero)
    total_fixed = sum((r.amount for r in fixed_results), zero)
    grand_total = total_energy + total_demand + total_fixed

    return TariffCalculationResult(
        total_energy_charges=total_energy,
        total_demand_charges=total_demand,
        total_fixed_charges=total_fixed,
        total=grand_total,
        energy_kwh=energy,
        peak_demand_kw=peak,
        tou_charges=tou_results,
        demand_charges=demand_results,
        tiered_charges=tiered_results,
        fixed_charges=fixed_results,
        currency=spec.currency,
        billing_period=spec.billing_period,
    )


# ---------------------------------------------------------------------------
# Convenience functions for common tariff structures
# ---------------------------------------------------------------------------


def create_simple_tou_tariff(
    *,
    currency: str = "USD",
    timezone: str = "UTC",
    peak_rate: Decimal | float | int = 0.25,
    off_peak_rate: Decimal | float | int = 0.10,
    peak_hours: tuple[int, ...] = (12, 13, 14, 15, 16, 17),
    peak_days: tuple[int, ...] = (1, 2, 3, 4, 5),
    demand_rate_per_kw: Optional[Decimal | float | int] = None,
    fixed_monthly_charge: Optional[Decimal | float | int] = None,
) -> TariffSpec:
    """Create a simple TOU tariff with peak/off-peak periods.

    Args:
        currency: ISO 4217 currency code.
        timezone: IANA timezone name.
        peak_rate: Rate per kWh during peak hours.
        off_peak_rate: Rate per kWh during off-peak hours.
        peak_hours: Hours (0-23) considered peak.
        peak_days: Days of week (1-7) considered peak.
        demand_rate_per_kw: Optional demand charge rate per kW.
        fixed_monthly_charge: Optional fixed monthly service charge.

    Returns:
        A TariffSpec with the defined structure.
    """
    peak_rate_d = _decimal(peak_rate)
    off_peak_rate_d = _decimal(off_peak_rate)

    # Build TOU periods
    tou_periods: list[TOUPeriod] = []

    # Peak period
    if peak_hours:
        start_hour = min(peak_hours)
        end_hour = max(peak_hours) + 1
        tou_periods.append(TOUPeriod(
            name="peak",
            days_of_week=peak_days,
            start_time=f"{start_hour:02d}:00",
            end_time=f"{end_hour:02d}:00",
            rate_per_kwh=peak_rate_d,
        ))

    # Off-peak period (all other hours)
    tou_periods.append(TOUPeriod(
        name="off_peak",
        days_of_week=(1, 2, 3, 4, 5, 6, 7),
        start_time="00:00",
        end_time="23:59",
        rate_per_kwh=off_peak_rate_d,
    ))

    # Demand charges
    demand_charges: list[DemandCharge] = []
    if demand_rate_per_kw is not None:
        demand_charges.append(DemandCharge(
            name="peak_demand",
            rate_per_kw=_decimal(demand_rate_per_kw),
            billing_demand_basis="peak_kw_monthly",
        ))

    # Fixed charges
    fixed_charges: list[FixedCharge] = []
    if fixed_monthly_charge is not None:
        fixed_charges.append(FixedCharge(
            name="service_fee",
            amount=_decimal(fixed_monthly_charge),
            frequency="monthly",
        ))

    return TariffSpec(
        schema_version="tariff.v1",
        currency=currency,
        timezone=timezone,
        billing_period="monthly",
        tou_periods=tuple(tou_periods),
        demand_charges=tuple(demand_charges),
        tiered_rates=(),
        fixed_charges=tuple(fixed_charges),
    )


def create_tiered_tariff(
    *,
    currency: str = "USD",
    timezone: str = "UTC",
    tiers: list[dict[str, Any]],
    demand_rate_per_kw: Optional[Decimal | float | int] = None,
    fixed_monthly_charge: Optional[Decimal | float | int] = None,
) -> TariffSpec:
    """Create a tiered rate tariff.

    Args:
        currency: ISO 4217 currency code.
        timezone: IANA timezone name.
        tiers: List of tier dicts with 'upper_limit_kwh' and 'rate_per_kwh'.
        demand_rate_per_kw: Optional demand charge rate per kW.
        fixed_monthly_charge: Optional fixed monthly service charge.

    Returns:
        A TariffSpec with tiered rates.
    """
    tiered_rates: list[TieredRate] = []
    if tiers:
        tiered_rates.append(TieredRate(
            name="energy_tiers",
            tiers=tuple(Tier.from_dict(t) for t in tiers),
        ))

    demand_charges: list[DemandCharge] = []
    if demand_rate_per_kw is not None:
        demand_charges.append(DemandCharge(
            name="peak_demand",
            rate_per_kw=_decimal(demand_rate_per_kw),
            billing_demand_basis="peak_kw_monthly",
        ))

    fixed_charges: list[FixedCharge] = []
    if fixed_monthly_charge is not None:
        fixed_charges.append(FixedCharge(
            name="service_fee",
            amount=_decimal(fixed_monthly_charge),
            frequency="monthly",
        ))

    return TariffSpec(
        schema_version="tariff.v1",
        currency=currency,
        timezone=timezone,
        billing_period="monthly",
        tou_periods=(),
        demand_charges=tuple(demand_charges),
        tiered_rates=tuple(tiered_rates),
        fixed_charges=tuple(fixed_charges),
    )


def create_flat_rate_tariff(
    *,
    currency: str = "USD",
    timezone: str = "UTC",
    rate_per_kwh: Decimal | float | int = 0.12,
    demand_rate_per_kw: Optional[Decimal | float | int] = None,
    fixed_monthly_charge: Optional[Decimal | float | int] = None,
) -> TariffSpec:
    """Create a flat rate tariff (single rate for all hours).

    Args:
        currency: ISO 4217 currency code.
        timezone: IANA timezone name.
        rate_per_kwh: Flat rate per kWh.
        demand_rate_per_kw: Optional demand charge rate per kW.
        fixed_monthly_charge: Optional fixed monthly service charge.

    Returns:
        A TariffSpec with a single flat rate.
    """
    rate = _decimal(rate_per_kwh)

    # Use a single tiered rate with one unlimited tier
    tiered_rates: list[TieredRate] = [
        TieredRate(
            name="flat_rate",
            tiers=(Tier(upper_limit_kwh=None, rate_per_kwh=rate),),
        )
    ]

    demand_charges: list[DemandCharge] = []
    if demand_rate_per_kw is not None:
        demand_charges.append(DemandCharge(
            name="peak_demand",
            rate_per_kw=_decimal(demand_rate_per_kw),
            billing_demand_basis="peak_kw_monthly",
        ))

    fixed_charges: list[FixedCharge] = []
    if fixed_monthly_charge is not None:
        fixed_charges.append(FixedCharge(
            name="service_fee",
            amount=_decimal(fixed_monthly_charge),
            frequency="monthly",
        ))

    return TariffSpec(
        schema_version="tariff.v1",
        currency=currency,
        timezone=timezone,
        billing_period="monthly",
        tou_periods=(),
        demand_charges=tuple(demand_charges),
        tiered_rates=tuple(tiered_rates),
        fixed_charges=tuple(fixed_charges),
    )


# ---------------------------------------------------------------------------
# Result serialization
# ---------------------------------------------------------------------------


def tariff_result_to_dict(result: TariffCalculationResult) -> dict[str, Any]:
    """Convert a TariffCalculationResult to a JSON-serializable dict."""
    return {
        "total_energy_charges": _round_decimal(result.total_energy_charges),
        "total_demand_charges": _round_decimal(result.total_demand_charges),
        "total_fixed_charges": _round_decimal(result.total_fixed_charges),
        "total": _round_decimal(result.total),
        "energy_kwh": _round_decimal(result.energy_kwh),
        "peak_demand_kw": _round_decimal(result.peak_demand_kw),
        "tou_charges": [
            {
                "period_name": r.period_name,
                "energy_kwh": _round_decimal(r.energy_kwh),
                "rate_per_kwh": _round_decimal(r.rate_per_kwh),
                "charge": _round_decimal(r.charge),
            }
            for r in result.tou_charges
        ],
        "demand_charges": [
            {
                "charge_name": r.charge_name,
                "billing_demand_kw": _round_decimal(r.billing_demand_kw),
                "rate_per_kw": _round_decimal(r.rate_per_kw),
                "charge": _round_decimal(r.charge),
            }
            for r in result.demand_charges
        ],
        "tiered_charges": [
            {
                "rate_name": r.rate_name,
                "total_energy_kwh": _round_decimal(r.total_energy_kwh),
                "charge": _round_decimal(r.charge),
                "tier_breakdown": r.tier_breakdown,
            }
            for r in result.tiered_charges
        ],
        "fixed_charges": [
            {
                "charge_name": r.charge_name,
                "amount": _round_decimal(r.amount),
                "frequency": r.frequency,
            }
            for r in result.fixed_charges
        ],
        "currency": result.currency,
        "billing_period": result.billing_period,
        "execution_permitted": False,
    }


def calculate_tariff_to_dict(
    *,
    spec: TariffSpec,
    energy_kwh: Decimal | float | int,
    peak_demand_kw: Decimal | float | int,
    energy_by_period: Optional[dict[str, Decimal | float | int]] = None,
) -> dict[str, Any]:
    """Calculate tariff charges and return as a JSON-serializable dict.

    Convenience wrapper around calculate_tariff + tariff_result_to_dict.
    """
    result = calculate_tariff(
        spec=spec,
        energy_kwh=energy_kwh,
        peak_demand_kw=peak_demand_kw,
        energy_by_period=energy_by_period,
    )
    return tariff_result_to_dict(result)


# ---------------------------------------------------------------------------
# Load tariff from database row
# ---------------------------------------------------------------------------


def load_tariff_from_row(row: dict[str, Any]) -> TariffSpec:
    """Load a TariffSpec from a database row dict.

    Args:
        row: Dictionary with 'tariff_spec' key containing the JSONB data.

    Returns:
        A TariffSpec instance.
    """
    spec_data = row.get("tariff_spec")
    if spec_data is None:
        raise ValueError("tariff row missing tariff_spec")
    if isinstance(spec_data, str):
        return TariffSpec.from_json(spec_data)
    return TariffSpec.from_dict(spec_data)


# ---------------------------------------------------------------------------
# Example tariff specs for testing and documentation
# ---------------------------------------------------------------------------


EXAMPLE_TARIFF_SPEC: dict[str, Any] = {
    "schema_version": "tariff.v1",
    "currency": "USD",
    "timezone": "America/New_York",
    "billing_period": "monthly",
    "tou_periods": [
        {
            "name": "peak",
            "days_of_week": [1, 2, 3, 4, 5],
            "start_time": "12:00",
            "end_time": "18:00",
            "rate_per_kwh": "0.25",
        },
        {
            "name": "off_peak",
            "days_of_week": [1, 2, 3, 4, 5, 6, 7],
            "start_time": "18:00",
            "end_time": "12:00",
            "rate_per_kwh": "0.10",
        },
    ],
    "demand_charges": [
        {
            "name": "peak_demand",
            "rate_per_kw": "15.00",
            "billing_demand_basis": "peak_kw_monthly",
        }
    ],
    "tiered_rates": [],
    "fixed_charges": [
        {"name": "service_fee", "amount": "50.00", "frequency": "monthly"}
    ],
}


EXAMPLE_TIERED_TARIFF_SPEC: dict[str, Any] = {
    "schema_version": "tariff.v1",
    "currency": "USD",
    "timezone": "America/Los_Angeles",
    "billing_period": "monthly",
    "tou_periods": [],
    "demand_charges": [
        {
            "name": "peak_demand",
            "rate_per_kw": "12.50",
            "billing_demand_basis": "peak_kw_monthly",
        }
    ],
    "tiered_rates": [
        {
            "name": "energy_tiers",
            "tiers": [
                {"upper_limit_kwh": "1000", "rate_per_kwh": "0.15"},
                {"upper_limit_kwh": "5000", "rate_per_kwh": "0.12"},
                {"upper_limit_kwh": "10000", "rate_per_kwh": "0.10"},
                {"upper_limit_kwh": None, "rate_per_kwh": "0.08"},
            ],
        }
    ],
    "fixed_charges": [
        {"name": "service_fee", "amount": "75.00", "frequency": "monthly"}
    ],
}
