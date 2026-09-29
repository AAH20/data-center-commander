# Video Script: Data Center Commander — Architecture Deep Dive

**Target length:** 6–7 minutes  
**Audience:** Solutions architects, platform engineers, technical evaluators  
**Goal:** Explain the system's trust boundaries, bounded contexts, data flow, and deployment shapes.

---

## Scene 1 — Why Architecture Matters (0:00–0:45)

**Visual:** Animated diagram showing the high-level flow: Sources → Edge → Core → UI → Decisions. Use the mermaid diagram from `docs/ARCHITECTURE.md` as reference.

**Narration:**
> "Data center operations sit at the intersection of IT and facilities — two domains that historically don't share a data model. Data Center Commander is designed as a coordination layer that joins both worlds without replacing either. Let me walk through the architecture: what it owns, what it doesn't, and how data flows from a utility meter to an operator decision."

**On-screen text:** "Coordination layer · Not a BMS · Not a CMMS · Not a scheduler"

---

## Scene 2 — Trust Boundaries (0:45–2:00)

**Visual:** Animated diagram showing five trust boundaries as concentric zones. Label each: (1) Enterprise/control networks to site DMZ, (2) Connector to ingestion, (3) Ingestion to canonical records, (4) Analytics to decision, (5) Tenant to database.

**Narration:**
> "The architecture defines five trust boundaries. First, enterprise and control networks connect to a site DMZ through outbound-only paths where possible — no general-purpose agent sits on safety or control networks. Second, each connector has workload-bound identity, operator-provisioned endpoints, narrow read scopes, and rate budgets. Third, ingestion validates schema, tenant binding, identity, dedupe, timestamps, units, and quality before anything enters read models. Fourth, analytics are advisory — they carry lineage and uncertainty but cannot create infrastructure commands. Fifth, every tenant row is RLS-scoped in the database."

**Action:** Highlight each boundary as it's described. Show the "no actuation" boundary as a hard wall.

---

## Scene 3 — Bounded Contexts (2:00–3:30)

**Visual:** Table or grid showing the nine bounded contexts: Organization & estate, Telemetry & provenance, Energy & sustainability, Compute & service, Capacity & resilience, Maintenance & reliability, Operations & governance, Analytics & reporting. Each with "Owns" and "Does not own" columns.

**Narration:**
> "The system is decomposed into nine bounded contexts. Organization and estate owns tenants, sites, facilities, rooms, racks, and the asset graph — but it doesn't own physical truth without a source observation. Telemetry and provenance owns connector contracts, readings, quality, and calibration — but not source device control. Energy and sustainability owns boundaries, interval accounting, PUE/WUE, and allocation — but not utility billing truth or carbon certification. This separation prevents the common failure mode where one system tries to be authoritative for everything."

**Action:** Zoom into the Energy & sustainability context. Show the meter boundary hierarchy: Utility → Facility → IT → Cooling → Other.

---

## Scene 4 — Data & Event Flow (3:30–4:45)

**Visual:** Animated pipeline: `source envelope → validated raw observation → normalized measurement → asset/topology link → quality decision → derived metric → operator review → work record → observed outcome → evidence closeout`.

**Narration:**
> "Every data point follows the same pipeline. A source envelope arrives from a connector. It's validated, normalized, linked to an asset in the topology, quality-checked, and only then becomes a derived metric. Raw facts are immutable or versioned — corrections append a superseding record. Event consumers are idempotent by tenant, source ID, and source event ID. They tolerate late, duplicated, out-of-order, and replayed messages. This is how you build an audit trail that survives real-world data chaos."

**Action:** Show a concrete example: a meter reading arrives, gets validated, linked to an asset, quality-flagged as "good", and appears in the KPI rollup.

---

## Scene 5 — Scaling Path (4:45–5:45)

**Visual:** Diagram showing the scaling progression: single PostgreSQL → monthly partitioning → TimescaleDB or columnar lake. Show the separation: hot raw telemetry, compacted rollups, immutable evidence.

**Narration:**
> "The platform starts with portable PostgreSQL and scales deliberately. Reference data stays relational and tenant-partitioned. High-cardinality access is indexed by tenant, asset, metric, and timestamp. When measured row volume merits it, you add monthly partitioning, then adopt TimescaleDB or a columnar lake behind the same measurement and provenance contract. Hot raw telemetry, compacted hourly and daily rollups, and immutable evidence are separated. Ingestion uses bounded batches, per-source back-pressure, idempotency keys, cursor checkpoints, and circuit breakers."

---

## Scene 6 — Deployment Shapes (5:45–6:30)

**Visual:** Three deployment diagrams: (1) Local single-node PostgreSQL for engineering, (2) Site-edge collectors with regional aggregation, (3) Supabase managed Postgres/Auth/Realtime/Storage.

**Narration:**
> "There are three deployment shapes. Local single-node PostgreSQL is for engineering and synthetic demonstrations — that's what the demo uses. Site-edge collectors buffer during WAN loss; regional services aggregate approved site data; a central control view joins regions only where residency and tenant policy permit. Multi-site failure must not disable local facility controls. A Supabase deployment is one managed option — not the architecture itself. The domain model doesn't depend on Supabase Auth or RLS; those are deployment adapters."

---

## Scene 7 — Close (6:30–7:00)

**Visual:** Return to the high-level architecture diagram. Fade to the project's `docs/ARCHITECTURE.md` on GitHub.

**Narration:**
> "The full architecture document is in the repo under docs/ARCHITECTURE.md. It includes the complete trust boundary specifications, bounded context definitions, scaling benchmarks, and deployment runbooks. Data Center Commander is open source — fork it, adapt it, and extend it for your environment."

---

## Production notes

- Use animated diagrams built from the mermaid source in `docs/ARCHITECTURE.md`.
- Keep diagrams clean — no more than 7 elements per view.
- Use color coding consistently: teal for trusted core, amber for boundaries, red for prohibited paths.
- Caption all narration.
