# ADR-001: Read-Only Architecture Boundary

## Status
Accepted

## Context
Data Center Commander must not actuate physical infrastructure (breakers, cooling, fire systems, workload lifecycle). The system's value is in observation, analysis, and decision support—not control.

## Decision
All integrations and APIs are strictly read-only. The system contains no write path to BMS, EPMS, CMMS, hypervisors, or cloud control planes. Recommendations are advisory and require human approval through external systems.

## Consequences
- **Positive:** Eliminates safety risk from automated actuation; simplifies security posture; clear separation of concerns.
- **Negative:** Cannot automate responses; operators must act on recommendations manually.
- **Mitigation:** Future execution adapters require a separate, independently reviewed project gate.
