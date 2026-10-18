"""Example: Price lookup by item and date.

Queries the price engine for the applicable price at a point in time.
"""
from datetime import date
from dcc.economics.prices import PriceEngine, PriceQuery, create_price_record

engine = PriceEngine()
engine.add_price(create_price_record(
    item_code="SERVER-R760",
    description="Dell R760 Server",
    category="it",
    quantity_unit="unit",
    unit_price=15_000,
    currency="USD",
    geography="US-East",
    price_basis="contracted",
    source_name="Dell Contract",
    source_ref="DELL-2026",
    effective_from="2026-01-01",
    effective_to="2026-12-31",
    confidence=0.95,
))
query = PriceQuery(item_code="SERVER-R760", effective_on=date(2026, 6, 15), currency="USD")
result = engine.query(query)
print(f"Total found: {result.total_found}")
if result.records:
    print(f"Price: ${result.records[0].unit_price:,.2f}")
    print(f"Status: {result.records[0].status}")
