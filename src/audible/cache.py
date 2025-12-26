"""
Caching layer for Audible API responses with TTL support.

Implements file-based caching with configurable TTL to avoid
excessive API calls and respect rate limits.
"""

import hashlib
import json
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Generic, Optional, TypeVar

import orjson

T = TypeVar("T")


class CacheEntry(Generic[T]):
    """A cached item with metadata."""

    def __init__(
        self,
        data: T,
        timestamp: float,
        ttl_seconds: float,
        key: str,
    ):
        self.data = data
        self.timestamp = timestamp
        self.ttl_seconds = ttl_seconds
        self.key = key

    @property
    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return time.time() > (self.timestamp + self.ttl_seconds)

    @property
    def expires_at(self) -> datetime:
        """When this entry expires (timezone-aware UTC)."""
        return datetime.fromtimestamp(self.timestamp + self.ttl_seconds, tz=timezone.utc)

    @property
    def age_seconds(self) -> float:
        """Age of this cache entry in seconds."""
        return time.time() - self.timestamp

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "data": self.data,
            "timestamp": self.timestamp,
            "ttl_seconds": self.ttl_seconds,
            "key": self.key,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CacheEntry":
        """Deserialize from storage."""
        return cls(
            data=d["data"],
            timestamp=d["timestamp"],
            ttl_seconds=d["ttl_seconds"],
            key=d["key"],
        )


class AudibleCache:
    """
    File-based cache for Audible API responses.

    Features:
    - TTL-based expiration
    - Automatic cleanup of expired entries
    - Namespace support for different data types
    - Memory + disk caching hybrid
    """

    def __init__(
        self,
        cache_dir: Path,
        default_ttl_days: int = 10,
        max_memory_entries: int = 1000,
    ):
        """
        Initialize the cache.

        Args:
            cache_dir: Directory to store cache files
            default_ttl_days: Default TTL in days for cached items
            max_memory_entries: Maximum entries to keep in memory
        """
        self.cache_dir = Path(cache_dir)
        self.default_ttl_seconds = default_ttl_days * 24 * 60 * 60
        self.max_memory_entries = max_memory_entries

        # In-memory cache for fast access
        self._memory_cache: dict[str, CacheEntry] = {}

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Namespaces for organization
        self.namespaces = {
            "library": "library",  # User library items
            "catalog": "catalog",  # Catalog lookups by ASIN
            "search": "search",  # Search results
            "stats": "stats",  # User statistics
            "account": "account",  # Account info
        }

    def _get_cache_key(self, namespace: str, identifier: str) -> str:
        """Generate a unique cache key."""
        return f"{namespace}:{identifier}"

    def _get_cache_path(self, namespace: str, identifier: str) -> Path:
        """Get file path for a cached item."""
        # Create namespace directory
        ns_dir = self.cache_dir / namespace
        ns_dir.mkdir(exist_ok=True)

        # Hash the identifier for safe filename
        safe_id = hashlib.sha256(identifier.encode()).hexdigest()[:32]
        return ns_dir / f"{safe_id}.json"

    def get(
        self,
        namespace: str,
        identifier: str,
        ignore_expired: bool = False,
    ) -> Any | None:
        """
        Get an item from cache.

        Args:
            namespace: Cache namespace (library, catalog, etc.)
            identifier: Unique identifier (ASIN, query hash, etc.)
            ignore_expired: If True, return even if expired

        Returns:
            Cached data or None if not found/expired
        """
        cache_key = self._get_cache_key(namespace, identifier)

        # Check memory cache first
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if ignore_expired or not entry.is_expired:
                return entry.data
            else:
                # Expired, remove from memory
                del self._memory_cache[cache_key]

        # Check disk cache
        cache_path = self._get_cache_path(namespace, identifier)
        if cache_path.exists():
            try:
                with open(cache_path, "rb") as f:
                    data = orjson.loads(f.read())
                entry = CacheEntry.from_dict(data)

                if ignore_expired or not entry.is_expired:
                    # Add to memory cache
                    self._add_to_memory(cache_key, entry)
                    return entry.data
                else:
                    # Expired, delete file
                    cache_path.unlink()
            except (json.JSONDecodeError, KeyError, OSError):
                # Corrupted cache file, delete it
                cache_path.unlink(missing_ok=True)

        return None

    def set(
        self,
        namespace: str,
        identifier: str,
        data: Any,
        ttl_seconds: float | None = None,
    ) -> None:
        """
        Store an item in cache.

        Args:
            namespace: Cache namespace
            identifier: Unique identifier
            data: Data to cache (must be JSON-serializable)
            ttl_seconds: Custom TTL in seconds (uses default if None)
        """
        if ttl_seconds is None:
            ttl_seconds = self.default_ttl_seconds

        cache_key = self._get_cache_key(namespace, identifier)

        entry = CacheEntry(
            data=data,
            timestamp=time.time(),
            ttl_seconds=ttl_seconds,
            key=cache_key,
        )

        # Add to memory cache
        self._add_to_memory(cache_key, entry)

        # Write to disk
        cache_path = self._get_cache_path(namespace, identifier)
        try:
            with open(cache_path, "wb") as f:
                f.write(orjson.dumps(entry.to_dict()))
        except OSError as e:
            # Log but don't fail
            pass

    def _add_to_memory(self, cache_key: str, entry: CacheEntry) -> None:
        """Add entry to memory cache with LRU eviction."""
        self._memory_cache[cache_key] = entry

        # Evict oldest entries if over limit
        if len(self._memory_cache) > self.max_memory_entries:
            # Remove oldest entries (by timestamp)
            sorted_keys = sorted(
                self._memory_cache.keys(),
                key=lambda k: self._memory_cache[k].timestamp,
            )
            for key in sorted_keys[: len(sorted_keys) // 4]:  # Remove 25%
                del self._memory_cache[key]

    def delete(self, namespace: str, identifier: str) -> bool:
        """
        Delete an item from cache.

        Returns:
            True if item was deleted, False if not found
        """
        cache_key = self._get_cache_key(namespace, identifier)

        # Remove from memory
        deleted = cache_key in self._memory_cache
        self._memory_cache.pop(cache_key, None)

        # Remove from disk
        cache_path = self._get_cache_path(namespace, identifier)
        if cache_path.exists():
            cache_path.unlink()
            deleted = True

        return deleted

    def clear_namespace(self, namespace: str) -> int:
        """
        Clear all cached items in a namespace.

        Returns:
            Number of items deleted
        """
        count = 0

        # Clear from memory
        keys_to_delete = [k for k in self._memory_cache.keys() if k.startswith(f"{namespace}:")]
        for key in keys_to_delete:
            del self._memory_cache[key]
            count += 1

        # Clear from disk
        ns_dir = self.cache_dir / namespace
        if ns_dir.exists():
            for cache_file in ns_dir.glob("*.json"):
                cache_file.unlink()
                count += 1

        return count

    def clear_all(self) -> int:
        """
        Clear all cached items.

        Returns:
            Number of items deleted
        """
        count = len(self._memory_cache)
        self._memory_cache.clear()

        # Clear all namespace directories
        for namespace in self.namespaces.values():
            ns_dir = self.cache_dir / namespace
            if ns_dir.exists():
                for cache_file in ns_dir.glob("*.json"):
                    cache_file.unlink()
                    count += 1

        return count

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of expired items removed
        """
        count = 0

        # Clean memory cache
        expired_keys = [k for k, v in self._memory_cache.items() if v.is_expired]
        for key in expired_keys:
            del self._memory_cache[key]
            count += 1

        # Clean disk cache
        for namespace in self.namespaces.values():
            ns_dir = self.cache_dir / namespace
            if not ns_dir.exists():
                continue

            for cache_file in ns_dir.glob("*.json"):
                try:
                    with open(cache_file, "rb") as f:
                        data = orjson.loads(f.read())
                    entry = CacheEntry.from_dict(data)
                    if entry.is_expired:
                        cache_file.unlink()
                        count += 1
                except (json.JSONDecodeError, KeyError, OSError):
                    # Corrupted file, delete it
                    cache_file.unlink(missing_ok=True)
                    count += 1

        return count

    def get_stats(self) -> dict:
        """Get cache statistics."""
        stats = {
            "memory_entries": len(self._memory_cache),
            "disk_entries": 0,
            "namespaces": {},
        }

        for namespace in self.namespaces.values():
            ns_dir = self.cache_dir / namespace
            if ns_dir.exists():
                file_count = len(list(ns_dir.glob("*.json")))
                stats["namespaces"][namespace] = file_count
                stats["disk_entries"] += file_count

        return stats

    # Convenience methods for common operations

    def get_library_item(self, asin: str) -> dict | None:
        """Get cached library item by ASIN."""
        return self.get("library", asin)

    def set_library_item(self, asin: str, data: dict, ttl_seconds: float | None = None) -> None:
        """Cache a library item."""
        self.set("library", asin, data, ttl_seconds)

    def get_catalog_product(self, asin: str) -> dict | None:
        """Get cached catalog product by ASIN."""
        return self.get("catalog", asin)

    def set_catalog_product(self, asin: str, data: dict, ttl_seconds: float | None = None) -> None:
        """Cache a catalog product."""
        self.set("catalog", asin, data, ttl_seconds)

    def get_search_results(self, query_hash: str) -> dict | None:
        """Get cached search results."""
        return self.get("search", query_hash)

    def set_search_results(self, query_hash: str, data: dict, ttl_seconds: float | None = None) -> None:
        """Cache search results."""
        self.set("search", query_hash, data, ttl_seconds)


def cached(
    namespace: str,
    key_func: Callable[..., str],
    ttl_seconds: float | None = None,
):
    """
    Decorator to cache method results.

    Args:
        namespace: Cache namespace
        key_func: Function to generate cache key from method args
        ttl_seconds: Optional TTL override

    Example:
        @cached("catalog", lambda self, asin: asin)
        async def get_product(self, asin: str) -> AudibleCatalogProduct:
            ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get cache from self (assumes client has cache attribute)
            cache: AudibleCache | None = getattr(self, "_cache", None)
            if cache is None:
                return func(self, *args, **kwargs)

            # Generate cache key
            cache_key = key_func(self, *args, **kwargs)

            # Check cache
            cached_data = cache.get(namespace, cache_key)
            if cached_data is not None:
                return cached_data

            # Call function and cache result
            result = func(self, *args, **kwargs)
            if result is not None:
                # Convert to dict if it's a pydantic model
                if hasattr(result, "model_dump"):
                    cache.set(namespace, cache_key, result.model_dump(), ttl_seconds)
                else:
                    cache.set(namespace, cache_key, result, ttl_seconds)

            return result

        return wrapper

    return decorator
