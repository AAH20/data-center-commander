# ADR-027: Scaling Path

## Status
Accepted

## Context
The system must scale from single-node demos to production multi-site deployments.

## Decision
Scaling strategy: (1) Keep reference data relational and tenant-partitioned; (2) Index high-cardinality access by `(tenant_id, asset_id, metric_id, observed_at)`; (3) Start with PostgreSQL, add monthly partitioning when volume merits; (4) Adopt TimescaleDB or columnar lake behind the same contract; (5) Separate hot raw telemetry, compacted rollups, and immutable evidence; (6) Use bounded ingestion batches, back-pressure, DLQ, idempotency keys, cursor checkpoints, exponential retry with jitter, and circuit breakers.

## Consequences
- **Positive:** Clear scaling strategy; technology flexibility; operational resilience.
- **Negative:** Complexity at scale; requires operational expertise.
- **Mitigation:** Load testing; published test data shape, p95/p99, error budget; retention policies.
