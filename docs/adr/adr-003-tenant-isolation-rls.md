# ADR-003: Tenant Isolation via Row-Level Security

## Status
Accepted

## Context
Multiple tenants share the same database. Cross-tenant data leakage is a critical isolation failure.

## Decision
Every table in the `dcc` schema has a `tenant_id` column with RLS policies forcing `tenant_id = current_setting('dcc.tenant_id')`. The API sets the tenant context per transaction. All tables use `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`.

## Consequences
- **Positive:** Database-enforced isolation; defense in depth; works with any PostgreSQL client.
- **Negative:** Requires careful connection pooling; tenant context must be set correctly per request.
- **Mitigation:** `/readyz` endpoint verifies RLS is enforced; consistency validation includes tenant boundary checks.
