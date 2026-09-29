# ADR-024: Telemetry Deduplication

## Status
Accepted

## Context
Source systems may send duplicate readings. The system must be idempotent and tolerate replayed messages.

## Decision
Telemetry readings use `(tenant_id, connector_id, source_event_id)` as a unique constraint. Replays are detected and marked with `quality_status = 'replayed'`. The ingestion pipeline validates schema, tenant binding, identity mapping, dedupe, bounded payloads, timestamps, units, quality flags, and provenance before data enters read models.

## Consequences
- **Positive:** Idempotent ingestion; replay protection; data integrity.
- **Negative:** Requires unique event IDs from sources; storage for dedupe metadata.
- **Mitigation:** Source event ID requirements; quality status tracking; replay detection.
