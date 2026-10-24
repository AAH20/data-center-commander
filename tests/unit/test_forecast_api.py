"""Tests for the forecasting endpoints.

These assert behaviour, not status codes: that the forecast actually projects, that
the at-risk window is the window where capacity crosses the reserve, and that the
drift endpoint reports which detectors fired. Negative controls assert the rejection
reason, because a 400 for the wrong reason is as wrong as a 500.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from dcc.api_async import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _series(days: int = 30, start=1000.0, step=-25.0):
    """Usable capacity shrinking by `step` per day, starting at `start`."""
    return [
        {
            "observed_at": f"2026-09-{d + 1:02d}T00:00:00Z",
            "usable": start + d * step,
            "reserved": 100.0,
            "policy_reserve": 150.0,
            "quality_status": "ok",
            "scenario": "base",
        }
        for d in range(days)
    ]


class TestCapacityForecast:
    def test_projects_the_requested_horizon(self, client):
        response = client.post(
            "/v2/forecast/capacity",
            json={
                "facility_id": "dc-1",
                "dimension": "power_kw",
                "unit": "kW",
                "data_points": _series(30),
                "horizon_days": 60,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()

        forecast = body["forecast"]
        assert forecast["method"] == "linear"
        assert forecast["data_points_used"] == 30
        # A 60-day horizon must produce a 60-point projection, not 30.
        assert len(forecast["forecast_points"]) == 60
        assert forecast["forecast_horizon_days"] == 60

    def test_projection_continues_the_downward_trend(self, client):
        """The forecast must extend the trend, not restart it."""
        response = client.post(
            "/v2/forecast/capacity",
            json={
                "facility_id": "dc-1",
                "dimension": "power_kw",
                "unit": "kW",
                "data_points": _series(30, start=1000.0, step=-25.0),
                "horizon_days": 10,
            },
        )
        points = response.json()["forecast"]["forecast_points"]
        values = [p["predicted_value"] for p in points]
        # History ends at 1000 - 29*25 = 275 kW and is falling, so the projection
        # must start below that and keep falling.
        assert values[0] < 275.0
        assert values == sorted(values, reverse=True)

    def test_at_risk_reports_the_breach_window(self, client):
        response = client.post(
            "/v2/forecast/capacity",
            json={
                "facility_id": "dc-1",
                "dimension": "power_kw",
                "unit": "kW",
                "data_points": _series(30),
                "horizon_days": 60,
            },
        )
        at_risk = response.json()["at_risk"]
        assert at_risk["dimension"] == "power_kw"
        assert at_risk["facility_id"] == "dc-1"
        # Capacity falls to zero, so a zero threshold must be crossed.
        assert at_risk["at_risk_dates"]

    def test_rejects_unknown_dimension(self, client):
        response = client.post(
            "/v2/forecast/capacity",
            json={
                "facility_id": "dc-1",
                "dimension": "power",  # not power_kw
                "unit": "kW",
                "data_points": _series(5),
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_dimension"

    def test_rejects_naive_timestamp(self, client):
        """A timestamp without an offset means 'local time', which silently shifts
        the whole forecast by the operator's offset."""
        series = _series(3)
        series[0]["observed_at"] = "2026-09-01T00:00:00"
        response = client.post(
            "/v2/forecast/capacity",
            json={"facility_id": "dc-1", "dimension": "power_kw", "unit": "kW", "data_points": series},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "naive_timestamp"

    def test_rejects_unknown_field_and_names_it(self, client):
        response = client.post(
            "/v2/forecast/capacity",
            json={
                "facility_id": "dc-1",
                "dimension": "power_kw",
                "unit": "kW",
                "data_points": _series(3),
                "horizon_dayz": 30,
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["error"] == "unknown_field"
        assert detail["fields"] == ["horizon_dayz"]

    def test_rejects_boolean_as_a_number(self, client):
        series = _series(3)
        series[1]["usable"] = True
        response = client.post(
            "/v2/forecast/capacity",
            json={"facility_id": "dc-1", "dimension": "power_kw", "unit": "kW", "data_points": series},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_type"

    def test_rejects_empty_series(self, client):
        response = client.post(
            "/v2/forecast/capacity",
            json={"facility_id": "dc-1", "dimension": "power_kw", "unit": "kW", "data_points": []},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "empty_series"

    def test_rejects_horizon_out_of_range(self, client):
        response = client.post(
            "/v2/forecast/capacity",
            json={
                "facility_id": "dc-1",
                "dimension": "power_kw",
                "unit": "kW",
                "data_points": _series(3),
                "horizon_days": 0,
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "out_of_range"


class TestDrift:
    @staticmethod
    def _gauss(mean: float, n: int = 200, seed: int = 0):
        import random

        rng = random.Random(seed)
        return [rng.gauss(mean, 5.0) for _ in range(n)]

    def test_detects_a_shifted_distribution(self, client):
        response = client.post(
            "/v2/forecast/drift",
            json={"reference": self._gauss(100), "incoming": self._gauss(130)},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["drift_detected"] is True
        assert body["detectors_fired"], "a 6-sigma mean shift must trip at least one detector"
        assert len(body["results"]) >= 1

    def test_identical_series_do_not_drift(self, client):
        """Negative control: the detector must not fire on unchanged data."""
        series = self._gauss(100)
        response = client.post(
            "/v2/forecast/drift",
            json={"reference": series, "incoming": series},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["drift_detected"] is False, body["detectors_fired"]

    def test_rejects_unknown_field(self, client):
        response = client.post(
            "/v2/forecast/drift",
            json={"reference": [1.0, 2.0], "incoming": [1.0, 2.0], "bogus": 1},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "unknown_field"

    def test_rejects_non_numeric_series(self, client):
        response = client.post(
            "/v2/forecast/drift",
            json={"reference": [1.0, "two"], "incoming": [1.0, 2.0]},
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["error"] == "invalid_type"
        assert detail["field"] == "reference[1]"


class TestFailurePrediction:
    ASSETS = [
        {"id": "ups-1", "name": "UPS-1", "asset_type": "ups", "criticality": "high"},
        {"id": "crah-2", "name": "CRAH-2", "asset_type": "crah"},
    ]

    def test_returns_one_profile_per_asset(self, client):
        response = client.post(
            "/v2/forecast/failure",
            json={"tenant_id": "t1", "assets": self.ASSETS},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total_assets"] == 2
        assert len(body["risk_profiles"]) == 2

    def test_identifiers_survive_the_round_trip(self, client):
        """The library reads asset["id"] but reports asset_id. A caller passing the
        reported name must not get an empty identifier."""
        body = client.post(
            "/v2/forecast/failure",
            json={"tenant_id": "t1", "assets": self.ASSETS},
        ).json()
        assert [p["asset_id"] for p in body["risk_profiles"]] == ["ups-1", "crah-2"]
        assert [p["asset_name"] for p in body["risk_profiles"]] == ["UPS-1", "CRAH-2"]

    def test_rejects_asset_id_instead_of_id(self, client):
        """asset_id is what the RESPONSE calls it, so it is the natural thing to send.
        It must be rejected with the accepted keys named, not silently blank."""
        response = client.post(
            "/v2/forecast/failure",
            json={"tenant_id": "t1", "assets": [{"asset_id": "ups-1", "asset_type": "ups"}]},
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["error"] == "missing_field"
        assert detail["missing"] == ["id"]

    def test_rejects_missing_assets(self, client):
        response = client.post("/v2/forecast/failure", json={"tenant_id": "t1"})
        assert response.status_code == 400
        assert response.json()["detail"]["field"] == "assets"


class TestRoutesAreReachable:
    def test_all_three_are_registered(self):
        # Include routers are NOT flattened into app.routes: FastAPI wraps them in an
        # _IncludedRouter that has no .path, so a naive {route.path for route in
        # app.routes} raises on the wrapper and would silently miss included routes.
        # Use the app's own enumeration, which descends into sub-routers.
        from dcc.api_async import _iter_routes

        paths = {getattr(route, "path", None) for route in _iter_routes(app.routes)}
        for path in ("/v2/forecast/capacity", "/v2/forecast/failure", "/v2/forecast/drift"):
            assert path in paths, f"{path} is not registered on the served app"
