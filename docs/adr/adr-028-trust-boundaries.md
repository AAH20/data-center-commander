# ADR-028: Trust Boundaries

## Status
Accepted

## Context
The system operates across enterprise networks, site DMZs, and cloud services. Clear trust boundaries are essential for security.

## Decision
Five trust boundaries defined: (1) Enterprise/control networks to site DMZ—outbound-only, protocol translation at reviewed gateway; (2) Connector to ingestion—workload-bound identity, operator-provisioned config, untrusted payload; (3) Ingestion to canonical records—schema validation, tenant binding, dedupe, quality flags, provenance; (4) Analytics to decision—advisory only, carry lineage and uncertainty, cannot create commands; (5) Tenant to database—RLS-scoped, least privilege, transaction-local tenant context.

## Consequences
- **Positive:** Clear security architecture; defense in depth; supports threat modeling.
- **Negative:** Operational complexity; requires careful configuration.
- **Mitigation:** Security audits; penetration testing; threat review; least privilege enforcement.
