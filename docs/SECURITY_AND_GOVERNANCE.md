# Security, governance, and operator authority

## Non-negotiable boundaries

- Local starter binds only to loopback and is not production-authenticated.
- Tenant and facility filters are validated server-side. PostgreSQL RLS is defense
  in depth, not a replacement for app authorization.
- The first release has no remote executor, shell, desktop control, control-system
  writes, workload scheduler, or secret reveal feature.
- Facility safety systems and qualified roles retain all emergency and actuation
  authority. AI is decision support, not an operator of record.
- Human approval, two-person checks, permit-to-work, change management, and
  independent postcondition checks are enforced in authoritative systems.

## Identity and access

Production design uses enterprise SSO/OIDC, MFA, tenant membership, scoped RBAC
plus resource attributes, just-in-time privileged sessions, short sessions,
session recording where lawful, dual control for critical operations, and
prompt revocation. Separate identities exist for people, workload services,
connectors, and agents. Connector identity never inherits a user's permissions.
Admin/service roles are not used for telemetry ingestion. Log every grant,
approval, policy version, target, reason, expiry, and revocation.

## Data protection and threat model

Protect site layouts, IPs, serial numbers, operational trends, personnel,
credentials, and availability data. Encrypt transport and storage; minimize
collection; redact logs; classify/retain/export per tenant; verify backups and
restore. Threats include hostile/misconfigured sensors, spoofed identity,
replayed/out-of-order data, connector compromise, tenant escape, poisoned
analytics, stale topology, credential theft, exposed admin UI, and unsafe
operator reliance on inaccurate recommendations.

Mitigations include pinned/validated sources, exact egress allowlists, bounded
parsers, idempotent ingestion, RLS tests, signed deploys, SBOM/dependency scan,
separation of duties, quality/freshness visualization, model governance,
independent source corroboration, low-confidence suppression of automated
recommendation, and practiced incident/restore procedures.

## AI and analytics governance

Model output must be traceable to input watermark, feature/model/formula version,
training/validation scope, confidence, drift state, and human disposition. Agents
may summarize or draft work items; they cannot issue permits, alarm suppression,
breaker commands, BMS setpoints, shutdowns, or unreviewed maintenance directives.
Prompt injection in telemetry text, tickets, logs, and vendor documents is
untrusted content. Tools are allowlisted per agent; connector scopes do not
expand because an agent asks.

## Production-readiness exit gate

Independent threat model and architecture review; external auth; RLS/grant tests;
backup/restore and region-failure exercise; safety/security review with site
owners; connector security and conformance; performance and soak tests; telemetry
completeness and replay test; privacy/retention review; incident, key rotation,
revocation, and recovery runbooks; accessibility/usability assessment; signed
release, rollback plan, and explicit accountable owner. The local starter is not
production-ready until these checks pass.
