"""Integration tests for economics modules.

Tests cost estimation, TCO, pricing, tariffs, reconciliation,
budget forecasting, unit economics, allocation, and scenarios.
"""
from __future__ import annotations

import unittest
from decimal import Decimal


class TestUnitEconomicsIntegration(unittest.TestCase):
    """Integration tests for unit economics calculations."""

    def test_equivalent_annual_cost_zero_rate(self):
        from dcc.economics.unit import equivalent_annual_cost
        result = equivalent_annual_cost(100000, 10, 0.0)
        self.assertAlmostEqual(result, 10000.0)

    def test_equivalent_annual_cost_with_rate(self):
        from dcc.economics.unit import equivalent_annual_cost
        result = equivalent_annual_cost(100000, 10, 0.08)
        self.assertGreater(result, 10000.0)

    def test_equivalent_annual_cost_rejects_negative_pv(self):
        from dcc.economics.unit import equivalent_annual_cost
        with self.assertRaises(ValueError):
            equivalent_annual_cost(-1, 10, 0.0)

    def test_equivalent_annual_cost_rejects_zero_years(self):
        from dcc.economics.unit import equivalent_annual_cost
        with self.assertRaises(ValueError):
            equivalent_annual_cost(100000, 0, 0.0)

    def test_equivalent_annual_cost_rejects_invalid_rate(self):
        from dcc.economics.unit import equivalent_annual_cost
        with self.assertRaises(ValueError):
            equivalent_annual_cost(100000, 10, 1.0)

    def test_cost_per_kw_year(self):
        from dcc.economics.unit import cost_per_kw_year
        result = cost_per_kw_year(120000, 100)
        self.assertEqual(result.value, 1200.0)
        self.assertEqual(result.status, "ok")

    def test_cost_per_kw_year_rejects_zero_capacity(self):
        from dcc.economics.unit import cost_per_kw_year
        result = cost_per_kw_year(120000, 0)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "unknown")

    def test_cost_per_rack_year(self):
        from dcc.economics.unit import cost_per_rack_year
        result = cost_per_rack_year(50000, 50)
        self.assertEqual(result.value, 1000.0)

    def test_cost_per_m2_year(self):
        from dcc.economics.unit import cost_per_m2_year
        result = cost_per_m2_year(200000, 1000)
        self.assertEqual(result.value, 200.0)

    def test_cost_per_kwh_it_boundary(self):
        from dcc.economics.unit import cost_per_kwh
        result = cost_per_kwh(10000, 50000)
        self.assertEqual(result["it_boundary"].value, 0.2)

    def test_cost_per_kwh_facility_boundary(self):
        from dcc.economics.unit import cost_per_kwh
        result = cost_per_kwh(10000, 50000, 100000)
        self.assertEqual(result["facility_boundary"].value, 0.1)

    def test_cost_per_work_unit(self):
        from dcc.economics.unit import cost_per_work_unit
        result = cost_per_work_unit(50000, 10000)
        self.assertEqual(result.value, 5.0)

    def test_compute_all_unit_economics(self):
        from dcc.economics.unit import compute_all_unit_economics
        result = compute_all_unit_economics(
            present_value=1000000,
            years=10,
            discount_rate=0.08,
            it_capacity_kw=100,
            rack_count=50,
            area_m2=1000,
            energy_cost=50000,
            it_energy_kwh=500000,
        )
        self.assertIn("eac", result)
        self.assertIn("cost_per_kw", result)
        self.assertIn("cost_per_rack", result)
        self.assertIn("cost_per_m2", result)
        self.assertIn("cost_per_kwh", result)

    def test_not_priced_sentinel(self):
        from dcc.economics.unit import NOT_PRICED, UNKNOWN
        self.assertEqual(NOT_PRICED, "Not priced")
        self.assertEqual(UNKNOWN, "Unknown")


class TestAllocationIntegration(unittest.TestCase):
    """Integration tests for cost allocation."""

    def test_allocate_equal_share(self):
        from dcc.economics.allocation import allocate_cost, AllocationMethod
        report = allocate_cost(
            cost_actual_id="ca1",
            total_amount=Decimal("1000"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2", "w3"],
        )
        self.assertEqual(report.total_amount, Decimal("1000"))
        self.assertEqual(len(report.results), 3)
        self.assertEqual(report.reconciliation["fully_allocated"], True)

    def test_allocate_by_direct_meter(self):
        from dcc.economics.allocation import allocate_cost, AllocationMethod, WorkloadShare
        report = allocate_cost(
            cost_actual_id="ca1",
            total_amount=Decimal("1000"),
            currency="USD",
            method=AllocationMethod.DIRECT_METER,
            workload_ids=["w1", "w2"],
            shares=[
                WorkloadShare(workload_id="w1", share_value=Decimal("300")),
                WorkloadShare(workload_id="w2", share_value=Decimal("700")),
            ],
        )
        self.assertEqual(report.total_amount, Decimal("1000"))
        self.assertEqual(len(report.results), 2)

    def test_allocate_manual_approved(self):
        from dcc.economics.allocation import allocate_cost, AllocationMethod
        report = allocate_cost(
            cost_actual_id="ca1",
            total_amount=Decimal("1000"),
            currency="USD",
            method=AllocationMethod.MANUAL_APPROVED,
            workload_ids=["w1", "w2"],
            custom_weights={"w1": Decimal("400"), "w2": Decimal("600")},
        )
        self.assertEqual(report.total_amount, Decimal("1000"))

    def test_allocate_rejects_negative_amount(self):
        from dcc.economics.allocation import allocate_cost, AllocationMethod
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="ca1",
                total_amount=Decimal("-100"),
                currency="USD",
                method=AllocationMethod.EQUAL_SHARE,
                workload_ids=["w1"],
            )

    def test_allocate_rejects_invalid_currency(self):
        from dcc.economics.allocation import allocate_cost, AllocationMethod
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="ca1",
                total_amount=Decimal("100"),
                currency="US",
                method=AllocationMethod.EQUAL_SHARE,
                workload_ids=["w1"],
            )

    def test_allocate_rejects_empty_workloads(self):
        from dcc.economics.allocation import allocate_cost, AllocationMethod
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="ca1",
                total_amount=Decimal("100"),
                currency="USD",
                method=AllocationMethod.EQUAL_SHARE,
                workload_ids=[],
            )

    def test_allocate_rejects_duplicate_workloads(self):
        from dcc.economics.allocation import allocate_cost, AllocationMethod
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="ca1",
                total_amount=Decimal("100"),
                currency="USD",
                method=AllocationMethod.EQUAL_SHARE,
                workload_ids=["w1", "w1"],
            )

    def test_allocate_rejects_missing_shares(self):
        from dcc.economics.allocation import allocate_cost, AllocationMethod
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="ca1",
                total_amount=Decimal("100"),
                currency="USD",
                method=AllocationMethod.DIRECT_METER,
                workload_ids=["w1"],
            )

    def test_allocate_rejects_incomplete_shares(self):
        from dcc.economics.allocation import allocate_cost, AllocationMethod, WorkloadShare
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="ca1",
                total_amount=Decimal("100"),
                currency="USD",
                method=AllocationMethod.DIRECT_METER,
                workload_ids=["w1", "w2"],
                shares=[WorkloadShare(workload_id="w1", share_value=Decimal("100"))],
            )

    def test_allocate_rejects_negative_share(self):
        from dcc.economics.allocation import allocate_cost, AllocationMethod, WorkloadShare
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="ca1",
                total_amount=Decimal("100"),
                currency="USD",
                method=AllocationMethod.DIRECT_METER,
                workload_ids=["w1"],
                shares=[WorkloadShare(workload_id="w1", share_value=Decimal("-1"))],
            )

    def test_allocate_rejects_zero_total_weight(self):
        from dcc.economics.allocation import allocate_cost, AllocationMethod
        with self.assertRaises(ValueError):
            allocate_cost(
                cost_actual_id="ca1",
                total_amount=Decimal("100"),
                currency="USD",
                method=AllocationMethod.MANUAL_APPROVED,
                workload_ids=["w1"],
                custom_weights={"w1": Decimal("0")},
            )

    def test_compute_allocation_hash(self):
        from dcc.economics.allocation import allocate_cost, AllocationMethod, compute_allocation_hash
        report = allocate_cost(
            cost_actual_id="ca1",
            total_amount=Decimal("1000"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2"],
        )
        hash1 = compute_allocation_hash(report)
        hash2 = compute_allocation_hash(report)
        self.assertEqual(hash1, hash2)

    def test_validate_allocation(self):
        from dcc.economics.allocation import allocate_cost, AllocationMethod, validate_allocation
        report = allocate_cost(
            cost_actual_id="ca1",
            total_amount=Decimal("1000"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2"],
        )
        self.assertTrue(validate_allocation(report))

    def test_allocation_rows_for_insert(self):
        from dcc.economics.allocation import allocate_cost, AllocationMethod, allocation_rows_for_insert
        from datetime import datetime, timezone
        report = allocate_cost(
            cost_actual_id="ca1",
            total_amount=Decimal("1000"),
            currency="USD",
            method=AllocationMethod.EQUAL_SHARE,
            workload_ids=["w1", "w2"],
        )
        rows = allocation_rows_for_insert(
            report,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 31, tzinfo=timezone.utc),
        )
        self.assertEqual(len(rows), 2)
        self.assertIn("allocation_hash", rows[0]["evidence"])

    def test_shares_from_energy_allocations(self):
        from dcc.economics.allocation import shares_from_energy_allocations
        from datetime import datetime, timezone
        rows = [
            {"workload_id": "w1", "energy_kwh": 100, "allocation_method": "direct_meter", "coverage": 0.9},
            {"workload_id": "w2", "energy_kwh": 200, "allocation_method": "direct_meter", "coverage": 0.8},
        ]
        shares = shares_from_energy_allocations(
            rows,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 31, tzinfo=timezone.utc),
        )
        self.assertEqual(len(shares), 2)

    def test_shares_from_floor_areas(self):
        from dcc.economics.allocation import shares_from_floor_areas
        shares = shares_from_floor_areas({"w1": Decimal("100"), "w2": Decimal("200")})
        self.assertEqual(len(shares), 2)

    def test_shares_from_rack_units(self):
        from dcc.economics.allocation import shares_from_rack_units
        shares = shares_from_rack_units({"w1": Decimal("10"), "w2": Decimal("20")})
        self.assertEqual(len(shares), 2)

    def test_shares_from_headcount(self):
        from dcc.economics.allocation import shares_from_headcount
        shares = shares_from_headcount({"w1": Decimal("5"), "w2": Decimal("10")})
        self.assertEqual(len(shares), 2)

    def test_shares_from_capacity(self):
        from dcc.economics.allocation import shares_from_capacity
        shares = shares_from_capacity({"w1": Decimal("50"), "w2": Decimal("100")})
        self.assertEqual(len(shares), 2)

    def test_build_evidence(self):
        from dcc.economics.allocation import build_evidence, AllocationMethod
        from datetime import datetime, timezone
        evidence = build_evidence(
            AllocationMethod.EQUAL_SHARE,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 31, tzinfo=timezone.utc),
            {"source": "test"},
        )
        self.assertEqual(evidence["method"], "equal_share")
        self.assertIn("window_start", evidence)


class TestBudgetIntegration(unittest.TestCase):
    """Integration tests for budget forecasting."""

    def test_forecast_budget_one_time(self):
        from dcc.economics.budget import forecast_budget
        result = forecast_budget(
            line_items=[{
                "line_id": "l1", "description": "Server", "phase": "it_equipment",
                "cost_behavior": "one_time", "quantity": 10, "base_unit_cost": 1000,
            }],
            horizon_months=12,
        )
        self.assertEqual(result["horizon_months"], 12)
        self.assertIn("total_base", result)
        self.assertIn("monthly_budgets", result)

    def test_forecast_budget_fixed_recurring(self):
        from dcc.economics.budget import forecast_budget
        result = forecast_budget(
            line_items=[{
                "line_id": "l1", "description": "Maintenance", "phase": "maintenance",
                "cost_behavior": "fixed_recurring", "quantity": 1, "base_unit_cost": 100,
                "recurrence_months": 12,
            }],
            horizon_months=24,
        )
        self.assertEqual(result["horizon_months"], 24)

    def test_forecast_budget_variable(self):
        from dcc.economics.budget import forecast_budget
        result = forecast_budget(
            line_items=[{
                "line_id": "l1", "description": "Energy", "phase": "energy",
                "cost_behavior": "variable", "quantity": 1000, "base_unit_cost": 0.1,
                "recurrence_months": 1,
            }],
            horizon_months=12,
        )
        self.assertEqual(result["horizon_months"], 12)

    def test_forecast_budget_step_fixed(self):
        from dcc.economics.budget import forecast_budget
        result = forecast_budget(
            line_items=[{
                "line_id": "l1", "description": "License", "phase": "software",
                "cost_behavior": "step_fixed", "quantity": 1, "base_unit_cost": 5000,
                "recurrence_months": 6,
            }],
            horizon_months=12,
        )
        self.assertEqual(result["horizon_months"], 12)

    def test_forecast_budget_capitalized(self):
        from dcc.economics.budget import forecast_budget
        result = forecast_budget(
            line_items=[{
                "line_id": "l1", "description": "Hardware", "phase": "it_equipment",
                "cost_behavior": "capitalized", "quantity": 1, "base_unit_cost": 10000,
            }],
            horizon_months=12,
        )
        self.assertEqual(result["horizon_months"], 12)

    def test_forecast_budget_with_growth_plan(self):
        from dcc.economics.budget import forecast_budget
        result = forecast_budget(
            line_items=[{
                "line_id": "l1", "description": "Energy", "phase": "energy",
                "cost_behavior": "variable", "quantity": 1000, "base_unit_cost": 0.1,
                "recurrence_months": 1,
            }],
            horizon_months=12,
            growth_plan={"monthly_capacity_growth": 0.02},
        )
        self.assertEqual(result["horizon_months"], 12)

    def test_forecast_budget_with_contingency(self):
        from dcc.economics.budget import forecast_budget
        result = forecast_budget(
            line_items=[{
                "line_id": "l1", "description": "Server", "phase": "it_equipment",
                "cost_behavior": "one_time", "quantity": 10, "base_unit_cost": 1000,
            }],
            horizon_months=12,
            contingency_pct=0.1,
        )
        self.assertEqual(result["horizon_months"], 12)

    def test_forecast_budget_rejects_invalid_horizon(self):
        from dcc.economics.budget import forecast_budget
        with self.assertRaises(ValueError):
            forecast_budget(line_items=[], horizon_months=0)

    def test_forecast_budget_rejects_horizon_over_600(self):
        from dcc.economics.budget import forecast_budget
        with self.assertRaises(ValueError):
            forecast_budget(line_items=[], horizon_months=601)

    def test_forecast_budget_rejects_invalid_discount_rate(self):
        from dcc.economics.budget import forecast_budget
        with self.assertRaises(ValueError):
            forecast_budget(line_items=[], horizon_months=12, discount_rate=1.0)

    def test_forecast_budget_rejects_invalid_contingency(self):
        from dcc.economics.budget import forecast_budget
        with self.assertRaises(ValueError):
            forecast_budget(line_items=[], horizon_months=12, contingency_pct=1.5)

    def test_forecast_budget_rejects_missing_line_id(self):
        from dcc.economics.budget import forecast_budget
        with self.assertRaises(ValueError):
            forecast_budget(
                line_items=[{"description": "Test", "phase": "energy", "cost_behavior": "one_time", "quantity": 1, "base_unit_cost": 100}],
                horizon_months=12,
            )

    def test_forecast_budget_rejects_invalid_cost_behavior(self):
        from dcc.economics.budget import forecast_budget
        with self.assertRaises(ValueError):
            forecast_budget(
                line_items=[{"line_id": "l1", "description": "Test", "phase": "energy", "cost_behavior": "invalid", "quantity": 1, "base_unit_cost": 100}],
                horizon_months=12,
            )

    def test_forecast_budget_rejects_negative_quantity(self):
        from dcc.economics.budget import forecast_budget
        with self.assertRaises(ValueError):
            forecast_budget(
                line_items=[{"line_id": "l1", "description": "Test", "phase": "energy", "cost_behavior": "one_time", "quantity": -1, "base_unit_cost": 100}],
                horizon_months=12,
            )

    def test_forecast_budget_rejects_low_above_base(self):
        from dcc.economics.budget import forecast_budget
        with self.assertRaises(ValueError):
            forecast_budget(
                line_items=[{"line_id": "l1", "description": "Test", "phase": "energy", "cost_behavior": "one_time", "quantity": 1, "base_unit_cost": 100, "low_unit_cost": 200}],
                horizon_months=12,
            )

    def test_forecast_budget_rejects_high_below_base(self):
        from dcc.economics.budget import forecast_budget
        with self.assertRaises(ValueError):
            forecast_budget(
                line_items=[{"line_id": "l1", "description": "Test", "phase": "energy", "cost_behavior": "one_time", "quantity": 1, "base_unit_cost": 100, "high_unit_cost": 50}],
                horizon_months=12,
            )

    def test_forecast_budget_rejects_recurring_without_recurrence(self):
        from dcc.economics.budget import forecast_budget
        with self.assertRaises(ValueError):
            forecast_budget(
                line_items=[{"line_id": "l1", "description": "Test", "phase": "energy", "cost_behavior": "fixed_recurring", "quantity": 1, "base_unit_cost": 100}],
                horizon_months=12,
            )

    def test_forecast_budget_rejects_negative_waste_factor(self):
        from dcc.economics.budget import forecast_budget
        with self.assertRaises(ValueError):
            forecast_budget(
                line_items=[{"line_id": "l1", "description": "Test", "phase": "energy", "cost_behavior": "one_time", "quantity": 1, "base_unit_cost": 100, "waste_factor": -0.1}],
                horizon_months=12,
            )

    def test_forecast_budget_rejects_waste_factor_over_1(self):
        from dcc.economics.budget import forecast_budget
        with self.assertRaises(ValueError):
            forecast_budget(
                line_items=[{"line_id": "l1", "description": "Test", "phase": "energy", "cost_behavior": "one_time", "quantity": 1, "base_unit_cost": 100, "waste_factor": 1.1}],
                horizon_months=12,
            )

    def test_forecast_budget_rejects_negative_start_month(self):
        from dcc.economics.budget import forecast_budget
        with self.assertRaises(ValueError):
            forecast_budget(
                line_items=[{"line_id": "l1", "description": "Test", "phase": "energy", "cost_behavior": "one_time", "quantity": 1, "base_unit_cost": 100, "start_month": -1}],
                horizon_months=12,
            )

    def test_forecast_budget_rejects_negative_useful_life(self):
        from dcc.economics.budget import forecast_budget
        with self.assertRaises(ValueError):
            forecast_budget(
                line_items=[{"line_id": "l1", "description": "Test", "phase": "energy", "cost_behavior": "one_time", "quantity": 1, "base_unit_cost": 100, "useful_life_months": -1}],
                horizon_months=12,
            )

    def test_forecast_budget_annual_totals(self):
        from dcc.economics.budget import forecast_budget
        result = forecast_budget(
            line_items=[{
                "line_id": "l1", "description": "Server", "phase": "it_equipment",
                "cost_behavior": "one_time", "quantity": 10, "base_unit_cost": 1000,
            }],
            horizon_months=24,
        )
        self.assertIn("annual_totals", result)
        self.assertGreaterEqual(len(result["annual_totals"]), 1)

    def test_forecast_budget_phase_totals(self):
        from dcc.economics.budget import forecast_budget
        result = forecast_budget(
            line_items=[
                {"line_id": "l1", "description": "Server", "phase": "it_equipment", "cost_behavior": "one_time", "quantity": 10, "base_unit_cost": 1000},
                {"line_id": "l2", "description": "Energy", "phase": "energy", "cost_behavior": "one_time", "quantity": 100, "base_unit_cost": 0.1},
            ],
            horizon_months=12,
        )
        self.assertIn("phase_totals", result)
        self.assertIn("it_equipment", result["phase_totals"])
        self.assertIn("energy", result["phase_totals"])

    def test_forecast_from_estimate(self):
        from dcc.economics.budget import forecast_from_estimate
        result = forecast_from_estimate(
            estimate_id="est1",
            line_items=[{
                "line_id": "l1", "description": "Server", "phase": "it_equipment",
                "cost_behavior": "one_time", "quantity": 10, "base_unit_cost": 1000,
            }],
            horizon_months=12,
        )
        self.assertEqual(result["estimate_id"], "est1")

    def test_compare_scenarios(self):
        from dcc.economics.budget import compare_scenarios
        result = compare_scenarios(scenarios=[
            {"name": "Base", "line_items": [{"line_id": "l1", "description": "Test", "phase": "energy", "cost_behavior": "one_time", "quantity": 1, "base_unit_cost": 100}]},
            {"name": "Alt", "line_items": [{"line_id": "l1", "description": "Test", "phase": "energy", "cost_behavior": "one_time", "quantity": 1, "base_unit_cost": 200}]},
        ])
        self.assertIn("scenarios", result)
        self.assertIn("variance", result)

    def test_compare_scenarios_rejects_empty(self):
        from dcc.economics.budget import compare_scenarios
        with self.assertRaises(ValueError):
            compare_scenarios(scenarios=[])

    def test_compare_scenarios_rejects_too_many(self):
        from dcc.economics.budget import compare_scenarios
        with self.assertRaises(ValueError):
            compare_scenarios(scenarios=[{"name": f"S{i}", "line_items": []} for i in range(11)])

    def test_compare_scenarios_rejects_missing_line_items(self):
        from dcc.economics.budget import compare_scenarios
        with self.assertRaises(ValueError):
            compare_scenarios(scenarios=[{"name": "Test"}])

    def test_compute_unit_economics(self):
        from dcc.economics.budget import compute_unit_economics
        result = compute_unit_economics(
            total_cost=1000000,
            horizon_years=10,
            discount_rate=0.08,
            denominator=100,
            denominator_unit="kW",
        )
        self.assertIn("equivalent_annual_cost", result)
        self.assertIn("cost_per_unit", result)

    def test_compute_unit_economics_rejects_negative_cost(self):
        from dcc.economics.budget import compute_unit_economics
        with self.assertRaises(ValueError):
            compute_unit_economics(total_cost=-1, horizon_years=10)

    def test_compute_unit_economics_rejects_zero_horizon(self):
        from dcc.economics.budget import compute_unit_economics
        with self.assertRaises(ValueError):
            compute_unit_economics(total_cost=100, horizon_years=0)

    def test_compute_unit_economics_rejects_invalid_rate(self):
        from dcc.economics.budget import compute_unit_economics
        with self.assertRaises(ValueError):
            compute_unit_economics(total_cost=100, horizon_years=10, discount_rate=1.0)

    def test_compute_unit_economics_rejects_zero_denominator(self):
        from dcc.economics.budget import compute_unit_economics
        with self.assertRaises(ValueError):
            compute_unit_economics(total_cost=100, horizon_years=10, denominator=0)


class TestPricesIntegration(unittest.TestCase):
    """Integration tests for the price engine."""

    def test_create_price_record(self):
        from dcc.economics.prices import create_price_record
        from datetime import date
        record = create_price_record(
            item_code="SRV-1",
            description="Server",
            category="it_equipment",
            quantity_unit="unit",
            unit_price=Decimal("1000"),
            currency="USD",
            geography="US-East",
            delivery_basis="installed",
            source_kind="vendor_quote",
            source_name="Vendor",
            source_ref="Q-1",
            effective_from=date(2026, 1, 1),
        )
        self.assertEqual(record.item_code, "SRV-1")

    def test_compute_price_at_date(self):
        from dcc.economics.prices import compute_price_at_date, create_price_record
        from datetime import date
        record = create_price_record(
            item_code="SRV-1",
            description="Server",
            category="it_equipment",
            quantity_unit="unit",
            unit_price=Decimal("1000"),
            currency="USD",
            geography="US-East",
            effective_from=date(2026, 1, 1),
        )
        result = compute_price_at_date([record], date(2026, 6, 1))
        self.assertIsNotNone(result)

    def test_compute_weighted_average_price(self):
        from dcc.economics.prices import compute_weighted_average_price, PriceRecord, PriceStatus
        from datetime import date
        records = [
            PriceRecord(
                item_code="A", description="A", category="it_equipment",
                unit_price=Decimal("100"), currency="USD", quantity_unit="unit",
                geography="US", delivery_basis="delivered", effective_from=date(2026, 1, 1),
                status=PriceStatus.APPROVED, price_basis="budgetary", source_kind="manual",
                source_name="", source_ref="", confidence=1.0, fx_to_book=1.0,
            ),
            PriceRecord(
                item_code="B", description="B", category="it_equipment",
                unit_price=Decimal("200"), currency="USD", quantity_unit="unit",
                geography="US", delivery_basis="delivered", effective_from=date(2026, 1, 1),
                status=PriceStatus.APPROVED, price_basis="budgetary", source_kind="manual",
                source_name="", source_ref="", confidence=1.0, fx_to_book=1.0,
            ),
        ]
        result = compute_weighted_average_price(records)
        self.assertIsNotNone(result)

    def test_compute_escalated_price(self):
        from dcc.economics.prices import compute_escalated_price
        result = compute_escalated_price(
            base_price=Decimal("100"),
            escalation_rate=Decimal("0.10"),
            periods=1,
        )
        self.assertEqual(result, Decimal("110"))

    def test_compute_price_index(self):
        from dcc.economics.prices import compute_price_index
        result = compute_price_index(
            base_records=[],
            comparison_records=[],
        )
        self.assertIsNotNone(result)


class TestTariffsIntegration(unittest.TestCase):
    """Integration tests for tariff calculations."""

    def test_create_flat_rate_tariff(self):
        from dcc.economics.tariffs import create_flat_rate_tariff
        spec = create_flat_rate_tariff(rate_per_kwh=0.12)
        self.assertEqual(spec.currency, "USD")

    def test_create_simple_tou_tariff(self):
        from dcc.economics.tariffs import create_simple_tou_tariff
        spec = create_simple_tou_tariff(peak_rate=0.25, off_peak_rate=0.10)
        self.assertEqual(len(spec.tou_periods), 2)

    def test_create_tiered_tariff(self):
        from dcc.economics.tariffs import create_tiered_tariff
        spec = create_tiered_tariff(tiers=[
            {"upper_limit_kwh": "1000", "rate_per_kwh": "0.15"},
            {"upper_limit_kwh": None, "rate_per_kwh": "0.10"},
        ])
        self.assertEqual(len(spec.tiered_rates), 1)

    def test_calculate_tou_charges(self):
        from dcc.economics.tariffs import calculate_tou_charges, TOUPeriod
        from decimal import Decimal
        periods = [
            TOUPeriod(name="peak", days_of_week=(1,2,3,4,5), start_time="12:00", end_time="18:00", rate_per_kwh=Decimal("0.25")),
        ]
        results = calculate_tou_charges(tou_periods=periods, energy_by_period={"peak": Decimal("100")})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].charge, Decimal("25"))

    def test_calculate_demand_charges(self):
        from dcc.economics.tariffs import calculate_demand_charges, DemandCharge
        from decimal import Decimal
        charges = [
            DemandCharge(name="peak_demand", rate_per_kw=Decimal("15"), billing_demand_basis="peak_kw_monthly"),
        ]
        results = calculate_demand_charges(demand_charges=charges, billing_demand_kw=Decimal("100"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].charge, Decimal("1500"))

    def test_calculate_tiered_charges(self):
        from dcc.economics.tariffs import calculate_tiered_charges, TieredRate, Tier
        from decimal import Decimal
        rates = [
            TieredRate(name="energy", tiers=(
                Tier(upper_limit_kwh=Decimal("1000"), rate_per_kwh=Decimal("0.15")),
                Tier(upper_limit_kwh=None, rate_per_kwh=Decimal("0.10")),
            )),
        ]
        results = calculate_tiered_charges(tiered_rates=rates, total_energy_kwh=Decimal("1500"))
        self.assertEqual(len(results), 1)

    def test_calculate_fixed_charges(self):
        from dcc.economics.tariffs import calculate_fixed_charges, FixedCharge
        from decimal import Decimal
        charges = [
            FixedCharge(name="service_fee", amount=Decimal("50"), frequency="monthly"),
        ]
        results = calculate_fixed_charges(fixed_charges=charges, billing_period="monthly")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].amount, Decimal("50"))

    def test_calculate_tariff(self):
        from dcc.economics.tariffs import calculate_tariff, create_flat_rate_tariff
        spec = create_flat_rate_tariff(rate_per_kwh=0.12)
        result = calculate_tariff(spec=spec, energy_kwh=1000, peak_demand_kw=50)
        self.assertEqual(result.energy_kwh, Decimal("1000"))

    def test_tariff_result_to_dict(self):
        from dcc.economics.tariffs import calculate_tariff, create_flat_rate_tariff, tariff_result_to_dict
        spec = create_flat_rate_tariff(rate_per_kwh=0.12)
        result = calculate_tariff(spec=spec, energy_kwh=1000, peak_demand_kw=50)
        d = tariff_result_to_dict(result)
        self.assertIn("total", d)
        self.assertIn("energy_kwh", d)

    def test_calculate_tariff_to_dict(self):
        from dcc.economics.tariffs import calculate_tariff_to_dict, create_flat_rate_tariff
        spec = create_flat_rate_tariff(rate_per_kwh=0.12)
        d = calculate_tariff_to_dict(spec=spec, energy_kwh=1000, peak_demand_kw=50)
        self.assertIn("total", d)

    def test_load_tariff_from_row(self):
        from dcc.economics.tariffs import load_tariff_from_row, EXAMPLE_TARIFF_SPEC
        spec = load_tariff_from_row({"tariff_spec": EXAMPLE_TARIFF_SPEC})
        self.assertEqual(spec.currency, "USD")

    def test_load_tariff_from_row_json(self):
        import json
        from dcc.economics.tariffs import load_tariff_from_row, EXAMPLE_TARIFF_SPEC
        spec = load_tariff_from_row({"tariff_spec": json.dumps(EXAMPLE_TARIFF_SPEC)})
        self.assertEqual(spec.currency, "USD")

    def test_load_tariff_from_row_missing_spec(self):
        from dcc.economics.tariffs import load_tariff_from_row
        with self.assertRaises(ValueError):
            load_tariff_from_row({})

    def test_validate_tariff_spec_rejects_invalid_billing_period(self):
        from dcc.economics.tariffs import TariffSpec, _validate_tariff_spec
        spec = TariffSpec(
            schema_version="tariff.v1", currency="USD", timezone="UTC",
            billing_period="invalid", tou_periods=(), demand_charges=(),
            tiered_rates=(), fixed_charges=(),
        )
        with self.assertRaises(ValueError):
            _validate_tariff_spec(spec)

    def test_validate_tariff_spec_rejects_empty_tou_days(self):
        from dcc.economics.tariffs import TariffSpec, TOUPeriod, _validate_tariff_spec
        from decimal import Decimal
        spec = TariffSpec(
            schema_version="tariff.v1", currency="USD", timezone="UTC",
            billing_period="monthly",
            tou_periods=(TOUPeriod(name="peak", days_of_week=(), start_time="12:00", end_time="18:00", rate_per_kwh=Decimal("0.25")),),
            demand_charges=(), tiered_rates=(), fixed_charges=(),
        )
        with self.assertRaises(ValueError):
            _validate_tariff_spec(spec)

    def test_validate_tariff_spec_rejects_invalid_day(self):
        from dcc.economics.tariffs import TariffSpec, TOUPeriod, _validate_tariff_spec
        from decimal import Decimal
        spec = TariffSpec(
            schema_version="tariff.v1", currency="USD", timezone="UTC",
            billing_period="monthly",
            tou_periods=(TOUPeriod(name="peak", days_of_week=(8,), start_time="12:00", end_time="18:00", rate_per_kwh=Decimal("0.25")),),
            demand_charges=(), tiered_rates=(), fixed_charges=(),
        )
        with self.assertRaises(ValueError):
            _validate_tariff_spec(spec)

    def test_validate_tariff_spec_rejects_negative_rate(self):
        from dcc.economics.tariffs import TariffSpec, TOUPeriod, _validate_tariff_spec
        from decimal import Decimal
        spec = TariffSpec(
            schema_version="tariff.v1", currency="USD", timezone="UTC",
            billing_period="monthly",
            tou_periods=(TOUPeriod(name="peak", days_of_week=(1,), start_time="12:00", end_time="18:00", rate_per_kwh=Decimal("-0.25")),),
            demand_charges=(), tiered_rates=(), fixed_charges=(),
        )
        with self.assertRaises(ValueError):
            _validate_tariff_spec(spec)

    def test_validate_tariff_spec_rejects_same_start_end_time(self):
        from dcc.economics.tariffs import TariffSpec, TOUPeriod, _validate_tariff_spec
        from decimal import Decimal
        spec = TariffSpec(
            schema_version="tariff.v1", currency="USD", timezone="UTC",
            billing_period="monthly",
            tou_periods=(TOUPeriod(name="peak", days_of_week=(1,), start_time="12:00", end_time="12:00", rate_per_kwh=Decimal("0.25")),),
            demand_charges=(), tiered_rates=(), fixed_charges=(),
        )
        with self.assertRaises(ValueError):
            _validate_tariff_spec(spec)

    def test_validate_tariff_spec_rejects_negative_demand_rate(self):
        from dcc.economics.tariffs import TariffSpec, DemandCharge, _validate_tariff_spec
        from decimal import Decimal
        spec = TariffSpec(
            schema_version="tariff.v1", currency="USD", timezone="UTC",
            billing_period="monthly", tou_periods=(),
            demand_charges=(DemandCharge(name="test", rate_per_kw=Decimal("-1"), billing_demand_basis="peak_kw_monthly"),),
            tiered_rates=(), fixed_charges=(),
        )
        with self.assertRaises(ValueError):
            _validate_tariff_spec(spec)

    def test_validate_tariff_spec_rejects_empty_tiers(self):
        from dcc.economics.tariffs import TariffSpec, TieredRate, _validate_tariff_spec
        spec = TariffSpec(
            schema_version="tariff.v1", currency="USD", timezone="UTC",
            billing_period="monthly", tou_periods=(), demand_charges=(),
            tiered_rates=(TieredRate(name="test", tiers=()),), fixed_charges=(),
        )
        with self.assertRaises(ValueError):
            _validate_tariff_spec(spec)

    def test_validate_tariff_spec_rejects_non_ascending_tiers(self):
        from dcc.economics.tariffs import TariffSpec, TieredRate, Tier, _validate_tariff_spec
        from decimal import Decimal
        spec = TariffSpec(
            schema_version="tariff.v1", currency="USD", timezone="UTC",
            billing_period="monthly", tou_periods=(), demand_charges=(),
            tiered_rates=(TieredRate(name="test", tiers=(
                Tier(upper_limit_kwh=Decimal("5000"), rate_per_kwh=Decimal("0.15")),
                Tier(upper_limit_kwh=Decimal("1000"), rate_per_kwh=Decimal("0.10")),
            )),), fixed_charges=(),
        )
        with self.assertRaises(ValueError):
            _validate_tariff_spec(spec)

    def test_validate_tariff_spec_rejects_last_tier_with_limit(self):
        from dcc.economics.tariffs import TariffSpec, TieredRate, Tier, _validate_tariff_spec
        from decimal import Decimal
        spec = TariffSpec(
            schema_version="tariff.v1", currency="USD", timezone="UTC",
            billing_period="monthly", tou_periods=(), demand_charges=(),
            tiered_rates=(TieredRate(name="test", tiers=(
                Tier(upper_limit_kwh=Decimal("1000"), rate_per_kwh=Decimal("0.15")),
                Tier(upper_limit_kwh=Decimal("5000"), rate_per_kwh=Decimal("0.10")),
            )),), fixed_charges=(),
        )
        with self.assertRaises(ValueError):
            _validate_tariff_spec(spec)

    def test_validate_tariff_spec_rejects_negative_fixed_amount(self):
        from dcc.economics.tariffs import TariffSpec, FixedCharge, _validate_tariff_spec
        from decimal import Decimal
        spec = TariffSpec(
            schema_version="tariff.v1", currency="USD", timezone="UTC",
            billing_period="monthly", tou_periods=(), demand_charges=(),
            tiered_rates=(),
            fixed_charges=(FixedCharge(name="test", amount=Decimal("-50"), frequency="monthly"),),
        )
        with self.assertRaises(ValueError):
            _validate_tariff_spec(spec)

    def test_validate_tariff_spec_rejects_invalid_frequency(self):
        from dcc.economics.tariffs import TariffSpec, FixedCharge, _validate_tariff_spec
        from decimal import Decimal
        spec = TariffSpec(
            schema_version="tariff.v1", currency="USD", timezone="UTC",
            billing_period="monthly", tou_periods=(), demand_charges=(),
            tiered_rates=(),
            fixed_charges=(FixedCharge(name="test", amount=Decimal("50"), frequency="invalid"),),
        )
        with self.assertRaises(ValueError):
            _validate_tariff_spec(spec)


class TestReconciliationIntegration(unittest.TestCase):
    """Integration tests for estimate-to-actual reconciliation."""

    def test_reconcile_estimate(self):
        from dcc.economics.reconciliation import reconcile_estimate
        result = reconcile_estimate(
            estimate_id="est1",
            estimate_name="Test Estimate",
            currency="USD",
            estimate_rollup=[{"phase": "energy", "present_value_base": 1000, "present_value_low": 900, "present_value_high": 1100, "line_count": 1}],
            actuals=[{"phase": "energy", "amount": 950, "currency": "USD"}],
        )
        self.assertEqual(result["estimate_id"], "est1")
        self.assertIn("summary", result)
        self.assertIn("by_phase", result)

    def test_reconcile_from_database_rows(self):
        from dcc.economics.reconciliation import reconcile_from_database_rows
        result = reconcile_from_database_rows(
            estimate_row={"id": "est1", "name": "Test", "currency": "USD"},
            rollup_rows=[{"phase": "energy", "present_value_base": 1000, "present_value_low": 900, "present_value_high": 1100, "line_count": 1}],
            actual_rows=[{"phase": "energy", "amount": 950, "currency": "USD"}],
        )
        self.assertEqual(result["estimate_id"], "est1")

    def test_reconcile_multiple(self):
        from dcc.economics.reconciliation import reconcile_multiple
        result = reconcile_multiple(estimates=[
            {
                "estimate_row": {"id": "est1", "name": "Test 1", "currency": "USD"},
                "rollup_rows": [{"phase": "energy", "present_value_base": 1000, "present_value_low": 900, "present_value_high": 1100, "line_count": 1}],
                "actual_rows": [{"phase": "energy", "amount": 950, "currency": "USD"}],
            },
        ])
        self.assertIn("estimates", result)
        self.assertIn("combined", result)

    def test_reconcile_multiple_rejects_empty(self):
        from dcc.economics.reconciliation import reconcile_multiple
        with self.assertRaises(ValueError):
            reconcile_multiple(estimates=[])

    def test_reconcile_multiple_rejects_too_many(self):
        from dcc.economics.reconciliation import reconcile_multiple
        with self.assertRaises(ValueError):
            reconcile_multiple(estimates=[{"estimate_row": {"id": f"e{i}", "name": f"E{i}", "currency": "USD"}, "rollup_rows": [], "actual_rows": []} for i in range(51)])

    def test_variance_thresholds_from_dict(self):
        from dcc.economics.reconciliation import VarianceThresholds
        thresholds = VarianceThresholds.from_dict({"favorable_pct": -0.15, "unfavorable_pct": 0.15})
        self.assertEqual(thresholds.favorable_pct, Decimal("-0.15"))

    def test_variance_thresholds_default(self):
        from dcc.economics.reconciliation import VarianceThresholds
        thresholds = VarianceThresholds()
        self.assertEqual(thresholds.favorable_pct, Decimal("-0.10"))


class TestTCOIntegration(unittest.TestCase):
    """Integration tests for TCO calculations."""

    def test_evaluate_tco(self):
        from dcc.economics.tco import evaluate_tco, TCOAssumptions, TCOCostBreakdown, TCOScenario
        scenario = TCOScenario(
            name="Test",
            costs=TCOCostBreakdown(hardware_capex=100000, energy_annual=5000),
            assumptions=TCOAssumptions(currency="USD", horizon_years=5),
        )
        result = evaluate_tco(scenario)
        self.assertIsNotNone(result)

    def test_compare_tco(self):
        from dcc.economics.tco import compare_tco, TCOAssumptions, TCOCostBreakdown, TCOScenario
        result = compare_tco(
            scenarios=[
                TCOScenario(name="OnPrem", costs=TCOCostBreakdown(hardware_capex=100000, energy_annual=5000), assumptions=TCOAssumptions(currency="USD", horizon_years=5)),
                TCOScenario(name="Cloud", costs=TCOCostBreakdown(hardware_capex=0, energy_annual=10000), assumptions=TCOAssumptions(currency="USD", horizon_years=5)),
            ],
        )
        self.assertIsNotNone(result)

    def test_quick_tco(self):
        from dcc.economics.tco import quick_tco
        result = quick_tco(
            hardware_capex=100000,
            energy_annual=60000,
            horizon_years=5,
        )
        self.assertIsNotNone(result)

    def test_run_tco_sensitivity(self):
        from dcc.economics.tco import run_tco_sensitivity, TCOAssumptions, TCOCostBreakdown, TCOScenario
        scenario = TCOScenario(
            name="Test",
            costs=TCOCostBreakdown(hardware_capex=100000, energy_annual=5000),
            assumptions=TCOAssumptions(currency="USD", horizon_years=5),
        )
        result = run_tco_sensitivity(
            scenario=scenario,
            parameter_name="hardware_capex",
            values=[50000, 100000, 150000],
        )
        self.assertIsNotNone(result)

    def test_tco_breakdown_by_category(self):
        from dcc.economics.tco import tco_breakdown_by_category, TCOAssumptions, TCOCostBreakdown, TCOScenario, evaluate_tco
        scenario = TCOScenario(
            name="Test",
            costs=TCOCostBreakdown(hardware_capex=100000, energy_annual=5000, maintenance_annual=2000),
            assumptions=TCOAssumptions(currency="USD", horizon_years=5),
        )
        result = evaluate_tco(scenario)
        breakdown = tco_breakdown_by_category(result)
        self.assertIsNotNone(breakdown)

    def test_tco_cost_per_unit(self):
        from dcc.economics.tco import tco_cost_per_unit, TCOAssumptions, TCOCostBreakdown, TCOScenario, evaluate_tco
        scenario = TCOScenario(
            name="Test",
            costs=TCOCostBreakdown(hardware_capex=100000, energy_annual=5000),
            assumptions=TCOAssumptions(currency="USD", horizon_years=5),
        )
        result = evaluate_tco(scenario)
        cpu = tco_cost_per_unit(result, "it_capacity_kw", 100)
        self.assertIsNotNone(cpu)


class TestScenariosIntegration(unittest.TestCase):
    """Integration tests for what-if scenario modeling."""

    def test_evaluate_scenario(self):
        from dcc.economics.scenarios import evaluate_scenario, DeploymentScenario, CostBreakdown, ScenarioAssumptions
        scenario = DeploymentScenario(
            name="Test",
            costs=CostBreakdown(capex=100000, power_monthly=5000),
            assumptions=ScenarioAssumptions(currency="USD", horizon_months=36),
        )
        result = evaluate_scenario(scenario)
        self.assertEqual(result.scenario_name, "Test")
        self.assertIsNotNone(result.npv)

    def test_compare_scenarios(self):
        from dcc.economics.scenarios import compare_scenarios, DeploymentScenario, CostBreakdown, ScenarioAssumptions
        scenarios = [
            DeploymentScenario(name="A", costs=CostBreakdown(capex=100000), assumptions=ScenarioAssumptions()),
            DeploymentScenario(name="B", costs=CostBreakdown(capex=200000), assumptions=ScenarioAssumptions()),
        ]
        result = compare_scenarios(scenarios)
        self.assertEqual(len(result.scenarios), 2)

    def test_run_sensitivity(self):
        from dcc.economics.scenarios import run_sensitivity, DeploymentScenario, CostBreakdown, ScenarioAssumptions
        scenario = DeploymentScenario(
            name="Test",
            costs=CostBreakdown(capex=100000, power_monthly=5000),
            assumptions=ScenarioAssumptions(),
        )
        result = run_sensitivity(scenario, "discount_rate", [0.05, 0.08, 0.12])
        self.assertEqual(len(result.npv_results), 3)

    def test_scenario_engine(self):
        from dcc.economics.scenarios import ScenarioEngine, DeploymentScenario, CostBreakdown, ScenarioAssumptions
        engine = ScenarioEngine()
        engine.add_scenario(DeploymentScenario(name="A", costs=CostBreakdown(capex=100000), assumptions=ScenarioAssumptions()))
        engine.add_scenario(DeploymentScenario(name="B", costs=CostBreakdown(capex=200000), assumptions=ScenarioAssumptions()))
        self.assertEqual(engine.count, 2)

    def test_scenario_engine_evaluate(self):
        from dcc.economics.scenarios import ScenarioEngine, DeploymentScenario, CostBreakdown, ScenarioAssumptions
        engine = ScenarioEngine()
        engine.add_scenario(DeploymentScenario(name="A", costs=CostBreakdown(capex=100000), assumptions=ScenarioAssumptions()))
        result = engine.evaluate("A")
        self.assertEqual(result.scenario_name, "A")

    def test_scenario_engine_compare(self):
        from dcc.economics.scenarios import ScenarioEngine, DeploymentScenario, CostBreakdown, ScenarioAssumptions
        engine = ScenarioEngine()
        engine.add_scenario(DeploymentScenario(name="A", costs=CostBreakdown(capex=100000), assumptions=ScenarioAssumptions()))
        engine.add_scenario(DeploymentScenario(name="B", costs=CostBreakdown(capex=200000), assumptions=ScenarioAssumptions()))
        result = engine.compare()
        self.assertEqual(len(result.scenarios), 2)

    def test_scenario_engine_sensitivity(self):
        from dcc.economics.scenarios import ScenarioEngine, DeploymentScenario, CostBreakdown, ScenarioAssumptions
        engine = ScenarioEngine()
        engine.add_scenario(DeploymentScenario(name="A", costs=CostBreakdown(capex=100000, power_monthly=5000), assumptions=ScenarioAssumptions()))
        result = engine.sensitivity("discount_rate", [0.05, 0.08])
        self.assertEqual(len(result.npv_results), 2)

    def test_scenario_engine_break_even(self):
        from dcc.economics.scenarios import ScenarioEngine, DeploymentScenario, CostBreakdown, ScenarioAssumptions
        engine = ScenarioEngine()
        engine.add_scenario(DeploymentScenario(name="A", costs=CostBreakdown(capex=100000, power_monthly=5000), assumptions=ScenarioAssumptions()))
        engine.add_scenario(DeploymentScenario(name="B", costs=CostBreakdown(capex=50000, power_monthly=8000), assumptions=ScenarioAssumptions()))
        result = engine.break_even("A", "B", "capex", 0, 200000)
        self.assertIsNotNone(result)

    def test_scenario_engine_to_dict(self):
        from dcc.economics.scenarios import ScenarioEngine, DeploymentScenario, CostBreakdown, ScenarioAssumptions
        engine = ScenarioEngine()
        engine.add_scenario(DeploymentScenario(name="A", costs=CostBreakdown(capex=100000), assumptions=ScenarioAssumptions()))
        d = engine.to_dict()
        self.assertEqual(d["scenario_count"], 1)

    def test_scenario_engine_remove(self):
        from dcc.economics.scenarios import ScenarioEngine, DeploymentScenario, CostBreakdown, ScenarioAssumptions
        engine = ScenarioEngine()
        engine.add_scenario(DeploymentScenario(name="A", costs=CostBreakdown(capex=100000), assumptions=ScenarioAssumptions()))
        engine.remove_scenario("A")
        self.assertEqual(engine.count, 0)

    def test_scenario_engine_clear(self):
        from dcc.economics.scenarios import ScenarioEngine, DeploymentScenario, CostBreakdown, ScenarioAssumptions
        engine = ScenarioEngine()
        engine.add_scenario(DeploymentScenario(name="A", costs=CostBreakdown(capex=100000), assumptions=ScenarioAssumptions()))
        engine.clear()
        self.assertEqual(engine.count, 0)

    def test_cost_breakdown_total_upfront(self):
        from dcc.economics.scenarios import CostBreakdown
        costs = CostBreakdown(capex=100000, site=50000, migration=25000)
        self.assertEqual(costs.total_upfront, 175000)

    def test_cost_breakdown_total_monthly(self):
        from dcc.economics.scenarios import CostBreakdown
        costs = CostBreakdown(power_monthly=5000, software_monthly=2000, maintenance_monthly=1000)
        self.assertEqual(costs.total_monthly, 8000)

    def test_cost_breakdown_terminal_net(self):
        from dcc.economics.scenarios import CostBreakdown
        costs = CostBreakdown(exit_cost=10000, residual_value=5000)
        self.assertEqual(costs.terminal_net, 5000)

    def test_cost_breakdown_rejects_negative(self):
        from dcc.economics.scenarios import CostBreakdown
        with self.assertRaises(ValueError):
            CostBreakdown(capex=-1)

    def test_cost_breakdown_rejects_invalid_refresh_month(self):
        from dcc.economics.scenarios import CostBreakdown
        with self.assertRaises(ValueError):
            CostBreakdown(refresh_month=121)

    def test_scenario_assumptions_rejects_invalid_currency(self):
        from dcc.economics.scenarios import ScenarioAssumptions
        with self.assertRaises(ValueError):
            ScenarioAssumptions(currency="US")

    def test_scenario_assumptions_rejects_invalid_horizon(self):
        from dcc.economics.scenarios import ScenarioAssumptions
        with self.assertRaises(ValueError):
            ScenarioAssumptions(horizon_months=0)

    def test_scenario_assumptions_rejects_invalid_discount_rate(self):
        from dcc.economics.scenarios import ScenarioAssumptions
        with self.assertRaises(ValueError):
            ScenarioAssumptions(annual_discount_rate=1.5)

    def test_scenario_assumptions_rejects_zero_units(self):
        from dcc.economics.scenarios import ScenarioAssumptions
        with self.assertRaises(ValueError):
            ScenarioAssumptions(useful_units_per_month=0)

    def test_scenario_assumptions_rejects_empty_unit_name(self):
        from dcc.economics.scenarios import ScenarioAssumptions
        with self.assertRaises(ValueError):
            ScenarioAssumptions(useful_unit_name="")

    def test_scenario_assumptions_rejects_empty_demand_profile(self):
        from dcc.economics.scenarios import ScenarioAssumptions
        with self.assertRaises(ValueError):
            ScenarioAssumptions(demand_profile="")

    def test_deployment_scenario_rejects_empty_name(self):
        from dcc.economics.scenarios import DeploymentScenario, CostBreakdown
        with self.assertRaises(ValueError):
            DeploymentScenario(name="", costs=CostBreakdown())

    def test_deployment_scenario_rejects_long_name(self):
        from dcc.economics.scenarios import DeploymentScenario, CostBreakdown
        with self.assertRaises(ValueError):
            DeploymentScenario(name="x" * 121, costs=CostBreakdown())

    def test_deployment_scenario_rejects_non_string_description(self):
        from dcc.economics.scenarios import DeploymentScenario, CostBreakdown
        with self.assertRaises(ValueError):
            DeploymentScenario(name="Test", costs=CostBreakdown(), description=123)

    def test_deployment_scenario_rejects_empty_scenario_type(self):
        from dcc.economics.scenarios import DeploymentScenario, CostBreakdown
        with self.assertRaises(ValueError):
            DeploymentScenario(name="Test", costs=CostBreakdown(), scenario_type="")

    def test_deployment_scenario_rejects_non_list_tags(self):
        from dcc.economics.scenarios import DeploymentScenario, CostBreakdown
        with self.assertRaises(ValueError):
            DeploymentScenario(name="Test", costs=CostBreakdown(), tags="not-a-list")

    def test_deployment_scenario_rejects_non_dict_metadata(self):
        from dcc.economics.scenarios import DeploymentScenario, CostBreakdown
        with self.assertRaises(ValueError):
            DeploymentScenario(name="Test", costs=CostBreakdown(), metadata="not-a-dict")

    def test_compare_scenarios_rejects_empty(self):
        from dcc.economics.scenarios import compare_scenarios
        with self.assertRaises(ValueError):
            compare_scenarios([])

    def test_compare_scenarios_rejects_invalid_baseline(self):
        from dcc.economics.scenarios import compare_scenarios, DeploymentScenario, CostBreakdown, ScenarioAssumptions
        with self.assertRaises(ValueError):
            compare_scenarios([DeploymentScenario(name="A", costs=CostBreakdown(), assumptions=ScenarioAssumptions())], baseline_index=5)

    def test_run_sensitivity_rejects_unsupported_parameter(self):
        from dcc.economics.scenarios import run_sensitivity, DeploymentScenario, CostBreakdown, ScenarioAssumptions
        scenario = DeploymentScenario(name="Test", costs=CostBreakdown(), assumptions=ScenarioAssumptions())
        with self.assertRaises(ValueError):
            run_sensitivity(scenario, "unsupported", [1, 2])

    def test_run_sensitivity_rejects_empty_values(self):
        from dcc.economics.scenarios import run_sensitivity, DeploymentScenario, CostBreakdown, ScenarioAssumptions
        scenario = DeploymentScenario(name="Test", costs=CostBreakdown(), assumptions=ScenarioAssumptions())
        with self.assertRaises(ValueError):
            run_sensitivity(scenario, "discount_rate", [])


if __name__ == "__main__":
    unittest.main()
