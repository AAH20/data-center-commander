"""Unit tests for dcc.economics.prices module."""

import unittest
from datetime import date
from decimal import Decimal
from typing import Any

from dcc.economics.prices import (
    MAX_CONFIDENCE,
    MAX_FX_RATE,
    MAX_PRICE_VALUE,
    MIN_CONFIDENCE,
    PRICE_PRECISION,
    DeliveryBasis,
    PriceBasis,
    PriceEngine,
    PriceLookupResult,
    PriceQuery,
    PriceRecord,
    PriceStatus,
    PriceSummary,
    PriceVariance,
    PriceVersion,
    compute_escalated_price,
    compute_price_at_date,
    compute_price_index,
    compute_weighted_average_price,
    create_price_record,
)


def _record(**overrides: Any) -> PriceRecord:
    """Build a PriceRecord with the required identity fields filled in.

    PriceRecord requires delivery_basis and effective_from alongside the core
    identity/price fields — a price without a delivery basis and an effective
    date is not actionable, so neither has a default.
    """
    fields: dict[str, Any] = {
        "item_code": "test-item",
        "description": "Test item",
        "category": "electrical",
        "unit_price": Decimal("100.00"),
        "currency": "USD",
        "quantity_unit": "kW",
        "geography": "us-east",
        "delivery_basis": DeliveryBasis.DELIVERED.value,
        "effective_from": date(2024, 1, 1),
    }
    fields.update(overrides)
    return PriceRecord(**fields)


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
        r = _record(
            item_code="test-item",
            unit_price=Decimal("100.00"),
        )
        self.assertEqual(r.item_code, "test-item")
        self.assertEqual(r.unit_price, Decimal("100.00"))

    def test_defaults(self):
        r = _record()
        self.assertEqual(r.delivery_basis, "delivered")
        self.assertEqual(r.status, PriceStatus.DRAFT)
        self.assertEqual(r.price_basis, "budgetary")
        self.assertIsNone(r.effective_to)

    def test_is_effective_on(self):
        r = _record(effective_from=date(2024, 1, 1), effective_to=date(2024, 12, 31))
        self.assertTrue(r.is_effective_on(date(2024, 6, 1)))
        self.assertFalse(r.is_effective_on(date(2025, 6, 1)))


class TestPriceVersion(unittest.TestCase):
    def test_creation(self):
        # A version groups whole records for one item; it does not carry its own
        # effective_from/effective_to (those live on each PriceRecord).
        v = PriceVersion(
            item_code="test-item",
            records=(_record(),),
            version="1",
            created_at=date(2024, 1, 1),
        )
        self.assertEqual(v.version, "1")
        self.assertEqual(len(v.records), 1)

    def test_latest(self):
        older = _record(effective_from=date(2024, 1, 1))
        newer = _record(effective_from=date(2024, 6, 1))
        v = PriceVersion(item_code="test-item", records=(older, newer))
        self.assertEqual(v.latest, newer)
        self.assertEqual(v.earliest, older)

    def test_empty_version_has_no_latest(self):
        v = PriceVersion(item_code="test-item", records=())
        self.assertIsNone(v.latest)


class TestPriceQuery(unittest.TestCase):
    def test_creation(self):
        # The date filter is effective_on (the query has several date modes:
        # effective_on / effective_after / effective_before).
        q = PriceQuery(
            item_code="test-item",
            geography="us-east",
            effective_on=date(2024, 1, 1),
        )
        self.assertEqual(q.item_code, "test-item")
        self.assertEqual(q.effective_on, date(2024, 1, 1))

    def test_defaults(self):
        q = PriceQuery()
        self.assertFalse(q.include_expired)
        self.assertFalse(q.include_drafts)
        self.assertEqual(q.limit, 100)


class TestPriceLookupResult(unittest.TestCase):
    def test_creation(self):
        # A lookup result wraps matching records plus the query that produced
        # them; it has no scalar price/status field of its own.
        q = PriceQuery(item_code="test-item")
        r = PriceLookupResult(
            records=[_record()],
            total_found=1,
            query=q,
        )
        self.assertEqual(r.total_found, 1)
        self.assertEqual(len(r.records), 1)
        # The engine is read-only, so execution is never permitted.
        self.assertFalse(r.execution_permitted)


class TestPriceVariance(unittest.TestCase):
    def test_creation(self):
        # Variance compares two full records, so the price values live on
        # baseline/comparison rather than as flat old/new fields.
        baseline = _record(unit_price=Decimal("100.00"))
        comparison = _record(
            unit_price=Decimal("110.00"), effective_from=date(2025, 1, 1)
        )
        v = PriceVariance(
            baseline=baseline,
            comparison=comparison,
            absolute_change=Decimal("10.00"),
            percent_change=Decimal("10.0"),
            annualized_change=Decimal("10.0"),
            is_increase=True,
            is_decrease=False,
        )
        self.assertEqual(v.percent_change, Decimal("10.0"))
        self.assertTrue(v.is_increase)


class TestPriceSummary(unittest.TestCase):
    def test_creation(self):
        # PriceSummary reports counts and statistics with explicit field names
        # (record_count / mean_price / median_price) instead of count / avg_price.
        s = PriceSummary(
            item_code="test",
            record_count=5,
            approved_count=3,
            min_price=Decimal("90.00"),
            max_price=Decimal("110.00"),
            mean_price=Decimal("100.00"),
            median_price=Decimal("100.00"),
            currency="USD",
            earliest_effective=date(2024, 1, 1),
            latest_effective=date(2024, 12, 1),
            current_price=None,
            price_range=(Decimal("90.00"), Decimal("110.00")),
        )
        self.assertEqual(s.record_count, 5)
        self.assertEqual(s.mean_price, Decimal("100.00"))


class TestPriceEngine(unittest.TestCase):
    def test_creation(self):
        engine = PriceEngine()
        self.assertIsNotNone(engine)

    def test_add_and_lookup(self):
        engine = PriceEngine()
        engine.add_price(_record())
        found = engine.get_price("test-item", date(2024, 1, 1))
        self.assertEqual(found.item_code, "test-item")


class TestCreatePriceRecord(unittest.TestCase):
    def test_create(self):
        # create_price_record requires effective_from (a price with no effective
        # date cannot be placed on a timeline) and defaults delivery_basis.
        r = create_price_record(
            item_code="test-item",
            description="Test item",
            category="electrical",
            unit_price=Decimal("100.00"),
            currency="USD",
            quantity_unit="kW",
            geography="us-east",
            effective_from=date(2024, 1, 1),
        )
        self.assertIsInstance(r, PriceRecord)
        self.assertEqual(r.delivery_basis, "delivered")

    def test_create_accepts_iso_string_date(self):
        r = create_price_record(
            item_code="test-item",
            description="Test item",
            category="electrical",
            unit_price="100.00",
            currency="USD",
            quantity_unit="kW",
            geography="us-east",
            effective_from="2024-01-01",
        )
        self.assertEqual(r.effective_from, date(2024, 1, 1))
        self.assertEqual(r.unit_price, Decimal("100.00"))


class TestComputePriceAtDate(unittest.TestCase):
    def test_compute(self):
        records = [
            _record(
                item_code="test",
                effective_from=date(2024, 1, 1),
                effective_to=date(2024, 12, 31),
            ),
        ]
        # The date argument is on_date, not date.
        result = compute_price_at_date(records, date(2024, 6, 1))
        self.assertIsNotNone(result)
        self.assertEqual(result.unit_price, Decimal("100.00"))

    def test_outside_window_returns_none(self):
        records = [
            _record(effective_from=date(2024, 1, 1), effective_to=date(2024, 12, 31)),
        ]
        self.assertIsNone(compute_price_at_date(records, date(2025, 6, 1)))


class TestComputeWeightedAveragePrice(unittest.TestCase):
    def test_compute(self):
        # The average is taken over normalized_unit_price, which PriceRecord
        # derives as unit_price * fx_to_book (here fx=1, so 100.00).
        records = [_record(item_code="test", unit_price=Decimal("100.00"))]
        self.assertEqual(records[0].normalized_unit_price, Decimal("100.000000"))
        result = compute_weighted_average_price(records)
        self.assertIsNotNone(result)
        self.assertEqual(result, Decimal("100.000000"))

    def test_weighted(self):
        records = [
            _record(unit_price=Decimal("100.00")),
            _record(unit_price=Decimal("200.00")),
        ]
        # weights must be Decimal: they are mixed with Decimal prices.
        result = compute_weighted_average_price(records, [Decimal(3), Decimal(1)])
        self.assertEqual(result, Decimal("125.000000"))

    def test_fx_is_applied(self):
        # Normalization means a foreign-currency price is averaged at its book
        # value: 100 EUR at fx 1.1 -> 110 USD-equivalent.
        records = [_record(unit_price=Decimal("100.00"), fx_to_book=Decimal("1.1"))]
        self.assertEqual(compute_weighted_average_price(records), Decimal("110.000000"))

    def test_no_records_returns_none(self):
        self.assertIsNone(compute_weighted_average_price([]))


class TestComputeEscalatedPrice(unittest.TestCase):
    def test_compute(self):
        # The horizon parameter is `periods` (default period_months=12, i.e. years),
        # so 5 years is periods=5.
        result = compute_escalated_price(
            base_price=Decimal("100.00"),
            escalation_rate=Decimal("0.03"),
            periods=5,
        )
        self.assertGreater(result, Decimal("100.00"))
        self.assertEqual(result, Decimal("115.927407"))


class TestComputePriceIndex(unittest.TestCase):
    def test_compute(self):
        # compute_price_index takes two sets of price RECORDS and returns a
        # Laspeyres-style index where 100 means no change — not a ratio.
        base = [_record(unit_price=Decimal("100.00"))]
        comparison = [_record(unit_price=Decimal("110.00"))]
        result = compute_price_index(base, comparison)
        self.assertEqual(result, Decimal("110.000000"))

    def test_no_change_is_100(self):
        base = [_record()]
        self.assertEqual(compute_price_index(base, base), Decimal("100.000000"))

    def test_empty_returns_none(self):
        self.assertIsNone(compute_price_index([], []))


class TestModuleConstants(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(PRICE_PRECISION, Decimal("0.000001"))
        self.assertGreater(MAX_PRICE_VALUE, Decimal(0))
        self.assertGreater(MAX_FX_RATE, Decimal(0))
        self.assertEqual(MAX_CONFIDENCE, Decimal("1.0"))
        self.assertEqual(MIN_CONFIDENCE, Decimal("0.0"))


if __name__ == "__main__":
    unittest.main()
