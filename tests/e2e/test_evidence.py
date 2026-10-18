"""E2E tests for the Evidence & Audit view."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from helpers import navigate_to

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestEvidenceView:
    """Test the Evidence & audit view."""

    def test_evidence_view_title(self, page: Page, api_server, mock_all_empty):
        """Evidence view should have correct title."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "evidence")
        expect(page.locator("#view-evidence h2")).to_contain_text("Evidence")

    def test_evidence_view_description(self, page: Page, api_server, mock_all_empty):
        """Evidence view should have description."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "evidence")
        expect(page.locator("#view-evidence p").first).to_contain_text("Append-only")

    def test_evidence_view_empty(self, page: Page, api_server, mock_all_empty):
        """Evidence view should show empty state."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "evidence")
        expect(page.locator("#evidenceView")).to_contain_text("No evidence event references")

    def test_evidence_view_hidden_by_default(self, page: Page, api_server, mock_all_empty):
        """Evidence view should be hidden by default."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        expect(page.locator("#view-evidence")).not_to_have_class(re.compile(r"\bactive\b"))

    def test_evidence_nav_active(self, page: Page, api_server, mock_all_empty):
        """Evidence nav should be active when on evidence view."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        navigate_to(page, "evidence")
        expect(page.locator('.nav [data-view="evidence"]')).to_have_class(re.compile(r"\bactive\b"))
