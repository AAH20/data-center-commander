"""Directory-format backups: incremental and differential dumps must be real.

The defect these tests exist for: ``pg_dump --format=directory`` writes a
*directory*, and ``create_backup`` then tried to gzip it as if it were a file::

    IsADirectoryError: [Errno 21] Is a directory: '.../data.sql'

so every incremental and differential backup failed, including the
``Hourly Incremental`` policy ``DROrchestrator.setup_tenant`` installs by
default. The product advertised a backup mode that could not produce a usable
artifact.

The design decisions, which these tests pin:

* **Artifact.** A directory dump is written to ``data.dir/`` beside
  ``metadata.json`` -- a different name from the plain ``data.sql`` so the two
  shapes cannot be confused again -- and is never wrapped in gzip.
* **size_bytes** is the sum of the regular files inside that directory. Not the
  directory inode's size (filesystem-dependent) and not a tar's size (a tar is
  a second artifact ``pg_restore`` cannot read).
* **checksum** is a SHA-256 over a canonical manifest of
  ``(relative path, size, per-file SHA-256)``, sorted by path, with no mtimes
  and no absolute paths -- so it is reproducible on any copy, in any location.
* **compression** for a directory artifact is handed to ``pg_dump -Z`` (its own,
  per-data-file compression); the engine refuses to wrap the directory
  afterwards. ``GZIP`` -> ``-Z 6``, ``NONE`` -> ``-Z 0``.
* **verify_backup** reads the shape from metadata and measures a tree over its
  contents; it requires ``toc.dat`` because ``pg_restore`` cannot read a tree
  without it.
* **restore** uses ``pg_restore --format=directory`` for a directory artifact and
  ``psql`` for a plain one. A backup is only recorded successful if
  ``pg_restore --list`` can read its table of contents.
"""

from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dcc.operations.backup import (
    ArtifactFormat,
    BackupEngine,
    BackupError,
    BackupMetadata,
    BackupStatus,
    BackupType,
    CompressionType,
    compute_directory_checksum,
    compute_file_checksum,
    directory_size,
    iter_artifact_files,
)

TENANT = "dcc00000-0000-4000-8000-000000000001"
DSN = os.environ.get("DCC_DATABASE_URL") or "postgresql://localhost:5432/dcc_demo_local"

#: Nothing listens on port 1: pg_dump exits non-zero, which is the real failure path.
UNREACHABLE_DSN = "postgresql://127.0.0.1:1/absolutely_no_database"


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine(tmp_path: Path) -> BackupEngine:
    """An engine over a throwaway root that is deleted with the test."""
    return BackupEngine(tmp_path / "backups")


def _write_dir_artifact(path: Path, *, data: bytes = b"row\n" * 50, compress: bool = True) -> None:
    """Write a minimal but structurally faithful pg_dump -Fd tree."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "toc.dat").write_bytes(b"PGDMP\x00fake-toc")
    name = "3855.dat.gz" if compress else "3855.dat"
    payload = gzip.compress(data) if compress else data
    (path / name).write_bytes(payload)


def _fake_pg_dump(*, compress: bool = True):
    """A stand-in for pg_dump that writes the artifact the real one would."""

    def run(
        self,
        *,
        dsn,
        output_path,
        tables,
        backup_type,
        parent_id,
        data_format=None,
        compression=CompressionType.NONE,
    ):
        if data_format == ArtifactFormat.DIRECTORY:
            _write_dir_artifact(output_path, compress=compress)
        else:
            output_path.write_text("-- plain sql dump\n", encoding="utf-8")

    return run


# ---------------------------------------------------------------------------
# The checksum: a canonical manifest, not a digest of bytes-in-an-order
# ---------------------------------------------------------------------------


def test_directory_checksum_is_reproducible(tmp_path: Path) -> None:
    """Two computations over one artifact must agree -- the brief's explicit ask."""
    artifact = tmp_path / "data.dir"
    _write_dir_artifact(artifact)

    first = compute_directory_checksum(artifact)
    second = compute_directory_checksum(artifact)

    assert first == second
    assert len(first) == 64 and int(first, 16) >= 0  # a hex SHA-256 digest


def test_directory_checksum_ignores_mtime_and_location(tmp_path: Path) -> None:
    """A copied artifact verifies: mtimes and absolute paths are not in the pre-image."""
    artifact = tmp_path / "a" / "data.dir"
    _write_dir_artifact(artifact)
    original = compute_directory_checksum(artifact)

    copy = tmp_path / "elsewhere" / "renamed.dir"
    shutil.copytree(artifact, copy)
    os.utime(copy / "toc.dat", (1_000_000, 1_000_000))
    os.utime(copy / "3855.dat.gz", (2_000_000, 2_000_000))

    assert compute_directory_checksum(copy) == original


def test_directory_checksum_detects_changed_and_added_files(tmp_path: Path) -> None:
    """Content and layout are both covered, so tampering cannot pass verification."""
    artifact = tmp_path / "data.dir"
    _write_dir_artifact(artifact)
    baseline = compute_directory_checksum(artifact)

    (artifact / "3855.dat.gz").write_bytes(gzip.compress(b"different rows\n"))
    assert compute_directory_checksum(artifact) != baseline

    _write_dir_artifact(artifact)
    assert compute_directory_checksum(artifact) == baseline

    (artifact / "9999.dat").write_bytes(b"an extra table")
    assert compute_directory_checksum(artifact) != baseline


def test_directory_size_sums_the_regular_files(tmp_path: Path) -> None:
    """size_bytes is what the tree occupies, not the directory inode's size."""
    artifact = tmp_path / "data.dir"
    _write_dir_artifact(artifact)

    expected = sum(p.stat().st_size for p in artifact.rglob("*") if p.is_file())
    assert directory_size(artifact) == expected
    assert directory_size(artifact) != artifact.stat().st_size
    assert sorted(rel for rel, _size in iter_artifact_files(artifact)) == [
        "3855.dat.gz",
        "toc.dat",
    ]


def test_directory_measurements_refuse_a_file(tmp_path: Path) -> None:
    """A plain file is not a directory artifact, and is not measured as one."""
    plain = tmp_path / "data.sql"
    plain.write_text("-- sql\n", encoding="utf-8")

    with pytest.raises(BackupError) as checksum_error:
        compute_directory_checksum(plain)
    assert checksum_error.value.code == "artifact_not_a_directory"

    with pytest.raises(BackupError) as size_error:
        directory_size(plain)
    assert size_error.value.code == "artifact_not_a_directory"


# ---------------------------------------------------------------------------
# The reproduction itself: compression must never be applied to a directory
# ---------------------------------------------------------------------------


def test_compress_file_refuses_a_directory_artifact(engine: BackupEngine, tmp_path: Path) -> None:
    """The exact defect, now a named refusal instead of IsADirectoryError."""
    artifact = tmp_path / "data.dir"
    _write_dir_artifact(artifact)
    dest = tmp_path / "data.sql.gz"

    with pytest.raises(BackupError) as excinfo:
        engine._compress_file(artifact, dest)

    assert excinfo.value.code == "directory_artifact_compression"
    assert "pg_dump -Fd" in str(excinfo.value)
    assert not dest.exists()


def test_incremental_backup_records_a_directory_artifact(
    engine: BackupEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """create_backup never gzips a directory dump, and measures the tree instead."""
    monkeypatch.setattr(BackupEngine, "_run_pg_dump", _fake_pg_dump())
    monkeypatch.setattr(BackupEngine, "_assert_restorable", lambda self, path: None)
    monkeypatch.setattr(BackupEngine, "_get_row_counts", lambda self, **kw: {})

    def forbidden(self, source, dest):  # pragma: no cover - fired only on regression
        raise AssertionError(f"_compress_file called on {source} during a directory backup")

    monkeypatch.setattr(BackupEngine, "_compress_file", forbidden)

    result = engine.create_backup(TENANT, backup_type=BackupType.INCREMENTAL, dsn="dsn")

    assert result.success, result.message
    meta = result.metadata
    assert meta is not None
    assert meta.data_format == ArtifactFormat.DIRECTORY
    assert meta.compression == CompressionType.GZIP

    artifact = engine._dir_artifact_path(TENANT, meta.backup_id)
    assert artifact.is_dir(), "the artifact must still be a directory"
    assert (artifact / "toc.dat").is_file()
    assert not engine._data_path(TENANT, meta.backup_id, compressed=True).exists()

    assert meta.size_bytes == directory_size(artifact)
    assert meta.checksum == compute_directory_checksum(artifact)
    assert meta.size_bytes > 0

    verification = engine.verify_backup(TENANT, meta.backup_id)
    assert verification.valid, verification.errors
    assert verification.checksum_match and verification.size_match


def test_differential_backup_uses_the_directory_format_too(
    engine: BackupEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(BackupEngine, "_run_pg_dump", _fake_pg_dump(compress=False))
    monkeypatch.setattr(BackupEngine, "_assert_restorable", lambda self, path: None)
    monkeypatch.setattr(BackupEngine, "_get_row_counts", lambda self, **kw: {})

    result = engine.create_backup(
        TENANT,
        backup_type=BackupType.DIFFERENTIAL,
        compression=CompressionType.NONE,
        dsn="dsn",
    )

    assert result.success, result.message
    meta = result.metadata
    assert meta is not None and meta.data_format == ArtifactFormat.DIRECTORY
    artifact = engine._dir_artifact_path(TENANT, meta.backup_id)
    assert artifact.is_dir()
    assert not any(p.name.endswith(".gz") for p in artifact.iterdir())


def test_full_backup_stays_a_gzipped_plain_file(
    engine: BackupEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The file-based format is untouched: same shape, same size, same checksum."""
    monkeypatch.setattr(BackupEngine, "_run_pg_dump", _fake_pg_dump())
    monkeypatch.setattr(BackupEngine, "_get_row_counts", lambda self, **kw: {})

    result = engine.create_backup(TENANT, backup_type=BackupType.FULL, dsn="dsn")

    assert result.success, result.message
    meta = result.metadata
    assert meta is not None and meta.data_format == ArtifactFormat.PLAIN

    artifact = engine._data_path(TENANT, meta.backup_id, compressed=True)
    assert artifact.is_file()
    assert not engine._dir_artifact_path(TENANT, meta.backup_id).exists()
    with gzip.open(artifact, "rb") as handle:
        assert handle.read() == b"-- plain sql dump\n"

    assert meta.size_bytes == artifact.stat().st_size
    assert meta.checksum == compute_file_checksum(artifact)
    assert engine.verify_backup(TENANT, meta.backup_id).valid


def test_pg_dump_compression_level_is_passed_through() -> None:
    """compression selects pg_dump's own -Z level for a directory artifact."""
    assert BackupEngine._pg_dump_compression_level(CompressionType.GZIP) == 6
    assert BackupEngine._pg_dump_compression_level(CompressionType.NONE) == 0


def test_directory_dump_command_uses_format_directory_and_z(
    engine: BackupEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dump command itself: -Fd plus -Z, and no external compression step."""
    captured: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        captured.append(list(cmd))
        Path(cmd[cmd.index("--file") + 1]).mkdir(parents=True, exist_ok=True)

        class Result:
            returncode = 0
            stderr = ""
            stdout = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    engine._run_pg_dump(
        dsn="postgresql://example/db",
        output_path=engine._dir_artifact_path(TENANT, "b"),
        tables=["assets"],
        backup_type=BackupType.INCREMENTAL,
        parent_id=None,
        data_format=ArtifactFormat.DIRECTORY,
        compression=CompressionType.GZIP,
    )

    cmd = captured[0]
    assert "--format=directory" in cmd
    assert cmd[cmd.index("-Z") + 1] == "6"
    assert cmd[cmd.index("--table") + 1] == "dcc.assets"


# ---------------------------------------------------------------------------
# Verification: an honest answer for both shapes
# ---------------------------------------------------------------------------


def _directory_metadata(engine: BackupEngine, tmp_path: Path, *, checksum: str | None = None) -> BackupMetadata:
    artifact = engine._dir_artifact_path(TENANT, "b0000000-0000-4000-8000-0000000000d1")
    _write_dir_artifact(artifact)
    meta = BackupMetadata(
        backup_id="b0000000-0000-4000-8000-0000000000d1",
        tenant_id=TENANT,
        backup_type=BackupType.INCREMENTAL,
        status=BackupStatus.COMPLETED,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        size_bytes=directory_size(artifact),
        checksum=checksum if checksum is not None else compute_directory_checksum(artifact),
        compression=CompressionType.GZIP,
        data_format=ArtifactFormat.DIRECTORY,
        tables=["assets"],
    )
    engine._write_metadata(meta)
    return meta


def test_verify_accepts_an_intact_directory_artifact(
    engine: BackupEngine, tmp_path: Path
) -> None:
    meta = _directory_metadata(engine, tmp_path)

    result = engine.verify_backup(TENANT, meta.backup_id)

    assert result.valid, result.errors
    assert result.checksum_match and result.size_match and result.metadata_valid
    assert result.errors == []


def test_verify_rejects_a_tampered_directory_artifact(
    engine: BackupEngine, tmp_path: Path
) -> None:
    meta = _directory_metadata(engine, tmp_path)
    (engine._dir_artifact_path(TENANT, meta.backup_id) / "3855.dat.gz").write_bytes(b"tampered")

    result = engine.verify_backup(TENANT, meta.backup_id)

    assert not result.valid
    assert not result.checksum_match
    assert any("checksum mismatch" in error for error in result.errors)


def test_verify_rejects_a_directory_without_a_table_of_contents(
    engine: BackupEngine, tmp_path: Path
) -> None:
    """A tree pg_restore cannot read must not verify, whatever its checksum says."""
    meta = _directory_metadata(engine, tmp_path)
    (engine._dir_artifact_path(TENANT, meta.backup_id) / "toc.dat").unlink()

    result = engine.verify_backup(TENANT, meta.backup_id)

    assert not result.valid
    assert any("toc.dat" in error for error in result.errors)


def test_verify_reports_a_missing_directory_artifact(
    engine: BackupEngine, tmp_path: Path
) -> None:
    meta = _directory_metadata(engine, tmp_path)
    shutil.rmtree(engine._dir_artifact_path(TENANT, meta.backup_id))

    result = engine.verify_backup(TENANT, meta.backup_id)

    assert not result.valid
    assert any("directory artifact not found" in error for error in result.errors)


def test_legacy_metadata_without_data_format_reads_as_plain() -> None:
    """Old records predate this field and were plain files; they must not be guessed at."""
    legacy = {
        "backup_id": "b0000000-0000-4000-8000-000000000001",
        "tenant_id": TENANT,
        "backup_type": "full",
        "status": "completed",
        "created_at": "2026-01-01T00:00:00+00:00",
        "compression": "gzip",
    }

    meta = BackupMetadata.from_dict(legacy)

    assert meta.data_format == ArtifactFormat.PLAIN
    assert meta.to_dict()["data_format"] == "plain"


# ---------------------------------------------------------------------------
# End to end: a real dump, a real restore, a real failure
# ---------------------------------------------------------------------------

needs_pg_dump = pytest.mark.skipif(
    shutil.which("pg_dump") is None,
    reason="pg_dump is not on PATH; a directory artifact cannot be produced without it",
)
needs_pg_restore = pytest.mark.skipif(
    shutil.which("pg_restore") is None,
    reason="pg_restore is not on PATH; a directory artifact cannot be read or restored without it",
)
needs_psql = pytest.mark.skipif(
    shutil.which("psql") is None or shutil.which("createdb") is None,
    reason="psql/createdb are not on PATH; a scratch restore target cannot be created",
)


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


needs_database = pytest.mark.skipif(
    not _database_reachable(),
    reason=f"no PostgreSQL reachable at {DSN}; the behaviour under test is a real dump",
)


def _dsn_for(database: str) -> str:
    """Point the configured DSN at another database, keeping host and credentials."""
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    return make_conninfo(**{**conninfo_to_dict(DSN), "dbname": database})


class _ScratchDatabase:
    """A throwaway database that is dropped even when the test fails."""

    def __init__(self) -> None:
        self.name = f"dcc_probe_{uuid.uuid4().hex[:12]}"

    def __enter__(self) -> str:
        import psycopg

        with psycopg.connect(_dsn_for("postgres"), autocommit=True, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(f'CREATE DATABASE "{self.name}"')
        return _dsn_for(self.name)

    def __exit__(self, *exc_info) -> None:
        import psycopg

        with psycopg.connect(_dsn_for("postgres"), autocommit=True, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(f'DROP DATABASE IF EXISTS "{self.name}" WITH (FORCE)')


def _count(dsn: str, sql: str) -> int:
    import psycopg

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()[0]


@needs_pg_dump
@needs_pg_restore
@needs_psql
@needs_database
def test_incremental_backup_verifies_and_restores_into_a_scratch_database(
    engine: BackupEngine,
) -> None:
    """The whole claim, against a real database: dump -> checksum -> verify -> restore."""
    result = engine.create_backup(
        TENANT, backup_type=BackupType.INCREMENTAL, dsn=DSN, tables=["assets"]
    )
    assert result.success, result.error or result.message
    meta = result.metadata
    assert meta is not None and meta.data_format == ArtifactFormat.DIRECTORY

    artifact = engine._dir_artifact_path(TENANT, meta.backup_id)
    assert artifact.is_dir(), f"incremental artifact is not a directory: {artifact}"
    assert (artifact / "toc.dat").is_file()

    # size and checksum are reproducible, and agree with what was recorded
    first = compute_directory_checksum(artifact)
    second = compute_directory_checksum(artifact)
    assert first == second == meta.checksum
    assert directory_size(artifact) == meta.size_bytes > 0

    verification = engine.verify_backup(TENANT, meta.backup_id)
    assert verification.valid, verification.errors

    with _ScratchDatabase() as scratch_dsn:
        restored = engine.restore_backup(
            TENANT, meta.backup_id, dsn=scratch_dsn, tables=["assets"]
        )
        assert restored.success, restored.error or restored.message

        table_count = _count(
            scratch_dsn,
            "select count(*) from information_schema.tables where table_schema = 'dcc'",
        )
        rows = _count(scratch_dsn, "select count(*) from dcc.assets")
        source_rows = _count(DSN, "select count(*) from dcc.assets")

    assert table_count >= 1, "the restore created no tables"
    assert rows == source_rows > 0, f"restored {rows} rows against {source_rows} in the source"


@needs_pg_dump
@needs_pg_restore
@needs_database
def test_a_directory_backup_that_cannot_be_read_is_not_recorded_successful(
    engine: BackupEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pg_dump wrote something, but pg_restore cannot read it: that is a failure."""

    def garbage_dump(self, *, output_path, **kwargs):
        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / "toc.dat").write_bytes(b"not a real archive")
        (output_path / "3855.dat").write_bytes(b"not real data")

    monkeypatch.setattr(BackupEngine, "_run_pg_dump", garbage_dump)

    result = engine.create_backup(
        TENANT, backup_type=BackupType.INCREMENTAL, dsn=DSN, tables=["assets"]
    )

    assert result.success is False, "recorded success for an artifact pg_restore cannot read"
    assert "restor" in (result.error or "").lower(), result.error
    assert not engine._dir_artifact_path(TENANT, result.backup_id).exists(), (
        "a failed backup left its artifact behind"
    )


@needs_pg_dump
def test_failed_incremental_records_a_reason_and_no_artifact(engine: BackupEngine) -> None:
    """A bogus DSN is a recorded failure with a reason -- and no artifact on disk."""
    result = engine.create_backup(
        TENANT, backup_type=BackupType.INCREMENTAL, dsn=UNREACHABLE_DSN, tables=["assets"]
    )

    assert result.success is False
    assert result.error and "pg_dump" in result.error.lower()
    assert result.metadata is not None and result.metadata.status == BackupStatus.FAILED
    assert result.metadata.error_message

    assert not engine._dir_artifact_path(TENANT, result.backup_id).exists()
    assert not engine._data_path(TENANT, result.backup_id, compressed=True).exists()
    # The failed attempt is still recorded, so the failure is durable.
    assert engine.get_backup(TENANT, result.backup_id).status == BackupStatus.FAILED


# ---------------------------------------------------------------------------
# The policy that was permanently broken
# ---------------------------------------------------------------------------

@needs_pg_dump
@needs_pg_restore
@needs_database
def test_default_hourly_incremental_policy_now_produces_a_real_artifact(tmp_path: Path) -> None:
    """``setup_tenant``'s default incremental policy must actually back the data up."""
    from dcc.dr.orchestrator import DROrchestrator, DROrchestratorConfig
    from dcc.operations.backup import install_dr_backup_execution

    config = DROrchestratorConfig(
        backup_root=str(tmp_path / "backups"),
        policy_root=str(tmp_path / "policies"),
        procedure_root=str(tmp_path / "procedures"),
        tracker_root=str(tmp_path / "tracking"),
        test_root=str(tmp_path / "dr_tests"),
    )

    install_dr_backup_execution()
    try:
        orchestrator = DROrchestrator(config)
        setUp = orchestrator.setup_tenant(TENANT)

        policies = {
            policy.policy_id: policy
            for policy in orchestrator.policy_engine.list_policies(TENANT)
        }
        incremental = [p for p in policies.values() if p.name == "Hourly Incremental"]
        assert incremental, f"setup_tenant created no incremental policy: {setUp}"
        policy = incremental[0]

        # Make the policy due without waiting an hour.
        from datetime import timedelta

        orchestrator.policy_engine.update_policy(
            TENANT,
            policy.policy_id,
            next_run_at=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
        )

        runs = orchestrator.run_due_policies(TENANT, dsn=DSN)
        run = [r for r in runs if r["policy_id"] == policy.policy_id][0]

        assert run["success"] is True, run
        assert run["verified"] is True, run
        artifact = orchestrator.backup_engine._dir_artifact_path(TENANT, run["backup_id"])
        assert artifact.is_dir()
        assert (artifact / "toc.dat").is_file()
    finally:
        from dcc.dr.orchestrator import DROrchestrator as Orchestrator

        Orchestrator.use_backup_engine_factory(None)

    # Nothing this test created survives it: the roots live under tmp_path.
    assert not (Path.cwd() / "dcc_backups").exists()
