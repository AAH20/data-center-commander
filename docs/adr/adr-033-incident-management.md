# ADR-033: Incident Management

## Status
Accepted

## Context
Incidents must be tracked with severity, impact, timeline, root cause analysis, and resolution evidence.

## Decision
Incidents capture: severity, state, incident commander, opened/detected/mitigated/resolved timestamps, impact, root cause confidence, and timeline. Incidents link to workflows. The timeline captures key events during the incident lifecycle. Root cause confidence indicates the reliability of the analysis.

## Consequences
- **Positive:** Structured incident response; clear accountability; learning opportunities.
- **Negative:** Requires discipline in incident documentation; timeline maintenance.
- **Mitigation:** Severity-based escalation; timeline templates; post-incident review process.
