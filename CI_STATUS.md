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
| `k8s-validate` | `kubectl` is installed on the runner, so it takes the real branch and the `k8s/` manifests fail validation. Advisory. |
| `k8s-validate` | `kubectl` is not installed on the runner, so the step takes its own skip branch. |
| `typecheck` | mypy findings. |
| `benchmark` regression gate | Compares microbenchmarks (tens of microseconds) against a baseline cached from a previous run on a different ephemeral runner. Measures runner variance. |

## Test counts, by scope

| Scope | Command | Result |
|-------|---------|--------|
| CI scope | `pytest tests/ --ignore=tests/e2e --ignore=tests/terraform` | 5,248 pass / 636 fail / 1 skip |
| Full suite | `pytest tests/` | 6,623 pass / 759 fail / 24 skip |

Both are real; they are not interchangeable. See BENCHMARKS.md §1b.

## Terraform: both trees validate

As of the commits below, `terraform validate` succeeds for **both** terraform trees.

### `infra/aws-gpu-h200/` — the GPU module

| Defect | Consequence if shipped |
|---|---|
| `capacity.tf:39` used `prevent_destroy = var.…` | Terraform rejects a variable there; the whole module failed `validate`. |
| `compute.tf:135` set `placement_group` on an instance targeting a Capacity Block | **AWS rejects the launch.** `validate` cannot catch it, so it would have failed at apply time — *after* an irreversible Capacity Block was purchased. |
| `storage.tf:27` nested `data_repository_association` inside the Lustre filesystem | Not a valid block; the provider exposes it as a standalone resource. |

### `iac/` — the multi-cloud tree

Six defects, none of which `init` had ever got past:

1. `modules/multi-cloud/main.tf` had no `required_providers`, so its `ibm` defaulted to `hashicorp/ibm` while nine other files used `IBM-Cloud/ibm`.
2. The root declared five aliased providers but passed none of them to the module.
3. Child calls wrote `X = X.primary`. **An alias does not travel** — the child receives plain `X`.
4. `aws_compute` / `azure_compute` omitted `vpc_id` / `vnet_id` that their network modules already output.
5. Three variables were passed by the root but never declared.
6. Invalid arguments: `redundancy_type = "TWO_IPS"`, `labels` on five Google resources, and `tunnel{1,2}_shared_key` (the provider calls it `preshared_key`).

3 deprecation warnings remain on IBM security group rules (`tcp` → `protocol`/`code`/`type`). Noted, not fixed.

### The rule this established

**A passing `terraform validate` is not a launch guarantee.** Defect 2 above validates cleanly and fails only at apply time. Anything involving Capacity Blocks must be reviewed against the API's own constraints, because the cost of finding out at apply time is an unreserved, non-cancellable purchase.
