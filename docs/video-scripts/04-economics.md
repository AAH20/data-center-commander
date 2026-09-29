# Video Script: Data Center Commander — Economics & Unit Economics

**Target length:** 5–6 minutes  
**Audience:** Data center operators, finance leads, capacity planners, CFOs  
**Goal:** Show how the platform connects sizing, price intelligence, lifecycle estimating, and unit economics to produce decision-grade cost views.

---

## Scene 1 — The Cost Visibility Problem (0:00–0:40)

**Visual:** Screen recording of the "Sizing & economics" view. Show the estimate cards: Lifecycle PV, Annualized cost, $/kW-year, $/m²-year, $/rack-year, $/kWh.

**Narration:**
> "Data center costs are notoriously hard to see. Capital and operational expenses live in different systems, in different currencies, with different accounting treatments. Data Center Commander makes the design-to-operations cost chain explicit — from quantity takeoff to lifecycle cash flow to unit economics. Let me show you how."

**On-screen text:** "Not a substitute for engineering estimates · Not a financial recommendation"

---

## Scene 2 — Sizing & Quantity Takeoff (0:40–1:40)

**Visual:** Animated flow: Demand envelope → Capacity sizing (MW/racks/area/redundancy) → Classified quantities (WBS/UniFormat/MasterFormat/IFC GUID) → Versioned estimate.

**Narration:**
> "Sizing starts with an approved demand envelope: contracted and forecast IT load, coincident peak, utilization growth, rack power density, compute and storage, latency and sovereignty requirements, and redundancy topology. From there, quantities are classified using standard formats — WBS, UniFormat, MasterFormat, or IFC GUIDs from BIM models. Each estimate is versioned with its assumptions and denominators. The system never converts gross floor area to IT capacity with an implicit constant."

**Action:** Show the estimate line items table with quantity, unit, waste factor, low/base/high rate, cost behavior, useful life, recurrence, escalation, and phase.

---

## Scene 3 — Price Collection & Source Quality (1:40–2:50)

**Visual:** Show the "Price book · source and freshness" table. Highlight columns: SKU/model, unit, currency, geography, delivery basis, effective dates, source digest, confidence, review state.

**Narration:**
> "Prices are append-only observations — corrections create a new observation, they don't overwrite history. Each price captures the SKU, unit, currency, geography, delivery basis, taxes and exclusions, quote or contract reference, source digest, observed time, effective dates, FX basis, normalization factor, confidence, and review state. The system rejects expired, mismatched, or ambiguous rates. It never silently falls back to another region or currency. Low, base, and high are documented estimate bounds — not statistical confidence intervals."

**Action:** Show a sample price row. Point to the "review state" column showing "approved" vs "pending".

---

## Scene 4 — Lifecycle Cost & Accounting (2:50–3:50)

**Visual:** Animated diagram: Versioned estimate → Lifecycle cash flows (recurrence, escalation, discount) → Present value calculation → Unit economics normalization.

**Narration:**
> "The rollup calculates dated low, base, and high present values from one-off or recurring cash-flow lines. Costs are classified by lifecycle phase: land and site diligence, design, civils, utility interconnect, electrical, mechanical, IT, network, software, labor, commissioning, energy, water, carbon, maintenance, tax, financing, refresh, residual value, and decommissioning. Contingency, schedule escalation, FX, taxes, discount rate, and financing are all explicit. The system doesn't invent salvage value, tax treatment, or utility demand charges."

**Action:** Show the actual cost ledger with period reconciliation. Point to the "unpriced" count.

---

## Scene 5 — Unit Economics (3:50–4:50)

**Visual:** Show the unit economics cards: $/IT kW-year, $/rack-year, $/m²-year, $/kWh, $/work unit. Show the formula: EAC = PV × r / (1 − (1+r)^(−n)).

**Narration:**
> "Unit economics normalize annualized cost by measured denominators — but only when their scopes match. Cost per IT kW-year, per rack-year, per square meter, per kWh. Energy OPEX is shown at both IT and facility boundaries. Allocated lifecycle cost is divided by verified useful workload units — requests, jobs, tokens, transactions — with SLO and service tier preserved. The equivalent annual cost formula is shown on screen: PV times r over 1 minus (1+r) to the negative n. When a denominator is absent or zero, the card says 'Unknown' — never zero."

**Action:** Hover over a unit economics card to show the denominator and calculation version.

---

## Scene 6 — Live Price Lookup (4:50–5:30)

**Visual:** Show the Azure retail price lookup form. Fill in: Service = "Virtual Machines", Region = "eastus", SKU = "Standard_D2s_v5", Currency = "USD". Click "Fetch live retail rates". Show results.

**Narration:**
> "The platform includes a live, read-only adapter for Microsoft's public Azure Retail Prices catalog. It queries the fixed endpoint, retrieves dated list rates by service, region, SKU, and currency, and displays them with provenance. These are list rates — not negotiated prices, not quotes, not total cost of ownership. The Google Cloud Billing Catalog is also supported. Both adapters are bounded, read-only, and clearly labeled."

---

## Scene 7 — Close (5:30–6:00)

**Visual:** Return to the economics view. Fade to `docs/COST_ESTIMATING_AND_UNIT_ECONOMICS.md`.

**Narration:**
> "Every cost number in Data Center Commander is traceable to a named source observation with a versioned calculation definition. The system doesn't replace your quantity surveyor, vendor tender, or finance approval — it makes the entire chain explicit and auditable. Full documentation is in the cost estimating guide."

---

## Production notes

- Use screen recordings from the synthetic demo for UI scenes.
- Animated diagrams for the cost flow and unit economics formula.
- The "Not priced" and "Unknown" states are important — show them clearly.
- Caption all narration.
