"""The load scenarios, as pytest tests that skip unless their capability exists.

These are the only tests in this directory that need something the CI runner does
not have. Each one names what is missing and how to supply it, so a skip is a
statement about the environment rather than a silently disabled gate:

* ``k6`` / ``artillery`` on ``PATH`` -- the external tool.
* ``DCC_PERF_LIVE_URL`` -- a running DCC instance to point load at, e.g.
  ``DCC_PERF_LIVE_URL=http://127.0.0.1:8790``.

When the URL is set they run a short smoke pass (2 VUs, 3 s) so the scenario is
proven to parse and to reach the server. They deliberately do NOT reproduce the
long runs: the real p95/p99 load profiles are ``k6 run k6/load-test.js`` and
``artillery run artillery/load-test.yml``, documented in the README, and running a
9-minute ramp on every push would be both slow and meaningless on a shared runner.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from .conftest import LIVE_URL, TENANT_ID as TENANT

PERF_DIR = Path(__file__).resolve().parent
K6_DIR = PERF_DIR / "k6"
ARTILLERY_DIR = PERF_DIR / "artillery"

K6_SCENARIOS = ("load-test.js", "stress-test.js", "spike-test.js", "endurance-test.js")
ARTILLERY_SCENARIOS = (
    "load-test.yml",
    "stress-test.yml",
    "spike-test.yml",
    "endurance-test.yml",
)

SMOKE_TIMEOUT_S = 120


def _require_live_server() -> str:
    if not LIVE_URL:
        pytest.skip(
            "no live DCC server: the load scenario needs a running instance. "
            "Start one and set DCC_PERF_LIVE_URL=http://127.0.0.1:8790 to enable it."
        )
    return LIVE_URL


@pytest.mark.parametrize("script", K6_SCENARIOS)
def test_k6_scenario_runs_against_a_live_server(script: str, tmp_path: Path) -> None:
    """Smoke: the scenario parses, every request succeeds, and none return an error.

    Thresholds are disabled for the smoke pass (`--no-thresholds`) because these are
    production-load thresholds: `http_reqs: rate>10` cannot be met by 2 VUs in 3
    seconds, and failing the smoke on throughput would say nothing about the script.
    Throughput is asserted instead through the summary export -- at least one request
    and a zero failure rate -- so a scenario that 404s (the state this directory was
    in when every path was `/v1/*`) cannot pass.
    """
    base_url = _require_live_server()
    binary = shutil.which("k6")
    if binary is None:
        pytest.skip(
            "k6 binary not on PATH: this scenario needs the external k6 load "
            "generator (`brew install k6`)"
        )

    summary_path = tmp_path / f"{script}.summary.json"
    command = [
        binary,
        "run",
        "--quiet",
        "--no-thresholds",
        "--summary-export", str(summary_path),
        "--vus", "2",
        "--duration", "3s",
        "--env", f"BASE_URL={base_url}",
        "--env", f"TENANT_ID={TENANT}",
        str(K6_DIR / script),
    ]
    completed = subprocess.run(
        command, capture_output=True, text=True, timeout=SMOKE_TIMEOUT_S
    )
    assert completed.returncode == 0, (
        f"k6 {script} failed against {base_url} with exit {completed.returncode}\n"
        f"stdout:\n{completed.stdout[-2000:]}\nstderr:\n{completed.stderr[-2000:]}"
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    metrics = summary["metrics"]
    # k6 v2 writes flat metric objects ({"count": N}); older versions nested the
    # numbers under "values". Accept both rather than pinning to a k6 release.
    def _metric(name: str) -> dict:
        entry = metrics[name]
        return entry.get("values", entry)

    requests = _metric("http_reqs")["count"]
    failures = _metric("http_req_failed").get("rate", _metric("http_req_failed").get("value"))
    assert failures is not None, f"k6 {script}: summary has no failure rate"
    assert requests > 0, f"k6 {script} made no requests against {base_url}"
    assert failures == 0, (
        f"k6 {script}: {failures:.1%} of {requests} requests failed against "
        f"{base_url}. A scenario pointed at paths the server does not serve fails "
        f"here rather than passing on fast 404s."
    )


@pytest.mark.parametrize("script", ARTILLERY_SCENARIOS)
def test_artillery_scenario_runs_against_a_live_server(script: str) -> None:
    base_url = _require_live_server()
    binary = shutil.which("artillery")
    if binary is None:
        pytest.skip(
            "artillery binary not on PATH: this scenario needs the external "
            "artillery load generator (`npm install -g artillery`)"
        )

    completed = subprocess.run(
        [binary, "run", "--quiet", str(ARTILLERY_DIR / script)],
        capture_output=True,
        text=True,
        timeout=SMOKE_TIMEOUT_S,
        env={
            **os.environ,
            "BASE_URL": base_url,
            "DURATION": "3",
        },
    )
    assert completed.returncode == 0, (
        f"artillery {script} failed against {base_url} with exit "
        f"{completed.returncode}\nstdout:\n{completed.stdout[-2000:]}\n"
        f"stderr:\n{completed.stderr[-2000:]}"
    )
