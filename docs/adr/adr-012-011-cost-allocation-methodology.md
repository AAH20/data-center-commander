# ADR-012: Cost Allocation Methodology

## Status
Accepted

## Context
Shared costs (energy, facilities, operations) must be distributed across workloads using defensible, auditable methods.

## Decision
Eight allocation methods are supported: direct_meter, measured_usage, capacity_share, floor_area, rack_units, headcount, equal_share, and manual_approved. Allocation uses largest-remainder rounding to ensure full distribution. Each allocation produces evidence with method version, source data, and a deterministic hash for audit.

## Consequences
- **Positive:** Multiple defensible methods; full allocation guarantee; auditable evidence; reproducible results.
- **Negative:** Method selection requires judgment; some methods need external data (headcount).
- **Mitigation:** Method version tracking; evidence preservation; operator selection with approval workflow.
