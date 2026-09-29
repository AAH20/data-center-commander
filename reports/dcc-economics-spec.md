# DCC Cost Intelligence Specification

**Source:** `docs/COST_ESTIMATING_AND_UNIT_ECONOMICS.md`, `docs/DATA_MODEL_AND_KPIS.md`, `docs/INTEGRATIONS.md`, `docs/ARCHITECTURE.md`, `src/dcc/api.py`, `src/dcc/azure_prices.py`, `src/dcc/google_prices.py`, `ui/placement-comparison.js`, `ui/index.html`

**Scope:** All cost models, data sources, calculation methods, and unit economics defined in the Data Center Commander design.

---

## 1. Cost Model Families

### 1.1 Lifecycle Estimate Model (Design-to-Operations Cost Chain)

The core cost model spans the full project lifecycle from demand through deconstruction.

**Flow:**
```
Demand envelope → Capacity sizing → Classified quantities → Immutable price observations
→ Versioned estimate (low/base/high) → Lifecycle cash flows → Unit economics → Decision
```

**Key entities:**

| Entity | Table | Purpose |
|---|---|---|
| Estimate project | `estimate_projects` | Versions project assumptions, denominators, currency, geography, horizon, discount rate, contingency |
| Estimate line item | `estimate_line_items` | Quantity, normalized unit, waste factor, low/base/high rate, cost behavior, useful life, recurrence, escalation, phase, classification/asset/IFC links |
| Price observation | `price_observations` | Append-only price records with SKU, unit, currency, geography, delivery basis, taxes, source digest, FX basis, confidence, review state |
| Cost rollup | `estimate_cost_rollup` | Dated low/base/high present values from one-off or recurring cash-flow lines |
| Cost actuals | `cost_actuals` | Periodized ERP/AP/utility/CMMS actuals with source system, account code, invoice digest, accrual state |
| Cost allocations | `cost_allocations` | Shared cost assignment to workloads with named method, interval, fraction, formula version, evidence |

**Cost classification dimensions:**
- **Lifecycle phase:** land/site diligence, design, civils, utility/interconnect, electrical, mechanical, IT, network, software/licenses, labor, commissioning, energy/demand charges, water, carbon, maintenance/spares, tax, financing, refresh/replacement, residual value, decommissioning
- **Accounting type:** capital/expense, cash/accrual (local policy decides capitalization and depreciation)
- **Cost behavior:** one-off vs. recurring
- **Estimate bound:** low / base / high (documented bounds, not statistical confidence intervals)

**Explicit exclusions (not invented by the rollup):**
- Salvage value
- Tax treatment
- Utility demand charges
- Probability distributions

### 1.2 Placement TCO Comparison Model (On-Prem vs. Cloud)

Browser-local, user-entered comparison of on-premises/colocation vs. cloud subscription costs.

**Cost categories:**

| Side | One-time | Recurring monthly | Terminal |
|---|---|---|---|
| On-prem | Server/storage/network acquisition, site fit-out, migration/commissioning | Power/cooling/space, software licenses, maintenance/warranty/spares, operations labor, connectivity, backup/DR/security | Hardware refresh (at entered month), decommission/exit cost, residual value (credit) |
| Cloud | Migration/refactoring/dual-run | Compute subscription, storage/snapshots, network egress/inter-region, managed services, software/marketplace, support plan, cloud ops labor, DR replicas/security, unused commitment exposure | Data extraction/termination cost, recoverable credits/residual |

**Calculation method:**
- One-time costs at month 0
- Monthly recurring costs at month end
- Refresh at entered month (on-prem only)
- Exit/residual at horizon
- Nominal lifecycle total = undiscounted sum
- Discounted NPV with annual discount rate compounded monthly: `factor = (1 + r)^(month/12)`
- Average monthly equivalent = NPV / horizon
- Cost per delivered unit = NPV / (horizon × monthly volume)

**Explicit exclusions:** Taxes/VAT, inflation/escalation, FX, financing, carbon valuation, downtime/service credits, staffing ramp, utilization changes, architecture redesign — unless captured in entered amounts.

### 1.3 Cloud Catalog Estimate Model (Azure / Google Cloud)

Public retail price lookup with user-entered quantity for monthly/annualized list cost.

**Azure adapter:**
- Endpoint: `https://prices.azure.com/api/retail/prices` (API version `2023-01-01-preview`)
- Filter: `serviceName`, `armRegionName`, `armSkuName`, `priceType eq 'Consumption'`, `currencyCode`
- Calculation: `monthly_list_cost = retailPrice × quantity_per_month`; `annualized = monthly × 12`
- Bounded: 1 page, max 100 rows, 1 MB response limit, no redirect following
- Not persisted; not a quote or bill

**Google Cloud adapter:**
- Endpoint: `https://cloudbilling.googleapis.com/v1` (server-side API key)
- Two-step: service lookup → SKU list with tiered rates
- Only single zero-threshold tier rates are estimate-eligible
- Bounded: first SKU page (up to 1000), max 100 result rows, 2 MB response limit
- Not persisted; not a quote or bill

### 1.4 Unit Economics Normalization Model

Converts lifecycle present value into comparable unit costs.

**Equivalent Annual Cost (EAC):**
```
EAC = PV / n                          when r = 0
EAC = PV × r / (1 - (1+r)^(-n))      when r > 0
```
Where `PV` = present value, `n` = horizon in years, `r` = annual discount rate.

**Normalization denominators (scope-matched only):**

| Metric | Denominator | Boundary |
|---|---|---|
| USD / IT kW-year | `it_capacity_kw` | IT critical load |
| USD / rack-year | `rack_count` | Rack count |
| USD / m²-year | `facility_area_m2` | Gross or IT floor area |
| USD / kWh | `annual_it_energy_kwh` | Metered IT energy |
| USD / kWh (facility) | Total facility kWh | Whole-facility energy |
| USD / work unit | `annual_useful_work` | Verified useful workload (requests, jobs, tokens, transactions) |
| USD / service-hour | Available service hours | Only with approved reliability model |
| Cost of unavailability | Business impact model | Only with approved reliability/business-impact model |

**UI display rules:**
- "Not priced" for absent prices
- "Unknown" for absent or zero denominators
- First estimate's normalized cards shown
- Each estimate shows low/base/high PV, line counts, unpriced count, synthetic provenance

### 1.5 Energy Cost Model

Interval energy cost from metered consumption and tariff.

**Formula:** `interval_cost = interval_kWh × effective_tariff + demand_charge + tax_component`

- Records tariff version and currency conversion time
- Requires matching site, timezone-aligned interval, compatible meter boundary, and quality coverage
- PUE = `facility_energy / IT_energy` (only with aligned boundaries and quality coverage)

### 1.6 Carbon Cost Model

**Formula:** `carbon = interval_energy × time/location/method-specific_emission_factor`

- Preserves factor source, market/location basis, scope, uncertainty, and revision

---

## 2. Data Sources

### 2.1 Price Observation Sources

| Source Family | Examples | Characteristics |
|---|---|---|
| Authorized vendor/partner APIs | Azure Retail Prices, Google Cloud Billing Catalog | Dated list rates; no negotiated discounts |
| Dated vendor quotations | Quote documents, contracts | Customer-specific; may include discounts |
| Published utility tariffs | Tariff schedules, utility bills | Geography-specific; regulatory |
| Approved public/industry benchmarks | Industry studies | Planning-grade; not quotes |
| Labor and construction schedules | Internal labor rates | Internal cost basis |
| Controlled manual entry | Operator-entered prices | Requires review and approval workflow |

**Price observation fields:**
- SKU/model, unit, currency, country/site geography
- Delivery basis: ex-works / FOB / CIF / delivered / installed / metered
- Taxes/exclusions, quote/contract reference
- Source digest, observed time, effective dates
- FX basis date, normalization factor
- Confidence, review state, provenance

**Separate cost components (when materially different):**
- Rate-card, discount, freight, duty, installation, commissioning, spares, warranty

### 2.2 Actual Cost Sources

| Source | Content |
|---|---|
| ERP/AP systems | Periodized actuals with account codes, invoice digests |
| Utility bills | Energy/demand charges, water |
| CMMS | Maintenance/spares actuals |

**Actuals fields:** accounting period, cost type, currency, amount, source system, account code, invoice digest, accrual state, facility/asset links, estimate-line links.

### 2.3 Integration Adapters

| Adapter | Status | Capability |
|---|---|---|
| Azure Retail Prices | Live, read-only | Bounded catalog lookup by service/region/SKU/currency |
| Google Cloud Billing Catalog | Live, read-only | Bounded SKU and tiered-rate lookup |
| Facility EPMS/BMS | Contract/design only | Not implemented |
| UPS/PDU/rack | Contract/design only | Not implemented |
| BACnet/Modbus/OPC UA | Unsupported in starter | — |
| Utility/tariff/carbon | Source-specific adapter required | — |
| CMMS/ITSM/EAM | Contract/design only | — |
| Asset/topology (NetBox/DCIM) | Contract/design only | — |
| Virtualization (VMware/KVM) | New implementation required | — |
| Kubernetes/cloud | Source-specific adapter required | — |
| Workloads/observability | Source-specific mapping required | — |

**Adapter contract requirements:**
- Manifest: adapter_id, version, vendor/product/API versions, protocols, capabilities, scopes, endpoint allowlist, credential reference, rate/size/time limits
- Probe: endpoint identity, TLS, version, scopes, clock, minimal read
- Sync: cursor/checkpoint, idempotency key, bounded page/batch, source time, retry/backoff, back-pressure, late/replay semantics, DLQ/quarantine
- Map: external identity → canonical asset/meter/service + confidence
- Health: auth/schema/scope errors, last success, lag, freshness, coverage, duplicate/replay, clock skew, rate limit, version drift

### 2.4 IFC/BIM Geometry Source

- Provides geometry and element identity (IFC GlobalId)
- One source among several; engineering schedules, asset registers, quotes, and site surveys remain separate
- Deduplication required: never count the same item from both IFC takeoff and equipment schedule

---

## 3. Calculation Methods

### 3.1 Estimate Rollup (Present Value)

For each line item, calculate dated low/base/high present values:

- **One-off costs:** Discounted from occurrence date to valuation date
- **Recurring costs:** Annuity-style discounting over the recurrence period
- **Escalation:** Applied per recurrence cycle
- **Waste factor:** Applied to quantity before rate multiplication
- **Contingency:** Explicit percentage on top of subtotal
- **Discount rate:** Annual rate applied to each cash flow line

The rollup does NOT invent: salvage value, tax treatment, utility demand charges, or probability distributions.

### 3.2 Equivalent Annual Cost (EAC)

```
EAC = PV / n                          when discount rate r = 0
EAC = PV × r / (1 - (1+r)^(-n))      when r > 0
```

Implemented in UI as:
```javascript
const annuity = rate ? rate / (1 - Math.pow(1 + rate, -years)) : 1 / years;
const annual = pv * annuity;
```

### 3.3 Unit Cost Normalization

```
unit_cost = annual_cost / denominator
```

Only computed when denominator scope matches the cost scope. Returns `null` (displayed as "Unknown") when denominator is zero or absent.

### 3.4 Placement TCO NPV

```javascript
for (let month = 1; month <= horizon; month++) {
    const factor = (1 + rate) ** (month / 12);
    npv += monthly / factor;
    if (refreshAt === month) npv += refresh / factor;
}
const terminalFactor = (1 + rate) ** (horizon / 12);
npv += (exit - residual) / terminalFactor;
```

### 3.5 Cloud Catalog Monthly/Annualized

```
monthly_list_cost = retailPrice × quantity_per_month
annualized_list_cost = monthly × 12
```

### 3.6 Energy Cost

```
interval_cost = interval_kWh × effective_tariff + demand_charge + tax_component
```

### 3.7 PUE

```
PUE = facility_energy / IT_energy
```

Only computed when: matching site, timezone-aligned interval, compatible meter boundary, required quality coverage. Otherwise returns unavailable with reason codes.

### 3.8 Compute Efficiency

```
useful_compute_per_kwh = verified_useful_workload_units / attributable_kWh
```

GPU utilization percent is NOT useful work. State allocation tier and confidence interval.

### 3.9 Cost Allocation

Shared costs assigned to workloads with:
- Named allocation method
- Interval
- Allocation fraction
- Formula version
- Evidence reference

Reconciliation: allocated totals must reconcile to ledger totals; residual/unallocated amount stays visible.

---

## 4. Data Quality and Governance

### 4.1 Price Selection Rules

Select a rate by: item/model, normalized unit, geography, price basis, effective date, currency, approval status.

**Reject:** expired, mismatched, or ambiguous rates. Do NOT silently fall back to another region or currency.

### 4.2 Source Quality Hierarchy

1. Dated vendor quotations and contracts (customer-specific)
2. Authorized vendor/partner APIs (list rates)
3. Published utility tariffs (regulatory)
4. Approved public/industry benchmarks (planning-grade)
5. Controlled manual entry (requires review)

### 4.3 Synthetic Data Handling

- Seeded price rows are synthetic test fixtures only
- UI displays "Not priced" for absent prices
- Synthetic provenance is flagged in API responses
- Synthetic demo mode is explicitly labeled "NOT LIVE"
- No synthetic data is presented as live telemetry, market prices, or operational evidence

### 4.4 Security Controls

- Connector credentials in secret manager, not cost book
- API reads are tenant-scoped and read-only
- Supabase deployments must retain RLS on every new table
- Verify view access under non-owner roles
- No procurement, billing, dispatch, or control write is performed
- Integration run retains: source version, pagination/cursor, currency/unit conversion, rejected-row count, source timestamp, digest

### 4.5 Estimate-to-Actual Reconciliation

Budget-vs-actual, estimate-at-completion, and variance become reliable only when:
- Period aligns
- Accounting basis aligns
- Currency aligns
- Scope aligns

---

## 5. UI Display Rules

### 5.1 Estimate Cards

For each estimate, display:
- Lifecycle PV (with currency and horizon)
- Annualized lifecycle cost (with discount rate and calculation version)
- Equivalent cost / IT kW-year
- Equivalent cost / facility m²-year
- Equivalent cost / rack-year
- Equivalent cost / IT kWh
- Equivalent cost / work unit (when available)

### 5.2 Price Book Display

Show: item code, description, category, quantity unit, unit price, currency, normalized unit price, book currency, FX basis, geography, delivery basis, observed time, validity window, source kind/name/reference, confidence, quality status, provenance.

### 5.3 Actual Cost Ledger

Group by: accounting period, cost type, currency. Show: actual amount, entry count, synthetic flag.

### 5.4 Placement Comparison Results

Show for each side (on-prem, cloud):
- NPV at horizon
- Average monthly equivalent
- Cost per delivered unit
- First-year cash
- Lifecycle nominal (undiscounted)
- One-time costs, recurring monthly costs
- Evidence grade (SCENARIO ONLY vs. SOURCE-REFERENCED)
- Lower-cost case label (financial arithmetic only, not a recommendation)

---

## 6. Explicit Model Boundaries

The cost intelligence system does NOT:
- Replace an engineer's signed load schedule
- Substitute for a quantity surveyor takeoff
- Act as a vendor tender
- Determine utility tariff
- Provide finance approval
- Replace an accounting system
- Invent salvage value, tax treatment, or utility demand charges
- Create probability distributions from low/base/high bounds
- Perform procurement, billing, dispatch, or control writes
- Treat a lower modeled cost as a placement recommendation
- Compare WUE across materially different reporting definitions without normalization
- Treat GPU utilization percent as useful work
- Silently fall back to another region or currency when a rate is missing
- Persist cloud catalog prices as quotes or bills
