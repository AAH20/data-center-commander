# Local development and synthetic-only walkthrough

The normal start reads from `DCC_DATABASE_URL`. It never seeds records. A clean
database displays an empty/needs-connection state. Use a newly created disposable
database whose name starts with `dcc_demo_` for synthetic walkthroughs.

1. Create a disposable PostgreSQL database, e.g. `dcc_demo_local`, then apply
   `database/schema.sql` to it.
2. Set `DCC_DATABASE_URL` to loopback and that exact DB name.
3. Seed only with `DCC_ALLOW_SYNTHETIC_DATA=YES_SYNTHETIC_dcc_demo_local` and
   `scripts/db-seed-demo.sh`.
4. Open the UI with `?tenant_id=dcc00000-0000-4000-8000-000000000001` in the URL;
   the application labels this data as **SYNTHETIC DEMO · NOT LIVE**.
5. Verify demo labels in tenant, connector, readings, workflow, and KPI records.
6. Reset only with `DCC_ALLOW_DEMO_RESET=RESET_dcc_demo_local` and
   `scripts/db-reset-demo.sh`. The reset rejects other DB names and non-loopback
   database hosts.

Never use the synthetic walkthrough for energy-efficiency reporting, carbon
disclosure, uptime claims, vendor validation, or production-like forecasting.
The API/UI display its `synthetic` provenance on every demo KPI.

## Workspace onboarding, graph, and evidence snapshot

`Workspace setup` stores only a browser-local organization profile and objective
(`localStorage`); it filters workload suggestions but does not alter tenant
records, generate telemetry, or authorize a source. The onboarding flow walks an
operator through selecting an authoritative source, implementing a versioned
read-only adapter, validating schema/tenant/freshness/quality, and retaining
provenance. It deliberately does not collect credentials.

The Estate & lifecycle view renders `/v1/topology`, a tenant-scoped PostgreSQL
read transaction over `assets` and current `asset_relationships`. The client
uses bounded layered layout and adjacency-list breadth-first traversal, caps
the display to 200 nodes / 400 edges, and labels the source. This is dependency
context, not proof of network reachability or actuation capability.

The onboarding dialog can export a local JSON due-diligence snapshot assembled
from tenant-scoped read APIs. It carries the synthetic/source state as returned
and an explicit non-certification disclaimer. Review and redact the downloaded
file before sharing; it may contain tenant inventory, operational evidence,
and cost summaries.
