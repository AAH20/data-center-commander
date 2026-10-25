"""The /metrics exposition must be something Prometheus can actually ingest.

One illegal metric name does not degrade a scrape -- Prometheus rejects the response
whole. So a name like `/v2/overview_bucket` does not lose the latency panel; it loses
every series the process publishes, and every alert built on one becomes silent while
still looking configured.

That was live. metrics_middleware called record_latency(label, elapsed_ms), passing the
route template as the metric NAME and milliseconds into a _seconds histogram. The
docstring above the call described the correct behaviour -- route as a label, bounded
cardinality -- but the argument positions contradicted it.

These tests read the real exposition rather than the intended one.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

# Prometheus metric names: [a-zA-Z_:][a-zA-Z0-9_:]*
LEGAL_NAME = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")
TENANT = "dcc00000-0000-4000-8000-000000000001"


@pytest.fixture(scope="module")
def exposition() -> str:
    from dcc.api_async import app

    client = TestClient(app)
    # Drive one matched route and one unmatched, so both label values exist.
    client.get("/v2/overview", params={"tenant_id": TENANT})
    client.get("/definitely-not-a-route")
    response = client.get("/metrics")
    assert response.status_code == 200
    return response.text


def _sample_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line and not line.startswith("#")]


def test_every_metric_name_is_legal(exposition: str) -> None:
    """A single invalid name makes Prometheus discard the entire scrape."""
    illegal = []
    for line in _sample_lines(exposition):
        name = line.split("{")[0].split(" ")[0]
        if not LEGAL_NAME.match(name):
            illegal.append(name)

    assert not illegal, (
        f"{len(illegal)} illegal metric name(s) in /metrics: {sorted(set(illegal))[:5]}. "
        f"Prometheus rejects the whole response, so every app metric and every alert "
        f"built on one goes silent."
    )


def test_no_metric_name_contains_a_path(exposition: str) -> None:
    """Route identity belongs in a label, never in the metric name."""
    offenders = [
        line.split("{")[0].split(" ")[0]
        for line in _sample_lines(exposition)
        if "/" in line.split("{")[0].split(" ")[0]
    ]

    assert not offenders, f"route paths leaked into metric names: {sorted(set(offenders))[:5]}"


def test_latency_is_published_under_a_stable_name_with_a_route_label(exposition: str) -> None:
    """The cardinality bound must be a label value, which Prometheus can aggregate."""
    latency = [line for line in _sample_lines(exposition) if line.startswith("api_request_duration_seconds")]

    assert latency, "no request latency is published at all"
    assert any('route="/v2/overview"' in line for line in latency), (
        "the route template is not carried as a label, so latency cannot be aggregated "
        "per route"
    )


def test_latency_is_recorded_in_seconds(exposition: str) -> None:
    """A _seconds histogram fed milliseconds puts every observation above the top bucket.

    The request measured here is an in-process call, so a plausible duration is far below
    one second. A sum in the thousands means the value was scaled wrong.
    """
    sums = [
        float(line.rsplit(" ", 1)[1])
        for line in _sample_lines(exposition)
        if line.startswith("api_request_duration_seconds_sum")
    ]

    assert sums, "no latency sum published"
    assert max(sums) < 30.0, (
        f"latency sum {max(sums)} is implausible for a seconds histogram; the value is "
        f"probably milliseconds"
    )


def test_unmatched_requests_are_labelled_not_named(exposition: str) -> None:
    """An unmatched path must not create a series per path."""
    assert "unmatched" in exposition, "unmatched requests are not recorded at all"
    assert not any(
        "/definitely-not-a-route" in line.split("{")[0].split(" ")[0]
        for line in _sample_lines(exposition)
    ), "the concrete unmatched path leaked into a metric name"
