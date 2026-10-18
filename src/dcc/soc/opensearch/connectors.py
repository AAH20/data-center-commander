"""OpenSearch data connectors for SOC integration."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .models import (
    OpenSearchConnector,
    OpenSearchConnectorStatus,
    OpenSearchConnectorType,
)

logger = logging.getLogger(__name__)


@dataclass
class OpenSearchAPIConfig:
    """Configuration for OpenSearch REST API connection."""

    api_url: str = "http://localhost:9200"
    username: str = "admin"
    password: str = ""
    api_key: str = ""
    timeout: int = 30
    verify_ssl: bool = True
    ca_cert: str = ""
    proxy: str = ""

    @property
    def auth_header(self) -> dict[str, str]:
        """Get authentication headers."""
        if self.api_key:
            return {"Authorization": f"ApiKey {self.api_key}", "Content-Type": "application/json"}
        import base64

        creds = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}


class OpenSearchConnectorManager:
    """Manages OpenSearch data connectors."""

    def __init__(self, config: OpenSearchAPIConfig) -> None:
        self.config = config
        self._connectors: dict[str, OpenSearchConnector] = {}

    def create_connector(
        self,
        name: str,
        connector_type: OpenSearchConnectorType,
        listen_port: int = 514,
        listen_address: str = "0.0.0.0",
        index_name: str = "",
        config: Optional[dict] = None,
        description: str = "",
    ) -> OpenSearchConnector:
        """Create a new OpenSearch input connector."""
        connector_id = f"connector-{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
        connector = OpenSearchConnector(
            connector_id=connector_id,
            name=name,
            connector_type=connector_type,
            listen_address=listen_address,
            listen_port=listen_port,
            index_name=index_name,
            config=config or {},
            description=description,
        )
        self._connectors[connector_id] = connector
        logger.info("Created OpenSearch connector: %s (%s)", name, connector_type.value)
        return connector

    def create_syslog_udp_connector(
        self,
        name: str = "Syslog UDP",
        port: int = 514,
        index_name: str = "security-syslog",
    ) -> OpenSearchConnector:
        """Create a Syslog UDP input connector."""
        return self.create_connector(
            name=name,
            connector_type=OpenSearchConnectorType.SYSLOG_UDP,
            listen_port=port,
            index_name=index_name,
            config={"recv_buffer_size": 2097152, "number_worker_threads": 2},
        )

    def create_syslog_tcp_connector(
        self,
        name: str = "Syslog TCP",
        port: int = 1514,
        index_name: str = "security-syslog",
    ) -> OpenSearchConnector:
        """Create a Syslog TCP input connector."""
        return self.create_connector(
            name=name,
            connector_type=OpenSearchConnectorType.SYSLOG_TCP,
            listen_port=port,
            index_name=index_name,
            config={"recv_buffer_size": 2097152, "number_worker_threads": 2},
        )

    def create_beats_connector(
        self,
        name: str = "Beats",
        port: int = 5044,
        index_name: str = "security-beats",
    ) -> OpenSearchConnector:
        """Create a Beats input connector."""
        return self.create_connector(
            name=name,
            connector_type=OpenSearchConnectorType.BEATS,
            listen_port=port,
            index_name=index_name,
            config={"recv_buffer_size": 2097152, "number_worker_threads": 2},
        )

    def create_kafka_connector(
        self,
        name: str = "Kafka",
        port: int = 9092,
        index_name: str = "security-kafka",
        kafka_config: Optional[dict] = None,
    ) -> OpenSearchConnector:
        """Create a Kafka input connector."""
        config = kafka_config or {
            "bootstrap_servers": "localhost:9092",
            "consumer_threads": 2,
            "fetch_wait_max": 100,
        }
        return self.create_connector(
            name=name,
            connector_type=OpenSearchConnectorType.KAFKA,
            listen_port=port,
            index_name=index_name,
            config=config,
        )

    def create_s3_connector(
        self,
        name: str = "S3",
        index_name: str = "security-s3",
        s3_config: Optional[dict] = None,
    ) -> OpenSearchConnector:
        """Create an S3 input connector."""
        config = s3_config or {
            "bucket": "security-logs",
            "region": "us-east-1",
            "prefix": "logs/",
            "compression": "gzip",
        }
        return self.create_connector(
            name=name,
            connector_type=OpenSearchConnectorType.S3,
            index_name=index_name,
            config=config,
        )

    def create_cloudtrail_connector(
        self,
        name: str = "CloudTrail",
        index_name: str = "security-cloudtrail",
        cloudtrail_config: Optional[dict] = None,
    ) -> OpenSearchConnector:
        """Create an AWS CloudTrail input connector."""
        config = cloudtrail_config or {
            "bucket": "cloudtrail-logs",
            "region": "us-east-1",
            "prefix": "AWSLogs/",
            "compression": "gzip",
        }
        return self.create_connector(
            name=name,
            connector_type=OpenSearchConnectorType.CLOUDTRAIL,
            index_name=index_name,
            config=config,
        )

    def create_cef_connector(
        self,
        name: str = "CEF",
        port: int = 514,
        index_name: str = "security-cef",
    ) -> OpenSearchConnector:
        """Create a CEF (Common Event Format) input connector."""
        return self.create_connector(
            name=name,
            connector_type=OpenSearchConnectorType.CEF,
            listen_port=port,
            index_name=index_name,
            config={"recv_buffer_size": 2097152},
        )

    def create_netflow_connector(
        self,
        name: str = "NetFlow",
        port: int = 2055,
        index_name: str = "security-netflow",
    ) -> OpenSearchConnector:
        """Create a NetFlow input connector."""
        return self.create_connector(
            name=name,
            connector_type=OpenSearchConnectorType.NETFLOW,
            listen_port=port,
            index_name=index_name,
            config={"recv_buffer_size": 2097152},
        )

    def get_connector(self, connector_id: str) -> Optional[OpenSearchConnector]:
        """Get a connector by ID."""
        return self._connectors.get(connector_id)

    def list_connectors(
        self,
        connector_type: Optional[OpenSearchConnectorType] = None,
        status: Optional[OpenSearchConnectorStatus] = None,
    ) -> list[OpenSearchConnector]:
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
            connector.status = OpenSearchConnectorStatus.RUNNING
            connector.updated_at = datetime.now(timezone.utc).isoformat()
            logger.info("Started connector: %s", connector.name)
            return True
        return False

    def stop_connector(self, connector_id: str) -> bool:
        """Stop a connector."""
        connector = self._connectors.get(connector_id)
        if connector:
            connector.status = OpenSearchConnectorStatus.STOPPED
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

    def get_connector_config(self, connector: OpenSearchConnector) -> dict[str, Any]:
        """Get the OpenSearch API configuration for a connector."""
        config: dict[str, Any] = {
            "name": connector.name,
            "description": connector.description,
            "index_name": connector.index_name,
            "configuration": {
                "listen_address": connector.listen_address,
                "listen_port": connector.listen_port,
                "batch_size": connector.batch_size,
                "batch_wait_time": connector.batch_wait_time,
            },
        }
        config["configuration"].update(connector.config)
        return config

    def to_api_payload(self, connector: OpenSearchConnector) -> dict[str, Any]:
        """Convert connector to OpenSearch API payload."""
        return self.get_connector_config(connector)
