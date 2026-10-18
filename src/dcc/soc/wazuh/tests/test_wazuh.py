"""Tests for Wazuh SOC integration."""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from dcc.soc.wazuh import (
    WazuhAgent,
    WazuhAgentStatus,
    WazuhAlert,
    WazuhAlertSeverity,
    WazuhAuthenticationError,
    WazuhCapability,
    WazuhClusterNode,
    WazuhConfig,
    WazuhConnectionError,
    WazuhConnector,
    WazuhConnectorError,
    WazuhDecoder,
    WazuhHealthcheck,
    WazuhMITRETechnique,
    WazuhRateLimitError,
    WazuhRootcheckResult,
    WazuhRule,
    WazuhRuleGroup,
    WazuhSCAResult,
    WazuhStats,
    WazuhSyscheckResult,
    WazuhValidationError,
    WazuhVulnerabilityResult,
    create_wazuh_connector,
)


class TestModels(unittest.TestCase):
    """Test Wazuh data models."""

    def test_severity_enum(self):
        assert WazuhAlertSeverity.INFO.value == 1
        assert WazuhAlertSeverity.CRITICAL.value == 10
        assert WazuhAlertSeverity.EMERGENCY.value == 15

    def test_rule_severity_mapping(self):
        rule = WazuhRule(
            rule_id=1001,
            level=12,
            description="Test rule",
            group=WazuhRuleGroup.GENERAL,
        )
        assert rule.severity == WazuhAlertSeverity.EMERGENCY

        rule2 = WazuhRule(
            rule_id=1002,
            level=5,
            description="Test rule 2",
            group=WazuhRuleGroup.GENERAL,
        )
        assert rule2.severity == WazuhAlertSeverity.MEDIUM

        rule3 = WazuhRule(
            rule_id=1003,
            level=0,
            description="Test rule 3",
            group=WazuhRuleGroup.GENERAL,
        )
        assert rule3.severity == WazuhAlertSeverity.INFO

    def test_alert_creation(self):
        rule = WazuhRule(
            rule_id=1001,
            level=10,
            description="Test alert",
            group=WazuhRuleGroup.AUTHENTICATION,
        )
        alert = WazuhAlert(
            alert_id="test-001",
            timestamp="2024-01-01T00:00:00Z",
            rule=rule,
            agent_id="001",
            agent_name="test-agent",
            agent_ip="192.168.1.100",
        )
        assert alert.severity == WazuhAlertSeverity.CRITICAL
        assert alert.mitre_tactic == ""
        assert alert.mitre_technique == ""
        assert alert.compliance_refs == []

    def test_alert_inherits_from_rule(self):
        rule = WazuhRule(
            rule_id=1001,
            level=12,
            description="Test alert",
            group=WazuhRuleGroup.AUTHENTICATION,
            mitre_tactic="TA0001",
            mitre_technique="T1110",
            compliance_refs=["PCI-DSS"],
        )
        alert = WazuhAlert(
            alert_id="test-001",
            timestamp="2024-01-01T00:00:00Z",
            rule=rule,
            agent_id="001",
            agent_name="test-agent",
        )
        assert alert.severity == WazuhAlertSeverity.EMERGENCY
        assert alert.mitre_tactic == "TA0001"
        assert alert.mitre_technique == "T1110"
        assert alert.compliance_refs == ["PCI-DSS"]

    def test_agent_creation(self):
        agent = WazuhAgent(
            agent_id="001",
            agent_name="test-agent",
            agent_ip="192.168.1.100",
            status=WazuhAgentStatus.ACTIVE,
            version="4.7.0",
            os="Ubuntu",
            os_version="22.04",
            os_arch="x86_64",
        )
        assert agent.agent_id == "001"
        assert agent.status == WazuhAgentStatus.ACTIVE
        assert agent.alerts_count == 0

    def test_syscheck_result(self):
        result = WazuhSyscheckResult(
            result_id="/etc/passwd",
            agent_id="001",
            agent_name="test-agent",
            file_path="/etc/passwd",
            event_type="modified",
            size=1024,
            md5="abc123",
            sha1="def456",
        )
        assert result.event_type == "modified"
        assert result.size == 1024

    def test_vulnerability_result(self):
        result = WazuhVulnerabilityResult(
            result_id="CVE-2024-1234",
            agent_id="001",
            agent_name="test-agent",
            cve="CVE-2024-1234",
            severity="high",
            cvss_score=7.5,
            package="openssl",
            version="1.1.1",
        )
        assert result.cve == "CVE-2024-1234"
        assert result.cvss_score == 7.5

    def test_healthcheck(self):
        hc = WazuhHealthcheck(
            status="ok",
            version="4.7.0",
            cluster_enabled=True,
            cluster_name="wazuh-cluster",
            agents=10,
            agent_status={"active": 8, "disconnected": 2},
        )
        assert hc.status == "ok"
        assert hc.cluster_enabled is True
        assert hc.agents == 10

    def test_stats(self):
        stats = WazuhStats(
            total_agents=100,
            active_agents=90,
            disconnected_agents=10,
            total_alerts=5000,
            alerts_today=50,
            rules_loaded=2000,
            decoders_loaded=300,
        )
        assert stats.total_agents == 100
        assert stats.active_agents == 90


class TestConfig(unittest.TestCase):
    """Test Wazuh configuration."""

    def test_valid_config(self):
        config = WazuhConfig(
            url="https://wazuh.example.com:55000",
            username="wazuh-wui",
            password="secret",
        )
        assert config.url == "https://wazuh.example.com:55000"
        assert config.verify_tls is True
        assert config.timeout_s == 15

    def test_missing_url(self):
        with self.assertRaises(WazuhValidationError):
            WazuhConfig(url="", username="user", password="pass")

    def test_missing_username(self):
        with self.assertRaises(WazuhValidationError):
            WazuhConfig(url="https://host:55000", username="", password="pass")

    def test_missing_password(self):
        with self.assertRaises(WazuhValidationError):
            WazuhConfig(url="https://host:55000", username="user", password="")

    def test_invalid_timeout(self):
        with self.assertRaises(WazuhValidationError):
            WazuhConfig(
                url="https://host:55000",
                username="user",
                password="pass",
                timeout_s=0.1,
            )

    def test_invalid_rate_limit(self):
        with self.assertRaises(WazuhValidationError):
            WazuhConfig(
                url="https://host:55000",
                username="user",
                password="pass",
                rate_limit_per_minute=0,
            )


class TestConnector(unittest.TestCase):
    """Test Wazuh connector."""

    def _make_connector(self) -> WazuhConnector:
        config = WazuhConfig(
            url="https://wazuh.example.com:55000",
            username="wazuh-wui",
            password="secret",
        )
        return WazuhConnector(config)

    def test_capabilities(self):
        connector = self._make_connector()
        assert connector.supports(WazuhCapability.AGENT_READ)
        assert connector.supports(WazuhCapability.ALERT_READ)
        assert connector.supports(WazuhCapability.RULE_READ)
        assert connector.supports(WazuhCapability.HEALTHCHECK)
        assert connector.supports(WazuhCapability.STATS_READ)

    def test_base_url(self):
        connector = self._make_connector()
        assert connector.base_url == "https://wazuh.example.com:55000"

    def test_not_authenticated_initially(self):
        connector = self._make_connector()
        assert not connector.is_authenticated

    def test_snapshot(self):
        connector = self._make_connector()
        snap = connector.snapshot()
        assert snap["name"] == "generic-wazuh"
        assert snap["version"] == "0.1.0"
        assert snap["url"] == "https://wazuh.example.com:55000"
        assert "agent_read" in snap["capabilities"]
        assert snap["persisted"] is False
        assert snap["execution_permitted"] is False

    def test_health_check_failure(self):
        connector = self._make_connector()
        with patch("dcc.soc.wazuh.connector._http_request") as mock_req:
            mock_req.side_effect = WazuhConnectionError("unreachable")
            assert connector.health_check() is False
            assert connector._consecutive_failures == 1

    def test_health_check_success(self):
        connector = self._make_connector()
        with patch("dcc.soc.wazuh.connector._http_request") as mock_req:
            mock_req.return_value = {"data": {"title": "Wazuh API"}}
            assert connector.health_check() is True
            assert connector._consecutive_failures == 0

    def test_get_agents_validation(self):
        connector = self._make_connector()
        with self.assertRaises(WazuhValidationError):
            connector.get_agents(limit=0)
        with self.assertRaises(WazuhValidationError):
            connector.get_agents(limit=10000)
        with self.assertRaises(WazuhValidationError):
            connector.get_agents(offset=-1)

    def test_get_alerts_validation(self):
        connector = self._make_connector()
        with self.assertRaises(WazuhValidationError):
            connector.get_alerts(limit=0)
        with self.assertRaises(WazuhValidationError):
            connector.get_alerts(limit=10000)
        with self.assertRaises(WazuhValidationError):
            connector.get_alerts(offset=-1)

    def test_get_rules_validation(self):
        connector = self._make_connector()
        with self.assertRaises(WazuhValidationError):
            connector.get_rules(limit=0)
        with self.assertRaises(WazuhValidationError):
            connector.get_rules(limit=10000)

    def test_get_syscheck_validation(self):
        connector = self._make_connector()
        with self.assertRaises(WazuhValidationError):
            connector.get_syscheck("")
        with self.assertRaises(WazuhValidationError):
            connector.get_syscheck("001", limit=0)

    def test_get_rootcheck_validation(self):
        connector = self._make_connector()
        with self.assertRaises(WazuhValidationError):
            connector.get_rootcheck("")
        with self.assertRaises(WazuhValidationError):
            connector.get_rootcheck("001", limit=0)

    def test_get_sca_validation(self):
        connector = self._make_connector()
        with self.assertRaises(WazuhValidationError):
            connector.get_sca_results("")
        with self.assertRaises(WazuhValidationError):
            connector.get_sca_results("001", limit=0)

    def test_get_vulnerabilities_validation(self):
        connector = self._make_connector()
        with self.assertRaises(WazuhValidationError):
            connector.get_vulnerabilities("")
        with self.assertRaises(WazuhValidationError):
            connector.get_vulnerabilities("001", limit=0)

    def test_get_mitre_validation(self):
        connector = self._make_connector()
        with self.assertRaises(WazuhValidationError):
            connector.get_mitre_techniques(limit=0)
        with self.assertRaises(WazuhValidationError):
            connector.get_mitre_techniques(limit=10000)

    def test_get_cluster_nodes_validation(self):
        connector = self._make_connector()
        with self.assertRaises(WazuhValidationError):
            connector.get_cluster_nodes(limit=0)
        with self.assertRaises(WazuhValidationError):
            connector.get_cluster_nodes(limit=1000)


class TestFactory(unittest.TestCase):
    """Test factory function."""

    def test_create_connector(self):
        connector = create_wazuh_connector(
            url="https://wazuh.example.com:55000",
            username="wazuh-wui",
            password="secret",
        )
        assert isinstance(connector, WazuhConnector)
        assert connector.base_url == "https://wazuh.example.com:55000"

    def test_create_connector_with_options(self):
        connector = create_wazuh_connector(
            url="https://wazuh.example.com:55000",
            username="wazuh-wui",
            password="secret",
            verify_tls=False,
            timeout_s=30,
            max_retries=5,
            rate_limit_per_minute=200,
        )
        assert connector.config.verify_tls is False
        assert connector.config.timeout_s == 30
        assert connector.config.max_retries == 5
        assert connector.config.rate_limit_per_minute == 200

    def test_invalid_url(self):
        with self.assertRaises(WazuhValidationError):
            create_wazuh_connector(
                url="",
                username="user",
                password="pass",
            )
        with self.assertRaises(WazuhValidationError):
            create_wazuh_connector(
                url="ftp://invalid",
                username="user",
                password="pass",
            )

    def test_invalid_api_version(self):
        with self.assertRaises(WazuhValidationError):
            create_wazuh_connector(
                url="https://host:55000",
                username="user",
                password="pass",
                api_version="v4;drop",
            )

    def test_invalid_rate_limit(self):
        with self.assertRaises(WazuhValidationError):
            create_wazuh_connector(
                url="https://host:55000",
                username="user",
                password="pass",
                rate_limit_per_minute=0,
            )

    def test_invalid_timeout(self):
        with self.assertRaises(WazuhValidationError):
            create_wazuh_connector(
                url="https://host:55000",
                username="user",
                password="pass",
                timeout_s=0.1,
            )


class TestParseHelpers(unittest.TestCase):
    """Test parsing helper methods."""

    def _make_connector(self) -> WazuhConnector:
        config = WazuhConfig(
            url="https://wazuh.example.com:55000",
            username="wazuh-wui",
            password="secret",
        )
        return WazuhConnector(config)

    def test_parse_agents_empty(self):
        connector = self._make_connector()
        result = connector._parse_agents({"data": {"affected_items": []}})
        assert result == []

    def test_parse_agents_valid(self):
        connector = self._make_connector()
        payload = {
            "data": {
                "affected_items": [
                    {
                        "id": "001",
                        "name": "agent1",
                        "ip": "192.168.1.100",
                        "status": "active",
                        "version": "4.7.0",
                        "os": {"name": "Ubuntu", "version": "22.04", "arch": "x86_64"},
                        "groups": ["default", "linux"],
                        "dateAdd": "2024-01-01T00:00:00Z",
                    }
                ]
            }
        }
        agents = connector._parse_agents(payload)
        assert len(agents) == 1
        assert agents[0].agent_id == "001"
        assert agents[0].agent_name == "agent1"
        assert agents[0].status == WazuhAgentStatus.ACTIVE
        assert agents[0].os == "Ubuntu"
        assert agents[0].groups == ["default", "linux"]

    def test_parse_agents_invalid_status(self):
        connector = self._make_connector()
        payload = {
            "data": {
                "affected_items": [
                    {
                        "id": "001",
                        "name": "agent1",
                        "status": "unknown_status",
                    }
                ]
            }
        }
        agents = connector._parse_agents(payload)
        assert len(agents) == 1
        assert agents[0].status == WazuhAgentStatus.NEVER_CONNECTED

    def test_parse_alerts_empty(self):
        connector = self._make_connector()
        result = connector._parse_alerts({"data": {"affected_items": []}})
        assert result == []

    def test_parse_alerts_valid(self):
        connector = self._make_connector()
        payload = {
            "data": {
                "affected_items": [
                    {
                        "id": "alert-001",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "rule": {
                            "id": 100100,
                            "level": 10,
                            "description": "Test rule",
                            "group": "authentication",
                            "mitre": {"id": "TA0001", "technique": "T1110"},
                        },
                        "agent": {"id": "001", "name": "agent1", "ip": "192.168.1.100"},
                        "full_log": "Test log",
                        "location": "/var/log/auth.log",
                    }
                ]
            }
        }
        alerts = connector._parse_alerts(payload)
        assert len(alerts) == 1
        assert alerts[0].alert_id == "alert-001"
        assert alerts[0].rule.rule_id == 100100
        assert alerts[0].severity == WazuhAlertSeverity.CRITICAL
        assert alerts[0].mitre_tactic == "TA0001"

    def test_parse_rules_empty(self):
        connector = self._make_connector()
        result = connector._parse_rules({"data": {"affected_items": []}})
        assert result == []

    def test_parse_rules_valid(self):
        connector = self._make_connector()
        payload = {
            "data": {
                "affected_items": [
                    {
                        "id": 100100,
                        "level": 10,
                        "description": "Test rule",
                        "groups": ["authentication", "ssh"],
                        "mitre": {"id": "TA0001", "technique": "T1110"},
                        "compliance": {"pci_dss": "10.2.1"},
                    }
                ]
            }
        }
        rules = connector._parse_rules(payload)
        assert len(rules) == 1
        assert rules[0].rule_id == 100100
        assert rules[0].group == WazuhRuleGroup.AUTHENTICATION
        assert rules[0].mitre_tactic == "TA0001"
        assert "10.2.1" in rules[0].compliance_refs

    def test_parse_decoders_empty(self):
        connector = self._make_connector()
        result = connector._parse_decoders({"data": {"affected_items": []}})
        assert result == []

    def test_parse_decoders_valid(self):
        connector = self._make_connector()
        payload = {
            "data": {
                "affected_items": [
                    {
                        "id": "decoder-001",
                        "name": "ssh_decoder",
                        "program_name": "sshd",
                        "parent": "root",
                        "regex": "^sshd.*$",
                    }
                ]
            }
        }
        decoders = connector._parse_decoders(payload)
        assert len(decoders) == 1
        assert decoders[0].decoder_id == "decoder-001"
        assert decoders[0].name == "ssh_decoder"

    def test_parse_syscheck_empty(self):
        connector = self._make_connector()
        result = connector._parse_syscheck({"data": {"affected_items": []}}, "001")
        assert result == []

    def test_parse_syscheck_valid(self):
        connector = self._make_connector()
        payload = {
            "data": {
                "affected_items": [
                    {
                        "file": "/etc/passwd",
                        "event": "modified",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "size": 1024,
                        "md5": "abc123",
                        "sha1": "def456",
                    }
                ]
            }
        }
        results = connector._parse_syscheck(payload, "001")
        assert len(results) == 1
        assert results[0].file_path == "/etc/passwd"
        assert results[0].event_type == "modified"

    def test_parse_rootcheck_empty(self):
        connector = self._make_connector()
        result = connector._parse_rootcheck({"data": {"affected_items": []}}, "001")
        assert result == []

    def test_parse_rootcheck_valid(self):
        connector = self._make_connector()
        payload = {
            "data": {
                "affected_items": [
                    {
                        "title": "Rootkit found",
                        "severity": "high",
                        "description": "Possible rootkit detected",
                    }
                ]
            }
        }
        results = connector._parse_rootcheck(payload, "001")
        assert len(results) == 1
        assert results[0].title == "Rootkit found"

    def test_parse_sca_empty(self):
        connector = self._make_connector()
        result = connector._parse_sca({"data": {"affected_items": []}}, "001")
        assert result == []

    def test_parse_sca_valid(self):
        connector = self._make_connector()
        payload = {
            "data": {
                "affected_items": [
                    {
                        "id": "sca-001",
                        "policy_id": "cis_ubuntu",
                        "name": "CIS Ubuntu Benchmark",
                        "pass": 50,
                        "fail": 10,
                        "invalid": 2,
                        "score": 80.0,
                    }
                ]
            }
        }
        results = connector._parse_sca(payload, "001")
        assert len(results) == 1
        assert results[0].policy_id == "cis_ubuntu"
        assert results[0].pass_count == 50
        assert results[0].fail_count == 10

    def test_parse_vulnerabilities_empty(self):
        connector = self._make_connector()
        result = connector._parse_vulnerabilities({"data": {"affected_items": []}}, "001")
        assert result == []

    def test_parse_vulnerabilities_valid(self):
        connector = self._make_connector()
        payload = {
            "data": {
                "affected_items": [
                    {
                        "cve": "CVE-2024-1234",
                        "severity": "high",
                        "title": "Test vulnerability",
                        "package": "openssl",
                        "version": "1.1.1",
                        "cvss_score": 7.5,
                    }
                ]
            }
        }
        results = connector._parse_vulnerabilities(payload, "001")
        assert len(results) == 1
        assert results[0].cve == "CVE-2024-1234"
        assert results[0].cvss_score == 7.5

    def test_parse_mitre_empty(self):
        connector = self._make_connector()
        result = connector._parse_mitre({"data": {"affected_items": []}})
        assert result == []

    def test_parse_mitre_valid(self):
        connector = self._make_connector()
        payload = {
            "data": {
                "affected_items": [
                    {
                        "id": "T1110",
                        "name": "Brute Force",
                        "description": "Adversaries may use brute force",
                        "tactics": ["credential-access"],
                        "platforms": ["Linux"],
                    }
                ]
            }
        }
        techniques = connector._parse_mitre(payload)
        assert len(techniques) == 1
        assert techniques[0].technique_id == "T1110"
        assert techniques[0].name == "Brute Force"

    def test_parse_cluster_nodes_empty(self):
        connector = self._make_connector()
        result = connector._parse_cluster_nodes({"data": {"affected_items": []}})
        assert result == []

    def test_parse_cluster_nodes_valid(self):
        connector = self._make_connector()
        payload = {
            "data": {
                "affected_items": [
                    {
                        "id": "node-001",
                        "name": "master-node",
                        "type": "master",
                        "ip": "10.0.0.1",
                        "version": "4.7.0",
                        "status": "connected",
                    }
                ]
            }
        }
        nodes = connector._parse_cluster_nodes(payload)
        assert len(nodes) == 1
        assert nodes[0].node_id == "node-001"
        assert nodes[0].node_type == "master"

    def test_parse_healthcheck(self):
        connector = self._make_connector()
        payload = {
            "data": {
                "status": "ok",
                "version": "4.7.0",
                "cluster_enabled": True,
                "cluster_name": "wazuh-cluster",
                "agents": {"total": 10, "active": 8, "disconnected": 2},
            }
        }
        hc = connector._parse_healthcheck(payload)
        assert hc.status == "ok"
        assert hc.cluster_enabled is True
        assert hc.agents == 10
        assert hc.agent_status == {"active": 8, "disconnected": 2}

    def test_parse_stats(self):
        connector = self._make_connector()
        payload = {
            "data": {
                "agents": {"total": 100, "active": 90, "disconnected": 10},
                "total_alerts": 5000,
                "alerts_today": 50,
                "rules_loaded": 2000,
                "decoders_loaded": 300,
            }
        }
        stats = connector._parse_stats(payload)
        assert stats.total_agents == 100
        assert stats.active_agents == 90
        assert stats.total_alerts == 5000
        assert stats.rules_loaded == 2000


class TestValidationHelpers(unittest.TestCase):
    """Test validation helper functions."""

    def test_validate_ip_valid_ipv4(self):
        from dcc.soc.wazuh.connector import _validate_ip_address
        assert _validate_ip_address("192.168.1.1") == "192.168.1.1"
        assert _validate_ip_address("10.0.0.1") == "10.0.0.1"

    def test_validate_ip_valid_ipv6(self):
        from dcc.soc.wazuh.connector import _validate_ip_address
        assert _validate_ip_address("::1") == "::1"
        assert _validate_ip_address("fe80::1") == "fe80::1"

    def test_validate_ip_invalid(self):
        from dcc.soc.wazuh.connector import _validate_ip_address
        with self.assertRaises(WazuhValidationError):
            _validate_ip_address("")
        with self.assertRaises(WazuhValidationError):
            _validate_ip_address("not-an-ip")
        with self.assertRaises(WazuhValidationError):
            _validate_ip_address("256.1.1.1")

    def test_validate_port_valid(self):
        from dcc.soc.wazuh.connector import _validate_port
        assert _validate_port(0) == 0
        assert _validate_port(80) == 80
        assert _validate_port(65535) == 65535
        assert _validate_port(None) is None

    def test_validate_port_invalid(self):
        from dcc.soc.wazuh.connector import _validate_port
        with self.assertRaises(WazuhValidationError):
            _validate_port(-1)
        with self.assertRaises(WazuhValidationError):
            _validate_port(65536)

    def test_safe_int(self):
        from dcc.soc.wazuh.connector import _safe_int
        assert _safe_int(42) == 42
        assert _safe_int("42") == 42
        assert _safe_int(None) is None
        assert _safe_int("abc") is None
        assert _safe_int(5, min_val=0, max_val=10) == 5
        assert _safe_int(15, min_val=0, max_val=10) is None
        assert _safe_int(-1, min_val=0) is None

    def test_safe_float(self):
        from dcc.soc.wazuh.connector import _safe_float
        assert _safe_float(3.14) == 3.14
        assert _safe_float("3.14") == 3.14
        assert _safe_float(None) is None
        assert _safe_float("abc") is None
        assert _safe_float(5.0, min_val=0.0, max_val=10.0) == 5.0
        assert _safe_float(15.0, min_val=0.0, max_val=10.0) is None
        assert _safe_float(float("nan")) is None
        assert _safe_float(float("inf")) is None


class TestErrorHierarchy(unittest.TestCase):
    """Test error class hierarchy."""

    def test_error_inheritance(self):
        assert issubclass(WazuhConnectionError, WazuhConnectorError)
        assert issubclass(WazuhAuthenticationError, WazuhConnectorError)
        assert issubclass(WazuhValidationError, WazuhConnectorError)
        assert issubclass(WazuhRateLimitError, WazuhConnectorError)


if __name__ == "__main__":
    unittest.main()