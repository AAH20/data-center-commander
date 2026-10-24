"""Overview must state where its numbers came from.

The console branches on `synthetic` sixteen times and on `synthetic_demo_mode` and
`source_status` once each. Overview returned none of the three, so every branch
evaluated false: a tenant whose rows are synthetic rendered exactly like a live one,
and an unconnected tenant rendered like a tenant with no activity.

The definitions mirror /v2/costs deliberately. Two endpoints disagreeing about what
"synthetic" means is worse than either being wrong, because a caller cannot tell which
one to believe.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from dcc.api_async import app

DEMO_TENANT = "dcc00000-0000-4000-8000-000000000001"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _overview(**params) -> dict:
    response = TestClient(app).get("/v2/overview", params=params)
    assert response.status_code == 200, response.text[:200]
    return response.json()


def test_provenance_fields_present(client: TestClient) -> None:
    body = _overview(tenant_id=DEMO_TENANT)

    for field in ("source_status", "synthetic", "synthetic_demo_mode"):
        assert field in body, f"overview does not report {field}; the console branches on it"


def test_source_status_is_a_known_value(client: TestClient) -> None:
    """Not just present -- constrained, so the console's comparison can match."""
    body = _overview(tenant_id=DEMO_TENANT)

    assert body["source_status"] in {"live", "no_telemetry"}


def test_tenant_with_no_telemetry_reports_no_telemetry(client: TestClient) -> None:
    """A tenant nobody has connected must be distinguishable from an idle one."""
    body = _overview(tenant_id=str(uuid.uuid4()))

    assert body["source_status"] == "no_telemetry", (
        f"an empty tenant reported {body['source_status']!r}; it has no telemetry source"
    )
    assert body["kpis"] == []


def test_demo_mode_is_opt_in_not_automatic(client: TestClient) -> None:
    """Synthetic rows exist, but showing them is the caller's explicit choice."""
    default = _overview(tenant_id=DEMO_TENANT)
    opted_in = _overview(tenant_id=DEMO_TENANT, demo="synthetic")

    assert opted_in["synthetic_demo_mode"] is True
    assert default["synthetic_demo_mode"] is False, (
        "synthetic data rendered by default; the console would present fixtures as live"
    )
    # The fact about the stored rows does not change with the caller's preference.
    assert default["synthetic"] == opted_in["synthetic"]


def test_synthetic_agrees_with_costs(client: TestClient) -> None:
    """Two endpoints must not disagree about whether a tenant's data is synthetic."""
    overview = _overview(tenant_id=DEMO_TENANT, demo="synthetic")
    costs = client.get("/v2/costs", params={"tenant_id": DEMO_TENANT, "demo": "synthetic"}).json()

    assert overview["synthetic"] == costs["synthetic"], (
        f"overview says synthetic={overview['synthetic']}, costs says {costs['synthetic']}"
    )
    assert overview["synthetic_demo_mode"] == costs["synthetic_demo_mode"]
