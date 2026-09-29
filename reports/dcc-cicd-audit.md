# CI/CD Pipeline Audit — Data Center Commander

**Date:** 2026-09-29  
**Scope:** `.github/workflows/ci.yml` and surrounding project infrastructure  
**Auditor:** Automated CI/CD gap analysis

---

## 1. Current Pipeline Summary

| Aspect | Current State |
|---|---|
| Workflow file | `.github/workflows/ci.yml` (single file) |
| Triggers | `pull_request` (all), `push` (main only) |
| Jobs | 1 (`tests`) |
| OS matrix | `ubuntu-latest` only |
| Python matrix | `3.11` only |
| Steps | checkout → setup-python → unittest → bash -n |
| Timeout | 10 min (job-level) |
| Permissions | `contents: read` (minimal — good) |
| Caching | None |
| Artifacts | None |
| Secrets | None |

### What the pipeline does well
- Minimal permissions (`contents: read`) — follows least-privilege principle.
- Runs on both PR and push to main.
- Validates shell scripts with `bash -n`.
- Uses `actions/checkout@v4` and `actions/setup-python@v5` (current major versions).
- 10-minute timeout prevents runaway jobs.

---

## 2. Gap Analysis

### 2.1 Missing Test Coverage

| Gap | Severity | Detail |
|---|---|---|
| **No code coverage** | Medium | No `coverage.py`, no `pytest-cov`, no Codecov upload. Tests exist but coverage is unmeasured. |
| **No integration tests** | High | All tests use mocks/fakes. No PostgreSQL service container exercises real queries, RLS policies, or migrations. |
| **No UI/JavaScript tests** | Medium | `ui/` contains 6 JS files (index.html, onboarding.js, topology.js, azure-prices.js, placement-comparison.js, placement-scenarios.js) with zero automated tests. |
| **No database migration tests** | Medium | 4 migrations in `database/migrations/` are never applied in CI to verify they work. |
| **No API contract tests against live server** | Medium | Tests call handler methods directly; no HTTP-level integration test starts the server and hits endpoints. |
| **No shell script tests** | Low | `bash -n` checks syntax only; no `shellcheck`, no `bats`, no execution tests for `db-seed-demo.sh` / `db-reset-demo.sh`. |

### 2.2 Missing Security Scanning

| Gap | Severity | Detail |
|---|---|---|
| **No SAST (Static Application Security Testing)** | High | No Bandit, no Semgrep, no CodeQL. The project handles tenant isolation and RLS — security-relevant code should be scanned. |
| **No dependency vulnerability scan** | High | No `pip-audit`, no `safety`, no Dependabot config. `psycopg[binary,pool]` is a dependency with known CVE history. |
| **No secret scanning** | Medium | No `gitleaks`, no GitHub secret scanning enforcement. |
| **No container image scan** | Low | No Dockerfile exists yet, but when one is added, Trivy/Grype should be included. |
| **No license compliance scan** | Low | AGPL-3.0 project; no `fossa`, no `license-checker`. |

### 2.3 Missing Multi-OS / Multi-Version Testing

| Gap | Severity | Detail |
|---|---|---|
| **Single OS** | Medium | Only `ubuntu-latest`. No `macos-latest`, no `windows-latest`. Shell scripts use `bash` — Windows compatibility untested. |
| **Single Python version** | Medium | Only Python 3.11. Project requires `>=3.11`; should test 3.11, 3.12, 3.13 to catch version-specific issues. |
| **No PostgreSQL version matrix** | Low | Schema targets PostgreSQL 14+; no testing against PG 14, 15, 16, 17. |

### 2.4 Missing Code Quality Gates

| Gap | Severity | Detail |
|---|---|---|
| **No linter** | Medium | No `ruff`, `flake8`, `pylint`. `api.py` is 476 lines with complex routing — linting would catch issues. |
| **No formatter check** | Medium | No `black`, no `ruff format --check`. |
| **No type checking** | Medium | No `mypy`, no `pyright`. Code uses type hints (`dict[str, list[str]]`, `tuple[bool, dict[str, str]]`) but they are unchecked. |
| **No import sorting** | Low | No `isort`, no `ruff --select I`. |
| **No pre-commit hooks** | Low | No `.pre-commit-config.yaml`. |

### 2.5 Missing Build & Packaging Verification

| Gap | Severity | Detail |
|---|---|---|
| **No package build test** | Medium | No `python -m build`, no wheel/sdist verification. `pyproject.toml` uses setuptools but build is never tested. |
| **No install test** | Medium | No verification that `pip install .` or `uv sync` works from a clean state. |
| **No `uv.lock` verification** | Low | `uv.lock` exists but CI doesn't verify it's up-to-date. |

### 2.6 Missing Benchmarking

| Gap | Severity | Detail |
|---|---|---|
| **No performance benchmarks** | Medium | No `pytest-benchmark`, no `cProfile` runs, no API latency measurement. The API has complex queries (topology BFS, analytics rollups) that should have baseline performance. |
| **No load testing** | Low | No `locust`, no `k6`, no `wrk`. Read-only API should handle concurrent tenant queries. |
| **No query performance tests** | Low | No `EXPLAIN ANALYZE` verification that queries use indexes. |
| **No regression benchmarks** | Low | No stored baselines to detect performance regressions. |

### 2.7 Missing CI/CD Best Practices

| Gap | Severity | Detail |
|---|---|---|
| **No dependency caching** | Low | No `actions/cache` for pip/uv — slower builds. |
| **No test result upload** | Low | No `actions/upload-artifact` for test results or coverage reports. |
| **No concurrency controls** | Low | No `concurrency` group — parallel runs on same PR can conflict. |
| **No workflow for releases** | Medium | No release automation, no PyPI publishing, no GitHub release creation. |
| **No stale issue/PR automation** | Low | No `stale` bot, no `actions/stale`. |
| **No PR labeling automation** | Low | No `actions/labeler`. |
| **No branch protection enforcement** | Low | No check that CI passes before merge (repo settings, not workflow). |

---

## 3. Recommended Priority Matrix

| Priority | Gap | Effort | Impact |
|---|---|---|---|
| **P0** | Add PostgreSQL service container for integration tests | Medium | High — validates real DB behavior |
| **P0** | Add Bandit SAST scan | Low | High — security-critical project |
| **P0** | Add `pip-audit` dependency scan | Low | High — supply chain security |
| **P1** | Add Python version matrix (3.11, 3.12, 3.13) | Low | Medium — catch version issues |
| **P1** | Add OS matrix (ubuntu, macos, windows) | Low | Medium — cross-platform confidence |
| **P1** | Add `ruff` lint + format check | Low | Medium — code quality |
| **P1** | Add `mypy` type checking | Medium | Medium — catch type errors |
| **P1** | Add code coverage (`coverage.py` + Codecov) | Low | Medium — measure test quality |
| **P1** | Add `shellcheck` for shell scripts | Low | Medium — script reliability |
| **P2** | Add `pytest-benchmark` for API endpoints | Medium | Medium — performance baseline |
| **P2** | Add package build verification (`python -m build`) | Low | Medium — packaging confidence |
| **P2** | Add pre-commit hooks | Low | Medium — local quality gate |
| **P2** | Add Dependabot configuration | Low | Medium — automated dep updates |
| **P2** | Add concurrency group to workflow | Low | Low — CI efficiency |
| **P2** | Add dependency caching | Low | Low — faster builds |
| **P3** | Add UI/JavaScript tests (Jest/Playwright) | High | Low — UI is secondary |
| **P3** | Add load testing (Locust/k6) | High | Low — not yet production |
| **P3** | Add release automation | Medium | Low — pre-release stage |
| **P3** | Add license compliance scan | Low | Low — AGPL is simple |

---

## 4. Recommended Target Workflow Structure

```
.github/workflows/
├── ci.yml                    # Main CI: lint, type-check, test (matrix)
├── security.yml              # Bandit, pip-audit, CodeQL, gitleaks
├── integration.yml           # PostgreSQL service, migration tests, API contract
├── benchmark.yml             # pytest-benchmark, query performance
├── release.yml               # Build, tag, publish to PyPI
└── dependabot.yml            # Automated dependency updates
```

### Suggested `ci.yml` matrix strategy:
```yaml
strategy:
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    python-version: ["3.11", "3.12", "3.13"]
```

### Suggested security workflow:
```yaml
- uses: github/codeql-action/analyze
- run: pip install bandit && bandit -r src/
- run: pip install pip-audit && pip-audit
- uses: gitleaks/gitleaks-action@v2
```

---

## 5. Summary

The current CI pipeline is **minimal but functional** — it runs unit tests and validates shell syntax on a single OS/Python version. For a project that handles **tenant isolation, row-level security, and energy/cost data**, the lack of security scanning and integration testing is the most critical gap.

**Top 3 immediate actions:**
1. Add PostgreSQL service container with integration tests
2. Add Bandit + pip-audit security scanning
3. Expand to multi-Python (3.11/3.12/3.13) and multi-OS matrix

The project has solid test *design* (contract tests, mock-based unit tests) but the CI *infrastructure* to validate those tests against real dependencies and multiple environments is missing.
