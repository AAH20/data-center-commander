"""Example: Weighted average price across multiple observations.

Computes a confidence-weighted average from multiple price sources.
"""
from dcc.economics.prices import compute_weighted_average_price, create_price_record

records = [
    create_price_record(
        item_code="CABLE-CAT6A", description="Cat6A Cable", category="network",
        quantity_unit="meter", unit_price=100, currency="USD", geography="US-East",
        price_basis="quoted", source_name="Vendor A", source_ref="A-1",
        effective_from="2026-01-01", confidence=0.9,
    ),
    create_price_record(
        item_code="CABLE-CAT6A", description="Cat6A Cable", category="network",
        quantity_unit="meter", unit_price=110, currency="USD", geography="US-East",
        price_basis="quoted", source_name="Vendor B", source_ref="B-1",
        effective_from="2026-01-01", confidence=0.7,
    ),
    create_price_record(
        item_code="CABLE-CAT6A", description="Cat6A Cable", category="network",
        quantity_unit="meter", unit_price=95, currency="USD", geography="US-East",
        price_basis="quoted", source_name="Vendor C", source_ref="C-1",
        effective_from="2026-01-01", confidence=0.8,
    ),
]
result = compute_weighted_average_price(records)
print(f"Weighted avg: ${result:.2f}")
