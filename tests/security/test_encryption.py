"""Tests for data encryption: at-rest, in-transit TLS, and key management."""
from __future__ import annotations

import base64
import os
import ssl
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from dcc.security.encryption import (
    AES_KEY_SIZE,
    ENCRYPTED_PREFIX,
    GCM_NONCE_SIZE,
    GCM_TAG_SIZE,
    AtRestEncryption,
    DecryptionError,
    EncryptionError,
    EncryptionKey,
    FieldEncryptor,
    KeyNotFoundError,
    KeyRotationError,
    KeyRotationPolicy,
    KeyStatus,
    MultiKeyFieldEncryptor,
    PlaintextTooLargeError,
    TLSConfig,
    TLSError,
    compute_hmac,
    create_default_field_encryptor,
    derive_key_from_password,
    derive_key_from_password_scrypt,
    generate_encryption_key,
    generate_key_id,
    load_key_from_env,
    load_key_from_file,
    save_key_to_file,
    verify_hmac,
)


# ---------------------------------------------------------------------------
# EncryptionKey tests
# ---------------------------------------------------------------------------


class TestEncryptionKey:
    def test_generate_key_is_valid(self):
        key = generate_encryption_key()
        assert len(key.key_bytes) == AES_KEY_SIZE
        assert key.status == KeyStatus.ACTIVE
        assert key.algorithm == "AES-256-GCM"
        assert key.is_usable
        assert key.can_encrypt
        assert key.can_decrypt

    def test_key_with_wrong_size_raises(self):
        with pytest.raises(ValueError, match="must be 32 bytes"):
            EncryptionKey(
                key_id="test",
                key_bytes=b"too-short",
                created_at=datetime.now(timezone.utc),
            )

    def test_rotated_key_cannot_encrypt(self):
        key = generate_encryption_key()
        rotated = EncryptionKey(
            key_id=key.key_id,
            key_bytes=key.key_bytes,
            created_at=key.created_at,
            status=KeyStatus.ROTATING,
        )
        assert not rotated.can_encrypt
        assert rotated.can_decrypt
        assert rotated.is_usable

    def test_retired_key_cannot_encrypt(self):
        key = generate_encryption_key()
        retired = EncryptionKey(
            key_id=key.key_id,
            key_bytes=key.key_bytes,
            created_at=key.created_at,
            status=KeyStatus.RETIRED,
        )
        assert not retired.can_encrypt
        assert retired.can_decrypt
        assert not retired.is_usable

    def test_destroyed_key_is_unusable(self):
        key = generate_encryption_key()
        destroyed = EncryptionKey(
            key_id=key.key_id,
            key_bytes=key.key_bytes,
            created_at=key.created_at,
            status=KeyStatus.DESTROYED,
        )
        assert not destroyed.can_encrypt
        assert not destroyed.can_decrypt
        assert not destroyed.is_usable

    def test_to_dict_excludes_key_material(self):
        key = generate_encryption_key()
        d = key.to_dict()
        assert "key_bytes" not in d
        assert "key_id" in d
        assert "status" in d
        assert "algorithm" in d

    def test_generate_key_id_is_unique(self):
        ids = {generate_key_id() for _ in range(100)}
        assert len(ids) == 100


# ---------------------------------------------------------------------------
# Key derivation tests
# ---------------------------------------------------------------------------


class TestKeyDerivation:
    def test_pbkdf2_derivation_is_deterministic(self):
        key1, salt1 = derive_key_from_password("a-very-secure-password-12345")
        key2, salt2 = derive_key_from_password("a-very-secure-password-12345", salt=salt1)
        assert key1 == key2
        assert salt1 == salt2
        assert len(key1) == AES_KEY_SIZE
        assert len(salt1) == 32

    def test_pbkdf2_different_passwords_different_keys(self):
        key1, _ = derive_key_from_password("a-very-secure-password-12345")
        key2, _ = derive_key_from_password("another-secure-password-67890")
        assert key1 != key2

    def test_pbkdf2_different_salts_different_keys(self):
        key1, _ = derive_key_from_password("a-very-secure-password-12345")
        key2, _ = derive_key_from_password("a-very-secure-password-12345")
        assert key1 != key2  # Random salts

    def test_pbkdf2_short_password_raises(self):
        with pytest.raises(ValueError, match="at least 16 characters"):
            derive_key_from_password("short")

    def test_scrypt_derivation_is_deterministic(self):
        key1, salt1 = derive_key_from_password_scrypt("a-very-secure-password-12345", n=2**14)
        key2, salt2 = derive_key_from_password_scrypt(
            "a-very-secure-password-12345", salt=salt1, n=2**14
        )
        assert key1 == key2
        assert salt1 == salt2

    def test_scrypt_different_passwords_different_keys(self):
        key1, _ = derive_key_from_password_scrypt("a-very-secure-password-12345", n=2**14)
        key2, _ = derive_key_from_password_scrypt("another-secure-password-67890", n=2**14)
        assert key1 != key2

    def test_scrypt_short_password_raises(self):
        with pytest.raises(ValueError, match="at least 16 characters"):
            derive_key_from_password_scrypt("short", n=2**14)


# ---------------------------------------------------------------------------
# Key loading tests
# ---------------------------------------------------------------------------


class TestKeyLoading:
    def test_load_key_from_env(self):
        key = generate_encryption_key()
        encoded = base64.b64encode(key.key_bytes).decode("ascii")
        with patch.dict(os.environ, {"DCC_ENCRYPTION_KEY": encoded}):
            loaded = load_key_from_env()
            assert loaded.key_bytes == key.key_bytes
            assert loaded.status == KeyStatus.ACTIVE

    def test_load_key_from_env_not_set(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(KeyNotFoundError, match="not set"):
                load_key_from_env()

    def test_load_key_from_env_invalid_base64(self):
        with patch.dict(os.environ, {"DCC_ENCRYPTION_KEY": "not-valid-base64!!!"}):
            with pytest.raises(ValueError, match="Invalid base64"):
                load_key_from_env()

    def test_load_key_from_env_wrong_size(self):
        encoded = base64.b64encode(b"too-short").decode("ascii")
        with patch.dict(os.environ, {"DCC_ENCRYPTION_KEY": encoded}):
            with pytest.raises(ValueError, match="must be 32 bytes"):
                load_key_from_env()

    def test_save_and_load_key_from_file(self):
        key = generate_encryption_key()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False) as f:
            path = f.name
        try:
            save_key_to_file(key, path)
            loaded = load_key_from_file(path)
            assert loaded.key_bytes == key.key_bytes
            # Check file permissions
            stat = os.stat(path)
            assert stat.st_mode & 0o777 == 0o600
        finally:
            os.unlink(path)

    def test_load_key_from_file_not_found(self):
        with pytest.raises(KeyNotFoundError, match="not found"):
            load_key_from_file("/nonexistent/path/to/key")

    def test_create_default_field_encryptor_from_env(self):
        key = generate_encryption_key()
        encoded = base64.b64encode(key.key_bytes).decode("ascii")
        with patch.dict(os.environ, {"DCC_ENCRYPTION_KEY": encoded}):
            encryptor = create_default_field_encryptor()
            assert isinstance(encryptor, FieldEncryptor)
            assert encryptor.key_id == encryptor.key_id

    def test_create_default_field_encryptor_from_file(self):
        key = generate_encryption_key()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False) as f:
            path = f.name
        try:
            save_key_to_file(key, path)
            with patch.dict(os.environ, {}, clear=True):
                encryptor = create_default_field_encryptor(key_path=path)
                assert isinstance(encryptor, FieldEncryptor)
        finally:
            os.unlink(path)

    def test_create_default_field_encryptor_no_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(KeyNotFoundError):
                create_default_field_encryptor()


# ---------------------------------------------------------------------------
# FieldEncryptor tests
# ---------------------------------------------------------------------------


class TestFieldEncryptor:
    def test_encrypt_decrypt_roundtrip(self):
        key = generate_encryption_key()
        encryptor = FieldEncryptor(key)
        plaintext = "sensitive data 123"
        encrypted = encryptor.encrypt(plaintext)
        assert encrypted.startswith(ENCRYPTED_PREFIX)
        assert plaintext not in encrypted
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_bytes(self):
        key = generate_encryption_key()
        encryptor = FieldEncryptor(key)
        plaintext = b"\x00\x01\x02\xff\xfe"
        encrypted = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt_bytes(encrypted)
        assert decrypted == plaintext

    def test_encrypt_produces_different_ciphertexts(self):
        key = generate_encryption_key()
        encryptor = FieldEncryptor(key)
        plaintext = "same data"
        enc1 = encryptor.encrypt(plaintext)
        enc2 = encryptor.encrypt(plaintext)
        assert enc1 != enc2  # Different nonces

    def test_decrypt_with_wrong_key_fails(self):
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        encryptor1 = FieldEncryptor(key1)
        encryptor2 = FieldEncryptor(key2)
        encrypted = encryptor1.encrypt("secret")
        with pytest.raises(DecryptionError):
            encryptor2.decrypt(encrypted)

    def test_decrypt_tampered_data_fails(self):
        key = generate_encryption_key()
        encryptor = FieldEncryptor(key)
        encrypted = encryptor.encrypt("secret")
        # Tamper with the ciphertext
        parts = encrypted.split(":")
        raw = base64.urlsafe_b64decode(parts[2])
        tampered = bytes([raw[0] ^ 0xFF]) + raw[1:]
        parts[2] = base64.urlsafe_b64encode(tampered).decode("ascii")
        tampered_wire = ":".join(parts)
        with pytest.raises(DecryptionError):
            encryptor.decrypt(tampered_wire)

    def test_decrypt_invalid_wire_format(self):
        key = generate_encryption_key()
        encryptor = FieldEncryptor(key)
        with pytest.raises(DecryptionError):
            encryptor.decrypt("not-valid")

    def test_decrypt_wrong_key_id(self):
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        encryptor1 = FieldEncryptor(key1)
        encryptor2 = FieldEncryptor(key2)
        encrypted = encryptor1.encrypt("secret")
        with pytest.raises(DecryptionError, match="Key ID mismatch"):
            encryptor2.decrypt(encrypted)

    def test_encrypt_with_associated_data(self):
        key = generate_encryption_key()
        encryptor = FieldEncryptor(key)
        plaintext = "authenticated data"
        aad = b"additional context"
        encrypted = encryptor.encrypt(plaintext, associated_data=aad)
        decrypted = encryptor.decrypt(encrypted, associated_data=aad)
        assert decrypted == plaintext

    def test_decrypt_with_wrong_aad_fails(self):
        key = generate_encryption_key()
        encryptor = FieldEncryptor(key)
        plaintext = "authenticated data"
        encrypted = encryptor.encrypt(plaintext, associated_data=b"correct-aad")
        with pytest.raises(DecryptionError):
            encryptor.decrypt(encrypted, associated_data=b"wrong-aad")

    def test_encrypt_too_large_raises(self):
        key = generate_encryption_key()
        encryptor = FieldEncryptor(key)
        with pytest.raises(PlaintextTooLargeError):
            encryptor.encrypt("x" * 2_000_000)

    def test_encrypt_with_unusable_key_raises(self):
        key = generate_encryption_key()
        destroyed = EncryptionKey(
            key_id=key.key_id,
            key_bytes=key.key_bytes,
            created_at=key.created_at,
            status=KeyStatus.DESTROYED,
        )
        with pytest.raises(EncryptionError, match="not usable"):
            FieldEncryptor(destroyed)

    def test_rotate_key(self):
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        encryptor = FieldEncryptor(key1)
        encrypted_old = encryptor.encrypt("data")
        encryptor.rotate_key(key2)
        encrypted_new = encryptor.encrypt("data")
        assert encrypted_old != encrypted_new
        # New data decrypts with new key
        assert encryptor.decrypt(encrypted_new) == "data"
        # Old data no longer decrypts (key ID changed)
        with pytest.raises(DecryptionError):
            encryptor.decrypt(encrypted_old)

    def test_rotate_to_unusable_key_raises(self):
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        encryptor = FieldEncryptor(key1)
        destroyed = EncryptionKey(
            key_id=key2.key_id,
            key_bytes=key2.key_bytes,
            created_at=key2.created_at,
            status=KeyStatus.DESTROYED,
        )
        with pytest.raises(KeyRotationError):
            encryptor.rotate_key(destroyed)


# ---------------------------------------------------------------------------
# EncryptedField wire format tests
# ---------------------------------------------------------------------------


class TestEncryptedField:
    def test_wire_format_roundtrip(self):
        key = generate_encryption_key()
        encryptor = FieldEncryptor(key)
        encrypted = encryptor.encrypt("test data")
        # Parse the wire format
        parts = encrypted.split(":")
        assert len(parts) == 3
        assert parts[0] == ENCRYPTED_PREFIX
        assert parts[1] == key.key_id
        raw = base64.urlsafe_b64decode(parts[2])
        assert len(raw) >= GCM_NONCE_SIZE + GCM_TAG_SIZE

    def test_from_wire_format_invalid_prefix(self):
        with pytest.raises(DecryptionError, match="Invalid encrypted field format"):
            from dcc.security.encryption import EncryptedField
            EncryptedField.from_wire_format("wrong:format")

    def test_from_wire_format_too_short(self):
        from dcc.security.encryption import EncryptedField
        short = base64.urlsafe_b64encode(b"short").decode("ascii")
        with pytest.raises(DecryptionError, match="too short"):
            EncryptedField.from_wire_format(f"{ENCRYPTED_PREFIX}:abc:{short}")


# ---------------------------------------------------------------------------
# MultiKeyFieldEncryptor tests
# ---------------------------------------------------------------------------


class TestMultiKeyFieldEncryptor:
    def test_encrypt_with_primary_decrypt_with_primary(self):
        key = generate_encryption_key()
        encryptor = MultiKeyFieldEncryptor(key)
        encrypted = encryptor.encrypt("secret")
        assert encryptor.decrypt(encrypted) == "secret"

    def test_decrypt_with_legacy_key(self):
        old_key = generate_encryption_key()
        new_key = generate_encryption_key()
        old_encryptor = FieldEncryptor(old_key)
        encrypted_with_old = old_encryptor.encrypt("legacy data")

        multi = MultiKeyFieldEncryptor(new_key, [old_key])
        assert multi.decrypt(encrypted_with_old) == "legacy data"

    def test_decrypt_unknown_key_id_fails(self):
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        encryptor1 = FieldEncryptor(key1)
        encrypted = encryptor1.encrypt("secret")
        multi = MultiKeyFieldEncryptor(key2)
        with pytest.raises(DecryptionError, match="No decryption key"):
            multi.decrypt(encrypted)

    def test_add_decryption_key(self):
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        encryptor1 = FieldEncryptor(key1)
        encrypted = encryptor1.encrypt("secret")
        multi = MultiKeyFieldEncryptor(key2)
        with pytest.raises(DecryptionError):
            multi.decrypt(encrypted)
        multi.add_decryption_key(key1)
        assert multi.decrypt(encrypted) == "secret"

    def test_remove_decryption_key(self):
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        encryptor1 = FieldEncryptor(key1)
        encrypted = encryptor1.encrypt("secret")
        multi = MultiKeyFieldEncryptor(key2, [key1])
        assert multi.decrypt(encrypted) == "secret"
        multi.remove_decryption_key(key1.key_id)
        with pytest.raises(DecryptionError):
            multi.decrypt(encrypted)


# ---------------------------------------------------------------------------
# AtRestEncryption tests
# ---------------------------------------------------------------------------


class TestAtRestEncryption:
    def test_encrypt_decrypt_row_with_sensitive_fields(self):
        key = generate_encryption_key()
        encryptor = FieldEncryptor(key)
        enc = AtRestEncryption(encryptor, sensitive_fields={"ssn", "api_key"})
        row = {"name": "server-1", "ssn": "123-45-6789", "api_key": "sk-abc123"}
        encrypted_row = enc.encrypt_row(row)
        assert encrypted_row["name"] == "server-1"  # Not encrypted
        assert encrypted_row["ssn"] != "123-45-6789"
        assert encrypted_row["ssn"].startswith(ENCRYPTED_PREFIX)
        assert encrypted_row["api_key"] != "sk-abc123"
        assert encrypted_row["api_key"].startswith(ENCRYPTED_PREFIX)
        decrypted_row = enc.decrypt_row(encrypted_row)
        assert decrypted_row == row

    def test_encrypt_row_without_sensitive_fields_set(self):
        key = generate_encryption_key()
        encryptor = FieldEncryptor(key)
        enc = AtRestEncryption(encryptor)  # No sensitive_fields = encrypt all strings
        row = {"name": "server-1", "status": "active"}
        encrypted_row = enc.encrypt_row(row)
        assert encrypted_row["name"].startswith(ENCRYPTED_PREFIX)
        assert encrypted_row["status"].startswith(ENCRYPTED_PREFIX)
        decrypted_row = enc.decrypt_row(encrypted_row)
        assert decrypted_row == row

    def test_encrypt_row_skips_non_string_values(self):
        key = generate_encryption_key()
        encryptor = FieldEncryptor(key)
        enc = AtRestEncryption(encryptor)
        row = {"name": "server-1", "count": 42, "active": True}
        encrypted_row = enc.encrypt_row(row)
        assert encrypted_row["count"] == 42
        assert encrypted_row["active"] is True

    def test_encrypt_row_skips_already_encrypted(self):
        key = generate_encryption_key()
        encryptor = FieldEncryptor(key)
        enc = AtRestEncryption(encryptor)
        row = {"name": "server-1"}
        encrypted_row = enc.encrypt_row(row)
        # Double-encrypt should be a no-op
        double_encrypted = enc.encrypt_row(encrypted_row)
        assert double_encrypted == encrypted_row

    def test_encrypt_decrypt_value(self):
        key = generate_encryption_key()
        encryptor = FieldEncryptor(key)
        enc = AtRestEncryption(encryptor)
        encrypted = enc.encrypt_value("ssn", "123-45-6789")
        assert encrypted.startswith(ENCRYPTED_PREFIX)
        decrypted = enc.decrypt_value("ssn", encrypted)
        assert decrypted == "123-45-6789"


# ---------------------------------------------------------------------------
# KeyRotationPolicy tests
# ---------------------------------------------------------------------------


class TestKeyRotationPolicy:
    def test_should_not_rotate_when_auto_rotate_disabled(self):
        policy = KeyRotationPolicy(auto_rotate=False)
        key = generate_encryption_key()
        assert not policy.should_rotate(key)

    def test_should_not_rotate_young_key(self):
        policy = KeyRotationPolicy(rotation_interval_days=90)
        key = generate_encryption_key()
        assert not policy.should_rotate(key)

    def test_should_rotate_old_key(self):
        policy = KeyRotationPolicy(rotation_interval_days=90)
        old_key = EncryptionKey(
            key_id="old",
            key_bytes=generate_encryption_key().key_bytes,
            created_at=datetime.now(timezone.utc) - timedelta(days=100),
        )
        assert policy.should_rotate(old_key)

    def test_should_not_rotate_non_active_key(self):
        policy = KeyRotationPolicy(rotation_interval_days=90)
        old_key = EncryptionKey(
            key_id="old",
            key_bytes=generate_encryption_key().key_bytes,
            created_at=datetime.now(timezone.utc) - timedelta(days=100),
            status=KeyStatus.ROTATING,
        )
        assert not policy.should_rotate(old_key)

    def test_should_retire_old_rotating_key(self):
        policy = KeyRotationPolicy(retirement_delay_days=30)
        old_key = EncryptionKey(
            key_id="old",
            key_bytes=generate_encryption_key().key_bytes,
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
            status=KeyStatus.ROTATING,
        )
        assert policy.should_retire(old_key)

    def test_should_not_retire_young_rotating_key(self):
        policy = KeyRotationPolicy(retirement_delay_days=30)
        key = EncryptionKey(
            key_id="rotating",
            key_bytes=generate_encryption_key().key_bytes,
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
            status=KeyStatus.ROTATING,
        )
        assert not policy.should_retire(key)


# ---------------------------------------------------------------------------
# TLSConfig tests
# ---------------------------------------------------------------------------


class TestTLSConfig:
    def test_create_ssl_context_requires_cert_and_key(self):
        config = TLSConfig()
        with pytest.raises(TLSError, match="certificate and key paths are required"):
            config.create_ssl_context()

    def test_create_ssl_context_missing_cert_file(self):
        config = TLSConfig(
            cert_path=Path("/nonexistent/cert.pem"),
            key_path=Path("/nonexistent/key.pem"),
        )
        with pytest.raises(TLSError, match="certificate not found"):
            config.create_ssl_context()

    def test_create_ssl_context_missing_key_file(self):
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as f:
            cert_path = Path(f.name)
        config = TLSConfig(
            cert_path=cert_path,
            key_path=Path("/nonexistent/key.pem"),
        )
        try:
            with pytest.raises(TLSError, match="private key not found"):
                config.create_ssl_context()
        finally:
            os.unlink(cert_path)

    def test_get_security_headers(self):
        config = TLSConfig()
        headers = config.get_security_headers()
        assert "Strict-Transport-Security" in headers
        assert "max-age=31536000" in headers["Strict-Transport-Security"]
        assert "includeSubDomains" in headers["Strict-Transport-Security"]
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"

    def test_get_security_headers_no_subdomains(self):
        config = TLSConfig(hsts_include_subdomains=False)
        headers = config.get_security_headers()
        assert "includeSubDomains" not in headers["Strict-Transport-Security"]

    def test_from_env(self):
        with patch.dict(os.environ, {
            "DCC_TLS_CERT_PATH": "/path/to/cert.pem",
            "DCC_TLS_KEY_PATH": "/path/to/key.pem",
            "DCC_TLS_CA_PATH": "/path/to/ca.pem",
            "DCC_TLS_VERIFY_CLIENT": "true",
        }):
            config = TLSConfig.from_env()
            assert config.cert_path == Path("/path/to/cert.pem")
            assert config.key_path == Path("/path/to/key.pem")
            assert config.ca_path == Path("/path/to/ca.pem")
            assert config.verify_client is True

    def test_from_env_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            config = TLSConfig.from_env()
            assert config.cert_path is None
            assert config.key_path is None
            assert config.ca_path is None
            assert config.verify_client is False

    def test_create_ssl_context_with_generated_certs(self):
        """Test SSL context creation with self-signed certs."""
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        import datetime as dt

        # Generate a self-signed cert for testing
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(dt.datetime.utcnow())
            .not_valid_after(dt.datetime.utcnow() + dt.timedelta(days=1))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName("localhost")]),
                critical=False,
            )
            .sign(private_key, hashes.SHA256())
        )

        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as cert_f:
            cert_f.write(cert.public_bytes(serialization.Encoding.PEM))
            cert_path = Path(cert_f.name)
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as key_f:
            key_f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))
            key_path = Path(key_f.name)

        try:
            config = TLSConfig(cert_path=cert_path, key_path=key_path)
            ctx = config.create_ssl_context()
            assert isinstance(ctx, ssl.SSLContext)
            assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2
        finally:
            os.unlink(cert_path)
            os.unlink(key_path)


# ---------------------------------------------------------------------------
# HMAC tests
# ---------------------------------------------------------------------------


class TestHMAC:
    def test_hmac_roundtrip(self):
        key = os.urandom(32)
        message = "integrity check"
        mac = compute_hmac(key, message)
        assert len(mac) == 64  # SHA-256 hex
        assert verify_hmac(key, message, mac)

    def test_hmac_wrong_key_fails(self):
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        message = "integrity check"
        mac = compute_hmac(key1, message)
        assert not verify_hmac(key2, message, mac)

    def test_hmac_wrong_message_fails(self):
        key = os.urandom(32)
        mac = compute_hmac(key, "original")
        assert not verify_hmac(key, "tampered", mac)

    def test_hmac_with_bytes(self):
        key = os.urandom(32)
        message = b"\x00\x01\x02"
        mac = compute_hmac(key, message)
        assert verify_hmac(key, message, mac)

    def test_hmac_timing_safe(self):
        """verify_hmac should use constant-time comparison."""
        key = os.urandom(32)
        mac = compute_hmac(key, "test")
        # Should not raise, just return False
        assert not verify_hmac(key, "test", "00" * 32)
