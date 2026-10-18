"""Tests for Graylog OSS SOC integration."""
from __future__ import annotations

import pytest

from dcc.soc.graylog import (
    GraylogAlertManager,
    GraylogAPIConfig,
    GraylogConnectorManager,
    GraylogDashboardManager,
    GraylogSOCEngine,
    GraylogEventManager,
    GraylogAlertSeverity,
    GraylogConnectorType,
    GraylogEventStatus,
    GraylogRuleType,
    GraylogStreamType,
    GraylogStreamManager,
)


class TestGraylogModels:
    """Test Graylog data models."""

    def test_alert_severity_enum(self) -> None:
        assert GraylogAlertSeverity.INFO == 1
        assert GraylogAlertSeverity.CRITICAL == 5

    def test_connector_type_enum(self) -> None:
        assert GraylogConnectorType.SYSLOG_UDP == "syslog_udp"
        assert GraylogConnectorType.GELF == "gelf"

    def test_stream_type_enum(self) -> None:
        assert GraylogStreamType.SECURITY == "security"
        assert GraylogStreamType.FIREWALL == "firewall"

    def test_event_status_enum(self) -> None:
        assert GraylogEventStatus.OPEN == "open"
        assert GraylogEventStatus.RESOLVED == "resolved"

    def test_rule_type_enum(self) -> None:
        assert GraylogRuleType.AGGREGATION == "aggregation"
        assert GraylogRuleType.MATCH == "match"


class TestGraylogConnectorManager:
    """Test Graylog connector management."""

    def setup_method(self) -> None:
        self.config = GraylogAPIConfig(api_url="http://localhost:9000/api")
        self.manager = GraylogConnectorManager(self.config)

    def test_create_syslog_udp_connector(self) -> None:
        connector = self.manager.create_syslog_udp_connector(port=514)
        assert connector.name == "Syslog UDP"
        assert connector.connector_type == GraylogConnectorType.SYSLOG_UDP
        assert connector.listen_port == 514

    def test_create_gelf_connector(self) -> None:
        connector = self.manager.create_gelf_connector(port=12201)
        assert connector.name == "GELF"
        assert connector.connector_type == GraylogConnectorType.GELF
        assert connector.listen_port == 12201

    def test_create_beats_connector(self) -> None:
        connector = self.manager.create_beats_connector(port=5044)
        assert connector.name == "Beats"
        assert connector.connector_type == GraylogConnectorType.BEATS

    def test_list_connectors(self) -> None:
        self.manager.create_syslog_udp_connector()
        self.manager.create_gelf_connector()
        connectors = self.manager.list_connectors()
        assert len(connectors) == 2

    def test_list_connectors_filtered_by_type(self) -> None:
        self.manager.create_syslog_udp_connector()
        self.manager.create_gelf_connector()
        connectors = self.manager.list_connectors(connector_type=GraylogConnectorType.GELF)
        assert len(connectors) == 1
        assert connectors[0].connector_type == GraylogConnectorType.GELF

    def test_start_connector(self) -> None:
        connector = self.manager.create_syslog_udp_connector()
        assert self.manager.start_connector(connector.connector_id)
        assert connector.status.value == "running"

    def test_stop_connector(self) -> None:
        connector = self.manager.create_syslog_udp_connector()
        self.manager.start_connector(connector.connector_id)
        assert self.manager.stop_connector(connector.connector_id)
        assert connector.status.value == "stopped"

    def test_delete_connector(self) -> None:
        connector = self.manager.create_syslog_udp_connector()
        assert self.manager.delete_connector(connector.connector_id)
        assert self.manager.get_connector(connector.connector_id) is None

    def test_get_connector_config(self) -> None:
        connector = self.manager.create_syslog_udp_connector(port=514)
        config = self.manager.get_connector_config(connector)
        assert config["name"] == "Syslog UDP"
        assert config["configuration"]["port"] == 514


class TestGraylogStreamManager:
    """Test Graylog stream management."""

    def setup_method(self) -> None:
        self.manager = GraylogStreamManager()

    def test_create_security_stream(self) -> None:
        stream = self.manager.create_security_stream()
        assert stream.title == "Security Events"
        assert stream.stream_type == GraylogStreamType.SECURITY
        assert stream.enabled is True

    def test_create_firewall_stream(self) -> None:
        stream = self.manager.create_firewall_stream()
        assert stream.title == "Firewall Logs"
        assert stream.stream_type == GraylogStreamType.FIREWALL

    def test_create_ids_stream(self) -> None:
        stream = self.manager.create_ids_stream()
        assert stream.title == "IDS/IPS Alerts"
        assert stream.stream_type == GraylogStreamType.IDS

    def test_create_auth_stream(self) -> None:
        stream = self.manager.create_auth_stream()
        assert stream.title == "Authentication Logs"
        assert stream.stream_type == GraylogStreamType.AUTH

    def test_list_streams(self) -> None:
        self.manager.create_security_stream()
        self.manager.create_firewall_stream()
        streams = self.manager.list_streams()
        assert len(streams) == 2

    def test_list_streams_filtered_by_type(self) -> None:
        self.manager.create_security_stream()
        self.manager.create_firewall_stream()
        streams = self.manager.list_streams(stream_type=GraylogStreamType.SECURITY)
        assert len(streams) == 1

    def test_enable_disable_stream(self) -> None:
        stream = self.manager.create_security_stream()
        assert self.manager.disable_stream(stream.stream_id)
        assert stream.enabled is False
        assert self.manager.enable_stream(stream.stream_id)
        assert stream.enabled is True

    def test_add_stream_rule(self) -> None:
        stream = self.manager.create_security_stream()
        assert self.manager.add_stream_rule(stream.stream_id, "field:value")
        assert len(stream.rules) == 1


class TestGraylogAlertManager:
    """Test Graylog alert management."""

    def setup_method(self) -> None:
        self.manager = GraylogAlertManager()

    def test_create_alert(self) -> None:
        alert = self.manager.create_alert(
            event_definition_id="event-123",
            event_definition_title="Test Alert",
            severity=GraylogAlertSeverity.HIGH,
        )
        assert alert.event_definition_title == "Test Alert"
        assert alert.severity == GraylogAlertSeverity.HIGH
        assert alert.status == GraylogEventStatus.OPEN

    def test_list_alerts(self) -> None:
        self.manager.create_alert("event-1", "Alert 1")
        self.manager.create_alert("event-2", "Alert 2")
        alerts = self.manager.list_alerts()
        assert len(alerts) == 2

    def test_list_alerts_filtered_by_severity(self) -> None:
        self.manager.create_alert("event-1", "Alert 1", severity=GraylogAlertSeverity.LOW)
        self.manager.create_alert("event-2", "Alert 2", severity=GraylogAlertSeverity.HIGH)
        alerts = self.manager.list_alerts(severity=GraylogAlertSeverity.HIGH)
        assert len(alerts) == 1

    def test_acknowledge_alert(self) -> None:
        alert = self.manager.create_alert("event-1", "Alert 1")
        assert self.manager.acknowledge_alert(alert.alert_id, "admin")
        assert alert.status == GraylogEventStatus.ACKNOWLEDGED
        assert alert.acknowledged_by == "admin"

    def test_resolve_alert(self) -> None:
        alert = self.manager.create_alert("event-1", "Alert 1")
        assert self.manager.resolve_alert(alert.alert_id, "Fixed")
        assert alert.status == GraylogEventStatus.RESOLVED
        assert alert.notes == "Fixed"

    def test_mark_false_positive(self) -> None:
        alert = self.manager.create_alert("event-1", "Alert 1")
        assert self.manager.mark_false_positive(alert.alert_id, "Not an attack")
        assert alert.status == GraylogEventStatus.FALSE_POSITIVE

    def test_get_open_alerts(self) -> None:
        self.manager.create_alert("event-1", "Alert 1", severity=GraylogAlertSeverity.HIGH)
        self.manager.create_alert("event-2", "Alert 2", severity=GraylogAlertSeverity.LOW)
        open_alerts = self.manager.get_open_alerts(min_severity=GraylogAlertSeverity.HIGH)
        assert len(open_alerts) == 1

    def test_get_alert_stats(self) -> None:
        self.manager.create_alert("event-1", "Alert 1", severity=GraylogAlertSeverity.HIGH)
        self.manager.create_alert("event-2", "Alert 2", severity=GraylogAlertSeverity.LOW)
        stats = self.manager.get_alert_stats()
        assert stats["total"] == 2
        assert stats["open"] == 2


class TestGraylogEventManager:
    """Test Graylog event definition management."""

    def setup_method(self) -> None:
        self.manager = GraylogEventManager()

    def test_create_event_definition(self) -> None:
        event = self.manager.create_event_definition(
            title="Test Event",
            rule_type=GraylogRuleType.MATCH,
            severity=GraylogAlertSeverity.HIGH,
        )
        assert event.title == "Test Event"
        assert event.rule_type == GraylogRuleType.MATCH
        assert event.severity == GraylogAlertSeverity.HIGH

    def test_create_brute_force_rule(self) -> None:
        event = self.manager.create_brute_force_rule()
        assert "Brute Force" in event.title
        assert event.rule_type == GraylogRuleType.AGGREGATION
        assert event.alert is True

    def test_create_port_scan_rule(self) -> None:
        event = self.manager.create_port_scan_rule()
        assert "Port Scan" in event.title
        assert event.rule_type == GraylogRuleType.AGGREGATION

    def test_create_malware_detection_rule(self) -> None:
        event = self.manager.create_malware_detection_rule()
        assert "Malware" in event.title
        assert event.severity == GraylogAlertSeverity.CRITICAL

    def test_list_events(self) -> None:
        self.manager.create_event_definition("Event 1")
        self.manager.create_event_definition("Event 2")
        events = self.manager.list_events()
        assert len(events) == 2

    def test_list_events_filtered_by_type(self) -> None:
        self.manager.create_event_definition("Event 1", rule_type=GraylogRuleType.MATCH)
        self.manager.create_event_definition("Event 2", rule_type=GraylogRuleType.AGGREGATION)
        events = self.manager.list_events(rule_type=GraylogRuleType.MATCH)
        assert len(events) == 1

    def test_enable_disable_event(self) -> None:
        event = self.manager.create_event_definition("Test Event")
        assert self.manager.disable_event(event.event_id)
        assert event.status == "disabled"
        assert self.manager.enable_event(event.event_id)
        assert event.status == "enabled"


class TestGraylogDashboardManager:
    """Test Graylog dashboard management."""

    def setup_method(self) -> None:
        self.manager = GraylogDashboardManager()

    def test_create_security_overview_dashboard(self) -> None:
        dashboard = self.manager.create_security_overview_dashboard()
        assert dashboard.title == "Security Overview"
        assert len(dashboard.widgets) > 0

    def test_create_threat_hunting_dashboard(self) -> None:
        dashboard = self.manager.create_threat_hunting_dashboard()
        assert dashboard.title == "Threat Hunting"
        assert len(dashboard.widgets) > 0

    def test_create_compliance_dashboard(self) -> None:
        dashboard = self.manager.create_compliance_dashboard()
        assert dashboard.title == "Compliance Monitoring"
        assert len(dashboard.widgets) > 0

    def test_create_auth_monitoring_dashboard(self) -> None:
        dashboard = self.manager.create_auth_monitoring_dashboard()
        assert dashboard.title == "Authentication Monitoring"
        assert len(dashboard.widgets) > 0

    def test_list_dashboards(self) -> None:
        self.manager.create_security_overview_dashboard()
        self.manager.create_threat_hunting_dashboard()
        dashboards = self.manager.list_dashboards()
        assert len(dashboards) == 2

    def test_add_widget(self) -> None:
        dashboard = self.manager.create_security_overview_dashboard()
        widget_count = len(dashboard.widgets)
        assert self.manager.add_widget(dashboard.dashboard_id, {"type": "TEST", "title": "Test"})
        assert len(dashboard.widgets) == widget_count + 1


class TestGraylogSOCEngine:
    """Test Graylog SOC orchestration engine."""

    def setup_method(self) -> None:
        self.config = GraylogAPIConfig(api_url="http://localhost:9000/api")
        self.engine = GraylogSOCEngine(self.config)

    def test_initialize(self) -> None:
        self.engine.initialize()
        assert self.engine._initialized is True

    def test_initialize_creates_default_streams(self) -> None:
        self.engine.initialize()
        streams = self.engine.streams.list_streams()
        assert len(streams) >= 6

    def test_initialize_creates_default_connectors(self) -> None:
        self.engine.initialize()
        connectors = self.engine.connectors.list_connectors()
        assert len(connectors) >= 6

    def test_initialize_creates_default_events(self) -> None:
        self.engine.initialize()
        events = self.engine.events.list_events()
        assert len(events) >= 8

    def test_initialize_creates_default_dashboards(self) -> None:
        self.engine.initialize()
        dashboards = self.engine.dashboards.list_dashboards()
        assert len(dashboards) >= 4

    def test_get_status(self) -> None:
        self.engine.initialize()
        status = self.engine.get_status()
        assert status.server_id == "graylog-soc"
        assert status.streams_count >= 6
        assert status.connectors_count >= 6

    def test_get_open_alerts(self) -> None:
        self.engine.initialize()
        alerts = self.engine.get_open_alerts()
        assert isinstance(alerts, list)

    def test_acknowledge_alert(self) -> None:
        self.engine.initialize()
        alert = self.engine.alerts.create_alert("event-1", "Test Alert")
        assert self.engine.acknowledge_alert(alert.alert_id, "admin")

    def test_resolve_alert(self) -> None:
        self.engine.initialize()
        alert = self.engine.alerts.create_alert("event-1", "Test Alert")
        assert self.engine.resolve_alert(alert.alert_id, "Resolved")

    def test_get_alert_stats(self) -> None:
        self.engine.initialize()
        stats = self.engine.get_alert_stats()
        assert "total" in stats
        assert "open" in stats

    def test_create_incident_from_alert(self) -> None:
        self.engine.initialize()
        alert = self.engine.alerts.create_alert("event-1", "Test Alert")
        incident = self.engine.create_incident_from_alert(alert.alert_id)
        assert incident["title"] == "Test Alert"
        assert incident["status"] == "new"

    def test_export_configuration(self) -> None:
        self.engine.initialize()
        config = self.engine.export_configuration()
        assert "streams" in config
        assert "connectors" in config
        assert "events" in config
        assert "dashboards" in config

    def test_health_check(self) -> None:
        self.engine.initialize()
        health = self.engine.health_check()
        assert health["healthy"] is True
        assert health["server_id"] == "graylog-soc"
