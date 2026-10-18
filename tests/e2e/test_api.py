"""E2E tests for API health and readiness endpoints."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8790"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"


class TestApiHealth:
    """Test API health and readiness endpoints."""

    def test_healthz_endpoint(self, page: Page, api_server):
        """Healthz endpoint should return 200."""
        response = page.request.get(f"{BASE_URL}/healthz")
        assert response.status == 200
        body = response.json()
        assert body["service"] == "data-center-commander"
        assert body["mode"] == "read_only"

    def test_readyz_endpoint(self, page: Page, api_server):
        """Readyz endpoint should return 200 or 503."""
        response = page.request.get(f"{BASE_URL}/readyz")
        assert response.status in (200, 503)

    def test_api_status_updates(self, page: Page, api_server, mock_all_empty):
        """API status should update after page load."""
        page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
        page.wait_for_timeout(500)
        expect(page.locator("#apiStatus")).to_contain_text("API ready")

    def test_404_unknown_route(self, page: Page, api_server):
        """Unknown API route should return 404."""
        response = page.request.get(f"{BASE_URL}/v1/nonexistent?tenant_id={TENANT_ID}")
        assert response.status == 404

    def test_invalid_tenant_id(self, page: Page, api_server):
        """Invalid tenant_id should return 400."""
        response = page.request.get(f"{BASE_URL}/v1/overview?tenant_id=invalid")
        assert response.status == 400

    def test_missing_tenant_id(self, page: Page, api_server):
        """Missing tenant_id should return 400."""
        response = page.request.get(f"{BASE_URL}/v1/overview")
        assert response.status == 400

    def test_assets_endpoint(self, page: Page, api_server, mock_all_empty):
        """Assets endpoint should return 200."""
        response = page.request.get(f"{BASE_URL}/v1/assets?tenant_id={TENANT_ID}")
        assert response.status == 200

    def test_facilities_endpoint(self, page: Page, api_server, mock_all_empty):
        """Facilities endpoint should return 200."""
        response = page.request.get(f"{BASE_URL}/v1/facilities?tenant_id={TENANT_ID}")
        assert response.status == 200

    def test_workflows_endpoint(self, page: Page, api_server, mock_all_empty):
        """Workflows endpoint should return 200."""
        response = page.request.get(f"{BASE_URL}/v1/workflows?tenant_id={TENANT_ID}")
        assert response.status == 200

    def test_connectors_endpoint(self, page: Page, api_server, mock_all_empty):
        """Connectors endpoint should return 200."""
        response = page.request.get(f"{BASE_URL}/v1/connectors?tenant_id={TENANT_ID}")
        assert response.status == 200

    def test_capacity_endpoint(self, page: Page, api_server, mock_all_empty):
        """Capacity endpoint should return 200."""
        response = page.request.get(f"{BASE_URL}/v1/capacity?tenant_id={TENANT_ID}")
        assert response.status == 200

    def test_evidence_endpoint(self, page: Page, api_server, mock_all_empty):
        """Evidence endpoint should return 200."""
        response = page.request.get(f"{BASE_URL}/v1/evidence?tenant_id={TENANT_ID}")
        assert response.status == 200

    def test_analytics_endpoint(self, page: Page, api_server, mock_all_empty):
        """Analytics endpoint should return 200."""
        response = page.request.get(f"{BASE_URL}/v1/analytics?tenant_id={TENANT_ID}")
        assert response.status == 200

    def test_costs_endpoint(self, page: Page, api_server, mock_all_empty):
        """Costs endpoint should return 200."""
        response = page.request.get(f"{BASE_URL}/v1/costs?tenant_id={TENANT_ID}")
        assert response.status == 200

    def test_topology_endpoint(self, page: Page, api_server, mock_all_empty):
        """Topology endpoint should return 200."""
        response = page.request.get(f"{BASE_URL}/v1/topology?tenant_id={TENANT_ID}")
        assert response.status == 200

    def test_placement_scenarios_endpoint(self, page: Page, api_server, mock_all_empty):
        """Placement scenarios endpoint should return 200."""
        response = page.request.get(f"{BASE_URL}/v1/placement/scenarios?tenant_id={TENANT_ID}")
        assert response.status == 200

    def test_analytics_window_days_validation(self, page: Page, api_server):
        """Analytics endpoint should validate window_days."""
        response = page.request.get(f"{BASE_URL}/v1/analytics?tenant_id={TENANT_ID}&window_days=0")
        assert response.status == 400

    def test_analytics_window_days_max(self, page: Page, api_server):
        """Analytics endpoint should reject window_days > 90."""
        response = page.request.get(f"{BASE_URL}/v1/analytics?tenant_id={TENANT_ID}&window_days=91")
        assert response.status == 400
