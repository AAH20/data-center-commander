# ADR-019: Evidence Events as Audit Trail

## Status
Accepted

## Context
All system actions must be auditable: data ingestion, quality decisions, KPI calculations, workflow transitions, approvals, and human decisions.

## Decision
The `evidence_events` table stores all events with tenant isolation, sequence ordering, and hash chaining. Events capture event type, timestamp, actor, subject, and payload. The table is append-only. The API exposes recent events per tenant. Events support compliance audits and forensic analysis.

## Consequences
- **Positive:** Comprehensive audit trail; tamper-evident; tenant-isolated; supports compliance.
- **Negative:** Storage growth; query performance for large event volumes.
- **Mitigation:** Partitioning by tenant and time; retention policies; indexed queries.
