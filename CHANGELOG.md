# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-09-28

### Overview

Initial public release of **Data Center Commander** — an open, operator-centered
system for governing the full data-center lifecycle from utility boundary to
useful compute. This release delivers a local decision-support prototype with a
portable PostgreSQL schema, read-only loopback API, multi-tab command-center UI,
and explicitly synthetic demo data.

**Status:** local decision-support prototype. Vendor adapters, validated
forecasts, production IAM, and facility control are not delivered.

---

### Added

#### Database & Schema

- **Portable PostgreSQL schema** (`database/schema.sql`, 352 lines) covering:
  - Tenant-scoped operational model with forced Row-Level Security (RLS)
  - Sites, spaces, assets, and topology hierarchy
  - Meter boundaries, telemetry, and quality tracking
  - Capacity, workflows, work orders, and incidents
  - Effective-dated prices, estimate lines, and actuals
  - Append-only evidence ledger
- **Four ordered migrations** for existing databases:
  - `001_cost_intelligence.sql` — cost intelligence tables and views
  - `002_lifecycle_rollup_fix.sql` — corrected lifecycle rollup logic
  - `003_estimate_price_link_validation.sql` — estimate-to-price link validation
  - `004_placement_comparison_snapshots.sql` — append-only draft snapshots for placement comparisons
- **Demo seed scripts**:
  - `database/demo_seed.sql` — base synthetic tenant data
  - `database/cost_demo_seed.sql` — cost-only fixture for existing demo databases
  - `database/demo_analytics_expansion.sql` — additive 30-day history with 15-minute interval energy and derived daily energy/PUE points; modeled thermal, carbon, compute-efficiency, and headroom values explicitly marked synthetic; idempotent and non-destructive

#### Backend API (`src/dcc/`)

- **Loopback read-only API** (`api.py`, 476 lines):
  - Health and readiness endpoints (`/healthz`, `/readyz`)
  - Read-model routes for facilities, energy, capacity, economics, workflows, and evidence
  - Tenant-scoped queries with forced RLS
  - Refuses non-loopback binds
- **Azure Prices adapter** (`azure_prices.py`, 105 lines) — read-only cloud price retrieval
- **Google Prices adapter** (`google_prices.py`, 138 lines) — read-only cloud price retrieval
- **Adapter framework** (`adapters/`):
  - `registry.py` — versioned read-only adapter registry
  - `bms.py` — Building Management System adapter contract
  - `cloud.py` — Cloud provider adapter contract
  - `cmms.py` — CMMS adapter contract
  - `epms.py` — EPMS adapter contract
  - `hypervisor.py` — Hypervisor adapter contract
  - `meter.py` — Meter adapter contract
  - `oem.py` — OEM adapter contract
  - `utility.py` — Utility adapter contract
  - `weather.py` — Weather adapter contract
- **Economics module** (`economics/`):
  - `allocation.py` — cost allocation logic
  - `budget.py` — budget tracking
  - `estimates.py` — estimate management
  - `prices.py` — effective-dated price observations
  - `reconciliation.py` — estimate-to-actual reconciliation
  - `scenarios.py` — scenario modeling
  - `tariffs.py` — tariff structures
  - `tco.py` — Total Cost of Ownership calculations
  - `unit.py` — unit economics
- **Forecasting module** (`forecasting/`):
  - `backtest.py` — time-split backtesting
  - `calibration.py` — model calibration
  - `capacity.py` — capacity forecasting
  - `drift.py` — drift detection
  - `failure.py` — failure prediction
  - `features.py` — condition feature engineering
  - `load.py` — load forecasting
  - `maintenance.py` — maintenance signal analysis
  - `price.py` — price forecasting
- **Provenance module** (`provenance/`):
  - `tracker.py` — source lineage and provenance tracking
- **Quality module** (`quality/`):
  - `anomaly.py` — anomaly detection
  - `engine.py` — quality engine
  - `freshness.py` — data freshness checks
- **Validation module** (`validation/`):
  - `boundaries.py` — meter boundary validation
  - `consistency.py` — cross-source consistency checks
  - `intervals.py` — interval alignment
  - `schema.py` — schema validation
  - `units.py` — unit normalization

#### Frontend UI (`ui/`)

- **Multi-tab command center** (`index.html`, 154 lines) with panels for:
  - Command picture (facility overview)
  - Energy & carbon
  - Data science & BI
  - Sizing & economics
  - Placement tradeoffs
  - Capacity & resilience
  - Estate & lifecycle
  - Reliability
  - Operations queue
  - Integrations
  - Evidence & audit
  - Suggested workloads
  - Critical environments & GRC
- **UI modules**:
  - `azure-prices.js` — Azure pricing panel
  - `economics-dashboard.js` — Economics dashboard
  - `forecast-dashboard.js` — Forecast dashboard
  - `onboarding.js` — Onboarding wizard
  - `placement-comparison.js` — Placement comparison tool
  - `placement-scenarios.js` — Scenario modeling
  - `quality-dashboard.js` — Data quality dashboard
  - `topology.js` — Topology visualization
- **Synthetic demo mode** — opt-in via `?demo=synthetic` query parameter; all data visibly tagged with `SYNTHETIC DEMO · NOT LIVE` banner; quarantined from operational view without explicit demo switch

#### Tests (`tests/`)

- **27 test modules** covering:
  - API and schema contract tests (`test_contracts.py`, 205 lines)
  - Adapter tests (`test_adapters.py`, `test_cmms_adapter.py`, `test_epms_adapter.py`, `test_meter_adapter.py`)
  - Economics tests (`test_economics_estimates.py`, `test_economics_prices.py`, `test_economics_unit.py`, `test_allocation.py`, `test_scenarios.py`, `test_tco.py`)
  - Forecasting tests (`test_backtest.py`, `test_calibration.py`, `test_capacity_forecast.py`, `test_drift.py`, `test_failure_prediction.py`, `test_features.py`, `test_maintenance.py`, `test_price_forecasting.py`)
  - Quality tests (`test_anomaly.py`, `test_freshness.py`)
  - Validation tests (`test_consistency.py`, `test_intervals.py`, `test_units.py`)
  - Cloud price tests (`test_azure_prices.py`, 112 lines)

#### Documentation (`docs/`)

- `ARCHITECTURE.md` — Full system architecture (113 lines)
- `COST_ESTIMATING_AND_UNIT_ECONOMICS.md` — Lifecycle sizing, dated price observations, estimate-to-actual accounting, and unit economics (122 lines)
- `DATA_MODEL_AND_KPIS.md` — Data model and KPI definitions (87 lines)
- `INTEGRATIONS.md` — Adapter contracts and staged onboarding plans (122 lines)
- `LIFECYCLE_OPERATIONS.md` — Lifecycle operations documentation (92 lines)
- `LOCAL_DEVELOPMENT.md` — Local development setup guide (42 lines)
- `OPERATOR_WORKFLOWS.md` — Operator workflow documentation (90 lines)
- `PURPLE_TEAM_READINESS.md` — Purple-team telemetry-validation lab boundaries and read-only connector readiness gate (30 lines)
- `SECURITY_AND_GOVERNANCE.md` — Security and governance documentation (59 lines)

#### CI/CD

- **GitHub Actions workflow** (`.github/workflows/ci.yml`):
  - Runs on push to `main` and pull requests
  - Python 3.11 on ubuntu-latest
  - Executes API and schema contract tests via `python -m unittest discover -s tests -v`
  - Validates shell script syntax via `bash -n scripts/*.sh`
  - 10-minute timeout
  - Read-only permissions

#### Scripts

- `scripts/run-local.py` — Local development server launcher
- `scripts/db-seed-demo.sh` — Demo database seeding script
- `scripts/db-reset-demo.sh` — Demo database reset script

#### Project Configuration

- `pyproject.toml` — Python project configuration (setuptools backend, Python ≥3.11, optional postgres and test extras)
- `uv.lock` — UV package manager lockfile
- `.gitignore` — Standard Python ignores plus `.env`, `.coverage`, `dist/`, `build/`, `*.egg-info/`
- `LICENSE` — GNU Affero General Public License v3.0 (AGPL-3.0-only)

---

### Changed

- **README.md** — Expanded from initial release to include:
  - CI badge and license badge
  - Architecture section with Mermaid diagram
  - Detailed data and analytics flows with two Mermaid diagrams
  - Roadmap table (Stages 0–6)
  - Screenshots and GIF section with 13 section captures
  - Safety and authority boundary section
  - Local synthetic walkthrough instructions
  - Migration ordering instructions

---

### Fixed

- **CI pipeline** — Added GitHub Actions workflow to run tests and validate shell scripts on every push/PR
- **README accuracy** — Clarified demo media status; initially stated screenshots/GIF were outstanding, then updated to reflect committed synthetic visual tour

---

### Media Assets

- **13 synthetic demo screenshots** committed to `docs/media/`:
  - `command-picture.jpg` — Facility command picture
  - `energy-carbon.jpg` — Energy and carbon panel
  - `data-science-bi.jpg` — Data science and BI panel
  - `sizing-economics.jpg` — Sizing and economics panel
  - `placement-tradeoffs.jpg` — Placement tradeoffs panel
  - `capacity-resilience.jpg` — Capacity and resilience panel
  - `estate-lifecycle.jpg` — Estate and lifecycle panel
  - `reliability.jpg` — Reliability panel
  - `operations-queue.jpg` — Operations queue panel
  - `integrations.jpg` — Integrations panel
  - `evidence-audit.jpg` — Evidence and audit panel
  - `suggested-workloads.jpg` — Suggested workloads panel
  - `critical-grc.jpg` — Critical environments and GRC panel
- **1 overview GIF** (`overview.gif`, ~1.4 MB) — Animated tour across all synthetic demo sections
- All captures preserve the `SYNTHETIC DEMO · NOT LIVE` banner and use only the documented local synthetic walkthrough

---

### Commits

| Hash | Date | Description |
|------|------|-------------|
| `dd4ab1f` | 2026-09-28 11:40:27 +0300 | Prepare initial public release |
| `4abd3a3` | 2026-09-28 12:11:42 +0300 | Fix CI and surface architecture in README |
| `d52de55` | 2026-09-28 12:35:17 +0300 | Clarify README demo media status |
| `81579fd` | 2026-09-28 13:18:58 +0300 | Add synthetic visual demo tour |
| `31c4ea8` | 2026-09-28 13:50:55 +0300 | Move overview GIF to README top |

---

### Statistics

- **36 files** changed in initial release
- **3,712 lines** added in initial release
- **27 test modules** in test suite
- **10 adapter contracts** defined
- **9 economics modules** implemented
- **9 forecasting modules** implemented
- **13 documentation files** (excluding media)
- **13 synthetic demo screenshots** + **1 overview GIF**

---

### Safety & Authority Boundary

This release is observation and decision-support only. It contains no generic
shell, remote desktop, BMS write, breaker/switch control, setpoint change, VM
lifecycle, or workload dispatch path. Recommendations are not commands. Any
future execution adapter requires a separate, independently reviewed project gate.

The local API remains unauthenticated and loopback-only; do not expose it remotely.

---

### Roadmap

| Stage | Deliverable | Status |
|---|---|---|
| 0 · Local command center | Portable schema, guarded demo seed, 30-day synthetic history, overview/energy/BI/economics/workflow/evidence panels | ✅ Complete |
| 1 · Source onboarding | Read-only connector registry, onboarding wizard, identity/scope/freshness checks, import previews | Planned |
| 2 · Data quality and BI | Boundary-aligned intervals, missingness/coverage budgets, versioned formulas, KPI lineage and cost actual reconciliation | Planned |
| 3 · Predictive maintenance | Condition features, work-order/failure labels, maintenance history, interpretable forecasting and drift | Planned |
| 4 · Lifecycle and economics | Sourced dated prices/tariffs/contracts, quantity takeoff, contingency/escalation/FX, estimate-to-actual and unit economics | Planned |
| 5 · Production hardening | AuthN/AuthZ, tenant isolation, secret manager, migrations, backups/restore, observability, incident handling, HA | Planned |
| 6 · Certified ecosystem | OEM/cloud/facility adapter conformance, optional enterprise analytics and support | Planned |

The roadmap is an implementation sequence, not a readiness claim.

---

[0.1.0]: https://github.com/AAH20/data-center-commander/releases/tag/v0.1.0
