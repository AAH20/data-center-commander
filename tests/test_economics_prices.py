"""Tests for effective-dated price management engine."""
import unittest
from datetime import date, timedelta
from decimal import Decimal

from dcc.economics.prices import (
    PriceEngine,
    PriceRecord,
    PriceVersion,
    PriceQuery,
    PriceStatus,
    PriceBasis,
    DeliveryBasis,
    PriceLookupResult,
    PriceVariance,
    PriceSummary,
    create_price_record,
    compute_price_at_date,
    compute_weighted_average_price,
    compute_escalated_price,
    compute_price_index,
    PRICE_PRECISION,
    MAX_PRICE_VALUE,
)


class TestPriceRecord(unittest.TestCase):
    """Tests for PriceRecord dataclass."""

    def _make_record(self, **kwargs):
        defaults = dict(
            item_code="UPS-500K",
            description="500KVA UPS",
            category="electrical",
            unit_price=Decimal("50000"),
            currency="USD",
            quantity_unit="kW",
            geography="US-East",
            delivery_basis=DeliveryBasis.DELIVERED.value,
            effective_from=date(2026, 1, 1),
        )
        defaults.update(kwargs)
        return PriceRecord(**defaults)

    def test_create_basic_record(self):
        record = self._make_record()
        self.assertEqual(record.item_code, "UPS-500K")
        self.assertEqual(record.status, PriceStatus.DRAFT)
        self.assertTrue(record.is_open_ended)
        self.assertFalse(record.is_active)

    def test_effective_to_before_from_raises(self):
        with self.assertRaises(ValueError):
            self._make_record(
                effective_from=date(2026, 6, 1),
                effective_to=date(2026, 1, 1),
            )

    def test_effective_to_equal_from_raises(self):
        with self.assertRaises(ValueError):
            self._make_record(
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 1, 1),
            )

    def test_negative_unit_price_raises(self):
        with self.assertRaises(ValueError):
            self._make_record(unit_price=Decimal("-1"))

    def test_excessive_unit_price_raises(self):
        with self.assertRaises(ValueError):
            self._make_record(unit_price=MAX_PRICE_VALUE + Decimal("1"))

    def test_invalid_currency_raises(self):
        with self.assertRaises(ValueError):
            self._make_record(currency="US")
        with self.assertRaises(ValueError):
            self._make_record(currency="USDD")
        with self.assertRaises(ValueError):
            self._make_record(currency="usd")

    def test_invalid_confidence_raises(self):
        with self.assertRaises(ValueError):
            self._make_record(confidence=Decimal("1.5"))
        with self.assertRaises(ValueError):
            self._make_record(confidence=Decimal("-0.1"))

    def test_invalid_fx_rate_raises(self):
        with self.assertRaises(ValueError):
            self._make_record(fx_to_book=Decimal("0"))
        with self.assertRaises(ValueError):
            self._make_record(fx_to_book=Decimal("-1"))

    def test_normalized_price_auto_computed(self):
        record = self._make_record(
            unit_price=Decimal("100"),
            fx_to_book=Decimal("1.1"),
        )
        self.assertEqual(record.normalized_unit_price, Decimal("110.000000"))

    def test_book_currency_defaults_to_currency(self):
        record = self._make_record(currency="EUR")
        self.assertEqual(record.book_currency, "EUR")

    def test_is_effective_on(self):
        record = self._make_record(
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
        )
        self.assertTrue(record.is_effective_on(date(2026, 6, 15)))
        self.assertTrue(record.is_effective_on(date(2026, 1, 1)))
        self.assertFalse(record.is_effective_on(date(2026, 12, 31)))
        self.assertFalse(record.is_effective_on(date(2025, 12, 31)))

    def test_is_effective_on_open_ended(self):
        record = self._make_record(effective_from=date(2026, 1, 1))
        self.assertTrue(record.is_effective_on(date(2026, 1, 1)))
        self.assertTrue(record.is_effective_on(date(2030, 1, 1)))
        self.assertFalse(record.is_effective_on(date(2025, 12, 31)))

    def test_is_active(self):
        today = date.today()
        record = self._make_record(
            effective_from=today - timedelta(days=30),
            status=PriceStatus.APPROVED,
        )
        self.assertTrue(record.is_active)

    def test_is_active_expired(self):
        record = self._make_record(
            effective_from=date(2020, 1, 1),
            effective_to=date(2020, 12, 31),
            status=PriceStatus.APPROVED,
        )
        self.assertFalse(record.is_active)

    def test_is_active_draft(self):
        record = self._make_record(
            effective_from=date(2020, 1, 1),
            status=PriceStatus.DRAFT,
        )
        self.assertFalse(record.is_active)

    def test_duration_days(self):
        record = self._make_record(
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
        )
        self.assertEqual(record.duration_days, 364)

    def test_overlaps_with(self):
        r1 = self._make_record(
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
        )
        r2 = self._make_record(
            effective_from=date(2026, 6, 1),
            effective_to=date(2026, 12, 31),
        )
        r3 = self._make_record(
            effective_from=date(2026, 7, 1),
            effective_to=date(2026, 12, 31),
        )
        self.assertTrue(r1.overlaps_with(r2))
        self.assertFalse(r1.overlaps_with(r3))

    def test_overlaps_open_ended(self):
        r1 = self._make_record(effective_from=date(2026, 1, 1))
        r2 = self._make_record(effective_from=date(2026, 6, 1))
        self.assertTrue(r1.overlaps_with(r2))
        self.assertTrue(r2.overlaps_with(r1))


class TestPriceVersion(unittest.TestCase):
    """Tests for PriceVersion dataclass."""

    def _make_record(self, **kwargs):
        defaults = dict(
            item_code="UPS-500K",
            description="500KVA UPS",
            category="electrical",
            unit_price=Decimal("50000"),
            currency="USD",
            quantity_unit="kW",
            geography="US-East",
            delivery_basis=DeliveryBasis.DELIVERED.value,
            effective_from=date(2026, 1, 1),
        )
        defaults.update(kwargs)
        return PriceRecord(**defaults)

    def test_version_basic(self):
        r1 = self._make_record(effective_from=date(2026, 1, 1))
        r2 = self._make_record(effective_from=date(2026, 6, 1))
        v = PriceVersion(item_code="UPS-500K", records=(r1, r2))
        self.assertEqual(v.item_code, "UPS-500K")
        self.assertEqual(v.latest, r2)
        self.assertEqual(v.earliest, r1)

    def test_version_approved_records(self):
        r1 = self._make_record(
            effective_from=date(2026, 1, 1),
            status=PriceStatus.APPROVED,
        )
        r2 = self._make_record(
            effective_from=date(2026, 6, 1),
            status=PriceStatus.DRAFT,
        )
        v = PriceVersion(item_code="UPS-500K", records=(r1, r2))
        self.assertEqual(len(v.approved_records), 1)
        self.assertEqual(v.approved_records[0], r1)

    def test_version_is_active(self):
        today = date.today()
        r1 = self._make_record(
            effective_from=today - timedelta(days=30),
            status=PriceStatus.APPROVED,
        )
        v = PriceVersion(item_code="UPS-500K", records=(r1,))
        self.assertTrue(v.is_active)

    def test_version_empty(self):
        v = PriceVersion(item_code="UPS-500K", records=())
        self.assertIsNone(v.latest)
        self.assertIsNone(v.earliest)
        self.assertFalse(v.is_active)


class TestPriceQuery(unittest.TestCase):
    """Tests for PriceQuery dataclass."""

    def test_default_query(self):
        q = PriceQuery()
        self.assertIsNone(q.item_code)
        self.assertEqual(q.limit, 100)

    def test_invalid_limit(self):
        with self.assertRaises(ValueError):
            PriceQuery(limit=0)
        with self.assertRaises(ValueError):
            PriceQuery(limit=10001)

    def test_invalid_min_confidence(self):
        with self.assertRaises(ValueError):
            PriceQuery(min_confidence=Decimal("1.5"))
        with self.assertRaises(ValueError):
            PriceQuery(min_confidence=Decimal("-0.1"))


class TestPriceEngine(unittest.TestCase):
    """Tests for PriceEngine."""

    def _make_record(self, **kwargs):
        defaults = dict(
            item_code="UPS-500K",
            description="500KVA UPS",
            category="electrical",
            unit_price=Decimal("50000"),
            currency="USD",
            quantity_unit="kW",
            geography="US-East",
            delivery_basis=DeliveryBasis.DELIVERED.value,
            effective_from=date(2026, 1, 1),
        )
        defaults.update(kwargs)
        return PriceRecord(**defaults)

    def setUp(self):
        self.engine = PriceEngine()

    def test_add_and_get_price(self):
        record = self._make_record()
        self.engine.add_price(record)
        fetched = self.engine.get_price("UPS-500K", date(2026, 1, 1))
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.item_code, "UPS-500K")

    def test_add_duplicate_raises(self):
        record = self._make_record()
        self.engine.add_price(record)
        with self.assertRaises(ValueError):
            self.engine.add_price(record)

    def test_add_prices_bulk(self):
        records = [
            self._make_record(effective_from=date(2026, 1, 1)),
            self._make_record(effective_from=date(2026, 6, 1)),
        ]
        self.engine.add_prices(records)
        self.assertEqual(self.engine.record_count, 2)

    def test_query_by_item_code(self):
        self.engine.add_price(self._make_record())
        result = self.engine.query(PriceQuery(item_code="UPS-500K", include_drafts=True))
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.total_found, 1)

    def test_query_by_geography(self):
        self.engine.add_price(self._make_record(geography="US-East"))
        self.engine.add_price(self._make_record(geography="EU-West", effective_from=date(2026, 6, 1)))
        result = self.engine.query(PriceQuery(geography="US-East", include_drafts=True))
        self.assertEqual(len(result.records), 1)

    def test_query_by_category(self):
        self.engine.add_price(self._make_record(category="electrical"))
        self.engine.add_price(self._make_record(category="mechanical", effective_from=date(2026, 6, 1)))
        result = self.engine.query(PriceQuery(category="electrical", include_drafts=True))
        self.assertEqual(len(result.records), 1)

    def test_query_by_status(self):
        self.engine.add_price(self._make_record(status=PriceStatus.DRAFT))
        self.engine.add_price(self._make_record(
            effective_from=date(2026, 6, 1),
            status=PriceStatus.APPROVED,
        ))
        result = self.engine.query(PriceQuery(status=PriceStatus.APPROVED))
        self.assertEqual(len(result.records), 1)

    def test_query_by_effective_on(self):
        self.engine.add_price(self._make_record(
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            status=PriceStatus.APPROVED,
        ))
        self.engine.add_price(self._make_record(
            effective_from=date(2026, 7, 1),
            status=PriceStatus.APPROVED,
        ))
        result = self.engine.query(PriceQuery(effective_on=date(2026, 3, 15)))
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].effective_from, date(2026, 1, 1))

    def test_query_exclude_expired_by_default(self):
        self.engine.add_price(self._make_record(
            effective_from=date(2020, 1, 1),
            effective_to=date(2020, 12, 31),
            status=PriceStatus.EXPIRED,
        ))
        result = self.engine.query(PriceQuery())
        self.assertEqual(len(result.records), 0)

    def test_query_include_expired(self):
        self.engine.add_price(self._make_record(
            effective_from=date(2020, 1, 1),
            effective_to=date(2020, 12, 31),
            status=PriceStatus.EXPIRED,
        ))
        result = self.engine.query(PriceQuery(include_expired=True))
        self.assertEqual(len(result.records), 1)

    def test_query_exclude_drafts_by_default(self):
        self.engine.add_price(self._make_record(status=PriceStatus.DRAFT))
        result = self.engine.query(PriceQuery())
        self.assertEqual(len(result.records), 0)

    def test_query_include_drafts(self):
        self.engine.add_price(self._make_record(status=PriceStatus.DRAFT))
        result = self.engine.query(PriceQuery(include_drafts=True))
        self.assertEqual(len(result.records), 1)

    def test_query_limit(self):
        for i in range(10):
            self.engine.add_price(self._make_record(
                item_code=f"ITEM-{i}",
                effective_from=date(2026, 1, 1),
            ))
        result = self.engine.query(PriceQuery(limit=5, include_drafts=True))
        self.assertEqual(len(result.records), 5)
        self.assertEqual(result.total_found, 10)

    def test_get_current_price(self):
        today = date.today()
        self.engine.add_price(self._make_record(
            effective_from=today - timedelta(days=30),
            status=PriceStatus.APPROVED,
        ))
        current = self.engine.get_current_price("UPS-500K")
        self.assertIsNotNone(current)

    def test_get_current_price_none(self):
        current = self.engine.get_current_price("NONEXISTENT")
        self.assertIsNone(current)

    def test_get_price_history(self):
        self.engine.add_price(self._make_record(effective_from=date(2026, 1, 1)))
        self.engine.add_price(self._make_record(effective_from=date(2026, 6, 1)))
        history = self.engine.get_price_history("UPS-500K")
        self.assertEqual(len(history), 2)

    def test_supersede_price(self):
        old = self._make_record(effective_from=date(2026, 1, 1))
        self.engine.add_price(old)
        new = self._make_record(
            effective_from=date(2026, 6, 1),
            unit_price=Decimal("55000"),
        )
        self.engine.supersede_price("UPS-500K", date(2026, 1, 1), new)
        old_fetched = self.engine.get_price("UPS-500K", date(2026, 1, 1))
        self.assertEqual(old_fetched.status, PriceStatus.SUPERSEDED)
        self.assertEqual(old_fetched.effective_to, date(2026, 6, 1))

    def test_supersede_nonexistent_raises(self):
        new = self._make_record(effective_from=date(2026, 6, 1))
        with self.assertRaises(ValueError):
            self.engine.supersede_price("NONEXISTENT", date(2026, 1, 1), new)

    def test_expire_price(self):
        self.engine.add_price(self._make_record(
            effective_from=date(2026, 1, 1),
            status=PriceStatus.APPROVED,
        ))
        expired = self.engine.expire_price("UPS-500K", date(2026, 1, 1))
        self.assertIsNotNone(expired)
        self.assertEqual(expired.status, PriceStatus.EXPIRED)

    def test_expire_nonexistent(self):
        result = self.engine.expire_price("NONEXISTENT", date(2026, 1, 1))
        self.assertIsNone(result)

    def test_approve_price(self):
        self.engine.add_price(self._make_record(status=PriceStatus.DRAFT))
        approved = self.engine.approve_price("UPS-500K", date(2026, 1, 1))
        self.assertIsNotNone(approved)
        self.assertEqual(approved.status, PriceStatus.APPROVED)

    def test_approve_non_draft_raises(self):
        self.engine.add_price(self._make_record(status=PriceStatus.APPROVED))
        with self.assertRaises(ValueError):
            self.engine.approve_price("UPS-500K", date(2026, 1, 1))

    def test_reject_price(self):
        self.engine.add_price(self._make_record(status=PriceStatus.DRAFT))
        rejected = self.engine.reject_price("UPS-500K", date(2026, 1, 1))
        self.assertIsNotNone(rejected)
        self.assertEqual(rejected.status, PriceStatus.REJECTED)

    def test_find_overlaps(self):
        self.engine.add_price(self._make_record(
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
        ))
        overlapping = self._make_record(
            item_code="UPS-500K",
            effective_from=date(2026, 6, 1),
            effective_to=date(2027, 6, 1),
        )
        overlaps = self.engine.find_overlaps(overlapping)
        self.assertEqual(len(overlaps), 1)

    def test_compare_prices(self):
        r1 = self._make_record(unit_price=Decimal("100"))
        r2 = self._make_record(unit_price=Decimal("120"))
        variance = self.engine.compare_prices(r1, r2)
        self.assertEqual(variance.absolute_change, Decimal("20"))
        self.assertEqual(variance.percent_change, Decimal("20"))
        self.assertTrue(variance.is_increase)
        self.assertFalse(variance.is_decrease)

    def test_compare_prices_decrease(self):
        r1 = self._make_record(unit_price=Decimal("100"))
        r2 = self._make_record(unit_price=Decimal("80"))
        variance = self.engine.compare_prices(r1, r2)
        self.assertTrue(variance.is_decrease)
        self.assertFalse(variance.is_increase)

    def test_compare_prices_different_currency_raises(self):
        r1 = self._make_record(currency="USD")
        r2 = self._make_record(currency="EUR")
        with self.assertRaises(ValueError):
            self.engine.compare_prices(r1, r2)

    def test_summarize(self):
        self.engine.add_price(self._make_record(
            unit_price=Decimal("100"),
            status=PriceStatus.APPROVED,
        ))
        self.engine.add_price(self._make_record(
            unit_price=Decimal("200"),
            effective_from=date(2026, 6, 1),
            status=PriceStatus.APPROVED,
        ))
        summary = self.engine.summarize("UPS-500K")
        self.assertIsNotNone(summary)
        self.assertEqual(summary.record_count, 2)
        self.assertEqual(summary.approved_count, 2)
        self.assertEqual(summary.min_price, Decimal("100"))
        self.assertEqual(summary.max_price, Decimal("200"))

    def test_summarize_empty(self):
        summary = self.engine.summarize("NONEXISTENT")
        self.assertIsNone(summary)

    def test_detect_price_changes(self):
        self.engine.add_price(self._make_record(
            unit_price=Decimal("100"),
            effective_from=date(2026, 1, 1),
            status=PriceStatus.APPROVED,
        ))
        self.engine.add_price(self._make_record(
            unit_price=Decimal("110"),
            effective_from=date(2026, 6, 1),
            status=PriceStatus.APPROVED,
        ))
        changes = self.engine.detect_price_changes("UPS-500K", threshold_pct=Decimal("5"))
        self.assertEqual(len(changes), 1)

    def test_detect_price_changes_below_threshold(self):
        self.engine.add_price(self._make_record(
            unit_price=Decimal("100"),
            effective_from=date(2026, 1, 1),
            status=PriceStatus.APPROVED,
        ))
        self.engine.add_price(self._make_record(
            unit_price=Decimal("102"),
            effective_from=date(2026, 6, 1),
            status=PriceStatus.APPROVED,
        ))
        changes = self.engine.detect_price_changes("UPS-500K", threshold_pct=Decimal("5"))
        self.assertEqual(len(changes), 0)

    def test_bulk_approve(self):
        self.engine.add_price(self._make_record(status=PriceStatus.DRAFT))
        self.engine.add_price(self._make_record(
            item_code="OTHER",
            effective_from=date(2026, 1, 1),
            status=PriceStatus.DRAFT,
        ))
        results = self.engine.bulk_approve(["UPS-500K", "OTHER"])
        self.assertEqual(results["UPS-500K"], 1)
        self.assertEqual(results["OTHER"], 1)

    def test_bulk_expire(self):
        past = date.today() - timedelta(days=30)
        self.engine.add_price(self._make_record(
            effective_from=past - timedelta(days=60),
            effective_to=past,
            status=PriceStatus.APPROVED,
        ))
        count = self.engine.bulk_expire()
        self.assertEqual(count, 1)

    def test_get_all_items(self):
        self.engine.add_price(self._make_record(item_code="A"))
        self.engine.add_price(self._make_record(item_code="B"))
        items = self.engine.get_all_items()
        self.assertEqual(items, ["A", "B"])

    def test_to_dict(self):
        self.engine.add_price(self._make_record())
        result = self.engine.to_dict()
        self.assertEqual(result["record_count"], 1)
        self.assertIn("UPS-500K", result["items"])
        self.assertFalse(result["execution_permitted"])


class TestConvenienceFunctions(unittest.TestCase):
    """Tests for module-level convenience functions."""

    def test_create_price_record(self):
        record = create_price_record(
            item_code="TEST-001",
            description="Test item",
            category="electrical",
            unit_price="99.99",
            currency="USD",
            quantity_unit="kW",
            geography="US-East",
            effective_from="2026-01-01",
        )
        self.assertEqual(record.item_code, "TEST-001")
        self.assertEqual(record.unit_price, Decimal("99.99"))

    def test_create_price_record_with_dates(self):
        record = create_price_record(
            item_code="TEST-001",
            description="Test item",
            category="electrical",
            unit_price=100,
            currency="USD",
            quantity_unit="kW",
            geography="US-East",
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
        )
        self.assertEqual(record.effective_from, date(2026, 1, 1))
        self.assertEqual(record.effective_to, date(2026, 12, 31))

    def test_compute_price_at_date(self):
        r1 = create_price_record(
            item_code="TEST",
            description="Test",
            category="electrical",
            unit_price=100,
            currency="USD",
            quantity_unit="kW",
            geography="US-East",
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
        )
        r2 = create_price_record(
            item_code="TEST",
            description="Test",
            category="electrical",
            unit_price=120,
            currency="USD",
            quantity_unit="kW",
            geography="US-East",
            effective_from=date(2026, 7, 1),
        )
        result = compute_price_at_date([r1, r2], date(2026, 3, 15))
        self.assertEqual(result.unit_price, Decimal("100"))
        result = compute_price_at_date([r1, r2], date(2026, 8, 15))
        self.assertEqual(result.unit_price, Decimal("120"))

    def test_compute_price_at_date_none(self):
        result = compute_price_at_date([], date(2026, 1, 1))
        self.assertIsNone(result)

    def test_compute_weighted_average_price(self):
        r1 = create_price_record(
            item_code="TEST",
            description="Test",
            category="electrical",
            unit_price=100,
            currency="USD",
            quantity_unit="kW",
            geography="US-East",
            effective_from=date(2026, 1, 1),
        )
        r2 = create_price_record(
            item_code="TEST",
            description="Test",
            category="electrical",
            unit_price=200,
            currency="USD",
            quantity_unit="kW",
            geography="US-East",
            effective_from=date(2026, 6, 1),
        )
        avg = compute_weighted_average_price([r1, r2])
        self.assertEqual(avg, Decimal("150"))

    def test_compute_weighted_average_price_empty(self):
        result = compute_weighted_average_price([])
        self.assertIsNone(result)

    def test_compute_escalated_price(self):
        result = compute_escalated_price(Decimal("100"), Decimal("0.03"), 5)
        self.assertAlmostEqual(float(result), 115.93, places=2)

    def test_compute_escalated_price_zero_periods(self):
        result = compute_escalated_price(Decimal("100"), Decimal("0.03"), 0)
        self.assertEqual(result, Decimal("100"))

    def test_compute_escalated_price_invalid(self):
        with self.assertRaises(ValueError):
            compute_escalated_price(Decimal("-100"), Decimal("0.03"), 5)
        with self.assertRaises(ValueError):
            compute_escalated_price(Decimal("100"), Decimal("-1.5"), 5)
        with self.assertRaises(ValueError):
            compute_escalated_price(Decimal("100"), Decimal("0.03"), -1)

    def test_compute_price_index(self):
        base = [create_price_record(
            item_code="TEST",
            description="Test",
            category="electrical",
            unit_price=100,
            currency="USD",
            quantity_unit="kW",
            geography="US-East",
            effective_from=date(2026, 1, 1),
        )]
        comp = [create_price_record(
            item_code="TEST",
            description="Test",
            category="electrical",
            unit_price=110,
            currency="USD",
            quantity_unit="kW",
            geography="US-East",
            effective_from=date(2026, 6, 1),
        )]
        index = compute_price_index(base, comp)
        self.assertEqual(index, Decimal("110"))

    def test_compute_price_index_empty(self):
        result = compute_price_index([], [])
        self.assertIsNone(result)


class TestPriceStatus(unittest.TestCase):
    """Tests for PriceStatus enum."""

    def test_status_values(self):
        self.assertEqual(PriceStatus.DRAFT.value, "draft")
        self.assertEqual(PriceStatus.APPROVED.value, "approved")
        self.assertEqual(PriceStatus.EXPIRED.value, "expired")
        self.assertEqual(PriceStatus.REJECTED.value, "rejected")
        self.assertEqual(PriceStatus.SUPERSEDED.value, "superseded")

    def test_status_from_string(self):
        self.assertEqual(PriceStatus("draft"), PriceStatus.DRAFT)
        self.assertEqual(PriceStatus("approved"), PriceStatus.APPROVED)


class TestPriceBasis(unittest.TestCase):
    """Tests for PriceBasis enum."""

    def test_basis_values(self):
        self.assertEqual(PriceBasis.BUDGETARY.value, "budgetary")
        self.assertEqual(PriceBasis.QUOTED.value, "quoted")
        self.assertEqual(PriceBasis.CONTRACTED.value, "contracted")
        self.assertEqual(PriceBasis.ACTUAL.value, "actual")
        self.assertEqual(PriceBasis.BENCHMARK.value, "benchmark")


class TestDeliveryBasis(unittest.TestCase):
    """Tests for DeliveryBasis enum."""

    def test_delivery_values(self):
        self.assertEqual(DeliveryBasis.EX_WORKS.value, "ex_works")
        self.assertEqual(DeliveryBasis.FOB.value, "fob")
        self.assertEqual(DeliveryBasis.CIF.value, "cif")
        self.assertEqual(DeliveryBasis.DELIVERED.value, "delivered")
        self.assertEqual(DeliveryBasis.INSTALLED.value, "installed")
        self.assertEqual(DeliveryBasis.SUBSCRIPTION.value, "subscription")
        self.assertEqual(DeliveryBasis.METERED.value, "metered")
        self.assertEqual(DeliveryBasis.OTHER.value, "other")


if __name__ == "__main__":
    unittest.main()
