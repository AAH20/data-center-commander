"""OSSEC detection rules — correlation and enrichment rules."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .models import OSSECAlert, OSSECEvent, OSSECGroup, OSSECRule, Severity


@dataclass
class CorrelationRule:
    """A correlation rule for multi-event detection."""

    rule_id: str
    name: str
    description: str
    severity: Severity
    group: OSSECGroup
    conditions: list[dict] = field(default_factory=list)
    timeframe: int = 300  # seconds
    threshold: int = 1
    enabled: bool = True
    mitre_tactic: str = ""
    mitre_technique: str = ""
    compliance_refs: list[str] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)


# Pre-built correlation rules
CORRELATION_RULES: list[CorrelationRule] = [
    CorrelationRule(
        rule_id="CORR-001",
        name="Brute Force SSH Detection",
        description="Multiple failed SSH authentication attempts from same source",
        severity=Severity.HIGH,
        group=OSSECGroup.AUTHENTICATION,
        conditions=[
            {"field": "rule.group", "op": "eq", "value": "authentication"},
            {"field": "rule.description", "op": "contains", "value": "Failed password"},
        ],
        timeframe=300,
        threshold=5,
        mitre_tactic="Credential Access",
        mitre_technique="T1110",
        compliance_refs=["CIS-5.2.1", "NIST-IA-5"],
    ),
    CorrelationRule(
        rule_id="CORR-002",
        name="Privilege Escalation Detection",
        description="Sudo or su usage followed by root command execution",
        severity=Severity.CRITICAL,
        group=OSSECGroup.AUTHENTICATION,
        conditions=[
            {"field": "rule.group", "op": "eq", "value": "sudo"},
            {"field": "rule.description", "op": "contains", "value": "COMMAND"},
        ],
        timeframe=60,
        threshold=1,
        mitre_tactic="Privilege Escalation",
        mitre_technique="T1548",
        compliance_refs=["CIS-5.2.4", "NIST-AC-6"],
    ),
    CorrelationRule(
        rule_id="CORR-003",
        name="File Integrity Violation",
        description="Critical system file modified outside change window",
        severity=Severity.HIGH,
        group=OSSECGroup.INTEGRITY_CHECK,
        conditions=[
            {"field": "rule.group", "op": "eq", "value": "syscheck"},
            {"field": "rule.description", "op": "contains", "value": "Integrity checksum changed"},
        ],
        timeframe=0,
        threshold=1,
        mitre_tactic="Defense Evasion",
        mitre_technique="T1070",
        compliance_refs=["CIS-3.4", "NIST-SI-7"],
    ),
    CorrelationRule(
        rule_id="CORR-004",
        name="Web Attack Detection",
        description="Multiple web attack patterns detected",
        severity=Severity.HIGH,
        group=OSSECGroup.WEB,
        conditions=[
            {"field": "rule.group", "op": "eq", "value": "web-accesslog"},
            {"field": "rule.description", "op": "contains", "value": "attack"},
        ],
        timeframe=60,
        threshold=3,
        mitre_tactic="Initial Access",
        mitre_technique="T1190",
        compliance_refs=["CIS-6.5", "NIST-SI-4"],
    ),
    CorrelationRule(
        rule_id="CORR-005",
        name="Rootkit Detection",
        description="Rootkit indicators found by OSSEC rootcheck",
        severity=Severity.EMERGENCY,
        group=OSSECGroup.ROOTKIT,
        conditions=[
            {"field": "rule.group", "op": "eq", "value": "rootcheck"},
            {"field": "rule.description", "op": "contains", "value": "Rootkit"},
        ],
        timeframe=0,
        threshold=1,
        mitre_tactic="Defense Evasion",
        mitre_technique="T1014",
        compliance_refs=["CIS-3.1", "NIST-SI-3"],
    ),
    CorrelationRule(
        rule_id="CORR-006",
        name="Firewall Block Storm",
        description="High volume of firewall blocks from single source",
        severity=Severity.MEDIUM,
        group=OSSECGroup.FIREWALL,
        conditions=[
            {"field": "rule.group", "op": "eq", "value": "firewall"},
            {"field": "rule.description", "op": "contains", "value": "blocked"},
        ],
        timeframe=60,
        threshold=10,
        mitre_tactic="Defense Evasion",
        mitre_technique="T1070",
        compliance_refs=["CIS-4.1", "NIST-SC-7"],
    ),
    CorrelationRule(
        rule_id="CORR-007",
        name="Malware Detection",
        description="OSSEC detected known malware signatures",
        severity=Severity.CRITICAL,
        group=OSSECGroup.SYSTEM,
        conditions=[
            {"field": "rule.group", "op": "eq", "value": "syscheck"},
            {"field": "rule.description", "op": "contains", "value": "malware"},
        ],
        timeframe=0,
        threshold=1,
        mitre_tactic="Execution",
        mitre_technique="T1204",
        compliance_refs=["CIS-3.2", "NIST-SI-3"],
    ),
    CorrelationRule(
        rule_id="CORR-008",
        name="Account Lockout Storm",
        description="Multiple account lockouts indicating brute force",
        severity=Severity.HIGH,
        group=OSSECGroup.AUTHENTICATION,
        conditions=[
            {"field": "rule.group", "op": "eq", "value": "pam"},
            {"field": "rule.description", "op": "contains", "value": "locked"},
        ],
        timeframe=300,
        threshold=3,
        mitre_tactic="Credential Access",
        mitre_technique="T1110",
        compliance_refs=["CIS-5.2.1", "NIST-IA-5"],
    ),
]


class RuleEngine:
    """OSSEC rule matching and correlation engine."""

    def __init__(self) -> None:
        self.rules: list[OSSECRule] = []
        self.correlation_rules: list[CorrelationRule] = list(CORRELATION_RULES)
        self._event_buffer: list[OSSECEvent] = []

    def load_rules(self, rules: list[OSSECRule]) -> None:
        """Load OSSEC rules into the engine."""
        self.rules = rules

    def match_event(self, event: OSSECEvent) -> list[OSSECRule]:
        """Match an event against loaded rules."""
        matched: list[OSSECRule] = []
        for rule in self.rules:
            if self._rule_matches(rule, event):
                matched.append(rule)
        return matched

    def _rule_matches(self, rule: OSSECRule, event: OSSECEvent) -> bool:
        """Check if a rule matches an event."""
        if rule.regex:
            try:
                if re.search(rule.regex, event.raw_log):
                    return True
            except re.error:
                pass

        if rule.program_name and event.program_name:
            if rule.program_name in event.program_name:
                return True

        if rule.src_ip and event.src_ip:
            if rule.src_ip == event.src_ip:
                return True

        return False

    def correlate(self, alerts: list[OSSECAlert]) -> list[dict]:
        """Run correlation rules against alert set."""
        results: list[dict] = []

        for corr_rule in self.correlation_rules:
            if not corr_rule.enabled:
                continue

            matching_alerts = self._find_matching_alerts(corr_rule, alerts)

            if len(matching_alerts) >= corr_rule.threshold:
                results.append(
                    {
                        "rule_id": corr_rule.rule_id,
                        "name": corr_rule.name,
                        "description": corr_rule.description,
                        "severity": corr_rule.severity,
                        "matched_alerts": len(matching_alerts),
                        "alert_ids": [a.alert_id for a in matching_alerts],
                        "mitre_tactic": corr_rule.mitre_tactic,
                        "mitre_technique": corr_rule.mitre_technique,
                        "compliance_refs": corr_rule.compliance_refs,
                    }
                )

        return results

    def _find_matching_alerts(
        self, corr_rule: CorrelationRule, alerts: list[OSSECAlert]
    ) -> list[OSSECAlert]:
        """Find alerts matching a correlation rule."""
        matching: list[OSSECAlert] = []

        for alert in alerts:
            if self._alert_matches_correlation(corr_rule, alert):
                matching.append(alert)

        return matching

    def _alert_matches_correlation(
        self, corr_rule: CorrelationRule, alert: OSSECAlert
    ) -> bool:
        """Check if an alert matches correlation rule conditions."""
        for condition in corr_rule.conditions:
            field = condition["field"]
            op = condition["op"]
            value = condition["value"]

            actual = self._get_alert_field(alert, field)

            if op == "eq" and actual != value:
                return False
            elif op == "contains" and value not in str(actual):
                return False
            elif op == "gt" and not (actual > value):
                return False
            elif op == "lt" and not (actual < value):
                return False

        return True

    def _get_alert_field(self, alert: OSSECAlert, field_path: str) -> str:
        """Get a field value from an alert using dot notation."""
        parts = field_path.split(".")
        obj: object = alert

        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                return ""

        # Handle enums - return the value, not the enum name
        if hasattr(obj, "value"):
            return str(obj.value)
        return str(obj) if obj is not None else ""
