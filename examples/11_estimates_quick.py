"""Example: Quick deployment estimate.

Uses quick_estimate for rapid bottom-up cost estimation.
"""
from dcc.economics.estimates import quick_estimate

result = quick_estimate(
    it_capacity_kw=2000,
    geography="US-East",
)
print(f"Total PV: ${result['total_pv_base']:,.2f}")
print(f"Line items: {result['line_count']}")
for phase in result["phase_subtotals"][:5]:
    print(f"  {phase['phase']}: ${phase['total_pv_base']:,.2f}")
