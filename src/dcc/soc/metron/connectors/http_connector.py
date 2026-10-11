"""HTTP/HTTPS log-to-Metron connector.

Ingests web server access logs (Apache, Nginx, IIS) and forwards
them to Metron's Kafka topic for web traffic analysis.
"""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

try:
    from kafka import KafkaProducer
except ImportError:
    KafkaProducer = None

logger = logging.getLogger(__name__)

# Apache/Nginx combined log format
COMBINED_LOG_PATTERN = re.compile(
    r"(?P<srcaddr>\S+)\s+"
    r"(?P<ident>\S+)\s+"
    r"(?P<authuser>\S+)\s+"
    r"\[(?P<timestamp>[^\]]+)\]\s+"
    r'"(?P<method>\S+)\s+(?P<request>\S+)\s+(?P<protocol>\S+)"\s+'
    r"(?P<status>\d{3})\s+"
    r"(?P<bytes>\d+|-)\s+"
    r'"(?P<referer>[^"]*)"\s+'
    r'"(?P<user_agent>[^"]*)"'
)

# Common log format (no referer/user-agent)
COMMON_LOG_PATTERN = re.compile(
    r"(?P<srcaddr>\S+)\s+"
    r"(?P<ident>\S+)\s+"
    r"(?P<authuser>\S+)\s+"
    r"\[(?P<timestamp>[^\]]+)\]\s+"
    r'"(?P<method>\S+)\s+(?P<request>\S+)\s+(?P<protocol>\S+)"\s+'
    r"(?P<status>\d{3})\s+"
    r"(?P<bytes>\d+|-)"
)

# IIS log format (W3C)
IIS_LOG_PATTERN = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<s_ip>\S+)\s+"
    r"(?P<method>\S+)\s+"
    r"(?P<uri_stem>\S+)\s+"
    r"(?P<uri_query>\S+)\s+"
    r"(?P<s_port>\d+)\s+"
    r"(?P<username>\S+)\s+"
    r"(?P<c_ip>\S+)\s+"
    r"(?P<user_agent>\S+)\s+"
    r"(?P<status>\d+)\s+"
    r"(?P<substatus>\d+)\s+"
    r"(?P<win32_status>\d+)"
)

MONTH_MAP = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def parse_apache_timestamp(ts: str) -> str | None:
    """Parse Apache log timestamp to ISO 8601."""
    # Format: 10/Oct/2023:13:55:36 +0000
    try:
        parts = ts.split()
        date_part = parts[0]

        day, month_year, time_part = date_part.split("/", 2)
        month, year = month_year.split("/")
        hour, minute, second = time_part.split(":")

        dt = datetime(
            int(year),
            MONTH_MAP[month],
            int(day),
            int(hour),
            int(minute),
            int(second),
            tzinfo=UTC,
        )
        return dt.isoformat()
    except (ValueError, KeyError, IndexError):
        return None


def parse_combined_log_line(line: str) -> dict[str, Any] | None:
    """Parse a combined/common log format line."""
    m = COMBINED_LOG_PATTERN.match(line)
    if not m:
        m = COMMON_LOG_PATTERN.match(line)
    if not m:
        return None

    gd = m.groupdict()
    bytes_sent = 0 if gd.get("bytes", "-") == "-" else int(gd.get("bytes", 0))
    status = int(gd.get("status", 0))
    method = str(gd.get("method", ""))

    record = {
        "srcaddr": gd.get("srcaddr", ""),
        "ident": gd.get("ident", "-"),
        "authuser": gd.get("authuser", "-"),
        "timestamp": parse_apache_timestamp(gd.get("timestamp", "")),
        "method": method,
        "request": gd.get("request", ""),
        "protocol": gd.get("protocol", ""),
        "status": status,
        "bytes": bytes_sent,
        "referer": gd.get("referer", "-"),
        "user_agent": gd.get("user_agent", "-"),
        "log_format": "combined" if "user_agent" in gd else "common",
    }

    # Derived fields
    record["is_error"] = status >= 400
    record["is_server_error"] = status >= 500
    record["is_redirect"] = 300 <= status < 400
    record["is_success"] = 200 <= status < 300
    record["is_get"] = method == "GET"
    record["is_post"] = method == "POST"

    return record


def parse_iis_log_line(line: str) -> dict[str, Any] | None:
    """Parse an IIS W3C log line."""
    m = IIS_LOG_PATTERN.match(line)
    if not m:
        return None

    gd = m.groupdict()
    try:
        dt = datetime.strptime(gd["timestamp"], "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=UTC)
        timestamp = dt.isoformat()
    except ValueError:
        timestamp = gd["timestamp"]

    return {
        "timestamp": timestamp,
        "s_ip": gd.get("s_ip", ""),
        "method": gd.get("method", ""),
        "uri_stem": gd.get("uri_stem", ""),
        "uri_query": gd.get("uri_query", ""),
        "s_port": int(gd.get("s_port", 0)),
        "username": gd.get("username", ""),
        "srcaddr": gd.get("c_ip", ""),
        "user_agent": gd.get("user_agent", ""),
        "status": int(gd.get("status", 0)),
        "substatus": int(gd.get("substatus", 0)),
        "win32_status": int(gd.get("win32_status", 0)),
        "log_format": "iis",
    }


class HTTPLogToMetronConnector:
    """Processes HTTP access log lines and forwards to Metron's Kafka."""

    def __init__(
        self,
        kafka_brokers: str = "localhost:9092",
        kafka_topic: str = "http",
        log_format: str = "auto",
    ):
        self.kafka_brokers = kafka_brokers
        self.kafka_topic = kafka_topic
        self.log_format = log_format
        self._producer: Any | None = None

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

    def process_line(self, line: str, source_ip: str = "") -> dict[str, Any] | None:
        """Parse a single log line and enrich it."""
        line = line.strip()
        if not line or line.startswith("#"):
            return None

        record = None
        if self.log_format in ("auto", "combined", "common"):
            record = parse_combined_log_line(line)
        if record is None and self.log_format in ("auto", "iis"):
            record = parse_iis_log_line(line)

        if record is None:
            logger.warning("Failed to parse HTTP log line: %s", line[:200])
            return None

        record["source_ip"] = source_ip
        record["ingest_timestamp"] = datetime.now(UTC).isoformat()
        record["connector"] = "http_connector"
        record["connector_version"] = "1.0.0"
        record["metron_enrichment"] = {
            "needs_geoip": True,
            "needs_host_rep": True,
            "needs_whois": False,
        }

        return record

    def send_to_kafka(self, record: dict[str, Any]) -> None:
        """Send a parsed record to Metron's Kafka topic."""
        producer = self._get_producer()
        key = record.get("srcaddr", "")
        producer.send(self.kafka_topic, key=key, value=record)
        producer.flush()

    def process_file(self, filepath: str) -> int:
        """Process an entire log file and send to Kafka."""
        count = 0
        with open(filepath, encoding="utf-8", errors="replace") as f:
            for line in f:
                record = self.process_line(line)
                if record:
                    self.send_to_kafka(record)
                    count += 1
        logger.info("Processed %d records from %s", count, filepath)
        return count
