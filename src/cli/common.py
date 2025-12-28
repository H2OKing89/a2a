"""
Common utilities shared across CLI commands.

This module provides:
- Factory functions for API clients and cache
- Library ID resolution
- Shared console and UI instances
- Async CLI utilities
"""

import logging
from typing import Any

import typer

from src.abs import ABSClient
from src.audible import AudibleClient
from src.cache import SQLiteCache
from src.config import get_settings
from src.utils.ui import Icons, console, ui

from .async_utils import (
    AsyncBatchProcessor,
    async_command,
    gather_with_progress,
    run_async,
    stream_with_progress,
)

__all__ = [
    "async_command",
    "AsyncBatchProcessor",
    "console",
    "gather_with_progress",
    "get_abs_client",
    "get_audible_client",
    "get_cache",
    "get_default_library_id",
    "Icons",
    "logger",
    "resolve_library_id",
    "run_async",
    "stream_with_progress",
    "ui",
]

logger = logging.getLogger(__name__)

# Global cache instance (lazy-loaded)
_cache: SQLiteCache | None = None


def get_default_library_id() -> str | None:
    """Get the default library ID from settings."""
    return get_settings().abs.library_id


def resolve_library_id(library_id: str | None) -> str:
    """Resolve library ID, using default if not provided.

    Args:
        library_id: Explicit library ID, or None to use default

    Returns:
        Resolved library ID

    Raises:
        typer.Exit: If no library ID available
    """
    if library_id:
        return library_id

    default_id = get_default_library_id()
    if default_id:
        return default_id

    console.print("[red]Error:[/red] No library ID provided and ABS_LIBRARY_ID not set in .env")
    console.print("[dim]Hint: Set ABS_LIBRARY_ID in .env or pass --library/-l option[/dim]")
    raise typer.Exit(1)


def get_cache() -> SQLiteCache | None:
    """Get shared SQLite cache instance.

    Returns:
        SQLiteCache instance if caching is enabled, else None
    """
    global _cache
    settings = get_settings()

    if not settings.cache.enabled:
        return None

    if _cache is None:
        _cache = SQLiteCache(
            db_path=settings.cache.db_path,
            default_ttl_hours=settings.cache.default_ttl_hours,
            max_memory_entries=settings.cache.max_memory_entries,
        )

    return _cache


def get_abs_client() -> ABSClient:
    """Get configured ABS client.

    Returns:
        ABSClient instance with settings from config
    """
    settings = get_settings()

    cache = get_cache() if settings.cache.enabled else None

    return ABSClient(
        host=settings.abs.host,
        api_key=settings.abs.api_key,
        rate_limit_delay=settings.abs.rate_limit_delay,
        cache=cache,
        cache_ttl_hours=settings.cache.abs_ttl_hours,
    )


def get_audible_client() -> AudibleClient:
    """Get configured Audible client.

    Returns:
        AudibleClient instance with settings from config
    """
    settings = get_settings()

    cache = get_cache() if settings.cache.enabled else None

    return AudibleClient.from_file(
        auth_file=settings.audible.auth_file,
        cache=cache,
        cache_ttl_hours=settings.cache.audible_ttl_hours,
        rate_limit_delay=settings.audible.rate_limit_delay,
        requests_per_minute=settings.audible.requests_per_minute,
        burst_size=settings.audible.burst_size,
        backoff_multiplier=settings.audible.backoff_multiplier,
        max_backoff_seconds=settings.audible.max_backoff_seconds,
    )


def format_duration(seconds: float | int | None) -> str:
    """Format duration in seconds to human readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "12h 30m" or "N/A"
    """
    if not seconds:
        return "N/A"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def format_size(size_mb: float | None) -> str:
    """Format size in MB to human readable string.

    Args:
        size_mb: Size in megabytes

    Returns:
        Formatted string like "1.2 GB" or "500 MB"
    """
    if not size_mb:
        return "N/A"
    if size_mb >= 1024:
        return f"{size_mb / 1024:.1f} GB"
    return f"{size_mb:.0f} MB"


def format_bitrate(kbps: float | None) -> str:
    """Format bitrate to human readable string.

    Args:
        kbps: Bitrate in kilobits per second

    Returns:
        Formatted string like "128 kbps"
    """
    if not kbps:
        return "N/A"
    return f"{int(kbps)} kbps"
