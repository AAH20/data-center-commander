# ADR-016: Placement Comparison Snapshots

## Status
Accepted

## Context
Operators compare on-premises vs cloud placement scenarios. Draft comparisons must be saved without being mistaken for approved estimates.

## Decision
Placement comparisons are saved as immutable draft snapshots in `placement_comparison_snapshots`. Snapshots have a schema version, SHA-256 payload hash, and are append-only (no UPDATE/DELETE via trigger). They are tenant-scoped and explicitly marked as draft. Approved estimates use separate `estimate_projects` and `estimate_line_items` tables.

## Consequences
- **Positive:** Clear draft vs approved separation; immutable audit trail; schema versioning for evolution.
- **Negative:** Cannot edit snapshots (must create new); separate from approved workflow.
- **Mitigation:** UI clearly distinguishes draft snapshots; migration path to approved estimates.
