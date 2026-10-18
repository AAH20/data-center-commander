"""E2E tests for synthetic demo mode."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestSyntheticDemo:
    """Test synthetic demo mode behavior."""

    def test_synthetic_toggle_button(self, page: Page, api_server, mock_all_empty):
        """Synthetic demo toggle button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator('button:has-text("Open synthetic demo")')).to_be_visible()

    def test_synthetic_toggle_enters_demo(self, page: Page, api_server, mock_all_empty):
        """Clicking toggle should enter synthetic demo mode."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        page.click('button:has-text("Open synthetic demo")')
        page.wait_for_timeout(500)
        expect(page).to_have_url(f"{BASE_URL}/?demo=synthetic&tenant_id={TENANT_ID}")

    def test_synthetic_ribbon_displayed(self, page: Page, api_server, mock_all_empty):
        """Synthetic demo ribbon should be displayed in demo mode."""
        page.goto(f"{BASE_URL}/?demo=synthetic&tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator(".banner.warn").first).to_contain_text("SYNTHETIC DEMO")

    def test_synthetic_api_status(self, page: Page, api_server, mock_all_empty):
        """API status should show synthetic demo in demo mode."""
        page.goto(f"{BASE_URL}/?demo=synthetic&tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#apiStatus")).to_contain_text("SYNTHETIC DEMO")

    def test_synthetic_exit_button(self, page: Page, api_server, mock_all_empty):
        """Exit synthetic demo button should be present in demo mode."""
        page.goto(f"{BASE_URL}/?demo=synthetic&tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator('button:has-text("Exit synthetic demo")')).to_be_visible()

    def test_synthetic_exit_demo(self, page: Page, api_server, mock_all_empty):
        """Clicking exit should leave synthetic demo mode."""
        page.goto(f"{BASE_URL}/?demo=synthetic&tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        page.click('button:has-text("Exit synthetic demo")')
        page.wait_for_timeout(500)
        expect(page).not_to_have_url(f"{BASE_URL}/?demo=synthetic")

    def test_synthetic_quarantine_message(self, page: Page, api_server, mock_all_empty):
        """Synthetic data should show quarantine message."""
        page.goto(f"{BASE_URL}/?demo=synthetic&tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#qualityState")).to_contain_text("SYNTHETIC DEMO DATA")

    def test_synthetic_kpi_not_verified(self, page: Page, api_server, mock_all_empty):
        """KPIs should show Not verified in synthetic mode."""
        page.goto(f"{BASE_URL}/?demo=synthetic&tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator('[data-kpi="facility_energy_kwh"]')).to_have_text("Not verified")
