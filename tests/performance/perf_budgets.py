"""Measurement primitives and budget assertions for the performance suite.

WHY THIS MODULE EXISTS
----------------------
``tests/performance`` used to contain only k6 and Artillery scenarios. Those need a
live server plus an external binary, so nothing in this directory could run in CI,
``pytest tests/performance`` exited 5 ("no tests ran"), and there was no number
anywhere in the repo that would move if somebody introduced an O(n^2) regression.

Everything here is pure pytest + ``time.perf_counter`` -- no pytest-benchmark, no
dependency that is not already in the test extra.

DESIGN RULES (read before changing a budget)
-------------------------------------------
1. A budget must be able to fail. Every assertion states the measured value, the
   budget, and how far over it went, so a red build is actionable without a rerun.
2. Prefer RATIO gates over absolute wall-clock gates wherever a size knob exists.
   A ratio compares the same code on the same machine at two input sizes, so it is
   machine-independent: 10x the input must not cost more than ``max_ratio`` times
   the time. That is what detects an accidental quadratic, and it is unaffected by
   a slow CI runner.
3. Absolute gates carry a deliberate margin, and that margin is expressed against a
   REFERENCE MACHINE and then scaled by a probe measured in the same run -- see
   ``machine_scale``. A stated ceiling therefore means "this many ms on an idle
   reference machine"; on a slower or busier machine the ceiling loosens by the
   measured factor, capped at ``CALIBRATION_MAX_SCALE``. Without this the gate is
   either flaky (a busy runner trips it) or useless (a ceiling large enough for the
   busiest runner cannot notice a 10x regression). With it, the ceiling still trips
   on a 10x regression on any machine, because the margin (6x) is smaller than the
   regression we care about (10x) and the cap (4x) does not change that.
4. ``min`` over trials, never ``mean``: we want the cost of the code, not the cost
   of whatever else the machine was doing.
"""

from __future__ import annotations

import gc
import json
import math
import statistics
import time
from collections.abc import Callable, Sequence

__all__ = [
    "BUDGET_MARGIN_NOTE",
    "CALIBRATION_MAX_SCALE",
    "RECORD",
    "assert_scales_linearly",
    "assert_within",
    "best_p95",
    "best_per_call",
    "machine_scale",
    "measure_latencies",
    "percentile",
]

#: Recorded as (label, measured_seconds, budget_ms) so conftest can print a table of
#: every number the suite produced, pass or fail. A perf suite whose numbers are
#: invisible on a green run gets "optimised" blind.
RECORD: list[tuple[str, float, float]] = []

BUDGET_MARGIN_NOTE = (
    "ceilings are ~6x the value measured on an idle reference machine and are scaled "
    "up (never down) by the measured machine factor; the margin is deliberately "
    "smaller than 10x so an order-of-magnitude regression still reddens"
)

TRIALS = 3

#: Median cost of one ``_calibration_work`` call on an IDLE reference machine
#: (Apple M-series, CPython 3.11): ~30 us. Deliberately set at the high end of what
#: was observed, because over-estimating it only means "no scaling" on a fast
#: machine, while under-estimating it would loosen every ceiling on a fast machine.
CALIBRATION_REFERENCE_S = 0.000030

#: A machine more than this much slower than the reference is simply too slow to
#: measure on; the factor stops here so the gate cannot be loosened without bound.
CALIBRATION_MAX_SCALE = 4.0

#: Probe samples per scale measurement. The MEDIAN is used, not the minimum: a
#: minimum measures the machine's best instant, which is the same whether the box is
#: idle or loaded with five other builds, and therefore cannot detect the contention
#: that makes a wall-clock ceiling flaky in the first place.
CALIBRATION_SAMPLES = 9


def _calibration_work() -> str:
    """A fixed amount of ALLOCATION-heavy work, used to detect a slow/busy machine.

    Deliberately not a tight integer loop: the workloads being measured (dict
    building, JSON encoding, SHA-256 over 10k dicts) slow down far more under
    contention than a register-resident loop does, because they compete for memory
    bandwidth and the allocator. An integer probe reads ~1.0x while those paths are
    running 4x slower, which is exactly the case this factor exists to catch.
    """
    payload = {"items": [{"id": i, "name": f"n{i}", "v": i * 1.5} for i in range(30)]}
    return json.dumps(payload, sort_keys=True)


def machine_scale() -> float:
    """How much slower this machine is right now than the reference, clamped to [1, 4].

    Measured fresh on every call so a test that runs while the runner is busy is
    judged against the machine it actually ran on. The result only ever LOOSENS a
    ceiling: a machine faster than the reference gets 1.0, never a tighter budget,
    because tightening would make the gate a machine-speed test.
    """
    samples: list[float] = []
    for _ in range(CALIBRATION_SAMPLES):
        started = time.perf_counter()
        _calibration_work()
        samples.append(time.perf_counter() - started)
    measured = statistics.median(samples)
    return min(CALIBRATION_MAX_SCALE, max(1.0, measured / CALIBRATION_REFERENCE_S))


def _timed(fn: Callable[[], object], calls: int) -> float:
    """Run ``fn`` ``calls`` times with the collector paused; seconds per call.

    The cyclic GC is disabled for the timed region because its cost is a function of
    heap size, not of the code under test: a serialisation benchmark that allocates
    a 2,000-item page triggers generational collections the 500-item run never
    reaches, which shows up as a *super-linear* ratio that has nothing to do with
    the algorithm. Pausing it makes the measurement describe the code.
    """
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        started = time.perf_counter()
        for _ in range(calls):
            fn()
        elapsed = time.perf_counter() - started
    finally:
        if was_enabled:
            gc.enable()
    return elapsed / calls


def best_per_call(fn: Callable[[], object], calls: int = 1, trials: int = TRIALS) -> float:
    """Seconds per call for ``fn``, best of ``trials`` runs of ``calls`` calls.

    ``calls`` amortises timer resolution and per-call noise; the reported value is
    the fastest observed average, which is the closest available estimate of the
    code's own cost. ``min`` over trials rather than the mean: on a shared machine
    the mean measures the neighbours, the min measures the code.
    """
    if calls < 1:
        raise ValueError("calls must be >= 1")
    gc.collect()
    return min(_timed(fn, calls) for _ in range(trials))


def measure_latencies(
    fn: Callable[[], object],
    samples: int = 30,
    warmup: int = 3,
) -> list[float]:
    """Per-call latencies (seconds) for ``samples`` sequential calls.

    A warmup is discarded so the first-call cost of lazy imports and connection
    setup does not dominate a p95 over a small sample.
    """
    for _ in range(warmup):
        fn()
    out: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        fn()
        out.append(time.perf_counter() - started)
    return out


def best_p95(
    fn: Callable[[], object],
    samples: int = 30,
    warmup: int = 3,
    trials: int = TRIALS,
    pct: float = 95.0,
) -> tuple[float, list[float]]:
    """Best p95 across ``trials`` independent batches of ``samples`` calls.

    p95 of a single 30-sample batch is the second-worst call, so ONE context switch
    or a neighbouring build on the same runner becomes the reported p95 -- a 3x
    swing that has nothing to do with the handler. Taking the p95 of each batch and
    keeping the best batch keeps the assertion about the tail of the code's own
    latency distribution rather than about the machine's scheduling luck.

    Returns ``(p95_seconds, samples_of_the_winning_batch)``.
    """
    if samples < 20:
        raise ValueError("samples must be >= 20 for a meaningful p95")
    best = math.inf
    best_samples: list[float] = []
    for _ in range(trials):
        batch = measure_latencies(fn, samples=samples, warmup=warmup)
        value = percentile(batch, pct)
        if value < best:
            best, best_samples = value, batch
    return best, best_samples


def percentile(samples: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile. ``pct`` is 0-100."""
    if not samples:
        raise ValueError("no samples")
    if not 0 < pct <= 100:
        raise ValueError("pct must be in (0, 100]")
    ordered = sorted(samples)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[rank - 1]


def _record(label: str, measured_s: float, budget_ms: float, record: bool) -> None:
    if record:
        RECORD.append((label, measured_s, budget_ms))


def assert_within(
    label: str,
    measured_s: float,
    budget_ms: float,
    note: str = "",
    record: bool = True,
    scale: float | None = None,
) -> None:
    """Fail with the measured number if ``measured_s`` exceeds ``budget_ms``.

    ``budget_ms`` is stated for the reference machine; it is multiplied by
    ``machine_scale()`` (or by ``scale`` when the caller already measured one) before
    the comparison, and both numbers appear in the failure message.

    The message is the whole point of the gate: a human reading CI output must be
    able to tell what got slower, by how much, and against what ceiling.
    """
    factor = machine_scale() if scale is None else scale
    effective_ms = budget_ms * factor
    _record(label, measured_s, effective_ms, record)
    budget_s = effective_ms / 1000.0
    if measured_s > budget_s:
        raise AssertionError(
            f"BUDGET EXCEEDED: {label} took {measured_s * 1000:.2f} ms, "
            f"budget {effective_ms:.2f} ms "
            f"({budget_ms:.2f} ms x {factor:.2f} machine scale) -- "
            f"{measured_s / budget_s:.1f}x over, "
            f"{measured_s * 1000 - effective_ms:+.2f} ms. {note} {BUDGET_MARGIN_NOTE}."
        )


def assert_scales_linearly(
    label: str,
    small_s: float,
    large_s: float,
    size_factor: float,
    max_ratio: float,
    note: str = "",
) -> float:
    """Fail if going ``size_factor``x bigger cost more than ``max_ratio``x the time.

    ``max_ratio`` sits just above the ideal ``size_factor`` (plus the log factor
    for a sort), so linear-with-a-small-constant passes and quadratic does not.
    Returns the measured ratio so a caller can print it.
    """
    ratio = large_s / small_s if small_s > 0 else math.inf
    if ratio > max_ratio:
        raise AssertionError(
            f"NOT LINEAR: {label} cost {ratio:.2f}x more for {size_factor:g}x the input "
            f"(budget {max_ratio:.2f}x). small={small_s * 1000:.3f} ms, "
            f"large={large_s * 1000:.3f} ms. That shape is super-linear -- an O(n^2) "
            f"or repeated-scan regression, not noise (a ratio is machine-independent). "
            f"{note}"
        )
    return ratio
