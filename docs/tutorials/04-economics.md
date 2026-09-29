# Tutorial 4: Economics & Cost Estimation

## Overview

Data Center Commander provides bottom-up cost estimation, lifecycle cash-flow
modeling, unit economics, and price intelligence. This tutorial covers the
estimation pipeline, TCO calculations, unit economics formulas, and the
price observation workflow.

## The Estimation Pipeline

```
DeploymentSpec → Component Sizing → Quantity Takeoff → Unit Cost Application
→ Lifecycle Calculation → Low/Base/High Bounds → Estimate Result
```

All calculations are deterministic, tenant-scoped, and read-only. No I/O, no
network, no persistence — callers persist results.

## Deployment Specification

The `DeploymentSpec` dataclass defines a deployment:

```python
from dcc.economics.estimates import DeploymentSpec, DeploymentType, RedundancyLevel, TierLevel
from decimal import Decimal

spec = DeploymentSpec(
    name="New 2MW DC",
    deployment_type=DeploymentType.GREENFIELD,
    it_capacity_kw=Decimal("2000"),
    geography="US-East",
    currency="USD",
    redundancy=RedundancyLevel.N_PLUS_1,
    tier_level=TierLevel.TIER_III,
    pue=Decimal("1.45"),
    horizon_months=180,
    discount_rate=Decimal("0.08"),
    contingency_pct=Decimal("0.10"),
)
```

Key derived properties:

- `effective_rack_count` — derived from IT capacity ÷ 8 kW/rack if not set
- `effective_white_space_m2` — derived from IT capacity ÷ 1.5 kW/m² if not set
- `annual_it_energy` — explicit or derived from capacity × 0.8 × 8760 hours
- `annual_facility_energy` — IT energy × PUE

## Component Sizing

The `ComponentSizingEngine` derives quantities from the spec:

| Method | Components | Key ratios |
|---|---|---|
| `size_electrical()` | Switchgear, UPS, PDUs, generators | PUE × (1 + 25% overhead) × redundancy factor |
| `size_mechanical()` | Chillers, cooling towers, CRAH/CRAC | 0.45 cooling kW per IT kW × (1 + 15% overhead) × redundancy |
| `size_civil()` | Building shell, raised floor | White space × 2.0 (total area), $800/m² shell |
| `size_it_equipment()` | Servers, storage, racks | IT kW, 0.3× IT kW storage, rack count |
| `size_network()` | Switches, routers, cabling | Rack count × $5,000/rack |
| `size_design_and_other()` | Engineering, labor, software | 8% of construction, IT kW × labor rate |
| `size_energy_opex()` | Annual electricity | Facility energy × $0.12/kWh |
| `size_maintenance_opex()` | Preventive maintenance | IT kW × $1,200 × 5% |
| `size_refresh_capex()` | IT refresh (amortized) | IT kW × $1,000 / refresh years |

### Redundancy Factors

| Level | Factor |
|---|---|
| N | 1.0 |
| N+1 | 1.2 |
| N+2 | 1.4 |
| 2N | 2.0 |
| 2N+1 | 2.2 |

## Building the Estimate

```python
from dcc.economics.estimates import BottomUpEstimator

estimator = BottomUpEstimator(spec)
result = estimator.estimate()

print(f"Total PV (base): {result.total_pv_base:,.2f} {result.currency}")
print(f"Total PV (low):  {result.total_pv_low:,.2f}")
print(f"Total PV (high): {result.total_pv_high:,.2f}")
print(f"EAC:             {result.equivalent_annual_cost:,.2f}")
print(f"Cost per kW-year: {result.cost_per_kw_year:,.2f}")
print(f"Cost per rack-year: {result.cost_per_rack_year:,.2f}")
print(f"Cost per m²-year: {result.cost_per_m2_year:,.2f}")
```

## Lifecycle Cost Calculation

The `LifecycleCostCalculator` computes present values using:

```
PV = Σ [extended × (1 + escalation)^(months/12) / (1 + discount)^(month/12)]
```

For each line item, it iterates over recurrence months (for recurring costs)
or a single period (for one-time costs), applying escalation and discount
factors.

### Cost Behaviors

| Behavior | Description |
|---|---|
| `one_time` | Single payment at start month |
| `fixed_recurring` | Recurs every N months |
| `variable` | Recurs with variable amount |
| `step_fixed` | Fixed within steps |
| `capitalized` | Capital expenditure |

## Unit Economics

The `src/dcc/economics/unit.py` module implements:

### Equivalent Annual Cost (EAC)

```
EAC = PV / n                    when r = 0
EAC = PV × r / (1 - (1+r)^(-n))  when r > 0
```

### Cost per Unit

| Metric | Formula | Unit |
|---|---|---|
| Cost per kW-year | EAC / IT capacity (kW) | USD/kW-year |
| Cost per rack-year | EAC / rack count | USD/rack-year |
| Cost per m²-year | EAC / floor area (m²) | USD/m²-year |
| Cost per kWh (IT) | Energy cost / IT kWh | USD/kWh |
| Cost per kWh (facility) | Energy cost / facility kWh | USD/kWh |
| Cost per work unit | Allocated cost / useful work | USD/work-unit |

All functions return `None` for absent/zero denominators (displayed as
"Unknown") or when pricing data is missing (displayed as "Not priced").

## TCO Calculator

The `src/dcc/economics/tco.py` module provides a higher-level TCO engine:

```python
from dcc.economics.tco import TCOEngine, TCOScenario, TCOCostBreakdown, TCOAssumptions

engine = TCOEngine()

engine.add_scenario(TCOScenario(
    name="On-prem 2MW",
    costs=TCOCostBreakdown(
        hardware_capex=2_000_000,
        facility_capex=5_000_000,
        energy_annual=1_500_000,
        maintenance_annual=200_000,
    ),
    assumptions=TCOAssumptions(
        currency="USD",
        horizon_years=10,
        annual_discount_rate=0.08,
    ),
    it_capacity_kw=2000,
    rack_count=250,
    area_m2=5000,
))

comparison = engine.compare()
print(comparison.summary)
```

### Sensitivity Analysis

```python
sensitivity = engine.sensitivity("discount_rate", [0.05, 0.08, 0.12])
print(f"PV range: {sensitivity.pv_range}")
print(f"EAC range: {sensitivity.eac_range}")
```

Supported parameters: `discount_rate`, `energy_escalation`,
`maintenance_escalation`, `labor_escalation`, `hardware_capex`,
`energy_annual`, `horizon_years`, `contingency`.

## Price Observations

The `price_observations` table stores append-only price records. Each record
captures:

- SKU/model, description, category
- Quantity, unit, currency
- Normalized unit price, currency basis date, FX to book
- Geography, delivery basis (ex-works/FOB/CIF/delivered/installed/metered)
- Source kind, source name, source reference
- Confidence, quality status, provenance
- Valid from/to dates, observed timestamp

### Source Families

| Source kind | SLA (hours) | Description |
|---|---|---|
| vendor_api | 24 | Vendor APIs and price books |
| vendor_quote | 168 | Dated vendor quotations |
| contract | 720 | Contracts |
| utility_tariff | 168 | Published utility tariff schedules |
| public_benchmark | 72 | Approved public/industry benchmarks |
| manual | 168 | Controlled manual entry |
| synthetic_demo | ∞ | Synthetic test fixtures (no SLA) |

### Selecting a Rate

Select by: item/model, normalized unit, geography, price basis, effective
date, currency, and approval status. Reject expired, mismatched, or ambiguous
rates. Do not silently fall back to another region or currency.

## Estimate-to-Actual Reconciliation

The `cost_actuals` table accepts periodized ERP/AP/utility/CMMS actuals with:

- Source system, account code, invoice digest
- Accrual state, facility/asset links
- Estimate-line links

`cost_allocations` assigns shared costs to workloads with a named method,
interval, allocation fraction, formula version, and evidence. Reconcile
allocated totals to ledger totals; residual/unallocated amount stays visible.

## The Economics UI

The **Sizing & economics** section shows:

1. **Azure retail catalog lookup** — live price query form
2. **Estimate cards** — lifecycle PV, annualized cost, cost per kW-year,
   cost per m²-year, cost per rack-year, cost per kWh
3. **Estimate rollup** — line items with phase, quantity, unit cost,
   extended cost, pricing status
4. **Price book** — source and freshness for each price observation
5. **Actual cost ledger** — period reconciliation by cost type and currency

All synthetic price rows are tagged. The UI displays "Not priced" for absent
prices and "Unknown" for absent or zero denominators.

## Next Steps

- [Tutorial 5: Security & Governance](05-security.md) — tenant isolation and read-only boundaries
- [Tutorial 8: Capacity & Resilience](08-capacity.md) — capacity scenarios and headroom
