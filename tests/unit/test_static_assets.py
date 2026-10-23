"""Every script the console references must actually be served.

ui/index.html loads ten module scripts from /assets/*.js -- topology, forecast, quality,
security, economics, placement, onboarding, ops and pricing dashboards. The files exist
in ui/, but the app mounted only "/" and "/v2/*", so all ten returned 404 and every
dashboard they drive stayed on its static placeholder text. Nothing caught it: the
console contract test checks that the API paths the HTML fetches exist, and these are
<script src> paths, not fetches.

This test reads the <script src> values out of the real HTML, so a new dashboard added
without a corresponding mount fails here rather than 404ing in a browser.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dcc.api_async import app

UI_DIR = Path(__file__).resolve().parents[2] / "ui"
INDEX = UI_DIR / "index.html"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _asset_paths() -> list[str]:
    html = INDEX.read_text(encoding="utf-8")
    return sorted(set(re.findall(r'src="(/assets/[^"]+\.js)"', html)))


def test_console_index_exists() -> None:
    """Guard the parser: with no HTML, every other assertion here is vacuous."""
    assert INDEX.is_file(), f"{INDEX} is missing"
    assert len(_asset_paths()) >= 8, f"expected at least 8 module scripts, found {len(_asset_paths())}"


def test_every_referenced_asset_is_served(client: TestClient) -> None:
    missing = [p for p in _asset_paths() if client.get(p).status_code != 200]

    assert not missing, f"{len(missing)} console script(s) 404: {missing}"


def test_served_asset_has_javascript_content(client: TestClient) -> None:
    """A 200 with an HTML error page would satisfy a status check and break the browser."""
    path = _asset_paths()[0]
    response = client.get(path)

    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "").lower()
    assert len(response.content) > 0


def test_asset_directory_traversal_is_refused(client: TestClient) -> None:
    """Mounting ui/ must not expose anything outside it."""
    response = client.get("/assets/../src/dcc/api_async.py")

    assert response.status_code in (307, 404), (
        f"traversal returned {response.status_code}; ui/ mount may be escaping its directory"
    )
