"""Example: Cost per rack-year and per m²-year.

Useful for comparing colocation vs. owned space economics.
"""
from dcc.economics.unit import cost_per_rack_year, cost_per_m2_year

rack = cost_per_rack_year(annual_cost=1_200_000, rack_count=300)
print(f"Per rack-year: ${rack.value:,.2f} [{rack.status}]")

m2 = cost_per_m2_year(annual_cost=1_200_000, area_m2=5000)
print(f"Per m²-year: ${m2.value:,.2f} [{m2.status}]")
