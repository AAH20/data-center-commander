"""E2E tests for the Forecast Dashboard view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import navigate_to

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestForecastDashboard:
    """Test the forecast visualization dashboard."""

    def test_forecast_nav_button(self, page: Page, api_server, mock_all_empty):
        """Forecast dashboard nav button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator('.nav [data-view="forecast"]')).to_be_visible()

    def test_forecast_view_title(self, page: Page, api_server, mock_all_empty):
        """Forecast view should have correct title."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "forecast")
        expect(page.locator("#view-forecast h1")).to_contain_text("Forecast visualization")

    def test_forecast_status_banner(self, page: Page, api_server, mock_all_empty):
        """Forecast status banner should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "forecast")
        expect(page.locator("#fd-status")).to_be_visible()

    def test_forecast_horizon_selector(self, page: Page, api_server, mock_all_empty):
        """Forecast horizon selector should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "forecast")
        expect(page.locator("#fd-horizon")).to_be_visible()

    def test_forecast_min_points_selector(self, page: Page, api_server, mock_all_empty):
        """Forecast min points selector should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "forecast")
        expect(page.locator("#fd-min-points")).to_be_visible()

    def test_forecast_refresh_button(self, page: Page, api_server, mock_all_empty):
        """Forecast refresh button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "forecast")
        expect(page.locator("#fd-refresh")).to_be_visible()

    def test_forecast_export_button(self, page: Page, api_server, mock_all_empty):
        """Forecast export button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "forecast")
        expect(page.locator("#fd-export")).to_be_visible()

    def test_forecast_charts_container(self, page: Page, api_server, mock_all_empty):
        """Forecast charts container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "forecast")
        expect(page.locator("#fd-charts")).to_be_visible()

    def test_forecast_summary_container(self, page: Page, api_server, mock_all_empty):
        """Forecast summary container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "forecast")
        expect(page.locator("#fd-summary")).to_be_visible()

    def test_forecast_no_tenant_message(self, page: Page, api_server, mock_all_empty):
        """Without tenant, forecast should show enter tenant message."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_timeout(500)
        navigate_to(page, "forecast")
        expect(page.locator("#fd-status")).to_contain_text("Enter a tenant UUID")

    def test_forecast_horizon_options(self, page: Page, api_server, mock_all_empty):
        """Forecast horizon should have correct options."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "forecast")
        options = page.locator("#fd-horizon option")
        assert options.count() == 3

    def test_forecast_min_points_options(self, page: Page, api_server, mock_all_empty):
        """Forecast min points should have correct options."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "forecast")
        options = page.locator("#fd-min-points option")
        assert options.count() == 4

    def test_forecast_view_hidden_by_default(self, page: Page, api_server, mock_all_empty):
        """Forecast view should be hidden by default."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#view-forecast")).not_to_have_class(re.compile(r"\bactive\b"))

    def test_forecast_hash_navigation(self, page: Page, api_server, mock_all_empty):
        """URL hash should navigate to forecast view."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}#forecast")
        page.wait_for_timeout(500)
        expect(page.locator("#view-forecast")).to_have_class(re.compile(r"\bactive\b"))
