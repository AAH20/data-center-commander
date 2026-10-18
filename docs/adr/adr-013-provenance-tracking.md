# ADR-013: Provenance Tracking

## Status
Accepted

## Context
Every derived metric, KPI, and cost estimate must be traceable to its source observations and transformation steps for audit and reproducibility.

## Decision
The `LineageTracker` maintains a graph of nodes (data artifacts) and edges (transformations). Each step is hash-chained per tenant. Provenance records capture source type, quality status, lineage steps, source refs, and content hashes. The system supports upstream and downstream lineage queries with configurable depth.

## Consequences
- **Positive:** Full data lineage; hash-chained integrity; supports compliance and debugging.
- **Negative:** In-memory implementation requires persistence backing; graph queries can be expensive.
- **Mitigation:** Backed by `evidence_events` table; depth-limited queries; tenant-scoped chains.
