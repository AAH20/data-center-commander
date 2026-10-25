"""Tests for durable key configuration (DCC_API_KEYS) and the minting CLI.

The store is in-memory and per-process. Without a durable source, every restart forgot
every key and each worker held a different set, so enforced authentication was unusable
in any real deployment. DCC_API_KEYS closes that gap; these tests prove the bootstrap
actually produces a key that authenticates.
"""

from __future__ import annotations

import os
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
        # This asserts the LEGACY print-only path, which only exists when no database is
        # configured. It must clear DCC_DATABASE_URL from the child environment: with a
        # DSN, `create` correctly requires a UUID tenant and writes a durable row, so the
        # same command exits 2 and this test failed or passed depending on whether the
        # developer happened to export a DSN. A test that changes behaviour with the
        # ambient environment is not testing the code it claims to.
        env = {k: v for k, v in os.environ.items() if k != "DCC_DATABASE_URL"}
        result = subprocess.run(
            [sys.executable, "-m", "dcc.keys_cli", "create", "--tenant", "t"],
            capture_output=True, text=True, env=env,
        )
        assert "DCC_API_KEYS=" in result.stdout
        assert "shown ONCE" in result.stdout


class TestLockoutGuard:
    """Enforced auth with an empty store rejects everything and says nothing.

    That failure mode is silent by construction -- every request is a plain 401 -- so
    the process has to announce it at startup or an operator has no thread to pull.
    """

    def _clear(self, monkeypatch):
        monkeypatch.delenv("DCC_ALLOW_ANONYMOUS", raising=False)
        monkeypatch.delenv("DCC_API_KEYS", raising=False)
        monkeypatch.delenv("DCC_REQUIRE_KEYS", raising=False)
        monkeypatch.setattr(api, "_BOOTSTRAPPED_KEYS", 0, raising=False)
        store = api._API_KEYS
        store._keys.clear()
        store._hash_to_id.clear()
        # count() also consults the durable backend when a DSN is configured, so
        # clearing the in-memory dict is not enough to make the store empty. Detach it:
        # the lockout guard is a process-startup check, and this test is about the guard,
        # not about whatever rows a previous run left in the development database.
        monkeypatch.setattr(store, "_backend", None, raising=False)

    def test_warns_when_enforced_with_no_keys(self, monkeypatch, caplog):
        self._clear(monkeypatch)
        with caplog.at_level("WARNING", logger="dcc.auth"):
            api._warn_if_locked_out()
        assert any("NO API KEYS" in r.message for r in caplog.records), caplog.text

    def test_warning_names_the_remediation(self, monkeypatch, caplog):
        """A warning that does not say how to fix it is just noise."""
        self._clear(monkeypatch)
        with caplog.at_level("WARNING", logger="dcc.auth"):
            api._warn_if_locked_out()
        text = " ".join(r.message for r in caplog.records)
        assert "keys_cli" in text
        assert "DCC_API_KEYS" in text

    def test_require_keys_makes_it_fatal(self, monkeypatch):
        self._clear(monkeypatch)
        monkeypatch.setenv("DCC_REQUIRE_KEYS", "true")
        with pytest.raises(RuntimeError, match="no API keys"):
            api._warn_if_locked_out()

    def test_silent_when_anonymous(self, monkeypatch, caplog):
        self._clear(monkeypatch)
        monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
        with caplog.at_level("WARNING", logger="dcc.auth"):
            api._warn_if_locked_out()
        assert not [r for r in caplog.records if "NO API KEYS" in r.message]

    def test_silent_when_keys_exist(self, monkeypatch, caplog):
        self._clear(monkeypatch)
        raw = generate_api_key()
        api._API_KEYS.register_hash(tenant_id=TENANT_A, key_hash=hash_api_key(raw))
        with caplog.at_level("WARNING", logger="dcc.auth"):
            api._warn_if_locked_out()
        assert not [r for r in caplog.records if "NO API KEYS" in r.message]
