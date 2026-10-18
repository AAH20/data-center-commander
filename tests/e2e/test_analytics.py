"""E2E tests for the Data Science & BI / Analytics view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import navigate_to

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestAnalyticsView:
    """Test the Data science & BI view."""

    def test_analytics_view_title(self, page: Page, api_server, mock_all_empty):
        """Analytics view should have correct title."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#view-analytics h1")).to_contain_text("Data science")

    def test_analytics_status_banner(self, page: Page, api_server, mock_all_empty):
        """Analytics status banner should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#analyticsStatus")).to_be_visible()

    def test_analytics_cards_present(self, page: Page, api_server, mock_all_empty):
        """Analytics cards container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#analyticsCards")).to_be_visible()

    def test_analytics_window_selector(self, page: Page, api_server, mock_all_empty):
        """Analysis window selector should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#analysisWindow")).to_be_visible()

    def test_analytics_refresh_button(self, page: Page, api_server, mock_all_empty):
        """Recompute insights button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#refreshAnalytics")).to_be_visible()

    def test_analytics_export_button(self, page: Page, api_server, mock_all_empty):
        """Export snapshot button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#exportAnalytics")).to_be_visible()

    def test_analytics_trend_charts(self, page: Page, api_server, mock_all_empty):
        """Trend charts container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#trendCharts")).to_be_visible()

    def test_analytics_quality_insights(self, page: Page, api_server, mock_all_empty):
        """Quality insights container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#qualityInsights")).to_be_visible()

    def test_analytics_kpi_quality_table(self, page: Page, api_server, mock_all_empty):
        """KPI quality table container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#kpiQualityTable")).to_be_visible()

    def test_analytics_telemetry_quality(self, page: Page, api_server, mock_all_empty):
        """Telemetry quality table container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#telemetryQualityTable")).to_be_visible()

    def test_analytics_workflow_health(self, page: Page, api_server, mock_all_empty):
        """Workflow health table container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#workflowHealthTable")).to_be_visible()

    def test_analytics_capacity_insight(self, page: Page, api_server, mock_all_empty):
        """Capacity insight container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#capacityInsight")).to_be_visible()

    def test_analytics_forecast_state(self, page: Page, api_server, mock_all_empty):
        """Forecast state tag should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#forecastState")).to_be_visible()

    def test_analytics_model_readiness(self, page: Page, api_server, mock_all_empty):
        """Model readiness tag should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#modelReadiness")).to_be_visible()

    def test_analytics_window_change(self, page: Page, api_server, mock_all_empty):
        """Changing analysis window should trigger reload."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        page.select_option("#analysisWindow", "7")
        page.wait_for_timeout(500)
        expect(page.locator("#analyticsStatus")).to_be_visible()

    def test_analytics_no_tenant_message(self, page: Page, api_server, mock_all_empty):
        """Without tenant, analytics should show enter tenant message."""
        page.goto(f"{BASE_URL}/")
        navigate_to(page, "analytics")
        expect(page.locator("#analyticsStatus")).to_contain_text("Enter a tenant UUID")

    def test_analytics_refresh_click(self, page: Page, api_server, mock_all_empty):
        """Clicking refresh should update analytics."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        page.click("#refreshAnalytics")
        page.wait_for_timeout(500)
        expect(page.locator("#analyticsStatus")).to_be_visible()

    def test_analytics_export_click(self, page: Page, api_server, mock_all_empty):
        """Clicking export should trigger download."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        with page.expect_download() as download_info:
            page.click("#exportAnalytics")
        download = download_info.value
        assert download.suggested_filename == "dcc-bi-snapshot.json"
