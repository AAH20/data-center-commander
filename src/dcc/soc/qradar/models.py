"""Data models for IBM QRadar SOC integration.

Defines normalized representations of QRadar entities: offenses, events,
assets, flows, rules, and dashboards. All models are immutable dataclasses
with slots for memory efficiency.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class OffenseStatus(str, Enum):
    """Status of a QRadar offense."""
    OPEN = "open"
    CLOSED = "closed"
    HIDDEN = "hidden"
    PROTECTED = "protected"


class OffenseSeverity(str, Enum):
    """Severity level of a QRadar offense."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class EventCategory(str, Enum):
    """Category of a QRadar event."""
    AUTHENTICATION = "authentication"
    NETWORK = "network"
    SYSTEM = "system"
    APPLICATION = "application"
    DATABASE = "database"
    WEB = "web"
    MAIL = "malware"
    POLICY = "policy"
    OTHER = "other"


class AssetStatus(str, Enum):
    """Status of a QRadar asset."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"
    UNKNOWN = "unknown"


class FlowProtocol(str, Enum):
    """Network flow protocol."""
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    OTHER = "other"


class RuleType(str, Enum):
    """Type of QRadar rule."""
    EVENT = "event"
    FLOW = "flow"
    COMMON = "common"
    ANOMALY = "anomaly"
    BEHAVIOR = "behavior"


class RuleStatus(str, Enum):
    """Status of a QRadar rule."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"


class DashboardType(str, Enum):
    """Type of QRadar dashboard."""
    STANDARD = "standard"
    CUSTOM = "custom"
    SYSTEM = "system"


# ---------------------------------------------------------------------------
# Offense models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class QRadarOffense:
    """Normalized QRadar offense."""
    offense_id: str
    status: OffenseStatus
    severity: OffenseSeverity
    description: str
    source_ip: str | None = None
    destination_ip: str | None = None
    source_port: int | None = None
    destination_port: int | None = None
    protocol: str | None = None
    event_count: int = 0
    flow_count: int = 0
    rule_id: str | None = None
    rule_name: str | None = None
    assigned_to: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    closed_at: str | None = None
    close_reason: str | None = None
    follow_up: bool = False
    protected: bool = False
    source_network: str | None = None
    destination_network: str | None = None
    source_asset_id: str | None = None
    destination_asset_id: str | None = None
    username: str | None = None
    categories: list[str] = field(default_factory=list)
    log_sources: list[str] = field(default_factory=list)
    relevance: int = 0
    credibility: int = 0
    impact: int = 0
    destination_country: str | None = None
    source_country: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "offense_id": self.offense_id,
            "status": self.status.value,
            "severity": self.severity.value,
            "description": self.description,
            "source_ip": self.source_ip,
            "destination_ip": self.destination_ip,
            "source_port": self.source_port,
            "destination_port": self.destination_port,
            "protocol": self.protocol,
            "event_count": self.event_count,
            "flow_count": self.flow_count,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "closed_at": self.closed_at,
            "close_reason": self.close_reason,
            "follow_up": self.follow_up,
            "protected": self.protected,
            "source_network": self.source_network,
            "destination_network": self.destination_network,
            "source_asset_id": self.source_asset_id,
            "destination_asset_id": self.destination_asset_id,
            "username": self.username,
            "categories": list(self.categories),
            "log_sources": list(self.log_sources),
            "relevance": self.relevance,
            "credibility": self.credibility,
            "impact": self.impact,
            "destination_country": self.destination_country,
            "source_country": self.source_country,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QRadarOffense:
        """Reconstruct from dictionary."""
        return cls(
            offense_id=str(data["offense_id"]),
            status=OffenseStatus(data.get("status", "open")),
            severity=OffenseSeverity(data.get("severity", "medium")),
            description=str(data.get("description", "")),
            source_ip=data.get("source_ip"),
            destination_ip=data.get("destination_ip"),
            source_port=data.get("source_port"),
            destination_port=data.get("destination_port"),
            protocol=data.get("protocol"),
            event_count=int(data.get("event_count", 0)),
            flow_count=int(data.get("flow_count", 0)),
            rule_id=data.get("rule_id"),
            rule_name=data.get("rule_name"),
            assigned_to=data.get("assigned_to"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            closed_at=data.get("closed_at"),
            close_reason=data.get("close_reason"),
            follow_up=bool(data.get("follow_up", False)),
            protected=bool(data.get("protected", False)),
            source_network=data.get("source_network"),
            destination_network=data.get("destination_network"),
            source_asset_id=data.get("source_asset_id"),
            destination_asset_id=data.get("destination_asset_id"),
            username=data.get("username"),
            categories=list(data.get("categories", [])),
            log_sources=list(data.get("log_sources", [])),
            relevance=int(data.get("relevance", 0)),
            credibility=int(data.get("credibility", 0)),
            impact=int(data.get("impact", 0)),
            destination_country=data.get("destination_country"),
            source_country=data.get("source_country"),
            metadata=dict(data.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Event models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class QRadarEvent:
    """Normalized QRadar event."""
    event_id: str
    category: EventCategory
    description: str
    source_ip: str | None = None
    destination_ip: str | None = None
    source_port: int | None = None
    destination_port: int | None = None
    protocol: str | None = None
    severity: int = 0
    credibility: int = 0
    relevance: int = 0
    impact: int = 0
    username: str | None = None
    log_source_id: str | None = None
    log_source_name: str | None = None
    event_time: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    magnitude: float = 0.0
    count: int = 1
    source_network: str | None = None
    destination_network: str | None = None
    source_asset_id: str | None = None
    destination_asset_id: str | None = None
    source_country: str | None = None
    destination_country: str | None = None
    device_type: str | None = None
    device_category: str | None = None
    payload: str | None = None
    flags: list[str] = field(default_factory=list)
    custom_properties: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "category": self.category.value,
            "description": self.description,
            "source_ip": self.source_ip,
            "destination_ip": self.destination_ip,
            "source_port": self.source_port,
            "destination_port": self.destination_port,
            "protocol": self.protocol,
            "severity": self.severity,
            "credibility": self.credibility,
            "relevance": self.relevance,
            "impact": self.impact,
            "username": self.username,
            "log_source_id": self.log_source_id,
            "log_source_name": self.log_source_name,
            "event_time": self.event_time,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "magnitude": self.magnitude,
            "count": self.count,
            "source_network": self.source_network,
            "destination_network": self.destination_network,
            "source_asset_id": self.source_asset_id,
            "destination_asset_id": self.destination_asset_id,
            "source_country": self.source_country,
            "destination_country": self.destination_country,
            "device_type": self.device_type,
            "device_category": self.device_category,
            "payload": self.payload,
            "flags": list(self.flags),
            "custom_properties": dict(self.custom_properties),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QRadarEvent:
        """Reconstruct from dictionary."""
        return cls(
            event_id=str(data["event_id"]),
            category=EventCategory(data.get("category", "other")),
            description=str(data.get("description", "")),
            source_ip=data.get("source_ip"),
            destination_ip=data.get("destination_ip"),
            source_port=data.get("source_port"),
            destination_port=data.get("destination_port"),
            protocol=data.get("protocol"),
            severity=int(data.get("severity", 0)),
            credibility=int(data.get("credibility", 0)),
            relevance=int(data.get("relevance", 0)),
            impact=int(data.get("impact", 0)),
            username=data.get("username"),
            log_source_id=data.get("log_source_id"),
            log_source_name=data.get("log_source_name"),
            event_time=data.get("event_time"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            magnitude=float(data.get("magnitude", 0.0)),
            count=int(data.get("count", 1)),
            source_network=data.get("source_network"),
            destination_network=data.get("destination_network"),
            source_asset_id=data.get("source_asset_id"),
            destination_asset_id=data.get("destination_asset_id"),
            source_country=data.get("source_country"),
            destination_country=data.get("destination_country"),
            device_type=data.get("device_type"),
            device_category=data.get("device_category"),
            payload=data.get("payload"),
            flags=list(data.get("flags", [])),
            custom_properties=dict(data.get("custom_properties", {})),
            metadata=dict(data.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Asset models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class QRadarAsset:
    """Normalized QRadar asset."""
    asset_id: str
    name: str
    status: AssetStatus
    ip_addresses: list[str] = field(default_factory=list)
    mac_addresses: list[str] = field(default_factory=list)
    hostnames: list[str] = field(default_factory=list)
    operating_system: str | None = None
    vulnerability_count: int = 0
    open_port_count: int = 0
    risk_score: float = 0.0
    criticality: int = 0
    business_owner: str | None = None
    support_contact: str | None = None
    asset_type: str | None = None
    zone: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    last_updated: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "asset_id": self.asset_id,
            "name": self.name,
            "status": self.status.value,
            "ip_addresses": list(self.ip_addresses),
            "mac_addresses": list(self.mac_addresses),
            "hostnames": list(self.hostnames),
            "operating_system": self.operating_system,
            "vulnerability_count": self.vulnerability_count,
            "open_port_count": self.open_port_count,
            "risk_score": self.risk_score,
            "criticality": self.criticality,
            "business_owner": self.business_owner,
            "support_contact": self.support_contact,
            "asset_type": self.asset_type,
            "zone": self.zone,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "last_updated": self.last_updated,
            "properties": dict(self.properties),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QRadarAsset:
        """Reconstruct from dictionary."""
        return cls(
            asset_id=str(data["asset_id"]),
            name=str(data.get("name", "")),
            status=AssetStatus(data.get("status", "unknown")),
            ip_addresses=list(data.get("ip_addresses", [])),
            mac_addresses=list(data.get("mac_addresses", [])),
            hostnames=list(data.get("hostnames", [])),
            operating_system=data.get("operating_system"),
            vulnerability_count=int(data.get("vulnerability_count", 0)),
            open_port_count=int(data.get("open_port_count", 0)),
            risk_score=float(data.get("risk_score", 0.0)),
            criticality=int(data.get("criticality", 0)),
            business_owner=data.get("business_owner"),
            support_contact=data.get("support_contact"),
            asset_type=data.get("asset_type"),
            zone=data.get("zone"),
            first_seen=data.get("first_seen"),
            last_seen=data.get("last_seen"),
            last_updated=data.get("last_updated"),
            properties=dict(data.get("properties", {})),
            metadata=dict(data.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Flow models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class QRadarFlow:
    """Normalized QRadar network flow."""
    flow_id: str
    protocol: FlowProtocol
    source_ip: str
    destination_ip: str
    source_port: int | None = None
    destination_port: int | None = None
    source_bytes: int = 0
    destination_bytes: int = 0
    source_packets: int = 0
    destination_packets: int = 0
    start_time: str | None = None
    end_time: str | None = None
    duration_seconds: float = 0.0
    source_network: str | None = None
    destination_network: str | None = None
    source_country: str | None = None
    destination_country: str | None = None
    application: str | None = None
    direction: str | None = None
    flags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "flow_id": self.flow_id,
            "protocol": self.protocol.value,
            "source_ip": self.source_ip,
            "destination_ip": self.destination_ip,
            "source_port": self.source_port,
            "destination_port": self.destination_port,
            "source_bytes": self.source_bytes,
            "destination_bytes": self.destination_bytes,
            "source_packets": self.source_packets,
            "destination_packets": self.destination_packets,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "source_network": self.source_network,
            "destination_network": self.destination_network,
            "source_country": self.source_country,
            "destination_country": self.destination_country,
            "application": self.application,
            "direction": self.direction,
            "flags": list(self.flags),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QRadarFlow:
        """Reconstruct from dictionary."""
        return cls(
            flow_id=str(data["flow_id"]),
            protocol=FlowProtocol(data.get("protocol", "other")),
            source_ip=str(data["source_ip"]),
            destination_ip=str(data["destination_ip"]),
            source_port=data.get("source_port"),
            destination_port=data.get("destination_port"),
            source_bytes=int(data.get("source_bytes", 0)),
            destination_bytes=int(data.get("destination_bytes", 0)),
            source_packets=int(data.get("source_packets", 0)),
            destination_packets=int(data.get("destination_packets", 0)),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            source_network=data.get("source_network"),
            destination_network=data.get("destination_network"),
            source_country=data.get("source_country"),
            destination_country=data.get("destination_country"),
            application=data.get("application"),
            direction=data.get("direction"),
            flags=list(data.get("flags", [])),
            metadata=dict(data.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Rule models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class QRadarRule:
    """Normalized QRadar custom rule."""
    rule_id: str
    name: str
    rule_type: RuleType
    status: RuleStatus
    description: str = ""
    severity: int = 0
    credibility: int = 0
    relevance: int = 0
    impact: int = 0
    enabled: bool = True
    origin: str | None = None
    creation_date: str | None = None
    modification_date: str | None = None
    owner: str | None = None
    groups: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "rule_type": self.rule_type.value,
            "status": self.status.value,
            "description": self.description,
            "severity": self.severity,
            "credibility": self.credibility,
            "relevance": self.relevance,
            "impact": self.impact,
            "enabled": self.enabled,
            "origin": self.origin,
            "creation_date": self.creation_date,
            "modification_date": self.modification_date,
            "owner": self.owner,
            "groups": list(self.groups),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QRadarRule:
        """Reconstruct from dictionary."""
        return cls(
            rule_id=str(data["rule_id"]),
            name=str(data.get("name", "")),
            rule_type=RuleType(data.get("rule_type", "event")),
            status=RuleStatus(data.get("status", "active")),
            description=str(data.get("description", "")),
            severity=int(data.get("severity", 0)),
            credibility=int(data.get("credibility", 0)),
            relevance=int(data.get("relevance", 0)),
            impact=int(data.get("impact", 0)),
            enabled=bool(data.get("enabled", True)),
            origin=data.get("origin"),
            creation_date=data.get("creation_date"),
            modification_date=data.get("modification_date"),
            owner=data.get("owner"),
            groups=list(data.get("groups", [])),
            metadata=dict(data.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Dashboard models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class QRadarDashboard:
    """Normalized QRadar dashboard."""
    dashboard_id: str
    name: str
    dashboard_type: DashboardType
    description: str = ""
    owner: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    widgets: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "dashboard_id": self.dashboard_id,
            "name": self.name,
            "dashboard_type": self.dashboard_type.value,
            "description": self.description,
            "owner": self.owner,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "widgets": list(self.widgets),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QRadarDashboard:
        """Reconstruct from dictionary."""
        return cls(
            dashboard_id=str(data["dashboard_id"]),
            name=str(data.get("name", "")),
            dashboard_type=DashboardType(data.get("dashboard_type", "custom")),
            description=str(data.get("description", "")),
            owner=data.get("owner"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            widgets=list(data.get("widgets", [])),
            metadata=dict(data.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Correlation models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class OffenseCorrelation:
    """Correlation between a data center event and a QRadar offense."""
    correlation_id: str
    offense_id: str
    event_id: str
    correlation_type: str
    confidence: float
    matched_fields: list[str] = field(default_factory=list)
    matched_values: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "correlation_id": self.correlation_id,
            "offense_id": self.offense_id,
            "event_id": self.event_id,
            "correlation_type": self.correlation_type,
            "confidence": self.confidence,
            "matched_fields": list(self.matched_fields),
            "matched_values": dict(self.matched_values),
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OffenseCorrelation:
        """Reconstruct from dictionary."""
        return cls(
            correlation_id=str(data["correlation_id"]),
            offense_id=str(data["offense_id"]),
            event_id=str(data["event_id"]),
            correlation_type=str(data.get("correlation_type", "unknown")),
            confidence=float(data.get("confidence", 0.0)),
            matched_fields=list(data.get("matched_fields", [])),
            matched_values=dict(data.get("matched_values", {})),
            created_at=str(data.get("created_at", dt.datetime.now(dt.timezone.utc).isoformat())),
            metadata=dict(data.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Search models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class QRadarSearch:
    """Normalized QRadar AQL search."""
    search_id: str
    name: str
    query: str
    status: str = "COMPLETED"
    result_count: int = 0
    created_at: str | None = None
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "search_id": self.search_id,
            "name": self.name,
            "query": self.query,
            "status": self.status,
            "result_count": self.result_count,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QRadarSearch:
        """Reconstruct from dictionary."""
        return cls(
            search_id=str(data["search_id"]),
            name=str(data.get("name", "")),
            query=str(data.get("query", "")),
            status=str(data.get("status", "COMPLETED")),
            result_count=int(data.get("result_count", 0)),
            created_at=data.get("created_at"),
            completed_at=data.get("completed_at"),
            metadata=dict(data.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Reference set models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class QRadarReferenceSet:
    """Normalized QRadar reference set."""
    set_id: str
    name: str
    element_type: str
    data_type: str
    number_of_elements: int = 0
    creation_time: str | None = None
    last_updated: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "set_id": self.set_id,
            "name": self.name,
            "element_type": self.element_type,
            "data_type": self.data_type,
            "number_of_elements": self.number_of_elements,
            "creation_time": self.creation_time,
            "last_updated": self.last_updated,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QRadarReferenceSet:
        """Reconstruct from dictionary."""
        return cls(
            set_id=str(data["set_id"]),
            name=str(data.get("name", "")),
            element_type=str(data.get("element_type", "")),
            data_type=str(data.get("data_type", "")),
            number_of_elements=int(data.get("number_of_elements", 0)),
            creation_time=data.get("creation_time"),
            last_updated=data.get("last_updated"),
            metadata=dict(data.get("metadata", {})),
        )
