"""E2E tests for the Workloads & Assurance / Critical Environments views."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import base_url, navigate_to

TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestWorkloadsView:
    """Test the Suggested workloads blueprints view."""

    def test_workloads_nav_button(self, page: Page, api_server, mock_all_empty):
        """Workloads nav button should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator('.nav [data-view="workloads"]')).to_be_visible()

    def test_workloads_view_title(self, page: Page, api_server, mock_all_empty):
        """Workloads view should have correct title."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "workloads")
        expect(page.locator("#view-workloads h1")).to_contain_text("Suggested workload blueprints")

    def test_workloads_search_input(self, page: Page, api_server, mock_all_empty):
        """Workload search input should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "workloads")
        expect(page.locator("#workloadSearch")).to_be_visible()

    def test_workloads_tier_filter(self, page: Page, api_server, mock_all_empty):
        """Workload tier filter should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "workloads")
        expect(page.locator("#workloadTier")).to_be_visible()

    def test_workloads_mode_filter(self, page: Page, api_server, mock_all_empty):
        """Workload mode filter should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "workloads")
        expect(page.locator("#workloadMode")).to_be_visible()

    def test_workloads_count(self, page: Page, api_server, mock_all_empty):
        """Workload count should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "workloads")
        expect(page.locator("#workloadCount")).to_be_visible()

    def test_workloads_cards(self, page: Page, api_server, mock_all_empty):
        """Workload cards container should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "workloads")
        expect(page.locator("#workloadCards")).to_be_visible()

    def test_workloads_view_hidden_by_default(self, page: Page, api_server, mock_all_empty):
        """Workloads view should be hidden by default."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#view-workloads")).not_to_have_class(re.compile(r"\bactive\b"))

    def test_workloads_hash_navigation(self, page: Page, api_server, mock_all_empty):
        """URL hash should navigate to workloads view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}#workloads")
        page.wait_for_timeout(500)
        expect(page.locator("#view-workloads")).to_have_class(re.compile(r"\bactive\b"))

    def test_workloads_tier_options(self, page: Page, api_server, mock_all_empty):
        """Workload tier should have correct options."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "workloads")
        options = page.locator("#workloadTier option")
        assert options.count() == 6

    def test_workloads_mode_options(self, page: Page, api_server, mock_all_empty):
        """Workload mode should have correct options."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "workloads")
        options = page.locator("#workloadMode option")
        assert options.count() == 6

    def test_workloads_search_filters(self, page: Page, api_server, mock_all_empty):
        """Search should filter workload cards."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "workloads")
        page.fill("#workloadSearch", "enterprise")
        page.wait_for_timeout(300)
        expect(page.locator("#workloadCount")).to_contain_text("of 16")

    def test_workloads_tier_filter_applies(self, page: Page, api_server, mock_all_empty):
        """Tier filter should filter workload cards."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "workloads")
        page.select_option("#workloadTier", "solo")
        page.wait_for_timeout(300)
        expect(page.locator("#workloadCount")).to_contain_text("of 16")


class TestCriticalEnvironmentsView:
    """Test the Critical environments & GRC view."""

    def test_critical_nav_button(self, page: Page, api_server, mock_all_empty):
        """Critical environments nav button should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator('.nav [data-view="critical"]')).to_be_visible()

    def test_critical_view_title(self, page: Page, api_server, mock_all_empty):
        """Critical view should have correct title."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "critical")
        expect(page.locator("#view-critical h1")).to_contain_text("Critical environments")

    def test_critical_profile_filter(self, page: Page, api_server, mock_all_empty):
        """Critical profile filter should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "critical")
        expect(page.locator("#criticalProfile")).to_be_visible()

    def test_critical_export_button(self, page: Page, api_server, mock_all_empty):
        """Export GRC checklist button should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "critical")
        expect(page.locator("#exportGrc")).to_be_visible()

    def test_critical_summary(self, page: Page, api_server, mock_all_empty):
        """Critical summary container should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "critical")
        expect(page.locator("#criticalSummary")).to_be_visible()

    def test_critical_controls(self, page: Page, api_server, mock_all_empty):
        """Critical controls table should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "critical")
        expect(page.locator("#criticalControls")).to_be_visible()

    def test_critical_view_hidden_by_default(self, page: Page, api_server, mock_all_empty):
        """Critical view should be hidden by default."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#view-critical")).not_to_have_class(re.compile(r"\bactive\b"))

    def test_critical_hash_navigation(self, page: Page, api_server, mock_all_empty):
        """URL hash should navigate to critical view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}#critical")
        page.wait_for_timeout(500)
        expect(page.locator("#view-critical")).to_have_class(re.compile(r"\bactive\b"))

    def test_critical_profile_options(self, page: Page, api_server, mock_all_empty):
        """Critical profile should have correct options."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "critical")
        options = page.locator("#criticalProfile option")
        assert options.count() == 8

    def test_critical_export_download(self, page: Page, api_server, mock_all_empty):
        """Export GRC should trigger CSV download."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "critical")
        with page.expect_download() as download_info:
            page.click("#exportGrc")
        download = download_info.value
        assert download.suggested_filename == "critical-environment-grc-checklist.csv"

    def test_critical_fail_closed_banner(self, page: Page, api_server, mock_all_empty):
        """Fail-closed assurance banner should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "critical")
        expect(page.locator("#view-critical .banner.warn")).to_contain_text("Fail-closed assurance")
