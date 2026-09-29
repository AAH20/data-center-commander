# ADR-010: Workflow State Machine

## Status
Accepted

## Context
Operational workflows (demand, design, procurement, build, commissioning, operations, maintenance, incident, change, decommission) need structured stages, approvals, and evidence.

## Decision
Workflows follow a state machine with stages, status (open, in_progress, closed, cancelled), priority, and accountable owner. Tasks have sequence numbers, preconditions, and outcomes. Approvals capture decision, scope digest, reason, and evidence. Workflows link to procedures, risk assessments, and exit evidence.

## Consequences
- **Positive:** Structured operational process; clear accountability; evidence-backed decisions.
- **Negative:** State machine complexity; requires discipline in workflow design.
- **Mitigation:** Procedure templates; approval policies; workflow health monitoring.
