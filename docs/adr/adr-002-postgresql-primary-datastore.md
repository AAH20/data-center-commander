# ADR-002: PostgreSQL as Primary Datastore

## Status
Accepted

## Context
The system needs a relational datastore that supports JSONB for flexible schemas, row-level security for multi-tenancy, and strong consistency for operational data.

## Decision
Use PostgreSQL 14+ as the primary datastore. The schema uses a `dcc` schema with tenant-partitioned tables. JSONB columns store flexible attributes (provenance, metadata, assumptions). No extension is required for the core schema.

## Consequences
- **Positive:** Mature ecosystem; RLS for tenant isolation; JSONB flexibility; portable to Supabase.
- **Negative:** Vertical scaling limits; requires partitioning strategy for high-volume telemetry.
- **Mitigation:** Monthly partitioning when volume merits; TimescaleDB behind the same contract if needed.
