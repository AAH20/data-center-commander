"""Unit tests for dcc.economics.allocation module."""
import unittest
from dataclasses import replace
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

WINDOW_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2024, 2, 1, tzinfo=timezone.utc)


def _results() -> list[AllocationResult]:
    return [
        AllocationResult(
            workload_id="w1",
            allocated_amount=Decimal("60.0"),
            allocation_fraction=Decimal("0.6"),
            basis="measured_share",
        ),
        AllocationResult(
            workload_id="w2",
            allocated_amount=Decimal("40.0"),
            allocation_fraction=Decimal("0.4"),
            basis="measured_share",
        ),
    ]


def _report(
    total_amount: Decimal = Decimal("100.0"),
    allocated_total: Decimal = Decimal("100.0"),
    unallocated_amount: Decimal = Decimal("0"),
    results: list[AllocationResult] | None = None,
) -> AllocationReport:
    """Build a minimal valid AllocationReport for tests."""
    return AllocationReport(
        cost_actual_id="c1",
        total_amount=total_amount,
        allocated_total=allocated_total,
        unallocated_amount=unallocated_amount,
        currency="USD",
        method="direct_meter",
        method_version=METHOD_VERSION,
        results=_results() if results is None else results,
        reconciliation={"fully_allocated": unallocated_amount == 0},
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
        self.assertEqual(ws.evidence, {})

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
        self.assertEqual(r.evidence, {})

    def test_with_evidence(self):
        r = AllocationResult(
            workload_id="w1",
            allocated_amount=Decimal("50.0"),
            allocation_fraction=Decimal("0.5"),
            basis="direct_meter",
            evidence={"share_value": "50"},
        )
        self.assertEqual(r.evidence["share_value"], "50")


class TestAllocationReport(unittest.TestCase):
    def test_creation(self):
        r = _report()
        self.assertEqual(r.cost_actual_id, "c1")
        self.assertEqual(r.currency, "USD")
        self.assertEqual(r.method_version, METHOD_VERSION)
        self.assertIsInstance(r.created_at, datetime)
        self.assertEqual(len(r.results), 2)

    def test_reconciliation_payload(self):
        r = _report()
        self.assertTrue(r.reconciliation["fully_allocated"])


class TestAllocateCost(unittest.TestCase):
    def test_allocate(self):
        shares = [
            WorkloadShare(workload_id="w1", share_value=Decimal("60.0")),
            WorkloadShare(workload_id="w2", share_value=Decimal("40.0")),
        ]
        result = allocate_cost(
            cost_actual_id="c1",
            total_amount=Decimal("100.0"),
            currency="USD",
            method=AllocationMethod.DIRECT_METER,
            workload_ids=["w1", "w2"],
            shares=shares,
        )
        self.assertIsInstance(result, AllocationReport)
        self.assertEqual(len(result.results), 2)
        self.assertEqual(result.method, "direct_meter")
        self.assertEqual(result.allocated_total, Decimal("100.0"))
        self.assertEqual(result.unallocated_amount, Decimal("0"))
        self.assertTrue(result.reconciliation["fully_allocated"])
        by_id = {r.workload_id: r for r in result.results}
        self.assertEqual(by_id["w1"].allocated_amount, Decimal("60.0"))
        self.assertEqual(by_id["w2"].allocated_amount, Decimal("40.0"))

    def test_equal_share(self):
        result = allocate_cost(
            cost_actual_id="c1",
            total_amount=Decimal("100.0"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2", "w3"],
        )
        self.assertIsInstance(result, AllocationReport)
        self.assertEqual(len(result.results), 3)
        # Largest-remainder adjustment keeps the total exact.
        self.assertEqual(result.allocated_total, Decimal("100.0"))
        self.assertEqual(result.unallocated_amount, Decimal("0"))

    def test_manual_approved_weights(self):
        result = allocate_cost(
            cost_actual_id="c1",
            total_amount=Decimal("100.0"),
            currency="USD",
            method=AllocationMethod.MANUAL_APPROVED,
            workload_ids=["w1", "w2"],
            custom_weights={"w1": Decimal("1"), "w2": Decimal("3")},
        )
        by_id = {r.workload_id: r for r in result.results}
        self.assertEqual(by_id["w2"].allocated_amount, Decimal("75.0"))
        self.assertEqual(by_id["w1"].allocated_amount, Decimal("25.0"))

    def test_shares_required_without_method(self):
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="c1",
                total_amount=Decimal("100.0"),
                currency="USD",
                method=AllocationMethod.DIRECT_METER,
                workload_ids=["w1"],
            )

    def test_shares_must_cover_workloads(self):
        shares = [WorkloadShare(workload_id="w1", share_value=Decimal("1"))]
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="c1",
                total_amount=Decimal("100.0"),
                currency="USD",
                method=AllocationMethod.DIRECT_METER,
                workload_ids=["w1", "w2"],
                shares=shares,
            )


class TestBuildEvidence(unittest.TestCase):
    def test_build(self):
        evidence = build_evidence(
            method=AllocationMethod.DIRECT_METER,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            source_data={"row_count": 2},
        )
        self.assertIsInstance(evidence, dict)
        self.assertEqual(evidence["method"], "direct_meter")
        self.assertEqual(evidence["method_version"], METHOD_VERSION)
        self.assertEqual(evidence["window_start"], WINDOW_START.isoformat())
        self.assertEqual(evidence["source_data"]["row_count"], 2)


class TestComputeAllocationHash(unittest.TestCase):
    def test_hash(self):
        h = compute_allocation_hash(_report())
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    def test_hash_is_deterministic(self):
        self.assertEqual(compute_allocation_hash(_report()), compute_allocation_hash(_report()))

    def test_hash_changes_with_amounts(self):
        base = compute_allocation_hash(_report())
        changed = compute_allocation_hash(_report(total_amount=Decimal("101.0")))
        self.assertNotEqual(base, changed)


class TestValidateAllocation(unittest.TestCase):
    def test_validate(self):
        self.assertIs(validate_allocation(_report()), True)

    def test_validate_detects_short_allocation(self):
        report = _report(
            results=[
                AllocationResult(
                    workload_id="w1",
                    allocated_amount=Decimal("60.0"),
                    allocation_fraction=Decimal("1"),
                    basis="measured_share",
                ),
            ],
            allocated_total=Decimal("60.0"),
            unallocated_amount=Decimal("40.0"),
        )
        self.assertIs(validate_allocation(report), False)


class TestAllocationRowsForInsert(unittest.TestCase):
    def test_rows(self):
        report = _report()
        rows = allocation_rows_for_insert(report, WINDOW_START, WINDOW_END)
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 2)
        row = rows[0]
        self.assertEqual(row["cost_actual_id"], "c1")
        self.assertEqual(row["currency"], "USD")
        self.assertEqual(row["allocation_basis"], "direct_meter")
        self.assertEqual(row["method_version"], METHOD_VERSION)
        self.assertEqual(row["window_start"], WINDOW_START)
        self.assertEqual(row["window_end"], WINDOW_END)
        self.assertEqual(row["evidence"]["allocation_hash"], compute_allocation_hash(report))


class TestSharesFromEnergyAllocations(unittest.TestCase):
    def test_shares(self):
        allocations = [
            {"workload_id": "w1", "energy_kwh": 60.0, "allocation_method": "metered"},
            {"workload_id": "w2", "energy_kwh": 40.0, "allocation_method": "metered"},
        ]
        shares = shares_from_energy_allocations(allocations, WINDOW_START, WINDOW_END)
        self.assertIsInstance(shares, list)
        self.assertEqual(len(shares), 2)
        self.assertEqual(shares[0].share_value, Decimal("60.0"))
        self.assertEqual(shares[0].evidence["source"], "energy_allocations")
        self.assertEqual(shares[0].evidence["window_start"], WINDOW_START.isoformat())

    def test_skips_missing_or_non_positive(self):
        allocations = [
            {"workload_id": "w1", "energy_kwh": 10.0},
            {"workload_id": "w2", "energy_kwh": 0},
            {"workload_id": None, "energy_kwh": 5.0},
            {"workload_id": "w3"},
        ]
        shares = shares_from_energy_allocations(allocations, WINDOW_START, WINDOW_END)
        self.assertEqual([s.workload_id for s in shares], ["w1"])


class TestSharesFromFloorAreas(unittest.TestCase):
    def test_shares(self):
        spaces = {"w1": Decimal("100.0"), "w2": Decimal("200.0")}
        shares = shares_from_floor_areas(spaces)
        self.assertIsInstance(shares, list)
        self.assertEqual(len(shares), 2)
        self.assertEqual(shares[0].evidence["source"], "spaces.floor_area_m2")

    def test_skips_non_positive(self):
        shares = shares_from_floor_areas({"w1": Decimal("100.0"), "w2": Decimal("0")})
        self.assertEqual([s.workload_id for s in shares], ["w1"])


class TestSharesFromRackUnits(unittest.TestCase):
    def test_shares(self):
        spaces = {"w1": Decimal("10"), "w2": Decimal("20")}
        shares = shares_from_rack_units(spaces)
        self.assertIsInstance(shares, list)
        self.assertEqual(len(shares), 2)
        self.assertEqual(shares[1].share_value, Decimal("20"))


class TestSharesFromHeadcount(unittest.TestCase):
    def test_shares(self):
        workloads = {"w1": Decimal("5"), "w2": Decimal("10")}
        shares = shares_from_headcount(workloads)
        self.assertIsInstance(shares, list)
        self.assertEqual(len(shares), 2)
        self.assertEqual(shares[0].evidence["source"], "headcount")


class TestSharesFromCapacity(unittest.TestCase):
    def test_shares(self):
        snapshots = {"w1": Decimal("100.0"), "w2": Decimal("200.0")}
        shares = shares_from_capacity(snapshots)
        self.assertIsInstance(shares, list)
        self.assertEqual(len(shares), 2)
        self.assertEqual(shares[1].evidence["source"], "capacity_snapshots")


class TestAllocationPrecision(unittest.TestCase):
    def test_precision_constant(self):
        self.assertEqual(ALLOCATION_PRECISION, Decimal("0.000001"))

    def test_rounding_residual_is_absorbed(self):
        # 100 / 3 has a repeating remainder; the engine must still balance exactly.
        result = allocate_cost(
            cost_actual_id="c1",
            total_amount=Decimal("100"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2", "w3"],
        )
        self.assertEqual(sum(r.allocated_amount for r in result.results), Decimal("100"))


if __name__ == "__main__":
    unittest.main()
