"""Structured logging engine for Data Center Commander.

Provides JSON-formatted logs with correlation IDs, configurable log levels,
and context binding. All log output is structured (key-value pairs) for
machine readability and easy ingestion by log aggregation systems.

Usage:
    from dcc.observability import get_logger, configure_logging, bind_context

    configure_logging(level="INFO")
    logger = get_logger("dcc.api")

    with bind_context(tenant_id="abc-123", request_id="req-456"):
        logger.info("request_started", path="/v1/assets", method="GET")
        logger.info("request_completed", status=200, duration_ms=42)
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
import threading
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, TextIO


# ---------------------------------------------------------------------------
# Log levels
# ---------------------------------------------------------------------------

class LogLevel(str, Enum):
    """Standard log levels with numeric values matching Python's logging module."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @property
    def numeric(self) -> int:
        """Return the numeric level matching Python's logging module."""
        return {
            LogLevel.DEBUG: 10,
            LogLevel.INFO: 20,
            LogLevel.WARNING: 30,
            LogLevel.ERROR: 40,
            LogLevel.CRITICAL: 50,
        }[self]

    @classmethod
    def from_string(cls, value: str) -> LogLevel:
        """Parse a log level from a string (case-insensitive)."""
        try:
            return cls(value.upper())
        except ValueError:
            raise ValueError(
                f"Invalid log level: {value!r}. "
                f"Valid levels: {', '.join(l.value for l in cls)}"
            ) from None


# ---------------------------------------------------------------------------
# Correlation ID context
# ---------------------------------------------------------------------------

_correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "dcc_correlation_id", default=None
)
_tenant_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "dcc_tenant_id", default=None
)
_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "dcc_request_id", default=None
)
_extra_context_var: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "dcc_extra_context", default={}
)


def correlation_id() -> str | None:
    """Get the current correlation ID from context, if any."""
    return _correlation_id_var.get()


def bind_context(
    *,
    correlation_id: str | None = None,
    tenant_id: str | None = None,
    request_id: str | None = None,
    **extra: Any,
) -> Any:
    """Bind context variables for structured logging.

    Returns a token that can be passed to clear_context() to reset.
    If a parameter is None, the existing value is preserved.
    """
    tokens: list[contextvars.Token] = []

    if correlation_id is not None:
        tokens.append(_correlation_id_var.set(correlation_id))
    if tenant_id is not None:
        tokens.append(_tenant_id_var.set(tenant_id))
    if request_id is not None:
        tokens.append(_request_id_var.set(request_id))

    if extra:
        current = _extra_context_var.get()
        merged = {**current, **extra}
        tokens.append(_extra_context_var.set(merged))

    return _CompositeToken(tokens)


def clear_context(token: Any) -> None:
    """Clear context variables using a token from bind_context()."""
    if isinstance(token, _CompositeToken):
        for t in reversed(token.tokens):
            t.var.reset(t)
    else:
        token.var.reset(token)


class _CompositeToken:
    """Wrapper for multiple contextvar tokens."""
    def __init__(self, tokens: list[contextvars.Token]):
        self.tokens = tokens


# ---------------------------------------------------------------------------
# Log record
# ---------------------------------------------------------------------------

@dataclass
class LogRecord:
    """A structured log record."""
    timestamp: str
    level: str
    logger: str
    message: str
    correlation_id: str | None = None
    tenant_id: str | None = None
    request_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)
    exception: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary suitable for JSON serialization."""
        result: dict[str, Any] = {
            "timestamp": self.timestamp,
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
        }
        if self.correlation_id is not None:
            result["correlation_id"] = self.correlation_id
        if self.tenant_id is not None:
            result["tenant_id"] = self.tenant_id
        if self.request_id is not None:
            result["request_id"] = self.request_id
        if self.extra:
            result["extra"] = self.extra
        if self.source:
            result["source"] = self.source
        if self.exception is not None:
            result["exception"] = self.exception
        return result

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), default=str, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Structured formatter
# ---------------------------------------------------------------------------

class StructuredFormatter(logging.Formatter):
    """Formats log records as JSON lines."""

    def __init__(self, *, include_source: bool = False):
        super().__init__()
        self.include_source = include_source

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string."""
        # Extract extra fields (anything not in the standard LogRecord attributes)
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "asctime", "taskName",
        }
        extra: dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                extra[key] = value

        # Build exception info if present
        exception_info: dict[str, Any] | None = None
        if record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info
            exception_info = {
                "type": exc_type.__name__ if exc_type else None,
                "message": str(exc_value) if exc_value else None,
                "stacktrace": "".join(traceback.format_exception(*record.exc_info)),
            }

        # Build source location
        source: dict[str, Any] = {}
        if self.include_source:
            source = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Get context variables
        corr_id = _correlation_id_var.get()
        tenant_id = _tenant_id_var.get()
        request_id = _request_id_var.get()
        ctx_extra = _extra_context_var.get()

        # Merge extra from context and record
        merged_extra = {**ctx_extra, **extra}

        log_record = LogRecord(
            timestamp=datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            correlation_id=corr_id,
            tenant_id=tenant_id,
            request_id=request_id,
            extra=merged_extra,
            source=source,
            exception=exception_info,
        )

        return log_record.to_json()


# ---------------------------------------------------------------------------
# Structured logger
# ---------------------------------------------------------------------------

class StructuredLogger:
    """A logger that outputs structured JSON log records.

    Wraps Python's standard logging.Logger and provides a consistent
    interface for structured logging with context awareness.
    """

    def __init__(self, name: str, level: LogLevel = LogLevel.INFO):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level.numeric)
        self._level = level

    @property
    def name(self) -> str:
        return self._logger.name

    @property
    def level(self) -> LogLevel:
        return self._level

    def set_level(self, level: LogLevel) -> None:
        """Set the log level."""
        self._level = level
        self._logger.setLevel(level.numeric)

    def is_enabled_for(self, level: LogLevel) -> bool:
        """Check if a log level is enabled."""
        return self._logger.isEnabledFor(level.numeric)

    def debug(self, message: str, **extra: Any) -> None:
        """Log a DEBUG message."""
        self._log(LogLevel.DEBUG, message, **extra)

    def info(self, message: str, **extra: Any) -> None:
        """Log an INFO message."""
        self._log(LogLevel.INFO, message, **extra)

    def warning(self, message: str, **extra: Any) -> None:
        """Log a WARNING message."""
        self._log(LogLevel.WARNING, message, **extra)

    def error(self, message: str, **extra: Any) -> None:
        """Log an ERROR message."""
        self._log(LogLevel.ERROR, message, **extra)

    def critical(self, message: str, **extra: Any) -> None:
        """Log a CRITICAL message."""
        self._log(LogLevel.CRITICAL, message, **extra)

    def exception(self, message: str, **extra: Any) -> None:
        """Log an ERROR message with exception info."""
        self._log(LogLevel.ERROR, message, exc_info=True, **extra)

    def _log(self, level: LogLevel, message: str, **extra: Any) -> None:
        """Internal log method."""
        if not self._logger.isEnabledFor(level.numeric):
            return
        # exc_info is a reserved kwarg for logger.log, not an extra field
        exc_info = extra.pop("exc_info", None)
        self._logger.log(level.numeric, message, exc_info=exc_info, extra=extra)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_config_lock = threading.Lock()
_configured = False
_default_level = LogLevel.INFO
_loggers: dict[str, StructuredLogger] = {}


def configure_logging(
    level: str | LogLevel = "INFO",
    *,
    output: str | Path | TextIO | None = None,
    include_source: bool = False,
    json_format: bool = True,
) -> None:
    """Configure the root logger for structured logging.

    Args:
        level: Minimum log level to emit.
        output: Where to write logs. None = stdout, "stderr" = stderr,
                a file path = write to file, or a file-like object.
        include_source: Include file/line/function in each log record.
        json_format: If True, output JSON lines. If False, output plain text.
    """
    global _configured, _default_level

    with _config_lock:
        if isinstance(level, str):
            _default_level = LogLevel.from_string(level)
        else:
            _default_level = level

        # Determine output stream
        if output is None or output == "stdout":
            stream: TextIO = sys.stdout
        elif output == "stderr":
            stream = sys.stderr
        elif isinstance(output, (str, Path)):
            stream = open(output, "a", encoding="utf-8")
        else:
            stream = output  # type: ignore[assignment]

        # Configure root logger
        root = logging.getLogger()
        root.setLevel(_default_level.numeric)

        # Remove existing handlers
        for handler in root.handlers[:]:
            root.removeHandler(handler)

        handler = logging.StreamHandler(stream)
        if json_format:
            handler.setFormatter(StructuredFormatter(include_source=include_source))
        else:
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            ))
        root.addHandler(handler)

        # Also configure the dcc namespace
        dcc_logger = logging.getLogger("dcc")
        dcc_logger.setLevel(_default_level.numeric)

        _configured = True


def get_logger(name: str, level: str | LogLevel | None = None) -> StructuredLogger:
    """Get or create a structured logger.

    Args:
        name: Logger name (use __name__ from the calling module).
        level: Optional override for this logger's level.
    """
    if name in _loggers:
        return _loggers[name]

    log_level = _default_level
    if level is not None:
        if isinstance(level, str):
            log_level = LogLevel.from_string(level)
        else:
            log_level = level

    logger = StructuredLogger(name, log_level)
    _loggers[name] = logger
    return logger


def get_current_context() -> dict[str, Any]:
    """Get the current logging context as a dictionary."""
    ctx: dict[str, Any] = {}
    corr_id = _correlation_id_var.get()
    tenant_id = _tenant_id_var.get()
    request_id = _request_id_var.get()
    extra = _extra_context_var.get()

    if corr_id is not None:
        ctx["correlation_id"] = corr_id
    if tenant_id is not None:
        ctx["tenant_id"] = tenant_id
    if request_id is not None:
        ctx["request_id"] = request_id
    if extra:
        ctx.update(extra)

    return ctx


def reset_logging() -> None:
    """Reset logging configuration (useful for testing)."""
    global _configured, _loggers

    with _config_lock:
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)
        root.setLevel(logging.NOTSET)
        _loggers.clear()
        _configured = False
        _default_level = LogLevel.INFO
