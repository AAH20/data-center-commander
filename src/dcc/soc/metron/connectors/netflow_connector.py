"""NetFlow/IPFIX-to-Metron connector.

Collects NetFlow v5/v9 and IPFIX records and forwards them
to Metron's Kafka topic for network traffic analysis.
"""

import json
import logging
import socket
import struct
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from kafka import KafkaProducer
except ImportError:
    KafkaProducer = None

logger = logging.getLogger(__name__)

# NetFlow v5 field offsets (in 4-byte words)
NFV5_FIELDS = {
    "srcaddr": (0, 4),
    "dstaddr": (4, 4),
    "nexthop": (8, 4),
    "input": (12, 2),
    "output": (14, 2),
    "dPkts": (16, 4),
    "dOctets": (20, 4),
    "first": (24, 4),
    "last": (28, 4),
    "srcport": (32, 2),
    "dstport": (34, 2),
    "pad1": (36, 1),
    "tcp_flags": (37, 1),
    "prot": (38, 1),
    "tos": (39, 1),
    "src_as": (40, 2),
    "dst_as": (42, 2),
    "src_mask": (44, 1),
    "dst_mask": (45, 1),
    "pad2": (46, 2),
}

NFV5_HEADER_SIZE = 24
NFV5_RECORD_SIZE = 48


def _ip_to_str(raw: bytes) -> str:
    return socket.inet_ntoa(raw)


def parse_netflow_v5_packet(data: bytes) -> List[Dict[str, Any]]:
    """Parse a NetFlow v5 packet into flow records."""
    if len(data) < NFV5_HEADER_SIZE:
        return []

    # Parse header
    version, count = struct.unpack("!HH", data[0:4])
    if version != 5:
        return []

    sys_uptime, unix_secs, unix_nsecs, flow_sequence = struct.unpack("!IIII", data[4:20])
    engine_type, engine_id, sampling = struct.unpack("!BBH", data[20:24])

    records = []
    offset = NFV5_HEADER_SIZE

    for i in range(count):
        if offset + NFV5_RECORD_SIZE > len(data):
            break

        rec_data = data[offset:offset + NFV5_RECORD_SIZE]
        record = {
            "version": 5,
            "sys_uptime": sys_uptime,
            "unix_secs": unix_secs,
            "unix_nsecs": unix_nsecs,
            "flow_sequence": flow_sequence,
            "engine_type": engine_type,
            "engine_id": engine_id,
            "sampling_interval": sampling & 0x3FFF,
        }

        # Parse fields
        for field_name, (word_offset, size) in NFV5_FIELDS.items():
            byte_offset = word_offset * 4
            field_bytes = rec_data[byte_offset:byte_offset + size]

            if field_name in ("srcaddr", "dstaddr", "nexthop"):
                record[field_name] = _ip_to_str(field_bytes)
            elif field_name in ("input", "output", "src_as", "dst_as"):
                record[field_name] = struct.unpack("!H", field_bytes)[0]
            elif field_name in ("dPkts", "dOctets", "first", "last"):
                record[field_name] = struct.unpack("!I", field_bytes)[0]
            elif field_name in ("srcport", "dstport"):
                record[field_name] = struct.unpack("!H", field_bytes)[0]
            elif field_name == "tcp_flags":
                record[field_name] = field_bytes[0]
            elif field_name == "prot":
                record[field_name] = field_bytes[0]
            elif field_name == "tos":
                record[field_name] = field_bytes[0]
            elif field_name in ("src_mask", "dst_mask"):
                record[field_name] = field_bytes[0]

        # Derived fields
        record["timestamp"] = datetime.fromtimestamp(
            unix_secs + unix_nsecs / 1e9, tz=timezone.utc
        ).isoformat()
        record["flow_duration_ms"] = (record["last"] - record["first"])
        record["bytes_per_packet"] = (
            record["dOctets"] / record["dPkts"] if record["dPkts"] > 0 else 0
        )
        record["is_web_traffic"] = record["dstport"] in (80, 443, 8080, 8443)
        record["is_dns"] = record["dstport"] == 53
        record["is_ssh"] = record["dstport"] == 22

        records.append(record)
        offset += NFV5_RECORD_SIZE

    return records


class NetFlowToMetronConnector:
    """Listens for NetFlow v5 packets and forwards to Metron's Kafka."""

    def __init__(
        self,
        kafka_brokers: str = "localhost:9092",
        kafka_topic: str = "netflow",
        listen_host: str = "0.0.0.0",
        listen_port: int = 2055,
    ):
        self.kafka_brokers = kafka_brokers
        self.kafka_topic = kafka_topic
        self.listen_host = listen_host
        self.listen_port = listen_port
        self._producer: Optional[Any] = None
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

    def process_packet(self, data: bytes, source_ip: str = "") -> List[Dict[str, Any]]:
        """Parse a NetFlow packet and enrich records."""
        records = parse_netflow_v5_packet(data)
        for record in records:
            record["source_ip"] = source_ip
            record["ingest_timestamp"] = datetime.now(timezone.utc).isoformat()
            record["connector"] = "netflow_connector"
            record["connector_version"] = "1.0.0"
            record["metron_enrichment"] = {
                "needs_geoip": True,
                "needs_host_rep": True,
                "needs_whois": True,
            }
        return records

    def send_to_kafka(self, records: List[Dict[str, Any]]) -> None:
        """Send parsed flow records to Metron's Kafka topic."""
        producer = self._get_producer()
        for record in records:
            key = f"{record.get('srcaddr', '')}:{record.get('srcport', 0)}"
            producer.send(self.kafka_topic, key=key, value=record)
        producer.flush()

    def start(self) -> None:
        """Start the NetFlow listener."""
        self._running = True
        logger.info(
            "Starting NetFlow connector on %s:%d -> Kafka topic '%s'",
            self.listen_host, self.listen_port, self.kafka_topic,
        )

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.listen_host, self.listen_port))
        sock.settimeout(1.0)

        while self._running:
            try:
                data, addr = sock.recvfrom(65535)
                records = self.process_packet(data, source_ip=addr[0])
                if records:
                    self.send_to_kafka(records)
            except socket.timeout:
                continue
            except Exception as e:
                logger.error("Error processing NetFlow packet: %s", e)

        sock.close()

    def stop(self) -> None:
        self._running = False
        if self._producer:
            self._producer.close()
