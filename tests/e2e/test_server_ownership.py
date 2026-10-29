"""Guards on the E2E harness itself, not on the product.

The tier used to share a hardcoded port 8790 with whatever happened to be
listening on the machine, and it adopted that process whenever one was there.
Measured on this repository at da04ff0: with another uvicorn already on 8790 the
fixture's own child had exited, the tests were pointed at the stranger's socket,
and the tier reported "291 passed" about a server it never started. These tests
make that specific regression loud, because the fixture is only as trustworthy as
its proof of ownership.

`conftest.api_server` refuses a foreign listener. What it cannot do is notice
that it has stopped checking, so the invariant is asserted here independently --
this file reads the listener table itself rather than calling the conftest
helper whose correctness it is checking.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request

import pytest

RETIRED_FIXED_PORT = 8790


def _listener_pids(port: int) -> list[int]:
    """PIDs listening on `port`, read without reusing conftest's implementation."""
    if not shutil.which("lsof"):
        pytest.skip("lsof is not available; cannot inspect the listener table")
    out = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
    )
    return sorted({int(x) for x in out.stdout.split() if x.strip().isdigit()})


class TestServerOwnership:
    def test_listener_is_the_process_the_fixture_started(self, api_server):
        """The port the tests address is served by the fixture's own child."""
        pids = _listener_pids(api_server.port)
        assert pids == [api_server.pid], (
            f"port {api_server.port} is served by {pids}, but the fixture started "
            f"pid {api_server.pid}"
        )
        assert api_server.proc.poll() is None, "the fixture's server is not running"

    def test_health_identity_on_that_port(self, api_server):
        """/healthz on the fixture's URL reports the v2 app, not a stranger.

        The body alone is not proof of ownership -- the legacy `dcc.api` handler
        returns the identical JSON -- which is why the PID assertion above exists
        as well. Both are asserted so a future "fix" cannot drop one and still
        look green.
        """
        with urllib.request.urlopen(api_server.url + "/healthz", timeout=5) as response:
            assert response.status == 200
            body = json.loads(response.read().decode())
        assert body["service"] == "data-center-commander"
        assert body["mode"] == "read_only"
        if not os.environ.get("DCC_E2E_PORT"):
            # Only meaningful when the fixture chose the port itself. DCC_E2E_PORT
            # is an explicit developer override, so a pinned 8790 is allowed there
            # and is checked for occupancy instead (conftest._assert_port_free).
            assert api_server.port != RETIRED_FIXED_PORT, (
                "the fixture picked the retired fixed port 8790; ephemeral "
                "selection is what stops the tier colliding with an unrelated "
                "process"
            )
