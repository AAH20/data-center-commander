# Compliance control mapping: phantom variables → observable state

Every built-in control in `src/dcc/compliance/controls.py` used to decide its verdict
by reading an environment variable. Most of those variables appeared nowhere in the
served application, so an operator could set one, change nothing about the running
system, and watch the compliance report turn green.

This document records, per control, what it used to read, what it measures now, and —
the part that matters — whether its status can actually move.

## Summary

| | Count |
|---|---|
| Controls total (unchanged) | **16** |
| Controls that read at least one environment variable **the application never consults** | **15 of 16** |
| Distinct phantom variables removed | **15** |
| Repointed at a measured fact (PASS ⇄ FAIL possible) | **12** |
| Now `NOT_ASSESSED` by design (no observable exists) | **4** |
| Controls that can neither pass nor fail (always `NOT_ASSESSED`) | **4** |

Two reconciliations with the original report, stated plainly:

* The brief counts **13** controls on phantom variables. The measured number in the
  code before this change was **15**. `SOC2-CC6.1` had already been repointed at the
  authentication posture but still read `DCC_MFA_ENABLED` for its second half (13),
  and `ISO27001-A.12.4.1` read `DCC_LOG_LEVEL`, which `src/dcc/logging.py` *does*
  consume, so it was not strictly phantom while still proving nothing about logging
  (14). `SOC2-CC6.1`'s MFA read is the fifteenth. Counting the way the brief does
  (excluding the already-repointed CC6.1 and the consumed `DCC_LOG_LEVEL`) gives 13.
* The phantom variables in the code immediately before this change were these
  **15**: `DCC_MFA_ENABLED`, `DCC_SESSION_TIMEOUT_MINUTES`, `DCC_AUDIT_ENABLED`,
  `DCC_MONITORING_ENABLED`, `DCC_IR_PLAN_PATH`, `DCC_RBAC_ENABLED`,
  `DCC_SECURITY_POLICY_PATH`, `DCC_NETWORK_SEGMENTED`, `DCC_ENCRYPTION_AT_REST`,
  `DCC_MIN_PASSWORD_LENGTH`, `DCC_AUDIT_TRAIL_ENABLED`, `DCC_UNIQUE_USER_IDS`,
  `DCC_TLS_ENFORCED`, `DCC_ACCOUNT_MANAGEMENT`, `DCC_AUDIT_POLICY_PATH` — plus
  `DCC_AUTH_ENABLED`, which `SOC2-CC6.1` had already stopped reading (it defaults to
  "true" and is consulted by nothing, so it was the clearest case of the defect).

## How a status is decided now

Findings are produced from `dcc.compliance.observables.Measurement`, which carries a
three-valued verdict:

| Verdict | Finding | Meaning |
|---|---|---|
| `True` | `PASS` | the fact was measured and holds |
| `False` | `FAIL` | the fact was measured and is violated |
| `None` | `NOT_ASSESSED` | the fact cannot be measured from inside this application; the reason is in the message |

`NOT_ASSESSED` is a new `ComplianceStatus` member. The scanner collapses multiple
findings **FAIL > ERROR > NOT_ASSESSED > PASS**, so a control that measured half of its
requirement cannot present as complete. `ComplianceReport.compliance_score` counts
`NOT_ASSESSED` with `FAIL` in the numerator's complement: sixteen unmeasured controls
score 0%, not 100%.

`/v2/compliance/scan` previously reported `configuration_gaps.affected_controls: 16`;
it now reports `0`, because no control reads a variable the application ignores.

## Per-control mapping

`Status can change?` answers whether the status is a function of system state today.

| # | Control | Framework | OLD — variable read (phantom) | NEW — observable | Status can now change? |
|---|---|---|---|---|---|
| 1 | `SOC2-CC6.1` | SOC 2 | `DCC_AUTH_ENABLED` (never consulted; defaulted "true"), `DCC_MFA_ENABLED` | `dcc.security.posture.auth_posture()` — the `DCC_ALLOW_ANONYMOUS` + `DCC_API_KEYS` the auth middleware really enforces. MFA half → `NOT_ASSESSED`: no factor is verified anywhere and nothing populates the `mfa_verified` claim `security.authz` can require | **Yes** — auth half PASS ⇄ FAIL (anonymous ⇒ CRITICAL fail; enforced with zero keys ⇒ lockout fail). Overall status is never PASS while MFA is unimplemented |
| 2 | `SOC2-CC6.2` | SOC 2 | `DCC_SESSION_TIMEOUT_MINUTES` | Credential expiry. Live `ApiKeyStore` if this process holds one (`expires_at` per key), otherwise the `DCC_API_KEYS` loader, which registers every entry with `expires_at=None` | **Yes**, but only via the store branch. From `DCC_API_KEYS` alone it is permanently FAIL: that format cannot express an expiry |
| 3 | `SOC2-CC6.3` | SOC 2 | `DCC_AUDIT_ENABLED` | Access/authentication/permission `event_type`s present in `dcc.evidence_events` (RLS-scoped per tenant) — the evidence a review reads | **Yes** — FAIL ⇄ PASS proven (fixture-only events FAIL; one `auth.*` event PASSes) |
| 4 | `SOC2-CC7.1` | SOC 2 | `DCC_MONITORING_ENABLED` | Alert rules parsed from `monitoring/prometheus` + `monitoring/iac/prometheus`; every rule over a `dcc_`/`api_`/`iac_` metric must reference a series the exporters or the app actually publish | **Yes** — FAIL ⇄ PASS proven against scratch rule trees with real files |
| 5 | `SOC2-CC7.2` | SOC 2 | `DCC_IR_PLAN_PATH` | `dcc.incidents` exists with `opened_at`/`detected_at`/`mitigated_at`/`resolved_at`/`incident_commander` | **Yes** — PASS ⇄ FAIL proven (dropping `detected_at` FAILs) |
| 6 | `ISO27001-A.9.4.1` | ISO 27001 | `DCC_RBAC_ENABLED` | `pg_class`/`pg_policy`: every `dcc` table with `tenant_id` has ROW LEVEL SECURITY **enabled and forced** with ≥1 policy (52 tables, re-counted 2026-10-26) | **Yes** — PASS ⇄ FAIL proven (`DISABLE ROW LEVEL SECURITY`, `NO FORCE`, `DROP POLICY`) |
| 7 | `ISO27001-A.12.4.1` | ISO 27001 | `DCC_LOG_LEVEL` (consumed by `logging.py`, but a level name is not a log record) | Recorded events exist and every row carries `actor_ref` — an event that does not say who acted is not an audit record | **Yes** — PASS ⇄ FAIL proven (a null `actor_ref` FAILs) |
| 8 | `ISO27001-A.14.1.1` | ISO 27001 | `DCC_SECURITY_POLICY_PATH` | **`NOT_ASSESSED`** — whether requirements were *analysed* is a document-review judgement. The finding reports which governance documents exist (`docs/SECURITY_AND_GOVERNANCE.md`, …) and asserts nothing about them | **No** — always `NOT_ASSESSED` |
| 9 | `PCI-1.1` | PCI DSS | `DCC_NETWORK_SEGMENTED` | **`NOT_ASSESSED`** — segmentation is enforced by network devices this process cannot query. NetworkPolicy manifests in the repo are listed as *declared* configuration, explicitly not evidence they are applied | **No** — always `NOT_ASSESSED` |
| 10 | `PCI-3.4` | PCI DSS | `DCC_ENCRYPTION_AT_REST` | **`NOT_ASSESSED`** — at-rest encryption is a property of the storage volume; no SQL or process inspection reports it. The finding also measures field-level encryption call sites (currently 0 outside its own module), so no column is shown to be ciphertext | **No** — always `NOT_ASSESSED` |
| 11 | `PCI-8.2` | PCI DSS | `DCC_MIN_PASSWORD_LENGTH` | Credential strength: every `DCC_API_KEYS` entry must be a 256-bit key stored as a SHA-256 digest. This deployment has no password authentication, so a password-length setting was measuring a mechanism that does not exist | **Yes** — PASS ⇄ FAIL proven (truncated/plaintext entry FAILs, no keys FAILs) |
| 12 | `PCI-10.1` | PCI DSS | `DCC_AUDIT_TRAIL_ENABLED` | `dcc.provenance.evidence.verify_evidence_chain` recomputed over the stored rows: `event_hash` per row and `previous_hash` linkage per tenant | **Yes** — PASS ⇄ FAIL proven (payload edit ⇒ `event_hash_mismatch`; deleted middle row ⇒ `chain_link_mismatch`) |
| 13 | `HIPAA-164.312(a)(1)` | HIPAA | `DCC_UNIQUE_USER_IDS` | Each credential hash is unique and resolves to exactly one existing tenant in `dcc.tenants` | **Yes** — PASS ⇄ FAIL proven (shared hash, unknown tenant id) |
| 14 | `HIPAA-164.312(e)(1)` | HIPAA | `DCC_TLS_ENFORCED` | Two measured halves: the DSN's `sslmode` must refuse plaintext, and every live session in `pg_stat_ssl` must be encrypted | **Yes, one direction here** — FAIL whenever the DSN permits plaintext or a session is cleartext (both true on this cluster, which runs `ssl = off`). PASS requires a TLS-capable server; the decision rule is unit-tested for the encrypted case. Browser→API TLS terminates outside this process and is not claimed |
| 15 | `NIST-AC-2` | NIST 800-53 | `DCC_ACCOUNT_MANAGEMENT` | `dcc.tenants` as the account register: every credentialed tenant must exist and be `active`, so suspension is a working way to withdraw access | **Yes** — PASS ⇄ FAIL proven (`status='suspended'` FAILs) |
| 16 | `NIST-AU-1` | NIST 800-53 | `DCC_AUDIT_POLICY_PATH` | **`NOT_ASSESSED`** — policy adequacy is a review judgement; document presence is reported, a pass is not asserted | **No** — always `NOT_ASSESSED` |

## Which controls still cannot fail, and why

Four controls can never move off `NOT_ASSESSED`. Each is a case where an honest
observable does not exist inside this application, so the only alternatives were a
fabricated PASS or a fabricated FAIL:

| Control | Why no observable exists | What evidence would settle it |
|---|---|---|
| `ISO27001-A.14.1.1` | "Security requirements were analysed" is a judgement about a document and a process | Reviewed requirements register / threat model with owners and dates, assessed by a person |
| `PCI-1.1` | Segmentation is a property of subnets, security groups and NetworkPolicy as *applied*; the process cannot query the network fabric | Cloud/network inventory showing the CDE isolated, or a segmentation penetration test |
| `PCI-3.4` | At-rest encryption lives under the Postgres data directory (volume encryption) or in a KMS-managed column; neither is visible to SQL or to this process | Volume-encryption attestation (EBS/LUKS/KMS) or a ciphertext column inventory |
| `NIST-AU-1` | An audit *policy* is a document; its existence is not its adequacy | Reviewed policy document with approval and review dates |

Three controls cannot currently reach `PASS`, for reasons that are true of the
system rather than of the control (statuses as measured 2026-10-26):

* `SOC2-CC6.1` — `PASS` is unreachable while MFA is unimplemented, because the
  control asserts two things and can measure one. This is the honest reading of the
  control as written; if MFA is built, the MFA measurement becomes a real observation
  and the control can pass.
* `HIPAA-164.312(e)(1)` — `PASS` needs a TLS-capable Postgres. `sslmode=require`
  against a server with `ssl = off` fails to connect, which the control reports as
  `NOT_ASSESSED` ("required but no session could be observed") rather than as a pass.
* `SOC2-CC6.2` from configuration alone — `DCC_API_KEYS` has no expiry field, so the
  configuration branch is a permanent FAIL by construction. The live-store branch
  passes when keys carry `expires_at`.

## What was discovered by measuring

Repointing the controls at real state immediately surfaced defects the phantom
variables had been hiding:

1. **The audit trail verifies, on the one row the seed wrote.** `dcc.evidence_events`
   holds a single seeded event (`demo.fixture.seeded`), and `PCI-10.1` now **PASSes**:

   ```
   The audit trail holds 1 event(s) across 1 tenant(s) and every hash chain verifies
   (no edited, inserted or reordered rows)
   ```

   That is a genuine chain verification over real stored rows, but it certifies a chain
   of one. Earlier revisions of this section reported `PCI-10.1` as FAIL because the
   seeded row carried a placeholder hash; that is no longer what the scan reports. What
   remains unproven is breadth, not correctness: the control has never been exercised
   over a multi-row chain in this database (the `FAIL` direction is unit-tested —
   `tests/compliance/test_controls_real_state.py`).
2. **Alert rules for this service now reference series that exist — with one exception
   that is a defect in this control, not in the rules.** Re-measured 2026-10-26, the
   `SOC2-CC7.1` finding reads:

   ```
   1 of 13 alert rule(s) for this service reference metrics nothing exports
   (api_request_duration_seconds_bucket), so they can never fire: DCCHighLatency
   ```

   The three rules this section previously described as permanently silent are fixed:
   `DCCHighErrorRate` uses `api_errors_total{type=~"internal|timeout"}` and
   `api_requests_total`, `DCCHighLatency` uses the latency histogram, and
   `DCCDatabaseUnavailable` uses `api_database_errors_total{operation}`
   (`monitoring/prometheus/rules/dcc-alerts.yml`). The remaining failure is this control's
   own metric-name resolution: `_exported_metrics()`
   (`src/dcc/compliance/observables.py:1252-1276`) scrapes string literals out of the
   source and never expands Prometheus' histogram suffixes, so
   `api_request_duration_seconds_bucket` is reported as unexported even though the app's
   `/metrics` emits it:

   ```
   GET /metrics, after one request to /v2/overview (excerpt):
   api_request_duration_seconds_bucket{le="0.25",route="/v2/overview"} 1
   ...
   api_request_duration_seconds_bucket{le="+Inf",route="/v2/overview"} 1
   api_request_duration_seconds_sum{route="/v2/overview"} 0.117376
   api_request_duration_seconds_count{route="/v2/overview"} 1
   ```

   So `SOC2-CC7.1` is FAIL for a false positive. Reported rather than papered over: the
   control's claim "can never fire" is wrong about `DCCHighLatency` on this tree.
3. **No access events are recorded.** The only evidence event is
   `demo.fixture.seeded`, so a periodic access review has no material to review
   (`SOC2-CC6.3` FAIL).
4. **Credentials do not expire and the database link is cleartext.** `SOC2-CC6.2` is
   `NOT_ASSESSED` on this cluster — "the live key store is empty, so there is no
   credential lifecycle to assess" — so the expiry gap is not currently being judged at
   all; from `DCC_API_KEYS` alone it remains a permanent FAIL by construction.
   `HIPAA-164.312(e)(1)` FAILs: the DSN permits plaintext and the server runs `ssl = off`.

## Verification

```bash
# 16 controls, unchanged ids, both directions of movement
.venv/bin/python -m pytest tests/compliance -q

# the durable guard: no control may read a variable the application ignores
.venv/bin/python -m pytest tests/compliance/test_controls_real_state.py -q -k phantom

# endpoint contract unchanged (200, same keys), configuration_gaps now empty
DCC_ALLOW_ANONYMOUS=1 DCC_DATABASE_URL=postgresql://localhost:5432/dcc_demo_local \
  .venv/bin/python -c "from fastapi.testclient import TestClient; \
  from dcc.api_async import app; c=TestClient(app); \
  print(c.get('/v2/compliance/controls').status_code, c.get('/v2/compliance/scan').json()['configuration_gaps'])"
```

Baseline: `541 passed, 1 skipped` → after: `601 passed, 1 skipped`.

Re-measured 2026-10-26 on `4375603`:

```
$ .venv/bin/python -m pytest tests/compliance -q -p no:cacheprovider
601 passed, 1 skipped in 23.76s
```

and the scan itself:

```
$ GET /v2/compliance/scan
summary {"total": 16, "by_status": {"fail": 5, "not_assessed": 7, "pass": 4}}
configuration_gaps {"affected_controls": 0, ...}
```

## Guard against regression

`tests/compliance/test_controls_real_state.py::TestNoPhantomVariables` enforces this
mechanically, in two ways:

1. **Textual** — it parses `src/dcc/compliance/**` with `ast`, resolves the module
   constants (`DSN_ENV = "DCC_DATABASE_URL"`), and asserts every environment variable
   the compliance package reads is one the application reads. Adding
   `os.environ.get("DCC_TLS_ENFORCED")` anywhere in the package fails this test with
   the offending name.
2. **Behavioural** — for each of the 17 historical knobs, setting it to `true`,
   `false`, `1`, `0` or a path must change **no** control's findings. Named
   variables that survive as prose in docstrings cannot make this pass.
