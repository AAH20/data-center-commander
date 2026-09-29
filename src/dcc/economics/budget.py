"""Budget forecasting engine for Data Center Commander.

Projects future budgets from estimate line items, cost actuals, and growth plans.
All calculations are deterministic, tenant-scoped, and read-only.

The engine handles:
- One-time, fixed-recurring, variable, step-fixed, and capitalized cost behaviors
- Escalation and discount rates
- Low/base/high scenario bounds
- Growth plan multipliers (capacity expansion, cost reduction)
- Monthly and annual budget aggregation
- Present value calculations
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GrowthPlan:
    """Growth assumptions that modify the base cost trajectory.

    Attributes:
        monthly_capacity_growth: Monthly capacity growth rate (e.g. 0.02 = 2%/month).
            Applied to variable and step_fixed cost lines.
        monthly_cost_reduction: Monthly cost reduction rate (e.g. 0.01 = 1%/month).
            Applied to all recurring costs (efficiency improvements).
        expansion_phases: List of (start_month, capacity_multiplier) tuples for
            step changes in capacity (e.g. new facility coming online).
        new_lines: Additional line items that start at a future month.
    """

    monthly_capacity_growth: Decimal = Decimal("0")
    monthly_cost_reduction: Decimal = Decimal("0")
    expansion_phases: tuple[tuple[int, Decimal], ...] = ()
    new_lines: tuple[dict[str, Any], ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> GrowthPlan:
        if not data:
            return cls()
        phases = tuple(
            (int(m), Decimal(str(v)))
            for m, v in data.get("expansion_phases", [])
        )
        new_lines = tuple(data.get("new_lines", []))
        return cls(
            monthly_capacity_growth=Decimal(str(data.get("monthly_capacity_growth", 0))),
            monthly_cost_reduction=Decimal(str(data.get("monthly_cost_reduction", 0))),
            expansion_phases=phases,
            new_lines=new_lines,
        )


@dataclass
class BudgetLine:
    """A single budget line item extracted from an estimate line item."""

    line_id: str
    description: str
    phase: str
    cost_behavior: str
    quantity: Decimal
    waste_factor: Decimal
    base_unit_cost: Decimal
    low_unit_cost: Decimal | None
    high_unit_cost: Decimal | None
    currency: str
    escalation_pct: Decimal
    recurrence_months: int | None
    start_month: int
    useful_life_months: int | None
    pricing_status: str

    @property
    def extended_base(self) -> Decimal:
        return self.quantity * (Decimal("1") + self.waste_factor) * self.base_unit_cost

    @property
    def extended_low(self) -> Decimal:
        if self.low_unit_cost is not None:
            return self.quantity * (Decimal("1") + self.waste_factor) * self.low_unit_cost
        return self.extended_base

    @property
    def extended_high(self) -> Decimal:
        if self.high_unit_cost is not None:
            return self.quantity * (Decimal("1") + self.waste_factor) * self.high_unit_cost
        return self.extended_base


@dataclass
class MonthlyBudget:
    """Budget projection for a single month."""

    month: int
    base: Decimal = Decimal("0")
    low: Decimal = Decimal("0")
    high: Decimal = Decimal("0")
    present_value_base: Decimal = Decimal("0")
    present_value_low: Decimal = Decimal("0")
    present_value_high: Decimal = Decimal("0")
    by_phase: dict[str, Decimal] = field(default_factory=dict)
    by_phase_low: dict[str, Decimal] = field(default_factory=dict)
    by_phase_high: dict[str, Decimal] = field(default_factory=dict)
    line_count: int = 0


@dataclass
class BudgetForecast:
    """Complete budget forecast result."""

    horizon_months: int
    currency: str
    discount_rate: Decimal
    contingency_pct: Decimal
    monthly_budgets: list[MonthlyBudget]
    total_base: Decimal
    total_low: Decimal
    total_high: Decimal
    total_pv_base: Decimal
    total_pv_low: Decimal
    total_pv_high: Decimal
    annual_totals: list[dict[str, Any]]
    phase_totals: dict[str, dict[str, Decimal]]
    growth_plan: GrowthPlan
    execution_permitted: bool = False


# ---------------------------------------------------------------------------
# Input validation and extraction
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


def _validate_line_item(item: dict[str, Any], index: int | str) -> BudgetLine:
    """Validate and convert a raw line item dict to a BudgetLine."""
    required = ("line_id", "description", "phase", "cost_behavior", "quantity", "base_unit_cost")
    for key in required:
        if key not in item:
            raise ValueError(f"line item {index}: missing required field '{key}'")

    behavior = item["cost_behavior"]
    if behavior not in ("one_time", "fixed_recurring", "variable", "step_fixed", "capitalized"):
        raise ValueError(f"line item {index}: unknown cost_behavior '{behavior}'")

    quantity = _decimal(item["quantity"])
    if quantity < 0:
        raise ValueError(f"line item {index}: quantity must be non-negative")

    base_cost = _decimal(item["base_unit_cost"])
    if base_cost < 0:
        raise ValueError(f"line item {index}: base_unit_cost must be non-negative")

    low_cost = _decimal(item["low_unit_cost"]) if item.get("low_unit_cost") is not None else None
    high_cost = _decimal(item["high_unit_cost"]) if item.get("high_unit_cost") is not None else None

    if low_cost is not None and low_cost > base_cost:
        raise ValueError(f"line item {index}: low_unit_cost exceeds base_unit_cost")
    if high_cost is not None and high_cost < base_cost:
        raise ValueError(f"line item {index}: high_unit_cost below base_unit_cost")

    escalation = _decimal(item.get("escalation_pct", 0))
    if escalation < Decimal("-1"):
        raise ValueError(f"line item {index}: escalation_pct must be >= -1")

    recurrence = item.get("recurrence_months")
    if behavior in ("fixed_recurring", "variable"):
        if recurrence is None or recurrence < 1:
            raise ValueError(f"line item {index}: {behavior} requires recurrence_months >= 1")
        recurrence = int(recurrence)
    else:
        recurrence = None

    start_month = int(item.get("start_month", 0))
    if start_month < 0:
        raise ValueError(f"line item {index}: start_month must be non-negative")

    useful_life = item.get("useful_life_months")
    if useful_life is not None:
        useful_life = int(useful_life)
        if useful_life < 1:
            raise ValueError(f"line item {index}: useful_life_months must be positive")

    waste = _decimal(item.get("waste_factor", 0))
    if waste < 0 or waste > 1:
        raise ValueError(f"line item {index}: waste_factor must be between 0 and 1")

    return BudgetLine(
        line_id=str(item["line_id"]),
        description=str(item["description"]),
        phase=str(item["phase"]),
        cost_behavior=behavior,
        quantity=quantity,
        waste_factor=waste,
        base_unit_cost=base_cost,
        low_unit_cost=low_cost,
        high_unit_cost=high_cost,
        currency=str(item.get("currency", "USD")),
        escalation_pct=escalation,
        recurrence_months=recurrence,
        start_month=start_month,
        useful_life_months=useful_life,
        pricing_status=str(item.get("pricing_status", "sourced")),
    )


def _validate_horizon(horizon_months: int) -> int:
    if not isinstance(horizon_months, int) or isinstance(horizon_months, bool):
        raise ValueError("horizon_months must be an integer")
    if not 1 <= horizon_months <= 600:
        raise ValueError("horizon_months must be between 1 and 600 (50 years)")
    return horizon_months


def _validate_discount_rate(rate: float | Decimal) -> Decimal:
    rate_d = _decimal(rate)
    if rate_d < 0 or rate_d >= 1:
        raise ValueError("discount_rate must be in [0, 1)")
    return rate_d


def _validate_contingency(pct: float | Decimal) -> Decimal:
    pct_d = _decimal(pct)
    if pct_d < 0 or pct_d > 1:
        raise ValueError("contingency_pct must be between 0 and 1")
    return pct_d


# ---------------------------------------------------------------------------
# Core forecasting logic
# ---------------------------------------------------------------------------


def _capacity_multiplier(
    month: int,
    growth_plan: GrowthPlan,
    behavior: str,
) -> Decimal:
    """Compute the capacity multiplier for a given month and cost behavior.

    Only variable and step_fixed costs scale with capacity growth.
    """
    if behavior not in ("variable", "step_fixed"):
        return Decimal("1")

    multiplier = Decimal("1")

    # Apply compounding monthly capacity growth
    if growth_plan.monthly_capacity_growth != 0:
        multiplier *= (Decimal("1") + growth_plan.monthly_capacity_growth) ** month

    # Apply expansion phases (step changes)
    for phase_month, phase_multiplier in growth_plan.expansion_phases:
        if month >= phase_month:
            multiplier *= phase_multiplier

    return multiplier


def _cost_reduction_multiplier(month: int, growth_plan: GrowthPlan) -> Decimal:
    """Compute the cost reduction multiplier for a given month.

    Applied to all recurring costs (efficiency improvements over time).
    """
    if growth_plan.monthly_cost_reduction == 0:
        return Decimal("1")
    return (Decimal("1") - growth_plan.monthly_cost_reduction) ** month


def _escalation_multiplier(month: int, line: BudgetLine) -> Decimal:
    """Compute the escalation multiplier for a given month relative to line start."""
    if line.escalation_pct == 0:
        return Decimal("1")
    months_elapsed = month - line.start_month
    if months_elapsed <= 0:
        return Decimal("1")
    years = Decimal(months_elapsed) / Decimal("12")
    return (Decimal("1") + line.escalation_pct) ** years


def _discount_factor(month: int, discount_rate: Decimal) -> Decimal:
    """Compute the discount factor for present value calculation."""
    if discount_rate == 0:
        return Decimal("1")
    years = Decimal(month) / Decimal("12")
    return (Decimal("1") + discount_rate) ** (-years)


def _line_active_in_month(line: BudgetLine, month: int) -> bool:
    """Determine if a line item has a cost in the given month."""
    if month < line.start_month:
        return False

    if line.cost_behavior == "one_time":
        return month == line.start_month

    if line.cost_behavior == "capitalized":
        # Capitalized costs are one-time at start but may have a useful life
        # for depreciation purposes; for budget purposes, they hit at start.
        return month == line.start_month

    if line.cost_behavior in ("fixed_recurring", "variable"):
        if line.recurrence_months is None:
            return False
        months_since_start = month - line.start_month
        return months_since_start % line.recurrence_months == 0

    if line.cost_behavior == "step_fixed":
        # Step-fixed: constant within each recurrence period
        if line.recurrence_months is None:
            return False
        months_since_start = month - line.start_month
        return months_since_start % line.recurrence_months == 0

    return False


def _line_cost_in_month(line: BudgetLine, month: int, growth_plan: GrowthPlan) -> tuple[Decimal, Decimal, Decimal]:
    """Compute the cost of a line item in a given month.

    Returns (base, low, high) tuple.
    """
    if not _line_active_in_month(line, month):
        return Decimal("0"), Decimal("0"), Decimal("0")

    base = line.extended_base
    low = line.extended_low
    high = line.extended_high

    # Apply escalation
    esc = _escalation_multiplier(month, line)
    base *= esc
    low *= esc
    high *= esc

    # Apply capacity multiplier (only for variable/step_fixed)
    cap = _capacity_multiplier(month, growth_plan, line.cost_behavior)
    base *= cap
    low *= cap
    high *= cap

    # Apply cost reduction (only for recurring costs)
    if line.cost_behavior in ("fixed_recurring", "variable", "step_fixed"):
        red = _cost_reduction_multiplier(month, growth_plan)
        base *= red
        low *= red
        high *= red

    return base, low, high


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def forecast_budget(
    *,
    line_items: list[dict[str, Any]],
    horizon_months: int,
    discount_rate: float | Decimal = 0.0,
    contingency_pct: float | Decimal = 0.0,
    growth_plan: dict[str, Any] | GrowthPlan | None = None,
    currency: str = "USD",
) -> dict[str, Any]:
    """Forecast future budgets from line items and growth plans.

    Args:
        line_items: List of line item dicts (from estimate_line_items or cost actuals).
        horizon_months: Number of months to forecast (1-600).
        discount_rate: Annual discount rate for present value (0-1).
        contingency_pct: Contingency percentage to add (0-1).
        growth_plan: Growth assumptions (dict or GrowthPlan).
        currency: Currency code for the forecast.

    Returns:
        A dict with monthly budgets, annual totals, phase totals, and metadata.
    """
    horizon = _validate_horizon(horizon_months)
    rate = _validate_discount_rate(discount_rate)
    contingency = _validate_contingency(contingency_pct)

    if isinstance(growth_plan, GrowthPlan):
        plan = growth_plan
    else:
        plan = GrowthPlan.from_dict(growth_plan)

    # Validate and convert line items
    lines: list[BudgetLine] = []
    for i, item in enumerate(line_items):
        lines.append(_validate_line_item(item, i))

    # Add new lines from growth plan
    for i, item in enumerate(plan.new_lines):
        lines.append(_validate_line_item(item, f"new_{i}"))

    # Compute monthly budgets
    monthly: list[MonthlyBudget] = []
    for month in range(horizon):
        mb = MonthlyBudget(month=month)
        discount = _discount_factor(month, rate)

        for line in lines:
            base, low, high = _line_cost_in_month(line, month, plan)
            if base == 0 and low == 0 and high == 0:
                continue

            mb.base += base
            mb.low += low
            mb.high += high
            mb.present_value_base += base * discount
            mb.present_value_low += low * discount
            mb.present_value_high += high * discount
            mb.line_count += 1

            # Phase aggregation
            mb.by_phase[line.phase] = mb.by_phase.get(line.phase, Decimal("0")) + base
            mb.by_phase_low[line.phase] = mb.by_phase_low.get(line.phase, Decimal("0")) + low
            mb.by_phase_high[line.phase] = mb.by_phase_high.get(line.phase, Decimal("0")) + high

        # Apply contingency
        if contingency > 0:
            mb.base *= (Decimal("1") + contingency)
            mb.low *= (Decimal("1") + contingency)
            mb.high *= (Decimal("1") + contingency)
            mb.present_value_base *= (Decimal("1") + contingency)
            mb.present_value_low *= (Decimal("1") + contingency)
            mb.present_value_high *= (Decimal("1") + contingency)

        monthly.append(mb)

    # Compute totals
    total_base = sum((mb.base for mb in monthly), Decimal("0"))
    total_low = sum((mb.low for mb in monthly), Decimal("0"))
    total_high = sum((mb.high for mb in monthly), Decimal("0"))
    total_pv_base = sum((mb.present_value_base for mb in monthly), Decimal("0"))
    total_pv_low = sum((mb.present_value_low for mb in monthly), Decimal("0"))
    total_pv_high = sum((mb.present_value_high for mb in monthly), Decimal("0"))

    # Annual aggregation
    annual_totals: list[dict[str, Any]] = []
    for year_start in range(0, horizon, 12):
        year_end = min(year_start + 12, horizon)
        year_months = monthly[year_start:year_end]
        year_num = year_start // 12 + 1
        annual_totals.append({
            "year": year_num,
            "months": f"M{year_start + 1}-M{year_end}",
            "base": _round_decimal(sum((mb.base for mb in year_months), Decimal("0"))),
            "low": _round_decimal(sum((mb.low for mb in year_months), Decimal("0"))),
            "high": _round_decimal(sum((mb.high for mb in year_months), Decimal("0"))),
            "pv_base": _round_decimal(sum((mb.present_value_base for mb in year_months), Decimal("0"))),
            "pv_low": _round_decimal(sum((mb.present_value_low for mb in year_months), Decimal("0"))),
            "pv_high": _round_decimal(sum((mb.present_value_high for mb in year_months), Decimal("0"))),
        })

    # Phase totals
    phase_totals: dict[str, dict[str, Decimal]] = {}
    all_phases: set[str] = set()
    for mb in monthly:
        all_phases.update(mb.by_phase.keys())
    for phase in sorted(all_phases):
        phase_totals[phase] = {
            "base": sum((mb.by_phase.get(phase, Decimal("0")) for mb in monthly), Decimal("0")),
            "low": sum((mb.by_phase_low.get(phase, Decimal("0")) for mb in monthly), Decimal("0")),
            "high": sum((mb.by_phase_high.get(phase, Decimal("0")) for mb in monthly), Decimal("0")),
        }

    result = BudgetForecast(
        horizon_months=horizon,
        currency=currency,
        discount_rate=rate,
        contingency_pct=contingency,
        monthly_budgets=monthly,
        total_base=total_base,
        total_low=total_low,
        total_high=total_high,
        total_pv_base=total_pv_base,
        total_pv_low=total_pv_low,
        total_pv_high=total_pv_high,
        annual_totals=annual_totals,
        phase_totals=phase_totals,
        growth_plan=plan,
    )

    return _forecast_to_dict(result)


def forecast_from_estimate(
    *,
    estimate_id: str,
    line_items: list[dict[str, Any]],
    horizon_months: int,
    discount_rate: float | Decimal = 0.0,
    contingency_pct: float | Decimal = 0.0,
    growth_plan: dict[str, Any] | GrowthPlan | None = None,
    currency: str = "USD",
) -> dict[str, Any]:
    """Forecast budget from an estimate's line items.

    Convenience wrapper that tags the forecast with the estimate ID.
    """
    result = forecast_budget(
        line_items=line_items,
        horizon_months=horizon_months,
        discount_rate=discount_rate,
        contingency_pct=contingency_pct,
        growth_plan=growth_plan,
        currency=currency,
    )
    result["estimate_id"] = estimate_id
    return result


def compare_scenarios(
    *,
    scenarios: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare multiple budget forecast scenarios.

    Each scenario dict must have 'name' and 'line_items' keys, plus optional
    'growth_plan', 'discount_rate', 'contingency_pct'.

    Returns a comparison with side-by-side totals and variance analysis.
    """
    if not scenarios:
        raise ValueError("at least one scenario is required")
    if len(scenarios) > 10:
        raise ValueError("maximum 10 scenarios can be compared")

    results = []
    for i, scenario in enumerate(scenarios):
        name = scenario.get("name", f"Scenario {i + 1}")
        line_items = scenario.get("line_items", [])
        if not line_items:
            raise ValueError(f"scenario '{name}' has no line_items")

        forecast = forecast_budget(
            line_items=line_items,
            horizon_months=scenario.get("horizon_months", 36),
            discount_rate=scenario.get("discount_rate", 0.0),
            contingency_pct=scenario.get("contingency_pct", 0.0),
            growth_plan=scenario.get("growth_plan"),
            currency=scenario.get("currency", "USD"),
        )
        forecast["name"] = name
        results.append(forecast)

    # Compute variance between scenarios
    comparison: dict[str, Any] = {
        "scenarios": results,
        "variance": {},
    }

    if len(results) >= 2:
        base_totals = [r["total_base"] for r in results]
        comparison["variance"] = {
            "max_base": max(base_totals),
            "min_base": min(base_totals),
            "spread": max(base_totals) - min(base_totals),
            "spread_pct": (
                (max(base_totals) - min(base_totals)) / min(base_totals)
                if min(base_totals) > 0
                else Decimal("0")
            ),
        }

    return comparison


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _round_decimal(value: Decimal | int, places: int = 2) -> Decimal:
    """Round a Decimal to the specified number of decimal places."""
    quantize_str = "0." + "0" * places
    return Decimal(str(value)).quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)


def _forecast_to_dict(forecast: BudgetForecast) -> dict[str, Any]:
    """Convert a BudgetForecast to a JSON-serializable dict."""
    return {
        "horizon_months": forecast.horizon_months,
        "currency": forecast.currency,
        "discount_rate": float(forecast.discount_rate),
        "contingency_pct": float(forecast.contingency_pct),
        "total_base": _round_decimal(forecast.total_base),
        "total_low": _round_decimal(forecast.total_low),
        "total_high": _round_decimal(forecast.total_high),
        "total_pv_base": _round_decimal(forecast.total_pv_base),
        "total_pv_low": _round_decimal(forecast.total_pv_low),
        "total_pv_high": _round_decimal(forecast.total_pv_high),
        "monthly_budgets": [
            {
                "month": mb.month,
                "base": _round_decimal(mb.base),
                "low": _round_decimal(mb.low),
                "high": _round_decimal(mb.high),
                "present_value_base": _round_decimal(mb.present_value_base),
                "present_value_low": _round_decimal(mb.present_value_low),
                "present_value_high": _round_decimal(mb.present_value_high),
                "by_phase": {k: _round_decimal(v) for k, v in mb.by_phase.items()},
                "by_phase_low": {k: _round_decimal(v) for k, v in mb.by_phase_low.items()},
                "by_phase_high": {k: _round_decimal(v) for k, v in mb.by_phase_high.items()},
                "line_count": mb.line_count,
            }
            for mb in forecast.monthly_budgets
        ],
        "annual_totals": forecast.annual_totals,
        "phase_totals": {
            phase: {k: _round_decimal(v) for k, v in totals.items()}
            for phase, totals in forecast.phase_totals.items()
        },
        "growth_plan": {
            "monthly_capacity_growth": float(forecast.growth_plan.monthly_capacity_growth),
            "monthly_cost_reduction": float(forecast.growth_plan.monthly_cost_reduction),
            "expansion_phases": [
                [m, float(v)] for m, v in forecast.growth_plan.expansion_phases
            ],
            "new_line_count": len(forecast.growth_plan.new_lines),
        },
        "execution_permitted": False,
    }


def compute_unit_economics(
    *,
    total_cost: float | Decimal,
    horizon_years: float | Decimal,
    discount_rate: float | Decimal = 0.0,
    denominator: float | Decimal | None = None,
    denominator_unit: str = "",
) -> dict[str, Any]:
    """Compute equivalent annual cost and optional unit economics.

    For present value PV, horizon n years, annual discount rate r:
    - EAC = PV / n when r = 0
    - EAC = PV * r / (1 - (1+r)^(-n)) when r > 0

    If denominator is provided, also computes cost per unit.
    """
    pv = _decimal(total_cost)
    n = _decimal(horizon_years)
    r = _decimal(discount_rate)

    if pv < 0:
        raise ValueError("total_cost must be non-negative")
    if n <= 0:
        raise ValueError("horizon_years must be positive")
    if r < 0 or r >= 1:
        raise ValueError("discount_rate must be in [0, 1)")

    if r == 0:
        eac = pv / n
    else:
        eac = pv * r / (Decimal("1") - (Decimal("1") + r) ** (-n))

    result: dict[str, Any] = {
        "present_value": _round_decimal(pv),
        "horizon_years": float(n),
        "discount_rate": float(r),
        "equivalent_annual_cost": _round_decimal(eac),
    }

    if denominator is not None:
        denom = _decimal(denominator)
        if denom <= 0:
            raise ValueError("denominator must be positive")
        result["cost_per_unit"] = _round_decimal(eac / denom)
        result["denominator_unit"] = denominator_unit

    return result
