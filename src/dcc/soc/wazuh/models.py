"""Data models for Wazuh SOC integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class WazuhAlertSeverity(int, Enum):
    """Wazuh alert severity levels (1-15)."""

    INFO = 1
    LOW = 3
    MEDIUM = 5
    HIGH = 7
    CRITICAL = 10
    EMERGENCY = 15


class WazuhAgentStatus(str, Enum):
    """Wazuh agent connection status."""

    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    NEVER_CONNECTED = "never_connected"
    PENDING = "pending"


class WazuhRuleLevel(int, Enum):
    """Wazuh rule severity levels (0-15)."""

    LEVEL_0 = 0
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3
    LEVEL_4 = 4
    LEVEL_5 = 5
    LEVEL_6 = 6
    LEVEL_7 = 7
    LEVEL_8 = 8
    LEVEL_9 = 9
    LEVEL_10 = 10
    LEVEL_11 = 11
    LEVEL_12 = 12
    LEVEL_13 = 13
    LEVEL_14 = 14
    LEVEL_15 = 15


class WazuhRuleGroup(str, Enum):
    """Wazuh rule groups."""

    AUTHENTICATION = "authentication"
    INTEGRITY_CHECK = "syscheck"
    ROOTKIT = "rootkit"
    POLICY = "policy"
    WEB = "web"
    FIREWALL = "firewall"
    IDS = "ids"
    SYSTEM = "system"
    WINDOWS = "windows"
    LINUX = "linux"
    GENERAL = "general"
    VULNERABILITY = "vulnerability"
    SCA = "sca"
    COMPLIANCE = "compliance"


class WazuhScanType(str, Enum):
    """Wazuh scan/audit types."""

    SYSCHECK = "syscheck"
    ROOTCHECK = "rootcheck"
    SCA = "sca"
    VULNERABILITY = "vulnerability"
    CAPABILITY = "capability"


@dataclass
class WazuhRule:
    """A Wazuh detection rule."""

    rule_id: int
    level: int
    description: str
    group: WazuhRuleGroup = WazuhRuleGroup.GENERAL
    regex: str = ""
    decoded_as: str = ""
    frequency: int = 0
    timeframe: int = 0
    ignore: int = 0
    match: list[str] = field(default_factory=list)
    pattern: list[str] = field(default_factory=list)
    srcip: str = ""
    dstip: str = ""
    srcport: int = 0
    dstport: int = 0
    user: str = ""
    program_name: str = ""
    url: str = ""
    data: str = ""
    action: str = ""
    status: str = ""
    extra_data: str = ""
    mitre_tactic: str = ""
    mitre_technique: str = ""
    compliance_refs: list[str] = field(default_factory=list)
    active: bool = True
    filename: str = ""
    relative_dirname: str = ""

    @property
    def severity(self) -> WazuhAlertSeverity:
        """Map Wazuh rule level to severity enum."""
        if self.level >= 12:
            return WazuhAlertSeverity.EMERGENCY
        elif self.level >= 10:
            return WazuhAlertSeverity.CRITICAL
        elif self.level >= 7:
            return WazuhAlertSeverity.HIGH
        elif self.level >= 4:
            return WazuhAlertSeverity.MEDIUM
        elif self.level >= 1:
            return WazuhAlertSeverity.LOW
        return WazuhAlertSeverity.INFO


@dataclass
class WazuhAlert:
    """A Wazuh alert event."""

    alert_id: str
    timestamp: str
    rule: WazuhRule
    agent_id: str
    agent_name: str
    agent_ip: str = ""
    source: str = "syslog"
    status: str = "new"
    src_ip: str = ""
    dst_ip: str = ""
    src_port: int = 0
    dst_port: int = 0
    protocol: str = ""
    user: str = ""
    program_name: str = ""
    file_path: str = ""
    full_log: str = ""
    location: str = ""
    severity: WazuhAlertSeverity = WazuhAlertSeverity.INFO
    mitre_tactic: str = ""
    mitre_technique: str = ""
    compliance_refs: list[str] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    acknowledged_by: str = ""
    acknowledged_at: str = ""
    resolved_at: str = ""
    notes: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity == WazuhAlertSeverity.INFO and self.rule:
            self.severity = self.rule.severity
        if not self.mitre_tactic and self.rule:
            self.mitre_tactic = self.rule.mitre_tactic
        if not self.mitre_technique and self.rule:
            self.mitre_technique = self.rule.mitre_technique
        if not self.compliance_refs and self.rule:
            self.compliance_refs = self.rule.compliance_refs


@dataclass
class WazuhAgent:
    """A Wazuh agent."""

    agent_id: str
    agent_name: str
    agent_ip: str = ""
    status: WazuhAgentStatus = WazuhAgentStatus.NEVER_CONNECTED
    last_seen: str = ""
    version: str = ""
    os: str = ""
    os_version: str = ""
    os_arch: str = ""
    last_check: str = ""
    alerts_count: int = 0
    events_count: int = 0
    integrity_checks: int = 0
    rootkit_checks: int = 0
    sca_checks: int = 0
    vulnerability_checks: int = 0
    groups: list[str] = field(default_factory=list)
    manager: str = ""
    node_name: str = ""
    date_add: str = ""
    disconnection_time: str = ""
    registration_ip: str = ""
    keepalive_status: str = ""


@dataclass
class WazuhDecoder:
    """A Wazuh decoder."""

    decoder_id: str
    name: str
    program_name: str = ""
    parent: str = ""
    regex: str = ""
    order: str = ""
    prematch: str = ""
    plugin_decoder: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    filename: str = ""
    relative_dirname: str = ""


@dataclass
class WazuhSyscheckResult:
    """A Wazuh syscheck (file integrity) result."""

    result_id: str
    agent_id: str
    agent_name: str
    file_path: str
    event_type: str  # added, modified, deleted
    timestamp: str = ""
    size: int = 0
    perm: str = ""
    uid: str = ""
    gid: str = ""
    md5: str = ""
    sha1: str = ""
    sha256: str = ""
    inode: int = 0
    changes: dict[str, Any] = field(default_factory=dict)


@dataclass
class WazuhRootcheckResult:
    """A Wazuh rootcheck result."""

    result_id: str
    agent_id: str
    agent_name: str
    scan_id: str = ""
    scan_time: str = ""
    event_type: str = ""
    severity: str = ""
    description: str = ""
    file: str = ""
    title: str = ""
    status: str = ""
    cis: str = ""
    pci_dss: str = ""
    nist: str = ""
    gpg13: str = ""
    gdpr: str = ""
    hipaa: str = ""
    tsc: str = ""


@dataclass
class WazuhSCAResult:
    """A Wazuh Security Configuration Assessment result."""

    result_id: str
    agent_id: str
    agent_name: str
    policy_id: str = ""
    policy_name: str = ""
    description: str = ""
    start_scan: str = ""
    end_scan: str = ""
    pass_count: int = 0
    fail_count: int = 0
    invalid_count: int = 0
    score: float = 0.0
    references: str = ""
    remediation: str = ""
    checks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class WazuhVulnerabilityResult:
    """A Wazuh vulnerability scan result."""

    result_id: str
    agent_id: str
    agent_name: str
    cve: str = ""
    severity: str = ""
    title: str = ""
    description: str = ""
    package: str = ""
    version: str = ""
    architecture: str = ""
    cvss_score: float = 0.0
    cvss_vector: str = ""
    detection_time: str = ""
    status: str = ""
    external_references: list[str] = field(default_factory=list)
    published: str = ""
    updated: str = ""


@dataclass
class WazuhMITRETechnique:
    """A Wazuh MITRE ATT&CK technique mapping."""

    technique_id: str
    name: str
    description: str = ""
    tactics: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    defenses: list[str] = field(default_factory=list)
    url: str = ""


@dataclass
class WazuhClusterNode:
    """A Wazuh cluster node."""

    node_id: str
    node_name: str
    node_type: str  # master, worker
    ip: str = ""
    version: str = ""
    status: str = ""
    last_seen: str = ""
    n_agents: int = 0


@dataclass
class WazuhHealthcheck:
    """Wazuh manager healthcheck status."""

    status: str
    version: str = ""
    cluster_enabled: bool = False
    cluster_name: str = ""
    nodes: list[WazuhClusterNode] = field(default_factory=list)
    agents: int = 0
    agent_status: dict[str, int] = field(default_factory=dict)
    last_check: str = ""


@dataclass
class WazuhStats:
    """Wazuh operational statistics."""

    total_agents: int = 0
    active_agents: int = 0
    disconnected_agents: int = 0
    never_connected_agents: int = 0
    total_alerts: int = 0
    alerts_today: int = 0
    alerts_last_7d: int = 0
    rules_loaded: int = 0
    decoders_loaded: int = 0
    last_check: str = ""