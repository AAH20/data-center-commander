#!/usr/bin/env python3
"""
SOC Trace Processor — consumes OTel spans from webhook, enriches with
security context, and forwards to SIEM (Elasticsearch) + alerting pipeline.

Listens on :8080/v1/traces for incoming trace batches from OTel Collector.
"""
import hashlib
import json
import logging
import os
import urllib.request
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("soc-processor")

SIEM_URL = os.environ.get("SIEM_URL", "http://elasticsearch:9200")
SIEM_INDEX = os.environ.get("SIEM_INDEX", "soc-traces")
ALERT_WEBHOOK = os.environ.get("ALERT_WEBHOOK", "")
TRACE_RETENTION_DAYS = int(os.environ.get("TRACE_RETENTION_DAYS", "30"))

# Security-relevant span attributes to watch
SENSITIVE_ATTRIBUTES = {
    "http.url",
    "http.target",
    "http.host",
    "http.user_agent",
    "db.statement",
    "db.query",
    "rpc.method",
    "rpc.service",
    "messaging.destination",
    "messaging.url",
    "net.peer.ip",
    "net.peer.name",
    "net.host.ip",
    "user.id",
    "user.name",
    "user.email",
    "auth.token",
    "auth.method",
    "file.path",
    "file.name",
    "container.id",
    "container.name",
    "k8s.pod.name",
    "k8s.namespace.name",
    "k8s.deployment.name",
}

# Known attack patterns in span attributes
ATTACK_PATTERNS = [
    ("sql_injection", ["'", "union", "select", "drop", "insert", "delete", "--"]),
    ("xss", ["<script", "javascript:", "onerror=", "onload="]),
    ("path_traversal", ["../", "..\\", "/etc/passwd", "/etc/shadow"]),
    ("command_injection", [";", "|", "&", "$()", "`", "&&", "||"]),
    ("ssrf", ["http://169.254", "http://localhost", "http://127.0.0.1"]),
]


def compute_threat_score(span: dict[str, Any]) -> tuple[float, list[str]]:
    """Compute a threat score (0-100) and list of detected threats."""
    score = 0.0
    threats: list[str] = []

    # Check status code
    status = span.get("status", {})
    if status.get("code") == "ERROR":
        score += 30.0
        threats.append("error_status")

    # Check for sensitive attributes
    attrs = span.get("attributes", {})
    for _attr_key in attrs:
        if _attr_key in SENSITIVE_ATTRIBUTES:
            score += 5.0

    # Check for attack patterns in attribute values
    for _attr_key, attr_val in attrs.items():
        val_str = str(attr_val).lower()
        for threat_name, patterns in ATTACK_PATTERNS:
            for pattern in patterns:
                if pattern in val_str:
                    score += 25.0
                    threats.append(threat_name)
                    break

    # Check for unusual duration (potential DoS)
    duration_ns = span.get("duration_ns", 0)
    if duration_ns > 10_000_000_000:  # > 10 seconds
        score += 15.0
        threats.append("long_duration")

    # Check for high fan-out (potential scanning)
    if span.get("span_kind") == "server" and attrs.get("http.method") == "GET":
        score += 5.0

    return min(score, 100.0), list(set(threats))


def enrich_span(span: dict[str, Any]) -> dict[str, Any]:
    """Enrich span with SOC context."""
    score, threats = compute_threat_score(span)
    span["soc"] = {
        "threat_score": score,
        "threats": threats,
        "enriched_at": datetime.now(UTC).isoformat(),
        "processor_version": "1.0.0",
        "retention_days": TRACE_RETENTION_DAYS,
    }
    # Generate a deterministic trace ID for correlation
    span["soc"]["trace_hash"] = hashlib.sha256(
        f"{span.get('trace_id', '')}:{span.get('span_id', '')}".encode()
    ).hexdigest()[:16]
    return span


def send_to_siem(spans: list[dict[str, Any]]) -> None:
    """Bulk-index enriched spans into Elasticsearch."""
    if not spans:
        return
    bulk_body = ""
    for span in spans:
        bulk_body += json.dumps({"index": {"_index": SIEM_INDEX}}) + "\n"
        bulk_body += json.dumps(span) + "\n"

    req = urllib.request.Request(
        f"{SIEM_URL}/_bulk",
        data=bulk_body.encode(),
        headers={"Content-Type": "application/x-ndjson"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            log.info(f"SIEM bulk index: {resp.status} ({len(spans)} spans)")
    except Exception as e:
        log.error(f"SIEM bulk index failed: {e}")


def send_alert(span: dict[str, Any]) -> None:
    """Send high-threat alert to webhook."""
    if not ALERT_WEBHOOK:
        return
    payload = {
        "alert_type": "soc_trace_threat",
        "severity": "critical" if span["soc"]["threat_score"] >= 70 else "warning",
        "threat_score": span["soc"]["threat_score"],
        "threats": span["soc"]["threats"],
        "trace_id": span.get("trace_id"),
        "span_id": span.get("span_id"),
        "service": span.get("service_name"),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    req = urllib.request.Request(
        ALERT_WEBHOOK,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            log.info(f"Alert sent: {resp.status}")
    except Exception as e:
        log.error(f"Alert failed: {e}")


class TraceHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler dispatches on this exact name
        if self.path != "/v1/traces":
            self.send_error(404)
            return
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        # Extract spans from OTLP JSON format
        spans: list[dict[str, Any]] = []
        for resource_span in data.get("resourceSpans", []):
            service_name = "unknown"
            for attr in resource_span.get("resource", {}).get("attributes", []):
                if attr.get("key") == "service.name":
                    service_name = attr.get("value", {}).get("stringValue", "unknown")
            for scope_span in resource_span.get("scopeSpans", []):
                for span in scope_span.get("spans", []):
                    span["service_name"] = service_name
                    # Convert OTLP trace/span IDs from bytes to hex
                    if "traceId" in span:
                        span["trace_id"] = span.pop("traceId")
                    if "spanId" in span:
                        span["span_id"] = span.pop("spanId")
                    # Convert attributes from OTLP format
                    attrs = {}
                    for attr in span.get("attributes", []):
                        key = attr.get("key", "")
                        val = attr.get("value", {})
                        attrs[key] = (
                            val.get("stringValue")
                            or val.get("intValue")
                            or val.get("boolValue")
                            or val.get("doubleValue")
                        )
                    span["attributes"] = attrs
                    # Convert timestamps
                    if "startTimeUnixNano" in span:
                        span["start_time"] = int(span.pop("startTimeUnixNano"))
                    if "endTimeUnixNano" in span:
                        span["end_time"] = int(span.pop("endTimeUnixNano"))
                    span["duration_ns"] = span.get("end_time", 0) - span.get("start_time", 0)
                    span["span_kind"] = span.get("kind", "internal")
                    spans.append(span)

        # Enrich and process
        enriched = []
        for span in spans:
            enriched_span = enrich_span(span)
            enriched.append(enriched_span)
            if enriched_span["soc"]["threat_score"] >= 50:
                send_alert(enriched_span)

        send_to_siem(enriched)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"processed": len(enriched)}).encode())

    def log_message(self, format: str, *args: Any) -> None:
        log.info(f"{self.address_string()} - {format % args}")


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), TraceHandler)
    log.info(f"SOC Trace Processor listening on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
