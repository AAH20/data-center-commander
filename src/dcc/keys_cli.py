"""Mint an API key for the served application.

The key store is in-memory, so a key created at runtime disappears on restart and is
invisible to sibling worker processes. The durable path is DCC_API_KEYS, which holds
tenant/hash pairs. This CLI produces both halves: the plaintext key, shown once, and
the configuration entry to install.

    python -m dcc.keys_cli create --tenant <uuid> --name ops
"""

from __future__ import annotations

import argparse
import sys

from .security.api_keys import generate_api_key, hash_api_key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dcc.keys_cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="generate a key and its configuration entry")
    create.add_argument("--tenant", required=True,
                        help="tenant identifier the key belongs to")
    create.add_argument("--name", default="ops", help="human label for the key")
    create.add_argument("--hash-only", action="store_true",
                        help="print only the tenant:hash entry")

    args = parser.parse_args(argv)

    if args.command == "create":
        raw = generate_api_key()
        digest = hash_api_key(raw)
        entry = f"{args.tenant}:{digest}"

        if args.hash_only:
            print(entry)
            return 0

        print("API key created. The key is shown ONCE and cannot be recovered.")
        print()
        print(f"  name  : {args.name}")
        print(f"  tenant: {args.tenant}")
        print(f"  key   : {raw}")
        print()
        print("Install it durably by adding this to DCC_API_KEYS (hashes only):")
        print()
        print(f'  DCC_API_KEYS="{entry}"')
        print()
        print("For the bundled console, also set DCC_UI_API_KEY to the key above.")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
