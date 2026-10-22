"""The console and the API must agree on which routes exist.

The bundled UI shipped calling nine /v1 endpoints while the served app exposed /v2,
so every panel 404'd and -- because the page used Promise.all -- one failure blanked
the whole workspace. Nothing caught it, because no test compared the two.

This does exactly that, by reading the paths out of the HTML and checking them against
the app's own route table.
"""

from __future__ import annotations

import re
from pathlib import Path

from dcc.api_async import app

UI = Path(__file__).resolve().parents[2] / "ui" / "index.html"


def _console_paths() -> list[str]:
    html = UI.read_text(encoding="utf-8")
    # get('/v2/overview') and get(`/v2/x`) are both used in the page.
    return sorted(set(re.findall(r"get\(['\"`](/v[12]/[a-z/-]+)", html)))


def test_console_file_exists():
    assert UI.exists(), f"console missing at {UI}"


def test_console_calls_routes_that_exist():
    """Every path the console fetches must be registered on the served app."""
    registered = {route.path for route in app.routes if hasattr(route, "path")}
    missing = [path for path in _console_paths() if path not in registered]
    assert not missing, (
        f"the console calls {missing} but the app does not serve them; "
        "these panels would 404"
    )


def test_console_uses_no_legacy_v1_paths():
    """api.py is a stdlib server that is never mounted. Nothing should still call /v1."""
    legacy = [path for path in _console_paths() if path.startswith("/v1/")]
    assert not legacy, f"console still calls unmounted /v1 routes: {legacy}"


def test_console_does_not_rely_on_a_single_failing_panel():
    """Promise.all means one missing route blanks everything. allSettled is required."""
    html = UI.read_text(encoding="utf-8")
    assert "Promise.allSettled" in html
    assert "await Promise.all([" not in html, (
        "one unavailable panel would take down the whole console again"
    )
