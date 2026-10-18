"""Unit tests for dcc.economics.prices module."""
import unittest
from datetime import date, timedelta
from decimal import Decimal

from dcc.economics.prices import (
    PriceStatus,
    PriceBasis,
    DeliveryBasis,
    PriceRecord,
    PriceVersion,
    PriceQuery,
    PriceLookupResult,
    PriceVariance,
    PriceSummary,
    PriceEngine,
    PRICE_PRECISION,
    MAX_PRICE_VALUE,
    MAX_FX_RATE,
    MAX_CONFIDENCE,
    MIN_CONFIDENCE,
    create_price_record,
    compute_price_at_date,
    compute_weighted_average_price,
    compute_escalated_price,
    compute_price_index,
)


class TestPriceStatus(unittest.TestCase):
    def test_values(self):
        self.assertEqual(PriceStatus.DRAFT.value, "draft")
        self.assertEqual(PriceStatus.APPROVED.value, "approved")
        self.assertEqual(PriceStatus.EXPIRED.value, "expired")
        self.assertEqual(PriceStatus.REJECTED.value, "rejected")
        self.assertEqual(PriceStatus.SUPERSEDED.value, "superseded")


class TestPriceBasis(unittest.TestCase):
    def test_values(self):
        self.assertEqual(PriceBasis.BUDGETARY.value, "budgetary")
        self.assertEqual(PriceBasis.QUOTED.value, "quoted")
        self.assertEqual(PriceBasis.CONTRACTED.value, "contracted")
        self.assertEqual(PriceBasis.ACTUAL.value, "actual")
        self.assertEqual(PriceBasis.BENCHMARK.value, "benchmark")


class TestDeliveryBasis(unittest.TestCase):
    def test_values(self):
        self.assertEqual(DeliveryBasis.EX_WORKS.value, "ex_works")
        self.assertEqual(DeliveryBasis.FOB.value, "fob")
        self.assertEqual(DeliveryBasis.CIF.value, "cif")
        self.assertEqual(DeliveryBasis.DELIVERED.value, "delivered")


class TestPriceRecord(unittest.TestCase):
    def test_creation(self):
        r = PriceRecord(
            item_code="test-item",
            description="Test item",
            category="electrical",
            unit_price=Decimal("100.00"),
            currency="USD",
            quantity_unit="kW",
            geography="us-east",
        )
        self.assertEqual(r.item_code, "test-item")
        self.assertEqual(r.unit_price, Decimal("100.00"))


class TestPriceVersion(unittest.TestCase):
    def test_creation(self):
        v = PriceVersion(
            version="1",
            effective_from=date(2024, 1, 1),
            effective_to=None,
        )
        self.assertEqual(v.version, "1")


class TestPriceQuery(unittest.TestCase):
    def test_creation(self):
        q = PriceQuery(
            item_code="test-item",
            geography="us-east",
            date=date(2024, 1, 1),
        )
        self.assertEqual(q.item_code, "test-item")


class TestPriceLookupResult(unittest.TestCase):
    def test_creation(self):
        r = PriceLookupResult(
            price=Decimal("100.00"),
            currency="USD",
            status="ok",
        )
        self.assertEqual(r.price, Decimal("100.00"))


class TestPriceVariance(unittest.TestCase):
    def test_creation(self):
        v = PriceVariance(
            item_code="test",
            old_price=Decimal("100.00"),
            new_price=Decimal("110.00"),
            variance_pct=Decimal("10.0"),
        )
        self.assertEqual(v.variance_pct, Decimal("10.0"))


class TestPriceSummary(unittest.TestCase):
    def test_creation(self):
        s = PriceSummary(
            item_code="test",
            count=5,
            min_price=Decimal("90.00"),
            max_price=Decimal("110.00"),
            avg_price=Decimal("100.00"),
        )
        self.assertEqual(s.count, 5)


class TestPriceEngine(unittest.TestCase):
    def test_creation(self):
        engine = PriceEngine()
        self.assertIsNotNone(engine)


class TestCreatePriceRecord(unittest.TestCase):
    def test_create(self):
        r = create_price_record(
            item_code="test-item",
            description="Test item",
            category="electrical",
            unit_price=Decimal("100.00"),
            currency="USD",
            quantity_unit="kW",
            geography="us-east",
        )
        self.assertIsInstance(r, PriceRecord)


class TestComputePriceAtDate(unittest.TestCase):
    def test_compute(self):
        records = [
            PriceRecord(
                item_code="test",
                description="Test",
                category="electrical",
                unit_price=Decimal("100.00"),
                currency="USD",
                quantity_unit="kW",
                geography="us-east",
                effective_from=date(2024, 1, 1),
                effective_to=date(2024, 12, 31),
            ),
        ]
        result = compute_price_at_date(records, date(2024, 6, 1))
        self.assertIsNotNone(result)


class TestComputeWeightedAveragePrice(unittest.TestCase):
    def test_compute(self):
        records = [
            PriceRecord(
                item_code="test",
                description="Test",
                category="electrical",
                unit_price=Decimal("100.00"),
                currency="USD",
                quantity_unit="kW",
                geography="us-east",
            ),
        ]
        result = compute_weighted_average_price(records)
        self.assertIsNotNone(result)


class TestComputeEscalatedPrice(unittest.TestCase):
    def test_compute(self):
        result = compute_escalated_price(
            base_price=Decimal("100.00"),
            escalation_rate=Decimal("0.03"),
            years=5,
        )
        self.assertGreater(result, Decimal("100.00"))


class TestComputePriceIndex(unittest.TestCase):
    def test_compute(self):
        result = compute_price_index(
            base_price=Decimal("100.00"),
            current_price=Decimal("110.00"),
        )
        self.assertAlmostEqual(float(result), 1.1, places=2)


if __name__ == "__main__":
    unittest.main()
