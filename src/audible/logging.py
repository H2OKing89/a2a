"""
Logging configuration for the Audible module.

Integrates with the audible package's log_helper and provides
consistent logging across all audible-related operations.

Usage:
    from src.audible.logging import configure_logging, get_logger

    # Quick setup with console output
    configure_logging(level="info", console=True)

    # Full setup with file logging
    configure_logging(
        level="debug",
        console=True,
        file_path="logs/audible.log",
        capture_warnings=True
    )

    # Get a logger for your module
    logger = get_logger(__name__)
    logger.info("Starting operation...")
"""

import logging
import sys
from pathlib import Path
from typing import Literal

# Try to import audible's log_helper
try:
    from audible import log_helper

    HAS_AUDIBLE_LOG_HELPER = True
except ImportError:
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

    Args:
        name: Logger name (usually __name__). If None, returns the root audible logger.

    Returns:
        Configured logger instance
    """
    if name is None:
        return logging.getLogger(MODULE_LOGGER_NAME)
    return logging.getLogger(name)


def configure_logging(
    level: LogLevel | int = "info",
    console: bool = True,
    file_path: str | Path | None = None,
    file_level: LogLevel | int | None = None,
    capture_warnings: bool = True,
    format_string: str | None = None,
    configure_audible_package: bool = True,
) -> logging.Logger:
    """
    Configure logging for all audible-related operations.

    This configures both our wrapper module (src.audible) and the
    underlying audible package logging.

    Args:
        level: Base log level for all loggers
        console: Whether to log to console (stdout)
        file_path: Optional file path for file logging
        file_level: Log level for file (defaults to level)
        capture_warnings: Whether to capture Python warnings
        format_string: Custom format string (uses default if None)
        configure_audible_package: Also configure the audible package logger

    Returns:
        The configured logger

    Example:
        # Basic console logging
        configure_logging(level="info")

        # Debug logging to file and console
        configure_logging(
            level="debug",
            console=True,
            file_path="logs/audible.log"
        )
    """
    global _configured

    log_level = get_level(level)
    file_log_level = get_level(file_level) if file_level else log_level

    # Default format
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")

    # Configure our module logger
    logger = logging.getLogger(MODULE_LOGGER_NAME)
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

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

    # Configure the audible package's logger using its log_helper
    if configure_audible_package and HAS_AUDIBLE_LOG_HELPER:
        try:
            log_helper.set_level(level if isinstance(level, str) else "info")
            if console:
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
                if console:
                    audible_logger.addHandler(console_handler)
                if file_path:
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
    Quick helper to enable debug logging to console.

    Useful during development.
    """
    configure_logging(level="debug", console=True, capture_warnings=True)


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
