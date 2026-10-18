"""Graylog data connectors for SOC integration."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .models import (
    GraylogConnector,
    GraylogConnectorStatus,
    GraylogConnectorType,
)

logger = logging.getLogger(__name__)


@dataclass
class GraylogAPIConfig:
    """Configuration for Graylog REST API connection."""

    api_url: str = "http://localhost:9000/api"
    username: str = "admin"
    password: str = ""
    token: str = ""
    timeout: int = 30
    verify_ssl: bool = True
    ca_cert: str = ""
    proxy: str = ""

    @property
    def auth_header(self) -> dict[str, str]:
        """Get authentication headers."""
        if self.token:
            return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        import base64

        creds = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}


class GraylogConnectorManager:
    """Manages Graylog data connectors."""

    def __init__(self, config: GraylogAPIConfig) -> None:
        self.config = config
        self._connectors: dict[str, GraylogConnector] = {}

    def create_connector(
        self,
        name: str,
        connector_type: GraylogConnectorType,
        listen_port: int = 514,
        listen_address: str = "0.0.0.0",
        stream_ids: Optional[list[str]] = None,
        config: Optional[dict] = None,
        description: str = "",
    ) -> GraylogConnector:
        """Create a new Graylog input connector."""
        connector_id = f"connector-{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
        connector = GraylogConnector(
            connector_id=connector_id,
            name=name,
            connector_type=connector_type,
            listen_address=listen_address,
            listen_port=listen_port,
            stream_ids=stream_ids or [],
            config=config or {},
            description=description,
        )
        self._connectors[connector_id] = connector
        logger.info("Created Graylog connector: %s (%s)", name, connector_type.value)
        return connector

    def create_syslog_udp_connector(
        self,
        name: str = "Syslog UDP",
        port: int = 514,
        stream_ids: Optional[list[str]] = None,
    ) -> GraylogConnector:
        """Create a Syslog UDP input connector."""
        return self.create_connector(
            name=name,
            connector_type=GraylogConnectorType.SYSLOG_UDP,
            listen_port=port,
            stream_ids=stream_ids,
            config={"recv_buffer_size": 2097152, "number_worker_threads": 2},
        )

    def create_syslog_tcp_connector(
        self,
        name: str = "Syslog TCP",
        port: int = 514,
        stream_ids: Optional[list[str]] = None,
    ) -> GraylogConnector:
        """Create a Syslog TCP input connector."""
        return self.create_connector(
            name=name,
            connector_type=GraylogConnectorType.SYSLOG_TCP,
            listen_port=port,
            stream_ids=stream_ids,
            config={"recv_buffer_size": 2097152, "number_worker_threads": 2},
        )

    def create_gelf_connector(
        self,
        name: str = "GELF",
        port: int = 12201,
        stream_ids: Optional[list[str]] = None,
    ) -> GraylogConnector:
        """Create a GELF (Graylog Extended Log Format) input connector."""
        return self.create_connector(
            name=name,
            connector_type=GraylogConnectorType.GELF,
            listen_port=port,
            stream_ids=stream_ids,
            config={"recv_buffer_size": 2097152, "number_worker_threads": 2, "decompress_size_limit": 8388608},
        )

    def create_beats_connector(
        self,
        name: str = "Beats",
        port: int = 5044,
        stream_ids: Optional[list[str]] = None,
    ) -> GraylogConnector:
        """Create a Beats (Elasticsearch Beats) input connector."""
        return self.create_connector(
            name=name,
            connector_type=GraylogConnectorType.BEATS,
            listen_port=port,
            stream_ids=stream_ids,
            config={"recv_buffer_size": 2097152, "number_worker_threads": 2},
        )

    def create_kafka_connector(
        self,
        name: str = "Kafka",
        port: int = 9092,
        stream_ids: Optional[list[str]] = None,
        kafka_config: Optional[dict] = None,
    ) -> GraylogConnector:
        """Create a Kafka input connector."""
        config = kafka_config or {
            "bootstrap_servers": "localhost:9092",
            "consumer_threads": 2,
            "fetch_wait_max": 100,
        }
        return self.create_connector(
            name=name,
            connector_type=GraylogConnectorType.KAFKA,
            listen_port=port,
            stream_ids=stream_ids,
            config=config,
        )

    def create_cef_connector(
        self,
        name: str = "CEF",
        port: int = 514,
        stream_ids: Optional[list[str]] = None,
    ) -> GraylogConnector:
        """Create a CEF (Common Event Format) input connector."""
        return self.create_connector(
            name=name,
            connector_type=GraylogConnectorType.CEF,
            listen_port=port,
            stream_ids=stream_ids,
            config={"recv_buffer_size": 2097152},
        )

    def create_netflow_connector(
        self,
        name: str = "NetFlow",
        port: int = 2055,
        stream_ids: Optional[list[str]] = None,
    ) -> GraylogConnector:
        """Create a NetFlow input connector."""
        return self.create_connector(
            name=name,
            connector_type=GraylogConnectorType.NETFLOW,
            listen_port=port,
            stream_ids=stream_ids,
            config={"recv_buffer_size": 2097152},
        )

    def get_connector(self, connector_id: str) -> Optional[GraylogConnector]:
        """Get a connector by ID."""
        return self._connectors.get(connector_id)

    def list_connectors(
        self,
        connector_type: Optional[GraylogConnectorType] = None,
        status: Optional[GraylogConnectorStatus] = None,
    ) -> list[GraylogConnector]:
        """List all connectors, optionally filtered."""
        connectors = list(self._connectors.values())
        if connector_type:
            connectors = [c for c in connectors if c.connector_type == connector_type]
        if status:
            connectors = [c for c in connectors if c.status == status]
        return connectors

    def start_connector(self, connector_id: str) -> bool:
        """Start a connector."""
        connector = self._connectors.get(connector_id)
        if connector:
            connector.status = GraylogConnectorStatus.RUNNING
            connector.updated_at = datetime.now(timezone.utc).isoformat()
            logger.info("Started connector: %s", connector.name)
            return True
        return False

    def stop_connector(self, connector_id: str) -> bool:
        """Stop a connector."""
        connector = self._connectors.get(connector_id)
        if connector:
            connector.status = GraylogConnectorStatus.STOPPED
            connector.updated_at = datetime.now(timezone.utc).isoformat()
            logger.info("Stopped connector: %s", connector.name)
            return True
        return False

    def delete_connector(self, connector_id: str) -> bool:
        """Delete a connector."""
        if connector_id in self._connectors:
            del self._connectors[connector_id]
            logger.info("Deleted connector: %s", connector_id)
            return True
        return False

    def get_connector_config(self, connector: GraylogConnector) -> dict[str, Any]:
        """Get the Graylog API configuration for a connector."""
        config: dict[str, Any] = {
            "name": connector.name,
            "title": connector.name,
            "description": connector.description,
            "global": True,
            "configuration": {
                "recv_buffer_size": connector.recv_buffer_size,
                "number_worker_threads": connector.number_worker_threads,
                "bind_address": connector.listen_address,
                "port": connector.listen_port,
                "decompress_size_limit": 8388608,
            },
        }
        config["configuration"].update(connector.config)
        return config

    def to_api_payload(self, connector: GraylogConnector) -> dict[str, Any]:
        """Convert connector to Graylog API payload."""
        return self.get_connector_config(connector)
