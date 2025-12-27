"""
SQLite-based caching for API responses.

Provides efficient storage and retrieval of cached data with:
- TTL-based expiration
- Indexed lookups by key, namespace, and common fields
- Full-text search capability
- Cross-referencing between data sources
"""

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import orjson


class SQLiteCache:
    """
    SQLite-based cache for API responses.

    Features:
    - Namespace support for different data types (abs_items, audible_library, etc.)
    - TTL-based expiration with efficient cleanup
    - Indexed lookups by key and common metadata fields
    - Full-text search on titles and authors
    - Memory cache layer for hot data

    Example:
        cache = SQLiteCache("./data/cache.db")

        # Store data
        cache.set("audible_library", "B08XYZ123", book_data, ttl_hours=2)

        # Retrieve
        data = cache.get("audible_library", "B08XYZ123")

        # Search
        results = cache.search_by_title("Project Hail Mary")
    """

    def __init__(
        self,
        db_path: Path | str,
        default_ttl_hours: float = 2.0,
        max_memory_entries: int = 500,
    ):
        """
        Initialize the SQLite cache.

        Args:
            db_path: Path to SQLite database file
            default_ttl_hours: Default TTL in hours for cached items
            max_memory_entries: Maximum entries to keep in memory cache
        """
        self.db_path = Path(db_path)
        self.default_ttl_seconds = default_ttl_hours * 3600
        self.max_memory_entries = max_memory_entries

        # In-memory cache for frequently accessed items
        self._memory_cache: dict[str, tuple[Any, float]] = {}  # key -> (data, expires_at)

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                -- Main cache table
                CREATE TABLE IF NOT EXISTS cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,

                    -- Metadata for searching (extracted from data)
                    asin TEXT,
                    title TEXT,
                    author TEXT,
                    source TEXT,  -- 'abs' or 'audible'

                    UNIQUE(namespace, key)
                );

                -- Indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_cache_namespace_key
                    ON cache(namespace, key);
                CREATE INDEX IF NOT EXISTS idx_cache_expires
                    ON cache(expires_at);
                CREATE INDEX IF NOT EXISTS idx_cache_asin
                    ON cache(asin) WHERE asin IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_cache_source_asin
                    ON cache(source, asin) WHERE asin IS NOT NULL;

                -- Full-text search table
                CREATE VIRTUAL TABLE IF NOT EXISTS cache_fts USING fts5(
                    title,
                    author,
                    namespace,
                    key,
                    content='cache',
                    content_rowid='id'
                );

                -- Triggers to keep FTS in sync
                CREATE TRIGGER IF NOT EXISTS cache_ai AFTER INSERT ON cache BEGIN
                    INSERT INTO cache_fts(rowid, title, author, namespace, key)
                    VALUES (new.id, new.title, new.author, new.namespace, new.key);
                END;

                CREATE TRIGGER IF NOT EXISTS cache_ad AFTER DELETE ON cache BEGIN
                    INSERT INTO cache_fts(cache_fts, rowid, title, author, namespace, key)
                    VALUES ('delete', old.id, old.title, old.author, old.namespace, old.key);
                END;

                CREATE TRIGGER IF NOT EXISTS cache_au AFTER UPDATE ON cache BEGIN
                    INSERT INTO cache_fts(cache_fts, rowid, title, author, namespace, key)
                    VALUES ('delete', old.id, old.title, old.author, old.namespace, old.key);
                    INSERT INTO cache_fts(rowid, title, author, namespace, key)
                    VALUES (new.id, new.title, new.author, new.namespace, new.key);
                END;

                -- Cross-reference table for ABS <-> Audible mapping
                CREATE TABLE IF NOT EXISTS asin_mapping (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT NOT NULL UNIQUE,
                    abs_id TEXT,
                    abs_path TEXT,
                    audible_asin TEXT,
                    title TEXT,
                    author TEXT,
                    match_confidence REAL,  -- 0.0 to 1.0
                    matched_at REAL,
                    UNIQUE(abs_id)
                );

                CREATE INDEX IF NOT EXISTS idx_mapping_asin
                    ON asin_mapping(asin);
                CREATE INDEX IF NOT EXISTS idx_mapping_abs_id
                    ON asin_mapping(abs_id) WHERE abs_id IS NOT NULL;
            """
            )

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Get a database connection with proper settings."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            isolation_level=None,  # Autocommit mode
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
        conn.execute("PRAGMA synchronous=NORMAL")  # Good balance of safety/speed
        try:
            yield conn
        finally:
            conn.close()

    def _memory_key(self, namespace: str, key: str) -> str:
        """Generate memory cache key."""
        return f"{namespace}:{key}"

    def _extract_metadata(self, data: dict | list, namespace: str) -> dict:
        """Extract searchable metadata from cached data."""
        metadata = {
            "asin": None,
            "title": None,
            "author": None,
            "source": None,
        }

        # Determine source from namespace
        if namespace.startswith("abs_"):
            metadata["source"] = "abs"
        elif namespace.startswith("audible") or namespace in ("library", "catalog", "search"):
            metadata["source"] = "audible"

        # Handle list data (e.g., library items) - no metadata extraction for lists
        if isinstance(data, list):
            return metadata

        # Extract ASIN
        metadata["asin"] = data.get("asin")

        # Extract title - handle different data structures
        if "title" in data:
            metadata["title"] = data["title"]
        elif "media" in data and "metadata" in data["media"]:
            metadata["title"] = data["media"]["metadata"].get("title")

        # Extract author
        if "authors" in data and data["authors"]:
            if isinstance(data["authors"][0], dict):
                metadata["author"] = data["authors"][0].get("name")
            else:
                metadata["author"] = str(data["authors"][0])
        elif "primary_author" in data:
            metadata["author"] = data["primary_author"]
        elif "media" in data and "metadata" in data["media"]:
            metadata["author"] = data["media"]["metadata"].get("authorName")

        return metadata

    # -------------------------------------------------------------------------
    # Core Cache Operations
    # -------------------------------------------------------------------------

    def get(
        self,
        namespace: str,
        key: str,
        ignore_expired: bool = False,
    ) -> Any | None:
        """
        Get an item from cache.

        Args:
            namespace: Cache namespace
            key: Unique identifier
            ignore_expired: If True, return even if expired

        Returns:
            Cached data or None if not found/expired
        """
        mem_key = self._memory_key(namespace, key)
        now = time.time()

        # Check memory cache first
        if mem_key in self._memory_cache:
            data, expires_at = self._memory_cache[mem_key]
            if ignore_expired or expires_at > now:
                return data
            else:
                del self._memory_cache[mem_key]

        # Check database
        with self._get_connection() as conn:
            if ignore_expired:
                row = conn.execute(
                    "SELECT data FROM cache WHERE namespace = ? AND key = ?", (namespace, key)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT data, expires_at FROM cache WHERE namespace = ? AND key = ? AND expires_at > ?",
                    (namespace, key, now),
                ).fetchone()

            if row:
                data = orjson.loads(row["data"])
                expires_at = row["expires_at"] if "expires_at" in row.keys() else now + 3600

                # Add to memory cache
                self._add_to_memory(mem_key, data, expires_at)
                return data

        return None

    def set(
        self,
        namespace: str,
        key: str,
        data: Any,
        ttl_seconds: float | None = None,
    ) -> None:
        """
        Store an item in cache.

        Args:
            namespace: Cache namespace
            key: Unique identifier
            data: Data to cache (must be JSON-serializable)
            ttl_seconds: Custom TTL in seconds
        """
        if ttl_seconds is None:
            ttl_seconds = self.default_ttl_seconds

        now = time.time()
        expires_at = now + ttl_seconds

        # Convert Pydantic models to dict
        if hasattr(data, "model_dump"):
            data = data.model_dump()

        # Extract metadata
        metadata = self._extract_metadata(data, namespace)

        # Serialize data
        data_json = orjson.dumps(data).decode("utf-8")

        # Store in database
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO cache (namespace, key, data, created_at, expires_at, asin, title, author, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET
                    data = excluded.data,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at,
                    asin = excluded.asin,
                    title = excluded.title,
                    author = excluded.author,
                    source = excluded.source
            """,
                (
                    namespace,
                    key,
                    data_json,
                    now,
                    expires_at,
                    metadata["asin"],
                    metadata["title"],
                    metadata["author"],
                    metadata["source"],
                ),
            )

        # Add to memory cache
        mem_key = self._memory_key(namespace, key)
        self._add_to_memory(mem_key, data, expires_at)

    def _add_to_memory(self, key: str, data: Any, expires_at: float) -> None:
        """Add to memory cache with LRU eviction."""
        self._memory_cache[key] = (data, expires_at)

        # Evict if over limit
        if len(self._memory_cache) > self.max_memory_entries:
            # Remove oldest entries
            sorted_keys = sorted(
                self._memory_cache.keys(), key=lambda k: self._memory_cache[k][1]  # Sort by expires_at
            )
            for k in sorted_keys[: len(sorted_keys) // 4]:
                del self._memory_cache[k]

    def delete(self, namespace: str, key: str) -> bool:
        """
        Delete an item from cache.

        Returns:
            True if item was deleted
        """
        mem_key = self._memory_key(namespace, key)
        self._memory_cache.pop(mem_key, None)

        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM cache WHERE namespace = ? AND key = ?", (namespace, key))
            return cursor.rowcount > 0

    def clear_namespace(self, namespace: str) -> int:
        """Clear all items in a namespace."""
        # Clear from memory
        keys_to_delete = [k for k in self._memory_cache if k.startswith(f"{namespace}:")]
        for k in keys_to_delete:
            del self._memory_cache[k]

        # Clear from database
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM cache WHERE namespace = ?", (namespace,))
            return cursor.rowcount

    def delete_by_pattern(self, namespace: str, key_pattern: str) -> int:
        """
        Delete cache entries matching a key pattern.

        Args:
            namespace: Cache namespace
            key_pattern: SQL LIKE pattern (use % for wildcard)
                        Example: "wishlist_%" deletes all wishlist entries
                        Example: "item_B08%_%" deletes items starting with B08

        Returns:
            Number of entries deleted
        """
        # Clear matching entries from memory cache
        prefix = f"{namespace}:"
        # Convert SQL pattern to simple prefix matching for memory cache
        simple_prefix = key_pattern.rstrip("%")
        keys_to_delete = [
            k for k in self._memory_cache if k.startswith(prefix) and k[len(prefix) :].startswith(simple_prefix)
        ]
        for k in keys_to_delete:
            del self._memory_cache[k]

        # Delete from database using LIKE pattern
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE namespace = ? AND key LIKE ?",
                (namespace, key_pattern),
            )
            return cursor.rowcount

    def delete_by_asin(self, asin: str, namespaces: list[str] | None = None) -> int:
        """
        Delete all cache entries for a specific ASIN.

        Useful when data for an item has changed (e.g., added to library,
        price changed, etc.) and all related cache entries should be invalidated.

        Args:
            asin: The ASIN to invalidate
            namespaces: Optional list of namespaces to clear (None = all)

        Returns:
            Number of entries deleted
        """
        # Clear from memory cache
        deleted_count = 0
        keys_to_check = list(self._memory_cache.keys())
        for mem_key in keys_to_check:
            ns, key = mem_key.split(":", 1)
            if namespaces and ns not in namespaces:
                continue
            # Check if key contains the ASIN
            if asin in key:
                del self._memory_cache[mem_key]
                deleted_count += 1

        # Delete from database
        with self._get_connection() as conn:
            if namespaces:
                # Use multiple OR conditions instead of IN with dynamic placeholders
                # This avoids potential SQL injection flagged by bandit
                for ns in namespaces:
                    cursor = conn.execute(
                        "DELETE FROM cache WHERE asin = ? AND namespace = ?",  # nosec B608
                        (asin, ns),
                    )
                    deleted_count += cursor.rowcount
            else:
                cursor = conn.execute("DELETE FROM cache WHERE asin = ?", (asin,))
                deleted_count += cursor.rowcount

        return deleted_count

    def invalidate_related(self, asin: str) -> dict[str, int]:
        """
        Invalidate all cache entries related to an ASIN across all namespaces.

        This is the recommended way to invalidate data when something changes
        (e.g., book added to library, price changed, wishlist modified).

        Args:
            asin: The ASIN whose related entries should be invalidated

        Returns:
            Dict with counts per namespace: {"audible_enrichment": 1, "library": 1, ...}
        """
        invalidated: dict[str, int] = {}

        with self._get_connection() as conn:
            # Find all related entries
            rows = conn.execute(
                """
                SELECT DISTINCT namespace FROM cache
                WHERE asin = ? OR key LIKE ?
                """,
                (asin, f"%{asin}%"),
            ).fetchall()

            namespaces = [row["namespace"] for row in rows]

            for ns in namespaces:
                # Delete from this namespace
                cursor = conn.execute(
                    """
                    DELETE FROM cache
                    WHERE namespace = ? AND (asin = ? OR key LIKE ?)
                    """,
                    (ns, asin, f"%{asin}%"),
                )
                if cursor.rowcount > 0:
                    invalidated[ns] = cursor.rowcount

        # Also clear memory cache
        keys_to_delete = [k for k in self._memory_cache if asin in k]
        for k in keys_to_delete:
            del self._memory_cache[k]

        return invalidated

    def touch(self, namespace: str, key: str, extend_ttl_seconds: float | None = None) -> bool:
        """
        Refresh the TTL of a cached item without modifying its data.

        Args:
            namespace: Cache namespace
            key: Cache key
            extend_ttl_seconds: New TTL in seconds (default: use default_ttl_seconds)

        Returns:
            True if item was found and updated
        """
        if extend_ttl_seconds is None:
            extend_ttl_seconds = self.default_ttl_seconds

        new_expires_at = time.time() + extend_ttl_seconds

        # Update memory cache
        mem_key = self._memory_key(namespace, key)
        if mem_key in self._memory_cache:
            data, _ = self._memory_cache[mem_key]
            self._memory_cache[mem_key] = (data, new_expires_at)

        # Update database
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE cache SET expires_at = ? WHERE namespace = ? AND key = ?",
                (new_expires_at, namespace, key),
            )
            return cursor.rowcount > 0

    def clear_all(self) -> int:
        """Clear all cached items."""
        self._memory_cache.clear()

        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM cache")
            return cursor.rowcount

    def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        now = time.time()

        # Clean memory cache
        expired_keys = [k for k, (_, expires_at) in self._memory_cache.items() if expires_at <= now]
        for k in expired_keys:
            del self._memory_cache[k]

        # Clean database
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM cache WHERE expires_at <= ?", (now,))
            return cursor.rowcount

    # -------------------------------------------------------------------------
    # Search Operations
    # -------------------------------------------------------------------------

    def search_by_asin(self, asin: str, source: str | None = None) -> list[dict]:
        """
        Find cached items by ASIN.

        Args:
            asin: ASIN to search for
            source: Filter by source ('abs' or 'audible')

        Returns:
            List of matching cached data
        """
        now = time.time()

        with self._get_connection() as conn:
            if source:
                rows = conn.execute(
                    "SELECT namespace, key, data FROM cache WHERE asin = ? AND source = ? AND expires_at > ?",
                    (asin, source, now),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT namespace, key, data FROM cache WHERE asin = ? AND expires_at > ?", (asin, now)
                ).fetchall()

            return [
                {"namespace": row["namespace"], "key": row["key"], "data": orjson.loads(row["data"])} for row in rows
            ]

    def search_by_title(self, query: str, limit: int = 20) -> list[dict]:
        """
        Full-text search by title.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching items with relevance scores
        """
        now = time.time()

        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT c.namespace, c.key, c.data, c.title, c.author,
                       bm25(cache_fts) as score
                FROM cache_fts
                JOIN cache c ON cache_fts.rowid = c.id
                WHERE cache_fts MATCH ? AND c.expires_at > ?
                ORDER BY score
                LIMIT ?
            """,
                (f'title:"{query}"*', now, limit),
            ).fetchall()

            return [
                {
                    "namespace": row["namespace"],
                    "key": row["key"],
                    "title": row["title"],
                    "author": row["author"],
                    "score": row["score"],
                    "data": orjson.loads(row["data"]),
                }
                for row in rows
            ]

    def search_fts(self, query: str, limit: int = 20) -> list[dict]:
        """
        Full-text search across title and author.

        Args:
            query: Search query
            limit: Maximum results
        """
        now = time.time()

        with self._get_connection() as conn:
            # Escape special FTS characters and add wildcards
            safe_query = query.replace('"', '""')
            rows = conn.execute(
                """
                SELECT c.namespace, c.key, c.data, c.title, c.author,
                       bm25(cache_fts) as score
                FROM cache_fts
                JOIN cache c ON cache_fts.rowid = c.id
                WHERE cache_fts MATCH ? AND c.expires_at > ?
                ORDER BY score
                LIMIT ?
            """,
                (f'"{safe_query}"*', now, limit),
            ).fetchall()

            return [
                {
                    "namespace": row["namespace"],
                    "key": row["key"],
                    "title": row["title"],
                    "author": row["author"],
                    "score": row["score"],
                    "data": orjson.loads(row["data"]),
                }
                for row in rows
            ]

    # -------------------------------------------------------------------------
    # ASIN Mapping (ABS <-> Audible cross-reference)
    # -------------------------------------------------------------------------

    def set_asin_mapping(
        self,
        asin: str,
        abs_id: str | None = None,
        abs_path: str | None = None,
        audible_asin: str | None = None,
        title: str | None = None,
        author: str | None = None,
        confidence: float = 1.0,
    ) -> None:
        """
        Store an ASIN mapping between ABS and Audible.

        Args:
            asin: Primary ASIN (usually from metadata)
            abs_id: ABS library item ID
            abs_path: ABS file path
            audible_asin: Audible ASIN (may differ from metadata)
            title: Book title
            author: Author name
            confidence: Match confidence (0.0 to 1.0)
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO asin_mapping (asin, abs_id, abs_path, audible_asin, title, author, match_confidence, matched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asin) DO UPDATE SET
                    abs_id = COALESCE(excluded.abs_id, asin_mapping.abs_id),
                    abs_path = COALESCE(excluded.abs_path, asin_mapping.abs_path),
                    audible_asin = COALESCE(excluded.audible_asin, asin_mapping.audible_asin),
                    title = COALESCE(excluded.title, asin_mapping.title),
                    author = COALESCE(excluded.author, asin_mapping.author),
                    match_confidence = excluded.match_confidence,
                    matched_at = excluded.matched_at
            """,
                (asin, abs_id, abs_path, audible_asin, title, author, confidence, time.time()),
            )

    def get_asin_mapping(self, asin: str) -> dict | None:
        """Get ASIN mapping by ASIN."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM asin_mapping WHERE asin = ?", (asin,)).fetchone()

            if row:
                return dict(row)
        return None

    def get_mapping_by_abs_id(self, abs_id: str) -> dict | None:
        """Get ASIN mapping by ABS item ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM asin_mapping WHERE abs_id = ?", (abs_id,)).fetchone()

            if row:
                return dict(row)
        return None

    def get_unmapped_abs_items(self) -> list[dict]:
        """Get ABS items that don't have Audible mappings."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT c.key, c.data, c.title, c.author
                FROM cache c
                LEFT JOIN asin_mapping m ON c.key = m.abs_id
                WHERE c.namespace LIKE 'abs_%'
                  AND c.expires_at > ?
                  AND m.audible_asin IS NULL
            """,
                (time.time(),),
            ).fetchall()

            return [
                {
                    "abs_id": row["key"],
                    "title": row["title"],
                    "author": row["author"],
                    "data": orjson.loads(row["data"]),
                }
                for row in rows
            ]

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._get_connection() as conn:
            # Total counts
            total = conn.execute("SELECT COUNT(*) as count FROM cache").fetchone()["count"]

            # By namespace
            namespaces = {}
            for row in conn.execute("SELECT namespace, COUNT(*) as count FROM cache GROUP BY namespace").fetchall():
                namespaces[row["namespace"]] = row["count"]

            # Expired count
            now = time.time()
            expired = conn.execute("SELECT COUNT(*) as count FROM cache WHERE expires_at <= ?", (now,)).fetchone()[
                "count"
            ]

            # Mapping stats
            mapping_count = conn.execute("SELECT COUNT(*) as count FROM asin_mapping").fetchone()["count"]

            matched_count = conn.execute(
                "SELECT COUNT(*) as count FROM asin_mapping WHERE audible_asin IS NOT NULL"
            ).fetchone()["count"]

            # Database size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            "enabled": True,
            "backend": "sqlite",
            "db_path": str(self.db_path),
            "db_size_mb": round(db_size / (1024 * 1024), 2),
            "total_entries": total,
            "expired_entries": expired,
            "memory_entries": len(self._memory_cache),
            "namespaces": namespaces,
            "asin_mappings": mapping_count,
            "matched_items": matched_count,
        }

    # -------------------------------------------------------------------------
    # Convenience Methods (compatible with old interface)
    # -------------------------------------------------------------------------

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
