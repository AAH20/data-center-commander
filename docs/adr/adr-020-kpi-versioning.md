# ADR-020: KPI Versioning

## Status
Accepted

## Context
KPI definitions evolve as calculation methods improve. Historical observations must remain reproducible with their original formula version.

## Decision
KPI definitions include `formula_version` and `metric_key`. Observations reference a specific KPI definition and include `calculation_hash`, `formula_version`, `source_watermark`, and `provenance`. The `kpi_definitions` table supports multiple versions per metric. Active flag controls which version is used for new calculations.

## Consequences
- **Positive:** Reproducible historical KPIs; safe formula evolution; clear lineage.
- **Negative:** Storage for multiple versions; complexity in version management.
- **Mitigation:** Versioned calculation definitions; calculation manifests; quality gates.
