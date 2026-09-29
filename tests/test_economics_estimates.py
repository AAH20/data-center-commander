"""Tests for bottom-up cost estimation engine."""
import unittest
from decimal import Decimal
from datetime import date

from dcc.economics.estimates import (
    BottomUpEstimator,
    ComponentQuantity,
    ComponentSizingEngine,
    CostBehavior,
    CostPhase,
    DeploymentSpec,
    DeploymentType,
    EstimateBuilder,
    EstimateLineItem,
    EstimateResult,
    LifecycleCostCalculator,
    PhaseSubtotal,
    RedundancyLevel,
    TierLevel,
    estimate_deployment,
    quick_estimate,
    DEFAULT_PUE,
    DEFAULT_CONTINGENCY_PCT,
    DEFAULT_ESCALATION_PCT,
    DEFAULT_DISCOUNT_RATE,
)
from dcc.economics.prices import PriceEngine, PriceRecord, PriceStatus


class TestDeploymentSpec(unittest.TestCase):
    """Tests for DeploymentSpec dataclass."""

    def test_basic_creation(self):
        spec = DeploymentSpec(name="Test DC", it_capacity_kw=Decimal("1000"))
        self.assertEqual(spec.name, "Test DC")
        self.assertEqual(spec.it_capacity_kw, Decimal("1000"))
        self.assertEqual(spec.deployment_type, DeploymentType.GREENFIELD)
        self.assertEqual(spec.redundancy, RedundancyLevel.N_PLUS_1)
        self.assertEqual(spec.tier_level, TierLevel.TIER_III)
        self.assertEqual(spec.pue, DEFAULT_PUE)

    def test_derived_rack_count(self):
        spec = DeploymentSpec(name="Test", it_capacity_kw=Decimal("1000"))
        # 1000 kW / 8 kW per rack = 125 racks
        self.assertEqual(spec.effective_rack_count, 125)

    def test_explicit_rack_count(self):
        spec = DeploymentSpec(
            name="Test",
            it_capacity_kw=Decimal("1000"),
            rack_count=50,
        )
        self.assertEqual(spec.effective_rack_count, 50)

    def test_derived_white_space(self):
        spec = DeploymentSpec(name="Test", it_capacity_kw=Decimal("1000"))
        # 1000 / 1.5 = 666.67 m²
        self.assertAlmostEqual(
            float(spec.effective_white_space_m2),
            666.67,
            places=1,
        )

    def test_annual_energy_derivation(self):
        spec = DeploymentSpec(name="Test", it_capacity_kw=Decimal("1000"))
        # 1000 × 0.8 × 8760 = 7,008,000 kWh
        expected = Decimal("1000") * Decimal("0.8") * Decimal("8760")
        self.assertEqual(spec.annual_it_energy, expected)

    def test_facility_energy_with_pue(self):
        spec = DeploymentSpec(
            name="Test",
            it_capacity_kw=Decimal("1000"),
            pue=Decimal("1.5"),
        )
        it_energy = spec.annual_it_energy
        self.assertEqual(spec.annual_facility_energy, it_energy * Decimal("1.5"))

    def test_invalid_name(self):
        with self.assertRaises(ValueError):
            DeploymentSpec(name="", it_capacity_kw=Decimal("1000"))

    def test_invalid_capacity(self):
        with self.assertRaises(ValueError):
            DeploymentSpec(name="Test", it_capacity_kw=Decimal("0"))

    def test_invalid_horizon(self):
        with self.assertRaises(ValueError):
            DeploymentSpec(
                name="Test",
                it_capacity_kw=Decimal("1000"),
                horizon_months=0,
            )

    def test_invalid_discount_rate(self):
        with self.assertRaises(ValueError):
            DeploymentSpec(
                name="Test",
                it_capacity_kw=Decimal("1000"),
                discount_rate=Decimal("1.0"),
            )


class TestComponentQuantity(unittest.TestCase):
    """Tests for ComponentQuantity dataclass."""

    def test_basic_quantity(self):
        cq = ComponentQuantity(
            phase=CostPhase.ELECTRICAL,
            description="Test component",
            quantity=Decimal("1000"),
            quantity_unit="kW",
            cost_behavior=CostBehavior.CAPITALIZED,
            unit_cost_item_code="TEST-KW",
            unit_cost_override=Decimal("2400"),
        )
        self.assertEqual(cq.extended_base, Decimal("2400000"))

    def test_lump_sum_quantity(self):
        cq = ComponentQuantity(
            phase=CostPhase.DESIGN,
            description="Design services",
            quantity=Decimal("500000"),
            quantity_unit="USD",
            cost_behavior=CostBehavior.ONE_TIME,
        )
        self.assertTrue(cq.is_lump_sum)
        self.assertEqual(cq.extended_base, Decimal("500000"))
        self.assertEqual(cq.extended_low, Decimal("500000"))
        self.assertEqual(cq.extended_high, Decimal("500000"))

    def test_extended_with_waste_factor(self):
        cq = ComponentQuantity(
            phase=CostPhase.CIVIL,
            description="Civil works",
            quantity=Decimal("1000"),
            quantity_unit="m²",
            cost_behavior=CostBehavior.CAPITALIZED,
            unit_cost_override=Decimal("800"),
            waste_factor=Decimal("0.05"),
        )
        # 1000 × 1.05 × 800 = 840,000
        self.assertEqual(cq.extended_base, Decimal("840000"))

    def test_extended_low_high_bounds(self):
        cq = ComponentQuantity(
            phase=CostPhase.ELECTRICAL,
            description="Test",
            quantity=Decimal("100"),
            quantity_unit="kW",
            cost_behavior=CostBehavior.CAPITALIZED,
            unit_cost_override=Decimal("2400"),
            low_unit_cost=Decimal("1800"),
            high_unit_cost=Decimal("3200"),
        )
        self.assertEqual(cq.extended_base, Decimal("240000"))
        self.assertEqual(cq.extended_low, Decimal("180000"))
        self.assertEqual(cq.extended_high, Decimal("320000"))


class TestComponentSizingEngine(unittest.TestCase):
    """Tests for ComponentSizingEngine."""

    def setUp(self):
        self.spec = DeploymentSpec(
            name="Test 1MW",
            it_capacity_kw=Decimal("1000"),
            geography="US-East",
        )
        self.sizing = ComponentSizingEngine(self.spec)

    def test_size_electrical(self):
        components = self.sizing.size_electrical()
        self.assertGreater(len(components), 0)
        # Should have switchgear, UPS, PDUs, generators (Tier III)
        phases = [c.phase for c in components]
        self.assertEqual(phases[0], CostPhase.ELECTRICAL)

    def test_size_mechanical(self):
        components = self.sizing.size_mechanical()
        self.assertGreater(len(components), 0)

    def test_size_civil(self):
        components = self.sizing.size_civil()
        self.assertGreater(len(components), 0)

    def test_size_it_equipment(self):
        components = self.sizing.size_it_equipment()
        self.assertGreater(len(components), 0)

    def test_size_network(self):
        components = self.sizing.size_network()
        self.assertGreater(len(components), 0)

    def test_size_energy_opex(self):
        components = self.sizing.size_energy_opex()
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0].phase, CostPhase.ENERGY)

    def test_size_maintenance_opex(self):
        components = self.sizing.size_maintenance_opex()
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0].phase, CostPhase.MAINTENANCE)

    def test_size_refresh_capex(self):
        components = self.sizing.size_refresh_capex()
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0].phase, CostPhase.IT_EQUIPMENT)

    def test_size_all_components(self):
        components = self.sizing.size_all_components()
        self.assertGreater(len(components), 10)
        # All components should have positive quantities
        for c in components:
            self.assertGreater(c.quantity, 0, f"{c.description} has non-positive quantity")

    def test_redundancy_factor(self):
        self.assertEqual(self.sizing._redundancy_factor(), Decimal("1.2"))  # N+1

        spec_2n = DeploymentSpec(
            name="Test",
            it_capacity_kw=Decimal("1000"),
            redundancy=RedundancyLevel.TWO_N,
        )
        sizing_2n = ComponentSizingEngine(spec_2n)
        self.assertEqual(sizing_2n._redundancy_factor(), Decimal("2.0"))

    def test_no_generators_for_tier_i(self):
        spec = DeploymentSpec(
            name="Test",
            it_capacity_kw=Decimal("1000"),
            tier_level=TierLevel.TIER_I,
        )
        sizing = ComponentSizingEngine(spec)
        electrical = sizing.size_electrical()
        descriptions = [c.description for c in electrical]
        self.assertFalse(any("generator" in d.lower() for d in descriptions))


class TestEstimateBuilder(unittest.TestCase):
    """Tests for EstimateBuilder."""

    def setUp(self):
        self.spec = DeploymentSpec(
            name="Test 1MW",
            it_capacity_kw=Decimal("1000"),
            geography="US-East",
        )
        self.builder = EstimateBuilder(self.spec)

    def test_build_line_items(self):
        items = self.builder.build_line_items()
        self.assertGreater(len(items), 10)
        for item in items:
            self.assertIsInstance(item, EstimateLineItem)
            self.assertGreater(item.quantity, 0)
            self.assertIn(item.phase, [p.value for p in CostPhase])

    def test_pricing_status_with_overrides(self):
        spec = DeploymentSpec(
            name="Test",
            it_capacity_kw=Decimal("1000"),
            price_overrides={
                "SWITCHGEAR-KW": Decimal("2500"),
                "UPS-KW": Decimal("500"),
            },
        )
        builder = EstimateBuilder(spec)
        items = builder.build_line_items()
        # Items with overrides should be "sourced"
        for item in items:
            if item.description == "Main switchgear and distribution":
                self.assertEqual(item.pricing_status, "sourced")
                self.assertEqual(item.base_unit_cost, Decimal("2500"))

    def test_pricing_status_allowance(self):
        # Without overrides, should be "allowance" (has default bounds)
        items = self.builder.build_line_items()
        statuses = {item.pricing_status for item in items}
        self.assertIn("allowance", statuses)

    def test_line_item_extended_costs(self):
        items = self.builder.build_line_items()
        for item in items:
            self.assertGreaterEqual(item.extended_low, 0)
            self.assertGreaterEqual(item.extended_base, item.extended_low)
            self.assertGreaterEqual(item.extended_high, item.extended_base)


class TestLifecycleCostCalculator(unittest.TestCase):
    """Tests for LifecycleCostCalculator."""

    def setUp(self):
        self.spec = DeploymentSpec(
            name="Test 1MW",
            it_capacity_kw=Decimal("1000"),
            geography="US-East",
        )
        self.builder = EstimateBuilder(self.spec)
        self.calculator = LifecycleCostCalculator(self.spec)
        self.items = self.builder.build_line_items()

    def test_calculate_pv(self):
        pv_base, pv_low, pv_high = self.calculator.calculate_pv(self.items)
        self.assertGreater(pv_base, 0)
        self.assertGreater(pv_low, 0)
        self.assertGreater(pv_high, 0)
        self.assertLessEqual(pv_low, pv_base)
        self.assertGreaterEqual(pv_high, pv_base)

    def test_phase_subtotals(self):
        subtotals = self.calculator.calculate_phase_subtotals(self.items)
        self.assertGreater(len(subtotals), 0)
        for st in subtotals:
            self.assertIsInstance(st, PhaseSubtotal)
            self.assertGreater(st.line_count, 0)
            self.assertGreater(st.total_base, 0)

    def test_first_period_cost(self):
        first_period = self.calculator.calculate_first_period_cost(self.items)
        self.assertGreater(first_period, 0)

    def test_annual_opex(self):
        energy, maintenance = self.calculator.calculate_annual_opex(self.items)
        self.assertGreater(energy, 0)
        self.assertGreater(maintenance, 0)

    def test_pv_decreases_with_higher_discount(self):
        spec_low = DeploymentSpec(
            name="Test",
            it_capacity_kw=Decimal("1000"),
            discount_rate=Decimal("0.05"),
        )
        calc_low = LifecycleCostCalculator(spec_low)
        pv_low, _, _ = calc_low.calculate_pv(self.items)

        spec_high = DeploymentSpec(
            name="Test",
            it_capacity_kw=Decimal("1000"),
            discount_rate=Decimal("0.15"),
        )
        calc_high = LifecycleCostCalculator(spec_high)
        pv_high, _, _ = calc_high.calculate_pv(self.items)

        self.assertGreater(pv_low, pv_high)


class TestBottomUpEstimator(unittest.TestCase):
    """Tests for BottomUpEstimator main engine."""

    def test_basic_estimate(self):
        spec = DeploymentSpec(
            name="Test 1MW DC",
            it_capacity_kw=Decimal("1000"),
            geography="US-East",
        )
        estimator = BottomUpEstimator(spec)
        result = estimator.estimate()

        self.assertIsInstance(result, EstimateResult)
        self.assertGreater(result.total_base, 0)
        self.assertGreater(result.total_low, 0)
        self.assertGreater(result.total_high, 0)
        self.assertGreater(result.total_pv_base, 0)
        self.assertGreater(result.first_period_cost, 0)
        self.assertGreater(result.annual_energy_cost, 0)
        self.assertGreater(result.annual_maintenance_cost, 0)
        self.assertGreater(result.equivalent_annual_cost, 0)
        self.assertGreater(result.contingency_amount, 0)
        self.assertFalse(result.execution_permitted)

    def test_estimate_with_price_engine(self):
        engine = PriceEngine()
        engine.add_price(PriceRecord(
            item_code="SWITCHGEAR-KW",
            description="Switchgear",
            category="electrical",
            unit_price=Decimal("2500"),
            currency="USD",
            quantity_unit="kW",
            geography="US-East",
            delivery_basis="installed",
            effective_from=date(2026, 1, 1),
            status=PriceStatus.APPROVED,
        ))

        spec = DeploymentSpec(
            name="Test",
            it_capacity_kw=Decimal("1000"),
            geography="US-East",
        )
        estimator = BottomUpEstimator(spec, price_engine=engine)
        result = estimator.estimate()

        # Find the switchgear line item
        switchgear_items = [
            item for item in result.line_items
            if item.description == "Main switchgear and distribution"
        ]
        self.assertEqual(len(switchgear_items), 1)
        self.assertEqual(switchgear_items[0].base_unit_cost, Decimal("2500"))
        self.assertEqual(switchgear_items[0].pricing_status, "sourced")

    def test_to_dict(self):
        spec = DeploymentSpec(
            name="Test",
            it_capacity_kw=Decimal("1000"),
        )
        estimator = BottomUpEstimator(spec)
        result = estimator.estimate()
        d = result.to_dict()

        self.assertIn("name", d)
        self.assertIn("total_base", d)
        self.assertIn("total_pv_base", d)
        self.assertIn("line_count", d)
        self.assertIn("phase_subtotals", d)
        self.assertIn("execution_permitted", d)
        self.assertFalse(d["execution_permitted"])

    def test_larger_capacity_costs_more(self):
        spec_small = DeploymentSpec(
            name="Small",
            it_capacity_kw=Decimal("100"),
        )
        spec_large = DeploymentSpec(
            name="Large",
            it_capacity_kw=Decimal("1000"),
        )
        est_small = BottomUpEstimator(spec_small).estimate()
        est_large = BottomUpEstimator(spec_large).estimate()

        self.assertGreater(est_large.total_base, est_small.total_base)

    def test_high_tier_costs_more(self):
        spec_t1 = DeploymentSpec(
            name="Tier I",
            it_capacity_kw=Decimal("1000"),
            tier_level=TierLevel.TIER_I,
        )
        spec_t4 = DeploymentSpec(
            name="Tier IV",
            it_capacity_kw=Decimal("1000"),
            tier_level=TierLevel.TIER_IV,
        )
        est_t1 = BottomUpEstimator(spec_t1).estimate()
        est_t4 = BottomUpEstimator(spec_t4).estimate()

        self.assertGreater(est_t4.total_base, est_t1.total_base)


class TestConvenienceFunctions(unittest.TestCase):
    """Tests for estimate_deployment and quick_estimate."""

    def test_estimate_deployment(self):
        result = estimate_deployment(
            name="Test DC",
            it_capacity_kw=1000,
            geography="US-East",
        )
        self.assertIsInstance(result, EstimateResult)
        self.assertGreater(result.total_pv_base, 0)

    def test_estimate_deployment_with_overrides(self):
        result = estimate_deployment(
            name="Test DC",
            it_capacity_kw=500,
            geography="EU-West",
            redundancy="2N",
            tier_level="Tier IV",
            pue=1.6,
        )
        self.assertIsInstance(result, EstimateResult)

    def test_quick_estimate(self):
        result = quick_estimate(1000)
        self.assertIsInstance(result, dict)
        self.assertIn("total_base", result)
        self.assertIn("line_count", result)

    def test_estimate_deployment_invalid_inputs(self):
        with self.assertRaises(ValueError):
            estimate_deployment(name="Test", it_capacity_kw=0)


class TestEstimateLineItem(unittest.TestCase):
    """Tests for EstimateLineItem dataclass."""

    def test_creation(self):
        item = EstimateLineItem(
            line_no=10,
            phase="electrical",
            description="Test item",
            quantity=Decimal("1000"),
            quantity_unit="kW",
            waste_factor=Decimal("0"),
            base_unit_cost=Decimal("2400"),
            low_unit_cost=Decimal("1800"),
            high_unit_cost=Decimal("3200"),
            currency="USD",
            pricing_status="sourced",
            cost_behavior="capitalized",
            recurrence_months=None,
            start_month=0,
            escalation_pct=Decimal("0.03"),
            extended_base=Decimal("2400000"),
            extended_low=Decimal("1800000"),
            extended_high=Decimal("3200000"),
        )
        self.assertEqual(item.line_no, 10)
        self.assertEqual(item.extended_base, Decimal("2400000"))


class TestEstimateResult(unittest.TestCase):
    """Tests for EstimateResult dataclass."""

    def test_to_dict_structure(self):
        spec = DeploymentSpec(name="Test", it_capacity_kw=Decimal("100"))
        estimator = BottomUpEstimator(spec)
        result = estimator.estimate()
        d = result.to_dict()

        expected_keys = {
            "name", "deployment_type", "it_capacity_kw", "rack_count",
            "white_space_m2", "geography", "currency", "redundancy",
            "tier_level", "pue", "horizon_months", "discount_rate",
            "contingency_pct", "escalation_pct", "total_base", "total_low",
            "total_high", "total_pv_base", "total_pv_low", "total_pv_high",
            "first_period_cost", "annual_energy_cost", "annual_maintenance_cost",
            "equivalent_annual_cost", "cost_per_kw_year", "cost_per_rack_year",
            "cost_per_m2_year", "cost_per_kwh", "contingency_amount",
            "line_count", "phase_subtotals", "calculation_version",
            "execution_permitted",
        }
        self.assertEqual(set(d.keys()), expected_keys)


if __name__ == "__main__":
    unittest.main()
