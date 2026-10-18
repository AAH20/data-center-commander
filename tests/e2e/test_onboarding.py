"""E2E tests for onboarding flow."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestOnboarding:
    """Test onboarding dialog and flow."""

    def test_onboarding_dialog_present(self, page: Page, api_server, mock_all_empty):
        """Onboarding dialog should be present in DOM."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        expect(page.locator(".dcc-dialog")).to_be_attached()

    def test_onboarding_auto_shows_first_run(self, page: Page, api_server, mock_all_empty):
        """Onboarding should auto-show on first run."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        dialog = page.locator(".dcc-dialog")
        assert dialog.evaluate("el => el.open")

    def test_onboarding_profile_select(self, page: Page, api_server, mock_all_empty):
        """Profile select should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator('select[name="profile"]')).to_be_visible()

    def test_onboarding_objective_select(self, page: Page, api_server, mock_all_empty):
        """Objective select should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator('select[name="objective"]')).to_be_visible()

    def test_onboarding_profile_options(self, page: Page, api_server, mock_all_empty):
        """Profile select should have correct options."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        options = page.locator('select[name="profile"] option')
        assert options.count() == 5

    def test_onboarding_objective_options(self, page: Page, api_server, mock_all_empty):
        """Objective select should have correct options."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        options = page.locator('select[name="objective"] option')
        assert options.count() == 4

    def test_onboarding_cancel_button(self, page: Page, api_server, mock_all_empty):
        """Cancel button should close dialog."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        page.click("#dccSetupCancel")
        page.wait_for_timeout(300)
        dialog = page.locator(".dcc-dialog")
        assert not dialog.evaluate("el => el.open")

    def test_onboarding_submit_saves_profile(self, page: Page, api_server, mock_all_empty):
        """Submitting onboarding should save profile."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        page.select_option('select[name="profile"]', "enterprise")
        page.select_option('select[name="objective"]', "cost")
        page.click('button[type="submit"]')
        page.wait_for_timeout(300)
        dialog = page.locator(".dcc-dialog")
        assert not dialog.evaluate("el => el.open")

    def test_onboarding_profile_badge(self, page: Page, api_server, mock_all_empty):
        """Profile badge should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#dccProfileBadge")).to_be_visible()

    def test_onboarding_start_button(self, page: Page, api_server, mock_all_empty):
        """Start onboarding button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#dccStartOnboarding")).to_be_visible()

    def test_onboarding_start_button_opens_dialog(self, page: Page, api_server, mock_all_empty):
        """Start onboarding button should open dialog."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        page.click("#dccStartOnboarding")
        page.wait_for_timeout(300)
        dialog = page.locator(".dcc-dialog")
        assert dialog.evaluate("el => el.open")

    def test_onboarding_live_notice(self, page: Page, api_server, mock_all_empty):
        """Live data boundary notice should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#dccLiveNotice")).to_be_visible()

    def test_onboarding_export_button(self, page: Page, api_server, mock_all_empty):
        """Export due-diligence snapshot button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator('button:has-text("Export due-diligence snapshot")')).to_be_visible()

    def test_onboarding_export_download(self, page: Page, api_server, mock_all_empty):
        """Export should trigger JSON download."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        with page.expect_download() as download_info:
            page.click('button:has-text("Export due-diligence snapshot")')
        download = download_info.value
        assert download.suggested_filename == "dcc-due-diligence-snapshot.json"

    def test_onboarding_open_integrations(self, page: Page, api_server, mock_all_empty):
        """Open integrations button should navigate to integrations."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        page.evaluate(\'document.querySelector("#dccOpenIntegrations").click()\')
        page.wait_for_timeout(300)
        expect(page.locator("#view-integrations")).to_have_class(re.compile(r"\bactive\b"))

    def test_onboarding_tags_present(self, page: Page, api_server, mock_all_empty):
        """Onboarding tags should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator(".dcc-tag").first).to_be_visible()

    def test_onboarding_steps_present(self, page: Page, api_server, mock_all_empty):
        """Onboarding steps should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator(".dcc-step").first).to_be_visible()
