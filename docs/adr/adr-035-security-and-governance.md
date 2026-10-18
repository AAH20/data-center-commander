# ADR-035: Security and Governance

## Status
Accepted

## Context
The system handles sensitive operational data across multiple tenants and trust boundaries. Security and governance must be foundational.

## Decision
Security measures: (1) Read-only architecture boundary; (2) Tenant isolation via RLS; (3) Loopback-only local API; (4) Evidence ledger for audit; (5) Trust boundary enforcement; (6) Input validation and bounded payloads; (7) No bundled credentials; (8) Secret reference-only config. Governance: (1) Approval workflows; (2) Change management; (3) Incident management; (4) Procedure enforcement; (5) Evidence-backed decisions; (6) Purple team readiness validation.

## Consequences
- **Positive:** Defense in depth; auditability; operational safety; compliance support.
- **Negative:** Operational overhead; requires security expertise.
- **Mitigation:** Security audits; penetration testing; threat review; runbooks; SLOs.
