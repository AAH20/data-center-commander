"""Unit tests for dcc.quality.freshness module."""
import unittest
import datetime as dt

from dcc.quality.freshness import (
    SourceFreshness,
    FreshnessReport,
    DEFAULT_SLA_HOURS,
    PRICE_SOURCE_KIND_SLA_HOURS,
    evaluate_sla,
    get_source_freshness,
    build_freshness_report,
    check_freshness,
    format_freshness_report,
)


class TestSourceFreshness(unittest.TestCase):
    def test_creation(self):
        s = SourceFreshness(
            source="test",
            table="test_table",
            latest_timestamp="2024-01-01T00:00:00Z",
            age_hours=1.0,
            sla_hours=24,
            status="ok",
        )
        self.assertEqual(s.source, "test")
        self.assertEqual(s.table, "test_table")
        self.assertEqual(s.status, "ok")


class TestFreshnessReport(unittest.TestCase):
    def test_creation(self):
        r = FreshnessReport(tenant_id="t1", checked_at="2024-01-01T00:00:00Z")
        self.assertEqual(r.tenant_id, "t1")
        self.assertEqual(r.sources, [])
        self.assertEqual(r.overall_status, "ok")

    def test_with_sources(self):
        s = SourceFreshness(
            source="test",
            table="test_table",
            latest_timestamp="2024-01-01T00:00:00Z",
            age_hours=1.0,
            sla_hours=24,
            status="ok",
        )
        r = FreshnessReport(tenant_id="t1", checked_at="2024-01-01T00:00:00Z", sources=[s])
        self.assertEqual(len(r.sources), 1)


class TestDefaultSlaHours(unittest.TestCase):
    def test_telemetry_sla(self):
        self.assertEqual(DEFAULT_SLA_HOURS["telemetry_readings"], 1)

    def test_kpi_sla(self):
        self.assertEqual(DEFAULT_SLA_HOURS["kpi_observations"], 26)

    def test_all_sources_have_sla(self):
        self.assertGreater(len(DEFAULT_SLA_HOURS), 5)


class TestPriceSourceKindSlaHours(unittest.TestCase):
    def test_vendor_api(self):
        self.assertEqual(PRICE_SOURCE_KIND_SLA_HOURS["vendor_api"], 24)

    def test_contract(self):
        self.assertEqual(PRICE_SOURCE_KIND_SLA_HOURS["contract"], 720)


class TestEvaluateSla(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(evaluate_sla(1.0, 24), "ok")

    def test_warning(self):
        self.assertEqual(evaluate_sla(20.0, 24), "warning")

    def test_violation(self):
        self.assertEqual(evaluate_sla(25.0, 24), "violation")

    def test_no_data(self):
        self.assertEqual(evaluate_sla(None, 24), "no_data")

    def test_zero_rows(self):
        self.assertEqual(evaluate_sla(1.0, 24, row_count=0), "no_data")


class TestGetSourceFreshness(unittest.TestCase):
    def test_get_freshness(self):
        # This would need a mock connection in practice
        pass


class TestBuildFreshnessReport(unittest.TestCase):
    def test_build_report(self):
        # This would need a mock connection in practice
        pass


class TestCheckFreshness(unittest.TestCase):
    def test_check(self):
        # This would need a mock connection in practice
        pass


class TestFormatFreshnessReport(unittest.TestCase):
    def test_format(self):
        r = FreshnessReport(tenant_id="t1", checked_at="2024-01-01T00:00:00Z")
        # format_freshness_report returns structured data (dict), not a rendered
        # string; the name is about shaping the report, not formatting it for display.
        result = format_freshness_report(r)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["tenant_id"], "t1")


if __name__ == "__main__":
    unittest.main()
