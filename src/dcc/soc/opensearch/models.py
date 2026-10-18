"""Data models for OpenSearch OSS SOC integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional  # noqa: F401


class OpenSearchAlertSeverity(int, Enum):
    """OpenSearch alert severity levels (1-5)."""

    INFO = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


class OpenSearchConnectorType(str, Enum):
    """Types of OpenSearch data connectors."""

    SYSLOG_UDP = "syslog_udp"
    SYSLOG_TCP = "syslog_tcp"
    BEATS = "beats"
    KAFKA = "kafka"
    S3 = "s3"
    CLOUDTRAIL = "cloudtrail"
    JSON_HTTP = "json_http"
    CEF = "cef"
    NETFLOW = "netflow"
    SNMP = "snmp"


class OpenSearchConnectorStatus(str, Enum):
    """Status of an OpenSearch data connector."""

    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    ERROR = "error"
    PENDING = "pending"


class OpenSearchEventStatus(str, Enum):
    """Status of an OpenSearch event/alert."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class OpenSearchRuleType(str, Enum):
    """Types of OpenSearch detection rules."""

    THRESHOLD = "threshold"
    CORRELATION = "correlation"
    ANOMALY = "anomaly"
    MATCH = "match"
    AGGREGATION = "aggregation"


@dataclass
class OpenSearchIndex:
    """An OpenSearch index configuration."""

    index_name: str
    description: str = ""
    index_pattern: str = ""
    shards: int = 3
    replicas: int = 1
    retention_days: int = 30
    rollover_size: str = "50gb"
    rollover_age: str = "30d"
    refresh_interval: str = "1s"
    codec: str = "best_compression"
    mappings: dict = field(default_factory=dict)
    settings: dict = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class OpenSearchConnector:
    """An OpenSearch data connector configuration."""

    connector_id: str
    name: str
    connector_type: OpenSearchConnectorType
    status: OpenSearchConnectorStatus = OpenSearchConnectorStatus.PENDING
    config: dict = field(default_factory=dict)
    index_name: str = ""
    listen_address: str = "0.0.0.0"
    listen_port: int = 514
    batch_size: int = 500
    batch_wait_time: int = 1000
    tags: dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    last_connected: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


@dataclass
class OpenSearchEvent:
    """A raw OpenSearch event before rule matching."""

    event_id: str
    timestamp: str
    source: str = ""
    raw_log: str = ""
    decoded_fields: dict[str, str] = field(default_factory=dict)
    index_name: str = ""
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
class OpenSearchAlert:
    """An OpenSearch alert event."""

    alert_id: str
    timestamp: str
    rule_id: str
    rule_name: str
    severity: OpenSearchAlertSeverity = OpenSearchAlertSeverity.MEDIUM
    status: OpenSearchEventStatus = OpenSearchEventStatus.OPEN
    source: str = ""
    message: str = ""
    index_name: str = ""
    src_ip: str = ""
    dst_ip: str = ""
    src_port: int = 0
    dst_port: int = 0
    protocol: str = ""
    user: str = ""
    program_name: str = ""
    file_path: str = ""
    full_log: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    mitre_tactics: list[str] = field(default_factory=list)
    mitre_techniques: list[str] = field(default_factory=list)
    compliance_refs: list[str] = field(default_factory=list)
    acknowledged_by: str = ""
    acknowledged_at: str = ""
    resolved_at: str = ""
    notes: str = ""
    tags: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class OpenSearchRule:
    """An OpenSearch detection rule."""

    rule_id: str
    name: str
    description: str = ""
    rule_type: OpenSearchRuleType = OpenSearchRuleType.MATCH
    severity: OpenSearchAlertSeverity = OpenSearchAlertSeverity.MEDIUM
    status: str = "enabled"  # enabled, disabled, draft
    condition: str = ""
    index_pattern: str = ""
    threshold: int = 1
    timeframe: int = 300  # seconds
    group_by: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    match_patterns: list[str] = field(default_factory=list)
    notification_emails: list[str] = field(default_factory=list)
    notification_webhooks: list[str] = field(default_factory=list)
    mitre_tactics: list[str] = field(default_factory=list)
    mitre_techniques: list[str] = field(default_factory=list)
    compliance_refs: list[str] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


@dataclass
class OpenSearchSOCStatus:
    """OpenSearch SOC overall status."""

    cluster_name: str = ""
    cluster_health: str = "green"  # green, yellow, red
    version: str = ""
    is_processing: bool = True
    last_seen: str = ""
    indices_count: int = 0
    connectors_count: int = 0
    rules_count: int = 0
    alerts_count: int = 0
    docs_count: int = 0
    store_size: int = 0
    tags: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.last_seen:
            self.last_seen = datetime.now(timezone.utc).isoformat()
