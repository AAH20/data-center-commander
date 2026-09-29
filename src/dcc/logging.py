"""
Centralized logging module for Data Center Commander.

Provides structured JSON logging with tenant context, request tracing,
and automatic log shipping to Loki/ELK via file outputs.

Usage:
    from dcc.logging import get_logger

    logger = get_logger(__name__)
    logger.info("Processing telemetry", extra={"tenant_id": tenant, "count": len(readings)})
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import threading
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Context variables for request-scoped logging
tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Log directory setup
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Subdirectories for different log types
APP_LOG_DIR = LOG_DIR / "app"
API_LOG_DIR = LOG_DIR / "api"
ERROR_LOG_DIR = LOG_DIR / "errors"
AUDIT_LOG_DIR = LOG_DIR / "audit"

for d in [APP_LOG_DIR, API_LOG_DIR, ERROR_LOG_DIR, AUDIT_LOG_DIR]:
    d.mkdir(exist_ok=True)


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "thread_name": record.threadName,
        }

        # Add context variables
        tenant_id = tenant_id_var.get()
        request_id = request_id_var.get()
        if tenant_id:
            log_obj["tenant_id"] = tenant_id
        if request_id:
            log_obj["request_id"] = request_id

        # Add extra fields
        extra = getattr(record, "extra", None)
        if extra:
            log_obj.update(extra)

        # Add exception info
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str, ensure_ascii=False)


class ContextFilter(logging.Filter):
    """Injects context variables into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.tenant_id = tenant_id_var.get()
        record.request_id = request_id_var.get()
        return True


def get_logger(name: str) -> logging.Logger:
    """Get a logger with JSON formatting and context support."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(os.environ.get("DCC_LOG_LEVEL", "INFO"))
    logger.addFilter(ContextFilter())

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(JSONFormatter())
    logger.addHandler(console)

    # File handlers with rotation
    app_handler = logging.handlers.RotatingFileHandler(
        APP_LOG_DIR / "application.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    app_handler.setFormatter(JSONFormatter())
    logger.addHandler(app_handler)

    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        ERROR_LOG_DIR / "error.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    logger.addHandler(error_handler)

    return logger


def set_tenant_context(tenant_id: str | None) -> None:
    """Set the tenant ID for the current context."""
    tenant_id_var.set(tenant_id)


def set_request_context(request_id: str | None) -> None:
    """Set the request ID for the current context."""
    request_id_var.set(request_id)


def clear_context() -> None:
    """Clear all context variables."""
    tenant_id_var.set(None)
    request_id_var.set(None)


class LogContext:
    """Context manager for request-scoped logging context."""

    def __init__(self, tenant_id: str | None = None, request_id: str | None = None):
        self.tenant_id = tenant_id
        self.request_id = request_id
        self._tenant_token = None
        self._request_token = None

    def __enter__(self):
        if self.tenant_id:
            self._tenant_token = tenant_id_var.set(self.tenant_id)
        if self.request_id:
            self._request_token = request_id_var.set(self.request_id)
        return self

    def __exit__(self, *args):
        if self._tenant_token:
            tenant_id_var.reset(self._tenant_token)
        if self._request_token:
            request_id_var.reset(self._request_token)


# Audit logger for security events
def get_audit_logger() -> logging.Logger:
    """Get the audit logger for security-sensitive events."""
    logger = logging.getLogger("dcc.audit")

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.addFilter(ContextFilter())

    audit_handler = logging.handlers.RotatingFileHandler(
        AUDIT_LOG_DIR / "audit.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
    )
    audit_handler.setFormatter(JSONFormatter())
    logger.addHandler(audit_handler)

    return logger


# API access logger
def get_api_logger() -> logging.Logger:
    """Get the API access logger."""
    logger = logging.getLogger("dcc.api")

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.addFilter(ContextFilter())

    api_handler = logging.handlers.RotatingFileHandler(
        API_LOG_DIR / "access.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    api_handler.setFormatter(JSONFormatter())
    logger.addHandler(api_handler)

    return logger
