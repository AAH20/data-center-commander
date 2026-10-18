"""Core data models for Google Chronicle SOC integration.

Defines the types used throughout the Chronicle integration: security events,
alerts, detections, YARA-L rules, and dashboard configurations. All models are
serialisable dataclasses so they can be persisted, exported, and audited.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EventSeverity(str, Enum):
    """Severity levels for Chronicle security events."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventStatus(str, Enum):
    """Status of a security event."""

    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"
    FALSE_POSITIVE = "false_positive"


class AlertState(str, Enum):
    """State of a Chronicle alert."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    CLOSED = "closed"


class DetectionStatus(str, Enum):
    """Status of a detection/rule match."""

    NEW = "new"
    REVIEWED = "reviewed"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class RuleSeverity(str, Enum):
    """Severity levels for YARA-L rules."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleStatus(str, Enum):
    """Status of a YARA-L rule."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    DRAFT = "draft"


class DataSourceType(str, Enum):
    """Types of data sources for Chronicle ingestion."""

    AWS_CLOUDTRAIL = "aws_cloudtrail"
    AZURE_ACTIVITY = "azure_activity"
    GCP_AUDIT = "gcp_audit"
    SYSLOG = "syslog"
    CEPTOR = "ceptor"
    OKTA = "okta"
    ACTIVE_DIRECTORY = "active_directory"
    FIREWALL = "firewall"
    PROXY = "proxy"
    EDR = "edr"
    CUSTOM = "custom"


class LogType(str, Enum):
    """Chronicle log types."""

    AWS_CLOUDTRAIL = "AWS_CLOUDTRAIL"
    AZURE_ACTIVITY = "AZURE_ACTIVITY"
    GCP_AUDIT = "GCP_AUDIT"
    OKTA = "OKTA"
    WINDOWS = "WINDOWS"
    LINUX_SYSMON = "LINUX_SYSMON"
    LINUX_AUDITD = "LINUX_AUDITD"
    CISCO_ASA = "CISCO_ASA"
    FORTINET = "FORTINET"
    PALO_ALTO = "PALO_ALTO"
    CUSTOM = "CUSTOM"


# ---------------------------------------------------------------------------
# Security Event
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecurityEvent:
    """A single security event ingested from or sent to Chronicle.

    Attributes
    ----------
    event_id:
        Unique identifier for this event.
    timestamp:
        When the event occurred (UTC).
    source:
        The data source that produced the event.
    event_type:
        Type of event (e.g., "authentication", "network", "file").
    severity:
        Severity level of the event.
    status:
        Current status of the event.
    description:
        Human-readable description.
    raw_event:
        The original raw event data.
    metadata:
        Additional context (e.g., enrichment data).
    """

    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    event_type: str = ""
    severity: EventSeverity = EventSeverity.INFO
    status: EventStatus = EventStatus.NEW
    description: str = ""
    raw_event: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "event_type": self.event_type,
            "severity": self.severity.value,
            "status": self.status.value,
            "description": self.description,
            "raw_event": self.raw_event,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SecurityEvent:
        return cls(
            event_id=data.get("event_id", str(uuid4())),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data.get("source", ""),
            event_type=data.get("event_type", ""),
            severity=EventSeverity(data.get("severity", "info")),
            status=EventStatus(data.get("status", "new")),
            description=data.get("description", ""),
            raw_event=data.get("raw_event", {}),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------


@dataclass
class ChronicleAlert:
    """A Chronicle alert with lifecycle management.

    Attributes
    ----------
    alert_id:
        Unique identifier for this alert.
    title:
        Short description of the alert.
    description:
        Detailed description.
    state:
        Current state of the alert.
    severity:
        Severity level.
    events:
        Associated security events.
    created_at:
        When the alert was created.
    updated_at:
        When the alert was last updated.
    assigned_to:
        User assigned to investigate.
    notes:
        Investigation notes.
    """

    alert_id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    description: str = ""
    state: AlertState = AlertState.ACTIVE
    severity: EventSeverity = EventSeverity.MEDIUM
    events: list[SecurityEvent] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    assigned_to: str = ""
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def acknowledge(self, user: str) -> None:
        """Acknowledge the alert."""
        self.state = AlertState.ACKNOWLEDGED
        self.assigned_to = user
        self.updated_at = datetime.now(timezone.utc)

    def resolve(self) -> None:
        """Resolve the alert."""
        self.state = AlertState.RESOLVED
        self.updated_at = datetime.now(timezone.utc)

    def close(self) -> None:
        """Close the alert."""
        self.state = AlertState.CLOSED
        self.updated_at = datetime.now(timezone.utc)

    def add_event(self, event: SecurityEvent) -> None:
        """Add a security event to this alert."""
        self.events.append(event)
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "title": self.title,
            "description": self.description,
            "state": self.state.value,
            "severity": self.severity.value,
            "events": [e.to_dict() for e in self.events],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "assigned_to": self.assigned_to,
            "notes": self.notes,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChronicleAlert:
        return cls(
            alert_id=data.get("alert_id", str(uuid4())),
            title=data.get("title", ""),
            description=data.get("description", ""),
            state=AlertState(data.get("state", "active")),
            severity=EventSeverity(data.get("severity", "medium")),
            events=[SecurityEvent.from_dict(e) for e in data.get("events", [])],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            assigned_to=data.get("assigned_to", ""),
            notes=data.get("notes", ""),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


@dataclass
class Detection:
    """A detection produced by a YARA-L rule match.

    Attributes
    ----------
    detection_id:
        Unique identifier for this detection.
    rule_id:
        The rule that produced this detection.
    rule_name:
        Human-readable rule name.
    status:
        Current status of the detection.
    severity:
        Severity level.
    event:
        The security event that triggered the detection.
    description:
        Description of the detection.
    created_at:
        When the detection was created.
    reviewed_by:
        User who reviewed the detection.
    review_notes:
        Notes from the review.
    """

    detection_id: str = field(default_factory=lambda: str(uuid4()))
    rule_id: str = ""
    rule_name: str = ""
    status: DetectionStatus = DetectionStatus.NEW
    severity: RuleSeverity = RuleSeverity.MEDIUM
    event: SecurityEvent | None = None
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_by: str = ""
    review_notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def review(self, user: str, notes: str = "") -> None:
        """Mark the detection as reviewed."""
        self.status = DetectionStatus.REVIEWED
        self.reviewed_by = user
        self.review_notes = notes

    def confirm(self, user: str, notes: str = "") -> None:
        """Confirm the detection as a true positive."""
        self.status = DetectionStatus.CONFIRMED
        self.reviewed_by = user
        self.review_notes = notes

    def dismiss(self, user: str, notes: str = "") -> None:
        """Dismiss the detection as a false positive."""
        self.status = DetectionStatus.DISMISSED
        self.reviewed_by = user
        self.review_notes = notes

    def to_dict(self) -> dict[str, Any]:
        return {
            "detection_id": self.detection_id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "status": self.status.value,
            "severity": self.severity.value,
            "event": self.event.to_dict() if self.event else None,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "reviewed_by": self.reviewed_by,
            "review_notes": self.review_notes,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Detection:
        return cls(
            detection_id=data.get("detection_id", str(uuid4())),
            rule_id=data.get("rule_id", ""),
            rule_name=data.get("rule_name", ""),
            status=DetectionStatus(data.get("status", "new")),
            severity=RuleSeverity(data.get("severity", "medium")),
            event=SecurityEvent.from_dict(data["event"]) if data.get("event") else None,
            description=data.get("description", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            reviewed_by=data.get("reviewed_by", ""),
            review_notes=data.get("review_notes", ""),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# YARA-L Rule
# ---------------------------------------------------------------------------


@dataclass
class YaraRule:
    """A YARA-L rule for Chronicle detection.

    Attributes
    ----------
    rule_id:
        Unique identifier for this rule.
    name:
        Human-readable rule name.
    description:
        What the rule detects.
    yara_l:
        The YARA-L rule source code.
    severity:
        Severity level for detections.
    status:
        Current status of the rule.
    tags:
        Tags for filtering and grouping.
    version:
        Rule version.
    created_at:
        When the rule was created.
    updated_at:
        When the rule was last updated.
    """

    rule_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    yara_l: str = ""
    severity: RuleSeverity = RuleSeverity.MEDIUM
    status: RuleStatus = RuleStatus.DRAFT
    tags: list[str] = field(default_factory=list)
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def enable(self) -> None:
        """Enable the rule."""
        self.status = RuleStatus.ENABLED
        self.updated_at = datetime.now(timezone.utc)

    def disable(self) -> None:
        """Disable the rule."""
        self.status = RuleStatus.DISABLED
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "yara_l": self.yara_l,
            "severity": self.severity.value,
            "status": self.status.value,
            "tags": self.tags,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> YaraRule:
        return cls(
            rule_id=data.get("rule_id", str(uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            yara_l=data.get("yara_l", ""),
            severity=RuleSeverity(data.get("severity", "medium")),
            status=RuleStatus(data.get("status", "draft")),
            tags=data.get("tags", []),
            version=data.get("version", "1.0.0"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Data Source
# ---------------------------------------------------------------------------


@dataclass
class DataSource:
    """A data source configuration for Chronicle ingestion.

    Attributes
    ----------
    source_id:
        Unique identifier for this data source.
    name:
        Human-readable name.
    source_type:
        Type of data source.
    log_type:
        Chronicle log type.
    enabled:
        Whether the source is enabled.
    config:
        Source-specific configuration.
    last_ingested:
        Timestamp of last successful ingestion.
    """

    source_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    source_type: DataSourceType = DataSourceType.CUSTOM
    log_type: LogType = LogType.CUSTOM
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)
    last_ingested: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "source_type": self.source_type.value,
            "log_type": self.log_type.value,
            "enabled": self.enabled,
            "config": self.config,
            "last_ingested": self.last_ingested.isoformat() if self.last_ingested else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DataSource:
        return cls(
            source_id=data.get("source_id", str(uuid4())),
            name=data.get("name", ""),
            source_type=DataSourceType(data.get("source_type", "custom")),
            log_type=LogType(data.get("log_type", "CUSTOM")),
            enabled=data.get("enabled", True),
            config=data.get("config", {}),
            last_ingested=(
                datetime.fromisoformat(data["last_ingested"])
                if data.get("last_ingested")
                else None
            ),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@dataclass
class DashboardWidget:
    """A single dashboard widget.

    Attributes
    ----------
    widget_id:
        Unique identifier for this widget.
    title:
        Widget title.
    widget_type:
        Type of widget (e.g., "timeseries", "table", "pie").
    query:
        Chronicle query for the widget.
    config:
        Widget-specific configuration.
    """

    widget_id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    widget_type: str = "timeseries"
    query: str = ""
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "title": self.title,
            "widget_type": self.widget_type,
            "query": self.query,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DashboardWidget:
        return cls(
            widget_id=data.get("widget_id", str(uuid4())),
            title=data.get("title", ""),
            widget_type=data.get("widget_type", "timeseries"),
            query=data.get("query", ""),
            config=data.get("config", {}),
        )


@dataclass
class ChronicleDashboard:
    """A Chronicle dashboard configuration.

    Attributes
    ----------
    dashboard_id:
        Unique identifier for this dashboard.
    name:
        Dashboard name.
    description:
        Dashboard description.
    widgets:
        List of widgets in the dashboard.
    created_at:
        When the dashboard was created.
    updated_at:
        When the dashboard was last updated.
    """

    dashboard_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    widgets: list[DashboardWidget] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_widget(self, widget: DashboardWidget) -> None:
        """Add a widget to the dashboard."""
        self.widgets.append(widget)
        self.updated_at = datetime.now(timezone.utc)

    def remove_widget(self, widget_id: str) -> bool:
        """Remove a widget from the dashboard."""
        for i, w in enumerate(self.widgets):
            if w.widget_id == widget_id:
                self.widgets.pop(i)
                self.updated_at = datetime.now(timezone.utc)
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "dashboard_id": self.dashboard_id,
            "name": self.name,
            "description": self.description,
            "widgets": [w.to_dict() for w in self.widgets],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChronicleDashboard:
        return cls(
            dashboard_id=data.get("dashboard_id", str(uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            widgets=[DashboardWidget.from_dict(w) for w in data.get("widgets", [])],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# SOC Report
# ---------------------------------------------------------------------------


@dataclass
class SOCReport:
    """Aggregate SOC report for Chronicle integration.

    Attributes
    ----------
    report_id:
        Unique identifier for this report.
    started_at:
        When the report period started.
    completed_at:
        When the report period ended.
    total_events:
        Total number of events in the period.
    total_alerts:
        Total number of alerts in the period.
    total_detections:
        Total number of detections in the period.
    events:
        List of security events.
    alerts:
        List of alerts.
    detections:
        List of detections.
    severity_counts:
        Count of events by severity.
    source_counts:
        Count of events by source.
    """

    report_id: UUID = field(default_factory=uuid4)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    total_events: int = 0
    total_alerts: int = 0
    total_detections: int = 0
    events: list[SecurityEvent] = field(default_factory=list)
    alerts: list[ChronicleAlert] = field(default_factory=list)
    detections: list[Detection] = field(default_factory=list)
    severity_counts: dict[str, int] = field(default_factory=dict)
    source_counts: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": str(self.report_id),
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_events": self.total_events,
            "total_alerts": self.total_alerts,
            "total_detections": self.total_detections,
            "events": [e.to_dict() for e in self.events],
            "alerts": [a.to_dict() for a in self.alerts],
            "detections": [d.to_dict() for d in self.detections],
            "severity_counts": self.severity_counts,
            "source_counts": self.source_counts,
            "metadata": self.metadata,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def save(self, path: str | Path) -> Path:
        """Save the report to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SOCReport:
        return cls(
            report_id=UUID(data.get("report_id", str(uuid4()))),
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            total_events=data.get("total_events", 0),
            total_alerts=data.get("total_alerts", 0),
            total_detections=data.get("total_detections", 0),
            events=[SecurityEvent.from_dict(e) for e in data.get("events", [])],
            alerts=[ChronicleAlert.from_dict(a) for a in data.get("alerts", [])],
            detections=[Detection.from_dict(d) for d in data.get("detections", [])],
            severity_counts=data.get("severity_counts", {}),
            source_counts=data.get("source_counts", {}),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def load(cls, path: str | Path) -> SOCReport:
        """Load a report from a JSON file."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)
