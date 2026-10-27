"""The console must load its own files while authentication is enforced.

The console is a shell at "/" plus ten module scripts and eleven HTML fragments served
from /assets/*. A browser cannot attach an Authorization header to a <script src>, so
requiring a key for those files left the default, secure deployment serving a page
whose every module 401'd: the shell rendered, the scripts did not, and the console did
nothing. It looked fine locally only because every local run sets DCC_ALLOW_ANONYMOUS.

The fix must open the shipped static tree and nothing else. Both directions are
asserted below, because a fix that made the console work by opening /v2 would trade a
visible bug for an invisible one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import dcc.api_async as api
from dcc.api_async import app

UI_DIR = Path(__file__).resolve().parents[2] / "ui"
INDEX = UI_DIR / "index.html"

#: Extensions that would mean the public tree had grown a data payload.
DATA_SUFFIXES = {
    ".json", ".ndjson", ".csv", ".tsv", ".db", ".sqlite", ".sqlite3", ".parquet",
    ".xlsx", ".xls", ".yaml", ".yml", ".env", ".pem", ".key",
}


@pytest.fixture()
def enforced(monkeypatch):
    """A client with authentication ENFORCED -- the production default."""
    monkeypatch.delenv("DCC_ALLOW_ANONYMOUS", raising=False)
    api._API_KEYS.reset()
    yield TestClient(app)
    api._API_KEYS.reset()


@pytest.fixture()
def tenant_key(monkeypatch):
    """A real API key for one tenant. monkeypatch keeps nothing behind after the test."""
    raw, record = api._API_KEYS.create(name="asset-test", tenant_id="tenant-asset")
    return raw, record


def _console_scripts() -> list[str]:
    """Every /assets path the shipped page actually loads."""
    html = INDEX.read_text(encoding="utf-8")
    return sorted(set(re.findall(r'src="(/assets/[^"]+)"', html)))


class TestConsoleAssetsLoadWithoutAKey:
    def test_the_page_lists_scripts_at_all(self):
        """Guard: with no scripts every assertion below would be vacuous."""
        scripts = _console_scripts()
        assert len(scripts) >= 10, f"the console references only {len(scripts)} assets"

    def test_every_module_script_the_console_loads_is_public(self, enforced):
        """THE regression test. Each of these returned 401 before the fix."""
        broken = []
        for path in _console_scripts():
            response = enforced.get(path)
            if response.status_code != 200:
                broken.append((path, response.status_code))
        assert not broken, f"the console loads these and they are not served: {broken}"

    def test_a_module_script_returns_javascript(self, enforced):
        response = enforced.get("/assets/economics-dashboard.js")
        assert response.status_code == 200
        assert "javascript" in response.headers.get("content-type", "").lower()
        assert len(response.content) > 0, "served 200 with an empty body"

    def test_a_component_fragment_is_public_too(self, enforced):
        """The panel templates live under the same mount; a half-open tree still breaks."""
        fragments = sorted(p.name for p in (UI_DIR / "components").glob("*.html"))
        assert fragments, "no component fragments found"
        for name in fragments:
            response = enforced.get(f"/assets/components/{name}")
            assert response.status_code == 200, f"/assets/components/{name} -> {response.status_code}"

    def test_the_asset_response_is_not_a_body_it_could_not_have_served(self, enforced):
        """A 200 carrying the auth error document would still be a blank console."""
        response = enforced.get("/assets/topology.js")
        assert response.status_code == 200
        assert "missing_credentials" not in response.text


class TestTenantDataStaysClosed:
    def test_a_v2_route_without_a_key_is_still_401(self, enforced):
        response = enforced.get("/v2/facilities?tenant_id=tenant-asset")
        assert response.status_code == 401
        assert response.json()["error"] == "missing_credentials"
        assert response.headers.get("www-authenticate") == "Bearer"

    def test_a_v2_route_still_challenges_a_bogus_key(self, enforced):
        response = enforced.get("/v2/facilities", headers={"X-API-Key": "dcc_not-a-real-key"})
        assert response.status_code == 401
        assert response.json()["error"] == "invalid_credentials"

    def test_a_valid_key_is_still_refused_for_another_tenant(self, enforced, tenant_key):
        raw, _ = tenant_key
        own = enforced.get("/v2/facilities?tenant_id=tenant-asset", headers={"X-API-Key": raw})
        assert own.status_code not in (401, 403), "the key fixture itself is not valid"
        other = enforced.get("/v2/facilities?tenant_id=tenant-other", headers={"X-API-Key": raw})
        assert other.status_code == 403
        assert other.json()["error"] == "tenant_mismatch"

    def test_no_registered_v2_route_is_covered_by_the_asset_exemption(self):
        """The exemption is derived from the route table; prove no data route matches."""
        covered = [
            str(getattr(route, "path", ""))
            for route in app.routes
            if str(getattr(route, "path", "")).startswith("/v2")
            and api._is_public_console_asset(str(getattr(route, "path", "")))
        ]
        assert not covered, f"these data routes are public: {covered}"


class TestTheExemptionCannotBeBorrowed:
    def test_the_public_prefix_is_the_static_mount(self):
        assert api._console_asset_prefixes() == ("/assets",)

    def test_every_route_under_the_prefix_is_the_static_mount(self):
        """Nothing but StaticFiles may live under the exempt prefix."""
        from starlette.routing import Mount
        from starlette.staticfiles import StaticFiles

        non_static = []
        for route in app.routes:
            path = str(getattr(route, "path", ""))
            if not path.startswith("/assets"):
                continue
            directory = getattr(route.app, "directory", None) if isinstance(route, Mount) else None
            is_console_mount = (
                isinstance(route, Mount)
                and isinstance(route.app, StaticFiles)
                and directory is not None
                and Path(directory).resolve() == UI_DIR.resolve()
            )
            if not is_console_mount:
                non_static.append((path, type(route).__name__))
        assert not non_static, f"handlers share the public asset prefix: {non_static}"

    def test_a_parent_path_does_not_inherit_the_exemption(self):
        """'/assets/../v2/overview' starts with the prefix and resolves elsewhere."""
        assert api._is_public_console_asset("/assets/../v2/overview") is False
        assert api._is_public_console_asset("/assets/../../src/dcc/api_async.py") is False
        assert api._is_public_console_asset("/v2/../assets/topology.js") is False

    def test_a_lookalike_prefix_does_not_inherit_the_exemption(self):
        assert api._is_public_console_asset("/assets-private/report.csv") is False
        assert api._is_public_console_asset("/assetsx/topology.js") is False

    def test_traversal_via_the_asset_prefix_is_still_challenged(self, enforced):
        """Whatever the router does with it, the middleware must not answer 200."""
        for path in ("/assets/../v2/facilities?tenant_id=tenant-asset",
                     "/assets/%2e%2e/v2/facilities?tenant_id=tenant-asset"):
            response = enforced.get(path)
            assert response.status_code == 401, (
                f"{path} answered {response.status_code}; the exemption leaked"
            )

    def test_the_public_tree_carries_no_data_payloads(self):
        """The exemption rests on these files being identical on every deployment."""
        offenders = [
            p.relative_to(UI_DIR).as_posix()
            for p in UI_DIR.rglob("*")
            if p.is_file() and p.suffix.lower() in DATA_SUFFIXES
        ]
        assert not offenders, f"the public asset tree contains data files: {offenders}"
