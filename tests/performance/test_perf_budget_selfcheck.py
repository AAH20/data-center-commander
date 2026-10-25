"""Proof that the performance budgets can actually fail.

A performance test that has never been seen red is decoration. This session's repo
had exactly that: a ``tests/performance`` directory with no pytest tests at all, so
"the performance suite is green" was a vacuous statement.

This module is the permanent canary. It drives the *same* helpers the real
benchmarks use (``perf_budgets.assert_within``,
``perf_budgets.assert_scales_linearly``) against functions whose cost is known in
advance, and requires the gate to reject them:

* a function that takes longer than its ceiling must raise ``BUDGET EXCEEDED``;
* an implementation that is quadratic in its input must raise ``NOT LINEAR``;
* and -- the half that stops this file from being satisfiable by "always fail" -- a
  linear function against a generous ceiling must be accepted.

If somebody "fixes" a red budget by making the assertion unfireable (raising the
ceiling to infinity, dropping the comparison, switching to ``xfail``), these tests go
red. That is the point of them.
"""

from __future__ import annotations

import time

import pytest

from .perf_budgets import (
    RECORD,
    assert_scales_linearly,
    assert_within,
    best_per_call,
    measure_latencies,
    percentile,
)


def _sleepy() -> None:
    time.sleep(0.05)


def _quadratic(n: int) -> int:
    """Deliberately O(n^2): the shape a bad chain verifier takes."""
    total = 0
    for i in range(n):
        for _ in range(n):
            total += i
    return total


def _constant(n: int) -> int:
    """Fixed cost regardless of ``n`` -- the shape of a cached lookup."""
    time.sleep(0.002)
    return n


def _linear(n: int) -> int:
    """Deliberately O(n), with a per-element cost big enough to time reliably.

    ``sum(range(n))`` was the first version and it made this control flaky: at
    ~0.5 ms the whole measurement is inside timer and scheduling noise, so the ratio
    between two runs bounced anywhere from 3x to 20x and the control failed for no
    algorithmic reason. A Python-level loop gives a stable ~10x signal.
    """
    total = 0
    for i in range(n):
        total += (i * 7) % 13
    return total


class TestAbsoluteBudgetFires:
    def test_a_slow_function_trips_its_budget(self):
        measured = best_per_call(_sleepy, calls=1, trials=1)

        with pytest.raises(AssertionError) as excinfo:
            assert_within("canary: 50 ms sleep", measured, budget_ms=10.0, record=False)

        message = str(excinfo.value)
        assert "BUDGET EXCEEDED" in message
        # The message has to be actionable on its own: what, how slow, against what
        # (the stated ceiling AND the machine-scaled one), and by how much.
        assert "canary: 50 ms sleep" in message
        assert "(10.00 ms x " in message
        assert "x over" in message

    def test_the_failure_reports_the_measured_number(self):
        with pytest.raises(AssertionError) as excinfo:
            assert_within("canary: exact 50 ms", 0.050, budget_ms=10.0, record=False)
        assert "50.00 ms" in str(excinfo.value), (
            "a budget failure that does not state the measured value forces a rerun; "
            f"got: {excinfo.value}"
        )

    def test_a_latency_ceiling_fires_on_the_p95_of_a_slow_call(self):
        """The p95 path used by the API latency floors must also be able to fail."""
        samples = measure_latencies(_sleepy, samples=20, warmup=1)
        p95 = percentile(samples, 95.0)

        with pytest.raises(AssertionError, match="BUDGET EXCEEDED"):
            assert_within("canary: p95 of 50 ms calls", p95, budget_ms=5.0, record=False)

    def test_a_passing_budget_does_not_raise_and_is_recorded(self):
        before = len(RECORD)
        assert_within("canary: within budget", 0.001, budget_ms=10.0, scale=1.0)
        assert len(RECORD) == before + 1
        label, measured, budget_ms = RECORD[-1]
        assert label == "canary: within budget"
        assert measured == pytest.approx(0.001)
        assert budget_ms == pytest.approx(10.0)
        RECORD.pop()


class TestLinearityGateFires:
    def test_a_quadratic_implementation_trips_the_linearity_gate(self):
        small = best_per_call(lambda: _quadratic(200), calls=1, trials=1)
        large = best_per_call(lambda: _quadratic(2000), calls=1, trials=1)

        with pytest.raises(AssertionError) as excinfo:
            assert_scales_linearly(
                "canary: quadratic 2,000 vs 200",
                small,
                large,
                size_factor=10,
                max_ratio=16.0,
            )

        message = str(excinfo.value)
        assert "NOT LINEAR" in message
        assert "10x the input" in message
        assert "quadratic" in message or "super-linear" in message

    def test_a_linear_implementation_passes_the_same_gate(self):
        """Control: the gate must not be a constant ``raise``.

        Without this, the canary above is satisfied by a gate that always fails and
        the real benchmarks would be red-by-construction -- which people disable.
        """
        # ~7 ms and ~70 ms, each the best of 5 trials. Both the window size and the
        # min-of-trials matter: a single preempted run on the large side is what
        # pushed this control past its ceiling when it was trials=3, and a control
        # that fails for scheduling reasons teaches people to ignore the gate.
        small = best_per_call(lambda: _linear(100_000), calls=1, trials=5)
        large = best_per_call(lambda: _linear(1_000_000), calls=1, trials=5)

        ratio = assert_scales_linearly(
            "canary: linear 1,000,000 vs 100,000",
            small,
            large,
            size_factor=10,
            max_ratio=20.0,
        )
        assert 1.0 <= ratio <= 20.0

    def test_a_constant_time_implementation_passes(self):
        """A cheaper-than-linear change (caching) must never be punished.

        A fixed 2 ms of work, whatever ``n`` is: timing ``lambda: None`` instead
        would sit in the noise floor, where the ratio between two sub-microsecond
        measurements is arbitrary and the control fails at random.
        """
        small = best_per_call(lambda: _constant(100), calls=1, trials=3)
        large = best_per_call(lambda: _constant(100_000), calls=1, trials=3)
        # No tighter assertion than the gate's own ceiling on purpose: a sleep can
        # be preempted either side of the timer read, so on a busy machine even a
        # constant workload legitimately reports several times the ratio of an idle
        # one. The claim under test is "the gate accepts constant work", not
        # "constant work measures 1.00x on a contended box".
        assert_scales_linearly(
            "canary: constant time", small, large, size_factor=10, max_ratio=20.0
        )
