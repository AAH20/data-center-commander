"""CI-enforceable integrity checks for the k6 / Artillery load scenarios.

The load scenarios are not runnable in CI (they need a live server and an external
binary), so before this file they were only checked by a human remembering they
existed. Deleting one, emptying a threshold list, or breaking an Artillery YAML left
every automated run green.

These assertions run everywhere in milliseconds: the eight scenario files are still
present, still non-trivial, still declare the thresholds that make them fail rather
than merely print, and still parse. That is the part of "keep the k6/Artillery
scenarios working" that a unit-test-style gate can honestly own; actually running
them is ``test_perf_live_scenarios.py``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

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


@pytest.mark.parametrize("script", K6_SCENARIOS)
def test_k6_scenario_declares_thresholds(script: str) -> None:
    """A k6 script without a ``thresholds`` block exits 0 no matter how slow it is."""
    path = K6_DIR / script
    assert path.exists(), f"{path} is missing; the {script} load scenario was removed"
    source = path.read_text(encoding="utf-8")
    assert len(source) > 500, f"{path} is {len(source)} bytes -- gutted, not a scenario"
    assert "export const options" in source, f"{path} declares no k6 options"
    assert "thresholds" in source, (
        f"{path} declares no thresholds, so `k6 run` cannot fail on latency or errors"
    )
    assert re.search(r"p\(9[59]\)", source), (
        f"{path} has no p(95)/p(99) latency threshold"
    )


@pytest.mark.parametrize("script", ARTILLERY_SCENARIOS)
def test_artillery_scenario_parses_and_declares_an_sla(script: str) -> None:
    """Artillery ignores a scenario with no ``ensure``; it just reports numbers."""
    path = ARTILLERY_DIR / script
    assert path.exists(), f"{path} is missing; the {script} load scenario was removed"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict), f"{path} is not a YAML mapping"
    config = document.get("config") or {}
    assert config.get("target"), f"{path} has no config.target"
    assert config.get("phases"), f"{path} has no load phases"
    assert config.get("ensure"), (
        f"{path} has no config.ensure block, so no threshold can fail the run"
    )
    scenarios = document.get("scenarios") or []
    assert scenarios, f"{path} defines no scenarios"
    assert any((s or {}).get("flow") for s in scenarios), f"{path} has no scenario flow"


@pytest.mark.parametrize("helper", ("shared.js",))
def test_k6_shared_helpers_exist(helper: str) -> None:
    path = K6_DIR / helper
    assert path.exists(), f"{path} is missing; the k6 scenarios import it"
    assert "BASE_URL" in path.read_text(encoding="utf-8")


def test_artillery_processor_exists() -> None:
    path = ARTILLERY_DIR / "helpers.js"
    assert path.exists(), f"{path} is missing; every scenario names it as its processor"


def test_npm_scripts_still_point_at_the_scenarios() -> None:
    """The documented entry points (``npm run test:k6:all`` ...) must stay wired."""
    package = json.loads((PERF_DIR / "package.json").read_text(encoding="utf-8"))
    scripts = package.get("scripts") or {}
    joined = " ".join(scripts.values())
    for script in K6_SCENARIOS:
        assert f"k6/{script}" in joined, f"package.json no longer runs k6/{script}"
    for script in ARTILLERY_SCENARIOS:
        assert f"artillery/{script}" in joined, (
            f"package.json no longer runs artillery/{script}"
        )


_PATH_RE = re.compile(r"""["'](?P<path>/(?:v\d+|healthz|readyz|metrics)[A-Za-z0-9_/-]*)""")


def _referenced_paths() -> dict[str, set[str]]:
    """Every API path named by a load scenario, mapped to the files that name it."""
    found: dict[str, set[str]] = {}
    for directory in (K6_DIR, ARTILLERY_DIR):
        for path in sorted(directory.iterdir()):
            if path.suffix not in {".js", ".yml"}:
                continue
            for match in _PATH_RE.finditer(path.read_text(encoding="utf-8")):
                found.setdefault(match.group("path"), set()).add(path.name)
    return found


def test_every_scenario_path_is_a_real_route() -> None:
    """The scenarios must load-test the application that is actually served.

    This is not a style check. Every k6 and Artillery scenario used to target
    ``/v1/*`` paths, which belong to the legacy stdlib API in ``dcc/api.py``. The
    served product is ``dcc.api_async:app`` (Dockerfile ENTRYPOINT, and
    ``scripts/run-local.py``), which exposes ``/v2/*`` only -- so all eight
    scenarios were driving 404s. A 404 is fast, so their "p95 < 1500 ms" thresholds
    passed with flying colours while measuring nothing. This assertion is what makes
    that failure mode impossible to reintroduce.
    """
    import dcc.api_async as api

    registered = {getattr(route, "path", "") for route in api.app.routes}
    referenced = _referenced_paths()
    assert referenced, "no API paths found in the load scenarios -- the parser is stale"

    unknown = {
        path: sorted(files)
        for path, files in referenced.items()
        if path not in registered
    }
    assert not unknown, (
        "load scenarios reference paths the served app does not expose "
        f"(dcc.api_async:app routes under /v2): {unknown}. Registered paths: "
        f"{sorted(p for p in registered if p.startswith('/v'))}"
    )


def test_scenarios_target_the_seeded_tenant_by_default() -> None:
    """A load test against a tenant with no rows measures empty responses."""
    placeholder = "00000000-0000-4000-8000-000000000001"
    offenders = [
        path.name
        for path in list(K6_DIR.iterdir()) + list(ARTILLERY_DIR.iterdir())
        if path.suffix in {".js", ".yml"}
        and placeholder in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"{offenders} still default to the placeholder tenant {placeholder}, which has "
        f"no rows in the seeded database; the scenarios would exercise empty results"
    )
