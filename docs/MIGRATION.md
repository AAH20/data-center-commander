# Data Center Commander — Migration Guide

This document describes every breaking change in Data Center Commander and
provides step-by-step migration instructions. Changes are grouped by version
and area of impact.

---

## Table of Contents

- [Version 0.1.0 — Initial Public Release](#version-010--initial-public-release)
  - [Database Schema](#database-schema)
  - [API Surface](#api-surface)
  - [Configuration](#configuration)
  - [UI / Client](#ui--client)
  - [Adapters](#adapters)
  - [Economics Engine](#economics-engine)
  - [Forecasting](#forecasting)
  - [Quality & Validation](#quality--validation)
  - [Security & Tenant Isolation](#security--tenant-isolation)
  - [Provenance & Lineage](#provenance--lineage)
- [Migration Procedures](#migration-procedures)
  - [Fresh Install](#fresh-install)
  - [Upgrading from Pre-Release](#upgrading-from-pre-release)
  - [Database Migration Order](#database-migration-order)
  - [Rollback Procedures](#rollback-procedures)
- [Breaking Changes Summary](#breaking-changes-summary)

---

## Version 0.1.0 — Initial Public Release

### Database Schema

#### New Schema: `dcc`

All tables now live under the `dcc` schema (not `public`). The schema is
created by `database/schema.sql` and is idempotent for fresh installs.

**Breaking:** If you previously created tables in `public`, you must migrate
them to `dcc`. The application sets `search_path = dcc, public` at the start
of each migration, but all DDL now targets `dcc.` explicitly.

#### New Tables

| Table | Purpose | Migration |
|---|---|---|
| `dcc.cost_books` | Versioned cost book headers with approval workflow | 001 |
| `dcc.price_observations` | Immutable price records with FX normalization | 001 |
| `dcc.estimate_projects` | Versioned estimate project headers | 001 |
| `dcc.estimate_line_items` | Individual cost line items with pricing status | 001 |
| `dcc.cost_actuals` | Actual cost entries from ERP/AP/CMMS | 001 |
| `dcc.cost_allocations` | Shared cost allocation to workloads | 001 |
| `dcc.placement_comparison_snapshots` | Immutable draft TCO comparison snapshots | 004 |

#### Modified Tables

- **`estimate_line_items`**: Added `cost_behavior` column with values
  `one_time`, `fixed_recurring`, `variable`, `step_fixed`, `capitalized`.
  Added `useful_life_months`, `escalation_pct`, `recurrence_months`,
  `start_month`, `pricing_status` columns. Added `extended_base` as a
  generated column: `quantity * (1 + waste_factor) * base_unit_cost`.

- **`estimate_line_items`**: Added `price_observation_id` foreign key to
  `dcc.price_observations`. When `pricing_status = 'sourced'`, this field
  is mandatory and must reference an approved price observation.

#### New Constraints

1. **Price Link Validation Trigger** (`estimate_price_link_check`):
   - Fires on `INSERT` or `UPDATE` of `estimate_line_items`.
   - Validates that `pricing_status = 'sourced'` lines have a pinned
     `price_observation_id`.
   - Validates that the pinned price observation belongs to the same tenant.
   - Validates that both the price observation and its cost book have
     `quality_status = 'approved'` and `status = 'approved'` respectively.
   - Validates that `quantity_unit`, `currency`, and `geography` match
     between the line item and the pinned price.
   - Validates that the price is not stale relative to the estimate's
     `price_as_of` date.
   - Validates that `base_unit_cost` equals the price observation's
     `normalized_unit_price`.

   **Breaking:** Existing `sourced` line items without a valid pinned price
   observation will fail to insert or update. You must either:
   - Set `pricing_status` to `'allowance'` or `'unpriced'` for lines without
     a pinned price, OR
   - Create the required price observation and cost book records first.

2. **Placement Snapshot Immutability** (`placement_snapshots_immutable`):
   - Fires on `UPDATE` or `DELETE` of `placement_comparison_snapshots`.
   - Raises an exception: "placement comparison snapshots are immutable".

   **Breaking:** You cannot modify or delete placement comparison snapshots
   after creation. To "change" a snapshot, create a new one.

3. **Cost Book Approval Check**:
   - `CHECK((status = 'approved') = (approved_at IS NOT NULL))`
   - A cost book can only have `status = 'approved'` if `approved_at` is set.

4. **Synthetic Demo Provenance Check**:
   - `CHECK(source_kind <> 'synthetic_demo' OR provenance @> '{"synthetic":true}')`
   - All synthetic demo price observations must carry
     `provenance.synthetic = true`.

5. **Recurrence Months Check**:
   - `CHECK((cost_behavior IN ('fixed_recurring', 'variable') AND recurrence_months > 0) OR (cost_behavior NOT IN ('fixed_recurring', 'variable') AND recurrence_months IS NULL))`
   - Recurring cost behaviors must have a positive `recurrence_months`;
   - non-recurring behaviors must have `recurrence_months IS NULL`.

6. **Unpriced Line Check**:
   - `CHECK((pricing_status = 'unpriced') OR price_observation_id IS NOT NULL OR assumptions ? 'pricing_basis')`
   - Unpriced lines must either have a pinned price or an explicit
     `pricing_basis` key in their `assumptions` JSONB.

7. **Extended Range Check**:
   - `CHECK((extended_low IS NULL AND extended_high IS NULL) OR (extended_low IS NOT NULL AND extended_high IS NOT NULL AND extended_low <= extended_base AND extended_high >= extended_base))`
   - Low/high bounds must be consistent with the base extended cost.

#### New Indexes

| Index | Table | Columns |
|---|---|---|
| `price_lookup_idx` | `price_observations` | `(tenant_id, item_code, geography, valid_from DESC)` partial on `quality_status = 'approved'` |
| `price_source_freshness_idx` | `price_observations` | `(tenant_id, source_kind, observed_at DESC)` |
| `estimate_line_rollup_idx` | `estimate_line_items` | `(tenant_id, estimate_id, phase, line_no)` |
| `cost_actuals_period_idx` | `cost_actuals` | `(tenant_id, accounting_period, cost_type, facility_id)` |
| `cost_allocation_workload_idx` | `cost_allocations` | `(tenant_id, workload_id, window_end DESC)` |
| `placement_snapshots_recent_idx` | `placement_comparison_snapshots` | `(tenant_id, created_at DESC, id DESC)` |

#### New Views

- **`estimate_cost_rollup`**: Aggregates line items by estimate, currency,
  and phase. Computes `first_period_cost`, `present_value_base`,
  `present_value_low`, `present_value_high`, `line_count`,
  `unpriced_lines`, and `synthetic_lines`.

  **Breaking:** The view was corrected in migration 002 to use
  `count(DISTINCT l.id)` instead of `count(*)` and to properly handle
  multiple takeoff lines sharing a phase. If you have custom queries
  depending on the old behavior, they will return different results.

#### Row Level Security (RLS)

All tables in the `dcc` schema have RLS enabled and forced. The policy
`tenant_scope` is applied to every table:

```sql
CREATE POLICY tenant_scope ON dcc.<table>
  USING (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('dcc.tenant_id', true), '')::uuid);
```

**Breaking:** Direct database access without setting `dcc.tenant_id` will
return zero rows. You must execute:

```sql
SELECT set_config('dcc.tenant_id', '<tenant-uuid>', true);
```

before querying any `dcc` table. The API does this automatically; direct
SQL clients must do it manually.

#### Tenant Foreign Key Cascade

Every table with a `tenant_id` column has a foreign key to `dcc.tenants(id)`
with `ON DELETE CASCADE`. Deleting a tenant removes all associated data.

---

### API Surface

#### Base URL

The API binds to `127.0.0.1:8790` by default (loopback only). The port can
be overridden via the `PORT` environment variable.

#### Authentication

**Breaking:** The initial release has no authentication. The API is
loopback-only and relies on network isolation. Production deployments
must place a reverse proxy with authentication in front of the API.

#### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/healthz` | Service health (no database check) |
| `GET` | `/readyz` | Readiness probe (checks schema + RLS) |
| `GET` | `/v1/overview` | Executive summary (facilities, KPIs, workflows) |
| `GET` | `/v1/facilities` | Facility list |
| `GET` | `/v1/assets` | Asset inventory |
| `GET` | `/v1/topology` | Asset dependency graph (nodes + edges) |
| `GET` | `/v1/workflows` | Operational workflow queue |
| `GET` | `/v1/connectors` | Connector registry |
| `GET` | `/v1/capacity` | Capacity snapshots |
| `GET` | `/v1/evidence` | Evidence event log |
| `GET` | `/v1/costs` | Cost intelligence (estimates, prices, actuals) |
| `GET` | `/v1/analytics` | KPI series, quality metrics, telemetry health |
| `GET` | `/v1/placement/scenarios` | List saved placement comparison drafts |
| `POST` | `/v1/placement/scenarios` | Save a placement comparison draft |
| `GET` | `/v1/pricing/azure-retail` | Azure retail price lookup |
| `GET` | `/v1/pricing/google-cloud-retail` | Google Cloud price lookup |
| `GET` | `/` | Command center UI (HTML) |
| `GET` | `/assets/<name>` | UI JavaScript modules |

#### Query Parameters

**All endpoints except `/healthz` and `/` require `tenant_id`:**

```
?tenant_id=<uuid>
```

The `tenant_id` must be a valid UUID. Multiple `tenant_id` values or
malformed UUIDs return `400`.

**Optional parameters:**

- `window_days` (integer, 1-90, default 30): Time window for analytics and
  overview endpoints.
- `demo=synthetic`: When set, synthetic demo data is included in responses.
  Without this parameter, synthetic data is quarantined (replaced with
  empty arrays and "Not verified" labels).

#### Response Format

All responses are JSON with `Content-Type: application/json; charset=utf-8`
and `Cache-Control: no-store`.

Every response includes `read_only: true` and `execution_permitted: false`
where applicable.

**Error responses:**

```json
{
  "error": "<error_code>",
  "read_only": true,
  "execution_permitted": false
}
```

Common error codes:
- `tenant_id must be one UUID` — missing or invalid tenant_id
- `window_days must be an integer from 1 to 90` — invalid window
- `database_not_configured` — DCC_DATABASE_URL not set
- `database_unavailable_or_schema_missing` — database unreachable
- `route_not_found` — unknown path
- `same_origin_required` — POST without matching Origin header
- `placement_snapshot_database_unavailable` — snapshot persistence failed

#### POST /v1/placement/scenarios

**Request:**

```json
{
  "tenant_id": "<uuid>",
  "name": "My comparison (1-120 chars)",
  "payload": {
    "schema_version": "placement-tco-comparison.v1",
    "assumptions": {
      "currency": "USD",
      "horizon_months": 36,
      "annual_discount_rate_pct": 8.0,
      "useful_units_per_month": 1000,
      "useful_unit_name": "requests",
      "demand_profile": "Steady / predictable"
    },
    "sources": {
      "onprem": {
        "type": "Vendor quote / contract",
        "reference": "Q-2026-001",
        "observed_on": "2026-01-15"
      },
      "cloud": {
        "type": "Provider calculator / public catalog",
        "reference": "azure-retail-eastus",
        "observed_on": "2026-01-15"
      }
    },
    "results": {
      "onprem": { "...": "..." },
      "cloud": { "...": "..." }
    }
  }
}
```

**Validation:**
- `name`: 1-120 characters (trimmed)
- `payload.schema_version`: must be `"placement-tco-comparison.v1"`
- `payload.assumptions.currency`: 3-letter code
- `payload.assumptions.horizon_months`: integer 1-120
- `payload.sources.onprem` and `payload.sources.cloud`: must have `type`,
  `reference`, `observed_on` (YYYY-MM-DD)
- `payload.results.onprem` and `payload.results.cloud`: must be objects
- Maximum payload size: 64 KiB (70,000 bytes request body)

**Response (201):**

```json
{
  "tenant_id": "<uuid>",
  "scenario": {
    "id": "<uuid>",
    "name": "My comparison",
    "schema_version": "placement-tco-comparison.v1",
    "payload": { "...": "..." },
    "payload_sha256": "<64-char-hex>",
    "created_at": "2026-01-15T10:30:00+00:00"
  },
  "status": "draft_snapshot",
  "execution_permitted": false
}
```

**Breaking:** Snapshots are immutable. There is no `PUT`, `PATCH`, or
`DELETE` endpoint for snapshots. To update a comparison, create a new
snapshot.

#### GET /v1/placement/scenarios

Returns up to 100 most recent snapshots for the tenant, ordered by
`created_at DESC, id DESC`.

#### Pricing Endpoints

**GET /v1/pricing/azure-retail**

Parameters: `service_name` (required), `region`, `sku`, `currency` (3-letter,
default USD).

Returns bounded first-page results (max 100 rows, 1 MB response limit).
Never follows `NextPageLink`. Does not persist prices.

**GET /v1/pricing/google-cloud-retail**

Parameters: `service_name` (required), `region` (required), `sku_query`
(required), `currency` (3-letter, default USD).

Requires `GOOGLE_CLOUD_BILLING_API_KEY` environment variable. Returns
bounded first-page results (max 100 rows, 2 MB response limit). Does not
persist prices.

**Breaking:** Google Cloud pricing returns `503` when the API key is not
configured (not `502`). Check for this status code in error handling.

---

### Configuration

#### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DCC_DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `PORT` | No | `8790` | API listen port |
| `GOOGLE_CLOUD_BILLING_API_KEY` | No | — | Google Cloud Billing API key |
| `DCC_ALLOW_SYNTHETIC_DATA` | No | — | Set to `YES_SYNTHETIC_<db-name>` to enable demo seed |
| `DCC_ALLOW_DEMO_RESET` | No | — | Set to `RESET_<db-name>` to enable demo reset |

**Breaking:** `DCC_DATABASE_URL` must point to a database with the `dcc`
schema applied. The application will not auto-create the schema.

#### Database Connection

The application uses `psycopg_pool.ConnectionPool` with:
- `min_size=1`, `max_size=8`
- `timeout=3` seconds
- `prepare_threshold=None` (no prepared statements)

The pool is created at startup. If the database is unreachable, the API
starts but returns `503` for all database-backed endpoints.

---

### UI / Client

#### New Command Center Views

The UI is a single-page application served at `/`. It requires a `tenant_id`
query parameter to display data.

**Views:**

1. **Command Picture** (`#view-overview`) — Executive summary
2. **Energy & Carbon** (`#view-energy`) — Energy metrics and carbon
3. **Data Science & BI** (`#view-analytics`) — KPI series and quality
4. **Sizing & Economics** (`#view-finance`) — Cost estimates and unit economics
5. **Placement Tradeoffs** (`#view-placement`) — On-prem vs. cloud TCO
6. **Cost Intelligence** (`#view-economics`) — Cost breakdowns and trends
7. **Capacity & Resilience** (`#view-capacity`) — Capacity snapshots
8. **Estate & Lifecycle** (`#view-assets`) — Asset inventory and topology
9. **Reliability** (`#view-reliability`) — Failure risk profiles
10. **Operations Queue** (`#view-workflows`) — Workflow management
11. **Integrations** (`#view-integrations`) — Connector management
12. **Evidence & Audit** (`#view-evidence`) — Evidence event log
13. **Forecast Dashboard** (`#view-forecast`) — KPI forecasts

#### UI Modules (JavaScript)

| Module | Path | Description |
|---|---|---|
| `onboarding.js` | `/assets/onboarding.js` | First-run workspace setup |
| `azure-prices.js` | `/assets/azure-prices.js` | Azure retail price lookup |
| `placement-comparison.js` | `/assets/placement-comparison.js` | TCO comparison calculator |
| `placement-scenarios.js` | `/assets/placement-scenarios.js` | Saved draft management |
| `economics-dashboard.js` | `/assets/economics-dashboard.js` | Cost intelligence dashboard |
| `forecast-dashboard.js` | `/assets/forecast-dashboard.js` | Forecast visualization |
| `quality-dashboard.js` | `/assets/quality-dashboard.js` | Data quality metrics |
| `topology.js` | `/assets/topology.js` | Asset dependency graph |

**Breaking:** The UI is served by the Python API server, not a separate
web server. You must serve the UI through the API or copy the `ui/`
directory to a static file server.

#### Synthetic Data Quarantine

When `demo=synthetic` is not in the URL, synthetic data is automatically
quarantined:
- KPI values are replaced with "Not verified"
- Cost records are replaced with empty arrays
- A banner indicates "Synthetic demonstration records are quarantined"

**Breaking:** If you previously relied on synthetic data being visible
without the `demo=synthetic` parameter, you must add it to the URL.

#### Workspace Onboarding

The onboarding flow stores a workspace profile in `localStorage` under the
key `dcc-workspace-profile-v1`. This is browser-local only and does not
affect server state.

**Breaking:** Clearing browser storage will reset the onboarding profile.
The onboarding dialog will reappear on next visit.

---

### Adapters

#### Adapter Registry

The adapter registry (`src/dcc/adapters/registry.py`) provides:
- Thread-safe adapter registration and discovery
- Capability-based negotiation
- Health monitoring with consecutive failure tracking
- Rate-limit state tracking from HTTP headers

**Breaking:** Adapters must implement the `AdapterProtocol`:
- `name: str`
- `version: str`
- `health_check() -> bool`
- `supports(capability: AdapterCapability) -> bool`

#### Available Adapters

| Adapter | Capabilities | Status |
|---|---|---|
| Azure Retail Prices | `PRICE_LOOKUP`, `SKU_SEARCH`, `REGION_AVAILABILITY` | Live, read-only |
| Google Cloud Billing | `PRICE_LOOKUP`, `SKU_SEARCH` | Live, read-only, requires API key |

**Breaking:** No facility, meter, inventory, or hypervisor adapters are
implemented. The adapter registry is designed for future adapters but only
cloud pricing adapters are available.

#### Adapter Capabilities

```python
class AdapterCapability(enum.Enum):
    PRICE_LOOKUP = "price_lookup"
    SKU_SEARCH = "sku_search"
    REGION_AVAILABILITY = "region_availability"
    COST_ESTIMATION = "cost_estimation"
    USAGE_METRICS = "usage_metrics"
    TAG_MANAGEMENT = "tag_management"
    BUDGET_ALERTS = "budget_alerts"
    RESERVATION_PRICING = "reservation_pricing"
    SPOT_PRICING = "spot_pricing"
    COMMITMENT_DISCOUNTS = "commitment_discounts"
```

---

### Economics Engine

#### New Modules

| Module | Path | Description |
|---|---|---|
| `prices.py` | `src/dcc/economics/prices.py` | Effective-dated price management |
| `unit.py` | `src/dcc/economics/unit.py` | Unit economics (EAC, $/kW-year, etc.) |
| `budget.py` | `src/dcc/economics/budget.py` | Budget forecasting |
| `reconciliation.py` | `src/dcc/economics/reconciliation.py` | Estimate-to-actual reconciliation |
| `scenarios.py` | `src/dcc/economics/scenarios.py` | What-if scenario modeling |
| `allocation.py` | `src/dcc/economics/allocation.py` | Cost allocation to workloads |
| `estimates.py` | `src/dcc/economics/estimates.py` | Bottom-up cost estimation |
| `tco.py` | `src/dcc/economics/tco.py` | Total Cost of Ownership calculator |
| `tariffs.py` | `src/dcc/economics/tariffs.py` | Tariff structure modeling |

#### Price Engine

The `PriceEngine` class provides in-memory price management with:
- Versioned price records with effective date ranges
- Price status lifecycle: `draft` → `approved` → `expired` / `rejected`
- Overlapping effective date detection
- Currency normalization via FX rates
- Price comparison and variance analysis

**Breaking:** Price records are immutable in intent. Corrections create a
new record; the old record's status is set to `superseded`.

#### Tariff Calculation

The tariff engine supports:
- Time-of-use (TOU) rates
- Demand charges
- Tiered rates
- Fixed charges

All calculations use `Decimal` for financial precision.

**Breaking:** Tariff specs use `tariff.v1` schema version. Specs with
other versions will be accepted but may not validate correctly.

#### Unit Economics

Unit economics functions return `UnitEconomicsResult` with:
- `value`: Computed unit cost or `None`
- `unit`: Human-readable unit label
- `status`: `"ok"`, `"not_priced"`, or `"unknown"`
- `detail`: Explanation when status is not `"ok"`

**Breaking:** Functions return `None` for absent/zero denominators
(displayed as "Unknown") or when pricing data is missing (displayed as
"Not priced"). This replaces any previous behavior of returning 0 or
raising exceptions.

---

### Forecasting

#### New Modules

| Module | Path | Description |
|---|---|---|
| `load.py` | `src/dcc/forecasting/load.py` | Energy load forecasting |
| `capacity.py` | `src/dcc/forecasting/capacity.py` | Capacity demand forecasting |
| `failure.py` | `src/dcc/forecasting/failure.py` | Equipment failure prediction |
| `drift.py` | `src/dcc/forecasting/drift.py` | Model drift detection |
| `calibration.py` | `src/dcc/forecasting/calibration.py` | Forecast calibration |
| `backtest.py` | `src/dcc/forecasting/backtest.py` | Walk-forward validation |
| `maintenance.py` | `src/dcc/forecasting/maintenance.py` | Maintenance scheduling |
| `price.py` | `src/dcc/forecasting/price.py` | Energy price forecasting |
| `features.py` | `src/dcc/forecasting/features.py` | Time-series feature extraction |

#### Forecasting Models

**Load Forecasting:**
- Moving average
- Exponential smoothing
- Holt-Winters (double exponential smoothing)
- Linear trend

**Capacity Forecasting:**
- Linear trend
- Moving average
- Exponential smoothing

**Failure Prediction:**
- Z-score anomaly detection
- IQR anomaly detection
- EWMA-based anomaly detection
- Degradation trend analysis
- Criticality-weighted risk scoring

**Breaking:** All forecasts are advisory. The model policy is included in
every response:

```json
{
  "model_policy": {
    "trend_forecast_min_daily_points": 7,
    "anomaly_min_daily_points": 14,
    "maintenance_failure_labels_required": true,
    "note": "Forecasts and anomalies require adequate non-synthetic history; no failure-probability model is enabled by this read model."
  }
}
```

#### Drift Detection

Supported methods:
- PSI (Population Stability Index)
- KS (Kolmogorov-Smirnov)
- CUSUM (Cumulative sum control chart)
- Error rate threshold
- Mean shift
- Variance shift

**Breaking:** Drift detection requires a reference distribution of at least
30 samples. Incoming data must also have at least 30 samples.

---

### Quality & Validation

#### New Modules

| Module | Path | Description |
|---|---|---|
| `engine.py` | `src/dcc/quality/engine.py` | Data quality scoring |
| `anomaly.py` | `src/dcc/quality/anomaly.py` | Statistical anomaly detection |
| `freshness.py` | `src/dcc/quality/freshness.py` | Data freshness SLA monitoring |
| `schema.py` | `src/dcc/validation/schema.py` | Schema validation layer |
| `units.py` | `src/dcc/validation/units.py` | Unit conversion validation |
| `boundaries.py` | `src/dcc/validation/boundaries.py` | Meter boundary validation |
| `consistency.py` | `src/dcc/validation/consistency.py` | Cross-record consistency |
| `intervals.py` | `src/dcc/validation/intervals.py` | Time interval validation |

#### Quality Dimensions

The quality engine scores four dimensions:
- **Completeness** (weight 0.30): Required and optional field presence
- **Freshness** (weight 0.25): Age of newest record vs. SLA
- **Consistency** (weight 0.25): Validation rule pass rate
- **Accuracy** (weight 0.20): Match against reference values

**Breaking:** Quality scores are 0.0-1.0. Scores below 0.5 are "critical";
below 0.8 are "needs improvement".

#### Freshness SLAs

| Source | SLA (hours) |
|---|---|
| `telemetry_readings` | 1 |
| `kpi_observations` | 26 |
| `capacity_snapshots` | 26 |
| `price_observations` | 72 (varies by source kind) |
| `connectors` | 26 |
| `assets` | 168 |
| `cost_actuals` | 720 |
| `energy_allocations` | 26 |

**Breaking:** Freshness status is `ok`, `warning` (>80% of SLA),
`violation` (>SLA), or `no_data`.

#### Schema Validation

The `SchemaValidator` class validates entities against field definitions
with type, required, min/max length, min/max value, pattern, enum, and
custom validator rules.

**Breaking:** Validation errors raise `ValidationError` or
`ConstraintViolation` (subclass of `ValidationError`). Catch
`ValidationError` to handle both.

---

### Security & Tenant Isolation

#### Trust Boundaries

1. **Enterprise/control networks to site DMZ:** Outbound-only where possible
2. **Connector to ingestion:** Workload-bound identity, untrusted payload
3. **Ingestion to canonical records:** Schema validation, tenant binding,
   dedupe, bounded payloads
4. **Analytics to decision:** Advisory only, carries lineage and uncertainty
5. **Tenant to database:** RLS-scoped, least privilege

#### Non-Negotiable Boundaries

- Local starter binds only to loopback
- No remote executor, shell, desktop control, or control-system writes
- No workload scheduler or secret reveal feature
- Facility safety systems retain all emergency and actuation authority
- Human approval and two-person checks enforced in authoritative systems

**Breaking:** The first release has no authentication. Production
deployments must add authentication at the reverse proxy layer.

#### RLS Policy

Every `dcc` table has RLS enabled and forced. The `tenant_scope` policy
requires `dcc.tenant_id` to be set in the session.

**Breaking:** Direct database queries without `set_config('dcc.tenant_id', ...)`
return zero rows. This is intentional and cannot be bypassed by the
application.

---

### Provenance & Lineage

#### New Module

`src/dcc/provenance/tracker.py` provides:
- `LineageTracker`: In-memory lineage graph with hash-chained steps
- `LineageNode`: Data artifact representation
- `LineageEdge`: Directed data flow edge
- `LineageStep`: Transformation step with input/output hashes
- `ProvenanceRecord`: Complete provenance for an artifact

#### Source Types

```python
class SourceType(str, Enum):
    CONNECTOR = "connector"
    MANUAL_ENTRY = "manual_entry"
    API_IMPORT = "api_import"
    SEED_FIXTURE = "seed_fixture"
    CALCULATED = "calculated"
    EXTERNAL_SYSTEM = "external_system"
```

#### Transformation Types

```python
class TransformationType(str, Enum):
    INGESTION = "ingestion"
    VALIDATION = "validation"
    AGGREGATION = "aggregation"
    ALLOCATION = "allocation"
    NORMALIZATION = "normalization"
    CALCULATION = "calculation"
    FILTER = "filter"
    JOIN = "join"
    DERIVATION = "derivation"
```

**Breaking:** The lineage tracker is in-memory only. For persistence,
back it with the `dcc.evidence_events` table. The hash chain is
tenant-scoped and verifiable via `verify_chain()`.

---

## Migration Procedures

### Fresh Install

1. Create a PostgreSQL database:
   ```bash
   createdb dcc_production
   ```

2. Apply the schema:
   ```bash
   psql dcc_production -f database/schema.sql
   ```

3. Set environment variables:
   ```bash
   export DCC_DATABASE_URL="postgresql://user:pass@localhost:5432/dcc_production"
   export PORT=8790
   ```

4. Start the API:
   ```bash
   python -m dcc.api
   ```

5. Open the UI:
   ```
   http://127.0.0.1:8790/?tenant_id=<your-tenant-uuid>
   ```

### Upgrading from Pre-Release

If you have a pre-release version with tables in `public`:

1. **Backup your database:**
   ```bash
   pg_dump dcc_pre_release > backup.sql
   ```

2. **Create the new schema:**
   ```bash
   psql dcc_pre_release -f database/schema.sql
   ```

3. **Migrate data from `public` to `dcc`:**
   ```sql
   -- Example for tenants table
   INSERT INTO dcc.tenants (id, slug, name, status, data_region, retention_policy, created_at)
   SELECT id, slug, name, status, data_region, retention_policy, created_at
   FROM public.tenants;
   ```

4. **Apply migrations in order:**
   ```bash
   psql dcc_pre_release -f database/migrations/001_cost_intelligence.sql
   psql dcc_pre_release -f database/migrations/002_lifecycle_rollup_fix.sql
   psql dcc_pre_release -f database/migrations/003_estimate_price_link_validation.sql
   psql dcc_pre_release -f database/migrations/004_placement_comparison_snapshots.sql
   ```

5. **Verify RLS is enabled:**
   ```sql
   SELECT tablename, rowsecurity,forcerowsecurity
   FROM pg_tables
   WHERE schemaname = 'dcc';
   ```

6. **Update application configuration** to use the new `dcc` schema.

### Database Migration Order

Migrations must be applied in order:

1. `001_cost_intelligence.sql` — Creates cost books, price observations,
   estimate projects, line items, actuals, allocations, and the
   `estimate_cost_rollup` view.

2. `002_lifecycle_rollup_fix` — Corrects the `estimate_cost_rollup` view
   to use `count(DISTINCT l.id)` and handle multiple takeoff lines.

3. `003_estimate_price_link_validation` — Adds the
   `validate_estimate_price_link` trigger function and
   `estimate_price_link_check` trigger on `estimate_line_items`.

4. `004_placement_comparison_snapshots` — Creates the
   `placement_comparison_snapshots` table with immutability trigger and
   RLS.

**Breaking:** Migration 003 will fail if existing `sourced` line items
do not have valid pinned price observations. Run this query to identify
problematic rows:

```sql
SELECT eli.id, eli.estimate_id, eli.line_no, eli.pricing_status
FROM dcc.estimate_line_items eli
WHERE eli.pricing_status = 'sourced'
  AND eli.price_observation_id IS NULL;
```

### Rollback Procedures

**Migration 001 (Cost Intelligence):**
```sql
DROP TABLE IF EXISTS dcc.cost_allocations CASCADE;
DROP TABLE IF EXISTS dcc.cost_actuals CASCADE;
DROP TABLE IF EXISTS dcc.estimate_line_items CASCADE;
DROP TABLE IF EXISTS dcc.estimate_projects CASCADE;
DROP TABLE IF EXISTS dcc.price_observations CASCADE;
DROP TABLE IF EXISTS dcc.cost_books CASCADE;
```

**Migration 002 (Rollup Fix):**
```sql
-- Restore the old view definition if needed
-- (No destructive changes; the view is replaced)
```

**Migration 003 (Price Link Validation):**
```sql
DROP TRIGGER IF EXISTS estimate_price_link_check ON dcc.estimate_line_items;
DROP FUNCTION IF EXISTS dcc.validate_estimate_price_link();
```

**Migration 004 (Placement Snapshots):**
```sql
DROP TRIGGER IF EXISTS placement_snapshots_immutable ON dcc.placement_comparison_snapshots;
DROP FUNCTION IF EXISTS dcc.reject_placement_snapshot_mutation();
DROP TABLE IF EXISTS dcc.placement_comparison_snapshots CASCADE;
```

**Breaking:** Rolling back migrations may leave orphaned data. Always
backup before migrating.

---

## Breaking Changes Summary

| Area | Change | Impact |
|---|---|---|
| Schema | All tables moved to `dcc` schema | High — all queries must use `dcc.` prefix |
| RLS | Enabled and forced on all tables | High — direct queries need `set_config` |
| API | Loopback-only, no authentication | Medium — production needs reverse proxy |
| API | `tenant_id` required on all endpoints | Medium — all clients must send tenant_id |
| API | Synthetic data quarantined by default | Medium — add `?demo=synthetic` to see demo data |
| DB | Price link validation trigger | High — sourced lines need pinned prices |
| DB | Placement snapshots immutable | Medium — no update/delete on snapshots |
| DB | Cost book approval check | Medium — approved books need `approved_at` |
| DB | Synthetic provenance check | Low — synthetic prices need `provenance.synthetic` |
| DB | Recurrence months constraint | Medium — recurring costs need `recurrence_months` |
| DB | Unpriced line check | Medium — unpriced lines need `pricing_basis` |
| UI | 13 views (up from initial) | Low — new views are additive |
| UI | Onboarding stored in localStorage | Low — browser-local only |
| Config | `DCC_DATABASE_URL` required | High — no default database |
| Config | `GOOGLE_CLOUD_BILLING_API_KEY` for Google pricing | Medium — returns 503 if missing |
| Adapters | Only cloud pricing adapters live | Medium — no facility/meter adapters |
| Forecasting | All models advisory with policy | Low — advisory only, no actuation |
| Quality | Four-dimension scoring | Low — new scoring system |
| Security | No authentication in v0.1.0 | High — production must add auth proxy |
| Provenance | In-memory lineage tracker | Low — needs persistence backing |
