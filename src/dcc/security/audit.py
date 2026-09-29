"""Comprehensive audit logging for Data Center Commander.

Captures all data access, changes, admin actions, and security events
with tamper-evident hash chaining and tenant isolation.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import UUID, uuid4


class AuditCategory(str, Enum):
    """High-level category of the audited action."""
    DATA_ACCESS = "data_access"
    DATA_CHANGE = "data_change"
    ADMIN_ACTION = "admin_action"
    SECURITY = "security"
    API_REQUEST = "api_request"
    DATABASE = "database"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CONFIGURATION = "configuration"
    EXPORT = "export"
    CONNECTOR = "connector"
    SYSTEM = "system"


class AuditAction(str, Enum):
    """Specific action being audited."""
    # Data access
    READ = "read"
    LIST = "list"
    QUERY = "query"
    EXPORT = "export"
    DOWNLOAD = "download"
    SEARCH = "search"
    # Data changes
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    INSERT = "insert"
    UPSERT = "upsert"
    BULK_INSERT = "bulk_insert"
    BULK_UPDATE = "bulk_update"
    BULK_DELETE = "bulk_delete"
    # Admin actions
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_DISABLE = "user_disable"
    USER_ENABLE = "user_enable"
    ROLE_ASSIGN = "role_assign"
    ROLE_REVOKE = "role_revoke"
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    TENANT_CREATE = "tenant_create"
    TENANT_UPDATE = "tenant_update"
    TENANT_DELETE = "tenant_delete"
    TENANT_SUSPEND = "tenant_suspend"
    TENANT_ACTIVATE = "tenant_activate"
    SETTING_CHANGE = "setting_change"
    POLICY_CHANGE = "policy_change"
    # Security
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_ISSUE = "token_issue"
    TOKEN_REVOKE = "token_revoke"
    TOKEN_REFRESH = "token_refresh"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    MFA_SUCCESS = "mfa_success"
    MFA_FAILURE = "mfa_failure"
    SESSION_EXPIRE = "session_expire"
    RATE_LIMIT_HIT = "rate_limit_hit"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    # API
    API_CALL = "api_call"
    API_ERROR = "api_error"
    API_REJECTED = "api_rejected"
    # Database
    DB_QUERY = "db_query"
    DB_TRANSACTION = "db_transaction"
    DB_SCHEMA_CHANGE = "db_schema_change"
    DB_MIGRATION = "db_migration"
    # Connector
    CONNECTOR_RUN = "connector_run"
    CONNECTOR_ERROR = "connector_error"
    CONNECTOR_CONFIG_CHANGE = "connector_config_change"
    # System
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SYSTEM_CONFIG_CHANGE = "system_config_change"
    BACKUP_CREATE = "backup_create"
    BACKUP_RESTORE = "backup_restore"


class AuditSeverity(str, Enum):
    """Severity level of the audit event."""
    DEBUG = "debug"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    ALERT = "alert"
    EMERGENCY = "emergency"


@dataclass
class AuditEvent:
    """A single immutable audit event.

    Each event is hash-chained to the previous event in the same tenant
    to provide tamper evidence.
    """
    event_id: str
    tenant_id: str
    category: AuditCategory
    action: AuditAction
    severity: AuditSeverity
    actor_ref: str
    actor_type: str
    resource_type: str
    resource_id: str
    occurred_at: datetime
    duration_ms: float | None
    success: bool
    metadata: dict[str, Any]
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    session_id: str | None
    previous_hash: str
    event_hash: str
    details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "category": self.category.value,
            "action": self.action.value,
            "severity": self.severity.value,
            "actor_ref": self.actor_ref,
            "actor_type": self.actor_type,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "occurred_at": self.occurred_at.isoformat(),
            "duration_ms": self.duration_ms,
            "success": self.success,
            "metadata": self.metadata,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "previous_hash": self.previous_hash,
            "event_hash": self.event_hash,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEvent:
        """Reconstruct from dictionary."""
        return cls(
            event_id=data["event_id"],
            tenant_id=data["tenant_id"],
            category=AuditCategory(data["category"]),
            action=AuditAction(data["action"]),
            severity=AuditSeverity(data["severity"]),
            actor_ref=data["actor_ref"],
            actor_type=data["actor_type"],
            resource_type=data["resource_type"],
            resource_id=data["resource_id"],
            occurred_at=datetime.fromisoformat(data["occurred_at"]),
            duration_ms=data.get("duration_ms"),
            success=data["success"],
            metadata=data.get("metadata", {}),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
            request_id=data.get("request_id"),
            session_id=data.get("session_id"),
            previous_hash=data["previous_hash"],
            event_hash=data["event_hash"],
            details=data.get("details"),
        )


class AuditStorage(Protocol):
    """Protocol for audit storage backends."""

    def append(self, event: AuditEvent) -> None:
        """Store a single audit event."""
        ...

    def query(
        self,
        *,
        tenant_id: str | None = None,
        category: AuditCategory | None = None,
        action: AuditAction | None = None,
        severity: AuditSeverity | None = None,
        actor_ref: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        success: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """Query audit events with filters."""
        ...

    def count(
        self,
        *,
        tenant_id: str | None = None,
        category: AuditCategory | None = None,
        action: AuditAction | None = None,
        severity: AuditSeverity | None = None,
        actor_ref: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        success: bool | None = None,
    ) -> int:
        """Count audit events matching filters."""
        ...

    def get_chain_head(self, tenant_id: str) -> str | None:
        """Get the hash of the most recent event for a tenant."""
        ...

    def verify_chain(self, tenant_id: str) -> dict[str, Any]:
        """Verify hash-chain integrity for a tenant."""
        ...


class InMemoryAuditStorage:
    """In-memory audit storage with hash-chain verification.

    Suitable for testing and development. Not persistent.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._tenant_chains: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.append(event)
            chain = self._tenant_chains.setdefault(event.tenant_id, [])
            chain.append(event.event_hash)

    def query(
        self,
        *,
        tenant_id: str | None = None,
        category: AuditCategory | None = None,
        action: AuditAction | None = None,
        severity: AuditSeverity | None = None,
        actor_ref: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        success: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        with self._lock:
            filtered = self._events
            if tenant_id is not None:
                filtered = [e for e in filtered if e.tenant_id == tenant_id]
            if category is not None:
                filtered = [e for e in filtered if e.category == category]
            if action is not None:
                filtered = [e for e in filtered if e.action == action]
            if severity is not None:
                filtered = [e for e in filtered if e.severity == severity]
            if actor_ref is not None:
                filtered = [e for e in filtered if e.actor_ref == actor_ref]
            if resource_type is not None:
                filtered = [e for e in filtered if e.resource_type == resource_type]
            if resource_id is not None:
                filtered = [e for e in filtered if e.resource_id == resource_id]
            if start_time is not None:
                filtered = [e for e in filtered if e.occurred_at >= start_time]
            if end_time is not None:
                filtered = [e for e in filtered if e.occurred_at <= end_time]
            if success is not None:
                filtered = [e for e in filtered if e.success == success]
            return filtered[offset : offset + limit]

    def count(
        self,
        *,
        tenant_id: str | None = None,
        category: AuditCategory | None = None,
        action: AuditAction | None = None,
        severity: AuditSeverity | None = None,
        actor_ref: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        success: bool | None = None,
    ) -> int:
        with self._lock:
            filtered = self._events
            if tenant_id is not None:
                filtered = [e for e in filtered if e.tenant_id == tenant_id]
            if category is not None:
                filtered = [e for e in filtered if e.category == category]
            if action is not None:
                filtered = [e for e in filtered if e.action == action]
            if severity is not None:
                filtered = [e for e in filtered if e.severity == severity]
            if actor_ref is not None:
                filtered = [e for e in filtered if e.actor_ref == actor_ref]
            if resource_type is not None:
                filtered = [e for e in filtered if e.resource_type == resource_type]
            if resource_id is not None:
                filtered = [e for e in filtered if e.resource_id == resource_id]
            if start_time is not None:
                filtered = [e for e in filtered if e.occurred_at >= start_time]
            if end_time is not None:
                filtered = [e for e in filtered if e.occurred_at <= end_time]
            if success is not None:
                filtered = [e for e in filtered if e.success == success]
            return len(filtered)

    def get_chain_head(self, tenant_id: str) -> str | None:
        with self._lock:
            chain = self._tenant_chains.get(tenant_id, [])
            return chain[-1] if chain else None

    def verify_chain(self, tenant_id: str) -> dict[str, Any]:
        with self._lock:
            events = sorted(
                [e for e in self._events if e.tenant_id == tenant_id],
                key=lambda e: e.occurred_at,
            )
            if not events:
                return {"tenant_id": tenant_id, "valid": True, "events_checked": 0, "broken_at": None}

            previous_hash = ""
            for i, event in enumerate(events):
                expected_hash = _compute_event_hash(event)
                if event.event_hash != expected_hash:
                    return {
                        "tenant_id": tenant_id,
                        "valid": False,
                        "events_checked": i,
                        "broken_at": event.event_id,
                        "reason": "event_hash_mismatch",
                    }
                if event.previous_hash != previous_hash:
                    return {
                        "tenant_id": tenant_id,
                        "valid": False,
                        "events_checked": i,
                        "broken_at": event.event_id,
                        "reason": "chain_link_mismatch",
                    }
                previous_hash = event.event_hash

            return {
                "tenant_id": tenant_id,
                "valid": True,
                "events_checked": len(events),
                "broken_at": None,
            }


class FileAuditStorage:
    """File-based audit storage with append-only JSONL format.

    Each tenant gets its own file. Events are hash-chained.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._tenant_chains: dict[str, str] = {}
        self._load_chain_heads()

    def _load_chain_heads(self) -> None:
        """Load the last hash for each tenant from existing files."""
        for f in self._base_dir.glob("*.jsonl"):
            tenant_id = f.stem
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    lines = fh.readlines()
                    if lines:
                        last = json.loads(lines[-1])
                        self._tenant_chains[tenant_id] = last["event_hash"]
            except (json.JSONDecodeError, KeyError):
                continue

    def _tenant_file(self, tenant_id: str) -> Path:
        return self._base_dir / f"{tenant_id}.jsonl"

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            f = self._tenant_file(event.tenant_id)
            with open(f, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.to_dict(), default=str) + "\n")
            self._tenant_chains[event.tenant_id] = event.event_hash

    def query(
        self,
        *,
        tenant_id: str | None = None,
        category: AuditCategory | None = None,
        action: AuditAction | None = None,
        severity: AuditSeverity | None = None,
        actor_ref: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        success: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        with self._lock:
            files = [self._tenant_file(tenant_id)] if tenant_id else list(self._base_dir.glob("*.jsonl"))
            results: list[AuditEvent] = []
            for f in files:
                if not f.exists():
                    continue
                with open(f, "r", encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            data = json.loads(line)
                            event = AuditEvent.from_dict(data)
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
                        if category is not None and event.category != category:
                            continue
                        if action is not None and event.action != action:
                            continue
                        if severity is not None and event.severity != severity:
                            continue
                        if actor_ref is not None and event.actor_ref != actor_ref:
                            continue
                        if resource_type is not None and event.resource_type != resource_type:
                            continue
                        if resource_id is not None and event.resource_id != resource_id:
                            continue
                        if start_time is not None and event.occurred_at < start_time:
                            continue
                        if end_time is not None and event.occurred_at > end_time:
                            continue
                        if success is not None and event.success != success:
                            continue
                        results.append(event)
            results.sort(key=lambda e: e.occurred_at, reverse=True)
            return results[offset : offset + limit]

    def count(
        self,
        *,
        tenant_id: str | None = None,
        category: AuditCategory | None = None,
        action: AuditAction | None = None,
        severity: AuditSeverity | None = None,
        actor_ref: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        success: bool | None = None,
    ) -> int:
        with self._lock:
            files = [self._tenant_file(tenant_id)] if tenant_id else list(self._base_dir.glob("*.jsonl"))
            count = 0
            for f in files:
                if not f.exists():
                    continue
                with open(f, "r", encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            data = json.loads(line)
                            event = AuditEvent.from_dict(data)
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
                        if category is not None and event.category != category:
                            continue
                        if action is not None and event.action != action:
                            continue
                        if severity is not None and event.severity != severity:
                            continue
                        if actor_ref is not None and event.actor_ref != actor_ref:
                            continue
                        if resource_type is not None and event.resource_type != resource_type:
                            continue
                        if resource_id is not None and event.resource_id != resource_id:
                            continue
                        if start_time is not None and event.occurred_at < start_time:
                            continue
                        if end_time is not None and event.occurred_at > end_time:
                            continue
                        if success is not None and event.success != success:
                            continue
                        count += 1
            return count

    def get_chain_head(self, tenant_id: str) -> str | None:
        with self._lock:
            return self._tenant_chains.get(tenant_id)

    def verify_chain(self, tenant_id: str) -> dict[str, Any]:
        with self._lock:
            f = self._tenant_file(tenant_id)
            if not f.exists():
                return {"tenant_id": tenant_id, "valid": True, "events_checked": 0, "broken_at": None}
            events: list[AuditEvent] = []
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        events.append(AuditEvent.from_dict(json.loads(line)))
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
            if not events:
                return {"tenant_id": tenant_id, "valid": True, "events_checked": 0, "broken_at": None}
            events.sort(key=lambda e: e.occurred_at)
            previous_hash = ""
            for i, event in enumerate(events):
                expected_hash = _compute_event_hash(event)
                if event.event_hash != expected_hash:
                    return {
                        "tenant_id": tenant_id,
                        "valid": False,
                        "events_checked": i,
                        "broken_at": event.event_id,
                        "reason": "event_hash_mismatch",
                    }
                if event.previous_hash != previous_hash:
                    return {
                        "tenant_id": tenant_id,
                        "valid": False,
                        "events_checked": i,
                        "broken_at": event.event_id,
                        "reason": "chain_link_mismatch",
                    }
                previous_hash = event.event_hash
            return {
                "tenant_id": tenant_id,
                "valid": True,
                "events_checked": len(events),
                "broken_at": None,
            }


class AuditLogger:
    """Main audit logging interface.

    Provides a fluent API for recording audit events with automatic
    hash chaining, tenant isolation, and severity-based filtering.
    """

    def __init__(
        self,
        storage: AuditStorage,
        *,
        min_severity: AuditSeverity = AuditSeverity.DEBUG,
        default_actor: str = "system",
        default_actor_type: str = "system",
    ) -> None:
        self._storage = storage
        self._min_severity = min_severity
        self._default_actor = default_actor
        self._default_actor_type = default_actor_type
        self._context: dict[str, Any] = {}
        self._lock = threading.Lock()

    def with_context(self, **kwargs: Any) -> AuditLogger:
        """Return a logger with additional context fields."""
        new_logger = AuditLogger(
            self._storage,
            min_severity=self._min_severity,
            default_actor=self._default_actor,
            default_actor_type=self._default_actor_type,
        )
        new_logger._context = {**self._context, **kwargs}
        return new_logger

    def with_tenant(self, tenant_id: str) -> AuditLogger:
        """Return a logger scoped to a specific tenant."""
        return self.with_context(tenant_id=tenant_id)

    def with_actor(self, actor_ref: str, actor_type: str = "user") -> AuditLogger:
        """Return a logger with a specific actor."""
        return self.with_context(_actor_ref=actor_ref, _actor_type=actor_type)

    def with_request(self, request_id: str, session_id: str | None = None) -> AuditLogger:
        """Return a logger with request context."""
        return self.with_context(_request_id=request_id, _session_id=session_id)

    def log(
        self,
        *,
        category: AuditCategory,
        action: AuditAction,
        severity: AuditSeverity = AuditSeverity.INFO,
        tenant_id: str,
        resource_type: str,
        resource_id: str = "",
        actor_ref: str | None = None,
        actor_type: str | None = None,
        success: bool = True,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        session_id: str | None = None,
        details: str | None = None,
    ) -> AuditEvent | None:
        """Log a single audit event.

        Returns the event if it was recorded, None if filtered by severity.
        """
        if severity.value < self._min_severity.value:
            return None

        ctx = self._context
        event = AuditEvent(
            event_id=str(uuid4()),
            tenant_id=tenant_id,
            category=category,
            action=action,
            severity=severity,
            actor_ref=actor_ref or ctx.get("_actor_ref", self._default_actor),
            actor_type=actor_type or ctx.get("_actor_type", self._default_actor_type),
            resource_type=resource_type,
            resource_id=resource_id,
            occurred_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            success=success,
            metadata={**ctx, **(metadata or {})},
            ip_address=ip_address or ctx.get("ip_address"),
            user_agent=user_agent or ctx.get("user_agent"),
            request_id=request_id or ctx.get("_request_id"),
            session_id=session_id or ctx.get("_session_id"),
            previous_hash="",
            event_hash="",
            details=details,
        )

        with self._lock:
            head = self._storage.get_chain_head(tenant_id)
            event.previous_hash = head or ""
            event.event_hash = _compute_event_hash(event)
            self._storage.append(event)

        return event

    # Convenience methods for common audit patterns

    def _ctx_tenant(self) -> str:
        """Get tenant_id from context or raise."""
        tenant_id = self._context.get("tenant_id")
        if tenant_id is None:
            raise ValueError("tenant_id is required (use with_tenant() or pass tenant_id=...)")
        return str(tenant_id)

    def data_access(
        self,
        *,
        tenant_id: str | None = None,
        resource_type: str,
        resource_id: str = "",
        action: AuditAction = AuditAction.READ,
        actor_ref: str | None = None,
        success: bool = True,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AuditEvent | None:
        """Log a data access event."""
        return self.log(
            category=AuditCategory.DATA_ACCESS,
            action=action,
            severity=AuditSeverity.INFO,
            tenant_id=tenant_id or self._ctx_tenant(),
            resource_type=resource_type,
            resource_id=resource_id,
            actor_ref=actor_ref,
            success=success,
            duration_ms=duration_ms,
            metadata=metadata,
            **kwargs,
        )

    def data_change(
        self,
        *,
        tenant_id: str | None = None,
        resource_type: str,
        resource_id: str,
        action: AuditAction,
        actor_ref: str | None = None,
        success: bool = True,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AuditEvent | None:
        """Log a data change event."""
        return self.log(
            category=AuditCategory.DATA_CHANGE,
            action=action,
            severity=AuditSeverity.NOTICE,
            tenant_id=tenant_id or self._ctx_tenant(),
            resource_type=resource_type,
            resource_id=resource_id,
            actor_ref=actor_ref,
            success=success,
            duration_ms=duration_ms,
            metadata=metadata,
            **kwargs,
        )

    def admin_action(
        self,
        *,
        tenant_id: str | None = None,
        action: AuditAction,
        resource_type: str,
        resource_id: str = "",
        actor_ref: str | None = None,
        success: bool = True,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AuditEvent | None:
        """Log an admin action event."""
        return self.log(
            category=AuditCategory.ADMIN_ACTION,
            action=action,
            severity=AuditSeverity.WARNING,
            tenant_id=tenant_id or self._ctx_tenant(),
            resource_type=resource_type,
            resource_id=resource_id,
            actor_ref=actor_ref,
            success=success,
            duration_ms=duration_ms,
            metadata=metadata,
            **kwargs,
        )

    def security_event(
        self,
        *,
        tenant_id: str | None = None,
        action: AuditAction,
        resource_type: str = "security",
        resource_id: str = "",
        severity: AuditSeverity = AuditSeverity.WARNING,
        actor_ref: str | None = None,
        success: bool = True,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AuditEvent | None:
        """Log a security event."""
        return self.log(
            category=AuditCategory.SECURITY,
            action=action,
            severity=severity,
            tenant_id=tenant_id or self._ctx_tenant(),
            resource_type=resource_type,
            resource_id=resource_id,
            actor_ref=actor_ref,
            success=success,
            duration_ms=duration_ms,
            metadata=metadata,
            **kwargs,
        )

    def api_request(
        self,
        *,
        tenant_id: str | None = None,
        resource_type: str,
        resource_id: str = "",
        method: str = "GET",
        path: str = "",
        status_code: int = 200,
        actor_ref: str | None = None,
        duration_ms: float | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AuditEvent | None:
        """Log an API request event."""
        success = 200 <= status_code < 400
        severity = AuditSeverity.INFO if success else AuditSeverity.WARNING
        if status_code >= 500:
            severity = AuditSeverity.ERROR
        meta = {"method": method, "path": path, "status_code": status_code, **(metadata or {})}
        return self.log(
            category=AuditCategory.API_REQUEST,
            action=AuditAction.API_CALL,
            severity=severity,
            tenant_id=tenant_id or self._ctx_tenant(),
            resource_type=resource_type,
            resource_id=resource_id,
            actor_ref=actor_ref,
            success=success,
            duration_ms=duration_ms,
            metadata=meta,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            session_id=session_id,
            **kwargs,
        )

    def db_query(
        self,
        *,
        tenant_id: str | None = None,
        query_type: str,
        table: str,
        duration_ms: float | None = None,
        success: bool = True,
        row_count: int | None = None,
        actor_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AuditEvent | None:
        """Log a database query event."""
        meta = {"query_type": query_type, "table": table, "row_count": row_count, **(metadata or {})}
        return self.log(
            category=AuditCategory.DATABASE,
            action=AuditAction.DB_QUERY,
            severity=AuditSeverity.DEBUG,
            tenant_id=tenant_id or self._ctx_tenant(),
            resource_type="database",
            resource_id=table,
            actor_ref=actor_ref,
            success=success,
            duration_ms=duration_ms,
            metadata=meta,
            **kwargs,
        )

    def connector_run(
        self,
        *,
        tenant_id: str | None = None,
        connector_id: str,
        connector_name: str,
        outcome: str,
        records_read: int = 0,
        records_rejected: int = 0,
        duration_ms: float | None = None,
        error_code: str | None = None,
        actor_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AuditEvent | None:
        """Log a connector run event."""
        success = outcome in ("healthy", "partial")
        severity = AuditSeverity.INFO if success else AuditSeverity.ERROR
        meta = {
            "connector_name": connector_name,
            "outcome": outcome,
            "records_read": records_read,
            "records_rejected": records_rejected,
            "error_code": error_code,
            **(metadata or {}),
        }
        return self.log(
            category=AuditCategory.CONNECTOR,
            action=AuditAction.CONNECTOR_RUN,
            severity=severity,
            tenant_id=tenant_id or self._ctx_tenant(),
            resource_type="connector",
            resource_id=connector_id,
            actor_ref=actor_ref,
            success=success,
            duration_ms=duration_ms,
            metadata=meta,
            **kwargs,
        )

    def export(
        self,
        *,
        tenant_id: str | None = None,
        resource_type: str,
        resource_id: str = "",
        format: str = "json",
        record_count: int = 0,
        actor_ref: str | None = None,
        success: bool = True,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AuditEvent | None:
        """Log an export event."""
        meta = {"format": format, "record_count": record_count, **(metadata or {})}
        return self.log(
            category=AuditCategory.EXPORT,
            action=AuditAction.EXPORT,
            severity=AuditSeverity.NOTICE,
            tenant_id=tenant_id or self._ctx_tenant(),
            resource_type=resource_type,
            resource_id=resource_id,
            actor_ref=actor_ref,
            success=success,
            duration_ms=duration_ms,
            metadata=meta,
            **kwargs,
        )

    def query(
        self,
        *,
        tenant_id: str | None = None,
        category: AuditCategory | None = None,
        action: AuditAction | None = None,
        severity: AuditSeverity | None = None,
        actor_ref: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        success: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """Query audit events."""
        return self._storage.query(
            tenant_id=tenant_id,
            category=category,
            action=action,
            severity=severity,
            actor_ref=actor_ref,
            resource_type=resource_type,
            resource_id=resource_id,
            start_time=start_time,
            end_time=end_time,
            success=success,
            limit=limit,
            offset=offset,
        )

    def count(
        self,
        *,
        tenant_id: str | None = None,
        category: AuditCategory | None = None,
        action: AuditAction | None = None,
        severity: AuditSeverity | None = None,
        actor_ref: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        success: bool | None = None,
    ) -> int:
        """Count audit events."""
        return self._storage.count(
            tenant_id=tenant_id,
            category=category,
            action=action,
            severity=severity,
            actor_ref=actor_ref,
            resource_type=resource_type,
            resource_id=resource_id,
            start_time=start_time,
            end_time=end_time,
            success=success,
        )

    def verify_chain(self, tenant_id: str) -> dict[str, Any]:
        """Verify hash-chain integrity for a tenant."""
        return self._storage.verify_chain(tenant_id)


def _compute_event_hash(event: AuditEvent) -> str:
    """Compute the tamper-evident hash for an audit event.

    The hash covers all fields except event_hash itself and is chained
    to the previous event's hash.
    """
    payload = json.dumps(
        {
            "event_id": event.event_id,
            "tenant_id": event.tenant_id,
            "category": event.category.value,
            "action": event.action.value,
            "severity": event.severity.value,
            "actor_ref": event.actor_ref,
            "actor_type": event.actor_type,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "occurred_at": event.occurred_at.isoformat(),
            "duration_ms": event.duration_ms,
            "success": event.success,
            "metadata": event.metadata,
            "ip_address": event.ip_address,
            "user_agent": event.user_agent,
            "request_id": event.request_id,
            "session_id": event.session_id,
            "previous_hash": event.previous_hash,
            "details": event.details,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# Module-level singleton for convenience
_default_logger: AuditLogger | None = None
_default_lock = threading.Lock()


def get_audit_logger(
    storage: AuditStorage | None = None,
    *,
    min_severity: AuditSeverity = AuditSeverity.DEBUG,
) -> AuditLogger:
    """Get or create the default audit logger singleton."""
    global _default_logger
    with _default_lock:
        if _default_logger is None:
            if storage is None:
                storage = InMemoryAuditStorage()
            _default_logger = AuditLogger(storage, min_severity=min_severity)
        return _default_logger


def set_audit_logger(logger: AuditLogger) -> None:
    """Set the default audit logger singleton."""
    global _default_logger
    with _default_lock:
        _default_logger = logger


def reset_audit_logger() -> None:
    """Reset the default audit logger singleton."""
    global _default_logger
    with _default_lock:
        _default_logger = None
