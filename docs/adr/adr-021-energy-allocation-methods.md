# ADR-021: Energy Allocation Methods

## Status
Accepted

## Context
Facility energy must be allocated to workloads for cost accounting and sustainability reporting. Allocation methods must be defensible and auditable.

## Decision
Energy allocations use methods: direct_meter, device_model, capacity_share, shared, and unallocated. Each allocation records the method, formula version, source watermark, coverage, and uncertainty. Allocations include lower and upper bounds. The `energy_allocations` table stores results with provenance.

## Consequences
- **Positive:** Multiple allocation methods; uncertainty quantification; auditable results.
- **Negative:** Method selection requires judgment; some methods need additional data.
- **Mitigation:** Method version tracking; coverage requirements; consistency validation.
