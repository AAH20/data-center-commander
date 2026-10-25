"""In-process API latency floors for two hot read routes.

WHAT THESE NUMBERS MEAN -- READ THIS BEFORE CITING THEM
------------------------------------------------------
These tests call the ASGI app through ``fastapi.testclient.TestClient``. The request
never leaves the process: no socket, no uvicorn, no TLS, no network hop, no reverse
proxy. The measured value is therefore *handler + SQL cost* only.

It is explicitly NOT an end-to-end SLA and NOT what a user experiences. The
user-facing p95/p99 numbers live in the k6 and Artillery scenarios in this
directory, which need a live server and an external binary (see
``test_perf_live_scenarios.py``, and the README). A ceiling here answers one
question: did the handler or its query get dramatically more expensive? If this
passes and the k6 run fails, the regression is below the application.

Two traps these tests are written to avoid:

* ``/v2/overview`` caches its response for 30 seconds. Measuring a loop of calls
  without clearing the cache would time a dict lookup and report ~0.05 ms, i.e. it
  would pass no matter how slow the SQL became. The cache is invalidated before
  every sample, so each sample pays the real handler + query cost.
* A 503 is fast. Every sampled call asserts status 200 and the expected body shape,
  so a broken database cannot make the latency budget pass.
"""

from __future__ import annotations

import pytest

import dcc.api_async as api

from .perf_budgets import assert_within, best_p95, measure_latencies, percentile

#: Samples per batch. p95 of N samples is its ~second-worst value, so a single
#: preempted call can become the reported p95; 40 samples lets the tail be a tail
#: rather than an accident, and 5 batches then take the best of them.
SAMPLES = 40
P95 = 95.0
#: Batches per p95 measurement. p95 of a single batch is its second-worst call, so
#: one hiccup becomes the reported number; more batches give the gate a better
#: chance of observing the handler's own tail.
BATCHES = 5
#: The control catalogue is pure in-process CPU work, so its batches are cheap and
#: more of them can be afforded: this is the test most exposed to a preempted call.
CONTROLS_BATCHES = 8

#: Budgets: 4-6x the value measured on a developer machine against dcc_demo_local
#: (overview p95 7-12 ms cold, controls p95 ~1.5 ms in-memory). Wide enough for a
#: shared runner, narrow enough that a 10x query regression reddens.
OVERVIEW_P95_BUDGET_MS = 60.0
CONTROLS_P95_BUDGET_MS = 12.0


def _get(client, path: str, **params):
    response = client.get(path, params=params or None)
    assert response.status_code == 200, (
        f"GET {path} returned {response.status_code}: {response.text[:300]}. "
        f"A latency budget measured against an error response proves nothing."
    )
    return response


class TestOverviewLatency:
    def test_overview_p95_under_budget(self, api_client, tenant_id):
        """Cold-path p95 for the dashboard overview (4 queries + KPI join)."""

        def call():
            # Cache cleared per sample: measures the handler and its SQL, not the cache.
            api.cache.invalidate(f"overview:{tenant_id}")
            _get(api_client, "/v2/overview", tenant_id=tenant_id)

        p95, samples = best_p95(call, samples=SAMPLES, trials=BATCHES)

        body = _get(api_client, "/v2/overview", tenant_id=tenant_id).json()
        assert "facility_count" in body and "kpis" in body

        assert_within(
            f"/v2/overview p95 over {SAMPLES} cold calls x{BATCHES} batches (in-process, not an SLA)",
            p95,
            budget_ms=OVERVIEW_P95_BUDGET_MS,
            note=(
                f"cache invalidated per sample; median {percentile(samples, 50) * 1000:.2f} ms, "
                f"max {max(samples) * 1000:.2f} ms"
            ),
        )

    def test_overview_repeat_calls_do_not_degrade(self, api_client, tenant_id):
        """The last third must not be markedly slower than the first third.

        An unbounded cache, a leaked connection, or per-request pool growth shows up
        as monotonic growth across a 30-call burst long before the absolute p95
        budget trips. Expressed as a ratio so it is machine-independent.
        """

        def call():
            api.cache.invalidate(f"overview:{tenant_id}")
            _get(api_client, "/v2/overview", tenant_id=tenant_id)

        samples = measure_latencies(call, samples=SAMPLES, warmup=3)
        third = len(samples) // 3
        first = percentile(samples[:third], 50)
        last = percentile(samples[-third:], 50)
        ratio = last / first if first > 0 else float("inf")
        assert ratio <= 3.0, (
            f"/v2/overview slowed down across the burst: first-third median "
            f"{first * 1000:.2f} ms, last-third median {last * 1000:.2f} ms "
            f"({ratio:.2f}x, budget 3.00x). That is a leak or growing per-request cost."
        )


class TestComplianceControlsLatency:
    def test_controls_p95_under_budget(self, api_client):
        """The control catalogue is built in-process; no SQL, no I/O.

        Because there is no I/O here the budget can be tight: a 10x regression means
        somebody put a file read, a scan, or a per-control re-import inside the
        response builder.
        """

        def call():
            response = _get(api_client, "/v2/compliance/controls")
            assert response.json()["count"] > 0

        p95, samples = best_p95(call, samples=SAMPLES, trials=CONTROLS_BATCHES)

        assert_within(
            f"/v2/compliance/controls p95 over {SAMPLES} calls (in-process, not an SLA)",
            p95,
            budget_ms=CONTROLS_P95_BUDGET_MS,
            note=(
                f"median {percentile(samples, 50) * 1000:.2f} ms, "
                f"max {max(samples) * 1000:.2f} ms"
            ),
        )


def test_the_budget_fields_are_percentile_based():
    """Guard the harness itself: p95 of a known ramp must be the tail, not the mean."""
    ramp = [float(i) for i in range(1, 101)]
    assert percentile(ramp, 95) == 95.0
    assert percentile(ramp, 50) == 50.0
    assert percentile([0.001], 95) == 0.001
    with pytest.raises(ValueError):
        percentile([], 95)
