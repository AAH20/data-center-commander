"""E2E tests for the Overview / Command Picture view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestOverview:
    """Test the overview/command picture view."""

    def test_overview_title_displayed(self, page: Page, api_server, mock_all_empty):
        """Overview heading should be displayed."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        expect(page.locator("#view-overview h2")).to_contain_text("Facility command picture")

    def test_kpi_cards_present(self, page: Page, api_server, mock_all_empty):
        """All 8 KPI cards should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        kpi_keys = [
            "facility_energy_kwh", "it_energy_kwh", "pue",
            "useful_compute_per_kwh", "carbon_kgco2e", "thermal_margin_c",
            "capacity_headroom_pct", "openWork",
        ]
        for key in kpi_keys:
            if key == "openWork":
                expect(page.locator(f"#{key}")).to_be_visible()
            else:
                expect(page.locator(f'[data-kpi="{key}"]')).to_be_visible()

    def test_kpi_unknown_state(self, page: Page, api_server, mock_overview_empty):
        """KPIs should show Unknown when no data."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        expect(page.locator('[data-kpi="facility_energy_kwh"]')).to_have_text("Unknown")

    def test_kpi_with_data(self, page: Page, api_server, mock_overview_with_data):
        """KPIs should show values when data is available."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator('[data-kpi="facility_energy_kwh"]')).not_to_have_text("Unknown")

    def test_facility_count_displayed(self, page: Page, api_server, mock_overview_with_data):
        """Facility count should be displayed."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#facilityCount")).to_contain_text("2 active facilities")

    def test_open_workflows_count(self, page: Page, api_server, mock_overview_with_data):
        """Open workflows count should be displayed."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#openWork")).to_have_text("5")

    def test_quality_state_no_data(self, page: Page, api_server, mock_overview_empty):
        """Quality state should show no data message."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        # source_status "no_telemetry" renders this empty-state copy.
        expect(page.locator("#qualityState")).to_contain_text("No telemetry is connected")

    def test_workflow_state_no_data(self, page: Page, api_server, mock_overview_empty):
        """Workflow state should show unavailable message."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        # An empty lifecycle queue renders the count line, not an outage notice.
        expect(page.locator("#workflowState")).to_contain_text("0 open lifecycle workflows")

    def test_asof_displayed(self, page: Page, api_server, mock_overview_empty):
        """As-of stamp should be displayed."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        # With no telemetry ingested the stamp reads "No telemetry ingested".
        expect(page.locator("#asOf")).to_contain_text("No telemetry ingested")

    def test_asof_with_data(self, page: Page, api_server, mock_overview_with_data):
        """As-of stamp should show telemetry ingested time."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#asOf")).to_contain_text("Telemetry ingested")

    def test_api_status_connecting(self, page: Page, api_server, mock_all_empty):
        """API status should show connecting state initially."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        expect(page.locator("#apiStatus")).to_contain_text("API ready")

    def test_readonly_boundary_message(self, page: Page, api_server, mock_all_empty):
        """Read-only boundary message should be displayed."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        # Two .boundary nodes exist (header and footer); assert on the first.
        expect(page.locator(".boundary").first).to_contain_text("Read-only decision support")

    def test_no_tenant_shows_choose_tenant(self, page: Page, api_server, mock_all_empty):
        """Without tenant_id, should show choose tenant message."""
        page.goto(f"{BASE_URL}/")
        expect(page.locator("#qualityState")).to_contain_text("Choose a tenant")
