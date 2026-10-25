"""Backup policy management for Data Center Commander.

Provides declarative backup policies that define what to back up, when,
and how long to keep it. Policies are tenant-scoped and produce
structured, auditable results.

One policy, two independent axes
--------------------------------
A backup policy answers two different questions, and this module keeps them
in two different fields:

* **what a run writes** -- :class:`BackupType` (``full``/``incremental``/
  ``differential``), stored in ``dcc.backup_policies.backup_type``. The same
  three values are ``dcc.backup_runs.backup_type`` and the real engine's
  ``BackupType``, so a policy and the run it produces describe the artifact
  the same way.
* **when a run happens** -- :class:`PolicyTrigger` (``scheduled``/
  ``on_demand``/``continuous``/``snapshot``), stored in
  ``dcc.backup_policies.policy_type``. Intervals live in ``schedule``
  (:class:`PolicySchedule`) plus ``custom_cron``.

Collapsing those two axes into one field is what produced the defect this
module used to have: the table's ``policy_type`` CHECK accepted
``scheduled|continuous|on_demand|snapshot`` while :class:`PolicyType` used
``full|incremental|differential``, so the two layers agreed only on the words
``continuous`` and ``snapshot`` and a ``PolicyType.FULL`` write was rejected
by the database. :class:`PolicyType` survives only as the pre-unification
vocabulary; :meth:`PolicyType.split` is the explicit, total translation from
it to the two axes, and nothing stores a ``PolicyType``.

Pure stdlib implementation: no external dependencies.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Mapping
from uuid import uuid4


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PolicyError(Exception):
    """Base exception for policy failures."""

    def __init__(self, message: str, code: str = "policy_error") -> None:
        self.code = code
        super().__init__(message)


class PolicyNotFoundError(PolicyError):
    """Raised when a policy cannot be found."""

    def __init__(self, policy_id: str) -> None:
        super().__init__(f"policy {policy_id!r} not found", "policy_not_found")


class PolicyValidationError(PolicyError):
    """Raised when a policy definition is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "policy_validation_error")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BackupType(str, Enum):
    """What a run writes -- the backup *kind*.

    Exactly the members of ``dcc.operations.backup.BackupType`` and of the
    ``dcc.backup_runs.backup_type`` CHECK, so the value a policy declares is
    the value the engine records and the database accepts.
    """

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class PolicyTrigger(str, Enum):
    """When a run happens -- the *schedule kind*, not the backup kind.

    Exactly the ``dcc.backup_policies.policy_type`` CHECK. A policy that runs
    nightly and a policy that runs when asked can both produce FULL backups;
    only this field distinguishes them.
    """

    SCHEDULED = "scheduled"
    ON_DEMAND = "on_demand"
    CONTINUOUS = "continuous"
    SNAPSHOT = "snapshot"


class Compression(str, Enum):
    """Compression codec -- the *same* vocabulary as the database column.

    Replaces the ``bool`` this field used to be. A boolean could not express
    ``zstd`` or ``lz4``, and it read as "compression on" while the column's
    own default, ``'none'``, meant the opposite.
    """

    NONE = "none"
    GZIP = "gzip"
    ZSTD = "zstd"
    LZ4 = "lz4"


class PolicyType(str, Enum):
    """DEPRECATED pre-unification vocabulary. Do not store this.

    This is the enum the API used to hand around, and it mixes the two axes:
    ``full``/``incremental``/``differential`` are backup kinds, while
    ``continuous``/``snapshot`` are trigger kinds. It is kept because
    ``DROrchestrator.setup_tenant`` and existing policy JSON files pass it,
    and because it is the one place the old values can be translated from.

    Use :meth:`split` to get the two real fields, :class:`BackupType` and
    :class:`PolicyTrigger`, and store those.
    """

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    CONTINUOUS = "continuous"
    SNAPSHOT = "snapshot"

    @property
    def axis(self) -> str:
        """Which field this member belongs in: ``"backup"`` or ``"trigger"``."""
        if self in (PolicyType.FULL, PolicyType.INCREMENTAL, PolicyType.DIFFERENTIAL):
            return "backup"
        return "trigger"

    def split(self) -> tuple[BackupType | None, PolicyTrigger]:
        """Translate one legacy value into the two fields it really means.

        Total: every member maps to exactly one ``(backup_type, policy_type)``
        pair, so no legacy value is silently dropped. ``continuous`` and
        ``snapshot`` describe protection with no discrete engine backup
        artifact, so their ``backup_type`` is ``None`` -- which is what the
        database's biconditional CHECK requires for them.
        """
        return _LEGACY_SPLIT[PolicyType(self)]


#: The one place a legacy value becomes the two real fields. Written out
#: rather than derived so a new :class:`PolicyType` member cannot default
#: into a plausible-looking translation.
_LEGACY_SPLIT: dict[PolicyType, tuple[BackupType | None, PolicyTrigger]] = {
    PolicyType.FULL: (BackupType.FULL, PolicyTrigger.SCHEDULED),
    PolicyType.INCREMENTAL: (BackupType.INCREMENTAL, PolicyTrigger.SCHEDULED),
    PolicyType.DIFFERENTIAL: (BackupType.DIFFERENTIAL, PolicyTrigger.SCHEDULED),
    PolicyType.CONTINUOUS: (None, PolicyTrigger.CONTINUOUS),
    PolicyType.SNAPSHOT: (None, PolicyTrigger.SNAPSHOT),
}


class PolicySchedule(str, Enum):
    """Schedule frequency for a policy.

    Exactly the values migration 012 allows in ``dcc.backup_policies.schedule``.
    """

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class PolicyStatus(str, Enum):
    """Lifecycle status of a policy."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    ARCHIVED = "archived"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BackupPolicy:
    """Declarative backup policy -- a record of intent, not an executor.

    Nothing in this class, and nothing in this package, runs a backup. The only
    component in the product that executes backups is
    :class:`dcc.operations.backup.BackupEngine`, which shells out to ``pg_dump``
    and ``psql``; ``dcc.dr`` deliberately does not import ``dcc.operations`` so
    that DR policy bookkeeping stays stdlib-only and importable without a
    database. Every field here is metadata: what to back up, how often, and how
    long to keep it.

    The bridge to the engine is :meth:`to_engine_params`, which produces the
    keyword arguments ``BackupEngine.create_backup`` accepts. It refuses
    policies the engine cannot execute -- a continuous or snapshot policy has
    no ``backup_type`` at all, and a ``zstd``/``lz4`` codec has no engine
    equivalent -- instead of silently mapping them onto a full gzip dump. A
    policy that claims continuous protection while doing a nightly dump is
    worse than one that fails loudly.

    The stored shape is one row of ``dcc.backup_policies``, and the mapping is
    explicit in both directions (:func:`policy_from_row` /
    :func:`policy_to_row`) rather than left to each caller. Field names are
    identical on both sides; that is the point of migration 012.

    Attributes:
        policy_id: Unique identifier.
        tenant_id: Tenant this policy belongs to.
        name: Human-readable name.
        policy_type: When the policy runs -- a :class:`PolicyTrigger`. A
            ``PolicyType`` is accepted and translated, see ``__post_init__``.
        backup_type: What a run writes -- a :class:`BackupType`, or ``None``
            for ``continuous``/``snapshot`` triggers that produce no discrete
            engine backup.
        schedule: How often to run, or ``None`` when there is no cadence.
        retention_days: How long to keep backups.
        tables: Tables to include (empty = all).
        compression: Codec used for the backup file, a :class:`Compression`.
        verify_after: Whether to verify after backup.
        enabled: Whether the policy is active.
        tags: Arbitrary metadata, flat string-to-string.
        created_at: When the policy was created.
        updated_at: When the policy was last updated.
        last_run_at: When the policy last ran.
        next_run_at: When the policy is next scheduled.
        status: Lifecycle state -- a :class:`PolicyStatus`. Run outcomes belong
            to ``dcc.backup_runs``, not to the policy definition.
        custom_cron: Cron expression, required iff ``schedule`` is ``custom``.
    """

    policy_id: str
    tenant_id: str
    name: str
    policy_type: PolicyTrigger = PolicyTrigger.SCHEDULED
    backup_type: BackupType | None = BackupType.FULL
    schedule: PolicySchedule | None = PolicySchedule.DAILY
    retention_days: int = 30
    tables: list[str] = field(default_factory=list)
    compression: Compression = Compression.GZIP
    verify_after: bool = True
    enabled: bool = True
    tags: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    status: PolicyStatus = PolicyStatus.ACTIVE
    custom_cron: str | None = None

    def __post_init__(self) -> None:
        """Translate legacy input, then enforce the invariants migration 012 stores.

        Everything here is a rejection with a named field, never a silent
        coercion: a ``bool`` compression is an error rather than "on", and a
        ``str`` status is an error rather than a guessed member.
        """
        # A PolicyType mixes the two axes, so it is split once, here, in either
        # field, and never kept. This is the only compatibility path.
        legacy: PolicyType | None = None
        if isinstance(self.policy_type, PolicyType):
            legacy = self.policy_type
        elif isinstance(self.backup_type, PolicyType):
            legacy = self.backup_type
        if legacy is not None:
            backup_type, trigger = legacy.split()
            object.__setattr__(self, "policy_type", trigger)
            object.__setattr__(self, "backup_type", backup_type)

        if not isinstance(self.policy_type, PolicyTrigger):
            raise PolicyValidationError(
                f"policy_type must be a PolicyTrigger, got {self.policy_type!r}"
            )
        if self.backup_type is not None and not isinstance(self.backup_type, BackupType):
            raise PolicyValidationError(
                f"backup_type must be a BackupType or None, got {self.backup_type!r}"
            )
        if self.schedule is not None and not isinstance(self.schedule, PolicySchedule):
            raise PolicyValidationError(
                f"schedule must be a PolicySchedule or None, got {self.schedule!r}"
            )
        if not isinstance(self.compression, Compression):
            raise PolicyValidationError(
                f"compression must be a Compression codec "
                f"({', '.join(c.value for c in Compression)}), got {self.compression!r}"
            )
        if not isinstance(self.status, PolicyStatus):
            raise PolicyValidationError(
                f"status must be a PolicyStatus, got {self.status!r}"
            )

        #: Triggers that produce no discrete engine backup artifact.
        _no_artifact = (PolicyTrigger.CONTINUOUS, PolicyTrigger.SNAPSHOT)
        if self.policy_type in _no_artifact and self.backup_type is not None:
            raise PolicyValidationError(
                f"{self.policy_type.value} policy cannot declare backup_type "
                f"{self.backup_type.value!r}: it produces no full/incremental/"
                f"differential backup"
            )
        if self.policy_type not in _no_artifact and self.backup_type is None:
            raise PolicyValidationError(
                f"{self.policy_type.value} policy must declare a backup_type "
                f"({', '.join(b.value for b in BackupType)})"
            )

        if self.policy_type is PolicyTrigger.SCHEDULED and self.schedule is None:
            raise PolicyValidationError(
                "a scheduled policy needs a schedule "
                f"({', '.join(s.value for s in PolicySchedule)})"
            )
        if self.schedule is PolicySchedule.CUSTOM and not self.custom_cron:
            raise PolicyValidationError("custom schedule requires custom_cron")
        if self.schedule is not PolicySchedule.CUSTOM and self.custom_cron:
            raise PolicyValidationError(
                "custom_cron is only meaningful with schedule='custom'; "
                f"got schedule={self.schedule.value if self.schedule else None!r}"
            )

        if self.retention_days < 1:
            raise PolicyValidationError("retention_days must be >= 1")
        if self.enabled and self.status is not PolicyStatus.ACTIVE:
            # is_due() requires both, so enabled+paused would be a policy that
            # is switched on and never runs. The database CHECK says the same.
            raise PolicyValidationError(
                f"an enabled policy must have status 'active', got "
                f"{self.status.value!r}; set enabled=False to pause it"
            )
        if not isinstance(self.tags, dict) or any(
            not isinstance(k, str) or not isinstance(v, str)
            for k, v in self.tags.items()
        ):
            raise PolicyValidationError(
                "tags must be a flat mapping of string keys to string values"
            )

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe view. Field names are the column names of the table."""
        return {
            "policy_id": self.policy_id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "policy_type": self.policy_type.value,
            "backup_type": self.backup_type.value if self.backup_type else None,
            "schedule": self.schedule.value if self.schedule else None,
            "retention_days": self.retention_days,
            "tables": list(self.tables),
            "compression": self.compression.value,
            "verify_after": self.verify_after,
            "enabled": self.enabled,
            "tags": dict(self.tags),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "status": self.status.value,
            "custom_cron": self.custom_cron,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupPolicy:
        """Rebuild from :meth:`to_dict` output or from a pre-012 JSON document.

        The legacy spellings that exist in the wild are translated explicitly
        here -- a ``bool`` compression and a run-state ``status`` -- because
        both were written to disk by older versions of this very module.
        ``PolicyEngine.list_policies`` skips documents it cannot parse, so
        rejecting them instead of translating them would silently drop every
        policy file written before the unification.
        """
        trigger, backup_type = _type_fields_from_stored(
            data.get("policy_type", PolicyTrigger.SCHEDULED.value),
            data.get("backup_type"),
        )
        status = _status_from_stored(data.get("status"))
        # A policy that is not active is not enabled either, exactly as
        # migration 012 sets it: enabled+paused would be switched on and
        # guaranteed never to run.
        enabled = bool(data.get("enabled", True)) and status is PolicyStatus.ACTIVE
        return cls(
            policy_id=data["policy_id"],
            tenant_id=data["tenant_id"],
            name=data["name"],
            policy_type=trigger,
            backup_type=backup_type,
            schedule=_schedule_from_stored(data.get("schedule")),
            retention_days=int(data.get("retention_days", 30)),
            tables=list(data.get("tables") or []),
            compression=_compression_from_stored(data.get("compression")),
            verify_after=bool(data.get("verify_after", True)),
            enabled=enabled,
            tags=dict(data.get("tags") or {}),
            created_at=_as_datetime(data["created_at"], field="created_at"),
            updated_at=_as_datetime(data["updated_at"], field="updated_at"),
            last_run_at=_as_datetime(data.get("last_run_at"), field="last_run_at"),
            next_run_at=_as_datetime(data.get("next_run_at"), field="next_run_at"),
            status=_status_from_stored(data.get("status")),
            custom_cron=data.get("custom_cron"),
        )

    # ------------------------------------------------------------------
    # Bridge to the real execution engine
    # ------------------------------------------------------------------

    #: Codecs ``dcc.operations.backup.BackupEngine`` can actually write. The
    #: engine's ``CompressionType`` has two members, so ``zstd`` and ``lz4`` are
    #: declarable in the policy table (the column allows them) but not
    #: executable; ``to_engine_params`` refuses rather than downgrading.
    ENGINE_COMPRESSION: ClassVar[dict[Compression, str]] = {
        Compression.NONE: "none",
        Compression.GZIP: "gzip",
    }

    def to_engine_params(self) -> dict[str, Any]:
        """Keyword arguments for ``BackupEngine.create_backup``.

        Returned values are plain strings matching the engine's ``BackupType``
        and ``CompressionType`` members, so this module does not have to import
        ``dcc.operations`` and stays stdlib-only.

        Returns:
            Dict with ``tenant_id``, ``backup_type``, ``tables``, ``compression``
            and ``tags`` -- a subset of ``create_backup``'s parameters. Each key
            is asserted against the engine's real signature in the unit tests,
            so the two cannot drift apart silently.

        Raises:
            PolicyValidationError: If the policy has no engine equivalent -- a
                continuous or snapshot trigger, or a codec the engine cannot
                write -- rather than downgrading it to a full gzip backup.
        """
        if self.backup_type is None:
            raise PolicyValidationError(
                f"policy type {self.policy_type.value!r} has no BackupEngine "
                f"equivalent; the engine can run "
                f"{sorted(b.value for b in BackupType)}"
            )
        try:
            compression = self.ENGINE_COMPRESSION[self.compression]
        except KeyError:
            raise PolicyValidationError(
                f"compression {self.compression.value!r} has no BackupEngine "
                f"equivalent; the engine can write "
                f"{sorted(c.value for c in self.ENGINE_COMPRESSION)}"
            ) from None

        return {
            "tenant_id": self.tenant_id,
            # The engine treats None as "every table"; an empty list here means
            # the same thing, so translating is what keeps "all" from being
            # read as "no tables".
            "tables": list(self.tables) or None,
            "backup_type": self.backup_type.value,
            "compression": compression,
            "tags": dict(self.tags) or None,
        }

    def to_retention_params(self) -> dict[str, int]:
        """Retention fields for ``BackupEngine.apply_retention``.

        ``retention_days`` is an age cap, which is the engine's
        ``max_age_days``. The engine's per-period counts (keep_daily/weekly/
        monthly/yearly) have no counterpart on this record, so they are left
        alone and the engine's own defaults apply.
        """
        return {"max_age_days": self.retention_days}


# ---------------------------------------------------------------------------
# Translating between the record and its row
# ---------------------------------------------------------------------------

#: Every column of ``dcc.backup_policies`` that carries policy state, in the
#: order :func:`policy_from_row` expects. ``SELECT_COLUMNS`` is this list
#: spelled for a query, so the API cannot drift from the record by writing its
#: own column list. The two uuid columns are cast to text because the record
#: holds ids as strings and the API returns them as strings.
ROW_COLUMNS: tuple[str, ...] = (
    "policy_id",
    "tenant_id",
    "name",
    "policy_type",
    "backup_type",
    "schedule",
    "custom_cron",
    "retention_days",
    "tables",
    "compression",
    "verify_after",
    "enabled",
    "status",
    "tags",
    "created_at",
    "updated_at",
    "last_run_at",
    "next_run_at",
)

SELECT_COLUMNS: str = ", ".join(
    f"{column}::text AS {column}" if column in ("policy_id", "tenant_id") else column
    for column in ROW_COLUMNS
)

#: Run states the pre-012 ``status`` column used to hold. They are per-run
#: facts, not lifecycle, so migration 012 maps them onto lifecycle values and
#: this table is repeated here to keep already-written JSON documents reading
#: the same way the database does.
_RUN_STATE_TO_LIFECYCLE: dict[str, PolicyStatus] = {
    "pending": PolicyStatus.ACTIVE,
    "running": PolicyStatus.ACTIVE,
    "succeeded": PolicyStatus.ACTIVE,
    "failed": PolicyStatus.PAUSED,
    "disabled": PolicyStatus.DISABLED,
}


def _as_datetime(value: Any, *, field: str) -> datetime | None:
    """Accept a ``datetime`` from psycopg or an ISO string from JSON.

    Naive values are read as UTC rather than as local time, because the column
    is ``timestamptz`` and a policy's schedule must not move with the server's
    timezone setting.
    """
    if value is None or isinstance(value, datetime):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise PolicyValidationError(f"{field} is not an ISO-8601 timestamp: {value!r}") from exc
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    raise PolicyValidationError(f"{field} must be a timestamp, got {value!r}")


def _schedule_from_stored(value: Any) -> PolicySchedule | None:
    if value is None or value == "":
        return None
    try:
        return PolicySchedule(value)
    except ValueError as exc:
        raise PolicyValidationError(
            f"schedule {value!r} is not one of "
            f"{sorted(s.value for s in PolicySchedule)}"
        ) from exc


def _compression_from_stored(value: Any) -> Compression:
    """Codec from storage, translating the pre-012 boolean exactly once.

    ``True`` meant gzip and ``False`` meant no compression in the old dataclass,
    and those are the only two readings of a boolean that are defensible, so
    they are translated explicitly rather than through ``bool()``.
    """
    if isinstance(value, bool):
        return Compression.GZIP if value else Compression.NONE
    if value is None or value == "":
        # The column default is 'none'; a missing value means the default.
        return Compression.NONE
    try:
        return Compression(value)
    except ValueError as exc:
        raise PolicyValidationError(
            f"compression {value!r} is not one of "
            f"{sorted(c.value for c in Compression)}"
        ) from exc


def _status_from_stored(value: Any) -> PolicyStatus:
    if value is None or value == "":
        return PolicyStatus.ACTIVE
    try:
        return PolicyStatus(value)
    except ValueError:
        pass
    try:
        return _RUN_STATE_TO_LIFECYCLE[value]
    except KeyError:
        raise PolicyValidationError(
            f"status {value!r} is neither a lifecycle state "
            f"({sorted(s.value for s in PolicyStatus)}) nor a pre-012 run state "
            f"({sorted(_RUN_STATE_TO_LIFECYCLE)})"
        ) from None


def _type_fields_from_stored(
    policy_type: Any, backup_type: Any
) -> tuple[PolicyTrigger, BackupType | None]:
    """Resolve the two type fields from a row or a JSON document.

    A document carrying ``backup_type`` was written after the unification and
    its ``policy_type`` is already a trigger. A document without one is a
    pre-012 document whose single field may hold either axis, so it goes
    through :meth:`PolicyType.split` -- the same translation ``__post_init__``
    applies, not a second copy of it.
    """
    if backup_type is None and policy_type is not None:
        try:
            PolicyType(policy_type)
        except ValueError:
            legacy = None
        else:
            legacy = PolicyType(policy_type)
        if legacy is not None:
            translated_backup, trigger = legacy.split()
            return trigger, translated_backup
    try:
        trigger = PolicyTrigger(policy_type)
    except ValueError as exc:
        raise PolicyValidationError(
            f"policy_type {policy_type!r} is not a trigger "
            f"({sorted(t.value for t in PolicyTrigger)})"
        ) from exc
    if backup_type is None:
        return trigger, None
    try:
        return trigger, BackupType(backup_type)
    except ValueError as exc:
        raise PolicyValidationError(
            f"backup_type {backup_type!r} is not "
            f"{sorted(b.value for b in BackupType)}"
        ) from exc


def policy_from_row(row: Mapping[str, Any]) -> BackupPolicy:
    """Build a :class:`BackupPolicy` from a ``dcc.backup_policies`` row.

    Accepts a psycopg ``dict_row`` or any mapping with the same keys; missing
    keys raise ``KeyError`` rather than filling in a default, because a default
    that disagrees with the stored row is exactly the kind of silent divergence
    this module exists to prevent.
    """
    return BackupPolicy.from_dict(
        {
            "policy_id": row["policy_id"],
            "tenant_id": row["tenant_id"],
            "name": row["name"],
            "policy_type": row["policy_type"],
            "backup_type": row["backup_type"],
            "schedule": row["schedule"],
            "custom_cron": row["custom_cron"],
            "retention_days": row["retention_days"],
            "tables": list(row["tables"] or []),
            "compression": row["compression"],
            "verify_after": row["verify_after"],
            "enabled": row["enabled"],
            "status": row["status"],
            "tags": dict(row["tags"] or {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_run_at": row["last_run_at"],
            "next_run_at": row["next_run_at"],
        }
    )


def policy_to_row(policy: BackupPolicy) -> dict[str, Any]:
    """Column values for an ``INSERT``/``UPDATE`` of ``dcc.backup_policies``.

    Keys are exactly :data:`ROW_COLUMNS`, values are already in the database's
    vocabulary (enum values as text, ``None`` where the column is nullable), so
    a caller writes the row without re-deriving anything.
    """
    row: dict[str, Any] = {
        "policy_id": policy.policy_id,
        "tenant_id": policy.tenant_id,
        "name": policy.name,
        "policy_type": policy.policy_type.value,
        "backup_type": policy.backup_type.value if policy.backup_type else None,
        "schedule": policy.schedule.value if policy.schedule else None,
        "custom_cron": policy.custom_cron,
        "retention_days": policy.retention_days,
        "tables": list(policy.tables),
        "compression": policy.compression.value,
        "verify_after": policy.verify_after,
        "enabled": policy.enabled,
        "status": policy.status.value,
        "tags": dict(policy.tags),
        "created_at": policy.created_at,
        "updated_at": policy.updated_at,
        "last_run_at": policy.last_run_at,
        "next_run_at": policy.next_run_at,
    }
    assert tuple(row) == ROW_COLUMNS, "policy_to_row drifted from ROW_COLUMNS"
    return row


@dataclass
class PolicyRunResult:
    """Result of executing a policy."""

    success: bool
    policy_id: str
    backup_id: str | None = None
    message: str = ""
    duration_seconds: float = 0.0
    error: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "policy_id": self.policy_id,
            "backup_id": self.backup_id,
            "message": self.message,
            "duration_seconds": round(self.duration_seconds, 3),
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# Policy engine
# ---------------------------------------------------------------------------


class PolicyEngine:
    """Manages backup policies for tenants.

    Stores policies on the filesystem with a structured layout::

        <policy_root>/
        ├── <tenant_id>/
        │   ├── <policy_id>.json
        │   └── ...
        └── _defaults.json

    All operations are synchronous and thread-safe at the filesystem level
    via atomic writes.
    """

    def __init__(self, policy_root: str | Path) -> None:
        self.policy_root = Path(policy_root).resolve()
        self._ensure_root()

    def _ensure_root(self) -> None:
        self.policy_root.mkdir(parents=True, exist_ok=True)

    def _tenant_dir(self, tenant_id: str) -> Path:
        return self.policy_root / tenant_id

    def _policy_path(self, tenant_id: str, policy_id: str) -> Path:
        return self._tenant_dir(tenant_id) / f"{policy_id}.json"

    def _write_policy(self, policy: BackupPolicy) -> None:
        path = self._policy_path(policy.tenant_id, policy.policy_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(policy.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        tmp.rename(path)

    def _read_policy(self, tenant_id: str, policy_id: str) -> BackupPolicy:
        path = self._policy_path(tenant_id, policy_id)
        if not path.exists():
            raise PolicyNotFoundError(policy_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        return BackupPolicy.from_dict(data)

    def create_policy(
        self,
        tenant_id: str,
        name: str,
        *,
        policy_type: PolicyType | PolicyTrigger = PolicyType.FULL,
        backup_type: BackupType | None = None,
        schedule: PolicySchedule | None = PolicySchedule.DAILY,
        retention_days: int = 30,
        tables: list[str] | None = None,
        compression: Compression = Compression.GZIP,
        verify_after: bool = True,
        tags: dict[str, str] | None = None,
        custom_cron: str | None = None,
    ) -> BackupPolicy:
        """Create a new backup policy.

        Args:
            tenant_id: Tenant UUID string.
            name: Human-readable policy name.
            policy_type: When the policy runs. Defaults to the pre-unification
                ``PolicyType.FULL``, which means "a full backup on a schedule";
                pass a :class:`PolicyTrigger` to say so directly. Passing a
                legacy ``PolicyType`` also fixes ``backup_type``.
            backup_type: What a run writes. Ignored when ``policy_type`` is a
                legacy ``PolicyType``, which already carries that answer.
            schedule: How often to run, or ``None`` for no cadence.
            retention_days: How long to keep backups.
            tables: Tables to include (None = all).
            compression: Codec for the backup file.
            verify_after: Whether to verify after backup.
            tags: Arbitrary metadata.
            custom_cron: Cron expression for custom schedules.

        Returns:
            The created BackupPolicy.
        """
        policy_id = str(uuid4())
        now = datetime.now(timezone.utc)

        # Calculate next run time. A policy with no cadence is never "next
        # due" -- the scheduler reads next_run_at, so a fabricated one would
        # make an on-demand policy fire on its own.
        next_run = self._calculate_next_run(schedule, now)

        # Split the legacy enum before constructing, so the stored record never
        # holds a PolicyType and the two fields are decided in one visible place
        # rather than implicitly inside __post_init__.
        if isinstance(policy_type, PolicyType):
            resolved_backup, trigger = policy_type.split()
        elif isinstance(backup_type, PolicyType):
            resolved_backup, trigger = backup_type.split()
        else:
            resolved_backup, trigger = backup_type, policy_type

        policy = BackupPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            name=name,
            policy_type=trigger,
            backup_type=resolved_backup,
            schedule=schedule,
            retention_days=retention_days,
            tables=tables or [],
            compression=compression,
            verify_after=verify_after,
            tags=tags or {},
            created_at=now,
            updated_at=now,
            next_run_at=next_run,
            custom_cron=custom_cron,
        )
        self._write_policy(policy)
        return policy

    def _calculate_next_run(
        self, schedule: PolicySchedule | None, now: datetime
    ) -> datetime | None:
        """Calculate the next run time for a schedule."""
        if schedule is None:
            return None
        if schedule == PolicySchedule.HOURLY:
            return now + timedelta(hours=1)
        if schedule == PolicySchedule.DAILY:
            return now + timedelta(days=1)
        if schedule == PolicySchedule.WEEKLY:
            return now + timedelta(weeks=1)
        if schedule == PolicySchedule.MONTHLY:
            # Approximate: add 30 days
            return now + timedelta(days=30)
        return None  # CUSTOM

    def get_policy(self, tenant_id: str, policy_id: str) -> BackupPolicy:
        """Get a policy by ID."""
        return self._read_policy(tenant_id, policy_id)

    def list_policies(
        self,
        tenant_id: str,
        *,
        status: PolicyStatus | None = None,
        enabled_only: bool = False,
    ) -> list[BackupPolicy]:
        """List policies for a tenant.

        Args:
            tenant_id: Tenant UUID string.
            status: Filter by status.
            enabled_only: Only return enabled policies.

        Returns:
            List of BackupPolicy, sorted by created_at descending.
        """
        tenant_dir = self._tenant_dir(tenant_id)
        if not tenant_dir.exists():
            return []

        results: list[BackupPolicy] = []
        for entry in tenant_dir.iterdir():
            if not entry.is_file() or not entry.name.endswith(".json"):
                continue
            if entry.name.startswith("_"):
                continue
            try:
                data = json.loads(entry.read_text(encoding="utf-8"))
                policy = BackupPolicy.from_dict(data)
            except Exception:
                continue
            if status and policy.status != status:
                continue
            if enabled_only and not policy.enabled:
                continue
            results.append(policy)

        results.sort(key=lambda p: p.created_at, reverse=True)
        return results

    def update_policy(
        self,
        tenant_id: str,
        policy_id: str,
        **updates: Any,
    ) -> BackupPolicy:
        """Update a policy.

        Args:
            tenant_id: Tenant UUID string.
            policy_id: Policy UUID string.
            **updates: Fields to update.

        Returns:
            The updated BackupPolicy.
        """
        policy = self._read_policy(tenant_id, policy_id)
        data = policy.to_dict()
        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        for key, value in updates.items():
            if key in data and key not in ("policy_id", "tenant_id", "created_at"):
                data[key] = value

        updated = BackupPolicy.from_dict(data)
        self._write_policy(updated)
        return updated

    def delete_policy(self, tenant_id: str, policy_id: str) -> bool:
        """Delete a policy.

        Returns:
            True if deleted, False if not found.
        """
        path = self._policy_path(tenant_id, policy_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def is_due(self, policy: BackupPolicy, now: datetime | None = None) -> bool:
        """Check if a policy is due to run.

        Args:
            policy: The policy to check.
            now: Current time (defaults to now).

        Returns:
            True if the policy should run.
        """
        if not policy.enabled or policy.status != PolicyStatus.ACTIVE:
            return False
        current = now or datetime.now(timezone.utc)
        if policy.next_run_at is None:
            return True
        return current >= policy.next_run_at

    def record_run(
        self,
        tenant_id: str,
        policy_id: str,
        *,
        success: bool,
        backup_id: str | None = None,
    ) -> BackupPolicy:
        """Record that a policy ran.

        Args:
            tenant_id: Tenant UUID string.
            policy_id: Policy UUID string.
            success: Whether the run succeeded.
            backup_id: ID of the backup created.

        Returns:
            The updated BackupPolicy.
        """
        policy = self._read_policy(tenant_id, policy_id)
        now = datetime.now(timezone.utc)
        data = policy.to_dict()
        data["last_run_at"] = now.isoformat()
        data["updated_at"] = now.isoformat()

        # Calculate next run
        next_run = self._calculate_next_run(policy.schedule, now)
        data["next_run_at"] = next_run.isoformat() if next_run else None

        updated = BackupPolicy.from_dict(data)
        self._write_policy(updated)
        return updated

    def get_due_policies(
        self,
        tenant_id: str,
        now: datetime | None = None,
    ) -> list[BackupPolicy]:
        """Get all policies that are due to run for a tenant."""
        policies = self.list_policies(tenant_id, enabled_only=True)
        return [p for p in policies if self.is_due(p, now)]

    def get_policy_stats(self, tenant_id: str) -> dict[str, Any]:
        """Get policy statistics for a tenant."""
        policies = self.list_policies(tenant_id)
        active = [p for p in policies if p.status == PolicyStatus.ACTIVE]
        enabled = [p for p in policies if p.enabled]
        due = [p for p in enabled if self.is_due(p)]

        return {
            "tenant_id": tenant_id,
            "total_policies": len(policies),
            "active_policies": len(active),
            "enabled_policies": len(enabled),
            "due_policies": len(due),
            "policies": [p.to_dict() for p in policies],
        }


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def create_policy(
    policy_root: str | Path,
    tenant_id: str,
    name: str,
    **kwargs: Any,
) -> BackupPolicy:
    """Convenience function: create a policy with a new engine."""
    engine = PolicyEngine(policy_root)
    return engine.create_policy(tenant_id, name, **kwargs)


def get_policy(
    policy_root: str | Path,
    tenant_id: str,
    policy_id: str,
) -> BackupPolicy:
    """Convenience function: get a policy with a new engine."""
    engine = PolicyEngine(policy_root)
    return engine.get_policy(tenant_id, policy_id)


def list_policies(
    policy_root: str | Path,
    tenant_id: str,
    **kwargs: Any,
) -> list[BackupPolicy]:
    """Convenience function: list policies with a new engine."""
    engine = PolicyEngine(policy_root)
    return engine.list_policies(tenant_id, **kwargs)


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "PolicyError",
    "PolicyNotFoundError",
    "PolicyValidationError",
    "BackupType",
    "Compression",
    "PolicyTrigger",
    "PolicyType",
    "PolicySchedule",
    "PolicyStatus",
    "BackupPolicy",
    "PolicyRunResult",
    "PolicyEngine",
    "ROW_COLUMNS",
    "SELECT_COLUMNS",
    "policy_from_row",
    "policy_to_row",
    "create_policy",
    "get_policy",
    "list_policies",
]
