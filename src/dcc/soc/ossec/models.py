"""Data models for OSSEC SOC integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Severity(int, Enum):
    """OSSEC alert severity levels (0-15)."""

    INFO = 0
    LOW = 3
    MEDIUM = 5
    HIGH = 7
    CRITICAL = 10
    EMERGENCY = 15


class OSSECSource(str, Enum):
    """OSSEC data source types."""

    SYSLOG = "syslog"
    FILE = "file"
    INTEGRITY = "integrity"
    PROCESS = "process"
    CONNECTION = "connection"
    AUTH = "auth"
    WEB = "web"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class OSSECStatus(str, Enum):
    """OSSEC alert status."""

    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"
    SUPPRESSED = "suppressed"


class OSSECGroup(str, Enum):
    """OSSEC rule groups."""

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


@dataclass
class OSSECRule:
    """An OSSEC detection rule."""

    rule_id: int
    level: int
    description: str
    group: OSSECGroup
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

    @property
    def severity(self) -> Severity:
        """Map OSSEC level to severity enum."""
        if self.level >= 12:
            return Severity.EMERGENCY
        elif self.level >= 10:
            return Severity.CRITICAL
        elif self.level >= 7:
            return Severity.HIGH
        elif self.level >= 4:
            return Severity.MEDIUM
        elif self.level >= 1:
            return Severity.LOW
        return Severity.INFO


@dataclass
class OSSECAlert:
    """An OSSEC alert event."""

    alert_id: str
    timestamp: str
    rule: OSSECRule
    agent_id: str
    agent_name: str
    agent_ip: str
    source: OSSECSource
    status: OSSECStatus = OSSECStatus.NEW
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
    severity: Severity = Severity.INFO
    mitre_tactic: str = ""
    mitre_technique: str = ""
    compliance_refs: list[str] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    acknowledged_by: str = ""
    acknowledged_at: str = ""
    resolved_at: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.severity:
            self.severity = self.rule.severity
        if not self.mitre_tactic:
            self.mitre_tactic = self.rule.mitre_tactic
        if not self.mitre_technique:
            self.mitre_technique = self.rule.mitre_technique
        if not self.compliance_refs:
            self.compliance_refs = self.rule.compliance_refs


@dataclass
class OSSECEvent:
    """A raw OSSEC event before rule matching."""

    event_id: str
    timestamp: str
    agent_id: str
    agent_name: str
    agent_ip: str
    source: OSSECSource
    raw_log: str = ""
    decoded_fields: dict[str, str] = field(default_factory=dict)
    location: str = ""
    program_name: str = ""
    pid: int = 0
    user: str = ""
    group: str = ""
    file_path: str = ""
    file_md5: str = ""
    file_sha1: str = ""
    src_ip: str = ""
    dst_ip: str = ""
    src_port: int = 0
    dst_port: int = 0
    protocol: str = ""
    url: str = ""
    http_method: str = ""
    status_code: int = 0
    size: int = 0
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class OSSECStatus:
    """OSSEC agent status."""

    agent_id: str
    agent_name: str
    agent_ip: str
    status: str  # active, disconnected, never_connected
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
