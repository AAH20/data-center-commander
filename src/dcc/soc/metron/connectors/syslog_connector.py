"""Syslog-to-Metron connector.

Ingests syslog messages (RFC 3164 / RFC 5424) and forwards them
to Metron's Kafka topic for real-time enrichment and indexing.
"""

import json
import logging
import re
import socket
from datetime import UTC, datetime
from typing import Any

try:
    from kafka import KafkaProducer
except ImportError:
    KafkaProducer = None

logger = logging.getLogger(__name__)

# RFC 5424 syslog pattern
RFC5424_PATTERN = re.compile(
    r"<(?P<priority>\d{1,3})>"
    r"(?P<version>\d)\s+"
    r"(?P<timestamp>\S+)\s+"
    r"(?P<hostname>\S+)\s+"
    r"(?P<app_name>\S+)\s+"
    r"(?P<proc_id>\S+)\s+"
    r"(?P<msg_id>\S+)\s+"
    r"(?P<sd>\[.*?\]|-)\s*"
    r"(?P<message>.*)",
    re.DOTALL,
)

# RFC 3164 syslog pattern
RFC3164_PATTERN = re.compile(
    r"<(?P<priority>\d{1,3})>"
    r"(?P<timestamp>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<hostname>\S+)\s+"
    r"(?P<message>.*)",
    re.DOTALL,
)

FACILITY_NAMES = {
    0: "kern",
    1: "user",
    2: "mail",
    3: "daemon",
    4: "auth",
    5: "syslog",
    6: "lpr",
    7: "news",
    8: "uucp",
    9: "cron",
    10: "authpriv",
    11: "ftp",
    16: "local0",
    17: "local1",
    18: "local2",
    19: "local3",
    20: "local4",
    21: "local5",
    22: "local6",
    23: "local7",
}

SEVERITY_NAMES = {
    0: "emergency",
    1: "alert",
    2: "critical",
    3: "error",
    4: "warning",
    5: "notice",
    6: "info",
    7: "debug",
}


def parse_syslog(raw: str) -> dict[str, Any] | None:
    """Parse a raw syslog message into a structured dict."""
    # Try RFC 5424 first
    m = RFC5424_PATTERN.match(raw)
    if m:
        gd = m.groupdict()
        priority = int(gd["priority"])
        return {
            "timestamp": gd["timestamp"],
            "hostname": gd["hostname"],
            "app_name": gd["app_name"],
            "proc_id": gd["proc_id"],
            "msg_id": gd["msg_id"],
            "facility": FACILITY_NAMES.get(priority >> 3, "unknown"),
            "severity": SEVERITY_NAMES.get(priority & 0x07, "unknown"),
            "severity_code": priority & 0x07,
            "facility_code": priority >> 3,
            "message": gd["message"].strip(),
            "protocol": "RFC5424",
        }

    # Fall back to RFC 3164
    m = RFC3164_PATTERN.match(raw)
    if m:
        gd = m.groupdict()
        priority = int(gd["priority"])
        return {
            "timestamp": gd["timestamp"],
            "hostname": gd["hostname"],
            "app_name": "-",
            "proc_id": "-",
            "msg_id": "-",
            "facility": FACILITY_NAMES.get(priority >> 3, "unknown"),
            "severity": SEVERITY_NAMES.get(priority & 0x07, "unknown"),
            "severity_code": priority & 0x07,
            "facility_code": priority >> 3,
            "message": gd["message"].strip(),
            "protocol": "RFC3164",
        }

    return None


class SyslogToMetronConnector:
    """Listens for syslog messages and forwards them to Metron's Kafka."""

    def __init__(
        self,
        kafka_brokers: str = "localhost:9092",
        kafka_topic: str = "syslog",
        listen_host: str = "0.0.0.0",
        listen_port: int = 514,
        protocol: str = "udp",
    ):
        self.kafka_brokers = kafka_brokers
        self.kafka_topic = kafka_topic
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.protocol = protocol
        self._producer: Any | None = None
        self._running = False

    def _get_producer(self) -> Any:
        if self._producer is None:
            if KafkaProducer is None:
                raise RuntimeError("kafka-python is required: pip install kafka-python")
            self._producer = KafkaProducer(
                bootstrap_servers=self.kafka_brokers.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                retries=3,
                linger_ms=10,
            )
        return self._producer

    def process_message(self, raw: str, source_ip: str = "") -> dict[str, Any] | None:
        """Parse and enrich a single syslog message."""
        parsed = parse_syslog(raw)
        if parsed is None:
            logger.warning("Failed to parse syslog message: %s", raw[:200])
            return None

        parsed["source_ip"] = source_ip
        parsed["ingest_timestamp"] = datetime.now(UTC).isoformat()
        parsed["connector"] = "syslog_connector"
        parsed["connector_version"] = "1.0.0"

        # Metron-specific enrichment hints
        parsed["metron_enrichment"] = {
            "needs_geoip": True,
            "needs_host_rep": True,
            "needs_whois": False,
        }

        return parsed

    def send_to_kafka(self, message: dict[str, Any]) -> None:
        """Send a parsed message to Metron's Kafka topic."""
        producer = self._get_producer()
        key = message.get("hostname", "")
        producer.send(self.kafka_topic, key=key, value=message)
        producer.flush()

    def start(self) -> None:
        """Start the syslog listener and Kafka forwarder."""
        self._running = True
        logger.info(
            "Starting syslog connector on %s:%d (%s) -> Kafka topic '%s'",
            self.listen_host,
            self.listen_port,
            self.protocol,
            self.kafka_topic,
        )

        if self.protocol == "udp":
            self._listen_udp()
        else:
            self._listen_tcp()

    def _listen_udp(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.listen_host, self.listen_port))
        sock.settimeout(1.0)

        while self._running:
            try:
                data, addr = sock.recvfrom(65535)
                raw = data.decode("utf-8", errors="replace")
                parsed = self.process_message(raw, source_ip=addr[0])
                if parsed:
                    self.send_to_kafka(parsed)
            except TimeoutError:
                continue
            except Exception as e:
                logger.error("Error processing syslog message: %s", e)

        sock.close()

    def _listen_tcp(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.listen_host, self.listen_port))
        sock.listen(5)
        sock.settimeout(1.0)

        while self._running:
            try:
                conn, addr = sock.accept()
                with conn:
                    data = b""
                    while True:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        data += chunk
                    raw = data.decode("utf-8", errors="replace")
                    parsed = self.process_message(raw, source_ip=addr[0])
                    if parsed:
                        self.send_to_kafka(parsed)
            except TimeoutError:
                continue
            except Exception as e:
                logger.error("Error processing TCP syslog message: %s", e)

        sock.close()

    def stop(self) -> None:
        self._running = False
        if self._producer:
            self._producer.close()
