"""The console must not put a credential anywhere that outlives the request.

A key in a URL is written to browser history, to the Referer of every subsequent
request, and to the server's access log -- a leak that survives the tab closing. The
console previously accepted ``?api_key=`` as a key source for convenience.

These are static checks against the shipped HTML, so they run without a browser.
"""

from __future__ import annotations

import re
from pathlib import Path

UI_DIR = Path(__file__).resolve().parents[2] / "ui"
INDEX = UI_DIR / "index.html"


def _html() -> str:
    return INDEX.read_text(encoding="utf-8")


def test_index_exists() -> None:
    """Guard: with no file every assertion below is vacuous."""
    assert INDEX.is_file(), f"{INDEX} is missing"


def test_url_is_not_a_credential_source() -> None:
    """The console must not read the API key out of the query string."""
    html = _html()

    assert 'get("api_key")' not in html, "the console reads the API key from the URL"
    assert "get('api_key')" not in html


def test_incoming_url_key_is_scrubbed() -> None:
    """An old bookmark with ?api_key= must be cleared from history, not left behind."""
    html = _html()

    assert "scrubUrlKey" in html, "no URL scrub for a key arriving in the query string"
    assert ".delete(" in html and "replaceState" in html


def test_key_is_sent_as_a_header() -> None:
    """X-API-Key keeps the credential out of URLs and access logs."""
    html = _html()

    assert "X-API-Key" in html
    # A header assignment inside the fetch wrapper, not a query append.
    assert not re.search(r"searchParams\.set\(\s*['\"]api_key", html)


def test_no_hardcoded_key_in_the_shipped_file() -> None:
    """Keys must never be committed into the console."""
    html = _html()

    # dcc_ keys are the format generate_api_key() mints.
    leaked = re.findall(r"dcc_[A-Za-z0-9_\-]{16,}", html)

    assert not leaked, f"the console contains what looks like a real API key: {leaked[:2]}"
