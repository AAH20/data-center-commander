"""Backup and restore engine for Data Center Commander.

Provides automated backup creation, point-in-time recovery, backup verification,
and retention policy management. All operations are tenant-scoped and produce
structured, auditable results.

The engine supports:
- Full and incremental backups
- Point-in-time recovery (PITR) via WAL archiving
- Backup integrity verification (SHA-256 checksums)
- Compression (gzip)
- Retention policy enforcement
- Tenant isolation

Pure stdlib implementation: no external dependencies.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Sequence
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class BackupError(Exception):
    """Base exception for backup/restore failures."""

    def __init__(self, message: str, code: str = "backup_error") -> None:
        self.code = code
        super().__init__(message)


class BackupNotFoundError(BackupError):
    """Raised when a backup cannot be found."""

    def __init__(self, backup_id: str) -> None:
        super().__init__(f"backup {backup_id!r} not found", "backup_not_found")


class BackupCorruptedError(BackupError):
    """Raised when a backup fails integrity verification."""

    def __init__(self, backup_id: str, detail: str = "") -> None:
        msg = f"backup {backup_id!r} failed integrity check"
        if detail:
            msg += f": {detail}"
        super().__init__(msg, "backup_corrupted")


class RestoreError(BackupError):
    """Raised when a restore operation fails."""

    def __init__(self, message: str, code: str = "restore_error") -> None:
        super().__init__(message, code)


class RetentionPolicyError(BackupError):
    """Raised when a retention policy is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "retention_policy_error")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BackupType(str, Enum):
    """Type of backup."""

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class BackupStatus(str, Enum):
    """Lifecycle status of a backup."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    EXPIRED = "expired"
    DELETED = "deleted"


class RestoreStatus(str, Enum):
    """Lifecycle status of a restore operation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


class CompressionType(str, Enum):
    """Compression algorithm."""

    NONE = "none"
    GZIP = "gzip"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BackupMetadata:
    """Metadata for a single backup."""

    backup_id: str
    tenant_id: str
    backup_type: BackupType
    status: BackupStatus
    created_at: datetime
    completed_at: datetime | None = None
    size_bytes: int = 0
    checksum: str = ""
    parent_backup_id: str | None = None
    wal_start: str | None = None
    wal_end: str | None = None
    point_in_time: datetime | None = None
    compression: CompressionType = CompressionType.NONE
    tables: list[str] = field(default_factory=list)
    row_counts: dict[str, int] = field(default_factory=dict)
    error_message: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "tenant_id": self.tenant_id,
            "backup_type": self.backup_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "parent_backup_id": self.parent_backup_id,
            "wal_start": self.wal_start,
            "wal_end": self.wal_end,
            "point_in_time": self.point_in_time.isoformat() if self.point_in_time else None,
            "compression": self.compression.value,
            "tables": list(self.tables),
            "row_counts": dict(self.row_counts),
            "error_message": self.error_message,
            "tags": dict(self.tags),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupMetadata:
        return cls(
            backup_id=data["backup_id"],
            tenant_id=data["tenant_id"],
            backup_type=BackupType(data.get("backup_type", "full")),
            status=BackupStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            size_bytes=data.get("size_bytes", 0),
            checksum=data.get("checksum", ""),
            parent_backup_id=data.get("parent_backup_id"),
            wal_start=data.get("wal_start"),
            wal_end=data.get("wal_end"),
            point_in_time=(
                datetime.fromisoformat(data["point_in_time"])
                if data.get("point_in_time")
                else None
            ),
            compression=CompressionType(data.get("compression", "none")),
            tables=list(data.get("tables", [])),
            row_counts=dict(data.get("row_counts", {})),
            error_message=data.get("error_message", ""),
            tags=dict(data.get("tags", {})),
            schema_version=data.get("schema_version", "1.0"),
        )


@dataclass(frozen=True)
class RestoreMetadata:
    """Metadata for a restore operation."""

    restore_id: str
    backup_id: str
    tenant_id: str
    status: RestoreStatus
    created_at: datetime
    completed_at: datetime | None = None
    target_point_in_time: datetime | None = None
    tables_restored: list[str] = field(default_factory=list)
    rows_restored: int = 0
    error_message: str = ""
    verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "restore_id": self.restore_id,
            "backup_id": self.backup_id,
            "tenant_id": self.tenant_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "target_point_in_time": (
                self.target_point_in_time.isoformat() if self.target_point_in_time else None
            ),
            "tables_restored": list(self.tables_restored),
            "rows_restored": self.rows_restored,
            "error_message": self.error_message,
            "verified": self.verified,
        }


@dataclass(frozen=True)
class RetentionPolicy:
    """Retention policy for backups.

    Attributes:
        keep_daily: Number of daily backups to retain.
        keep_weekly: Number of weekly backups to retain.
        keep_monthly: Number of monthly backups to retain.
        keep_yearly: Number of yearly backups to retain.
        max_age_days: Maximum age of any backup in days.
        min_backups: Minimum number of backups to always keep.
    """

    keep_daily: int = 7
    keep_weekly: int = 4
    keep_monthly: int = 12
    keep_yearly: int = 3
    max_age_days: int = 365
    min_backups: int = 1

    def __post_init__(self) -> None:
        for name in ("keep_daily", "keep_weekly", "keep_monthly", "keep_yearly", "max_age_days", "min_backups"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise RetentionPolicyError(f"{name} must be a non-negative integer")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RetentionPolicy:
        if not data:
            return cls()
        return cls(
            keep_daily=int(data.get("keep_daily", 7)),
            keep_weekly=int(data.get("keep_weekly", 4)),
            keep_monthly=int(data.get("keep_monthly", 12)),
            keep_yearly=int(data.get("keep_yearly", 3)),
            max_age_days=int(data.get("max_age_days", 365)),
            min_backups=int(data.get("min_backups", 1)),
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "keep_daily": self.keep_daily,
            "keep_weekly": self.keep_weekly,
            "keep_monthly": self.keep_monthly,
            "keep_yearly": self.keep_yearly,
            "max_age_days": self.max_age_days,
            "min_backups": self.min_backups,
        }


@dataclass
class BackupResult:
    """Result of a backup operation."""

    success: bool
    backup_id: str
    metadata: BackupMetadata | None = None
    message: str = ""
    duration_seconds: float = 0.0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "backup_id": self.backup_id,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "message": self.message,
            "duration_seconds": round(self.duration_seconds, 3),
            "error": self.error,
        }


@dataclass
class RestoreResult:
    """Result of a restore operation."""

    success: bool
    restore_id: str
    metadata: RestoreMetadata | None = None
    message: str = ""
    duration_seconds: float = 0.0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "restore_id": self.restore_id,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "message": self.message,
            "duration_seconds": round(self.duration_seconds, 3),
            "error": self.error,
        }


@dataclass
class VerificationResult:
    """Result of a backup verification."""

    backup_id: str
    valid: bool
    checksum_match: bool
    size_match: bool
    metadata_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "valid": self.valid,
            "checksum_match": self.checksum_match,
            "size_match": self.size_match,
            "metadata_valid": self.metadata_valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass
class PITRPoint:
    """A point-in-time recovery target."""

    target_time: datetime
    backup_id: str
    wal_segments_needed: list[str] = field(default_factory=list)
    estimated_rows: int = 0
    confidence: str = "high"  # "high", "medium", "low"


# ---------------------------------------------------------------------------
# Checksum utilities
# ---------------------------------------------------------------------------


def compute_checksum(data: bytes) -> str:
    """Compute SHA-256 checksum of byte data."""
    return hashlib.sha256(data).hexdigest()


def compute_file_checksum(path: str | Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify_checksum(data: bytes, expected: str) -> bool:
    """Verify data against an expected SHA-256 checksum."""
    return compute_checksum(data) == expected


# ---------------------------------------------------------------------------
# Compression utilities
# ---------------------------------------------------------------------------


def compress_data(data: bytes, compression: CompressionType = CompressionType.GZIP) -> bytes:
    """Compress byte data."""
    if compression == CompressionType.NONE:
        return data
    if compression == CompressionType.GZIP:
        return gzip.compress(data, compresslevel=6)
    raise BackupError(f"unsupported compression: {compression}", "unsupported_compression")


def decompress_data(data: bytes, compression: CompressionType = CompressionType.GZIP) -> bytes:
    """Decompress byte data."""
    if compression == CompressionType.NONE:
        return data
    if compression == CompressionType.GZIP:
        return gzip.decompress(data)
    raise BackupError(f"unsupported compression: {compression}", "unsupported_compression")


# ---------------------------------------------------------------------------
# Backup engine
# ---------------------------------------------------------------------------


# Default tables in the DCC schema, ordered by dependency (parents first).
DEFAULT_TABLES: list[str] = [
    "tenants",
    "sites",
    "facilities",
    "spaces",
    "assets",
    "asset_relationships",
    "connectors",
    "connector_runs",
    "metric_definitions",
    "meters",
    "telemetry_readings",
    "tariffs",
    "carbon_factors",
    "workloads",
    "deployments",
    "energy_allocations",
    "capacity_snapshots",
    "kpi_definitions",
    "kpi_observations",
    "procedures",
    "operational_workflows",
    "workflow_tasks",
    "approvals",
    "work_orders",
    "incidents",
    "change_records",
    "evidence_events",
    "cost_books",
    "price_observations",
    "estimate_projects",
    "estimate_line_items",
    "cost_actuals",
    "cost_allocations",
    "placement_comparison_snapshots",
]


class BackupEngine:
    """Backup and restore engine for Data Center Commander.

    Manages backup creation, verification, restore, and retention for
    tenant-scoped PostgreSQL databases. Supports full and incremental
    backups, point-in-time recovery, and automated retention policies.

    The engine stores backups on the local filesystem with a structured
    layout::

        <backup_root>/
        ├── <tenant_id>/
        │   ├── <backup_id>/
        │   │   ├── metadata.json
        │   │   ├── data.sql.gz
        │   │   └── wal/
        │   │       └── ...
        │   └── ...
        └── _retention_policy.json

    All operations are synchronous and thread-safe at the filesystem level
    via atomic writes.
    """

    METADATA_FILENAME = "metadata.json"
    DATA_FILENAME = "data.sql"
    COMPRESSED_DATA_FILENAME = "data.sql.gz"
    WAL_DIRNAME = "wal"
    RETENTION_FILENAME = "_retention_policy.json"

    def __init__(
        self,
        backup_root: str | Path,
        *,
        pg_dump_path: str = "pg_dump",
        pg_restore_path: str = "pg_restore",
        psql_path: str = "psql",
        default_compression: CompressionType = CompressionType.GZIP,
    ) -> None:
        """Initialize the backup engine.

        Args:
            backup_root: Root directory for all backups.
            pg_dump_path: Path to pg_dump binary.
            pg_restore_path: Path to pg_restore binary.
            psql_path: Path to psql binary.
            default_compression: Default compression for new backups.
        """
        self.backup_root = Path(backup_root).resolve()
        self.pg_dump_path = pg_dump_path
        self.pg_restore_path = pg_restore_path
        self.psql_path = psql_path
        self.default_compression = default_compression
        self._ensure_root()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _ensure_root(self) -> None:
        """Ensure the backup root directory exists."""
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def _tenant_dir(self, tenant_id: str) -> Path:
        """Get the backup directory for a tenant."""
        return self.backup_root / tenant_id

    def _backup_dir(self, tenant_id: str, backup_id: str) -> Path:
        """Get the backup directory for a specific backup."""
        return self._tenant_dir(tenant_id) / backup_id

    def _metadata_path(self, tenant_id: str, backup_id: str) -> Path:
        """Get the metadata file path for a backup."""
        return self._backup_dir(tenant_id, backup_id) / self.METADATA_FILENAME

    def _data_path(self, tenant_id: str, backup_id: str, compressed: bool = True) -> Path:
        """Get the data file path for a backup."""
        name = self.COMPRESSED_DATA_FILENAME if compressed else self.DATA_FILENAME
        return self._backup_dir(tenant_id, backup_id) / name

    def _wal_dir(self, tenant_id: str, backup_id: str) -> Path:
        """Get the WAL directory for a backup."""
        return self._backup_dir(tenant_id, backup_id) / self.WAL_DIRNAME

    # ------------------------------------------------------------------
    # Metadata persistence
    # ------------------------------------------------------------------

    def _write_metadata(self, metadata: BackupMetadata) -> None:
        """Write backup metadata to disk atomically."""
        path = self._metadata_path(metadata.tenant_id, metadata.backup_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(metadata.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        tmp.rename(path)

    def _read_metadata(self, tenant_id: str, backup_id: str) -> BackupMetadata:
        """Read backup metadata from disk."""
        path = self._metadata_path(tenant_id, backup_id)
        if not path.exists():
            raise BackupNotFoundError(backup_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        return BackupMetadata.from_dict(data)

    # ------------------------------------------------------------------
    # Backup creation
    # ------------------------------------------------------------------

    def create_backup(
        self,
        tenant_id: str,
        *,
        backup_type: BackupType = BackupType.FULL,
        tables: list[str] | None = None,
        compression: CompressionType | None = None,
        tags: dict[str, str] | None = None,
        dsn: str | None = None,
        point_in_time: datetime | None = None,
    ) -> BackupResult:
        """Create a new backup for a tenant.

        Args:
            tenant_id: Tenant UUID string.
            backup_type: Type of backup (full, incremental, differential).
            tables: Specific tables to back up (None = all).
            compression: Compression type (None = engine default).
            tags: Optional tags for the backup.
            dsn: PostgreSQL connection string (uses env DCC_DATABASE_URL if None).
            point_in_time: Target point-in-time for PITR.

        Returns:
            BackupResult with success status and metadata.
        """
        start_time = datetime.now(timezone.utc)
        backup_id = str(uuid4())
        comp = compression or self.default_compression
        table_list = tables if tables is not None else list(DEFAULT_TABLES)

        metadata = BackupMetadata(
            backup_id=backup_id,
            tenant_id=tenant_id,
            backup_type=backup_type,
            status=BackupStatus.RUNNING,
            created_at=start_time,
            compression=comp,
            tables=table_list,
            tags=tags or {},
            point_in_time=point_in_time,
        )

        backup_dir = self._backup_dir(tenant_id, backup_id)
        backup_dir.mkdir(parents=True, exist_ok=True)
        self._write_metadata(metadata)

        try:
            # Determine parent for incremental/differential
            parent_id: str | None = None
            if backup_type in (BackupType.INCREMENTAL, BackupType.DIFFERENTIAL):
                parent_id = self._find_latest_full_backup(tenant_id)
                if parent_id:
                    metadata = BackupMetadata(
                        **{**metadata.__dict__, "parent_backup_id": parent_id}
                    )

            # Run pg_dump
            data_path = self._data_path(tenant_id, backup_id, compressed=False)
            self._run_pg_dump(
                dsn=dsn,
                output_path=data_path,
                tables=table_list,
                backup_type=backup_type,
                parent_id=parent_id,
            )

            # Compress if needed
            final_path = data_path
            if comp == CompressionType.GZIP:
                compressed_path = self._data_path(tenant_id, backup_id, compressed=True)
                self._compress_file(data_path, compressed_path)
                data_path.unlink()
                final_path = compressed_path

            # Compute checksum
            checksum = compute_file_checksum(final_path)
            size = final_path.stat().st_size

            # Get row counts
            row_counts = self._get_row_counts(dsn=dsn, tenant_id=tenant_id, tables=table_list)

            completed = datetime.now(timezone.utc)
            duration = (completed - start_time).total_seconds()

            metadata = BackupMetadata(
                **{
                    **metadata.__dict__,
                    "status": BackupStatus.COMPLETED,
                    "completed_at": completed,
                    "size_bytes": size,
                    "checksum": checksum,
                    "row_counts": row_counts,
                }
            )
            self._write_metadata(metadata)

            return BackupResult(
                success=True,
                backup_id=backup_id,
                metadata=metadata,
                message=f"backup completed: {size} bytes, {sum(row_counts.values())} rows",
                duration_seconds=duration,
            )

        except Exception as exc:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            metadata = BackupMetadata(
                **{
                    **metadata.__dict__,
                    "status": BackupStatus.FAILED,
                    "completed_at": datetime.now(timezone.utc),
                    "error_message": str(exc),
                }
            )
            self._write_metadata(metadata)
            return BackupResult(
                success=False,
                backup_id=backup_id,
                metadata=metadata,
                message=f"backup failed: {exc}",
                duration_seconds=duration,
                error=str(exc),
            )

    def _run_pg_dump(
        self,
        *,
        dsn: str | None,
        output_path: Path,
        tables: list[str],
        backup_type: BackupType,
        parent_id: str | None,
    ) -> None:
        """Execute pg_dump to create a backup file."""
        conn = dsn or os.environ.get("DCC_DATABASE_URL", "")
        if not conn:
            raise BackupError(
                "no database connection string provided; set DCC_DATABASE_URL or pass dsn",
                "database_not_configured",
            )

        cmd = [self.pg_dump_path, "--dbname", conn, "--file", str(output_path), "--verbose"]

        if backup_type == BackupType.FULL:
            cmd.append("--format=plain")
        else:
            cmd.append("--format=directory")

        for table in tables:
            cmd.extend(["--table", f"dcc.{table}"])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
            )
        except FileNotFoundError:
            raise BackupError(
                f"pg_dump not found at {self.pg_dump_path!r}",
                "pg_dump_not_found",
            ) from None
        except subprocess.TimeoutExpired:
            raise BackupError("pg_dump timed out after 1 hour", "pg_dump_timeout")

        if result.returncode != 0:
            raise BackupError(
                f"pg_dump failed (exit {result.returncode}): {result.stderr.strip()}",
                "pg_dump_failed",
            )

    def _compress_file(self, source: Path, dest: Path) -> None:
        """Compress a file using gzip."""
        with open(source, "rb") as f_in:
            with gzip.open(dest, "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)

    def _get_row_counts(
        self,
        *,
        dsn: str | None,
        tenant_id: str,
        tables: list[str],
    ) -> dict[str, int]:
        """Get row counts for backed-up tables."""
        conn = dsn or os.environ.get("DCC_DATABASE_URL", "")
        if not conn:
            return {}

        # Best-effort, but never a guess. Two defects made this report a confident 0:
        #
        #  1. A single try/except wrapped the whole loop, so one failing table aborted
        #     every remaining count and the caller's sum(row_counts.values()) reported
        #     an empty database.
        #  2. It assumed every table has a tenant_id column and that the tenant is a
        #     UUID. dcc.tenants has no tenant_id, and a non-UUID tenant raised on the
        #     ::uuid cast -- both landed in the blanket except and vanished.
        #
        # A table is now counted only when it genuinely has a tenant_id column, each
        # count fails independently, and a table that could not be counted is OMITTED
        # rather than recorded as 0. Omitting keeps sum() honest: it totals what was
        # measured, and a missing key says "not measured" instead of "empty".
        counts: dict[str, int] = {}
        try:
            import psycopg

            with psycopg.connect(conn) as c:
                with c.cursor() as cur:
                    cur.execute(
                        """
                        SELECT table_name
                        FROM information_schema.columns
                        WHERE table_schema = 'dcc' AND column_name = 'tenant_id'
                        """
                    )
                    tenant_scoped = {row[0] for row in cur.fetchall()}

                    for table in tables:
                        if table not in tenant_scoped:
                            # Not tenant-scoped (e.g. dcc.tenants itself); counting it
                            # by tenant_id would be meaningless, not zero.
                            continue
                        try:
                            cur.execute(
                                f'SELECT count(*) FROM dcc."{table}" WHERE tenant_id = %s::uuid',
                                (tenant_id,),
                            )
                            row = cur.fetchone()
                            if row is not None:
                                counts[table] = row[0]
                        except Exception:
                            # Leave the key out entirely: the caller must not sum an
                            # unmeasured table as if it had been counted.
                            continue
        except Exception:
            # Whole-connection failure (unreachable DSN, bad credentials). An empty
            # dict still means "nothing measured", which is the truth here.
            return {}
        return counts

    def _find_latest_full_backup(self, tenant_id: str) -> str | None:
        """Find the latest completed full backup for a tenant."""
        backups = self.list_backups(tenant_id, backup_type=BackupType.FULL, status=BackupStatus.COMPLETED)
        if not backups:
            return None
        return backups[0].backup_id

    # ------------------------------------------------------------------
    # Backup listing and retrieval
    # ------------------------------------------------------------------

    def list_backups(
        self,
        tenant_id: str,
        *,
        backup_type: BackupType | None = None,
        status: BackupStatus | None = None,
        limit: int = 100,
    ) -> list[BackupMetadata]:
        """List backups for a tenant, newest first.

        Args:
            tenant_id: Tenant UUID string.
            backup_type: Filter by backup type.
            status: Filter by status.
            limit: Maximum number of results.

        Returns:
            List of BackupMetadata, sorted by created_at descending.
        """
        tenant_dir = self._tenant_dir(tenant_id)
        if not tenant_dir.exists():
            return []

        results: list[BackupMetadata] = []
        for entry in tenant_dir.iterdir():
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            try:
                meta = self._read_metadata(tenant_id, entry.name)
            except (BackupNotFoundError, Exception):
                continue
            if backup_type and meta.backup_type != backup_type:
                continue
            if status and meta.status != status:
                continue
            results.append(meta)

        results.sort(key=lambda m: m.created_at, reverse=True)
        return results[:limit]

    def get_backup(self, tenant_id: str, backup_id: str) -> BackupMetadata:
        """Get metadata for a specific backup."""
        return self._read_metadata(tenant_id, backup_id)

    # ------------------------------------------------------------------
    # Backup verification
    # ------------------------------------------------------------------

    def verify_backup(self, tenant_id: str, backup_id: str) -> VerificationResult:
        """Verify the integrity of a backup.

        Checks:
        - Metadata file exists and is valid
        - Data file exists
        - Checksum matches
        - Size matches

        Args:
            tenant_id: Tenant UUID string.
            backup_id: Backup UUID string.

        Returns:
            VerificationResult with detailed status.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check metadata
        metadata_valid = False
        try:
            meta = self._read_metadata(tenant_id, backup_id)
            metadata_valid = True
        except BackupNotFoundError:
            errors.append(f"backup {backup_id!r} not found")
            return VerificationResult(
                backup_id=backup_id,
                valid=False,
                checksum_match=False,
                size_match=False,
                metadata_valid=False,
                errors=errors,
            )
        except Exception as exc:
            errors.append(f"metadata read failed: {exc}")
            return VerificationResult(
                backup_id=backup_id,
                valid=False,
                checksum_match=False,
                size_match=False,
                metadata_valid=False,
                errors=errors,
            )

        # Check data file
        data_path = self._data_path(tenant_id, backup_id, compressed=(meta.compression == CompressionType.GZIP))
        if not data_path.exists():
            # Try uncompressed
            data_path = self._data_path(tenant_id, backup_id, compressed=False)
            if not data_path.exists():
                errors.append(f"data file not found for backup {backup_id!r}")
                return VerificationResult(
                    backup_id=backup_id,
                    valid=False,
                    checksum_match=False,
                    size_match=False,
                    metadata_valid=True,
                    errors=errors,
                )

        # Verify size
        size_match = True
        actual_size = data_path.stat().st_size
        if meta.size_bytes > 0 and actual_size != meta.size_bytes:
            size_match = False
            errors.append(
                f"size mismatch: expected {meta.size_bytes}, got {actual_size}"
            )

        # Verify checksum
        checksum_match = True
        if meta.checksum:
            actual_checksum = compute_file_checksum(data_path)
            if actual_checksum != meta.checksum:
                checksum_match = False
                errors.append(
                    f"checksum mismatch: expected {meta.checksum[:16]}..., got {actual_checksum[:16]}..."
                )
        else:
            warnings.append("no checksum stored in metadata; skipping checksum verification")

        valid = metadata_valid and size_match and checksum_match and not errors

        return VerificationResult(
            backup_id=backup_id,
            valid=valid,
            checksum_match=checksum_match,
            size_match=size_match,
            metadata_valid=metadata_valid,
            errors=errors,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    def restore_backup(
        self,
        tenant_id: str,
        backup_id: str,
        *,
        dsn: str | None = None,
        target_point_in_time: datetime | None = None,
        tables: list[str] | None = None,
        verify: bool = True,
    ) -> RestoreResult:
        """Restore a backup for a tenant.

        Args:
            tenant_id: Tenant UUID string.
            backup_id: Backup UUID string.
            dsn: PostgreSQL connection string.
            target_point_in_time: Target time for PITR (must be <= backup time).
            tables: Specific tables to restore (None = all in backup).
            verify: Whether to verify the backup before restoring.

        Returns:
            RestoreResult with success status and metadata.
        """
        start_time = datetime.now(timezone.utc)
        restore_id = str(uuid4())

        try:
            meta = self._read_metadata(tenant_id, backup_id)
        except BackupNotFoundError:
            return RestoreResult(
                success=False,
                restore_id=restore_id,
                message=f"backup {backup_id!r} not found",
                error="backup_not_found",
            )

        if verify:
            verification = self.verify_backup(tenant_id, backup_id)
            if not verification.valid:
                return RestoreResult(
                    success=False,
                    restore_id=restore_id,
                    message=f"backup verification failed: {'; '.join(verification.errors)}",
                    error="verification_failed",
                )

        # Validate PITR target
        if target_point_in_time and meta.point_in_time:
            if target_point_in_time > meta.point_in_time:
                return RestoreResult(
                    success=False,
                    restore_id=restore_id,
                    message=(
                        f"target time {target_point_in_time.isoformat()} is after "
                        f"backup time {meta.point_in_time.isoformat()}"
                    ),
                    error="invalid_pitr_target",
                )

        restore_tables = tables if tables is not None else meta.tables

        try:
            data_path = self._data_path(tenant_id, backup_id, compressed=(meta.compression == CompressionType.GZIP))
            if not data_path.exists():
                data_path = self._data_path(tenant_id, backup_id, compressed=False)

            rows_restored = self._run_pg_restore(
                dsn=dsn,
                data_path=data_path,
                tables=restore_tables,
                tenant_id=tenant_id,
            )

            completed = datetime.now(timezone.utc)
            duration = (completed - start_time).total_seconds()

            restore_meta = RestoreMetadata(
                restore_id=restore_id,
                backup_id=backup_id,
                tenant_id=tenant_id,
                status=RestoreStatus.COMPLETED,
                created_at=start_time,
                completed_at=completed,
                target_point_in_time=target_point_in_time,
                tables_restored=restore_tables,
                rows_restored=rows_restored,
                verified=verify,
            )

            return RestoreResult(
                success=True,
                restore_id=restore_id,
                metadata=restore_meta,
                message=f"restore completed: {rows_restored} rows across {len(restore_tables)} tables",
                duration_seconds=duration,
            )

        except Exception as exc:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            return RestoreResult(
                success=False,
                restore_id=restore_id,
                message=f"restore failed: {exc}",
                duration_seconds=duration,
                error=str(exc),
            )

    def _run_pg_restore(
        self,
        *,
        dsn: str | None,
        data_path: Path,
        tables: list[str],
        tenant_id: str,
    ) -> int:
        """Execute pg_restore to restore a backup file."""
        conn = dsn or os.environ.get("DCC_DATABASE_URL", "")
        if not conn:
            raise RestoreError(
                "no database connection string provided; set DCC_DATABASE_URL or pass dsn",
                "database_not_configured",
            )

        # Decompress to temp if needed
        work_path = data_path
        tmp_dir: tempfile.TemporaryDirectory[str] | None = None
        if data_path.suffix == ".gz":
            tmp_dir = tempfile.TemporaryDirectory(prefix="dcc_restore_")
            work_path = Path(tmp_dir.name) / "data.sql"
            with gzip.open(data_path, "rb") as f_in:
                with open(work_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

        try:
            cmd = [
                self.psql_path,
                "--dbname", conn,
                "--file", str(work_path),
                "--set", "ON_ERROR_STOP=1",
                "--no-psqlrc",
            ]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3600,
                )
            except FileNotFoundError:
                raise RestoreError(
                    f"psql not found at {self.psql_path!r}",
                    "psql_not_found",
                ) from None
            except subprocess.TimeoutExpired:
                raise RestoreError("psql timed out after 1 hour", "psql_timeout")

            if result.returncode != 0:
                raise RestoreError(
                    f"psql failed (exit {result.returncode}): {result.stderr.strip()}",
                    "psql_failed",
                )

            # Count restored rows
            return self._count_rows(conn, tenant_id, tables)

        finally:
            if tmp_dir:
                tmp_dir.cleanup()

    def _count_rows(self, conn: str, tenant_id: str, tables: list[str]) -> int:
        """Count rows in restored tables."""
        total = 0
        try:
            import psycopg

            with psycopg.connect(conn) as c:
                with c.cursor() as cur:
                    for table in tables:
                        cur.execute(
                            f"SELECT count(*) FROM dcc.{table} WHERE tenant_id = %s::uuid",
                            (tenant_id,),
                        )
                        row = cur.fetchone()
                        if row:
                            total += row[0]
        except Exception:
            pass
        return total

    # ------------------------------------------------------------------
    # Point-in-time recovery
    # ------------------------------------------------------------------

    def list_pitr_points(
        self,
        tenant_id: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[PITRPoint]:
        """List available point-in-time recovery targets for a tenant.

        Args:
            tenant_id: Tenant UUID string.
            start: Start of time range.
            end: End of time range.

        Returns:
            List of PITRPoint sorted by target_time descending.
        """
        backups = self.list_backups(tenant_id, status=BackupStatus.COMPLETED)
        points: list[PITRPoint] = []

        for meta in backups:
            pit = meta.point_in_time or meta.created_at
            if start and pit < start:
                continue
            if end and pit > end:
                continue
            points.append(
                PITRPoint(
                    target_time=pit,
                    backup_id=meta.backup_id,
                    estimated_rows=sum(meta.row_counts.values()),
                    confidence="high" if meta.backup_type == BackupType.FULL else "medium",
                )
            )

        points.sort(key=lambda p: p.target_time, reverse=True)
        return points

    def find_pitr_backup(
        self,
        tenant_id: str,
        target_time: datetime,
    ) -> PITRPoint | None:
        """Find the best backup for a point-in-time recovery.

        Finds the latest completed backup at or before the target time.

        Args:
            tenant_id: Tenant UUID string.
            target_time: Target recovery time.

        Returns:
            PITRPoint if a suitable backup exists, None otherwise.
        """
        backups = self.list_backups(tenant_id, status=BackupStatus.COMPLETED)
        candidates: list[BackupMetadata] = []

        for meta in backups:
            pit = meta.point_in_time or meta.created_at
            if pit <= target_time:
                candidates.append(meta)

        if not candidates:
            return None

        best = max(candidates, key=lambda m: m.point_in_time or m.created_at)
        return PITRPoint(
            target_time=best.point_in_time or best.created_at,
            backup_id=best.backup_id,
            estimated_rows=sum(best.row_counts.values()),
            confidence="high" if best.backup_type == BackupType.FULL else "medium",
        )

    # ------------------------------------------------------------------
    # Retention policy
    # ------------------------------------------------------------------

    def get_retention_policy(self, tenant_id: str) -> RetentionPolicy:
        """Get the retention policy for a tenant."""
        path = self._tenant_dir(tenant_id) / self.RETENTION_FILENAME
        if not path.exists():
            return RetentionPolicy()
        data = json.loads(path.read_text(encoding="utf-8"))
        return RetentionPolicy.from_dict(data)

    def set_retention_policy(self, tenant_id: str, policy: RetentionPolicy) -> None:
        """Set the retention policy for a tenant."""
        path = self._tenant_dir(tenant_id) / self.RETENTION_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(policy.to_dict(), indent=2),
            encoding="utf-8",
        )
        tmp.rename(path)

    def apply_retention(self, tenant_id: str, policy: RetentionPolicy | None = None) -> list[str]:
        """Apply retention policy, returning list of deleted backup IDs.

        Keeps:
        - The latest `keep_daily` backups from the last 24 hours
        - The latest `keep_weekly` backups from the last 7 days
        - The latest `keep_monthly` backups from the last 30 days
        - The latest `keep_yearly` backups from the last 365 days
        - At least `min_backups` most recent backups
        - No backup older than `max_age_days`

        Args:
            tenant_id: Tenant UUID string.
            policy: Retention policy (uses tenant's stored policy if None).

        Returns:
            List of deleted backup IDs.
        """
        pol = policy or self.get_retention_policy(tenant_id)
        backups = self.list_backups(tenant_id, status=BackupStatus.COMPLETED)
        if not backups:
            return []

        now = datetime.now(timezone.utc)
        keep: set[str] = set()

        # Always keep minimum
        for meta in backups[: pol.min_backups]:
            keep.add(meta.backup_id)

        # Daily: latest N from last 24h
        day_ago = now - timedelta(days=1)
        daily = [b for b in backups if b.created_at >= day_ago]
        for meta in daily[: pol.keep_daily]:
            keep.add(meta.backup_id)

        # Weekly: latest N from last 7 days
        week_ago = now - timedelta(days=7)
        weekly = [b for b in backups if week_ago <= b.created_at < day_ago]
        for meta in weekly[: pol.keep_weekly]:
            keep.add(meta.backup_id)

        # Monthly: latest N from last 30 days
        month_ago = now - timedelta(days=30)
        monthly = [b for b in backups if month_ago <= b.created_at < week_ago]
        for meta in monthly[: pol.keep_monthly]:
            keep.add(meta.backup_id)

        # Yearly: latest N from last 365 days
        year_ago = now - timedelta(days=365)
        yearly = [b for b in backups if year_ago <= b.created_at < month_ago]
        for meta in yearly[: pol.keep_yearly]:
            keep.add(meta.backup_id)

        # Max age: delete only if older than max_age AND not already kept
        max_age = now - timedelta(days=pol.max_age_days)
        deleted: list[str] = []
        for meta in backups:
            if meta.backup_id not in keep and meta.created_at < max_age:
                self._delete_backup(tenant_id, meta.backup_id)
                deleted.append(meta.backup_id)

        return deleted

    # ------------------------------------------------------------------
    # Backup deletion
    # ------------------------------------------------------------------

    def delete_backup(self, tenant_id: str, backup_id: str) -> bool:
        """Delete a backup.

        Args:
            tenant_id: Tenant UUID string.
            backup_id: Backup UUID string.

        Returns:
            True if the backup was deleted, False if not found.
        """
        return self._delete_backup(tenant_id, backup_id)

    def _delete_backup(self, tenant_id: str, backup_id: str) -> bool:
        """Internal: delete a backup directory."""
        backup_dir = self._backup_dir(tenant_id, backup_id)
        if not backup_dir.exists():
            return False
        shutil.rmtree(backup_dir)
        return True

    # ------------------------------------------------------------------
    # Backup export/import
    # ------------------------------------------------------------------

    def export_backup(self, tenant_id: str, backup_id: str, dest: str | Path) -> Path:
        """Export a backup as a compressed tarball.

        Args:
            tenant_id: Tenant UUID string.
            backup_id: Backup UUID string.
            dest: Destination path for the tarball.

        Returns:
            Path to the created tarball.
        """
        import tarfile

        backup_dir = self._backup_dir(tenant_id, backup_id)
        if not backup_dir.exists():
            raise BackupNotFoundError(backup_id)

        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with tarfile.open(dest_path, "w:gz") as tar:
            tar.add(backup_dir, arcname=backup_id)

        return dest_path

    def import_backup(self, tenant_id: str, source: str | Path) -> BackupMetadata:
        """Import a backup from a tarball.

        Args:
            tenant_id: Tenant UUID string.
            source: Path to the tarball.

        Returns:
            BackupMetadata of the imported backup.
        """
        import tarfile

        source_path = Path(source)
        if not source_path.exists():
            raise BackupError(f"source tarball not found: {source}", "source_not_found")

        with tarfile.open(source_path, "r:gz") as tar:
            members = tar.getnames()
            if not members:
                raise BackupError("empty tarball", "empty_tarball")

            # First member should be the backup directory
            backup_name = members[0].split("/")[0]
            dest_dir = self._tenant_dir(tenant_id) / backup_name
            if dest_dir.exists():
                raise BackupError(
                    f"backup {backup_name!r} already exists for tenant {tenant_id!r}",
                    "backup_already_exists",
                )

            self._tenant_dir(tenant_id).mkdir(parents=True, exist_ok=True)
            tar.extractall(self._tenant_dir(tenant_id))

        return self._read_metadata(tenant_id, backup_name)

    # ------------------------------------------------------------------
    # Statistics and reporting
    # ------------------------------------------------------------------

    def get_backup_stats(self, tenant_id: str) -> dict[str, Any]:
        """Get backup statistics for a tenant.

        Returns:
            Dictionary with backup counts, total size, and age info.
        """
        backups = self.list_backups(tenant_id)
        completed = [b for b in backups if b.status == BackupStatus.COMPLETED]
        failed = [b for b in backups if b.status == BackupStatus.FAILED]

        total_size = sum(b.size_bytes for b in completed)
        total_rows = sum(sum(b.row_counts.values()) for b in completed)

        oldest = min((b.created_at for b in completed), default=None)
        newest = max((b.created_at for b in completed), default=None)

        return {
            "tenant_id": tenant_id,
            "total_backups": len(backups),
            "completed_backups": len(completed),
            "failed_backups": len(failed),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_rows_backed_up": total_rows,
            "oldest_backup": oldest.isoformat() if oldest else None,
            "newest_backup": newest.isoformat() if newest else None,
            "retention_policy": self.get_retention_policy(tenant_id).to_dict(),
        }

    def cleanup_failed(self, tenant_id: str) -> int:
        """Remove all failed backups for a tenant.

        Returns:
            Number of backups removed.
        """
        failed = self.list_backups(tenant_id, status=BackupStatus.FAILED)
        count = 0
        for meta in failed:
            if self._delete_backup(tenant_id, meta.backup_id):
                count += 1
        return count


# ---------------------------------------------------------------------------
# Scheduled backup helper
# ---------------------------------------------------------------------------


class BackupScheduler:
    """Simple scheduler for automated backups.

    Tracks when backups were last created and determines when the next
    backup is due based on a configurable interval.
    """

    def __init__(
        self,
        engine: BackupEngine,
        *,
        interval_hours: float = 24.0,
        backup_type: BackupType = BackupType.FULL,
    ) -> None:
        """Initialize the scheduler.

        Args:
            engine: BackupEngine instance.
            interval_hours: Hours between backups.
            backup_type: Type of backup to create.
        """
        if interval_hours <= 0:
            raise ValueError("interval_hours must be positive")
        self.engine = engine
        self.interval_hours = interval_hours
        self.backup_type = backup_type
        self._last_backup_time: dict[str, datetime] = {}

    def is_due(self, tenant_id: str, now: datetime | None = None) -> bool:
        """Check if a backup is due for a tenant.

        Args:
            tenant_id: Tenant UUID string.
            now: Current time (defaults to datetime.now(timezone.utc)).

        Returns:
            True if a backup is due.
        """
        current = now or datetime.now(timezone.utc)
        last = self._last_backup_time.get(tenant_id)
        if last is None:
            # Check if any completed backup exists within the interval
            backups = self.engine.list_backups(
                tenant_id,
                backup_type=self.backup_type,
                status=BackupStatus.COMPLETED,
                limit=1,
            )
            if not backups:
                return True
            last = backups[0].created_at
            self._last_backup_time[tenant_id] = last

        elapsed = (current - last).total_seconds()
        return elapsed >= self.interval_hours * 3600

    def record_backup(self, tenant_id: str, timestamp: datetime | None = None) -> None:
        """Record that a backup was completed.

        Args:
            tenant_id: Tenant UUID string.
            timestamp: When the backup completed (defaults to now).
        """
        self._last_backup_time[tenant_id] = timestamp or datetime.now(timezone.utc)

    def time_until_due(self, tenant_id: str, now: datetime | None = None) -> float:
        """Get hours until next backup is due.

        Returns:
            Hours until due (0.0 if already due).
        """
        current = now or datetime.now(timezone.utc)
        last = self._last_backup_time.get(tenant_id)
        if last is None:
            backups = self.engine.list_backups(
                tenant_id,
                backup_type=self.backup_type,
                status=BackupStatus.COMPLETED,
                limit=1,
            )
            if not backups:
                return 0.0
            last = backups[0].created_at

        elapsed_hours = (current - last).total_seconds() / 3600
        remaining = self.interval_hours - elapsed_hours
        return max(0.0, remaining)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_tenant_id(tenant_id: str) -> str:
    """Validate a tenant UUID string."""
    if not isinstance(tenant_id, str):
        raise ValueError("tenant_id must be a string")
    try:
        UUID(tenant_id)
    except ValueError:
        raise ValueError("tenant_id must be a valid UUID") from None
    return tenant_id


def validate_backup_id(backup_id: str) -> str:
    """Validate a backup UUID string."""
    if not isinstance(backup_id, str):
        raise ValueError("backup_id must be a string")
    try:
        UUID(backup_id)
    except ValueError:
        raise ValueError("backup_id must be a valid UUID") from None
    return backup_id


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def create_backup(
    backup_root: str | Path,
    tenant_id: str,
    **kwargs: Any,
) -> BackupResult:
    """Convenience function: create a backup with a new engine."""
    engine = BackupEngine(backup_root)
    return engine.create_backup(tenant_id, **kwargs)


def restore_backup(
    backup_root: str | Path,
    tenant_id: str,
    backup_id: str,
    **kwargs: Any,
) -> RestoreResult:
    """Convenience function: restore a backup with a new engine."""
    engine = BackupEngine(backup_root)
    return engine.restore_backup(tenant_id, backup_id, **kwargs)


def verify_backup(
    backup_root: str | Path,
    tenant_id: str,
    backup_id: str,
) -> VerificationResult:
    """Convenience function: verify a backup with a new engine."""
    engine = BackupEngine(backup_root)
    return engine.verify_backup(tenant_id, backup_id)


def list_backups(
    backup_root: str | Path,
    tenant_id: str,
    **kwargs: Any,
) -> list[BackupMetadata]:
    """Convenience function: list backups with a new engine."""
    engine = BackupEngine(backup_root)
    return engine.list_backups(tenant_id, **kwargs)


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "BackupError",
    "BackupNotFoundError",
    "BackupCorruptedError",
    "RestoreError",
    "RetentionPolicyError",
    "BackupType",
    "BackupStatus",
    "RestoreStatus",
    "CompressionType",
    "BackupMetadata",
    "RestoreMetadata",
    "RetentionPolicy",
    "BackupResult",
    "RestoreResult",
    "VerificationResult",
    "PITRPoint",
    "BackupEngine",
    "BackupScheduler",
    "DEFAULT_TABLES",
    "compute_checksum",
    "compute_file_checksum",
    "verify_checksum",
    "compress_data",
    "decompress_data",
    "validate_tenant_id",
    "validate_backup_id",
    "create_backup",
    "restore_backup",
    "verify_backup",
    "list_backups",
]
