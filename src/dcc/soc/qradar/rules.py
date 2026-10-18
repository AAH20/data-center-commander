"""QRadar custom rules for data center security monitoring.

Provides rule definitions that can be imported into QRadar to detect
data center-specific security events, anomalies, and policy violations.
Rules are defined as Python data structures that map to QRadar's
custom rule JSON format.

Contract/design only — no live QRadar integration is certified.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Rule categories
# ---------------------------------------------------------------------------

class RuleCategory(str, Enum):
    """Category of a data center security rule."""
    INTRUSION_DETECTION = "intrusion_detection"
    ANOMALY_DETECTION = "anomaly_detection"
    POLICY_VIOLATION = "policy_violation"
    COMPLIANCE = "compliance"
    THREAT_INTEL = "threat_intel"
    DATA_EXFILTRATION = "data_exfiltration"
    LATERAL_MOVEMENT = "lateral_movement"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    MALWARE = "malware"
    BRUTE_FORCE = "brute_force"
    DDOS = "ddos"
    INSIDER_THREAT = "insider_threat"


class RuleSeverity(str, Enum):
    """Severity level of a rule."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RuleResponseType(str, Enum):
    """Response action when a rule triggers."""
    LOG = "log"
    EMAIL = "email"
    SNMP_TRAP = "snmp_trap"
    SYSLOG = "syslog"
    TICKET = "ticket"
    BLOCK_IP = "block_ip"
    QUARANTINE = "quarantine"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Rule definition models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class RuleCondition:
    """A single condition within a rule."""
    field: str
    operator: str  # equals, not_equals, contains, not_contains, greater_than, less_than, in, not_in, regex
    value: Any
    case_sensitive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator,
            "value": self.value,
            "case_sensitive": self.case_sensitive,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuleCondition:
        return cls(
            field=str(data["field"]),
            operator=str(data["operator"]),
            value=data.get("value"),
            case_sensitive=bool(data.get("case_sensitive", False)),
        )


@dataclass(slots=True)
class RuleAction:
    """An action to take when a rule triggers."""
    action_type: RuleResponseType
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuleAction:
        return cls(
            action_type=RuleResponseType(data.get("action_type", "log")),
            parameters=dict(data.get("parameters", {})),
        )


@dataclass(slots=True)
class QRadarRuleDefinition:
    """A complete QRadar custom rule definition."""
    rule_id: str
    name: str
    category: RuleCategory
    severity: RuleSeverity
    description: str
    conditions: list[RuleCondition] = field(default_factory=list)
    actions: list[RuleAction] = field(default_factory=list)
    enabled: bool = True
    mitre_tactics: list[str] = field(default_factory=list)
    mitre_techniques: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    false_positive_rate: float = 0.0
    confidence: int = 0
    relevance: int = 0
    impact: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "category": self.category.value,
            "severity": self.severity.value,
            "description": self.description,
            "conditions": [c.to_dict() for c in self.conditions],
            "actions": [a.to_dict() for a in self.actions],
            "enabled": self.enabled,
            "mitre_tactics": list(self.mitre_tactics),
            "mitre_techniques": list(self.mitre_techniques),
            "tags": list(self.tags),
            "false_positive_rate": self.false_positive_rate,
            "confidence": self.confidence,
            "relevance": self.relevance,
            "impact": self.impact,
            "metadata": dict(self.metadata),
        }

    def to_qradar_json(self) -> str:
        """Export as QRadar-compatible custom rule JSON."""
        qradar_format = {
            "name": self.name,
            "description": self.description,
            "type": "EVENT",
            "enabled": self.enabled,
            "group": "Data Center Commander",
            "origin": "custom",
            "severity": self.severity.value,
            "credibility": self.confidence,
            "relevance": self.relevance,
            "impact": self.impact,
            "test": {
                "type": "AND",
                "tests": [
                    {
                        "field": c.field,
                        "operator": c.operator,
                        "value": c.value,
                        "caseSensitive": c.case_sensitive,
                    }
                    for c in self.conditions
                ],
            },
            "actions": [
                {
                    "type": a.action_type.value,
                    "parameters": a.parameters,
                }
                for a in self.actions
            ],
            "tags": self.tags,
            "mitre_tactics": self.mitre_tactics,
            "mitre_techniques": self.mitre_techniques,
        }
        return json.dumps(qradar_format, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QRadarRuleDefinition:
        """Reconstruct from dictionary."""
        return cls(
            rule_id=str(data["rule_id"]),
            name=str(data.get("name", "")),
            category=RuleCategory(data.get("category", "intrusion_detection")),
            severity=RuleSeverity(data.get("severity", "medium")),
            description=str(data.get("description", "")),
            conditions=[RuleCondition.from_dict(c) for c in data.get("conditions", [])],
            actions=[RuleAction.from_dict(a) for a in data.get("actions", [])],
            enabled=bool(data.get("enabled", True)),
            mitre_tactics=list(data.get("mitre_tactics", [])),
            mitre_techniques=list(data.get("mitre_techniques", [])),
            tags=list(data.get("tags", [])),
            false_positive_rate=float(data.get("false_positive_rate", 0.0)),
            confidence=int(data.get("confidence", 0)),
            relevance=int(data.get("relevance", 0)),
            impact=int(data.get("impact", 0)),
            metadata=dict(data.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Pre-built data center security rules
# ---------------------------------------------------------------------------

def get_data_center_rules() -> list[QRadarRuleDefinition]:
    """Return the default set of data center security rules for QRadar."""
    return [
        # Rule 1: Brute force detection
        QRadarRuleDefinition(
            rule_id="dcc-brute-force-001",
            name="DCC: Brute Force Authentication Attempts",
            category=RuleCategory.BRUTE_FORCE,
            severity=RuleSeverity.HIGH,
            description="Detects multiple failed authentication attempts from a single source IP within a short time window, indicating a brute force attack.",
            conditions=[
                RuleCondition(field="event_category", operator="equals", value="authentication"),
                RuleCondition(field="event_outcome", operator="equals", value="failure"),
                RuleCondition(field="event_count", operator="greater_than", value=10),
            ],
            actions=[
                RuleAction(action_type=RuleResponseType.LOG, parameters={"priority": "high"}),
                RuleAction(action_type=RuleResponseType.EMAIL, parameters={"recipients": ["soc@example.com"]}),
            ],
            mitre_tactics=["Credential Access"],
            mitre_techniques=["T1110"],
            tags=["brute-force", "authentication", "dcc"],
            confidence=8,
            relevance=7,
            impact=6,
        ),
        # Rule 2: Data exfiltration detection
        QRadarRuleDefinition(
            rule_id="dcc-exfil-001",
            name="DCC: Potential Data Exfiltration",
            category=RuleCategory.DATA_EXFILTRATION,
            severity=RuleSeverity.CRITICAL,
            description="Detects large outbound data transfers to unknown or suspicious destinations, indicating potential data exfiltration.",
            conditions=[
                RuleCondition(field="direction", operator="equals", value="outbound"),
                RuleCondition(field="bytes_out", operator="greater_than", value=100_000_000),
                RuleCondition(field="destination_reputation", operator="equals", value="unknown"),
            ],
            actions=[
                RuleAction(action_type=RuleResponseType.LOG, parameters={"priority": "critical"}),
                RuleAction(action_type=RuleResponseType.BLOCK_IP, parameters={"duration_minutes": 60}),
                RuleAction(action_type=RuleResponseType.TICKET, parameters={"assignee": "soc-l2"}),
            ],
            mitre_tactics=["Exfiltration"],
            mitre_techniques=["T1041", "T1048"],
            tags=["exfiltration", "data-loss", "dcc"],
            confidence=9,
            relevance=8,
            impact=9,
        ),
        # Rule 3: Lateral movement detection
        QRadarRuleDefinition(
            rule_id="dcc-lateral-001",
            name="DCC: Lateral Movement Detection",
            category=RuleCategory.LATERAL_MOVEMENT,
            severity=RuleSeverity.HIGH,
            description="Detects internal host-to-host connections that deviate from normal communication patterns, indicating potential lateral movement.",
            conditions=[
                RuleCondition(field="source_network", operator="equals", value="internal"),
                RuleCondition(field="destination_network", operator="equals", value="internal"),
                RuleCondition(field="connection_type", operator="equals", value="new"),
                RuleCondition(field="port", operator="in", value=[445, 135, 139, 3389, 5985, 5986]),
            ],
            actions=[
                RuleAction(action_type=RuleResponseType.LOG, parameters={"priority": "high"}),
                RuleAction(action_type=RuleResponseType.SNMP_TRAP, parameters={"community": "public"}),
            ],
            mitre_tactics=["Lateral Movement"],
            mitre_techniques=["T1021"],
            tags=["lateral-movement", "internal", "dcc"],
            confidence=7,
            relevance=8,
            impact=7,
        ),
        # Rule 4: Privilege escalation detection
        QRadarRuleDefinition(
            rule_id="dcc-privesc-001",
            name="DCC: Privilege Escalation Attempt",
            category=RuleCategory.PRIVILEGE_ESCALATION,
            severity=RuleSeverity.CRITICAL,
            description="Detects attempts to gain elevated privileges through suspicious account modifications or exploit patterns.",
            conditions=[
                RuleCondition(field="event_type", operator="equals", value="account_modification"),
                RuleCondition(field="privilege_change", operator="equals", value="elevated"),
                RuleCondition(field="user", operator="not_equals", value="system"),
            ],
            actions=[
                RuleAction(action_type=RuleResponseType.LOG, parameters={"priority": "critical"}),
                RuleAction(action_type=RuleResponseType.EMAIL, parameters={"recipients": ["soc@example.com", "admin@example.com"]}),
                RuleAction(action_type=RuleResponseType.TICKET, parameters={"assignee": "soc-l3"}),
            ],
            mitre_tactics=["Privilege Escalation"],
            mitre_techniques=["T1078", "T1098"],
            tags=["privilege-escalation", "account", "dcc"],
            confidence=8,
            relevance=7,
            impact=8,
        ),
        # Rule 5: DDoS detection
        QRadarRuleDefinition(
            rule_id="dcc-ddos-001",
            name="DCC: DDoS Attack Detection",
            category=RuleCategory.DDOS,
            severity=RuleSeverity.CRITICAL,
            description="Detects distributed denial of service attacks based on traffic volume anomalies and source distribution.",
            conditions=[
                RuleCondition(field="event_type", operator="equals", value="traffic_anomaly"),
                RuleCondition(field="packets_per_second", operator="greater_than", value=10000),
                RuleCondition(field="unique_sources", operator="greater_than", value=100),
            ],
            actions=[
                RuleAction(action_type=RuleResponseType.LOG, parameters={"priority": "critical"}),
                RuleAction(action_type=RuleResponseType.SNMP_TRAP, parameters={"community": "public"}),
                RuleAction(action_type=RuleResponseType.CUSTOM, parameters={"script": "mitigate_ddos.sh"}),
            ],
            mitre_tactics=["Impact"],
            mitre_techniques=["T1498"],
            tags=["ddos", "availability", "dcc"],
            confidence=9,
            relevance=9,
            impact=9,
        ),
        # Rule 6: Insider threat detection
        QRadarRuleDefinition(
            rule_id="dcc-insider-001",
            name="DCC: Insider Threat Indicator",
            category=RuleCategory.INSIDER_THREAT,
            severity=RuleSeverity.HIGH,
            description="Detects suspicious activities by authorized users that may indicate insider threats, such as unusual access patterns or data access outside normal hours.",
            conditions=[
                RuleCondition(field="user_type", operator="equals", value="internal"),
                RuleCondition(field="access_time", operator="regex", value="^(2[0-3]|[01]?[0-9]):[0-5][0-9]$"),
                RuleCondition(field="data_classification", operator="equals", value="confidential"),
                RuleCondition(field="access_type", operator="equals", value="unusual"),
            ],
            actions=[
                RuleAction(action_type=RuleResponseType.LOG, parameters={"priority": "high"}),
                RuleAction(action_type=RuleResponseType.EMAIL, parameters={"recipirs": ["insider-threat@example.com"]}),
            ],
            mitre_tactics=["Collection", "Exfiltration"],
            mitre_techniques=["T1567", "T1213"],
            tags=["insider-threat", "behavioral", "dcc"],
            confidence=6,
            relevance=7,
            impact=7,
        ),
        # Rule 7: Malware detection
        QRadarRuleDefinition(
            rule_id="dcc-malware-001",
            name="DCC: Malware Activity Detection",
            category=RuleCategory.MALWARE,
            severity=RuleSeverity.CRITICAL,
            description="Detects known malware indicators including suspicious file execution, command and control communication, and persistence mechanisms.",
            conditions=[
                RuleCondition(field="event_type", operator="in", value=["file_execution", "c2_communication", "persistence"]),
                RuleCondition(field="threat_intel_match", operator="equals", value=True),
            ],
            actions=[
                RuleAction(action_type=RuleResponseType.LOG, parameters={"priority": "critical"}),
                RuleAction(action_type=RuleResponseType.QUARANTINE, parameters={"scope": "host"}),
                RuleAction(action_type=RuleResponseType.TICKET, parameters={"assignee": "soc-l3"}),
            ],
            mitre_tactics=["Command and Control", "Persistence"],
            mitre_techniques=["T1071", "T1543"],
            tags=["malware", "threat-intel", "dcc"],
            confidence=9,
            relevance=8,
            impact=9,
        ),
        # Rule 8: Compliance violation
        QRadarRuleDefinition(
            rule_id="dcc-compliance-001",
            name="DCC: Compliance Policy Violation",
            category=RuleCategory.COMPLIANCE,
            severity=RuleSeverity.MEDIUM,
            description="Detects activities that violate compliance policies such as PCI-DSS, HIPAA, or SOX requirements.",
            conditions=[
                RuleCondition(field="policy_type", operator="in", value=["pci_dss", "hipaa", "sox"]),
                RuleCondition(field="violation_type", operator="equals", value="detected"),
            ],
            actions=[
                RuleAction(action_type=RuleResponseType.LOG, parameters={"priority": "medium"}),
                RuleAction(action_type=RuleResponseType.EMAIL, parameters={"recipients": ["compliance@example.com"]}),
            ],
            mitre_tactics=["Defense Evasion"],
            mitre_techniques=["T1070"],
            tags=["compliance", "policy", "dcc"],
            confidence=7,
            relevance=6,
            impact=5,
        ),
        # Rule 9: Anomaly detection
        QRadarRuleDefinition(
            rule_id="dcc-anomaly-001",
            name="DCC: Behavioral Anomaly Detection",
            category=RuleCategory.ANOMALY_DETECTION,
            severity=RuleSeverity.MEDIUM,
            description="Detects behavioral anomalies that deviate from established baselines for users, hosts, or network segments.",
            conditions=[
                RuleCondition(field="anomaly_score", operator="greater_than", value=0.8),
                RuleCondition(field="baseline_deviation", operator="greater_than", value=3.0),
            ],
            actions=[
                RuleAction(action_type=RuleResponseType.LOG, parameters={"priority": "medium"}),
                RuleAction(action_type=RuleResponseType.SYSLOG, parameters={"facility": "local0"}),
            ],
            mitre_tactics=["Defense Evasion"],
            mitre_techniques=["T1078"],
            tags=["anomaly", "behavioral", "dcc"],
            confidence=5,
            relevance=6,
            impact=5,
        ),
        # Rule 10: Threat intel match
        QRadarRuleDefinition(
            rule_id="dcc-threatintel-001",
            name="DCC: Threat Intelligence Match",
            category=RuleCategory.THREAT_INTEL,
            severity=RuleSeverity.HIGH,
            description="Detects network connections or file hashes matching known threat intelligence indicators.",
            conditions=[
                RuleCondition(field="threat_intel_source", operator="not_equals", value=""),
                RuleCondition(field="threat_intel_confidence", operator="greater_than", value=7),
            ],
            actions=[
                RuleAction(action_type=RuleResponseType.LOG, parameters={"priority": "high"}),
                RuleAction(action_type=RuleResponseType.BLOCK_IP, parameters={"duration_minutes": 1440}),
                RuleAction(action_type=RuleResponseType.EMAIL, parameters={"recipients": ["threat-intel@example.com"]}),
            ],
            mitre_tactics=["Command and Control", "Exfiltration"],
            mitre_techniques=["T1071", "T1041"],
            tags=["threat-intel", "ioc", "dcc"],
            confidence=8,
            relevance=7,
            impact=7,
        ),
    ]


# ---------------------------------------------------------------------------
# Rule management
# ---------------------------------------------------------------------------

class QRadarRuleManager:
    """Manages QRadar rule definitions and deployment."""

    def __init__(self) -> None:
        self._rules: dict[str, QRadarRuleDefinition] = {}

    def add_rule(self, rule: QRadarRuleDefinition) -> None:
        """Add a rule definition."""
        self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule definition. Returns True if it existed."""
        return self._rules.pop(rule_id, None) is not None

    def get_rule(self, rule_id: str) -> QRadarRuleDefinition | None:
        """Get a rule definition by ID."""
        return self._rules.get(rule_id)

    def get_rules(
        self,
        *,
        category: RuleCategory | None = None,
        severity: RuleSeverity | None = None,
        enabled_only: bool = False,
    ) -> list[QRadarRuleDefinition]:
        """Get rules, optionally filtered."""
        results: list[QRadarRuleDefinition] = []
        for rule in self._rules.values():
            if category is not None and rule.category != category:
                continue
            if severity is not None and rule.severity != severity:
                continue
            if enabled_only and not rule.enabled:
                continue
            results.append(rule)
        return results

    def export_to_json(self, *, indent: int = 2) -> str:
        """Export all rules as JSON."""
        data = [rule.to_dict() for rule in self._rules.values()]
        return json.dumps(data, indent=indent)

    def export_to_qradar_format(self) -> str:
        """Export all rules in QRadar-compatible format."""
        data = [json.loads(rule.to_qradar_json()) for rule in self._rules.values()]
        return json.dumps(data, indent=2)

    def load_defaults(self) -> None:
        """Load the default data center security rules."""
        for rule in get_data_center_rules():
            self.add_rule(rule)

    @property
    def rule_count(self) -> int:
        return len(self._rules)
