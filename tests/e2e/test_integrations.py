"""E2E tests for the Integrations & Source Health view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import navigate_to

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestIntegrationsView:
    """Test the Integrations & source health view."""

    def test_integrations_view_title(self, page: Page, api_server, mock_all_empty):
        """Integrations view should have correct title."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "integrations")
        expect(page.locator("#view-integrations h2")).to_contain_text("Integrations")

    def test_integrations_view_description(self, page: Page, api_server, mock_all_empty):
        """Integrations view should have description."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "integrations")
        expect(page.locator("#view-integrations p").first).to_contain_text("Registered source status")

    def test_connector_view_empty(self, page: Page, api_server, mock_all_empty):
        """Connector view should show empty state."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "integrations")
        expect(page.locator("#connectorView")).to_contain_text("No connector registrations")

    def test_integrations_view_hidden_by_default(self, page: Page, api_server, mock_all_empty):
        """Integrations view should be hidden by default."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        expect(page.locator("#view-integrations")).not_to_have_class(re.compile(r"\bactive\b"))

    def test_integrations_nav_active(self, page: Page, api_server, mock_all_empty):
        """Integrations nav should be active when on integrations view."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "integrations")
        expect(page.locator('.nav [data-view="integrations"]')).to_have_class(re.compile(r"\bactive\b"))
