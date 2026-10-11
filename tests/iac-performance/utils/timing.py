"""
Timing utilities for IaC performance tests.
Provides decorators and helpers for measuring execution time.
"""

import functools
import statistics
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any


class Timer:
    """Context manager for timing code blocks."""

    def __init__(self, name: str = "operation"):
        self.name = name
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.elapsed: float = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.end_time = time.perf_counter()
        self.elapsed = self.end_time - self.start_time

    @property
    def elapsed_ms(self) -> float:
        return self.elapsed * 1000


def benchmark(repeats: int = 5, warmup: int = 1) -> Callable:
    """
    Decorator that benchmarks a function over multiple repeats.
    Returns a dict with timing statistics.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> dict[str, Any]:
            # Warmup runs
            for _ in range(warmup):
                func(*args, **kwargs)

            timings: list[float] = []
            for _ in range(repeats):
                start = time.perf_counter()
                result = func(*args, **kwargs)
                end = time.perf_counter()
                timings.append((end - start) * 1000)  # ms

            return {
                "result": result,
                "timings_ms": timings,
                "mean_ms": statistics.mean(timings),
                "median_ms": statistics.median(timings),
                "stdev_ms": statistics.stdev(timings) if len(timings) > 1 else 0.0,
                "min_ms": min(timings),
                "max_ms": max(timings),
                "repeats": repeats,
            }

        return wrapper

    return decorator


@contextmanager
def timed_section(name: str):
    """Context manager that prints timing information."""
    timer = Timer(name)
    with timer:
        yield timer
    print(f"  [{timer.name}] {timer.elapsed_ms:.1f}ms")


def assert_performance(
    elapsed_ms: float,
    threshold_ms: float,
    operation: str,
    details: str = "",
):
    """Assert that an operation completed within the performance threshold."""
    if elapsed_ms > threshold_ms:
        raise AssertionError(
            f"Performance regression: {operation} took {elapsed_ms:.1f}ms "
            f"(threshold: {threshold_ms:.1f}ms). {details}"
        )
