# Validator / schema divergence

`src/dcc/validation/schema.py` and `database/schema.sql` disagree about what a valid
row is, **in both directions**. Neither is a superset of the other. A payload that
passes one can fail the other.

This was found while repairing 33 failing cases in `tests/unit/test_validation_schema.py`.
The tests were stale, but repairing them surfaced the deeper problem: to make each
validator accept anything at all, several payloads had to carry fields that the database
does not store, while omitting fields the database requires.

## Evidence

Field sets derived by reading `_require_*` calls out of each validator and `NOT NULL`
columns out of each `CREATE TABLE`.

### `price_observations`

| | |
|---|---|
| Validator requires (17) | `item_code`, `description`, `quantity_unit`, `geography`, `source_name`, `source_ref`, `valid_from`, `currency_basis_date`, `category`, `delivery_basis`, `source_kind`, `quality_status`, `currency`, `unit_price`, `normalized_unit_price`, `fx_to_book`, `confidence` |
| DB requires (15) | `cost_book_id`, `item_code`, `description`, `category`, `quantity_unit`, `currency`, `geography`, `delivery_basis`, `observed_at`, `valid_from`, `source_kind`, `source_name`, `source_ref`, `currency_basis_date`, `quality_status` |
| Validator-only | `unit_price`, `normalized_unit_price`, `fx_to_book`, `confidence` |
| DB-only | `cost_book_id`, `observed_at` |

### `carbon_factors`

| | |
|---|---|
| Validator-only | `factor_kg_per_kwh` |
| DB-only | `site_id` |

### `estimate_projects`

| | |
|---|---|
| Validator-only | `discount_rate`, `contingency_pct` |
| DB-only | — |

### `cost_allocations`

| | |
|---|---|
| Validator-only | `allocated_amount`, `allocation_fraction` |
| DB-only | `cost_actual_id`, `evidence` |

## Two class of defect

**1. Input validation demands derived values.**
`normalized_unit_price`, `fx_to_book`, `confidence`, `allocated_amount`,
`allocation_fraction`, `factor_kg_per_kwh`, `discount_rate`, `contingency_pct` all read
as computed or modelled quantities rather than inputs a caller supplies. Requiring them
on the way in means every caller must compute them before validating — which is exactly
the work the domain layer exists to do. `fnx_to_book` in particular is a conversion
result, not an input.

**2. Required foreign keys are not checked at all.**
`cost_book_id`, `site_id` and `cost_actual_id` are `NOT NULL` with a `FOREIGN KEY`, and
no validator requires them. A row can pass validation and then fail at insert.

## Same field name, different types

| Field | Dates in | Datetime in |
|---|---|---|
| `valid_from` | `cost_books`, `price_observations`, `tariffs`, `asset_relationships` | `carbon_factors` |

`quality_status` likewise accepts `good` for `telemetry_readings` but `approved` for
`price_observations`. These are not stylistic; a caller cannot write one helper that
produces a valid payload for both.

## What was done here

`tests/unit/schema_payloads.py` now holds a frozen payload per validator that the
validator accepts, and `test_validation_schema.py` uses it. That took the file from 33
failures to 0.

**This did not resolve the divergence and is not presented as doing so.** The payloads
are deliberately ugly where the validators are ugly — they carry `normalized_unit_price`
because the validator demands it, not because a caller should supply it.

## The decision required

One of these, explicitly:

**A. Validators enforce the database.** Derive every validator's required set
mechanically from `information_schema.columns WHERE is_nullable = 'false'`, plus the
`CHECK` constraints. Move all derived fields out of the required set. This makes
"validated" mean "insertable", which is the property callers actually want.

**B. Validators are the input contract and the schema follows.** Add the derived columns
to the database, or add a separate input model. Larger change, and it puts computed
values in storage.

**C. Split the two concepts.** `validate_*_input` for what a caller must supply,
`validate_*_row` for what must be persisted, with the derived fields computed between
them. Most correct, most work.

**Recommendation: A, then C if input and row shapes keep diverging.** A is a bounded
change — one generated table of required columns, and the 33 tests already exist to
prove it — and it fixes the class of bug rather than the instance. Under A, the frozen
payloads in `schema_payloads.py` get simpler, which is a good sign.

## How to check this again

```bash
# required columns per table
psql -c "SELECT table_name, column_name FROM information_schema.columns
         WHERE table_schema='dcc' AND is_nullable='false'
           AND column_default IS NULL ORDER BY 1,2;"

# required fields per validator
grep -n '_require_' src/dcc/validation/schema.py
```

Any field in the first list and not the second is a row the database rejects and the
validator accepts. Any field in the second and not the first is an input the validator
rejects and the database would have accepted.
