"""Pins the one backup-policy definition: two axes, four agreed fields.

The defect this module exists for
--------------------------------
``dcc.backup_policies``, ``dcc.dr.policies`` and ``/v2/dr/policies`` each had
their own idea of what a backup policy is, and the API had no idea at all -- it
returned the raw row. The four fields where they disagreed:

  field         database                          record
  ------------  --------------------------------  ---------------------------
  policy_type   scheduled|continuous|on_demand|    full|incremental|
                snapshot  (WHEN it runs)           differential|continuous|
                                                  snapshot  (WHAT it writes)
  compression   none|gzip|zstd|lz4                bool
  status        pending|running|succeeded|        active|paused|disabled|
                failed|disabled  (run state)       archived  (lifecycle)

The two ``policy_type`` vocabularies intersect only on
``continuous``/``snapshot``, so ``PolicyType.FULL`` -- the default of both
``BackupPolicy`` and ``create_policy`` -- was rejected by the table's CHECK.
That is a legitimate call failing, and it is the first thing tested here.

What is asserted
----------------
1. The two axes stay two fields, with an explicit, total translation from the
   old single field. Nothing stores a ``PolicyType``.
2. Compression is a codec and status is a lifecycle state, in the record as in
   the table. A ``bool`` or a run state is refused rather than coerced.
3. The row translation round-trips: a policy built from ``PolicyType.FULL`` and
   written to the table reads back through ``/v2/dr/policies`` with every field
   intact.
4. The CHECK constraints still reject genuinely invalid values -- a widened
   constraint would make (3) pass for the wrong reason.

(3) and (4) need the real database, because the defect was in a CHECK
constraint and a fake cursor would assert against the bug instead of the
behaviour. They are skipped without ``DCC_DATABASE_URL``; run them with::

    DCC_DATABASE_URL=postgresql://localhost:5432/dcc_demo_local \\
        pytest tests/unit/test_dr_policies_unified.py -v
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from dcc.dr.policies import (
    ROW_COLUMNS,
    SELECT_COLUMNS,
    BackupPolicy,
    BackupType,
    Compression,
    PolicyEngine,
    PolicySchedule,
    PolicyStatus,
    PolicyTrigger,
    PolicyType,
    PolicyValidationError,
    policy_from_row,
    policy_to_row,
)

psycopg = pytest.importorskip("psycopg")

DSN = os.environ.get("DCC_DATABASE_URL", "").strip()
TENANT = "dcc00000-0000-4000-8000-000000000012"

requires_db = pytest.mark.skipif(
    not DSN,
    reason=(
        "DCC_DATABASE_URL is not set: the CHECK constraints and the /v2/dr/policies "
        "read path can only be proven against a database with schema.sql and "
        "migrations 001-012 applied."
    ),
)


def _policy(**overrides: Any) -> BackupPolicy:
    base: dict[str, Any] = {
        "policy_id": "11111111-1111-4111-8111-111111111111",
        "tenant_id": TENANT,
        "name": "nightly",
    }
    base.update(overrides)
    return BackupPolicy(**base)


# ---------------------------------------------------------------------------
# 1. Two axes, two fields
# ---------------------------------------------------------------------------


def test_the_legacy_single_field_splits_into_the_two_axes() -> None:
    """Every pre-012 value maps to exactly one (backup, trigger) pair.

    Total by construction: ``split`` is a dict lookup, so a new member would
    have to be given a translation rather than falling through to a default.
    """
    assert PolicyType.FULL.split() == (BackupType.FULL, PolicyTrigger.SCHEDULED)
    assert PolicyType.INCREMENTAL.split() == (
        BackupType.INCREMENTAL,
        PolicyTrigger.SCHEDULED,
    )
    assert PolicyType.DIFFERENTIAL.split() == (
        BackupType.DIFFERENTIAL,
        PolicyTrigger.SCHEDULED,
    )
    # No engine artifact, so no backup kind -- which is what the table's
    # biconditional CHECK demands of these two triggers.
    assert PolicyType.CONTINUOUS.split() == (None, PolicyTrigger.CONTINUOUS)
    assert PolicyType.SNAPSHOT.split() == (None, PolicyTrigger.SNAPSHOT)

    for member in PolicyType:
        backup_type, trigger = member.split()
        assert member.axis == ("trigger" if backup_type is None else "backup")


def test_constructing_from_a_legacy_policy_type_fills_both_fields() -> None:
    """The old call site -- ``policy_type=PolicyType.FULL`` -- keeps working.

    It works by being translated, not by the record keeping a union field.
    """
    policy = _policy(policy_type=PolicyType.FULL)

    assert policy.policy_type is PolicyTrigger.SCHEDULED
    assert policy.backup_type is BackupType.FULL
    assert not isinstance(policy.policy_type, PolicyType)
    assert not isinstance(policy.backup_type, PolicyType)

    # And the stored/returned shape never contains a PolicyType value.
    assert policy.to_dict()["policy_type"] == "scheduled"
    assert policy.to_dict()["backup_type"] == "full"


def test_the_axes_are_independent() -> None:
    """Any trigger can carry any backup kind it can actually produce."""
    scheduled_incremental = _policy(
        policy_type=PolicyTrigger.SCHEDULED, backup_type=BackupType.INCREMENTAL
    )
    on_demand_full = _policy(
        policy_type=PolicyTrigger.ON_DEMAND, backup_type=BackupType.FULL
    )
    snapshot = _policy(policy_type=PolicyTrigger.SNAPSHOT, backup_type=None)

    assert (scheduled_incremental.policy_type.value, scheduled_incremental.backup_type.value) == (
        "scheduled",
        "incremental",
    )
    assert on_demand_full.policy_type is PolicyTrigger.ON_DEMAND
    assert on_demand_full.backup_type is BackupType.FULL
    assert snapshot.backup_type is None


def test_a_trigger_that_produces_no_backup_cannot_claim_a_backup_kind() -> None:
    """The biconditional the database enforces, enforced in the record too."""
    with pytest.raises(PolicyValidationError) as exc:
        _policy(policy_type=PolicyTrigger.CONTINUOUS, backup_type=BackupType.FULL)
    assert "continuous" in str(exc.value)

    with pytest.raises(PolicyValidationError):
        _policy(policy_type=PolicyTrigger.SNAPSHOT, backup_type=BackupType.DIFFERENTIAL)

    with pytest.raises(PolicyValidationError):
        _policy(policy_type=PolicyTrigger.SCHEDULED, backup_type=None)


# ---------------------------------------------------------------------------
# 2. compression is a codec; status is a lifecycle
# ---------------------------------------------------------------------------


def test_compression_is_a_codec_not_a_bool() -> None:
    """The old bool is refused, with the allowed codecs named in the error.

    A bool cannot express ``zstd``, and ``True`` disagreed with the column's
    own default of ``'none'`` about what "no value" means.
    """
    assert _policy().compression is Compression.GZIP
    assert _policy(compression=Compression.ZSTD).to_dict()["compression"] == "zstd"

    for bad in (True, False, "gzip", 1):
        with pytest.raises(PolicyValidationError) as exc:
            _policy(compression=bad)
        assert "none, gzip, zstd, lz4" in str(exc.value)

def test_a_codec_the_engine_cannot_write_is_refused_not_downgraded() -> None:
    """Declarable in the table, not executable: refuse rather than silently use gzip."""
    assert _policy(compression=Compression.NONE).to_engine_params()["compression"] == "none"
    assert _policy(compression=Compression.GZIP).to_engine_params()["compression"] == "gzip"

    with pytest.raises(PolicyValidationError) as exc:
        _policy(compression=Compression.ZSTD).to_engine_params()
    assert "zstd" in str(exc.value)


def test_status_is_lifecycle_and_rejects_a_run_state() -> None:
    """Run state was never the policy's own; it belongs to a run."""
    assert _policy().status is PolicyStatus.ACTIVE
    assert _policy(enabled=False, status=PolicyStatus.PAUSED).status is PolicyStatus.PAUSED

    for run_state in ("pending", "running", "succeeded"):
        with pytest.raises(PolicyValidationError) as exc:
            _policy(status=run_state)
        assert "status must be a PolicyStatus" in str(exc.value)


def test_enabled_and_status_cannot_contradict_each_other() -> None:
    """enabled=True with a non-active status is a policy that never runs."""
    with pytest.raises(PolicyValidationError) as exc:
        _policy(enabled=True, status=PolicyStatus.PAUSED)
    assert "enabled" in str(exc.value)

    assert _policy(enabled=False, status=PolicyStatus.ACTIVE).enabled is False


def test_pre_unification_json_documents_still_load() -> None:
    """Policy files on disk predate the split, and list_policies skips documents
    it cannot parse -- so rejecting them would silently drop every old policy."""
    legacy = _policy().to_dict()
    legacy.pop("backup_type")
    legacy.update({"policy_type": "differential", "compression": True, "status": "succeeded"})

    restored = BackupPolicy.from_dict(legacy)

    assert restored.policy_type is PolicyTrigger.SCHEDULED
    assert restored.backup_type is BackupType.DIFFERENTIAL
    assert restored.compression is Compression.GZIP
    assert restored.status is PolicyStatus.ACTIVE


def test_a_legacy_failed_status_pauses_rather_than_reenables() -> None:
    """Same mapping as migration 012: 'failed' must not become 'active' silently."""
    legacy = _policy().to_dict()
    legacy.pop("backup_type")
    legacy.update({"policy_type": "full", "status": "failed", "compression": False})

    restored = BackupPolicy.from_dict(legacy)

    assert restored.status is PolicyStatus.PAUSED
    assert restored.enabled is False
    assert restored.compression is Compression.NONE


# ---------------------------------------------------------------------------
# 3. The row translation
# ---------------------------------------------------------------------------


def test_the_row_translation_round_trips_every_field() -> None:
    """No field is lost and none is invented by the trip through a row."""
    original = _policy(
        policy_type=PolicyType.INCREMENTAL,
        schedule=PolicySchedule.CUSTOM,
        custom_cron="15 3 * * 2",
        retention_days=14,
        tables=["assets", "evidence_events"],
        compression=Compression.LZ4,
        verify_after=False,
        enabled=False,
        status=PolicyStatus.PAUSED,
        tags={"owner": "sre"},
        last_run_at=datetime(2026, 10, 1, 2, 0, tzinfo=timezone.utc),
        next_run_at=datetime(2026, 10, 8, 2, 15, tzinfo=timezone.utc),
    )

    row = policy_to_row(original)
    restored = policy_from_row(row)

    assert tuple(row) == ROW_COLUMNS
    assert restored == original


def test_the_select_list_is_the_column_list() -> None:
    """One definition of the row shape: the API cannot select a different set."""
    for column in ROW_COLUMNS:
        assert column in SELECT_COLUMNS
    assert len(SELECT_COLUMNS.split(",")) == len(ROW_COLUMNS)


# ---------------------------------------------------------------------------
# 4. The round trip through the database and the API
# ---------------------------------------------------------------------------


@pytest.fixture()
def tenant() -> Any:
    """A tenant of our own, so the fixture rows cannot collide with seed data."""
    if not DSN:
        pytest.skip("no database")
    with psycopg.connect(DSN) as conn:
        conn.execute(
            "INSERT INTO dcc.tenants (id, slug, name) VALUES (%s, %s, %s)",
            (TENANT, "policy-unification-test", "Policy unification test"),
        )
    yield TENANT
    with psycopg.connect(DSN) as conn:
        conn.execute("DELETE FROM dcc.tenants WHERE id = %s", (TENANT,))


def _db_params(row: dict[str, Any]) -> list[Any]:
    """Adapt the row for psycopg: ``tags`` is jsonb, which psycopg does not
    adapt from a plain dict by itself."""
    from psycopg.types.json import Jsonb

    return [Jsonb(v) if k == "tags" else v for k, v in row.items()]


def _insert(row: dict[str, Any]) -> None:
    """Insert exactly what ``policy_to_row`` produced, under the tenant's RLS scope."""
    columns = ", ".join(row)
    placeholders = ", ".join(["%s"] * len(row))
    with psycopg.connect(DSN) as conn:
        conn.execute("SELECT set_config('dcc.tenant_id', %s, true)", (TENANT,))
        conn.execute(
            f"INSERT INTO dcc.backup_policies ({columns}) VALUES ({placeholders})",
            _db_params(row),
        )


@requires_db
def test_policytype_full_round_trips_through_the_api(tenant: str) -> None:
    """The headline: FULL + a schedule kind is stored, and read back intact.

    The chain is the one the product actually uses: ``PolicyEngine.create_policy``
    with the legacy ``PolicyType.FULL`` (what ``setup_tenant`` passes) writes a
    JSON policy; the policy is written to the table through the shared
    translation; ``/v2/dr/policies`` reads it back. Before migration 012 the
    write stopped at the table's CHECK constraint, so this test failed at the
    INSERT with ``new row ... violates check constraint
    "backup_policies_policy_type_check"``.
    """
    engine = PolicyEngine(Path(os.environ.get("TMPDIR", "/tmp")) / f"pol-{uuid.uuid4()}")
    created = engine.create_policy(
        tenant,
        "Weekly full with zstd",
        policy_type=PolicyType.FULL,
        schedule=PolicySchedule.WEEKLY,
        retention_days=14,
        tables=["assets", "evidence_events"],
        compression=Compression.ZSTD,
        tags={"owner": "sre", "ticket": "DR-14"},
    )

    # The record never stored the legacy enum.
    assert created.policy_type is PolicyTrigger.SCHEDULED
    assert created.backup_type is BackupType.FULL

    _insert(policy_to_row(created))

    from dcc import api_async

    payload = asyncio.run(
        api_async.list_backup_policies(tenant_id=tenant, enabled=None, limit=100, cursor=None)
    )

    items = payload["items"]
    assert len(items) == 1, payload
    item = items[0]

    # The API returns the record's own shape: every field, no more, no less.
    assert set(item) == set(created.to_dict())
    for field in ROW_COLUMNS:
        if field in ("created_at", "updated_at", "last_run_at", "next_run_at"):
            stored = (
                datetime.fromisoformat(item[field])
                if isinstance(item[field], str)
                else item[field]
            )
            assert stored == getattr(created, field), field
        else:
            assert item[field] == created.to_dict()[field], field

    # Spelled out, because these four are the defect.
    assert item["policy_type"] == "scheduled"  # WHEN it runs
    assert item["backup_type"] == "full"  # WHAT it writes
    assert item["compression"] == "zstd"  # a codec, not a bool
    assert item["status"] == "active"  # a lifecycle, not a run state
    assert item["schedule"] == "weekly"
    assert item["tables"] == ["assets", "evidence_events"]
    assert item["tags"] == {"owner": "sre", "ticket": "DR-14"}


@requires_db
def test_the_table_and_the_record_agree_on_the_column_set(tenant: str) -> None:
    """A column added to the table without the translation would be invisible."""
    with psycopg.connect(DSN) as conn:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='dcc' AND table_name='backup_policies'"
        ).fetchall()

    assert {r[0] for r in rows} == set(ROW_COLUMNS)


# ---------------------------------------------------------------------------
# 5. The constraints still reject genuinely bad values
# ---------------------------------------------------------------------------


@requires_db
def test_the_check_constraints_still_reject_bad_values(tenant: Any) -> None:
    """A widened CHECK would make the round trip above pass for the wrong reason.

    Each case is a value the *old* three-layer model would have produced: the
    old ``PolicyType.FULL`` written into ``policy_type``, a codec typo, a
    backup kind the engine cannot run, a run state in a lifecycle column, an
    array in the tags column, and the two internal contradictions.
    """
    good = policy_to_row(_policy())

    cases: list[tuple[str, dict[str, Any], str]] = [
        (
            "the old PolicyType.FULL in the trigger column",
            {"policy_type": "full", "backup_type": "full"},
            "backup_policies_policy_type_check",
        ),
        (
            "a codec that does not exist",
            {"compression": "bzip2"},
            "backup_policies_compression_check",
        ),
        (
            "a backup kind the engine cannot run",
            {"backup_type": "weekly"},
            "backup_policies_backup_type_check",
        ),
        (
            "a continuous policy claiming a discrete backup",
            {"policy_type": "continuous", "backup_type": "full"},
            "backup_policies_backup_type_check",
        ),
        (
            "a run state in the lifecycle column",
            # enabled=False so this case is decided by the status CHECK alone;
            # the enabled/status contradiction has its own case below.
            {"status": "pending", "enabled": False},
            "backup_policies_status_check",
        ),
        (
            "a cadence that does not exist",
            {"schedule": "fortnightly"},
            "backup_policies_schedule_check",
        ),
        (
            "a scheduled policy with no cadence",
            {"schedule": None},
            "backup_policies_schedule_coherence_check",
        ),
        (
            "a cron expression with no custom schedule",
            {"custom_cron": "0 2 * * *"},
            "backup_policies_schedule_coherence_check",
        ),
        (
            "enabled but paused",
            {"enabled": True, "status": "paused"},
            "backup_policies_lifecycle_check",
        ),
        (
            "an array in the tags object",
            {"tags": ["owner"]},
            "backup_policies_tags_check",
        ),
    ]

    for label, override, constraint in cases:
        row = {**good, **override, "name": f"bad-{uuid.uuid4().hex[:8]}"}
        columns = ", ".join(row)
        placeholders = ", ".join(["%s"] * len(row))
        conn = psycopg.connect(DSN)
        try:
            conn.execute("SELECT set_config('dcc.tenant_id', %s, true)", (TENANT,))
            with pytest.raises(psycopg.errors.CheckViolation) as exc:
                conn.execute(
                    f"INSERT INTO dcc.backup_policies ({columns}) VALUES ({placeholders})",
                    _db_params(row),
                )
        finally:
            # The failed statement aborted this transaction; roll it back so the
            # next case starts clean.
            conn.rollback()
            conn.close()
        message = str(exc.value)
        assert constraint in message, f"{label}: expected {constraint}, got {message}"
        print(f"REJECTED ({label}): {message.splitlines()[0]}")

    # Nothing was written by any rejected attempt.
    with psycopg.connect(DSN) as conn:
        conn.execute("SELECT set_config('dcc.tenant_id', %s, true)", (TENANT,))
        remaining = conn.execute(
            "SELECT count(*) FROM dcc.backup_policies WHERE tenant_id = %s", (TENANT,)
        ).fetchone()
    assert remaining[0] == 0
