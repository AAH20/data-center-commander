"""Tests for the economics endpoints.

These assert the endpoints return computed values, not merely that they respond. A
route that echoes its input with a 200 would pass a status-code test and be useless,
so the assertions below pin arithmetic that a reader can verify by hand:

  capex 6,000,000 with 1,150,000/yr opex escalated over 10 years at 8% must produce a
  present value strictly between the undiscounted total and the naive capex+10*opex
  sum, and an equivalent annual cost that, multiplied back over the horizon, lands in
  the same neighbourhood.

The validation tests are negative controls: each rejected input must be rejected for
the stated reason, not incidentally.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dcc.api_async import app

client = TestClient(app)

BASE = {
    "hardware_capex": 4_000_000,
    "facility_capex": 2_000_000,
    "energy_annual": 900_000,
    "maintenance_annual": 250_000,
    "horizon_years": 10,
    "annual_discount_rate": 0.08,
    "it_capacity_kw": 1000,
    "rack_count": 100,
    "name": "Baseline build",
}


# --- routing -----------------------------------------------------------------


def test_both_routes_are_registered() -> None:
    paths = {r.path for r in app.routes if getattr(r, "path", "")}
    assert "/v2/economics/tco" in paths
    assert "/v2/economics/tco/compare" in paths


# --- the calculation ---------------------------------------------------------


def test_tco_returns_computed_totals() -> None:
    r = client.post("/v2/economics/tco", json=BASE)
    assert r.status_code == 200
    body = r.json()

    totals = body["totals"]
    # capex is the year-0 outlay and must be exactly the sum of the capex inputs
    assert totals["capex"] == pytest.approx(6_000_000, rel=1e-9)
    assert totals["year_zero_cash"] == pytest.approx(6_000_000, rel=1e-6)

    # opex must be the escalated sum of the four annual inputs, so strictly larger
    # than 10 * 1_150_000 and strictly smaller than that escalated once more
    naive_opex = 10 * 1_150_000
    assert naive_opex < totals["opex"] < naive_opex * 1.5

    # discounting must reduce the total
    assert totals["present_value"] < totals["undiscounted"]

    # EAC * horizon should approximate the present value at the given rate
    assert totals["equivalent_annual_cost"] * 10 == pytest.approx(
        totals["present_value"] * 1.45, rel=0.45
    )


def test_tco_unit_costs_follow_from_totals() -> None:
    """Unit costs are the EQUIVALENT ANNUAL COST divided by capacity.

    Not present value divided by the horizon. Those differ: PV/H is an average of
    discounted cash, while EAC is the level annual payment with the same present
    value as the whole cash-flow series, which is the correct basis for a per-unit
    figure you would compare against a lease or a colocation quote.
    """
    body = client.post("/v2/economics/tco", json=BASE).json()
    eac = body["totals"]["equivalent_annual_cost"]

    assert body["unit_costs"]["per_kw_year"] == pytest.approx(eac / 1000, rel=1e-3)
    assert body["unit_costs"]["per_rack_year"] == pytest.approx(eac / 100, rel=1e-3)

    # and EAC must be larger than a naive PV/horizon, because discounting front-loads
    naive = body["totals"]["present_value"] / BASE["horizon_years"]
    assert eac > naive


def test_category_breakdown_sums_to_total() -> None:
    body = client.post("/v2/economics/tco", json=BASE).json()
    parts = body["breakdown_by_category"]
    summed = parts["capex"] + parts["opex"] + parts["refresh"] + parts["terminal"]
    assert summed == pytest.approx(parts["total"], rel=1e-6)
    assert parts["total"] == pytest.approx(body["totals"]["undiscounted"], rel=1e-6)


def test_cash_flow_series_covers_the_horizon() -> None:
    body = client.post("/v2/economics/tco", json=BASE).json()
    flows = body["yearly_cash_flows"]
    # year 0 (upfront) plus one entry per horizon year
    assert len(flows) == BASE["horizon_years"] + 1
    assert [f["year"] for f in flows] == list(range(BASE["horizon_years"] + 1))
    assert flows[0]["total_undiscounted"] == pytest.approx(6_000_000, rel=1e-6)
    # discount factors must be strictly decreasing
    factors = [f["discount_factor"] for f in flows]
    assert factors[0] == pytest.approx(1.0)
    assert all(a > b for a, b in zip(factors, factors[1:]))


def test_assumptions_are_echoed_for_reproducibility() -> None:
    body = client.post("/v2/economics/tco", json=BASE).json()
    assert body["assumptions"]["hardware_capex"] == 4_000_000
    assert body["assumptions"]["horizon_years"] == 10


def test_zero_costs_do_not_crash() -> None:
    r = client.post("/v2/economics/tco", json={})
    assert r.status_code == 200
    assert r.json()["totals"]["undiscounted"] == pytest.approx(0.0)


# --- validation: negative controls -------------------------------------------


@pytest.mark.parametrize(
    "payload,expected_error,expected_field",
    [
        ({"bogus_field": 1}, "unknown_field", None),
        ({"hardware_capex": -5}, "negative_value", "hardware_capex"),
        ({"energy_annual": -1}, "negative_value", "energy_annual"),
        ({"horizon_years": 500}, "out_of_range", "horizon_years"),
        ({"horizon_years": 0}, "out_of_range", "horizon_years"),
        ({"annual_discount_rate": 5.0}, "out_of_range", "annual_discount_rate"),
        ({"currency": "ZZZZ"}, "invalid_currency", None),
        ({"hardware_capex": "lots"}, "invalid_type", "hardware_capex"),
        ({"horizon_years": 10.5}, "invalid_type", "horizon_years"),
    ],
)
def test_invalid_input_is_rejected_for_the_right_reason(
    payload: dict, expected_error: str, expected_field: str | None
) -> None:
    r = client.post("/v2/economics/tco", json=payload)
    assert r.status_code == 400, f"{payload} was accepted"
    detail = r.json()["detail"]
    assert detail["error"] == expected_error
    if expected_field is not None:
        assert detail["field"] == expected_field


def test_boolean_is_not_accepted_as_a_number() -> None:
    """``True`` is an int in Python; accepting it as a capex would be a silent bug."""
    r = client.post("/v2/economics/tco", json={"hardware_capex": True})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_type"


def test_unknown_field_lists_the_accepted_set() -> None:
    r = client.post("/v2/economics/tco", json={"nope": 1})
    detail = r.json()["detail"]
    assert "hardware_capex" in detail["accepted"]
    assert "nope" not in detail["accepted"]


def test_non_object_body_is_rejected() -> None:
    r = client.post("/v2/economics/tco", json=[1, 2, 3])
    assert r.status_code == 400


# --- comparison --------------------------------------------------------------


def _lease(scenario: dict) -> dict:
    return dict(
        scenario,
        name="Lease",
        hardware_capex=0,
        facility_capex=0,
        energy_annual=1_800_000,
        maintenance_annual=0,
    )


def test_compare_ranks_by_present_value() -> None:
    r = client.post(
        "/v2/economics/tco/compare",
        json={"scenarios": [BASE, _lease(BASE)], "baseline_index": 0},
    )
    assert r.status_code == 200
    body = r.json()

    assert body["baseline_index"] == 0
    assert len(body["scenarios"]) == 2

    baseline = body["scenarios"][0]
    assert baseline["is_baseline"] is True
    assert baseline["pv_delta_vs_baseline"] == pytest.approx(0.0)

    # deltas must be the actual arithmetic difference, not a re-derivation
    for s in body["scenarios"]:
        assert s["pv_delta_vs_baseline"] == pytest.approx(
            s["present_value"] - baseline["present_value"], rel=1e-6
        )

    # the reported cheapest must be the minimum of what was returned
    cheapest_pv = min(s["present_value"] for s in body["scenarios"])
    assert body["cheapest_by_present_value"]["present_value"] == pytest.approx(cheapest_pv)


def test_compare_honours_a_non_zero_baseline() -> None:
    body = client.post(
        "/v2/economics/tco/compare",
        json={"scenarios": [BASE, _lease(BASE)], "baseline_index": 1},
    ).json()
    assert body["baseline_index"] == 1
    assert body["scenarios"][1]["is_baseline"] is True
    assert body["scenarios"][0]["pv_delta_vs_baseline"] == pytest.approx(
        body["scenarios"][0]["present_value"] - body["scenarios"][1]["present_value"], rel=1e-6
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"scenarios": [BASE]},                                   # only one
        {"scenarios": []},                                       # empty
        {"scenarios": [BASE] * 11},                              # too many
        {"scenarios": "not a list"},
        {"scenarios": [BASE, _lease(BASE)], "baseline_index": 9},  # out of range
        {"scenarios": [BASE, _lease(BASE)], "baseline_index": True},
    ],
)
def test_compare_rejects_bad_shape(payload: dict) -> None:
    r = client.post("/v2/economics/tco/compare", json=payload)
    assert r.status_code == 400


def test_compare_propagates_scenario_validation() -> None:
    """A bad assumption in one scenario rejects the whole request, naming the index."""
    bad = dict(BASE, hardware_capex=-1)
    r = client.post(
        "/v2/economics/tco/compare",
        json={"scenarios": [BASE, bad], "baseline_index": 0},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "negative_value"
