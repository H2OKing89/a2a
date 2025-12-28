"""
Shared logging utilities with Rich markup support.

Provides common logging helper functions used across modules
with consistent Rich-enhanced formatting.
"""

import logging
from typing import Any


def log_success(
    message: str,
    *args: Any,
    logger_name: str | None = None,
    logger: logging.Logger | None = None,
    **kwargs: Any,
) -> None:
    """
    Log a success message with green checkmark.

    Args:
        message: Message to log
        *args: Positional arguments for logger
        logger_name: Name of logger to use (if logger not provided)
        logger: Logger instance to use (overrides logger_name)
        **kwargs: Keyword arguments for logger
    """
    if logger is None:
        logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    logger.info("[green]✓[/green] %s", message, *args, **kwargs)


def log_error(
    message: str,
    *args: Any,
    logger_name: str | None = None,
    logger: logging.Logger | None = None,
    **kwargs: Any,
) -> None:
    """
    Log an error message with red X.

    Args:
        message: Message to log
        *args: Positional arguments for logger
        logger_name: Name of logger to use (if logger not provided)
        logger: Logger instance to use (overrides logger_name)
        **kwargs: Keyword arguments for logger
    """
    if logger is None:
        logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    logger.error("[red]✗[/red] %s", message, *args, **kwargs)


def log_warning(
    message: str,
    *args: Any,
    logger_name: str | None = None,
    logger: logging.Logger | None = None,
    **kwargs: Any,
) -> None:
    """
    Log a warning message with yellow warning sign.

    Args:
        message: Message to log
        *args: Positional arguments for logger
        logger_name: Name of logger to use (if logger not provided)
        logger: Logger instance to use (overrides logger_name)
        **kwargs: Keyword arguments for logger
    """
    if logger is None:
        logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    logger.warning("[yellow]⚠[/yellow] %s", message, *args, **kwargs)


def log_info(
    message: str,
    *args: Any,
    logger_name: str | None = None,
    logger: logging.Logger | None = None,
    **kwargs: Any,
) -> None:
    """
    Log an info message with cyan info icon.

    Args:
        message: Message to log
        *args: Positional arguments for logger
        logger_name: Name of logger to use (if logger not provided)
        logger: Logger instance to use (overrides logger_name)
        **kwargs: Keyword arguments for logger
    """
    if logger is None:
        logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    logger.info("[cyan]ℹ[/cyan] %s", message, *args, **kwargs)


def log_debug(
    message: str,
    *args: Any,
    logger_name: str | None = None,
    logger: logging.Logger | None = None,
    **kwargs: Any,
) -> None:
    """
    Log a debug message with dimmed text.

    Args:
        message: Message to log
        *args: Positional arguments for logger
        logger_name: Name of logger to use (if logger not provided)
        logger: Logger instance to use (overrides logger_name)
        **kwargs: Keyword arguments for logger
    """
    if logger is None:
        logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    logger.debug("[dim]%s[/dim]", message, *args, **kwargs)
