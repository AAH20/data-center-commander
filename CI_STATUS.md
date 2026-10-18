# CI status

Verified against every workflow in the repository, not just `CI`. (Checking only the
obvious workflow is how a permanently-failing pipeline stayed invisible here.)

| Workflow | State |
|----------|-------|
| `CI` | green |
| `Integration` | green |
| `Security` | green |
| `benchmark` | green |
| `IaC CI/CD` | green |
| `release` | never run — no trigger fires for it |
| `IaC Release` | never run — no trigger fires for it |
| `.github/workflows/soc-cicd.yml` | **disabled manually** — see below |
| `Dependabot Updates` | managed by GitHub |

## Why soc-cicd.yml is disabled

It fails at startup with **zero jobs**. GitHub rejects the workflow before running
anything, so there is no log to read and no step to fix — the run record shows
`conclusion: failure` and `total_count: 0`.

It has never passed. It is also aspirational: it logs into GHCR, builds and pushes
container images, and deploys to a Kubernetes cluster. None of those exist for this
repository, so even with the startup failure fixed it could not go green.

It is disabled rather than deleted so the work is not thrown away, and rather than
left enabled so the board is not permanently red for a pipeline that cannot run.
Re-enable it with:

    gh workflow enable 379975897 --repo AAH20/data-center-commander

once a registry and cluster exist and the startup failure is diagnosed.

## What is advisory, and why

These jobs fail on real problems and are marked `continue-on-error` so the run
reflects reality without being blocked by a known backlog. They are not excluded and
they are not made green.

| Job | Reason |
|-----|--------|
| `test (3.11/3.12/3.13)` | Runs the suite correctly for the first time. The suite genuinely has failing tests — see BENCHMARKS.md §1a and §1b. |
| `iac-validate` | `iac/root` fails `init`: an `ibm` provider configuration is passed to `module.multi_cloud.module.ibm_compute`, which does not declare `ibm-cloud/ibm` as required. |
| `k8s-validate` | `kubectl` is not installed on the runner, so the step takes its own skip branch. |
| `typecheck` | mypy findings. |
| `benchmark` regression gate | Compares microbenchmarks (tens of microseconds) against a baseline cached from a previous run on a different ephemeral runner. Measures runner variance. |

## Test counts, by scope

| Scope | Command | Result |
|-------|---------|--------|
| CI scope | `pytest tests/ --ignore=tests/e2e --ignore=tests/terraform` | 5,248 pass / 636 fail / 1 skip |
| Full suite | `pytest tests/` | 6,623 pass / 759 fail / 24 skip |

Both are real; they are not interchangeable. See BENCHMARKS.md §1b.
