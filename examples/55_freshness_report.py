"""Example: Freshness report for multiple sources.

Aggregates freshness status across all data sources.
"""
from dcc.quality.freshness import FreshnessReport, SourceFreshness

report = FreshnessReport(
    tenant_id="tenant-1",
    checked_at="2026-01-15T12:00:00Z",
    sources=[
        SourceFreshness(source="telemetry", table="telemetry_readings", latest_timestamp="2026-01-15T11:30:00Z", age_hours=0.5, sla_hours=1, status="ok"),
        SourceFreshness(source="kpis", table="kpi_observations", latest_timestamp="2026-01-14T10:00:00Z", age_hours=26, sla_hours=26, status="violation"),
        SourceFreshness(source="prices", table="price_observations", latest_timestamp="2026-01-13T00:00:00Z", age_hours=60, sla_hours=72, status="warning"),
    ],
)
print(f"Overall: {report.overall_status}")
print(f"Violations: {report.violations}")
print(f"Warnings: {report.warnings}")
