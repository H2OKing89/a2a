"""
Caching module for API responses.

Provides SQLite-based caching with:
- TTL-based expiration
- Namespace support for different data sources
- Full-text search on titles and authors
- ASIN cross-referencing between ABS and Audible
- Month-boundary-aware TTL for pricing data
"""

from .sqlite_cache import (
    PRICING_NAMESPACES,
    SQLiteCache,
    calculate_pricing_ttl_seconds,
    get_seconds_until_next_month,
)

__all__ = [
    "SQLiteCache",
    "calculate_pricing_ttl_seconds",
    "get_seconds_until_next_month",
    "PRICING_NAMESPACES",
]


def get_cache(
    db_path: str = "./data/cache/cache.db",
    default_ttl_hours: float = 2.0,
) -> SQLiteCache:
    """
    Factory function to get a cache instance.

    Args:
        db_path: Path to SQLite database
        default_ttl_hours: Default TTL for cached items

    Returns:
        SQLiteCache instance
    """
    return SQLiteCache(
        db_path=db_path,
        default_ttl_hours=default_ttl_hours,
    )
