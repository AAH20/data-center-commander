# ADR-031: Approval Workflow

## Status
Accepted

## Context
Operational decisions (changes, procurements, decommissions) require approval with clear accountability and evidence.

## Decision
Approvals capture: approver reference, decision (pending, approved, rejected, revoked, expired), scope digest, reason, decided timestamp, expiry, signature reference, and evidence. Approvals link to workflows. The scope digest ensures the approval covers the specific workflow state. Expired approvals are automatically invalid.

## Consequences
- **Positive:** Clear accountability; evidence-backed decisions; expiry enforcement.
- **Negative:** Workflow complexity; requires approval policy design.
- **Mitigation:** Approval policies per procedure; scope digest validation; expiry tracking.
