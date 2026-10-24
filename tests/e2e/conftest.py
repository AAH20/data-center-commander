"""Shared fixtures for Data Center Commander E2E tests."""
from __future__ import annotations

import pytest

# Playwright is an OPTIONAL dependency: it is not declared in pyproject.toml, and
# the browser suite cannot run without it. Without this guard the whole `tests/e2e`
# directory raises ModuleNotFoundError at COLLECTION time, which aborts the entire
# run (not just these tests) -- one missing optional dep took down 6,025 tests.
# importorskip marks these as SKIPPED with a reason rather than silently passing.
pytest.importorskip(
    "playwright.sync_api",
    reason="optional dependency 'playwright' not installed; E2E browser suite skipped",
)

# The Python package and the browser binary are installed separately. With the
# package present but no downloaded browser, every test below fails in fixture
# setup with "Executable doesn't exist ... run playwright install" -- 291 errors
# that look like a regression and are not one. Skip with the install command
# named instead.
def _browser_binaries_present() -> bool:
    import glob
    import os
    import sys

    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        root = os.environ["PLAYWRIGHT_BROWSERS_PATH"]
    elif sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Caches/ms-playwright")
    else:
        root = os.path.expanduser("~/.cache/ms-playwright")
    if not os.path.isdir(root):
        return False
    return bool(glob.glob(os.path.join(root, "chromium*")))


if not _browser_binaries_present():
    pytest.skip(
        reason=(
            "playwright browser binaries not downloaded; run "
            "`python -m playwright install chromium-headless-shell` "
            "(E2E browser suite skipped)"
        ),
        allow_module_level=True,
    )

import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
API_PORT = 8790
BASE_URL = f"http://127.0.0.1:{API_PORT}"
TENANT_ID = "dcc00000-0000-4000-8000-000000000001"





def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


@pytest.fixture(scope="session")
def api_server() -> Generator[subprocess.Popen, None, None]:
    """Start the DCC API server for the test session."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    # DCC_DATABASE_URL is deliberately NOT stripped: the v2 app answers read
    # endpoints with 503 `database_not_configured` without a DSN, so tests that
    # need real read responses must be able to point the server at a database
    # (see the `database_url` fixture).
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "run-local.py")],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if _port_open("127.0.0.1", API_PORT):
            break
        time.sleep(0.1)
    else:
        proc.kill()
        # Server may fail to start without database; tests using mock_api don't need it
        import warnings
        warnings.warn("API server did not start; tests requiring real API will fail")
    yield proc
    proc.kill()
    proc.wait(timeout=5)


@pytest.fixture(scope="session")
def database_url() -> str:
    """PostgreSQL DSN that the API server was started with.

    The v2 application returns 503 ``database_not_configured`` for read
    endpoints when ``DCC_DATABASE_URL`` is unset, so a test asserting a real
    read response genuinely needs a database behind the server.
    """
    url = os.environ.get("DCC_DATABASE_URL")
    if not url:
        pytest.skip(
            reason=(
                "DCC_DATABASE_URL not set; /v2 read endpoints answer 503 "
                "database_not_configured without a live PostgreSQL database"
            )
        )
    return url


@pytest.fixture(scope="session")
def playwright_instance() -> Generator[Playwright, None, None]:
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright) -> Generator[Browser, None, None]:
    browser = playwright_instance.chromium.launch(headless=True)
    yield browser
    browser.close()


@pytest.fixture()
def context(browser: Browser) -> Generator[BrowserContext, None, None]:
    context = browser.new_context()
    yield context
    context.close()


@pytest.fixture()
def page(context: BrowserContext) -> Generator[Page, None, None]:
    page = context.new_page()
    # Pre-set onboarding profile so dialog doesn't auto-show
    page.add_init_script("""
        try { localStorage.setItem('dcc-workspace-profile-v1', JSON.stringify({profile:'enterprise',objective:'cost',saved_at:new Date().toISOString()})); } catch(e) {}
        // Prevent dialog from opening
        const _origShowModal = HTMLDialogElement.prototype.showModal;
        HTMLDialogElement.prototype.showModal = function() {
            if (this.classList.contains('dcc-dialog')) return;
            return _origShowModal.call(this);
        };
    """)
    yield page
    page.close()


@pytest.fixture()
def page_with_tenant(context: BrowserContext) -> Generator[Page, None, None]:
    """Page with tenant_id pre-set in URL."""
    page = context.new_page()
    page.goto(f"{BASE_URL}/?tenant_id={TENANT_ID}")
    yield page
    page.close()


@pytest.fixture()
def mock_api(page: Page) -> dict:
    """Install route handlers that return empty/successful API responses.

    The product serves ``/v2`` (``dcc.api_async``); ``/v1`` is the legacy
    handler. Different views in ``ui/`` still call one or the other, so both
    prefixes are intercepted and a fixture key such as ``v1/overview`` answers
    for ``/v1/overview`` and ``/v2/overview`` alike.
    """
    routes = {}

    def _resolve(key: str):
        for candidate in (key, key.replace("v2/", "v1/", 1), key.split("/", 1)[-1]):
            if candidate in routes:
                return routes[candidate]
        return None

    def handler(route):
        path = route.request.url.split("?")[0].replace(BASE_URL, "")
        key = path.lstrip("/")
        payload = _resolve(key)
        if payload is not None:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))
        else:
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"error": "not_found"}))

    page.route("**/v1/**", handler)
    page.route("**/v2/**", handler)
    page.route("**/healthz", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"service": "data-center-commander", "mode": "read_only"})))
    return routes


@pytest.fixture()
def mock_overview_empty(mock_api: dict) -> dict:
    """Mock overview endpoint with empty data."""
    mock_api["v1/overview"] = {
        "tenant_id": TENANT_ID,
        "facility_count": 0,
        "kpis": [],
        "open_workflows": 0,
        "latest_telemetry_ingested_at": None,
        "source_status": "no_telemetry",
        "synthetic": False,
        "synthetic_demo_mode": False,
        "read_only": True,
        "execution_permitted": False,
    }
    return mock_api


@pytest.fixture()
def mock_overview_synthetic(mock_api: dict) -> dict:
    """Overview payload for synthetic demo mode.

    The UI only raises its SYNTHETIC DEMO ribbon/badge and quarantines KPIs when
    the overview response itself reports ``synthetic: true``; an empty payload
    leaves the page looking like a normal connected (but data-less) workspace.
    """
    mock_api["v1/overview"] = {
        "tenant_id": TENANT_ID,
        "facility_count": 2,
        "kpis": [],
        "open_workflows": 0,
        "latest_telemetry_ingested_at": "2024-01-02T00:00:00Z",
        "source_status": "synthetic_demo",
        "synthetic": True,
        "synthetic_demo_mode": True,
        "read_only": True,
        "execution_permitted": False,
    }
    return mock_api


@pytest.fixture()
def mock_overview_with_data(mock_api: dict) -> dict:
    """Mock overview endpoint with sample data."""
    mock_api["v1/overview"] = {
        "tenant_id": TENANT_ID,
        "facility_count": 2,
        "kpis": [
            {"metric_key": "facility_energy_kwh", "name": "Facility energy", "unit": "kWh", "value_numeric": 12500.5, "window_start": "2024-01-01T00:00:00Z", "window_end": "2024-01-02T00:00:00Z", "observed_at": "2024-01-02T00:00:00Z", "coverage": 0.95, "uncertainty": 0.02, "quality_status": "good", "reason_codes": [], "provenance": {"synthetic": False}},
            {"metric_key": "it_energy_kwh", "name": "IT energy", "unit": "kWh", "value_numeric": 8200.3, "window_start": "2024-01-01T00:00:00Z", "window_end": "2024-01-02T00:00:00Z", "observed_at": "2024-01-02T00:00:00Z", "coverage": 0.92, "uncertainty": 0.03, "quality_status": "good", "reason_codes": [], "provenance": {"synthetic": False}},
            {"metric_key": "pue", "name": "PUE", "unit": "", "value_numeric": 1.45, "window_start": "2024-01-01T00:00:00Z", "window_end": "2024-01-02T00:00:00Z", "observed_at": "2024-01-02T00:00:00Z", "coverage": 0.88, "uncertainty": 0.05, "quality_status": "estimated", "reason_codes": [], "provenance": {"synthetic": False}},
        ],
        "open_workflows": 5,
        "latest_telemetry_ingested_at": "2024-01-02T00:00:00Z",
        "source_status": "observed",
        "synthetic": False,
        "synthetic_demo_mode": False,
        "read_only": True,
        "execution_permitted": False,
    }
    return mock_api


@pytest.fixture()
def mock_facilities(mock_api: dict) -> dict:
    mock_api["v1/facilities"] = {
        "tenant_id": TENANT_ID,
        "items": [
            {"id": str(uuid.uuid4()), "code": "DC1", "name": "Datacenter 1", "facility_type": "datacenter", "status": "active", "site_code": "SITE1", "site_name": "Site 1"},
            {"id": str(uuid.uuid4()), "code": "DC2", "name": "Datacenter 2", "facility_type": "datacenter", "status": "active", "site_code": "SITE2", "site_name": "Site 2"},
        ],
        "total": 2, "limit": 50, "offset": 0, "has_more": False,
        "next_cursor": None, "read_only": True, "execution_permitted": False,
    }
    return mock_api


@pytest.fixture()
def mock_assets(mock_api: dict) -> dict:
    mock_api["v1/assets"] = {
        "tenant_id": TENANT_ID,
        "items": [
            {"external_id": "srv-001", "asset_type": "server", "name": "Server 001", "manufacturer": "Dell", "model": "R750", "lifecycle_state": "active", "criticality": "high", "observed_at": "2024-01-01T00:00:00Z", "facility_name": "Datacenter 1", "space_name": "Row A"},
            {"external_id": "ups-001", "asset_type": "ups", "name": "UPS 001", "manufacturer": "APC", "model": "Symmetra", "lifecycle_state": "active", "criticality": "critical", "observed_at": "2024-01-01T00:00:00Z", "facility_name": "Datacenter 1", "space_name": "Electrical Room"},
        ],
        "total": 2, "limit": 50, "offset": 0, "has_more": False,
        "next_cursor": None, "read_only": True, "execution_permitted": False,
    }
    return mock_api


@pytest.fixture()
def mock_workflows(mock_api: dict) -> dict:
    mock_api["v1/workflows"] = {
        "tenant_id": TENANT_ID,
        "items": [
            {"id": str(uuid.uuid4()), "workflow_type": "maintenance", "stage": "operations", "status": "open", "priority": "high", "title": "Replace UPS battery", "accountable_owner": "John Doe", "opened_at": "2024-01-01T00:00:00Z", "due_at": "2024-01-15T00:00:00Z", "closed_at": None},
            {"id": str(uuid.uuid4()), "workflow_type": "demand", "stage": "design", "status": "in_progress", "priority": "normal", "title": "New rack deployment", "accountable_owner": "Jane Smith", "opened_at": "2024-01-05T00:00:00Z", "due_at": "2024-02-01T00:00:00Z", "closed_at": None},
        ],
        "total": 2, "limit": 50, "offset": 0, "has_more": False,
        "next_cursor": None, "read_only": True, "execution_permitted": False,
    }
    return mock_api


@pytest.fixture()
def mock_connectors(mock_api: dict) -> dict:
    mock_api["v1/connectors"] = {
        "tenant_id": TENANT_ID,
        "items": [
            {"id": str(uuid.uuid4()), "name": "BMS Adapter", "vendor": "Schneider", "product": "EcoStruxure", "adapter_id": "bms", "adapter_version": "1.0", "status": "active", "access_mode": "read_only", "scopes": ["read"], "last_success_at": "2024-01-02T00:00:00Z"},
        ],
        "total": 2, "limit": 50, "offset": 0, "has_more": False,
        "next_cursor": None, "read_only": True, "execution_permitted": False,
    }
    return mock_api


@pytest.fixture()
def mock_capacity(mock_api: dict) -> dict:
    mock_api["v1/capacity"] = {
        "tenant_id": TENANT_ID,
        "items": [
            {"facility_id": str(uuid.uuid4()), "dimension": "power_kw", "scenario": "normal", "usable": 500, "reserved": 50, "policy_reserve": 100, "forecast_peak": 450, "unit": "kW", "quality_status": "good", "observed_at": "2024-01-02T00:00:00Z"},
        ],
        "total": 2, "limit": 50, "offset": 0, "has_more": False,
        "next_cursor": None, "read_only": True, "execution_permitted": False,
    }
    return mock_api


@pytest.fixture()
def mock_evidence(mock_api: dict) -> dict:
    mock_api["v1/evidence"] = {
        "tenant_id": TENANT_ID,
        "items": [
            {"sequence": 1, "event_type": "asset.created", "occurred_at": "2024-01-01T00:00:00Z", "actor_ref": "system", "subject_type": "asset", "subject_id": str(uuid.uuid4()), "event_hash": "abc123"},
        ],
        "total": 2, "limit": 50, "offset": 0, "has_more": False,
        "next_cursor": None, "read_only": True, "execution_permitted": False,
    }
    return mock_api


@pytest.fixture()
def mock_analytics(mock_api: dict) -> dict:
    mock_api["v1/analytics"] = {
        "tenant_id": TENANT_ID,
        "window_days": 30,
        "kpi_series": [],
        "kpi_quality": [],
        "telemetry_quality": [],
        "workflow_health": [],
        "model_policy": {"trend_forecast_min_daily_points": 7, "anomaly_min_daily_points": 14, "maintenance_failure_labels_required": True, "note": "Forecasts and anomalies require adequate non-synthetic history; no failure-probability model is enabled by this read model."},
        "read_only": True,
        "execution_permitted": False,
    }
    return mock_api


@pytest.fixture()
def mock_costs(mock_api: dict) -> dict:
    mock_api["v1/costs"] = {
        "tenant_id": TENANT_ID,
        "estimates": [],
        "prices": [],
        "actuals": [],
        "read_only": True,
        "synthetic": False,
        "synthetic_demo_mode": False,
        "execution_permitted": False,
    }
    return mock_api


@pytest.fixture()
def mock_topology(mock_api: dict) -> dict:
    mock_api["v1/topology"] = {
        "tenant_id": TENANT_ID,
        "nodes": [
            {"id": str(uuid.uuid4()), "kind": "asset", "label": "Server 001", "type": "server", "state": "active", "criticality": "high", "external_id": "srv-001", "facility": "Datacenter 1"},
            {"id": str(uuid.uuid4()), "kind": "asset", "label": "UPS 001", "type": "ups", "state": "active", "criticality": "critical", "external_id": "ups-001", "facility": "Datacenter 1"},
        ],
        "edges": [
            {"source": "0", "target": "1", "relation": "feeds", "confidence": 0.95, "valid_from": "2024-01-01T00:00:00Z", "provenance": {}},
        ],
        "read_only": True,
        "source": "postgresql_asset_relationships",
        "execution_permitted": False,
    }
    return mock_api


@pytest.fixture()
def mock_placement_scenarios(mock_api: dict) -> dict:
    mock_api["v1/placement/scenarios"] = {
        "tenant_id": TENANT_ID,
        "scenarios": [],
        "status": "draft_snapshots",
        "execution_permitted": False,
    }
    return mock_api


@pytest.fixture()
def mock_all_empty(mock_api: dict) -> dict:
    """Mock all API endpoints with empty data."""
    mock_api["v1/overview"] = {"tenant_id": TENANT_ID, "facility_count": 0, "kpis": [], "open_workflows": 0, "latest_telemetry_ingested_at": None, "source_status": "no_telemetry", "synthetic": False, "synthetic_demo_mode": False, "read_only": True, "execution_permitted": False}
    mock_api["v1/facilities"] = {"items": [], "total": 0, "limit": 50, "offset": 0, "has_more": False, "next_cursor": None, "read_only": True, "execution_permitted": False}
    mock_api["v1/assets"] = {"items": [], "total": 0, "limit": 50, "offset": 0, "has_more": False, "next_cursor": None, "read_only": True, "execution_permitted": False}
    mock_api["v1/workflows"] = {"items": [], "total": 0, "limit": 50, "offset": 0, "has_more": False, "next_cursor": None, "read_only": True, "execution_permitted": False}
    mock_api["v1/connectors"] = {"items": [], "total": 0, "limit": 50, "offset": 0, "has_more": False, "next_cursor": None, "read_only": True, "execution_permitted": False}
    mock_api["v1/capacity"] = {"items": [], "total": 0, "limit": 50, "offset": 0, "has_more": False, "next_cursor": None, "read_only": True, "execution_permitted": False}
    mock_api["v1/evidence"] = {"items": [], "total": 0, "limit": 50, "offset": 0, "has_more": False, "next_cursor": None, "read_only": True, "execution_permitted": False}
    mock_api["v1/analytics"] = {"tenant_id": TENANT_ID, "window_days": 30, "kpi_series": [], "kpi_quality": [], "telemetry_quality": [], "workflow_health": [], "model_policy": {"trend_forecast_min_daily_points": 7, "anomaly_min_daily_points": 14, "maintenance_failure_labels_required": True, "note": "test"}, "read_only": True, "execution_permitted": False}
    mock_api["v1/costs"] = {"tenant_id": TENANT_ID, "estimates": [], "prices": [], "actuals": [], "read_only": True, "synthetic": False, "synthetic_demo_mode": False, "execution_permitted": False}
    mock_api["v1/topology"] = {"tenant_id": TENANT_ID, "nodes": [], "edges": [], "read_only": True, "source": "postgresql_asset_relationships", "execution_permitted": False}
    mock_api["v1/placement/scenarios"] = {"tenant_id": TENANT_ID, "scenarios": [], "status": "draft_snapshots", "execution_permitted": False}
    return mock_api
