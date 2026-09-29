# Video Script: Data Center Commander — Product Demo

**Target length:** 4–5 minutes  
**Audience:** Data center operators, facilities engineers, IT operations leads  
**Goal:** Show the command-center UI, walk through each major view, and demonstrate the synthetic demo mode.

---

## Scene 1 — Hook (0:00–0:30)

**Visual:** Screen recording of the UI loading at `http://127.0.0.1:8795/?tenant_id=dcc00000-0000-4000-8000-000000000001&demo=synthetic`. The amber "SYNTHETIC DEMO · NOT LIVE" banner is visible.

**Narration:**
> "You're looking at Data Center Commander — an open-source, operator-centered command center for the full data center lifecycle. Every number you see is explicitly tagged as synthetic demo data. Nothing here is live telemetry. Let me walk you through what the platform actually does."

**On-screen text:** "Open source · AGPL-3.0 · Read-only decision support"

---

## Scene 2 — Command Picture (0:30–1:15)

**Visual:** The default "Command picture" view. Eight KPI cards are visible: Facility energy, IT energy, PUE, Useful compute/kWh, Carbon, Thermal margin, Capacity headroom, Open lifecycle workflows. Hover over a card to show the provenance tooltip.

**Narration:**
> "The command picture gives you eight operational KPIs at a glance — energy, efficiency, carbon, thermal margin, capacity, and open work. Every card shows its quality status, coverage percentage, and time window. If a source isn't connected, the card says 'Unknown' — the system never fabricates a number."

**Action:** Click the "Refresh" button. Show the auto-refresh dropdown (30s / 1min / 5min).

---

## Scene 3 — Energy & Carbon (1:15–2:00)

**Visual:** Navigate to the "Energy & carbon" tab. A table of versioned interval metrics appears with columns: Metric, Value, Unit, Window, Quality, Coverage, Provenance.

**Narration:**
> "The energy view breaks down every interval metric with its meter boundary, quality flag, and source lineage. You can see exactly which readings are good, estimated, or suspect — and what percentage of the expected interval is covered. This is the energy-to-compute accounting layer: facility kWh, IT kWh, PUE, carbon, and cooling — all tied to named sources."

**Action:** Point to the "Provenance" column showing source connector and version.

---

## Scene 4 — Data Science & BI (2:00–2:45)

**Visual:** Navigate to "Data science & BI". Show the analytics cards (KPI signals, mean coverage, telemetry samples, open workflows). Below: KPI trend sparklines with dashed forecast projections. The "Forecast withheld" tag is visible on one series.

**Narration:**
> "The analytics view computes decision-grade KPIs from tenant-scoped PostgreSQL. Trend sparklines show observed values as solid lines and advisory projections as dashed lines. If there isn't enough clean history, the forecast is withheld — the system tells you why rather than guessing. Data quality distribution, model readiness, and operational signals are all visible here."

**Action:** Change the analysis window from 30 days to 7 days and back. Show the "Export snapshot" button.

---

## Scene 5 — Sizing & Economics (2:45–3:30)

**Visual:** Navigate to "Sizing & economics". Show the estimate cards (Lifecycle PV, Annualized cost, $/kW-year, $/m²-year, $/rack-year, $/kWh). Below: the Azure retail price lookup form.

**Narration:**
> "The economics view connects capacity, area, racks, energy, and workloads to classified quantities and traceable prices. Each estimate shows low/base/high present value, annualized cost, and unit economics — cost per IT kW-year, per rack-year, per square meter, per kWh. The Azure catalog lookup queries Microsoft's public retail prices API in real time — read-only, bounded, and clearly labeled as list rates, not quotes."

**Action:** Type "Virtual Machines" in the service field, "eastus" in region, "Standard_D2s_v5" in SKU, and click "Fetch live retail rates". Show results table.

---

## Scene 6 — Capacity, Reliability & Operations (3:30–4:15)

**Visual:** Quick-cut tour of three tabs: "Capacity & resilience" (capacity snapshots with scenario evaluation), "Reliability" (work-order and condition records), and "Operations queue" (filterable workflow table with search and status filter).

**Narration:**
> "Capacity and resilience evaluates usable capacity with policy reserves, planned maintenance, and failure scenarios — not just nameplate ratings. Reliability links to your authoritative CMMS. The operations queue shows every lifecycle workflow — demand, diligence, design, procure, build, commission, operate, maintain, optimize, assure, refresh, decommission — with owner, stage, status, and due date."

**Action:** Type "cooling" in the workflow search box. Filter by "open" status.

---

## Scene 7 — Integrations & Evidence (4:15–4:45)

**Visual:** Navigate to "Integrations" (connector registry with status). Then "Evidence & audit" (append-only event references).

**Narration:**
> "The integrations view shows registered source connectors and their health — but a connector isn't 'live' until its read contract is verified. The evidence view is an append-only, tenant-scoped audit trail. Every decision can be traced back to the observations that produced it."

---

## Scene 8 — Close (4:45–5:00)

**Visual:** Return to the Command picture. Fade to the project README or GitHub page.

**Narration:**
> "Data Center Commander is a local decision-support prototype — read-only, vendor-neutral, and explicitly synthetic in demo mode. It doesn't replace your BMS, EPMS, CMMS, or safety systems. It gives operators one accountable view across the entire facility lifecycle. The code is open source under AGPL-3.0. Link in the description."

**On-screen text:** GitHub repo URL · "docs/LOCAL_DEVELOPMENT.md for setup"

---

## Production notes

- All UI interactions are screen recordings from the documented local synthetic walkthrough.
- The amber "SYNTHETIC DEMO · NOT LIVE" banner must remain visible in every frame.
- No live credentials, production data, or facility telemetry should appear.
- Background music: subtle, non-distracting instrumental.
- Caption all narration for accessibility.
