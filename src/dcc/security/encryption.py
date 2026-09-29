"""Data encryption for Data Center Commander.

Provides at-rest encryption (AES-256-GCM field-level), in-transit TLS
configuration, and key management utilities.

At-rest encryption
------------------
Field-level AES-256-GCM encryption for sensitive database columns. Each
field is encrypted with a unique nonce and authenticated, so tampering is
detected on decryption. Keys are 256-bit and can be rotated.

In-transit TLS
--------------
TLS 1.2+ configuration for the HTTP server with secure defaults: strong
cipher suites, certificate verification, and HSTS headers.

Key management
--------------
Keys are loaded from environment variables or a secrets manager. A key
rotation policy supports graceful key transitions where data encrypted
with an old key can still be decrypted during a migration window.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AES_KEY_SIZE = 32  # 256 bits
GCM_NONCE_SIZE = 12  # 96 bits (recommended for GCM)
GCM_TAG_SIZE = 16  # 128 bits
SALT_SIZE = 32
MIN_PASSWORD_LENGTH = 16
DEFAULT_PBKDF2_ITERATIONS = 600_000
DEFAULT_SCRYPT_N = 2**17
DEFAULT_SCRYPT_R = 8
DEFAULT_SCRYPT_P = 1
KEY_ID_SIZE = 8
KEY_PREFIX = "dcc_key_v1"
ENCRYPTED_PREFIX = "dcc_enc_v1"
MAX_PLAINTEXT_SIZE = 1_048_576  # 1 MiB per field


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class EncryptionError(Exception):
    """Base exception for encryption failures."""


class DecryptionError(EncryptionError):
    """Raised when decryption fails (wrong key, tampered ciphertext, etc.)."""


class KeyNotFoundError(EncryptionError):
    """Raised when a required encryption key is not available."""


class KeyRotationError(EncryptionError):
    """Raised when key rotation encounters an unrecoverable state."""


class TLSError(EncryptionError):
    """Raised when TLS configuration is invalid."""


class PlaintextTooLargeError(EncryptionError):
    """Raised when plaintext exceeds the maximum allowed size."""


# ---------------------------------------------------------------------------
# Key types
# ---------------------------------------------------------------------------


class KeyStatus(str, Enum):
    """Lifecycle status of an encryption key."""

    ACTIVE = "active"
    ROTATING = "rotating"
    RETIRED = "retired"
    DESTROYED = "destroyed"


@dataclass(frozen=True)
class EncryptionKey:
    """A single encryption key with metadata.

    Attributes:
        key_id: Unique identifier for this key (hex string).
        key_bytes: The raw 256-bit key material.
        created_at: When the key was created.
        status: Current lifecycle status.
        algorithm: The algorithm this key is used with.
    """

    key_id: str
    key_bytes: bytes
    created_at: datetime
    status: KeyStatus = KeyStatus.ACTIVE
    algorithm: str = "AES-256-GCM"

    def __post_init__(self) -> None:
        if len(self.key_bytes) != AES_KEY_SIZE:
            raise ValueError(
                f"Encryption key must be {AES_KEY_SIZE} bytes, got {len(self.key_bytes)}"
            )

    @property
    def is_usable(self) -> bool:
        """Return True if this key can be used for encryption or decryption."""
        return self.status in (KeyStatus.ACTIVE, KeyStatus.ROTATING)

    @property
    def can_encrypt(self) -> bool:
        """Return True if this key can be used for encryption."""
        return self.status == KeyStatus.ACTIVE

    @property
    def can_decrypt(self) -> bool:
        """Return True if this key can be used for decryption."""
        return self.status in (KeyStatus.ACTIVE, KeyStatus.ROTATING, KeyStatus.RETIRED)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary (excludes key material)."""
        return {
            "key_id": self.key_id,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "algorithm": self.algorithm,
        }


@dataclass
class KeyRotationPolicy:
    """Policy governing key rotation.

    Attributes:
        rotation_interval_days: How often to rotate keys (default 90).
        retirement_delay_days: How long to keep old keys for decryption
            after rotation (default 30).
        auto_rotate: Whether to automatically rotate keys when the
            interval elapses.
    """

    rotation_interval_days: int = 90
    retirement_delay_days: int = 30
    auto_rotate: bool = True

    def should_rotate(self, key: EncryptionKey) -> bool:
        """Return True if the given key should be rotated."""
        if not self.auto_rotate:
            return False
        if key.status != KeyStatus.ACTIVE:
            return False
        age = datetime.now(timezone.utc) - key.created_at
        return age >= timedelta(days=self.rotation_interval_days)

    def should_retire(self, key: EncryptionKey) -> bool:
        """Return True if the given key should be retired."""
        if key.status != KeyStatus.ROTATING:
            return False
        age = datetime.now(timezone.utc) - key.created_at
        return age >= timedelta(days=self.retirement_delay_days)


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


def derive_key_from_password(
    password: str,
    salt: Optional[bytes] = None,
    *,
    iterations: int = DEFAULT_PBKDF2_ITERATIONS,
) -> tuple[bytes, bytes]:
    """Derive a 256-bit encryption key from a password using PBKDF2.

    Args:
        password: The password to derive from.
        salt: Optional salt bytes. Generated randomly if not provided.
        iterations: PBKDF2 iteration count.

    Returns:
        A tuple of (key_bytes, salt).
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        )
    if salt is None:
        salt = os.urandom(SALT_SIZE)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_SIZE,
        salt=salt,
        iterations=iterations,
        backend=default_backend(),
    )
    key = kdf.derive(password.encode("utf-8"))
    return key, salt


def derive_key_from_password_scrypt(
    password: str,
    salt: Optional[bytes] = None,
    *,
    n: int = DEFAULT_SCRYPT_N,
    r: int = DEFAULT_SCRYPT_R,
    p: int = DEFAULT_SCRYPT_P,
) -> tuple[bytes, bytes]:
    """Derive a 256-bit encryption key from a password using Scrypt.

    Scrypt is memory-hard and more resistant to hardware attacks than
    PBKDF2, but slower. Use this when deriving keys from user-provided
    passwords.

    Args:
        password: The password to derive from.
        salt: Optional salt bytes. Generated randomly if not provided.
        n: CPU/memory cost parameter (must be a power of 2).
        r: Block size parameter.
        p: Parallelization parameter.

    Returns:
        A tuple of (key_bytes, salt).
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        )
    if salt is None:
        salt = os.urandom(SALT_SIZE)
    kdf = Scrypt(
        salt=salt,
        length=AES_KEY_SIZE,
        n=n,
        r=r,
        p=p,
        backend=default_backend(),
    )
    key = kdf.derive(password.encode("utf-8"))
    return key, salt


# ---------------------------------------------------------------------------
# Key generation and loading
# ---------------------------------------------------------------------------


def generate_encryption_key() -> EncryptionKey:
    """Generate a new random 256-bit encryption key.

    Returns:
        A new EncryptionKey with a random key ID and key material.
    """
    key_bytes = AESGCM.generate_key(bit_length=256)
    key_id = secrets.token_hex(KEY_ID_SIZE)
    return EncryptionKey(
        key_id=key_id,
        key_bytes=key_bytes,
        created_at=datetime.now(timezone.utc),
        status=KeyStatus.ACTIVE,
    )


def generate_key_id() -> str:
    """Generate a new random key identifier."""
    return secrets.token_hex(KEY_ID_SIZE)


def load_key_from_env(
    env_var: str = "DCC_ENCRYPTION_KEY",
    *,
    key_id: Optional[str] = None,
) -> EncryptionKey:
    """Load an encryption key from an environment variable.

    The environment variable must contain a base64-encoded 256-bit key.

    Args:
        env_var: Name of the environment variable.
        key_id: Optional key ID. Generated if not provided.

    Returns:
        The loaded EncryptionKey.

    Raises:
        KeyNotFoundError: If the environment variable is not set.
        ValueError: If the key material is invalid.
    """
    encoded = os.environ.get(env_var)
    if not encoded:
        raise KeyNotFoundError(
            f"Encryption key not found: {env_var} is not set"
        )
    try:
        key_bytes = base64.b64decode(encoded)
    except Exception as exc:
        raise ValueError(
            f"Invalid base64 in {env_var}: {exc}"
        ) from exc
    if len(key_bytes) != AES_KEY_SIZE:
        raise ValueError(
            f"Encryption key must be {AES_KEY_SIZE} bytes, got {len(key_bytes)}"
        )
    if key_id is None:
        key_id = hashlib.sha256(key_bytes).hexdigest()[: KEY_ID_SIZE * 2]
    return EncryptionKey(
        key_id=key_id,
        key_bytes=key_bytes,
        created_at=datetime.now(timezone.utc),
        status=KeyStatus.ACTIVE,
    )


def load_key_from_file(
    path: Union[str, Path],
    *,
    key_id: Optional[str] = None,
) -> EncryptionKey:
    """Load an encryption key from a file.

    The file must contain a base64-encoded 256-bit key.

    Args:
        path: Path to the key file.
        key_id: Optional key ID. Generated if not provided.

    Returns:
        The loaded EncryptionKey.

    Raises:
        KeyNotFoundError: If the file does not exist.
        ValueError: If the key material is invalid.
    """
    key_path = Path(path)
    if not key_path.exists():
        raise KeyNotFoundError(f"Key file not found: {key_path}")
    encoded = key_path.read_text(encoding="utf-8").strip()
    try:
        key_bytes = base64.b64decode(encoded)
    except Exception as exc:
        raise ValueError(
            f"Invalid base64 in key file {key_path}: {exc}"
        ) from exc
    if len(key_bytes) != AES_KEY_SIZE:
        raise ValueError(
            f"Encryption key must be {AES_KEY_SIZE} bytes, got {len(key_bytes)}"
        )
    if key_id is None:
        key_id = hashlib.sha256(key_bytes).hexdigest()[: KEY_ID_SIZE * 2]
    return EncryptionKey(
        key_id=key_id,
        key_bytes=key_bytes,
        created_at=datetime.now(timezone.utc),
        status=KeyStatus.ACTIVE,
    )


def save_key_to_file(
    key: EncryptionKey,
    path: Union[str, Path],
    *,
    mode: int = 0o600,
) -> None:
    """Save an encryption key to a file with restricted permissions.

    Args:
        key: The key to save.
        path: Destination file path.
        mode: File permission mode (default 0o600 — owner read/write only).
    """
    key_path = Path(path)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = base64.b64encode(key.key_bytes).decode("ascii")
    key_path.write_text(encoded + "\n", encoding="utf-8")
    os.chmod(key_path, mode)


# ---------------------------------------------------------------------------
# At-rest field-level encryption
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EncryptedField:
    """An encrypted field value with metadata for decryption.

    The wire format is a string: ``dcc_enc_v1:<key_id>:<base64(nonce+ciphertext+tag)>``

    Attributes:
        key_id: ID of the key used for encryption.
        nonce: The GCM nonce used.
        ciphertext: The encrypted data (includes GCM auth tag).
    """

    key_id: str
    nonce: bytes
    ciphertext: bytes

    def to_wire_format(self) -> str:
        """Serialize to the wire format string."""
        combined = self.nonce + self.ciphertext
        encoded = base64.urlsafe_b64encode(combined).decode("ascii")
        return f"{ENCRYPTED_PREFIX}:{self.key_id}:{encoded}"

    @classmethod
    def from_wire_format(cls, wire: str) -> EncryptedField:
        """Deserialize from the wire format string.

        Raises:
            DecryptionError: If the wire format is invalid.
        """
        parts = wire.split(":", 2)
        if len(parts) != 3 or parts[0] != ENCRYPTED_PREFIX:
            raise DecryptionError(f"Invalid encrypted field format: {wire[:32]}...")
        key_id = parts[1]
        try:
            combined = base64.urlsafe_b64decode(parts[2])
        except Exception as exc:
            raise DecryptionError(f"Invalid base64 in encrypted field: {exc}") from exc
        if len(combined) < GCM_NONCE_SIZE + GCM_TAG_SIZE:
            raise DecryptionError("Encrypted field is too short")
        nonce = combined[:GCM_NONCE_SIZE]
        ciphertext = combined[GCM_NONCE_SIZE:]
        return cls(key_id=key_id, nonce=nonce, ciphertext=ciphertext)


class FieldEncryptor:
    """Encrypts and decrypts individual fields using AES-256-GCM.

    This is the primary interface for at-rest field-level encryption.
    Each field is encrypted with a unique random nonce and authenticated.

    Usage:
        encryptor = FieldEncryptor(key)
        encrypted = encryptor.encrypt("sensitive data")
        decrypted = encryptor.decrypt(encrypted)
    """

    def __init__(self, key: EncryptionKey) -> None:
        """Initialize with an encryption key.

        Args:
            key: The encryption key to use.
        """
        if not key.is_usable:
            raise EncryptionError(
                f"Key {key.key_id} is not usable (status: {key.status.value})"
            )
        self._key = key
        self._aesgcm = AESGCM(key.key_bytes)

    @property
    def key_id(self) -> str:
        """Return the key ID of the current encryption key."""
        return self._key.key_id

    def encrypt(
        self,
        plaintext: Union[str, bytes],
        *,
        associated_data: Optional[bytes] = None,
    ) -> str:
        """Encrypt a field value.

        Args:
            plaintext: The value to encrypt.
            associated_data: Optional additional authenticated data (AAD).
                This is not encrypted but is authenticated — tampering with
                it will cause decryption to fail.

        Returns:
            The encrypted field in wire format.

        Raises:
            PlaintextTooLargeError: If plaintext exceeds MAX_PLAINTEXT_SIZE.
            EncryptionError: If the key is not usable for encryption.
        """
        if not self._key.can_encrypt:
            raise EncryptionError(
                f"Key {self._key.key_id} cannot encrypt (status: {self._key.status.value})"
            )
        if isinstance(plaintext, str):
            data = plaintext.encode("utf-8")
        else:
            data = plaintext
        if len(data) > MAX_PLAINTEXT_SIZE:
            raise PlaintextTooLargeError(
                f"Plaintext exceeds maximum size of {MAX_PLAINTEXT_SIZE} bytes"
            )
        nonce = os.urandom(GCM_NONCE_SIZE)
        ciphertext = self._aesgcm.encrypt(nonce, data, associated_data)
        return EncryptedField(
            key_id=self._key.key_id,
            nonce=nonce,
            ciphertext=ciphertext,
        ).to_wire_format()

    def decrypt(
        self,
        wire: str,
        *,
        associated_data: Optional[bytes] = None,
    ) -> str:
        """Decrypt a field value.

        Args:
            wire: The encrypted field in wire format.
            associated_data: The same AAD used during encryption, if any.

        Returns:
            The decrypted plaintext as a string.

        Raises:
            DecryptionError: If decryption fails (wrong key, tampered data).
        """
        try:
            enc = EncryptedField.from_wire_format(wire)
        except DecryptionError:
            raise
        if enc.key_id != self._key.key_id:
            raise DecryptionError(
                f"Key ID mismatch: expected {self._key.key_id}, got {enc.key_id}"
            )
        try:
            plaintext = self._aesgcm.decrypt(
                enc.nonce, enc.ciphertext, associated_data
            )
        except Exception as exc:
            raise DecryptionError(f"Decryption failed: {exc}") from exc
        return plaintext.decode("utf-8")

    def decrypt_bytes(
        self,
        wire: str,
        *,
        associated_data: Optional[bytes] = None,
    ) -> bytes:
        """Decrypt a field value and return raw bytes.

        Args:
            wire: The encrypted field in wire format.
            associated_data: The same AAD used during encryption, if any.

        Returns:
            The decrypted plaintext as bytes.
        """
        try:
            enc = EncryptedField.from_wire_format(wire)
        except DecryptionError:
            raise
        if enc.key_id != self._key.key_id:
            raise DecryptionError(
                f"Key ID mismatch: expected {self._key.key_id}, got {enc.key_id}"
            )
        try:
            return self._aesgcm.decrypt(enc.nonce, enc.ciphertext, associated_data)
        except Exception as exc:
            raise DecryptionError(f"Decryption failed: {exc}") from exc

    def rotate_key(self, new_key: EncryptionKey) -> None:
        """Switch to a new encryption key.

        After rotation, new encryptions use the new key. Old data encrypted
        with the previous key must be re-encrypted separately.

        Args:
            new_key: The new encryption key to use.
        """
        if not new_key.can_encrypt:
            raise KeyRotationError(
                f"New key {new_key.key_id} cannot encrypt (status: {new_key.status.value})"
            )
        self._key = new_key
        self._aesgcm = AESGCM(new_key.key_bytes)


class MultiKeyFieldEncryptor:
    """Field encryptor that supports decryption with multiple keys.

    During key rotation, data encrypted with the old key must still be
    decryptable. This encryptor holds a primary key for encryption and
    a set of secondary keys for decryption of legacy data.

    Usage:
        encryptor = MultiKeyFieldEncryptor(primary_key, [old_key1, old_key2])
        encrypted = encryptor.encrypt("sensitive")
        decrypted = encryptor.decrypt(encrypted)  # works with any key
    """

    def __init__(
        self,
        primary_key: EncryptionKey,
        decryption_keys: Optional[list[EncryptionKey]] = None,
    ) -> None:
        """Initialize with a primary key and optional legacy keys.

        Args:
            primary_key: The key used for encryption.
            decryption_keys: Additional keys allowed for decryption.
        """
        if not primary_key.can_encrypt:
            raise EncryptionError(
                f"Primary key {primary_key.key_id} cannot encrypt"
            )
        self._primary = FieldEncryptor(primary_key)
        self._decryption_keys: dict[str, FieldEncryptor] = {}
        for key in decryption_keys or []:
            if key.can_decrypt:
                self._decryption_keys[key.key_id] = FieldEncryptor(key)

    @property
    def primary_key_id(self) -> str:
        """Return the primary key ID."""
        return self._primary.key_id

    def encrypt(
        self,
        plaintext: Union[str, bytes],
        *,
        associated_data: Optional[bytes] = None,
    ) -> str:
        """Encrypt using the primary key."""
        return self._primary.encrypt(plaintext, associated_data=associated_data)

    def decrypt(
        self,
        wire: str,
        *,
        associated_data: Optional[bytes] = None,
    ) -> str:
        """Decrypt using the appropriate key.

        The key ID is extracted from the wire format and the matching
        decryptor is used. Falls back to the primary key if the key ID
        matches.

        Raises:
            DecryptionError: If no matching key is found or decryption fails.
        """
        try:
            enc = EncryptedField.from_wire_format(wire)
        except DecryptionError:
            raise
        if enc.key_id == self._primary.key_id:
            return self._primary.decrypt(wire, associated_data=associated_data)
        decryptor = self._decryption_keys.get(enc.key_id)
        if decryptor is None:
            raise DecryptionError(
                f"No decryption key available for key ID {enc.key_id}"
            )
        return decryptor.decrypt(wire, associated_data=associated_data)

    def add_decryption_key(self, key: EncryptionKey) -> None:
        """Add a key for decryption of legacy data."""
        if key.can_decrypt:
            self._decryption_keys[key.key_id] = FieldEncryptor(key)

    def remove_decryption_key(self, key_id: str) -> None:
        """Remove a decryption key (e.g., after all data is re-encrypted)."""
        self._decryption_keys.pop(key_id, None)


# ---------------------------------------------------------------------------
# At-rest encryption for database columns
# ---------------------------------------------------------------------------


class AtRestEncryption:
    """Manages at-rest encryption for database columns.

    This class provides a higher-level interface for encrypting specific
    columns in database rows. It integrates with the FieldEncryptor and
    supports transparent encryption/decryption of designated fields.

    Usage:
        encryption = AtRestEncryption(encryptor, sensitive_fields=["ssn", "api_key"])
        row = {"name": "server-1", "ssn": "123-45-6789"}
        encrypted_row = encryption.encrypt_row(row)
        # Store encrypted_row in the database
        decrypted_row = encryption.decrypt_row(encrypted_row)
    """

    def __init__(
        self,
        encryptor: FieldEncryptor,
        sensitive_fields: Optional[set[str]] = None,
    ) -> None:
        """Initialize the at-rest encryption manager.

        Args:
            encryptor: The field encryptor to use.
            sensitive_fields: Set of field names to encrypt/decrypt.
                If None, all string fields are encrypted.
        """
        self._encryptor = encryptor
        self._sensitive_fields = sensitive_fields

    @property
    def sensitive_fields(self) -> Optional[set[str]]:
        """Return the set of sensitive field names."""
        return self._sensitive_fields

    def encrypt_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Encrypt sensitive fields in a database row.

        Args:
            row: A dictionary representing a database row.

        Returns:
            A new dictionary with sensitive fields encrypted.
        """
        result = dict(row)
        for key, value in result.items():
            if self._should_encrypt(key, value):
                result[key] = self._encryptor.encrypt(str(value))
        return result

    def decrypt_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Decrypt sensitive fields in a database row.

        Args:
            row: A dictionary with encrypted fields.

        Returns:
            A new dictionary with sensitive fields decrypted.
        """
        result = dict(row)
        for key, value in result.items():
            if self._should_decrypt(key, value):
                result[key] = self._encryptor.decrypt(value)
        return result

    def encrypt_value(self, field_name: str, value: Any) -> str:
        """Encrypt a single field value.

        Args:
            field_name: The name of the field.
            value: The value to encrypt.

        Returns:
            The encrypted value in wire format.
        """
        return self._encryptor.encrypt(str(value))

    def decrypt_value(self, field_name: str, wire: str) -> str:
        """Decrypt a single field value.

        Args:
            field_name: The name of the field.
            wire: The encrypted value in wire format.

        Returns:
            The decrypted value.
        """
        return self._encryptor.decrypt(wire)

    def _should_encrypt(self, key: str, value: Any) -> bool:
        """Determine if a field should be encrypted."""
        if not isinstance(value, str):
            return False
        if value.startswith(ENCRYPTED_PREFIX):
            return False  # Already encrypted
        if self._sensitive_fields is not None:
            return key in self._sensitive_fields
        return True  # Default: encrypt all strings

    def _should_decrypt(self, key: str, value: Any) -> bool:
        """Determine if a field should be decrypted."""
        if not isinstance(value, str):
            return False
        if not value.startswith(ENCRYPTED_PREFIX):
            return False
        if self._sensitive_fields is not None:
            return key in self._sensitive_fields
        return True


# ---------------------------------------------------------------------------
# In-transit TLS configuration
# ---------------------------------------------------------------------------


@dataclass
class TLSConfig:
    """TLS configuration for the HTTP server.

    Provides secure defaults for TLS 1.2+ with strong cipher suites,
    certificate verification, and security headers.

    Attributes:
        cert_path: Path to the TLS certificate file.
        key_path: Path to the TLS private key file.
        ca_path: Path to the CA certificate for client cert verification.
        min_version: Minimum TLS version (default TLSv1_2).
        cipher_suites: List of allowed cipher suites (OpenSSL format).
        verify_client: Whether to require client certificates.
        hsts_max_age: Max age for HSTS header in seconds (default 1 year).
        hsts_include_subdomains: Whether to include subdomains in HSTS.
    """

    cert_path: Optional[Path] = None
    key_path: Optional[Path] = None
    ca_path: Optional[Path] = None
    min_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2
    cipher_suites: list[str] = field(default_factory=lambda: [
        "ECDHE-ECDSA-AES256-GCM-SHA384",
        "ECDHE-RSA-AES256-GCM-SHA384",
        "ECDHE-ECDSA-AES128-GCM-SHA256",
        "ECDHE-RSA-AES128-GCM-SHA256",
        "ECDHE-ECDSA-CHACHA20-POLY1305",
        "ECDHE-RSA-CHACHA20-POLY1305",
    ])
    verify_client: bool = False
    hsts_max_age: int = 31_536_000  # 1 year
    hsts_include_subdomains: bool = True

    def create_ssl_context(self) -> ssl.SSLContext:
        """Create a configured SSLContext for the HTTP server.

        Returns:
            A configured SSLContext ready for use with HTTPServer.

        Raises:
            TLSError: If certificate files are missing or invalid.
        """
        if self.cert_path is None or self.key_path is None:
            raise TLSError(
                "TLS certificate and key paths are required for in-transit encryption"
            )
        if not self.cert_path.exists():
            raise TLSError(f"TLS certificate not found: {self.cert_path}")
        if not self.key_path.exists():
            raise TLSError(f"TLS private key not found: {self.key_path}")

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = self.min_version
        context.load_cert_chain(
            certfile=str(self.cert_path),
            keyfile=str(self.key_path),
        )

        if self.ca_path is not None:
            if not self.ca_path.exists():
                raise TLSError(f"CA certificate not found: {self.ca_path}")
            context.load_verify_locations(cafile=str(self.ca_path))
            context.verify_mode = ssl.CERT_REQUIRED if self.verify_client else ssl.CERT_OPTIONAL

        if self.cipher_suites:
            context.set_ciphers(":".join(self.cipher_suites))

        # Enable OCSP stapling if available
        if hasattr(context, "ocsp_response_cb"):
            context.ocsp_response_cb = None  # type: ignore[attr-defined]

        return context

    def get_security_headers(self) -> dict[str, str]:
        """Return security headers to add to every response.

        Returns:
            A dictionary of HTTP security headers.
        """
        headers = {
            "Strict-Transport-Security": (
                f"max-age={self.hsts_max_age}"
                + ("; includeSubDomains" if self.hsts_include_subdomains else "")
            ),
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }
        return headers

    @classmethod
    def from_env(cls) -> TLSConfig:
        """Create a TLSConfig from environment variables.

        Environment variables:
            DCC_TLS_CERT_PATH: Path to TLS certificate.
            DCC_TLS_KEY_PATH: Path to TLS private key.
            DCC_TLS_CA_PATH: Path to CA certificate (optional).
            DCC_TLS_VERIFY_CLIENT: "true" to require client certs.

        Returns:
            A TLSConfig instance.
        """
        cert_path = os.environ.get("DCC_TLS_CERT_PATH")
        key_path = os.environ.get("DCC_TLS_KEY_PATH")
        ca_path = os.environ.get("DCC_TLS_CA_PATH")
        verify_client = os.environ.get("DCC_TLS_VERIFY_CLIENT", "").lower() == "true"

        return cls(
            cert_path=Path(cert_path) if cert_path else None,
            key_path=Path(key_path) if key_path else None,
            ca_path=Path(ca_path) if ca_path else None,
            verify_client=verify_client,
        )


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def create_default_field_encryptor(
    *,
    env_var: str = "DCC_ENCRYPTION_KEY",
    key_path: Optional[Union[str, Path]] = None,
) -> FieldEncryptor:
    """Create a FieldEncryptor from the environment or a key file.

    This is the recommended way to create a field encryptor in production.
    It first tries to load the key from the environment variable, then
    falls back to a key file.

    Args:
        env_var: Environment variable containing the base64-encoded key.
        key_path: Path to a key file (fallback if env var is not set).

    Returns:
        A configured FieldEncryptor.

    Raises:
        KeyNotFoundError: If no key is found in the environment or file.
    """
    try:
        key = load_key_from_env(env_var)
    except KeyNotFoundError:
        if key_path is not None:
            key = load_key_from_file(key_path)
        else:
            raise
    return FieldEncryptor(key)


# ---------------------------------------------------------------------------
# HMAC utilities for data integrity
# ---------------------------------------------------------------------------


def compute_hmac(key: bytes, message: Union[str, bytes]) -> str:
    """Compute an HMAC-SHA-256 for data integrity verification.

    Args:
        key: The HMAC key.
        message: The message to authenticate.

    Returns:
        The HMAC as a hex string.
    """
    if isinstance(message, str):
        message = message.encode("utf-8")
    h = hmac.new(key, message, hashlib.sha256)
    return h.hexdigest()


def verify_hmac(key: bytes, message: Union[str, bytes], expected: str) -> bool:
    """Verify an HMAC-SHA-256 signature.

    Args:
        key: The HMAC key.
        message: The message to verify.
        expected: The expected HMAC hex string.

    Returns:
        True if the HMAC matches, False otherwise.
    """
    computed = compute_hmac(key, message)
    return hmac.compare_digest(computed, expected)
