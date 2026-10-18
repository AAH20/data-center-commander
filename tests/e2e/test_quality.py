"""E2E tests for the Data Quality Dashboard view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import navigate_to

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestQualityDashboard:
    """Test the data quality dashboard view."""

    def test_quality_nav_button(self, page: Page, api_server, mock_all_empty):
        """Quality dashboard nav button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator('.nav [data-view="quality"]')).to_be_visible()

    def test_quality_view_title(self, page: Page, api_server, mock_all_empty):
        """Quality view should have correct title."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "quality")
        expect(page.locator("#view-quality h1")).to_contain_text("Data Quality Dashboard")

    def test_quality_status_banner(self, page: Page, api_server, mock_all_empty):
        """Quality status banner should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "quality")
        expect(page.locator("#qdStatus")).to_be_visible()

    def test_quality_window_selector(self, page: Page, api_server, mock_all_empty):
        """Quality window selector should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "quality")
        expect(page.locator("#qdWindow")).to_be_visible()

    def test_quality_refresh_button(self, page: Page, api_server, mock_all_empty):
        """Quality refresh button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "quality")
        expect(page.locator("#qdRefresh")).to_be_visible()

    def test_quality_top_cards(self, page: Page, api_server, mock_all_empty):
        """Quality top cards container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "quality")
        expect(page.locator("#qdTopCards")).to_be_visible()

    def test_quality_score_gauges(self, page: Page, api_server, mock_all_empty):
        """Quality score gauges container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "quality")
        expect(page.locator("#qdScoreGauges")).to_be_visible()

    def test_quality_anomalies(self, page: Page, api_server, mock_all_empty):
        """Quality anomalies container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "quality")
        expect(page.locator("#qdAnomalies")).to_be_visible()

    def test_quality_kpi_quality(self, page: Page, api_server, mock_all_empty):
        """Quality KPI quality container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "quality")
        expect(page.locator("#qdKpiQuality")).to_be_visible()

    def test_quality_telemetry_dist(self, page: Page, api_server, mock_all_empty):
        """Quality telemetry distribution container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "quality")
        expect(page.locator("#qdTelemetryDist")).to_be_visible()

    def test_quality_freshness_timeline(self, page: Page, api_server, mock_all_empty):
        """Quality freshness timeline container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "quality")
        expect(page.locator("#qdFreshnessTimeline")).to_be_visible()

    def test_quality_heatmap(self, page: Page, api_server, mock_all_empty):
        """Quality heatmap container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "quality")
        expect(page.locator("#qdHeatmap")).to_be_visible()

    def test_quality_source_freshness(self, page: Page, api_server, mock_all_empty):
        """Quality source freshness container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "quality")
        expect(page.locator("#qdSourceFreshness")).to_be_visible()

    def test_quality_no_tenant_message(self, page: Page, api_server, mock_all_empty):
        """Without tenant, quality should show enter tenant message."""
        page.goto(f"{BASE_URL}/")
        page.wait_for_timeout(500)
        navigate_to(page, "quality")
        expect(page.locator("#qdStatus")).to_contain_text("Enter a tenant UUID")

    def test_quality_view_hidden_by_default(self, page: Page, api_server, mock_all_empty):
        """Quality view should be hidden by default."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#view-quality")).not_to_have_class(re.compile(r"\bactive\b"))

    def test_quality_hash_navigation(self, page: Page, api_server, mock_all_empty):
        """URL hash should navigate to quality view."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}#quality")
        page.wait_for_timeout(500)
        expect(page.locator("#view-quality")).to_have_class(re.compile(r"\bactive\b"))

    def test_quality_window_options(self, page: Page, api_server, mock_all_empty):
        """Quality window should have correct options."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "quality")
        options = page.locator("#qdWindow option")
        assert options.count() == 3
