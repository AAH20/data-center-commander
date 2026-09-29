"""API key generation, hashing, and verification.

API keys are opaque bearer tokens. The raw key is shown once at creation;
only a SHA-256 hash is stored. Verification uses constant-time comparison.

Format: ``dcc_<random>`` — the prefix makes keys identifiable in logs
without revealing the secret portion.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "ApiKey",
    "ApiKeyError",
    "ApiKeyStore",
    "generate_api_key",
    "hash_api_key",
    "verify_api_key",
]


class ApiKeyError(Exception):
    """Base exception for API key operations."""


class ApiKeyInvalidError(ApiKeyError):
    """Raised when an API key is malformed or has a bad hash."""


class ApiKeyExpiredError(ApiKeyError):
    """Raised when an API key has expired."""


class ApiKeyRevokedError(ApiKeyError):
    """Raised when an API key has been revoked."""


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

_KEY_PREFIX = "dcc"
_KEY_ENTROPY_BYTES = 32  # 256 bits


def generate_api_key() -> str:
    """Generate a new API key.

    Returns
    -------
    str
        A key in the format ``dcc_<64 hex chars>``.
    """
    random_part = secrets.token_hex(_KEY_ENTROPY_BYTES)
    return f"{_KEY_PREFIX}_{random_part}"


# ---------------------------------------------------------------------------
# Key hashing
# ---------------------------------------------------------------------------


def hash_api_key(key: str) -> str:
    """Compute the SHA-256 hash of an API key for storage.

    Parameters
    ----------
    key:
        The raw API key string.

    Returns
    -------
    str
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Key verification
# ---------------------------------------------------------------------------


def verify_api_key(key: str, key_hash: str) -> bool:
    """Verify an API key against its stored hash using constant-time comparison.

    Parameters
    ----------
    key:
        The raw API key to verify.
    key_hash:
        The stored SHA-256 hash.

    Returns
    -------
    bool
        True if the key matches the hash.
    """
    computed = hash_api_key(key)
    return hmac.compare_digest(computed, key_hash)


# ---------------------------------------------------------------------------
# ApiKey dataclass
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ApiKey:
    """Metadata for a stored API key.

    The raw key is never stored — only its hash.
    """

    id: str
    name: str
    key_hash: str
    tenant_id: str
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    last_used_at: float | None = None
    scopes: list[str] = field(default_factory=list)
    revoked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at

    @property
    def is_active(self) -> bool:
        return not self.revoked and not self.is_expired

    def to_dict(self, *, include_hash: bool = False) -> dict[str, Any]:
        """Serialize to dict. Never includes the raw key."""
        result: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_used_at": self.last_used_at,
            "scopes": list(self.scopes),
            "revoked": self.revoked,
            "metadata": dict(self.metadata),
        }
        if include_hash:
            result["key_hash"] = self.key_hash
        return result


# ---------------------------------------------------------------------------
# In-memory API key store
# ---------------------------------------------------------------------------


class ApiKeyStore:
    """Thread-safe in-memory store for API key metadata.

    This is suitable for single-process deployments. For multi-process or
    persistent storage, subclass and override the CRUD methods to use a
    database backend.
    """

    def __init__(self) -> None:
        self._keys: dict[str, ApiKey] = {}  # id -> ApiKey
        self._hash_to_id: dict[str, str] = {}  # key_hash -> id
        self._lock = __import__("threading").RLock()

    def create(
        self,
        *,
        name: str,
        tenant_id: str,
        scopes: list[str] | None = None,
        expires_at: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, ApiKey]:
        """Create a new API key.

        Returns
        -------
        tuple[str, ApiKey]
            The raw key (show once) and the stored metadata.
        """
        raw_key = generate_api_key()
        key_hash = hash_api_key(raw_key)
        key_id = secrets.token_hex(8)

        api_key = ApiKey(
            id=key_id,
            name=name,
            key_hash=key_hash,
            tenant_id=tenant_id,
            expires_at=expires_at,
            scopes=scopes or [],
            metadata=metadata or {},
        )

        with self._lock:
            self._keys[key_id] = api_key
            self._hash_to_id[key_hash] = key_id

        return raw_key, api_key

    def verify(self, raw_key: str) -> ApiKey:
        """Verify a raw API key and return its metadata.

        Raises
        ------
        ApiKeyInvalidError
            If the key is not found or the hash doesn't match.
        ApiKeyExpiredError
            If the key has expired.
        ApiKeyRevokedError
            If the key has been revoked.
        """
        key_hash = hash_api_key(raw_key)

        with self._lock:
            key_id = self._hash_to_id.get(key_hash)
            if key_id is None:
                raise ApiKeyInvalidError("unknown API key")
            api_key = self._keys.get(key_id)
            if api_key is None:
                raise ApiKeyInvalidError("unknown API key")

            # Double-check hash (defense in depth)
            if not verify_api_key(raw_key, api_key.key_hash):
                raise ApiKeyInvalidError("API key hash mismatch")

            if api_key.revoked:
                raise ApiKeyRevokedError("API key has been revoked")
            if api_key.is_expired:
                raise ApiKeyExpiredError("API key has expired")

            # Update last-used timestamp
            api_key.last_used_at = time.time()
            return api_key

    def get(self, key_id: str) -> ApiKey | None:
        """Look up an API key by ID."""
        with self._lock:
            return self._keys.get(key_id)

    def list_keys(self, tenant_id: str | None = None) -> list[ApiKey]:
        """List API keys, optionally filtered by tenant."""
        with self._lock:
            keys = list(self._keys.values())
        if tenant_id is not None:
            keys = [k for k in keys if k.tenant_id == tenant_id]
        return keys

    def revoke(self, key_id: str) -> bool:
        """Revoke an API key. Returns True if it existed."""
        with self._lock:
            api_key = self._keys.get(key_id)
            if api_key is None:
                return False
            api_key.revoked = True
            return True

    def delete(self, key_id: str) -> bool:
        """Permanently delete an API key. Returns True if it existed."""
        with self._lock:
            api_key = self._keys.pop(key_id, None)
            if api_key is None:
                return False
            self._hash_to_id.pop(api_key.key_hash, None)
            return True

    def cleanup_expired(self) -> int:
        """Remove all expired keys. Returns the count removed."""
        with self._lock:
            expired = [
                kid for kid, k in self._keys.items()
                if k.is_expired
            ]
            for kid in expired:
                key = self._keys.pop(kid)
                self._hash_to_id.pop(key.key_hash, None)
            return len(expired)
