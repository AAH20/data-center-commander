"""E2E tests for tenant input and tenant-scoped behavior."""
from __future__ import annotations

import re
import urllib.parse

import pytest
from playwright.sync_api import Page, expect

from helpers import base_url

TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestTenantInput:
    """Test tenant input field and tenant-scoped behavior."""

    def test_tenant_input_present(self, page: Page, api_server, mock_all_empty):
        """Tenant input field should be present."""
        page.goto(f"{base_url()}/")
        expect(page.locator("#tenantInput")).to_be_visible()

    def test_tenant_input_has_value(self, page: Page, api_server, mock_all_empty):
        """Tenant input should have value from URL."""
        page.goto(f"{base_url()}/?tenant_id={TENANT_ID}")
        expect(page.locator("#tenantInput")).to_have_value(TENANT_ID)

    def test_tenant_input_empty_by_default(self, page: Page, api_server, mock_all_empty):
        """Tenant input should be empty without URL param."""
        page.goto(f"{base_url()}/")
        expect(page.locator("#tenantInput")).to_have_value("")

    def test_tenant_input_valid_uuid(self, page: Page, api_server, mock_all_empty):
        """Valid UUID should be accepted."""
        page.goto(f"{base_url()}/")
        page.fill("#tenantInput", TENANT_ID)
        page.press("#tenantInput", "Enter")
        page.wait_for_timeout(500)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(page.url).query)
        assert params.get("tenant_id") == [TENANT_ID]

    def test_tenant_input_invalid_uuid(self, page: Page, api_server, mock_all_empty):
        """Invalid UUID should show validation error."""
        page.goto(f"{base_url()}/")
        page.fill("#tenantInput", "not-a-uuid")
        page.press("#tenantInput", "Enter")
        page.wait_for_timeout(300)
        # Should not navigate
        expect(page).not_to_have_url(f"{base_url()}/?tenant_id=not-a-uuid")

    def test_tenant_input_updates_url(self, page: Page, api_server, mock_all_empty):
        """Entering tenant should update URL."""
        page.goto(f"{base_url()}/")
        page.fill("#tenantInput", TENANT_ID)
        page.press("#tenantInput", "Enter")
        page.wait_for_timeout(500)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(page.url).query)
        assert params.get("tenant_id") == [TENANT_ID]

    def test_tenant_input_label(self, page: Page, api_server, mock_all_empty):
        """Tenant input should have label."""
        page.goto(f"{base_url()}/")
        expect(page.locator('label[for="tenantInput"]')).to_be_visible()

    def test_tenant_input_placeholder(self, page: Page, api_server, mock_all_empty):
        """Tenant input should have placeholder."""
        page.goto(f"{base_url()}/")
        expect(page.locator("#tenantInput")).to_have_attribute("placeholder", "tenant UUID")
