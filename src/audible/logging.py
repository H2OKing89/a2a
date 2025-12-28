"""
Rich-enhanced logging configuration for the Audible module.

Integrates with the audible package's log_helper and provides
beautiful console output with rich formatting.

.. warning::
    By default, ``configure_logging()`` installs a **global traceback handler**
    via Rich that affects all uncaught exceptions in the process. This is
    great for CLI applications but may conflict with other frameworks.
    Set ``rich_tracebacks=False`` to disable this behavior.

Usage:
    from src.audible.logging import configure_logging, get_logger

    # Quick setup with rich console output
    configure_logging(level="info", console_output=True, use_rich=True)

    # Full setup with file logging
    configure_logging(
        level="debug",
        console_output=True,
        file_path="logs/audible.log",
        capture_warnings=True,
        use_rich=True
    )

    # For library usage (avoid global side effects):
    configure_logging(level="info", use_rich=True, rich_tracebacks=False)

    # Get a logger for your module
    logger = get_logger(__name__)
    logger.info("[bold cyan]Starting operation...[/bold cyan]")
"""

import logging
import sys
from pathlib import Path
from typing import Literal

from rich.logging import RichHandler
from rich.traceback import install as install_rich_traceback

from src.utils.ui import console as rich_console

# Try to import audible's log_helper
try:
    from audible import log_helper

    HAS_AUDIBLE_LOG_HELPER = True
except ImportError:
    log_helper = None  # type: ignore[assignment]
    HAS_AUDIBLE_LOG_HELPER = False


LogLevel = Literal["debug", "info", "warning", "error", "critical", "notset"]

# Map string levels to logging constants
LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "notset": logging.NOTSET,
}

# Our module's logger name
MODULE_LOGGER_NAME = "src.audible"

# Track if we've configured
_configured = False


def get_level(level: LogLevel | int) -> int:
    """Convert string level to logging constant."""
    if isinstance(level, int):
        return level
    return LEVEL_MAP.get(level.lower(), logging.INFO)


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Get a logger for audible operations.

    Supports rich markup in log messages when using RichHandler.

    Args:
        name: Logger name (usually __name__). If None, returns the root audible logger.

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("[bold green]Success![/bold green] Operation completed")
        logger.error("[red]Failed:[/red] %s", error_message)
    """
    if name is None:
        return logging.getLogger(MODULE_LOGGER_NAME)
    return logging.getLogger(name)


def configure_logging(
    level: LogLevel | int = "info",
    console_output: bool = True,
    file_path: str | Path | None = None,
    file_level: LogLevel | int | None = None,
    capture_warnings: bool = True,
    format_string: str | None = None,
    configure_audible_package: bool = True,
    use_rich: bool = True,
    rich_tracebacks: bool = True,
    show_path: bool = False,
    show_time: bool = True,
    markup: bool = True,
) -> logging.Logger:
    """
    Configure rich-enhanced logging for all audible-related operations.

    This configures both our wrapper module (src.audible) and the
    underlying audible package logging with beautiful rich output.

    .. warning::
        **Global Side Effect:** When ``use_rich=True`` and ``rich_tracebacks=True``
        (the defaults), this function calls ``rich.traceback.install()`` which
        **modifies Python's global exception handling**. This affects ALL uncaught
        exceptions in the entire process, not just this module. This is ideal for
        CLI applications but may be inappropriate for libraries or when integrating
        with other frameworks that have their own exception handling.

    Args:
        level: Base log level for all loggers
        console_output: Whether to log to console (stdout)
        file_path: Optional file path for file logging
        file_level: Log level for file (defaults to level)
        capture_warnings: Whether to capture Python warnings
        format_string: Custom format string for file logging
        configure_audible_package: Also configure the audible package logger
        use_rich: Use rich handler for console (beautiful output).
            **Process-wide toggle** - enables Rich formatting globally.
        rich_tracebacks: Enable rich tracebacks for beautiful exception output.
            **Process-wide toggle** - installs a global exception hook via
            ``sys.excepthook`` that affects all uncaught exceptions.
        show_path: Show file path in console logs
        show_time: Show timestamp in console logs
        markup: Enable rich markup in log messages

    Returns:
        The configured logger

    Example:
        # Basic rich console logging (with global traceback handler)
        configure_logging(level="info", use_rich=True)

        # Debug logging with rich output
        configure_logging(
            level="debug",
            console_output=True,
            file_path="logs/audible.log",
            use_rich=True,
            rich_tracebacks=True
        )

        # For libraries or when you need to avoid global side effects:
        configure_logging(
            level="info",
            use_rich=True,
            rich_tracebacks=False  # Don't install global exception hook
        )

        # Completely disable Rich features (plain logging):
        configure_logging(level="info", use_rich=False)

        # Then use in your code:
        logger = get_logger(__name__)
        logger.info("[green]✓[/green] Connected to Audible")
        logger.warning("[yellow]⚠[/yellow] Rate limit approaching")
    """
    global _configured

    log_level = get_level(level)
    file_log_level = get_level(file_level) if file_level else log_level

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

    # Initialize handler variables
    console_handler: logging.Handler | None = None
    file_handler: logging.Handler | None = None

    # Console handler - use Rich if enabled
    if console_output:
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
                    "audible",
                    "library",
                    "catalog",
                    "ASIN",
                    "cache",
                    "auth",
                    "rate limit",
                ],
            )
        else:
            # Standard handler
            if format_string is None:
                format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
            formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    # File handler - always use standard formatting for parseable logs
    if file_path:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_format = format_string or "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        file_formatter = logging.Formatter(file_format, datefmt="%Y-%m-%d %H:%M:%S")

        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(file_log_level)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Configure the audible package's logger
    if configure_audible_package and HAS_AUDIBLE_LOG_HELPER:
        try:
            log_helper.set_level(level if isinstance(level, str) else "info")
            if console_output:
                log_helper.set_console_logger(level if isinstance(level, str) else "info")
            if file_path:
                log_helper.set_file_logger(
                    str(file_path).replace(".log", "_package.log"),
                    level if isinstance(level, str) else "info",
                )
            if capture_warnings:
                log_helper.capture_warnings()
        except Exception:
            # If audible log_helper fails, fall back to standard logging
            audible_logger = logging.getLogger("audible")
            audible_logger.setLevel(log_level)
            if not audible_logger.handlers:
                if console_handler is not None:
                    audible_logger.addHandler(console_handler)
                if file_handler is not None:
                    audible_logger.addHandler(file_handler)

    # Capture warnings
    if capture_warnings:
        logging.captureWarnings(True)

    _configured = True
    return logger


def set_level(level: LogLevel | int) -> None:
    """
    Change the log level for all audible loggers.

    Args:
        level: New log level
    """
    log_level = get_level(level)

    # Our logger
    logger = logging.getLogger(MODULE_LOGGER_NAME)
    logger.setLevel(log_level)
    for handler in logger.handlers:
        handler.setLevel(log_level)

    # Audible package logger
    if HAS_AUDIBLE_LOG_HELPER:
        try:
            log_helper.set_level(level if isinstance(level, str) else "info")
        except Exception:
            pass

    audible_logger = logging.getLogger("audible")
    audible_logger.setLevel(log_level)


def silence_audible_package() -> None:
    """
    Silence the audible package's logging.

    Useful when you only want to see your own logs.
    """
    logging.getLogger("audible").setLevel(logging.CRITICAL)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def enable_debug_logging() -> None:
    """
    Quick helper to enable debug logging to console with rich output.

    Useful during development.
    """
    configure_logging(level="debug", console_output=True, capture_warnings=True, use_rich=True, rich_tracebacks=True)


def enable_request_logging() -> None:
    """
    Enable logging of HTTP requests (debug level for httpx).

    Useful for debugging API issues.
    """
    logging.getLogger("httpx").setLevel(logging.DEBUG)
    logging.getLogger("httpcore").setLevel(logging.DEBUG)


class LogContext:
    """
    Context manager for temporarily changing log level.

    Example:
        with LogContext("debug"):
            # Debug logging enabled here
            client.get_library()
        # Back to previous level
    """

    def __init__(self, level: LogLevel | int):
        self.new_level = get_level(level)
        self.old_levels: dict[str, int] = {}

    def __enter__(self):
        # Save current levels
        for name in [MODULE_LOGGER_NAME, "audible"]:
            logger = logging.getLogger(name)
            self.old_levels[name] = logger.level
            logger.setLevel(self.new_level)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore levels
        for name, level in self.old_levels.items():
            logging.getLogger(name).setLevel(level)
        return False


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
    "get_logger",
    "set_level",
    "enable_debug_logging",
    "enable_request_logging",
    "silence_audible_package",
    "LogContext",
    "log_success",
    "log_error",
    "log_warning",
    "log_info",
    "log_debug",
]
