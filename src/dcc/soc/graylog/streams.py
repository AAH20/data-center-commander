"""Graylog stream management for SOC integration."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .models import (
    GraylogStream,
    GraylogStreamType,
)

logger = logging.getLogger(__name__)


class GraylogStreamManager:
    """Manages Graylog streams for security event routing."""

    def __init__(self) -> None:
        self._streams: dict[str, GraylogStream] = {}

    def create_stream(
        self,
        title: str,
        stream_type: GraylogStreamType = GraylogStreamType.SYSLOG,
        description: str = "",
        rules: Optional[list[str]] = None,
        index_set_id: str = "",
        default_stream: bool = False,
        matching_type: str = "AND",
        tags: Optional[dict[str, str]] = None,
    ) -> GraylogStream:
        """Create a new Graylog stream."""
        stream_id = f"stream-{title.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
        stream = GraylogStream(
            stream_id=stream_id,
            title=title,
            description=description,
            stream_type=stream_type,
            rules=rules or [],
            index_set_id=index_set_id,
            default_stream=default_stream,
            matching_type=matching_type,
            tags=tags or {},
        )
        self._streams[stream_id] = stream
        logger.info("Created Graylog stream: %s (%s)", title, stream_type.value)
        return stream

    def create_security_stream(
        self,
        title: str = "Security Events",
        description: str = "Security-related events from all sources",
        index_set_id: str = "",
    ) -> GraylogStream:
        """Create a security events stream."""
        return self.create_stream(
            title=title,
            stream_type=GraylogStreamType.SECURITY,
            description=description,
            index_set_id=index_set_id,
            tags={"category": "security", "soc": "true"},
        )

    def create_firewall_stream(
        self,
        title: str = "Firewall Logs",
        description: str = "Firewall and network security device logs",
        index_set_id: str = "",
    ) -> GraylogStream:
        """Create a firewall logs stream."""
        return self.create_stream(
            title=title,
            stream_type=GraylogStreamType.FIREWALL,
            description=description,
            index_set_id=index_set_id,
            tags={"category": "network", "soc": "true"},
        )

    def create_ids_stream(
        self,
        title: str = "IDS/IPS Alerts",
        description: str = "Intrusion detection and prevention system alerts",
        index_set_id: str = "",
    ) -> GraylogStream:
        """Create an IDS/IPS alerts stream."""
        return self.create_stream(
            title=title,
            stream_type=GraylogStreamType.IDS,
            description=description,
            index_set_id=index_set_id,
            tags={"category": "ids", "soc": "true"},
        )

    def create_auth_stream(
        self,
        title: str = "Authentication Logs",
        description: str = "Authentication and authorization logs",
        index_set_id: str = "",
    ) -> GraylogStream:
        """Create an authentication logs stream."""
        return self.create_stream(
            title=title,
            stream_type=GraylogStreamType.AUTH,
            description=description,
            index_set_id=index_set_id,
            tags={"category": "auth", "soc": "true"},
        )

    def create_web_stream(
        self,
        title: str = "Web Server Logs",
        description: str = "Web server access and error logs",
        index_set_id: str = "",
    ) -> GraylogStream:
        """Create a web server logs stream."""
        return self.create_stream(
            title=title,
            stream_type=GraylogStreamType.WEB,
            description=description,
            index_set_id=index_set_id,
            tags={"category": "web", "soc": "true"},
        )

    def create_audit_stream(
        self,
        title: str = "Audit Logs",
        description: str = "System and application audit logs",
        index_set_id: str = "",
    ) -> GraylogStream:
        """Create an audit logs stream."""
        return self.create_stream(
            title=title,
            stream_type=GraylogStreamType.AUDIT,
            description=description,
            index_set_id=index_set_id,
            tags={"category": "audit", "soc": "true"},
        )

    def get_stream(self, stream_id: str) -> Optional[GraylogStream]:
        """Get a stream by ID."""
        return self._streams.get(stream_id)

    def list_streams(
        self,
        stream_type: Optional[GraylogStreamType] = None,
        enabled_only: bool = False,
    ) -> list[GraylogStream]:
        """List all streams, optionally filtered."""
        streams = list(self._streams.values())
        if stream_type:
            streams = [s for s in streams if s.stream_type == stream_type]
        if enabled_only:
            streams = [s for s in streams if s.enabled]
        return streams

    def enable_stream(self, stream_id: str) -> bool:
        """Enable a stream."""
        stream = self._streams.get(stream_id)
        if stream:
            stream.enabled = True
            stream.updated_at = datetime.now(timezone.utc).isoformat()
            logger.info("Enabled stream: %s", stream.title)
            return True
        return False

    def disable_stream(self, stream_id: str) -> bool:
        """Disable a stream."""
        stream = self._streams.get(stream_id)
        if stream:
            stream.enabled = False
            stream.updated_at = datetime.now(timezone.utc).isoformat()
            logger.info("Disabled stream: %s", stream.title)
            return True
        return False

    def delete_stream(self, stream_id: str) -> bool:
        """Delete a stream."""
        if stream_id in self._streams:
            del self._streams[stream_id]
            logger.info("Deleted stream: %s", stream_id)
            return True
        return False

    def add_stream_rule(self, stream_id: str, rule: str) -> bool:
        """Add a rule to a stream."""
        stream = self._streams.get(stream_id)
        if stream:
            stream.rules.append(rule)
            stream.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def to_api_payload(self, stream: GraylogStream) -> dict[str, Any]:
        """Convert stream to Graylog API payload."""
        return {
            "title": stream.title,
            "description": stream.description,
            "rules": [{"type": rule} for rule in stream.rules],
            "content_pack": stream.content_pack,
            "index_set_id": stream.index_set_id,
            "default_stream": stream.default_stream,
            "matching_type": stream.matching_type,
            "remove_default_streams": False,
        }
