"""E2E tests for the Energy & Carbon view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import navigate_to

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestEnergyView:
    """Test the Energy, cost & carbon view."""

    def test_energy_view_title(self, page: Page, api_server, mock_all_empty):
        """Energy view should have correct title."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "energy")
        expect(page.locator("#view-energy h2")).to_contain_text("Energy, cost")

    def test_energy_table_headers(self, page: Page, api_server, mock_all_empty):
        """Energy table should have correct headers."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "energy")
        headers = page.locator("#view-energy th")
        expect(headers).to_have_count(7)

    def test_energy_rows_empty(self, page: Page, api_server, mock_all_empty):
        """Energy rows should be empty when no data."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "energy")
        rows = page.locator("#energyRows tr")
        assert rows.count() == 0

    def test_energy_view_description(self, page: Page, api_server, mock_all_empty):
        """Energy view should have description text."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "energy")
        expect(page.locator("#view-energy p").first).to_contain_text("Versioned interval metrics")

    def test_energy_tablewrap_present(self, page: Page, api_server, mock_all_empty):
        """Energy table wrapper should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "energy")
        expect(page.locator("#view-energy .tablewrap")).to_be_visible()

    def test_energy_nav_active(self, page: Page, api_server, mock_all_empty):
        """Energy nav button should be active when on energy view."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "energy")
        expect(page.locator('.nav [data-view="energy"]')).to_have_class(re.compile(r"\bactive\b"))

    def test_energy_view_hidden_by_default(self, page: Page, api_server, mock_all_empty):
        """Energy view should be hidden by default."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        expect(page.locator("#view-energy")).not_to_have_class(re.compile(r"\bactive\b"))

    def test_energy_synthetic_quarantine(self, page: Page, api_server, mock_all_empty):
        """Synthetic data should be quarantined from energy view."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}&demo=synthetic")
        page.wait_for_timeout(500)
        expect(page.locator("#energyRows")).to_be_empty()
