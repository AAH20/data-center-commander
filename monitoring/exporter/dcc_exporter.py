#!/usr/bin/env python3
"""
Prometheus exporter for Data Center Commander.

Polls the DCC API health/readiness endpoints and exposes metrics
in Prometheus text format on port 8000.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

DCC_API_URL = os.environ.get("DCC_API_URL", "http://host.docker.internal:8790")
DCC_TENANT_ID = os.environ.get("DCC_TENANT_ID", "dcc00000-0000-4000-8000-000000000001")
EXPORTER_PORT = int(os.environ.get("EXPORTER_PORT", "8000"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "15"))

# Metric storage
_metrics: dict[str, float] = {}
_last_poll_time: float = 0.0


def fetch_json(url: str, timeout: int = 5) -> dict | None:
    """Fetch JSON from a URL, returning None on any error."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        return None


def poll_dcc_api() -> None:
    """Poll DCC API and update metrics."""
    global _last_poll_time

    # Health check
    health_url = f"{DCC_API_URL}/healthz"
    health_data = fetch_json(health_url)
    if health_data is not None:
        _metrics["dcc_api_healthy"] = 1.0
        _metrics["dcc_api_mode"] = 1.0 if health_data.get("mode") == "read_only" else 0.0
    else:
        _metrics["dcc_api_healthy"] = 0.0
        _metrics["dcc_api_mode"] = 0.0

    # Readiness check
    ready_url = f"{DCC_API_URL}/readyz"
    ready_data = fetch_json(ready_url)
    if ready_data is not None:
        _metrics["dcc_database_ready"] = 1.0 if ready_data.get("ready") else 0.0
        checks = ready_data.get("checks", {})
        _metrics["dcc_database_schema_ok"] = 1.0 if checks.get("schema") == "ok" else 0.0
        _metrics["dcc_database_rls_ok"] = 1.0 if checks.get("tenant_rls") == "ok" else 0.0
    else:
        _metrics["dcc_database_ready"] = 0.0
        _metrics["dcc_database_schema_ok"] = 0.0
        _metrics["dcc_database_rls_ok"] = 0.0

    # Overview metrics
    overview_url = f"{DCC_API_URL}/v1/overview?tenant_id={DCC_TENANT_ID}"
    overview_data = fetch_json(overview_url)
    if overview_data is not None:
        _metrics["dcc_facility_count"] = float(overview_data.get("facility_count", 0))
        _metrics["dcc_open_workflows"] = float(overview_data.get("open_workflows", 0))
        _metrics["dcc_kpi_count"] = float(len(overview_data.get("kpis", [])))

        latest = overview_data.get("latest_telemetry_ingested_at")
        if latest:
            try:
                from datetime import datetime, timezone
                ts = datetime.fromisoformat(latest.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - ts).total_seconds()
                _metrics["dcc_latest_telemetry_age_seconds"] = age
            except (ValueError, TypeError):
                _metrics["dcc_latest_telemetry_age_seconds"] = -1.0
        else:
            _metrics["dcc_latest_telemetry_age_seconds"] = -1.0
    else:
        _metrics["dcc_facility_count"] = 0.0
        _metrics["dcc_open_workflows"] = 0.0
        _metrics["dcc_kpi_count"] = 0.0
        _metrics["dcc_latest_telemetry_age_seconds"] = -1.0

    _last_poll_time = time.time()


def metrics_poller() -> None:
    """Background thread that polls the DCC API periodically."""
    while True:
        try:
            poll_dcc_api()
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)


def render_metrics() -> str:
    """Render metrics in Prometheus text exposition format."""
    lines = []
    for name, value in sorted(_metrics.items()):
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name} {value}")
    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for /metrics endpoint."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/metrics":
            body = render_metrics().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/health":
            body = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:
        pass


def main() -> None:
    """Start the exporter."""
    # Initial poll
    poll_dcc_api()

    # Start background poller
    poller = Thread(target=metrics_poller, daemon=True)
    poller.start()

    # Start HTTP server
    server = HTTPServer(("0.0.0.0", EXPORTER_PORT), MetricsHandler)
    print(f"DCC Prometheus exporter listening on :{EXPORTER_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
