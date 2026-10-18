"""Example: Create a versioned price record.

Demonstrates effective-dated price management.
"""
from dcc.economics.prices import create_price_record

record = create_price_record(
    item_code="UPS-250KVA",
    description="250 kVA UPS System",
    category="electrical",
    quantity_unit="system",
    unit_price=250_000,
    currency="USD",
    geography="US-East",
    price_basis="quoted",
    source_name="Vendor ABC",
    source_ref="Q-2026-001",
    effective_from="2026-01-01",
    effective_to="2026-12-31",
    confidence=0.9,
)
print(f"Item: {record.item_code}")
print(f"Price: ${record.unit_price:,.2f} {record.currency}")
print(f"Status: {record.status}")
print(f"Effective: {record.effective_from} to {record.effective_to}")
