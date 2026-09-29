"""Total Cost of Ownership (TCO) calculator for Data Center Commander.

Computes lifecycle TCO over a defined horizon, including:
- Upfront CapEx (hardware, facility, design, commissioning)
- Recurring OpEx (energy, maintenance, labor, network, software)
- Refresh/replacement costs at specified intervals
- Terminal costs (decommissioning, residual value)
- Escalation and discount rate effects
- Year-by-year cash flow breakdown
- Present value and equivalent annual cost

All calculations are deterministic and read-only. No I/O, no persistence.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TCOAssumptions:
    """Shared assumptions for TCO calculations.

    Attributes:
        currency: ISO 4217 currency code (3 letters).
        horizon_years: Analysis horizon in years (1-50).
        annual_discount_rate: Annual discount rate as a decimal (0.0-1.0).
        energy_escalation_pct: Annual energy cost escalation rate.
        maintenance_escalation_pct: Annual maintenance cost escalation rate.
        labor_escalation_pct: Annual labor cost escalation rate.
        other_escalation_pct: Annual escalation for other recurring costs.
        contingency_pct: Contingency percentage applied to all costs (0-1).
        tax_rate: Effective tax rate for after-tax analysis (0-1).
        include_tax: Whether to compute after-tax TCO.
    """

    currency: str = "USD"
    horizon_years: int = 10
    annual_discount_rate: float = 0.08
    energy_escalation_pct: float = 0.03
    maintenance_escalation_pct: float = 0.025
    labor_escalation_pct: float = 0.03
    other_escalation_pct: float = 0.02
    contingency_pct: float = 0.0
    tax_rate: float = 0.0
    include_tax: bool = False

    def __post_init__(self) -> None:
        if not (isinstance(self.currency, str) and len(self.currency) == 3
                and self.currency.isalpha() and self.currency.isupper()):
            raise ValueError("currency must be a 3-letter ISO code (e.g. USD)")
        if not (isinstance(self.horizon_years, int) and not isinstance(self.horizon_years, bool)
                and 1 <= self.horizon_years <= 50):
            raise ValueError("horizon_years must be an integer from 1 to 50")
        if not (isinstance(self.annual_discount_rate, (int, float))
                and not isinstance(self.annual_discount_rate, bool)
                and 0.0 <= self.annual_discount_rate <= 1.0):
            raise ValueError("annual_discount_rate must be between 0.0 and 1.0")
        for name, val in [
            ("energy_escalation_pct", self.energy_escalation_pct),
            ("maintenance_escalation_pct", self.maintenance_escalation_pct),
            ("labor_escalation_pct", self.labor_escalation_pct),
            ("other_escalation_pct", self.other_escalation_pct),
        ]:
            if not (isinstance(val, (int, float)) and not isinstance(val, bool)
                    and -1.0 <= val <= 1.0):
                raise ValueError(f"{name} must be between -1.0 and 1.0")
        if not (isinstance(self.contingency_pct, (int, float))
                and not isinstance(self.contingency_pct, bool)
                and 0.0 <= self.contingency_pct <= 1.0):
            raise ValueError("contingency_pct must be between 0.0 and 1.0")
        if not (isinstance(self.tax_rate, (int, float))
                and not isinstance(self.tax_rate, bool)
                and 0.0 <= self.tax_rate <= 1.0):
            raise ValueError("tax_rate must be between 0.0 and 1.0")
        if not isinstance(self.include_tax, bool):
            raise ValueError("include_tax must be a boolean")


@dataclass
class TCOCostBreakdown:
    """Detailed cost structure for TCO analysis.

    All amounts are in the scenario currency. One-time costs occur at year 0;
    annual costs recur each year; refresh costs occur at specified years;
    terminal costs occur at the end of the horizon.

    Attributes:
        # Upfront CapEx (year 0)
        hardware_capex: IT hardware (servers, storage, network).
        facility_capex: Facility build-out and infrastructure.
        design_capex: Design, engineering, and project management.
        commissioning_capex: Commissioning and testing.
        migration_capex: Migration and integration.
        software_capex: One-time software licenses.
        # Annual OpEx (recurring)
        energy_annual: Annual energy and cooling costs.
        maintenance_annual: Annual maintenance and support.
        labor_annual: Annual operations labor.
        network_annual: Annual connectivity and transit.
        software_annual: Annual software subscriptions/licenses.
        insurance_annual: Annual insurance premiums.
        tax_annual: Annual property and other taxes.
        other_annual: Other recurring annual costs.
        # Refresh/replacement
        refresh_cost: One-time refresh CapEx amount.
        refresh_interval_years: Years between refreshes (0 = no refresh).
        # Terminal
        decommission_cost: Decommissioning/disposal cost at horizon end.
        residual_value: Residual/salvage value credit at horizon end.
    """

    # Upfront CapEx
    hardware_capex: float = 0.0
    facility_capex: float = 0.0
    design_capex: float = 0.0
    commissioning_capex: float = 0.0
    migration_capex: float = 0.0
    software_capex: float = 0.0

    # Annual OpEx
    energy_annual: float = 0.0
    maintenance_annual: float = 0.0
    labor_annual: float = 0.0
    network_annual: float = 0.0
    software_annual: float = 0.0
    insurance_annual: float = 0.0
    tax_annual: float = 0.0
    other_annual: float = 0.0

    # Refresh
    refresh_cost: float = 0.0
    refresh_interval_years: int = 0

    # Terminal
    decommission_cost: float = 0.0
    residual_value: float = 0.0

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if name == "refresh_interval_years":
                if not (isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 50):
                    raise ValueError("refresh_interval_years must be an integer from 0 to 50")
            else:
                if not (isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0):
                    raise ValueError(f"{name} must be a non-negative number")

    @property
    def total_upfront(self) -> float:
        """Total one-time CapEx at year 0."""
        return (self.hardware_capex + self.facility_capex + self.design_capex
                + self.commissioning_capex + self.migration_capex + self.software_capex)

    @property
    def total_annual_opex(self) -> float:
        """Total recurring annual OpEx (before escalation)."""
        return (self.energy_annual + self.maintenance_annual + self.labor_annual
                + self.network_annual + self.software_annual + self.insurance_annual
                + self.tax_annual + self.other_annual)

    @property
    def terminal_net(self) -> float:
        """Net terminal cost (decommission minus residual value)."""
        return self.decommission_cost - self.residual_value

    @property
    def total_capex(self) -> float:
        """All capital expenditures including refresh."""
        return self.total_upfront + self.refresh_cost

    @property
    def total_opex(self) -> float:
        """All operational expenditures."""
        return self.total_annual_opex


@dataclass
class YearlyCashFlow:
    """Cash flow for a single year in the TCO analysis.

    Attributes:
        year: Year number (0 = upfront, 1..N = operating years).
        capex: Capital expenditure in this year.
        opex: Operational expenditure in this year.
        refresh: Refresh/replacement cost in this year.
        terminal: Terminal cost (net) in this year.
        total_undiscounted: Sum of all costs in this year (undiscounted).
        discount_factor: Discount factor applied to this year.
        total_discounted: Total cost discounted to present value.
    """

    year: int
    capex: float = 0.0
    opex: float = 0.0
    refresh: float = 0.0
    terminal: float = 0.0
    total_undiscounted: float = 0.0
    discount_factor: float = 1.0
    total_discounted: float = 0.0


@dataclass
class TCOResult:
    """Computed TCO results for a single scenario.

    Attributes:
        scenario_name: Name of the scenario.
        scenario_type: Deployment type label.
        total_capex: Total capital expenditure (undiscounted).
        total_opex: Total operational expenditure (undiscounted).
        total_refresh: Total refresh costs (undiscounted).
        total_terminal: Net terminal cost (undiscounted).
        total_undiscounted: Sum of all costs without discounting.
        total_pv: Net present value of all cash flows.
        equivalent_annual_cost: EAC over the horizon.
        average_annual_cost: Undiscounted total divided by horizon years.
        year_one_cash: Undiscounted cash in year 1 (first operating year).
        year_zero_cash: Undiscounted cash at year 0 (upfront).
        cost_per_kw_year: TCO per IT kW-year (if capacity provided).
        cost_per_rack_year: TCO per rack-year (if rack count provided).
        cost_per_m2_year: TCO per m2-year (if area provided).
        cost_per_kwh: TCO per kWh (if energy provided).
        after_tax_pv: After-tax present value (if tax analysis enabled).
        after_tax_eac: After-tax equivalent annual cost.
        horizon_years: Analysis horizon in years.
        currency: Currency code.
        it_capacity_kw: IT capacity in kW (optional).
        rack_count: Number of racks (optional).
        area_m2: Floor area in m2 (optional).
        total_energy_kwh: Total energy over horizon in kWh (optional).
        yearly_cash_flows: List of YearlyCashFlow for each year.
        assumptions: The TCOAssumptions used.
    """

    scenario_name: str
    scenario_type: str
    total_capex: float
    total_opex: float
    total_refresh: float
    total_terminal: float
    total_undiscounted: float
    total_pv: float
    equivalent_annual_cost: float
    average_annual_cost: float
    year_one_cash: float
    year_zero_cash: float
    cost_per_kw_year: float | None
    cost_per_rack_year: float | None
    cost_per_m2_year: float | None
    cost_per_kwh: float | None
    after_tax_pv: float | None
    after_tax_eac: float | None
    horizon_years: int
    currency: str
    it_capacity_kw: float | None = None
    rack_count: float | None = None
    area_m2: float | None = None
    total_energy_kwh: float | None = None
    yearly_cash_flows: list[YearlyCashFlow] = field(default_factory=list)
    assumptions: TCOAssumptions | None = None


@dataclass
class TCOScenario:
    """A named TCO scenario with cost structure and metadata.

    Attributes:
        name: Human-readable scenario name (1-120 chars).
        description: Optional longer description.
        scenario_type: Deployment type label (e.g. "on-prem", "colocation", "cloud").
        costs: TCOCostBreakdown for this scenario.
        assumptions: TCOAssumptions for this scenario.
        it_capacity_kw: IT capacity in kW (optional, for unit economics).
        rack_count: Number of racks (optional).
        area_m2: Floor area in m2 (optional).
        annual_energy_kwh: Annual energy consumption in kWh (optional).
        tags: Optional list of string tags for filtering/grouping.
        metadata: Optional dict for additional caller-specific data.
    """

    name: str
    costs: TCOCostBreakdown
    assumptions: TCOAssumptions = field(default_factory=TCOAssumptions)
    description: str = ""
    scenario_type: str = "on-prem"
    it_capacity_kw: float | None = None
    rack_count: float | None = None
    area_m2: float | None = None
    annual_energy_kwh: float | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (isinstance(self.name, str) and 1 <= len(self.name.strip()) <= 120):
            raise ValueError("name must contain 1-120 characters")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string")
        if not isinstance(self.scenario_type, str) or not self.scenario_type.strip():
            raise ValueError("scenario_type must be a non-empty string")
        if not isinstance(self.tags, list) or not all(isinstance(t, str) for t in self.tags):
            raise ValueError("tags must be a list of strings")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")


@dataclass
class TCOComparison:
    """Side-by-side comparison of multiple TCO scenarios.

    Attributes:
        scenarios: List of TCOResult objects.
        baseline_index: Index of the baseline scenario in the list.
        pv_deltas: PV difference from baseline for each scenario.
        eac_deltas: EAC difference from baseline for each scenario.
        undiscounted_deltas: Undiscounted total difference from baseline.
        lower_pv_index: Index of the scenario with lowest PV.
        lower_eac_index: Index of scenario with lowest EAC.
        summary: Human-readable summary string.
    """

    scenarios: list[TCOResult]
    baseline_index: int = 0
    pv_deltas: list[float] = field(default_factory=list)
    eac_deltas: list[float] = field(default_factory=list)
    undiscounted_deltas: list[float] = field(default_factory=list)
    lower_pv_index: int = 0
    lower_eac_index: int = 0
    summary: str = ""


@dataclass
class TCOSensitivity:
    """Sensitivity analysis results for a single TCO parameter.

    Attributes:
        parameter_name: Name of the parameter varied.
        parameter_label: Human-readable label.
        base_value: Base case parameter value.
        values_tested: List of parameter values tested.
        pv_results: PV for each tested value.
        eac_results: EAC for each tested value.
        undiscounted_results: Undiscounted total for each tested value.
        pv_range: (min, max) PV across tested values.
        eac_range: (min, max) EAC across tested values.
        pv_sensitivity: Range of PV variation (max - min).
        eac_sensitivity: Range of EAC variation.
    """

    parameter_name: str
    parameter_label: str
    base_value: float
    values_tested: list[float]
    pv_results: list[float]
    eac_results: list[float]
    undiscounted_results: list[float]
    pv_range: tuple[float, float]
    eac_range: tuple[float, float]
    pv_sensitivity: float
    eac_sensitivity: float


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------


def _discount_factor(year: int, rate: float) -> float:
    """Compute the discount factor for a given year."""
    if rate == 0:
        return 1.0
    return (1.0 + rate) ** (-year)


def _escalation_factor(year: int, rate: float) -> float:
    """Compute the escalation factor for a given year."""
    if rate == 0:
        return 1.0
    return (1.0 + rate) ** year


def _compute_yearly_cash_flows(
    costs: TCOCostBreakdown,
    assumptions: TCOAssumptions,
) -> list[YearlyCashFlow]:
    """Compute year-by-year cash flows for the TCO analysis.

    Cash flow timing:
    - Year 0: Upfront CapEx (no discounting).
    - Years 1..N: Annual OpEx with escalation, refresh costs, terminal.
    - Terminal cost at final year.
    """
    horizon = assumptions.horizon_years
    rate = assumptions.annual_discount_rate
    contingency = assumptions.contingency_pct

    flows: list[YearlyCashFlow] = []

    # Year 0: Upfront CapEx
    year0_capex = costs.total_upfront * (1.0 + contingency)
    df0 = _discount_factor(0, rate)
    flows.append(YearlyCashFlow(
        year=0,
        capex=year0_capex,
        total_undiscounted=year0_capex,
        discount_factor=df0,
        total_discounted=year0_capex * df0,
    ))

    # Years 1..N: Operating costs
    for year in range(1, horizon + 1):
        # Escalated OpEx
        energy = costs.energy_annual * _escalation_factor(year, assumptions.energy_escalation_pct)
        maintenance = costs.maintenance_annual * _escalation_factor(year, assumptions.maintenance_escalation_pct)
        labor = costs.labor_annual * _escalation_factor(year, assumptions.labor_escalation_pct)
        other_opex = (costs.network_annual + costs.software_annual
                      + costs.insurance_annual + costs.tax_annual + costs.other_annual)
        other_opex *= _escalation_factor(year, assumptions.other_escalation_pct)

        annual_opex = energy + maintenance + labor + other_opex
        annual_opex *= (1.0 + contingency)

        # Refresh cost
        refresh = 0.0
        if (costs.refresh_cost > 0 and costs.refresh_interval_years > 0
                and year % costs.refresh_interval_years == 0
                and year < horizon):
            refresh = costs.refresh_cost * (1.0 + contingency)

        # Terminal cost (only in final year)
        terminal = 0.0
        if year == horizon:
            terminal = costs.terminal_net * (1.0 + contingency)

        total_undiscounted = annual_opex + refresh + terminal
        df = _discount_factor(year, rate)
        total_discounted = total_undiscounted * df

        flows.append(YearlyCashFlow(
            year=year,
            opex=annual_opex,
            refresh=refresh,
            terminal=terminal,
            total_undiscounted=total_undiscounted,
            discount_factor=df,
            total_discounted=total_discounted,
        ))

    return flows


def _equivalent_annual_cost(pv: float, years: int, rate: float) -> float:
    """Calculate equivalent annual cost from present value."""
    if years <= 0:
        raise ValueError("years must be positive")
    if rate == 0:
        return pv / years
    return pv * rate / (1.0 - (1.0 + rate) ** (-years))


def evaluate_tco(
    scenario: TCOScenario,
) -> TCOResult:
    """Evaluate a single TCO scenario and return computed results.

    Args:
        scenario: The TCO scenario to evaluate.

    Returns:
        TCOResult with all computed financial metrics.

    Raises:
        ValueError: If the scenario is invalid.
    """
    costs = scenario.costs
    assumptions = scenario.assumptions
    horizon = assumptions.horizon_years

    # Compute yearly cash flows
    yearly = _compute_yearly_cash_flows(costs, assumptions)

    # Aggregate totals
    total_capex = sum(f.capex for f in yearly)
    total_opex = sum(f.opex for f in yearly)
    total_refresh = sum(f.refresh for f in yearly)
    total_terminal = sum(f.terminal for f in yearly)
    total_undiscounted = sum(f.total_undiscounted for f in yearly)
    total_pv = sum(f.total_discounted for f in yearly)

    # EAC and averages
    eac = _equivalent_annual_cost(total_pv, horizon, assumptions.annual_discount_rate)
    avg_annual = total_undiscounted / horizon if horizon > 0 else 0.0
    year_one = yearly[1].total_undiscounted if len(yearly) > 1 else 0.0
    year_zero = yearly[0].total_undiscounted if yearly else 0.0

    # After-tax analysis
    after_tax_pv = None
    after_tax_eac = None
    if assumptions.include_tax and assumptions.tax_rate > 0:
        # Simple after-tax: tax shield on OpEx (not CapEx for simplicity)
        tax_rate = assumptions.tax_rate
        taxable_opex = total_opex * (1.0 - tax_rate)
        after_tax_undiscounted = total_capex + taxable_opex + total_refresh + total_terminal
        # Recompute PV with tax-adjusted OpEx
        at_pv = yearly[0].total_discounted  # CapEx at year 0 (no tax adjustment)
        for f in yearly[1:]:
            at_pv += (f.opex * (1.0 - tax_rate) + f.refresh + f.terminal) * f.discount_factor
        after_tax_pv = at_pv
        after_tax_eac = _equivalent_annual_cost(at_pv, horizon, assumptions.annual_discount_rate)

    # Unit economics
    cost_per_kw = None
    if scenario.it_capacity_kw is not None and scenario.it_capacity_kw > 0:
        cost_per_kw = eac / scenario.it_capacity_kw

    cost_per_rack = None
    if scenario.rack_count is not None and scenario.rack_count > 0:
        cost_per_rack = eac / scenario.rack_count

    cost_per_m2 = None
    if scenario.area_m2 is not None and scenario.area_m2 > 0:
        cost_per_m2 = eac / scenario.area_m2

    cost_per_kwh = None
    if scenario.annual_energy_kwh is not None and scenario.annual_energy_kwh > 0:
        total_energy = scenario.annual_energy_kwh * horizon
        cost_per_kwh = total_pv / total_energy if total_energy > 0 else None

    return TCOResult(
        scenario_name=scenario.name,
        scenario_type=scenario.scenario_type,
        total_capex=total_capex,
        total_opex=total_opex,
        total_refresh=total_refresh,
        total_terminal=total_terminal,
        total_undiscounted=total_undiscounted,
        total_pv=total_pv,
        equivalent_annual_cost=eac,
        average_annual_cost=avg_annual,
        year_one_cash=year_one,
        year_zero_cash=year_zero,
        cost_per_kw_year=cost_per_kw,
        cost_per_rack_year=cost_per_rack,
        cost_per_m2_year=cost_per_m2,
        cost_per_kwh=cost_per_kwh,
        after_tax_pv=after_tax_pv,
        after_tax_eac=after_tax_eac,
        horizon_years=horizon,
        currency=assumptions.currency,
        it_capacity_kw=scenario.it_capacity_kw,
        rack_count=scenario.rack_count,
        area_m2=scenario.area_m2,
        total_energy_kwh=(scenario.annual_energy_kwh * horizon
                          if scenario.annual_energy_kwh is not None else None),
        yearly_cash_flows=yearly,
        assumptions=assumptions,
    )


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def compare_tco(
    scenarios: list[TCOScenario],
    baseline_index: int = 0,
) -> TCOComparison:
    """Compare multiple TCO scenarios side-by-side.

    Args:
        scenarios: List of TCO scenarios to compare (at least 1).
        baseline_index: Index of the baseline scenario (default 0).

    Returns:
        TCOComparison with deltas and summary.

    Raises:
        ValueError: If scenarios list is empty or baseline_index is invalid.
    """
    if not scenarios:
        raise ValueError("at least one scenario is required for comparison")
    if not (0 <= baseline_index < len(scenarios)):
        raise ValueError(f"baseline_index {baseline_index} out of range for {len(scenarios)} scenarios")

    results = [evaluate_tco(s) for s in scenarios]
    baseline = results[baseline_index]

    pv_deltas = [r.total_pv - baseline.total_pv for r in results]
    eac_deltas = [r.equivalent_annual_cost - baseline.equivalent_annual_cost for r in results]
    undiscounted_deltas = [r.total_undiscounted - baseline.total_undiscounted for r in results]

    lower_pv_index = min(range(len(results)), key=lambda i: results[i].total_pv)
    lower_eac_index = min(range(len(results)), key=lambda i: results[i].equivalent_annual_cost)

    discount_rate = (
        baseline.assumptions.annual_discount_rate
        if baseline.assumptions is not None
        else 0.0
    )
    lines = [
        f"TCO comparison ({len(results)} scenarios, baseline: {baseline.scenario_name})",
        f"  Horizon: {baseline.horizon_years} years · Currency: {baseline.currency}",
        f"  Discount rate: {discount_rate:.1%}",
        "",
    ]
    for i, r in enumerate(results):
        marker = " [BASELINE]" if i == baseline_index else ""
        lines.append(
            f"  {r.scenario_name}{marker}: PV={r.total_pv:,.2f} · "
            f"EAC={r.equivalent_annual_cost:,.2f} · "
            f"undiscounted={r.total_undiscounted:,.2f}"
        )
        lines.append(
            f"    ΔPV={pv_deltas[i]:+,.2f} · "
            f"ΔEAC={eac_deltas[i]:+,.2f} · "
            f"Δundisc={undiscounted_deltas[i]:+,.2f}"
        )
    lines.append("")
    lines.append(f"  Lowest PV: {results[lower_pv_index].scenario_name}")
    lines.append(f"  Lowest EAC: {results[lower_eac_index].scenario_name}")

    return TCOComparison(
        scenarios=results,
        baseline_index=baseline_index,
        pv_deltas=pv_deltas,
        eac_deltas=eac_deltas,
        undiscounted_deltas=undiscounted_deltas,
        lower_pv_index=lower_pv_index,
        lower_eac_index=lower_eac_index,
        summary="\n".join(lines),
    )


# ---------------------------------------------------------------------------
# Sensitivity analysis
# ---------------------------------------------------------------------------


def run_tco_sensitivity(
    scenario: TCOScenario,
    parameter_name: str,
    values: list[float],
) -> TCOSensitivity:
    """Run sensitivity analysis on a single TCO scenario parameter.

    Supported parameters:
        - "discount_rate": Annual discount rate (0.0-1.0).
        - "energy_escalation": Energy escalation rate (-1.0 to 1.0).
        - "maintenance_escalation": Maintenance escalation rate (-1.0 to 1.0).
        - "labor_escalation": Labor escalation rate (-1.0 to 1.0).
        - "hardware_capex": Hardware CapEx multiplier (0.0-10.0).
        - "energy_annual": Annual energy cost multiplier (0.0-10.0).
        - "horizon_years": Analysis horizon (1-50).
        - "contingency": Contingency percentage (0.0-1.0).

    Args:
        scenario: Base scenario to analyze.
        parameter_name: Name of the parameter to vary.
        values: List of values to test.

    Returns:
        TCOSensitivity with results for each tested value.

    Raises:
        ValueError: If parameter_name is unsupported or values are invalid.
    """
    supported = {
        "discount_rate", "energy_escalation", "maintenance_escalation",
        "labor_escalation", "hardware_capex", "energy_annual",
        "horizon_years", "contingency",
    }
    if parameter_name not in supported:
        raise ValueError(f"unsupported parameter '{parameter_name}'. Supported: {sorted(supported)}")
    if not values:
        raise ValueError("at least one value is required for sensitivity analysis")

    labels = {
        "discount_rate": "Annual discount rate",
        "energy_escalation": "Energy escalation rate",
        "maintenance_escalation": "Maintenance escalation rate",
        "labor_escalation": "Labor escalation rate",
        "hardware_capex": "Hardware CapEx multiplier",
        "energy_annual": "Annual energy cost multiplier",
        "horizon_years": "Horizon (years)",
        "contingency": "Contingency percentage",
    }

    base_value = _get_tco_parameter(scenario, parameter_name)

    pv_results: list[float] = []
    eac_results: list[float] = []
    undiscounted_results: list[float] = []

    for val in values:
        modified = _set_tco_parameter(scenario, parameter_name, val)
        result = evaluate_tco(modified)
        pv_results.append(result.total_pv)
        eac_results.append(result.equivalent_annual_cost)
        undiscounted_results.append(result.total_undiscounted)

    pv_range = (min(pv_results), max(pv_results))
    eac_range = (min(eac_results), max(eac_results))

    return TCOSensitivity(
        parameter_name=parameter_name,
        parameter_label=labels[parameter_name],
        base_value=base_value,
        values_tested=list(values),
        pv_results=pv_results,
        eac_results=eac_results,
        undiscounted_results=undiscounted_results,
        pv_range=pv_range,
        eac_range=eac_range,
        pv_sensitivity=pv_range[1] - pv_range[0],
        eac_sensitivity=eac_range[1] - eac_range[0],
    )


def _get_tco_parameter(scenario: TCOScenario, parameter_name: str) -> float:
    """Get the current value of a parameter from a TCO scenario."""
    if parameter_name == "discount_rate":
        return scenario.assumptions.annual_discount_rate
    if parameter_name == "energy_escalation":
        return scenario.assumptions.energy_escalation_pct
    if parameter_name == "maintenance_escalation":
        return scenario.assumptions.maintenance_escalation_pct
    if parameter_name == "labor_escalation":
        return scenario.assumptions.labor_escalation_pct
    if parameter_name == "hardware_capex":
        return scenario.costs.hardware_capex
    if parameter_name == "energy_annual":
        return scenario.costs.energy_annual
    if parameter_name == "horizon_years":
        return float(scenario.assumptions.horizon_years)
    if parameter_name == "contingency":
        return scenario.assumptions.contingency_pct
    raise ValueError(f"unsupported parameter '{parameter_name}'")


def _set_tco_parameter(
    scenario: TCOScenario,
    parameter_name: str,
    value: float,
) -> TCOScenario:
    """Create a modified copy of a TCO scenario with a parameter changed.

    Returns a deep copy with the specified parameter set to the new value.
    The original scenario is not modified.
    """
    modified = copy.deepcopy(scenario)

    if parameter_name == "discount_rate":
        if not (0.0 <= value <= 1.0):
            raise ValueError("discount_rate must be between 0.0 and 1.0")
        modified.assumptions = TCOAssumptions(
            currency=modified.assumptions.currency,
            horizon_years=modified.assumptions.horizon_years,
            annual_discount_rate=value,
            energy_escalation_pct=modified.assumptions.energy_escalation_pct,
            maintenance_escalation_pct=modified.assumptions.maintenance_escalation_pct,
            labor_escalation_pct=modified.assumptions.labor_escalation_pct,
            other_escalation_pct=modified.assumptions.other_escalation_pct,
            contingency_pct=modified.assumptions.contingency_pct,
            tax_rate=modified.assumptions.tax_rate,
            include_tax=modified.assumptions.include_tax,
        )
    elif parameter_name == "energy_escalation":
        if not (-1.0 <= value <= 1.0):
            raise ValueError("energy_escalation must be between -1.0 and 1.0")
        modified.assumptions = TCOAssumptions(
            currency=modified.assumptions.currency,
            horizon_years=modified.assumptions.horizon_years,
            annual_discount_rate=modified.assumptions.annual_discount_rate,
            energy_escalation_pct=value,
            maintenance_escalation_pct=modified.assumptions.maintenance_escalation_pct,
            labor_escalation_pct=modified.assumptions.labor_escalation_pct,
            other_escalation_pct=modified.assumptions.other_escalation_pct,
            contingency_pct=modified.assumptions.contingency_pct,
            tax_rate=modified.assumptions.tax_rate,
            include_tax=modified.assumptions.include_tax,
        )
    elif parameter_name == "maintenance_escalation":
        if not (-1.0 <= value <= 1.0):
            raise ValueError("maintenance_escalation must be between -1.0 and 1.0")
        modified.assumptions = TCOAssumptions(
            currency=modified.assumptions.currency,
            horizon_years=modified.assumptions.horizon_years,
            annual_discount_rate=modified.assumptions.annual_discount_rate,
            energy_escalation_pct=modified.assumptions.energy_escalation_pct,
            maintenance_escalation_pct=value,
            labor_escalation_pct=modified.assumptions.labor_escalation_pct,
            other_escalation_pct=modified.assumptions.other_escalation_pct,
            contingency_pct=modified.assumptions.contingency_pct,
            tax_rate=modified.assumptions.tax_rate,
            include_tax=modified.assumptions.include_tax,
        )
    elif parameter_name == "labor_escalation":
        if not (-1.0 <= value <= 1.0):
            raise ValueError("labor_escalation must be between -1.0 and 1.0")
        modified.assumptions = TCOAssumptions(
            currency=modified.assumptions.currency,
            horizon_years=modified.assumptions.horizon_years,
            annual_discount_rate=modified.assumptions.annual_discount_rate,
            energy_escalation_pct=modified.assumptions.energy_escalation_pct,
            maintenance_escalation_pct=modified.assumptions.maintenance_escalation_pct,
            labor_escalation_pct=value,
            other_escalation_pct=modified.assumptions.other_escalation_pct,
            contingency_pct=modified.assumptions.contingency_pct,
            tax_rate=modified.assumptions.tax_rate,
            include_tax=modified.assumptions.include_tax,
        )
    elif parameter_name == "hardware_capex":
        if value < 0:
            raise ValueError("hardware_capex must be non-negative")
        modified.costs.hardware_capex = value
    elif parameter_name == "energy_annual":
        if value < 0:
            raise ValueError("energy_annual must be non-negative")
        modified.costs.energy_annual = value
    elif parameter_name == "horizon_years":
        if not (isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 50):
            raise ValueError("horizon_years must be an integer from 1 to 50")
        modified.assumptions = TCOAssumptions(
            currency=modified.assumptions.currency,
            horizon_years=value,
            annual_discount_rate=modified.assumptions.annual_discount_rate,
            energy_escalation_pct=modified.assumptions.energy_escalation_pct,
            maintenance_escalation_pct=modified.assumptions.maintenance_escalation_pct,
            labor_escalation_pct=modified.assumptions.labor_escalation_pct,
            other_escalation_pct=modified.assumptions.other_escalation_pct,
            contingency_pct=modified.assumptions.contingency_pct,
            tax_rate=modified.assumptions.tax_rate,
            include_tax=modified.assumptions.include_tax,
        )
    elif parameter_name == "contingency":
        if not (0.0 <= value <= 1.0):
            raise ValueError("contingency must be between 0.0 and 1.0")
        modified.assumptions = TCOAssumptions(
            currency=modified.assumptions.currency,
            horizon_years=modified.assumptions.horizon_years,
            annual_discount_rate=modified.assumptions.annual_discount_rate,
            energy_escalation_pct=modified.assumptions.energy_escalation_pct,
            maintenance_escalation_pct=modified.assumptions.maintenance_escalation_pct,
            labor_escalation_pct=modified.assumptions.labor_escalation_pct,
            other_escalation_pct=modified.assumptions.other_escalation_pct,
            contingency_pct=value,
            tax_rate=modified.assumptions.tax_rate,
            include_tax=modified.assumptions.include_tax,
        )
    else:
        raise ValueError(f"unsupported parameter '{parameter_name}'")

    return modified


# ---------------------------------------------------------------------------
# TCO Engine
# ---------------------------------------------------------------------------


class TCOEngine:
    """High-level engine for TCO analysis.

    Provides a fluent interface for building, comparing, and analyzing
    TCO scenarios. All methods are pure functions—no I/O.

    Example:
        engine = TCOEngine()
        engine.add_scenario(onprem_scenario)
        engine.add_scenario(colo_scenario)
        comparison = engine.compare()
        sensitivity = engine.sensitivity("discount_rate", [0.05, 0.08, 0.12])
    """

    def __init__(self) -> None:
        self._scenarios: list[TCOScenario] = []

    def add_scenario(self, scenario: TCOScenario) -> TCOEngine:
        """Add a scenario to the engine. Returns self for chaining."""
        self._scenarios.append(scenario)
        return self

    def remove_scenario(self, name: str) -> TCOEngine:
        """Remove a scenario by name. Returns self for chaining."""
        self._scenarios = [s for s in self._scenarios if s.name != name]
        return self

    def clear(self) -> TCOEngine:
        """Remove all scenarios. Returns self for chaining."""
        self._scenarios.clear()
        return self

    @property
    def scenarios(self) -> list[TCOScenario]:
        """Return a copy of the current scenario list."""
        return list(self._scenarios)

    @property
    def count(self) -> int:
        """Number of scenarios in the engine."""
        return len(self._scenarios)

    def evaluate(self, name: str | None = None) -> TCOResult | list[TCOResult]:
        """Evaluate one or all scenarios.

        Args:
            name: Scenario name to evaluate, or None for all.

        Returns:
            TCOResult for a single scenario, or list of all results.
        """
        if name is not None:
            for s in self._scenarios:
                if s.name == name:
                    return evaluate_tco(s)
            raise ValueError(f"scenario '{name}' not found")
        return [evaluate_tco(s) for s in self._scenarios]

    def compare(self, baseline: str | None = None) -> TCOComparison:
        """Compare all scenarios.

        Args:
            baseline: Name of baseline scenario, or None to use first.

        Returns:
            TCOComparison with all results and deltas.
        """
        if not self._scenarios:
            raise ValueError("no scenarios to compare")
        baseline_index = 0
        if baseline is not None:
            for i, s in enumerate(self._scenarios):
                if s.name == baseline:
                    baseline_index = i
                    break
            else:
                raise ValueError(f"baseline scenario '{baseline}' not found")
        return compare_tco(self._scenarios, baseline_index)

    def sensitivity(
        self,
        parameter_name: str,
        values: list[float],
        scenario_name: str | None = None,
    ) -> TCOSensitivity:
        """Run sensitivity analysis on a parameter.

        Args:
            parameter_name: Parameter to vary.
            values: Values to test.
            scenario_name: Scenario to analyze, or None for first.

        Returns:
            TCOSensitivity with results.
        """
        if not self._scenarios:
            raise ValueError("no scenarios for sensitivity analysis")
        target = self._scenarios[0]
        if scenario_name is not None:
            for s in self._scenarios:
                if s.name == scenario_name:
                    target = s
                    break
            else:
                raise ValueError(f"scenario '{scenario_name}' not found")
        return run_tco_sensitivity(target, parameter_name, values)

    def to_dict(self) -> dict[str, Any]:
        """Serialize all scenarios and their results to a dict."""
        return {
            "scenario_count": len(self._scenarios),
            "scenarios": [
                {
                    "name": s.name,
                    "type": s.scenario_type,
                    "description": s.description,
                    "tags": s.tags,
                    "assumptions": {
                        "currency": s.assumptions.currency,
                        "horizon_years": s.assumptions.horizon_years,
                        "annual_discount_rate": s.assumptions.annual_discount_rate,
                        "energy_escalation_pct": s.assumptions.energy_escalation_pct,
                        "maintenance_escalation_pct": s.assumptions.maintenance_escalation_pct,
                        "labor_escalation_pct": s.assumptions.labor_escalation_pct,
                        "other_escalation_pct": s.assumptions.other_escalation_pct,
                        "contingency_pct": s.assumptions.contingency_pct,
                        "tax_rate": s.assumptions.tax_rate,
                        "include_tax": s.assumptions.include_tax,
                    },
                    "costs": {
                        "hardware_capex": s.costs.hardware_capex,
                        "facility_capex": s.costs.facility_capex,
                        "design_capex": s.costs.design_capex,
                        "commissioning_capex": s.costs.commissioning_capex,
                        "migration_capex": s.costs.migration_capex,
                        "software_capex": s.costs.software_capex,
                        "energy_annual": s.costs.energy_annual,
                        "maintenance_annual": s.costs.maintenance_annual,
                        "labor_annual": s.costs.labor_annual,
                        "network_annual": s.costs.network_annual,
                        "software_annual": s.costs.software_annual,
                        "insurance_annual": s.costs.insurance_annual,
                        "tax_annual": s.costs.tax_annual,
                        "other_annual": s.costs.other_annual,
                        "refresh_cost": s.costs.refresh_cost,
                        "refresh_interval_years": s.costs.refresh_interval_years,
                        "decommission_cost": s.costs.decommission_cost,
                        "residual_value": s.costs.residual_value,
                    },
                    "result": evaluate_tco(s).__dict__,
                }
                for s in self._scenarios
            ],
        }


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def quick_tco(
    *,
    hardware_capex: float = 0.0,
    facility_capex: float = 0.0,
    design_capex: float = 0.0,
    commissioning_capex: float = 0.0,
    migration_capex: float = 0.0,
    software_capex: float = 0.0,
    energy_annual: float = 0.0,
    maintenance_annual: float = 0.0,
    labor_annual: float = 0.0,
    network_annual: float = 0.0,
    software_annual: float = 0.0,
    insurance_annual: float = 0.0,
    tax_annual: float = 0.0,
    other_annual: float = 0.0,
    refresh_cost: float = 0.0,
    refresh_interval_years: int = 0,
    decommission_cost: float = 0.0,
    residual_value: float = 0.0,
    horizon_years: int = 10,
    annual_discount_rate: float = 0.08,
    energy_escalation_pct: float = 0.03,
    maintenance_escalation_pct: float = 0.025,
    labor_escalation_pct: float = 0.03,
    other_escalation_pct: float = 0.02,
    contingency_pct: float = 0.0,
    currency: str = "USD",
    name: str = "TCO Analysis",
    scenario_type: str = "on-prem",
    it_capacity_kw: float | None = None,
    rack_count: float | None = None,
    area_m2: float | None = None,
    annual_energy_kwh: float | None = None,
) -> TCOResult:
    """Quick TCO calculation from individual cost components.

    Convenience function that builds a TCOScenario and evaluates it.
    All cost parameters are optional and default to 0.

    Returns:
        TCOResult with all computed metrics.
    """
    costs = TCOCostBreakdown(
        hardware_capex=hardware_capex,
        facility_capex=facility_capex,
        design_capex=design_capex,
        commissioning_capex=commissioning_capex,
        migration_capex=migration_capex,
        software_capex=software_capex,
        energy_annual=energy_annual,
        maintenance_annual=maintenance_annual,
        labor_annual=labor_annual,
        network_annual=network_annual,
        software_annual=software_annual,
        insurance_annual=insurance_annual,
        tax_annual=tax_annual,
        other_annual=other_annual,
        refresh_cost=refresh_cost,
        refresh_interval_years=refresh_interval_years,
        decommission_cost=decommission_cost,
        residual_value=residual_value,
    )
    assumptions = TCOAssumptions(
        currency=currency,
        horizon_years=horizon_years,
        annual_discount_rate=annual_discount_rate,
        energy_escalation_pct=energy_escalation_pct,
        maintenance_escalation_pct=maintenance_escalation_pct,
        labor_escalation_pct=labor_escalation_pct,
        other_escalation_pct=other_escalation_pct,
        contingency_pct=contingency_pct,
    )
    scenario = TCOScenario(
        name=name,
        costs=costs,
        assumptions=assumptions,
        scenario_type=scenario_type,
        it_capacity_kw=it_capacity_kw,
        rack_count=rack_count,
        area_m2=area_m2,
        annual_energy_kwh=annual_energy_kwh,
    )
    return evaluate_tco(scenario)


def tco_breakdown_by_category(result: TCOResult) -> dict[str, float]:
    """Break down TCO result into high-level categories.

    Returns a dict with keys: "capex", "opex", "refresh", "terminal", "total".
    """
    return {
        "capex": result.total_capex,
        "opex": result.total_opex,
        "refresh": result.total_refresh,
        "terminal": result.total_terminal,
        "total": result.total_undiscounted,
    }


def tco_cost_per_unit(
    result: TCOResult,
    unit_type: str,
    unit_value: float,
) -> float | None:
    """Compute TCO per unit for a given denominator.

    Args:
        result: The TCOResult to compute from.
        unit_type: One of "kw", "rack", "m2", "kwh".
        unit_value: The denominator value (must be positive).

    Returns:
        Cost per unit, or None if unit_value is not positive.
    """
    if unit_value <= 0:
        return None
    if unit_type == "kw":
        return result.equivalent_annual_cost / unit_value
    if unit_type == "rack":
        return result.equivalent_annual_cost / unit_value
    if unit_type == "m2":
        return result.equivalent_annual_cost / unit_value
    if unit_type == "kwh":
        if result.total_energy_kwh and result.total_energy_kwh > 0:
            return result.total_pv / result.total_energy_kwh
        return None
    raise ValueError(f"unsupported unit_type '{unit_type}'")
