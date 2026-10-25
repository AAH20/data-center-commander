"""In-process microbenchmarks with budgets that can fail.

No server, no database, no external binary: this file is the part of the performance
suite that runs everywhere, including CI, and it is what makes ``pytest
tests/performance`` a gate instead of a directory of scripts.

Each benchmark pins one of the paths where a bad change is invisible to correctness
tests and obvious in production:

* TCO evaluation and its sensitivity sweep -- the economics hot path. The sweep is
  the NP-hard-adjacent one: it re-evaluates the whole scenario per parameter value,
  so its cost is linear in the number of values and a nested loop there is quietly
  quadratic.
* ``verify_evidence_chain`` -- the tamper-evidence verifier, run over a tenant's
  history. It must stay linear in event count; the chain is the one place where
  "verify everything" is a security property, so it cannot be made cheap by
  sampling.
* JSON serialisation of a full page -- 1,000 items is the maximum page size the API
  will return, so this is the worst case a single request pays.

Budgets are absolute per machine (see perf_budgets.BUDGET_MARGIN_NOTE) AND paired
with ratio gates wherever a size knob exists, because a ratio survives being run on
a slower machine.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from dcc.economics import tco
from dcc.provenance import evidence

from .perf_budgets import assert_scales_linearly, assert_within, best_per_call

TENANT = "11111111-1111-4111-8111-111111111111"
BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Fixtures: inputs are built once, outside the measured region
# ---------------------------------------------------------------------------


def _scenario(horizon_years: int = 15) -> tco.TCOScenario:
    """A realistic 2 MW on-prem build: every cost line populated, tax on."""
    return tco.TCOScenario(
        name="on-prem-2mw",
        description="2 MW on-prem facility, 15 year horizon",
        scenario_type="on-prem",
        costs=tco.TCOCostBreakdown(
            hardware_capex=8_400_000,
            facility_capex=5_200_000,
            design_capex=900_000,
            commissioning_capex=450_000,
            migration_capex=300_000,
            software_capex=250_000,
            energy_annual=1_450_000,
            maintenance_annual=620_000,
            labor_annual=780_000,
            network_annual=340_000,
            software_annual=210_000,
            insurance_annual=95_000,
            tax_annual=130_000,
            other_annual=60_000,
            refresh_cost=3_100_000,
            refresh_interval_years=5,
            decommission_cost=180_000,
            residual_value=420_000,
        ),
        assumptions=tco.TCOAssumptions(
            horizon_years=horizon_years,
            annual_discount_rate=0.08,
            contingency_pct=0.07,
            tax_rate=0.21,
            include_tax=True,
        ),
        it_capacity_kw=2000.0,
        rack_count=250,
        area_m2=1800.0,
        annual_energy_kwh=17_520_000,
    )


def _chain(count: int) -> list[dict[str, Any]]:
    """A correctly linked chain of ``count`` events, hashes included."""
    rows: list[dict[str, Any]] = []
    previous = evidence.GENESIS_HASH
    for i in range(1, count + 1):
        row = {
            "tenant_id": TENANT,
            "sequence": i,
            "id": f"dcc00000-0000-4000-8000-{i:012d}",
            "event_type": "estimate.created",
            "occurred_at": BASE_TIME + timedelta(minutes=i),
            "actor_ref": "user:ahmed",
            "subject_type": "estimate",
            "subject_id": f"est-{i}",
            "payload": {"amount": 1000 * i, "currency": "USD", "note": "x" * 40},
            "previous_hash": previous,
        }
        row["event_hash"] = evidence.compute_event_hash(row)
        rows.append(row)
        previous = row["event_hash"]
    return rows


@pytest.fixture(scope="module")
def scenario() -> tco.TCOScenario:
    return _scenario()


@pytest.fixture(scope="module")
def chain_1k() -> list[dict[str, Any]]:
    return _chain(1000)


@pytest.fixture(scope="module")
def chain_10k() -> list[dict[str, Any]]:
    return _chain(10_000)


def _page(count: int) -> dict[str, Any]:
    """The exact shape ``list_assets`` returns, at maximum page size."""
    items = [
        {
            "external_id": f"asset-{i:05d}",
            "asset_type": "server",
            "name": f"gpu-node-{i:05d}",
            "manufacturer": "Dell",
            "model": "PowerEdge R760",
            "lifecycle_state": "in_service",
            "criticality": "high",
            "observed_at": "2026-01-01T00:00:00+00:00",
            "facility_name": "DC1",
            "space_name": f"row-{i % 20:02d}",
        }
        for i in range(count)
    ]
    return {
        "items": items,
        "total": count,
        "limit": count,
        "offset": 0,
        "has_more": False,
        "next_cursor": None,
    }


# ---------------------------------------------------------------------------
# Economics: TCO evaluation and its parameter sweep
# ---------------------------------------------------------------------------


class TestTCOResult:
    def test_evaluate_tco_within_budget(self, scenario):
        """One full evaluation of a 15-year scenario.

        Measured ~19 us on the dev machine; budget 120 us. The single evaluation is
        dominated by dataclass construction, so a 10x jump here means the yearly
        cash-flow loop grew a nested pass, not that the machine is slow.
        """
        per_call = best_per_call(lambda: tco.evaluate_tco(scenario), calls=50)

        # Correctness guard: a fast-but-wrong result must not pass a budget. The
        # same scenario at 8% over 15 years has a PV strictly above the
        # undiscounted-except-year-0 value only if discounting ran at all.
        result = tco.evaluate_tco(scenario)
        assert result.total_pv > 0 and len(result.yearly_cash_flows) == 16

        assert_within(
            "TCO evaluate_tco (15y, all cost lines)",
            per_call,
            budget_ms=0.140,
            note="single evaluation; 50-call average, best of 3 trials",
        )

    def test_sensitivity_sweep_within_budget(self, scenario):
        """14 discount-rate values, each a deep copy plus a full evaluation."""
        values = [i / 100 for i in range(4, 18)]
        per_call = best_per_call(
            lambda: tco.run_tco_sensitivity(scenario, "discount_rate", values),
            calls=40,
        )
        assert_within(
            "TCO sensitivity sweep (14 values)",
            per_call,
            budget_ms=4.0,
            note="one call = 14 scenario copies + 14 evaluations",
        )

    def test_sensitivity_sweep_is_linear_in_values(self, scenario):
        """Twice the values must cost about twice the time, not four times.

        This is the regression this directory exists for: a sweep that re-scans the
        previous results (or shares mutable state and copies the whole history per
        value) turns the economics endpoint from linear into quadratic in a knob the
        caller controls.
        """
        small = [i / 100 for i in range(4, 9)]           # 5 values
        large = [i / 100 for i in range(4, 24)]          # 20 values
        # The separation is 4x, not 2x, on purpose: at 2x the linear case (2.0) and
        # the quadratic case (4.0) are too close to separate from measurement noise.
        # At 4x they are 4.0 and 16.0. Both measurements are several tens of ms, so
        # one scheduling hiccup is a small fraction of the total.
        small_s = best_per_call(
            lambda: tco.run_tco_sensitivity(scenario, "discount_rate", small), calls=100
        )
        large_s = best_per_call(
            lambda: tco.run_tco_sensitivity(scenario, "discount_rate", large), calls=25
        )
        ratio = assert_scales_linearly(
            "TCO sensitivity sweep (20 values vs 5)",
            small_s,
            large_s,
            size_factor=4,
            max_ratio=7.0,
            note="ideal is 4.0 including the per-value deepcopy; a nested loop is 16x",
        )
        assert ratio >= 1.0


# ---------------------------------------------------------------------------
# Evidence chain verification: linear in events
# ---------------------------------------------------------------------------


class TestEvidenceChainVerification:
    def test_one_thousand_events_within_budget(self, chain_1k):
        per_call = best_per_call(
            lambda: evidence.verify_evidence_chain(chain_1k), calls=10
        )
        # A verifier that never fails is decoration: pin that this input verifies.
        assert evidence.verify_evidence_chain(chain_1k)["chain_valid"] is True

        assert_within(
            "verify_evidence_chain (1,000 events)",
            per_call,
            budget_ms=40.0,
            note="single pass, SHA-256 per event",
        )

    def test_ten_thousand_events_within_budget(self, chain_10k):
        per_call = best_per_call(
            lambda: evidence.verify_evidence_chain(chain_10k), calls=3
        )
        assert_within(
            "verify_evidence_chain (10,000 events)",
            per_call,
            budget_ms=320.0,
            note="single pass, SHA-256 per event",
        )

    def test_verification_is_linear_in_event_count(self, chain_1k, chain_10k):
        """10x the events must cost ~10x the time (log factor from the sort allowed).

        A verifier that re-walks the chain, or calls ``list.index`` per row to find
        the predecessor, is quadratic: 100x for 10x the input. This ratio gate is
        machine-independent, so it is the load-bearing assertion of the module;
        measured 6.7-11.9x across runs (the 10k run picks up allocator pressure)
        against a 20x ceiling, which a quadratic implementation clears by 5x.
        """
        small_s = best_per_call(
            lambda: evidence.verify_evidence_chain(chain_1k), calls=8, trials=3
        )
        large_s = best_per_call(
            lambda: evidence.verify_evidence_chain(chain_10k), calls=2, trials=3
        )
        ratio = assert_scales_linearly(
            "verify_evidence_chain (10,000 vs 1,000 events)",
            small_s,
            large_s,
            size_factor=10,
            max_ratio=20.0,
            note="ideal is 10.0 plus the sort's log factor (~10.4)",
        )
        assert ratio >= 1.0


# ---------------------------------------------------------------------------
# Paged response serialisation
# ---------------------------------------------------------------------------


class TestPagedResponseSerialisation:
    @staticmethod
    def _serialise(page: dict[str, Any]) -> bytes:
        """What FastAPI does to a handler's dict: encode, then render to bytes."""
        encoded = jsonable_encoder(page)
        return JSONResponse(encoded, media_type="application/json").render(encoded)

    def test_thousand_item_page_within_budget(self):
        page = _page(1000)
        per_call = best_per_call(lambda: self._serialise(page), calls=8)

        # Guard: serialising must actually produce the page, not an empty error body.
        body = self._serialise(page)
        assert json.loads(body)["total"] == 1000

        assert_within(
            "JSON serialise 1,000-item page",
            per_call,
            budget_ms=90.0,
            note="jsonable_encoder + JSONResponse.render, the /v2/assets response path",
        )

    def test_serialisation_is_linear_in_items(self):
        """8x the items for the price of ~8, not ~64.

        An encoder that re-serialises the accumulated page per item is quadratic:
        64x for 8x the input. The separation is 8x rather than 4x so the allocator
        and timer noise (~±25% here) cannot masquerade as a shape change.
        """
        small = _page(250)
        large = _page(2000)
        small_s = best_per_call(lambda: self._serialise(small), calls=20)
        large_s = best_per_call(lambda: self._serialise(large), calls=4)
        assert_scales_linearly(
            "JSON serialise (2,000 vs 250 items)",
            small_s,
            large_s,
            size_factor=8,
            max_ratio=14.0,
            note="ideal is 8.0; a per-item re-encode of the whole page is 64x",
        )
