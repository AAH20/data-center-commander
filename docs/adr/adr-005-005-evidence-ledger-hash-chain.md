# ADR-005: Evidence Ledger with Hash Chaining

## Status
Accepted

## Context
Operational decisions must be auditable. Every event (data ingestion, KPI calculation, workflow action, approval) needs an immutable, verifiable record.

## Decision
The `evidence_events` table stores append-only events with `sequence`, `event_hash`, and `previous_hash` forming a per-tenant hash chain. Events are immutable (no UPDATE/DELETE). The `LineageTracker` provides in-memory lineage tracking backed by this table.

## Consequences
- **Positive:** Tamper-evident audit trail; verifiable data lineage; supports compliance requirements.
- **Negative:** Storage growth; hash verification overhead for large chains.
- **Mitigation:** Partitioning by tenant and time; batch verification; retention policies.
