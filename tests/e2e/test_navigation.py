"""E2E tests for navigation between views."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import base_url, navigate_to

TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestNavigation:
    """Test navigation between all main views."""

    def test_default_view_is_overview(self, page: Page, api_server, mock_all_empty):
        """Default view should be the overview/command picture."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        expect(page.locator("#view-overview")).to_have_class(re.compile(r"\bactive\b"))

    def test_nav_to_energy(self, page: Page, api_server, mock_all_empty):
        """Clicking Energy & carbon nav should activate that view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "energy")
        expect(page.locator("#view-energy")).to_have_class(re.compile(r"\bactive\b"))

    def test_nav_to_analytics(self, page: Page, api_server, mock_all_empty):
        """Clicking Data science & BI nav should activate analytics view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "analytics")
        expect(page.locator("#view-analytics")).to_have_class(re.compile(r"\bactive\b"))

    def test_nav_to_finance(self, page: Page, api_server, mock_all_empty):
        """Clicking Sizing & economics nav should activate finance view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#view-finance")).to_have_class(re.compile(r"\bactive\b"))

    def test_nav_to_capacity(self, page: Page, api_server, mock_all_empty):
        """Clicking Capacity & resilience nav should activate capacity view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "capacity")
        expect(page.locator("#view-capacity")).to_have_class(re.compile(r"\bactive\b"))

    def test_nav_to_assets(self, page: Page, api_server, mock_all_empty):
        """Clicking Estate & lifecycle nav should activate assets view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "assets")
        expect(page.locator("#view-assets")).to_have_class(re.compile(r"\bactive\b"))

    def test_nav_to_reliability(self, page: Page, api_server, mock_all_empty):
        """Clicking Reliability nav should activate reliability view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "reliability")
        expect(page.locator("#view-reliability")).to_have_class(re.compile(r"\bactive\b"))

    def test_nav_to_workflows(self, page: Page, api_server, mock_all_empty):
        """Clicking Operations queue nav should activate workflows view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        expect(page.locator("#view-workflows")).to_have_class(re.compile(r"\bactive\b"))

    def test_nav_to_integrations(self, page: Page, api_server, mock_all_empty):
        """Clicking Integrations nav should activate integrations view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "integrations")
        expect(page.locator("#view-integrations")).to_have_class(re.compile(r"\bactive\b"))

    def test_nav_to_evidence(self, page: Page, api_server, mock_all_empty):
        """Clicking Evidence & audit nav should activate evidence view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "evidence")
        expect(page.locator("#view-evidence")).to_have_class(re.compile(r"\bactive\b"))

    def test_breadcrumb_updates_on_nav(self, page: Page, api_server, mock_all_empty):
        """Breadcrumb should update when navigating."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "energy")
        expect(page.locator("#crumb")).to_contain_text("Energy")

    def test_hash_navigation(self, page: Page, api_server, mock_all_empty):
        """URL hash should navigate to the correct view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}#energy")
        expect(page.locator("#view-energy")).to_have_class(re.compile(r"\bactive\b"))

    def test_only_one_view_active(self, page: Page, api_server, mock_all_empty):
        """Only one view should be active at a time."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "energy")
        navigate_to(page, "finance")
        active_views = page.locator(".view.active")
        assert active_views.count() == 1

    def test_nav_button_highlight(self, page: Page, api_server, mock_all_empty):
        """Active nav button should have active class."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        navigate_to(page, "energy")
        expect(page.locator('.nav [data-view="energy"]')).to_have_class(re.compile(r"\bactive\b"))
