"""Shared helpers for E2E tests."""
from __future__ import annotations

from playwright.sync_api import Page


def navigate_to(page: Page, view_name: str) -> None:
    """Navigate to a view using JavaScript click to avoid overlay issues."""
    page.evaluate(f"document.querySelector('.nav [data-view=\"{view_name}\"]').click()")


def click_by_selector(page: Page, selector: str) -> None:
    """Click an element by CSS selector using JavaScript to avoid overlay issues."""
    page.evaluate(f"document.querySelector('{selector}').click()")
