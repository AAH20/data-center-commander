# Validator / schema divergence

`src/dcc/validation/schema.py` and `database/schema.sql` disagree about what a valid row
is, **in both directions**. Neither is a superset of the other.

> **Correction.** The first version of this document said `price_observations` required
> 15 columns and that the validator demanded four fields the table lacked. Both figures
> were wrong: a naive regex parsed only the first line of each multi-line column
> definition. The table has **18** required columns and shares **all** of
> `unit_price`, `normalized_unit_price` and `confidence` with the validator. The real
> gap is smaller and differently shaped. The figures below come from
> `tests/unit/test_validator_schema_alignment.py`, which parses the DDL properly and
> fails when this audit drifts.

## Current state

| Measure | Count |
|---|---|
| Validators compared against a table | 25 |
| Fully aligned | 6 |
| Validator requires a field its table lacks | 10 |
| `NOT NULL` columns no validator checks | 28 |

The audit is a test, not a document. `tests/unit/test_validator_schema_alignment.py`
parses `schema.sql`, parses the `_require_*` calls, and fails on any divergence not
explicitly recorded with a reason. It found `operational_workflows.scope` while this
document was being written.

## Defect class 1 — a row can validate and fail at INSERT

28 `NOT NULL` columns with no default are never checked. Examples:

| Table | Unvalidated column | Consequence |
|---|---|---|
| `price_observations` | `cost_book_id`, `observed_at` | INSERT fails |
| `cost_allocations` | `cost_actual_id`, `evidence` | INSERT fails |
| `operational_workflows` | `scope` | INSERT fails |
| `incidents` | `impact` | INSERT fails |
| `evidence_events` | `payload` | INSERT fails |
| `procedures` | `entry_criteria`, `exit_criteria`, `steps` | INSERT fails |

"Validated" does not currently mean "insertable", which is the property callers want.

## Defect class 2 — input validation demands derived values

Ten fields are required by a validator but absent from the table:

| Validator | Field | Why it looks derived |
|---|---|---|
| `validate_price_observation` | `fx_to_book` | FX conversion result |
| `validate_estimate_project` | `discount_rate`, `contingency_pct` | modelling assumptions |
| `validate_estimate_line_item` | `cost_behavior`, `escalation_pct`, `start_month`, `waste_factor` | scheduling / modelling inputs |
| `validate_meter` | `multiplier` | defaulted at ingest |
| `validate_kpi_observation` | `observed_at` | table uses `window_start`/`window_end` |
| `validate_evidence_event` | `occurred_at` | table defaults it via `now()` |

Requiring them on the way in makes every caller compute values the domain layer exists
to produce.

## Same field name, different types

| Field | Date in | Datetime in |
|---|---|---|
| `valid_from` | `cost_books`, `price_observations`, `tariffs`, `asset_relationships` | `carbon_factors` |

`quality_status` accepts `good` for `telemetry_readings` but `approved` for
`price_observations`. A caller cannot write one helper that produces a valid payload for
both. Both are recorded in `tests/unit/schema_payloads.py` rather than smoothed over.

## What was done

**`tests/unit/test_validator_schema_alignment.py`** — the audit as a gate, 54 tests:

1. the schema parser found ≥30 tables, so a broken regex cannot make the suite vacuous
2. every validator/table pair names a table that exists
3. no validator requires a field its table lacks, unless recorded
4. no `NOT NULL` column is unvalidated, unless recorded
5. no recorded entry has gone stale
6. the tolerated gap has not grown (10 / 28)

**`tests/unit/schema_payloads.py`** — one frozen payload per validator that it accepts,
used by `test_validation_schema.py` (33 failures → 0). The payloads are deliberately as
ugly as the validators are.

Neither of these fixes the divergence. They make it visible, bounded and non-growing.

## The decision required

**A. Validators enforce the database.** Derive each required set from
`information_schema.columns WHERE is_nullable='false' AND column_default IS NULL`, add
the missing checks, move derived fields out. "Validated" then means "insertable".

**B. Validators are the input contract; the schema follows.** Add the derived columns to
storage. Larger change, and it puts computed values in the database.

**C. Split the concepts.** `validate_*_input` for caller-supplied values,
`validate_*_row` for persisted values, with derivation between them.

**Recommendation: A, then C if the shapes keep diverging.** A is bounded — one generated
required-column table plus the 28 missing checks — and the alignment test already exists
to prove it. Under A the frozen payloads get simpler, which is the signal it was the
right direction.

## How to re-check

```bash
pytest tests/unit/test_validator_schema_alignment.py -v -s
```

Prints the tolerated-gap counts and names every unrecorded divergence. The equivalent
against a live database:

```sql
SELECT table_name, column_name FROM information_schema.columns
WHERE table_schema='dcc' AND is_nullable='false' AND column_default IS NULL
ORDER BY 1,2;
```

Any column in that result and not in a validator's `_require_*` set is a row the database
rejects and the validator accepts. Any `_require_*` field absent from that result is an
input the validator demands and the database would not have stored.
