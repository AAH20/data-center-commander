"""HTTP request tracing middleware for Data Center Commander.

Wraps request handling to automatically create spans for each incoming
HTTP request, enriching them with tenant, correlation, and timing info.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler
from typing import Any, Iterator
from urllib.parse import parse_qs, urlsplit

from .logging import bind_context, clear_context, get_logger
from .tracing import SpanKind, extract_context, get_tracer, inject_context

_logger = get_logger("dcc.observability.middleware")


@contextmanager
def trace_request(handler: BaseHTTPRequestHandler, operation: str) -> Iterator[None]:
    """Context manager that creates a server span for an HTTP request.

    Usage:
        with trace_request(self, "GET /v1/assets"):
            # ... handle request ...
    """
    tracer = get_tracer()
    start_ns = time.time_ns()

    # Extract incoming trace context for distributed tracing
    headers = {k.lower(): v for k, v in handler.headers.items()}
    parent_ctx = extract_context(headers)

    # Start server span
    span = tracer.start_span(
        operation,
        span_kind=SpanKind.SERVER,
        parent_context=parent_ctx,
        attributes={
            "http.method": handler.command,
            "http.target": handler.path,
            "http.host": handler.headers.get("Host", "unknown"),
            "http.scheme": "http",
            "http.user_agent": handler.headers.get("User-Agent", "unknown"),
        },
    )

    # Extract and bind tenant context
    token = None
    try:
        path = urlsplit(handler.path)
        query = parse_qs(path.query, keep_blank_values=True)
        tenant_values = query.get("tenant_id", [])
        if tenant_values:
            tenant_id = tenant_values[0]
            span.set_attribute("tenant.id", tenant_id)
            token = bind_context(tenant_id=tenant_id)
    except Exception:
        pass

    try:
        yield
    except Exception as exc:
        span.record_exception(exc)
        raise
    finally:
        span.end_time_ns = time.time_ns()
        if token is not None:
            try:
                clear_context(token)
            except Exception:
                pass


def inject_trace_headers(headers: dict[str, str]) -> dict[str, str]:
    """Inject current trace context into HTTP headers for downstream calls."""
    inject_context(headers)
    return headers
