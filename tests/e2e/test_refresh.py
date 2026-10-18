"""E2E tests for refresh functionality."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestRefresh:
    """Test refresh functionality."""

    def test_refresh_button_present(self, page: Page, api_server, mock_all_empty):
        """Refresh button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        expect(page.locator("#refreshAll")).to_be_visible()

    def test_refresh_button_click(self, page: Page, api_server, mock_all_empty):
        """Clicking refresh should update timestamp."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.click("#refreshAll")
        page.wait_for_timeout(500)
        expect(page.locator("#updatedAt")).to_contain_text("Updated")

    def test_refresh_rate_selector(self, page: Page, api_server, mock_all_empty):
        """Refresh rate selector should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        expect(page.locator("#refreshRate")).to_be_visible()

    def test_refresh_rate_options(self, page: Page, api_server, mock_all_empty):
        """Refresh rate should have correct options."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        options = page.locator("#refreshRate option")
        assert options.count() == 4  # Off, 30s, 1min, 5min

    def test_refresh_rate_default(self, page: Page, api_server, mock_all_empty):
        """Default refresh rate should be 1 min."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        expect(page.locator("#refreshRate")).to_have_value("60")

    def test_refresh_rate_change(self, page: Page, api_server, mock_all_empty):
        """Changing refresh rate should persist."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.select_option("#refreshRate", "30")
        page.wait_for_timeout(300)
        expect(page.locator("#refreshRate")).to_have_value("30")

    def test_updated_at_initial(self, page: Page, api_server, mock_all_empty):
        """Updated at should show initial state."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        expect(page.locator("#updatedAt")).to_contain_text("Not refreshed")

    def test_refresh_updates_timestamp(self, page: Page, api_server, mock_all_empty):
        """Refresh should update the timestamp."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.click("#refreshAll")
        page.wait_for_timeout(500)
        expect(page.locator("#updatedAt")).to_contain_text("Updated")
