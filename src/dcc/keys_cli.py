"""Operate the API key store: issue, inspect, revoke, rotate, prune.

``ApiKeyStore`` writes to ``dcc.api_keys`` in PostgreSQL whenever a DSN is
configured, so keys survive a restart and every worker sees the same set. That makes
this CLI the operator's real key-management surface, and it talks to the store
directly instead of printing a string for someone to paste into a deployment.

    python -m dcc.keys_cli create --tenant <uuid> --label ops --expires-in-days 90
    python -m dcc.keys_cli list   --tenant <uuid>
    python -m dcc.keys_cli verify --key dcc_...
    python -m dcc.keys_cli revoke --id <key-uuid>
    python -m dcc.keys_cli rotate --id <key-uuid> --expires-in-days 90
    python -m dcc.keys_cli prune  --tenant <uuid> --dry-run

Two properties this file is built around:

* **The raw key exists once.** It is printed to stdout, once, by ``create`` and
  ``rotate`` -- never written to the database, never logged, never echoed by
  ``list``. Only its SHA-256 hash is stored, and that hash is itself
  credential-adjacent, so no command prints it either.
* **No silent degradation.** Without ``DCC_DATABASE_URL`` the store is
  process-local: a key minted today is gone when the process exits. Every durable
  command therefore refuses to run and says why, instead of appearing to succeed.

``print-env`` (also reachable as ``create --hash-only``) keeps the old print-only
behaviour for the ``DCC_API_KEYS`` bootstrap path. It needs no database because it
writes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Sequence

from .security.api_keys import (
    ApiKey,
    ApiKeyError,
    ApiKeyExpiredError,
    ApiKeyInvalidError,
    ApiKeyRevokedError,
    ApiKeyStore,
    generate_api_key,
    hash_api_key,
)

__all__ = ["main"]

PROG = "dcc.keys_cli"

EXIT_OK = 0
EXIT_FAILED = 1  # the command ran and the outcome is "no" (not found, not valid)
EXIT_USAGE = 2  # the command cannot be run as asked (bad id, no database)

# Every authentication failure that says nothing about *which* key was presented.
# An unknown key and a key that belongs to another tenant must be indistinguishable:
# otherwise `verify` becomes an enumeration oracle that confirms a captured key is
# live somewhere, and tells the holder which tenant to aim it at.
_AUTH_UNKNOWN = "invalid API key"

# Set on records this CLI creates, so the audit trail says where a key came from.
_CREATED_BY = "cli:keys_cli"

_DURABLE_COMMANDS = ("create", "list", "revoke", "verify", "rotate", "prune")

_EPILOG = """\
commands that read or write dcc.api_keys -- these REQUIRE DCC_DATABASE_URL:
  create    issue a key, print it once
  list      show keys without secrets
  revoke    revoke one key (idempotent)
  verify    check a key and report its tenant
  rotate    issue a replacement and revoke the old key
  prune     delete revoked/expired rows (dry run unless --apply)

commands that need NO database:
  print-env print a legacy  DCC_API_KEYS="tenant:hash"  entry for env bootstrap
            (also reachable as: create --hash-only)

Without DCC_DATABASE_URL a store is process-local, so a key minted in this process
would be discarded the moment it exits and would never reach another worker. Rather
than pretend otherwise, every durable command exits 2 and explains.

Set it for a real run, e.g.:
  export DCC_DATABASE_URL=postgresql://localhost:5432/dcc_demo_local

The raw key is printed exactly once, by create/rotate. Only its SHA-256 hash is
stored, so a lost key cannot be recovered -- issue a new one and revoke the old.
"""


class CliError(Exception):
    """A failure with an operator-facing message and a process exit code."""

    def __init__(self, message: str, code: int = EXIT_USAGE) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def _emit(text: str = "") -> None:
    print(text)


def _warn(text: str) -> None:
    print(f"warning: {text}", file=sys.stderr)


def _dsn() -> str:
    return (os.environ.get("DCC_DATABASE_URL") or "").strip()


def _as_uuid(value: Any) -> Optional[str]:
    """Canonical UUID string, or None. Mirrors the store's own check."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


def _ts(value: Optional[float]) -> str:
    if value is None:
        return "never"
    return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _days(value: Optional[int]) -> Optional[float]:
    """``--expires-in-days`` -> absolute epoch seconds."""
    if value is None:
        return None
    if value <= 0:
        raise CliError("--expires-in-days must be a positive number of days")
    return time.time() + value * 86400


def _scopes(values: Optional[Sequence[str]]) -> List[str]:
    """``--scopes a,b`` (repeatable) -> ordered, de-duplicated list."""
    out: List[str] = []
    for chunk in values or ():
        for part in str(chunk).split(","):
            scope = part.strip()
            if scope and scope not in out:
                out.append(scope)
    return out


def _no_database(command: str) -> CliError:
    return CliError(
        f"'{command}' needs a database: DCC_DATABASE_URL is not set. API keys live in "
        "dcc.api_keys, and without a DSN the store is process-local -- a key minted "
        "now would disappear when this process exits and would never be visible to "
        "another worker, which is the defect durable keys exist to fix. Set "
        "DCC_DATABASE_URL (for example postgresql://localhost:5432/dcc_demo_local), "
        "or use 'print-env' for a legacy DCC_API_KEYS entry.",
        code=EXIT_USAGE,
    )


@contextmanager
def _store_for(command: str, injected: Optional[ApiKeyStore]) -> Iterator[ApiKeyStore]:
    """Open the store for one command and close it if this file created it.

    Tests pass a store in; operators get one built from ``DCC_DATABASE_URL``. The
    injected path exists so a memory store can be exercised without a database, not
    so a deployment can run without one: the CLI itself only ever builds a store
    when a DSN is present.
    """
    if injected is not None:
        yield injected
        return
    dsn = _dsn()
    if not dsn:
        raise _no_database(command)
    store = ApiKeyStore(dsn=dsn)
    try:
        yield store
    finally:
        store.close()


def _check_tenant(store: ApiKeyStore, value: str, *, required: bool) -> Optional[str]:
    """Validate a tenant argument against what this backend can hold."""
    if value is None:
        if required:
            raise CliError("--tenant is required for this command")
        return None
    canonical = _as_uuid(value)
    if canonical is None:
        if store.backend == "postgres":
            raise CliError(
                f"--tenant must be a UUID (got {value!r}): dcc.api_keys.tenant_id is a "
                "uuid column with a foreign key to dcc.tenants, so a non-UUID tenant "
                "cannot be stored. 'print-env' still accepts one for the legacy "
                "DCC_API_KEYS path.",
                code=EXIT_USAGE,
            )
        return str(value)
    return canonical


def _check_key_id(store: ApiKeyStore, value: str) -> str:
    if not value or not str(value).strip():
        raise CliError("--id is required")
    value = str(value).strip()
    if store.backend == "postgres":
        canonical = _as_uuid(value)
        if canonical is None:
            raise CliError(
                f"--id must be the key's UUID (got {value!r}); see 'list --tenant <uuid>'"
            )
        return canonical
    return value


def _record_json(record: ApiKey) -> Dict[str, Any]:
    """The only fields this CLI will ever print for a key.

    Built explicitly rather than from ``to_dict()`` so that adding a field to the
    record -- or a caller passing ``include_hash=True`` -- cannot leak a digest
    through the CLI by accident.
    """
    return {
        "id": record.id,
        "tenant_id": record.tenant_id,
        "label": record.name,
        "created_at": _ts(record.created_at) if record.created_at else None,
        "expires_at": _ts(record.expires_at) if record.expires_at else None,
        "revoked": bool(record.revoked),
        "last_used_at": _ts(record.last_used_at) if record.last_used_at else None,
        "scopes": list(record.scopes),
    }


def _print_key_table(records: Sequence[ApiKey]) -> None:
    if not records:
        _emit("no keys")
        return
    header = ("ID", "TENANT", "LABEL", "CREATED", "EXPIRES", "REVOKED", "LAST USED", "SCOPES")
    rows = [
        (
            r.id,
            r.tenant_id,
            r.name or "-",
            _ts(r.created_at),
            _ts(r.expires_at),
            "yes" if r.revoked else "no",
            _ts(r.last_used_at),
            ",".join(r.scopes) or "-",
        )
        for r in records
    ]
    widths = [max(len(header[i]), *(len(row[i]) for row in rows)) for i in range(len(header))]
    _emit("  ".join(header[i].ljust(widths[i]) for i in range(len(header))))
    _emit("  ".join("-" * widths[i] for i in range(len(header))))
    for row in rows:
        _emit("  ".join(row[i].ljust(widths[i]) for i in range(len(header))))


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def _print_env_block(tenant: str, label: str, *, hash_only: bool) -> int:
    """The pre-durability behaviour, preserved verbatim for the bootstrap path."""
    raw = generate_api_key()
    digest = hash_api_key(raw)
    entry = f"{tenant}:{digest}"

    if hash_only:
        _emit(entry)
        return EXIT_OK

    _emit("API key created. The key is shown ONCE and cannot be recovered.")
    _emit()
    _emit(f"  name  : {label}")
    _emit(f"  tenant: {tenant}")
    _emit(f"  key   : {raw}")
    _emit()
    _emit("Install it durably by adding this to DCC_API_KEYS (hashes only):")
    _emit()
    _emit(f'  DCC_API_KEYS="{entry}"')
    _emit()
    _emit("For the bundled console, also set DCC_UI_API_KEY to the key above.")
    return EXIT_OK


def _cmd_create(args: argparse.Namespace, injected: Optional[ApiKeyStore]) -> int:
    if args.hash_only:
        return _print_env_block(args.tenant, args.label, hash_only=True)

    tenant = _as_uuid(args.tenant)
    if tenant is None:
        if injected is not None or _dsn():
            raise CliError(
                f"--tenant must be a UUID (got {args.tenant!r}). dcc.api_keys.tenant_id "
                "is a uuid with a foreign key to dcc.tenants, so a durable key cannot "
                "belong to a non-UUID tenant. Use 'print-env' if you want the legacy "
                "DCC_API_KEYS entry instead.",
                code=EXIT_USAGE,
            )
        # No database and no UUID: nothing durable can be claimed either way, so the
        # old print-only path still applies -- with a warning, because the smoke test
        # suite and muscle memory both rely on it and neither should believe the
        # output is a stored key.
        _warn(
            f"{args.tenant!r} is not a UUID and DCC_DATABASE_URL is not set: printing a "
            "legacy DCC_API_KEYS entry. Nothing was written to a database."
        )
        return _print_env_block(args.tenant, args.label, hash_only=False)

    expires_at = _days(args.expires_in_days)
    scopes = _scopes(args.scopes)

    with _store_for("create", injected) as store:
        raw_key, record = store.create(
            name=args.label,
            tenant_id=tenant,
            scopes=scopes,
            expires_at=expires_at,
            created_by=_CREATED_BY,
        )
        stored = store.get(record.id, tenant)
        if stored is None:
            # The store reports this as an error on the durable path; check anyway,
            # because handing out a credential that authenticates nowhere is worse
            # than failing.
            raise CliError(
                f"key {record.id} was written but cannot be read back; do not use it",
                code=EXIT_FAILED,
            )

        _emit("API key issued and stored in dcc.api_keys.")
        _emit()
        _emit(f"  id      : {record.id}")
        _emit(f"  tenant  : {record.tenant_id}")
        _emit(f"  label   : {record.name or '-'}")
        _emit(f"  scopes  : {','.join(record.scopes) or '-'}")
        _emit(f"  created : {_ts(record.created_at)}")
        _emit(f"  expires : {_ts(record.expires_at)}")
        _emit(f"  backend : {store.backend}")
        _emit()
        _emit(f"  key     : {raw_key}")
        _emit()
        _emit("This key is shown ONCE and cannot be recovered: only its SHA-256 hash is")
        _emit("stored. Copy it into your secret manager now; to replace it, run 'rotate'.")
    return EXIT_OK


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def _cmd_list(args: argparse.Namespace, injected: Optional[ApiKeyStore]) -> int:
    with _store_for("list", injected) as store:
        tenant = _check_tenant(store, args.tenant, required=False)
        records = store.list_keys(tenant)

        if tenant is None and store.backend == "postgres":
            if records:
                # The only way to see rows with no tenant bound is a role that bypasses
                # row level security, so say that rather than implying the listing is
                # scoped: it is not.
                _warn(
                    "listing with no --tenant: this role bypasses row level security "
                    "(superuser or BYPASSRLS), so these rows span every tenant. Use "
                    "--tenant <uuid> for a scoped listing."
                )
            else:
                try:
                    total = store.count()
                except Exception:  # noqa: BLE001 - the note is advisory only
                    total = 0
                _warn(
                    "no --tenant given. dcc.api_keys is protected by FORCE row level "
                    "security, so a listing with no tenant bound sees 0 rows by design "
                    f"(the store reports {total} key(s) across all tenants). "
                    "Pass --tenant <uuid> for a real listing."
                )

        if args.json:
            _emit(json.dumps([_record_json(r) for r in records], indent=2, sort_keys=True))
            return EXIT_OK

        if not records:
            _emit(f"no keys{f' for tenant {tenant}' if tenant else ''}")
            return EXIT_OK
        _print_key_table(records)
        _emit()
        _emit(f"{len(records)} key(s). Hashes and raw keys are never printed.")
    return EXIT_OK


# ---------------------------------------------------------------------------
# revoke
# ---------------------------------------------------------------------------


def _cmd_revoke(args: argparse.Namespace, injected: Optional[ApiKeyStore]) -> int:
    with _store_for("revoke", injected) as store:
        tenant = _check_tenant(store, args.tenant, required=False)
        key_id = _check_key_id(store, args.id)
        record = store.get(key_id, tenant)
        if record is None:
            raise CliError(
                f"no API key with id {key_id}"
                + (f" for tenant {tenant}" if tenant else "")
                + ". Use 'list --tenant <uuid>' to find it.",
                code=EXIT_FAILED,
            )
        if record.revoked:
            # Idempotent: revoking twice is an operator retry, not an error, and the
            # store keeps the first revocation time so the audit trail stays honest.
            _emit(f"key {record.id} is already revoked; nothing changed.")
            return EXIT_OK

        if not store.revoke(record.id, record.tenant_id):
            raise CliError(
                f"revoke of key {record.id} was attempted but the store reported no "
                "row updated; the key may already be gone. Check 'list'.",
                code=EXIT_FAILED,
            )

        after = store.get(record.id, record.tenant_id)
        if after is None or not after.revoked:
            raise CliError(
                f"revoke of key {record.id} did not take effect: it still reads as "
                "active. Treat the key as compromised and investigate the database.",
                code=EXIT_FAILED,
            )

        _emit(f"revoked key {record.id} (tenant {record.tenant_id}, label {record.name or '-'}).")
        _emit("It stops authenticating on the next request, in every worker.")
    return EXIT_OK


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


def _auth_failure(reason: str) -> int:
    print(f"not authenticated: {reason}", file=sys.stderr)
    return EXIT_FAILED


def _cmd_verify(args: argparse.Namespace, injected: Optional[ApiKeyStore]) -> int:
    req_tenant = _as_uuid(args.tenant) if args.tenant else None
    if args.tenant is not None and req_tenant is None:
        raise CliError(f"--tenant must be a UUID (got {args.tenant!r})")

    with _store_for("verify", injected) as store:
        try:
            record = store.verify(args.key)
        except ApiKeyRevokedError:
            return _auth_failure("API key has been revoked")
        except ApiKeyExpiredError:
            return _auth_failure("API key has expired")
        except ApiKeyInvalidError as exc:
            if "unavailable" in str(exc).lower():
                # Not the caller's fault, and saying "invalid key" here would send an
                # operator hunting for a problem with a credential that is fine.
                return _auth_failure("API key store unavailable")
            return _auth_failure(_AUTH_UNKNOWN)
        except ApiKeyError:
            return _auth_failure(_AUTH_UNKNOWN)

        if req_tenant is not None and record.tenant_id != req_tenant:
            # Deliberately identical to an unknown key. Saying "this key belongs to
            # another tenant" would confirm a captured key is live and name its owner.
            return _auth_failure(_AUTH_UNKNOWN)

        _emit("authenticated")
        _emit(f"  tenant    : {record.tenant_id}")
        _emit(f"  id        : {record.id}")
        _emit(f"  label     : {record.name or '-'}")
        _emit(f"  scopes    : {','.join(record.scopes) or '-'}")
        _emit(f"  created   : {_ts(record.created_at)}")
        _emit(f"  expires   : {_ts(record.expires_at)}")
    return EXIT_OK


# ---------------------------------------------------------------------------
# rotate
# ---------------------------------------------------------------------------


def _cmd_rotate(args: argparse.Namespace, injected: Optional[ApiKeyStore]) -> int:
    with _store_for("rotate", injected) as store:
        tenant = _check_tenant(store, args.tenant, required=False)
        key_id = _check_key_id(store, args.id)
        old = store.get(key_id, tenant)
        if old is None:
            raise CliError(
                f"no API key with id {key_id}. Use 'list --tenant <uuid>' to find it.",
                code=EXIT_FAILED,
            )

        if args.expires_in_days is not None:
            expires_at = _days(args.expires_in_days)
        else:
            expires_at = old.expires_at
            if expires_at is not None and expires_at <= time.time():
                raise CliError(
                    f"key {old.id} expired at {_ts(expires_at)}; a replacement cannot "
                    "inherit a dead expiry. Pass --expires-in-days to set a new one.",
                    code=EXIT_USAGE,
                )

        # Create first: if the insert fails, the old key is still live and the
        # operator still has a working credential.
        raw_key, record = store.create(
            name=old.name,
            tenant_id=old.tenant_id,
            scopes=old.scopes,
            expires_at=expires_at,
            created_by=f"{_CREATED_BY}:rotate",
        )

        revoked = store.revoke(old.id, old.tenant_id)
        still_live = store.get(old.id, old.tenant_id)
        if not revoked or (still_live is not None and not still_live.revoked):
            # The replacement exists but the old key still works: say so loudly and
            # exit non-zero. Printing the new key is still right -- it is the only
            # copy -- but the caller must not believe rotation is complete.
            _emit(f"  key     : {raw_key}")
            raise CliError(
                f"replacement {record.id} was issued, but revoking old key {old.id} "
                "FAILED -- both keys are live. Revoke the old key manually.",
                code=EXIT_FAILED,
            )

        _emit(f"Rotated key {old.id} -> {record.id}.")
        _emit()
        _emit(f"  id      : {record.id}")
        _emit(f"  tenant  : {record.tenant_id}")
        _emit(f"  label   : {record.name or '-'}")
        _emit(f"  scopes  : {','.join(record.scopes) or '-'}")
        _emit(f"  expires : {_ts(record.expires_at)}")
        _emit(f"  revoked : {old.id} (the previous key, immediately)")
        _emit()
        _emit(f"  key     : {raw_key}")
        _emit()
        _emit("This key is shown ONCE and cannot be recovered: only its SHA-256 hash is")
        _emit("stored. The previous key no longer authenticates.")
    return EXIT_OK


# ---------------------------------------------------------------------------
# prune
# ---------------------------------------------------------------------------


def _cmd_prune(args: argparse.Namespace, injected: Optional[ApiKeyStore]) -> int:
    # Dry run is the default. Deleting audit rows is not something to do by fat-finger.
    apply_changes = bool(args.apply) and not bool(args.dry_run)

    with _store_for("prune", injected) as store:
        tenant = _check_tenant(store, args.tenant, required=False)
        if tenant is None and store.backend == "postgres":
            raise CliError(
                "prune needs --tenant: dcc.api_keys is under FORCE row level security, "
                "so a delete with no tenant bound matches no rows (and a delete that "
                "silently matches nothing is worse than one that refuses). "
                "Pass --tenant <uuid>.",
                code=EXIT_USAGE,
            )

        records = store.list_keys(tenant)
        targets: List[tuple[ApiKey, str]] = []
        for record in records:
            if record.is_active:
                # Never touch a live key, whatever the flags say.
                continue
            if args.expired:
                if not record.is_expired:
                    continue
                reason = "expired"
            else:
                reason = "revoked" if record.revoked else "expired"
            targets.append((record, reason))

        deleted = 0
        for record, reason in targets:
            if apply_changes:
                if store.delete(record.id, record.tenant_id if store.backend == "postgres" else tenant):
                    deleted += 1
                    _emit(f"deleted {record.id}  tenant={record.tenant_id}  label={record.name or '-'}  ({reason})")
                else:
                    _emit(f"could not delete {record.id} ({reason})")
            else:
                _emit(
                    f"would delete {record.id}  tenant={record.tenant_id}  "
                    f"label={record.name or '-'}  ({reason})"
                )

        _emit()
        if not targets:
            _emit("nothing to prune.")
            return EXIT_OK
        if apply_changes:
            _emit(f"deleted {deleted} of {len(targets)} key(s).")
        else:
            _emit(
                f"dry run: {len(targets)} key(s) would be deleted; nothing was changed. "
                "Re-run with --apply to delete them."
            )
    return EXIT_OK


# ---------------------------------------------------------------------------
# print-env (legacy)
# ---------------------------------------------------------------------------


def _cmd_print_env(args: argparse.Namespace, injected: Optional[ApiKeyStore]) -> int:
    return _print_env_block(args.tenant, args.label, hash_only=bool(args.hash_only))


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Issue, inspect, revoke, rotate and prune API keys in the durable store "
            "(dcc.api_keys)."
        ),
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    def _common(p: argparse.ArgumentParser, *, label_flag: bool = True) -> None:
        if label_flag:
            p.add_argument(
                "--label",
                "--name",
                dest="label",
                default="ops",
                metavar="TEXT",
                help="human label for the key (default: ops; --name is accepted as an alias)",
            )

    create = sub.add_parser(
        "create",
        help="issue a key, write it to the store, print it once [needs a database]",
        description=(
            "Issue a key for a tenant and store it in dcc.api_keys. The raw key is "
            "printed exactly once and cannot be recovered. Requires DCC_DATABASE_URL."
        ),
    )
    create.add_argument("--tenant", required=True, help="tenant UUID the key belongs to")
    _common(create)
    create.add_argument(
        "--expires-in-days", type=int, metavar="N", help="key expires N days from now (default: never)"
    )
    create.add_argument(
        "--scopes",
        action="append",
        metavar="a,b",
        help="comma-separated scopes, repeatable (default: none)",
    )
    create.add_argument(
        "--hash-only",
        action="store_true",
        help="legacy mode: print only the 'tenant:hash' DCC_API_KEYS entry, store nothing",
    )
    create.set_defaults(handler=_cmd_create)

    listing = sub.add_parser(
        "list",
        help="show keys without hashes or secrets [needs a database]",
        description=(
            "Print id, tenant, label, created, expires, revoked, last used and scopes. "
            "Never prints a key hash or a raw key. Requires DCC_DATABASE_URL. Under row "
            "level security a listing needs --tenant."
        ),
    )
    listing.add_argument("--tenant", help="only keys for this tenant UUID")
    listing.add_argument("--json", action="store_true", help="machine-readable output")
    listing.set_defaults(handler=_cmd_list)

    revoke = sub.add_parser(
        "revoke",
        help="revoke one key, idempotently [needs a database]",
        description=(
            "Set revoked_at on a key. Idempotent: revoking an already-revoked key "
            "reports that and exits 0. Requires DCC_DATABASE_URL."
        ),
    )
    revoke.add_argument("--id", required=True, help="key UUID (see 'list')")
    revoke.add_argument("--tenant", help="tenant UUID, to avoid a cross-tenant lookup")
    revoke.set_defaults(handler=_cmd_revoke)

    verify = sub.add_parser(
        "verify",
        help="check whether a raw key authenticates [needs a database]",
        description=(
            "Report whether a key authenticates and which tenant it belongs to. "
            "An unknown key and a key from another tenant produce the same message, so "
            "this cannot be used to enumerate keys. Requires DCC_DATABASE_URL."
        ),
    )
    verify.add_argument("--key", required=True, help="the raw key to check")
    verify.add_argument(
        "--tenant",
        help="also require the key to belong to this tenant UUID (mismatch reports "
        "exactly like an unknown key)",
    )
    verify.set_defaults(handler=_cmd_verify)

    rotate = sub.add_parser(
        "rotate",
        help="issue a replacement and revoke the old key [needs a database]",
        description=(
            "Issue a new key with the same tenant, label and scopes, then revoke the "
            "old one. Only the new raw key is printed. Requires DCC_DATABASE_URL."
        ),
    )
    rotate.add_argument("--id", required=True, help="key UUID to replace")
    rotate.add_argument("--tenant", help="tenant UUID, to avoid a cross-tenant lookup")
    rotate.add_argument(
        "--expires-in-days",
        type=int,
        metavar="N",
        help="replacement expires N days from now (default: inherits the old expiry)",
    )
    rotate.set_defaults(handler=_cmd_rotate)

    prune = sub.add_parser(
        "prune",
        help="delete revoked or expired rows; dry run unless --apply [needs a database]",
        description=(
            "Delete rows that are revoked or expired. Live keys are never touched. "
            "Dry run by default: nothing is deleted until --apply is passed. "
            "Requires DCC_DATABASE_URL and, on the durable store, --tenant."
        ),
    )
    prune.add_argument("--tenant", help="tenant UUID to prune (required for the durable store)")
    prune.add_argument(
        "--expired", action="store_true", help="only expired keys (leave revoked rows alone)"
    )
    prune.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be deleted without deleting (the default)",
    )
    prune.add_argument(
        "--apply",
        action="store_true",
        help="actually delete; without this (or with --dry-run) nothing changes",
    )
    prune.set_defaults(handler=_cmd_prune)

    legacy = sub.add_parser(
        "print-env",
        help="print a legacy DCC_API_KEYS='tenant:hash' entry [no database needed]",
        description=(
            "Generate a key and print the 'tenant:hash' entry for the DCC_API_KEYS "
            "bootstrap path. Writes nothing anywhere; the raw key is printed once. "
            "Kept for muscle memory and for deployments that have no database yet -- "
            "'create' is the durable path."
        ),
    )
    legacy.add_argument("--tenant", required=True, help="tenant identifier (need not be a UUID)")
    _common(legacy)
    legacy.add_argument("--hash-only", action="store_true", help="print only the entry")
    legacy.set_defaults(handler=_cmd_print_env)

    return parser


def main(argv: Optional[List[str]] = None, store: Optional[ApiKeyStore] = None) -> int:
    """Run one subcommand. Returns a process exit code; never raises for CLI errors.

    ``store`` is a test seam: pass ``ApiKeyStore(dsn="")`` to exercise the commands
    without a database. When it is None the store comes from ``DCC_DATABASE_URL``,
    and its absence is a hard error rather than a silently process-local store.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args, store)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.code
    except ApiKeyError as exc:
        print(f"error: API key store: {exc}", file=sys.stderr)
        return EXIT_FAILED
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - a CLI reports, it does not traceback
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
