# Data Center Commander — Documentation Audit

**Date:** 2026-09-29  
**Scope:** All project documentation (README, architecture, lifecycle, integrations, security, runbooks, data model, cost estimating, local development, purple-team readiness)  
**Method:** Cross-referenced every documented claim against actual source code, schema, scripts, tests, and CI configuration.

---

## 1. Executive Summary

The project has **10 documentation files** totaling ~52 KB. Documentation is generally well-structured, safety-conscious, and honest about what is implemented vs. planned. However, there are **significant gaps** in operational runbooks, API reference, schema documentation, and contributor guidance. Several documented features lack corresponding implementation details, and a few documented items are inconsistent with the actual codebase.

**Overall grade: B-** — Good architectural and safety documentation; weak operational and contributor documentation.

---

## 2. Documentation Inventory

| File | Lines | Size | Last Modified | Grade |
|---|---|---|---|---|
| `README.md` | 244 | 13.8 KB | 2026-09-28 | B+ |
| `docs/ARCHITECTURE.md` | 113 | 6.0 KB | 2026-09-28 | B |
| `docs/LIFECYCLE_OPERATIONS.md` | 92 | 7.6 KB | 2026-09-28 | B+ |
| `docs/INTEGRATIONS.md` | 122 | 9.3 KB | 2026-09-28 | B+ |
| `docs/SECURITY_AND_GOVERNANCE.md` | 59 | 3.3 KB | 2026-09-28 | B |
| `docs/OPERATOR_WORKFLOWS.md` | 90 | 5.0 KB | 2026-09-28 | B+ |
| `docs/DATA_MODEL_AND_KPIS.md` | 87 | 4.4 KB | 2026-09-28 | B |
| `docs/COST_ESTIMATING_AND_UNIT_ECONOMICS.md` | 122 | 7.0 KB | 2026-09-28 | B+ |
| `docs/LOCAL_DEVELOPMENT.md` | 42 | 2.4 KB | 2026-09-28 | B |
| `docs/PURPLE_TEAM_READINESS.md` | 30 | 4.1 KB | 2026-09-28 | B+ |

**Total:** 10 files, 761 lines, ~63 KB

---

## 3. Missing Documentation

### 3.1 Critical Gaps (Should exist for any production-adjacent project)

| Missing Doc | Severity | Rationale |
|---|---|---|
| **API Reference** | 🔴 High | No OpenAPI/Swagger spec or endpoint reference. The API has 12+ routes (`/healthz`, `/readyz`, `/v1/overview`, `/v1/topology`, `/v1/facilities`, `/v1/assets`, `/v1/workflows`, `/v1/connectors`, `/v1/capacity`, `/v1/evidence`, `/v1/costs`, `/v1/analytics`, `/v1/placement/scenarios`, `/v1/pricing/azure-retail`, `/v1/pricing/google-cloud-retail`) with no formal API documentation. |
| **Runbook: Backup & Restore** | 🔴 High | No backup/restore procedures documented. The schema has no documented backup strategy. |
| **Runbook: Incident Response** | 🔴 High | No incident response runbook. Security doc mentions "practiced incident/restore procedures" but none are documented. |
| **Runbook: Troubleshooting** | 🟡 Medium | No troubleshooting guide for common issues (DB connection failures, missing schema, RLS misconfiguration, demo seed issues). |
| **Schema/Data Dictionary** | 🟡 Medium | `database/schema.sql` defines 30+ tables but there is no human-readable data dictionary explaining each table's purpose, relationships, and field semantics. |
| **Deployment Guide** | 🟡 Medium | Only local development is documented. No guide for deploying to Supabase, Docker, or any production environment. |
| **Testing Guide** | 🟡 Medium | Tests exist (`test_contracts.py`, `test_azure_prices.py`) but there's no documentation on how to run them, what they cover, or how to add new tests. |
| **Migration Guide** | 🟡 Medium | README mentions migrations 001-004 but doesn't explain what each migration does or how to apply them in order. |

### 3.2 Important Gaps (Needed for contributor and operational maturity)

| Missing Doc | Severity | Rationale |
|---|---|---|
| **CONTRIBUTING.md** | 🟡 Medium | No contributor guide. No code style, PR process, or development workflow documentation. |
| **CHANGELOG.md** | 🟡 Medium | No version history or changelog. |
| **CODE_OF_CONDUCT.md** | 🟢 Low | No code of conduct. |
| **Performance/Scale Documentation** | 🟡 Medium | Architecture doc mentions scaling path but no performance benchmarks, load testing results, or capacity planning guide. |
| **Adapter Development Guide** | 🟡 Medium | INTEGRATIONS.md describes the adapter contract but doesn't provide a step-by-step guide for implementing a new adapter. |
| **UI Component Documentation** | 🟢 Low | UI has 6 JS files with no documentation on component structure, state management, or how to add new views. |

---

## 4. Outdated or Inconsistent Documentation

### 4.1 Port Inconsistency

**README.md** references two different ports:
- Line 93: `uv run --extra postgres python scripts/run-local.py --host 127.0.0.1 --port 8790`
- Line 145: `http://127.0.0.1:8795/?tenant_id=...&demo=synthetic`
- Line 215: `http://127.0.0.1:8795/?tenant_id=...&demo=synthetic`

The API server (`api.py`) defaults to port 8790. The UI is served by the same server. **Port 8795 is never mentioned in any code** — it appears to be a typo or stale reference. The UI should be accessed at `http://127.0.0.1:8790/`.

### 4.2 Undocumented API Endpoint: Placement Snapshots

The API implements `POST /v1/placement/scenarios` (api.py:419-457) for saving placement comparison snapshots, but this endpoint is **not documented in any documentation file**. The README mentions "Save draft snapshot" (line 78) but doesn't describe the API contract.

### 4.3 Undocumented Security Measures

The code implements several security measures that are only partially documented:
- **Loopback-only binding** (api.py:461-462) — mentioned in README but not in SECURITY_AND_GOVERNANCE.md
- **Read-only transactions** (api.py:84, 242) — not documented anywhere
- **Tenant RLS via `set_config`** (api.py:133, 243, 444) — mentioned in README but not in SECURITY_AND_GOVERNANCE.md
- **Request body size limits** (api.py:431) — not documented
- **Same-origin enforcement** (api.py:424-428) — not documented
- **Silent logging** (api.py:111-113) — not documented

### 4.4 Architecture Doc Lacks "Current Implementation" Section

`docs/ARCHITECTURE.md` describes a target architecture with components like "Read-only connector agents," "Protocol-aware industrial DMZ gateway," "Durable local spool," etc. While the README clarifies this is a "local decision-support prototype," the architecture doc itself doesn't clearly distinguish between:
- What is currently implemented (PostgreSQL schema, read-only API, 2 cloud price adapters)
- What is designed but not implemented (all facility/BMS/EPMS/CMMS adapters, ingestion pipeline, analytics engine)
- What is aspirational (multi-site, regional aggregation, TimescaleDB)

### 4.5 Data Model Doc Incomplete

`docs/DATA_MODEL_AND_KPIS.md` describes the conceptual model but doesn't map to the actual schema. For example:
- The ER diagram shows `WORKLOAD ||--o{ DEPLOYMENT` but the actual schema has `workloads` and `deployments` tables with different columns
- The doc mentions `KPI_DEFINITION` and `KPI_OBSERVATION` but the actual tables are `kpi_definitions` and `kpi_observations` with additional fields not in the doc
- The doc doesn't document `placement_comparison_snapshots`, `cost_books`, `estimate_cost_rollup`, `connector_runs`, `procedures`, `workflow_tasks`, `approvals`, `work_orders`, `incidents`, `change_records`, `tariffs`, `carbon_factors`, `meters`, `metric_definitions`

### 4.6 Migration Documentation Missing

README mentions migrations 001-004 but doesn't explain what each does:
- `001_cost_intelligence.sql` — adds cost tables
- `002_lifecycle_rollup_fix.sql` — fixes lifecycle rollup
- `003_estimate_price_link_validation.sql` — adds price link validation
- `004_placement_comparison_snapshots.sql` — adds placement snapshots

No migration doc explains the purpose, dependencies, or rollback procedure for each.

### 4.7 Demo Seed Scripts Not Documented

`database/demo_analytics_expansion.sql` and `database/cost_demo_seed.sql` are mentioned in README but their contents, purpose, and effects are not documented. Operators need to know:
- What data each script adds
- Whether they are idempotent
- What tables they affect
- How they interact with the base schema

---

## 5. Documentation Strengths

1. **Safety-first documentation** — The project consistently and clearly documents what it does NOT do (no actuation, no control, no production auth). This is excellent.
2. **Honest status reporting** — README clearly states "local decision-support prototype" and lists what works vs. what doesn't.
3. **Clear product contract** — The 5-point product contract in README is well-defined and testable.
4. **Lifecycle coverage** — LIFECYCLE_OPERATIONS.md covers all 15 lifecycle stages with clear gates and evidence requirements.
5. **Integration honesty** — INTEGRATIONS.md clearly distinguishes between "contract/design only" and "implemented" adapters.
6. **Purple-team readiness** — PURPLE_TEAM_READINESS.md is appropriately cautious and clearly separates planning from execution.
7. **Synthetic data quarantine** — The project clearly documents how synthetic data is tagged, quarantined, and reset.

---

## 6. Recommendations

### Priority 1 — Critical (Do immediately)

1. **Create API reference documentation** — Document all 15+ endpoints with request/response schemas, error codes, and examples. Consider generating from code or creating an OpenAPI spec.
2. **Fix port inconsistency** — Change port 8795 to 8790 in README (lines 145, 215).
3. **Document placement snapshot API** — Add the `POST /v1/placement/scenarios` endpoint to INTEGRATIONS.md or a new API doc.
4. **Create backup/restore runbook** — Document how to backup and restore the PostgreSQL database, including schema and demo data.

### Priority 2 — Important (Do within 1-2 weeks)

5. **Add "Current Implementation" section to ARCHITECTURE.md** — Clearly separate implemented vs. designed vs. aspirational components.
6. **Create data dictionary** — Document all 30+ tables in `database/schema.sql` with field descriptions and relationships.
7. **Document migrations** — Add a migration guide explaining each migration's purpose and how to apply them.
8. **Create troubleshooting runbook** — Document common issues and resolutions.
9. **Document security measures** — Add loopback binding, read-only transactions, RLS, and request limits to SECURITY_AND_GOVERNANCE.md.
10. **Create CONTRIBUTING.md** — Document code style, PR process, and development workflow.

### Priority 3 — Nice to Have

11. **Create CHANGELOG.md** — Track version history.
12. **Document demo seed scripts** — Explain what each script does and how to use them.
13. **Create adapter development guide** — Step-by-step guide for implementing new adapters.
14. **Add testing documentation** — How to run tests, what they cover, how to add new ones.
15. **Document UI components** — Component structure and how to add new views.

---

## 7. Documentation-to-Code Cross-Reference Matrix

| Documented Feature | In Code? | In Docs? | Notes |
|---|---|---|---|
| Loopback-only API | ✅ api.py:461 | ✅ README | Not in SECURITY doc |
| Read-only transactions | ✅ api.py:84,242 | ❌ | Undocumented |
| Tenant RLS | ✅ api.py:133,243 | ✅ README | Not in SECURITY doc |
| Health endpoint | ✅ api.py:160 | ✅ README | |
| Readiness endpoint | ✅ api.py:163 | ✅ README | |
| Azure price adapter | ✅ azure_prices.py | ✅ INTEGRATIONS | |
| Google price adapter | ✅ google_prices.py | ✅ INTEGRATIONS | |
| Placement snapshots API | ✅ api.py:419 | ❌ | Undocumented endpoint |
| Synthetic data quarantine | ✅ api.py:377-387 | ✅ README | |
| Demo seed scripts | ✅ database/*.sql | ✅ README | Effects undocumented |
| Migrations 001-004 | ✅ database/migrations/ | ✅ README | Purpose undocumented |
| CI pipeline | ✅ .github/workflows/ | ✅ README badge | |
| Tests | ✅ tests/ | ✅ README | Coverage undocumented |
| UI views | ✅ ui/*.js | ✅ README screenshots | Component doc missing |
| Cost estimating | ✅ schema + api.py | ✅ COST_ESTIMATING | |
| Lifecycle operations | ✅ schema | ✅ LIFECYCLE_OPERATIONS | |
| Operator workflows | ✅ schema | ✅ OPERATOR_WORKFLOWS | |
| Purple-team readiness | ✅ GRC controls | ✅ PURPLE_TEAM_READINESS | |
| BMS/EPMS/CMMS adapters | ❌ | ✅ INTEGRATIONS (design only) | Correctly marked |
| Kubernetes/cloud adapters | ❌ | ✅ INTEGRATIONS (design only) | Correctly marked |
| Predictive maintenance | ❌ | ✅ LIFECYCLE (design only) | Correctly marked |
| Multi-site deployment | ❌ | ✅ ARCHITECTURE (design only) | Correctly marked |

---

## 8. Conclusion

The documentation is **architecturally sound and safety-conscious** but **operationally incomplete**. The most critical gaps are the lack of API reference documentation, backup/restore runbooks, and incident response procedures. The port inconsistency (8790 vs 8795) is a concrete bug that should be fixed immediately. The undocumented placement snapshot API endpoint represents a feature that exists in code but is invisible to users.

The project would benefit most from:
1. An API reference (OpenAPI spec or similar)
2. Operational runbooks (backup/restore, troubleshooting, incident response)
3. A "current implementation" section in the architecture doc
4. A data dictionary for the schema

---

*Audit completed 2026-09-29 by automated documentation review.*
