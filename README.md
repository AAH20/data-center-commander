# Data Center Commander

## Publisher

**Apex Growth Systems LLC** — U.S. registered company (Arizona, ACC 25121151,
formed 2026-09-14; EIN 61-2391219). Founder: Ahmed Hassan, AI Infrastructure &
Multi-Cloud Architect, CISO/GRC specialist.

This project can be incorporated in any other country around the globe when needed.

Contact: aah@a2zsoc.com | https://a2zsoc.com


![Overview tour across the synthetic demo sections](docs/media/overview.gif)

**An open, operator-centered system for governing the full data-center lifecycle, from utility boundary to useful compute.**

[![CI](https://github.com/AAH20/data-center-commander/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/AAH20/data-center-commander/actions/workflows/ci.yml)
[![License: AGPL-3.0-only](https://img.shields.io/badge/License-AGPL--3.0-only-blue.svg)](LICENSE)

> One command view for facilities, energy, capacity, maintenance, economics,
> analytics, and evidence, with read-only integrations and explicit safety
> boundaries.

**Status:** decision-support system with enforced API-key authentication and tenant
isolation. Adapter code exists for nine source families and is covered by mocked contract
tests; no live vendor run ships with the repository. Forecasts are not validated at
production accuracy, and there is no facility control path.

---

## Table of contents

- [Architecture](#architecture)
- [Product contract](#product-contract)
- [Feature overview](#feature-overview)
- [Quick start](#quick-start)
- [API reference](#api-reference)
- [Database schema](#database-schema)
- [Adapters](#adapters)
- [Economics engine](#economics-engine)
- [Forecasting](#forecasting)
- [Quality and validation](#quality-and-validation)
- [Security and tenant isolation](#security-and-tenant-isolation)
- [Provenance and lineage](#provenance-and-lineage)
- [Observability](#observability)
- [Infrastructure as code](#infrastructure-as-code)
- [Synthetic demo](#synthetic-demo)
- [Standalone layout](#standalone-layout)
- [Migrations](#migrations)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Safety and authority boundary](#safety-and-authority-boundary)
- [Screenshots](#screenshots)
- [License](#license)

---

## Architecture

Data moves from authorized sources through validation before it reaches
operator views and analytics. Recommendations remain advisory.

```mermaid
flowchart LR
  SRC[Utility, OEM, cloud and facility sources] --> ADAPTER[Versioned read-only adapters]
  ADAPTER --> QUALITY[Identity, units, freshness and provenance checks]
  QUALITY --> DB[(Portable PostgreSQL schema)]
  CONSOLE[Console and authenticated API] --> DB
  DB --> BI[Reproducible KPIs and continuous BI]
  BI --> GATE{Evidence sufficient?}
  GATE -->|No| UNKNOWN[Unknown, no forecast]
  GATE -->|Yes| REC[Human-reviewed advisory]
  classDef plain fill:none,stroke:#333,stroke-width:1px
  class SRC,ADAPTER,QUALITY,DB,CONSOLE,BI,GATE,UNKNOWN,REC plain
```

**Explore:** [full architecture](docs/ARCHITECTURE.md) ·
[lifecycle operations](docs/LIFECYCLE_OPERATIONS.md) ·
[integrations](docs/INTEGRATIONS.md) ·
[data model and KPIs](docs/DATA_MODEL_AND_KPIS.md)

Data Center Commander is a standalone, vendor-neutral operations and decision-support project. It joins facility, energy, environmental, asset, workload, capacity, maintenance, incident, change, and evidence data under one tenant-scoped operational model. It is not a BMS, EPMS, CMMS, hypervisor, scheduler, or safety controller; those systems remain authoritative for their domains.

---

## Product contract

- Energy-to-compute is measured with explicit meter boundaries, aligned intervals, units, quality, source lineage, and allocation uncertainty.
- Every KPI is reproducible from named source observations and a versioned calculation definition; missing inputs produce `unknown`, not zero.
- All integrations begin read-only. Every connector declares identity, endpoint, scopes, version, freshness, rate limits, and tested capabilities.
- Workflows are durable records with owner, stage, approvals, procedure version, hazards, evidence, exit criteria, and handoff. The project does not actuate electrical, cooling, fire, or life-safety controls.
- No synthetic readings appear as live data. Synthetic demo data is opt-in, visibly tagged, and reset only in a specifically named demo database.
- The OSS core uses portable PostgreSQL SQL and can be adapted to Supabase. Supabase Auth/RLS is a deployment adapter, not a dependency of the domain model.

---

## Feature overview

### Multi-tab command center UI

The browser-based UI is a single page with 14 `<section class="view">` elements. The left
rail exposes 12 of them; `view-workloads` and `view-critical` exist in the markup without
a rail entry. The console shell itself calls twelve `/v2` endpoints. The ten module
scripts in `ui/` all address the served `/v2` API now; no fetch in `ui/` targets `/v1`
any more, and the three surviving `/v1` mentions are comments recording where the old
paths came from (`ui/azure-prices.js:25-26`, `ui/security-dashboard.js:723`). Every one
of those calls needs the key, which the console gets from the rail's "API key" field or
from a loopback meta tag — see [Authentication](#authentication). The rows below cover
the sections and the panels they render:

| Section or panel | Description |
|---|---|
| **Command Picture** | Executive overview: facility count, KPI summary, open workflows, latest telemetry |
| **Energy & Carbon** | Energy consumption, PUE, carbon intensity, and efficiency trends |
| **Data Science & BI** | KPI series, quality metrics, telemetry health, and workflow analytics |
| **Sizing & Economics** | Cost estimates, unit economics, TCO comparisons, and lifecycle costing |
| **Placement Tradeoffs** | On-prem vs. cloud TCO comparison with scenario snapshots |
| **Capacity & Resilience** | Power, cooling, rack, network, and storage capacity with headroom |
| **Estate & Lifecycle** | Asset inventory, lifecycle states, and facility hierarchy |
| **Reliability** | Failure prediction, maintenance signals, and risk profiles |
| **Operations Queue** | Workflow backlog, priorities, due dates, and overdue items |
| **Integrations** | Connector registry, health status, and run history |
| **Evidence & Audit** | Hash-chained evidence events and lineage verification |
| **Suggested Workloads** | Workload placement recommendations with SLO and energy budget |
| **Critical & GRC** | Critical environments, governance, risk, and compliance posture |

### Read-only API

Served by FastAPI on uvicorn (`dcc.api_async:app`), with psycopg3 for PostgreSQL
access. Every `/v2` endpoint requires an API key and enforces tenant scoping via
PostgreSQL RLS. See [API Reference](#api-reference) for full details.

### Portable PostgreSQL schema

53 tables covering the full data-center lifecycle, counted from a database built from
`schema.sql` plus all nine migrations:
- Multi-tenant row-level security (RLS) with forced enforcement
- Hash-chained evidence events
- Immutable placement comparison snapshots
- Estimate-to-actual cost tracking with price pinning
- Asset relationship topology with confidence scoring
- Capacity snapshots across 9 dimensions
- KPI observations with quality status and provenance

### Versioned read-only adapters

All adapters are bounded, read-only, never persist data, and never follow redirects:

| Adapter | Source | Capabilities |
|---|---|---|
| **Cloud Pricing** | AWS, Azure, GCP | Price lookup, SKU search, region availability |
| **EPMS** | Electrical Power Monitoring | Meter readings, breaker status, UPS status, alarms |
| **CMMS** | Maintenance Management | Work orders, assets, schedules |
| **BMS** | Building Management | HVAC, lighting, access control, alarms |
| **Meter** | Modbus TCP, BACnet/IP, SNMP | Energy readings with quality classification |
| **OEM** | Redfish (Dell, HPE, Lenovo, Supermicro, Cisco, Arista, Juniper) | Server, storage, network, power, thermal telemetry |
| **Utility** | Utility gateway | Tariffs, bills, rate schedules, demand charges |
| **Weather** | Open-Meteo, Electricity Maps | Weather forecast, grid carbon intensity |
| **Hypervisor** | VMware vCenter, KVM/libvirt, Hyper-V | VM/host inventory, power, capacity metrics |

### Economics engine

- **Unit Economics:** cost/kWh, cost/kW-year, cost/m²-year, cost/rack-year, cost/work-unit, equivalent annual cost
- **Bottom-Up Estimating:** component sizing, quantity takeoff, phase subtotals, lifecycle cost calculation
- **TCO Analysis:** multi-scenario comparison, sensitivity analysis, yearly cash flows, cost breakdown by category
- **Price Engine:** versioned prices, weighted average, escalation, price index, delivery basis
- **Tariff Calculations:** flat rate, tiered, time-of-use (TOU), demand charges, fixed charges
- **Reconciliation:** estimate-to-actual variance with configurable thresholds

### Forecasting

- **Load Forecasting:** moving average, exponential smoothing, Holt-Winters, linear trend
- **Price Forecasting:** tariff-aware price projection
- **Failure Prediction:** asset risk profiles with confidence scoring
- **Anomaly Detection:** statistical outlier identification
- **Drift Detection:** PSI (Population Stability Index), KS statistic, performance tracking
- **Calibration:** bias correction, multiplicative correction, forecast-actual matching
- **Backtesting:** walk-forward validation, cross-validation, metric computation

### Quality and validation

- **Quality Engine:** multi-dimensional scoring (coverage, freshness, completeness, accuracy, consistency)
- **Unit Conversion:** dimensional analysis with power factor support
- **Time Series:** alignment, resampling, gap detection, coverage reports
- **Consistency Validation:** 15 validators covering energy sources, asset references, capacity headroom, KPI vs. telemetry, cost rollup, workflow linkage, tenant boundaries, temporal consistency, unit consistency, provenance, PUE, price freshness, estimate price links, energy allocation coverage, and connector data freshness
- **Schema Validation:** 41 entity validators in `src/dcc/validation/schema.py` with constraint checking

### Security and tenant isolation

- **PostgreSQL RLS:** forced row-level security on all tenant tables
- **Tenant Context:** context-variable propagation, fail-closed design
- **Audit Logging:** structured audit events with severity and category
- **Secrets Management:** AWS Secrets Manager and HashiCorp Vault adapters
- **Loopback-Only Legacy Server:** `src/dcc/api.py` refuses non-loopback binds; the
  FastAPI app does not restrict the bind address, and access control is the API key

### Provenance and lineage

- **Hash-Chained Steps:** every transformation is SHA-256 hashed and linked
- **Source Classification:** connector, manual entry, API import, seed fixture, calculated, external system
- **Transformation Tracking:** ingestion, validation, aggregation, allocation, normalization, calculation, filter, join, derivation
- **Chain Verification:** integrity checking with break detection
- **Tenant-Scoped:** lineage chains are isolated per tenant

### Observability

- **Structured Logging:** JSON log records with configurable levels
- **Correlation IDs:** request-scoped tracing
- **SLO Tracking:** availability, latency, error budget, compliance reporting

---

## Quick start

Requires Python 3.11+ and PostgreSQL 14+. Do not point the demo at a production database.

```bash
cd data-center-commander
uv sync --extra postgres

# Build a database from schema.sql plus all nine migrations, on a scratch database,
# then smoke-test every GET /v2 route against it.
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src scripts/verify-fresh-deploy.sh

# Or by hand, against a database you created yourself:
createdb data_center_commander_dev
export DCC_DATABASE_URL='postgresql://127.0.0.1/data_center_commander_dev'
psql "$DCC_DATABASE_URL" -v ON_ERROR_STOP=1 -f database/schema.sql
for f in database/migrations/*.sql; do
  psql "$DCC_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
done

# Mint a key, then export the tenant:hash entry it prints.
.venv/bin/python -m dcc.keys_cli create --tenant <uuid> --name ops
export DCC_API_KEYS='<tenant-uuid>:<hash>'

# Start the served API.
.venv/bin/python -m uvicorn dcc.api_async:app --host 127.0.0.1 --port 8790
```

Open `http://127.0.0.1:8790/` for the console shell, then paste the key into the rail's
"API key" field: the shell itself loads without one, but every `/v2` panel answers `401`
until a key is presented. Setting `DCC_UI_API_KEY` to the same key does that for you on a
loopback connection. Schema changes go to a new database only. `scripts/run-local.py`
starts this same application — it prints the console and `/docs` URLs — and `--legacy`
selects the unmounted standard-library handler in `src/dcc/api.py` instead (routes under
`/v1`, no authentication). To see a clearly synthetic walkthrough, use the separately
gated instructions in [`docs/LOCAL_DEVELOPMENT.md`](docs/LOCAL_DEVELOPMENT.md).

### Health checks

- `/healthz`: process liveness
- `/readyz`: returns `200` only when PostgreSQL is reachable and the `dcc.tenants` and
  `dcc.assets` tables exist; the probe runs inside a `READ ONLY` transaction. It does
  not inspect row-level security: `scripts/verify-fresh-deploy.sh` is what asserts
  forced RLS on the schema.

`/v2` is authenticated. With no key configured every `/v2` request returns `401`; see
[Authentication](#authentication).

### Running tests

```bash
uv run --extra test python -m unittest discover -s tests -v
```

Discovery also collects `tests/terraform`, `tests/iac-*` and `tests/e2e`. The e2e
modules import playwright (the `e2e` extra), so without that extra they error at import
rather than skip.

Test coverage includes:
- Adapter contracts (EPMS, CMMS, meter, Azure pricing)
- Economics (unit, estimates, prices, TCO, allocation)
- Forecasting (backtest, calibration, drift, capacity, features, load, price, anomaly)
- Quality (freshness, anomaly)
- Validation (consistency, intervals, units, boundaries, schema)
- Security (tenant isolation)
- API contracts and integration

---

## API reference

Served by `dcc.api_async:app`, the application declares 32 `/v2` operations: 20 `GET`
and 12 `POST`. It also serves `/healthz`, `/readyz`, `/metrics`, the console shell at
`/`, the `/assets` static mount and the generated `/docs`, `/redoc` and
`/openapi.json`. Every `/v2` operation requires an API key. `/`, the `/assets` static
mount that serves the console's own scripts and HTML fragments, `/healthz`, `/readyz`,
`/metrics` and the generated documentation do not; none of them carries tenant data, and
everything that does is under `/v2` and stays behind the key.

The table below was generated from the app's own route table, not from an earlier
draft:

```bash
PYTHONPATH=src .venv/bin/python -c "
from dcc.api_async import app, _iter_routes
for r in _iter_routes(app.routes):
    for m in (getattr(r, 'methods', None) or []):
        p = getattr(r, 'path', '')
        if m not in ('HEAD', 'OPTIONS') and p.startswith('/v2'):
            print(m, p)"
```

`_iter_routes` rather than `app.routes` because `include_router` does not flatten into
`app.routes` in this FastAPI version: it wraps the sub-router in an `_IncludedRouter`
with no `.path`, so a plain loop over `app.routes` silently skips every included route.
That is how the three backup operations stayed out of this table, and out of
`openapi.json`, after they were mounted.

### Request path

```mermaid
flowchart LR
  REQ[HTTP request] --> MET[metrics]
  MET --> SAFE[safety contract]
  SAFE --> AUTH{auth: key and tenant}
  AUTH -->|missing, invalid or revoked| R401[401]
  AUTH -->|valid key| RATE{rate limit}
  RATE -->|exceeded| R429[429]
  RATE -->|allowed| ROUTE[route handler]
  ROUTE --> POOL[(PostgreSQL pool, RLS session)]
  POOL --> SAFE
  classDef plain fill:none,stroke:#333,stroke-width:1px
  class REQ,MET,SAFE,AUTH,R401,RATE,R429,ROUTE,POOL plain
```

Auth rejects a request before the handler runs, yet metrics is outermost, so a 401 or a
429 is counted; `read_only` and `execution_permitted` are added on the way back out by
middleware, which is why a new handler cannot omit them.

> `/v1/*` belongs to a different, legacy handler: `src/dcc/api.py`, a standard-library
> `ThreadingHTTPServer` that `scripts/run-local.py --legacy` starts. It serves no `/v2`
> route and performs no authentication. The FastAPI app serves no `/v1` route: an
> authenticated `/v1/facilities` there returns `404`, and an unauthenticated one returns
> `401` because the key check runs before routing ever sees the path. Everything below
> describes the FastAPI app.

### Authentication

Every `/v2` route requires a key, sent either as an `X-API-Key` header or as an
`Authorization: Bearer` token.

| Situation | Status |
|---|---|
| No credentials | `401` |
| Invalid, expired, or revoked key | `401` |
| Valid key, `tenant_id` belonging to another tenant | `403` |

Missing and invalid keys return the same code so the endpoint is not a key-enumeration
oracle. `DCC_ALLOW_ANONYMOUS=true` disables enforcement for local development and logs
a warning; it is never appropriate in a deployment.

The console's own files are the exception, and only those files: `/assets/topology.js`
returns `200` without a key, while `/v2/topology` on the same server returns `401`.

That is not the API being open. The exemption admits a path only when it resolves to a
file in this repository's `ui/` tree — the shell's module scripts and HTML fragments,
byte-identical on every deployment and holding no tenant rows. It is derived from the
route table rather than a written-down prefix: `_console_asset_prefixes()`
(`src/dcc/api_async.py:614`) counts a mount only when it is a `StaticFiles` instance
whose directory resolves to `ui/`, so a data route registered under `/assets` later
would not inherit the exemption, and a mount at `/` is refused outright because it
would exempt everything. `_is_public_console_asset()` (`:651`) then rejects any path
carrying a `.` or `..` segment instead of normalising it, so `/assets/../v2/facilities`
gets `401` rather than a tenant route.

Everything that carries tenant data is under `/v2` and still requires a key. The
exemption exists because a browser cannot attach a header to a `<script src>`: without
it the shell loaded while every script tag it emitted answered `401`, which is a blank
page rather than a secure one.

A customer supplies the key in one of two ways:

- **Typed into the console.** The left rail has a field labelled "API key"
  (`#apiKeyInput`, `ui/index.html:15`). On change it is stored in this browser's
  `localStorage` under `dcc-api-key`, and every request the console makes then carries
  it as `X-API-Key` (`:142-143`, `:301`). The key is not baked into `ui/index.html`, and
  a `?api_key=` arriving from an old bookmark is read once and scrubbed from the address
  bar (`:141`).
- **Injected by the server for a local operator.** When `DCC_UI_API_KEY` is set and the
  request comes from loopback, `GET /` carries an extra `<meta name="dcc-api-key">` tag
  (`src/dcc/api_async.py:2836-2847`) that the page reads as its last-resort key. Loopback
  only: injecting it into a page served to any other host would hand every visitor the
  credential.

Mint a key:

```bash
python -m dcc.keys_cli create --tenant <uuid> --name ops
```

Then set `DCC_API_KEYS` to the printed `tenant:hash` entry. `DCC_REQUIRE_KEYS=true`
turns a locked-out configuration into a startup failure instead of a warning.

### Health and operations

| Method | Path | Description |
|---|---|---|
| GET | `/healthz` | Process liveness |
| GET | `/readyz` | Database reachability and `dcc.tenants`/`dcc.assets` presence |
| GET | `/metrics` | Prometheus text exposition, labelled by route template |
| GET | `/` | Console shell (public, no tenant data) |
| GET | `/assets/*` | Console scripts and HTML fragments from `ui/`; public, no tenant data |
| GET | `/docs`, `/redoc`, `/openapi.json` | Generated API documentation; public |

### Operations

All 32 operations, sorted by path. The ten that end in a page envelope are named in
[Response conventions](#response-conventions).

| Method | Path | Description |
|---|---|---|
| GET | `/v2/analytics` | KPI series, KPI quality, telemetry quality, workflow health |
| GET | `/v2/assets` | Asset inventory with type, lifecycle state, criticality |
| GET | `/v2/backup/runs` | Recorded backup runs, newest first; `status` filter, cursor paging |
| POST | `/v2/backup/runs` | Record a run that has already happened. Does not run `pg_dump`; execution stays out of the request path |
| GET | `/v2/backup/verify/{run_id}` | `checksum_match`, `metadata_valid` and the combined `valid`. `checksum_match` is `null` when nothing was verified, never `true` |
| POST | `/v2/cache/invalidate` | Drop cache keys matching `pattern`, a required query parameter |
| GET | `/v2/capacity` | Capacity snapshots per facility, dimension and scenario |
| GET | `/v2/compliance/controls` | Control catalogue across SOC 2, ISO 27001, PCI-DSS, HIPAA, NIST 800-53 and a `custom` framework |
| GET | `/v2/compliance/scan` | Per-control status, with `configuration_gaps` naming controls that read variables the app ignores |
| GET | `/v2/connectors` | Connector registry with scopes and allowed destinations |
| GET | `/v2/costs` | Estimate projects with rollups, pinned prices and actuals |
| GET | `/v2/dr/policies` | Backup policies with schedule and next run |
| GET | `/v2/dr/summary` | Policy counts, due count, test pass rate, RTO and RPO compliance |
| POST | `/v2/economics/tco` | Total cost of ownership for one scenario from explicit assumptions |
| POST | `/v2/economics/tco/compare` | TCO across scenarios, reported as a delta against a baseline |
| GET | `/v2/evidence` | Hash-chained evidence events in sequence order |
| GET | `/v2/evidence/verify` | Chain verification. Bounded by `max_events`; a truncated scan returns `chain_valid: null`, never `true` |
| GET | `/v2/facilities` | Facilities with site codes and names |
| POST | `/v2/forecast/capacity` | Capacity projection with the at-risk window |
| POST | `/v2/forecast/drift` | Distribution drift between a reference series and an incoming one |
| POST | `/v2/forecast/failure` | Failure risk per asset from inventory and telemetry |
| POST | `/v2/optimize/capacity-allocation` | Greedy density allocation |
| POST | `/v2/optimize/energy-allocation` | Max-min fair energy allocation |
| POST | `/v2/optimize/maintenance-routing` | Clarke-Wright savings routing |
| POST | `/v2/optimize/network-zoning` | DSATUR zoning |
| POST | `/v2/optimize/placement` | First-fit decreasing placement |
| GET | `/v2/overview` | Facility count, latest KPIs, open workflows, latest telemetry |
| GET | `/v2/placement/scenarios` | Saved placement comparison scenarios, newest first |
| GET | `/v2/procedures` | Runbooks with risk class, roles, hazards, entry and exit criteria. Collapses to the current version per key |
| GET | `/v2/security/posture` | Weighted posture score across five dimensions from observed process state |
| GET | `/v2/topology` | Asset relationship graph as nodes, edges and relations |
| GET | `/v2/workflows` | Operational workflows with stage, status, owner and due dates |

### Query parameters

| Parameter | Default | Applies to and values |
|---|---|---|
| `tenant_id` | required where declared | Tenant UUID, 36 characters. Declared by 18 of the 32 operations; the other 14 resolve the tenant from the API key alone. When present it must equal the key's tenant, otherwise `403` |
| `limit` | `100` | Page size, 1–1000, on the page routes. Defaults to `200` on `/v2/capacity` and `/v2/evidence`, and to `50` with a ceiling of 500 on `/v2/backup/runs` |
| `cursor` | none | Opaque pagination cursor, accepted by the ten page routes |
| `window_days` | `30` | Analytics window, 1–90 (`/v2/analytics` only) |
| `demo` | none | `synthetic` reveals seeded demo data on `/v2/costs`. `/v2/overview` accepts it but only uses it as a cache-key component |
| `max_events` | `10000` | Evidence verification cap, max 100000 |
| `include_events` | `false` | `/v2/evidence/verify` also returns the scanned events |
| `framework` | none | `/v2/compliance/controls` and `/v2/compliance/scan`; unknown values return `unknown_framework` |
| `dimension` | none | `/v2/capacity` capacity dimension filter |
| `domain`, `risk_class` | none | `/v2/procedures` filters |
| `latest_only` | `true` | `/v2/procedures`; collapses to the current version per key |
| `status` | none | `/v2/workflows`, `/v2/procedures` and `/v2/backup/runs` status filter |
| `enabled` | none | `/v2/dr/policies` filter |
| `relation` | none | `/v2/topology` relation type filter |
| `pattern` | required | `/v2/cache/invalidate` key pattern, a `POST` query parameter |

### Response conventions

Ten of the 20 `GET` operations return a page envelope with the keys `items`, `total`,
`limit`, `offset`, `has_more` and `next_cursor`: `/v2/assets`, `/v2/backup/runs`,
`/v2/capacity`, `/v2/connectors`, `/v2/dr/policies`, `/v2/evidence`, `/v2/facilities`,
`/v2/placement/scenarios`, `/v2/procedures` and `/v2/workflows`.

The other ten return a single object with its own shape: `/v2/analytics`,
`/v2/backup/verify/{run_id}`, `/v2/compliance/controls`, `/v2/compliance/scan`,
`/v2/costs`, `/v2/dr/summary`, `/v2/evidence/verify`, `/v2/overview`,
`/v2/security/posture` and `/v2/topology`.

Every 2xx `/v2` JSON response carries `read_only: true` and `execution_permitted:
false`, injected by middleware after the handler runs rather than set per-handler. This
was measured on a collection route (`/v2/facilities`, page envelope), on single object
routes (`/v2/overview`, `/v2/topology`, `/v2/compliance/controls`,
`/v2/backup/verify/{run_id}`) and on two `POST` routes (`/v2/backup/runs`,
`/v2/cache/invalidate`), against a database built from `database/schema.sql` and all
nine migrations. A handler that sets either field explicitly keeps its own value, and a
non-2xx body is left alone, so a `403` does not read as though it carried data.

The guarantee used to depend on which handler remembered to add the fields:
`/v2/overview` carried them, `/v2/facilities` did not. Enforcing it in one place makes it
uniform and fail-closed, so a new endpoint cannot omit it.

Every `/v2` operation declares a response schema in `/openapi.json`: 32 of 32
operations have a `200` schema, and
[`tests/unit/test_openapi_contract.py`](tests/unit/test_openapi_contract.py) fails if a
new route is added without one.

Errors carry a machine-readable key at `detail.error`. A rejected enum also returns
`detail.value` and the accepted set in `detail.accepted`.


## Database schema

The schema is portable PostgreSQL 14+ / Supabase-compatible. No extensions required.

### Core entity tables

| Table | Purpose |
|---|---|
| `tenants` | Tenant isolation root |
| `sites` | Geographic sites with timezone and utility metadata |
| `facilities` | Data centers, edge sites, labs with design capacity |
| `spaces` | Hierarchical spaces (electrical, mechanical, white space, room, row, zone, yard) |
| `assets` | Equipment with lifecycle state, criticality, warranty |
| `asset_relationships` | Directed topology graph with relation type, confidence, validity period |

### Connector and telemetry

| Table | Purpose |
|---|---|
| `connectors` | Registered connectors with vendor, adapter, scopes, rate limits |
| `connector_runs` | Run history with outcome, records read/rejected, source lag |
| `metric_definitions` | KPI metric definitions with quality policy and versioning |
| `meters` | Meter boundaries with direction, multiplier, calibration |
| `telemetry_readings` | Time-series readings with quality status, provenance, clock offset |

### Energy and capacity

| Table | Purpose |
|---|---|
| `tariffs` | Utility tariff specifications with validity periods |
| `carbon_factors` | Grid carbon intensity factors by geography and method |
| `workloads` | Workloads with service class, SLO, energy budget |
| `deployments` | Workload-to-asset allocation with method and fraction |
| `energy_allocations` | Per-workload energy allocation with bounds and coverage |
| `capacity_snapshots` | Facility capacity across 9 dimensions (power, cooling, rack U, network, storage, CPU, GPU, water, fuel) |

### KPI and lifecycle

| Table | Purpose |
|---|---|
| `kpi_definitions` | KPI definitions with formula version and JSON definition |
| `kpi_observations` | Computed KPI values with coverage, uncertainty, quality, calculation hash |
| `procedures` | Operational procedures with risk class, hazards, steps, exit criteria |
| `operational_workflows` | Work items with type, stage, status, priority, owner, procedure linkage |
| `workflow_tasks` | Task sequences within workflows |
| `approvals` | Approval decisions with scope digest and signature reference |
| `work_orders` | Maintenance work orders with failure codes, findings, verification |
| `incidents` | Incident records with severity, timeline, root cause confidence |
| `change_records` | Change management with risk class, blast radius, rollback plan |

### Evidence and cost

| Table | Purpose |
|---|---|
| `evidence_events` | Append-only hash-chained evidence log |
| `cost_books` | Approved cost books with currency, geography, price basis |
| `price_observations` | Immutable price records with source, confidence, quality, FX normalization |
| `estimate_projects` | Cost estimates with lifecycle phase, horizon, discount rate, contingency |
| `estimate_line_items` | Line items with quantity, unit cost, escalation, recurrence, price pinning |
| `cost_actuals` | Actual costs with accounting period, accrual state, source system |
| `cost_allocations` | Cost-to-workload allocation with method and evidence |
| `placement_comparison_snapshots` | Immutable draft TCO comparison snapshots |

### Views and functions

- **`estimate_cost_rollup`**: Aggregated present-value rollups by estimate, currency, and phase
- **`validate_estimate_price_link()`**: Trigger ensuring sourced lines pin approved, in-date, matching price observations
- **`reject_placement_snapshot_mutation()`**: Trigger enforcing snapshot immutability

### RLS policies

All tenant tables have forced row-level security:
```sql
CREATE POLICY tenant_scope ON dcc.<table>
  USING (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid);
```

---

## Adapters

All adapters follow the same contract:
- **Read-only**: never write to source or persist data
- **Bounded**: response size limits, row limits, timeout enforcement
- **No redirects**: SSRF prevention via redirect handler
- **Tenant-scoped**: all queries filtered by tenant context
- **Credential references**: secrets live in external managers, never in source

### Cloud pricing adapter

```python
from dcc.adapters import CloudCostAdapter, fetch_aws_prices

adapter = CloudCostAdapter()
result = adapter.fetch_prices("azure", service="Virtual Machines", region="eastus")
# or
result = fetch_aws_prices(service="ec2", region="us-east-1", sku="m5.large")
```

### EPMS adapter

```python
from dcc.adapters import create_epms_adapter

epms = create_epms_adapter("https://epms.example.com/api", vendor="generic")
readings = epms.read_meters(since="2024-01-01T00:00:00Z")
breakers = epms.read_breakers()
ups = epms.read_ups()
alarms = epms.read_alarms(severity="critical")
```

### CMMS adapter

```python
from dcc.adapters.cmms import probe_cmms, fetch_work_orders, fetch_assets

probe_cmms(endpoint="https://cmms.example.com/api")
orders = fetch_work_orders(endpoint="https://cmms.example.com/api", status="open", limit=50)
assets = fetch_assets(endpoint="https://cmms.example.com/api", asset_type="server")
```

### BMS adapter

```python
from dcc.adapters.bms import probe, fetch_points, fetch_alarms, fetch_hvac_summary

probe()
points = fetch_points(category="hvac", since="2024-01-01T00:00:00Z")
alarms = fetch_alarms(active_only=True, limit=100)
hvac = fetch_hvac_summary()
```

### OEM Redfish adapter

```python
from dcc.adapters.oem import probe, fetch_telemetry, fetch_server_telemetry

probe(vendor="dell")
telemetry = fetch_telemetry(vendor="hpe", resource_type="systems", metrics=["power_consumed_watts", "temperature_celsius"])
servers = fetch_server_telemetry(vendor="supermicro")
```

### Utility adapter

```python
from dcc.adapters.utility import probe, fetch_tariffs, fetch_bills, fetch_rate_schedule

probe()
tariffs = fetch_tariffs(tariff_code="COMM-IND-2024")
bills = fetch_bills(account_number="123456789")
schedule = fetch_rate_schedule(tariff_code="COMM-IND-2024")
```

### Weather and carbon adapter

```python
from dcc.adapters.weather import fetch_weather, fetch_carbon_intensity, fetch_weather_and_carbon

weather = fetch_weather(latitude="40.7128", longitude="-74.0060", forecast_days=3)
carbon = fetch_carbon_intensity(latitude="40.7128", longitude="-74.0060")
both = fetch_weather_and_carbon(latitude="40.7128", longitude="-74.0060")
```

### Hypervisor adapter

```python
from dcc.adapters.hypervisor import probe, fetch_vm_inventory, fetch_host_inventory, fetch_power_metrics

probe()
vms = fetch_vm_inventory(hypervisor_type="vmware_vcenter", power_state="powered_on")
hosts = fetch_host_inventory(hypervisor_type="kvm_libvirt")
power = fetch_power_metrics(hypervisor_type="vmware_vcenter", vm_ids=["vm-123"])
```

### Adapter registry

```python
from dcc.adapters import get_registry, AdapterInfo, AdapterCapability, HealthStatus

registry = get_registry()
registry.register(AdapterInfo(
    name="my-adapter", version="1.0.0", description="Custom adapter",
    capabilities=frozenset([AdapterCapability.PRICE_LOOKUP]),
    endpoint="https://api.example.com",
))
healthy = registry.discover(capability=AdapterCapability.PRICE_LOOKUP, healthy_only=True)
best = registry.negotiate(required={AdapterCapability.PRICE_LOOKUP})
health = registry.check_health("my-adapter")
rate_limit = registry.get_rate_limit("my-adapter")
```

---

## Economics engine

### Unit economics

```python
from dcc.economics import cost_per_kwh, cost_per_kw_year, cost_per_m2_year, cost_per_rack_year, cost_per_work_unit

result = cost_per_kwh(total_cost=1_000_000, annual_kwh=10_000_000)
# result.value = 0.10, result.unit = "USD/kWh"
```

### Bottom-up estimating

```python
from dcc.economics import DeploymentSpec, DeploymentType, estimate_deployment, quick_estimate

spec = DeploymentSpec(
    deployment_type=DeploymentType.COLOCATION,
    it_capacity_kw=500,
    facility_area_m2=2000,
    rack_count=100,
    tier_level="III",
    redundancy_level="N+1",
)
result = estimate_deployment(spec)
# result.line_items, result.phase_subtotals, result.total_cost
```

### TCO analysis

```python
from dcc.economics import TCOEngine, TCOAssumptions, TCOScenario, compare_tco

engine = TCOEngine()
assumptions = TCOAssumptions(discount_rate=0.05, horizon_years=5, currency="USD")
onprem = TCOScenario(name="On-Prem", capex=1_000_000, annual_opex=200_000)
cloud = TCOScenario(name="Cloud", capex=0, annual_opex=400_000)
result = compare_tco(onprem, cloud, assumptions)
# result.winner, result.tco_onprem, result.tco_cloud, result.yearly_cash_flows
```

### Price engine

```python
from dcc.economics import PriceEngine, PriceRecord, PriceStatus

engine = PriceEngine()
record = engine.create_price_record(
    item_code="SRV-R640", description="Dell R640 Server",
    category="it_equipment", quantity_unit="each",
    unit_price=5000, currency="USD", geography="US-East",
    source_kind="vendor_quote", source_name="Dell", source_ref="Q-2024-001",
    confidence=0.9, quality_status=PriceStatus.APPROVED,
)
```

### Tariff calculations

```python
from dcc.economics import create_flat_rate_tariff, create_tiered_tariff, create_simple_tou_tariff, calculate_tariff

flat = create_flat_rate_tariff(rate=0.10, unit="kWh")
tiered = create_tiered_tariff(tiers=[
    {"up_to": 1000, "rate": 0.08},
    {"up_to": 5000, "rate": 0.10},
    {"above": 5000, "rate": 0.12},
])
tou = create_simple_tou_tariff(peak_rate=0.15, off_peak_rate=0.06)
result = calculate_tariff(tiered, consumption_kwh=3000)
```

### Reconciliation

```python
from dcc.economics import reconcile_estimate, VarianceThresholds

thresholds = VarianceThresholds(warning_pct=0.05, critical_pct=0.10)
summary = reconcile_estimate(estimate_id="...", actuals=[...], thresholds=thresholds)
# summary.variances, summary.total_variance, summary.status
```

---

## Forecasting

### Load forecasting

```python
from dcc.forecasting import (
    MovingAverageForecaster, ExponentialSmoothingForecaster,
    HoltWintersForecaster, LinearTrendForecaster,
    select_best_model, detect_anomalies, compute_metrics,
)

forecaster = ExponentialSmoothingForecaster(alpha=0.3)
result = forecaster.forecast(observations, horizon=30)
# result.points, result.confidence_intervals, result.metrics

best = select_best_model(observations, candidates=["ma", "es", "hw", "lt"])
anomalies = detect_anomalies(observations, threshold=3.0)
```

### Failure prediction

```python
from dcc.forecasting import predict_equipment_failures

result = predict_equipment_failures(
    asset_id="...",
    condition_features=[...],
    maintenance_history=[...],
    failure_labels=[...],
)
# result.risk_score, result.failure_probability, result.contributing_factors
```

### Drift detection

```python
from dcc.forecasting import DriftDetector, DriftMethod, compute_psi, compute_ks_statistic

detector = DriftDetector(method=DriftMethod.PSI, threshold=0.2)
result = detector.detect(reference_distribution, current_distribution)
# result.drift_detected, result.severity, result.metric_value

psi = compute_psi(reference, current, bins=10)
ks = compute_ks_statistic(reference, current)
```

### Calibration

```python
from dcc.forecasting import calibrate_forecasts, apply_bias_correction, apply_multiplicative_correction

calibrated = calibrate_forecasts(forecast_actual_pairs, method="bias")
# or
corrected = apply_multiplicative_correction(forecasts, actuals)
```

### Backtesting

```python
from dcc.forecasting import walk_forward, cross_validate, evaluate_forecast

result = walk_forward(observations, forecaster, train_size=30, test_size=7)
# result.fold_results, result.mean_metrics

cv = cross_validate(observations, forecaster, n_splits=5)
# result.fold_results, result.mean_metrics, result.std_metrics
```

---

## Quality and validation

### Quality engine

```python
from dcc.quality import QualityEngine, QualityDimension, DEFAULT_WEIGHTS

engine = QualityEngine()
report = engine.score_source(
    source_id="connector-1",
    dimensions={
        QualityDimension.COVERAGE: 0.95,
        QualityDimension.FRESHNESS: 0.88,
        QualityDimension.COMPLETENESS: 0.92,
        QualityDimension.ACCURACY: 0.85,
        QualityDimension.CONSISTENCY: 0.90,
    },
)
# report.overall_score, report.dimension_scores, report.quality_grade
```

### Unit conversion

```python
from dcc.validation import convert, convert_temperature, UnitRegistry, get_registry

result = convert(100, "kW", "MW")  # 0.1
temp = convert_temperature(25, "C", "F")  # 77.0
registry = get_registry()
```

### Time series alignment

```python
from dcc.validation import align_series, detect_gaps, coverage_report, resample

aligned = align_series(series_a, series_b, interval="1h")
gaps = detect_gaps(observations, expected_interval_seconds=900)
report = coverage_report(observations, window_start, window_end)
resampled = resample(observations, interval="1h", aggregation="mean")
```

### Consistency validation

```python
from dcc.validation import (
    run_consistency_validation,
    reconcile_energy_sources,
    validate_asset_references,
    validate_capacity_headroom,
    validate_kpi_vs_telemetry,
    validate_cost_rollup,
    validate_workflow_facility_linkage,
    validate_tenant_boundary,
    validate_temporal_consistency,
    validate_unit_consistency,
    validate_provenance_consistency,
    validate_pue_consistency,
    validate_price_freshness,
    validate_estimate_price_links,
    validate_energy_allocation_coverage,
    validate_connector_data_freshness,
)

report = run_consistency_validation(tenant_id="...")
# report.findings, report.summary, report.is_valid
```

### Schema validation

```python
from dcc.validation import validate_asset, validate_facility, validate_estimate_project

try:
    validate_asset({
        "external_id": "SRV-001",
        "asset_type": "server",
        "name": "Web Server 1",
        "lifecycle_state": "active",
        "criticality": "high",
    })
except ValidationError as e:
    print(e.field, e.message)
```

---

## Security and tenant isolation

### Tenant context

```python
from dcc.security.tenant import TenantContext, current_tenant, tenant_context

# Context manager for database operations
with TenantContext(tenant_id, conn) as ctx:
    rows = conn.execute("SELECT * FROM dcc.assets").fetchall()

# Functional style
with tenant_context(tenant_id, conn):
    rows = conn.execute("SELECT * FROM dcc.assets").fetchall()

# Fail-closed: raises TenantNotFoundError if no context
try:
    current_tenant()
except TenantNotFoundError:
    pass
```

### Audit logging

```python
from dcc.security import AuditLogger, AuditAction, AuditCategory, AuditSeverity

logger = AuditLogger()
logger.log(AuditAction.READ, AuditCategory.DATA_ACCESS, severity=AuditSeverity.INFO,
           actor="operator-1", resource_type="asset", resource_id="...")
```

### Secrets management

```python
from dcc.security import create_aws_secrets_manager_adapter, create_vault_adapter

aws = create_aws_secrets_manager_adapter(region="us-east-1")
vault = create_vault_adapter(url="https://vault.example.com:8200", token="...")
```

---

## Provenance and lineage

```python
from dcc.provenance import LineageTracker, SourceType, TransformationType, QualityStatus

tracker = LineageTracker()

# Register a source
source = tracker.register_source(
    tenant_id="...",
    node_type="connector_reading",
    label="EPMS Meter Reading",
    source_type=SourceType.CONNECTOR,
    content={"meter_id": "M-001", "value": 150.5},
)

# Record a transformation
step = tracker.record_transformation(
    tenant_id="...",
    operation="kpi_calculation",
    transformation_type=TransformationType.CALCULATION,
    input_node_ids=[source.node_id],
    output_node_id="kpi-obs-1",
    output_content={"metric": "pue", "value": 1.45},
)

# Create a provenance record
record = tracker.create_record(
    tenant_id="...",
    artifact_type="kpi_observation",
    artifact_id="kpi-obs-1",
    source_type=SourceType.CALCULATED,
    quality_status=QualityStatus.GOOD,
    lineage_steps=[step],
)

# Verify chain integrity
result = tracker.verify_chain(tenant_id="...")
# result.valid, result.steps_checked, result.broken_at

# Trace lineage
lineage = tracker.get_lineage(tenant_id="...", artifact_id="kpi-obs-1", direction="upstream")
```

---

## Observability

```python
from dcc.observability import get_logger, configure_logging, correlation_id, bind_context
from dcc.observability import availability_slo, latency_slo, error_budget, build_slo_report

configure_logging(level="INFO")
logger = get_logger("dcc.api")
logger.info("Request processed", extra={"tenant_id": "...", "duration_ms": 45})

# SLO tracking
slo = availability_slo(target=0.999, window_days=30)
report = build_slo_report([slo], window_days=30)
```

---

## Infrastructure as code

Data Center Commander includes a comprehensive Terraform module library under [`iac/modules/`](iac/modules/) for provisioning cloud infrastructure, compliance controls, virtualization, and containerization across AWS, GCP, IBM Cloud, and DigitalOcean. All modules require Terraform >= 1.5.0.

### AWS infrastructure

| Module | Description |
|---|---|
| [`aws/vpc`](iac/modules/aws/vpc) | VPC with DNS support, flow logs to CloudWatch, and configurable CIDR |
| [`aws/subnets`](iac/modules/aws/subnets) | Public, private, and database subnets across multiple AZs with route tables and optional NAT gateway |
| [`aws/security-groups`](iac/modules/aws/security-groups) | Security groups with configurable ingress/egress rules |
| [`aws/ec2`](iac/modules/aws/ec2) | EC2 instances with configurable storage, networking, monitoring, EBS encryption, and EIP assignment |
| [`aws/iam`](iac/modules/aws/iam) | IAM roles, policies, instance profiles, groups, and users |
| [`aws/s3`](iac/modules/aws/s3) | S3 bucket with versioning, KMS encryption, public access blocking, lifecycle rules, and access logging |
| [`aws/rds`](iac/modules/aws/rds) | RDS instance with automated backups, encryption, Multi-AZ, Performance Insights, and CloudWatch log exports |
| [`aws/cloudwatch`](iac/modules/aws/cloudwatch) | CloudWatch log groups, metric alarms, dashboards, and event rules |

### AWS compliance as code

| Module | Description |
|---|---|
| [`aws-compliance`](iac/modules/aws-compliance) | Aggregator module for all AWS compliance services |
| [`aws-compliance/aws-config`](iac/modules/aws-compliance/aws-config) | AWS Config recorder, delivery channel, managed & custom rules, and aggregator |
| [`aws-compliance/guardduty`](iac/modules/aws-compliance/guardduty) | GuardDuty detector with S3/K8s/EC2 data sources, member invitations, and publishing destination |
| [`aws-compliance/security-hub`](iac/modules/aws-compliance/security-hub) | Security Hub with AWS Foundational, CIS, and PCI DSS standards |
| [`aws-compliance/cloudtrail`](iac/modules/aws-compliance/cloudtrail) | Multi-region CloudTrail with log validation, event selectors, and insights |
| [`aws-compliance/iam-access-analyzer`](iac/modules/aws-compliance/iam-access-analyzer) | IAM Access Analyzer with unused access analysis and archive rules |

### GCP compliance as code

| Module | Description |
|---|---|
| [`gcp-compliance/cloud-audit-logs`](iac/modules/gcp-compliance/cloud-audit-logs) | Cloud Audit Logs with log sinks, custom log buckets, and log views |
| [`gcp-compliance/organization-policies`](iac/modules/gcp-compliance/organization-policies) | Organization Policy constraints (OS Login, Shielded VMs, VPC Flow Logs, serial port disable, etc.) |
| [`gcp-compliance/security-command-center`](iac/modules/gcp-compliance/security-command-center) | Security Command Center source with notification configs, mute rules, and custom configs |
| [`gcp-compliance/vpc-service-controls`](iac/modules/gcp-compliance/vpc-service-controls) | VPC Service Controls perimeters with access policies, access levels, and ingress/egress policies |

### IBM Cloud infrastructure

| Module | Description |
|---|---|
| [`ibm/vpc`](iac/modules/ibm/vpc) | VPC with subnets, public gateways, network ACLs, security groups, and flow logs |
| [`ibm/vsi`](iac/modules/ibm/vsi) | Virtual Server Instance with boot/data volumes, floating IP, and SSH keys |
| [`ibm/block-storage`](iac/modules/ibm/block-storage) | Block storage volume with VSI attachment and customer-managed encryption |
| [`ibm/object-storage`](iac/modules/ibm/object-storage) | COS bucket with versioning, lifecycle rules, encryption, and activity tracking |
| [`ibm/iam`](iac/modules/ibm/iam) | IAM access groups with members, policies, and dynamic rules |

### DigitalOcean infrastructure

| Module | Description |
|---|---|
| [`digitalocean/vpc`](iac/modules/digitalocean/vpc) | VPC with configurable IP range and region |
| [`digitalocean/droplets`](iac/modules/digitalocean/droplets) | Droplet instances with backups, monitoring, IPv6, user data, and graceful shutdown |
| [`digitalocean/load-balancer`](iac/modules/digitalocean/load-balancer) | Load balancer with health checks, forwarding rules, and SSL/TLS |
| [`digitalocean/block-storage`](iac/modules/digitalocean/block-storage) | Block storage volumes with filesystem configuration and droplet attachment |
| [`digitalocean/database`](iac/modules/digitalocean/database) | Managed database cluster with maintenance window and private networking |
| [`digitalocean/monitoring`](iac/modules/digitalocean/monitoring) | Monitoring alerts with email and Slack notifications |

### Virtualization (KVM/libvirt)

| Module | Description |
|---|---|
| [`kvm`](iac/modules/kvm) | KVM/libvirt storage pools, virtual networks (NAT/routed/isolated), and VMs with cloud-init, multiple disks, and network interfaces |
| [`integration/virtualization`](iac/modules/integration/virtualization) | Complete virtualization environment with storage pool, NAT network, golden image cloning, cloud-init, and VM fleet |

### Containerization (Docker)

| Module | Description |
|---|---|
| [`integration/containerization`](iac/modules/integration/containerization) | Docker network, service containers with healthchecks, Traefik reverse proxy with TLS, Prometheus + Grafana monitoring stack, and local registry |

### OpenShift

| Module | Description |
|---|---|
| [`openshift/cluster`](iac/modules/openshift/cluster) | OpenShift cluster provisioning via `openshift-install` (AWS/Azure/GCP) |
| [`openshift/project`](iac/modules/openshift/project) | OpenShift project/namespace with resource quotas, limit ranges, and network policies |
| [`openshift/deployment`](iac/modules/openshift/deployment) | Deployment with ConfigMap, Secret, Service, HPA, PDB, health probes, and rolling update strategy |
| [`openshift/rbac`](iac/modules/openshift/rbac) | ServiceAccount with Role/ClusterRole and bindings |
| [`openshift/route`](iac/modules/openshift/route) | Route with edge/passthrough/reencrypt TLS termination |

### Data center operations

| Module | Description |
|---|---|
| [`integration/data-center-ops`](iac/modules/integration/data-center-ops) | Generates DC configuration JSON, capacity plans, Prometheus alert rules, backup scripts, and operations runbooks |

### Usage

Each module is self-contained with its own `variables.tf`, `outputs.tf`, and `main.tf`. Modules can be composed together:

```hcl
module "vpc" {
  source     = "./modules/aws/vpc"
  name       = "datacenter-vpc"
  cidr_block = "10.0.0.0/16"
}

module "subnets" {
  source               = "./modules/aws/subnets"
  name                 = "datacenter"
  vpc_id               = module.vpc.vpc_id
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.20.0/24"]
}

module "compliance" {
  source              = "./modules/aws-compliance"
  aws_region          = "us-east-1"
  environment         = "production"
  compliance_s3_bucket = "my-compliance-logs"
}
```

---

## Synthetic demo

After applying the normal schema and demo seed, add the optional additive
30-day history using `database/demo_analytics_expansion.sql` against only the
specifically named local demo database. The script adds 15-minute interval
energy and derived daily energy/PUE points; modeled thermal, carbon,
compute-efficiency and headroom values are explicitly marked synthetic. It is
idempotent and does not reset or delete data.

Open the local UI with the seeded tenant and explicit demo switch:

```text
http://127.0.0.1:8795/?tenant_id=dcc00000-0000-4000-8000-000000000001&demo=synthetic
```

Without `demo=synthetic`, synthetic facility KPIs and synthetic cost-book rows
remain quarantined from the operational view. Demo mode is presentation-only:
all data remain visibly tagged, price assumptions are not market quotes, and
forecasts stay disabled where minimum history or authoritative labels are
missing. It never enables facility actuation or other writes. See
[`docs/LOCAL_DEVELOPMENT.md`](docs/LOCAL_DEVELOPMENT.md) before running seeds.

---

## Standalone layout

```text
data-center-commander/
├── database/       portable schema, optional synthetic seed, guarded reset
│   ├── schema.sql
│   ├── demo_seed.sql
│   ├── demo_analytics_expansion.sql
│   ├── cost_demo_seed.sql
│   └── migrations/
│       ├── 001_cost_intelligence.sql
│       ├── 002_lifecycle_rollup_fix.sql
│       ├── 003_estimate_price_link_validation.sql
│       ├── 004_placement_comparison_snapshots.sql
│       ├── 005_performance_indexes.sql
│       ├── 006_performance_optimization.sql
│       ├── 007_evidence_verifier_single_source.sql
│       ├── 008_disaster_recovery.sql
│       └── 009_backup_operations.sql
├── docs/           architecture, lifecycle, data/KPI, adapters, security, runbooks
│   ├── ARCHITECTURE.md
│   ├── COST_ESTIMATING_AND_UNIT_ECONOMICS.md
│   ├── DATA_MODEL_AND_KPIS.md
│   ├── INTEGRATIONS.md
│   ├── LIFECYCLE_OPERATIONS.md
│   ├── LOCAL_DEVELOPMENT.md
│   ├── OPERATOR_WORKFLOWS.md
│   ├── PURPLE_TEAM_READINESS.md
│   ├── SECURITY_AND_GOVERNANCE.md
│   └── media/       screenshots and overview GIF
├── scripts/        local startup, safe bootstrap, fresh-deploy verification
│   ├── run-local.py            starts the FastAPI app; --legacy serves /v1
│   ├── verify-fresh-deploy.sh  schema + all migrations + GET-route smoke test
│   ├── db-seed-demo.sh
│   └── db-reset-demo.sh
├── src/dcc/        loopback read-model API and domain libraries
│   ├── api_async.py    served FastAPI app, routing, auth middleware, tenant scoping
│   ├── pgcompat.py     psycopg3 adapter for the asyncpg-style queries
│   ├── api.py          legacy stdlib ThreadingHTTPServer (serves /v1 under run-local.py --legacy)
│   ├── azure_prices.py Azure retail price client
│   ├── google_prices.py GCP billing catalog client
│   ├── adapters/       read-only source adapters
│   │   ├── registry.py     adapter discovery, health, rate limits
│   │   ├── cloud.py        AWS/Azure/GCP pricing
│   │   ├── epms.py         electrical power monitoring
│   │   ├── cmms.py         maintenance management
│   │   ├── bms.py          building management
│   │   ├── meter.py        Modbus/BACnet/SNMP meters
│   │   ├── oem.py          Redfish server telemetry
│   │   ├── utility.py      utility tariffs and bills
│   │   ├── weather.py      weather and carbon intensity
│   │   └── hypervisor.py   VM/host telemetry
│   ├── economics/      cost and pricing engine
│   │   ├── unit.py         unit economics calculations
│   │   ├── estimates.py    bottom-up estimating
│   │   ├── tco.py          total cost of ownership
│   │   ├── prices.py       price engine and versioning
│   │   ├── tariffs.py      tariff calculations
│   │   ├── reconciliation.py  estimate-to-actual
│   │   ├── allocation.py   cost allocation
│   │   └── budget.py       budget forecasting
│   ├── forecasting/    predictive models
│   │   ├── load.py         load forecasting
│   │   ├── price.py        price forecasting
│   │   ├── failure.py      failure prediction
│   │   ├── drift.py        drift detection
│   │   ├── calibration.py  forecast calibration
│   │   ├── backtest.py     backtesting framework
│   │   ├── capacity.py     capacity forecasting
│   │   ├── maintenance.py  maintenance signals
│   │   └── features.py     feature engineering
│   ├── quality/        data quality engine
│   │   ├── engine.py       quality scoring
│   │   ├── anomaly.py      anomaly detection
│   │   └── freshness.py    freshness checks
│   ├── validation/     validation and consistency
│   │   ├── units.py        unit conversion
│   │   ├── intervals.py    time series alignment
│   │   ├── consistency.py  15 consistency validators
│   │   ├── schema.py       41 entity validators
│   │   └── boundaries.py   boundary checks
│   ├── security/       tenant isolation and secrets
│   │   └── tenant.py       RLS context management
│   ├── provenance/     lineage tracking
│   │   └── tracker.py      hash-chained lineage
│   └── observability/  logging and SLOs
│       └── logging.py      structured logging
├── tests/          comprehensive test suite
│   ├── test_adapters.py
│   ├── test_allocation.py
│   ├── test_anomaly.py
│   ├── test_azure_prices.py
│   ├── test_backtest.py
│   ├── test_calibration.py
│   ├── test_capacity_forecast.py
│   ├── test_cmms_adapter.py
│   ├── test_consistency.py
│   ├── test_contracts.py
│   ├── test_drift.py
│   ├── test_economics_estimates.py
│   ├── test_economics_prices.py
│   ├── test_economics_unit.py
│   ├── test_epms_adapter.py
│   ├── test_failure_prediction.py
│   ├── test_features.py
│   ├── test_freshness.py
│   ├── test_intervals.py
│   ├── test_maintenance.py
│   ├── test_meter_adapter.py
│   ├── test_price_forecasting.py
│   ├── test_scenarios.py
│   ├── test_tco.py
│   ├── test_units.py
│   └── security/
│       └── __init__.py
├── iac/            Terraform/OpenTofu modules, root config, and policies for multi-cloud IaC
│   ├── root/         OpenTofu root orchestrator (main.tf, variables.tf, outputs.tf)
│   ├── modules/
│   │   ├── aws/            VPC, subnets, security groups, EC2, IAM, S3, RDS, CloudWatch
│   │   ├── aws-compliance/ Config, GuardDuty, Security Hub, CloudTrail, IAM Access Analyzer
│       ├── gcp-compliance/ Audit Logs, Org Policies, SCC, VPC Service Controls
│       ├── ibm/            VPC, VSI, block storage, object storage, IAM
│       ├── digitalocean/   VPC, droplets, load balancer, block storage, database, monitoring
│       ├── kvm/            KVM/libvirt virtualization (pools, networks, VMs)
│       ├── openshift/      Cluster, project, deployment, RBAC, route
│       └── integration/    Virtualization, containerization, data-center-ops
├── k8s/            Kubernetes manifests (Kustomize-based deployment)
│   ├── 00-namespace.yaml
│   ├── 01-configmap.yaml
│   ├── 02-secret.yaml
│   ├── 03-serviceaccount.yaml
│   ├── 04-deployment.yaml
│   ├── 05-service.yaml
│   ├── 06-ingress.yaml
│   ├── 07-hpa.yaml
│   ├── 08-pdb.yaml
│   ├── 09-networkpolicy.yaml
│   └── kustomization.yaml
├── monitoring/     Prometheus + Grafana monitoring stack
│   ├── docker-compose.monitoring.yml
│   ├── prometheus/
│   ├── grafana/
│   └── alertmanager/
├── reports/        audit and specification documents
├── ui/             live command-center view (no fabricated readings)
│   ├── index.html
│   ├── onboarding.js
│   ├── topology.js
│   ├── azure-prices.js
│   ├── placement-comparison.js
│   ├── placement-scenarios.js
│   ├── quality-dashboard.js
│   ├── security-dashboard.js
│   ├── ops-dashboard.js
│   ├── economics-dashboard.js
│   └── forecast-dashboard.js
├── pyproject.toml
├── uv.lock
└── LICENSE         AGPL-3.0-only
```

---

## Migrations

Existing databases created before the cost-intelligence module should apply migrations in order:

1. [`001_cost_intelligence.sql`](database/migrations/001_cost_intelligence.sql): cost books, price observations, estimates, actuals
2. [`002_lifecycle_rollup_fix.sql`](database/migrations/002_lifecycle_rollup_fix.sql): corrected lifecycle rollup
3. [`003_estimate_price_link_validation.sql`](database/migrations/003_estimate_price_link_validation.sql): price pinning trigger
4. [`004_placement_comparison_snapshots.sql`](database/migrations/004_placement_comparison_snapshots.sql): immutable draft snapshots
5. [`005_performance_indexes.sql`](database/migrations/005_performance_indexes.sql): query indexes
6. [`006_performance_optimization.sql`](database/migrations/006_performance_optimization.sql): further index work
7. [`007_evidence_verifier_single_source.sql`](database/migrations/007_evidence_verifier_single_source.sql): removes the database-side verifier that disagreed with the writer
8. [`008_disaster_recovery.sql`](database/migrations/008_disaster_recovery.sql): backup policies, DR test plans and executions, RTO/RPO measurements, all under RLS
9. [`009_backup_operations.sql`](database/migrations/009_backup_operations.sql): `backup_runs` under RLS, the table the three backup operations read and write

A new database is built from `database/schema.sql` followed by **all nine**
migrations. `database/schema.sql` alone is not sufficient: 005–009 add objects the API
reads (`mv_workflow_health` and its column shape, the DR tables, `backup_runs`, the
performance indexes).
`scripts/verify-fresh-deploy.sh` performs exactly that sequence on a scratch database
and then asserts the table count, the required views and DR tables, forced RLS, and a
smoke test of every GET `/v2` route that takes no path parameter, 19 of the 20. Existing
synthetic demo databases can add the cost-only fixture with `database/cost_demo_seed.sql`.

---

## Testing

Run the full test suite:

```bash
uv run --extra test python -m unittest discover -s tests -v
```

The test suite covers:
- **Adapter contracts**: EPMS, CMMS, meter, Azure pricing
- **Economics**: unit economics, estimates, prices, TCO, allocation
- **Forecasting**: backtest, calibration, drift, capacity, features, load, price, anomaly, maintenance
- **Quality**: freshness, anomaly detection
- **Validation**: consistency, intervals, units, boundaries, schema
- **Security**: tenant isolation
- **API**: route contracts, response shapes, error handling

---

## Roadmap

| Stage | Deliverable | Acceptance evidence |
|---|---|---|
| 0 · Local command center | Portable schema, guarded demo seed, 30-day synthetic history, overview/energy/BI/economics/workflow/evidence panels | API/schema checks, source labels, rerunnable additive seed, and synthetic visual tour in `docs/media/` |
| 1 · Source onboarding | Read-only connector registry, onboarding wizard, identity/scope/freshness checks, import previews | Vendor sandbox contracts, malformed/stale-data tests, secret-reference-only config, operator-confirmed mapping |
| 2 · Data quality and BI | Boundary-aligned intervals, missingness/coverage budgets, versioned formulas, KPI lineage and cost actual reconciliation | Reproducible queries, boundary tests, quality SLOs and calculation manifests |
| 3 · Predictive maintenance | Condition features, work-order/failure labels, maintenance history, interpretable forecasting and drift | Time-split backtests, calibration/error analysis, leakage checks, minimum-history gates and human disposition |
| 4 · Lifecycle and economics | Sourced dated prices/tariffs/contracts, quantity takeoff, contingency/escalation/FX, estimate-to-actual and unit economics | Source digest, review/expiry policy, uncertainty ranges, independent Finance/Facilities review |
| 5 · Production hardening | AuthN/AuthZ, tenant isolation, secret manager, migrations, backups/restore, observability, incident handling, HA | Threat review, penetration tests, recovery drill, SLOs, runbooks, privacy/retention signoff |
| 6 · Certified ecosystem | OEM/cloud/facility adapter conformance, optional enterprise analytics and support | Conformance suite and customer-controlled credentials/export; portable core remains OSS |

The roadmap is an implementation sequence, not a readiness claim. Authentication,
tenant isolation, migrations, observability and evidence verification are now
delivered and tested; vendor/cloud live adapters, forecasts validated at production
accuracy, external audit and safety-control integration are not. The API no longer
requires loopback-only deployment for access control, but it has not been
penetration-tested by a third party and should not be exposed to the public internet
without that review.

---

## Safety and authority boundary

See [`docs/SECURITY_AND_GOVERNANCE.md`](docs/SECURITY_AND_GOVERNANCE.md). This
starter is observation and decision-support only. It contains no generic shell,
remote desktop, BMS write, breaker/switch control, setpoint change, VM lifecycle,
or workload dispatch path. Recommendations are not commands. Any future
execution adapter requires a separate, independently reviewed project gate.

---

## Screenshots

The captures below use the documented local synthetic walkthrough:
`http://127.0.0.1:8795/?tenant_id=dcc00000-0000-4000-8000-000000000001&demo=synthetic`.
Every capture keeps the **SYNTHETIC DEMO · NOT LIVE** banner visible. All readings,
workflows, estimates, and price assumptions are fixtures; they are not facility
telemetry, forecasts, quotes, invoices, approvals, or operational evidence.

<details>
<summary>View screenshots for every section</summary>

| Section | Capture |
|---|---|
| Command picture | ![Facility command picture](docs/media/command-picture.jpg) |
| Energy & carbon | ![Energy and carbon](docs/media/energy-carbon.jpg) |
| Data science & BI | ![Data science and BI](docs/media/data-science-bi.jpg) |
| Sizing & economics | ![Sizing and economics](docs/media/sizing-economics.jpg) |
| Placement tradeoffs | ![Placement tradeoffs](docs/media/placement-tradeoffs.jpg) |
| Capacity & resilience | ![Capacity and resilience](docs/media/capacity-resilience.jpg) |
| Estate & lifecycle | ![Estate and lifecycle](docs/media/estate-lifecycle.jpg) |
| Reliability | ![Reliability](docs/media/reliability.jpg) |
| Operations queue | ![Operations queue](docs/media/operations-queue.jpg) |
| Integrations | ![Integrations](docs/media/integrations.jpg) |
| Evidence & audit | ![Evidence and audit](docs/media/evidence-audit.jpg) |
| Suggested workloads | ![Suggested workloads](docs/media/suggested-workloads.jpg) |
| Critical & GRC | ![Critical environments and GRC](docs/media/critical-grc.jpg) |

</details>

---

## License

This project is licensed under the GNU Affero General Public License v3.0
(AGPL-3.0-only); see [LICENSE](LICENSE).
