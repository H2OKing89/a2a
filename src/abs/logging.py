"""
Logging configuration for the ABS module.

Provides centralized logging setup with configurable handlers for
console and file output.
"""

import logging
import sys
from pathlib import Path
from typing import Literal

# Module logger name - all ABS module logs use this prefix
MODULE_LOGGER_NAME = "src.abs"

# Type alias for log levels
LogLevel = Literal["debug", "info", "warning", "error", "critical"]

# Module state
_configured = False


def _get_log_level(level: LogLevel | int) -> int:
    """Convert level string to logging constant."""
    if isinstance(level, int):
        return level

    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    return level_map.get(level.lower(), logging.INFO)


def configure_logging(
    level: LogLevel | int = "info",
    console: bool = True,
    file_path: str | Path | None = None,
    file_log_level: LogLevel | int | None = None,
    format_string: str | None = None,
) -> logging.Logger:
    """
    Configure logging for the ABS module.

    Args:
        level: Log level for console output
        console: Whether to enable console logging
        file_path: Optional file path for file logging
        file_log_level: Log level for file output (defaults to level)
        format_string: Custom format string

    Returns:
        Configured logger instance

    Example:
        logger = configure_logging("debug", file_path="logs/abs.log")
    """
    global _configured

    log_level = _get_log_level(level)
    file_log_level = _get_log_level(file_log_level) if file_log_level else log_level

    # Default format
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    formatter = logging.Formatter(format_string)

    # Configure our module logger
    logger = logging.getLogger(MODULE_LOGGER_NAME)
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Initialize handler variables for potential reuse
    console_handler: logging.Handler | None = None
    file_handler: logging.Handler | None = None

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler
    if file_path:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(file_log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _configured = True
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Get a logger for the ABS module.

    Args:
        name: Optional sub-logger name (e.g., "client", "async")

    Returns:
        Logger instance

    Example:
        logger = get_logger("client")  # Returns src.abs.client logger
    """
    if name:
        return logging.getLogger(f"{MODULE_LOGGER_NAME}.{name}")
    return logging.getLogger(MODULE_LOGGER_NAME)


def set_level(level: LogLevel | int) -> None:
    """
    Change the log level for all ABS loggers.

    Args:
        level: New log level
    """
    log_level = _get_log_level(level)
    logger = logging.getLogger(MODULE_LOGGER_NAME)
    logger.setLevel(log_level)
    for handler in logger.handlers:
        handler.setLevel(log_level)


def enable_debug_logging() -> None:
    """Enable debug logging for troubleshooting."""
    set_level("debug")


class LogContext:
    """
    Context manager for temporarily changing log level.

    Example:
        with LogContext("debug"):
            # Debug logging active
            client.get_library(library_id)
        # Back to original level
    """

    def __init__(self, level: LogLevel | int):
        """Initialize with target level."""
        self._target_level = _get_log_level(level)
        self._original_level: int | None = None

    def __enter__(self) -> "LogContext":
        """Enter context and set new level."""
        logger = logging.getLogger(MODULE_LOGGER_NAME)
        self._original_level = logger.level
        logger.setLevel(self._target_level)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and restore original level."""
        if self._original_level is not None:
            logger = logging.getLogger(MODULE_LOGGER_NAME)
            logger.setLevel(self._original_level)
