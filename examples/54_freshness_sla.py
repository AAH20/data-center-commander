"""Example: Data freshness SLA evaluation.

Checks if data sources meet their freshness SLAs.
"""
from dcc.quality.freshness import evaluate_sla

# Check telemetry freshness (1 hour SLA)
status = evaluate_sla(age_hours=0.5, sla_hours=1)
print(f"Telemetry (0.5h old): {status}")

# Check KPI freshness (26 hour SLA)
status = evaluate_sla(age_hours=30, sla_hours=26)
print(f"KPIs (30h old): {status}")

# Warning at 80% of SLA
status = evaluate_sla(age_hours=21, sla_hours=26)
print(f"KPIs (21h old, 80% of SLA): {status}")
