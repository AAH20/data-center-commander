"""Example: Price lookup by item and date.

Queries the price engine for the applicable price at a point in time.
"""
from dcc.economics.prices import PriceEngine, PriceQuery, PriceStatus

engine = PriceEngine()
engine.add_record(create_price_record(
    item_code="SERVER-R760",
    description="Dell R760 Server",
    category="it",
    quantity_unit="unit",
    unit_price=15_000,
    currency="USD",
    basis=PriceBasis.CONTRACT,
    source_name="Dell Contract",
    source_ref="DELL-2026",
    effective_from="2026-01-01",
    effective_to="2026-12-31",
    confidence=0.95,
))
query = PriceQuery(item_code="SERVER-R760", date="2026-06-15", currency="USD")
result = engine.lookup(query)
print(f"Found: {result.found}")
if result.found:
    print(f"Price: ${result.price:,.2f}")
    print(f"Status: {result.status}")
