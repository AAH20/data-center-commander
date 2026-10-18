"""Built-in YARA-L rules for Google Chronicle SOC integration.

Provides a library of pre-built YARA-L rules for common security
detections including brute force, privilege escalation, data exfiltration,
and cloud-specific threats.

Pure-Python implementation with no external dependencies.
"""
from __future__ import annotations

from typing import Any, Sequence

from .models import RuleSeverity, RuleStatus, YaraRule


# ---------------------------------------------------------------------------
# Built-in rules
# ---------------------------------------------------------------------------


def get_builtin_rules() -> list[YaraRule]:
    """Get all built-in YARA-L rules."""
    return [
        _brute_force_login_rule(),
        _privilege_escalation_rule(),
        _data_exfiltration_rule(),
        _impossible_travel_rule(),
        _suspicious_api_call_rule(),
        _credential_access_rule(),
        _lateral_movement_rule(),
        _persistence_rule(),
        _defense_evasion_rule(),
        _initial_access_rule(),
        _cloud_trail_tampering_rule(),
        _iam_policy_change_rule(),
        _security_group_change_rule(),
        _vpc_flow_anomaly_rule(),
        _dns_tunneling_rule(),
        _malware_detection_rule(),
        _phishing_detection_rule(),
        _ransomware_detection_rule(),
        _insider_threat_rule(),
        _compliance_violation_rule(),
    ]


def get_rules_by_severity(severity: RuleSeverity) -> list[YaraRule]:
    """Get built-in rules filtered by severity."""
    return [r for r in get_builtin_rules() if r.severity == severity]


def get_rules_by_tag(tag: str) -> list[YaraRule]:
    """Get built-in rules filtered by tag."""
    return [r for r in get_builtin_rules() if tag in r.tags]


def _brute_force_login_rule() -> YaraRule:
    """Detect brute force login attempts."""
    return YaraRule(
        name="Brute Force Login Detection",
        description="Detects multiple failed login attempts from a single source within a short time window",
        yara_l='''
rule brute_force_login {
    meta:
        author = "DCC SOC"
        description = "Detects brute force login attempts"
        severity = "high"
        category = "credential_access"
        mitre = "T1110"
    condition:
        $event.metadata.outcome == "FAILURE" and
        $event.event_type == "authentication" and
        $event.metadata.attempt_count > 5
}
''',
        severity=RuleSeverity.HIGH,
        tags=["authentication", "brute_force", "credential_access", "mitre_t1110"],
        status=RuleStatus.ENABLED,
    )


def _privilege_escalation_rule() -> YaraRule:
    """Detect privilege escalation attempts."""
    return YaraRule(
        name="Privilege Escalation Detection",
        description="Detects attempts to gain elevated privileges through IAM policy changes or role assumption",
        yara_l='''
rule privilege_escalation {
    meta:
        author = "DCC SOC"
        description = "Detects privilege escalation attempts"
        severity = "critical"
        category = "privilege_escalation"
        mitre = "T1078"
    condition:
        $event.metadata.event_name in ("AttachUserPolicy", "PutUserPolicy", "AttachRolePolicy", "AssumeRole", "CreateAccessKey") and
        $event.metadata.user_name != "system"
}
''',
        severity=RuleSeverity.CRITICAL,
        tags=["iam", "privilege_escalation", "mitre_t1078"],
    )


def _data_exfiltration_rule() -> YaraRule:
    """Detect potential data exfiltration."""
    return YaraRule(
        name="Data Exfiltration Detection",
        description="Detects large data transfers that may indicate exfiltration",
        yara_l='''
rule data_exfiltration {
    meta:
        author = "DCC SOC"
        description = "Detects potential data exfiltration"
        severity = "high"
        category = "exfiltration"
        mitre = "T1041"
    condition:
        $event.metadata.bytes_transferred > 100000000 and
        $event.metadata.destination_ip != "internal"
}
''',
        severity=RuleSeverity.HIGH,
        tags=["exfiltration", "data_loss", "mitre_t1041"],
    )


def _impossible_travel_rule() -> YaraRule:
    """Detect impossible travel scenarios."""
    return YaraRule(
        name="Impossible Travel Detection",
        description="Detects logins from geographically distant locations within impossible time windows",
        yara_l='''
rule impossible_travel {
    meta:
        author = "DCC SOC"
        description = "Detects impossible travel scenarios"
        severity = "high"
        category = "initial_access"
        mitre = "T1078"
    condition:
        $event.metadata.previous_login_location != $event.metadata.current_login_location and
        $event.metadata.time_between_logins < 3600
}
''',
        severity=RuleSeverity.HIGH,
        tags=["authentication", "impossible_travel", "mitre_t1078"],
    )


def _suspicious_api_call_rule() -> YaraRule:
    """Detect suspicious API calls."""
    return YaraRule(
        name="Suspicious API Call Detection",
        description="Detects API calls that are unusual or high-risk",
        yara_l='''
rule suspicious_api_call {
    meta:
        author = "DCC SOC"
        description = "Detects suspicious API calls"
        severity = "medium"
        category = "reconnaissance"
        mitre = "T1087"
    condition:
        $event.metadata.event_name in ("DescribeInstances", "ListBuckets", "GetPolicy", "ListUsers", "GetAccountAuthorizationDetails") and
        $event.metadata.source_ip not in $event.metadata.authorized_ips
}
''',
        severity=RuleSeverity.MEDIUM,
        tags=["reconnaissance", "api", "mitre_t1087"],
    )


def _credential_access_rule() -> YaraRule:
    """Detect credential access attempts."""
    return YaraRule(
        name="Credential Access Detection",
        description="Detects attempts to access or dump credentials",
        yara_l='''
rule credential_access {
    meta:
        author = "DCC SOC"
        description = "Detects credential access attempts"
        severity = "critical"
        category = "credential_access"
        mitre = "T1003"
    condition:
        $event.metadata.event_name in ("GetCredentialReport", "GetAccountPasswordPolicy", "ListAccessKeys", "GetLoginProfile") and
        $event.metadata.user_name != "system"
}
''',
        severity=RuleSeverity.CRITICAL,
        tags=["credential_access", "mitre_t1003"],
    )


def _lateral_movement_rule() -> YaraRule:
    """Detect lateral movement attempts."""
    return YaraRule(
        name="Lateral Movement Detection",
        description="Detects potential lateral movement within the network",
        yara_l='''
rule lateral_movement {
    meta:
        author = "DCC SOC"
        description = "Detects lateral movement attempts"
        severity = "high"
        category = "lateral_movement"
        mitre = "T1021"
    condition:
        $event.metadata.destination_port in (22, 3389, 445, 135, 5985, 5986) and
        $event.metadata.source_ip != $event.metadata.destination_ip and
        $event.metadata.internal_only == false
}
''',
        severity=RuleSeverity.HIGH,
        tags=["lateral_movement", "network", "mitre_t1021"],
    )


def _persistence_rule() -> YaraRule:
    """Detect persistence mechanisms."""
    return YaraRule(
        name="Persistence Mechanism Detection",
        description="Detects attempts to establish persistence through scheduled tasks, registry keys, or startup items",
        yara_l='''
rule persistence_mechanism {
    meta:
        author = "DCC SOC"
        description = "Detects persistence mechanisms"
        severity = "high"
        category = "persistence"
        mitre = "T1053"
    condition:
        $event.metadata.event_name in ("CreateScheduledTask", "SetRegistryKey", "CreateStartupItem", "CreateService") and
        $event.metadata.user_name != "system"
}
''',
        severity=RuleSeverity.HIGH,
        tags=["persistence", "mitre_t1053"],
    )


def _defense_evasion_rule() -> YaraRule:
    """Detect defense evasion techniques."""
    return YaraRule(
        name="Defense Evasion Detection",
        description="Detects attempts to evade security controls through log clearing, disabling security tools, or masquerading",
        yara_l='''
rule defense_evasion {
    meta:
        author = "DCC SOC"
        description = "Detects defense evasion techniques"
        severity = "critical"
        category = "defense_evasion"
        mitre = "T1070"
    condition:
        $event.metadata.event_name in ("ClearEventLog", "StopLogging", "DeleteTrail", "DisableSecurityTool", "SetSecurityToolConfig") and
        $event.metadata.user_name != "system"
}
''',
        severity=RuleSeverity.CRITICAL,
        tags=["defense_evasion", "anti_forensics", "mitre_t1070"],
    )


def _initial_access_rule() -> YaraRule:
    """Detect initial access attempts."""
    return YaraRule(
        name="Initial Access Detection",
        description="Detects attempts to gain initial access through exploitation, phishing, or brute force",
        yara_l='''
rule initial_access {
    meta:
        author = "DCC SOC"
        description = "Detects initial access attempts"
        severity = "high"
        category = "initial_access"
        mitre = "T1190"
    condition:
        $event.metadata.event_name in ("ExploitPublicFacingApplication", "SpearphishingAttachment", "ExternalRemoteService") and
        $event.metadata.source_ip not in $event.metadata.authorized_ips
}
''',
        severity=RuleSeverity.HIGH,
        tags=["initial_access", "phishing", "exploitation", "mitre_t1190"],
    )


def _cloud_trail_tampering_rule() -> YaraRule:
    """Detect CloudTrail tampering attempts."""
    return YaraRule(
        name="CloudTrail Tampering Detection",
        description="Detects attempts to disable, modify, or delete CloudTrail logging",
        yara_l='''
rule cloudtrail_tampering {
    meta:
        author = "DCC SOC"
        description = "Detects CloudTrail tampering attempts"
        severity = "critical"
        category = "defense_evasion"
        mitre = "T1562"
    condition:
        $event.metadata.event_name in ("StopLogging", "DeleteTrail", "UpdateTrail", "PutEventSelectors") and
        $event.metadata.user_name != "system"
}
''',
        severity=RuleSeverity.CRITICAL,
        tags=["cloudtrail", "defense_evasion", "aws", "mitre_t1562"],
    )


def _iam_policy_change_rule() -> YaraRule:
    """Detect IAM policy changes."""
    return YaraRule(
        name="IAM Policy Change Detection",
        description="Detects changes to IAM policies that may grant excessive permissions",
        yara_l='''
rule iam_policy_change {
    meta:
        author = "DCC SOC"
        description = "Detects IAM policy changes"
        severity = "high"
        category = "privilege_escalation"
        mitre = "T1098"
    condition:
        $event.metadata.event_name in ("PutUserPolicy", "PutRolePolicy", "PutGroupPolicy", "AttachUserPolicy", "AttachRolePolicy") and
        $event.metadata.policy_document contains "*"
}
''',
        severity=RuleSeverity.HIGH,
        tags=["iam", "policy", "privilege_escalation", "mitre_t1098"],
    )


def _security_group_change_rule() -> YaraRule:
    """Detect security group changes."""
    return YaraRule(
        name="Security Group Change Detection",
        description="Detects changes to security groups that may expose resources",
        yara_l='''
rule security_group_change {
    meta:
        author = "DCC SOC"
        description = "Detects security group changes"
        severity = "high"
        category = "defense_evasion"
        mitre = "T1562"
    condition:
        $event.metadata.event_name in ("AuthorizeSecurityGroupIngress", "AuthorizeSecurityGroupEgress", "ModifySecurityGroupRules") and
        $event.metadata.cidr == "0.0.0.0/0"
}
''',
        severity=RuleSeverity.HIGH,
        tags=["security_group", "network", "aws", "mitre_t1562"],
    )


def _vpc_flow_anomaly_rule() -> YaraRule:
    """Detect VPC flow anomalies."""
    return YaraRule(
        name="VPC Flow Anomaly Detection",
        description="Detects unusual VPC flow patterns that may indicate data exfiltration or scanning",
        yara_l='''
rule vpc_flow_anomaly {
    meta:
        author = "DCC SOC"
        description = "Detects VPC flow anomalies"
        severity = "medium"
        category = "exfiltration"
        mitre = "T1041"
    condition:
        $event.metadata.bytes_out > 1000000000 and
        $event.metadata.destination_ip not in $event.metadata.authorized_ips
}
''',
        severity=RuleSeverity.MEDIUM,
        tags=["vpc", "network", "anomaly", "mitre_t1041"],
    )


def _dns_tunneling_rule() -> YaraRule:
    """Detect DNS tunneling attempts."""
    return YaraRule(
        name="DNS Tunneling Detection",
        description="Detects potential DNS tunneling through unusual query patterns",
        yara_l='''
rule dns_tunneling {
    meta:
        author = "DCC SOC"
        description = "Detects DNS tunneling attempts"
        severity = "high"
        category = "command_and_control"
        mitre = "T1071"
    condition:
        $event.metadata.dns_query_length > 100 and
        $event.metadata.dns_query_type in ("TXT", "CNAME") and
        $event.metadata.dns_query_count > 50
}
''',
        severity=RuleSeverity.HIGH,
        tags=["dns", "tunneling", "command_and_control", "mitre_t1071"],
    )


def _malware_detection_rule() -> YaraRule:
    """Detect malware indicators."""
    return YaraRule(
        name="Malware Detection",
        description="Detects known malware indicators and suspicious file executions",
        yara_l='''
rule malware_detection {
    meta:
        author = "DCC SOC"
        description = "Detects malware indicators"
        severity = "critical"
        category = "malware"
        mitre = "T1059"
    condition:
        $event.metadata.file_hash in $event.metadata.known_bad_hashes or
        $event.metadata.process_name in ("mimikatz.exe", "pwdump.exe", "procdump.exe", "cobaltstrike.exe")
}
''',
        severity=RuleSeverity.CRITICAL,
        tags=["malware", "mitre_t1059"],
    )


def _phishing_detection_rule() -> YaraRule:
    """Detect phishing attempts."""
    return YaraRule(
        name="Phishing Detection",
        description="Detects phishing emails and suspicious URL clicks",
        yara_l='''
rule phishing_detection {
    meta:
        author = "DCC SOC"
        description = "Detects phishing attempts"
        severity = "high"
        category = "initial_access"
        mitre = "T1566"
    condition:
        $event.metadata.email_subject contains "urgent" and
        $event.metadata.email_links not in $event.metadata.authorized_domains
}
''',
        severity=RuleSeverity.HIGH,
        tags=["phishing", "email", "initial_access", "mitre_t1566"],
    )


def _ransomware_detection_rule() -> YaraRule:
    """Detect ransomware activity."""
    return YaraRule(
        name="Ransomware Detection",
        description="Detects ransomware indicators including mass file encryption and ransom notes",
        yara_l='''
rule ransomware_detection {
    meta:
        author = "DCC SOC"
        description = "Detects ransomware activity"
        severity = "critical"
        category = "impact"
        mitre = "T1486"
    condition:
        $event.metadata.files_modified > 100 and
        $event.metadata.file_extension_changed == true and
        $event.metadata.ransom_note_created == true
}
''',
        severity=RuleSeverity.CRITICAL,
        tags=["ransomware", "impact", "mitre_t1486"],
    )


def _insider_threat_rule() -> YaraRule:
    """Detect insider threat indicators."""
    return YaraRule(
        name="Insider Threat Detection",
        description="Detects potential insider threats through unusual access patterns and data access",
        yara_l='''
rule insider_threat {
    meta:
        author = "DCC SOC"
        description = "Detects insider threat indicators"
        severity = "high"
        category = "insider_threat"
        mitre = "T1083"
    condition:
        $event.metadata.user_name != "system" and
        $event.metadata.access_time not in $event.metadata.normal_hours and
        $event.metadata.data_accessed not in $event.metadata.authorized_data
}
''',
        severity=RuleSeverity.HIGH,
        tags=["insider_threat", "data_access", "mitre_t1083"],
    )


def _compliance_violation_rule() -> YaraRule:
    """Detect compliance violations."""
    return YaraRule(
        name="Compliance Violation Detection",
        description="Detects actions that may violate compliance requirements (SOC2, ISO27001, PCI DSS, HIPAA)",
        yara_l='''
rule compliance_violation {
    meta:
        author = "DCC SOC"
        description = "Detects compliance violations"
        severity = "high"
        category = "compliance"
        mitre = "T1078"
    condition:
        $event.metadata.event_name in ("DeleteLogging", "DisableEncryption", "ModifyAuditConfig", "DisableMFA") and
        $event.metadata.user_name != "system"
}
''',
        severity=RuleSeverity.HIGH,
        tags=["compliance", "soc2", "iso27001", "pci_dss", "hipaa", "mitre_t1078"],
    )


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def get_rule_names() -> list[str]:
    """Get names of all built-in rules."""
    return [r.name for r in get_builtin_rules()]


def get_rule_count() -> int:
    """Get the total number of built-in rules."""
    return len(get_builtin_rules())


def find_rule_by_name(name: str) -> YaraRule | None:
    """Find a built-in rule by name."""
    for rule in get_builtin_rules():
        if rule.name == name:
            return rule
    return None
