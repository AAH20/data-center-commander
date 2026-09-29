"""Effective-dated price management engine for Data Center Commander.

Provides versioned price records with effective date ranges, price status
lifecycle, and query capabilities. All calculations are deterministic and
pure—no I/O, no network, no persistence.

The engine handles:
- Versioned price records with effective_from / effective_to dates
- Price status lifecycle (draft → approved → expired / rejected)
- Overlapping effective date detection and resolution
- Price lookup by item, geography, and date
- Currency normalization via FX rates
- Price comparison and variance analysis
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRICE_PRECISION = Decimal("0.000001")  # 6 decimal places
MAX_PRICE_VALUE = Decimal("999999999999.999999")
MAX_FX_RATE = Decimal("999999.9999999999")
MAX_CONFIDENCE = Decimal("1.0")
MIN_CONFIDENCE = Decimal("0.0")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PriceStatus(str, Enum):
    """Price record status lifecycle."""

    DRAFT = "draft"
    APPROVED = "approved"
    EXPIRED = "expired"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class PriceBasis(str, Enum):
    """Price basis classification."""

    BUDGETARY = "budgetary"
    QUOTED = "quoted"
    CONTRACTED = "contracted"
    ACTUAL = "actual"
    BENCHMARK = "benchmark"


class DeliveryBasis(str, Enum):
    """Delivery basis for price records."""

    EX_WORKS = "ex_works"
    FOB = "fob"
    CIF = "cif"
    DELIVERED = "delivered"
    INSTALLED = "installed"
    SUBSCRIPTION = "subscription"
    METERED = "metered"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PriceRecord:
    """A single effective-dated price record.

    Attributes:
        item_code: Unique identifier for the priced item.
        description: Human-readable description.
        category: Cost category (e.g., "electrical", "mechanical").
        unit_price: Price per unit in the specified currency.
        currency: ISO 4217 currency code (3 letters).
        quantity_unit: Unit of measure (e.g., "kW", "m²", "each").
        geography: Geographic scope (e.g., "US-East", "EU-West").
        delivery_basis: Delivery/incoterm basis.
        effective_from: Start of effectiveness (inclusive).
        effective_to: End of effectiveness (exclusive), or None for open-ended.
        status: Current price status.
        price_basis: Basis classification (budgetary, quoted, etc.).
        source_kind: Source type (vendor_api, contract, etc.).
        source_name: Source name or identifier.
        source_ref: Source reference (quote number, contract ID).
        source_digest: Optional hash of source document.
        confidence: Confidence score [0, 1].
        fx_to_book: FX rate to book currency (default 1).
        currency_basis_date: Date of FX rate basis.
        book_currency: Target book currency (defaults to currency).
        normalized_unit_price: Price normalized to book currency.
        version: Version string for this price record.
        superseded_by: ID of the record that superseded this one.
        observed_at: When the price was observed.
        provenance: Additional provenance metadata.
        metadata: Additional caller-specific data.
    """

    item_code: str
    description: str
    category: str
    unit_price: Decimal
    currency: str
    quantity_unit: str
    geography: str
    delivery_basis: str
    effective_from: date
    effective_to: Optional[date] = None
    status: PriceStatus = PriceStatus.DRAFT
    price_basis: str = PriceBasis.BUDGETARY.value
    source_kind: str = "manual"
    source_name: str = ""
    source_ref: str = ""
    source_digest: Optional[str] = None
    confidence: Decimal = Decimal("1.0")
    fx_to_book: Decimal = Decimal("1")
    currency_basis_date: Optional[date] = None
    book_currency: Optional[str] = None
    normalized_unit_price: Optional[Decimal] = None
    version: str = "1"
    superseded_by: Optional[str] = None
    observed_at: Optional[date] = None
    provenance: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Validate effective dates
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")

        # Validate unit_price
        if self.unit_price < 0:
            raise ValueError("unit_price must be non-negative")
        if self.unit_price > MAX_PRICE_VALUE:
            raise ValueError(f"unit_price exceeds maximum {MAX_PRICE_VALUE}")

        # Validate currency
        if not (isinstance(self.currency, str) and len(self.currency) == 3
                and self.currency.isalpha() and self.currency.isupper()):
            raise ValueError("currency must be a 3-letter ISO code")

        # Validate confidence
        if not (MIN_CONFIDENCE <= self.confidence <= MAX_CONFIDENCE):
            raise ValueError("confidence must be between 0 and 1")

        # Validate FX rate
        if self.fx_to_book <= 0:
            raise ValueError("fx_to_book must be positive")
        if self.fx_to_book > MAX_FX_RATE:
            raise ValueError(f"fx_to_book exceeds maximum {MAX_FX_RATE}")

        # Compute normalized price if not provided
        if self.normalized_unit_price is None:
            object.__setattr__(
                self,
                "normalized_unit_price",
                _round_price(self.unit_price * self.fx_to_book),
            )

        # Default book_currency to currency
        if self.book_currency is None:
            object.__setattr__(self, "book_currency", self.currency)

    @property
    def is_open_ended(self) -> bool:
        """True if the price has no end date."""
        return self.effective_to is None

    @property
    def is_active(self) -> bool:
        """True if the price is currently active (approved and within effective range)."""
        if self.status != PriceStatus.APPROVED:
            return False
        today = date.today()
        return self.effective_from <= today and (
            self.effective_to is None or today < self.effective_to
        )

    @property
    def duration_days(self) -> int:
        """Number of days this price is effective."""
        end = self.effective_to or date.today()
        return (end - self.effective_from).days

    def is_effective_on(self, on_date: date) -> bool:
        """Check if this price is effective on a specific date."""
        return self.effective_from <= on_date and (
            self.effective_to is None or on_date < self.effective_to
        )

    def overlaps_with(self, other: PriceRecord) -> bool:
        """Check if this price's effective range overlaps with another."""
        self_end = self.effective_to
        other_end = other.effective_to
        if self_end is None and other_end is None:
            return True
        if self_end is None:
            return other_end is not None and other_end > self.effective_from
        if other_end is None:
            return self_end > other.effective_from
        return self.effective_from < other_end and other.effective_from < self_end


@dataclass(frozen=True)
class PriceVersion:
    """A versioned collection of price records for the same item.

    Attributes:
        item_code: The item this version group belongs to.
        records: List of price records in this version group.
        version: Version identifier.
        created_at: When this version was created.
        created_by: Who created this version.
        notes: Optional version notes.
    """

    item_code: str
    records: tuple[PriceRecord, ...]
    version: str = "1"
    created_at: Optional[date] = None
    created_by: Optional[str] = None
    notes: str = ""

    @property
    def latest(self) -> Optional[PriceRecord]:
        """The most recent record by effective_from date."""
        if not self.records:
            return None
        return max(self.records, key=lambda r: r.effective_from)

    @property
    def earliest(self) -> Optional[PriceRecord]:
        """The earliest record by effective_from date."""
        if not self.records:
            return None
        return min(self.records, key=lambda r: r.effective_from)

    @property
    def approved_records(self) -> list[PriceRecord]:
        """All approved records in this version."""
        return [r for r in self.records if r.status == PriceStatus.APPROVED]

    @property
    def is_active(self) -> bool:
        """True if any record in this version is currently active."""
        return any(r.is_active for r in self.records)


@dataclass(frozen=True)
class PriceQuery:
    """Query parameters for looking up prices.

    Attributes:
        item_code: Filter by item code (exact match).
        geography: Filter by geography (exact match).
        category: Filter by category (exact match).
        effective_on: Find prices effective on this date.
        effective_after: Find prices effective on or after this date.
        effective_before: Find prices effective before this date.
        status: Filter by status.
        currency: Filter by currency.
        delivery_basis: Filter by delivery basis.
        price_basis: Filter by price basis.
        source_kind: Filter by source kind.
        min_confidence: Minimum confidence threshold.
        include_expired: Include expired records in results.
        include_drafts: Include draft records in results.
        limit: Maximum number of results.
    """

    item_code: Optional[str] = None
    geography: Optional[str] = None
    category: Optional[str] = None
    effective_on: Optional[date] = None
    effective_after: Optional[date] = None
    effective_before: Optional[date] = None
    status: Optional[PriceStatus] = None
    currency: Optional[str] = None
    delivery_basis: Optional[str] = None
    price_basis: Optional[str] = None
    source_kind: Optional[str] = None
    min_confidence: Optional[Decimal] = None
    include_expired: bool = False
    include_drafts: bool = False
    limit: int = 100

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > 10000:
            raise ValueError("limit must be between 1 and 10000")
        if self.min_confidence is not None:
            if not (MIN_CONFIDENCE <= self.min_confidence <= MAX_CONFIDENCE):
                raise ValueError("min_confidence must be between 0 and 1")


@dataclass
class PriceLookupResult:
    """Result of a price lookup.

    Attributes:
        records: Matching price records.
        total_found: Total matches before limit.
        query: The query that produced this result.
        execution_permitted: Always False (read-only engine).
    """

    records: list[PriceRecord]
    total_found: int
    query: PriceQuery
    execution_permitted: bool = False


@dataclass
class PriceVariance:
    """Variance analysis between two price records.

    Attributes:
        baseline: The baseline price record.
        comparison: The comparison price record.
        absolute_change: Absolute price difference.
        percent_change: Percentage change from baseline.
        annualized_change: Annualized change rate.
        is_increase: True if price increased.
        is_decrease: True if price decreased.
    """

    baseline: PriceRecord
    comparison: PriceRecord
    absolute_change: Decimal
    percent_change: Optional[Decimal]
    annualized_change: Optional[Decimal]
    is_increase: bool
    is_decrease: bool


@dataclass
class PriceSummary:
    """Summary statistics for a collection of price records.

    Attributes:
        item_code: Item code for this summary.
        record_count: Number of records.
        approved_count: Number of approved records.
        min_price: Minimum unit price.
        max_price: Maximum unit price.
        mean_price: Mean unit price.
        median_price: Median unit price.
        currency: Currency for all records.
        earliest_effective: Earliest effective date.
        latest_effective: Latest effective date.
        current_price: Currently active price, if any.
        price_range: (min, max) tuple.
    """

    item_code: str
    record_count: int
    approved_count: int
    min_price: Optional[Decimal]
    max_price: Optional[Decimal]
    mean_price: Optional[Decimal]
    median_price: Optional[Decimal]
    currency: str
    earliest_effective: Optional[date]
    latest_effective: Optional[date]
    current_price: Optional[PriceRecord]
    price_range: Optional[tuple[Decimal, Decimal]]


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _round_price(value: Decimal) -> Decimal:
    """Round a price to standard precision."""
    return value.quantize(PRICE_PRECISION, rounding=ROUND_HALF_UP)


def _validate_item_code(item_code: str) -> str:
    """Validate and normalize an item code."""
    if not isinstance(item_code, str) or not item_code.strip():
        raise ValueError("item_code must be a non-empty string")
    code = item_code.strip()
    if len(code) > 120:
        raise ValueError("item_code must be at most 120 characters")
    return code


def _validate_date(value: Any, name: str) -> date:
    """Validate and convert a date value."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{name} must be a valid ISO date (YYYY-MM-DD)") from exc
    raise ValueError(f"{name} must be a date or ISO date string")


def _validate_decimal(value: Any, name: str, min_val: Optional[Decimal] = None, max_val: Optional[Decimal] = None) -> Decimal:
    """Validate and convert a decimal value."""
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be a valid number") from exc
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    if min_val is not None and result < min_val:
        raise ValueError(f"{name} must be >= {min_val}")
    if max_val is not None and result > max_val:
        raise ValueError(f"{name} must be <= {max_val}")
    return result


# ---------------------------------------------------------------------------
# Price Engine
# ---------------------------------------------------------------------------


class PriceEngine:
    """Effective-dated price management engine.

    Provides in-memory storage and querying of versioned price records.
    All operations are pure computation—no I/O or persistence.

    Example:
        engine = PriceEngine()
        engine.add_price(price_record)
        result = engine.query(PriceQuery(item_code="UPS-500K", effective_on=date.today()))
    """

    def __init__(self) -> None:
        self._records: dict[str, PriceRecord] = {}
        self._versions: dict[str, PriceVersion] = {}
        self._item_index: dict[str, set[str]] = {}
        self._geography_index: dict[str, set[str]] = {}
        self._category_index: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # Record management
    # ------------------------------------------------------------------

    def add_price(self, record: PriceRecord) -> PriceRecord:
        """Add a price record to the engine.

        Args:
            record: The price record to add.

        Returns:
            The added record.

        Raises:
            ValueError: If a record with the same identity already exists.
        """
        key = self._record_key(record)
        if key in self._records:
            raise ValueError(
                f"price record already exists for {record.item_code} "
                f"effective {record.effective_from}"
            )

        self._records[key] = record
        self._index_record(record)
        self._update_versions(record)
        return record

    def add_prices(self, records: list[PriceRecord]) -> list[PriceRecord]:
        """Add multiple price records.

        Args:
            records: List of price records to add.

        Returns:
            List of added records.
        """
        return [self.add_price(r) for r in records]

    def get_price(self, item_code: str, effective_from: date) -> Optional[PriceRecord]:
        """Get a specific price record by item code and effective date.

        Args:
            item_code: The item code.
            effective_from: The effective start date.

        Returns:
            The matching record, or None.
        """
        key = f"{item_code}|{effective_from.isoformat()}"
        return self._records.get(key)

    def supersede_price(
        self,
        item_code: str,
        effective_from: date,
        new_record: PriceRecord,
    ) -> PriceRecord:
        """Supersede an existing price record with a new one.

        The old record's status is set to SUPERSEDED and its effective_to
        is set to the new record's effective_from.

        Args:
            item_code: Item code of the record to supersede.
            effective_from: Effective date of the record to supersede.
            new_record: The new price record.

        Returns:
            The new record.

        Raises:
            ValueError: If the old record doesn't exist.
        """
        old_key = f"{item_code}|{effective_from.isoformat()}"
        old_record = self._records.get(old_key)
        if old_record is None:
            raise ValueError(
                f"no price record found for {item_code} effective {effective_from}"
            )

        # Mark old record as superseded
        superseded = PriceRecord(
            **{
                **old_record.__dict__,
                "status": PriceStatus.SUPERSEDED,
                "effective_to": new_record.effective_from,
                "superseded_by": f"{new_record.item_code}|{new_record.effective_from.isoformat()}",
            }
        )
        self._records[old_key] = superseded

        # Add new record
        return self.add_price(new_record)

    def expire_price(self, item_code: str, effective_from: date, as_of: Optional[date] = None) -> Optional[PriceRecord]:
        """Mark a price record as expired.

        Args:
            item_code: Item code of the record to expire.
            effective_from: Effective date of the record to expire.
            as_of: Date to set as effective_to (defaults to today).

        Returns:
            The expired record, or None if not found.
        """
        key = f"{item_code}|{effective_from.isoformat()}"
        record = self._records.get(key)
        if record is None:
            return None

        expire_date = as_of or date.today()
        expired = PriceRecord(
            **{
                **record.__dict__,
                "status": PriceStatus.EXPIRED,
                "effective_to": expire_date,
            }
        )
        self._records[key] = expired
        return expired

    def approve_price(self, item_code: str, effective_from: date) -> Optional[PriceRecord]:
        """Approve a draft price record.

        Args:
            item_code: Item code of the record to approve.
            effective_from: Effective date of the record to approve.

        Returns:
            The approved record, or None if not found.

        Raises:
            ValueError: If the record is not in draft status.
        """
        key = f"{item_code}|{effective_from.isoformat()}"
        record = self._records.get(key)
        if record is None:
            return None
        if record.status != PriceStatus.DRAFT:
            raise ValueError(
                f"cannot approve record with status {record.status.value}"
            )

        approved = PriceRecord(
            **{**record.__dict__, "status": PriceStatus.APPROVED}
        )
        self._records[key] = approved
        return approved

    def reject_price(self, item_code: str, effective_from: date) -> Optional[PriceRecord]:
        """Reject a draft price record.

        Args:
            item_code: Item code of the record to reject.
            effective_from: Effective date of the record to reject.

        Returns:
            The rejected record, or None if not found.
        """
        key = f"{item_code}|{effective_from.isoformat()}"
        record = self._records.get(key)
        if record is None:
            return None

        rejected = PriceRecord(
            **{**record.__dict__, "status": PriceStatus.REJECTED}
        )
        self._records[key] = rejected
        return rejected

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def query(self, query: PriceQuery) -> PriceLookupResult:
        """Query price records.

        Args:
            query: Query parameters.

        Returns:
            PriceLookupResult with matching records.
        """
        candidates: list[PriceRecord] = []

        # Use index for item_code if available
        if query.item_code and query.item_code in self._item_index:
            keys = self._item_index[query.item_code]
            candidates = [self._records[k] for k in keys if k in self._records]
        else:
            candidates = list(self._records.values())

        # Apply filters
        results: list[PriceRecord] = []
        for record in candidates:
            if not self._matches(record, query):
                continue
            results.append(record)

        # Sort by effective_from descending (most recent first)
        results.sort(key=lambda r: r.effective_from, reverse=True)

        total_found = len(results)
        return PriceLookupResult(
            records=results[: query.limit],
            total_found=total_found,
            query=query,
        )

    def get_current_price(
        self,
        item_code: str,
        geography: Optional[str] = None,
        as_of: Optional[date] = None,
    ) -> Optional[PriceRecord]:
        """Get the currently active approved price for an item.

        Args:
            item_code: The item code.
            geography: Optional geography filter.
            as_of: Date to check (defaults to today).

        Returns:
            The current active price, or None.
        """
        check_date = as_of or date.today()
        query = PriceQuery(
            item_code=item_code,
            geography=geography,
            effective_on=check_date,
            status=PriceStatus.APPROVED,
            limit=1,
        )
        result = self.query(query)
        return result.records[0] if result.records else None

    def get_price_history(
        self,
        item_code: str,
        geography: Optional[str] = None,
    ) -> list[PriceRecord]:
        """Get the full price history for an item.

        Args:
            item_code: The item code.
            geography: Optional geography filter.

        Returns:
            List of price records sorted by effective_from descending.
        """
        query = PriceQuery(
            item_code=item_code,
            geography=geography,
            include_expired=True,
            include_drafts=True,
            limit=10000,
        )
        result = self.query(query)
        return result.records

    def find_overlaps(self, record: PriceRecord) -> list[PriceRecord]:
        """Find records that overlap with the given record's effective range.

        Args:
            record: The record to check.

        Returns:
            List of overlapping records.
        """
        overlaps: list[PriceRecord] = []
        for other in self._records.values():
            if other.item_code != record.item_code:
                continue
            if other.effective_from == record.effective_from:
                continue  # Same record
            if record.overlaps_with(other):
                overlaps.append(other)
        return overlaps

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def compare_prices(
        self,
        baseline: PriceRecord,
        comparison: PriceRecord,
    ) -> PriceVariance:
        """Compare two price records and compute variance.

        Args:
            baseline: The baseline price record.
            comparison: The comparison price record.

        Returns:
            PriceVariance with analysis results.

        Raises:
            ValueError: If records have different currencies.
        """
        if baseline.currency != comparison.currency:
            raise ValueError("cannot compare prices with different currencies")

        base_price = baseline.normalized_unit_price or Decimal("0")
        comp_price = comparison.normalized_unit_price or Decimal("0")
        abs_change = comp_price - base_price

        if base_price == 0:
            pct_change = None
        else:
            pct_change = _round_price(
                (abs_change / base_price) * Decimal("100")
            )

        # Annualized change
        days_between = (comparison.effective_from - baseline.effective_from).days
        if days_between > 0 and pct_change is not None:
            years = Decimal(days_between) / Decimal("365.25")
            annualized = _round_price(pct_change / years)
        else:
            annualized = None

        return PriceVariance(
            baseline=baseline,
            comparison=comparison,
            absolute_change=_round_price(abs_change),
            percent_change=pct_change,
            annualized_change=annualized,
            is_increase=abs_change > 0,
            is_decrease=abs_change < 0,
        )

    def summarize(
        self,
        item_code: str,
        geography: Optional[str] = None,
    ) -> Optional[PriceSummary]:
        """Generate summary statistics for an item's prices.

        Args:
            item_code: The item code.
            geography: Optional geography filter.

        Returns:
            PriceSummary, or None if no records found.
        """
        records = self.get_price_history(item_code, geography)
        if not records:
            return None

        approved = [r for r in records if r.status == PriceStatus.APPROVED]
        prices = [r.normalized_unit_price for r in approved if r.normalized_unit_price is not None]

        if not prices:
            return PriceSummary(
                item_code=item_code,
                record_count=len(records),
                approved_count=0,
                min_price=None,
                max_price=None,
                mean_price=None,
                median_price=None,
                currency=records[0].currency,
                earliest_effective=min(r.effective_from for r in records),
                latest_effective=max(r.effective_from for r in records),
                current_price=None,
                price_range=None,
            )

        sorted_prices = sorted(prices)
        n = len(sorted_prices)
        mean_price = _round_price(sum(prices) / Decimal(n))
        if n % 2 == 0:
            median_price = _round_price(
                (sorted_prices[n // 2 - 1] + sorted_prices[n // 2]) / Decimal("2")
            )
        else:
            median_price = sorted_prices[n // 2]

        current = self.get_current_price(item_code, geography)

        return PriceSummary(
            item_code=item_code,
            record_count=len(records),
            approved_count=len(approved),
            min_price=min(prices),
            max_price=max(prices),
            mean_price=mean_price,
            median_price=median_price,
            currency=records[0].currency,
            earliest_effective=min(r.effective_from for r in records),
            latest_effective=max(r.effective_from for r in records),
            current_price=current,
            price_range=(min(prices), max(prices)),
        )

    def detect_price_changes(
        self,
        item_code: str,
        threshold_pct: Decimal = Decimal("5"),
        geography: Optional[str] = None,
    ) -> list[PriceVariance]:
        """Detect significant price changes for an item.

        Args:
            item_code: The item code.
            threshold_pct: Minimum percentage change to report.
            geography: Optional geography filter.

        Returns:
            List of PriceVariance for changes exceeding the threshold.
        """
        records = self.get_price_history(item_code, geography)
        approved = [r for r in records if r.status == PriceStatus.APPROVED]
        approved.sort(key=lambda r: r.effective_from)

        changes: list[PriceVariance] = []
        for i in range(1, len(approved)):
            variance = self.compare_prices(approved[i - 1], approved[i])
            if variance.percent_change is not None and abs(variance.percent_change) >= threshold_pct:
                changes.append(variance)

        return changes

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def bulk_approve(self, item_codes: list[str]) -> dict[str, int]:
        """Approve all draft prices for the given item codes.

        Args:
            item_codes: List of item codes to approve.

        Returns:
            Dict mapping item codes to count of approved records.
        """
        results: dict[str, int] = {}
        for code in item_codes:
            count = 0
            if code in self._item_index:
                for key in self._item_index[code]:
                    record = self._records.get(key)
                    if record and record.status == PriceStatus.DRAFT:
                        self.approve_price(code, record.effective_from)
                        count += 1
            results[code] = count
        return results

    def bulk_expire(self, as_of: Optional[date] = None) -> int:
        """Expire all approved prices that have passed their effective_to date.

        Args:
            as_of: Date to check against (defaults to today).

        Returns:
            Number of records expired.
        """
        check_date = as_of or date.today()
        count = 0
        for key, record in list(self._records.items()):
            if (record.status == PriceStatus.APPROVED
                    and record.effective_to is not None
                    and record.effective_to <= check_date):
                self.expire_price(record.item_code, record.effective_from, check_date)
                count += 1
        return count

    def get_all_items(self) -> list[str]:
        """Get all item codes in the engine."""
        return sorted(self._item_index.keys())

    def get_all_geographies(self) -> list[str]:
        """Get all geographies in the engine."""
        return sorted(self._geography_index.keys())

    def get_all_categories(self) -> list[str]:
        """Get all categories in the engine."""
        return sorted(self._category_index.keys())

    @property
    def record_count(self) -> int:
        """Total number of price records."""
        return len(self._records)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize all records to a dict."""
        return {
            "record_count": self.record_count,
            "items": self.get_all_items(),
            "geographies": self.get_all_geographies(),
            "categories": self.get_all_categories(),
            "records": [
                {
                    "item_code": r.item_code,
                    "description": r.description,
                    "category": r.category,
                    "unit_price": str(r.unit_price),
                    "currency": r.currency,
                    "quantity_unit": r.quantity_unit,
                    "geography": r.geography,
                    "delivery_basis": r.delivery_basis,
                    "effective_from": r.effective_from.isoformat(),
                    "effective_to": r.effective_to.isoformat() if r.effective_to else None,
                    "status": r.status.value,
                    "price_basis": r.price_basis,
                    "source_kind": r.source_kind,
                    "source_name": r.source_name,
                    "source_ref": r.source_ref,
                    "confidence": str(r.confidence),
                    "fx_to_book": str(r.fx_to_book),
                    "normalized_unit_price": str(r.normalized_unit_price) if r.normalized_unit_price else None,
                    "version": r.version,
                    "is_active": r.is_active,
                }
                for r in sorted(self._records.values(), key=lambda x: (x.item_code, x.effective_from))
            ],
            "execution_permitted": False,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_key(self, record: PriceRecord) -> str:
        """Generate a unique key for a price record."""
        return f"{record.item_code}|{record.effective_from.isoformat()}"

    def _index_record(self, record: PriceRecord) -> None:
        """Add a record to all indexes."""
        key = self._record_key(record)

        if record.item_code not in self._item_index:
            self._item_index[record.item_code] = set()
        self._item_index[record.item_code].add(key)

        if record.geography not in self._geography_index:
            self._geography_index[record.geography] = set()
        self._geography_index[record.geography].add(key)

        if record.category not in self._category_index:
            self._category_index[record.category] = set()
        self._category_index[record.category].add(key)

    def _update_versions(self, record: PriceRecord) -> None:
        """Update version tracking for a record."""
        if record.item_code not in self._versions:
            self._versions[record.item_code] = PriceVersion(
                item_code=record.item_code,
                records=(record,),
                version=record.version,
            )
        else:
            existing = self._versions[record.item_code]
            self._versions[record.item_code] = PriceVersion(
                item_code=record.item_code,
                records=existing.records + (record,),
                version=record.version,
            )

    def _matches(self, record: PriceRecord, query: PriceQuery) -> bool:
        """Check if a record matches the query filters."""
        if query.item_code and record.item_code != query.item_code:
            return False
        if query.geography and record.geography != query.geography:
            return False
        if query.category and record.category != query.category:
            return False
        if query.status and record.status != query.status:
            return False
        if query.currency and record.currency != query.currency:
            return False
        if query.delivery_basis and record.delivery_basis != query.delivery_basis:
            return False
        if query.price_basis and record.price_basis != query.price_basis:
            return False
        if query.source_kind and record.source_kind != query.source_kind:
            return False
        if query.min_confidence is not None and record.confidence < query.min_confidence:
            return False

        if query.effective_on and not record.is_effective_on(query.effective_on):
            return False
        if query.effective_after and record.effective_from < query.effective_after:
            return False
        if query.effective_before:
            if record.effective_to is not None and record.effective_to >= query.effective_before:
                return False
            if record.effective_from >= query.effective_before:
                return False

        if not query.include_expired and record.status == PriceStatus.EXPIRED:
            return False
        if not query.include_drafts and record.status == PriceStatus.DRAFT:
            return False

        return True


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def create_price_record(
    *,
    item_code: str,
    description: str,
    category: str,
    unit_price: float | Decimal | str,
    currency: str,
    quantity_unit: str,
    geography: str,
    delivery_basis: str = DeliveryBasis.DELIVERED.value,
    effective_from: date | str,
    effective_to: Optional[date | str] = None,
    status: str | PriceStatus = PriceStatus.DRAFT.value,
    price_basis: str = PriceBasis.BUDGETARY.value,
    source_kind: str = "manual",
    source_name: str = "",
    source_ref: str = "",
    source_digest: Optional[str] = None,
    confidence: float | Decimal | str = 1.0,
    fx_to_book: float | Decimal | str = 1.0,
    currency_basis_date: Optional[date | str] = None,
    book_currency: Optional[str] = None,
    version: str = "1",
    observed_at: Optional[date | str] = None,
    provenance: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> PriceRecord:
    """Create a PriceRecord with validation.

    Convenience factory that handles type conversion and validation.
    """
    eff_from = _validate_date(effective_from, "effective_from")
    eff_to = _validate_date(effective_to, "effective_to") if effective_to else None
    basis_date = _validate_date(currency_basis_date, "currency_basis_date") if currency_basis_date else None
    obs_at = _validate_date(observed_at, "observed_at") if observed_at else None

    if isinstance(status, str):
        status = PriceStatus(status)

    return PriceRecord(
        item_code=_validate_item_code(item_code),
        description=description,
        category=category,
        unit_price=_validate_decimal(unit_price, "unit_price", Decimal("0"), MAX_PRICE_VALUE),
        currency=currency,
        quantity_unit=quantity_unit,
        geography=geography,
        delivery_basis=delivery_basis,
        effective_from=eff_from,
        effective_to=eff_to,
        status=status,
        price_basis=price_basis,
        source_kind=source_kind,
        source_name=source_name,
        source_ref=source_ref,
        source_digest=source_digest,
        confidence=_validate_decimal(confidence, "confidence", MIN_CONFIDENCE, MAX_CONFIDENCE),
        fx_to_book=_validate_decimal(fx_to_book, "fx_to_book", Decimal("0.000001"), MAX_FX_RATE),
        currency_basis_date=basis_date,
        book_currency=book_currency,
        version=version,
        observed_at=obs_at,
        provenance=provenance or {},
        metadata=metadata or {},
    )


def compute_price_at_date(
    records: list[PriceRecord],
    on_date: date,
) -> Optional[PriceRecord]:
    """Find the price record effective on a specific date.

    If multiple records are effective, returns the one with the latest
    effective_from date.

    Args:
        records: List of price records to search.
        on_date: The date to check.

    Returns:
        The effective price record, or None.
    """
    candidates = [r for r in records if r.is_effective_on(on_date)]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.effective_from)


def compute_weighted_average_price(
    records: list[PriceRecord],
    weights: Optional[list[Decimal]] = None,
) -> Optional[Decimal]:
    """Compute the weighted average price across records.

    Args:
        records: List of price records.
        weights: Optional weights (defaults to equal weighting).

    Returns:
        Weighted average price, or None if no records.
    """
    if not records:
        return None

    prices = [r.normalized_unit_price for r in records if r.normalized_unit_price is not None]
    if not prices:
        return None

    if weights is None:
        return _round_price(sum(prices) / Decimal(len(prices)))

    if len(weights) != len(prices):
        raise ValueError("weights must match records length")

    total_weight = sum(weights)
    if total_weight == 0:
        return _round_price(sum(prices) / Decimal(len(prices)))

    weighted_sum = sum(p * w for p, w in zip(prices, weights))
    return _round_price(weighted_sum / total_weight)


def compute_escalated_price(
    base_price: Decimal,
    escalation_rate: Decimal,
    periods: int,
    period_months: int = 12,
) -> Decimal:
    """Compute an escalated future price.

    Args:
        base_price: Starting price.
        escalation_rate: Escalation rate per period (e.g., 0.03 for 3%).
        periods: Number of periods to escalate.
        period_months: Months per period (default 12 for annual).

    Returns:
        Escalated price.
    """
    if base_price < 0:
        raise ValueError("base_price must be non-negative")
    if escalation_rate < -1:
        raise ValueError("escalation_rate must be >= -1")
    if periods < 0:
        raise ValueError("periods must be non-negative")
    if period_months < 1:
        raise ValueError("period_months must be positive")

    return _round_price(base_price * (Decimal("1") + escalation_rate) ** periods)


def compute_price_index(
    base_records: list[PriceRecord],
    comparison_records: list[PriceRecord],
) -> Optional[Decimal]:
    """Compute a price index (Laspeyres-style) between two periods.

    Args:
        base_records: Base period price records.
        comparison_records: Comparison period price records.

    Returns:
        Price index (100 = no change), or None if not computable.
    """
    if not base_records or not comparison_records:
        return None

    base_prices = [r.normalized_unit_price or Decimal("0") for r in base_records]
    comp_prices = [r.normalized_unit_price or Decimal("0") for r in comparison_records]

    if not base_prices or not comp_prices:
        return None

    base_avg = sum(base_prices) / Decimal(len(base_prices))
    comp_avg = sum(comp_prices) / Decimal(len(comp_prices))

    if base_avg == 0:
        return None

    return _round_price((comp_avg / base_avg) * Decimal("100"))
