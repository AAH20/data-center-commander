"""Fuzz tests for cost allocation engine using Hypothesis."""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st, assume

from dcc.economics.allocation import (
    AllocationMethod,
    WorkloadShare,
    allocate_cost,
    validate_allocation,
    compute_allocation_hash,
)


# Strategies
non_negative_decimals = st.decimals(
    min_value=Decimal("0"), max_value=Decimal("1000000"), allow_nan=False, allow_infinity=False
)

positive_decimals = st.decimals(
    min_value=Decimal("0.001"), max_value=Decimal("1000000"), allow_nan=False, allow_infinity=False
)

currency_codes = st.sampled_from(["USD", "EUR", "GBP", "JPY"])

allocation_methods = st.sampled_from(list(AllocationMethod))


class TestAllocationFuzz:
    """Fuzz cost allocation with various inputs."""

    @given(
        total_amount=non_negative_decimals,
        currency=currency_codes,
        num_workloads=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_equal_share_allocation(self, total_amount, currency, num_workloads):
        """Equal share allocation should always sum to total."""
        workload_ids = [f"wl-{i}" for i in range(num_workloads)]
        report = allocate_cost(
            cost_actual_id="test-cost",
            total_amount=total_amount,
            currency=currency,
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=workload_ids,
        )
        assert report.allocated_total == total_amount
        assert len(report.results) == num_workloads
        assert validate_allocation(report)

    @given(
        total_amount=non_negative_decimals,
        currency=currency_codes,
        shares=st.lists(non_negative_decimals, min_size=1, max_size=10),
    )
    @settings(max_examples=100)
    def test_direct_meter_allocation(self, total_amount, currency, shares):
        """Direct meter allocation should always sum to total."""
        workload_ids = [f"wl-{i}" for i in range(len(shares))]
        share_objs = [
            WorkloadShare(workload_id=wid, share_value=val)
            for wid, val in zip(workload_ids, shares)
        ]
        report = allocate_cost(
            cost_actual_id="test-cost",
            total_amount=total_amount,
            currency=currency,
            method=AllocationMethod.DIRECT_METER,
            workload_ids=workload_ids,
            shares=share_objs,
        )
        assert report.allocated_total == total_amount
        assert len(report.results) == len(shares)
        assert validate_allocation(report)

    @given(
        total_amount=non_negative_decimals,
        currency=currency_codes,
        weights=st.lists(positive_decimals, min_size=1, max_size=10),
    )
    @settings(max_examples=100)
    def test_manual_approved_allocation(self, total_amount, currency, weights):
        """Manual approved allocation should always sum to total."""
        workload_ids = [f"wl-{i}" for i in range(len(weights))]
        custom_weights = {wid: val for wid, val in zip(workload_ids, weights)}
        report = allocate_cost(
            cost_actual_id="test-cost",
            total_amount=total_amount,
            currency=currency,
            method=AllocationMethod.MANUAL_APPROVED,
            workload_ids=workload_ids,
            custom_weights=custom_weights,
        )
        assert report.allocated_total == total_amount
        assert len(report.results) == len(weights)
        assert validate_allocation(report)

    @given(
        total_amount=non_negative_decimals,
        currency=currency_codes,
        num_workloads=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_allocation_with_zero_shares(self, total_amount, currency, num_workloads):
        """Allocation with all zero shares should fall back to equal division."""
        workload_ids = [f"wl-{i}" for i in range(num_workloads)]
        shares = [WorkloadShare(workload_id=wid, share_value=Decimal("0")) for wid in workload_ids]
        report = allocate_cost(
            cost_actual_id="test-cost",
            total_amount=total_amount,
            currency=currency,
            method=AllocationMethod.DIRECT_METER,
            workload_ids=workload_ids,
            shares=shares,
        )
        assert report.allocated_total == total_amount
        assert validate_allocation(report)

    @given(
        total_amount=non_negative_decimals,
        currency=currency_codes,
        num_workloads=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_allocation_hash_deterministic(self, total_amount, currency, num_workloads):
        """Allocation hash should be deterministic."""
        workload_ids = [f"wl-{i}" for i in range(num_workloads)]
        report1 = allocate_cost(
            cost_actual_id="test-cost",
            total_amount=total_amount,
            currency=currency,
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=workload_ids,
        )
        report2 = allocate_cost(
            cost_actual_id="test-cost",
            total_amount=total_amount,
            currency=currency,
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=workload_ids,
        )
        assert compute_allocation_hash(report1) == compute_allocation_hash(report2)

    @given(
        total_amount=non_negative_decimals,
        currency=currency_codes,
        num_workloads=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_allocation_fractions_sum_to_one(self, total_amount, currency, num_workloads):
        """Allocation fractions should sum to approximately 1.0."""
        assume(total_amount > 0)
        workload_ids = [f"wl-{i}" for i in range(num_workloads)]
        report = allocate_cost(
            cost_actual_id="test-cost",
            total_amount=total_amount,
            currency=currency,
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=workload_ids,
        )
        fraction_sum = sum(r.allocation_fraction for r in report.results)
        assert abs(fraction_sum - Decimal("1")) < Decimal("0.001")
