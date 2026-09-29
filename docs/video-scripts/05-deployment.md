# Video Script: Data Center Commander — Deployment & Setup

**Target length:** 5–6 minutes  
**Audience:** Platform engineers, DevOps, IT operations leads  
**Goal:** Walk through local development setup, synthetic demo mode, deployment shapes, and production hardening roadmap.

---

## Scene 1 — What You're Deploying (0:00–0:40)

**Visual:** Screen recording of the UI loading. Show the left sidebar with all navigation items. Point to the footer: "Local development · PostgreSQL-backed read model · No live source is implied".

**Narration:**
> "Data Center Commander is a local, PostgreSQL-backed, read-only decision support system. It's not a SaaS platform — you run it yourself, on your infrastructure, with your data. Let me show you how to get it running locally, what the demo mode does, and what the production roadmap looks like."

**On-screen text:** "Python 3.11+ · PostgreSQL 14+ · Loopback-only API"

---

## Scene 2 — Local Setup (0:40–2:00)

**Visual:** Terminal recording. Show each command as it's typed and executed.

**Narration:**
> "Setup requires Python 3.11 or later and PostgreSQL 14 or later. First, sync dependencies with uv. Then create a new database — never point the demo at production. Apply the schema. Set the database URL environment variable. Start the local server on port 8790. The API refuses non-loopback binds — it will not expose itself to the network."

**Action — terminal commands:**
```bash
cd data-center-commander
uv sync --extra postgres
createdb data_center_commander_dev
export DCC_DATABASE_URL='postgresql://127.0.0.1/data_center_commander_dev'
psql "$DCC_DATABASE_URL" -v ON_ERROR_STOP=1 -f database/schema.sql
uv run --extra postgres python scripts/run-local.py --host 127.0.0.1 --port 8790
```

**Narration (continued):**
> "Health checks are built in. `/healthz` reports process liveness. `/readyz` succeeds only when PostgreSQL, the required schema tables, and forced tenant row-level security are all available. The local service has no user authentication — it must remain loopback-only."

---

## Scene 3 — Synthetic Demo Mode (2:00–3:15)

**Visual:** Terminal recording showing the demo seed commands. Then screen recording of the UI with the amber "SYNTHETIC DEMO · NOT LIVE" banner.

**Narration:**
> "To see the platform with data, use the synthetic demo mode. Create a disposable database whose name starts with `dcc_demo_`. Apply the schema, then seed with the demo script and the explicit synthetic data flag. Open the UI with the tenant UUID and the demo parameter. Every record is visibly tagged as synthetic. The banner stays on screen at all times."

**Action — terminal commands:**
```bash
createdb dcc_demo_local
export DCC_DATABASE_URL='postgresql://127.0.0.1/dcc_demo_local'
psql "$DCC_DATABASE_URL" -v ON_ERROR_STOP=1 -f database/schema.sql
DCC_ALLOW_SYNTHETIC_DATA=YES_SYNTHETIC_dcc_demo_local scripts/db-seed-demo.sh
```

**Action — browser:**
```
http://127.0.0.1:8795/?tenant_id=dcc00000-0000-4000-8000-000000000001&demo=synthetic
```

**Narration (continued):**
> "The demo data includes 30-day synthetic history with 15-minute interval energy readings, modeled thermal and carbon values, and explicitly marked synthetic forecasts. It's idempotent — it doesn't reset or delete data. Reset only works with the explicit reset flag and only against the named demo database. The reset rejects other database names and non-loopback hosts."

---

## Scene 4 — Running Tests (3:15–3:45)

**Visual:** Terminal recording showing the test suite running.

**Narration:**
> "The project includes a comprehensive test suite covering API contracts, schema validation, adapter behavior, cost calculations, forecasting, allocation, and more. Run it with uv."

**Action — terminal command:**
```bash
uv run --extra test python -m unittest discover -s tests -v
```

---

## Scene 5 — Deployment Shapes (3:45–4:45)

**Visual:** Three deployment diagrams: (1) Local single-node, (2) Site-edge with regional aggregation, (3) Supabase managed.

**Narration:**
> "For production, there are three deployment shapes. Local single-node PostgreSQL is for engineering and demos. Site-edge collectors buffer during WAN loss — they keep ingesting even when the connection to regional services is down. Regional services aggregate approved site data. A central control view joins regions only where data residency and tenant policy permit. Multi-site failure must not disable local facility controls. A Supabase deployment is one managed Postgres, Auth, Realtime, and Storage option — not the architecture itself. The domain model uses portable PostgreSQL SQL and can be adapted to Supabase, but Supabase Auth and RLS are deployment adapters, not dependencies."

---

## Scene 6 — Production Hardening Roadmap (4:45–5:30)

**Visual:** Table or timeline showing the roadmap stages: Stage 5 (Production hardening) and Stage 6 (Certified ecosystem).

**Narration:**
> "The roadmap is explicit about what's delivered and what isn't. Stage 5 — production hardening — adds authentication and authorization, tenant isolation, a secret manager, migrations, backups and restore, observability, incident handling, and high availability. Stage 6 — certified ecosystem — adds OEM, cloud, and facility adapter conformance testing, optional enterprise analytics, and support. The current build is a local decision-support prototype. Vendor adapters, validated forecasts, production IAM, and facility control are not delivered. The roadmap is an implementation sequence, not a readiness claim."

---

## Scene 7 — Close (5:30–6:00)

**Visual:** Return to the UI. Fade to the README.

**Narration:**
> "Data Center Commander is open source under AGPL-3.0. The full setup guide is in docs/LOCAL_DEVELOPMENT.md. The architecture, lifecycle operations, integrations, and cost documentation are all in the docs folder. Start with the synthetic demo, connect your own read-only sources, and build from there."

**On-screen text:** GitHub repo URL · "docs/LOCAL_DEVELOPMENT.md"

---

## Production notes

- Terminal recordings should use a clean, readable font with syntax highlighting.
- Show actual command output — don't just show the commands.
- The amber "SYNTHETIC DEMO · NOT LIVE" banner must be visible in all UI frames.
- Caption all narration.
- Include a disclaimer slide: "Do not point the demo at a production database."
