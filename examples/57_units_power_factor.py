"""Example: Power factor conversion.

Converts between real power (kW), apparent power (kVA), and power factor.
"""
from dcc.validation.units import convert_with_power_factor

# Given 800 kW at 0.95 power factor, find kVA
result = convert_with_power_factor(
    value=800,
    from_unit="kW",
    to_unit="kVA",
    power_factor=0.95,
)
print(f"800 kW at 0.95 PF = {result.value:.1f} {result.unit.symbol}")
