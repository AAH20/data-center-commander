"""Tests for OpenSearch OSS SOC integration."""
from __future__ import annotations

import pytest

from dcc.soc.opensearch import (
    OpenSearchAlertSeverity,
    OpenSearchAPIConfig,
    OpenSearchConnectorManager,
    OpenSearchConnectorType,
    OpenSearchEvent,
    OpenSearchEventStatus,
    OpenSearchRuleEngine,
    OpenSearchRuleType,
    OpenSearchSOCEngine,
)


class TestOpenSearchModels:
    """Test OpenSearch data models."""

    def test_alert_severity_enum(self) -> None:
        assert OpenSearchAlertSeverity.INFO == 1
        assert OpenSearchAlertSeverity.CRITICAL == 5

    def test_connector_type_enum(self) -> None:
        assert OpenSearchConnectorType.SYSLOG_UDP == "syslog_udp"
        assert OpenSearchConnectorType.BEATS == "beats"
        assert OpenSearchConnectorType.S3 == "s3"

    def test_event_status_enum(self) -> None:
        assert OpenSearchEventStatus.OPEN == "open"
        assert OpenSearchEventStatus.RESOLVED == "resolved"

    def test_rule_type_enum(self) -> None:
        assert OpenSearchRuleType.THRESHOLD == "threshold"
        assert OpenSearchRuleType.MATCH == "match"
        assert OpenSearchRuleType.ANOMALY == "anomaly"


class TestOpenSearchConnectorManager:
    """Test OpenSearch connector management."""

    def setup_method(self) -> None:
        self.config = OpenSearchAPIConfig(api_url="http://localhost:9200")
        self.manager = OpenSearchConnectorManager(self.config)

    def test_create_syslog_udp_connector(self) -> None:
        connector = self.manager.create_syslog_udp_connector(port=514)
        assert connector.name == "Syslog UDP"
        assert connector.connector_type == OpenSearchConnectorType.SYSLOG_UDP
        assert connector.listen_port == 514

    def test_create_beats_connector(self) -> None:
        connector = self.manager.create_beats_connector(port=5044)
        assert connector.name == "Beats"
        assert connector.connector_type == OpenSearchConnectorType.BEATS
        assert connector.listen_port == 5044

    def test_create_kafka_connector(self) -> None:
        connector = self.manager.create_kafka_connector(port=9092)
        assert connector.name == "Kafka"
        assert connector.connector_type == OpenSearchConnectorType.KAFKA

    def test_create_s3_connector(self) -> None:
        connector = self.manager.create_s3_connector()
        assert connector.name == "S3"
        assert connector.connector_type == OpenSearchConnectorType.S3

    def test_create_cloudtrail_connector(self) -> None:
        connector = self.manager.create_cloudtrail_connector()
        assert connector.name == "CloudTrail"
        assert connector.connector_type == OpenSearchConnectorType.CLOUDTRAIL

    def test_list_connectors(self) -> None:
        self.manager.create_syslog_udp_connector()
        self.manager.create_beats_connector()
        connectors = self.manager.list_connectors()
        assert len(connectors) == 2

    def test_list_connectors_filtered_by_type(self) -> None:
        self.manager.create_syslog_udp_connector()
        self.manager.create_beats_connector()
        connectors = self.manager.list_connectors(connector_type=OpenSearchConnectorType.BEATS)
        assert len(connectors) == 1
        assert connectors[0].connector_type == OpenSearchConnectorType.BEATS

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
        assert config["configuration"]["listen_port"] == 514


class TestOpenSearchRuleEngine:
    """Test OpenSearch rule engine."""

    def setup_method(self) -> None:
        self.engine = OpenSearchRuleEngine()

    def test_create_rule(self) -> None:
        rule = self.engine.create_rule(
            name="Test Rule",
            rule_type=OpenSearchRuleType.MATCH,
            severity=OpenSearchAlertSeverity.HIGH,
        )
        assert rule.name == "Test Rule"
        assert rule.rule_type == OpenSearchRuleType.MATCH
        assert rule.severity == OpenSearchAlertSeverity.HIGH

    def test_create_brute_force_rule(self) -> None:
        rule = self.engine.create_brute_force_rule()
        assert "Brute Force" in rule.name
        assert rule.rule_type == OpenSearchRuleType.THRESHOLD
        assert rule.severity == OpenSearchAlertSeverity.HIGH

    def test_create_port_scan_rule(self) -> None:
        rule = self.engine.create_port_scan_rule()
        assert "Port Scan" in rule.name
        assert rule.rule_type == OpenSearchRuleType.THRESHOLD

    def test_create_malware_detection_rule(self) -> None:
        rule = self.engine.create_malware_detection_rule()
        assert "Malware" in rule.name
        assert rule.severity == OpenSearchAlertSeverity.CRITICAL

    def test_create_ddos_detection_rule(self) -> None:
        rule = self.engine.create_ddos_detection_rule()
        assert "DDoS" in rule.name
        assert rule.severity == OpenSearchAlertSeverity.CRITICAL

    def test_list_rules(self) -> None:
        self.engine.create_rule("Rule 1")
        self.engine.create_rule("Rule 2")
        rules = self.engine.list_rules()
        assert len(rules) == 2

    def test_list_rules_filtered_by_type(self) -> None:
        self.engine.create_rule("Rule 1", rule_type=OpenSearchRuleType.MATCH)
        self.engine.create_rule("Rule 2", rule_type=OpenSearchRuleType.THRESHOLD)
        rules = self.engine.list_rules(rule_type=OpenSearchRuleType.MATCH)
        assert len(rules) == 1

    def test_enable_disable_rule(self) -> None:
        rule = self.engine.create_rule("Test Rule")
        assert self.engine.disable_rule(rule.rule_id)
        assert rule.status == "disabled"
        assert self.engine.enable_rule(rule.rule_id)
        assert rule.status == "enabled"

    def test_match_event(self) -> None:
        self.engine.create_brute_force_rule()
        event = OpenSearchEvent(
            event_id="evt-001",
            timestamp="2024-01-01T00:00:00Z",
            raw_log="Failed password for root from 192.168.1.1",
        )
        matched = self.engine.match_event(event)
        assert len(matched) >= 1

    def test_create_alert(self) -> None:
        rule = self.engine.create_brute_force_rule()
        event = OpenSearchEvent(
            event_id="evt-001",
            timestamp="2024-01-01T00:00:00Z",
            raw_log="Failed password for root",
        )
        alert = self.engine.create_alert(rule, event)
        assert alert.rule_name == rule.name
        assert alert.severity == OpenSearchAlertSeverity.HIGH
        assert alert.status == OpenSearchEventStatus.OPEN

    def test_list_alerts(self) -> None:
        rule = self.engine.create_brute_force_rule()
        event = OpenSearchEvent(
            event_id="evt-001",
            timestamp="2024-01-01T00:00:00Z",
            raw_log="Failed password",
        )
        self.engine.create_alert(rule, event)
        alerts = self.engine.list_alerts()
        assert len(alerts) == 1

    def test_list_alerts_filtered_by_severity(self) -> None:
        rule1 = self.engine.create_brute_force_rule()
        rule2 = self.engine.create_port_scan_rule()
        event = OpenSearchEvent(
            event_id="evt-001",
            timestamp="2024-01-01T00:00:00Z",
            raw_log="Failed password",
        )
        self.engine.create_alert(rule1, event)
        self.engine.create_alert(rule2, event)
        alerts = self.engine.list_alerts(severity=OpenSearchAlertSeverity.HIGH)
        assert len(alerts) == 1

    def test_acknowledge_alert(self) -> None:
        rule = self.engine.create_brute_force_rule()
        event = OpenSearchEvent(
            event_id="evt-001",
            timestamp="2024-01-01T00:00:00Z",
            raw_log="Failed password",
        )
        alert = self.engine.create_alert(rule, event)
        assert self.engine.acknowledge_alert(alert.alert_id, "admin")
        assert alert.status == OpenSearchEventStatus.ACKNOWLEDGED
        assert alert.acknowledged_by == "admin"

    def test_resolve_alert(self) -> None:
        rule = self.engine.create_brute_force_rule()
        event = OpenSearchEvent(
            event_id="evt-001",
            timestamp="2024-01-01T00:00:00Z",
            raw_log="Failed password",
        )
        alert = self.engine.create_alert(rule, event)
        assert self.engine.resolve_alert(alert.alert_id, "Fixed")
        assert alert.status == OpenSearchEventStatus.RESOLVED
        assert alert.notes == "Fixed"

    def test_mark_false_positive(self) -> None:
        rule = self.engine.create_brute_force_rule()
        event = OpenSearchEvent(
            event_id="evt-001",
            timestamp="2024-01-01T00:00:00Z",
            raw_log="Failed password",
        )
        alert = self.engine.create_alert(rule, event)
        assert self.engine.mark_false_positive(alert.alert_id, "Not an attack")
        assert alert.status == OpenSearchEventStatus.FALSE_POSITIVE

    def test_get_open_alerts(self) -> None:
        rule = self.engine.create_brute_force_rule()
        event = OpenSearchEvent(
            event_id="evt-001",
            timestamp="2024-01-01T00:00:00Z",
            raw_log="Failed password",
        )
        self.engine.create_alert(rule, event)
        open_alerts = self.engine.get_open_alerts(min_severity=OpenSearchAlertSeverity.HIGH)
        assert len(open_alerts) == 1

    def test_get_alert_stats(self) -> None:
        rule = self.engine.create_brute_force_rule()
        event = OpenSearchEvent(
            event_id="evt-001",
            timestamp="2024-01-01T00:00:00Z",
            raw_log="Failed password",
        )
        self.engine.create_alert(rule, event)
        stats = self.engine.get_alert_stats()
        assert stats["total"] == 1
        assert stats["open"] == 1


class TestOpenSearchSOCEngine:
    """Test OpenSearch SOC orchestration engine."""

    def setup_method(self) -> None:
        self.config = OpenSearchAPIConfig(api_url="http://localhost:9200")
        self.engine = OpenSearchSOCEngine(self.config)

    def test_initialize(self) -> None:
        self.engine.initialize()
        assert self.engine._initialized is True

    def test_initialize_creates_default_indices(self) -> None:
        self.engine.initialize()
        assert len(self.engine._indices) >= 6

    def test_initialize_creates_default_connectors(self) -> None:
        self.engine.initialize()
        connectors = self.engine.connectors.list_connectors()
        assert len(connectors) >= 8

    def test_initialize_creates_default_rules(self) -> None:
        self.engine.initialize()
        rules = self.engine.rules.list_rules()
        assert len(rules) >= 10

    def test_get_status(self) -> None:
        self.engine.initialize()
        status = self.engine.get_status()
        assert status.cluster_name == "opensearch-soc"
        assert status.indices_count >= 6
        assert status.connectors_count >= 8

    def test_get_open_alerts(self) -> None:
        self.engine.initialize()
        alerts = self.engine.get_open_alerts()
        assert isinstance(alerts, list)

    def test_acknowledge_alert(self) -> None:
        self.engine.initialize()
        rule = self.engine.rules.create_brute_force_rule()
        event = OpenSearchEvent(
            event_id="evt-001",
            timestamp="2024-01-01T00:00:00Z",
            raw_log="Failed password",
        )
        alert = self.engine.rules.create_alert(rule, event)
        assert self.engine.acknowledge_alert(alert.alert_id, "admin")

    def test_resolve_alert(self) -> None:
        self.engine.initialize()
        rule = self.engine.rules.create_brute_force_rule()
        event = OpenSearchEvent(
            event_id="evt-001",
            timestamp="2024-01-01T00:00:00Z",
            raw_log="Failed password",
        )
        alert = self.engine.rules.create_alert(rule, event)
        assert self.engine.resolve_alert(alert.alert_id, "Resolved")

    def test_get_alert_stats(self) -> None:
        self.engine.initialize()
        stats = self.engine.get_alert_stats()
        assert "total" in stats
        assert "open" in stats

    def test_create_incident_from_alert(self) -> None:
        self.engine.initialize()
        rule = self.engine.rules.create_brute_force_rule()
        event = OpenSearchEvent(
            event_id="evt-001",
            timestamp="2024-01-01T00:00:00Z",
            raw_log="Failed password",
        )
        alert = self.engine.rules.create_alert(rule, event)
        incident = self.engine.create_incident_from_alert(alert.alert_id)
        assert incident["title"] == rule.name
        assert incident["status"] == "new"

    def test_export_configuration(self) -> None:
        self.engine.initialize()
        config = self.engine.export_configuration()
        assert "indices" in config
        assert "connectors" in config
        assert "rules" in config
        assert "alerts" in config

    def test_health_check(self) -> None:
        self.engine.initialize()
        health = self.engine.health_check()
        assert health["healthy"] is True
        assert health["cluster_name"] == "opensearch-soc"
