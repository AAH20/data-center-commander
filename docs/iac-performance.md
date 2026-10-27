# IaC performance suite (`tests/iac-performance`)

Status: **green on this machine and fast enough for a blocking gate** — 92 tests,
46-75 s wall clock depending on machine load. It was 86 tests, 50 failed /
21 passed / 15 skipped, 2,647 s (44 min) and excluded from every CI job. This
document records what the suite measures, why it is built the way it is, what
each budget is for, and what is still not measured.

Re-run it with:

```bash
export PYTHONPATH=src
.venv/bin/python -m pytest tests/iac-performance -q
```

It needs `terraform` (verified 1.16.6), `opa` (verified 1.21.0) and `checkov`
(verified 3.3.29) on `PATH`, and nothing else — no database, no cloud account,
no network. `DCC_DATABASE_URL` is irrelevant to this directory; the suite passes
without it set.

## What the suite measures, and what it refuses to measure

Every test asserts a **structural** property read out of the tool's own output
before it looks at a clock:

| Stage | Structural assertion | Fails when |
| --- | --- | --- |
| `terraform plan` | `Plan: N to add` equals the generated resource count | terraform planned nothing, or planned the wrong thing |
| `terraform validate` | `"valid": true` in the `-json` document, and `valid: false` + diagnostics for a deliberately broken config | validate stops reporting, or always answers valid |
| drift | `plan -detailed-exitcode` exits 0 with no drift, then 2 with `N to change` after the config changes | drift is not detected (or exit 2 is mistaken for an error) |
| `state list` | exact address count and the `terraform_data.` prefix, after a real `apply` | an empty state file is being timed |
| checkov | `resource_count` equals the config size and `checks_evaluated > 0` | the scan matched no check — the failure that made three old tests vacuous |
| OPA | the deny set grows for a non-compliant input, and a named control appears in it | the policy stops reading its input |

The clock is the **secondary** assertion. A wall-clock threshold on a 50 ms
operation is decided by the machine, not the code: set it high and nothing can
fail, set it at the measurement and it flakes on a shared runner. Every budget
below is therefore sized against a specific failure mode (a provider download, a
cloud API call, a Prisma Cloud round trip) rather than against the fastest
measurement: 15x or more over the idle measurement, and 3x or more over the
worst measurement taken while four test workers were competing for the CPU.

## Verified failure groups in the old suite

Baseline: 50 failed, 21 passed, 15 skipped, 2,647 s. The groups below were
reproduced from the committed code (`git archive HEAD tests/iac-performance`)
in a scratch tree, not inferred:

| Group | Tests | What actually happened (measured) |
| --- | --- | --- |
| A. provider download inside `init` | `test_init_*` | Generated configs were `aws_instance`, so `init` fetched `registry.terraform.io/hashicorp/aws`: **55,655 ms** against a 30,000 ms threshold. `init_medium` (57,190 ms vs 60 s) and `init_large` (56,045 ms vs 120 s) *passed* — the only reason the suite had 2 passing terraform tests is that those two thresholds happened to be larger than the download. |
| B. no AWS credentials | every `plan`/`apply`/`refresh`/drift test | `plan` died in **14,821 ms** with `No valid credential sources found` / `failed to refresh cached credentials, no EC2 IMDS role found`. Not fixable by a threshold; there is no account on the runner. |
| C. no state was ever written | 3 × `state_list` | `terraform state list` returned `No state file was found!` — the tests never ran `apply`, so the state they timed did not exist. All 3 failed. |
| D. OPA policy path | 14 policy tests (the 14 of 15 skips) | `PROJECT_ROOT` was computed as `parents[2]` from `fixtures/conftest.py`, resolving to `tests/policies/rego` instead of `policies/rego`. Every test skipped with `Policy not found`. Behind that skip sat a second defect: `opa eval <file.rego>` does not load the file — the trailing argument is the query — so the wrapper would have "passed" against a parse error. |
| E. e2e pipeline | 12 | `validate` ran before `init`, which fails with `Missing required provider`; checks were also vacuous (`scan_ms` computed and discarded). |
| F. checkov phone-home | 3 flaky (found in the inherited work, not the baseline) | `non_compliant[small]` 47,230 ms vs 45,000; `[medium]` 90,166 ms vs 60,000; `scaling[1]` 50,816 ms vs 30,500 — the same scan measured 1.2 s a minute earlier. Cause: checkov calls Prisma Cloud for policy metadata on every run. |

Verdicts: A, C, D, E were **wrong setup** (fixed in the fixtures/helpers); B is a
**missing capability** (kept as one explicitly-reasoned skip); F was **wrong
setup plus a budget that could not catch it** (fixed at the harness level, plus a
deterministic assertion).

## Why the built-in terraform provider

Configurations are generated from `terraform_data` resources
(`terraform.io/builtin/terraform`) instead of `aws_instance`.

* `init` costs **20-24 ms** and downloads nothing (vs 55-56 s for the AWS
  provider), so `init` is measurable offline.
* `apply` writes real local state, so drift, refresh-over-state and
  `state list` test the real thing. Nothing is created in any cloud.
* The AWS path still exists (`generate_terraform_config(provider="aws")`) and is
  exercised by `test_apply_aws_config_requires_credentials`, which skips unless
  `TF_PERF_TEST_CLOUD=1`. That is the one capability this directory cannot
  provide: a plan of `aws_instance` resources calls STS/EC2 IMDS, and there are
  no credentials on a CI runner.

`terraform` subprocesses run with `TF_IN_AUTOMATION=1`, `CHECKPOINT_DISABLE=1`,
`TF_INPUT=0` and a shared `TF_PLUGIN_CACHE_DIR`, so a prompt can never hang a
build and a cloud provider is downloaded at most once per machine.

## Why checkov runs with `--skip-download`

checkov asks Prisma Cloud for policy metadata before scanning unless
`--skip-download` is passed. Measured on a one-resource config: **16.17 s wall
for 2.49 s of user CPU** with the call, **4.64 s** with `--skip-download`, and
byte-identical findings (`summary` and `resource_count` compared document by
document). The call's latency varied from 5 s to 90 s, which is what made three
timing assertions fail in one run and pass in the next.

`utils/checkov_utils.checkov_env()` additionally points `HTTP(S)_PROXY` at a
closed loopback port, so an accidental egress attempt fails in milliseconds
instead of hanging; with the proxies removed and the flag in place the same
scan took 3.2 s, i.e. the flag is the fix and the proxy is a tripwire.
`TestCheckovOfflineContract` asserts both, and fails in ~2.5 s if either is
dropped.

## Measured costs

Medians on this machine (macOS, arm64), from
`utils.terraform_utils.TerraformRunner` and `utils.rego_utils.OpaRunner`:

| Operation | 5 resources | 25 resources | 100 resources | Budget |
| --- | --- | --- | --- | --- |
| terraform init | 23.6 ms | 20.5 ms | 23.0 ms | 3,000 ms |
| terraform plan | 29.4 ms | 34.1 ms | 49.9 ms | 3,000 ms |
| terraform validate | 26.5 ms | 26.5 ms | 35.2 ms | 2,000 ms |
| terraform apply | 47.3 ms | 111.1 ms | 435.0 ms | 10,000 ms |
| terraform refresh | 31.4 ms | 39.6 ms | 58.1 ms | 3,000 ms |
| drift plan (`-detailed-exitcode`) | 29.1 ms | 36.7 ms | 58.4 ms | 3,000 ms |
| terraform state list | 24.6 ms | 26.2 ms | 27.4 ms | 1,500 ms |
| checkov scan | ~1.2 s | ~1.3 s | ~1.5 s | 25,000 ms |
| `opa eval` (one invocation) | 13.9-33.0 ms, median 15.2 ms | | | 500 ms |
| `opa eval` query metric | 186,125 ns median | | | 1,000,000 ns |

Scaling budgets are `floor + per-resource` (`1,000 + 15n` for terraform and
`500 + 10n` for the full pipeline) so a super-linear regression fails while a
slow machine does not. checkov does not get a per-resource budget, because its
cost is flat in resource count: the scaling property is asserted as a ratio
(`test_scan_cost_is_sublinear`, 1 vs 100 resources, threshold 5x) and the
absolute ceiling is set generously enough not to flake.

## Proving the assertions can fail

Timing assertions that cannot fail are worse than none, so each mechanism was
made to fail deliberately and then restored:

1. Removing `--skip-download` from `scan_directory` fails
   `TestCheckovOfflineContract` in 2.53 s with
   `scan_directory dropped --skip-download ...`.
2. Removing the no-egress proxy variables fails the same test in 3.22 s with
   `HTTP_PROXY is '': a checkov process with working egress can hang ...`.
3. The old suite itself demonstrates the terraform assertions: `init` at
   55,655 ms breaches a 30,000 ms budget, and `plan` fails with
   `No valid credential sources found`.
4. `test_scan_cost_is_sublinear` compares two real measurements (2621 ms for 1
   resource, 2321 ms for 100). Tightening its ratio from 5x to 0.5x makes it
   fail with `scan time grew 0.9x for 100x the resources`, so the assertion is
   live and its numbers are produced by checkov, not by a constant.

## Runtime

| State | Summary line | Wall clock |
| --- | --- | --- |
| baseline (committed code) | 50 failed, 21 passed, 15 skipped | 2,647 s (0:44:07) |
| after the fixture/provider/policy fixes | 3 failed, 87 passed, 1 skipped | 412.80 s (0:06:52) |
| after `--skip-download` + budgets sized to measurement | 91 passed, 1 skipped | 47.46 s |
| final, idle machine | 91 passed, 1 skipped | 45.39 s |
| final, machine busy with other test suites | 92 passed, 1 skipped | 63.94 s, 75.27 s on two runs |
| final, `pytest -n 4` | 91 passed, 1 skipped | 16.79 s |

What dominated each step:

* baseline: 53 terraform-backed tests, each paying a 55 s provider download (or
  a 15 s credential timeout) — ~44 min.
* inherited fixes: checkov still paid the Prisma Cloud round trip on every scan
  (~12 s each, occasionally 40-80 s), which was both 6.8 min of the runtime and
  the source of 3 flaky failures.
* now: 31 checkov invocations (25 in the compliance file, 6 in the e2e file)
  account for 56.1 s of the 74.5 s; the 39 terraform-backed tests together
  account for 11.8 s.

The same suite is 1.4-1.7x slower while other test suites are using the machine
(45.39 s idle, 63.94-75.27 s contended) — which is why the budgets are set
against contended measurements, not idle ones.

## Skips

Exactly one test skips, and it names a capability:

```
test_apply_aws_config_requires_credentials
  AWS credentials + registry access are not available in CI;
  set TF_PERF_TEST_CLOUD=1 on a credentialed machine to measure
  aws provider init/plan cost
```

Everything else that used to skip no longer can: the OPA policies exist and are
found, and the apply test runs against local state (`TF_PERF_TEST_APPLY` gate
removed; running `apply` on the built-in provider touches nothing).

## Adding this directory to the blocking CI gate

The suite is ready; the job setup is not, and `.github/` is out of scope here.
Two jobs matter:

* `.github/workflows/ci.yml` `test` job — installs `.[test,checkov]` (so checkov
  is present) but **not terraform or opa**. Adding `tests/iac-performance` to
  that step without also installing them would make 71 of the 92 tests *skip*
  rather than run — measured with `terraform` and `opa` removed from `PATH`:
  `22 passed, 71 skipped in 34.31s`, a green gate covering one fifth of the
  directory. It needs, in the same job:

  ```yaml
  - uses: hashicorp/setup-terraform@v3
    with: { terraform_version: "1.9.8" }
  - name: Install OPA
    run: |
      curl -sSfL -o /usr/local/bin/opa \
        https://github.com/open-policy-agent/opa/releases/download/v1.21.1/opa_linux_amd64_static
      chmod +x /usr/local/bin/opa
  ```

* `.github/workflows/soc-cicd.yml` `unit-tests` job already runs the directory
  as a matrix group (`tests/iac-performance`) but installs no checkov, terraform
  or opa, so every test in it skips: the group currently proves nothing.

With those three binaries present the directory is a 46-75 s blocking step and does
not need PostgreSQL. One operational note: the suite is parallel-safe (it uses
per-test temp directories, verified with `-n 4` in 16.8 s) and the budgets were
validated under four competing workers, but `-n auto` on a 2-core runner is the
shape most likely to produce a false timing failure — give this directory its
own job, or `-n 2`, rather than folding it into a matrix that is already busy.
