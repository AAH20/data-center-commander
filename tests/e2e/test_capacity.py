"""E2E tests for the Capacity & Resilience view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import base_url, navigate_to

TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestCapacityView:
    """Test the Capacity & resilience view."""

    def test_capacity_view_title(self, page: Page, api_server, mock_all_empty):
        """Capacity view should have correct title."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "capacity")
        expect(page.locator("#view-capacity h2")).to_contain_text("Capacity")

    def test_capacity_view_description(self, page: Page, api_server, mock_all_empty):
        """Capacity view should have description."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "capacity")
        expect(page.locator("#view-capacity p").first).to_contain_text("Usable capacity")

    def test_capacity_view_empty_state(self, page: Page, api_server, mock_all_empty):
        """Capacity view should show empty state."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "capacity")
        expect(page.locator("#capacityView")).to_contain_text("No records returned by the live database query")

    def test_capacity_view_hidden_by_default(self, page: Page, api_server, mock_all_empty):
        """Capacity view should be hidden by default."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        expect(page.locator("#view-capacity")).not_to_have_class(re.compile(r"\bactive\b"))

    def test_capacity_nav_active(self, page: Page, api_server, mock_all_empty):
        """Capacity nav should be active when on capacity view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "capacity")
        expect(page.locator('.nav [data-view="capacity"]')).to_have_class(re.compile(r"\bactive\b"))
