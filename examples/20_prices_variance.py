"""Example: Price variance analysis.

Compares observed prices against a benchmark to detect outliers.
"""
from dcc.economics.prices import PriceEngine, PriceVariance

engine = PriceEngine()
# Add multiple observations for the same item
for price, conf in [(100, 0.9), (105, 0.8), (98, 0.85), (150, 0.3)]:
    engine.add_record(create_price_record(
        item_code="CABLE-CAT6A",
        description="Cat6A Cable",
        category="network",
        quantity_unit="meter",
        unit_price=price,
        currency="USD",
        basis=PriceBasis.VENDOR_API,
        source_name="Vendor",
        source_ref=f"REF-{price}",
        effective_from="2026-01-01",
        confidence=conf,
    ))
variance = engine.compute_variance("CABLE-CAT6A")
print(f"Mean: ${variance.mean:.2f}")
print(f"Std dev: ${variance.std_dev:.2f}")
print(f"CV: {variance.cv:.2%}")
