"""E2E tests for the Asset Topology view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import base_url, navigate_to

TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestTopology:
    """Test the asset dependency graph / topology view."""

    def test_topology_search_input(self, page: Page, api_server, mock_all_empty):
        """Topology search input should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        page.wait_for_timeout(500)
        expect(page.locator("#topologySearch")).to_be_visible()

    def test_topology_relation_filter(self, page: Page, api_server, mock_all_empty):
        """Topology relation filter should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        page.wait_for_timeout(500)
        expect(page.locator("#topologyRelation")).to_be_visible()

    def test_topology_focus_select(self, page: Page, api_server, mock_all_empty):
        """Topology focus select should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        page.wait_for_timeout(500)
        expect(page.locator("#topologyFocus")).to_be_visible()

    def test_topology_trace_button(self, page: Page, api_server, mock_all_empty):
        """Topology trace button should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        page.wait_for_timeout(500)
        expect(page.locator("#topologyTrace")).to_be_visible()

    def test_topology_graph_container(self, page: Page, api_server, mock_all_empty):
        """Topology graph container should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        page.wait_for_timeout(500)
        expect(page.locator("#topologyGraph")).to_be_visible()

    def test_topology_details_container(self, page: Page, api_server, mock_all_empty):
        """Topology details container should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        page.wait_for_timeout(500)
        expect(page.locator("#topologyDetails")).to_be_visible()

    def test_topology_details_initial_text(self, page: Page, api_server, mock_all_empty):
        """Topology details should show initial text."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        page.wait_for_timeout(500)
        expect(page.locator("#topologyDetails")).to_contain_text("Choose a node")

    def test_topology_refresh_button(self, page: Page, api_server, mock_all_empty):
        """Refresh topology button should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        page.wait_for_timeout(500)
        expect(page.locator("#refreshTopology")).to_be_visible()

    def test_topology_empty_state(self, page: Page, api_server, mock_all_empty):
        """Topology should show empty state when no data."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        page.wait_for_timeout(500)
        expect(page.locator("#topologyGraph")).to_contain_text("No asset relationships")

    def test_topology_search_input_typing(self, page: Page, api_server, mock_all_empty):
        """Typing in topology search should not error."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        page.wait_for_timeout(500)
        page.fill("#topologySearch", "server")
        page.wait_for_timeout(300)
        expect(page.locator("#topologySearch")).to_have_value("server")

    def test_topology_trace_click(self, page: Page, api_server, mock_all_empty):
        """Clicking trace button should not error."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        page.wait_for_timeout(500)
        page.click("#topologyTrace")
        page.wait_for_timeout(300)
        expect(page.locator("#topologyGraph")).to_be_visible()
