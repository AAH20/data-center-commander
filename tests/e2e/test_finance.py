"""E2E tests for the Sizing & Economics / Finance view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import navigate_to

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestFinanceView:
    """Test the Facility sizing, estimating & unit economics view."""

    def test_finance_view_title(self, page: Page, api_server, mock_all_empty):
        """Finance view should have correct title."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#view-finance h2")).to_contain_text("Facility sizing")

    def test_azure_price_form_present(self, page: Page, api_server, mock_all_empty):
        """Azure price form should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#azurePriceForm")).to_be_visible()

    def test_azure_price_form_fields(self, page: Page, api_server, mock_all_empty):
        """Azure price form should have all required fields."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator('input[name="service_name"]')).to_be_visible()
        expect(page.locator('input[name="region"]')).to_be_visible()
        expect(page.locator('input[name="sku"]')).to_be_visible()
        expect(page.locator('input[name="currency"]')).to_be_visible()

    def test_azure_price_status(self, page: Page, api_server, mock_all_empty):
        """Azure price status should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#azurePriceStatus")).to_be_visible()

    def test_azure_price_results_hidden(self, page: Page, api_server, mock_all_empty):
        """Azure price results should be hidden initially."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#azurePriceResults")).to_be_hidden()

    def test_estimate_cards_present(self, page: Page, api_server, mock_all_empty):
        """Estimate cards container should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#estimateCards")).to_be_visible()

    def test_estimate_view_present(self, page: Page, api_server, mock_all_empty):
        """Estimate rollup view should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#estimateView")).to_be_visible()

    def test_price_view_present(self, page: Page, api_server, mock_all_empty):
        """Price book view should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#priceView")).to_be_visible()

    def test_actual_cost_view_present(self, page: Page, api_server, mock_all_empty):
        """Actual cost ledger view should be present."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#actualCostView")).to_be_visible()

    def test_demo_price_book_warning(self, page: Page, api_server, mock_all_empty):
        """Demo price book warning should be displayed."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#view-finance .boundary")).to_contain_text("Demo price book is synthetic")

    def test_azure_price_form_submit(self, page: Page, api_server, mock_all_empty):
        """Submitting Azure price form should show status."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        page.fill('input[name="service_name"]', "Virtual Machines")
        page.fill('input[name="region"]', "eastus")
        page.fill('input[name="sku"]', "Standard_D2s_v5")
        page.fill('input[name="currency"]', "USD")
        page.click('button[type="submit"]')
        page.wait_for_timeout(500)
        expect(page.locator("#azurePriceStatus")).to_be_visible()

    def test_estimate_view_no_data(self, page: Page, api_server, mock_all_empty):
        """Estimate view should show no data message."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#estimateView")).to_contain_text("No priced estimate")

    def test_price_view_no_data(self, page: Page, api_server, mock_all_empty):
        """Price view should show no data message."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#priceView")).to_contain_text("No price observations")

    def test_actual_cost_view_no_data(self, page: Page, api_server, mock_all_empty):
        """Actual cost view should show no data message."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "finance")
        expect(page.locator("#actualCostView")).to_contain_text("No actual cost")

    def test_finance_view_hidden_by_default(self, page: Page, api_server, mock_all_empty):
        """Finance view should be hidden by default."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        expect(page.locator("#view-finance")).not_to_have_class(re.compile(r"\bactive\b"))
