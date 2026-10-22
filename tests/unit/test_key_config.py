"""Tests for durable key configuration (DCC_API_KEYS) and the minting CLI.

The store is in-memory and per-process. Without a durable source, every restart forgot
every key and each worker held a different set, so enforced authentication was unusable
in any real deployment. DCC_API_KEYS closes that gap; these tests prove the bootstrap
actually produces a key that authenticates.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

import dcc.api_async as api
from dcc.api_async import app
from dcc.security.api_keys import generate_api_key, hash_api_key


TENANT_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


@pytest.fixture()
def fresh_client(monkeypatch):
    """A client with authentication ENFORCED.

    tests/conftest.py sets DCC_ALLOW_ANONYMOUS=1 for the legacy suite, so any test
    that asserts on 401/403 must clear it -- otherwise auth is open and the assertion
    is measuring FastAPI's query validation instead.
    """
    monkeypatch.delenv("DCC_ALLOW_ANONYMOUS", raising=False)
    return TestClient(app)


class TestBootstrap:
    def test_no_env_var_loads_nothing(self, monkeypatch):
        monkeypatch.delenv("DCC_API_KEYS", raising=False)
        assert api._bootstrap_api_keys() == 0

    def test_registered_hash_authenticates(self, monkeypatch, fresh_client):
        """The whole point: a key present in DCC_API_KEYS must actually work."""
        raw = generate_api_key()
        digest = hash_api_key(raw)
        monkeypatch.setenv("DCC_API_KEYS", f"{TENANT_A}:{digest}")
        assert api._bootstrap_api_keys() == 1

        client = fresh_client
        # 503 (no database) means auth passed and the route ran. 401/403 would mean
        # the key did not authenticate.
        response = client.get(f"/v2/overview?tenant_id={TENANT_A}", headers={"X-API-Key": raw})
        assert response.status_code not in (401, 403), response.text

    def test_unregistered_key_is_still_rejected(self, monkeypatch, fresh_client):
        raw = generate_api_key()
        monkeypatch.setenv("DCC_API_KEYS", f"{TENANT_A}:{hash_api_key(raw)}")
        api._bootstrap_api_keys()
        response = fresh_client.get(
            f"/v2/overview?tenant_id={TENANT_A}", headers={"X-API-Key": generate_api_key()}
        )
        assert response.status_code == 401

    def test_bootstrapped_key_cannot_cross_tenants(self, monkeypatch, fresh_client):
        raw = generate_api_key()
        monkeypatch.setenv("DCC_API_KEYS", f"{TENANT_A}:{hash_api_key(raw)}")
        api._bootstrap_api_keys()
        response = fresh_client.get(
            f"/v2/overview?tenant_id={TENANT_B}", headers={"X-API-Key": raw}
        )
        assert response.status_code == 403

    def test_multiple_entries_load(self, monkeypatch):
        a, b = generate_api_key(), generate_api_key()
        monkeypatch.setenv(
            "DCC_API_KEYS",
            f"tenant-a:{hash_api_key(a)},tenant-b:{hash_api_key(b)}",
        )
        assert api._bootstrap_api_keys() == 2

    def test_malformed_entry_fails_loudly(self, monkeypatch):
        """A silently skipped entry presents as "my key stopped working" with no clue."""
        monkeypatch.setenv("DCC_API_KEYS", "tenant-a-with-no-hash")
        with pytest.raises(RuntimeError, match="tenant_id:hash"):
            api._bootstrap_api_keys()

    def test_duplicate_entry_is_idempotent(self, monkeypatch):
        raw = generate_api_key()
        digest = hash_api_key(raw)
        monkeypatch.setenv("DCC_API_KEYS", f"tenant-a:{digest},tenant-a:{digest}")
        api._bootstrap_api_keys()
        # Two entries for the same hash must not create two registrations.
        matching = [k for k in api._API_KEYS.list_keys() if k.key_hash == digest]
        assert len(matching) == 1


class TestKeyCli:
    def test_create_prints_a_usable_entry(self):
        result = subprocess.run(
            [sys.executable, "-m", "dcc.keys_cli", "create", "--tenant", "tenant-a", "--hash-only"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        entry = result.stdout.strip()
        tenant, _, digest = entry.partition(":")
        assert tenant == "tenant-a"
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)

    def test_hash_only_does_not_leak_the_plaintext(self):
        result = subprocess.run(
            [sys.executable, "-m", "dcc.keys_cli", "create", "--tenant", "t", "--hash-only"],
            capture_output=True, text=True,
        )
        assert "dcc_" not in result.stdout, "the plaintext key must not appear in hash-only mode"

    def test_full_output_includes_the_key_once(self):
        result = subprocess.run(
            [sys.executable, "-m", "dcc.keys_cli", "create", "--tenant", "t"],
            capture_output=True, text=True,
        )
        assert "DCC_API_KEYS=" in result.stdout
        assert "shown ONCE" in result.stdout
