"""E2E tests for the Reliability & Maintenance view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import base_url, navigate_to

TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestReliabilityView:
    """Test the Reliability & maintenance view."""

    def test_reliability_view_title(self, page: Page, api_server, mock_all_empty):
        """Reliability view should have correct title."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "reliability")
        expect(page.locator("#view-reliability h2")).to_contain_text("Reliability")

    def test_reliability_view_description(self, page: Page, api_server, mock_all_empty):
        """Reliability view should have description."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "reliability")
        expect(page.locator("#view-reliability p").first).to_contain_text("Work-order")

    def test_reliability_view_empty(self, page: Page, api_server, mock_all_empty):
        """Reliability view should show empty state."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "reliability")
        expect(page.locator("#reliabilityView")).to_contain_text("No records returned by the live database query")

    def test_reliability_view_hidden_by_default(self, page: Page, api_server, mock_all_empty):
        """Reliability view should be hidden by default."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        expect(page.locator("#view-reliability")).not_to_have_class(re.compile(r"\bactive\b"))

    def test_reliability_nav_active(self, page: Page, api_server, mock_all_empty):
        """Reliability nav should be active when on reliability view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "reliability")
        expect(page.locator('.nav [data-view="reliability"]')).to_have_class(re.compile(r"\bactive\b"))
