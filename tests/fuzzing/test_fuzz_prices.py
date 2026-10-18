"""Fuzz tests for price engine using Hypothesis."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st, assume

from dcc.economics.prices import (
    PriceEngine,
    PriceRecord,
    PriceQuery,
    PriceStatus,
    PriceBasis,
    DeliveryBasis,
    create_price_record,
    compute_price_at_date,
    compute_weighted_average_price,
    compute_escalated_price,
    compute_price_index,
)


# Strategies
currency_codes = st.sampled_from(["USD", "EUR", "GBP", "JPY"])

non_negative_decimals = st.decimals(
    min_value=Decimal("0"), max_value=Decimal("999999999"), allow_nan=False, allow_infinity=False
)

positive_decimals = st.decimals(
    min_value=Decimal("0.001"), max_value=Decimal("999999999"), allow_nan=False, allow_infinity=False
)

confidence_values = st.decimals(
    min_value=Decimal("0"), max_value=Decimal("1"), allow_nan=False, allow_infinity=False
)

dates = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))

item_codes = st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N")))


class TestPriceEngineFuzz:
    """Fuzz price engine operations."""

    @given(
        item_code=item_codes,
        unit_price=non_negative_decimals,
        currency=currency_codes,
        effective_from=dates,
    )
    @settings(max_examples=100)
    def test_create_price_record(self, item_code, unit_price, currency, effective_from):
        """create_price_record should handle any valid inputs."""
        record = create_price_record(
            item_code=item_code,
            description="Test item",
            category="test",
            unit_price=unit_price,
            currency=currency,
            quantity_unit="kW",
            geography="US-East",
            effective_from=effective_from,
        )
        assert record.item_code == item_code
        assert record.unit_price == unit_price
        assert record.currency == currency

    @given(
        n_records=st.integers(min_value=1, max_value=20),
        currency=currency_codes,
    )
    @settings(max_examples=100)
    def test_price_engine_add_and_query(self, n_records, currency):
        """PriceEngine should handle adding and querying records."""
        engine = PriceEngine()
        base_date = date(2025, 1, 1)
        for i in range(n_records):
            record = create_price_record(
                item_code=f"item-{i}",
                description=f"Item {i}",
                category="test",
                unit_price=Decimal("100.00") + i,
                currency=currency,
                quantity_unit="kW",
                geography="US-East",
                effective_from=base_date,
            )
            engine.add_price(record)
        assert engine.record_count == n_records

        query = PriceQuery(item_code="item-0", include_drafts=True)
        result = engine.query(query)
        assert result.total_found >= 1

    @given(
        n_records=st.integers(min_value=1, max_value=20),
        currency=currency_codes,
    )
    @settings(max_examples=100)
    def test_price_engine_supersede(self, n_records, currency):
        """PriceEngine should handle superseding records."""
        engine = PriceEngine()
        base_date = date(2025, 1, 1)
        for i in range(n_records):
            record = create_price_record(
                item_code="test-item",
                description=f"Version {i}",
                category="test",
                unit_price=Decimal("100.00") + i,
                currency=currency,
                quantity_unit="kW",
                geography="US-East",
                effective_from=base_date,
            )
            engine.add_price(record)
            base_date = date.fromordinal(base_date.toordinal() + 1)

        # Supersede the first record
        new_record = create_price_record(
            item_code="test-item",
            description="Superseded version",
            category="test",
            unit_price=Decimal("200.00"),
            currency=currency,
            quantity_unit="kW",
            geography="US-East",
            effective_from=date(2025, 6, 1),
        )
        engine.supersede_price("test-item", date(2025, 1, 1), new_record)
        assert engine.record_count == n_records + 1

    @given(
        n_records=st.integers(min_value=1, max_value=20),
        currency=currency_codes,
    )
    @settings(max_examples=100)
    def test_price_engine_approve_reject(self, n_records, currency):
        """PriceEngine should handle approve/reject operations."""
        engine = PriceEngine()
        base_date = date(2025, 1, 1)
        for i in range(n_records):
            record = create_price_record(
                item_code=f"item-{i}",
                description=f"Item {i}",
                category="test",
                unit_price=Decimal("100.00"),
                currency=currency,
                quantity_unit="kW",
                geography="US-East",
                effective_from=base_date,
                status="draft",
            )
            engine.add_price(record)

        # Approve first record
        engine.approve_price("item-0", base_date)
        # Reject second record
        if n_records > 1:
            engine.reject_price("item-1", base_date)

        query = PriceQuery(status=PriceStatus.APPROVED)
        result = engine.query(query)
        assert result.total_found >= 1

    @given(
        n_records=st.integers(min_value=1, max_value=20),
        currency=currency_codes,
    )
    @settings(max_examples=100)
    def test_price_engine_summarize(self, n_records, currency):
        """PriceEngine should handle summarization."""
        engine = PriceEngine()
        base_date = date(2025, 1, 1)
        for i in range(n_records):
            record = create_price_record(
                item_code="test-item",
                description=f"Version {i}",
                category="test",
                unit_price=Decimal("100.00") + i,
                currency=currency,
                quantity_unit="kW",
                geography="US-East",
                effective_from=base_date,
                status="approved",
            )
            engine.add_price(record)
            base_date = date.fromordinal(base_date.toordinal() + 1)

        summary = engine.summarize("test-item")
        assert summary is not None
        assert summary.record_count == n_records

    @given(
        n_records=st.integers(min_value=1, max_value=20),
        currency=currency_codes,
    )
    @settings(max_examples=100)
    def test_price_engine_compare(self, n_records, currency):
        """PriceEngine should handle price comparison."""
        engine = PriceEngine()
        base_date = date(2025, 1, 1)
        records = []
        for i in range(n_records):
            record = create_price_record(
                item_code="test-item",
                description=f"Version {i}",
                category="test",
                unit_price=Decimal("100.00") + i,
                currency=currency,
                quantity_unit="kW",
                geography="US-East",
                effective_from=base_date,
                status="approved",
            )
            engine.add_price(record)
            records.append(record)
            base_date = date.fromordinal(base_date.toordinal() + 1)

        if len(records) >= 2:
            variance = engine.compare_prices(records[0], records[-1])
            assert variance.absolute_change != 0

    @given(
        n_records=st.integers(min_value=1, max_value=20),
        currency=currency_codes,
    )
    @settings(max_examples=100)
    def test_price_engine_detect_changes(self, n_records, currency):
        """PriceEngine should handle change detection."""
        engine = PriceEngine()
        base_date = date(2025, 1, 1)
        for i in range(n_records):
            record = create_price_record(
                item_code="test-item",
                description=f"Version {i}",
                category="test",
                unit_price=Decimal("100.00") + i * 10,
                currency=currency,
                quantity_unit="kW",
                geography="US-East",
                effective_from=base_date,
                status="approved",
            )
            engine.add_price(record)
            base_date = date.fromordinal(base_date.toordinal() + 1)

        changes = engine.detect_price_changes("test-item", threshold_pct=Decimal("5"))
        assert isinstance(changes, list)


class TestPriceComputationFuzz:
    """Fuzz price computation functions."""

    @given(
        base_price=positive_decimals,
        escalation_rate=st.decimals(min_value=Decimal("-0.99"), max_value=Decimal("0.5"), allow_nan=False, allow_infinity=False),
        periods=st.integers(min_value=0, max_value=50),
    )
    @settings(max_examples=100)
    def test_compute_escalated_price(self, base_price, escalation_rate, periods):
        """compute_escalated_price should handle any valid inputs."""
        result = compute_escalated_price(base_price, escalation_rate, periods)
        assert result >= 0

    @given(
        n_records=st.integers(min_value=1, max_value=20),
        currency=currency_codes,
    )
    @settings(max_examples=100)
    def test_compute_price_at_date(self, n_records, currency):
        """compute_price_at_date should handle any valid records."""
        base_date = date(2025, 1, 1)
        records = []
        for i in range(n_records):
            record = create_price_record(
                item_code="test-item",
                description=f"Version {i}",
                category="test",
                unit_price=Decimal("100.00") + i,
                currency=currency,
                quantity_unit="kW",
                geography="US-East",
                effective_from=base_date,
                status="approved",
            )
            records.append(record)
            base_date = date.fromordinal(base_date.toordinal() + 30)

        query_date = date(2025, 6, 1)
        result = compute_price_at_date(records, query_date)
        # Result may be None if no record is effective on that date
        if result is not None:
            assert result.is_effective_on(query_date)

    @given(
        n_records=st.integers(min_value=1, max_value=20),
        currency=currency_codes,
    )
    @settings(max_examples=100)
    def test_compute_weighted_average_price(self, n_records, currency):
        """compute_weighted_average_price should handle any valid records."""
        base_date = date(2025, 1, 1)
        records = []
        for i in range(n_records):
            record = create_price_record(
                item_code="test-item",
                description=f"Version {i}",
                category="test",
                unit_price=Decimal("100.00") + i,
                currency=currency,
                quantity_unit="kW",
                geography="US-East",
                effective_from=base_date,
                status="approved",
            )
            records.append(record)

        result = compute_weighted_average_price(records)
        assert result is not None
        assert result > 0

    @given(
        n_base=st.integers(min_value=1, max_value=10),
        n_comp=st.integers(min_value=1, max_value=10),
        currency=currency_codes,
    )
    @settings(max_examples=100)
    def test_compute_price_index(self, n_base, n_comp, currency):
        """compute_price_index should handle any valid records."""
        base_date = date(2025, 1, 1)
        base_records = []
        comp_records = []
        for i in range(n_base):
            base_records.append(create_price_record(
                item_code="test-item",
                description=f"Base {i}",
                category="test",
                unit_price=Decimal("100.00"),
                currency=currency,
                quantity_unit="kW",
                geography="US-East",
                effective_from=base_date,
                status="approved",
            ))
        for i in range(n_comp):
            comp_records.append(create_price_record(
                item_code="test-item",
                description=f"Comp {i}",
                category="test",
                unit_price=Decimal("110.00"),
                currency=currency,
                quantity_unit="kW",
                geography="US-East",
                effective_from=base_date,
                status="approved",
            ))

        result = compute_price_index(base_records, comp_records)
        assert result is not None
        assert result > 0
