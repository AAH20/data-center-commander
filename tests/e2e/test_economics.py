"""E2E tests for the Cost Intelligence / Economics dashboard view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import navigate_to

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestEconomicsDashboard:
    """Test the cost intelligence dashboard view."""

    def test_economics_nav_button(self, page: Page, api_server, mock_all_empty):
        """Economics dashboard nav button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator('.nav [data-view="economics"]')).to_be_visible()

    def test_economics_view_title(self, page: Page, api_server, mock_all_empty):
        """Economics view should have correct title."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "economics")
        expect(page.locator("#view-economics h1")).to_contain_text("Cost intelligence dashboard")

    def test_economics_banner(self, page: Page, api_server, mock_all_empty):
        """Economics banner container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "economics")
        # #econBanner: data-driven container -- rendered empty by the empty-data fixture,
        # so it has no box to be visible. Assert it is mounted instead.
        expect(page.locator("#econBanner")).to_be_attached()

    def test_economics_tabs(self, page: Page, api_server, mock_all_empty):
        """Economics tabs should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "economics")
        expect(page.locator(".econ-tabs")).to_be_visible()

    def test_economics_tab_breakdown(self, page: Page, api_server, mock_all_empty):
        """Cost breakdown tab should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "economics")
        expect(page.locator("#econ-tab-breakdown")).to_be_visible()

    def test_economics_tab_trends(self, page: Page, api_server, mock_all_empty):
        """Trends tab should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "economics")
        expect(page.locator("#econ-tab-trends")).to_be_visible()

    def test_economics_tab_compare(self, page: Page, api_server, mock_all_empty):
        """Estimate vs actual tab should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "economics")
        expect(page.locator("#econ-tab-compare")).to_be_visible()

    def test_economics_tab_prices(self, page: Page, api_server, mock_all_empty):
        """Price book tab should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "economics")
        expect(page.locator("#econ-tab-prices")).to_be_visible()

    def test_economics_breakdown_content(self, page: Page, api_server, mock_all_empty):
        """Breakdown content container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "economics")
        expect(page.locator("#econBreakdownContent")).to_be_visible()

    def test_economics_trends_content(self, page: Page, api_server, mock_all_empty):
        """Trends content container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "economics")
        # #econTrendsContent: data-driven container -- rendered empty by the empty-data fixture,
        # so it has no box to be visible. Assert it is mounted instead.
        expect(page.locator("#econTrendsContent")).to_be_attached()

    def test_economics_compare_content(self, page: Page, api_server, mock_all_empty):
        """Compare content container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "economics")
        # #econCompareContent: data-driven container -- rendered empty by the empty-data fixture,
        # so it has no box to be visible. Assert it is mounted instead.
        expect(page.locator("#econCompareContent")).to_be_attached()

    def test_economics_prices_content(self, page: Page, api_server, mock_all_empty):
        """Prices content container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "economics")
        # #econPricesContent: data-driven container -- rendered empty by the empty-data fixture,
        # so it has no box to be visible. Assert it is mounted instead.
        expect(page.locator("#econPricesContent")).to_be_attached()

    def test_economics_tab_switching(self, page: Page, api_server, mock_all_empty):
        """Clicking tabs should switch panels."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "economics")
        page.click("#econ-tab-trends")
        expect(page.locator("#econ-panel-trends")).not_to_be_hidden()
        expect(page.locator("#econ-panel-breakdown")).to_be_hidden()

    def test_economics_view_hidden_by_default(self, page: Page, api_server, mock_all_empty):
        """Economics view should be hidden by default."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#view-economics")).not_to_have_class(re.compile(r"\bactive\b"))

    def test_economics_hash_navigation(self, page: Page, api_server, mock_all_empty):
        """URL hash should navigate to economics view."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}#economics")
        page.wait_for_timeout(500)
        expect(page.locator("#view-economics")).to_have_class(re.compile(r"\bactive\b"))

    def test_economics_no_tenant_banner(self, page: Page, api_server, mock_all_empty):
        """Without tenant, economics should show warning banner."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_timeout(500)
        navigate_to(page, "economics")
        expect(page.locator("#econBanner")).to_contain_text("Select a tenant UUID")
