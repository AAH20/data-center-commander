"""E2E tests for the Operations Queue / Workflows view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import navigate_to

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestWorkflowsView:
    """Test the Lifecycle operations queue view."""

    def test_workflows_view_title(self, page: Page, api_server, mock_all_empty):
        """Workflows view should have correct title."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        expect(page.locator("#view-workflows h2")).to_contain_text("Lifecycle operations queue")

    def test_workflows_view_description(self, page: Page, api_server, mock_all_empty):
        """Workflows view should have description."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        expect(page.locator("#view-workflows p").first).to_contain_text("Demand")

    def test_workflow_search_input(self, page: Page, api_server, mock_all_empty):
        """Workflow search input should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        expect(page.locator("#workflowSearch")).to_be_visible()

    def test_workflow_status_filter(self, page: Page, api_server, mock_all_empty):
        """Workflow status filter should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        expect(page.locator("#workflowStatus")).to_be_visible()

    def test_export_workflows_button(self, page: Page, api_server, mock_all_empty):
        """Export CSV button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        expect(page.locator("#exportWorkflows")).to_be_visible()

    def test_review_sources_button(self, page: Page, api_server, mock_all_empty):
        """Review source connections button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        expect(page.locator('button[data-goto="integrations"]')).to_be_visible()

    def test_workflow_summary_present(self, page: Page, api_server, mock_all_empty):
        """Workflow summary should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        expect(page.locator("#workflowSummary")).to_be_visible()

    def test_workflow_table_empty(self, page: Page, api_server, mock_all_empty):
        """Workflow table should show empty state."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        expect(page.locator("#workflowTable")).to_contain_text("No workflow records")

    def test_workflows_view_hidden_by_default(self, page: Page, api_server, mock_all_empty):
        """Workflows view should be hidden by default."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        expect(page.locator("#view-workflows")).not_to_have_class(re.compile(r"\bactive\b"))

    def test_workflows_nav_active(self, page: Page, api_server, mock_all_empty):
        """Workflows nav should be active when on workflows view."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        expect(page.locator('.nav [data-view="workflows"]')).to_have_class(re.compile(r"\bactive\b"))

    def test_workflow_status_options(self, page: Page, api_server, mock_all_empty):
        """Workflow status filter should have correct options."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        options = page.locator("#workflowStatus option")
        assert options.count() == 5  # All + 4 statuses

    def test_workflow_search_filters(self, page: Page, api_server, mock_workflows):
        """Search should filter workflow results."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        page.wait_for_timeout(500)
        page.fill("#workflowSearch", "UPS")
        page.wait_for_timeout(300)
        expect(page.locator("#workflowSummary")).to_contain_text("1 of 2")

    def test_workflow_status_filter_applies(self, page: Page, api_server, mock_workflows):
        """Status filter should filter workflow results."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        page.wait_for_timeout(500)
        page.select_option("#workflowStatus", "open")
        page.wait_for_timeout(300)
        expect(page.locator("#workflowSummary")).to_contain_text("1 of 2")

    def test_export_workflows_download(self, page: Page, api_server, mock_workflows):
        """Export workflows should trigger CSV download."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        page.wait_for_timeout(500)
        with page.expect_download() as download_info:
            page.click("#exportWorkflows")
        download = download_info.value
        assert download.suggested_filename == "dcc-operations-queue.csv"

    def test_review_sources_navigates(self, page: Page, api_server, mock_all_empty):
        """Review source connections should navigate to integrations."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "workflows")
        page.evaluate(f'document.querySelector(\'button[data-goto=\"integrations\"]\').click()')
        expect(page.locator("#view-integrations")).to_have_class(re.compile(r"\bactive\b"))
