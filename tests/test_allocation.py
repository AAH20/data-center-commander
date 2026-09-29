"""Tests for the cost allocation engine."""

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from dcc.economics.allocation import (
    METHOD_VERSION,
    AllocationMethod,
    AllocationReport,
    WorkloadShare,
    allocate_cost,
    allocation_rows_for_insert,
    build_evidence,
    compute_allocation_hash,
    shares_from_capacity,
    shares_from_energy_allocations,
    shares_from_floor_areas,
    shares_from_headcount,
    shares_from_rack_units,
    validate_allocation,
)


class TestAllocateCostEqualShare(unittest.TestCase):
    def test_equal_share_two_workloads(self):
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("1000.00"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2"],
        )
        self.assertEqual(len(report.results), 2)
        self.assertEqual(report.results[0].allocated_amount, Decimal("500.000000"))
        self.assertEqual(report.results[1].allocated_amount, Decimal("500.000000"))
        self.assertEqual(report.allocated_total, Decimal("1000.000000"))
        self.assertEqual(report.unallocated_amount, Decimal("0"))
        self.assertTrue(report.reconciliation["fully_allocated"])

    def test_equal_share_three_workloads_with_remainder(self):
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("100.00"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2", "w3"],
        )
        self.assertEqual(len(report.results), 3)
        # 100/3 = 33.333333... -> rounded to 33.333333 each = 99.999999
        # Residual 0.000001 goes to first workload
        self.assertEqual(report.results[0].allocated_amount, Decimal("33.333334"))
        self.assertEqual(report.results[1].allocated_amount, Decimal("33.333333"))
        self.assertEqual(report.results[2].allocated_amount, Decimal("33.333333"))
        self.assertEqual(report.allocated_total, Decimal("100.000000"))
        self.assertEqual(report.unallocated_amount, Decimal("0"))
        self.assertTrue(report.reconciliation["fully_allocated"])

    def test_equal_share_single_workload(self):
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("500.00"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1"],
        )
        self.assertEqual(len(report.results), 1)
        self.assertEqual(report.results[0].allocated_amount, Decimal("500.000000"))
        self.assertEqual(report.results[0].allocation_fraction, Decimal("1.000000"))

    def test_equal_share_zero_amount(self):
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("0"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2"],
        )
        self.assertEqual(report.results[0].allocated_amount, Decimal("0"))
        self.assertEqual(report.results[1].allocated_amount, Decimal("0"))
        self.assertTrue(report.reconciliation["fully_allocated"])


class TestAllocateCostByWeights(unittest.TestCase):
    def test_proportional_allocation(self):
        shares = [
            WorkloadShare(workload_id="w1", share_value=Decimal("75")),
            WorkloadShare(workload_id="w2", share_value=Decimal("25")),
        ]
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("1000.00"),
            currency="USD",
            method=AllocationMethod.MEASURED_USAGE,
            workload_ids=["w1", "w2"],
            shares=shares,
        )
        self.assertEqual(report.results[0].allocated_amount, Decimal("750.000000"))
        self.assertEqual(report.results[1].allocated_amount, Decimal("250.000000"))
        self.assertEqual(report.allocated_total, Decimal("1000.000000"))
        self.assertTrue(report.reconciliation["fully_allocated"])

    def test_proportional_allocation_with_rounding(self):
        shares = [
            WorkloadShare(workload_id="w1", share_value=Decimal("1")),
            WorkloadShare(workload_id="w2", share_value=Decimal("1")),
            WorkloadShare(workload_id="w3", share_value=Decimal("1")),
        ]
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("100.00"),
            currency="USD",
            method=AllocationMethod.MEASURED_USAGE,
            workload_ids=["w1", "w2", "w3"],
            shares=shares,
        )
        # Each gets 33.333333, residual 0.000001 to first
        self.assertEqual(report.results[0].allocated_amount, Decimal("33.333334"))
        self.assertEqual(report.results[1].allocated_amount, Decimal("33.333333"))
        self.assertEqual(report.results[2].allocated_amount, Decimal("33.333333"))
        self.assertEqual(report.allocated_total, Decimal("100.000000"))

    def test_zero_shares_falls_back_to_equal(self):
        shares = [
            WorkloadShare(workload_id="w1", share_value=Decimal("0")),
            WorkloadShare(workload_id="w2", share_value=Decimal("0")),
        ]
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("100.00"),
            currency="USD",
            method=AllocationMethod.MEASURED_USAGE,
            workload_ids=["w1", "w2"],
            shares=shares,
        )
        self.assertEqual(report.results[0].allocated_amount, Decimal("50.000000"))
        self.assertEqual(report.results[1].allocated_amount, Decimal("50.000000"))

    def test_one_zero_share(self):
        shares = [
            WorkloadShare(workload_id="w1", share_value=Decimal("100")),
            WorkloadShare(workload_id="w2", share_value=Decimal("0")),
        ]
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("100.00"),
            currency="USD",
            method=AllocationMethod.MEASURED_USAGE,
            workload_ids=["w1", "w2"],
            shares=shares,
        )
        self.assertEqual(report.results[0].allocated_amount, Decimal("100.000000"))
        self.assertEqual(report.results[1].allocated_amount, Decimal("0"))

    def test_manual_approved_weights(self):
        weights = {
            "w1": Decimal("0.6"),
            "w2": Decimal("0.3"),
            "w3": Decimal("0.1"),
        }
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("1000.00"),
            currency="USD",
            method=AllocationMethod.MANUAL_APPROVED,
            workload_ids=["w1", "w2", "w3"],
            custom_weights=weights,
        )
        self.assertEqual(report.results[0].allocated_amount, Decimal("600.000000"))
        self.assertEqual(report.results[1].allocated_amount, Decimal("300.000000"))
        self.assertEqual(report.results[2].allocated_amount, Decimal("100.000000"))
        self.assertEqual(report.allocated_total, Decimal("1000.000000"))


class TestAllocateCostValidation(unittest.TestCase):
    def test_negative_amount_rejected(self):
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="cost-1",
                total_amount=Decimal("-100"),
                currency="USD",
                method=AllocationMethod.EQUAL_SHARE,
                workload_ids=["w1"],
            )

    def test_invalid_currency_rejected(self):
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="cost-1",
                total_amount=Decimal("100"),
                currency="US",
                method=AllocationMethod.EQUAL_SHARE,
                workload_ids=["w1"],
            )

    def test_empty_workloads_rejected(self):
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="cost-1",
                total_amount=Decimal("100"),
                currency="USD",
                method=AllocationMethod.EQUAL_SHARE,
                workload_ids=[],
            )

    def test_duplicate_workloads_rejected(self):
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="cost-1",
                total_amount=Decimal("100"),
                currency="USD",
                method=AllocationMethod.EQUAL_SHARE,
                workload_ids=["w1", "w1"],
            )

    def test_missing_shares_rejected(self):
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="cost-1",
                total_amount=Decimal("100"),
                currency="USD",
                method=AllocationMethod.DIRECT_METER,
                workload_ids=["w1", "w2"],
            )

    def test_missing_custom_weights_rejected(self):
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="cost-1",
                total_amount=Decimal("100"),
                currency="USD",
                method=AllocationMethod.MANUAL_APPROVED,
                workload_ids=["w1", "w2"],
            )

    def test_shares_must_match_workloads(self):
        shares = [WorkloadShare(workload_id="w1", share_value=Decimal("100"))]
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="cost-1",
                total_amount=Decimal("100"),
                currency="USD",
                method=AllocationMethod.MEASURED_USAGE,
                workload_ids=["w1", "w2"],
                shares=shares,
            )

    def test_negative_share_rejected(self):
        shares = [
            WorkloadShare(workload_id="w1", share_value=Decimal("-1")),
            WorkloadShare(workload_id="w2", share_value=Decimal("1")),
        ]
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="cost-1",
                total_amount=Decimal("100"),
                currency="USD",
                method=AllocationMethod.MEASURED_USAGE,
                workload_ids=["w1", "w2"],
                shares=shares,
            )

    def test_zero_total_weight_rejected(self):
        weights = {"w1": Decimal("0"), "w2": Decimal("0")}
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="cost-1",
                total_amount=Decimal("100"),
                currency="USD",
                method=AllocationMethod.MANUAL_APPROVED,
                workload_ids=["w1", "w2"],
                custom_weights=weights,
            )


class TestAllocationReport(unittest.TestCase):
    def test_report_fields(self):
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("1000.00"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2"],
        )
        self.assertEqual(report.cost_actual_id, "cost-1")
        self.assertEqual(report.total_amount, Decimal("1000.00"))
        self.assertEqual(report.currency, "USD")
        self.assertEqual(report.method, "equal_share")
        self.assertEqual(report.method_version, METHOD_VERSION)
        self.assertIsNotNone(report.created_at)

    def test_validate_allocation_passes(self):
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("100.00"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2"],
        )
        self.assertTrue(validate_allocation(report))

    def test_allocation_hash_is_deterministic(self):
        report1 = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("100.00"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2"],
        )
        report2 = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("100.00"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2"],
        )
        hash1 = compute_allocation_hash(report1)
        hash2 = compute_allocation_hash(report2)
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)

    def test_allocation_hash_differs_for_different_inputs(self):
        report1 = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("100.00"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2"],
        )
        report2 = allocate_cost(
            cost_actual_id="cost-2",
            total_amount=Decimal("100.00"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2"],
        )
        self.assertNotEqual(compute_allocation_hash(report1), compute_allocation_hash(report2))


class TestAllocationRowsForInsert(unittest.TestCase):
    def test_rows_match_cost_allocations_schema(self):
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("100.00"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2"],
        )
        window_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        window_end = datetime(2026, 1, 31, tzinfo=timezone.utc)
        rows = allocation_rows_for_insert(report, window_start, window_end)
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertIn("cost_actual_id", row)
            self.assertIn("workload_id", row)
            self.assertIn("allocation_basis", row)
            self.assertIn("allocated_amount", row)
            self.assertIn("currency", row)
            self.assertIn("allocation_fraction", row)
            self.assertIn("window_start", row)
            self.assertIn("window_end", row)
            self.assertIn("method_version", row)
            self.assertIn("evidence", row)
            self.assertIn("allocation_hash", row["evidence"])


class TestSharesFromHelpers(unittest.TestCase):
    def test_shares_from_energy_allocations(self):
        rows = [
            {"workload_id": "w1", "energy_kwh": 1000, "allocation_method": "direct_meter", "coverage": 0.95},
            {"workload_id": "w2", "energy_kwh": 2000, "allocation_method": "direct_meter", "coverage": 0.90},
        ]
        shares = shares_from_energy_allocations(rows, datetime(2026, 1, 1), datetime(2026, 1, 31))
        self.assertEqual(len(shares), 2)
        self.assertEqual(shares[0].share_value, Decimal("1000"))
        self.assertEqual(shares[1].share_value, Decimal("2000"))

    def test_shares_from_energy_allocations_skips_zero(self):
        rows = [
            {"workload_id": "w1", "energy_kwh": 0},
            {"workload_id": "w2", "energy_kwh": 100},
        ]
        shares = shares_from_energy_allocations(rows, datetime(2026, 1, 1), datetime(2026, 1, 31))
        self.assertEqual(len(shares), 1)
        self.assertEqual(shares[0].workload_id, "w2")

    def test_shares_from_floor_areas(self):
        areas = {"w1": Decimal("500"), "w2": Decimal("300")}
        shares = shares_from_floor_areas(areas)
        self.assertEqual(len(shares), 2)
        self.assertEqual(shares[0].share_value, Decimal("500"))

    def test_shares_from_rack_units(self):
        racks = {"w1": Decimal("20"), "w2": Decimal("10")}
        shares = shares_from_rack_units(racks)
        self.assertEqual(len(shares), 2)

    def test_shares_from_headcount(self):
        hc = {"w1": Decimal("50"), "w2": Decimal("30")}
        shares = shares_from_headcount(hc)
        self.assertEqual(len(shares), 2)

    def test_shares_from_capacity(self):
        caps = {"w1": Decimal("100"), "w2": Decimal("200")}
        shares = shares_from_capacity(caps)
        self.assertEqual(len(shares), 2)


class TestBuildEvidence(unittest.TestCase):
    def test_build_evidence_structure(self):
        window_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        window_end = datetime(2026, 1, 31, tzinfo=timezone.utc)
        source = {"facility_id": "f1", "meter_id": "m1"}
        evidence = build_evidence(AllocationMethod.DIRECT_METER, window_start, window_end, source)
        self.assertEqual(evidence["method"], "direct_meter")
        self.assertEqual(evidence["method_version"], METHOD_VERSION)
        self.assertIn("window_start", evidence)
        self.assertIn("window_end", evidence)
        self.assertEqual(evidence["source_data"], source)
        self.assertIn("computed_at", evidence)


class TestAllocationMethodEnum(unittest.TestCase):
    def test_all_defined_methods_exist(self):
        expected = {
            "direct_meter", "measured_usage", "capacity_share",
            "floor_area", "rack_units", "headcount", "equal_share", "manual_approved",
        }
        actual = {m.value for m in AllocationMethod}
        self.assertEqual(actual, expected)

    def test_string_method_accepted(self):
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("100.00"),
            currency="USD",
            method="equal_share",
            workload_ids=["w1"],
        )
        self.assertEqual(report.method, "equal_share")


class TestLargeScaleAllocation(unittest.TestCase):
    def test_many_workloads(self):
        n = 100
        workload_ids = [f"w{i}" for i in range(n)]
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("10000.00"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=workload_ids,
        )
        self.assertEqual(len(report.results), n)
        self.assertEqual(report.allocated_total, Decimal("10000.000000"))
        self.assertTrue(report.reconciliation["fully_allocated"])

    def test_very_small_amounts(self):
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("0.01"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2"],
        )
        self.assertEqual(report.allocated_total, Decimal("0.010000"))
        self.assertTrue(report.reconciliation["fully_allocated"])

    def test_very_large_amounts(self):
        report = allocate_cost(
            cost_actual_id="cost-1",
            total_amount=Decimal("999999999.99"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2"],
        )
        self.assertEqual(report.allocated_total, Decimal("999999999.990000"))
        self.assertTrue(report.reconciliation["fully_allocated"])


if __name__ == "__main__":
    unittest.main()
