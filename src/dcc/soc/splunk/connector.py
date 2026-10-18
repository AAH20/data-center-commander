"""Splunk HTTP Event Collector (HEC) data connector.

Sends DCC security audit events, alert events, and operational metrics
to Splunk via the HEC REST API. Supports batching, retry with backoff,
and index routing.

Usage:
    from dcc.soc.splunk import create_splunk_connector

    connector = create_splunk_connector(
        hec_url="https://splunk.example.com:8088",
        hec_token="your-token-here",
        index="dcc_security",
    )
    connector.send_event({"event": "login_failure", "user": "admin"})
    connector.flush()
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
from uuid import uuid4


class SplunkIndex(str, Enum):
    """Standard Splunk indexes for DCC data."""
    SECURITY = "dcc_security"
    AUDIT = "dcc_audit"
    ALERTS = "dcc_alerts"
    METRICS = "dcc_metrics"
    OPERATIONS = "dcc_operations"


@dataclass
class SplunkHECConfig:
    """Configuration for Splunk HEC connector.

    Attributes:
        hec_url: Splunk HEC endpoint URL (e.g., https://host:8088).
        hec_token: HEC authentication token.
        index: Target Splunk index.
        source: Source field value (default: "dcc").
        sourcetype: Sourcetype field value (default, "dcc:json").
        verify_tls: Whether to verify TLS certificates (default: True).
        timeout_seconds: HTTP timeout in seconds (default: 10).
        max_batch_size: Max events per batch (default: 100).
        max_queue_size: Max queued events before dropping (default: 10000).
        flush_interval_seconds: Auto-flush interval (default: 5.0).
        max_retries: Max retry attempts per batch (default: 3).
        retry_backoff_base: Base seconds for exponential backoff (default: 1.0).
    """
    hec_url: str
    hec_token: str
    index: str = SplunkIndex.SECURITY.value
    source: str = "dcc"
    sourcetype: str = "dcc:json"
    verify_tls: bool = True
    timeout_seconds: float = 10.0
    max_batch_size: int = 100
    max_queue_size: int = 10000
    flush_interval_seconds: float = 5.0
    max_retries: int = 3
    retry_backoff_base: float = 1.0

    def __post_init__(self) -> None:
        if not self.hec_url:
            raise ValueError("hec_url is required")
        if not self.hec_token:
            raise ValueError("hec_token is required")
        if self.max_batch_size < 1:
            raise ValueError("max_batch_size must be >= 1")
        if self.max_queue_size < 1:
            raise ValueError("max_queue_size must be >= 1")


@dataclass
class SplunkHECResponse:
    """Response from Splunk HEC."""
    success: bool
    status_code: int
    text: str
    batch_id: str
    events_sent: int
    error: str | None = None


class SplunkHECError(Exception):
    """Raised when Splunk HEC communication fails."""
    def __init__(self, message: str, response: SplunkHECResponse | None = None):
        super().__init__(message)
        self.response = response


class SplunkHECConnector:
    """Thread-safe Splunk HEC connector with batching and retry.

    Events are queued and sent in batches. Failed batches are retried
    with exponential backoff. Events that exhaust retries are dropped
    and counted in the dead-letter counter.
    """

    def __init__(self, config: SplunkHECConfig):
        self._config = config
        self._queue: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._flush_timer: threading.Timer | None = None
        self._shutdown = False
        self._total_sent = 0
        self._total_dropped = 0
        self._total_errors = 0
        self._start_flush_timer()

    @property
    def config(self) -> SplunkHECConfig:
        return self._config

    @property
    def queue_size(self) -> int:
        with self._lock:
            return len(self._queue)

    @property
    def total_sent(self) -> int:
        return self._total_sent

    @property
    def total_dropped(self) -> int:
        return self._total_dropped

    @property
    def total_errors(self) -> int:
        return self._total_errors

    def send_event(self, event: dict[str, Any]) -> None:
        """Queue a single event for delivery to Splunk.

        The event dict is wrapped with Splunk metadata (time, source,
        sourcetype, index) before being queued.
        """
        if self._shutdown:
            raise SplunkHECError("connector is shut down")

        enriched = {
            "time": time.time(),
            "source": self._config.source,
            "sourcetype": self._config.sourcetype,
            "index": self._config.index,
            "event": event,
        }

        with self._lock:
            if len(self._queue) >= self._config.max_queue_size:
                self._total_dropped += 1
                return
            self._queue.append(enriched)

    def send_events(self, events: list[dict[str, Any]]) -> None:
        """Queue multiple events for delivery."""
        for event in events:
            self.send_event(event)

    def flush(self) -> SplunkHECResponse:
        """Flush all queued events to Splunk immediately.

        Returns a summary response with counts of sent/failed events.
        """
        with self._lock:
            if not self._queue:
                return SplunkHECResponse(
                    success=True,
                    status_code=200,
                    text="",
                    batch_id=str(uuid4()),
                    events_sent=0,
                )
            batch = self._queue[: self._config.max_batch_size]
            self._queue = self._queue[self._config.max_batch_size :]

        return self._send_batch(batch)

    def _send_batch(self, batch: list[dict[str, Any]]) -> SplunkHECResponse:
        """Send a batch of events to Splunk HEC with retry."""
        batch_id = str(uuid4())
        payload = json.dumps(batch).encode("utf-8")
        url = f"{self._config.hec_url}/services/collector/event"

        last_error: str | None = None
        for attempt in range(self._config.max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={
                        "Authorization": f"Splunk {self._config.hec_token}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                ctx = None
                if not self._config.verify_tls:
                    import ssl
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE

                with urllib.request.urlopen(
                    req, timeout=self._config.timeout_seconds, context=ctx
                ) as resp:
                    body = resp.read().decode("utf-8")
                    self._total_sent += len(batch)
                    return SplunkHECResponse(
                        success=True,
                        status_code=resp.status,
                        text=body,
                        batch_id=batch_id,
                        events_sent=len(batch),
                    )
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}"
                self._total_errors += 1
                if e.code in (400, 401, 403, 404):
                    break
            except (urllib.error.URLError, OSError) as e:
                last_error = str(e)
                self._total_errors += 1

            if attempt < self._config.max_retries - 1:
                delay = self._config.retry_backoff_base * (2**attempt)
                time.sleep(delay)

        self._total_dropped += len(batch)
        return SplunkHECResponse(
            success=False,
            status_code=0,
            text="",
            batch_id=batch_id,
            events_sent=0,
            error=last_error,
        )

    def _start_flush_timer(self) -> None:
        """Start the periodic flush timer."""
        if self._shutdown:
            return
        self._flush_timer = threading.Timer(
            self._config.flush_interval_seconds, self._timed_flush
        )
        self._flush_timer.daemon = True
        self._flush_timer.start()

    def _timed_flush(self) -> None:
        """Callback for the periodic flush timer."""
        if not self._shutdown:
            try:
                self.flush()
            except Exception:
                pass
            self._start_flush_timer()

    def shutdown(self) -> None:
        """Shut down the connector, flushing remaining events."""
        self._shutdown = True
        if self._flush_timer:
            self._flush_timer.cancel()
        try:
            self.flush()
        except Exception:
            pass

    def __enter__(self) -> SplunkHECConnector:
        return self

    def __exit__(self, *args: Any) -> None:
        self.shutdown()


def create_splunk_connector(
    hec_url: str,
    hec_token: str,
    index: str = SplunkIndex.SECURITY.value,
    **kwargs: Any,
) -> SplunkHECConnector:
    """Factory function to create a Splunk HEC connector.

    Args:
        hec_url: Splunk HEC endpoint URL.
        hec_token: HEC authentication token.
        index: Target Splunk index.
        **kwargs: Additional config overrides.

    Returns:
        Configured SplunkHECConnector instance.
    """
    config = SplunkHECConfig(
        hec_url=hec_url,
        hec_token=hec_token,
        index=index,
        **kwargs,
    )
    return SplunkHECConnector(config)
