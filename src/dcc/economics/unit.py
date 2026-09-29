"""Unit economics calculations for Data Center Commander.

Implements cost-per-unit metrics as defined in docs/COST_ESTIMATING_AND_UNIT_ECONOMICS.md:
- Equivalent annual cost (EAC) from present value
- Cost per kW-year, rack-year, m²-year
- Cost per kWh (IT and facility boundaries)
- Cost per useful work unit

All functions return None for absent/zero denominators (displayed as "Unknown")
or when pricing data is missing (displayed as "Not priced").
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

# Sentinel values for UI display
NOT_PRICED = "Not priced"
UNKNOWN = "Unknown"

Numeric = Union[int, float]


@dataclass(frozen=True)
class UnitEconomicsResult:
    """Container for a unit economics calculation result.

    Attributes:
        value: The computed unit cost, or None if not computable.
        unit: Human-readable unit label (e.g., "USD/kW-year").
        status: "ok", "not_priced", or "unknown".
        detail: Optional explanation when status is not "ok".
    """
    value: Optional[float]
    unit: str
    status: str
    detail: Optional[str] = None


def _validate_pv(pv: Numeric) -> float:
    """Validate and convert present value."""
    pv_float = float(pv)
    if pv_float < 0:
        raise ValueError("Present value must be non-negative")
    return pv_float


def _validate_rate(rate: Numeric) -> float:
    """Validate discount rate."""
    rate_float = float(rate)
    if rate_float < 0 or rate_float >= 1:
        raise ValueError("Discount rate must be in [0, 1)")
    return rate_float


def _validate_horizon(years: Numeric) -> float:
    """Validate horizon in years."""
    years_float = float(years)
    if years_float <= 0:
        raise ValueError("Horizon must be positive")
    return years_float


def _validate_denominator(denominator: Numeric, name: str) -> float:
    """Validate a denominator value."""
    denom_float = float(denominator)
    if denom_float <= 0:
        raise ValueError(f"{name} must be positive")
    return denom_float


def equivalent_annual_cost(
    present_value: Numeric,
    years: Numeric,
    discount_rate: Numeric = 0.0,
) -> float:
    """Calculate equivalent annual cost (EAC).

    Formula:
        EAC = PV / n                    when r = 0
        EAC = PV * r / (1 - (1+r)^(-n))  when r > 0

    Args:
        present_value: Total present value of costs (non-negative).
        years: Time horizon in years (positive).
        discount_rate: Annual discount rate in [0, 1). Default 0.

    Returns:
        Equivalent annual cost.

    Raises:
        ValueError: If inputs are invalid.
    """
    pv = _validate_pv(present_value)
    n = _validate_horizon(years)
    r = _validate_rate(discount_rate)

    if r == 0:
        return pv / n
    return pv * r / (1 - (1 + r) ** (-n))


def cost_per_kw_year(
    annual_cost: Numeric,
    it_capacity_kw: Numeric,
) -> UnitEconomicsResult:
    """Calculate cost per kW-year.

    Args:
        annual_cost: Annualized cost in currency units.
        it_capacity_kw: IT capacity in kW (must be positive).

    Returns:
        UnitEconomicsResult with value in currency/kW-year.
    """
    try:
        cost = float(annual_cost)
        kw = _validate_denominator(it_capacity_kw, "IT capacity")
    except ValueError as exc:
        return UnitEconomicsResult(
            value=None,
            unit="USD/kW-year",
            status="unknown",
            detail=str(exc),
        )

    if cost < 0:
        return UnitEconomicsResult(
            value=None,
            unit="USD/kW-year",
            status="not_priced",
            detail="Annual cost is negative",
        )

    return UnitEconomicsResult(
        value=cost / kw,
        unit="USD/kW-year",
        status="ok",
    )


def cost_per_rack_year(
    annual_cost: Numeric,
    rack_count: Numeric,
) -> UnitEconomicsResult:
    """Calculate cost per rack-year.

    Args:
        annual_cost: Annualized cost in currency units.
        rack_count: Number of racks (must be positive).

    Returns:
        UnitEconomicsResult with value in currency/rack-year.
    """
    try:
        cost = float(annual_cost)
        racks = _validate_denominator(rack_count, "Rack count")
    except ValueError as exc:
        return UnitEconomicsResult(
            value=None,
            unit="USD/rack-year",
            status="unknown",
            detail=str(exc),
        )

    if cost < 0:
        return UnitEconomicsResult(
            value=None,
            unit="USD/rack-year",
            status="not_priced",
            detail="Annual cost is negative",
        )

    return UnitEconomicsResult(
        value=cost / racks,
        unit="USD/rack-year",
        status="ok",
    )


def cost_per_m2_year(
    annual_cost: Numeric,
    area_m2: Numeric,
) -> UnitEconomicsResult:
    """Calculate cost per m²-year.

    Args:
        annual_cost: Annualized cost in currency units.
        area_m2: Floor area in square meters (must be positive).

    Returns:
        UnitEconomicsResult with value in currency/m²-year.
    """
    try:
        cost = float(annual_cost)
        area = _validate_denominator(area_m2, "Floor area")
    except ValueError as exc:
        return UnitEconomicsResult(
            value=None,
            unit="USD/m²-year",
            status="unknown",
            detail=str(exc),
        )

    if cost < 0:
        return UnitEconomicsResult(
            value=None,
            unit="USD/m²-year",
            status="not_priced",
            detail="Annual cost is negative",
        )

    return UnitEconomicsResult(
        value=cost / area,
        unit="USD/m²-year",
        status="ok",
    )


def cost_per_kwh(
    energy_cost: Numeric,
    it_energy_kwh: Numeric,
    facility_energy_kwh: Optional[Numeric] = None,
) -> dict[str, UnitEconomicsResult]:
    """Calculate cost per kWh at IT and facility boundaries.

    Args:
        energy_cost: Energy OPEX in currency units.
        it_energy_kwh: Metered IT energy in kWh (must be positive).
        facility_energy_kwh: Total facility energy in kWh (optional, must be positive).

    Returns:
        Dictionary with keys "it_boundary" and optionally "facility_boundary".
    """
    results: dict[str, UnitEconomicsResult] = {}

    cost: Optional[float] = None
    it_kwh: Optional[float] = None

    try:
        cost = float(energy_cost)
        it_kwh = _validate_denominator(it_energy_kwh, "IT energy")
    except ValueError as exc:
        results["it_boundary"] = UnitEconomicsResult(
            value=None,
            unit="USD/kWh",
            status="unknown",
            detail=str(exc),
        )

    if it_kwh is not None and cost is not None:
        if cost < 0:
            results["it_boundary"] = UnitEconomicsResult(
                value=None,
                unit="USD/kWh",
                status="not_priced",
                detail="Energy cost is negative",
            )
        else:
            results["it_boundary"] = UnitEconomicsResult(
                value=cost / it_kwh,
                unit="USD/kWh",
                status="ok",
            )

    if facility_energy_kwh is not None:
        try:
            fac_kwh = _validate_denominator(facility_energy_kwh, "Facility energy")
            if cost is None:
                results["facility_boundary"] = UnitEconomicsResult(
                    value=None,
                    unit="USD/kWh",
                    status="unknown",
                    detail="Energy cost unavailable",
                )
            elif cost < 0:
                results["facility_boundary"] = UnitEconomicsResult(
                    value=None,
                    unit="USD/kWh",
                    status="not_priced",
                    detail="Energy cost is negative",
                )
            else:
                results["facility_boundary"] = UnitEconomicsResult(
                    value=cost / fac_kwh,
                    unit="USD/kWh",
                    status="ok",
                )
        except ValueError as exc:
            results["facility_boundary"] = UnitEconomicsResult(
                value=None,
                unit="USD/kWh",
                status="unknown",
                detail=str(exc),
            )

    return results


def cost_per_work_unit(
    allocated_cost: Numeric,
    useful_work: Numeric,
) -> UnitEconomicsResult:
    """Calculate cost per useful work unit.

    Args:
        allocated_cost: Allocated lifecycle cost in currency units.
        useful_work: Verified useful workload unit count (must be positive).

    Returns:
        UnitEconomicsResult with value in currency/work-unit.
    """
    try:
        cost = float(allocated_cost)
        work = _validate_denominator(useful_work, "Useful work")
    except ValueError as exc:
        return UnitEconomicsResult(
            value=None,
            unit="USD/work-unit",
            status="unknown",
            detail=str(exc),
        )

    if cost < 0:
        return UnitEconomicsResult(
            value=None,
            unit="USD/work-unit",
            status="not_priced",
            detail="Allocated cost is negative",
        )

    return UnitEconomicsResult(
        value=cost / work,
        unit="USD/work-unit",
        status="ok",
    )


def compute_all_unit_economics(
    present_value: Numeric,
    years: Numeric,
    discount_rate: Numeric,
    it_capacity_kw: Numeric,
    rack_count: Numeric,
    area_m2: Numeric,
    energy_cost: Numeric,
    it_energy_kwh: Numeric,
    facility_energy_kwh: Optional[Numeric] = None,
    allocated_cost: Optional[Numeric] = None,
    useful_work: Optional[Numeric] = None,
) -> dict[str, Union[UnitEconomicsResult, dict[str, UnitEconomicsResult], float]]:
    """Compute all unit economics metrics in one call.

    Args:
        present_value: Total present value of costs.
        years: Time horizon in years.
        discount_rate: Annual discount rate.
        it_capacity_kw: IT capacity in kW.
        rack_count: Number of racks.
        area_m2: Floor area in m².
        energy_cost: Energy OPEX.
        it_energy_kwh: IT energy in kWh.
        facility_energy_kwh: Facility energy in kWh (optional).
        allocated_cost: Allocated lifecycle cost for work unit (optional).
        useful_work: Useful work unit count (optional).

    Returns:
        Dictionary containing:
            - eac: Equivalent annual cost (float)
            - cost_per_kw: UnitEconomicsResult
            - cost_per_rack: UnitEconomicsResult
            - cost_per_m2: UnitEconomicsResult
            - cost_per_kwh: dict with "it_boundary" and optionally "facility_boundary"
            - cost_per_work: UnitEconomicsResult (only if allocated_cost and useful_work provided)
    """
    eac = equivalent_annual_cost(present_value, years, discount_rate)

    results: dict[str, Union[UnitEconomicsResult, dict[str, UnitEconomicsResult], float]] = {
        "eac": eac,
        "cost_per_kw": cost_per_kw_year(eac, it_capacity_kw),
        "cost_per_rack": cost_per_rack_year(eac, rack_count),
        "cost_per_m2": cost_per_m2_year(eac, area_m2),
        "cost_per_kwh": cost_per_kwh(energy_cost, it_energy_kwh, facility_energy_kwh),
    }

    if allocated_cost is not None and useful_work is not None:
        results["cost_per_work"] = cost_per_work_unit(allocated_cost, useful_work)

    return results
