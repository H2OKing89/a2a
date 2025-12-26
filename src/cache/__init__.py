"""
Caching module for API responses.

Provides SQLite-based caching with:
- TTL-based expiration
- Namespace support for different data sources
- Full-text search on titles and authors
- ASIN cross-referencing between ABS and Audible
"""

from .sqlite_cache import SQLiteCache

__all__ = ["SQLiteCache"]


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
