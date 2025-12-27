"""Tests for ABS logging module."""

import logging
from unittest.mock import patch

import pytest

from src.abs.logging import (
    LogContext,
    configure_logging,
    enable_debug_logging,
    get_logger,
    set_level,
)


@pytest.fixture(autouse=True)
def cleanup_abs_logger():
    """Clean up ABS logger handlers after each test."""
    yield
    # Remove all handlers from the abs logger after test
    logger = logging.getLogger("abs")
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


class TestConfigureLogging:
    """Test configure_logging function."""

    def test_configure_logging_defaults(self):
        """Test configure_logging with defaults."""
        logger = configure_logging()

        assert logger.name == "src.abs"
        assert logger.level == logging.INFO

    def test_configure_logging_debug_level(self):
        """Test configure_logging with debug level."""
        logger = configure_logging(level="debug")

        assert logger.level == logging.DEBUG

    def test_configure_logging_int_level(self):
        """Test configure_logging with integer level."""
        logger = configure_logging(level=logging.WARNING)

        assert logger.level == logging.WARNING

    def test_configure_logging_console_handler(self):
        """Test console handler is added."""
        logger = configure_logging(console=True)

        # Should have at least one handler
        assert len(logger.handlers) >= 1
        # First handler should be StreamHandler
        assert isinstance(logger.handlers[0], logging.StreamHandler)

    def test_configure_logging_no_console(self):
        """Test no console handler when disabled."""
        logger = configure_logging(console=False)

        # Should have no handlers (no file either)
        assert len(logger.handlers) == 0

    def test_configure_logging_file_handler(self, tmp_path):
        """Test file handler is created."""
        log_file = tmp_path / "test.log"
        logger = configure_logging(console=False, file_path=log_file)

        try:
            assert len(logger.handlers) == 1
            assert isinstance(logger.handlers[0], logging.FileHandler)
            assert log_file.exists()
        finally:
            # Explicitly close handlers to avoid ResourceWarning
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)


class TestGetLogger:
    """Test get_logger function."""

    def test_get_logger_default(self):
        """Test get_logger returns module logger."""
        logger = get_logger()
        assert logger.name == "src.abs"

    def test_get_logger_with_name(self):
        """Test get_logger with sub-logger name."""
        logger = get_logger("client")
        assert logger.name == "src.abs.client"

    def test_get_logger_async(self):
        """Test get_logger for async module."""
        logger = get_logger("async_client")
        assert logger.name == "src.abs.async_client"


class TestSetLevel:
    """Test set_level function."""

    def test_set_level_string(self):
        """Test set_level with string."""
        configure_logging()
        set_level("debug")

        logger = get_logger()
        assert logger.level == logging.DEBUG

    def test_set_level_int(self):
        """Test set_level with int."""
        configure_logging()
        set_level(logging.ERROR)

        logger = get_logger()
        assert logger.level == logging.ERROR


class TestEnableDebugLogging:
    """Test enable_debug_logging function."""

    def test_enable_debug(self):
        """Test enable_debug_logging sets DEBUG level."""
        configure_logging(level="info")
        enable_debug_logging()

        logger = get_logger()
        assert logger.level == logging.DEBUG


class TestLogContext:
    """Test LogContext context manager."""

    def test_log_context_changes_level(self):
        """Test LogContext temporarily changes level."""
        configure_logging(level="info")
        logger = get_logger()

        assert logger.level == logging.INFO

        with LogContext("debug"):
            assert logger.level == logging.DEBUG

        # Should restore original level
        assert logger.level == logging.INFO

    def test_log_context_with_int_level(self):
        """Test LogContext with integer level."""
        configure_logging(level="info")
        logger = get_logger()

        with LogContext(logging.WARNING):
            assert logger.level == logging.WARNING

        assert logger.level == logging.INFO

    def test_log_context_nested(self):
        """Test nested LogContext."""
        configure_logging(level="info")
        logger = get_logger()

        with LogContext("debug"):
            assert logger.level == logging.DEBUG

            with LogContext("error"):
                assert logger.level == logging.ERROR

            # Back to debug after inner context
            assert logger.level == logging.DEBUG

        # Back to info after outer context
        assert logger.level == logging.INFO
