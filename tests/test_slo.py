"""Tests for SLO/SLA tracking."""
import datetime as dt
import unittest

from dcc.observability.slo import (
    AvailabilitySLO,
    ErrorBudget,
    LatencySLO,
    SLOReport,
    SLOStatus,
    SLATracking,
    availability_slo,
    build_slo_report,
    error_budget,
    latency_slo,
    sla_compliance,
    slo_status,
)


class SLOStatusTests(unittest.TestCase):
    def test_ok_when_meets_target(self):
        self.assertEqual(slo_status(99.9, 99.9), SLOStatus.OK)

    def test_ok_when_exceeds_target(self):
        self.assertEqual(slo_status(99.95, 99.9), SLOStatus.OK)

    def test_warning_when_slightly_below_target(self):
        self.assertEqual(slo_status(99.5, 99.9), SLOStatus.WARNING)

    def test_violation_when_far_below_target(self):
        self.assertEqual(slo_status(95.0, 99.9), SLOStatus.VIOLATION)

    def test_custom_warning_threshold(self):
        self.assertEqual(slo_status(99.0, 99.9, warning_threshold=1.0), SLOStatus.WARNING)
        self.assertEqual(slo_status(98.5, 99.9, warning_threshold=1.0), SLOStatus.VIOLATION)


class AvailabilitySLOTests(unittest.TestCase):
    def test_perfect_availability(self):
        slo = AvailabilitySLO("test", 99.9, 30, 10000, 0)
        self.assertEqual(slo.availability_pct, 100.0)
        self.assertEqual(slo.error_rate_pct, 0.0)
        self.assertEqual(slo.status, SLOStatus.OK)

    def test_no_requests_returns_unknown(self):
        slo = AvailabilitySLO("test", 99.9, 30, 0, 0)
        self.assertEqual(slo.availability_pct, 100.0)
        self.assertEqual(slo.status, SLOStatus.UNKNOWN)

    def test_violation_when_below_target(self):
        slo = AvailabilitySLO("test", 99.9, 30, 10000, 20)
        self.assertAlmostEqual(slo.availability_pct, 99.8)
        self.assertEqual(slo.status, SLOStatus.WARNING)

    def test_warning_when_close_to_target(self):
        slo = AvailabilitySLO("test", 99.9, 30, 10000, 6)
        self.assertAlmostEqual(slo.availability_pct, 99.94)
        self.assertEqual(slo.status, SLOStatus.OK)

    def test_error_budget_remaining(self):
        slo = AvailabilitySLO("test", 99.9, 30, 10000, 5)
        # Budget = 0.1% of 10000 = 10; consumed = 5; remaining = 5
        self.assertAlmostEqual(slo.error_budget_remaining_pct, 0.05)

    def test_to_dict(self):
        slo = AvailabilitySLO("test", 99.9, 30, 1000, 1)
        d = slo.to_dict()
        self.assertEqual(d["name"], "test")
        self.assertEqual(d["target_pct"], 99.9)
        self.assertEqual(d["total_requests"], 1000)
        self.assertEqual(d["failed_requests"], 1)
        self.assertIn("availability_pct", d)
        self.assertIn("status", d)


class LatencySLOTests(unittest.TestCase):
    def test_no_latencies_returns_unknown(self):
        slo = LatencySLO("test", 500, 95, 30, [])
        self.assertEqual(slo.status, SLOStatus.UNKNOWN)
        self.assertEqual(slo.actual_percentile_ms, 0.0)

    def test_ok_when_within_target(self):
        latencies = [100.0] * 95 + [400.0] * 5
        slo = LatencySLO("test", 500, 95, 30, latencies)
        self.assertEqual(slo.status, SLOStatus.OK)
        self.assertLessEqual(slo.actual_percentile_ms, 500)

    def test_violation_when_exceeds_target(self):
        latencies = [100.0] * 50 + [1000.0] * 50
        slo = LatencySLO("test", 500, 95, 30, latencies)
        self.assertEqual(slo.status, SLOStatus.VIOLATION)

    def test_warning_when_close_to_target(self):
        latencies = [100.0] * 5 + [550.0] * 95
        slo = LatencySLO("test", 500, 95, 30, latencies)
        self.assertEqual(slo.status, SLOStatus.WARNING)

    def test_percentile_calculation(self):
        latencies = [float(i) for i in range(1, 101)]
        slo = LatencySLO("test", 500, 95, 30, latencies)
        self.assertAlmostEqual(slo.actual_percentile_ms, 95.05, places=1)

    def test_summary_stats(self):
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
        slo = LatencySLO("test", 100, 95, 30, latencies)
        self.assertEqual(slo.mean_ms, 30.0)
        self.assertEqual(slo.min_ms, 10.0)
        self.assertEqual(slo.max_ms, 50.0)
        self.assertEqual(slo.p50_ms, 30.0)

    def test_to_dict(self):
        latencies = [100.0] * 100
        slo = LatencySLO("test", 500, 95, 30, latencies)
        d = slo.to_dict()
        self.assertEqual(d["name"], "test")
        self.assertEqual(d["target_ms"], 500)
        self.assertEqual(d["percentile"], 95)
        self.assertEqual(d["sample_count"], 100)
        self.assertIn("p50_ms", d)
        self.assertIn("p95_ms", d)
        self.assertIn("p99_ms", d)


class ErrorBudgetTests(unittest.TestCase):
    def test_no_requests(self):
        budget = ErrorBudget("test", 99.9, 30, 0, 0)
        self.assertEqual(budget.budget_total, 0.0)
        self.assertEqual(budget.budget_remaining, 0.0)
        self.assertEqual(budget.status, SLOStatus.UNKNOWN)

    def test_full_budget_remaining(self):
        budget = ErrorBudget("test", 99.9, 30, 10000, 0)
        self.assertAlmostEqual(budget.budget_total, 10.0)
        self.assertAlmostEqual(budget.budget_remaining, 10.0)
        self.assertAlmostEqual(budget.budget_remaining_pct, 100.0)
        self.assertAlmostEqual(budget.burn_rate, 0.0)
        self.assertEqual(budget.status, SLOStatus.OK)

    def test_partial_budget_consumed(self):
        budget = ErrorBudget("test", 99.9, 30, 10000, 3)
        self.assertAlmostEqual(budget.budget_total, 10.0)
        self.assertAlmostEqual(budget.budget_consumed, 3.0)
        self.assertAlmostEqual(budget.budget_remaining, 7.0)
        self.assertAlmostEqual(budget.budget_remaining_pct, 70.0)
        self.assertAlmostEqual(budget.burn_rate, 0.3)
        self.assertEqual(budget.status, SLOStatus.OK)

    def test_warning_when_budget_low(self):
        budget = ErrorBudget("test", 99.9, 30, 10000, 7)
        self.assertAlmostEqual(budget.budget_remaining_pct, 30.0)
        self.assertEqual(budget.status, SLOStatus.WARNING)

    def test_violation_when_budget_critical(self):
        budget = ErrorBudget("test", 99.9, 30, 10000, 9)
        self.assertAlmostEqual(budget.budget_remaining_pct, 10.0)
        self.assertEqual(budget.status, SLOStatus.VIOLATION)

    def test_budget_exhausted(self):
        budget = ErrorBudget("test", 99.9, 30, 10000, 15)
        self.assertAlmostEqual(budget.budget_remaining, 0.0)
        self.assertAlmostEqual(budget.budget_remaining_pct, 0.0)
        self.assertAlmostEqual(budget.burn_rate, 1.5)
        self.assertEqual(budget.status, SLOStatus.VIOLATION)

    def test_estimated_days_to_exhaustion(self):
        budget = ErrorBudget("test", 99.9, 30, 10000, 5)
        # Daily burn = 5/30 = 0.167; remaining = 5; days = 5/0.167 = 30
        days = budget.estimated_days_to_exhaustion
        self.assertIsNotNone(days)
        self.assertAlmostEqual(days, 30.0, places=0)

    def test_no_exhaustion_when_no_failures(self):
        budget = ErrorBudget("test", 99.9, 30, 10000, 0)
        self.assertIsNone(budget.estimated_days_to_exhaustion)

    def test_to_dict(self):
        budget = ErrorBudget("test", 99.9, 30, 1000, 1)
        d = budget.to_dict()
        self.assertEqual(d["slo_name"], "test")
        self.assertEqual(d["target_pct"], 99.9)
        self.assertIn("budget_total", d)
        self.assertIn("budget_remaining", d)
        self.assertIn("burn_rate", d)
        self.assertIn("status", d)


class SLATrackingTests(unittest.TestCase):
    def test_overall_status_ok(self):
        tracking = sla_compliance(
            "api-service",
            30,
            target_availability_pct=99.9,
            target_latency_ms=500,
            total_requests=10000,
            failed_requests=0,
            latencies_ms=[100.0] * 100,
        )
        self.assertEqual(tracking.overall_status, SLOStatus.OK)

    def test_overall_status_violation(self):
        tracking = sla_compliance(
            "api-service",
            30,
            target_availability_pct=99.9,
            target_latency_ms=500,
            total_requests=10000,
            failed_requests=100,
            latencies_ms=[100.0] * 100,
        )
        self.assertEqual(tracking.overall_status, SLOStatus.VIOLATION)

    def test_overall_status_warning(self):
        tracking = sla_compliance(
            "api-service",
            30,
            target_availability_pct=99.9,
            target_latency_ms=500,
            total_requests=10000,
            failed_requests=5,
            latencies_ms=[100.0] * 100,
        )
        self.assertEqual(tracking.overall_status, SLOStatus.WARNING)

    def test_to_dict(self):
        tracking = sla_compliance(
            "api-service",
            30,
            total_requests=1000,
            failed_requests=1,
            latencies_ms=[100.0] * 100,
        )
        d = tracking.to_dict()
        self.assertEqual(d["service_name"], "api-service")
        self.assertEqual(d["window_days"], 30)
        self.assertIn("availability", d)
        self.assertIn("latency", d)
        self.assertIn("error_budget", d)
        self.assertIn("overall_status", d)


class SLOReportTests(unittest.TestCase):
    def test_empty_report(self):
        report = SLOReport(generated_at=dt.datetime.now(dt.timezone.utc).isoformat())
        self.assertEqual(report.overall_status, SLOStatus.UNKNOWN)
        self.assertEqual(report.violations, [])
        self.assertEqual(report.warnings, [])

    def test_report_with_services(self):
        services = [
            sla_compliance("svc1", 30, total_requests=1000, failed_requests=0, latencies_ms=[100.0] * 100),
            sla_compliance("svc2", 30, total_requests=1000, failed_requests=50, latencies_ms=[100.0] * 100),
        ]
        report = build_slo_report(services)
        self.assertEqual(report.overall_status, SLOStatus.VIOLATION)
        self.assertIn("svc2", report.violations)
        self.assertNotIn("svc1", report.violations)

    def test_report_to_dict(self):
        services = [
            sla_compliance("svc1", 30, total_requests=1000, failed_requests=0, latencies_ms=[100.0] * 100),
        ]
        report = build_slo_report(services)
        d = report.to_dict()
        self.assertIn("generated_at", d)
        self.assertIn("overall_status", d)
        self.assertIn("services", d)
        self.assertEqual(len(d["services"]), 1)


class ConvenienceFunctionTests(unittest.TestCase):
    def test_availability_slo_factory(self):
        slo = availability_slo("test", 99.9, 30, 1000, 1)
        self.assertIsInstance(slo, AvailabilitySLO)
        self.assertEqual(slo.name, "test")

    def test_latency_slo_factory(self):
        slo = latency_slo("test", 500, 95, 30, [100.0] * 100)
        self.assertIsInstance(slo, LatencySLO)
        self.assertEqual(slo.name, "test")

    def test_error_budget_factory(self):
        budget = error_budget("test", 99.9, 30, 1000, 1)
        self.assertIsInstance(budget, ErrorBudget)
        self.assertEqual(budget.slo_name, "test")

    def test_sla_compliance_factory(self):
        tracking = sla_compliance("test", 30, total_requests=1000, failed_requests=1)
        self.assertIsInstance(tracking, SLATracking)
        self.assertEqual(tracking.service_name, "test")
        self.assertIsNotNone(tracking.availability_slo)
        self.assertIsNotNone(tracking.latency_slo)
        self.assertIsNotNone(tracking.error_budget)


if __name__ == "__main__":
    unittest.main()
