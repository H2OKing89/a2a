"""Tests for Audible logging module."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audible.logging import (
    MODULE_LOGGER_NAME,
    LogContext,
    configure_logging,
    enable_debug_logging,
    enable_request_logging,
    get_level,
    get_logger,
    set_level,
    silence_audible_package,
)


@pytest.fixture(autouse=True)
def cleanup_audible_logger():
    """Clean up audible logger handlers after each test."""
    yield
    # Remove all handlers from the audible_tool logger after test
    logger = logging.getLogger(MODULE_LOGGER_NAME)
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


class TestConfigureLogging:
    """Test logging configuration."""

    def test_configure_logging_console_only(self):
        """Test console logging configuration."""
        configure_logging(level="info", console_output=True, file_path=None)

        logger = get_logger("test")
        # Just verify it doesn't raise
        logger.info("Test message")

        # Verify logger is configured
        parent = logging.getLogger(MODULE_LOGGER_NAME)
        assert parent.level == logging.INFO

    def test_configure_logging_with_level(self):
        """Test setting log level."""
        configure_logging(level="debug", console_output=True)

        logger = get_logger("test_level")
        # Check the parent logger (MODULE_LOGGER_NAME)
        parent = logging.getLogger(MODULE_LOGGER_NAME)
        assert parent.level == logging.DEBUG

    def test_configure_logging_invalid_level(self):
        """Test invalid log level defaults to INFO."""
        configure_logging(level="invalid", console_output=True)

        parent = logging.getLogger(MODULE_LOGGER_NAME)
        # Should default to INFO
        assert parent.level == logging.INFO

    def test_configure_logging_with_file(self, tmp_path):
        """Test file logging configuration."""
        log_file = tmp_path / "test.log"
        parent_logger = logging.getLogger(MODULE_LOGGER_NAME)

        try:
            configure_logging(level="info", console_output=False, file_path=str(log_file))

            logger = get_logger("test_file")
            logger.info("File test message")

            # Ensure handlers are flushed
            for handler in parent_logger.handlers:
                if hasattr(handler, "flush"):
                    handler.flush()

            # File should exist
            assert log_file.exists()
        finally:
            # Explicitly close handlers to avoid ResourceWarning
            for handler in parent_logger.handlers[:]:
                handler.close()
                parent_logger.removeHandler(handler)

    def test_get_logger_returns_logger(self):
        """Test get_logger returns a logger instance."""
        logger = get_logger("my_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "my_module"

    def test_get_logger_none_returns_module_logger(self):
        """Test get_logger with None returns module logger."""
        logger = get_logger(None)
        assert logger.name == MODULE_LOGGER_NAME

    def test_set_level(self):
        """Test set_level changes log level."""
        configure_logging(level="info", console_output=True)

        set_level("debug")
        parent = logging.getLogger(MODULE_LOGGER_NAME)
        assert parent.level == logging.DEBUG

        set_level("warning")
        assert parent.level == logging.WARNING

    def test_enable_debug_logging(self):
        """Test enable_debug_logging sets DEBUG level."""
        configure_logging(level="info", console_output=True)

        enable_debug_logging()
        parent = logging.getLogger(MODULE_LOGGER_NAME)
        assert parent.level == logging.DEBUG

    def test_enable_request_logging(self):
        """Test enable_request_logging enables httpcore logging."""
        enable_request_logging()
        httpcore_logger = logging.getLogger("httpcore")
        assert httpcore_logger.level == logging.DEBUG

    def test_silence_audible_package(self):
        """Test silencing audible package logs."""
        silence_audible_package()
        audible_logger = logging.getLogger("audible")
        assert audible_logger.level == logging.CRITICAL

    def test_get_level_string(self):
        """Test get_level with string."""
        assert get_level("debug") == logging.DEBUG
        assert get_level("info") == logging.INFO
        assert get_level("warning") == logging.WARNING
        assert get_level("error") == logging.ERROR

    def test_get_level_int(self):
        """Test get_level with int."""
        assert get_level(logging.DEBUG) == logging.DEBUG
        assert get_level(logging.INFO) == logging.INFO


class TestLogContext:
    """Test LogContext context manager."""

    def test_log_context_changes_level(self):
        """Test LogContext changes log level temporarily."""
        configure_logging(level="info", console_output=True)
        parent = logging.getLogger(MODULE_LOGGER_NAME)
        original_level = parent.level

        with LogContext("debug") as ctx:
            assert ctx is not None
            assert parent.level == logging.DEBUG

        # Level should be restored
        assert parent.level == original_level

    def test_log_context_with_int_level(self):
        """Test LogContext with int log level."""
        configure_logging(level="info", console_output=True)

        with LogContext(logging.WARNING):
            parent = logging.getLogger(MODULE_LOGGER_NAME)
            assert parent.level == logging.WARNING

    def test_log_context_nested(self):
        """Test nested LogContext."""
        configure_logging(level="info", console_output=True)
        parent = logging.getLogger(MODULE_LOGGER_NAME)

        with LogContext("debug"):
            assert parent.level == logging.DEBUG
            with LogContext("warning"):
                assert parent.level == logging.WARNING
            # Should restore to debug
            assert parent.level == logging.DEBUG


class TestEnvironmentVariables:
    """Test environment variable support."""

    def test_env_var_log_level(self, monkeypatch):
        """Test AUDIBLE_LOG_LEVEL environment variable."""
        monkeypatch.setenv("AUDIBLE_LOG_LEVEL", "debug")

        # Note: configure_logging doesn't auto-read env vars,
        # but we can test that the level mapping works
        assert get_level("debug") == logging.DEBUG


class TestAudiblePackageIntegration:
    """Test integration with audible package logging."""

    def test_configure_audible_package_true(self):
        """Test configure_audible_package=True configures audible logger."""
        with (
            patch("src.audible.logging.HAS_AUDIBLE_LOG_HELPER", True),
            patch("src.audible.logging.log_helper") as mock_log_helper,
        ):
            configure_logging(level="debug", console_output=True, configure_audible_package=True)
            # Should call log_helper to set level
            assert mock_log_helper.set_level.called or mock_log_helper.set_console_logger.called

    def test_configure_audible_package_false(self):
        """Test configure_audible_package=False skips audible config."""
        with (
            patch("src.audible.logging.HAS_AUDIBLE_LOG_HELPER", True),
            patch("src.audible.logging.log_helper") as mock_log_helper,
        ):
            configure_logging(level="info", console_output=True, configure_audible_package=False)
            # Should NOT call log_helper
            mock_log_helper.set_level.assert_not_called()
