"""Tests for the backup and restore engine."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from dcc.operations.backup import (
    BackupCorruptedError,
    BackupEngine,
    BackupError,
    BackupMetadata,
    BackupNotFoundError,
    BackupResult,
    BackupScheduler,
    BackupStatus,
    BackupType,
    CompressionType,
    PITRPoint,
    RestoreError,
    RestoreMetadata,
    RestoreResult,
    RestoreStatus,
    RetentionPolicy,
    RetentionPolicyError,
    VerificationResult,
    compress_data,
    compute_checksum,
    compute_file_checksum,
    create_backup,
    decompress_data,
    list_backups,
    restore_backup,
    validate_backup_id,
    validate_tenant_id,
    verify_backup,
    verify_checksum,
)


def _make_metadata(
    *,
    backup_id: str = "b0000000-0000-4000-8000-000000000001",
    tenant_id: str = "t0000000-0000-4000-8000-000000000001",
    status: BackupStatus = BackupStatus.COMPLETED,
    backup_type: BackupType = BackupType.FULL,
    created_at: datetime | None = None,
    size_bytes: int = 1024,
    checksum: str = "",
    compression: CompressionType = CompressionType.NONE,
    tables: list[str] | None = None,
    row_counts: dict[str, int] | None = None,
    parent_backup_id: str | None = None,
    point_in_time: datetime | None = None,
    completed_at: datetime | None = None,
) -> BackupMetadata:
    return BackupMetadata(
        backup_id=backup_id,
        tenant_id=tenant_id,
        backup_type=backup_type,
        status=status,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=completed_at,
        size_bytes=size_bytes,
        checksum=checksum,
        compression=compression,
        tables=tables or ["tenants", "assets"],
        row_counts=row_counts or {"tenants": 1, "assets": 10},
        parent_backup_id=parent_backup_id,
        point_in_time=point_in_time,
    )


class TestChecksum(unittest.TestCase):
    def test_compute_checksum(self):
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        self.assertEqual(compute_checksum(data), expected)

    def test_compute_checksum_empty(self):
        self.assertEqual(compute_checksum(b""), hashlib.sha256(b"").hexdigest())

    def test_verify_checksum_valid(self):
        data = b"test data"
        checksum = compute_checksum(data)
        self.assertTrue(verify_checksum(data, checksum))

    def test_verify_checksum_invalid(self):
        self.assertFalse(verify_checksum(b"data", "0" * 64))

    def test_compute_file_checksum(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"file content")
            f.flush()
            path = f.name
        try:
            expected = hashlib.sha256(b"file content").hexdigest()
            self.assertEqual(compute_file_checksum(path), expected)
        finally:
            os.unlink(path)


class TestCompression(unittest.TestCase):
    def test_compress_decompress_roundtrip(self):
        data = b"x" * 10000
        compressed = compress_data(data, CompressionType.GZIP)
        self.assertLess(len(compressed), len(data))
        decompressed = decompress_data(compressed, CompressionType.GZIP)
        self.assertEqual(decompressed, data)

    def test_no_compression(self):
        data = b"hello"
        self.assertEqual(compress_data(data, CompressionType.NONE), data)
        self.assertEqual(decompress_data(data, CompressionType.NONE), data)

    def test_unsupported_compression(self):
        with self.assertRaises(BackupError):
            compress_data(b"data", "lz4")  # type: ignore[arg-type]


class TestBackupMetadata(unittest.TestCase):
    def test_to_dict_from_dict_roundtrip(self):
        meta = _make_metadata(
            point_in_time=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 6, 15, 12, 5, tzinfo=timezone.utc),
        )
        d = meta.to_dict()
        restored = BackupMetadata.from_dict(d)
        self.assertEqual(restored.backup_id, meta.backup_id)
        self.assertEqual(restored.tenant_id, meta.tenant_id)
        self.assertEqual(restored.backup_type, meta.backup_type)
        self.assertEqual(restored.status, meta.status)
        self.assertEqual(restored.created_at, meta.created_at)
        self.assertEqual(restored.completed_at, meta.completed_at)
        self.assertEqual(restored.size_bytes, meta.size_bytes)
        self.assertEqual(restored.checksum, meta.checksum)
        self.assertEqual(restored.compression, meta.compression)
        self.assertEqual(restored.tables, meta.tables)
        self.assertEqual(restored.row_counts, meta.row_counts)
        self.assertEqual(restored.point_in_time, meta.point_in_time)

    def test_from_dict_minimal(self):
        data = {
            "backup_id": "b0000000-0000-4000-8000-000000000001",
            "tenant_id": "t0000000-0000-4000-8000-000000000001",
            "backup_type": "full",
            "status": "completed",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        meta = BackupMetadata.from_dict(data)
        self.assertEqual(meta.backup_type, BackupType.FULL)
        self.assertEqual(meta.status, BackupStatus.COMPLETED)
        self.assertIsNone(meta.completed_at)
        self.assertIsNone(meta.point_in_time)


class TestRetentionPolicy(unittest.TestCase):
    def test_defaults(self):
        p = RetentionPolicy()
        self.assertEqual(p.keep_daily, 7)
        self.assertEqual(p.keep_weekly, 4)
        self.assertEqual(p.keep_monthly, 12)
        self.assertEqual(p.keep_yearly, 3)
        self.assertEqual(p.max_age_days, 365)
        self.assertEqual(p.min_backups, 1)

    def test_from_dict(self):
        data = {"keep_daily": 3, "keep_weekly": 2, "max_age_days": 90}
        p = RetentionPolicy.from_dict(data)
        self.assertEqual(p.keep_daily, 3)
        self.assertEqual(p.keep_weekly, 2)
        self.assertEqual(p.max_age_days, 90)

    def test_from_none(self):
        p = RetentionPolicy.from_dict(None)
        self.assertEqual(p.keep_daily, 7)

    def test_invalid_negative(self):
        with self.assertRaises(RetentionPolicyError):
            RetentionPolicy(keep_daily=-1)

    def test_invalid_bool(self):
        with self.assertRaises(RetentionPolicyError):
            RetentionPolicy(keep_daily=True)  # type: ignore[arg-type]

    def test_to_dict(self):
        p = RetentionPolicy(keep_daily=5)
        d = p.to_dict()
        self.assertEqual(d["keep_daily"], 5)
        self.assertIn("max_age_days", d)


class TestValidation(unittest.TestCase):
    def test_validate_tenant_id_valid(self):
        self.assertEqual(
            validate_tenant_id("dcc00000-0000-4000-8000-000000000001"),
            "dcc00000-0000-4000-8000-000000000001",
        )

    def test_validate_tenant_id_invalid(self):
        with self.assertRaises(ValueError):
            validate_tenant_id("not-a-uuid")

    def test_validate_tenant_id_not_string(self):
        with self.assertRaises(ValueError):
            validate_tenant_id(123)  # type: ignore[arg-type]

    def test_validate_backup_id_valid(self):
        self.assertEqual(
            validate_backup_id("b0000000-0000-4000-8000-000000000001"),
            "b0000000-0000-4000-8000-000000000001",
        )

    def test_validate_backup_id_invalid(self):
        with self.assertRaises(ValueError):
            validate_backup_id("bad")


class TestBackupEngineInit(unittest.TestCase):
    def test_creates_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "backups"
            self.assertFalse(root.exists())
            engine = BackupEngine(root)
            self.assertTrue(root.exists())

    def test_resolves_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = BackupEngine(tmp)
            self.assertEqual(engine.backup_root, Path(tmp).resolve())


class TestBackupEngineMetadata(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = BackupEngine(self.tmp.name)
        self.tenant_id = "t0000000-0000-4000-8000-000000000001"

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_and_read_metadata(self):
        meta = _make_metadata(tenant_id=self.tenant_id)
        self.engine._write_metadata(meta)
        restored = self.engine._read_metadata(self.tenant_id, meta.backup_id)
        self.assertEqual(restored.backup_id, meta.backup_id)
        self.assertEqual(restored.tenant_id, meta.tenant_id)

    def test_read_missing_metadata(self):
        with self.assertRaises(BackupNotFoundError):
            self.engine._read_metadata(self.tenant_id, "nonexistent")

    def test_metadata_path_structure(self):
        meta = _make_metadata(tenant_id=self.tenant_id)
        path = self.engine._metadata_path(self.tenant_id, meta.backup_id)
        self.assertEqual(path.name, "metadata.json")
        self.assertIn(self.tenant_id, str(path))


class TestBackupEngineList(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = BackupEngine(self.tmp.name)
        self.tenant_id = "t0000000-0000-4000-8000-000000000001"

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_empty(self):
        self.assertEqual(self.engine.list_backups(self.tenant_id), [])

    def test_list_with_backups(self):
        for i in range(3):
            meta = _make_metadata(
                backup_id=f"b0000000-0000-4000-8000-00000000000{i}",
                tenant_id=self.tenant_id,
                created_at=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
            )
            self.engine._write_metadata(meta)

        backups = self.engine.list_backups(self.tenant_id)
        self.assertEqual(len(backups), 3)
        # Newest first
        self.assertEqual(backups[0].created_at.day, 3)

    def test_list_filter_by_type(self):
        full = _make_metadata(
            backup_id="b0000000-0000-4000-8000-000000000001",
            tenant_id=self.tenant_id,
            backup_type=BackupType.FULL,
        )
        incr = _make_metadata(
            backup_id="b0000000-0000-4000-8000-000000000002",
            tenant_id=self.tenant_id,
            backup_type=BackupType.INCREMENTAL,
        )
        self.engine._write_metadata(full)
        self.engine._write_metadata(incr)

        fulls = self.engine.list_backups(self.tenant_id, backup_type=BackupType.FULL)
        self.assertEqual(len(fulls), 1)
        self.assertEqual(fulls[0].backup_type, BackupType.FULL)

    def test_list_filter_by_status(self):
        completed = _make_metadata(
            backup_id="b0000000-0000-4000-8000-000000000001",
            tenant_id=self.tenant_id,
            status=BackupStatus.COMPLETED,
        )
        failed = _make_metadata(
            backup_id="b0000000-0000-4000-8000-000000000002",
            tenant_id=self.tenant_id,
            status=BackupStatus.FAILED,
        )
        self.engine._write_metadata(completed)
        self.engine._write_metadata(failed)

        completed_list = self.engine.list_backups(self.tenant_id, status=BackupStatus.COMPLETED)
        self.assertEqual(len(completed_list), 1)

    def test_list_limit(self):
        for i in range(10):
            meta = _make_metadata(
                backup_id=f"b0000000-0000-4000-8000-{i:012d}",
                tenant_id=self.tenant_id,
            )
            self.engine._write_metadata(meta)

        backups = self.engine.list_backups(self.tenant_id, limit=5)
        self.assertEqual(len(backups), 5)

    def test_list_skips_non_backup_dirs(self):
        # Create a non-backup directory
        tenant_dir = self.engine._tenant_dir(self.tenant_id)
        tenant_dir.mkdir(parents=True)
        (tenant_dir / "_retention_policy.json").write_text("{}")

        backups = self.engine.list_backups(self.tenant_id)
        self.assertEqual(len(backups), 0)


class TestBackupEngineVerify(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = BackupEngine(self.tmp.name)
        self.tenant_id = "t0000000-0000-4000-8000-000000000001"

    def tearDown(self):
        self.tmp.cleanup()

    def test_verify_valid_backup(self):
        data = b"backup data content"
        backup_id = "b0000000-0000-4000-8000-000000000001"
        backup_dir = self.engine._backup_dir(self.tenant_id, backup_id)
        backup_dir.mkdir(parents=True)

        data_path = self.engine._data_path(self.tenant_id, backup_id, compressed=False)
        data_path.write_bytes(data)

        checksum = compute_checksum(data)
        meta = _make_metadata(
            backup_id=backup_id,
            tenant_id=self.tenant_id,
            checksum=checksum,
            size_bytes=len(data),
        )
        self.engine._write_metadata(meta)

        result = self.engine.verify_backup(self.tenant_id, backup_id)
        self.assertTrue(result.valid)
        self.assertTrue(result.checksum_match)
        self.assertTrue(result.size_match)
        self.assertTrue(result.metadata_valid)

    def test_verify_missing_backup(self):
        result = self.engine.verify_backup(self.tenant_id, "nonexistent")
        self.assertFalse(result.valid)
        self.assertFalse(result.metadata_valid)

    def test_verify_checksum_mismatch(self):
        backup_id = "b0000000-0000-4000-8000-000000000001"
        backup_dir = self.engine._backup_dir(self.tenant_id, backup_id)
        backup_dir.mkdir(parents=True)

        data_path = self.engine._data_path(self.tenant_id, backup_id, compressed=False)
        data_path.write_bytes(b"actual data")

        meta = _make_metadata(
            backup_id=backup_id,
            tenant_id=self.tenant_id,
            checksum="0" * 64,
            size_bytes=11,
        )
        self.engine._write_metadata(meta)

        result = self.engine.verify_backup(self.tenant_id, backup_id)
        self.assertFalse(result.valid)
        self.assertFalse(result.checksum_match)

    def test_verify_size_mismatch(self):
        backup_id = "b0000000-0000-4000-8000-000000000001"
        backup_dir = self.engine._backup_dir(self.tenant_id, backup_id)
        backup_dir.mkdir(parents=True)

        data_path = self.engine._data_path(self.tenant_id, backup_id, compressed=False)
        data_path.write_bytes(b"actual")

        meta = _make_metadata(
            backup_id=backup_id,
            tenant_id=self.tenant_id,
            checksum=compute_checksum(b"actual"),
            size_bytes=999,
        )
        self.engine._write_metadata(meta)

        result = self.engine.verify_backup(self.tenant_id, backup_id)
        self.assertFalse(result.valid)
        self.assertFalse(result.size_match)

    def test_verify_compressed_backup(self):
        data = b"compressed backup data"
        compressed = compress_data(data, CompressionType.GZIP)
        backup_id = "b0000000-0000-4000-8000-000000000001"
        backup_dir = self.engine._backup_dir(self.tenant_id, backup_id)
        backup_dir.mkdir(parents=True)

        data_path = self.engine._data_path(self.tenant_id, backup_id, compressed=True)
        data_path.write_bytes(compressed)

        checksum = compute_checksum(compressed)
        meta = _make_metadata(
            backup_id=backup_id,
            tenant_id=self.tenant_id,
            checksum=checksum,
            size_bytes=len(compressed),
            compression=CompressionType.GZIP,
        )
        self.engine._write_metadata(meta)

        result = self.engine.verify_backup(self.tenant_id, backup_id)
        self.assertTrue(result.valid)


class TestBackupEngineDelete(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = BackupEngine(self.tmp.name)
        self.tenant_id = "t0000000-0000-4000-8000-000000000001"

    def tearDown(self):
        self.tmp.cleanup()

    def test_delete_existing(self):
        backup_id = "b0000000-0000-4000-8000-000000000001"
        backup_dir = self.engine._backup_dir(self.tenant_id, backup_id)
        backup_dir.mkdir(parents=True)
        (backup_dir / "metadata.json").write_text("{}")

        self.assertTrue(self.engine.delete_backup(self.tenant_id, backup_id))
        self.assertFalse(backup_dir.exists())

    def test_delete_nonexistent(self):
        self.assertFalse(self.engine.delete_backup(self.tenant_id, "nonexistent"))


class TestBackupEngineRetention(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = BackupEngine(self.tmp.name)
        self.tenant_id = "t0000000-0000-4000-8000-000000000001"

    def tearDown(self):
        self.tmp.cleanup()

    def test_get_default_retention(self):
        policy = self.engine.get_retention_policy(self.tenant_id)
        self.assertEqual(policy.keep_daily, 7)

    def test_set_and_get_retention(self):
        policy = RetentionPolicy(keep_daily=3, keep_weekly=2, max_age_days=90)
        self.engine.set_retention_policy(self.tenant_id, policy)
        restored = self.engine.get_retention_policy(self.tenant_id)
        self.assertEqual(restored.keep_daily, 3)
        self.assertEqual(restored.max_age_days, 90)

    def test_apply_retention_keeps_minimum(self):
        # Create 3 backups: 2 recent, 1 very old (beyond max_age)
        now = datetime.now(timezone.utc)
        for i in range(2):
            meta = _make_metadata(
                backup_id=f"b0000000-0000-4000-8000-{i:012d}",
                tenant_id=self.tenant_id,
                created_at=now - timedelta(days=30 - i * 10),
            )
            self.engine._write_metadata(meta)
        old = _make_metadata(
            backup_id="b0000000-0000-4000-8000-000000000009",
            tenant_id=self.tenant_id,
            created_at=now - timedelta(days=400),
        )
        self.engine._write_metadata(old)

        policy = RetentionPolicy(
            keep_daily=0,
            keep_weekly=0,
            keep_monthly=0,
            keep_yearly=0,
            min_backups=2,
            max_age_days=365,
        )
        deleted = self.engine.apply_retention(self.tenant_id, policy)
        self.assertEqual(len(deleted), 1)
        self.assertIn(old.backup_id, deleted)
        remaining = self.engine.list_backups(self.tenant_id)
        self.assertEqual(len(remaining), 2)

    def test_apply_retention_respects_max_age(self):
        old = _make_metadata(
            backup_id="b0000000-0000-4000-8000-000000000001",
            tenant_id=self.tenant_id,
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        new = _make_metadata(
            backup_id="b0000000-0000-4000-8000-000000000002",
            tenant_id=self.tenant_id,
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
        )
        self.engine._write_metadata(old)
        self.engine._write_metadata(new)

        policy = RetentionPolicy(
            keep_daily=0,
            keep_weekly=0,
            keep_monthly=0,
            keep_yearly=0,
            min_backups=0,
            max_age_days=30,
        )
        deleted = self.engine.apply_retention(self.tenant_id, policy)
        self.assertIn(old.backup_id, deleted)
        self.assertNotIn(new.backup_id, deleted)

    def test_apply_retention_empty(self):
        deleted = self.engine.apply_retention(self.tenant_id)
        self.assertEqual(deleted, [])


class TestBackupEngineStats(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = BackupEngine(self.tmp.name)
        self.tenant_id = "t0000000-0000-4000-8000-000000000001"

    def tearDown(self):
        self.tmp.cleanup()

    def test_stats_empty(self):
        stats = self.engine.get_backup_stats(self.tenant_id)
        self.assertEqual(stats["total_backups"], 0)
        self.assertEqual(stats["total_size_bytes"], 0)

    def test_stats_with_backups(self):
        meta = _make_metadata(
            tenant_id=self.tenant_id,
            size_bytes=2048,
            row_counts={"tenants": 1, "assets": 5},
        )
        self.engine._write_metadata(meta)

        stats = self.engine.get_backup_stats(self.tenant_id)
        self.assertEqual(stats["total_backups"], 1)
        self.assertEqual(stats["completed_backups"], 1)
        self.assertEqual(stats["total_size_bytes"], 2048)
        self.assertEqual(stats["total_rows_backed_up"], 6)
        self.assertIsNotNone(stats["newest_backup"])


class TestBackupEngineCleanup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = BackupEngine(self.tmp.name)
        self.tenant_id = "t0000000-0000-4000-8000-000000000001"

    def tearDown(self):
        self.tmp.cleanup()

    def test_cleanup_failed(self):
        failed = _make_metadata(
            backup_id="b0000000-0000-4000-8000-000000000001",
            tenant_id=self.tenant_id,
            status=BackupStatus.FAILED,
        )
        completed = _make_metadata(
            backup_id="b0000000-0000-4000-8000-000000000002",
            tenant_id=self.tenant_id,
            status=BackupStatus.COMPLETED,
        )
        self.engine._write_metadata(failed)
        self.engine._write_metadata(completed)

        count = self.engine.cleanup_failed(self.tenant_id)
        self.assertEqual(count, 1)
        remaining = self.engine.list_backups(self.tenant_id)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].status, BackupStatus.COMPLETED)


class TestBackupEngineExportImport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = BackupEngine(self.tmp.name)
        self.tenant_id = "t0000000-0000-4000-8000-000000000001"

    def tearDown(self):
        self.tmp.cleanup()

    def test_export_import_roundtrip(self):
        backup_id = "b0000000-0000-4000-8000-000000000001"
        backup_dir = self.engine._backup_dir(self.tenant_id, backup_id)
        backup_dir.mkdir(parents=True)

        data = b"export test data"
        data_path = self.engine._data_path(self.tenant_id, backup_id, compressed=False)
        data_path.write_bytes(data)

        meta = _make_metadata(
            backup_id=backup_id,
            tenant_id=self.tenant_id,
            checksum=compute_checksum(data),
            size_bytes=len(data),
        )
        self.engine._write_metadata(meta)

        # Export
        dest = Path(self.tmp.name) / "export.tar.gz"
        result_path = self.engine.export_backup(self.tenant_id, backup_id, dest)
        self.assertTrue(result_path.exists())

        # Delete original
        self.engine.delete_backup(self.tenant_id, backup_id)

        # Import
        imported = self.engine.import_backup(self.tenant_id, result_path)
        self.assertEqual(imported.backup_id, backup_id)
        self.assertEqual(imported.tenant_id, self.tenant_id)

        # Verify data file exists
        imported_data = self.engine._data_path(self.tenant_id, backup_id, compressed=False)
        self.assertTrue(imported_data.exists())

    def test_import_nonexistent_source(self):
        with self.assertRaises(BackupError):
            self.engine.import_backup(self.tenant_id, "/nonexistent/path.tar.gz")

    def test_import_duplicate(self):
        backup_id = "b0000000-0000-4000-8000-000000000001"
        backup_dir = self.engine._backup_dir(self.tenant_id, backup_id)
        backup_dir.mkdir(parents=True)
        meta = _make_metadata(backup_id=backup_id, tenant_id=self.tenant_id)
        self.engine._write_metadata(meta)

        # Export
        dest = Path(self.tmp.name) / "export.tar.gz"
        self.engine.export_backup(self.tenant_id, backup_id, dest)

        # Try to import again (should fail - already exists)
        with self.assertRaises(BackupError):
            self.engine.import_backup(self.tenant_id, dest)


class TestBackupEnginePITR(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = BackupEngine(self.tmp.name)
        self.tenant_id = "t0000000-0000-4000-8000-000000000001"

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_pitr_points_empty(self):
        points = self.engine.list_pitr_points(self.tenant_id)
        self.assertEqual(points, [])

    def test_list_pitr_points_with_backups(self):
        for i in range(3):
            meta = _make_metadata(
                backup_id=f"b0000000-0000-4000-8000-{i:012d}",
                tenant_id=self.tenant_id,
                created_at=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
                point_in_time=datetime(2026, 1, i + 1, 12, 0, tzinfo=timezone.utc),
            )
            self.engine._write_metadata(meta)

        points = self.engine.list_pitr_points(self.tenant_id)
        self.assertEqual(len(points), 3)
        # Newest first
        self.assertGreater(points[0].target_time, points[1].target_time)

    def test_list_pitr_points_time_range(self):
        old = _make_metadata(
            backup_id="b0000000-0000-4000-8000-000000000001",
            tenant_id=self.tenant_id,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        new = _make_metadata(
            backup_id="b0000000-0000-4000-8000-000000000002",
            tenant_id=self.tenant_id,
            created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        self.engine._write_metadata(old)
        self.engine._write_metadata(new)

        points = self.engine.list_pitr_points(
            self.tenant_id,
            start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].backup_id, new.backup_id)

    def test_find_pitr_backup(self):
        target = datetime(2026, 3, 15, tzinfo=timezone.utc)
        before = _make_metadata(
            backup_id="b0000000-0000-4000-8000-000000000001",
            tenant_id=self.tenant_id,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        after = _make_metadata(
            backup_id="b0000000-0000-4000-8000-000000000002",
            tenant_id=self.tenant_id,
            created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        self.engine._write_metadata(before)
        self.engine._write_metadata(after)

        result = self.engine.find_pitr_backup(self.tenant_id, target)
        self.assertIsNotNone(result)
        assert result is not None  # for type checker
        self.assertEqual(result.backup_id, before.backup_id)

    def test_find_pitr_backup_none_before(self):
        meta = _make_metadata(
            tenant_id=self.tenant_id,
            created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        self.engine._write_metadata(meta)

        result = self.engine.find_pitr_backup(
            self.tenant_id,
            datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        self.assertIsNone(result)


class TestBackupScheduler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = BackupEngine(self.tmp.name)
        self.scheduler = BackupScheduler(self.engine, interval_hours=24.0)
        self.tenant_id = "t0000000-0000-4000-8000-000000000001"

    def tearDown(self):
        self.tmp.cleanup()

    def test_is_due_no_backups(self):
        self.assertTrue(self.scheduler.is_due(self.tenant_id))

    def test_is_due_recent_backup(self):
        meta = _make_metadata(
            tenant_id=self.tenant_id,
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        self.engine._write_metadata(meta)
        self.assertFalse(self.scheduler.is_due(self.tenant_id))

    def test_is_due_old_backup(self):
        meta = _make_metadata(
            tenant_id=self.tenant_id,
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        )
        self.engine._write_metadata(meta)
        self.assertTrue(self.scheduler.is_due(self.tenant_id))

    def test_record_backup(self):
        self.scheduler.record_backup(self.tenant_id)
        self.assertFalse(self.scheduler.is_due(self.tenant_id))

    def test_time_until_due(self):
        self.assertEqual(self.scheduler.time_until_due(self.tenant_id), 0.0)

    def test_time_until_due_with_recent(self):
        meta = _make_metadata(
            tenant_id=self.tenant_id,
            created_at=datetime.now(timezone.utc) - timedelta(hours=12),
        )
        self.engine._write_metadata(meta)
        remaining = self.scheduler.time_until_due(self.tenant_id)
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 12.0)

    def test_invalid_interval(self):
        with self.assertRaises(ValueError):
            BackupScheduler(self.engine, interval_hours=0)

    def test_custom_interval(self):
        scheduler = BackupScheduler(self.engine, interval_hours=0.5)
        meta = _make_metadata(
            tenant_id=self.tenant_id,
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        self.engine._write_metadata(meta)
        self.assertTrue(scheduler.is_due(self.tenant_id))


class TestConvenienceFunctions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tenant_id = "t0000000-0000-4000-8000-000000000001"

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_backup_function(self):
        with patch.object(BackupEngine, "_run_pg_dump"), \
             patch.object(BackupEngine, "_get_row_counts", return_value={"tenants": 1}), \
             patch.object(BackupEngine, "_find_latest_full_backup", return_value=None):
            result = create_backup(self.tmp.name, self.tenant_id)
            # Will fail because no real pg_dump, but should return a result
            self.assertIsInstance(result, BackupResult)
            self.assertFalse(result.success)

    def test_list_backups_function(self):
        result = list_backups(self.tmp.name, self.tenant_id)
        self.assertEqual(result, [])

    def test_verify_backup_function(self):
        result = verify_backup(self.tmp.name, self.tenant_id, "nonexistent")
        self.assertFalse(result.valid)

    def test_restore_backup_function(self):
        result = restore_backup(self.tmp.name, self.tenant_id, "nonexistent")
        self.assertIsInstance(result, RestoreResult)
        self.assertFalse(result.success)


class TestBackupResult(unittest.TestCase):
    def test_to_dict(self):
        result = BackupResult(
            success=True,
            backup_id="b0000000-0000-4000-8000-000000000001",
            message="ok",
            duration_seconds=1.5,
        )
        d = result.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["backup_id"], "b0000000-0000-4000-8000-000000000001")
        self.assertEqual(d["duration_seconds"], 1.5)

    def test_to_dict_with_metadata(self):
        meta = _make_metadata()
        result = BackupResult(
            success=True,
            backup_id=meta.backup_id,
            metadata=meta,
        )
        d = result.to_dict()
        self.assertIsNotNone(d["metadata"])
        self.assertEqual(d["metadata"]["backup_id"], meta.backup_id)


class TestRestoreResult(unittest.TestCase):
    def test_to_dict(self):
        result = RestoreResult(
            success=True,
            restore_id="r0000000-0000-4000-8000-000000000001",
            message="restored",
            duration_seconds=2.0,
        )
        d = result.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["restore_id"], "r0000000-0000-4000-8000-000000000001")


class TestVerificationResult(unittest.TestCase):
    def test_to_dict(self):
        result = VerificationResult(
            backup_id="b0000000-0000-4000-8000-000000000001",
            valid=True,
            checksum_match=True,
            size_match=True,
            metadata_valid=True,
        )
        d = result.to_dict()
        self.assertTrue(d["valid"])
        self.assertEqual(d["errors"], [])


class TestExceptions(unittest.TestCase):
    def test_backup_error(self):
        err = BackupError("test error", "test_code")
        self.assertEqual(err.code, "test_code")
        self.assertEqual(str(err), "test error")

    def test_backup_not_found(self):
        err = BackupNotFoundError("abc")
        self.assertEqual(err.code, "backup_not_found")

    def test_backup_corrupted(self):
        err = BackupCorruptedError("abc", "checksum failed")
        self.assertEqual(err.code, "backup_corrupted")
        self.assertIn("checksum failed", str(err))

    def test_restore_error(self):
        err = RestoreError("restore failed", "restore_failed")
        self.assertEqual(err.code, "restore_failed")


class TestDefaultTables(unittest.TestCase):
    def test_tables_not_empty(self):
        from dcc.operations.backup import DEFAULT_TABLES
        self.assertGreater(len(DEFAULT_TABLES), 0)
        self.assertIn("tenants", DEFAULT_TABLES)
        self.assertIn("assets", DEFAULT_TABLES)
        self.assertIn("telemetry_readings", DEFAULT_TABLES)

    def test_tables_ordered_by_dependency(self):
        from dcc.operations.backup import DEFAULT_TABLES
        # Parents should come before children
        self.assertLess(DEFAULT_TABLES.index("tenants"), DEFAULT_TABLES.index("assets"))
        self.assertLess(DEFAULT_TABLES.index("facilities"), DEFAULT_TABLES.index("spaces"))
        self.assertLess(DEFAULT_TABLES.index("spaces"), DEFAULT_TABLES.index("assets"))


if __name__ == "__main__":
    unittest.main()
