"""Tests for data freshness SLA monitoring."""
import datetime as dt
import unittest
from unittest.mock import MagicMock, patch

from dcc.quality.freshness import (
    DEFAULT_SLA_HOURS,
    PRICE_SOURCE_KIND_SLA_HOURS,
    FreshnessReport,
    SourceFreshness,
    build_freshness_report,
    check_freshness,
    evaluate_sla,
    format_freshness_report,
    get_source_freshness,
)


class EvaluateSLATests(unittest.TestCase):
    def test_no_data_when_age_is_none(self):
        self.assertEqual(evaluate_sla(None, 24), "no_data")

    def test_no_data_when_row_count_is_zero(self):
        self.assertEqual(evaluate_sla(1.0, 24, row_count=0), "no_data")

    def test_ok_when_within_sla(self):
        self.assertEqual(evaluate_sla(1.0, 24), "ok")

    def test_warning_at_80_percent(self):
        # 80% of 24 = 19.2, so 19.3 should be warning
        self.assertEqual(evaluate_sla(19.3, 24), "warning")

    def test_violation_when_exceeds_sla(self):
        self.assertEqual(evaluate_sla(25.0, 24), "violation")

    def test_boundary_exactly_at_sla_is_warning(self):
        # At exactly 100% of SLA, it's > 80% so warning
        self.assertEqual(evaluate_sla(24.0, 24), "warning")

    def test_boundary_exactly_at_80_percent_is_ok(self):
        # Exactly 80% should still be ok (not > 80%)
        self.assertEqual(evaluate_sla(19.2, 24), "ok")


class BuildFreshnessReportTests(unittest.TestCase):
    def test_overall_ok_when_all_sources_ok(self):
        sources = [
            SourceFreshness("t1", "table1", "2026-01-01", 1.0, 24, "ok", 10),
            SourceFreshness("t2", "table2", "2026-01-01", 2.0, 48, "ok", 5),
        ]
        report = build_freshness_report("tenant-1", sources)
        self.assertEqual(report.overall_status, "ok")
        self.assertEqual(report.violations, [])
        self.assertEqual(report.warnings, [])

    def test_overall_warning_when_any_warning(self):
        sources = [
            SourceFreshness("t1", "table1", "2026-01-01", 1.0, 24, "ok", 10),
            SourceFreshness("t2", "table2", "2026-01-01", 20.0, 24, "warning", 5),
        ]
        report = build_freshness_report("tenant-1", sources)
        self.assertEqual(report.overall_status, "warning")
        self.assertEqual(report.warnings, ["t2"])

    def test_overall_violation_when_any_violation(self):
        sources = [
            SourceFreshness("t1", "table1", "2026-01-01", 1.0, 24, "ok", 10),
            SourceFreshness("t2", "table2", "2026-01-01", 25.0, 24, "violation", 5),
            SourceFreshness("t3", "table3", "2026-01-01", 20.0, 24, "warning", 3),
        ]
        report = build_freshness_report("tenant-1", sources)
        self.assertEqual(report.overall_status, "violation")
        self.assertEqual(report.violations, ["t2"])
        self.assertEqual(report.warnings, ["t3"])

    def test_no_data_does_not_affect_overall(self):
        sources = [
            SourceFreshness("t1", "table1", None, None, 24, "no_data", 0),
        ]
        report = build_freshness_report("tenant-1", sources)
        self.assertEqual(report.overall_status, "ok")


class FormatFreshnessReportTests(unittest.TestCase):
    def test_format_includes_all_fields(self):
        sources = [
            SourceFreshness("t1", "table1", "2026-01-01T00:00:00+00:00", 1.5, 24, "ok", 10),
        ]
        report = FreshnessReport(
            tenant_id="tenant-1",
            checked_at="2026-01-02T00:00:00+00:00",
            sources=sources,
            overall_status="ok",
            violations=[],
            warnings=[],
        )
        result = format_freshness_report(report)
        self.assertEqual(result["tenant_id"], "tenant-1")
        self.assertEqual(result["overall_status"], "ok")
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["source"], "t1")
        self.assertEqual(result["sources"][0]["age_hours"], 1.5)
        self.assertFalse(result["execution_permitted"])


class GetSourceFreshnessTests(unittest.TestCase):
    def _make_pool(self, mock_conn):
        """Create a mock pool that returns the given connection."""
        pool = MagicMock()
        conn_ctx = MagicMock()
        conn_ctx.__enter__ = MagicMock(return_value=mock_conn)
        conn_ctx.__exit__ = MagicMock(return_value=False)
        pool.connection.return_value = conn_ctx
        return pool

    def test_queries_all_sources(self):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_conn.execute.return_value.fetchone.return_value = None

        pool = self._make_pool(mock_conn)
        now = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)
        results = get_source_freshness(pool, "tenant-1", now=now)

        # Should query: telemetry, kpi, capacity, prices, connectors, assets, cost_actuals, energy_allocations
        self.assertGreaterEqual(len(results), 8)
        source_names = [r.source for r in results]
        self.assertIn("telemetry_readings", source_names)
        self.assertIn("kpi_observations", source_names)
        self.assertIn("capacity_snapshots", source_names)
        self.assertIn("connectors", source_names)
        self.assertIn("assets", source_names)
        self.assertIn("cost_actuals", source_names)
        self.assertIn("energy_allocations", source_names)

    def test_telemetry_freshness_calculated_correctly(self):
        now = dt.datetime(2026, 1, 2, 12, 0, tzinfo=dt.timezone.utc)
        latest = dt.datetime(2026, 1, 2, 11, 0, tzinfo=dt.timezone.utc)  # 1 hour ago

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {
            "latest": latest,
            "row_count": 100,
        }

        pool = self._make_pool(mock_conn)
        results = get_source_freshness(pool, "tenant-1", now=now)

        telemetry = next(r for r in results if r.source == "telemetry_readings")
        assert telemetry.age_hours is not None
        self.assertAlmostEqual(telemetry.age_hours, 1.0, places=1)
        self.assertEqual(telemetry.status, "warning")  # SLA is 1 hour, age is 1 hour (>80%)

    def test_telemetry_violation_when_stale(self):
        now = dt.datetime(2026, 1, 2, 12, 0, tzinfo=dt.timezone.utc)
        latest = dt.datetime(2026, 1, 2, 10, 0, tzinfo=dt.timezone.utc)  # 2 hours ago

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {
            "latest": latest,
            "row_count": 100,
        }

        pool = self._make_pool(mock_conn)
        results = get_source_freshness(pool, "tenant-1", now=now)

        telemetry = next(r for r in results if r.source == "telemetry_readings")
        assert telemetry.age_hours is not None
        self.assertAlmostEqual(telemetry.age_hours, 2.0, places=1)
        self.assertEqual(telemetry.status, "violation")  # SLA is 1 hour

    def test_price_observations_split_by_source_kind(self):
        now = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)

        mock_conn = MagicMock()
        # First calls return empty for other sources, then price query returns rows
        def execute_side_effect(query, params=None):
            result = MagicMock()
            if "source_kind" in query:
                result.fetchall.return_value = [
                    {"source_kind": "vendor_api", "latest": dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc), "row_count": 50},
                    {"source_kind": "contract", "latest": dt.datetime(2025, 12, 1, tzinfo=dt.timezone.utc), "row_count": 10},
                ]
            else:
                result.fetchone.return_value = None
                result.fetchall.return_value = []
            return result

        mock_conn.execute.side_effect = execute_side_effect

        pool = self._make_pool(mock_conn)
        results = get_source_freshness(pool, "tenant-1", now=now)

        price_results = [r for r in results if r.source.startswith("price_observations:")]
        self.assertEqual(len(price_results), 2)
        vendor_api = next(r for r in price_results if "vendor_api" in r.source)
        contract = next(r for r in price_results if "contract" in r.source)
        self.assertEqual(vendor_api.sla_hours, PRICE_SOURCE_KIND_SLA_HOURS["vendor_api"])
        self.assertEqual(contract.sla_hours, PRICE_SOURCE_KIND_SLA_HOURS["contract"])

    def test_no_data_source(self):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_conn.execute.return_value.fetchall.return_value = []

        pool = self._make_pool(mock_conn)
        now = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)
        results = get_source_freshness(pool, "tenant-1", now=now)

        for r in results:
            self.assertEqual(r.status, "no_data")
            self.assertIsNone(r.latest_timestamp)
            self.assertEqual(r.row_count, 0)


class CheckFreshnessIntegrationTests(unittest.TestCase):
    def test_check_freshness_returns_report(self):
        now = dt.datetime(2026, 1, 2, 12, 0, tzinfo=dt.timezone.utc)
        latest = dt.datetime(2026, 1, 2, 11, 0, tzinfo=dt.timezone.utc)

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {
            "latest": latest,
            "row_count": 100,
        }
        mock_conn.execute.return_value.fetchall.return_value = []

        pool = MagicMock()
        conn_ctx = MagicMock()
        conn_ctx.__enter__ = MagicMock(return_value=mock_conn)
        conn_ctx.__exit__ = MagicMock(return_value=False)
        pool.connection.return_value = conn_ctx

        report = check_freshness(pool, "tenant-1", now=now)
        self.assertIsInstance(report, FreshnessReport)
        self.assertEqual(report.tenant_id, "tenant-1")
        self.assertIn(report.overall_status, ("ok", "warning", "violation"))
        self.assertGreater(len(report.sources), 0)


class SLADefaultsTests(unittest.TestCase):
    def test_all_expected_sources_have_slas(self):
        expected = {
            "telemetry_readings", "kpi_observations", "capacity_snapshots",
            "price_observations", "connectors", "assets", "cost_actuals",
            "energy_allocations",
        }
        self.assertEqual(set(DEFAULT_SLA_HOURS.keys()), expected)

    def test_price_source_kind_slas_defined(self):
        expected_kinds = {
            "vendor_api", "vendor_quote", "contract", "utility_tariff",
            "public_benchmark", "manual", "synthetic_demo",
        }
        self.assertEqual(set(PRICE_SOURCE_KIND_SLA_HOURS.keys()), expected_kinds)

    def test_synthetic_demo_has_no_sla(self):
        self.assertEqual(PRICE_SOURCE_KIND_SLA_HOURS["synthetic_demo"], 999999)


if __name__ == "__main__":
    unittest.main()
