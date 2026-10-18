"""Unit tests for dcc.economics.allocation module."""
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from dcc.economics.allocation import (
    AllocationMethod,
    WorkloadShare,
    AllocationResult,
    AllocationReport,
    METHOD_VERSION,
    ALLOCATION_PRECISION,
    allocate_cost,
    build_evidence,
    compute_allocation_hash,
    validate_allocation,
    allocation_rows_for_insert,
    shares_from_energy_allocations,
    shares_from_floor_areas,
    shares_from_rack_units,
    shares_from_headcount,
    shares_from_capacity,
)


class TestAllocationMethod(unittest.TestCase):
    def test_method_values(self):
        self.assertEqual(AllocationMethod.DIRECT_METER.value, "direct_meter")
        self.assertEqual(AllocationMethod.MEASURED_USAGE.value, "measured_usage")
        self.assertEqual(AllocationMethod.CAPACITY_SHARE.value, "capacity_share")
        self.assertEqual(AllocationMethod.FLOOR_AREA.value, "floor_area")
        self.assertEqual(AllocationMethod.RACK_UNITS.value, "rack_units")
        self.assertEqual(AllocationMethod.HEADCOUNT.value, "headcount")
        self.assertEqual(AllocationMethod.EQUAL_SHARE.value, "equal_share")
        self.assertEqual(AllocationMethod.MANUAL_APPROVED.value, "manual_approved")


class TestWorkloadShare(unittest.TestCase):
    def test_creation(self):
        ws = WorkloadShare(
            workload_id="w1",
            share_value=Decimal("100.0"),
        )
        self.assertEqual(ws.workload_id, "w1")
        self.assertEqual(ws.share_value, Decimal("100.0"))

    def test_with_evidence(self):
        ws = WorkloadShare(
            workload_id="w1",
            share_value=Decimal("100.0"),
            evidence={"meter_id": "m1"},
        )
        self.assertEqual(ws.evidence["meter_id"], "m1")


class TestAllocationResult(unittest.TestCase):
    def test_creation(self):
        r = AllocationResult(
            workload_id="w1",
            allocated_amount=Decimal("50.0"),
            allocation_fraction=Decimal("0.5"),
            basis="direct_meter",
        )
        self.assertEqual(r.workload_id, "w1")
        self.assertEqual(r.allocated_amount, Decimal("50.0"))


class TestAllocationReport(unittest.TestCase):
    def test_creation(self):
        r = AllocationReport(
            cost_actual_id="c1",
            total_amount=Decimal("100.0"),
            allocated_total=Decimal("100.0"),
            unallocated_amount=Decimal("0"),
            currency="USD",
            method="direct_meter",
            method_version=METHOD_VERSION,
            results=[],
        )
        self.assertEqual(r.cost_actual_id, "c1")
        self.assertEqual(r.currency, "USD")


class TestAllocateCost(unittest.TestCase):
    def test_allocate(self):
        shares = [
            WorkloadShare(workload_id="w1", share_value=Decimal("60.0")),
            WorkloadShare(workload_id="w2", share_value=Decimal("40.0")),
        ]
        result = allocate_cost(
            total_amount=Decimal("100.0"),
            currency="USD",
            workload_ids=["w1", "w2"],
            shares=shares,
        )
        self.assertIsInstance(result, AllocationReport)
        self.assertEqual(len(result.results), 2)

    def test_equal_share(self):
        result = allocate_cost(
            total_amount=Decimal("100.0"),
            currency="USD",
            workload_ids=["w1", "w2", "w3"],
        )
        self.assertIsInstance(result, AllocationReport)
        self.assertEqual(len(result.results), 3)


class TestBuildEvidence(unittest.TestCase):
    def test_build(self):
        evidence = build_evidence(
            workload_id="w1",
            share_value=Decimal("100.0"),
            method="direct_meter",
        )
        self.assertIsInstance(evidence, dict)


class TestComputeAllocationHash(unittest.TestCase):
    def test_hash(self):
        h = compute_allocation_hash(
            cost_actual_id="c1",
            workload_id="w1",
            amount=Decimal("50.0"),
        )
        self.assertIsInstance(h, str)
        self.assertGreater(len(h), 0)


class TestValidateAllocation(unittest.TestCase):
    def test_validate(self):
        result = validate_allocation(
            total_amount=Decimal("100.0"),
            allocated_total=Decimal("100.0"),
        )
        self.assertIsInstance(result, bool)


class TestAllocationRowsForInsert(unittest.TestCase):
    def test_rows(self):
        report = AllocationReport(
            cost_actual_id="c1",
            total_amount=Decimal("100.0"),
            allocated_total=Decimal("100.0"),
            unallocated_amount=Decimal("0"),
            currency="USD",
            method="direct_meter",
            method_version=METHOD_VERSION,
            results=[
                AllocationResult(
                    workload_id="w1",
                    allocated_amount=Decimal("50.0"),
                    allocation_fraction=Decimal("0.5"),
                    basis="direct_meter",
                ),
            ],
        )
        rows = allocation_rows_for_insert(report)
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)


class TestSharesFromEnergyAllocations(unittest.TestCase):
    def test_shares(self):
        allocations = [
            {"workload_id": "w1", "energy_kwh": 60.0},
            {"workload_id": "w2", "energy_kwh": 40.0},
        ]
        shares = shares_from_energy_allocations(allocations)
        self.assertIsInstance(shares, list)
        self.assertEqual(len(shares), 2)


class TestSharesFromFloorAreas(unittest.TestCase):
    def test_shares(self):
        spaces = [
            {"workload_id": "w1", "floor_area_m2": 100.0},
            {"workload_id": "w2", "floor_area_m2": 200.0},
        ]
        shares = shares_from_floor_areas(spaces)
        self.assertIsInstance(shares, list)


class TestSharesFromRackUnits(unittest.TestCase):
    def test_shares(self):
        spaces = [
            {"workload_id": "w1", "rack_units": 10},
            {"workload_id": "w2", "rack_units": 20},
        ]
        shares = shares_from_rack_units(spaces)
        self.assertIsInstance(shares, list)


class TestSharesFromHeadcount(unittest.TestCase):
    def test_shares(self):
        workloads = [
            {"workload_id": "w1", "headcount": 5},
            {"workload_id": "w2", "headcount": 10},
        ]
        shares = shares_from_headcount(workloads)
        self.assertIsInstance(shares, list)


class TestSharesFromCapacity(unittest.TestCase):
    def test_shares(self):
        snapshots = [
            {"workload_id": "w1", "capacity": 100.0},
            {"workload_id": "w2", "capacity": 200.0},
        ]
        shares = shares_from_capacity(snapshots)
        self.assertIsInstance(shares, list)


if __name__ == "__main__":
    unittest.main()
