#!/usr/bin/env python3
"""Start Data Center Commander.

The served product is the FastAPI app in ``dcc.api_async`` (routes under ``/v2``).
This launcher previously started ``dcc.api`` -- the legacy stdlib HTTP handler that
serves ``/v1`` -- so the documented Quick Start and the container entrypoint both ran
a server that is not the product. Someone following the README got a working process
on a port where every documented endpoint 404s.

``dcc.api`` is still reachable with ``--legacy``: it is unmounted but exercised by the
test suite, and its parsers remain the reference for path-traversal behaviour.

The legacy server refuses to bind anything but loopback. That restriction belongs to a
development server with no authentication; the v2 app enforces authentication and tenant
isolation, so it is safe to bind a container interface.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Data Center Commander")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="interface to bind (default 127.0.0.1; use 0.0.0.0 in a container)",
    )
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="serve the legacy /v1 stdlib API instead of the v2 application",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="reload on source changes (development only; ignored with --legacy)",
    )
    args = parser.parse_args(argv)

    if args.legacy:
        from dcc.api import serve

        serve(args.host, args.port)
        return 0

    try:
        import uvicorn
    except ImportError:
        print(
            "uvicorn is required for the v2 application. Install it with:\n"
            "    uv pip install uvicorn   (or: pip install uvicorn)\n"
            "To run the legacy /v1 server instead, pass --legacy.",
            file=sys.stderr,
        )
        return 1

    print(f"serving dcc.api_async:app on http://{args.host}:{args.port}")
    print(f"  console:  http://{args.host}:{args.port}/")
    print(f"  openapi:  http://{args.host}:{args.port}/docs")
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        print(
            "  note: binding a non-loopback interface; authentication is enforced, "
            "so set DCC_API_KEYS or every request returns 401.",
            file=sys.stderr,
        )

    uvicorn.run(
        "dcc.api_async:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
