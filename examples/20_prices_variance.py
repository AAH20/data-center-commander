"""Example: Price variance analysis.

Compares observed prices against a benchmark to detect outliers.
"""
from dcc.economics.prices import PriceEngine, create_price_record

engine = PriceEngine()
baseline = create_price_record(
    item_code="CABLE-CAT6A",
    description="Cat6A Cable",
    category="network",
    quantity_unit="meter",
    unit_price=100,
    currency="USD",
    geography="US-East",
    price_basis="benchmark",
    source_name="Benchmark",
    source_ref="BENCH-001",
    effective_from="2026-01-01",
    confidence=0.95,
)
engine.add_price(baseline)
for i, (price, conf) in enumerate([(105, 0.8), (98, 0.85), (150, 0.3)]):
    comparison = create_price_record(
        item_code="CABLE-CAT6A",
        description="Cat6A Cable",
        category="network",
        quantity_unit="meter",
        unit_price=price,
        currency="USD",
        geography="US-East",
        price_basis="quoted",
        source_name="Vendor",
        source_ref=f"REF-{price}",
        effective_from=f"2026-0{i+2}-01",
        confidence=conf,
    )
    engine.add_price(comparison)
    variance = engine.compare_prices(baseline, comparison)
    print(f"  vs ${price}: change={variance.percent_change:.1%}, increase={variance.is_increase}")
