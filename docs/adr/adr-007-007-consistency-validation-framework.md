# ADR-007: Consistency Validation Framework

## Status
Accepted

## Context
Data from different sources must be cross-validated: utility meters vs submeters, KPI vs telemetry, capacity vs actual load, cost rollups vs line items.

## Decision
The `validation/consistency.py` module provides 15+ cross-source checks producing structured findings (PASS/WARN/FAIL/SKIP). Checks include energy reconciliation, asset reference integrity, capacity headroom, KPI vs telemetry, cost rollup consistency, tenant boundary, temporal consistency, unit consistency, provenance consistency, PUE consistency, price freshness, estimate price links, energy allocation coverage, and connector data freshness.

## Consequences
- **Positive:** Catches data quality issues early; structured findings for operator action; extensible check framework.
- **Negative:** False positives require tuning; some checks need reference data.
- **Mitigation:** Tolerance parameters per check; severity levels allow graduated response.
