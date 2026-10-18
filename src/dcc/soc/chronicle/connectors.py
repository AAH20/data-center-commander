"""Data connectors for Google Chronicle SOC integration.

Provides connectors for ingesting security data from various sources
(AWS CloudTrail, Azure Activity, GCP Audit, syslog, etc.) into
Chronicle's unified security data platform.

Pure-Python implementation with no external dependencies.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from .models import (
    DataSource,
    DataSourceType,
    EventSeverity,
    EventStatus,
    LogType,
    SecurityEvent,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ConnectorError(Exception):
    """Base exception for connector failures."""


class ConnectionError_(ConnectorError):
    """Network or protocol-level connection failure."""


class AuthenticationError(ConnectorError):
    """Authentication or authorization failure."""


class ValidationError(ConnectorError):
    """Input validation failed."""


class RateLimitError(ConnectorError):
    """Rate limit exceeded."""


class ParseError(ConnectorError):
    """Failed to parse incoming data."""


# ---------------------------------------------------------------------------
# Connector base
# ---------------------------------------------------------------------------


class ChronicleConnector:
    """Base class for Chronicle data connectors.

    Subclasses implement source-specific ingestion logic and translate
    native log formats into Chronicle SecurityEvent objects.
    """

    def __init__(self, name: str, source_type: DataSourceType, log_type: LogType) -> None:
        self._name = name
        self._source_type = source_type
        self._log_type = log_type
        self._connected = False
        self._last_ingested: datetime | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def source_type(self) -> DataSourceType:
        return self._source_type

    @property
    def log_type(self) -> LogType:
        return self._log_type

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def last_ingested(self) -> datetime | None:
        return self._last_ingested

    def connect(self, config: dict[str, Any]) -> bool:
        """Establish connection to the data source."""
        self._validate_config(config)
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Disconnect from the data source."""
        self._connected = False

    def ingest(self, raw_data: str | bytes | dict[str, Any]) -> list[SecurityEvent]:
        """Ingest raw data and return security events."""
        if not self._connected:
            raise ConnectionError_("Connector not connected")
        events = self._parse(raw_data)
        self._last_ingested = datetime.now(timezone.utc)
        return events

    def _validate_config(self, config: dict[str, Any]) -> None:
        """Validate connector configuration."""
        pass

    def _parse(self, raw_data: str | bytes | dict[str, Any]) -> list[SecurityEvent]:
        """Parse raw data into security events."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# AWS CloudTrail connector
# ---------------------------------------------------------------------------


class AWSCloudTrailConnector(ChronicleConnector):
    """Connector for AWS CloudTrail logs."""

    def __init__(self) -> None:
        super().__init__("AWS CloudTrail", DataSourceType.AWS_CLOUDTRAIL, LogType.AWS_CLOUDTRAIL)

    def _parse(self, raw_data: str | bytes | dict[str, Any]) -> list[SecurityEvent]:
        """Parse CloudTrail events."""
        events: list[SecurityEvent] = []
        records = self._extract_records(raw_data)

        for record in records:
            try:
                event = self._parse_record(record)
                if event:
                    events.append(event)
            except (KeyError, ValueError, TypeError):
                continue

        return events

    def _extract_records(self, raw_data: str | bytes | dict[str, Any]) -> list[dict[str, Any]]:
        """Extract CloudTrail records from raw data."""
        if isinstance(raw_data, dict):
            if "Records" in raw_data:
                return raw_data["Records"]
            return [raw_data]
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode("utf-8")
        try:
            data = json.loads(raw_data)
            if "Records" in data:
                return data["Records"]
            return [data]
        except json.JSONDecodeError:
            return []

    def _parse_record(self, record: dict[str, Any]) -> SecurityEvent | None:
        """Parse a single CloudTrail record."""
        event_name = record.get("eventName", "Unknown")
        event_source = record.get("eventSource", "unknown")
        event_time = record.get("eventTime", "")
        source_ip = record.get("sourceIPAddress", "")
        user_identity = record.get("userIdentity", {})
        user_name = user_identity.get("userName", user_identity.get("arn", "unknown"))
        error_code = record.get("errorCode", "")

        severity = EventSeverity.INFO
        if error_code:
            severity = EventSeverity.HIGH
        elif event_name in ("CreateAccessKey", "CreateUser", "PutUserPolicy", "AttachUserPolicy"):
            severity = EventSeverity.MEDIUM
        elif event_name in ("DeleteTrail", "StopLogging", "PutBucketPolicy"):
            severity = EventSeverity.CRITICAL

        description = f"AWS API call: {event_name} by {user_name}"
        if error_code:
            description += f" (Error: {error_code})"

        return SecurityEvent(
            timestamp=self._parse_timestamp(event_time),
            source=f"aws:{event_source}",
            event_type="aws_api_call",
            severity=severity,
            status=EventStatus.NEW,
            description=description,
            raw_event=record,
            metadata={
                "event_name": event_name,
                "event_source": event_source,
                "source_ip": source_ip,
                "user_name": user_name,
                "error_code": error_code,
                "region": record.get("awsRegion", ""),
                "request_id": record.get("requestID", ""),
            },
        )

    def _parse_timestamp(self, ts: str) -> datetime:
        """Parse CloudTrail timestamp."""
        if not ts:
            return datetime.now(timezone.utc)
        try:
            # CloudTrail uses ISO 8601 format
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Azure Activity connector
# ---------------------------------------------------------------------------


class AzureActivityConnector(ChronicleConnector):
    """Connector for Azure Activity logs."""

    def __init__(self) -> None:
        super().__init__("Azure Activity", DataSourceType.AZURE_ACTIVITY, LogType.AZURE_ACTIVITY)

    def _parse(self, raw_data: str | bytes | dict[str, Any]) -> list[SecurityEvent]:
        """Parse Azure Activity log events."""
        events: list[SecurityEvent] = []
        records = self._extract_records(raw_data)

        for record in records:
            try:
                event = self._parse_record(record)
                if event:
                    events.append(event)
            except (KeyError, ValueError, TypeError):
                continue

        return events

    def _extract_records(self, raw_data: str | bytes | dict[str, Any]) -> list[dict[str, Any]]:
        """Extract Azure Activity records from raw data."""
        if isinstance(raw_data, dict):
            if "value" in raw_data:
                return raw_data["value"]
            return [raw_data]
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode("utf-8")
        try:
            data = json.loads(raw_data)
            if "value" in data:
                return data["value"]
            return [data]
        except json.JSONDecodeError:
            return []

    def _parse_record(self, record: dict[str, Any]) -> SecurityEvent | None:
        """Parse a single Azure Activity record."""
        operation = record.get("operationName", {}).get("value", "Unknown")
        caller = record.get("caller", "unknown")
        status = record.get("status", {}).get("value", "")
        event_time = record.get("eventTimestamp", "")
        resource_type = record.get("resourceType", {}).get("value", "")

        severity = EventSeverity.INFO
        if status == "Failed":
            severity = EventSeverity.HIGH
        elif "Create" in operation or "Delete" in operation or "Update" in operation:
            severity = EventSeverity.MEDIUM

        description = f"Azure operation: {operation} by {caller}"
        if status:
            description += f" (Status: {status})"

        return SecurityEvent(
            timestamp=self._parse_timestamp(event_time),
            source=f"azure:{resource_type}",
            event_type="azure_operation",
            severity=severity,
            status=EventStatus.NEW,
            description=description,
            raw_event=record,
            metadata={
                "operation": operation,
                "caller": caller,
                "status": status,
                "resource_type": resource_type,
                "resource_group": record.get("resourceGroupName", ""),
                "subscription_id": record.get("subscriptionId", ""),
                "correlation_id": record.get("correlationId", ""),
            },
        )

    def _parse_timestamp(self, ts: str) -> datetime:
        """Parse Azure timestamp."""
        if not ts:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# GCP Audit connector
# ---------------------------------------------------------------------------


class GCPAuditConnector(ChronicleConnector):
    """Connector for GCP Audit logs."""

    def __init__(self) -> None:
        super().__init__("GCP Audit", DataSourceType.GCP_AUDIT, LogType.GCP_AUDIT)

    def _parse(self, raw_data: str | bytes | dict[str, Any]) -> list[SecurityEvent]:
        """Parse GCP Audit log events."""
        events: list[SecurityEvent] = []
        records = self._extract_records(raw_data)

        for record in records:
            try:
                event = self._parse_record(record)
                if event:
                    events.append(event)
            except (KeyError, ValueError, TypeError):
                continue

        return events

    def _extract_records(self, raw_data: str | bytes | dict[str, Any]) -> list[dict[str, Any]]:
        """Extract GCP Audit records from raw data."""
        if isinstance(raw_data, dict):
            if "entries" in raw_data:
                return raw_data["entries"]
            return [raw_data]
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode("utf-8")
        try:
            data = json.loads(raw_data)
            if "entries" in data:
                return data["entries"]
            return [data]
        except json.JSONDecodeError:
            return []

    def _parse_record(self, record: dict[str, Any]) -> SecurityEvent | None:
        """Parse a single GCP Audit record."""
        proto_payload = record.get("protoPayload", {})
        method_name = proto_payload.get("methodName", "Unknown")
        auth_info = proto_payload.get("authenticationInfo", {})
        principal = auth_info.get("principalEmail", "unknown")
        request = proto_payload.get("request", {})
        status = record.get("status", {})
        event_time = record.get("timestamp", "")

        severity = EventSeverity.INFO
        if status.get("code", 0) != 0:
            severity = EventSeverity.HIGH
        elif "setIamPolicy" in method_name or "createServiceAccount" in method_name:
            severity = EventSeverity.MEDIUM

        description = f"GCP API call: {method_name} by {principal}"

        return SecurityEvent(
            timestamp=self._parse_timestamp(event_time),
            source="gcp:audit",
            event_type="gcp_api_call",
            severity=severity,
            status=EventStatus.NEW,
            description=description,
            raw_event=record,
            metadata={
                "method_name": method_name,
                "principal": principal,
                "status_code": status.get("code", 0),
                "resource_name": proto_payload.get("resourceName", ""),
                "service_name": proto_payload.get("serviceName", ""),
            },
        )

    def _parse_timestamp(self, ts: str) -> datetime:
        """Parse GCP timestamp."""
        if not ts:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Syslog connector
# ---------------------------------------------------------------------------


class SyslogConnector(ChronicleConnector):
    """Connector for syslog data."""

    # Common syslog patterns
    _SYSLOG_PATTERN = re.compile(
        r"^<(?P<priority>\d+)>"
        r"(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
        r"(?P<hostname>\S+)\s+"
        r"(?P<process>\S+?)(?:\[(?P<pid>\d+)\])?:\s+"
        r"(?P<message>.*)$"
    )

    def __init__(self) -> None:
        super().__init__("Syslog", DataSourceType.SYSLOG, LogType.CUSTOM)

    def _parse(self, raw_data: str | bytes | dict[str, Any]) -> list[SecurityEvent]:
        """Parse syslog messages."""
        events: list[SecurityEvent] = []

        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode("utf-8", errors="replace")
        if isinstance(raw_data, dict):
            raw_data = json.dumps(raw_data)

        for line in raw_data.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                event = self._parse_line(line)
                if event:
                    events.append(event)
            except (ValueError, TypeError):
                continue

        return events

    def _parse_line(self, line: str) -> SecurityEvent | None:
        """Parse a single syslog line."""
        match = self._SYSLOG_PATTERN.match(line)
        if not match:
            return None

        groups = match.groupdict()
        message = groups.get("message", "")
        process = groups.get("process", "unknown")
        hostname = groups.get("hostname", "unknown")

        severity = self._classify_severity(message, process)

        return SecurityEvent(
            timestamp=datetime.now(timezone.utc),
            source=f"syslog:{hostname}",
            event_type="syslog",
            severity=severity,
            status=EventStatus.NEW,
            description=f"[{process}] {message[:200]}",
            raw_event={"line": line},
            metadata={
                "hostname": hostname,
                "process": process,
                "pid": groups.get("pid"),
                "priority": groups.get("priority"),
                "message": message,
            },
        )

    def _classify_severity(self, message: str, process: str) -> EventSeverity:
        """Classify syslog message severity."""
        msg_lower = message.lower()
        if any(kw in msg_lower for kw in ("emergency", "alert", "critical", "emerg")):
            return EventSeverity.CRITICAL
        if any(kw in msg_lower for kw in ("error", "failure", "failed", "denied")):
            return EventSeverity.HIGH
        if any(kw in msg_lower for kw in ("warning", "warn")):
            return EventSeverity.MEDIUM
        if any(kw in msg_lower for kw in ("info", "notice")):
            return EventSeverity.INFO
        return EventSeverity.LOW


# ---------------------------------------------------------------------------
# Okta connector
# ---------------------------------------------------------------------------


class OktaConnector(ChronicleConnector):
    """Connector for Okta system logs."""

    def __init__(self) -> None:
        super().__init__("Okta", DataSourceType.OKTA, LogType.OKTA)

    def _parse(self, raw_data: str | bytes | dict[str, Any]) -> list[SecurityEvent]:
        """Parse Okta system log events."""
        events: list[SecurityEvent] = []
        records = self._extract_records(raw_data)

        for record in records:
            try:
                event = self._parse_record(record)
                if event:
                    events.append(event)
            except (KeyError, ValueError, TypeError):
                continue

        return events

    def _extract_records(self, raw_data: str | bytes | dict[str, Any]) -> list[dict[str, Any]]:
        """Extract Okta log records from raw data."""
        if isinstance(raw_data, dict):
            if "data" in raw_data:
                return raw_data["data"]
            return [raw_data]
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode("utf-8")
        try:
            data = json.loads(raw_data)
            if "data" in data:
                return data["data"]
            return [data]
        except json.JSONDecodeError:
            return []

    def _parse_record(self, record: dict[str, Any]) -> SecurityEvent | None:
        """Parse a single Okta log record."""
        event_type = record.get("eventType", "unknown")
        actor = record.get("actor", {})
        actor_name = actor.get("displayName", actor.get("id", "unknown"))
        outcome = record.get("outcome", {}).get("result", "")
        event_time = record.get("published", "")
        client = record.get("client", {})
        ip_address = client.get("ipAddress", "")

        severity = EventSeverity.INFO
        if outcome == "FAILURE":
            severity = EventSeverity.HIGH
        elif event_type in ("user.session.start", "user.authentication"):
            severity = EventSeverity.LOW

        description = f"Okta event: {event_type} by {actor_name}"
        if outcome:
            description += f" (Outcome: {outcome})"

        return SecurityEvent(
            timestamp=self._parse_timestamp(event_time),
            source="okta",
            event_type="okta_event",
            severity=severity,
            status=EventStatus.NEW,
            description=description,
            raw_event=record,
            metadata={
                "event_type": event_type,
                "actor": actor_name,
                "outcome": outcome,
                "ip_address": ip_address,
                "debug_context": record.get("debugContext", {}),
            },
        )

    def _parse_timestamp(self, ts: str) -> datetime:
        """Parse Okta timestamp."""
        if not ts:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Connector registry
# ---------------------------------------------------------------------------


class ConnectorRegistry:
    """Registry for Chronicle data connectors."""

    def __init__(self) -> None:
        self._connectors: dict[DataSourceType, type[ChronicleConnector]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default connectors."""
        self.register(DataSourceType.AWS_CLOUDTRAIL, AWSCloudTrailConnector)
        self.register(DataSourceType.AZURE_ACTIVITY, AzureActivityConnector)
        self.register(DataSourceType.GCP_AUDIT, GCPAuditConnector)
        self.register(DataSourceType.SYSLOG, SyslogConnector)
        self.register(DataSourceType.OKTA, OktaConnector)

    def register(
        self,
        source_type: DataSourceType,
        connector_class: type[ChronicleConnector],
    ) -> None:
        """Register a connector for a data source type."""
        self._connectors[source_type] = connector_class

    def create(self, source_type: DataSourceType) -> ChronicleConnector:
        """Create a connector instance for a data source type."""
        if source_type not in self._connectors:
            raise ConnectorError(f"No connector registered for {source_type}")
        return self._connectors[source_type]()

    def list_connectors(self) -> list[DataSourceType]:
        """List all registered connector types."""
        return list(self._connectors.keys())


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def create_connector(source_type: DataSourceType) -> ChronicleConnector:
    """Create a connector for the given data source type."""
    registry = ConnectorRegistry()
    return registry.create(source_type)


def ingest_cloudtrail(raw_data: str | bytes | dict[str, Any]) -> list[SecurityEvent]:
    """Convenience function to ingest CloudTrail data."""
    connector = AWSCloudTrailConnector()
    connector.connect({})
    return connector.ingest(raw_data)


def ingest_azure_activity(raw_data: str | bytes | dict[str, Any]) -> list[SecurityEvent]:
    """Convenience function to ingest Azure Activity data."""
    connector = AzureActivityConnector()
    connector.connect({})
    return connector.ingest(raw_data)


def ingest_gcp_audit(raw_data: str | bytes | dict[str, Any]) -> list[SecurityEvent]:
    """Convenience function to ingest GCP Audit data."""
    connector = GCPAuditConnector()
    connector.connect({})
    return connector.ingest(raw_data)


def ingest_syslog(raw_data: str | bytes) -> list[SecurityEvent]:
    """Convenience function to ingest syslog data."""
    connector = SyslogConnector()
    connector.connect({})
    return connector.ingest(raw_data)


def ingest_okta(raw_data: str | bytes | dict[str, Any]) -> list[SecurityEvent]:
    """Convenience function to ingest Okta data."""
    connector = OktaConnector()
    connector.connect({})
    return connector.ingest(raw_data)
