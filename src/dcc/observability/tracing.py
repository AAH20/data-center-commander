"""Distributed tracing engine for Data Center Commander.

Provides OpenTelemetry-compatible span tracking, context propagation,
and trace export. Self-contained with no external dependencies — uses
OTLP-compatible JSON format for interoperability.

Key concepts:
- Trace: A collection of spans forming a tree
- Span: A single operation within a trace (e.g., adapter call, computation)
- Context: Propagated trace_id/span_id across process boundaries
- Attributes: Key-value metadata on spans
- Events: Timestamped annotations within a span
"""
from __future__ import annotations

import contextvars
import functools
import hashlib
import json
import os
import random
import threading
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Iterator, TypeVar
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRACE_ID_LENGTH = 32  # 16 bytes hex
SPAN_ID_LENGTH = 16   # 8 bytes hex
DEFAULT_MAX_SPANS_PER_TRACE = 1000
DEFAULT_MAX_EVENTS_PER_SPAN = 100
DEFAULT_MAX_ATTRIBUTES_PER_SPAN = 32


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SpanKind(str, Enum):
    """The role of a span within a trace."""
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatusCode(str, Enum):
    """Status code for a span."""
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class SamplingDecision(str, Enum):
    """Sampling decision for a span."""
    DROP = "drop"
    RECORD_ONLY = "record_only"
    RECORD_AND_SAMPLE = "record_and_sample"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TraceFlags:
    """W3C Trace Context flags."""
    sampled: bool = False

    def to_int(self) -> int:
        return 0x01 if self.sampled else 0x00

    @classmethod
    def from_int(cls, value: int) -> TraceFlags:
        return cls(sampled=bool(value & 0x01))


@dataclass(frozen=True)
class TraceState:
    """W3C Trace State — vendor-specific key-value pairs."""
    entries: dict[str, str] = field(default_factory=dict)

    def to_header(self) -> str:
        return ",".join(f"{k}={v}" for k, v in self.entries.items())

    @classmethod
    def from_header(cls, header: str) -> TraceState:
        entries: dict[str, str] = {}
        for part in header.split(","):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                entries[k.strip()] = v.strip()
        return cls(entries=entries)


@dataclass(frozen=True)
class TraceContext:
    """W3C Trace Context — propagated across process boundaries."""
    trace_id: str
    span_id: str
    trace_flags: TraceFlags = field(default_factory=TraceFlags)
    trace_state: TraceState = field(default_factory=TraceState)

    def to_traceparent(self) -> str:
        """Serialize to W3C traceparent header format."""
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags.to_int():02x}"

    @classmethod
    def from_traceparent(cls, header: str) -> TraceContext | None:
        """Parse a W3C traceparent header."""
        parts = header.strip().split("-")
        if len(parts) != 4:
            return None
        version, trace_id, span_id, flags_hex = parts
        if version != "00":
            return None
        if len(trace_id) != TRACE_ID_LENGTH or len(span_id) != SPAN_ID_LENGTH:
            return None
        try:
            flags = TraceFlags.from_int(int(flags_hex, 16))
        except ValueError:
            return None
        return cls(trace_id=trace_id, span_id=span_id, trace_flags=flags)


@dataclass(frozen=True)
class SpanEvent:
    """A timestamped event within a span."""
    name: str
    timestamp_ns: int
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """A single operation within a trace."""
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    span_kind: SpanKind
    start_time_ns: int
    end_time_ns: int | None = None
    status_code: SpanStatusCode = SpanStatusCode.UNSET
    status_message: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[SpanEvent] = field(default_factory=list)
    tenant_id: str | None = None
    service_name: str = "data-center-commander"
    service_version: str = "0.1.0"

    @property
    def duration_ns(self) -> int | None:
        if self.end_time_ns is None:
            return None
        return self.end_time_ns - self.start_time_ns

    @property
    def duration_ms(self) -> float | None:
        d = self.duration_ns
        return d / 1_000_000 if d is not None else None

    @property
    def is_recording(self) -> bool:
        return self.end_time_ns is None

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the span."""
        if len(self.attributes) >= DEFAULT_MAX_ATTRIBUTES_PER_SPAN:
            return
        self.attributes[key] = _sanitize_attribute(value)

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add a timestamped event to the span."""
        if len(self.events) >= DEFAULT_MAX_EVENTS_PER_SPAN:
            return
        self.events.append(SpanEvent(
            name=name,
            timestamp_ns=time.time_ns(),
            attributes={k: _sanitize_attribute(v) for k, v in (attributes or {}).items()},
        ))

    def set_status(self, code: SpanStatusCode, message: str = "") -> None:
        """Set the span status."""
        self.status_code = code
        self.status_message = message

    def record_exception(self, exc: BaseException) -> None:
        """Record an exception as span attributes and event."""
        self.set_attribute("exception.type", type(exc).__name__)
        self.set_attribute("exception.message", str(exc))
        self.set_attribute("exception.stacktrace", traceback.format_exc())
        self.add_event("exception", {
            "exception.type": type(exc).__name__,
            "exception.message": str(exc),
        })
        self.set_status(SpanStatusCode.ERROR, str(exc))

    def to_dict(self) -> dict[str, Any]:
        """Convert span to a dictionary (OTLP-compatible)."""
        return {
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "parentSpanId": self.parent_span_id,
            "name": self.name,
            "kind": self.span_kind.value,
            "startTimeUnixNano": str(self.start_time_ns),
            "endTimeUnixNano": str(self.end_time_ns) if self.end_time_ns else None,
            "status": {
                "code": self.status_code.value,
                "message": self.status_message,
            },
            "attributes": _attributes_to_otlp(self.attributes),
            "events": [
                {
                    "name": e.name,
                    "timeUnixNano": str(e.timestamp_ns),
                    "attributes": _attributes_to_otlp(e.attributes),
                }
                for e in self.events
            ],
            "tenantId": self.tenant_id,
            "serviceName": self.service_name,
            "serviceVersion": self.service_version,
        }


@dataclass
class Trace:
    """A collection of spans forming a tree."""
    trace_id: str
    spans: list[Span] = field(default_factory=list)
    root_span_id: str | None = None

    @property
    def root_span(self) -> Span | None:
        for span in self.spans:
            if span.span_id == self.root_span_id:
                return span
        return None

    @property
    def duration_ms(self) -> float | None:
        root = self.root_span
        if root is None:
            return None
        return root.duration_ms

    @property
    def span_count(self) -> int:
        return len(self.spans)

    @property
    def error_count(self) -> int:
        return sum(1 for s in self.spans if s.status_code == SpanStatusCode.ERROR)

    @property
    def services(self) -> set[str]:
        return {s.service_name for s in self.spans}

    def to_dict(self) -> dict[str, Any]:
        """Convert trace to a dictionary."""
        return {
            "traceId": self.trace_id,
            "rootSpanId": self.root_span_id,
            "spanCount": self.span_count,
            "errorCount": self.error_count,
            "durationMs": self.duration_ms,
            "services": sorted(self.services),
            "spans": [s.to_dict() for s in self.spans],
        }


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def _generate_trace_id() -> str:
    """Generate a random 128-bit trace ID as hex."""
    return hashlib.sha256(os.urandom(16) + str(time.time_ns()).encode()).hexdigest()[:TRACE_ID_LENGTH]


def _generate_span_id() -> str:
    """Generate a random 64-bit span ID as hex."""
    return hashlib.sha256(os.urandom(8) + str(time.time_ns()).encode()).hexdigest()[:SPAN_ID_LENGTH]


# ---------------------------------------------------------------------------
# Attribute sanitization
# ---------------------------------------------------------------------------

def _sanitize_attribute(value: Any) -> Any:
    """Sanitize an attribute value for storage."""
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, float):
            if value != value or value in (float("inf"), float("-inf")):
                return str(value)
        return value
    if isinstance(value, (list, tuple)):
        return [_sanitize_attribute(v) for v in value[:100]]
    return str(value)


def _attributes_to_otlp(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert attributes dict to OTLP KeyValue list format."""
    result: list[dict[str, Any]] = []
    for key, value in attrs.items():
        kv: dict[str, Any] = {"key": key}
        if isinstance(value, bool):
            kv["value"] = {"boolValue": value}
        elif isinstance(value, int):
            kv["value"] = {"intValue": str(value)}
        elif isinstance(value, float):
            kv["value"] = {"doubleValue": value}
        else:
            kv["value"] = {"stringValue": str(value)}
        result.append(kv)
    return result


# ---------------------------------------------------------------------------
# Context propagation
# ---------------------------------------------------------------------------

_current_span: contextvars.ContextVar[Span | None] = contextvars.ContextVar(
    "dcc_current_span", default=None
)
_current_trace_context: contextvars.ContextVar[TraceContext | None] = contextvars.ContextVar(
    "dcc_current_trace_context", default=None
)


def get_current_span() -> Span | None:
    """Get the current span from context."""
    return _current_span.get()


def get_current_trace_context() -> TraceContext | None:
    """Get the current trace context from context."""
    return _current_trace_context.get()


def set_current_span(span: Span | None) -> None:
    """Set the current span in context."""
    _current_span.set(span)


def set_current_trace_context(ctx: TraceContext | None) -> None:
    """Set the current trace context in context."""
    _current_trace_context.set(ctx)


# ---------------------------------------------------------------------------
# Sampler
# ---------------------------------------------------------------------------

class Sampler:
    """Determines whether a span should be recorded."""

    def __init__(self, rate: float = 1.0) -> None:
        if not 0.0 <= rate <= 1.0:
            raise ValueError("rate must be between 0.0 and 1.0")
        self._rate = rate

    def should_sample(self, trace_id: str) -> SamplingDecision:
        """Decide whether to sample based on trace ID."""
        if self._rate >= 1.0:
            return SamplingDecision.RECORD_AND_SAMPLE
        if self._rate <= 0.0:
            return SamplingDecision.DROP
        # Deterministic sampling based on trace ID
        hash_val = int(hashlib.sha256(trace_id.encode()).hexdigest()[:8], 16)
        if hash_val / 0xFFFFFFFF <= self._rate:
            return SamplingDecision.RECORD_AND_SAMPLE
        return SamplingDecision.DROP


# ---------------------------------------------------------------------------
# Span processor
# ---------------------------------------------------------------------------

class SpanProcessor:
    """Processes spans when they end."""

    def on_start(self, span: Span) -> None:
        """Called when a span starts."""

    def on_end(self, span: Span) -> None:
        """Called when a span ends."""

    def shutdown(self) -> None:
        """Shutdown the processor."""

    def force_flush(self) -> None:
        """Force flush any buffered spans."""


class InMemorySpanProcessor(SpanProcessor):
    """Stores spans in memory for later retrieval."""

    def __init__(self, max_spans: int = 10_000) -> None:
        self._spans: dict[str, Span] = {}
        self._max_spans = max_spans
        self._lock = threading.Lock()

    def on_end(self, span: Span) -> None:
        with self._lock:
            if len(self._spans) >= self._max_spans:
                # Evict oldest ended spans
                ended = [s for s in self._spans.values() if s.end_time_ns is not None]
                if ended:
                    oldest = min(ended, key=lambda s: s.end_time_ns or 0)
                    del self._spans[oldest.span_id]
            self._spans[span.span_id] = span

    def get_span(self, span_id: str) -> Span | None:
        with self._lock:
            return self._spans.get(span_id)

    def get_spans_by_trace(self, trace_id: str) -> list[Span]:
        with self._lock:
            return [s for s in self._spans.values() if s.trace_id == trace_id]

    def get_all_spans(self) -> list[Span]:
        with self._lock:
            return list(self._spans.values())

    def clear(self) -> None:
        with self._lock:
            self._spans.clear()

    @property
    def span_count(self) -> int:
        with self._lock:
            return len(self._spans)


class CompositeSpanProcessor(SpanProcessor):
    """Delegates to multiple processors."""

    def __init__(self, processors: list[SpanProcessor]) -> None:
        self._processors = processors

    def on_start(self, span: Span) -> None:
        for p in self._processors:
            p.on_start(span)

    def on_end(self, span: Span) -> None:
        for p in self._processors:
            p.on_end(span)

    def shutdown(self) -> None:
        for p in self._processors:
            p.shutdown()

    def force_flush(self) -> None:
        for p in self._processors:
            p.force_flush()


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------

class Tracer:
    """Creates and manages spans within a trace."""

    def __init__(
        self,
        service_name: str = "data-center-commander",
        service_version: str = "0.1.0",
        sampler: Sampler | None = None,
        processor: SpanProcessor | None = None,
    ) -> None:
        self._service_name = service_name
        self._service_version = service_version
        self._sampler = sampler or Sampler()
        self._processor = processor or InMemorySpanProcessor()

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def service_version(self) -> str:
        return self._service_version

    @property
    def processor(self) -> SpanProcessor:
        return self._processor

    def start_span(
        self,
        name: str,
        *,
        span_kind: SpanKind = SpanKind.INTERNAL,
        parent_context: TraceContext | None = None,
        attributes: dict[str, Any] | None = None,
        tenant_id: str | None = None,
        start_time_ns: int | None = None,
    ) -> Span:
        """Start a new span."""
        # Determine parent context
        if parent_context is None:
            parent_context = _current_trace_context.get()

        # Generate or inherit trace ID
        if parent_context:
            trace_id = parent_context.trace_id
            parent_span_id = parent_context.span_id
        else:
            trace_id = _generate_trace_id()
            parent_span_id = None

        span_id = _generate_span_id()
        start_ns = start_time_ns or time.time_ns()

        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            span_kind=span_kind,
            start_time_ns=start_ns,
            attributes=dict(attributes or {}),
            tenant_id=tenant_id,
            service_name=self._service_name,
            service_version=self._service_version,
        )

        self._processor.on_start(span)
        return span

    def start_as_current_span(
        self,
        name: str,
        *,
        span_kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> SpanContextManager:
        """Start a span and set it as the current span in context."""
        span = self.start_span(
            name,
            span_kind=span_kind,
            attributes=attributes,
            tenant_id=tenant_id,
        )
        return SpanContextManager(span, self._processor)

    def shutdown(self) -> None:
        self._processor.shutdown()

    def force_flush(self) -> None:
        self._processor.force_flush()


class SpanContextManager:
    """Context manager for a span — sets it as current and ends on exit."""

    def __init__(self, span: Span, processor: SpanProcessor) -> None:
        self._span = span
        self._processor = processor
        self._token: contextvars.Token | None = None
        self._trace_token: contextvars.Token | None = None

    def __enter__(self) -> Span:
        self._token = _current_span.set(self._span)
        self._trace_token = _current_trace_context.set(TraceContext(
            trace_id=self._span.trace_id,
            span_id=self._span.span_id,
            trace_flags=TraceFlags(sampled=True),
        ))
        return self._span

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_val is not None:
            self._span.record_exception(exc_val)
        self._span.end_time_ns = time.time_ns()
        self._processor.on_end(self._span)
        if self._token is not None:
            _current_span.reset(self._token)
        if self._trace_token is not None:
            _current_trace_context.reset(self._trace_token)


# ---------------------------------------------------------------------------
# Tracer provider (global access)
# ---------------------------------------------------------------------------

class TracerProvider:
    """Provides access to tracers and manages global tracing state."""

    _instance: TracerProvider | None = None
    _lock = threading.Lock()

    def __new__(cls) -> TracerProvider:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._tracers: dict[str, Tracer] = {}
        self._sampler = Sampler()
        self._processor: SpanProcessor = InMemorySpanProcessor()
        self._initialized = True

    def get_tracer(
        self,
        service_name: str = "data-center-commander",
        service_version: str = "0.1.0",
    ) -> Tracer:
        """Get or create a tracer for a service."""
        key = f"{service_name}:{service_version}"
        if key not in self._tracers:
            self._tracers[key] = Tracer(
                service_name=service_name,
                service_version=service_version,
                sampler=self._sampler,
                processor=self._processor,
            )
        return self._tracers[key]

    def set_sampler(self, sampler: Sampler) -> None:
        """Set the global sampler."""
        self._sampler = sampler

    def set_processor(self, processor: SpanProcessor) -> None:
        """Set the global span processor."""
        self._processor = processor

    def shutdown(self) -> None:
        """Shutdown all tracers."""
        for tracer in self._tracers.values():
            tracer.shutdown()
        self._tracers.clear()

    def force_flush(self) -> None:
        """Force flush all tracers."""
        for tracer in self._tracers.values():
            tracer.force_flush()

    @property
    def processor(self) -> SpanProcessor:
        return self._processor


def get_tracer(
    service_name: str = "data-center-commander",
    service_version: str = "0.1.0",
) -> Tracer:
    """Get a tracer from the global provider."""
    return TracerProvider().get_tracer(service_name, service_version)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

F = TypeVar("F", bound=Callable[..., Any])


def trace(
    name: str | None = None,
    *,
    span_kind: SpanKind = SpanKind.INTERNAL,
    attributes: dict[str, Any] | None = None,
    tenant_id: str | None = None,
) -> Callable[[F], F]:
    """Decorator to automatically trace a function call."""
    def decorator(func: F) -> F:
        span_name = name or func.__qualname__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_as_current_span(
                span_name,
                span_kind=span_kind,
                attributes=attributes,
                tenant_id=tenant_id,
            ) as span:
                # Add function metadata
                span.set_attribute("code.function", func.__qualname__)
                span.set_attribute("code.namespace", func.__module__)
                try:
                    result = func(*args, **kwargs)
                    span.set_status(SpanStatusCode.OK)
                    return result
                except Exception as exc:
                    span.record_exception(exc)
                    raise

        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# Trace retrieval and export
# ---------------------------------------------------------------------------

class TraceStore:
    """In-memory store for completed traces."""

    def __init__(self, max_traces: int = 1_000) -> None:
        self._traces: dict[str, Trace] = {}
        self._max_traces = max_traces
        self._lock = threading.Lock()

    def add_span(self, span: Span) -> None:
        """Add a span to the store, grouping by trace ID."""
        with self._lock:
            trace = self._traces.get(span.trace_id)
            if trace is None:
                if len(self._traces) >= self._max_traces:
                    # Evict oldest trace
                    oldest_id = min(
                        self._traces.keys(),
                        key=lambda tid: min(s.start_time_ns for s in self._traces[tid].spans),
                    )
                    del self._traces[oldest_id]
                trace = Trace(trace_id=span.trace_id)
                self._traces[span.trace_id] = trace

            trace.spans.append(span)
            if span.parent_span_id is None:
                trace.root_span_id = span.span_id

    def get_trace(self, trace_id: str) -> Trace | None:
        with self._lock:
            return self._traces.get(trace_id)

    def get_all_traces(self) -> list[Trace]:
        with self._lock:
            return list(self._traces.values())

    def clear(self) -> None:
        with self._lock:
            self._traces.clear()

    @property
    def trace_count(self) -> int:
        with self._lock:
            return len(self._traces)

    def to_otlp_json(self) -> str:
        """Export all traces as OTLP-compatible JSON."""
        with self._lock:
            traces_data = []
            for trace in self._traces.values():
                spans_by_service: dict[str, list[Span]] = {}
                for span in trace.spans:
                    svc = span.service_name
                    spans_by_service.setdefault(svc, []).append(span)

                resource_spans: list[dict[str, Any]] = []
                for svc_name, spans in spans_by_service.items():
                    resource_spans.append({
                        "resource": {
                            "attributes": [
                                {"key": "service.name", "value": {"stringValue": svc_name}},
                                {"key": "service.version", "value": {"stringValue": spans[0].service_version}},
                            ]
                        },
                        "scopeSpans": [
                            {
                                "scope": {"name": "data-center-commander", "version": "0.1.0"},
                                "spans": [s.to_dict() for s in spans],
                            }
                        ],
                    })

                traces_data.append({"resourceSpans": resource_spans})

            return json.dumps(
                {"resourceSpans": [rs for t in traces_data for rs in t["resourceSpans"]]},
                indent=2,
            )


class TraceStoreSpanProcessor(SpanProcessor):
    """Span processor that stores spans in a TraceStore."""

    def __init__(self, store: TraceStore) -> None:
        self._store = store

    def on_end(self, span: Span) -> None:
        self._store.add_span(span)


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

@contextmanager
def span(
    name: str,
    *,
    span_kind: SpanKind = SpanKind.INTERNAL,
    attributes: dict[str, Any] | None = None,
    tenant_id: str | None = None,
) -> Iterator[Span]:
    """Context manager for creating a span."""
    tracer = get_tracer()
    with tracer.start_as_current_span(
        name,
        span_kind=span_kind,
        attributes=attributes,
        tenant_id=tenant_id,
    ) as s:
        yield s


def inject_context(headers: dict[str, str]) -> None:
    """Inject trace context into HTTP headers (W3C Trace Context)."""
    ctx = _current_trace_context.get()
    if ctx:
        headers["traceparent"] = ctx.to_traceparent()
        if ctx.trace_state.entries:
            headers["tracestate"] = ctx.trace_state.to_header()


def extract_context(headers: dict[str, str]) -> TraceContext | None:
    """Extract trace context from HTTP headers."""
    traceparent = headers.get("traceparent") or headers.get("Traceparent")
    if not traceparent:
        return None
    ctx = TraceContext.from_traceparent(traceparent)
    if ctx is None:
        return None
    tracestate = headers.get("tracestate") or headers.get("Tracestate")
    if tracestate:
        return TraceContext(
            trace_id=ctx.trace_id,
            span_id=ctx.span_id,
            trace_flags=ctx.trace_flags,
            trace_state=TraceState.from_header(tracestate),
        )
    return ctx


def create_trace_from_context(
    ctx: TraceContext,
    name: str,
    *,
    span_kind: SpanKind = SpanKind.INTERNAL,
    attributes: dict[str, Any] | None = None,
    tenant_id: str | None = None,
) -> Span:
    """Create a new span continuing a remote trace context."""
    tracer = get_tracer()
    return tracer.start_span(
        name,
        span_kind=span_kind,
        parent_context=ctx,
        attributes=attributes,
        tenant_id=tenant_id,
    )


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    # Enums
    "SpanKind",
    "SpanStatusCode",
    "SamplingDecision",
    # Data models
    "TraceFlags",
    "TraceState",
    "TraceContext",
    "SpanEvent",
    "Span",
    "Trace",
    # Context
    "get_current_span",
    "get_current_trace_context",
    "set_current_span",
    "set_current_trace_context",
    # Sampling
    "Sampler",
    # Processing
    "SpanProcessor",
    "InMemorySpanProcessor",
    "CompositeSpanProcessor",
    # Tracing
    "Tracer",
    "TracerProvider",
    "get_tracer",
    "SpanContextManager",
    # Decorator
    "trace",
    # Store
    "TraceStore",
    "TraceStoreSpanProcessor",
    # Convenience
    "span",
    "inject_context",
    "extract_context",
    "create_trace_from_context",
]
