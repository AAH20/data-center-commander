"""Tests for the alerting rules engine."""
import json
import math
import time
import unittest

from dcc.observability.alerts import (
    Alert,
    AlertEngine,
    AlertEvent,
    AlertReport,
    AlertRule,
    AlertSeverity,
    AlertState,
    AlertType,
    AnomalyConfig,
    ComparisonOp,
    ThresholdConfig,
    create_anomaly_rule,
    create_threshold_rule,
    evaluate_anomaly,
    evaluate_threshold,
    evaluate_threshold_with_hysteresis,
)


class ThresholdConfigTests(unittest.TestCase):
    def test_valid_config(self):
        config = ThresholdConfig(
            upper_critical=90.0,
            upper_warning=80.0,
            lower_warning=10.0,
            lower_critical=5.0,
        )
        self.assertEqual(config.upper_critical, 90.0)
        self.assertEqual(config.upper_warning, 80.0)

    def test_negative_hysteresis_raises(self):
        with self.assertRaises(ValueError):
            ThresholdConfig(hysteresis=-1.0)

    def test_zero_sustained_for_raises(self):
        with self.assertRaises(ValueError):
            ThresholdConfig(sustained_for=0)

    def test_upper_critical_below_upper_warning_raises(self):
        with self.assertRaises(ValueError):
            ThresholdConfig(upper_critical=70.0, upper_warning=80.0)

    def test_lower_critical_above_lower_warning_raises(self):
        with self.assertRaises(ValueError):
            ThresholdConfig(lower_critical=15.0, lower_warning=10.0)

    def test_defaults(self):
        config = ThresholdConfig()
        self.assertIsNone(config.upper_critical)
        self.assertIsNone(config.upper_warning)
        self.assertIsNone(config.lower_warning)
        self.assertIsNone(config.lower_critical)
        self.assertEqual(config.hysteresis, 0.0)
        self.assertEqual(config.sustained_for, 1)


class AnomalyConfigTests(unittest.TestCase):
    def test_valid_config(self):
        config = AnomalyConfig(
            method="zscore",
            threshold=3.0,
            window=10,
            min_points=5,
        )
        self.assertEqual(config.method, "zscore")
        self.assertEqual(config.threshold, 3.0)

    def test_invalid_method_raises(self):
        with self.assertRaises(ValueError):
            AnomalyConfig(method="invalid")

    def test_negative_threshold_raises(self):
        with self.assertRaises(ValueError):
            AnomalyConfig(threshold=-1.0)

    def test_invalid_window_raises(self):
        with self.assertRaises(ValueError):
            AnomalyConfig(window=1)

    def test_invalid_period_raises(self):
        with self.assertRaises(ValueError):
            AnomalyConfig(period=1)

    def test_invalid_sensitivity_raises(self):
        with self.assertRaises(ValueError):
            AnomalyConfig(sensitivity="invalid")

    def test_defaults(self):
        config = AnomalyConfig()
        self.assertEqual(config.method, "zscore")
        self.assertEqual(config.threshold, 3.0)
        self.assertIsNone(config.window)
        self.assertEqual(config.period, 24)
        self.assertEqual(config.min_points, 10)
        self.assertEqual(config.sensitivity, "medium")


class AlertRuleTests(unittest.TestCase):
    def test_threshold_rule_requires_config(self):
        with self.assertRaises(ValueError):
            AlertRule(name="test", alert_type=AlertType.THRESHOLD)

    def test_anomaly_rule_requires_config(self):
        with self.assertRaises(ValueError):
            AlertRule(name="test", alert_type=AlertType.ANOMALY_ZSCORE)

    def test_empty_name_raises(self):
        with self.assertRaises(ValueError):
            AlertRule(name="")

    def test_valid_threshold_rule(self):
        rule = AlertRule(
            name="cpu_high",
            alert_type=AlertType.THRESHOLD,
            threshold_config=ThresholdConfig(upper_critical=90.0),
        )
        self.assertEqual(rule.name, "cpu_high")
        self.assertTrue(rule.enabled)

    def test_valid_anomaly_rule(self):
        rule = AlertRule(
            name="traffic_anomaly",
            alert_type=AlertType.ANOMALY_ZSCORE,
            anomaly_config=AnomalyConfig(method="zscore"),
        )
        self.assertEqual(rule.name, "traffic_anomaly")


class EvaluateThresholdTests(unittest.TestCase):
    def test_no_breach(self):
        config = ThresholdConfig(upper_critical=90.0, upper_warning=80.0)
        severity, threshold = evaluate_threshold(50.0, config)
        self.assertIsNone(severity)
        self.assertIsNone(threshold)

    def test_warning_upper(self):
        config = ThresholdConfig(upper_critical=90.0, upper_warning=80.0)
        severity, threshold = evaluate_threshold(85.0, config)
        self.assertEqual(severity, AlertSeverity.WARNING)
        self.assertEqual(threshold, 80.0)

    def test_critical_upper(self):
        config = ThresholdConfig(upper_critical=90.0, upper_warning=80.0)
        severity, threshold = evaluate_threshold(95.0, config)
        self.assertEqual(severity, AlertSeverity.CRITICAL)
        self.assertEqual(threshold, 90.0)

    def test_warning_lower(self):
        config = ThresholdConfig(lower_warning=10.0, lower_critical=5.0)
        severity, threshold = evaluate_threshold(7.0, config)
        self.assertEqual(severity, AlertSeverity.WARNING)
        self.assertEqual(threshold, 10.0)

    def test_critical_lower(self):
        config = ThresholdConfig(lower_warning=10.0, lower_critical=5.0)
        severity, threshold = evaluate_threshold(3.0, config)
        self.assertEqual(severity, AlertSeverity.CRITICAL)
        self.assertEqual(threshold, 5.0)

    def test_exact_threshold_is_warning(self):
        config = ThresholdConfig(upper_warning=80.0)
        severity, _ = evaluate_threshold(80.0, config)
        self.assertEqual(severity, AlertSeverity.WARNING)

    def test_exact_critical_is_critical(self):
        config = ThresholdConfig(upper_critical=90.0)
        severity, _ = evaluate_threshold(90.0, config)
        self.assertEqual(severity, AlertSeverity.CRITICAL)

    def test_only_upper_critical(self):
        config = ThresholdConfig(upper_critical=90.0)
        severity, _ = evaluate_threshold(95.0, config)
        self.assertEqual(severity, AlertSeverity.CRITICAL)
        severity, _ = evaluate_threshold(50.0, config)
        self.assertIsNone(severity)

    def test_only_lower_warning(self):
        config = ThresholdConfig(lower_warning=10.0)
        severity, _ = evaluate_threshold(5.0, config)
        self.assertEqual(severity, AlertSeverity.WARNING)
        severity, _ = evaluate_threshold(50.0, config)
        self.assertIsNone(severity)


class EvaluateThresholdHysteresisTests(unittest.TestCase):
    def test_no_hysteresis_no_change(self):
        config = ThresholdConfig(upper_critical=90.0, hysteresis=0.0)
        severity, _ = evaluate_threshold_with_hysteresis(
            95.0, config, was_firing=True
        )
        self.assertEqual(severity, AlertSeverity.CRITICAL)

    def test_hysteresis_prevents_clear(self):
        config = ThresholdConfig(upper_critical=90.0, hysteresis=5.0)
        # Value dropped to 87, which is below 90 but within hysteresis (85)
        severity, _ = evaluate_threshold_with_hysteresis(
            87.0, config, was_firing=True
        )
        self.assertEqual(severity, AlertSeverity.CRITICAL)

    def test_hysteresis_allows_clear(self):
        config = ThresholdConfig(upper_critical=90.0, hysteresis=5.0)
        # Value dropped to 80, which is below hysteresis band (85)
        severity, _ = evaluate_threshold_with_hysteresis(
            80.0, config, was_firing=True
        )
        self.assertIsNone(severity)

    def test_hysteresis_lower_bound(self):
        config = ThresholdConfig(lower_critical=10.0, hysteresis=2.0)
        # Value rose to 11, which is above 10 but within hysteresis (12)
        severity, _ = evaluate_threshold_with_hysteresis(
            11.0, config, was_firing=True
        )
        self.assertEqual(severity, AlertSeverity.CRITICAL)

    def test_hysteresis_lower_allows_clear(self):
        config = ThresholdConfig(lower_critical=10.0, hysteresis=2.0)
        # Value rose to 15, which is above hysteresis band (12)
        severity, _ = evaluate_threshold_with_hysteresis(
            15.0, config, was_firing=True
        )
        self.assertIsNone(severity)

    def test_not_firing_uses_normal_eval(self):
        config = ThresholdConfig(upper_critical=90.0, hysteresis=5.0)
        # Not firing, so normal evaluation
        severity, _ = evaluate_threshold_with_hysteresis(
            87.0, config, was_firing=False
        )
        self.assertIsNone(severity)


class EvaluateAnomalyTests(unittest.TestCase):
    def test_zscore_detects_outlier(self):
        config = AnomalyConfig(method="zscore", threshold=3.0, min_points=5)
        values = [10.0] * 20 + [100.0] + [10.0] * 20
        events = evaluate_anomaly(values, config)
        self.assertGreaterEqual(len(events), 1)
        # Check that the outlier event is present
        outlier_events = [e for e in events if e.value == 100.0]
        self.assertGreaterEqual(len(outlier_events), 1)

    def test_iqr_detects_outlier(self):
        config = AnomalyConfig(method="iqr", threshold=1.5, min_points=5)
        values = list(range(1, 101)) + [200]
        events = evaluate_anomaly(values, config)
        self.assertGreaterEqual(len(events), 1)

    def test_seasonal_detects_anomaly(self):
        config = AnomalyConfig(
            method="seasonal", threshold=3.0, period=24, min_points=48
        )
        values = []
        for day in range(5):
            for hour in range(24):
                values.append(50 + 10 * math.sin(2 * math.pi * hour / 24))
        values[3 * 24 + 12] = 200.0
        events = evaluate_anomaly(values, config)
        self.assertGreaterEqual(len(events), 1)

    def test_too_few_points_returns_empty(self):
        config = AnomalyConfig(method="zscore", min_points=100)
        values = [1.0] * 10
        events = evaluate_anomaly(values, config)
        self.assertEqual(len(events), 0)

    def test_no_anomalies_returns_empty(self):
        config = AnomalyConfig(method="zscore", threshold=3.0, min_points=5)
        values = [10.0 + i * 0.1 for i in range(50)]
        events = evaluate_anomaly(values, config)
        self.assertEqual(len(events), 0)

    def test_event_has_correct_fields(self):
        config = AnomalyConfig(method="zscore", threshold=2.0, min_points=5)
        values = [1.0] * 10 + [50.0]
        events = evaluate_anomaly(values, config)
        self.assertGreaterEqual(len(events), 1)
        event = events[0]
        self.assertIsInstance(event, AlertEvent)
        self.assertEqual(event.state, AlertState.FIRING)
        self.assertIn(event.severity, list(AlertSeverity))
        self.assertIsNotNone(event.value)
        self.assertIsNotNone(event.message)

    def test_sensitivity_high_more_severe(self):
        config = AnomalyConfig(
            method="zscore", threshold=2.0, min_points=5, sensitivity="high"
        )
        values = [0.0] * 20 + [20.0]
        events = evaluate_anomaly(values, config)
        self.assertGreaterEqual(len(events), 1)
        # High sensitivity should produce at least WARNING
        self.assertIn(events[0].severity, (AlertSeverity.WARNING, AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY))


class AlertEngineThresholdTests(unittest.TestCase):
    def setUp(self):
        self.engine = AlertEngine()

    def test_add_and_get_rule(self):
        rule = create_threshold_rule(
            "cpu_high", upper_critical=90.0, upper_warning=80.0
        )
        self.engine.add_rule(rule)
        retrieved = self.engine.get_rule("cpu_high")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "cpu_high")

    def test_remove_rule(self):
        rule = create_threshold_rule("test", upper_critical=90.0)
        self.engine.add_rule(rule)
        self.engine.remove_rule("test")
        self.assertIsNone(self.engine.get_rule("test"))

    def test_list_rules(self):
        self.engine.add_rule(create_threshold_rule("r1", upper_critical=90.0))
        self.engine.add_rule(create_threshold_rule("r2", upper_critical=80.0))
        rules = self.engine.list_rules()
        self.assertEqual(len(rules), 2)

    def test_submit_normal_value_no_alert(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        event = self.engine.submit("cpu", 50.0)
        self.assertIsNone(event)

    def test_submit_breach_fires_alert(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        event = self.engine.submit("cpu", 95.0)
        self.assertIsNotNone(event)
        self.assertEqual(event.state, AlertState.FIRING)
        self.assertEqual(event.severity, AlertSeverity.CRITICAL)

    def test_submit_warning_breach(self):
        self.engine.add_rule(
            create_threshold_rule("cpu", upper_critical=90.0, upper_warning=80.0)
        )
        event = self.engine.submit("cpu", 85.0)
        self.assertIsNotNone(event)
        self.assertEqual(event.severity, AlertSeverity.WARNING)

    def test_alert_resolves_when_value_normal(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        self.engine.submit("cpu", 95.0)
        event = self.engine.submit("cpu", 50.0)
        self.assertIsNotNone(event)
        self.assertEqual(event.state, AlertState.RESOLVED)

    def test_sustained_for_requires_consecutive(self):
        self.engine.add_rule(
            create_threshold_rule("cpu", upper_critical=90.0, sustained_for=3)
        )
        # First two breaches should not fire
        self.assertIsNone(self.engine.submit("cpu", 95.0))
        self.assertIsNone(self.engine.submit("cpu", 95.0))
        # Third breach should fire
        event = self.engine.submit("cpu", 95.0)
        self.assertIsNotNone(event)
        self.assertEqual(event.state, AlertState.FIRING)

    def test_sustained_for_resets_on_normal(self):
        self.engine.add_rule(
            create_threshold_rule("cpu", upper_critical=90.0, sustained_for=3)
        )
        self.engine.submit("cpu", 95.0)
        self.engine.submit("cpu", 95.0)
        # Normal value resets counter
        self.engine.submit("cpu", 50.0)
        # Need 3 more consecutive
        self.assertIsNone(self.engine.submit("cpu", 95.0))
        self.assertIsNone(self.engine.submit("cpu", 95.0))
        event = self.engine.submit("cpu", 95.0)
        self.assertIsNotNone(event)

    def test_acknowledge_alert(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        self.engine.submit("cpu", 95.0)
        event = self.engine.acknowledge("cpu", acknowledged_by="ops")
        self.assertIsNotNone(event)
        self.assertEqual(event.state, AlertState.ACKNOWLEDGED)
        alert = self.engine.get_alert("cpu")
        self.assertEqual(alert.state, AlertState.ACKNOWLEDGED)
        self.assertEqual(alert.acknowledged_by, "ops")

    def test_acknowledge_non_firing_returns_none(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        result = self.engine.acknowledge("cpu")
        self.assertIsNone(result)

    def test_manual_resolve(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        self.engine.submit("cpu", 95.0)
        event = self.engine.resolve("cpu")
        self.assertIsNotNone(event)
        self.assertEqual(event.state, AlertState.RESOLVED)

    def test_manual_resolve_inactive_returns_none(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        result = self.engine.resolve("cpu")
        self.assertIsNone(result)

    def test_unknown_rule_raises(self):
        with self.assertRaises(KeyError):
            self.engine.submit("nonexistent", 50.0)

    def test_disabled_rule_no_alert(self):
        rule = create_threshold_rule("cpu", upper_critical=90.0)
        rule.enabled = False
        self.engine.add_rule(rule)
        event = self.engine.submit("cpu", 95.0)
        self.assertIsNone(event)

    def test_fire_count_increments(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        self.engine.submit("cpu", 95.0)
        self.engine.submit("cpu", 96.0)
        self.engine.submit("cpu", 97.0)
        alert = self.engine.get_alert("cpu")
        self.assertEqual(alert.fire_count, 3)

    def test_events_recorded(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        self.engine.submit("cpu", 95.0)
        self.engine.submit("cpu", 50.0)
        events = self.engine.list_events()
        self.assertGreaterEqual(len(events), 2)

    def test_list_events_filtered_by_rule(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        self.engine.add_rule(create_threshold_rule("mem", upper_critical=85.0))
        self.engine.submit("cpu", 95.0)
        self.engine.submit("mem", 90.0)
        cpu_events = self.engine.list_events(rule_name="cpu")
        self.assertEqual(len(cpu_events), 1)
        self.assertEqual(cpu_events[0].rule_name, "cpu")

    def test_list_alerts_filtered_by_state(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        self.engine.add_rule(create_threshold_rule("mem", upper_critical=85.0))
        self.engine.submit("cpu", 95.0)
        self.engine.submit("mem", 50.0)
        firing = self.engine.list_alerts(state=AlertState.FIRING)
        self.assertEqual(len(firing), 1)
        self.assertEqual(firing[0].rule_name, "cpu")

    def test_reset_clears_all(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        self.engine.submit("cpu", 95.0)
        self.engine.reset()
        self.assertEqual(len(self.engine.list_alerts()), 0)
        self.assertEqual(len(self.engine.list_events()), 0)


class AlertEngineAnomalyTests(unittest.TestCase):
    def setUp(self):
        self.engine = AlertEngine()

    def test_submit_series_detects_anomaly(self):
        self.engine.add_rule(
            create_anomaly_rule("traffic", method="zscore", threshold=3.0)
        )
        values = [10.0] * 30 + [100.0] + [10.0] * 30
        events = self.engine.submit_series("traffic", values)
        self.assertGreaterEqual(len(events), 1)

    def test_submit_series_no_anomaly(self):
        self.engine.add_rule(
            create_anomaly_rule("traffic", method="zscore", threshold=3.0)
        )
        values = [10.0 + i * 0.1 for i in range(50)]
        events = self.engine.submit_series("traffic", values)
        self.assertEqual(len(events), 0)

    def test_anomaly_alert_resolves(self):
        self.engine.add_rule(
            create_anomaly_rule("traffic", method="zscore", threshold=3.0)
        )
        # First submit with anomaly
        values = [10.0] * 30 + [100.0] + [10.0] * 30
        self.engine.submit_series("traffic", values)
        alert = self.engine.get_alert("traffic")
        self.assertEqual(alert.state, AlertState.FIRING)
        # Second submit without anomaly
        clean_values = [10.0 + i * 0.1 for i in range(50)]
        self.engine.submit_series("traffic", clean_values)
        alert = self.engine.get_alert("traffic")
        self.assertEqual(alert.state, AlertState.RESOLVED)

    def test_threshold_rule_rejects_series(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        with self.assertRaises(ValueError):
            self.engine.submit_series("cpu", [1.0, 2.0, 3.0])

    def test_anomaly_rule_rejects_single_value(self):
        self.engine.add_rule(
            create_anomaly_rule("traffic", method="zscore")
        )
        with self.assertRaises(ValueError):
            self.engine.submit("traffic", 50.0)

    def test_anomaly_severity_classification(self):
        self.engine.add_rule(
            create_anomaly_rule(
                "traffic", method="zscore", threshold=2.0, sensitivity="high"
            )
        )
        values = [0.0] * 20 + [20.0]
        events = self.engine.submit_series("traffic", values)
        self.assertGreaterEqual(len(events), 1)
        # High sensitivity should produce at least WARNING
        self.assertIn(
            events[0].severity,
            (AlertSeverity.WARNING, AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY),
        )


class AlertEngineHysteresisTests(unittest.TestCase):
    def setUp(self):
        self.engine = AlertEngine()

    def test_hysteresis_prevents_flapping(self):
        self.engine.add_rule(
            create_threshold_rule("cpu", upper_critical=90.0, hysteresis=5.0)
        )
        # Fire the alert
        self.engine.submit("cpu", 95.0)
        # Value drops to 87 — within hysteresis, should stay firing
        event = self.engine.submit("cpu", 87.0)
        # Should not produce a resolved event
        if event is not None:
            self.assertNotEqual(event.state, AlertState.RESOLVED)
        alert = self.engine.get_alert("cpu")
        self.assertIn(alert.state, (AlertState.FIRING, AlertState.ACKNOWLEDGED))

    def test_hysteresis_allows_clear(self):
        self.engine.add_rule(
            create_threshold_rule("cpu", upper_critical=90.0, hysteresis=5.0)
        )
        self.engine.submit("cpu", 95.0)
        # Value drops to 80 — outside hysteresis band
        event = self.engine.submit("cpu", 80.0)
        self.assertIsNotNone(event)
        self.assertEqual(event.state, AlertState.RESOLVED)


class AlertReportTests(unittest.TestCase):
    def setUp(self):
        self.engine = AlertEngine()

    def test_report_structure(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        self.engine.add_rule(create_threshold_rule("mem", upper_critical=85.0))
        self.engine.submit("cpu", 95.0)
        self.engine.submit("mem", 50.0)
        report = self.engine.report()
        self.assertIsInstance(report, AlertReport)
        self.assertEqual(len(report.alerts), 2)
        self.assertGreaterEqual(report.firing_count, 1)

    def test_report_to_dict(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        self.engine.submit("cpu", 95.0)
        report = self.engine.report()
        d = report.to_dict()
        self.assertIn("generated_at", d)
        self.assertIn("summary", d)
        self.assertIn("alerts", d)
        self.assertIn("events", d)
        self.assertEqual(d["summary"]["firing"], 1)

    def test_report_json_serializable(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        self.engine.submit("cpu", 95.0)
        report = self.engine.report()
        d = report.to_dict()
        json.dumps(d)

    def test_critical_alerts_property(self):
        self.engine.add_rule(
            create_threshold_rule(
                "cpu", upper_critical=90.0, severity=AlertSeverity.CRITICAL
            )
        )
        self.engine.add_rule(
            create_threshold_rule(
                "mem", upper_critical=85.0, severity=AlertSeverity.WARNING
            )
        )
        self.engine.submit("cpu", 95.0)
        self.engine.submit("mem", 90.0)
        report = self.engine.report()
        critical = report.critical_alerts
        self.assertEqual(len(critical), 1)
        self.assertEqual(critical[0].rule_name, "cpu")

    def test_firing_alerts_property(self):
        self.engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        self.engine.add_rule(create_threshold_rule("mem", upper_critical=85.0))
        self.engine.submit("cpu", 95.0)
        self.engine.submit("mem", 50.0)
        report = self.engine.report()
        firing = report.firing_alerts
        self.assertEqual(len(firing), 1)
        self.assertEqual(firing[0].rule_name, "cpu")


class AlertDataclassTests(unittest.TestCase):
    def test_alert_event_to_dict(self):
        event = AlertEvent(
            rule_name="test",
            state=AlertState.FIRING,
            severity=AlertSeverity.WARNING,
            value=95.0,
            threshold=90.0,
            message="Test alert",
        )
        d = event.to_dict()
        self.assertEqual(d["rule_name"], "test")
        self.assertEqual(d["state"], "firing")
        self.assertEqual(d["severity"], "warning")
        self.assertEqual(d["value"], 95.0)

    def test_alert_to_dict(self):
        alert = Alert(
            rule_name="test",
            state=AlertState.FIRING,
            severity=AlertSeverity.CRITICAL,
            fire_count=3,
        )
        d = alert.to_dict()
        self.assertEqual(d["rule_name"], "test")
        self.assertEqual(d["fire_count"], 3)
        self.assertEqual(d["state"], "firing")

    def test_alert_defaults(self):
        alert = Alert(rule_name="test")
        self.assertEqual(alert.state, AlertState.INACTIVE)
        self.assertEqual(alert.fire_count, 0)
        self.assertIsNone(alert.first_fired_at)
        self.assertIsNone(alert.acknowledged_at)
        self.assertIsNone(alert.resolved_at)


class ConvenienceFactoryTests(unittest.TestCase):
    def test_create_threshold_rule(self):
        rule = create_threshold_rule(
            "cpu_high",
            description="CPU too high",
            upper_critical=90.0,
            upper_warning=80.0,
            severity=AlertSeverity.CRITICAL,
        )
        self.assertEqual(rule.name, "cpu_high")
        self.assertEqual(rule.alert_type, AlertType.THRESHOLD)
        self.assertIsNotNone(rule.threshold_config)
        self.assertEqual(rule.threshold_config.upper_critical, 90.0)

    def test_create_anomaly_rule(self):
        rule = create_anomaly_rule(
            "traffic_anomaly",
            method="zscore",
            threshold=3.0,
            sensitivity="high",
        )
        self.assertEqual(rule.name, "traffic_anomaly")
        self.assertEqual(rule.alert_type, AlertType.ANOMALY_ZSCORE)
        self.assertIsNotNone(rule.anomaly_config)
        self.assertEqual(rule.anomaly_config.method, "zscore")

    def test_create_anomaly_rule_iqr(self):
        rule = create_anomaly_rule("outlier", method="iqr", threshold=1.5)
        self.assertEqual(rule.alert_type, AlertType.ANOMALY_IQR)

    def test_create_anomaly_rule_seasonal(self):
        rule = create_anomaly_rule("seasonal", method="seasonal", period=24)
        self.assertEqual(rule.alert_type, AlertType.ANOMALY_SEASONAL)


class ComparisonOpTests(unittest.TestCase):
    def test_gt(self):
        from dcc.observability.alerts import _compare

        self.assertTrue(_compare(5.0, ComparisonOp.GT, 3.0))
        self.assertFalse(_compare(3.0, ComparisonOp.GT, 3.0))

    def test_gte(self):
        from dcc.observability.alerts import _compare

        self.assertTrue(_compare(3.0, ComparisonOp.GTE, 3.0))
        self.assertTrue(_compare(5.0, ComparisonOp.GTE, 3.0))

    def test_lt(self):
        from dcc.observability.alerts import _compare

        self.assertTrue(_compare(1.0, ComparisonOp.LT, 3.0))
        self.assertFalse(_compare(3.0, ComparisonOp.LT, 3.0))

    def test_lte(self):
        from dcc.observability.alerts import _compare

        self.assertTrue(_compare(3.0, ComparisonOp.LTE, 3.0))
        self.assertTrue(_compare(1.0, ComparisonOp.LTE, 3.0))

    def test_eq(self):
        from dcc.observability.alerts import _compare

        self.assertTrue(_compare(3.0, ComparisonOp.EQ, 3.0))
        self.assertFalse(_compare(1.0, ComparisonOp.EQ, 3.0))

    def test_neq(self):
        from dcc.observability.alerts import _compare

        self.assertTrue(_compare(1.0, ComparisonOp.NEQ, 3.0))
        self.assertFalse(_compare(3.0, ComparisonOp.NEQ, 3.0))


class IntegrationTests(unittest.TestCase):
    def test_full_lifecycle(self):
        engine = AlertEngine()
        engine.add_rule(
            create_threshold_rule(
                "cpu",
                upper_critical=90.0,
                upper_warning=80.0,
                severity=AlertSeverity.CRITICAL,
            )
        )

        # Normal — no alert
        self.assertIsNone(engine.submit("cpu", 50.0))

        # Warning level
        event = engine.submit("cpu", 85.0)
        self.assertIsNotNone(event)
        self.assertEqual(event.severity, AlertSeverity.WARNING)

        # Critical level
        event = engine.submit("cpu", 95.0)
        self.assertIsNotNone(event)
        self.assertEqual(event.severity, AlertSeverity.CRITICAL)

        # Acknowledge
        event = engine.acknowledge("cpu", "ops-team")
        self.assertIsNotNone(event)
        self.assertEqual(event.state, AlertState.ACKNOWLEDGED)

        # Resolve
        event = engine.submit("cpu", 50.0)
        self.assertIsNotNone(event)
        self.assertEqual(event.state, AlertState.RESOLVED)

        # Check report
        report = engine.report()
        self.assertEqual(report.resolved_count, 1)
        self.assertEqual(report.firing_count, 0)

    def test_multiple_rules_independent(self):
        engine = AlertEngine()
        engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        engine.add_rule(create_threshold_rule("mem", upper_critical=85.0))
        engine.add_rule(create_threshold_rule("disk", upper_critical=95.0))

        engine.submit("cpu", 95.0)
        engine.submit("mem", 50.0)
        engine.submit("disk", 99.0)

        firing = engine.list_alerts(state=AlertState.FIRING)
        self.assertEqual(len(firing), 2)
        names = {a.rule_name for a in firing}
        self.assertEqual(names, {"cpu", "disk"})

    def test_anomaly_and_threshold_together(self):
        engine = AlertEngine()
        engine.add_rule(create_threshold_rule("cpu", upper_critical=90.0))
        engine.add_rule(
            create_anomaly_rule("traffic", method="zscore", threshold=3.0)
        )

        # Threshold alert
        engine.submit("cpu", 95.0)
        # Anomaly alert
        values = [10.0] * 30 + [100.0] + [10.0] * 30
        engine.submit_series("traffic", values)

        report = engine.report()
        self.assertEqual(report.firing_count, 2)


if __name__ == "__main__":
    unittest.main()
