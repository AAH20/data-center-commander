# ADR-029: Bounded Contexts

## Status
Accepted

## Context
The system spans multiple domains (facilities, energy, compute, capacity, maintenance, operations, analytics). Clear context boundaries prevent coupling.

## Decision
Eight bounded contexts defined: (1) Organization & estate—tenants, sites, facilities, asset graph; (2) Telemetry & provenance—connector contracts, readings, quality; (3) Energy & sustainability—boundaries, tariffs, carbon, PUE/WUE; (4) Compute & service—clusters, hosts, workloads, placements; (5) Capacity & resilience—usable capacity, reserves, forecasts; (6) Maintenance & reliability—asset history, work orders, failure analysis; (7) Operations & governance—incidents, changes, approvals, evidence; (8) Analytics & reporting—metric definitions, quality coverage, decision records.

## Consequences
- **Positive:** Clear ownership boundaries; reduced coupling; supports modular development.
- **Negative:** Context integration complexity; potential duplication.
- **Mitigation:** Context mapping; integration contracts; shared kernel for common types.
