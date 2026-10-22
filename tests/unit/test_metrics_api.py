"""Tests for the metrics middleware (wires dcc.observability into the served app).

The property that matters most here is cardinality: the label must be the matched
route template, never the concrete request path. Labelling on the path makes the
registry grow with the number of distinct identifiers any client sends, which is a
memory leak with extra steps.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import dcc.api_async as api
from dcc.api_async import app


@pytest.fixture()
def client():
    # A fresh engine per test so counts are deterministic.
    api._METRICS.reset()
    return TestClient(app)


def _series(body: str) -> list[str]:
    return [line for line in body.split("\n") if line and not line.startswith("#")]


class TestPrometheusExposition:
    def test_metrics_endpoint_returns_prometheus_text(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "version=0.0.4" in response.headers["content-type"]

    def test_requests_are_counted(self, client):
        client.get("/v2/facilities")
        client.get("/v2/facilities")
        body = client.get("/metrics").text
        assert 'api_requests_total{route="/v2/facilities"} 2' in body

    def test_latency_is_recorded(self, client):
        client.get("/v2/facilities")
        body = client.get("/metrics").text
        # A histogram for the route must exist with a count and a sum.
        assert any("_count" in line and "/v2/facilities" in line for line in _series(body))
        assert any("_sum" in line and "/v2/facilities" in line for line in _series(body))

    def test_metric_families_carry_type_headers(self, client):
        client.get("/v2/facilities")
        body = client.get("/metrics").text
        types = [line for line in body.split("\n") if line.startswith("# TYPE")]
        assert len(types) >= 2, "Prometheus exposition must declare family types"


class TestCardinality:
    def test_labels_use_route_template_not_request_path(self, client):
        """Distinct path parameters must collapse onto ONE series."""
        for ident in ("aaa", "bbb", "ccc", "ddd", "eee"):
            client.get(f"/v2/assets/{ident}")
        body = client.get("/metrics").text
        for ident in ("aaa", "bbb", "ccc", "ddd", "eee"):
            assert ident not in body, f"request path fragment {ident!r} leaked into a label"

    def test_unbounded_identifiers_do_not_create_series(self, client):
        """The registry size must not grow with the number of distinct ids."""
        client.get("/v2/assets/one")
        first = len(_series(client.get("/metrics").text))
        for i in range(30):
            client.get(f"/v2/assets/id-{i}")
        second = len(_series(client.get("/metrics").text))
        assert second == first, (
            f"series count grew from {first} to {second} as identifiers varied; "
            "the label is not the route template"
        )

    def test_unmatched_paths_collapse_to_a_single_label(self, client):
        for suffix in ("nope1", "nope2", "nope3"):
            client.get(f"/does-not-exist/{suffix}")
        body = client.get("/metrics").text
        assert 'api_requests_total{route="unmatched"} 3' in body


class TestErrorClassification:
    def test_validation_error_is_classified_not_internal(self, client):
        client.get("/v2/assets")  # missing required query parameters -> 422/400
        body = client.get("/metrics").text
        assert 'type="validation"' in body
        assert 'type="internal"' not in body

    def test_not_found_is_not_counted_as_a_server_error(self, client):
        client.get("/v2/does-not-exist")
        body = client.get("/metrics").text
        assert 'type="internal"' not in body


class TestSelfExclusion:
    def test_scraping_does_not_count_itself(self, client):
        client.get("/metrics")
        body = client.get("/metrics").text
        assert 'route="/metrics"' not in body

    def test_health_checks_do_not_pollute_the_registry(self, client):
        client.get("/healthz")
        client.get("/readyz")
        body = client.get("/metrics").text
        assert 'route="/healthz"' not in body
        assert 'route="/readyz"' not in body
