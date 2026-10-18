"""Fuzz tests for boundary validation using Hypothesis."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st, assume

from dcc.validation.boundaries import (
    validate_meter_boundary,
    validate_energy_allocation,
    validate_allocation_rules,
    validate_energy_balance,
    validate_energy_budget,
    validate_meter_readings_batch,
    validate_energy_chain,
    VALID_DIRECTIONS,
    USABLE_QUALITY,
    VALID_ALLOCATION_METHODS,
)


# Strategies
decimal_values = st.decimals(
    min_value=Decimal("-1000000"), max_value=Decimal("1000000"), allow_nan=False, allow_infinity=False
)

positive_decimals = st.decimals(
    min_value=Decimal("0.001"), max_value=Decimal("1000000"), allow_nan=False, allow_infinity=False
)

non_negative_decimals = st.decimals(
    min_value=Decimal("0"), max_value=Decimal("1000000"), allow_nan=False, allow_infinity=False
)

directions = st.sampled_from(sorted(VALID_DIRECTIONS))

quality_statuses = st.sampled_from(["good", "estimated", "suspect", "missing", "unknown"])

allocation_methods = st.sampled_from(sorted(VALID_ALLOCATION_METHODS))

iso_timestamps = st.datetimes(
    min_value=datetime(2020, 1, 1, tzinfo=timezone.utc),
    max_value=datetime(2030, 12, 31, tzinfo=timezone.utc),
).map(lambda dt: dt.isoformat())


class TestMeterBoundaryFuzz:
    """Fuzz meter boundary validation."""

    @given(
        direction=directions,
        unit=st.sampled_from(["kWh", "kWh", "kW", "MW", "MWh", "W", "invalid"]),
        n_readings=st.integers(min_value=0, max_value=20),
        multiplier=st.one_of(st.none(), positive_decimals),
    )
    @settings(max_examples=100)
    def test_validate_meter_boundary(self, direction, unit, n_readings, multiplier):
        """validate_meter_boundary should handle any valid inputs."""
        readings = []
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for i in range(n_readings):
            readings.append({
                "value_numeric": float(i * 10),
                "quality_status": "good",
                "interval_start": (base.replace(hour=i)).isoformat(),
                "interval_end": (base.replace(hour=i + 1)).isoformat(),
            })
        result = validate_meter_boundary(
            meter_id="test-meter",
            boundary="energy" if "wh" in unit.lower() else "power",
            direction=direction,
            unit=unit,
            readings=readings,
            multiplier=multiplier,
        )
        assert isinstance(result.passed, bool)
        assert isinstance(result.findings, list)

    @given(
        direction=directions,
        unit=st.sampled_from(["kWh", "kW", "MW", "MWh"]),
        n_readings=st.integers(min_value=0, max_value=20),
        expected_interval=st.one_of(st.none(), st.integers(min_value=60, max_value=86400)),
    )
    @settings(max_examples=100)
    def test_validate_meter_readings_batch(self, direction, unit, n_readings, expected_interval):
        """validate_meter_readings_batch should handle any valid inputs."""
        readings = []
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for i in range(n_readings):
            readings.append({
                "value_numeric": float(i * 10),
                "quality_status": "good",
                "interval_start": (base.replace(hour=i)).isoformat(),
                "interval_end": (base.replace(hour=i + 1)).isoformat(),
            })
        result = validate_meter_readings_batch(
            meter_id="test-meter",
            boundary="energy" if "wh" in unit.lower() else "power",
            direction=direction,
            unit=unit,
            readings=readings,
            expected_interval_seconds=expected_interval,
        )
        assert isinstance(result.passed, bool)


class TestEnergyAllocationFuzz:
    """Fuzz energy allocation validation."""

    @given(
        energy_kwh=decimal_values,
        allocation_method=allocation_methods,
        lower_bound=st.one_of(st.none(), decimal_values),
        upper_bound=st.one_of(st.none(), decimal_values),
        coverage=st.one_of(st.none(), decimal_values),
    )
    @settings(max_examples=100)
    def test_validate_energy_allocation(self, energy_kwh, allocation_method, lower_bound, upper_bound, coverage):
        """validate_energy_allocation should handle any valid inputs."""
        result = validate_energy_allocation(
            allocation_id="test-alloc",
            workload_id="test-workload",
            window_start="2025-01-01T00:00:00+00:00",
            window_end="2025-01-31T23:59:59+00:00",
            energy_kwh=energy_kwh,
            allocation_method=allocation_method,
            lower_bound_kwh=lower_bound,
            upper_bound_kwh=upper_bound,
            coverage=coverage,
            formula_version="1.0",
            provenance={"source": "test"},
        )
        assert isinstance(result.passed, bool)
        assert isinstance(result.findings, list)

    @given(
        n_deployments=st.integers(min_value=0, max_value=10),
        n_allocations=st.integers(min_value=0, max_value=10),
        total_measured=st.one_of(st.none(), non_negative_decimals),
    )
    @settings(max_examples=100)
    def test_validate_allocation_rules(self, n_deployments, n_allocations, total_measured):
        """validate_allocation_rules should handle any valid inputs."""
        deployments = []
        for i in range(n_deployments):
            deployments.append({
                "allocation_method": "direct_meter",
                "allocation_fraction": 0.1,
            })
        allocations = []
        for i in range(n_allocations):
            allocations.append({
                "energy_kwh": 100.0,
            })
        result = validate_allocation_rules(
            workload_id="test-workload",
            deployments=deployments,
            allocations=allocations,
            total_measured_kwh=total_measured,
        )
        assert isinstance(result.passed, bool)

    @given(
        facility_energy=decimal_values,
        it_energy=decimal_values,
        pue_value=st.one_of(st.none(), st.decimals(min_value=Decimal("1.0"), max_value=Decimal("1000"), allow_nan=False, allow_infinity=False)),
        tolerance_pct=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_validate_energy_balance(self, facility_energy, it_energy, pue_value, tolerance_pct):
        """validate_energy_balance should handle any valid inputs."""
        result = validate_energy_balance(
            facility_energy_kwh=facility_energy,
            it_energy_kwh=it_energy,
            pue_value=pue_value,
            tolerance_pct=tolerance_pct,
        )
        assert isinstance(result.passed, bool)

    @given(
        budget=st.one_of(st.none(), decimal_values),
        allocated=decimal_values,
        window_days=st.integers(min_value=1, max_value=365),
    )
    @settings(max_examples=100)
    def test_validate_energy_budget(self, budget, allocated, window_days):
        """validate_energy_budget should handle any valid inputs."""
        result = validate_energy_budget(
            workload_id="test-workload",
            energy_budget_kwh=budget,
            allocated_kwh=allocated,
            window_days=window_days,
        )
        assert isinstance(result.passed, bool)


class TestEnergyChainFuzz:
    """Fuzz energy chain validation."""

    @given(
        n_readings=st.integers(min_value=0, max_value=20),
        n_allocations=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=100)
    def test_validate_energy_chain(self, n_readings, n_allocations):
        """validate_energy_chain should handle any valid inputs."""
        meter = {
            "id": "test-meter",
            "boundary": "energy",
            "direction": "import",
            "unit": "kWh",
            "multiplier": 1,
        }
        readings = []
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for i in range(n_readings):
            readings.append({
                "value_numeric": float(i * 10),
                "quality_status": "good",
                "interval_start": (base.replace(hour=i)).isoformat(),
                "interval_end": (base.replace(hour=i + 1)).isoformat(),
            })
        allocations = []
        for i in range(n_allocations):
            allocations.append({
                "id": f"alloc-{i}",
                "workload_id": "test-workload",
                "window_start": "2025-01-01T00:00:00+00:00",
                "window_end": "2025-01-31T23:59:59+00:00",
                "energy_kwh": 100.0,
                "allocation_method": "direct_meter",
                "formula_version": "1.0",
                "provenance": {"source": "test"},
            })
        result = validate_energy_chain(
            meter=meter,
            readings=readings,
            allocations=allocations,
        )
        assert isinstance(result.passed, bool)
