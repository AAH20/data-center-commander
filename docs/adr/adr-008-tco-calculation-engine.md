# ADR-008: TCO Calculation Engine

## Status
Accepted

## Context
Data center lifecycle economics require comparing on-premises, colocation, and cloud scenarios over multi-year horizons with escalation, discounting, and refresh cycles.

## Decision
The `TCOEngine` computes year-by-year cash flows with upfront CapEx, recurring OpEx (with category-specific escalation), refresh costs, terminal costs, and optional after-tax analysis. It produces present value, equivalent annual cost, and unit economics (per kW, rack, m², kWh). Sensitivity analysis varies single parameters.

## Consequences
- **Positive:** Deterministic, reproducible calculations; comprehensive cost model; sensitivity analysis for risk.
- **Negative:** Simplified tax model; no Monte Carlo simulation; deterministic only.
- **Mitigation:** Documented assumptions; calculation version tracking; independent Finance/Facilities review.
