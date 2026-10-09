"""CEF (Common Event Format)-to-Metron connector.

Ingests CEF-formatted security events from firewalls, IDS/IPS,
and other security devices, forwarding them to Metron's Kafka.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from kafka import KafkaProducer
except ImportError:
    KafkaProducer = None

logger = logging.getLogger(__name__)

# CEF header pattern: CEF:Version|Device Vendor|Device Product|Device Version|Signature ID|Name|Severity
CEF_HEADER_PATTERN = re.compile(
    r"^CEF:(?P<version>\d+)\|"
    r"(?P<device_vendor>[^|]*)\|"
    r"(?P<device_product>[^|]*)\|"
    r"(?P<device_version>[^|]*)\|"
    r"(?P<signature_id>[^|]*)\|"
    r"(?P<name>[^|]*)\|"
    r"(?P<severity>[^|]*)\|"
    r"(?P<extensions>.*)$"
)

# CEF extension key=value pairs (space-separated, values may contain escaped spaces)
CEF_EXTENSION_PATTERN = re.compile(r"(\w+)=((?:[^=\\]|\\.)*?)(?=\s+\w+=|$)")


def parse_cef_message(raw: str) -> Optional[Dict[str, Any]]:
    """Parse a CEF message into a structured dict."""
    raw = raw.strip()
    m = CEF_HEADER_PATTERN.match(raw)
    if not m:
        return None

    gd = m.groupdict()
    extensions_str = gd.pop("extensions", "")

    # Parse extensions
    extensions = {}
    for ext_match in CEF_EXTENSION_PATTERN.finditer(extensions_str):
        key = ext_match.group(1)
        value = ext_match.group(2)
        # Unescape CEF special characters
        value = value.replace("\\=", "=").replace("\\|", "|").replace("\\\\", "\\")
        extensions[key] = value

    # Map CEF severity to numeric
    severity_map = {
        "Unknown": 0, "Low": 1, "Medium": 5, "High": 8, "Very-High": 10,
    }
    severity_str = gd.get("severity", "Unknown")
    severity_num = severity_map.get(severity_str, 0)
    try:
        severity_num = int(severity_str)
    except ValueError:
        pass

    record = {
        "cef_version": int(gd.get("version", 0)),
        "device_vendor": gd.get("device_vendor", ""),
        "device_product": gd.get("device_product", ""),
        "device_version": gd.get("device_version", ""),
        "signature_id": gd.get("signature_id", ""),
        "name": gd.get("name", ""),
        "severity": severity_str,
        "severity_code": severity_num,
        "extensions": extensions,
    }

    # Extract common extension fields
    record["srcaddr"] = extensions.get("src", extensions.get("sourceAddress", ""))
    record["dstaddr"] = extensions.get("dst", extensions.get("destinationAddress", ""))
    record["srcport"] = int(extensions.get("spt", extensions.get("sourcePort", 0)) or 0)
    record["dstport"] = int(extensions.get("dpt", extensions.get("destinationPort", 0)) or 0)
    record["protocol"] = extensions.get("proto", extensions.get("transportProtocol", ""))
    record["action"] = extensions.get("act", extensions.get("deviceAction", ""))
    record["rule"] = extensions.get("cs1", extensions.get("deviceCustomString1", ""))
    record["message"] = extensions.get("msg", extensions.get("message", ""))

    # Derived fields
    record["is_high_severity"] = severity_num >= 8
    record["is_blocked"] = record["action"].lower() in ("block", "deny", "drop", "reset")
    record["is_allowed"] = record["action"].lower() in ("allow", "permit", "accept")

    return record


class CEFToMetronConnector:
    """Processes CEF messages and forwards to Metron's Kafka."""

    def __init__(
        self,
        kafka_brokers: str = "localhost:9092",
        kafka_topic: str = "cef",
    ):
        self.kafka_brokers = kafka_brokers
        self.kafka_topic = kafka_topic
        self._producer: Optional[Any] = None

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

    def process_message(self, raw: str, source_ip: str = "") -> Optional[Dict[str, Any]]:
        """Parse and enrich a CEF message."""
        record = parse_cef_message(raw)
        if record is None:
            logger.warning("Failed to parse CEF message: %s", raw[:200])
            return None

        record["source_ip"] = source_ip
        record["ingest_timestamp"] = datetime.now(timezone.utc).isoformat()
        record["connector"] = "cef_connector"
        record["connector_version"] = "1.0.0"
        record["metron_enrichment"] = {
            "needs_geoip": True,
            "needs_host_rep": True,
            "needs_whois": True,
        }

        return record

    def send_to_kafka(self, record: Dict[str, Any]) -> None:
        """Send a parsed CEF record to Metron's Kafka topic."""
        producer = self._get_producer()
        key = record.get("signature_id", "")
        producer.send(self.kafka_topic, key=key, value=record)
        producer.flush()

    def process_file(self, filepath: str) -> int:
        """Process an entire CEF log file and send to Kafka."""
        count = 0
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                record = self.process_message(line)
                if record:
                    self.send_to_kafka(record)
                    count += 1
        logger.info("Processed %d CEF records from %s", count, filepath)
        return count
