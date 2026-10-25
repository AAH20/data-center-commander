"""Unit tests for the API key store's contract, with no database involved.

These pin the behaviour that must hold on BOTH backends (the in-memory store here,
the durable store in tests/integration/test_api_keys_durable.py):

  * hashing round-trips, and the raw key is never part of a stored record;
  * expiry, revocation and unknown keys are distinguishable failures -- a caller
    needs to tell "expired" from "never existed" for logging, even though the HTTP
    layer deliberately returns the same 401 body for all of them;
  * scopes survive a round trip;
  * comparison goes through ``hmac.compare_digest``, not ``==``. A digest comparison
    that leaks timing is the classic way an API key scheme is defeated offline, so
    this asserts the primitive was actually called rather than trusting the reviewer
    to notice.

The store is always constructed with an explicit empty DSN here. ``ApiKeyStore()``
with no argument picks up ``DCC_DATABASE_URL``, which would make these tests depend on
whatever database the machine happens to have.
"""

from __future__ import annotations

import time

import pytest

from dcc.security import api_keys as api_keys_module
from dcc.security.api_keys import (
    ApiKeyExpiredError,
    ApiKeyInvalidError,
    ApiKeyRevokedError,
    ApiKeyStore,
    generate_api_key,
    hash_api_key,
    verify_api_key,
)

TENANT = "11111111-1111-4111-8111-111111111111"


@pytest.fixture()
def store():
    """A process-local store, regardless of the ambient environment."""
    instance = ApiKeyStore(dsn="")
    try:
        yield instance
    finally:
        instance.close()


class TestHashing:
    def test_hash_is_sha256_hex_and_round_trips(self):
        raw = generate_api_key()
        digest = hash_api_key(raw)

        assert len(digest) == 64
        assert digest == digest.lower()
        int(digest, 16)  # raises if it is not hex
        assert verify_api_key(raw, digest) is True

    def test_a_different_key_does_not_match(self):
        digest = hash_api_key(generate_api_key())
        assert verify_api_key(generate_api_key(), digest) is False

    def test_hash_is_deterministic(self):
        raw = generate_api_key()
        assert hash_api_key(raw) == hash_api_key(raw)

    def test_generated_keys_are_unique_and_prefixed(self):
        keys = {generate_api_key() for _ in range(50)}
        assert len(keys) == 50
        assert all(k.startswith("dcc_") and len(k) == 4 + 64 for k in keys)

    def test_verification_compares_in_constant_time(self, store, monkeypatch):
        """The digest comparison must go through ``hmac.compare_digest``.

        Monkeypatched rather than timed: a timing assertion on a shared CI machine is
        flaky and would prove nothing about a single call.
        """
        raw, _ = store.create(name="ct", tenant_id=TENANT)
        calls = []
        real = api_keys_module.hmac.compare_digest

        def recording(left, right):
            calls.append((left, right))
            return real(left, right)

        monkeypatch.setattr(api_keys_module.hmac, "compare_digest", recording)

        assert store.verify(raw).tenant_id == TENANT
        assert calls, "verify() never called hmac.compare_digest"
        left, right = calls[0]
        assert left == right == hash_api_key(raw)


class TestVerification:
    def test_unknown_key_is_rejected(self, store):
        with pytest.raises(ApiKeyInvalidError):
            store.verify(generate_api_key())

    def test_empty_key_is_rejected(self, store):
        with pytest.raises(ApiKeyInvalidError):
            store.verify("")

    def test_a_valid_key_returns_its_tenant(self, store):
        raw, record = store.create(name="ops", tenant_id=TENANT)
        verified = store.verify(raw)
        assert verified.tenant_id == TENANT
        assert verified.id == record.id

    def test_expired_key_is_rejected(self, store):
        raw, _ = store.create(
            name="old", tenant_id=TENANT, expires_at=time.time() - 1
        )
        with pytest.raises(ApiKeyExpiredError):
            store.verify(raw)

    def test_key_that_has_not_expired_is_accepted(self, store):
        raw, _ = store.create(
            name="fresh", tenant_id=TENANT, expires_at=time.time() + 60
        )
        assert store.verify(raw).tenant_id == TENANT

    def test_revoked_key_is_rejected(self, store):
        raw, record = store.create(name="leaked", tenant_id=TENANT)
        assert store.verify(raw) is not None

        assert store.revoke(record.id) is True
        with pytest.raises(ApiKeyRevokedError):
            store.verify(raw)

    def test_revoked_key_is_rejected_even_though_the_hash_matches(self, store):
        """Ordering matters: revocation must be checked, not just the digest."""
        raw, record = store.create(name="leaked", tenant_id=TENANT)
        store.revoke(record.id)
        with pytest.raises(ApiKeyRevokedError):
            store.verify(raw)

    def test_deleted_key_is_rejected(self, store):
        raw, record = store.create(name="gone", tenant_id=TENANT)
        assert store.delete(record.id) is True
        with pytest.raises(ApiKeyInvalidError):
            store.verify(raw)

    def test_verify_stamps_last_used(self, store):
        raw, record = store.create(name="used", tenant_id=TENANT)
        assert record.last_used_at is None
        verified = store.verify(raw)
        assert verified.last_used_at is not None


class TestScopesAndAuditFields:
    def test_scopes_are_preserved(self, store):
        raw, record = store.create(
            name="scoped", tenant_id=TENANT, scopes=["read", "write", "admin"]
        )
        assert record.scopes == ["read", "write", "admin"]
        assert store.verify(raw).scopes == ["read", "write", "admin"]

    def test_scopes_default_to_empty_not_none(self, store):
        raw, record = store.create(name="bare", tenant_id=TENANT)
        assert record.scopes == []
        assert store.verify(raw).scopes == []

    def test_registered_hash_keeps_its_scopes(self, store):
        digest = hash_api_key(generate_api_key())
        record = store.register_hash(
            tenant_id=TENANT, key_hash=digest, name="env", scopes=["read"]
        )
        assert record.scopes == ["read"]
        assert record.key_hash == digest

    def test_created_by_is_carried_on_the_record(self, store):
        _, record = store.create(
            name="attributed", tenant_id=TENANT, created_by="ops@example.test"
        )
        assert record.created_by == "ops@example.test"

    def test_record_never_contains_the_raw_key(self, store):
        raw, record = store.create(name="secret", tenant_id=TENANT)
        serialized = record.to_dict(include_hash=True)

        assert raw not in repr(serialized)
        assert record.key_hash == hash_api_key(raw)
        assert record.key_hash != raw
        assert raw not in record.key_hash

    def test_register_hash_rejects_a_short_digest(self, store):
        with pytest.raises(ValueError):
            store.register_hash(tenant_id=TENANT, key_hash="abc")

    def test_register_hash_requires_a_tenant(self, store):
        with pytest.raises(ValueError):
            store.register_hash(tenant_id="", key_hash="a" * 64)


class TestBackendSelection:
    def test_no_dsn_is_memory(self):
        store = ApiKeyStore(dsn="")
        try:
            assert store.backend == "memory"
        finally:
            store.close()

    def test_a_dsn_selects_postgres_without_connecting(self):
        """Construction must not touch the network: import time runs this.

        The DSN points at a port nothing listens on. If the constructor tried to
        connect, this test would hang or raise instead of passing.
        """
        store = ApiKeyStore(dsn="postgresql://127.0.0.1:1/none", timeout=0.5)
        try:
            assert store.backend == "postgres"
        finally:
            store.close()

    def test_non_uuid_tenant_degrades_to_a_process_local_key(self):
        """A tenant that cannot exist in dcc.tenants cannot be stored durably.

        Test fixtures and ``tenant-a``-style identifiers take this path. Issuing and
        verifying the key must still work, and must not require the database: the DSN
        here points at a closed port, so any durable attempt fails.
        """
        store = ApiKeyStore(dsn="postgresql://127.0.0.1:1/none", timeout=0.5)
        try:
            raw, record = store.create(name="fixture", tenant_id="tenant-a")
            assert record.tenant_id == "tenant-a"
            assert store.verify(raw).tenant_id == "tenant-a"
            assert len(store._keys) == 1, "the key should be process-local"
        finally:
            store.close()

    def test_reset_clears_process_state(self, store):
        store.create(name="x", tenant_id=TENANT)
        assert store.count() == 1
        store.reset()
        assert store.count() == 0


class TestAuditUpdateIsBestEffort:
    def test_scheduling_a_touch_never_raises(self, store):
        """The audit write is never worth a 401.

        A key still authenticates when ``last_used_at`` cannot be written; otherwise a
        momentarily unavailable audit path would lock every customer out. Here the
        executor itself refuses work, which is the worst case: the failure has to be
        swallowed at the scheduling site, because the caller cannot await it.
        """

        class ExplodingExecutor:
            def submit(self, *_args, **_kwargs):
                raise RuntimeError("executor is shut down")

        store._executor = ExplodingExecutor()
        store._schedule_touch(hash_api_key(generate_api_key()))  # must not raise

    def test_touch_is_throttled_per_key(self, store):
        """One audit write per key per interval, not one per request.

        Without this, every authenticated request would become an UPDATE on the
        authentication path -- the write amplification this design exists to avoid.
        """

        class RecordingExecutor:
            def __init__(self):
                self.submitted = []

            def submit(self, _fn, digest):
                self.submitted.append(digest)

        executor = RecordingExecutor()
        store._executor = executor
        store._touch_interval = 3600.0

        digest_a = hash_api_key(generate_api_key())
        digest_b = hash_api_key(generate_api_key())

        store._schedule_touch(digest_a)
        store._schedule_touch(digest_a)
        store._schedule_touch(digest_a)
        store._schedule_touch(digest_b)

        assert executor.submitted == [digest_a, digest_b]
