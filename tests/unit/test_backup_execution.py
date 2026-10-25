"""A policy run must produce the artifact it claims, or report the failure.

The defect this file exists for: ``DROrchestrator.run_due_policies`` recorded
``success=True`` for every due policy and never called any backup engine. No
checkpoint was taken, no file was written, and the record said the backup
succeeded. Nothing in the API calls the method today, which is exactly why the
false record was worth removing before it got wired up: in a governance product a
stored "backup succeeded" for work that never happened is worse than no record.

The engine that really executes backups is
:class:`dcc.operations.backup.BackupEngine`, which shells out to ``pg_dump`` and
recomputes a SHA-256 over the written file. These tests therefore assert against
that engine's real output -- a file on disk with a size and checksum -- and
against the failure path (an unreachable DSN) that must be recorded, not raised
and not swallowed.

Requires ``pg_dump`` and a reachable PostgreSQL. The behaviour under test is a
real dump of a real database and a real checksum over the result; a fake engine
would only assert against the mock. Point ``DCC_DATABASE_URL`` at a seeded
database to override the default demo DSN.
"""

from __future__ import annotations

import contextlib
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

DSN = os.environ.get("DCC_DATABASE_URL") or "postgresql://localhost:5432/dcc_demo_local"

#: Seeded by database/seed*.sql in the demo database; must exist as a tenant row
#: for row counts to be measurable rather than absent.
SEEDED_TENANT = "dcc00000-0000-4000-8000-000000000001"

#: Nothing listens here: pg_dump exits non-zero, which is the real failure path.
UNREACHABLE_DSN = "postgresql://127.0.0.1:1/absolutely_no_database"


def _database_reachable() -> bool:
    try:
        import psycopg

        with psycopg.connect(DSN, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                cur.fetchone()
    except Exception:
        return False
    return True


needs_pg_dump = pytest.mark.skipif(
    shutil.which("pg_dump") is None,
    reason="pg_dump is not on PATH; the engine cannot take a backup without it",
)
needs_database = pytest.mark.skipif(
    not _database_reachable(),
    reason=f"no PostgreSQL reachable at {DSN}; the behaviour under test is a real dump",
)

pytestmark = [needs_pg_dump, needs_database]


@contextlib.contextmanager
def _dr_roots(tmp_path: Path, sub: str, *, mode: str = "installed", engine=None):
    """Orchestrator over throwaway roots, cleaned up whatever the test does.

    ``mode`` selects how the engine is (or is not) made available:
    ``installed`` through the composition root, ``injected`` by constructor, and
    ``none`` for the refusal path.

    Cleanup removes three things: the temp roots (so no backup is left on disk),
    any policy the test created (the policy engine uses the shared database when
    ``DCC_DATABASE_URL`` is set, so its rows must not outlive the test), and the
    process-global engine factory.
    """
    from dcc.dr.orchestrator import DROrchestrator, DROrchestratorConfig
    from dcc.operations.backup import install_dr_backup_execution

    root = tmp_path / sub
    config = DROrchestratorConfig(
        backup_root=str(root / "backups"),
        policy_root=str(root / "policies"),
        procedure_root=str(root / "procedures"),
        tracker_root=str(root / "tracking"),
        test_root=str(root / "dr_tests"),
    )
    assert Path(config.backup_root).resolve().is_relative_to(tmp_path.resolve()), (
        "backup root escaped the test temp dir"
    )

    if mode == "installed":
        install_dr_backup_execution()
        orchestrator = DROrchestrator(config)
    elif mode == "injected":
        DROrchestrator.use_backup_engine_factory(None)
        orchestrator = DROrchestrator(config, backup_engine=engine)
    else:
        DROrchestrator.use_backup_engine_factory(None)
        orchestrator = DROrchestrator(config)

    pre_existing = {
        policy.policy_id for policy in orchestrator.policy_engine.list_policies(SEEDED_TENANT)
    }
    try:
        yield orchestrator, root
    finally:
        for policy in orchestrator.policy_engine.list_policies(SEEDED_TENANT):
            if policy.policy_id not in pre_existing:
                try:
                    orchestrator.policy_engine.delete_policy(SEEDED_TENANT, policy.policy_id)
                except Exception:  # cleanup must not mask the test's own failure
                    pass
        DROrchestrator.use_backup_engine_factory(None)
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture()
def dr(tmp_path: Path):
    """An orchestrator wired to the real backup engine the way the app wires it."""
    with _dr_roots(tmp_path, "dr") as context:
        yield context


def _due_policy(orchestrator, tenant_id: str, *, policy_type=None, name: str = "Nightly Full"):
    """Create a policy and make it due by moving its next run into the past."""
    kwargs = {}
    if policy_type is not None:
        kwargs["policy_type"] = policy_type
    policy = orchestrator.create_backup_policy(tenant_id, name, **kwargs)
    orchestrator.policy_engine.update_policy(
        tenant_id,
        policy.policy_id,
        next_run_at=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
    )
    return policy


def _data_files(root: Path) -> list[Path]:
    """Every dump artifact under a backup root, compressed or not."""
    if not root.exists():
        return []
    return [p for p in root.rglob("data.sql*")]


# ---------------------------------------------------------------------------
# The reproduction: a claimed success must come with the artifact
# ---------------------------------------------------------------------------


def test_due_policy_writes_a_real_backup_that_verifies(dr) -> None:
    """success=True must mean a dump exists on disk, sized and checksummed."""
    from dcc.operations.backup import compute_file_checksum

    orchestrator, root = dr
    policy = _due_policy(orchestrator, SEEDED_TENANT)

    results = orchestrator.run_due_policies(SEEDED_TENANT, dsn=DSN)

    assert len(results) == 1, results
    run = results[0]
    assert run["policy_id"] == policy.policy_id
    assert run["success"] is True, f"backup did not succeed: {run}"
    backup_id = run["backup_id"]
    assert backup_id, f"success recorded without a backup id: {run}"

    artifacts = _data_files(root / "backups")
    assert len(artifacts) == 1, f"expected exactly one dump on disk, found {artifacts}"

    artifact = artifacts[0]
    assert artifact.parent.name == backup_id
    size = artifact.stat().st_size
    assert size > 0, f"dump is empty: {artifact}"
    checksum = compute_file_checksum(artifact)

    # The recorded run must describe the artifact that is actually on disk.
    assert run["size_bytes"] == size
    assert run["checksum"] == checksum

    metadata = orchestrator.backup_engine.get_backup(SEEDED_TENANT, backup_id)
    assert metadata.size_bytes == size
    assert metadata.checksum == checksum

    verification = orchestrator.backup_engine.verify_backup(SEEDED_TENANT, backup_id)
    assert verification.valid, verification.errors
    assert verification.checksum_match
    assert verification.size_match


def test_success_is_never_recorded_without_an_artifact(dr) -> None:
    """The regression: an unreachable database must not yield success=True."""
    orchestrator, root = dr
    _due_policy(orchestrator, SEEDED_TENANT)

    results = orchestrator.run_due_policies(SEEDED_TENANT, dsn=UNREACHABLE_DSN)

    assert len(results) == 1, results
    run = results[0]
    assert run["success"] is False, (
        "recorded success for a backup that never ran: "
        f"{run} (artifacts on disk: {_data_files(root / 'backups')})"
    )
    assert run["error"], f"a failed run must name why: {run}"
    assert _data_files(root / "backups") == [], "a failed dump left a dump artifact behind"


def test_failed_dump_is_recorded_as_failed_and_does_not_raise(dr) -> None:
    """A bad DSN is a recorded failure with a reason -- not an escaped exception."""
    from dcc.operations.backup import BackupStatus

    orchestrator, _root = dr
    _due_policy(orchestrator, SEEDED_TENANT)

    results = orchestrator.run_due_policies(SEEDED_TENANT, dsn=UNREACHABLE_DSN)

    run = results[0]
    assert run["success"] is False
    assert "pg_dump" in run["error"].lower() or "database" in run["error"].lower(), run["error"]

    # The engine keeps the failed attempt, so the failure is not only in memory.
    failed = orchestrator.backup_engine.list_backups(SEEDED_TENANT, status=BackupStatus.FAILED)
    assert failed, "no failed backup record was persisted"
    assert failed[0].error_message


def test_policy_type_the_engine_cannot_run_refuses_instead_of_claiming_success(dr) -> None:
    """SNAPSHOT has no engine equivalent; the run must say so, not fake a backup."""
    from dcc.dr.policies import PolicyType

    orchestrator, root = dr
    _due_policy(orchestrator, SEEDED_TENANT, policy_type=PolicyType.SNAPSHOT, name="Snapshots")

    results = orchestrator.run_due_policies(SEEDED_TENANT, dsn=DSN)

    run = results[0]
    assert run["success"] is False, f"claimed to have run an unsupported policy: {run}"
    assert "snapshot" in run["error"].lower(), run["error"]
    assert _data_files(root / "backups") == []


# ---------------------------------------------------------------------------
# The record itself: durable, honest, and readable after a restart
# ---------------------------------------------------------------------------


def test_run_ledger_keeps_the_failure_reason_across_a_restart(dr) -> None:
    """A failed run must survive a restart, not vanish with the process."""
    from dcc.dr.orchestrator import DROrchestrator
    from dcc.operations.backup import BackupStatus

    orchestrator, _root = dr
    _due_policy(orchestrator, SEEDED_TENANT)
    orchestrator.run_due_policies(SEEDED_TENANT, dsn=UNREACHABLE_DSN)

    restarted = DROrchestrator(orchestrator.config)
    records = restarted.list_policy_runs(SEEDED_TENANT)

    assert records, "no run record survived a restart"
    latest = records[-1]
    assert latest["success"] is False
    assert latest["error"]
    # A failed attempt may still own an id -- the engine writes a FAILED record --
    # but that id must never point at a completed backup.
    if latest["backup_id"]:
        engine = restarted.backup_engine
        assert engine is not None
        metadata = engine.get_backup(SEEDED_TENANT, latest["backup_id"])
        assert metadata.status is BackupStatus.FAILED


def test_run_ledger_keeps_the_backup_id_of_a_real_run(dr) -> None:
    from dcc.dr.orchestrator import DROrchestrator

    orchestrator, _root = dr
    _due_policy(orchestrator, SEEDED_TENANT)
    run = orchestrator.run_due_policies(SEEDED_TENANT, dsn=DSN)[0]
    assert run["success"] is True, run

    restarted = DROrchestrator(orchestrator.config)
    records = restarted.list_policy_runs(SEEDED_TENANT)
    assert records[-1]["backup_id"] == run["backup_id"]
    assert records[-1]["success"] is True


# ---------------------------------------------------------------------------
# The engine pieces the wiring depends on
# ---------------------------------------------------------------------------


def test_engine_can_be_injected_without_the_global_factory(tmp_path: Path) -> None:
    """Constructor injection is the alternative to the composition root."""
    from dcc.operations.backup import BackupEngine

    with _dr_roots(
        tmp_path, "injected", mode="injected", engine=BackupEngine(tmp_path / "injected" / "backups")
    ) as (orchestrator, root):
        _due_policy(orchestrator, SEEDED_TENANT)

        run = orchestrator.run_due_policies(SEEDED_TENANT, dsn=DSN)[0]

        assert run["success"] is True, run
        assert (root / "backups" / SEEDED_TENANT / run["backup_id"]).is_dir()


def test_no_execution_layer_refuses_instead_of_claiming_a_backup(tmp_path: Path) -> None:
    """With no engine installed, a run must refuse -- the old code's exact lie."""
    with _dr_roots(tmp_path, "bare", mode="none") as (orchestrator, root):
        _due_policy(orchestrator, SEEDED_TENANT)

        results = orchestrator.run_due_policies(SEEDED_TENANT, dsn=DSN)

        run = results[0]
        assert run["success"] is False, f"claimed a backup with no engine: {run}"
        assert "no backup engine configured" in run["error"], run["error"]
        assert _data_files(root / "backups") == []
        # The refusal is durable too, so it is visible after a restart.
        assert orchestrator.list_policy_runs(SEEDED_TENANT)[-1]["success"] is False


def test_row_counts_are_still_measured_not_zeroed(dr) -> None:
    """``_get_row_counts`` still measures what it can and omits what it cannot."""
    orchestrator, _root = dr
    engine = orchestrator.backup_engine

    counts = engine._get_row_counts(dsn=DSN, tenant_id=SEEDED_TENANT, tables=["assets", "tenants"])

    assert "assets" in counts, f"assets was not measured: {counts}"
    assert isinstance(counts["assets"], int) and counts["assets"] >= 0
    assert "tenants" not in counts, "dcc.tenants has no tenant_id and must be omitted"

    unreachable = engine._get_row_counts(
        dsn=UNREACHABLE_DSN, tenant_id=SEEDED_TENANT, tables=["assets"]
    )
    assert unreachable == {}, f"an unreachable database measured {unreachable}"


def test_test_runs_never_touch_the_real_backup_directory() -> None:
    """The default ``dcc_backups`` path is never created by a test run."""
    assert not (Path.cwd() / "dcc_backups").exists(), (
        "a test wrote to the real dcc_backups directory"
    )
