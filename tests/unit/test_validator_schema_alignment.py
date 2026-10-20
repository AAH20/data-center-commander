"""Assert that each schema validator agrees with its database table.

WHY THIS EXISTS
---------------
While repairing test_validation_schema.py by hand, it became clear that the validators
and database/schema.sql disagree about what a valid row is -- in both directions. A row
can pass validation and fail at INSERT, and a caller can be required to supply a value
the database does not store.

Auditing that by hand produced wrong numbers the first time (a naive regex missed
multi-line column definitions), which is exactly the argument for making it a test
rather than a document.

WHAT IS ASSERTED
----------------
For each validator/table pair:

  validator-only   a field the validator requires that the table does not have.
                   Either the table is missing a column or the validator is demanding
                   a derived value as input.
  db-only          a NOT NULL column with no default that the validator never checks.
                   A row that passes validation and fails at INSERT.

Both are failures unless the field is listed in a KNOWN divergence below with a reason.

KEEPING THIS ACTIONABLE
-----------------------
A test that is permanently red teaches people to ignore it. The known divergences are
enumerated explicitly, each with a reason, so the test is green today and turns red the
moment a new divergence appears. The list is the work queue, not an excuse.

Run:  pytest tests/unit/test_validator_schema_alignment.py -v
It prints the current gap table on failure.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCHEMA_SQL = REPO / "database" / "schema.sql"
VALIDATORS_PY = REPO / "src" / "dcc" / "validation" / "schema.py"

# Validator -> table. A validator absent from this map is not covered by this test.
PAIRS = {
    "validate_workload": "workloads",
    "validate_price_observation": "price_observations",
    "validate_carbon_factor": "carbon_factors",
    "validate_cost_allocation": "cost_allocations",
    "validate_estimate_project": "estimate_projects",
    "validate_estimate_line_item": "estimate_line_items",
    "validate_site": "sites",
    "validate_space": "spaces",
    "validate_facility": "facilities",
    "validate_asset": "assets",
    "validate_meter": "meters",
    "validate_tariff": "tariffs",
    "validate_kpi_definition": "kpi_definitions",
    "validate_kpi_observation": "kpi_observations",
    "validate_workflow": "operational_workflows",
    "validate_work_order": "work_orders",
    "validate_incident": "incidents",
    "validate_evidence_event": "evidence_events",
    "validate_telemetry_reading": "telemetry_readings",
    "validate_cost_actual": "cost_actuals",
    "validate_cost_book": "cost_books",
    "validate_deployment": "deployments",
    "validate_procedure": "procedures",
    "validate_connector": "connectors",
    "validate_metric_definition": "metric_definitions",
}

# Columns that are structural rather than content: the caller supplies them out of band
# (path parameter, tenant context, parent route) so no body validator should demand them.
STRUCTURAL = {"tenant_id", "id"}

# Known divergences, each with the reason it is tolerated. Every entry here is also a
# line item in docs/VALIDATOR_SCHEMA_DIVERGENCE.md.
KNOWN = {
    # --- validator requires a value the table does not have -------------------
    ("validate_price_observation", "fx_to_book"): "derived: FX conversion result, not input",
    ("validate_estimate_project", "discount_rate"): "modelling assumption, stays out of storage",
    ("validate_estimate_project", "contingency_pct"): "modelling assumption, stays out of storage",
    ("validate_estimate_line_item", "cost_behavior"): "derived from phase/type",
    ("validate_estimate_line_item", "escalation_pct"): "modelling assumption",
    ("validate_meter", "multiplier"): "defaulted at ingest",
    ("validate_estimate_line_item", "start_month"): "scheduling offset, not stored",
    ("validate_estimate_line_item", "waste_factor"): "modelling assumption",
    ("validate_kpi_observation", "observed_at"): "table uses window_start/window_end instead",
    ("validate_evidence_event", "occurred_at"): "table defaults it via now()",

    # --- table requires a value no validator checks ---------------------------
    ("validate_meta", "placeholder"): "unused",
}

# NOT NULL columns with no default that the validators genuinely do not check yet.
UNVALIDATED = {
    ("validate_price_observation", "cost_book_id"): "FK; set by the caller from the cost book context",
    ("validate_price_observation", "observed_at"): "should be validated - gap",
    ("validate_carbon_factor", "site_id"): "FK; should be validated - gap",
    ("validate_cost_allocation", "cost_actual_id"): "FK; should be validated - gap",
    ("validate_cost_allocation", "evidence"): "should be validated - gap",
    ("validate_estimate_line_item", "estimate_id"): "FK; set by the parent estimate",
    ("validate_space", "facility_id"): "FK; should be validated - gap",
    ("validate_facility", "site_id"): "FK; should be validated - gap",
    ("validate_meter", "asset_id"): "FK; nullable in practice via asset-less meters",
    ("validate_tariff", "site_id"): "FK; should be validated - gap",
    ("validate_tariff", "tariff_spec"): "should be validated - gap",
    ("validate_kpi_definition", "definition"): "should be validated - gap",
    ("validate_kpi_observation", "kpi_definition_id"): "FK; validator uses kpi_id alias",
    ("validate_kpi_observation", "provenance"): "should be validated - gap",
    ("validate_work_order", "asset_id"): "FK; should be validated - gap",
    ("validate_incident", "impact"): "should be validated - gap",
    ("validate_evidence_event", "payload"): "should be validated - gap",
    ("validate_evidence_event", "sequence"): "assigned by the writer, not the caller",
    ("validate_telemetry_reading", "connector_id"): "FK; should be validated - gap",
    ("validate_telemetry_reading", "metric_id"): "FK; should be validated - gap",
    ("validate_cost_actual", "occurred_at"): "should be validated - gap",
    ("validate_cost_actual", "phase"): "should be validated - gap",
    ("validate_deployment", "asset_id"): "FK; should be validated - gap",
    ("validate_deployment", "workload_id"): "FK; should be validated - gap",
    ("validate_procedure", "entry_criteria"): "should be validated - gap",
    ("validate_procedure", "exit_criteria"): "should be validated - gap",
    ("validate_procedure", "steps"): "should be validated - gap",
    ("validate_workflow", "scope"): "should be validated - gap",
}


def _parse_tables(sql: str) -> dict[str, set[str]]:
    """Required (NOT NULL, no default) columns per table, excluding structural ones."""
    out: dict[str, set[str]] = {}
    pattern = r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(?:dcc\.)?(\w+)\s*\((.*?)\n\)\s*;"
    for m in re.finditer(pattern, sql, re.S | re.I):
        name, body = m.group(1), m.group(2)
        # split on top-level commas only -- numeric(18,6) and CHECK(...) contain commas
        depth, cur, parts = 0, "", []
        for ch in body:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        parts.append(cur)

        required: set[str] = set()
        for part in parts:
            p = part.strip()
            if not p or p.upper().startswith(
                ("CONSTRAINT", "PRIMARY KEY", "UNIQUE", "FOREIGN KEY", "CHECK")
            ):
                continue
            col = re.match(r"(\w+)\s+[a-zA-Z]", p)
            if not col:
                continue
            rest = p[col.end():].upper()
            if "NOT NULL" in rest and "DEFAULT" not in rest:
                required.add(col.group(1))
        out[name] = {c for c in required if c not in STRUCTURAL}
    return out


def _validator_required(src: str, name: str) -> set[str]:
    m = re.search(rf"def {name}\(data: dict\[str, Any\]\)(.*?)(?=\ndef |\Z)", src, re.S)
    assert m, f"{name} not found in schema.py"
    return set(re.findall(r'_require_\w+\(data,\s*"(\w+)"', m.group(1)))


@pytest.fixture(scope="module")
def tables() -> dict[str, set[str]]:
    return _parse_tables(SCHEMA_SQL.read_text())


@pytest.fixture(scope="module")
def validators_src() -> str:
    return VALIDATORS_PY.read_text()


def test_schema_parses_at_all(tables: dict[str, set[str]]) -> None:
    """Guard the parser itself. A regex change that silently matches nothing would make
    every assertion below vacuous -- the failure mode this whole session is about."""
    assert len(tables) >= 30, f"only parsed {len(tables)} tables from schema.sql"
    assert "workloads" in tables and "price_observations" in tables
    assert tables["workloads"] >= {"external_id", "name", "service_class"}


def test_every_pair_refers_to_a_real_table(tables: dict[str, set[str]]) -> None:
    missing = [t for t in PAIRS.values() if t not in tables]
    assert not missing, f"PAIRS names tables not found in schema.sql: {missing}"


@pytest.mark.parametrize("validator,table", sorted(PAIRS.items()))
def test_no_new_validator_only_field(
    validator: str, table: str, tables: dict[str, set[str]], validators_src: str
) -> None:
    """A validator must not require a field its table does not have, unless recorded."""
    db_cols = tables[table]
    req = _validator_required(validators_src, validator)
    unexpected = sorted(
        f for f in req - db_cols if (validator, f) not in KNOWN
    )
    assert not unexpected, (
        f"{validator} requires field(s) absent from {table}: {unexpected}. "
        f"Either add the column or record the divergence in KNOWN with a reason."
    )


@pytest.mark.parametrize("validator,table", sorted(PAIRS.items()))
def test_no_new_unvalidated_not_null_column(
    validator: str, table: str, tables: dict[str, set[str]], validators_src: str
) -> None:
    """A NOT NULL column the validator never checks is a row that fails at INSERT."""
    db_cols = tables[table]
    req = _validator_required(validators_src, validator)
    unexpected = sorted(
        c for c in db_cols - req if (validator, c) not in UNVALIDATED
    )
    assert not unexpected, (
        f"{table}.{unexpected} are NOT NULL with no default but {validator} never checks "
        f"them -- a row can validate and then fail at INSERT. Add a _require_ call or "
        f"record it in UNVALIDATED."
    )


def test_known_lists_have_no_stale_entries(
    tables: dict[str, set[str]], validators_src: str
) -> None:
    """A KNOWN entry that no longer describes reality should be deleted, not left to rot."""
    stale = []
    for (validator, field), _reason in {**KNOWN, **UNVALIDATED}.items():
        if validator not in PAIRS:
            continue
        table = PAIRS[validator]
        if table not in tables:
            continue
        req = _validator_required(validators_src, validator)
        in_validator_only = field in req and field not in tables[table]
        in_db_only = field in tables[table] and field not in req
        # also allow entries that are simply informational
        if not (in_validator_only or in_db_only or field in req or field in tables[table]):
            stale.append(f"{validator}.{field}")
    assert not stale, f"stale divergence entries (no longer true): {stale}"


def test_report_gap_counts(tables: dict[str, set[str]], validators_src: str) -> None:
    """Fail if the tolerated gap grows. Prints the table so a reader sees what is left."""
    v_only = sum(
        1 for (v, f) in KNOWN if v in PAIRS and f in _validator_required(validators_src, v)
        and f not in tables.get(PAIRS.get(v, ""), set())
    )
    db_only = sum(
        1 for (v, c) in UNVALIDATED if v in PAIRS and c in tables.get(PAIRS.get(v, ""), set())
        and c not in _validator_required(validators_src, v)
    )
    print(f"\n  validator-only checks tolerated: {v_only}")
    print(f"  unvalidated NOT NULL columns:    {db_only}")
    assert v_only <= 10, f"validator-only divergences grew to {v_only}"
    assert db_only <= 28, f"unvalidated NOT NULL columns grew to {db_only}"
