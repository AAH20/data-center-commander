"""Tests for structured logging engine."""
from __future__ import annotations

import io
import json
import logging
import unittest
from unittest.mock import patch

from dcc.observability import (
    LogLevel,
    LogRecord,
    StructuredLogger,
    configure_logging,
    get_logger,
    correlation_id,
    bind_context,
    clear_context,
    get_current_context,
    reset_logging,
)


class TestLogLevel(unittest.TestCase):
    def test_levels_exist(self):
        self.assertEqual(LogLevel.DEBUG.value, "DEBUG")
        self.assertEqual(LogLevel.INFO.value, "INFO")
        self.assertEqual(LogLevel.WARNING.value, "WARNING")
        self.assertEqual(LogLevel.ERROR.value, "ERROR")
        self.assertEqual(LogLevel.CRITICAL.value, "CRITICAL")

    def test_numeric_values(self):
        self.assertEqual(LogLevel.DEBUG.numeric, 10)
        self.assertEqual(LogLevel.INFO.numeric, 20)
        self.assertEqual(LogLevel.WARNING.numeric, 30)
        self.assertEqual(LogLevel.ERROR.numeric, 40)
        self.assertEqual(LogLevel.CRITICAL.numeric, 50)

    def test_from_string(self):
        self.assertEqual(LogLevel.from_string("debug"), LogLevel.DEBUG)
        self.assertEqual(LogLevel.from_string("INFO"), LogLevel.INFO)
        self.assertEqual(LogLevel.from_string("Warning"), LogLevel.WARNING)
        self.assertEqual(LogLevel.from_string("ERROR"), LogLevel.ERROR)
        self.assertEqual(LogLevel.from_string("critical"), LogLevel.CRITICAL)

    def test_from_string_invalid(self):
        with self.assertRaises(ValueError):
            LogLevel.from_string("invalid")


class TestLogRecord(unittest.TestCase):
    def test_to_dict_minimal(self):
        record = LogRecord(
            timestamp="2024-01-01T00:00:00+00:00",
            level="INFO",
            logger="test",
            message="hello",
        )
        d = record.to_dict()
        self.assertEqual(d["timestamp"], "2024-01-01T00:00:00+00:00")
        self.assertEqual(d["level"], "INFO")
        self.assertEqual(d["logger"], "test")
        self.assertEqual(d["message"], "hello")
        self.assertNotIn("correlation_id", d)
        self.assertNotIn("tenant_id", d)

    def test_to_dict_with_context(self):
        record = LogRecord(
            timestamp="2024-01-01T00:00:00+00:00",
            level="INFO",
            logger="test",
            message="hello",
            correlation_id="corr-123",
            tenant_id="tenant-456",
            request_id="req-789",
            extra={"key": "value"},
        )
        d = record.to_dict()
        self.assertEqual(d["correlation_id"], "corr-123")
        self.assertEqual(d["tenant_id"], "tenant-456")
        self.assertEqual(d["request_id"], "req-789")
        self.assertEqual(d["extra"], {"key": "value"})

    def test_to_json(self):
        record = LogRecord(
            timestamp="2024-01-01T00:00:00+00:00",
            level="INFO",
            logger="test",
            message="hello",
        )
        j = record.to_json()
        parsed = json.loads(j)
        self.assertEqual(parsed["message"], "hello")
        self.assertEqual(parsed["level"], "INFO")


class TestStructuredLogger(unittest.TestCase):
    def setUp(self):
        reset_logging()

    def tearDown(self):
        reset_logging()

    def test_get_logger(self):
        logger = get_logger("test.module")
        self.assertIsInstance(logger, StructuredLogger)
        self.assertEqual(logger.name, "test.module")

    def test_get_logger_cached(self):
        logger1 = get_logger("test.module")
        logger2 = get_logger("test.module")
        self.assertIs(logger1, logger2)

    def test_logger_levels(self):
        logger = get_logger("test.levels", "DEBUG")
        self.assertTrue(logger.is_enabled_for(LogLevel.DEBUG))
        self.assertTrue(logger.is_enabled_for(LogLevel.INFO))

        logger.set_level(LogLevel.WARNING)
        self.assertFalse(logger.is_enabled_for(LogLevel.INFO))
        self.assertTrue(logger.is_enabled_for(LogLevel.WARNING))

    def test_log_output_json(self):
        stream = io.StringIO()
        configure_logging(level="DEBUG", output=stream)
        logger = get_logger("test.output")
        logger.info("test_message", key="value")

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        self.assertEqual(parsed["message"], "test_message")
        self.assertEqual(parsed["level"], "INFO")
        self.assertEqual(parsed["logger"], "test.output")
        self.assertEqual(parsed["extra"]["key"], "value")
        self.assertIn("timestamp", parsed)

    def test_log_levels_filter(self):
        stream = io.StringIO()
        configure_logging(level="WARNING", output=stream)
        logger = get_logger("test.filter")

        logger.info("should_not_appear")
        logger.warning("should_appear")

        output = stream.getvalue().strip()
        lines = output.split("\n")
        self.assertEqual(len(lines), 1)
        parsed = json.loads(lines[0])
        self.assertEqual(parsed["message"], "should_appear")

    def test_exception_logging(self):
        stream = io.StringIO()
        configure_logging(level="DEBUG", output=stream)
        logger = get_logger("test.exception")

        try:
            raise ValueError("test error")
        except ValueError:
            logger.exception("caught_error")

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        self.assertEqual(parsed["message"], "caught_error")
        self.assertEqual(parsed["level"], "ERROR")
        self.assertIsNotNone(parsed["exception"])
        self.assertEqual(parsed["exception"]["type"], "ValueError")
        self.assertIn("test error", parsed["exception"]["message"])


class TestCorrelationId(unittest.TestCase):
    def setUp(self):
        reset_logging()

    def tearDown(self):
        reset_logging()

    def test_correlation_id_context(self):
        self.assertIsNone(correlation_id())

        token = bind_context(correlation_id="corr-123")
        self.assertEqual(correlation_id(), "corr-123")

        clear_context(token)
        self.assertIsNone(correlation_id())

    def test_bind_context_multiple(self):
        token = bind_context(
            correlation_id="corr-1",
            tenant_id="tenant-1",
            request_id="req-1",
            custom_key="custom_value",
        )
        ctx = get_current_context()
        self.assertEqual(ctx["correlation_id"], "corr-1")
        self.assertEqual(ctx["tenant_id"], "tenant-1")
        self.assertEqual(ctx["request_id"], "req-1")
        self.assertEqual(ctx["custom_key"], "custom_value")

        clear_context(token)
        ctx = get_current_context()
        self.assertNotIn("correlation_id", ctx)
        self.assertNotIn("tenant_id", ctx)

    def test_bind_context_preserves_existing(self):
        token1 = bind_context(correlation_id="corr-1")
        token2 = bind_context(tenant_id="tenant-1")

        ctx = get_current_context()
        self.assertEqual(ctx["correlation_id"], "corr-1")
        self.assertEqual(ctx["tenant_id"], "tenant-1")

        clear_context(token2)
        ctx = get_current_context()
        self.assertEqual(ctx["correlation_id"], "corr-1")
        self.assertNotIn("tenant_id", ctx)

        clear_context(token1)

    def test_context_in_log_output(self):
        stream = io.StringIO()
        configure_logging(level="DEBUG", output=stream)
        logger = get_logger("test.context")

        token = bind_context(
            correlation_id="corr-abc",
            tenant_id="tenant-xyz",
            request_id="req-123",
        )
        logger.info("with_context")
        clear_context(token)

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        self.assertEqual(parsed["correlation_id"], "corr-abc")
        self.assertEqual(parsed["tenant_id"], "tenant-xyz")
        self.assertEqual(parsed["request_id"], "req-123")


class TestConfigureLogging(unittest.TestCase):
    def setUp(self):
        reset_logging()

    def tearDown(self):
        reset_logging()

    def test_configure_default(self):
        configure_logging()
        root = logging.getLogger()
        self.assertEqual(root.level, logging.INFO)

    def test_configure_level_string(self):
        configure_logging(level="DEBUG")
        root = logging.getLogger()
        self.assertEqual(root.level, logging.DEBUG)

    def test_configure_level_enum(self):
        configure_logging(level=LogLevel.WARNING)
        root = logging.getLogger()
        self.assertEqual(root.level, logging.WARNING)

    def test_configure_invalid_level(self):
        with self.assertRaises(ValueError):
            configure_logging(level="INVALID")

    def test_configure_file_output(self):
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            tmppath = f.name

        try:
            configure_logging(level="DEBUG", output=tmppath)
            logger = get_logger("test.file")
            logger.info("file_test")

            # Force flush
            for handler in logging.getLogger().handlers:
                handler.flush()

            with open(tmppath) as f:
                content = f.read().strip()
                parsed = json.loads(content)
                self.assertEqual(parsed["message"], "file_test")
        finally:
            os.unlink(tmppath)

    def test_plain_text_format(self):
        stream = io.StringIO()
        configure_logging(level="DEBUG", output=stream, json_format=False)
        logger = get_logger("test.plain")
        logger.info("plain_message")

        output = stream.getvalue().strip()
        self.assertIn("plain_message", output)
        self.assertIn("INFO", output)
        self.assertNotIn("{", output)  # Not JSON


class TestResetLogging(unittest.TestCase):
    def test_reset(self):
        configure_logging(level="DEBUG")
        logger = get_logger("test.reset")
        self.assertTrue(logger.is_enabled_for(LogLevel.DEBUG))

        reset_logging()
        root = logging.getLogger()
        self.assertEqual(root.level, logging.NOTSET)


if __name__ == "__main__":
    unittest.main()
