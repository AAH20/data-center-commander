"""Tests for the durable API key management CLI.

The CLI is the operator's only key-management surface once keys live in
``dcc.api_keys``, so these tests pin the properties an operator has to be able to
trust:

  * ``create`` prints the raw key exactly once and the store actually holds it;
  * nothing ever prints a hash -- the hash is a credential-adjacent value, and a
    listing that leaks it hands an attacker an offline oracle;
  * ``revoke`` is idempotent, because a retried revoke is normal operations;
  * ``verify`` cannot be used to enumerate keys: an unknown key and a key from
    another tenant produce byte-identical output;
  * ``prune`` changes nothing without ``--apply``;
  * every durable command refuses to run without ``DCC_DATABASE_URL`` instead of
    quietly using a process-local store that discards keys on exit.

Everything here uses an injected ``ApiKeyStore(dsn="")`` or a deleted
``DCC_DATABASE_URL``, so the suite never needs a database and never touches rows a
real deployment owns.
"""

from __future__ import annotations

import json
import re
import time

import pytest

from dcc import keys_cli
from dcc.security.api_keys import ApiKeyStore, hash_api_key

T1 = "11111111-1111-4111-8111-111111111111"
T2 = "22222222-2222-4222-8222-222222222222"

# ``dcc_`` + 64 hex chars: the only shape a raw key has, and the thing that must
# appear exactly once in create's output and never anywhere else.
RAW_KEY = re.compile(r"dcc_[0-9a-f]{64}")
# A bare 64-hex token is a hash. No command may print one.
HEX64 = re.compile(r"\b[0-9a-f]{64}\b")


@pytest.fixture
def store():
    s = ApiKeyStore(dsn="")
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _no_ambient_dsn(monkeypatch):
    """Never let the machine's DCC_DATABASE_URL decide what these tests mean."""
    monkeypatch.delenv("DCC_DATABASE_URL", raising=False)


def run(argv, store=None):
    return keys_cli.main(argv, store=store)


def _one_raw_key(text: str) -> str:
    matches = RAW_KEY.findall(text)
    assert len(matches) == 1, f"expected exactly one raw key, got {matches!r}"
    return matches[0]


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    def test_prints_the_raw_key_exactly_once(self, store, capsys):
        rc = run(
            ["create", "--tenant", T1, "--label", "ops", "--expires-in-days", "7",
             "--scopes", "read,write"],
            store=store,
        )
        captured = capsys.readouterr()
        assert rc == 0, captured.err

        raw = _one_raw_key(captured.out)
        assert captured.out.count(raw) == 1
        assert "shown ONCE" in captured.out
        # The hash of the key it just printed must not be in the output.
        assert hash_api_key(raw) not in captured.out
        # And the raw key must never be echoed to stderr either.
        assert raw not in captured.err

    def test_the_store_holds_the_key_it_printed(self, store, capsys):
        rc = run(
            ["create", "--tenant", T1, "--label", "ci", "--scopes", "read",
             "--expires-in-days", "30"],
            store=store,
        )
        out = capsys.readouterr().out
        assert rc == 0
        raw = _one_raw_key(out)

        assert store.count() == 1
        record = store.verify(raw)  # authenticates: the key was really stored
        assert record.tenant_id == T1
        assert record.name == "ci"
        assert record.scopes == ["read"]
        assert record.created_by == "cli:keys_cli"
        assert record.expires_at is not None
        assert record.expires_at > time.time()
        assert record.id in out

    def test_refuses_a_non_uuid_tenant_when_durable(self, store, capsys):
        rc = run(["create", "--tenant", "tenant-a"], store=store)
        captured = capsys.readouterr()
        assert rc == keys_cli.EXIT_USAGE
        assert "UUID" in captured.err
        assert store.count() == 0

    def test_refuses_a_non_uuid_tenant_before_touching_the_database(self, monkeypatch, capsys):
        # A DSN is configured but points nowhere. Validation must happen first, so the
        # command fails on the argument rather than on a connection timeout.
        monkeypatch.setenv("DCC_DATABASE_URL", "postgresql://127.0.0.1:1/absent")
        rc = run(["create", "--tenant", "not-a-uuid"])
        captured = capsys.readouterr()
        assert rc == keys_cli.EXIT_USAGE
        assert "UUID" in captured.err
        assert "Connection" not in captured.err

    def test_legacy_hash_only_entry_still_works(self, capsys):
        rc = run(["create", "--tenant", "tenant-a", "--hash-only"])
        out = capsys.readouterr().out.strip()
        assert rc == 0
        tenant, _, digest = out.partition(":")
        assert tenant == "tenant-a"
        assert len(digest) == 64 and HEX64.match(digest)
        assert "dcc_" not in out, "hash-only must not print the plaintext key"

    def test_print_env_needs_no_database(self, capsys):
        rc = run(["print-env", "--tenant", "tenant-a", "--label", "ops"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "DCC_API_KEYS=" in out
        assert "shown ONCE" in out
        # The raw key is printed once, and the entry carries only the hash.
        raw = _one_raw_key(out)
        assert out.count(raw) == 1
        assert hash_api_key(raw) in out


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


class TestList:
    def _seed(self, store):
        ra, a = store.create(name="first", tenant_id=T1, scopes=["read"])
        rb, b = store.create(name="second", tenant_id=T1, scopes=["read", "write"])
        store.revoke(b.id)
        return a, ra, b, rb

    def test_never_prints_a_hash_or_a_raw_key(self, store, capsys):
        a, ra, b, rb = self._seed(store)

        rc = run(["list", "--tenant", T1], store=store)
        out = capsys.readouterr().out
        assert rc == 0

        for raw in (ra, rb):
            assert raw not in out
            assert hash_api_key(raw) not in out
        assert not RAW_KEY.search(out)
        assert not HEX64.search(out), "a hash is credential-adjacent; list must not print it"

        # But it does print what an operator needs.
        assert a.id in out and b.id in out
        assert "first" in out and "second" in out
        assert T1 in out

    def test_shows_revocation_and_expiry(self, store, capsys):
        _, live = store.create(name="live", tenant_id=T1)
        _, dead = store.create(name="dead", tenant_id=T1, expires_at=time.time() - 60)
        store.revoke(live.id)

        rc = run(["list", "--tenant", T1], store=store)
        out = capsys.readouterr().out
        assert rc == 0

        def row(key_id):
            lines = [line for line in out.splitlines() if line.startswith(key_id)]
            assert lines, out
            return lines[0]

        assert "yes" in row(live.id), "revoked key must read as revoked"
        assert "no" in row(dead.id), "expired is not revoked; the expiry column says so"
        # The expiry timestamp is shown for the expired key; the live one has none.
        assert keys_cli._ts(dead.expires_at) in row(dead.id)
        assert keys_cli._ts(live.expires_at) == "never"

    def test_json_output_is_secret_free(self, store, capsys):
        raw, _ = store.create(name="ops", tenant_id=T1, scopes=["read"])
        rc = run(["list", "--tenant", T1, "--json"], store=store)
        out = capsys.readouterr().out
        assert rc == 0

        payload = json.loads(out)
        assert len(payload) == 1
        entry = payload[0]
        assert set(entry) == {
            "id", "tenant_id", "label", "created_at", "expires_at",
            "revoked", "last_used_at", "scopes",
        }
        assert entry["tenant_id"] == T1
        assert entry["label"] == "ops"
        assert "key_hash" not in entry
        assert raw not in out
        assert not HEX64.search(out)

    def test_empty_store_says_so(self, store, capsys):
        rc = run(["list", "--tenant", T1], store=store)
        out = capsys.readouterr().out
        assert rc == 0
        assert "no keys" in out

    def test_rejects_a_non_uuid_tenant_on_a_durable_store(self, monkeypatch, capsys):
        # A DSN is configured but points nowhere: the tenant rule must be enforced
        # before any connection is attempted, so this never needs a database.
        monkeypatch.setenv("DCC_DATABASE_URL", "postgresql://127.0.0.1:1/absent")
        rc = run(["list", "--tenant", "tenant-a"])
        captured = capsys.readouterr()
        assert rc == keys_cli.EXIT_USAGE
        assert "UUID" in captured.err
        assert "Connection" not in captured.err


# ---------------------------------------------------------------------------
# revoke
# ---------------------------------------------------------------------------


class TestRevoke:
    def test_revokes_and_is_idempotent(self, store, capsys):
        raw, _ = store.create(name="ops", tenant_id=T1)
        key_id = store.list_keys()[0].id  # read it before revoking; verify() refuses after

        rc = run(["revoke", "--id", key_id], store=store)
        first = capsys.readouterr()
        assert rc == 0
        assert "revoked" in first.out
        assert raw not in first.out
        with pytest.raises(Exception):
            store.verify(raw)

        # Second call: still success, and it says nothing changed.
        rc = run(["revoke", "--id", key_id], store=store)
        second = capsys.readouterr()
        assert rc == 0, second.err
        assert "already revoked" in second.out
        assert store.count() == 1, "revoking must not delete the audit row"

    def test_unknown_id_fails_clearly(self, store, capsys):
        rc = run(["revoke", "--id", "33333333-3333-4333-8333-333333333333"], store=store)
        captured = capsys.readouterr()
        assert rc == keys_cli.EXIT_FAILED
        assert "no API key" in captured.err


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


class TestVerify:
    def test_reports_the_tenant_of_a_valid_key(self, store, capsys):
        raw, _ = store.create(name="ops", tenant_id=T1)
        rc = run(["verify", "--key", raw], store=store)
        out = capsys.readouterr().out
        assert rc == 0
        assert "authenticated" in out
        assert T1 in out
        assert raw not in out
        assert not HEX64.search(out)

    def test_unknown_and_wrong_tenant_are_indistinguishable(self, store, capsys):
        raw, _ = store.create(name="t1-key", tenant_id=T1)

        rc_other = run(["verify", "--key", raw, "--tenant", T2], store=store)
        other = capsys.readouterr()

        never = "dcc_" + "0" * 64
        rc_unknown = run(["verify", "--key", never], store=store)
        unknown = capsys.readouterr()

        assert rc_other == rc_unknown == keys_cli.EXIT_FAILED
        # Byte-identical: anything else is an enumeration oracle telling the holder
        # of a stolen key that it is live for a different tenant.
        assert other.err == unknown.err
        assert other.out == unknown.out == ""
        assert T1 not in other.err and T2 not in other.err

    def test_reports_why_a_revoked_key_fails(self, store, capsys):
        raw, _ = store.create(name="ops", tenant_id=T1)
        key_id = store.list_keys()[0].id
        store.revoke(key_id)

        rc = run(["verify", "--key", raw], store=store)
        err = capsys.readouterr().err
        assert rc == keys_cli.EXIT_FAILED
        assert "revoked" in err

    def test_reports_why_an_expired_key_fails(self, store, capsys):
        raw, _ = store.create(name="ops", tenant_id=T1, expires_at=time.time() - 1)
        rc = run(["verify", "--key", raw], store=store)
        err = capsys.readouterr().err
        assert rc == keys_cli.EXIT_FAILED
        assert "expired" in err


# ---------------------------------------------------------------------------
# rotate
# ---------------------------------------------------------------------------


class TestRotate:
    def test_issues_a_replacement_and_revokes_the_old_key(self, store, capsys):
        old_raw, _ = store.create(name="ops", tenant_id=T1, scopes=["read"])
        old_id = store.list_keys()[0].id

        rc = run(["rotate", "--id", old_id, "--expires-in-days", "5"], store=store)
        out = capsys.readouterr().out
        assert rc == 0

        new_raw = _one_raw_key(out)
        assert new_raw != old_raw
        assert old_raw not in out
        assert "shown ONCE" in out

        assert store.count() == 2, "rotation keeps the old row for the audit trail"
        record = store.verify(new_raw)
        assert record.tenant_id == T1
        assert record.scopes == ["read"]
        assert record.name == "ops"
        assert record.expires_at is not None

        old = store.get(old_id, T1)
        assert old is not None and old.revoked
        with pytest.raises(Exception):
            store.verify(old_raw)


# ---------------------------------------------------------------------------
# prune
# ---------------------------------------------------------------------------


class TestPrune:
    def _seed(self, store):
        _, live = store.create(name="live", tenant_id=T1)
        _, revoked = store.create(name="revoked", tenant_id=T1)
        _, expired = store.create(name="expired", tenant_id=T1, expires_at=time.time() - 3600)
        store.revoke(revoked.id)
        return live, revoked, expired

    def test_dry_run_changes_nothing(self, store, capsys):
        live, revoked, expired = self._seed(store)
        before = store.count()

        rc = run(["prune", "--tenant", T1], store=store)
        out = capsys.readouterr().out
        assert rc == 0
        assert store.count() == before
        assert out.count("would delete") == 2
        assert "nothing was changed" in out
        assert "live" not in out

        # Explicit --dry-run behaves the same way.
        rc = run(["prune", "--tenant", T1, "--dry-run"], store=store)
        capsys.readouterr()
        assert rc == 0
        assert store.count() == before

    def test_apply_deletes_only_dead_keys(self, store, capsys):
        live, revoked, expired = self._seed(store)

        rc = run(["prune", "--tenant", T1, "--apply"], store=store)
        out = capsys.readouterr().out
        assert rc == 0
        assert "deleted 2 of 2" in out

        remaining = {k.id for k in store.list_keys()}
        assert remaining == {live.id}
        assert revoked.id not in remaining and expired.id not in remaining

    def test_expired_flag_leaves_revoked_rows_alone(self, store, capsys):
        live, revoked, expired = self._seed(store)

        rc = run(["prune", "--tenant", T1, "--expired", "--apply"], store=store)
        out = capsys.readouterr().out
        assert rc == 0
        assert "deleted 1 of 1" in out

        remaining = {k.id for k in store.list_keys()}
        assert remaining == {live.id, revoked.id}

    def test_nothing_to_prune_is_not_an_error(self, store, capsys):
        store.create(name="live", tenant_id=T1)
        rc = run(["prune", "--tenant", T1, "--apply"], store=store)
        out = capsys.readouterr().out
        assert rc == 0
        assert "nothing to prune" in out


# ---------------------------------------------------------------------------
# no database
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["create", "--tenant", T1, "--label", "ops"],
        ["list", "--tenant", T1],
        ["revoke", "--id", "33333333-3333-4333-8333-333333333333"],
        ["verify", "--key", "dcc_" + "0" * 64],
        ["rotate", "--id", "33333333-3333-4333-8333-333333333333"],
        ["prune", "--tenant", T1],
    ],
)
def test_durable_commands_require_a_database(argv, capsys):
    rc = run(argv)
    captured = capsys.readouterr()
    assert rc == keys_cli.EXIT_USAGE, captured.out
    assert "DCC_DATABASE_URL" in captured.err
    assert "process-local" in captured.err
    assert argv[0] in captured.err


def test_help_states_which_commands_need_a_database(capsys):
    with pytest.raises(SystemExit) as excinfo:
        run(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "REQUIRE DCC_DATABASE_URL" in out
    assert "need NO database" in out
    for command in ("create", "list", "revoke", "verify", "rotate", "prune", "print-env"):
        assert command in out


def test_no_subcommand_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as excinfo:
        run([])
    assert excinfo.value.code == 2