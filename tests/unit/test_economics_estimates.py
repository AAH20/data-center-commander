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
        spec = DeploymentSpec(
            it_load_kw=Decimal("1000"),
            pue=Decimal("1.45"),
            racks=100,
            white_space_m2=Decimal("500"),
        )
        self.assertEqual(spec.it_load_kw, Decimal("1000"))


class TestComponentQuantity(unittest.TestCase):
    def test_creation(self):
        q = ComponentQuantity(
            component="electrical",
            quantity=Decimal("1000"),
            unit="kW",
        )
        self.assertEqual(q.component, "electrical")


class TestEstimateLineItem(unittest.TestCase):
    def test_creation(self):
        item = EstimateLineItem(
            line_id="l1",
            description="Test",
            phase="construction",
            quantity=Decimal("100"),
            unit_cost=Decimal("1000"),
            currency="USD",
        )
        self.assertEqual(item.line_id, "l1")


class TestPhaseSubtotal(unittest.TestCase):
    def test_creation(self):
        s = PhaseSubtotal(
            phase="construction",
            base=Decimal("100000"),
            low=Decimal("90000"),
            high=Decimal("110000"),
        )
        self.assertEqual(s.phase, "construction")


class TestEstimateResult(unittest.TestCase):
    def test_creation(self):
        r = EstimateResult(
            total_base=Decimal("1000000"),
            total_low=Decimal("900000"),
            total_high=Decimal("1100000"),
            currency="USD",
        )
        self.assertEqual(r.total_base, Decimal("1000000"))


class TestComponentSizingEngine(unittest.TestCase):
    def test_creation(self):
        engine = ComponentSizingEngine()
        self.assertIsNotNone(engine)


class TestEstimateBuilder(unittest.TestCase):
    def test_creation(self):
        builder = EstimateBuilder()
        self.assertIsNotNone(builder)


class TestLifecycleCostCalculator(unittest.TestCase):
    def test_creation(self):
        calc = LifecycleCostCalculator()
        self.assertIsNotNone(calc)


class TestBottomUpEstimator(unittest.TestCase):
    def test_creation(self):
        estimator = BottomUpEstimator()
        self.assertIsNotNone(estimator)


class TestEstimateDeployment(unittest.TestCase):
    def test_estimate(self):
        spec = DeploymentSpec(
            it_load_kw=Decimal("1000"),
            pue=Decimal("1.45"),
            racks=100,
            white_space_m2=Decimal("500"),
        )
        result = estimate_deployment(spec)
        self.assertIsInstance(result, EstimateResult)


class TestQuickEstimate(unittest.TestCase):
    def test_estimate(self):
        result = quick_estimate(
            it_load_kw=Decimal("1000"),
            pue=Decimal("1.45"),
            racks=100,
        )
        self.assertIsInstance(result, EstimateResult)


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
