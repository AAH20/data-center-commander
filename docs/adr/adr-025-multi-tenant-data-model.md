# ADR-025: Multi-Tenant Data Model

## Status
Accepted

## Context
The system serves multiple tenants with strict data isolation. All data must be tenant-scoped.

## Decision
Every table includes `tenant_id` as part of the primary key or as a foreign key to `tenants`. RLS policies enforce tenant isolation. The API requires `tenant_id` as a query parameter and sets it via `set_config`. Consistency validation includes tenant boundary checks. Tenant deletion cascades to all related data.

## Consequences
- **Positive:** Strong tenant isolation; scalable multi-tenancy; clear data ownership.
- **Negative:** All queries must include tenant context; cross-tenant reporting requires explicit design.
- **Mitigation:** RLS enforcement; tenant boundary validation; cascade deletes.
