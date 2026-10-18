"""E2E tests for the Azure & Google Cloud pricing module."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import navigate_to

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestAzurePrices:
    """Test the Azure retail prices lookup functionality."""

    def test_azure_price_form_service_name(self, page: Page, api_server, mock_all_empty):
        """Service name input should have default value."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator('input[name="service_name"]')).to_have_value("Virtual Machines")

    def test_azure_price_form_currency_default(self, page: Page, api_server, mock_all_empty):
        """Currency input should have default value."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator('input[name="currency"]')).to_have_value("USD")

    def test_azure_price_status_initial(self, page: Page, api_server, mock_all_empty):
        """Azure price status should show initial message."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#azurePriceStatus")).to_contain_text("No catalog request made")

    def test_azure_price_results_hidden_initially(self, page: Page, api_server, mock_all_empty):
        """Azure price results should be hidden initially."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#azurePriceResults")).to_be_hidden()

    def test_azure_price_form_required_fields(self, page: Page, api_server, mock_all_empty):
        """Azure price form should have required fields."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator('input[name="service_name"]')).to_have_attribute("required", "")
        expect(page.locator('input[name="currency"]')).to_have_attribute("required", "")

    def test_azure_price_form_currency_pattern(self, page: Page, api_server, mock_all_empty):
        """Currency input should have pattern validation."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator('input[name="currency"]')).to_have_attribute("pattern", "[A-Za-z]{3}")

    def test_azure_price_title(self, page: Page, api_server, mock_all_empty):
        """Azure price title should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#azurePriceTitle")).to_contain_text("Live Azure retail catalog lookup")

    def test_azure_price_description(self, page: Page, api_server, mock_all_empty):
        """Azure price description should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#azurePriceTitle + p")).to_contain_text("Read-only query")

    def test_azure_estimate_draft_container(self, page: Page, api_server, mock_all_empty):
        """Azure estimate draft container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        page.wait_for_timeout(500)
        expect(page.locator("#azureEstimateDraft")).to_be_visible()

    def test_azure_estimate_status(self, page: Page, api_server, mock_all_empty):
        """Azure estimate status should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        page.wait_for_timeout(500)
        expect(page.locator("#azureEstimateStatus")).to_be_visible()

    def test_azure_download_button(self, page: Page, api_server, mock_all_empty):
        """Download Azure estimate button should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        page.wait_for_timeout(500)
        expect(page.locator("#downloadAzureEstimate")).to_be_visible()

    def test_azure_download_disabled_initially(self, page: Page, api_server, mock_all_empty):
        """Download button should be disabled initially."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        page.wait_for_timeout(500)
        expect(page.locator("#downloadAzureEstimate")).to_be_disabled()

    def test_google_cloud_panel(self, page: Page, api_server, mock_all_empty):
        """Google Cloud panel should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        page.wait_for_timeout(500)
        expect(page.locator("text=Google Cloud public catalog lookup")).to_be_visible()

    def test_google_cloud_form(self, page: Page, api_server, mock_all_empty):
        """Google Cloud form should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        page.wait_for_timeout(500)
        expect(page.locator('input[name="service_name"]').nth(1)).to_be_visible()

    def test_google_cloud_status(self, page: Page, api_server, mock_all_empty):
        """Google Cloud status should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        page.wait_for_timeout(500)
        expect(page.locator("text=No Google Cloud request made")).to_be_visible()

    def test_google_cloud_results_hidden(self, page: Page, api_server, mock_all_empty):
        """Google Cloud results should be hidden initially."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        page.wait_for_timeout(500)
        # The second tablewrap is for Google Cloud results
        expect(page.locator(".tablewrap").nth(1)).to_be_hidden()
