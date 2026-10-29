# E2E browser tier

Playwright drives the real console (`ui/`) against a real `dcc.api_async` server on
loopback. Nothing here is mocked at the HTTP layer except through `page.route` in the
`mock_api` fixtures — the point of the tier is the browser plus the app's own routing.

## What it needs

| Requirement | Detail |
|---|---|
| Python package | `playwright` — declared as the `e2e` extra in `pyproject.toml` (`pip install -e ".[e2e]"`) |
| Browser binary | Chromium. The fixture skips with an install hint when no binary is present |
| Server | started by the `api_server` fixture, on a port it picks itself |
| Database | optional. Set `DCC_DATABASE_URL`; tests that assert real read responses use the `database_url` fixture and skip without it |

Install the browser once per machine / CI job:

```console
python -m playwright install --with-deps chromium-headless-shell
```

`--with-deps` is a Linux (CI) flag: it installs the system libraries Chromium needs.
On macOS, `python -m playwright install chromium-headless-shell` is enough.

## Running it

```console
PYTHONPATH=src DCC_DATABASE_URL=postgresql://localhost:5432/dcc_demo_local \
  .venv/bin/python -m pytest tests/e2e -q
```

Environment knobs, all optional:

- `DCC_E2E_PORT` — pin the server port. If anything is already listening there the
  fixture fails and names the process; it will not use it.
- `DCC_E2E_SERVER_LOG` — where the child server's stdout/stderr go. Defaults to
  `$TMPDIR/dcc-e2e-server-<port>.log`, and the tail is printed in any setup failure.

## The port contract

The fixture starts `scripts/run-local.py --host 127.0.0.1 --port <free port>` and only
declares itself ready when **all** of these hold:

1. the child process it spawned is still alive;
2. the only PID listening on that port is that child (checked with `lsof`, or
   `/proc/net/tcp` on Linux);
3. `/healthz` on that port returns `{"service": "data-center-commander", "mode":
   "read_only"}`.

Condition 3 alone is not identity: the legacy `dcc.api` handler answers `/healthz`
with the same body. Ownership is decided by PID.

This exists because the previous fixture polled a hardcoded port **8790** and treated
"a TCP connection succeeded" as "my server is up". With an unrelated server already
on 8790 it adopted that process: its responses became the test results, and its
failures were attributed to the code under review.

Do not reintroduce a hardcoded port in a test module. Use `base_url()` from
`helpers.py` (or the `base_url` / `api_server` fixtures); it raises rather than
falling back to a default, so a test can never quietly address a stranger.

## Current state

The tier is excluded from the blocking gate in `.github/workflows/ci.yml`
(`--ignore=tests/e2e`). Locally, on a machine with the browser installed and
PostgreSQL up, it is green — see the run recorded in the commit that changed this
fixture. What CI still lacks is the Chromium download and the linear runtime; both are
costs the orchestrator has to accept deliberately, not something this tier can fix
from inside.
