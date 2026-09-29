# Tutorial 1: Getting Started with Data Center Commander

## Overview

This tutorial walks you through installing Data Center Commander, setting up a
local PostgreSQL database, running the synthetic demo, and understanding the
command-center UI. By the end you will have a working local instance and know
how to navigate every major section.

## Prerequisites

- **Python 3.11+** — the project uses `uv` for dependency management
- **PostgreSQL 14+** — local instance or Docker container
- **uv** — install via `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Step 1: Clone and Sync

```bash
git clone https://github.com/AAH20/data-center-commander.git
cd data-center-commander
uv sync --extra postgres
```

This creates a virtual environment and installs all dependencies including the
PostgreSQL extras (`psycopg`, `psycopg-pool`).

## Step 2: Create a Development Database

```bash
createdb data_center_commander_dev
export DCC_DATABASE_URL='postgresql://127.0.0.1/data_center_commander_dev'
psql "$DCC_DATABASE_URL" -v ON_ERROR_STOP=1 -f database/schema.sql
```

The schema script creates the `dcc` namespace, all tables, RLS policies, and
the `estimate_cost_rollup` view. For existing databases created before the cost
intelligence module, apply migrations 001 through 004 in order.

## Step 3: Start the Local API

```bash
uv run --extra postgres python scripts/run-local.py --host 127.0.0.1 --port 8790
```

The API binds to loopback only. It refuses non-loopback binds with a
`ValueError`. Health endpoints:

- `GET /healthz` — process liveness (always 200 when the process is up)
- `GET /readyz` — database + schema + RLS readiness (200 only when PostgreSQL
  is reachable, required tables exist, and forced tenant RLS is enabled)

## Step 4: Load Synthetic Demo Data

The synthetic demo is **opt-in** and **visibly tagged**. It is never loaded by
the normal start path.

```bash
# Use a disposable database whose name starts with dcc_demo_
createdb dcc_demo_local
export DCC_DATABASE_URL='postgresql://127.0.0.1/dcc_demo_local'
psql "$DCC_DATABASE_URL" -v ON_ERROR_STOP=1 -f database/schema.sql

# Seed with the guard environment variable
export DCC_ALLOW_SYNTHETIC_DATA=YES_SYNTHETIC_dcc_demo_local
scripts/db-seed-demo.sh

# Add 30-day analytics history (idempotent, additive only)
psql "$DCC_DATABASE_URL" -v ON_ERROR_STOP=1 -f database/demo_analytics_expansion.sql
```

The seed script refuses to run unless `DCC_ALLOW_SYNTHETIC_DATA` matches the
exact database name. The reset script (`scripts/db-reset-demo.sh`) similarly
requires `DCC_ALLOW_DEMO_RESET=RESET_dcc_demo_local` and rejects non-loopback
hosts.

## Step 5: Open the Command Center

Navigate to:

```
http://127.0.0.1:8795/?tenant_id=dcc00000-0000-4000-8000-000000000001&demo=synthetic
```

The `demo=synthetic` query parameter is required to see synthetic data. Without
it, synthetic KPIs and cost rows are quarantined from the operational view.
The UI displays a persistent **SYNTHETIC DEMO · NOT LIVE** banner.

## Step 6: Navigate the UI Sections

The left rail contains these modules:

| Section | What it shows |
|---|---|
| **Command picture** | Top-level facility KPIs, open workflow count, telemetry freshness |
| **Energy & carbon** | Versioned interval metrics with boundary, coverage, uncertainty, provenance |
| **Data science & BI** | KPI trends, short-horizon forecasts, quality distribution, model readiness |
| **Sizing & economics** | Estimate rollups, unit economics cards, Azure/Google price lookups |
| **Capacity & resilience** | Usable/reserved/free capacity by dimension and scenario |
| **Estate & lifecycle** | Sites, facilities, assets, dependency graph (topology) |
| **Reliability** | Work-order and condition records |
| **Operations queue** | Lifecycle workflows with search, filter, CSV export |
| **Integrations** | Connector registry and source health |
| **Evidence & audit** | Append-only evidence event references |

## Step 7: Understand the Read-Only Boundary

Data Center Commander is **decision support only**. It does not actuate:

- Electrical breakers or switchgear
- BMS/EPMS setpoints
- Fire or life-safety systems
- Workload scheduling or VM lifecycle
- Any facility control path

The API returns `"execution_permitted": false` on every response. The UI
displays "Read-only decision support" in the footer.

## Step 8: Run Tests

```bash
uv run --extra test python -m unittest discover -s tests -v
```

Tests cover API routes, schema contracts, adapter bounds, quality engine,
economics calculations, and provenance tracking.

## Next Steps

- [Tutorial 2: Adapters & Integrations](02-adapters.md) — connect real price sources
- [Tutorial 7: Data Quality & Provenance](07-data-quality.md) — understand quality gates
- [Tutorial 10: Evidence & Audit](10-evidence-audit.md) — trace every number to its source
