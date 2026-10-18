"""Unit tests for dcc.soc.chronicle module."""
import json
import unittest

from dcc.soc.chronicle import (
    AlertState,
    ChronicleDashboard,
    ChronicleIntegration,
    DashboardWidget,
    DataSource,
    DataSourceType,
    Detection,
    DetectionStatus,
    EventSeverity,
    EventStatus,
    LogType,
    RuleEngine,
    RuleManager,
    RuleMatch,
    RuleSeverity,
    RuleStatus,
    SOCReport,
    SecurityEvent,
    YaraRule,
    create_connector,
    create_rule_engine,
    create_rule_manager,
    evaluate_event,
    find_rule_by_name,
    get_builtin_dashboards,
    get_builtin_rules,
    get_dashboard_names,
    get_rule_count,
    get_rule_names,
    get_rules_by_severity,
    get_rules_by_tag,
    ingest_azure_activity,
    ingest_cloudtrail,
    ingest_gcp_audit,
    ingest_okta,
    ingest_syslog,
)


class TestSecurityEvent(unittest.TestCase):
    def test_creation(self):
        event = SecurityEvent(
            source="test",
            event_type="test_event",
            severity=EventSeverity.HIGH,
            description="Test event",
        )
        self.assertEqual(event.source, "test")
        self.assertEqual(event.event_type, "test_event")
        self.assertEqual(event.severity, EventSeverity.HIGH)
        self.assertEqual(event.status, EventStatus.NEW)
        self.assertTrue(event.event_id)

    def test_to_dict(self):
        event = SecurityEvent(
            source="test",
            event_type="test_event",
            severity=EventSeverity.HIGH,
            description="Test event",
        )
        data = event.to_dict()
        self.assertEqual(data["source"], "test")
        self.assertEqual(data["event_type"], "test_event")
        self.assertEqual(data["severity"], "high")
        self.assertEqual(data["status"], "new")

    def test_from_dict(self):
        event = SecurityEvent(
            source="test",
            event_type="test_event",
            severity=EventSeverity.HIGH,
            description="Test event",
        )
        data = event.to_dict()
        restored = SecurityEvent.from_dict(data)
        self.assertEqual(restored.source, event.source)
        self.assertEqual(restored.event_type, event.event_type)
        self.assertEqual(restored.severity, event.severity)


class TestChronicleAlert(unittest.TestCase):
    def test_creation(self):
        from dcc.soc.chronicle.models import ChronicleAlert
        alert = ChronicleAlert(
            title="Test Alert",
            description="Test description",
            severity=EventSeverity.HIGH,
        )
        self.assertEqual(alert.title, "Test Alert")
        self.assertEqual(alert.state, AlertState.ACTIVE)
        self.assertTrue(alert.alert_id)

    def test_acknowledge(self):
        from dcc.soc.chronicle.models import ChronicleAlert
        alert = ChronicleAlert(title="Test Alert")
        alert.acknowledge("admin")
        self.assertEqual(alert.state, AlertState.ACKNOWLEDGED)
        self.assertEqual(alert.assigned_to, "admin")

    def test_resolve(self):
        from dcc.soc.chronicle.models import ChronicleAlert
        alert = ChronicleAlert(title="Test Alert")
        alert.resolve()
        self.assertEqual(alert.state, AlertState.RESOLVED)

    def test_close(self):
        from dcc.soc.chronicle.models import ChronicleAlert
        alert = ChronicleAlert(title="Test Alert")
        alert.close()
        self.assertEqual(alert.state, AlertState.CLOSED)


class TestDetection(unittest.TestCase):
    def test_creation(self):
        detection = Detection(
            rule_id="rule-1",
            rule_name="Test Rule",
            severity=RuleSeverity.HIGH,
            description="Test detection",
        )
        self.assertEqual(detection.rule_id, "rule-1")
        self.assertEqual(detection.rule_name, "Test Rule")
        self.assertEqual(detection.status, DetectionStatus.NEW)

    def test_review(self):
        detection = Detection(rule_id="rule-1", rule_name="Test Rule")
        detection.review("admin", "Looks suspicious")
        self.assertEqual(detection.status, DetectionStatus.REVIEWED)
        self.assertEqual(detection.reviewed_by, "admin")

    def test_confirm(self):
        detection = Detection(rule_id="rule-1", rule_name="Test Rule")
        detection.confirm("admin", "True positive")
        self.assertEqual(detection.status, DetectionStatus.CONFIRMED)

    def test_dismiss(self):
        detection = Detection(rule_id="rule-1", rule_name="Test Rule")
        detection.dismiss("admin", "False positive")
        self.assertEqual(detection.status, DetectionStatus.DISMISSED)


class TestYaraRule(unittest.TestCase):
    def test_creation(self):
        rule = YaraRule(
            name="Test Rule",
            description="Test YARA-L rule",
            yara_l='rule test { condition: true }',
            severity=RuleSeverity.HIGH,
        )
        self.assertEqual(rule.name, "Test Rule")
        self.assertEqual(rule.severity, RuleSeverity.HIGH)
        self.assertEqual(rule.status, RuleStatus.DRAFT)

    def test_enable_disable(self):
        rule = YaraRule(name="Test Rule", yara_l='rule test { condition: true }')
        rule.enable()
        self.assertEqual(rule.status, RuleStatus.ENABLED)
        rule.disable()
        self.assertEqual(rule.status, RuleStatus.DISABLED)

    def test_to_dict(self):
        rule = YaraRule(
            name="Test Rule",
            description="Test",
            yara_l='rule test { condition: true }',
            severity=RuleSeverity.HIGH,
        )
        data = rule.to_dict()
        self.assertEqual(data["name"], "Test Rule")
        self.assertEqual(data["severity"], "high")
        self.assertEqual(data["status"], "draft")


class TestDataSource(unittest.TestCase):
    def test_creation(self):
        source = DataSource(
            name="Test Source",
            source_type=DataSourceType.AWS_CLOUDTRAIL,
            log_type=LogType.AWS_CLOUDTRAIL,
        )
        self.assertEqual(source.name, "Test Source")
        self.assertEqual(source.source_type, DataSourceType.AWS_CLOUDTRAIL)
        self.assertTrue(source.enabled)

    def test_to_dict(self):
        source = DataSource(
            name="Test Source",
            source_type=DataSourceType.AWS_CLOUDTRAIL,
        )
        data = source.to_dict()
        self.assertEqual(data["name"], "Test Source")
        self.assertEqual(data["source_type"], "aws_cloudtrail")


class TestChronicleDashboard(unittest.TestCase):
    def test_creation(self):
        dashboard = ChronicleDashboard(name="Test Dashboard")
        self.assertEqual(dashboard.name, "Test Dashboard")
        self.assertEqual(len(dashboard.widgets), 0)

    def test_add_widget(self):
        dashboard = ChronicleDashboard(name="Test Dashboard")
        widget = DashboardWidget(title="Test Widget", widget_type="timeseries")
        dashboard.add_widget(widget)
        self.assertEqual(len(dashboard.widgets), 1)
        self.assertEqual(dashboard.widgets[0].title, "Test Widget")

    def test_remove_widget(self):
        dashboard = ChronicleDashboard(name="Test Dashboard")
        widget = DashboardWidget(title="Test Widget")
        dashboard.add_widget(widget)
        result = dashboard.remove_widget(widget.widget_id)
        self.assertTrue(result)
        self.assertEqual(len(dashboard.widgets), 0)

    def test_remove_nonexistent_widget(self):
        dashboard = ChronicleDashboard(name="Test Dashboard")
        result = dashboard.remove_widget("nonexistent")
        self.assertFalse(result)


class TestSOCReport(unittest.TestCase):
    def test_creation(self):
        report = SOCReport()
        self.assertEqual(report.total_events, 0)
        self.assertEqual(report.total_alerts, 0)
        self.assertEqual(report.total_detections, 0)

    def test_to_dict(self):
        report = SOCReport(
            total_events=10,
            total_alerts=2,
            total_detections=5,
        )
        data = report.to_dict()
        self.assertEqual(data["total_events"], 10)
        self.assertEqual(data["total_alerts"], 2)
        self.assertEqual(data["total_detections"], 5)

    def test_save_and_load(self):
        import tempfile
        from pathlib import Path

        report = SOCReport(
            total_events=10,
            total_alerts=2,
            total_detections=5,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            report.save(path)
            loaded = SOCReport.load(path)
            self.assertEqual(loaded.total_events, 10)
            self.assertEqual(loaded.total_alerts, 2)
            self.assertEqual(loaded.total_detections, 5)


class TestConnectors(unittest.TestCase):
    def test_create_connector(self):
        connector = create_connector(DataSourceType.AWS_CLOUDTRAIL)
        self.assertIsNotNone(connector)
        self.assertEqual(connector.source_type, DataSourceType.AWS_CLOUDTRAIL)

    def test_ingest_cloudtrail(self):
        raw_data = {
            "Records": [
                {
                    "eventName": "ConsoleLogin",
                    "eventSource": "signin.amazonaws.com",
                    "eventTime": "2024-01-01T00:00:00Z",
                    "sourceIPAddress": "1.2.3.4",
                    "userIdentity": {"userName": "admin"},
                }
            ]
        }
        events = ingest_cloudtrail(raw_data)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source, "aws:signin.amazonaws.com")
        self.assertEqual(events[0].metadata["event_name"], "ConsoleLogin")

    def test_ingest_azure_activity(self):
        raw_data = {
            "value": [
                {
                    "operationName": {"value": "Microsoft.Compute/virtualMachines/write"},
                    "caller": "user@example.com",
                    "status": {"value": "Succeeded"},
                    "eventTimestamp": "2024-01-01T00:00:00Z",
                }
            ]
        }
        events = ingest_azure_activity(raw_data)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].metadata["caller"], "user@example.com")

    def test_ingest_gcp_audit(self):
        raw_data = {
            "entries": [
                {
                    "protoPayload": {
                        "methodName": "compute.instances.insert",
                        "authenticationInfo": {"principalEmail": "user@example.com"},
                    },
                    "timestamp": "2024-01-01T00:00:00Z",
                }
            ]
        }
        events = ingest_gcp_audit(raw_data)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].metadata["method_name"], "compute.instances.insert")

    def test_ingest_syslog(self):
        raw_data = '<134>Jan 1 00:00:00 host sshd[1234]: Failed password for root'
        events = ingest_syslog(raw_data)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].metadata["process"], "sshd")

    def test_ingest_okta(self):
        raw_data = {
            "data": [
                {
                    "eventType": "user.session.start",
                    "actor": {"displayName": "John Doe"},
                    "outcome": {"result": "SUCCESS"},
                    "published": "2024-01-01T00:00:00Z",
                }
            ]
        }
        events = ingest_okta(raw_data)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].metadata["event_type"], "user.session.start")


class TestRuleEngine(unittest.TestCase):
    def test_create_engine(self):
        engine = create_rule_engine()
        self.assertIsNotNone(engine)
        self.assertEqual(len(engine.rules), 0)

    def test_register_rule(self):
        engine = create_rule_engine()
        rule = YaraRule(
            name="Test Rule",
            yara_l='rule test { condition: true }',
            severity=RuleSeverity.HIGH,
        )
        engine.register(rule)
        self.assertEqual(len(engine.rules), 1)

    def test_evaluate_event(self):
        engine = create_rule_engine()
        rule = YaraRule(
            name="Test Rule",
            yara_l='rule test { condition: true }',
            severity=RuleSeverity.HIGH,
        )
        engine.register(rule)
        event = SecurityEvent(source="test", event_type="test")
        matches = engine.evaluate(event)
        self.assertIsInstance(matches, list)

    def test_evaluate_batch(self):
        engine = create_rule_engine()
        rule = YaraRule(
            name="Test Rule",
            yara_l='rule test { condition: true }',
            severity=RuleSeverity.HIGH,
        )
        engine.register(rule)
        events = [
            SecurityEvent(source="test1", event_type="test"),
            SecurityEvent(source="test2", event_type="test"),
        ]
        matches = engine.evaluate_batch(events)
        self.assertIsInstance(matches, list)


class TestRuleManager(unittest.TestCase):
    def test_create_manager(self):
        manager = create_rule_manager()
        self.assertIsNotNone(manager)
        self.assertEqual(len(manager.rules), 0)

    def test_create_rule(self):
        manager = create_rule_manager()
        rule = manager.create_rule(
            name="Test Rule",
            description="Test",
            yara_l='rule test { condition: true }',
        )
        self.assertEqual(rule.name, "Test Rule")
        self.assertEqual(len(manager.rules), 1)

    def test_get_rule(self):
        manager = create_rule_manager()
        rule = manager.create_rule(
            name="Test Rule",
            yara_l='rule test { condition: true }',
        )
        retrieved = manager.get_rule(rule.rule_id)
        self.assertEqual(retrieved.name, "Test Rule")

    def test_delete_rule(self):
        manager = create_rule_manager()
        rule = manager.create_rule(
            name="Test Rule",
            yara_l='rule test { condition: true }',
        )
        result = manager.delete_rule(rule.rule_id)
        self.assertTrue(result)
        self.assertEqual(len(manager.rules), 0)

    def test_list_rules(self):
        manager = create_rule_manager()
        manager.create_rule(
            name="Rule 1",
            yara_l='rule test { condition: true }',
            severity=RuleSeverity.HIGH,
        )
        manager.create_rule(
            name="Rule 2",
            yara_l='rule test { condition: true }',
            severity=RuleSeverity.LOW,
        )
        high_rules = manager.list_rules(severity=RuleSeverity.HIGH)
        self.assertEqual(len(high_rules), 1)


class TestBuiltinRules(unittest.TestCase):
    def test_get_builtin_rules(self):
        rules = get_builtin_rules()
        self.assertGreater(len(rules), 0)

    def test_get_rule_count(self):
        count = get_rule_count()
        self.assertGreater(count, 0)

    def test_get_rule_names(self):
        names = get_rule_names()
        self.assertGreater(len(names), 0)
        self.assertIn("Brute Force Login Detection", names)

    def test_get_rules_by_severity(self):
        critical_rules = get_rules_by_severity(RuleSeverity.CRITICAL)
        self.assertGreater(len(critical_rules), 0)
        for rule in critical_rules:
            self.assertEqual(rule.severity, RuleSeverity.CRITICAL)

    def test_get_rules_by_tag(self):
        auth_rules = get_rules_by_tag("authentication")
        self.assertGreater(len(auth_rules), 0)

    def test_find_rule_by_name(self):
        rule = find_rule_by_name("Brute Force Login Detection")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.name, "Brute Force Login Detection")

    def test_find_nonexistent_rule(self):
        rule = find_rule_by_name("Nonexistent Rule")
        self.assertIsNone(rule)


class TestDashboards(unittest.TestCase):
    def test_get_builtin_dashboards(self):
        dashboards = get_builtin_dashboards()
        self.assertGreater(len(dashboards), 0)

    def test_get_dashboard_names(self):
        names = get_dashboard_names()
        self.assertGreater(len(names), 0)
        self.assertIn("Security Overview", names)

    def test_dashboard_has_widgets(self):
        dashboards = get_builtin_dashboards()
        for dashboard in dashboards:
            self.assertGreater(len(dashboard.widgets), 0)


class TestChronicleIntegration(unittest.TestCase):
    def test_creation(self):
        integration = ChronicleIntegration()
        self.assertIsNotNone(integration)
        self.assertEqual(len(integration.events), 0)
        self.assertEqual(len(integration.detections), 0)

    def test_load_builtin_rules(self):
        integration = ChronicleIntegration()
        count = integration.load_builtin_rules()
        self.assertGreater(count, 0)
        self.assertEqual(len(integration.engine.rules), count)

    def test_load_builtin_dashboards(self):
        integration = ChronicleIntegration()
        count = integration.load_builtin_dashboards()
        self.assertGreater(count, 0)
        self.assertEqual(len(integration.dashboards), count)

    def test_ingest_and_evaluate(self):
        integration = ChronicleIntegration()
        integration.load_builtin_rules()

        raw_data = {
            "Records": [
                {
                    "eventName": "ConsoleLogin",
                    "eventSource": "signin.amazonaws.com",
                    "eventTime": "2024-01-01T00:00:00Z",
                    "sourceIPAddress": "1.2.3.4",
                    "userIdentity": {"userName": "admin"},
                }
            ]
        }
        events = integration.ingest_cloudtrail(raw_data)
        self.assertEqual(len(events), 1)

        detections = integration.evaluate_events()
        self.assertIsInstance(detections, list)

    def test_get_report(self):
        integration = ChronicleIntegration()
        integration.load_builtin_rules()

        raw_data = {
            "Records": [
                {
                    "eventName": "ConsoleLogin",
                    "eventSource": "signin.amazonaws.com",
                    "eventTime": "2024-01-01T00:00:00Z",
                    "sourceIPAddress": "1.2.3.4",
                    "userIdentity": {"userName": "admin"},
                }
            ]
        }
        integration.ingest_cloudtrail(raw_data)
        integration.evaluate_events()

        report = integration.get_report()
        self.assertEqual(report.total_events, 1)
        self.assertIsInstance(report.to_dict(), dict)

    def test_reset(self):
        integration = ChronicleIntegration()
        integration.load_builtin_rules()

        raw_data = {
            "Records": [
                {
                    "eventName": "ConsoleLogin",
                    "eventSource": "signin.amazonaws.com",
                    "eventTime": "2024-01-01T00:00:00Z",
                    "sourceIPAddress": "1.2.3.4",
                    "userIdentity": {"userName": "admin"},
                }
            ]
        }
        integration.ingest_cloudtrail(raw_data)
        integration.reset()
        self.assertEqual(len(integration.events), 0)
        self.assertEqual(len(integration.detections), 0)


if __name__ == "__main__":
    unittest.main()
