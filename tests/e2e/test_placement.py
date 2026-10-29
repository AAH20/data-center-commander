"""E2E tests for the Placement Comparison view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import base_url, navigate_to

TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestPlacementComparison:
    """Test the on-premises vs cloud placement comparison view."""

    def test_placement_nav_button(self, page: Page, api_server, mock_all_empty):
        """Placement comparison nav button should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator('.nav [data-view="placement"]')).to_be_visible()

    def test_placement_view_title(self, page: Page, api_server, mock_all_empty):
        """Placement view should have correct title."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        expect(page.locator("#view-placement h1")).to_contain_text("On-premises vs cloud")

    def test_placement_workbench(self, page: Page, api_server, mock_all_empty):
        """Placement workbench container should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        expect(page.locator("#placementWorkbench")).to_be_visible()

    def test_placement_tabs(self, page: Page, api_server, mock_all_empty):
        """Placement tabs should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        expect(page.locator(".placement-tabs")).to_be_visible()

    def test_placement_tab_tco(self, page: Page, api_server, mock_all_empty):
        """TCO model tab should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        expect(page.locator("#placement-tab-tco")).to_be_visible()

    def test_placement_tab_fit(self, page: Page, api_server, mock_all_empty):
        """Workload fit tab should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        expect(page.locator("#placement-tab-fit")).to_be_visible()

    def test_placement_tab_gates(self, page: Page, api_server, mock_all_empty):
        """Decision gates tab should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        expect(page.locator("#placement-tab-gates")).to_be_visible()

    def test_placement_form_present(self, page: Page, api_server, mock_all_empty):
        """Placement form should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        expect(page.locator("#placementForm")).to_be_visible()

    def test_placement_results_container(self, page: Page, api_server, mock_all_empty):
        """Placement results container should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        expect(page.locator("#placementResults")).to_be_visible()

    def test_placement_gates_container(self, page: Page, api_server, mock_all_empty):
        """Placement gates container should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        # Empty until a comparison is run: assert it is mounted.
        expect(page.locator("#placementGates")).to_be_attached()

    def test_placement_gates_checkboxes(self, page: Page, api_server, mock_all_empty):
        """Placement gates should have checkboxes."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        page.click("#placement-tab-gates")
        checkboxes = page.locator("[data-placement-gate]")
        assert checkboxes.count() == 11

    def test_placement_gates_summary(self, page: Page, api_server, mock_all_empty):
        """Placement gates summary should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        page.click("#placement-tab-gates")
        # #placementScenarioStatus is the saved-drafts status outside this panel,
        # so it is hidden once the gates tab is selected; assert the gates panel
        # itself is the visible one.
        expect(page.locator("#placement-panel-gates")).to_be_visible()
        expect(page.locator("#placementGates")).to_be_attached()

    def test_placement_export_button(self, page: Page, api_server, mock_all_empty):
        """Export comparison button should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        expect(page.locator("#exportPlacement")).to_be_visible()

    def test_placement_view_hidden_by_default(self, page: Page, api_server, mock_all_empty):
        """Placement view should be hidden by default."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#view-placement")).not_to_have_class(re.compile(r"\bactive\b"))

    def test_placement_hash_navigation(self, page: Page, api_server, mock_all_empty):
        """URL hash should navigate to placement view."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}#placement")
        page.wait_for_timeout(500)
        expect(page.locator("#view-placement")).to_have_class(re.compile(r"\bactive\b"))

    def test_placement_tab_switching(self, page: Page, api_server, mock_all_empty):
        """Clicking tabs should switch panels."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        page.click("#placement-tab-fit")
        expect(page.locator("#placement-panel-fit")).not_to_be_hidden()
        expect(page.locator("#placement-panel-tco")).to_be_hidden()

    def test_placement_scenario_name_input(self, page: Page, api_server, mock_all_empty):
        """Placement scenario name input should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        expect(page.locator("#placementScenarioName")).to_be_visible()

    def test_placement_save_button(self, page: Page, api_server, mock_all_empty):
        """Save draft snapshot button should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        expect(page.locator("#savePlacementScenario")).to_be_visible()

    def test_placement_refresh_button(self, page: Page, api_server, mock_all_empty):
        """Refresh saved drafts button should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        expect(page.locator("#refreshPlacementScenarios")).to_be_visible()

    def test_placement_scenario_status(self, page: Page, api_server, mock_all_empty):
        """Placement scenario status should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        expect(page.locator("#placementScenarioStatus")).to_be_visible()

    def test_placement_scenario_list(self, page: Page, api_server, mock_all_empty):
        """Placement scenario list should be present."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        navigate_to(page, "placement")
        expect(page.locator("#placementScenarioList")).to_be_visible()
