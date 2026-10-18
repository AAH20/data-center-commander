"""E2E tests for the Estate & Lifecycle / Assets view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import navigate_to

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestAssetsView:
    """Test the Estate & lifecycle view."""

    def test_assets_view_title(self, page: Page, api_server, mock_all_empty):
        """Assets view should have correct title."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        expect(page.locator("#view-assets h2")).to_contain_text("Estate")

    def test_assets_view_description(self, page: Page, api_server, mock_all_empty):
        """Assets view should have description."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        expect(page.locator("#view-assets p").first).to_contain_text("Sites, facility spaces")

    def test_facility_view_empty(self, page: Page, api_server, mock_all_empty):
        """Facility view should show empty state."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        expect(page.locator("#facilityView")).to_contain_text("No facility records")

    def test_asset_view_empty(self, page: Page, api_server, mock_all_empty):
        """Asset view should show empty state."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        expect(page.locator("#assetView")).to_contain_text("No asset records")

    def test_topology_graph_present(self, page: Page, api_server, mock_all_empty):
        """Topology graph container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        expect(page.locator("#topologyGraph")).to_be_visible()

    def test_topology_details_present(self, page: Page, api_server, mock_all_empty):
        """Topology details container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        expect(page.locator("#topologyDetails")).to_be_visible()

    def test_refresh_topology_button(self, page: Page, api_server, mock_all_empty):
        """Refresh topology button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        expect(page.locator("#refreshTopology")).to_be_visible()

    def test_assets_view_hidden_by_default(self, page: Page, api_server, mock_all_empty):
        """Assets view should be hidden by default."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        expect(page.locator("#view-assets")).not_to_have_class(re.compile(r"\bactive\b"))

    def test_assets_nav_active(self, page: Page, api_server, mock_all_empty):
        """Assets nav should be active when on assets view."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        expect(page.locator('.nav [data-view="assets"]')).to_have_class(re.compile(r"\bactive\b"))

    def test_topology_controls_present(self, page: Page, api_server, mock_all_empty):
        """Topology controls should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        expect(page.locator("#topologyControls")).to_be_visible()
