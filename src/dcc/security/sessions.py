"""Secure session management for Data Center Commander.

Provides session lifecycle management with secure token generation,
refresh token rotation, revocation, and audit logging.

Security properties:
- Tokens are generated with ``secrets.token_urlsafe`` (CSPRNG).
- Only SHA-256 hashes of tokens are stored; raw tokens are never persisted.
- Access tokens have a short TTL; refresh tokens have a longer TTL.
- Refresh token rotation: each refresh issues a new pair and invalidates the old.
- All operations are thread-safe.
- Sessions are tenant-scoped and integrate with the audit logger.
"""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SessionError(Exception):
    """Base exception for session management errors."""


class SessionInvalidError(SessionError):
    """Raised when a session ID or token is malformed or not found."""


class SessionExpiredError(SessionError):
    """Raised when a session or token has exceeded its TTL."""


class SessionRevokedError(SessionError):
    """Raised when a session has been explicitly revoked."""


# ---------------------------------------------------------------------------
# Session status
# ---------------------------------------------------------------------------


class SessionStatus(str, Enum):
    """Lifecycle status of a session."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


# ---------------------------------------------------------------------------
# Token generation and hashing
# ---------------------------------------------------------------------------


def generate_token(length: int = 48) -> str:
    """Generate a cryptographically secure URL-safe token.

    Parameters
    ----------
    length:
        Number of random bytes before URL-safe encoding. The resulting
        string will be longer (ceil(length * 4 / 3) characters).
        Default 48 bytes → 64 characters.

    Returns
    -------
    str
        A URL-safe base64-encoded random token.
    """
    return secrets.token_urlsafe(length)


def generate_session_id() -> str:
    """Generate a unique session identifier.

    Returns
    -------
    str
        A UUID4 string.
    """
    return str(uuid4())


def hash_token(token: str) -> str:
    """Compute the SHA-256 hash of a token for storage.

    Parameters
    ----------
    token:
        The raw token string.

    Returns
    -------
    str
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Token pair
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenPair:
    """An access token and its associated refresh token.

    Attributes
    ----------
    access_token:
        Short-lived bearer token for API requests.
    refresh_token:
        Long-lived token used to obtain a new TokenPair.
    access_token_expires_at:
        Unix timestamp (seconds) when the access token expires.
    refresh_token_expires_at:
        Unix timestamp (seconds) when the refresh token expires.
    """

    access_token: str
    refresh_token: str
    access_token_expires_at: float
    refresh_token_expires_at: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary (for API responses)."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "access_token_expires_at": self.access_token_expires_at,
            "refresh_token_expires_at": self.refresh_token_expires_at,
            "token_type": "Bearer",
        }


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass
class Session:
    """A user session with metadata and lifecycle tracking.

    Attributes
    ----------
    session_id:
        Unique session identifier.
    tenant_id:
        The tenant this session belongs to.
    user_id:
        The user this session belongs to.
    status:
        Current lifecycle status.
    created_at:
        Unix timestamp when the session was created.
    last_activity_at:
        Unix timestamp of the last authenticated request.
    access_token_hash:
        SHA-256 hash of the current access token.
    refresh_token_hash:
        SHA-256 hash of the current refresh token.
    access_token_expires_at:
        Unix timestamp when the access token expires.
    refresh_token_expires_at:
        Unix timestamp when the refresh token expires.
    ip_address:
        Optional client IP address for audit.
    user_agent:
        Optional user agent string for audit.
    metadata:
        Arbitrary additional session metadata.
    """

    session_id: str
    tenant_id: str
    user_id: str
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)
    access_token_hash: str = ""
    refresh_token_hash: str = ""
    access_token_expires_at: float = 0.0
    refresh_token_expires_at: float = 0.0
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_access_token_valid(self, now: Optional[float] = None) -> bool:
        """Check if the access token is still valid (not expired and active)."""
        if self.status != SessionStatus.ACTIVE:
            return False
        current = now if now is not None else time.time()
        return current < self.access_token_expires_at

    def is_refresh_token_valid(self, now: Optional[float] = None) -> bool:
        """Check if the refresh token is still valid (not expired and active)."""
        if self.status != SessionStatus.ACTIVE:
            return False
        current = now if now is not None else time.time()
        return current < self.refresh_token_expires_at

    def touch(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity_at = time.time()

    def to_dict(self, include_tokens: bool = False) -> dict[str, Any]:
        """Serialize to a dictionary.

        Parameters
        ----------
        include_tokens:
            If True, include raw token values (only for immediate API responses,
            never for storage or logging).
        """
        result: dict[str, Any] = {
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_activity_at": self.last_activity_at,
            "access_token_expires_at": self.access_token_expires_at,
            "refresh_token_expires_at": self.refresh_token_expires_at,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "metadata": self.metadata,
        }
        if include_tokens:
            result["access_token"] = self.access_token_hash
            result["refresh_token"] = self.refresh_token_hash
        return result


# ---------------------------------------------------------------------------
# Audit event types for sessions
# ---------------------------------------------------------------------------


class SessionAuditAction:
    """Audit action strings for session lifecycle events."""

    CREATED = "session.created"
    REFRESHED = "session.refreshed"
    REVOKED = "session.revoked"
    EXPIRED = "session.expired"
    VALIDATED = "session.validated"
    REJECTED = "session.rejected"


# ---------------------------------------------------------------------------
# Session manager
# ---------------------------------------------------------------------------


class SessionManager:
    """Manages the full lifecycle of user sessions.

    This manager is thread-safe and stores sessions in memory. For
    production use, persist sessions to a database or Redis.

    Parameters
    ----------
    access_token_ttl:
        Access token time-to-live in seconds. Default 900 (15 minutes).
    refresh_token_ttl:
        Refresh token time-to-live in seconds. Default 604800 (7 days).
    max_sessions_per_user:
        Maximum concurrent active sessions per user. When exceeded, the
        oldest session is revoked. Default 5.
    audit_callback:
        Optional callable that receives (action: str, session: Session) for
        each lifecycle event. Used for audit logging.
    cleanup_interval:
        Seconds between automatic cleanup of expired sessions. Default 300.
    """

    def __init__(
        self,
        access_token_ttl: float = 900.0,
        refresh_token_ttl: float = 604800.0,
        max_sessions_per_user: int = 5,
        audit_callback: Optional[Callable[[str, Session], None]] = None,
        cleanup_interval: float = 300.0,
    ) -> None:
        self._access_token_ttl = access_token_ttl
        self._refresh_token_ttl = refresh_token_ttl
        self._max_sessions_per_user = max_sessions_per_user
        self._audit_callback = audit_callback
        self._cleanup_interval = cleanup_interval

        self._sessions: dict[str, Session] = {}
        self._access_token_index: dict[str, str] = {}  # token_hash -> session_id
        self._refresh_token_index: dict[str, str] = {}  # token_hash -> session_id
        self._user_sessions: dict[str, set[str]] = {}  # user_id -> set of session_ids
        self._lock = threading.RLock()
        self._last_cleanup = time.time()

    # -- Creation ---------------------------------------------------------

    def create_session(
        self,
        tenant_id: str,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[Session, TokenPair]:
        """Create a new session with a fresh token pair.

        Parameters
        ----------
        tenant_id:
            The tenant UUID this session belongs to.
        user_id:
            The user identifier.
        ip_address:
            Optional client IP for audit.
        user_agent:
            Optional user agent for audit.
        metadata:
            Optional additional metadata.

        Returns
        -------
        tuple[Session, TokenPair]
            The session and the token pair (raw tokens, never stored).

        Raises
        ------
        ValueError:
            If tenant_id or user_id is empty.
        """
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not user_id:
            raise ValueError("user_id is required")

        self._maybe_cleanup()

        now = time.time()
        access_token = generate_token()
        refresh_token = generate_token()
        access_expires = now + self._access_token_ttl
        refresh_expires = now + self._refresh_token_ttl

        session = Session(
            session_id=generate_session_id(),
            tenant_id=tenant_id,
            user_id=user_id,
            status=SessionStatus.ACTIVE,
            created_at=now,
            last_activity_at=now,
            access_token_hash=hash_token(access_token),
            refresh_token_hash=hash_token(refresh_token),
            access_token_expires_at=access_expires,
            refresh_token_expires_at=refresh_expires,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {},
        )

        token_pair = TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expires_at=access_expires,
            refresh_token_expires_at=refresh_expires,
        )

        with self._lock:
            self._sessions[session.session_id] = session
            self._access_token_index[session.access_token_hash] = session.session_id
            self._refresh_token_index[session.refresh_token_hash] = session.session_id
            self._user_sessions.setdefault(user_id, set()).add(session.session_id)
            self._enforce_session_limit(user_id)

        self._audit(SessionAuditAction.CREATED, session)
        return session, token_pair

    # -- Validation -------------------------------------------------------

    def validate_access_token(self, token: str) -> Session:
        """Validate an access token and return the associated session.

        Parameters
        ----------
        token:
            The raw access token from the client.

        Returns
        -------
        Session
            The valid session.

        Raises
        ------
        SessionInvalidError:
            If the token is not found.
        SessionExpiredError:
            If the access token has expired.
        SessionRevokedError:
            If the session has been revoked.
        """
        self._maybe_cleanup()

        token_hash = hash_token(token)
        with self._lock:
            session_id = self._access_token_index.get(token_hash)
            if session_id is None:
                raise SessionInvalidError("access token not found")
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionInvalidError("session not found")

            if session.status == SessionStatus.REVOKED:
                self._audit(SessionAuditAction.REJECTED, session)
                raise SessionRevokedError("session has been revoked")

            if session.status == SessionStatus.EXPIRED:
                self._audit(SessionAuditAction.REJECTED, session)
                raise SessionExpiredError("session has expired")

            now = time.time()
            if now >= session.access_token_expires_at:
                session.status = SessionStatus.EXPIRED
                self._audit(SessionAuditAction.EXPIRED, session)
                self._audit(SessionAuditAction.REJECTED, session)
                raise SessionExpiredError("access token has expired")

            session.touch()
            self._audit(SessionAuditAction.VALIDATED, session)
            return session

    # -- Refresh ----------------------------------------------------------

    def refresh_session(self, refresh_token: str) -> tuple[Session, TokenPair]:
        """Refresh a session using its refresh token.

        Implements refresh token rotation: the old refresh token is
        invalidated and a new token pair is issued.

        Parameters
        ----------
        refresh_token:
            The raw refresh token from the client.

        Returns
        -------
        tuple[Session, TokenPair]
            The updated session and the new token pair.

        Raises
        ------
        SessionInvalidError:
            If the refresh token is not found.
        SessionExpiredError:
            If the refresh token has expired.
        SessionRevokedError:
            If the session has been revoked.
        """
        self._maybe_cleanup()

        token_hash = hash_token(refresh_token)
        with self._lock:
            session_id = self._refresh_token_index.get(token_hash)
            if session_id is None:
                raise SessionInvalidError("refresh token not found")
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionInvalidError("session not found")

            if session.status == SessionStatus.REVOKED:
                self._audit(SessionAuditAction.REJECTED, session)
                raise SessionRevokedError("session has been revoked")

            if session.status == SessionStatus.EXPIRED:
                self._audit(SessionAuditAction.REJECTED, session)
                raise SessionExpiredError("session has expired")

            now = time.time()
            if now >= session.refresh_token_expires_at:
                session.status = SessionStatus.EXPIRED
                self._audit(SessionAuditAction.EXPIRED, session)
                self._audit(SessionAuditAction.REJECTED, session)
                raise SessionExpiredError("refresh token has expired")

            # Invalidate old tokens
            del self._access_token_index[session.access_token_hash]
            del self._refresh_token_index[session.refresh_token_hash]

            # Issue new tokens
            new_access = generate_token()
            new_refresh = generate_token()
            session.access_token_hash = hash_token(new_access)
            session.refresh_token_hash = hash_token(new_refresh)
            session.access_token_expires_at = now + self._access_token_ttl
            session.refresh_token_expires_at = now + self._refresh_token_ttl
            session.touch()

            self._access_token_index[session.access_token_hash] = session.session_id
            self._refresh_token_index[session.refresh_token_hash] = session.session_id

        token_pair = TokenPair(
            access_token=new_access,
            refresh_token=new_refresh,
            access_token_expires_at=session.access_token_expires_at,
            refresh_token_expires_at=session.refresh_token_expires_at,
        )

        self._audit(SessionAuditAction.REFRESHED, session)
        return session, token_pair

    # -- Revocation -------------------------------------------------------

    def revoke_session(self, session_id: str) -> Session:
        """Revoke a session immediately.

        Parameters
        ----------
        session_id:
            The session identifier to revoke.

        Returns
        -------
        Session
            The revoked session.

        Raises
        ------
        SessionInvalidError:
            If the session is not found.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionInvalidError("session not found")

            if session.status == SessionStatus.REVOKED:
                return session

            session.status = SessionStatus.REVOKED
            # Remove from token indexes to prevent further use
            self._access_token_index.pop(session.access_token_hash, None)
            self._refresh_token_index.pop(session.refresh_token_hash, None)

        self._audit(SessionAuditAction.REVOKED, session)
        return session

    def revoke_all_user_sessions(self, user_id: str) -> int:
        """Revoke all active sessions for a user.

        Parameters
        ----------
        user_id:
            The user whose sessions should be revoked.

        Returns
        -------
        int
            The number of sessions revoked.
        """
        with self._lock:
            session_ids = list(self._user_sessions.get(user_id, set()))
            count = 0
            for sid in session_ids:
                session = self._sessions.get(sid)
                if session and session.status == SessionStatus.ACTIVE:
                    session.status = SessionStatus.REVOKED
                    self._access_token_index.pop(session.access_token_hash, None)
                    self._refresh_token_index.pop(session.refresh_token_hash, None)
                    count += 1
            self._user_sessions.pop(user_id, None)

        # Audit outside the lock to avoid holding it during I/O
        for sid in session_ids:
            session = self._sessions.get(sid)
            if session:
                self._audit(SessionAuditAction.REVOKED, session)

        return count

    def revoke_all_tenant_sessions(self, tenant_id: str) -> int:
        """Revoke all active sessions for a tenant.

        Parameters
        ----------
        tenant_id:
            The tenant whose sessions should be revoked.

        Returns
        -------
        int
            The number of sessions revoked.
        """
        with self._lock:
            session_ids = [
                sid
                for sid, s in self._sessions.items()
                if s.tenant_id == tenant_id and s.status == SessionStatus.ACTIVE
            ]
            count = 0
            for sid in session_ids:
                session = self._sessions[sid]
                session.status = SessionStatus.REVOKED
                self._access_token_index.pop(session.access_token_hash, None)
                self._refresh_token_index.pop(session.refresh_token_hash, None)
                count += 1

        for sid in session_ids:
            session = self._sessions.get(sid)
            if session:
                self._audit(SessionAuditAction.REVOKED, session)

        return count

    # -- Lookup -----------------------------------------------------------

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID without validating tokens.

        Parameters
        ----------
        session_id:
            The session identifier.

        Returns
        -------
        Session or None
            The session if found, None otherwise.
        """
        with self._lock:
            return self._sessions.get(session_id)

    def list_user_sessions(self, user_id: str) -> list[Session]:
        """List all sessions for a user.

        Parameters
        ----------
        user_id:
            The user identifier.

        Returns
        -------
        list[Session]
            All sessions belonging to the user.
        """
        with self._lock:
            session_ids = list(self._user_sessions.get(user_id, set()))
            return [self._sessions[sid] for sid in session_ids if sid in self._sessions]

    def list_tenant_sessions(self, tenant_id: str) -> list[Session]:
        """List all sessions for a tenant.

        Parameters
        ----------
        tenant_id:
            The tenant identifier.

        Returns
        -------
        list[Session]
            All sessions belonging to the tenant.
        """
        with self._lock:
            return [
                s for s in self._sessions.values() if s.tenant_id == tenant_id
            ]

    # -- Cleanup ----------------------------------------------------------

    def cleanup_expired(self) -> int:
        """Remove expired and revoked sessions from memory.

        Returns
        -------
        int
            The number of sessions removed.
        """
        now = time.time()
        with self._lock:
            to_remove: list[str] = []
            for sid, session in self._sessions.items():
                if session.status == SessionStatus.REVOKED:
                    to_remove.append(sid)
                elif session.status == SessionStatus.ACTIVE:
                    if now >= session.refresh_token_expires_at:
                        session.status = SessionStatus.EXPIRED
                        to_remove.append(sid)

            for sid in to_remove:
                session = self._sessions.pop(sid, None)
                if session:
                    self._access_token_index.pop(session.access_token_hash, None)
                    self._refresh_token_index.pop(session.refresh_token_hash, None)
                    user_sessions = self._user_sessions.get(session.user_id)
                    if user_sessions:
                        user_sessions.discard(sid)
                        if not user_sessions:
                            self._user_sessions.pop(session.user_id, None)

            self._last_cleanup = now
            return len(to_remove)

    def _maybe_cleanup(self) -> None:
        """Run cleanup if the cleanup interval has elapsed."""
        now = time.time()
        if now - self._last_cleanup >= self._cleanup_interval:
            self.cleanup_expired()

    # -- Session limit ----------------------------------------------------

    def _enforce_session_limit(self, user_id: str) -> None:
        """Revoke oldest sessions if the user exceeds the limit.

        Must be called with ``self._lock`` held.
        """
        session_ids = self._user_sessions.get(user_id, set())
        if len(session_ids) <= self._max_sessions_per_user:
            return

        # Sort by creation time, oldest first
        sorted_sids = sorted(
            session_ids,
            key=lambda sid: self._sessions[sid].created_at,
        )
        to_revoke = sorted_sids[: len(sorted_sids) - self._max_sessions_per_user]
        for sid in to_revoke:
            session = self._sessions[sid]
            session.status = SessionStatus.REVOKED
            self._access_token_index.pop(session.access_token_hash, None)
            self._refresh_token_index.pop(session.refresh_token_hash, None)
            session_ids.discard(sid)

    # -- Audit ------------------------------------------------------------

    def _audit(self, action: str, session: Session) -> None:
        """Invoke the audit callback if configured."""
        if self._audit_callback:
            try:
                self._audit_callback(action, session)
            except Exception:
                # Audit failures must not break session operations
                pass

    # -- Stats ------------------------------------------------------------

    @property
    def session_count(self) -> int:
        """Total number of sessions in memory."""
        with self._lock:
            return len(self._sessions)

    @property
    def active_session_count(self) -> int:
        """Number of active sessions."""
        with self._lock:
            return sum(
                1 for s in self._sessions.values() if s.status == SessionStatus.ACTIVE
            )
