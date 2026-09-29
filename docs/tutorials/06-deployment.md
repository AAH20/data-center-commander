# Tutorial 6: Deployment & Operations

## Overview

Data Center Commander supports multiple deployment shapes from local
single-node development to multi-site production. This tutorial covers the
local development workflow, production deployment options, scaling path,
and operational runbooks.

## Local Development

### Quick Start

```bash
# 1. Create database
createdb data_center_commander_dev

# 2. Apply schema
export DCC_DATABASE_URL='postgresql://127.0.0.1/data_center_commander_dev'
psql "$DCC_DATABASE_URL" -v ON_ERROR_STOP=1 -f database/schema.sql

# 3. Start API
uv run --extra postgres python scripts/run-local.py --host 127.0.0.1 --port 8790

# 4. Open UI
open http://127.0.0.1:8790/
```

### Database URL

The `DCC_DATABASE_URL` environment variable configures the PostgreSQL
connection. The API uses `psycopg-pool` with:

- `min_size=1`, `max_size=8`
- `timeout=3` seconds
- `prepare_threshold=None` (no prepared statements)

If the database is not configured, the API returns
`{"error": "database_not_configured"}` with status 503.

### Health Checks

| Endpoint | Success criteria |
|---|---|
| `GET /healthz` | Process is running (always 200) |
| `GET /readyz` | PostgreSQL reachable, schema tables exist, forced RLS enabled |

The `/readyz` response:

```json
{
  "service": "data-center-commander",
  "ready": true,
  "checks": {
    "database": "ok",
    "schema": "ok",
    "tenant_rls": "ok"
  },
  "execution_permitted": false
}
```

### Running Tests

```bash
uv run --extra test python -m unittest discover -s tests -v
```

Test coverage includes:

- API route contracts
- Schema validation
- Adapter bounds and safety
- Quality engine scoring
- Economics calculations
- Provenance tracking
- Tenant isolation

## Deployment Shapes

### Shape 1: Local Single-Node (Development)

```
┌─────────────────────────────────┐
│  Local Machine                  │
│  ┌──────────┐  ┌─────────────┐ │
│  │ API      │  │ PostgreSQL  │ │
│  │ :8790    │  │ :5432       │ │
│  └──────────┘  └─────────────┘ │
│  ┌──────────┐                  │
│  │ UI       │                  │
│  │ :8795    │                  │
│  └──────────┘                  │
└─────────────────────────────────┘
```

- Loopback-only binding
- No authentication
- Synthetic demo data for walkthroughs
- Not production-ready

### Shape 2: Site-Edge Collector

```
┌──────────────┐     WAN      ┌──────────────┐
│ Site         │  ─────────►  │ Regional     │
│ ┌──────────┐ │  (lossy)     │ ┌──────────┐ │
│ │ Collector│ │              │ │ Service  │ │
│ │ (local   │ │              │ │ (read    │ │
│ │  spool)  │ │              │ │  model)  │ │
│ └──────────┘ │              │ └──────────┘ │
│ ┌──────────┐ │              └──────────────┘
│ │ BMS/EPMS │ │
│ └──────────┘ │
└──────────────┘
```

- Buffers during WAN loss
- Store-and-forward telemetry
- Local read model remains available during outage
- Multi-site failure must not disable local facility controls

### Shape 3: Regional Aggregation

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Site A   │  │ Site B   │  │ Site C   │
│ Collector  │  │ Collector │  │ Collector │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │              │              │
     └──────────────┼──────────────┘
                    │
            ┌───────┴───────┐
            │ Regional      │
            │ Service       │
            │ (read model)  │
            └───────────────┘
```

- Aggregates approved site data
- Central control view joins regions only where residency and tenant policy
  permit
- Supabase deployment is one managed Postgres/Auth/Realtime/Storage option

### Shape 4: Supabase Managed

```
┌─────────────────────────────────┐
│ Supabase                        │
│ ┌──────────┐  ┌───────────────┐ │
│ │ Auth     │  │ PostgreSQL    │ │
│ │ (OIDC)   │  │ (RLS enforced)│ │
│ └──────────┘  └───────────────┘ │
│ ┌──────────┐  ┌───────────────┐ │
│ │ Realtime │  │ Storage       │ │
│ └──────────┘  └───────────────┘ │
└─────────────────────────────────┘
```

- Supabase Auth/RLS is a deployment adapter, not a dependency of the domain
  model
- Must separately prove Auth claims, RLS, grants, and service-role isolation
- RLS must be verified on partitions, views, functions, and service-role
  routes

## Scaling Path

### Data Volume Triggers

Start with PostgreSQL and monthly partitioning when measured row volume
merits it. Adopt TimescaleDB or a columnar lake only behind the same
measurement and provenance contract.

### Indexing Strategy

- Keep reference data relational and tenant-partitioned
- Index high-cardinality access by `(tenant_id, asset_id, metric_id, observed_at)`
- Tenant-first indexes for approved-rate lookup, estimate rollups,
  accounting period, and workload/time

### Separation of Concerns

- **Hot raw telemetry** — recent readings, fast access
- **Compacted hourly/daily rollups** — operational/audit horizons
- **Immutable evidence** — digests and decision records per legal retention

Do not store full payload copies in every dashboard read model.

### Ingestion Pipeline

- Bounded ingestion batches
- Per-source back-pressure
- DLQ/quarantine for unmatched rows
- Idempotency keys
- Cursor checkpoints
- Exponential retry with jitter
- Circuit breakers
- Surface lag and dropped/duplicate counts

### Caching

Cache only versioned derived read models. Invalidate by:

- Source watermark
- Formula version
- Asset-graph version
- Tenant

## Migration Path

For existing databases created before the cost intelligence module:

```bash
# Apply in order, once each
psql "$DCC_DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/001_cost_intelligence.sql
psql "$DCC_DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/002_lifecycle_rollup_fix.sql
psql "$DCC_DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/003_estimate_price_link_validation.sql
psql "$DCC_DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/004_placement_comparison_snapshots.sql
```

New databases receive the tables and corrected rollup through
`database/schema.sql` plus migration 004.

## Backup and Recovery

- Verify backups and restore procedures
- Define RTO/RPO per tenant
- Test region-failure exercises
- Practice incident/restore procedures
- Document recovery runbooks

## Observability

- Surface lag and dropped/duplicate counts per source
- Monitor freshness SLA violations
- Track connector health (latency, consecutive failures, last success)
- Alert on quality score degradation
- Log every grant, approval, policy version, and revocation

## Operational Runbooks

### Shift Handover

1. Confirm identity, role, site, current restrictions, emergency contacts
2. Review unresolved incidents, active work permits, planned maintenance,
   facility alarms, load/thermal margins, data-source freshness, changes
3. Distinguish actionable alarms from stale, suppressed, test, and unknown
   points
4. Assign a named receiving owner and due time
5. Capture handover summary and acknowledgements

### Alarm to Incident

1. Ingest source event, preserve original ID/time/severity
2. Correlate topology and dependent workloads with confidence
3. Route safety/life-safety alarms to existing emergency procedure
4. Open incident, assign incident commander/technical leads
5. Verify recovery from independent telemetry/source-of-truth evidence
6. Close with timeline, root-cause confidence, follow-up work, lessons

### Planned Maintenance

1. Select asset and approved procedure version
2. Evaluate capacity/redundancy under normal, work-in-progress, and one
   additional failure scenarios
3. Link CMMS work order and safety permit
4. Confirm change window, impacted services, notifications, abort conditions
5. Record source-system completion, measured postconditions, exceptions

## Next Steps

- [Tutorial 5: Security & Governance](05-security.md) — production readiness gate
- [Tutorial 8: Capacity & Resilience](08-capacity.md) — capacity scenarios
