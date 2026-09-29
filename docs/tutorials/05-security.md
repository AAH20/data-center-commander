# Tutorial 5: Security & Governance

## Overview

Data Center Commander is designed with security as a foundational constraint.
This tutorial covers the non-negotiable boundaries, identity and access model,
data protection, AI governance, and the production-readiness exit gate.

## Non-Negotiable Boundaries

These constraints are enforced by the architecture, not by policy alone:

1. **Loopback-only local starter** — the development API binds to `127.0.0.1`
   or `::1` only. It refuses non-loopback binds with a `ValueError`.
2. **No production authentication** — the local starter has no user
   authentication. It must not be exposed remotely.
3. **Server-side tenant validation** — tenant and facility filters are
   validated server-side. PostgreSQL RLS is defense in depth, not a
   replacement for app authorization.
4. **No remote executor** — no shell, desktop control, or remote execution
   path exists in the codebase.
5. **No control-system writes** — no BMS write, breaker/switch control,
   setpoint change, VM lifecycle, or workload dispatch path.
6. **No secret reveal** — no feature that exposes credentials, API keys, or
   secrets through the UI or API.
7. **Human authority retained** — facility safety systems and qualified roles
   retain all emergency and actuation authority. AI is decision support, not
   an operator of record.
8. **Enforced approval workflows** — human approval, two-person checks,
   permit-to-work, change management, and independent postcondition checks
   are enforced in authoritative systems.

## Identity and Access

### Production Design (Not Yet Implemented)

The production design calls for:

- **Enterprise SSO/OIDC** — federated identity
- **MFA** — multi-factor authentication for all human access
- **Tenant membership** — explicit tenant assignment per user
- **Scoped RBAC + resource attributes** — role-based access control with
  resource-level attributes
- **Just-in-time privileged sessions** — elevated access granted for a
  limited time
- **Short sessions** — session TTLs minimize exposure window
- **Session recording** — where lawful, for audit
- **Dual control** — two-person checks for critical operations
- **Prompt revocation** — immediate access removal when needed

### Identity Separation

Separate identities exist for:

- **People** — human operators with SSO/MFA
- **Workload services** — service accounts for automated processes
- **Connectors** — workload-bound identities for data ingestion
- **Agents** — AI agents with allowlisted tools

Connector identity never inherits a user's permissions. Admin/service roles
are not used for telemetry ingestion.

### Audit Logging

Every grant, approval, policy version, target, reason, expiry, and
revocation is logged. The log captures:

- Who (identity)
- What (action)
- When (timestamp)
- Why (reason)
- Scope (target resource)
- Expiry (for time-bound grants)

## Data Protection and Threat Model

### Protected Data

- Site layouts and physical security details
- IP addresses and network topology
- Serial numbers and asset identifiers
- Operational trends and performance data
- Personnel information
- Credentials and secrets
- Availability and resilience data

### Threats

| Threat | Mitigation |
|---|---|
| Hostile/misconfigured sensors | Pinned/validated sources, quality gates |
| Spoofed identity | Enterprise SSO, MFA, connector identity binding |
| Replayed/out-of-order data | Idempotent ingestion, event IDs, dedupe |
| Connector compromise | Least-privilege scopes, egress allowlists, rotation |
| Tenant escape | PostgreSQL RLS, tenant-scoped queries |
| Poisoned analytics | Model governance, input lineage, drift detection |
| Stale topology | Freshness SLA monitoring, quality flags |
| Credential theft | Secret manager, no credentials in UI/logs |
| Exposed admin UI | Loopback-only local, production auth required |
| Unsafe operator reliance | Confidence intervals, uncertainty display, human review |

### Mitigations

- **Pinned/validated sources** — only approved endpoints
- **Exact egress allowlists** — operator-defined, not tenant-provided URLs
- **Bounded parsers** — response size limits, page limits, timeout bounds
- **Idempotent ingestion** — dedupe by `(tenant_id, connector, source_event_id)`
- **RLS tests** — automated tenant isolation verification
- **Signed deploys** — artifact signing and verification
- **SBOM/dependency scan** — software bill of materials
- **Separation of duties** — no single person can approve and execute
- **Quality/freshness visualization** — operators see data health
- **Model governance** — versioned models with lineage and drift detection
- **Independent source corroboration** — cross-check critical readings
- **Low-confidence suppression** — automated recommendations suppressed
  when confidence is low
- **Practiced incident/restore procedures** — runbooks and drills

## AI and Analytics Governance

### Model Output Requirements

Model output must be traceable to:

- **Input watermark** — when the data was current
- **Feature/model/formula version** — exact version used
- **Training/validation scope** — what data the model was trained on
- **Confidence** — prediction confidence or interval
- **Drift state** — whether the model has drifted from its training distribution
- **Human disposition** — how a human reviewer acted on the prediction

### Agent Constraints

Agents may:

- Summarize data
- Draft work items
- Answer questions within their data access scope

Agents may **not**:

- Issue permits
- Suppress alarms
- Issue breaker commands
- Change BMS setpoints
- Initiate shutdowns
- Issue unreviewed maintenance directives

### Prompt Injection Defense

Telemetry text, tickets, logs, and vendor documents are untrusted content.
Tools are allowlisted per agent. Connector scopes do not expand because an
agent asks.

## PostgreSQL Row-Level Security

The schema enforces RLS on all tenant-scoped tables. The `/readyz` endpoint
verifies:

```sql
SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'dcc'
  AND c.relname = ANY(['assets', 'evidence_events'])
```

Both `relrowsecurity` and `relforcerowsecurity` must be `true`. The API sets
the tenant context per transaction:

```sql
SELECT set_config('dcc.tenant_id', %s, true)
```

This is a transaction-local setting (`true` = transaction-local), so it
cannot leak across connections.

## Evidence Ledger

The `evidence_events` table is append-only and tenant-scoped. Each event has:

- `sequence` — monotonically increasing per tenant
- `event_type` — classification
- `occurred_at` — when the event happened
- `actor_ref` — who or what caused the event
- `subject_type` / `subject_id` — what the event is about
- `event_hash` — SHA-256 hash for integrity verification

The UI shows the last 100 evidence events per tenant. Full payload access
belongs in the authorized audit workflow.

## Production-Readiness Exit Gate

Before presenting this system as production-ready, verify:

1. Independent threat model and architecture review
2. External authentication (SSO/OIDC + MFA)
3. RLS/grant tests under non-owner roles
4. Backup/restore and region-failure exercise
5. Safety/security review with site owners
6. Connector security and conformance
7. Performance and soak tests
8. Telemetry completeness and replay test
9. Privacy/retention review
10. Incident, key rotation, revocation, and recovery runbooks
11. Accessibility/usability assessment
12. Signed release, rollback plan, and explicit accountable owner

The local starter is **not production-ready** until these checks pass.

## Next Steps

- [Tutorial 6: Deployment & Operations](06-deployment.md) — local dev, production shapes, scaling
- [Tutorial 10: Evidence & Audit](10-evidence-audit.md) — evidence ledger and audit trail
