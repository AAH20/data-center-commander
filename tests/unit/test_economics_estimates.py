"""Unit tests for dcc.economics.estimates module."""
import unittest
from decimal import Decimal

from dcc.economics.estimates import (
    DeploymentType,
    RedundancyLevel,
    TierLevel,
    CostPhase,
    CostBehavior,
    DeploymentSpec,
    ComponentQuantity,
    EstimateLineItem,
    PhaseSubtotal,
    EstimateResult,
    ComponentSizingEngine,
    EstimateBuilder,
    LifecycleCostCalculator,
    BottomUpEstimator,
    estimate_deployment,
    quick_estimate,
    effective_rack_count,
    effective_white_space_m2,
    annual_it_energy,
    annual_facility_energy,
)


def _spec():
    """A DeploymentSpec with the current field names (`name` is required)."""
    return DeploymentSpec(
        name="test",
        it_capacity_kw=Decimal("1000"),
        rack_count=100,
        white_space_m2=Decimal("500"),
        pue=Decimal("1.45"),
    )


def _estimate():
    return estimate_deployment(
        name="test",
        it_capacity_kw=1000,
        rack_count=100,
        white_space_m2=500,
        pue=1.45,
    )


class TestDeploymentType(unittest.TestCase):
    def test_values(self):
        self.assertIsNotNone(DeploymentType.__members__)


class TestRedundancyLevel(unittest.TestCase):
    def test_values(self):
        self.assertIsNotNone(RedundancyLevel.__members__)


class TestTierLevel(unittest.TestCase):
    def test_values(self):
        self.assertIsNotNone(TierLevel.__members__)


class TestCostPhase(unittest.TestCase):
    def test_values(self):
        self.assertIsNotNone(CostPhase.__members__)


class TestCostBehavior(unittest.TestCase):
    def test_values(self):
        self.assertIsNotNone(CostBehavior.__members__)


class TestDeploymentSpec(unittest.TestCase):
    def test_creation(self):
        # The spec uses `it_capacity_kw` / `rack_count` (not `it_load_kw` / `racks`)
        # and `name` is a required field.
        spec = _spec()
        self.assertEqual(spec.it_capacity_kw, Decimal("1000"))
        self.assertEqual(spec.rack_count, 100)
        self.assertEqual(spec.white_space_m2, Decimal("500"))

    def test_derived_quantities(self):
        spec = _spec()
        self.assertEqual(spec.effective_rack_count, 100)
        self.assertEqual(spec.effective_white_space_m2, Decimal("500"))
        self.assertGreater(spec.annual_it_energy, 0)
        self.assertGreater(spec.annual_facility_energy, spec.annual_it_energy)


class TestComponentQuantity(unittest.TestCase):
    def test_creation(self):
        # ComponentQuantity is keyed by `phase` + `description` + `quantity_unit`
        # + `cost_behavior`; there is no `component` / `unit` field.
        q = ComponentQuantity(
            phase=CostPhase.ELECTRICAL,
            description="Electrical distribution",
            quantity=Decimal("1000"),
            quantity_unit="kW",
            cost_behavior=CostBehavior.CAPITALIZED,
        )
        self.assertEqual(q.phase, CostPhase.ELECTRICAL)
        self.assertEqual(q.quantity_unit, "kW")


class TestEstimateLineItem(unittest.TestCase):
    def test_creation(self):
        # EstimateLineItem only exists with all pricing fields populated, so it is
        # produced by the builder rather than hand-constructed. There is no `line_id`
        # or `unit_cost` field: it uses `line_no` and base/low/high unit costs.
        item = _estimate().line_items[0]
        self.assertIsInstance(item, EstimateLineItem)
        self.assertGreater(item.line_no, 0)
        self.assertEqual(item.currency, "USD")
        self.assertGreater(item.extended_base, 0)


class TestPhaseSubtotal(unittest.TestCase):
    def test_creation(self):
        # PhaseSubtotal uses total_base / total_low / total_high (plus PV variants),
        # not base / low / high.
        s = _estimate().phase_subtotals[0]
        self.assertIsInstance(s, PhaseSubtotal)
        self.assertIsNotNone(s.phase)
        self.assertGreater(s.total_base, 0)
        self.assertLessEqual(s.total_low, s.total_base)
        self.assertGreaterEqual(s.total_high, s.total_base)


class TestEstimateResult(unittest.TestCase):
    def test_creation(self):
        # EstimateResult requires the full build context (spec, line items, phase
        # subtotals, ...), so it is produced by estimate_deployment.
        r = _estimate()
        self.assertIsInstance(r, EstimateResult)
        self.assertGreater(r.total_base, 0)
        self.assertLess(r.total_low, r.total_base)
        self.assertGreater(r.total_high, r.total_base)
        self.assertEqual(r.currency, "USD")


class TestComponentSizingEngine(unittest.TestCase):
    def test_creation(self):
        engine = ComponentSizingEngine(_spec())
        self.assertIsNotNone(engine)

    def test_sizes_components(self):
        components = ComponentSizingEngine(_spec()).size_all_components()
        self.assertGreater(len(components), 0)
        self.assertTrue(all(isinstance(c, ComponentQuantity) for c in components))


class TestEstimateBuilder(unittest.TestCase):
    def test_creation(self):
        builder = EstimateBuilder(_spec())
        self.assertIsNotNone(builder)

    def test_builds_line_items(self):
        items = EstimateBuilder(_spec()).build_line_items()
        self.assertGreater(len(items), 0)
        self.assertTrue(all(isinstance(i, EstimateLineItem) for i in items))


class TestLifecycleCostCalculator(unittest.TestCase):
    def test_creation(self):
        calc = LifecycleCostCalculator(_spec())
        self.assertIsNotNone(calc)


class TestBottomUpEstimator(unittest.TestCase):
    def test_creation(self):
        estimator = BottomUpEstimator(_spec())
        self.assertIsNotNone(estimator)

    def test_estimate_method(self):
        result = BottomUpEstimator(_spec()).estimate()
        self.assertIsInstance(result, EstimateResult)


class TestEstimateDeployment(unittest.TestCase):
    def test_estimate(self):
        # estimate_deployment is keyword-only and takes `it_capacity_kw` (not
        # `it_load_kw`); `name` is required. It builds the spec internally.
        result = _estimate()
        self.assertIsInstance(result, EstimateResult)
        self.assertEqual(result.spec.it_capacity_kw, Decimal("1000"))


class TestQuickEstimate(unittest.TestCase):
    def test_estimate(self):
        # quick_estimate takes a positional IT capacity in kW and returns a plain
        # dict of headline figures (it does not return an EstimateResult).
        result = quick_estimate(1000.0)
        self.assertIsInstance(result, dict)
        self.assertGreater(result["total_base"], 0)
        self.assertIn("equivalent_annual_cost", result)


class TestEffectiveRackCount(unittest.TestCase):
    def test_compute(self):
        result = effective_rack_count(
            it_load_kw=Decimal("1000"),
            kw_per_rack=Decimal("8"),
        )
        self.assertGreater(result, 0)


class TestEffectiveWhiteSpaceM2(unittest.TestCase):
    def test_compute(self):
        result = effective_white_space_m2(
            it_load_kw=Decimal("1000"),
            kw_per_m2=Decimal("1.5"),
        )
        self.assertGreater(result, 0)


class TestAnnualItEnergy(unittest.TestCase):
    def test_compute(self):
        result = annual_it_energy(
            it_load_kw=Decimal("1000"),
        )
        self.assertGreater(result, 0)


class TestAnnualFacilityEnergy(unittest.TestCase):
    def test_compute(self):
        result = annual_facility_energy(
            it_load_kw=Decimal("1000"),
            pue=Decimal("1.45"),
        )
        self.assertGreater(result, 0)


if __name__ == "__main__":
    unittest.main()
