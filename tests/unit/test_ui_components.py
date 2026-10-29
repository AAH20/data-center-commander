"""Console component fragments are served from the mount that exists.

``src/dcc/ui_components.py`` shipped a component loader that fetched
``/components/<name>.html``. Nothing is mounted at ``/components``: the served
application registers 39 routes and the only ``Mount`` is ``/assets``. The
fragments themselves live in ``ui/components/`` and are served from that mount,
so the loader would have answered 404 on its first call while the same file
answered 200 one prefix over.

It also had no consumer. The module was never imported, no route served its
``SHARED_JS`` / ``SHARED_CSS`` strings, and ``ui/index.html`` never called
``DCC.loadComponent`` in any commit -- the console drives its views with its own
``showView``. It was removed rather than re-pointed at ``/assets/components/``,
because a corrected URL would still have left nothing executing the loader.

These tests pin the two measured facts so the next person wiring a lazy loader
reads them instead of guessing: the prefix that module used is not a route (404),
and the mount the console actually uses serves every fragment (200) with the
file's own bytes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

import dcc.api_async as api
from dcc.api_async import app

UI_DIR = Path(__file__).resolve().parents[2] / "ui"
COMPONENTS_DIR = UI_DIR / "components"


@pytest.fixture()
def client(monkeypatch):
    """Routing with authentication out of the way.

    Anonymous mode is required to answer a routing question at all: with a key
    enforced, a request below /components gets 401 from the middleware before the
    router is consulted, which says nothing about whether a route exists.
    """
    monkeypatch.setenv("DCC_ALLOW_ANONYMOUS", "1")
    api._API_KEYS.reset()
    yield TestClient(app)
    api._API_KEYS.reset()


def _fragments() -> list[str]:
    return sorted(path.name for path in COMPONENTS_DIR.glob("*.html"))


def test_the_removed_loader_module_is_gone():
    """A resurrected module would re-introduce a loader no route can serve.

    The loader was JavaScript in a Python string with no producer: no route or
    script tag ever emitted it. Re-adding it has to bring a real consumer and a
    mounted path with it, not just a corrected URL.
    """
    assert importlib.util.find_spec("dcc.ui_components") is None, (
        "dcc.ui_components is back; it advertised /components/<name>.html, which is "
        "not mounted, and nothing served its SHARED_JS/SHARED_CSS strings"
    )


def test_the_components_prefix_the_loader_used_is_not_a_route(client):
    """THE regression: these returned 404 because /components is not mounted."""
    missing = []
    for name in _fragments():
        response = client.get(f"/components/{name}")
        if response.status_code != 404:
            missing.append((name, response.status_code))
    assert not missing, f"something answers under /components now: {missing}"


def test_no_route_outside_the_static_mount_serves_component_fragments():
    """The only way a fragment can be served is the console tree itself."""
    offenders = [
        str(getattr(route, "path", ""))
        for route in app.routes
        if "components" in str(getattr(route, "path", ""))
        and not str(getattr(route, "path", "")).startswith("/assets")
    ]
    assert not offenders, f"a route claims the fragment prefix: {offenders}"


def test_the_static_mount_is_rooted_at_the_console_tree():
    """Guard for the assertions below: they only mean something against ui/."""
    mounts = [
        route
        for route in app.routes
        if isinstance(route, Mount) and isinstance(route.app, StaticFiles)
    ]
    console = [
        route
        for route in mounts
        if getattr(route.app, "directory", None) is not None
        and Path(route.app.directory).resolve() == UI_DIR.resolve()
    ]
    assert len(console) == 1, (
        f"expected one mount of ui/, found {[r.path for r in console]}"
    )


def test_every_fragment_the_loader_wanted_is_served_by_the_mount(client):
    """The loader's ten names all exist and answer 200 under /assets/components/."""
    fragments = _fragments()
    assert len(fragments) >= 10, f"only {len(fragments)} fragments on disk"

    failures = []
    for name in fragments:
        response = client.get(f"/assets/components/{name}")
        on_disk = (COMPONENTS_DIR / name).read_bytes()
        if response.status_code != 200:
            failures.append((name, response.status_code))
        elif response.content != on_disk:
            failures.append((name, "body differs from the file on disk"))
        elif not response.content.lstrip().startswith(b"<div"):
            failures.append((name, "not an injectable fragment"))
    assert not failures, f"/assets/components/ does not serve: {failures}"


def test_a_name_the_loader_invented_fails_loudly(client):
    """A wrong component name must be a 404, not an empty 200 that blanks a view."""
    response = client.get("/assets/components/not-a-component.html")
    assert response.status_code == 404
