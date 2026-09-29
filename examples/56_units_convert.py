"""Example: Unit conversion with precision tracking.

Converts between units of the same dimension.
"""
from dcc.validation.units import convert, get_registry

registry = get_registry()
# Convert 5000 kW to MW
result = convert(5000, "kW", "MW", registry=registry)
print(f"5000 kW = {result.value} {result.unit.symbol}")

# Convert temperature
temp_f = convert_temperature(25, "C", "F")
print(f"25°C = {temp_f.value}°F")
