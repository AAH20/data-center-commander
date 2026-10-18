"""Tests for OSSEC SOC integration."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from dcc.soc.ossec.active_response import (
    ActiveResponse,
    ActiveResponseEngine,
    ResponseActionType,
    ResponseStatus,
)
from dcc.soc.ossec.connectors import OSSECLogConnector, OSSECQueueConnector
from dcc.soc.ossec.dashboards import OSSECDashboard
from dcc.soc.ossec.engine import OSSECEngine
from dcc.soc.ossec.models import (
    OSSECAlert,
    OSSECEvent,
    OSSECGroup,
    OSSECRule,
    OSSECSource,
    OSSECStatus,
    Severity,
)
from dcc.soc.ossec.rules import CORRELATION_RULES, CorrelationRule, RuleEngine


class TestModels:
    """Test OSSEC data models."""

    def test_severity_enum(self):
        assert Severity.INFO.value == 0
        assert Severity.CRITICAL.value == 10
        assert Severity.EMERGENCY.value == 15

    def test_ossec_rule_severity_mapping(self):
        rule = OSSECRule(
            rule_id=1001,
            level=12,
            description="Test rule",
            group=OSSECGroup.GENERAL,
        )
        assert rule.severity == Severity.EMERGENCY

        rule2 = OSSECRule(
            rule_id=1002,
            level=5,
            description="Test rule 2",
            group=OSSECGroup.GENERAL,
        )
        assert rule2.severity == Severity.MEDIUM

    def test_ossec_alert_creation(self):
        rule = OSSECRule(
            rule_id=1001,
            level=10,
            description="Test alert",
            group=OSSECGroup.AUTHENTICATION,
        )
        alert = OSSECAlert(
            alert_id="test-001",
            timestamp="2024-01-01T00:00:00Z",
            rule=rule,
            agent_id="001",
            agent_name="test-agent",
            agent_ip="192.168.1.100",
            source=OSSECSource.SYSLOG,
        )
        assert alert.severity == Severity.CRITICAL
        assert alert.mitre_tactic == ""


class TestConnectors:
    """Test OSSEC connectors."""

    def test_log_connector_parse(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write(
                "**Jan 1 00:00:00 test-agent sshd[1234]: "
                "Rule: 5716 (level 10) -> 'SSHD authentication failed.'\n"
            )
            f.flush()

            connector = OSSECLogConnector(f.name)
            alerts = connector.ingest()

            assert len(alerts) == 1
            assert alerts[0].rule.rule_id == 5716
            assert alerts[0].rule.level == 10

    def test_log_connector_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("")
            f.flush()

            connector = OSSECLogConnector(f.name)
            alerts = connector.ingest()
            assert len(alerts) == 0

    def test_queue_connector_read(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_dir = Path(tmpdir) / "alerts"
            queue_dir.mkdir()

            event_data = {
                "timestamp": "2024-01-01T00:00:00Z",
                "agent_id": "001",
                "agent_name": "test-agent",
                "agent_ip": "192.168.1.100",
                "source": "syslog",
                "raw_log": "Test log entry",
            }

            (queue_dir / "event1.json").write_text(json.dumps(event_data))

            connector = OSSECQueueConnector(queue_dir)
            events = connector.read_queue()

            assert len(events) == 1
            assert events[0].agent_name == "test-agent"


class TestRules:
    """Test OSSEC rule engine."""

    def test_correlation_rules_loaded(self):
        engine = RuleEngine()
        assert len(engine.correlation_rules) == len(CORRELATION_RULES)
        assert all(isinstance(r, CorrelationRule) for r in engine.correlation_rules)

    def test_rule_matching(self):
        engine = RuleEngine()
        rule = OSSECRule(
            rule_id=1001,
            level=5,
            description="Test rule",
            group=OSSECGroup.SYSTEM,
            program_name="sshd",
        )
        engine.load_rules([rule])

        event = OSSECEvent(
            event_id="evt-001",
            timestamp="2024-01-01T00:00:00Z",
            agent_id="001",
            agent_name="test-agent",
            agent_ip="192.168.1.100",
            source=OSSECSource.SYSLOG,
            program_name="sshd",
            raw_log="Test sshd log",
        )

        matched = engine.match_event(event)
        assert len(matched) == 1
        assert matched[0].rule_id == 1001

    def test_correlation_detection(self):
        engine = RuleEngine()

        alerts = []
        for i in range(6):
            rule = OSSECRule(
                rule_id=5716,
                level=10,
                description="Failed password for root",
                group=OSSECGroup.AUTHENTICATION,
            )
            alerts.append(
                OSSECAlert(
                    alert_id=f"alert-{i}",
                    timestamp="2024-01-01T00:00:00Z",
                    rule=rule,
                    agent_id="001",
                    agent_name="test-agent",
                    agent_ip="192.168.1.100",
                    source=OSSECSource.SYSLOG,
                )
            )

        results = engine.correlate(alerts)
        assert len(results) > 0
        assert any(r["rule_id"] == "CORR-001" for r in results)


class TestDashboards:
    """Test OSSEC dashboard generation."""

    def test_dashboard_summary(self):
        dashboard = OSSECDashboard()

        rule = OSSECRule(
            rule_id=1001,
            level=10,
            description="Test alert",
            group=OSSECGroup.AUTHENTICATION,
        )
        alert = OSSECAlert(
            alert_id="test-001",
            timestamp="2024-01-01T00:00:00Z",
            rule=rule,
            agent_id="001",
            agent_name="test-agent",
            agent_ip="192.168.1.100",
            source=OSSECSource.SYSLOG,
        )

        dashboard.load_alerts([alert])
        dashboard.load_agents(
            [
                OSSECStatus(
                    agent_id="001",
                    agent_name="test-agent",
                    agent_ip="192.168.1.100",
                    status="active",
                )
            ]
        )

        summary = dashboard.summary()
        assert summary["total_alerts"] == 1
        assert summary["total_agents"] == 1
        assert summary["active_agents"] == 1
        assert "critical" in summary["severity_breakdown"]

    def test_dashboard_export_json(self):
        dashboard = OSSECDashboard()
        dashboard.load_alerts([])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        dashboard.export_json(path)

        with open(path) as f:
            data = json.load(f)

        assert "total_alerts" in data
        assert "generated_at" in data


class TestActiveResponse:
    """Test OSSEC active response engine."""

    def test_default_responses_loaded(self):
        engine = ActiveResponseEngine()
        assert len(engine.responses) == 5
        assert all(isinstance(r, ActiveResponse) for r in engine.responses)

    def test_evaluate_alert_triggers_response(self):
        engine = ActiveResponseEngine()

        rule = OSSECRule(
            rule_id=5716,
            level=10,
            description="Failed password for root",
            group=OSSECGroup.AUTHENTICATION,
        )
        alert = OSSECAlert(
            alert_id="test-001",
            timestamp="2024-01-01T00:00:00Z",
            rule=rule,
            agent_id="001",
            agent_name="test-agent",
            agent_ip="192.168.1.100",
            source=OSSECSource.SYSLOG,
            src_ip="10.0.0.1",
        )

        triggered = engine.evaluate_alert(alert)
        assert len(triggered) > 0
        assert any(r.response_id == "AR-001" for r in triggered)

    def test_dry_run_execution(self):
        engine = ActiveResponseEngine()

        rule = OSSECRule(
            rule_id=5716,
            level=10,
            description="Failed password for root",
            group=OSSECGroup.AUTHENTICATION,
        )
        alert = OSSECAlert(
            alert_id="test-001",
            timestamp="2024-01-01T00:00:00Z",
            rule=rule,
            agent_id="001",
            agent_name="test-agent",
            agent_ip="192.168.1.100",
            source=OSSECSource.SYSLOG,
            src_ip="10.0.0.1",
        )

        triggered = engine.evaluate_alert(alert)
        if triggered:
            execution = engine.execute_response(triggered[0], alert, dry_run=True)
            assert execution.status == ResponseStatus.SKIPPED


class TestEngine:
    """Test main OSSEC SOC engine."""

    def test_engine_initialization(self):
        engine = OSSECEngine()
        assert engine.rule_engine is not None
        assert engine.dashboard is not None
        assert engine.active_response is not None

    def test_add_log_connector(self):
        engine = OSSECEngine()
        connector = engine.add_log_connector("/tmp/test.log")
        assert isinstance(connector, OSSECLogConnector)
        assert len(engine.connectors) == 1

    def test_add_api_connector(self):
        engine = OSSECEngine()
        connector = engine.add_api_connector(
            host="localhost", port=55000, username="wazuh", password="test"
        )
        assert connector.host == "localhost"
        assert connector.port == 55000

    def test_get_summary(self):
        engine = OSSECEngine()
        summary = engine.get_summary()
        assert "total_alerts" in summary
        assert "total_agents" in summary
