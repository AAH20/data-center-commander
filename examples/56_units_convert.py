"""Example: Unit conversion with precision tracking.

Converts between units of the same dimension.
"""
from decimal import Decimal
from dcc.validation.units import convert, get_registry, convert_temperature

registry = get_registry()
# Convert 5000 kW to MW
result = convert(Decimal("5000"), "MW", source_unit="kW")
print(f"5000 kW = {result.value} {result.unit.symbol}")

# Convert temperature
temp_f = convert_temperature(25, "C", "F")
print(f"25°C = {temp_f.value}°F")
