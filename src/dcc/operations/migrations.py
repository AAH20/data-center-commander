"""Schema migration engine for Data Center Commander.

Supports versioned, transactional migrations with rollback capability.
Migrations are stored as .sql files in the database/migrations/ directory.

Migration file format:
    -- @version: 001
    -- @name: cost_intelligence
    -- @description: Add cost intelligence tables

    -- UP
    BEGIN;
    CREATE TABLE ...;
    COMMIT;

    -- DOWN
    BEGIN;
    DROP TABLE ...;
    COMMIT;

If no UP/DOWN markers are present, the entire file is treated as an
UP migration with no rollback support.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "database" / "migrations"
TRACKING_TABLE = "dcc.schema_migrations"


class MigrationError(Exception):
    """Base exception for migration failures."""


class MigrationParseError(MigrationError):
    """Raised when a migration file cannot be parsed."""


class MigrationExecutionError(MigrationError):
    """Raised when a migration fails to execute."""


class MigrationNotFoundError(MigrationError):
    """Raised when a requested migration is not found."""


class MigrationState(str, Enum):
    """Status of a migration."""

    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Migration:
    """Represents a single schema migration."""

    version: str
    name: str
    description: str
    up_sql: str
    down_sql: Optional[str] = None
    file_path: Optional[Path] = None
    checksum: str = ""
    state: MigrationState = MigrationState.PENDING
    applied_at: Optional[datetime] = None
    execution_time_ms: Optional[float] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if not self.checksum and self.up_sql:
            self.checksum = hashlib.sha256(self.up_sql.encode()).hexdigest()

    @property
    def has_rollback(self) -> bool:
        """Whether this migration supports rollback."""
        return self.down_sql is not None and len(self.down_sql.strip()) > 0

    @property
    def version_tuple(self) -> tuple[int, ...]:
        """Version as a tuple for comparison."""
        return tuple(int(p) for p in self.version.split("."))


@dataclass
class MigrationResult:
    """Result of a migration operation."""

    success: bool
    migration: Migration
    message: str
    execution_time_ms: float = 0.0


@dataclass
class MigrationReport:
    """Report of migration operations."""

    applied: list[MigrationResult] = field(default_factory=list)
    rolled_back: list[MigrationResult] = field(default_factory=list)
    failed: list[MigrationResult] = field(default_factory=list)
    skipped: list[MigrationResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Whether all operations succeeded."""
        return len(self.failed) == 0

    @property
    def total_operations(self) -> int:
        """Total number of operations performed."""
        return len(self.applied) + len(self.rolled_back) + len(self.failed) + len(self.skipped)


def _parse_migration_file(path: Path) -> Migration:
    """Parse a migration file into a Migration object.

    Supports two formats:
    1. Explicit UP/DOWN markers
    2. Simple format (entire file is UP, no rollback)
    """
    content = path.read_text(encoding="utf-8")

    # Extract metadata from comments
    version_match = re.search(r"--\s*@version:\s*(\S+)", content)
    name_match = re.search(r"--\s*@name:\s*(\S+)", content)
    desc_match = re.search(r"--\s*@description:\s*(.+?)(?:\n|$)", content)

    # Try to infer version from filename (e.g., 001_cost_intelligence.sql)
    file_version_match = re.match(r"(\d+)_", path.name)
    file_name_match = re.match(r"\d+_(.+)\.sql$", path.name)

    version = version_match.group(1) if version_match else (file_version_match.group(1) if file_version_match else "")
    name = name_match.group(1) if name_match else (file_name_match.group(1) if file_name_match else path.stem)
    description = desc_match.group(1).strip() if desc_match else ""

    if not version:
        raise MigrationParseError(f"Cannot determine migration version from {path}")

    # Check for UP/DOWN markers
    up_match = re.search(r"--\s*UP\s*\n(.*?)(?=--\s*DOWN|$)", content, re.DOTALL | re.IGNORECASE)
    down_match = re.search(r"--\s*DOWN\s*\n(.*?)$", content, re.DOTALL | re.IGNORECASE)

    if up_match:
        up_sql = up_match.group(1).strip()
        down_sql = down_match.group(1).strip() if down_match else None
    else:
        # Simple format: entire file is UP
        up_sql = content.strip()
        down_sql = None

    if not up_sql:
        raise MigrationParseError(f"Migration {path} has no UP SQL")

    return Migration(
        version=version,
        name=name,
        description=description,
        up_sql=up_sql,
        down_sql=down_sql,
        file_path=path,
    )


def discover_migrations(migrations_dir: Path | None = None) -> list[Migration]:
    """Discover all migration files in the given directory.

    Returns migrations sorted by version.
    """
    if migrations_dir is None:
        migrations_dir = DEFAULT_MIGRATIONS_DIR

    if not migrations_dir.exists():
        raise MigrationError(f"Migrations directory not found: {migrations_dir}")

    migrations = []
    for path in sorted(migrations_dir.glob("*.sql")):
        try:
            migration = _parse_migration_file(path)
            migrations.append(migration)
        except MigrationParseError as exc:
            logger.warning("Skipping invalid migration file %s: %s", path, exc)

    # Sort by version
    migrations.sort(key=lambda m: m.version_tuple)
    return migrations


def _ensure_tracking_table(conn: Any) -> None:
    """Create the schema_migrations tracking table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TRACKING_TABLE} (
                version text PRIMARY KEY,
                name text NOT NULL,
                description text NOT NULL DEFAULT '',
                checksum text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now(),
                execution_time_ms numeric(12,2),
                state text NOT NULL DEFAULT 'applied'
                    CHECK (state IN ('applied', 'failed', 'rolled_back')),
                error_message text
            )
        """)
        # Add RLS
        cur.execute(f"""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'dcc' AND c.relname = 'schema_migrations'
                      AND c.relrowsecurity = true
                ) THEN
                    ALTER TABLE {TRACKING_TABLE} ENABLE ROW LEVEL SECURITY;
                    ALTER TABLE {TRACKING_TABLE} FORCE ROW LEVEL SECURITY;
                END IF;
            END $$;
        """)
    conn.commit()


def _get_applied_migrations(conn: Any) -> dict[str, Migration]:
    """Get all applied migrations from the tracking table."""
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT version, name, description, checksum, applied_at,
                   execution_time_ms, state, error_message
            FROM {TRACKING_TABLE}
            ORDER BY applied_at
        """)
        rows = cur.fetchall()

    applied = {}
    for row in rows:
        version = row[0]
        applied[version] = Migration(
            version=version,
            name=row[1],
            description=row[2] or "",
            up_sql="",  # Not stored, only checksum
            checksum=row[3] or "",
            applied_at=row[4],
            execution_time_ms=float(row[5]) if row[5] else None,
            state=MigrationState(row[6]) if row[6] else MigrationState.APPLIED,
            error_message=row[7],
        )
    return applied


def _record_migration(conn: Any, migration: Migration, execution_time_ms: float) -> None:
    """Record a successfully applied migration."""
    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO {TRACKING_TABLE}
                (version, name, description, checksum, applied_at, execution_time_ms, state)
            VALUES (%s, %s, %s, %s, now(), %s, 'applied')
            ON CONFLICT (version) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                checksum = EXCLUDED.checksum,
                applied_at = EXCLUDED.applied_at,
                execution_time_ms = EXCLUDED.execution_time_ms,
                state = 'applied',
                error_message = NULL
        """, (migration.version, migration.name, migration.description,
              migration.checksum, execution_time_ms))
    conn.commit()


def _record_rollback(conn: Any, version: str) -> None:
    """Record a migration rollback."""
    with conn.cursor() as cur:
        cur.execute(f"""
            UPDATE {TRACKING_TABLE}
            SET state = 'rolled_back', error_message = NULL
            WHERE version = %s
        """, (version,))
    conn.commit()


def _record_failure(conn: Any, migration: Migration, error: str) -> None:
    """Record a failed migration."""
    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO {TRACKING_TABLE}
                (version, name, description, checksum, applied_at, state, error_message)
            VALUES (%s, %s, %s, %s, now(), 'failed', %s)
            ON CONFLICT (version) DO UPDATE SET
                state = 'failed',
                error_message = EXCLUDED.error_message
        """, (migration.version, migration.name, migration.description,
              migration.checksum, error))
    conn.commit()


def _execute_sql(conn: Any, sql: str) -> None:
    """Execute SQL, handling multiple statements."""
    # Split on semicolons but be careful with $$ blocks
    # Simple approach: execute as-is, psycopg handles multiple statements
    with conn.cursor() as cur:
        cur.execute(sql)


def migrate(
    conn: Any,
    migrations_dir: Path | None = None,
    target_version: str | None = None,
    dry_run: bool = False,
) -> MigrationReport:
    """Apply pending migrations up to the target version.

    Args:
        conn: A psycopg connection object.
        migrations_dir: Directory containing migration files.
        target_version: Stop at this version (None = apply all).
        dry_run: If True, only report what would be done.

    Returns:
        MigrationReport with details of the operation.
    """
    report = MigrationReport()

    # Ensure tracking table exists
    _ensure_tracking_table(conn)

    # Discover migrations
    migrations = discover_migrations(migrations_dir)
    applied = _get_applied_migrations(conn)

    # Filter to pending migrations
    pending = []
    for m in migrations:
        if m.version in applied:
            existing = applied[m.version]
            if existing.state == MigrationState.APPLIED:
                # Check for checksum mismatch
                if existing.checksum and existing.checksum != m.checksum:
                    report.failed.append(MigrationResult(
                        success=False,
                        migration=m,
                        message=f"Checksum mismatch: applied={existing.checksum[:8]}... "
                                f"current={m.checksum[:8]}...",
                    ))
                else:
                    report.skipped.append(MigrationResult(
                        success=True,
                        migration=m,
                        message=f"Already applied at {existing.applied_at}",
                    ))
                continue
            elif existing.state == MigrationState.FAILED:
                # Retry failed migrations
                pending.append(m)
                continue
        else:
            pending.append(m)

    # Apply pending migrations
    for migration in pending:
        if target_version and migration.version_tuple > tuple(int(p) for p in target_version.split(".")):
            report.skipped.append(MigrationResult(
                success=True,
                migration=migration,
                message=f"Skipped (beyond target version {target_version})",
            ))
            continue

        if dry_run:
            report.skipped.append(MigrationResult(
                success=True,
                migration=migration,
                message="Dry run - would apply",
            ))
            continue

        logger.info("Applying migration %s: %s", migration.version, migration.name)
        start = datetime.now(timezone.utc)

        try:
            # Execute in a transaction
            with conn.transaction():
                _execute_sql(conn, migration.up_sql)
                _record_migration(conn, migration, 0)  # Will update with actual time

            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000

            # Update with actual execution time
            with conn.cursor() as cur:
                cur.execute(f"""
                    UPDATE {TRACKING_TABLE}
                    SET execution_time_ms = %s
                    WHERE version = %s
                """, (elapsed, migration.version))
            conn.commit()

            migration.state = MigrationState.APPLIED
            migration.applied_at = datetime.now(timezone.utc)
            migration.execution_time_ms = elapsed

            report.applied.append(MigrationResult(
                success=True,
                migration=migration,
                message=f"Applied in {elapsed:.1f}ms",
                execution_time_ms=elapsed,
            ))
            logger.info("Applied migration %s in %.1fms", migration.version, elapsed)

        except Exception as exc:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            error_msg = str(exc)
            logger.error("Migration %s failed: %s", migration.version, error_msg)

            try:
                _record_failure(conn, migration, error_msg)
            except Exception:
                logger.exception("Failed to record migration failure")

            migration.state = MigrationState.FAILED
            migration.error_message = error_msg

            report.failed.append(MigrationResult(
                success=False,
                migration=migration,
                message=f"Failed: {error_msg}",
                execution_time_ms=elapsed,
            ))

            # Stop on first failure
            break

    return report


def rollback(
    conn: Any,
    steps: int = 1,
    target_version: str | None = None,
    dry_run: bool = False,
) -> MigrationReport:
    """Rollback the last N migrations or to a target version.

    Args:
        conn: A psycopg connection object.
        steps: Number of migrations to rollback (ignored if target_version set).
        target_version: Rollback until this version is the latest applied.
        dry_run: If True, only report what would be done.

    Returns:
        MigrationReport with details of the operation.
    """
    report = MigrationReport()

    # Ensure tracking table exists
    _ensure_tracking_table(conn)

    # Get applied migrations
    applied = _get_applied_migrations(conn)
    applied_versions = sorted(
        [v for v, m in applied.items() if m.state == MigrationState.APPLIED],
        key=lambda v: tuple(int(p) for p in v.split(".")),
    )

    if not applied_versions:
        logger.info("No migrations to rollback")
        return report

    # Determine which migrations to rollback
    to_rollback = []
    if target_version:
        target_tuple = tuple(int(p) for p in target_version.split("."))
        for version in reversed(applied_versions):
            if tuple(int(p) for p in version.split(".")) > target_tuple:
                to_rollback.append(version)
            else:
                break
    else:
        to_rollback = list(reversed(applied_versions[-steps:]))

    if not to_rollback:
        logger.info("No migrations to rollback")
        return report

    # Discover migrations to get DOWN SQL
    all_migrations = {m.version: m for m in discover_migrations()}

    for version in to_rollback:
        migration = all_migrations.get(version)
        if not migration:
            report.failed.append(MigrationResult(
                success=False,
                migration=Migration(version=version, name="unknown", description="", up_sql=""),
                message=f"Migration file not found for version {version}",
            ))
            continue

        if not migration.has_rollback:
            report.failed.append(MigrationResult(
                success=False,
                migration=migration,
                message="No DOWN SQL available for rollback",
            ))
            continue

        if dry_run:
            report.skipped.append(MigrationResult(
                success=True,
                migration=migration,
                message="Dry run - would rollback",
            ))
            continue

        logger.info("Rolling back migration %s: %s", migration.version, migration.name)
        start = datetime.now(timezone.utc)

        try:
            with conn.transaction():
                _execute_sql(conn, migration.down_sql or "")
                _record_rollback(conn, version)

            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000

            migration.state = MigrationState.ROLLED_BACK
            report.rolled_back.append(MigrationResult(
                success=True,
                migration=migration,
                message=f"Rolled back in {elapsed:.1f}ms",
                execution_time_ms=elapsed,
            ))
            logger.info("Rolled back migration %s in %.1fms", migration.version, elapsed)

        except Exception as exc:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            error_msg = str(exc)
            logger.error("Rollback of migration %s failed: %s", migration.version, error_msg)

            report.failed.append(MigrationResult(
                success=False,
                migration=migration,
                message=f"Rollback failed: {error_msg}",
                execution_time_ms=elapsed,
            ))
            break

    return report


def status(conn: Any, migrations_dir: Path | None = None) -> dict[str, Any]:
    """Get the current migration status.

    Returns a dict with:
        - applied: list of applied migration versions
        - pending: list of pending migration versions
        - failed: list of failed migration versions
        - current_version: the latest applied version
    """
    _ensure_tracking_table(conn)
    applied = _get_applied_migrations(conn)
    all_migrations = discover_migrations(migrations_dir)

    applied_versions = []
    pending_versions = []
    failed_versions = []

    for m in all_migrations:
        if m.version in applied:
            if applied[m.version].state == MigrationState.APPLIED:
                applied_versions.append(m.version)
            elif applied[m.version].state == MigrationState.FAILED:
                failed_versions.append(m.version)
            else:
                pending_versions.append(m.version)
        else:
            pending_versions.append(m.version)

    current_version = applied_versions[-1] if applied_versions else None

    return {
        "applied": sorted(applied_versions, key=lambda v: tuple(int(p) for p in v.split("."))),
        "pending": sorted(pending_versions, key=lambda v: tuple(int(p) for p in v.split("."))),
        "failed": sorted(failed_versions, key=lambda v: tuple(int(p) for p in v.split("."))),
        "current_version": current_version,
        "total_migrations": len(all_migrations),
    }


def create_migration(
    name: str,
    migrations_dir: Path | None = None,
    up_sql: str = "",
    down_sql: str | None = None,
) -> Path:
    """Create a new migration file with the next version number.

    Args:
        name: Short name for the migration (e.g., "add_user_table").
        migrations_dir: Directory to create the file in.
        up_sql: Initial UP SQL content.
        down_sql: Initial DOWN SQL content.

    Returns:
        Path to the created migration file.
    """
    if migrations_dir is None:
        migrations_dir = DEFAULT_MIGRATIONS_DIR

    migrations_dir.mkdir(parents=True, exist_ok=True)

    # Find next version number
    existing = list(migrations_dir.glob("*.sql"))
    max_version = 0
    for path in existing:
        match = re.match(r"(\d+)_", path.name)
        if match:
            max_version = max(max_version, int(match.group(1)))

    next_version = f"{max_version + 1:03d}"
    filename = f"{next_version}_{name}.sql"
    filepath = migrations_dir / filename

    # Build content
    lines = [
        f"-- @version: {next_version}",
        f"-- @name: {name}",
        f"-- @description: ",
        "",
        "-- UP",
        up_sql.strip() if up_sql else "BEGIN;",
        "",
    ]

    if down_sql:
        lines.extend([
            "-- DOWN",
            down_sql.strip(),
            "",
        ])
    else:
        lines.extend([
            "-- DOWN",
            "-- TODO: Add rollback SQL",
            "",
        ])

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


def verify(conn: Any, migrations_dir: Path | None = None) -> list[str]:
    """Verify that applied migrations match their files.

    Returns a list of issues found. Empty list means all good.
    """
    _ensure_tracking_table(conn)
    applied = _get_applied_migrations(conn)
    all_migrations = {m.version: m for m in discover_migrations(migrations_dir)}

    issues = []
    for version, applied_migration in applied.items():
        if applied_migration.state != MigrationState.APPLIED:
            continue

        current = all_migrations.get(version)
        if not current:
            issues.append(f"Version {version}: file not found")
            continue

        if applied_migration.checksum != current.checksum:
            issues.append(
                f"Version {version}: checksum mismatch "
                f"(applied={applied_migration.checksum[:8]}..., "
                f"current={current.checksum[:8]}...)"
            )

    return issues
