"""What-if scenario modeling and comparison engine for Data Center Commander.

Provides deployment scenario definition, side-by-side comparison, sensitivity
analysis, and probabilistic modeling. All outputs are advisory planning
aids—not procurement recommendations or financial approvals.

The engine is purely computational: no I/O, no network, no persistence.
It operates on explicit inputs and returns structured results that callers
can persist, display, or export as needed.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioAssumptions:
    """Shared assumptions applied across scenarios in a comparison.

    Attributes:
        currency: ISO 4217 currency code (3 letters).
        horizon_months: Analysis horizon in months (1-120).
        annual_discount_rate: Annual discount rate as a decimal (0.0-1.0).
        useful_units_per_month: Workload units delivered per month.
        useful_unit_name: Name of the workload unit (e.g. "requests", "GPU-hours").
        demand_profile: Demand shape label (e.g. "steady", "bursty", "seasonal").
    """

    currency: str = "USD"
    horizon_months: int = 36
    annual_discount_rate: float = 0.08
    useful_units_per_month: float = 1.0
    useful_unit_name: str = "units"
    demand_profile: str = "steady"

    def __post_init__(self) -> None:
        if not (isinstance(self.currency, str) and len(self.currency) == 3
                and self.currency.isalpha() and self.currency.isupper()):
            raise ValueError("currency must be a 3-letter ISO code (e.g. USD)")
        if not (isinstance(self.horizon_months, int) and not isinstance(self.horizon_months, bool)
                and 1 <= self.horizon_months <= 120):
            raise ValueError("horizon_months must be an integer from 1 to 120")
        if not (isinstance(self.annual_discount_rate, (int, float))
                and not isinstance(self.annual_discount_rate, bool)
                and 0.0 <= self.annual_discount_rate <= 1.0):
            raise ValueError("annual_discount_rate must be between 0.0 and 1.0")
        if not (isinstance(self.useful_units_per_month, (int, float))
                and not isinstance(self.useful_units_per_month, bool)
                and self.useful_units_per_month > 0):
            raise ValueError("useful_units_per_month must be positive")
        if not isinstance(self.useful_unit_name, str) or not self.useful_unit_name.strip():
            raise ValueError("useful_unit_name must be a non-empty string")
        if not isinstance(self.demand_profile, str) or not self.demand_profile.strip():
            raise ValueError("demand_profile must be a non-empty string")


@dataclass
class CostBreakdown:
    """Detailed cost structure for a deployment scenario.

    All amounts are in the scenario currency. One-time costs occur at month 0;
    monthly costs recur each month; refresh costs occur at a specified month;
    terminal costs (exit minus residual) occur at the horizon.

    Attributes:
        capex: One-time capital expenditure (hardware, fit-out, migration).
        site: One-time site/facility preparation costs.
        migration: One-time migration and integration costs.
        power_monthly: Monthly power and cooling charges.
        software_monthly: Monthly software/license costs.
        maintenance_monthly: Monthly maintenance and support costs.
        labor_monthly: Monthly operations labor costs.
        network_monthly: Monthly connectivity and transit costs.
        backup_monthly: Monthly backup, DR, and security costs.
        other_monthly: Other recurring monthly costs.
        refresh: One-time hardware refresh CapEx within the horizon.
        refresh_month: Month of refresh (0 = no refresh).
        exit_cost: Decommission/disposal cost at horizon.
        residual_value: Residual value credit at horizon.
    """

    capex: float = 0.0
    site: float = 0.0
    migration: float = 0.0
    power_monthly: float = 0.0
    software_monthly: float = 0.0
    maintenance_monthly: float = 0.0
    labor_monthly: float = 0.0
    network_monthly: float = 0.0
    backup_monthly: float = 0.0
    other_monthly: float = 0.0
    refresh: float = 0.0
    refresh_month: int = 0
    exit_cost: float = 0.0
    residual_value: float = 0.0

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if name == "refresh_month":
                if not (isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 120):
                    raise ValueError("refresh_month must be an integer from 0 to 120")
            else:
                if not (isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0):
                    raise ValueError(f"{name} must be a non-negative number")

    @property
    def total_upfront(self) -> float:
        """Total one-time costs at month 0."""
        return self.capex + self.site + self.migration

    @property
    def total_monthly(self) -> float:
        """Total recurring monthly costs."""
        return (self.power_monthly + self.software_monthly + self.maintenance_monthly
                + self.labor_monthly + self.network_monthly + self.backup_monthly
                + self.other_monthly)

    @property
    def terminal_net(self) -> float:
        """Net terminal cost (exit cost minus residual value)."""
        return self.exit_cost - self.residual_value


@dataclass
class DeploymentScenario:
    """A named deployment scenario with cost structure and metadata.

    Attributes:
        name: Human-readable scenario name (1-120 chars).
        description: Optional longer description.
        scenario_type: Deployment type label (e.g. "on-prem", "cloud", "hybrid").
        costs: CostBreakdown for this scenario.
        assumptions: ScenarioAssumptions for this scenario.
        tags: Optional list of string tags for filtering/grouping.
        metadata: Optional dict for additional caller-specific data.
    """

    name: str
    costs: CostBreakdown
    assumptions: ScenarioAssumptions = field(default_factory=ScenarioAssumptions)
    description: str = ""
    scenario_type: str = "on-prem"
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
class ScenarioResult:
    """Computed financial results for a single scenario.

    Attributes:
        scenario_name: Name of the scenario.
        scenario_type: Deployment type label.
        npv: Net present value of all cash flows.
        undiscounted_lifecycle: Sum of all cash flows without discounting.
        average_monthly: NPV divided by horizon months.
        year_one_cash: Undiscounted cash in the first 12 months.
        cost_per_unit: NPV divided by total useful units over horizon.
        total_upfront: Total one-time costs at month 0.
        total_monthly: Total recurring monthly costs.
        total_refresh: Total refresh costs.
        terminal_net: Net terminal cost.
        horizon_months: Analysis horizon in months.
        currency: Currency code.
        monthly_units: Useful units per month.
        useful_unit_name: Name of the workload unit.
    """

    scenario_name: str
    scenario_type: str
    npv: float
    undiscounted_lifecycle: float
    average_monthly: float
    year_one_cash: float
    cost_per_unit: float
    total_upfront: float
    total_monthly: float
    total_refresh: float
    terminal_net: float
    horizon_months: int
    currency: str
    monthly_units: float
    useful_unit_name: str


@dataclass
class ScenarioComparison:
    """Side-by-side comparison of multiple scenarios.

    Attributes:
        scenarios: List of ScenarioResult objects.
        baseline_index: Index of the baseline scenario in the list.
        npv_deltas: NPV difference from baseline for each scenario.
        cost_per_unit_deltas: Cost-per-unit difference from baseline.
        lower_npv_index: Index of the scenario with lowest NPV.
        lower_cost_per_unit_index: Index of scenario with lowest cost per unit.
        summary: Human-readable summary string.
    """

    scenarios: list[ScenarioResult]
    baseline_index: int = 0
    npv_deltas: list[float] = field(default_factory=list)
    cost_per_unit_deltas: list[float] = field(default_factory=list)
    lower_npv_index: int = 0
    lower_cost_per_unit_index: int = 0
    summary: str = ""


@dataclass
class SensitivityAnalysis:
    """Sensitivity analysis results for a single parameter.

    Attributes:
        parameter_name: Name of the parameter varied.
        parameter_label: Human-readable label.
        base_value: Base case parameter value.
        values_tested: List of parameter values tested.
        npv_results: NPV for each tested value.
        cost_per_unit_results: Cost per unit for each tested value.
        npv_range: (min, max) NPV across tested values.
        cost_per_unit_range: (min, max) cost per unit across tested values.
        npv_sensitivity: Range of NPV variation (max - min).
        cost_per_unit_sensitivity: Range of cost-per-unit variation.
    """

    parameter_name: str
    parameter_label: str
    base_value: float
    values_tested: list[float]
    npv_results: list[float]
    cost_per_unit_results: list[float]
    npv_range: tuple[float, float]
    cost_per_unit_range: tuple[float, float]
    npv_sensitivity: float
    cost_per_unit_sensitivity: float


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------


def _calculate_npv(
    costs: CostBreakdown,
    assumptions: ScenarioAssumptions,
) -> tuple[float, float, float, float]:
    """Calculate NPV, undiscounted total, year-one cash, and total refresh.

    Cash flow timing:
    - One-time costs at month 0 (no discounting).
    - Monthly recurring costs at month end (discounted by (1+r)^(m/12)).
    - Refresh at the specified month (discounted).
    - Terminal (exit - residual) at horizon (discounted).

    Returns:
        Tuple of (npv, undiscounted_lifecycle, year_one_cash, total_refresh).
    """
    rate = assumptions.annual_discount_rate
    horizon = assumptions.horizon_months
    annual_factor = 1.0 + rate

    upfront = costs.total_upfront
    monthly = costs.total_monthly
    refresh = costs.refresh
    refresh_month = costs.refresh_month
    terminal = costs.terminal_net

    npv = upfront
    undiscounted = upfront
    year_one = upfront
    total_refresh = 0.0

    for month in range(1, horizon + 1):
        factor = annual_factor ** (month / 12.0)
        npv += monthly / factor
        undiscounted += monthly
        if month <= 12:
            year_one += monthly
        if refresh_month == month and refresh > 0:
            npv += refresh / factor
            undiscounted += refresh
            total_refresh += refresh
            if month <= 12:
                year_one += refresh

    terminal_factor = annual_factor ** (horizon / 12.0)
    npv += terminal / terminal_factor
    undiscounted += terminal
    if horizon <= 12:
        year_one += terminal

    return npv, undiscounted, year_one, total_refresh


def evaluate_scenario(scenario: DeploymentScenario) -> ScenarioResult:
    """Evaluate a single deployment scenario and return computed results.

    Args:
        scenario: The deployment scenario to evaluate.

    Returns:
        ScenarioResult with all computed financial metrics.

    Raises:
        ValueError: If the scenario is invalid.
    """
    npv, undiscounted, year_one, total_refresh = _calculate_npv(
        scenario.costs, scenario.assumptions
    )
    horizon = scenario.assumptions.horizon_months
    volume = scenario.assumptions.useful_units_per_month
    total_units = horizon * volume

    return ScenarioResult(
        scenario_name=scenario.name,
        scenario_type=scenario.scenario_type,
        npv=npv,
        undiscounted_lifecycle=undiscounted,
        average_monthly=npv / horizon,
        year_one_cash=year_one,
        cost_per_unit=npv / total_units if total_units > 0 else float("inf"),
        total_upfront=scenario.costs.total_upfront,
        total_monthly=scenario.costs.total_monthly,
        total_refresh=total_refresh,
        terminal_net=scenario.costs.terminal_net,
        horizon_months=horizon,
        currency=scenario.assumptions.currency,
        monthly_units=volume,
        useful_unit_name=scenario.assumptions.useful_unit_name,
    )


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def compare_scenarios(
    scenarios: list[DeploymentScenario],
    baseline_index: int = 0,
) -> ScenarioComparison:
    """Compare multiple deployment scenarios side-by-side.

    Args:
        scenarios: List of scenarios to compare (at least 1).
        baseline_index: Index of the baseline scenario (default 0).

    Returns:
        ScenarioComparison with deltas and summary.

    Raises:
        ValueError: If scenarios list is empty or baseline_index is invalid.
    """
    if not scenarios:
        raise ValueError("at least one scenario is required for comparison")
    if not (0 <= baseline_index < len(scenarios)):
        raise ValueError(f"baseline_index {baseline_index} out of range for {len(scenarios)} scenarios")

    results = [evaluate_scenario(s) for s in scenarios]
    baseline = results[baseline_index]

    npv_deltas = [r.npv - baseline.npv for r in results]
    cost_per_unit_deltas = [r.cost_per_unit - baseline.cost_per_unit for r in results]

    lower_npv_index = min(range(len(results)), key=lambda i: results[i].npv)
    lower_cost_per_unit_index = min(range(len(results)), key=lambda i: results[i].cost_per_unit)

    lines = [
        f"Scenario comparison ({len(results)} scenarios, baseline: {baseline.scenario_name})",
        f"  Horizon: {baseline.horizon_months} months · Currency: {baseline.currency}",
        f"  Discount rate: {scenarios[baseline_index].assumptions.annual_discount_rate:.1%}",
        "",
    ]
    for i, r in enumerate(results):
        marker = " [BASELINE]" if i == baseline_index else ""
        lines.append(
            f"  {r.scenario_name}{marker}: NPV={r.npv:,.2f} · "
            f"monthly={r.average_monthly:,.2f} · "
            f"unit={r.cost_per_unit:,.4f}/{r.useful_unit_name}"
        )
        lines.append(
            f"    ΔNPV={npv_deltas[i]:+,.2f} · "
            f"Δunit={cost_per_unit_deltas[i]:+,.4f}"
        )
    lines.append("")
    lines.append(f"  Lowest NPV: {results[lower_npv_index].scenario_name}")
    lines.append(f"  Lowest cost/unit: {results[lower_cost_per_unit_index].scenario_name}")

    return ScenarioComparison(
        scenarios=results,
        baseline_index=baseline_index,
        npv_deltas=npv_deltas,
        cost_per_unit_deltas=cost_per_unit_deltas,
        lower_npv_index=lower_npv_index,
        lower_cost_per_unit_index=lower_cost_per_unit_index,
        summary="\n".join(lines),
    )


# ---------------------------------------------------------------------------
# Sensitivity analysis
# ---------------------------------------------------------------------------


def run_sensitivity(
    scenario: DeploymentScenario,
    parameter_name: str,
    values: list[float],
) -> SensitivityAnalysis:
    """Run sensitivity analysis on a single scenario parameter.

    Supported parameters:
        - "discount_rate": Annual discount rate (0.0-1.0).
        - "power_monthly": Monthly power cost multiplier (0.0-10.0).
        - "capex": Capex multiplier (0.0-10.0).
        - "labor_monthly": Monthly labor cost multiplier (0.0-10.0).
        - "useful_units_per_month": Monthly workload units (positive).
        - "horizon_months": Analysis horizon (1-120).

    Args:
        scenario: Base scenario to analyze.
        parameter_name: Name of the parameter to vary.
        values: List of values to test.

    Returns:
        SensitivityAnalysis with results for each tested value.

    Raises:
        ValueError: If parameter_name is unsupported or values are invalid.
    """
    supported = {
        "discount_rate", "power_monthly", "capex", "labor_monthly",
        "useful_units_per_month", "horizon_months",
    }
    if parameter_name not in supported:
        raise ValueError(f"unsupported parameter '{parameter_name}'. Supported: {sorted(supported)}")
    if not values:
        raise ValueError("at least one value is required for sensitivity analysis")

    labels = {
        "discount_rate": "Annual discount rate",
        "power_monthly": "Power cost multiplier",
        "capex": "Capex multiplier",
        "labor_monthly": "Labor cost multiplier",
        "useful_units_per_month": "Monthly useful units",
        "horizon_months": "Horizon (months)",
    }

    base_scenario = scenario
    base_value = _get_parameter_value(scenario, parameter_name)

    npv_results: list[float] = []
    cost_per_unit_results: list[float] = []

    for val in values:
        modified = _set_parameter(scenario, parameter_name, val)
        result = evaluate_scenario(modified)
        npv_results.append(result.npv)
        cost_per_unit_results.append(result.cost_per_unit)

    npv_range = (min(npv_results), max(npv_results))
    cpu_range = (min(cost_per_unit_results), max(cost_per_unit_results))

    return SensitivityAnalysis(
        parameter_name=parameter_name,
        parameter_label=labels[parameter_name],
        base_value=base_value,
        values_tested=list(values),
        npv_results=npv_results,
        cost_per_unit_results=cost_per_unit_results,
        npv_range=npv_range,
        cost_per_unit_range=cpu_range,
        npv_sensitivity=npv_range[1] - npv_range[0],
        cost_per_unit_sensitivity=cpu_range[1] - cpu_range[0],
    )


def _get_parameter_value(scenario: DeploymentScenario, parameter_name: str) -> float:
    """Get the current value of a parameter from a scenario."""
    if parameter_name == "discount_rate":
        return scenario.assumptions.annual_discount_rate
    if parameter_name == "power_monthly":
        return scenario.costs.power_monthly
    if parameter_name == "capex":
        return scenario.costs.capex
    if parameter_name == "labor_monthly":
        return scenario.costs.labor_monthly
    if parameter_name == "useful_units_per_month":
        return scenario.assumptions.useful_units_per_month
    if parameter_name == "horizon_months":
        return float(scenario.assumptions.horizon_months)
    raise ValueError(f"unsupported parameter '{parameter_name}'")


def _set_parameter(
    scenario: DeploymentScenario,
    parameter_name: str,
    value: float,
) -> DeploymentScenario:
    """Create a modified copy of a scenario with a parameter changed.

    Returns a deep copy with the specified parameter set to the new value.
    The original scenario is not modified. For frozen dataclass fields
    (ScenarioAssumptions), a new instance is created.
    """
    modified = copy.deepcopy(scenario)

    if parameter_name == "discount_rate":
        if not (0.0 <= value <= 1.0):
            raise ValueError("discount_rate must be between 0.0 and 1.0")
        modified.assumptions = ScenarioAssumptions(
            currency=modified.assumptions.currency,
            horizon_months=modified.assumptions.horizon_months,
            annual_discount_rate=value,
            useful_units_per_month=modified.assumptions.useful_units_per_month,
            useful_unit_name=modified.assumptions.useful_unit_name,
            demand_profile=modified.assumptions.demand_profile,
        )
    elif parameter_name == "power_monthly":
        if value < 0:
            raise ValueError("power_monthly must be non-negative")
        modified.costs.power_monthly = value
    elif parameter_name == "capex":
        if value < 0:
            raise ValueError("capex must be non-negative")
        modified.costs.capex = value
    elif parameter_name == "labor_monthly":
        if value < 0:
            raise ValueError("labor_monthly must be non-negative")
        modified.costs.labor_monthly = value
    elif parameter_name == "useful_units_per_month":
        if value <= 0:
            raise ValueError("useful_units_per_month must be positive")
        modified.assumptions = ScenarioAssumptions(
            currency=modified.assumptions.currency,
            horizon_months=modified.assumptions.horizon_months,
            annual_discount_rate=modified.assumptions.annual_discount_rate,
            useful_units_per_month=value,
            useful_unit_name=modified.assumptions.useful_unit_name,
            demand_profile=modified.assumptions.demand_profile,
        )
    elif parameter_name == "horizon_months":
        if not (isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 120):
            raise ValueError("horizon_months must be an integer from 1 to 120")
        modified.assumptions = ScenarioAssumptions(
            currency=modified.assumptions.currency,
            horizon_months=value,
            annual_discount_rate=modified.assumptions.annual_discount_rate,
            useful_units_per_month=modified.assumptions.useful_units_per_month,
            useful_unit_name=modified.assumptions.useful_unit_name,
            demand_profile=modified.assumptions.demand_profile,
        )
    else:
        raise ValueError(f"unsupported parameter '{parameter_name}'")

    return modified


# ---------------------------------------------------------------------------
# Scenario engine
# ---------------------------------------------------------------------------


class ScenarioEngine:
    """High-level engine for what-if scenario modeling.

    Provides a fluent interface for building, comparing, and analyzing
    deployment scenarios. All methods are pure functions—no I/O.

    Example:
        engine = ScenarioEngine()
        engine.add_scenario(onprem_scenario)
        engine.add_scenario(cloud_scenario)
        comparison = engine.compare()
        sensitivity = engine.sensitivity("discount_rate", [0.05, 0.08, 0.12])
    """

    def __init__(self) -> None:
        self._scenarios: list[DeploymentScenario] = []

    def add_scenario(self, scenario: DeploymentScenario) -> ScenarioEngine:
        """Add a scenario to the engine. Returns self for chaining."""
        self._scenarios.append(scenario)
        return self

    def remove_scenario(self, name: str) -> ScenarioEngine:
        """Remove a scenario by name. Returns self for chaining."""
        self._scenarios = [s for s in self._scenarios if s.name != name]
        return self

    def clear(self) -> ScenarioEngine:
        """Remove all scenarios. Returns self for chaining."""
        self._scenarios.clear()
        return self

    @property
    def scenarios(self) -> list[DeploymentScenario]:
        """Return a copy of the current scenario list."""
        return list(self._scenarios)

    @property
    def count(self) -> int:
        """Number of scenarios in the engine."""
        return len(self._scenarios)

    def evaluate(self, name: str | None = None) -> ScenarioResult | list[ScenarioResult]:
        """Evaluate one or all scenarios.

        Args:
            name: Scenario name to evaluate, or None for all.

        Returns:
            ScenarioResult for a single scenario, or list of all results.
        """
        if name is not None:
            for s in self._scenarios:
                if s.name == name:
                    return evaluate_scenario(s)
            raise ValueError(f"scenario '{name}' not found")
        return [evaluate_scenario(s) for s in self._scenarios]

    def compare(self, baseline: str | None = None) -> ScenarioComparison:
        """Compare all scenarios.

        Args:
            baseline: Name of baseline scenario, or None to use first.

        Returns:
            ScenarioComparison with all results and deltas.
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
        return compare_scenarios(self._scenarios, baseline_index)

    def sensitivity(
        self,
        parameter_name: str,
        values: list[float],
        scenario_name: str | None = None,
    ) -> SensitivityAnalysis:
        """Run sensitivity analysis on a parameter.

        Args:
            parameter_name: Parameter to vary.
            values: Values to test.
            scenario_name: Scenario to analyze, or None for first.

        Returns:
            SensitivityAnalysis with results.
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
        return run_sensitivity(target, parameter_name, values)

    def break_even(
        self,
        scenario_a_name: str,
        scenario_b_name: str,
        parameter_name: str,
        low: float,
        high: float,
        tolerance: float = 0.01,
        max_iterations: int = 50,
    ) -> float | None:
        """Find the break-even point between two scenarios for a parameter.

        Uses bisection to find the parameter value where both scenarios
        have equal NPV.

        Args:
            scenario_a_name: First scenario name.
            scenario_b_name: Second scenario name.
            parameter_name: Parameter to solve for.
            low: Lower bound of search range.
            high: Upper bound of search range.
            tolerance: Convergence tolerance on NPV difference.
            max_iterations: Maximum bisection iterations.

        Returns:
            Break-even parameter value, or None if no break-even exists in range.
        """
        scenario_a = None
        scenario_b = None
        for s in self._scenarios:
            if s.name == scenario_a_name:
                scenario_a = s
            if s.name == scenario_b_name:
                scenario_b = s
        if scenario_a is None or scenario_b is None:
            raise ValueError("one or both scenarios not found")

        def npv_diff(val: float) -> float:
            a = _set_parameter(scenario_a, parameter_name, val)
            b = _set_parameter(scenario_b, parameter_name, val)
            return evaluate_scenario(a).npv - evaluate_scenario(b).npv

        f_low = npv_diff(low)
        f_high = npv_diff(high)

        if f_low * f_high > 0:
            return None  # No sign change = no break-even in range

        for _ in range(max_iterations):
            mid = (low + high) / 2.0
            f_mid = npv_diff(mid)
            if abs(f_mid) < tolerance:
                return mid
            if f_low * f_mid < 0:
                high = mid
                f_high = f_mid
            else:
                low = mid
                f_low = f_mid

        return (low + high) / 2.0

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
                        "horizon_months": s.assumptions.horizon_months,
                        "annual_discount_rate": s.assumptions.annual_discount_rate,
                        "useful_units_per_month": s.assumptions.useful_units_per_month,
                        "useful_unit_name": s.assumptions.useful_unit_name,
                        "demand_profile": s.assumptions.demand_profile,
                    },
                    "costs": {
                        "capex": s.costs.capex,
                        "site": s.costs.site,
                        "migration": s.costs.migration,
                        "power_monthly": s.costs.power_monthly,
                        "software_monthly": s.costs.software_monthly,
                        "maintenance_monthly": s.costs.maintenance_monthly,
                        "labor_monthly": s.costs.labor_monthly,
                        "network_monthly": s.costs.network_monthly,
                        "backup_monthly": s.costs.backup_monthly,
                        "other_monthly": s.costs.other_monthly,
                        "refresh": s.costs.refresh,
                        "refresh_month": s.costs.refresh_month,
                        "exit_cost": s.costs.exit_cost,
                        "residual_value": s.costs.residual_value,
                    },
                    "result": evaluate_scenario(s).__dict__,
                }
                for s in self._scenarios
            ],
        }
