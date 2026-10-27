# Data Center Commander — Benchmark Report

**Measured:** 2026-10-26
**Commit:** `4375603` (`main`)
**Environment:** macOS, Python 3.11.15, pytest 9.1.1, PostgreSQL on 5432, database `dcc_demo_local`
**Scope:** test results, code and schema composition, dependencies, CI wiring, and the performance
notes carried over from the 2026-09-29 audit.

Every number below is a command output quoted in this file or a count derived from one, and the
command is given. Where something was **not** measured, this file says so instead of supplying a
number. Earlier revisions quoted a 89.8% pass rate with 636 failing tests; that figure is
retracted — §1a records what it said, why it could not stand, and what replaced it.

---

## 1. Executive Summary

| Metric | Value | How measured |
|--------|-------|--------------|
| Python source LOC | 88,931 across 199 files under `src/` | `find src -name '*.py' -exec cat {} + \| wc -l` |
| Test LOC | 85,931 across 247 `test_*.py` files | `find tests -name 'test_*.py' -exec cat {} + \| wc -l` |
| Test-to-source ratio | 0.97 : 1 | division of the two rows above |
| **CI gate pass rate** | **100.00% (7,531 / 7,531 executed)** | §3.1: `7531 passed, 9 skipped` |
| Items executed in the gate | 7,540 | same run |
| **Failures in the gate** | **0** | same run |
| Collected across the whole tree | 7,962 | §3.2 |
| Failures outside the gate | 16 (`tests/e2e` + `tests/iac-visual`) | §3.3 |
| SQL LOC | 2,237 across 16 files | `wc -l database/*.sql database/migrations/*.sql` |
| UI LOC | 4,878 across 11 files in `ui/` | `find ui -maxdepth 1 -type f -exec cat {} + \| wc -l` |
| `/v2` paths served | 29 (37 routes including docs, metrics and probes) | `dcc.api_async.app.routes` |
| Database objects | 54 tables, 156 indexes, 7 views, 52 RLS policies, 2 triggers | §2.3, from `pg_class` / `pg_policies` |
| Runtime dependencies | 3 (`fastapi`, `uvicorn`, `cryptography`) | `pyproject.toml` |
| Commits | 156 | `git rev-list --count HEAD` |

Two suite facts matter more than the totals:

* **The suite is pytest and it runs in CI, blocking.** `ci.yml:146-165` runs
  `coverage run -m pytest tests/` with four documented exclusions; `ci.yml:103-111` records that
  the step lost its `continue-on-error` exemption. Older revisions of this file claimed CI ran
  only linting, and separately that it ran `unittest discover`. Both are false on this tree.
* **`tests/terraform` is green:** 865 passed, 879 subtests, 0 failed in 0.98s. Older revisions
  attributed 334 of the 636 failures to Terraform modules that had moved. That explanation was
  attached to a number that no longer exists, and it described a suite that now passes.

---

## 1a. Retracted figures

Kept on purpose: a benchmark that silently drops a wrong number leaves the next reader unable to
tell which of its numbers were ever wrong.

| Claim | Where it was stated | Status | What the measurement says |
|-------|--------------------|--------|---------------------------|
| "89.8% (5,248/5,846), 636 failing" | §1, §1b and §1a of the 2026-10-18 revision; also the justification in `ci.yml`'s removed `continue-on-error` comment | **False today** | §3.1: `7531 passed, 9 skipped` — 0 failed, 7,540 executed |
| "89.4% (6,623/7,406), 759 failing, 24 skipped" | §1, §1b (2026-10-18 revision) | **False today** | Whole tree collects 7,962; 7,540 execute in the gate with 0 failures; the other 422 are the four excluded directories, measured in §3.3 |
| "334 of the 636 failures are terraform tests … the layout does not exist" | §1a item 3 | **False today** | `tests/terraform`: `865 passed, 879 subtests passed in 0.98s` |
| "CI never ran this suite … a green badge is a LINT signal" | §1a item 1 | **False** | `ci.yml:146-165` runs pytest and the step is blocking |
| "99.8% (1,060/1,062), 1 failure + 1 error" | §3.1 (2026-09-29 revision) | **Superseded** | It described a `unittest` run; the suite is pytest (§3.4) |
| "Known test failures: 2" | §1, §3.2, §9 | **False** | Both named tests pass: `tests/test_tenant_security.py` → `31 passed`; `pytest tests/test_units.py -k ups_runtime` → `5 passed` |

The 2026-10-18 figures came from a tree whose collection was broken by a stray `pytest.ini`
(then moved aside). Whatever produced them, they do not describe this tree, and the Terraform
explanation written around them is contradicted by running the Terraform suite.

---

## 1b. Scopes: what "the suite" means here

`ci.yml` runs the suite with four exclusions, each for a missing capability rather than a red test:

| Scope | Command | Measured result |
|-------|---------|-----------------|
| **CI gate** (blocking) | `pytest tests/ -q --ignore=tests/e2e --ignore=tests/iac-performance --ignore=tests/iac-visual --ignore=tests/performance` | **7,531 passed, 9 skipped, 1,018 subtests passed, 0 failed** (252.39s) |
| `tests/e2e` (excluded) | needs a browser and its own server | 291 collected; 15 fail — §3.3 |
| `tests/iac-performance` (excluded) | 86 collected, ~44 min per `ci.yml:115-118` | **not measured in this pass** — §3.3 |
| `tests/iac-visual` (excluded) | needs 7 stored view baselines | 5 collected; 1 fails — §3.3 |
| `tests/performance` (excluded) | wall-clock microbenchmarks | 40 collected, 40 passed — §3.3 |
| Whole tree, collected | `pytest tests/ --collect-only` | **7,962 tests collected** |

7,540 + 291 + 86 + 5 + 40 = 7,962. The arithmetic closes exactly, which is the check that the
gate scope and the tree are one suite measured two ways.

---

## 2. Codebase Composition

### 2.1 Source layout

| Package | Files | LOC |
|---|---|---|
| `src/dcc/adapters/` | 13 | 7,243 |
| `src/dcc/autoscaling/` | 22 | 5,619 |
| `src/dcc/compliance/` | 22 | 6,984 |
| `src/dcc/containers/` | 18 | 3,665 |
| `src/dcc/cost_optimization/` | 7 | 1,325 |
| `src/dcc/dr/` | 6 | 4,840 |
| `src/dcc/economics/` | 10 | 8,058 |
| `src/dcc/forecasting/` | 10 | 4,769 |
| `src/dcc/iac/` | 5 | 1,018 |
| `src/dcc/iac_observability/` | 6 | 1,949 |
| `src/dcc/identity_federation/` | 6 | 2,312 |
| `src/dcc/network/` | 8 | 4,564 |
| `src/dcc/observability/` | 8 | 4,985 |
| `src/dcc/operations/` | 4 | 3,835 |
| `src/dcc/policy/` | 10 | 1,647 |
| `src/dcc/provenance/` | 3 | 670 |
| `src/dcc/quality/` | 4 | 1,296 |
| `src/dcc/security/` | 13 | 8,661 |
| `src/dcc/security_posture/` | 5 | 1,299 |
| `src/dcc/soc/` | 0 (namespace only) | 0 |
| `src/dcc/validation/` | 6 | 6,528 |
| `src/dcc/*.py` (top level) | 13 | 7,664 |
| **Total** | **199** | **88,931** |

### 2.2 Largest test files

247 `test_*.py` files, 85,931 LOC. The 15 largest:

| Test file | LOC |
|---|---|
| `tests/security/test_auth_bypass.py` | 2,159 |
| `tests/terraform/test_other_modules.py` | 1,473 |
| `tests/integration/test_adapters_integration.py` | 1,385 |
| `tests/integration/test_economics_integration.py` | 1,267 |
| `tests/compliance/checkov/test_checkov_policies.py` | 1,181 |
| `tests/test_units.py` | 1,092 |
| `tests/integration/test_api_integration.py` | 1,036 |
| `tests/compliance/opa/test_compliance.py` | 1,028 |
| `tests/policy/test_policy.py` | 992 |
| `tests/terraform/test_gcp_modules.py` | 959 |
| `tests/test_backup.py` | 940 |
| `tests/virtualization/test_proxmox_integration.py` | 888 |
| `tests/virtualization/test_docker_integration.py` | 881 |
| `tests/compliance/test_controls_real_state.py` | 881 |
| `tests/virtualization/test_vmware_integration.py` | 880 |

### 2.3 Database schema, counted from the live catalog

Measured against `dcc_demo_local` on 2026-10-26 with `psql -Atc`:

| Component | Count | Query basis |
|-----------|-------|-------------|
| Tables | 54 | `pg_class` `relkind in ('r','p')`, `nspname='dcc'` |
| Indexes | 156 | `pg_index` joined to `pg_class` in schema `dcc` |
| Views | 7 | `relkind in ('v','m')` |
| RLS policies | 52 | `pg_policies where schemaname='dcc'` |
| Tables with RLS enabled | 53 of 54 | `relrowsecurity` |
| Triggers | 2 | non-internal rows in `pg_trigger` |
| Migrations | 12 | `database/migrations/*.sql` |
| Seed / demo SQL | 3 | `demo_seed.sql`, `demo_analytics_expansion.sql`, `cost_demo_seed.sql` |

The one table without RLS is `dcc.tenants`, the tenant register itself: it carries no `tenant_id`
column and sits outside the isolation model rather than being an exception to it. The probe agrees
— `/readyz` reports `tenant_rls_tables: 52` (the tables that do carry `tenant_id`),
`tenant_rls_unprotected: 0` (`src/dcc/api_async.py:713-775`).

Earlier revisions claimed 28 tables, 14 indexes and "all tables" with forced RLS. Wrong on every
count, and low by roughly half on tables.

### 2.4 UI modules

11 files, 4,878 LOC under `ui/`: `index.html`, `economics-dashboard.js`, `forecast-dashboard.js`,
`quality-dashboard.js`, `ops-dashboard.js`, `security-dashboard.js`,
`placement-comparison.js`, `placement-scenarios.js`, `azure-prices.js`, `onboarding.js`,
`topology.js`, plus a `components/` directory.

---

## 3. Test Results

### 3.1 The CI gate, run as `ci.yml` specifies

```
$ PYTHONPATH=src DCC_DATABASE_URL=postgresql://localhost:5432/dcc_demo_local \
  HYPOTHESIS_PROFILE=ci .venv/bin/python -m pytest tests/ -q -p no:cacheprovider \
    --ignore=tests/e2e --ignore=tests/iac-performance \
    --ignore=tests/iac-visual --ignore=tests/performance
7531 passed, 9 skipped, 2 warnings, 1018 subtests passed in 252.39s (0:04:12)
```

Run twice on 2026-10-26, identical counts:

| Run | Result |
|-----|--------|
| 1 | `7531 passed, 9 skipped, 2 warnings, 1018 subtests passed in 220.87s (0:03:40)` |
| 2 | `7531 passed, 9 skipped, 2 warnings, 1018 subtests passed in 252.39s (0:04:12)` |

**Pass rate: 100.00% of executed tests (7,531/7,531); 99.88% of executed-and-skipped items
(7,531/7,540). Zero failures, zero errors.**

The 9 skips are capability skips inside the gate — 8 in `tests/iac-fuzzing` (a fuzzing profile not
selected in this run) and 1 in `tests/compliance/sentinel`. The run reports them; this document
does not launder them as passes.

### 3.2 Per-suite counts (gate scope)

Grouped from the JUnit XML of run 2 (`--junitxml=/tmp/dcc_junit.xml`) by module directory:

| Suite | Tests | Passed | Failed | Skipped |
|---|---|---|---|---|
| `tests/` (top-level files) | 1,792 | 1,792 | 0 | 0 |
| `tests/compliance/` | 140 | 140 | 0 | 0 |
| `tests/compliance/checkov/` | 80 | 80 | 0 | 0 |
| `tests/compliance/opa/` | 363 | 363 | 0 | 0 |
| `tests/compliance/sentinel/` | 8 | 7 | 0 | 1 |
| `tests/compliance/tfsec/` | 11 | 11 | 0 | 0 |
| `tests/containers/` | 15 | 15 | 0 | 0 |
| `tests/fuzzing/` | 104 | 104 | 0 | 0 |
| `tests/iac-fuzzing/` | 197 | 189 | 0 | 8 |
| `tests/integration/` | 684 | 684 | 0 | 0 |
| `tests/multicloud/` | 207 | 207 | 0 | 0 |
| `tests/policy/` | 85 | 85 | 0 | 0 |
| `tests/property/` | 162 | 162 | 0 | 0 |
| `tests/security/` | 942 | 942 | 0 | 0 |
| `tests/soc/` | 118 | 118 | 0 | 0 |
| `tests/terraform/` | 865 | 865 | 0 | 0 |
| `tests/test_cost_optimization/` | 50 | 50 | 0 | 0 |
| `tests/unit/` | 1,383 | 1,383 | 0 | 0 |
| `tests/virtualization/` | 329 | 329 | 0 | 0 |
| `tests/visual/` | 5 | 5 | 0 | 0 |
| **Total** | **7,540** | **7,531** | **0** | **9** |

`tests/terraform` alone, quoted directly:

```
$ pytest tests/terraform -q
865 passed, 879 subtests passed in 0.98s
```

### 3.3 What the excluded directories actually do

```
$ pytest tests/e2e tests/iac-visual tests/performance -q
16 failed, 312 passed, 8 skipped, 1 warning in 153.54s (0:02:33)
```

* **15 of the 16 failures are in `tests/e2e`.** They request `/v2/*` and get 404 where the tests
  expect 200 (and 422 for a bad tenant id). The cause is the `api_server` fixture
  (`tests/e2e/conftest.py:72-91`): it treats an open port 8790 as "server ready" and adopts
  whatever is listening. On this machine a **legacy** `dcc.api` handler was bound to 8790
  (`/v1/assets` → 200, `/v2/assets` → 404), so the v2 app never started. A fixture defect, not a
  product defect — reported here, not fixed, because `tests/` is outside this document's scope.
* **1 failure is `tests/iac-visual`:** `test_all_iac_views_have_baselines` — the baseline set is
  incomplete.
* **`tests/performance`: 40 collected, 40 passed.** Its exclusion in `ci.yml:120-126` is a
  timing-noise decision, not a red-test decision.
* **`tests/iac-performance` was not run** (86 tests, ~44 minutes). This file makes **no claim**
  about its result: unmeasured on 2026-10-26.

### 3.4 Execution characteristics

* **Framework:** pytest 9.1.1 with `pytest-subtests` (1,018 subtests in the gate run). 109 of the
  247 test files import pytest directly; `unittest discover` cannot collect the suite
  (`ci.yml:155-158` records the same finding).
* **Config:** `pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]`, per-directory
  `__init__.py` markers to disambiguate same-named modules.
* **Database required for part of it:** readiness, RLS, compliance and provenance tests read real
  catalog and table state through `DCC_DATABASE_URL`; the rest is pure unit testing.
* **Wall clock:** 3.7–4.2 minutes locally for the gate scope, against a 10-minute job timeout
  (`ci.yml:18`).

---

## 4. Performance Notes

### 4.1 Query patterns — carried from the 2026-09-29 audit, **not re-measured**

`reports/dcc-perf-audit.md` (2026-09-29) counts queries per request for the **legacy `/v1`
handler** in `src/dcc/api.py`. Those counts were not re-measured for this report, and the served
application is `dcc.api_async` (`/v2`), which the audit does not cover:

| Legacy endpoint | Queries/request (audit, 2026-09-29) | Severity as recorded |
|---|---|---|
| `/v1/analytics` | 4 | CRITICAL |
| `/v1/costs` | 3 | HIGH |
| `/v1/overview` | 4 | MEDIUM |
| `/v1/topology` | 2 | MEDIUM |
| `/v1/assets`, `/v1/facilities`, `/v1/workflows`, `/v1/connectors`, `/v1/capacity`, `/v1/evidence`, `/v1/placement/scenarios` | 1 each | LOW / MEDIUM |

Not measured in this pass: query counts for any `/v2` endpoint.

### 4.2 Connection pool — read from source, 2026-10-26

`src/dcc/api_async.py:271-289`:

| Setting | Value in source | Note |
|---|---|---|
| `min_size` | 1 | one connection at cold start |
| `max_size` | 20 | documented previously as 8 — stale |
| `timeout` | 5s | documented previously as 3s |
| `prepare_threshold` | `None` | **prepared statements are disabled** — still true |
| `pool_recycle` | not set | no recycling configured |

The ceiling is 20, not the documented 8, so the old "only 2 concurrent analytics requests fit"
arithmetic no longer applies; on the current value a 4-query endpoint allows 5 concurrent
requests. That is arithmetic over the source values, not a load test — no load test was run.

### 4.3 Index coverage

156 indexes exist in schema `dcc` (counted in §2.3). The audit's "missing index" list targets the
legacy handler's tables and query shapes; whether each is still missing was **not** re-checked, so
that list is not reproduced here as current fact. Settling it means `EXPLAIN` on the queries the
`/v2` handlers actually issue.

### 4.4 RLS overhead

Every tenant-scoped table carries forced RLS keyed on
`tenant_id = nullif(current_setting('dcc.tenant_id',true),'')::uuid`, and the handlers also filter
by `tenant_id`. The redundant predicate is deliberate defence in depth. No CPU-cost measurement
was taken; earlier wording that it "adds CPU overhead to every query plan" is unquantified here.

---

## 5. Architecture Metrics

### 5.1 Dependencies (`pyproject.toml`)

| Category | Count | Packages |
|---|---|---|
| Runtime | 3 | `fastapi>=0.110`, `uvicorn>=0.27`, `cryptography>=42` |
| Optional `postgres` | 1 | `psycopg[binary,pool]>=3.2,<4` |
| Optional `tracing` | 4 | `opentelemetry-api`, `-sdk`, `-exporter-otlp-proto-grpc`, `-exporter-jaeger` |
| Optional `test` | 6 | `psycopg`, `psutil`, `pytest`, `pyyaml`, `hypothesis`, `httpx` |
| Optional `e2e` / `checkov` / `fuzz` | 3 | `playwright`, `checkov`, `atheris` |
| Build | 1 | `setuptools>=68` |

Earlier revisions claimed "0 runtime dependencies, pure Python stdlib". False: the served app is
FastAPI on uvicorn, and `cryptography` is required for API-key handling.

### 5.2 API surface

* 29 `/v2` paths on `dcc.api_async:app`; 37 routes including `/healthz`, `/readyz`, `/metrics`,
  `/openapi.json`, `/docs`, `/redoc` and `/`.
* Authentication is **enforced by default**; `DCC_ALLOW_ANONYMOUS=true` is an explicit, logged
  opt-out (`src/dcc/api_async.py:516`, `:597`).
* 11 routes accept POST: `/v2/cache/invalidate` and ten compute endpoints that take a request body
  (`/v2/economics/tco`, `/v2/economics/tco/compare`, three `/v2/forecast/*`, five
  `/v2/optimize/*`). They compute over supplied inputs; none actuates infrastructure —
  `/healthz` returns `execution_permitted: false`.
* Legacy `/v1` handler: `src/dcc/api.py`, unmounted, reachable only via
  `scripts/run-local.py --legacy`.

### 5.3 Security posture

| Feature | Status | Evidence |
|---|---|---|
| Tenant isolation | Forced RLS on all 52 tenant-scoped tables | `/readyz` → `tenant_rls: ok`, `tenant_rls_unprotected: 0`; `ISO27001-A.9.4.1` PASS |
| Read-only operation | No actuation endpoint | `/healthz` → `execution_permitted: false` |
| Credential strength | 256-bit keys stored as SHA-256 digests | `PCI-8.2` measurement |
| Audit chain | `evidence_events` hash chain verified | `PCI-10.1` PASS |
| TLS to Postgres | **not satisfied** on this cluster (`ssl = off`) | `HIPAA-164.312(e)(1)` FAIL |
| MFA | **not implemented** | `SOC2-CC6.1` NOT_ASSESSED on the MFA half |
| Credential expiry | only via the API-key store; `DCC_API_KEYS` cannot express `expires_at` | `SOC2-CC6.2` |

`/v2/compliance/scan` on 2026-10-26: `{"total": 16, "by_status": {"fail": 5, "not_assessed": 7,
"pass": 4}}`, `configuration_gaps.affected_controls: 0`.

---

## 6. CI/CD

### 6.1 What the pipeline runs (`ci.yml`)

* Matrix **3.11 / 3.12 / 3.13** (`fail-fast: false`), 10-minute job timeout.
* Installs `-e ".[test,checkov]"`.
* Builds the database from `database/schema.sql` plus all 12 migrations with `ON_ERROR_STOP=1`,
  then seeds it with `demo_seed.sql`.
* Runs the pytest suite with the four documented exclusions under `coverage run`, then
  `coverage report -m` / `coverage xml`, uploading the XML from the 3.12 leg.
* **The test step is blocking.** It used to be `continue-on-error: true`, justified by the
  636-failure backlog; `ci.yml:103-111` records the removal and the reason.
* `HYPOTHESIS_PROFILE=ci` keeps fuzzing at `max_examples=100` rather than the default 1,000.

Other workflows: `integration.yml` (single-job suite run), `security.yml`, `benchmark.yml`,
`iac-cicd.yml`, `iac-release.yml`, `release.yml`, `soc-cicd.yml`.

### 6.2 Git history

156 commits at `4375603`; the first is `dd4ab1f Prepare initial public release`, 2026-09-28.
Earlier revisions described "5 commits" and listed five SHAs. That snapshot is far behind and is
dropped rather than kept as a stale list.

---

## 7. Domain Coverage

Per-file LOC, measured 2026-10-26.

### 7.1 Adapters — 13 files, 7,243 LOC

`meter.py` 1,002 · `container.py` 963 · `proxmox.py` 791 · `hypervisor.py` 785 · `epms.py` 713 ·
`oem.py` 609 · `utility.py` 534 · `bms.py` 489 · `cmms.py` 410 · `registry.py` 408 ·
`cloud.py` 263 · `weather.py` 226 · `__init__.py` 50

### 7.2 Economics — 10 files, 8,058 LOC

`estimates.py` 1,312 · `prices.py` 1,241 · `tco.py` 1,156 · `tariffs.py` 1,046 ·
`scenarios.py` 791 · `reconciliation.py` 725 · `budget.py` 696 · `allocation.py` 512 ·
`unit.py` 389 · `__init__.py` 190

### 7.3 Forecasting — 10 files, 4,769 LOC

`drift.py` 713 · `features.py` 619 · `price.py` 594 · `capacity.py` 561 · `maintenance.py` 548 ·
`failure.py` 498 · `backtest.py` 452 · `load.py` 343 · `calibration.py` 328 · `__init__.py` 113

### 7.4 Validation — 6 files, 6,528 LOC

`boundaries.py` 1,762 · `schema.py` 1,589 · `consistency.py` 1,368 · `units.py` 1,069 ·
`intervals.py` 543 · `__init__.py` 197

### 7.5 Quality and provenance

`quality/` (4 files, 1,296 LOC): `anomaly.py` 532 · `engine.py` 380 · `freshness.py` 366 ·
`__init__.py` 18
`provenance/` (3 files, 670 LOC): `tracker.py` 469 · `evidence.py` 172 · `__init__.py` 29

---

## 8. Recommendations

Ordered by what the measurements above show. Items from the previous revision that are already
done are removed, not re-listed.

### 8.1 P0

1. **`tests/e2e/conftest.py` adopts a foreign process.** The `api_server` fixture treats an open
   port as "server ready" and never starts the v2 app. Start it unconditionally, or verify a `/v2`
   handshake, so a legacy handler on 8790 cannot masquerade as the application. This explains 15
   of the 16 known failures (§3.3).
2. **`tests/iac-visual` baselines are incomplete** (`test_all_iac_views_have_baselines`). Generate
   them or delete the check; today it is a permanent red test in an excluded directory.
3. **Enable prepared statements** — `prepare_threshold: None` at `src/dcc/api_async.py:279`.
4. **Set `pool_recycle`** — no recycling configured (`src/dcc/api_async.py:271-289`).

### 8.2 P1

5. **Measure the `/v2` query patterns.** The only query-count audit covers the retired `/v1`
   handler (§4.1).
6. **Re-check index coverage against `/v2` queries** with `EXPLAIN`, instead of carrying the `/v1`
   list forward (§4.3).
7. **Settle `tests/iac-performance`:** fix and re-include it, or record it as permanently
   out-of-gate with a reason. Its result is currently unmeasured (§3.3).

### 8.3 P2

8. **Add the lint/type gates you want as controls.** `ci.yml` runs coverage but neither `ruff` nor
   `mypy` on this tree.
9. **Publish pool metrics.** `dcc_database_connections` has no producer, which is why that
   dashboard panel is empty.

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Basis |
|------|------------|--------|-------|
| Gate passes while `tests/iac-performance` stays unmeasured | High | Medium | §3.3 — 86 tests never run in CI |
| `tests/e2e` cannot detect a broken deployment | High | High | §3.3 — fixture adopts any listener on 8790 |
| Prepared statements disabled | Medium | Medium | §4.2 — `prepare_threshold: None` |
| No connection recycling | Medium | Medium | §4.2 — `pool_recycle` unset |
| Postgres link is cleartext (this cluster) | High | High | `HIPAA-164.312(e)(1)` FAIL |
| MFA absent, so `SOC2-CC6.1` cannot pass | Certain | Medium | §5.3 |
| Compliance control misjudges the latency alert | Medium | Low | `SOC2-CC7.1` reports `DCCHighLatency` over `api_request_duration_seconds_bucket` as unexported while the app emits that series — `src/dcc/compliance/observables.py:1252-1276` does not model histogram `_bucket` suffixes |

---

## 10. Conclusion

At `4375603` the suite is **green, blocking, and database-backed** in its CI gate scope: 7,531
passing, 9 capability skips, 0 failures, reproduced twice on 2026-10-26. That is the strongest
quality signal in this document, and it is not the signal this file carried a week ago.

What remains unestablished: `tests/iac-performance` (86 tests) was not run here; the 16 failures
outside the gate trace to a test fixture and a missing baseline rather than to product defects;
and no load or latency measurement of the served `/v2` API exists — §4 is still an audit of a
retired handler. Those gaps are named rather than filled with old numbers.

---

*Measured 2026-10-26 on `4375603`. Commands are quoted inline; re-run them before quoting this
file's numbers elsewhere.*
