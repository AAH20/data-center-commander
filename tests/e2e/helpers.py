"""Shared helpers for E2E tests."""
from __future__ import annotations

from playwright.sync_api import Page

# The E2E server port is chosen per run (ephemeral unless DCC_E2E_PORT pins it),
# so tests cannot hardcode a URL. The `api_server` fixture in conftest.py sets
# this once it has started a server AND proven it owns the listening socket; the
# module-level `BASE_URL = "http://127.0.0.1:8790"` constant that used to live in
# every test file is gone, because it made the tier address a port it did not
# necessarily own.
_BASE_URL: str | None = None


def set_base_url(url: str | None) -> None:
    """Set (or clear, with None) the URL of the session's server."""
    global _BASE_URL
    _BASE_URL = url


def base_url() -> str:
    """Base URL of the server the `api_server` fixture started.

    Raises instead of falling back to a default port: silently addressing 8790 is
    how this tier ended up testing another process.
    """
    if _BASE_URL is None:
        raise RuntimeError(
            "base_url() was called before the E2E server started. Request the "
            "`api_server` (or `page`) fixture in the test so a server is started "
            "and owned for the session."
        )
    return _BASE_URL


def navigate_to(page: Page, view_name: str) -> None:
    """Navigate to a view using JavaScript click to avoid overlay issues."""
    page.evaluate(f"document.querySelector('.nav [data-view=\"{view_name}\"]').click()")


def click_by_selector(page: Page, selector: str) -> None:
    """Click an element by CSS selector using JavaScript to avoid overlay issues."""
    page.evaluate(f"document.querySelector('{selector}').click()")
