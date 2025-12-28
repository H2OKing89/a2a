"""
Rich-enhanced logging configuration for the ABS module.

Provides centralized logging setup with beautiful rich console output
and configurable handlers for console and file output.

.. warning::
    By default, ``configure_logging()`` installs a **global traceback handler**
    via Rich that affects all uncaught exceptions in the process. This is
    great for CLI applications but may conflict with other frameworks.
    Set ``rich_tracebacks=False`` to disable this behavior.

Usage:
    from src.abs.logging import configure_logging, get_logger

    # Quick setup with rich console output
    configure_logging(level="info", console=True, use_rich=True)

    # For library usage (avoid global side effects):
    configure_logging(level="info", use_rich=True, rich_tracebacks=False)

    # Get a logger for your module
    logger = get_logger(__name__)
    logger.info("[green]✓[/green] Connected to ABS")
"""

import logging
import sys
from pathlib import Path
from typing import Literal

from rich.logging import RichHandler
from rich.traceback import install as install_rich_traceback

from src.utils.ui import console as rich_console

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
    use_rich: bool = True,
    rich_tracebacks: bool = True,
    show_path: bool = False,
    show_time: bool = True,
    markup: bool = True,
) -> logging.Logger:
    """
    Configure rich-enhanced logging for the ABS module.

    .. warning::
        **Global Side Effect:** When ``use_rich=True`` and ``rich_tracebacks=True``
        (the defaults), this function calls ``rich.traceback.install()`` which
        **modifies Python's global exception handling**. This affects ALL uncaught
        exceptions in the entire process, not just this module. This is ideal for
        CLI applications but may be inappropriate for libraries or when integrating
        with other frameworks that have their own exception handling.

    Args:
        level: Log level for console output
        console: Whether to enable console logging
        file_path: Optional file path for file logging
        file_log_level: Log level for file output (defaults to level)
        format_string: Custom format string for file logging
        use_rich: Use rich handler for console (beautiful output).
            **Process-wide toggle** - enables Rich formatting globally.
        rich_tracebacks: Enable rich tracebacks for beautiful exception output.
            **Process-wide toggle** - installs a global exception hook via
            ``sys.excepthook`` that affects all uncaught exceptions.
        show_path: Show file path in console logs
        show_time: Show timestamp in console logs
        markup: Enable rich markup in log messages

    Returns:
        Configured logger instance

    Example:
        # Standard usage with rich output (installs global handler)
        logger = configure_logging("debug", file_path="logs/abs.log", use_rich=True)
        logger.info("[green]✓[/green] Connected to server")

        # For libraries or to avoid global side effects:
        logger = configure_logging("info", use_rich=True, rich_tracebacks=False)

        # Completely disable Rich features (plain logging):
        logger = configure_logging("info", use_rich=False)
    """
    global _configured

    log_level = _get_log_level(level)
    file_log_level = _get_log_level(file_log_level) if file_log_level else log_level

    # Install rich tracebacks globally for beautiful exceptions
    if use_rich and rich_tracebacks:
        install_rich_traceback(
            console=rich_console,
            show_locals=False,
            width=rich_console.width,
            extra_lines=3,
            theme="monokai",
            word_wrap=True,
        )

    # Configure our module logger
    logger = logging.getLogger(MODULE_LOGGER_NAME)
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Initialize handler variables for potential reuse
    console_handler: logging.Handler | None = None
    file_handler: logging.Handler | None = None

    # Console handler - use Rich if enabled
    if console:
        if use_rich:
            console_handler = RichHandler(
                level=log_level,
                console=rich_console,
                show_time=show_time,
                show_path=show_path,
                rich_tracebacks=rich_tracebacks,
                markup=markup,
                log_time_format="[%X]",
                keywords=[
                    # Highlight these words in logs
                    "ABS",
                    "audiobookshelf",
                    "library",
                    "item",
                    "cache",
                    "API",
                ],
            )
        else:
            # Standard handler
            if format_string is None:
                format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            formatter = logging.Formatter(format_string)
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    # File handler - always use standard formatting for parseable logs
    if file_path:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_format = format_string or "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        file_formatter = logging.Formatter(file_format)

        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(file_log_level)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    _configured = True
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Get a logger for the ABS module.

    Supports rich markup in log messages when using RichHandler.

    Args:
        name: Optional sub-logger name (e.g., "client", "async")

    Returns:
        Logger instance

    Example:
        logger = get_logger("client")  # Returns src.abs.client logger
        logger.info("[green]✓[/green] Library fetched")
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
    """Enable debug logging with rich output for troubleshooting."""
    configure_logging(level="debug", use_rich=True, rich_tracebacks=True)


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


# =============================================================================
# Convenience log functions - re-exported from shared utilities
# =============================================================================

from src.utils.logging import (
    log_debug,
    log_error,
    log_info,
    log_success,
    log_warning,
)

__all__ = [
    "configure_logging",
    "enable_debug_logging",
    "get_logger",
    "log_debug",
    "log_error",
    "log_info",
    "log_success",
    "log_warning",
    "LogContext",
    "set_level",
]
