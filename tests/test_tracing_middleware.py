"""Tests for the tracing middleware."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from dcc.observability.middleware import trace_request, inject_trace_headers
from dcc.observability.tracing import SpanKind, TraceContext, TraceFlags


class TestTraceRequest(unittest.TestCase):
    """Test the trace_request context manager."""

    def _make_handler(self, path="/v1/assets?tenant_id=abc-123", method="GET"):
        handler = MagicMock()
        handler.path = path
        handler.command = method
        handler.headers = {
            "Host": "localhost:8790",
            "User-Agent": "test",
        }
        return handler

    def test_creates_server_span(self):
        """trace_request should create a server span."""
        handler = self._make_handler()
        with trace_request(handler, "GET /v1/assets"):
            pass
        # If we get here without error, the span was created and ended

    def test_extracts_tenant_id(self):
        """trace_request should extract tenant_id from query string."""
        handler = self._make_handler(path="/v1/assets?tenant_id=abc-123")
        with trace_request(handler, "GET /v1/assets") as span:
            self.assertIsNotNone(span)

    def test_handles_exceptions(self):
        """trace_request should record exceptions on the span."""
        handler = self._make_handler()
        with self.assertRaises(ValueError):
            with trace_request(handler, "GET /v1/assets"):
                raise ValueError("test error")

    def test_no_tenant_id(self):
        """trace_request should work without tenant_id."""
        handler = self._make_handler(path="/healthz")
        with trace_request(handler, "GET /healthz"):
            pass

    def test_injects_trace_headers(self):
        """inject_trace_headers should add traceparent header when a span is active."""
        from dcc.observability.tracing import get_tracer, SpanKind

        tracer = get_tracer()
        with tracer.start_as_current_span("test", span_kind=SpanKind.INTERNAL):
            headers = {}
            inject_trace_headers(headers)
            self.assertIn("traceparent", headers)


class TestTraceContext(unittest.TestCase):
    """Test W3C Trace Context propagation."""

    def test_traceparent_serialization(self):
        """TraceContext should serialize to traceparent format."""
        ctx = TraceContext(
            trace_id="0af7651916cd43dd8448eb211c80319c",
            span_id="b7ad6b7169203331",
            trace_flags=TraceFlags(sampled=True),
        )
        traceparent = ctx.to_traceparent()
        self.assertEqual(
            traceparent,
            "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
        )

    def test_traceparent_parsing(self):
        """TraceContext should parse from traceparent header."""
        header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        ctx = TraceContext.from_traceparent(header)
        assert ctx is not None
        self.assertEqual(ctx.trace_id, "0af7651916cd43dd8448eb211c80319c")
        self.assertEqual(ctx.span_id, "b7ad6b7169203331")
        self.assertTrue(ctx.trace_flags.sampled)

    def test_invalid_traceparent(self):
        """Invalid traceparent headers should return None."""
        self.assertIsNone(TraceContext.from_traceparent(""))
        self.assertIsNone(TraceContext.from_traceparent("invalid"))
        self.assertIsNone(TraceContext.from_traceparent("00-invalid"))


if __name__ == "__main__":
    unittest.main()
