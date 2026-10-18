"""Data models for Graylog OSS SOC integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional  # noqa: F401


class GraylogAlertSeverity(int, Enum):
    """Graylog alert severity levels (1-5, matching syslog levels)."""

    INFO = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


class GraylogStreamType(str, Enum):
    """Types of Graylog streams."""

    SYSLOG = "syslog"
    FIREWALL = "firewall"
    IDS = "ids"
    AUTH = "auth"
    WEB = "web"
    SYSTEM = "system"
    APPLICATION = "application"
    SECURITY = "security"
    AUDIT = "audit"
    CUSTOM = "custom"


class GraylogConnectorType(str, Enum):
    """Types of Graylog data connectors."""

    SYSLOG_UDP = "syslog_udp"
    SYSLOG_TCP = "syslog_tcp"
    GELF = "gelf"
    BEATS = "beats"
    KAFKA = "kafka"
    AMQP = "amqp"
    CLOUD_TRAIL = "cloud_trail"
    AWS_CLOUDTRAIL = "aws_cloudtrail"
    AZURE_ACTIVITY = "azure_activity"
    JSON_HTTP = "json_http"
    CEF = "cef"
    SNMP = "snmp"
    NETFLOW = "netflow"


class GraylogConnectorStatus(str, Enum):
    """Status of a Graylog data connector."""

    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    ERROR = "error"
    PENDING = "pending"


class GraylogEventStatus(str, Enum):
    """Status of a Graylog event/alert."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class GraylogRuleType(str, Enum):
    """Types of Graylog event/alert rules."""

    AGGREGATION = "aggregation"
    CORRELATION = "correlation"
    MATCH = "match"
    THRESHOLD = "threshold"
    GROUP = "group"
    TRENDS = "trends"


@dataclass
class GraylogStream:
    """A Graylog stream configuration."""

    stream_id: str
    title: str
    description: str = ""
    stream_type: GraylogStreamType = GraylogStreamType.SYSLOG
    rules: list[str] = field(default_factory=list)
    content_pack: str = ""
    index_set_id: str = ""
    default_stream: bool = False
    enabled: bool = True
    matching_type: str = "AND"  # AND, OR
    tags: dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


@dataclass
class GraylogConnector:
    """A Graylog data connector configuration."""

    connector_id: str
    name: str
    connector_type: GraylogConnectorType
    status: GraylogConnectorStatus = GraylogConnectorStatus.PENDING
    config: dict = field(default_factory=dict)
    stream_ids: list[str] = field(default_factory=list)
    listen_address: str = "0.0.0.0"
    listen_port: int = 514
    recv_buffer_size: int = 2097152
    number_worker_threads: int = 2
    batch_size: int = 500
    batch_wait_time: int = 1000
    message_backlog: int = 5000
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
class GraylogEventDefinition:
    """A Graylog event definition (alert rule)."""

    event_id: str
    title: str
    description: str = ""
    rule_type: GraylogRuleType = GraylogRuleType.MATCH
    severity: GraylogAlertSeverity = GraylogAlertSeverity.MEDIUM
    status: str = "enabled"  # enabled, disabled, draft
    condition: str = ""
    notification_emails: list[str] = field(default_factory=list)
    notification_webhooks: list[str] = field(default_factory=list)
    key_spec: list[str] = field(default_factory=list)
    priority: int = 1
    alert: bool = False
    field_spec: dict[str, str] = field(default_factory=dict)
    group_by: list[str] = field(default_factory=list)
    series: list[dict] = field(default_factory=list)
    streams: list[str] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    mitre_tactics: list[str] = field(default_factory=list)
    mitre_techniques: list[str] = field(default_factory=list)
    compliance_refs: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


@dataclass
class GraylogAlert:
    """A Graylog alert event."""

    alert_id: str
    timestamp: str
    event_definition_id: str
    event_definition_title: str
    severity: GraylogAlertSeverity = GraylogAlertSeverity.MEDIUM
    status: GraylogEventStatus = GraylogEventStatus.OPEN
    stream_ids: list[str] = field(default_factory=list)
    source: str = ""
    message: str = ""
    key: str = ""
    key_tuple: list[str] = field(default_factory=list)
    priority: int = 1
    fields: dict[str, str] = field(default_factory=dict)
    group_by_fields: dict[str, str] = field(default_factory=dict)
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
class GraylogDashboard:
    """A Graylog dashboard configuration."""

    dashboard_id: str
    title: str
    description: str = ""
    widgets: list[dict] = field(default_factory=list)
    stream_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    tags: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


@dataclass
class GraylogIndexSet:
    """A Graylog index set configuration."""

    index_set_id: str
    title: str
    description: str = ""
    index_prefix: str = "graylog"
    shards: int = 4
    replicas: int = 0
    rotation_strategy: str = "size"  # size, time, count
    rotation_period: str = "P1D"
    max_size: int = 10737418240  # 10GB
    retention_strategy: str = "delete"  # delete, close
    retention_count: int = 7
    creation_date: str = ""

    def __post_init__(self) -> None:
        if not self.creation_date:
            self.creation_date = datetime.now(timezone.utc).isoformat()


@dataclass
class GraylogSOCStatus:
    """Graylog SOC overall status."""

    server_id: str
    cluster_name: str = ""
    version: str = ""
    is_processing: bool = True
    is_leader: bool = False
    last_seen: str = ""
    streams_count: int = 0
    connectors_count: int = 0
    events_count: int = 0
    alerts_count: int = 0
    dashboards_count: int = 0
    index_sets_count: int = 0
    throughput_in: int = 0
    throughput_out: int = 0
    journal_size: int = 0
    journal_age: int = 0
    tags: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.last_seen:
            self.last_seen = datetime.now(timezone.utc).isoformat()
