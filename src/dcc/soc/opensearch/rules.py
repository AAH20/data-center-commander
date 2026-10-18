"""OpenSearch detection rules — correlation, threshold, and anomaly rules."""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .models import (
    OpenSearchAlert,
    OpenSearchAlertSeverity,
    OpenSearchEvent,
    OpenSearchEventStatus,
    OpenSearchRule,
    OpenSearchRuleType,
)

logger = logging.getLogger(__name__)


class OpenSearchRuleEngine:
    """Manages OpenSearch detection rules and alert matching."""

    def __init__(self) -> None:
        self._rules: dict[str, OpenSearchRule] = {}
        self._alerts: dict[str, OpenSearchAlert] = {}

    def create_rule(
        self,
        name: str,
        description: str = "",
        rule_type: OpenSearchRuleType = OpenSearchRuleType.MATCH,
        severity: OpenSearchAlertSeverity = OpenSearchAlertSeverity.MEDIUM,
        condition: str = "",
        index_pattern: str = "",
        threshold: int = 1,
        timeframe: int = 300,
        group_by: Optional[list[str]] = None,
        fields: Optional[list[str]] = None,
        match_patterns: Optional[list[str]] = None,
        mitre_tactics: Optional[list[str]] = None,
        mitre_techniques: Optional[list[str]] = None,
        compliance_refs: Optional[list[str]] = None,
    ) -> OpenSearchRule:
        """Create a new detection rule."""
        rule_id = f"rule-{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
        rule = OpenSearchRule(
            rule_id=rule_id,
            name=name,
            description=description,
            rule_type=rule_type,
            severity=severity,
            condition=condition,
            index_pattern=index_pattern,
            threshold=threshold,
            timeframe=timeframe,
            group_by=group_by or [],
            fields=fields or [],
            match_patterns=match_patterns or [],
            mitre_tactics=mitre_tactics or [],
            mitre_techniques=mitre_techniques or [],
            compliance_refs=compliance_refs or [],
        )
        self._rules[rule_id] = rule
        logger.info("Created OpenSearch rule: %s", name)
        return rule

    def create_brute_force_rule(
        self,
        name: str = "Brute Force Attack Detection",
        threshold: int = 10,
        timeframe: int = 300,
    ) -> OpenSearchRule:
        """Create a brute force attack detection rule."""
        return self.create_rule(
            name=name,
            description=f"Detects brute force attacks ({threshold} failed logins in {timeframe}s)",
            rule_type=OpenSearchRuleType.THRESHOLD,
            severity=OpenSearchAlertSeverity.HIGH,
            condition=f"count:>{threshold}",
            threshold=threshold,
            timeframe=timeframe,
            fields=["src_ip", "user"],
            match_patterns=["Failed password", "authentication failed", "Invalid user"],
            mitre_tactics=["Credential Access"],
            mitre_techniques=["T1110"],
            compliance_refs=["NIST-800-53-IA-2", "PCI-DSS-8.1.6"],
        )

    def create_port_scan_rule(
        self,
        name: str = "Port Scan Detection",
        threshold: int = 20,
        timeframe: int = 60,
    ) -> OpenSearchRule:
        """Create a port scan detection rule."""
        return self.create_rule(
            name=name,
            description=f"Detects port scans ({threshold} ports in {timeframe}s)",
            rule_type=OpenSearchRuleType.THRESHOLD,
            severity=OpenSearchAlertSeverity.MEDIUM,
            condition=f"count:>{threshold}",
            threshold=threshold,
            timeframe=timeframe,
            fields=["src_ip", "dst_port"],
            match_patterns=["SYN scan", "port scan", "connection refused"],
            mitre_tactics=["Discovery"],
            mitre_techniques=["T1046"],
            compliance_refs=["NIST-800-53-SI-4"],
        )

    def create_malware_detection_rule(
        self,
        name: str = "Malware Detection",
    ) -> OpenSearchRule:
        """Create a malware detection rule."""
        return self.create_rule(
            name=name,
            description="Detects malware-related events",
            rule_type=OpenSearchRuleType.MATCH,
            severity=OpenSearchAlertSeverity.CRITICAL,
            condition="event_type:malware OR event_type:virus OR event_type:trojan",
            match_patterns=["malware", "virus", "trojan", "ransomware", "backdoor"],
            mitre_tactics=["Execution"],
            mitre_techniques=["T1204"],
            compliance_refs=["NIST-800-53-SI-3", "PCI-DSS-5.1"],
        )

    def create_data_exfiltration_rule(
        self,
        name: str = "Data Exfiltration Detection",
        threshold: int = 1000000,
        timeframe: int = 3600,
    ) -> OpenSearchRule:
        """Create a data exfiltration detection rule."""
        return self.create_rule(
            name=name,
            description=f"Detects potential data exfiltration ({threshold} bytes in {timeframe}s)",
            rule_type=OpenSearchRuleType.THRESHOLD,
            severity=OpenSearchAlertSeverity.HIGH,
            condition=f"sum:bytes:>{threshold}",
            threshold=threshold,
            timeframe=timeframe,
            fields=["src_ip", "dst_ip", "bytes"],
            match_patterns=["large upload", "unusual outbound"],
            mitre_tactics=["Exfiltration"],
            mitre_techniques=["T1041"],
            compliance_refs=["NIST-800-53-SC-8", "PCI-DSS-3.4"],
        )

    def create_privilege_escalation_rule(
        self,
        name: str = "Privilege Escalation Detection",
    ) -> OpenSearchRule:
        """Create a privilege escalation detection rule."""
        return self.create_rule(
            name=name,
            description="Detects privilege escalation attempts",
            rule_type=OpenSearchRuleType.MATCH,
            severity=OpenSearchAlertSeverity.HIGH,
            condition="event_type:privilege_escalation OR event_type:sudo_abuse",
            match_patterns=["sudo", "su -", "privilege escalation", "chmod 4755"],
            mitre_tactics=["Privilege Escalation"],
            mitre_techniques=["T1068"],
            compliance_refs=["NIST-800-53-AC-6"],
        )

    def create_lateral_movement_rule(
        self,
        name: str = "Lateral Movement Detection",
    ) -> OpenSearchRule:
        """Create a lateral movement detection rule."""
        return self.create_rule(
            name=name,
            description="Detects lateral movement attempts",
            rule_type=OpenSearchRuleType.MATCH,
            severity=OpenSearchAlertSeverity.HIGH,
            condition="event_type:lateral_movement OR event_type:psexec OR event_type:wmi",
            match_patterns=["psexec", "wmiexec", "smbexec", "winrm"],
            mitre_tactics=["Lateral Movement"],
            mitre_techniques=["T1021"],
            compliance_refs=["NIST-800-53-SI-4"],
        )

    def create_web_attack_rule(
        self,
        name: str = "Web Attack Detection",
    ) -> OpenSearchRule:
        """Create a web attack detection rule."""
        return self.create_rule(
            name=name,
            description="Detects web-based attacks (SQLi, XSS, etc.)",
            rule_type=OpenSearchRuleType.MATCH,
            severity=OpenSearchAlertSeverity.HIGH,
            condition="event_type:sqli OR event_type:xss OR event_type:rfi OR event_type:lfi",
            match_patterns=["SELECT * FROM", "<script>", "../", "UNION SELECT"],
            mitre_tactics=["Initial Access"],
            mitre_techniques=["T1190"],
            compliance_refs=["NIST-800-53-SI-10", "PCI-DSS-6.5.1"],
        )

    def create_anomaly_detection_rule(
        self,
        name: str = "Anomaly Detection",
    ) -> OpenSearchRule:
        """Create an anomaly detection rule."""
        return self.create_rule(
            name=name,
            description="Detects anomalous behavior patterns",
            rule_type=OpenSearchRuleType.ANOMALY,
            severity=OpenSearchAlertSeverity.MEDIUM,
            condition="trend:deviation:>2",
            mitre_tactics=["Defense Evasion"],
            mitre_techniques=["T1078"],
        )

    def create_ddos_detection_rule(
        self,
        name: str = "DDoS Detection",
        threshold: int = 1000,
        timeframe: int = 60,
    ) -> OpenSearchRule:
        """Create a DDoS detection rule."""
        return self.create_rule(
            name=name,
            description=f"Detects DDoS attacks ({threshold} requests in {timeframe}s)",
            rule_type=OpenSearchRuleType.THRESHOLD,
            severity=OpenSearchAlertSeverity.CRITICAL,
            condition=f"count:>{threshold}",
            threshold=threshold,
            timeframe=timeframe,
            fields=["src_ip", "dst_ip", "dst_port"],
            match_patterns=["SYN flood", "UDP flood", "HTTP flood"],
            mitre_tactics=["Impact"],
            mitre_techniques=["T1498"],
            compliance_refs=["NIST-800-53-SC-5"],
        )

    def create_account_lockout_rule(
        self,
        name: str = "Account Lockout Storm",
        threshold: int = 3,
        timeframe: int = 300,
    ) -> OpenSearchRule:
        """Create an account lockout detection rule."""
        return self.create_rule(
            name=name,
            description=f"Detects account lockout storms ({threshold} lockouts in {timeframe}s)",
            rule_type=OpenSearchRuleType.THRESHOLD,
            severity=OpenSearchAlertSeverity.HIGH,
            condition=f"count:>{threshold}",
            threshold=threshold,
            timeframe=timeframe,
            fields=["user", "src_ip"],
            match_patterns=["account locked", "locked out", "too many failed attempts"],
            mitre_tactics=["Credential Access"],
            mitre_techniques=["T1110"],
            compliance_refs=["NIST-800-53-IA-5"],
        )

    def get_rule(self, rule_id: str) -> Optional[OpenSearchRule]:
        """Get a rule by ID."""
        return self._rules.get(rule_id)

    def list_rules(
        self,
        rule_type: Optional[OpenSearchRuleType] = None,
        severity: Optional[OpenSearchAlertSeverity] = None,
        enabled_only: bool = False,
    ) -> list[OpenSearchRule]:
        """List rules with optional filters."""
        rules = list(self._rules.values())
        if rule_type:
            rules = [r for r in rules if r.rule_type == rule_type]
        if severity:
            rules = [r for r in rules if r.severity == severity]
        if enabled_only:
            rules = [r for r in rules if r.status == "enabled"]
        return rules

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule."""
        rule = self._rules.get(rule_id)
        if rule:
            rule.status = "enabled"
            rule.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule."""
        rule = self._rules.get(rule_id)
        if rule:
            rule.status = "disabled"
            rule.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def match_event(self, event: OpenSearchEvent) -> list[OpenSearchRule]:
        """Match an event against all enabled rules."""
        matched: list[OpenSearchRule] = []
        for rule in self._rules.values():
            if rule.status != "enabled":
                continue
            if self._rule_matches(rule, event):
                matched.append(rule)
        return matched

    def _rule_matches(self, rule: OpenSearchRule, event: OpenSearchEvent) -> bool:
        """Check if a rule matches an event."""
        if rule.match_patterns:
            for pattern in rule.match_patterns:
                if pattern.lower() in event.raw_log.lower():
                    return True
        if rule.condition:
            if self._evaluate_condition(rule.condition, event):
                return True
        return False

    def _evaluate_condition(self, condition: str, event: OpenSearchEvent) -> bool:
        """Evaluate a condition string against an event."""
        if "OR" in condition:
            parts = condition.split(" OR ")
            return any(self._evaluate_condition(p.strip(), event) for p in parts)
        if "AND" in condition:
            parts = condition.split(" AND ")
            return all(self._evaluate_condition(p.strip(), event) for p in parts)
        if ":" in condition:
            field, _, value = condition.partition(":")
            field = field.strip()
            value = value.strip()
            actual = self._get_event_field(event, field)
            return value.lower() in str(actual).lower()
        return False

    def _get_event_field(self, event: OpenSearchEvent, field_path: str) -> str:
        """Get a field value from an event using dot notation."""
        parts = field_path.split(".")
        obj: Any = event

        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                return ""

        if hasattr(obj, "value"):
            return str(getattr(obj, "value"))
        return str(obj) if obj is not None else ""

    def create_alert(
        self,
        rule: OpenSearchRule,
        event: OpenSearchEvent,
        message: str = "",
    ) -> OpenSearchAlert:
        """Create an alert from a matched rule and event."""
        alert_id = f"alert-{uuid.uuid4().hex[:12]}"
        alert = OpenSearchAlert(
            alert_id=alert_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            rule_id=rule.rule_id,
            rule_name=rule.name,
            severity=rule.severity,
            status=OpenSearchEventStatus.OPEN,
            source=event.source,
            message=message or rule.description,
            index_name=event.index_name,
            src_ip=event.src_ip,
            dst_ip=event.dst_ip,
            src_port=event.src_port,
            dst_port=event.dst_port,
            protocol=event.protocol,
            user=event.user,
            program_name=event.program_name,
            file_path=event.file_path,
            full_log=event.raw_log,
            fields=event.decoded_fields,
            mitre_tactics=rule.mitre_tactics,
            mitre_techniques=rule.mitre_techniques,
            compliance_refs=rule.compliance_refs,
        )
        self._alerts[alert_id] = alert
        logger.info("Created OpenSearch alert: %s (severity: %s)", rule.name, rule.severity.name)
        return alert

    def get_alert(self, alert_id: str) -> Optional[OpenSearchAlert]:
        """Get an alert by ID."""
        return self._alerts.get(alert_id)

    def list_alerts(
        self,
        severity: Optional[OpenSearchAlertSeverity] = None,
        status: Optional[OpenSearchEventStatus] = None,
        source: str = "",
        limit: int = 100,
    ) -> list[OpenSearchAlert]:
        """List alerts with optional filters."""
        alerts = list(self._alerts.values())
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if status:
            alerts = [a for a in alerts if a.status == status]
        if source:
            alerts = [a for a in alerts if a.source == source]
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)[:limit]

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.status = OpenSearchEventStatus.ACKNOWLEDGED
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = datetime.now(timezone.utc).isoformat()
            logger.info("Alert %s acknowledged by %s", alert_id, acknowledged_by)
            return True
        return False

    def resolve_alert(self, alert_id: str, notes: str = "") -> bool:
        """Resolve an alert."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.status = OpenSearchEventStatus.RESOLVED
            alert.resolved_at = datetime.now(timezone.utc).isoformat()
            if notes:
                alert.notes = notes
            logger.info("Alert %s resolved", alert_id)
            return True
        return False

    def mark_false_positive(self, alert_id: str, notes: str = "") -> bool:
        """Mark an alert as false positive."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.status = OpenSearchEventStatus.FALSE_POSITIVE
            alert.resolved_at = datetime.now(timezone.utc).isoformat()
            if notes:
                alert.notes = notes
            logger.info("Alert %s marked as false positive", alert_id)
            return True
        return False

    def get_open_alerts(
        self, min_severity: OpenSearchAlertSeverity = OpenSearchAlertSeverity.LOW
    ) -> list[OpenSearchAlert]:
        """Get all open alerts with severity >= min_severity."""
        return [
            a
            for a in self._alerts.values()
            if a.status == OpenSearchEventStatus.OPEN and a.severity >= min_severity
        ]

    def get_alert_stats(self) -> dict[str, Any]:
        """Get alert statistics."""
        stats: dict[str, Any] = {
            "total": len(self._alerts),
            "open": 0,
            "acknowledged": 0,
            "resolved": 0,
            "false_positive": 0,
            "by_severity": {s.name: 0 for s in OpenSearchAlertSeverity},
        }
        for alert in self._alerts.values():
            if alert.status == OpenSearchEventStatus.OPEN:
                stats["open"] += 1
            elif alert.status == OpenSearchEventStatus.ACKNOWLEDGED:
                stats["acknowledged"] += 1
            elif alert.status == OpenSearchEventStatus.RESOLVED:
                stats["resolved"] += 1
            elif alert.status == OpenSearchEventStatus.FALSE_POSITIVE:
                stats["false_positive"] += 1
            stats["by_severity"][alert.severity.name] += 1
        return stats

    def to_api_payload(self, rule: OpenSearchRule) -> dict[str, Any]:
        """Convert rule to OpenSearch API payload."""
        return {
            "name": rule.name,
            "description": rule.description,
            "type": rule.rule_type.value,
            "severity": rule.severity.value,
            "status": rule.status,
            "condition": rule.condition,
            "index_pattern": rule.index_pattern,
            "threshold": rule.threshold,
            "timeframe": rule.timeframe,
            "group_by": rule.group_by,
            "fields": rule.fields,
            "match_patterns": rule.match_patterns,
            "mitre_tactics": rule.mitre_tactics,
            "mitre_techniques": rule.mitre_techniques,
            "compliance_refs": rule.compliance_refs,
            "tags": rule.tags,
        }
