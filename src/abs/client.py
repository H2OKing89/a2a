"""
Audiobookshelf API client.
"""

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import urljoin

import httpx
from pydantic import ValidationError

from .models import (
    Author,
    LibrariesResponse,
    Library,
    LibraryItem,
    LibraryItemExpanded,
    LibraryItemMinified,
    LibraryItemsResponse,
    LibraryStats,
    Series,
    User,
)

# Import from cache module (SQLite-based)
if TYPE_CHECKING:
    from ..cache import SQLiteCache

logger = logging.getLogger(__name__)


class ABSError(Exception):
    """Base exception for ABS API errors."""

    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class ABSConnectionError(ABSError):
    """Connection error."""

    pass


class ABSAuthError(ABSError):
    """Authentication error."""

    pass


class ABSNotFoundError(ABSError):
    """Resource not found error."""

    pass


class ABSClient:
    """
    Audiobookshelf API client.

    Uses Bearer token authentication as documented in the ABS API.
    """

    def __init__(
        self,
        host: str,
        api_key: str,
        timeout: float = 30.0,
        rate_limit_delay: float = 0.1,
        cache: Optional["SQLiteCache"] = None,
        cache_ttl_hours: float = 2.0,
        # Deprecated: kept for backwards compatibility
        cache_dir: Path | None = None,
    ):
        """
        Initialize the ABS client.

        Args:
            host: ABS server URL (e.g., https://abs.example.com)
            api_key: API token for authentication
            timeout: Request timeout in seconds
            rate_limit_delay: Delay between requests
            cache: SQLiteCache instance for caching API responses
            cache_ttl_hours: Cache TTL in hours (default 2)
            cache_dir: Deprecated - use cache parameter instead
        """
        self.host = host.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0
        self._cache_ttl_seconds = cache_ttl_hours * 3600

        self._client = httpx.Client(
            base_url=self.host,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

        # Setup caching - prefer new SQLiteCache, fall back to legacy
        self._cache: Optional["SQLiteCache"] = cache
        if cache is None and cache_dir:
            # Legacy support: create SQLiteCache from cache_dir
            from ..cache import SQLiteCache

            db_path = Path(cache_dir) / "cache.db"
            self._cache = SQLiteCache(
                db_path=db_path,
                default_ttl_hours=cache_ttl_hours,
            )

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict:
        """
        Make an API request.

        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., /api/libraries)
            params: Query parameters
            json: JSON body

        Returns:
            Response JSON as dict

        Raises:
            ABSError: On API errors
        """
        self._rate_limit()

        url = f"/api{endpoint}" if not endpoint.startswith("/api") else endpoint

        logger.debug("ABS API request: %s %s params=%s", method, url, params)

        try:
            response = self._client.request(
                method=method,
                url=url,
                params=params,
                json=json,
            )
        except httpx.ConnectError as e:
            logger.error("ABS connection error: %s", e)
            raise ABSConnectionError(f"Failed to connect to {self.host}: {e}")
        except httpx.TimeoutException as e:
            logger.error("ABS timeout: %s", e)
            raise ABSConnectionError(f"Request timed out: {e}")

        if response.status_code == 401:
            logger.error("ABS auth error: 401 Unauthorized")
            raise ABSAuthError("Authentication failed. Check your API key.")
        elif response.status_code == 403:
            logger.error("ABS auth error: 403 Forbidden")
            raise ABSAuthError("Access forbidden. Insufficient permissions.")
        elif response.status_code == 404:
            logger.debug("ABS resource not found: %s", endpoint)
            raise ABSNotFoundError(f"Resource not found: {endpoint}")
        elif response.status_code >= 400:
            logger.error("ABS API error: %d for %s", response.status_code, endpoint)
            raise ABSError(
                f"API error: {response.status_code}",
                status_code=response.status_code,
                response=response.json() if response.content else None,
            )

        logger.debug("ABS API response: %d", response.status_code)

        if not response.content:
            return {}

        return response.json()

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """Make a GET request."""
        return self._request("GET", endpoint, params=params)

    def _post(self, endpoint: str, json: dict | None = None, params: dict | None = None) -> dict:
        """Make a POST request."""
        return self._request("POST", endpoint, json=json, params=params)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "ABSClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # =====================
    # Cache Utilities
    # =====================

    def clear_cache(self, namespace: str | None = None) -> int:
        """
        Clear cached data.

        Args:
            namespace: Specific namespace to clear (None = all ABS caches)

        Returns:
            Number of items cleared
        """
        if not self._cache:
            return 0

        if namespace:
            return self._cache.clear_namespace(namespace)
        else:
            # Clear all ABS namespaces
            count = 0
            for ns in ["abs_libraries", "abs_items", "abs_stats", "abs_authors", "abs_series"]:
                count += self._cache.clear_namespace(ns)
            return count

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        if not self._cache:
            return {"enabled": False}

        stats = self._cache.get_stats()
        # Filter to only show ABS namespaces
        abs_namespaces = {k: v for k, v in stats.get("namespaces", {}).items() if k.startswith("abs_")}
        stats["abs_namespaces"] = abs_namespaces
        return stats

    # =====================
    # Authentication / User
    # =====================

    def get_me(self) -> User:
        """
        Get the authenticated user.

        Returns:
            User: The authenticated user
        """
        data = self._get("/me")
        return User.model_validate(data)

    def authorize(self) -> dict:
        """
        Get authorized user and server information.

        Returns:
            Dict with user, userDefaultLibraryId, serverSettings
        """
        return self._post("/authorize")

    # =====================
    # Libraries
    # =====================

    def get_libraries(self) -> list[Library]:
        """
        Get all libraries accessible to the user.

        Returns:
            List of libraries
        """
        data = self._get("/libraries")
        response = LibrariesResponse.model_validate(data)
        return response.libraries

    def get_library(self, library_id: str, include_filterdata: bool = False) -> Library:
        """
        Get a specific library.

        Args:
            library_id: Library ID
            include_filterdata: Include filter data

        Returns:
            Library
        """
        params = {}
        if include_filterdata:
            params["include"] = "filterdata"

        data = self._get(f"/libraries/{library_id}", params=params if params else None)

        # If filterdata was requested, library is in 'library' key
        if include_filterdata and "library" in data:
            return Library.model_validate(data["library"])
        return Library.model_validate(data)

    def get_library_items(
        self,
        library_id: str,
        limit: int = 0,
        page: int = 0,
        sort: str | None = None,
        desc: bool = False,
        filter_by: str | None = None,
        minified: bool = True,
        collapseseries: bool = False,
        include: str | None = None,
    ) -> LibraryItemsResponse:
        """
        Get library items.

        Args:
            library_id: Library ID
            limit: Number of items per page (0 = no limit)
            page: Page number (0-indexed)
            sort: Sort field (e.g., media.metadata.title)
            desc: Sort descending
            filter_by: Filter string
            minified: Return minified items
            collapseseries: Collapse series
            include: Include additional data (rssfeed)

        Returns:
            LibraryItemsResponse with results
        """
        params = {
            "limit": limit,
            "page": page,
            "minified": 1 if minified else 0,
            "collapseseries": 1 if collapseseries else 0,
        }

        if sort:
            params["sort"] = sort
        if desc:
            params["desc"] = 1
        if filter_by:
            params["filter"] = filter_by
        if include:
            params["include"] = include

        data = self._get(f"/libraries/{library_id}/items", params=params)
        return LibraryItemsResponse.model_validate(data)

    def get_all_library_items(
        self,
        library_id: str,
        batch_size: int = 100,
        sort: str | None = None,
        desc: bool = False,
        filter_by: str | None = None,
    ) -> list[LibraryItemMinified]:
        """
        Get all library items using pagination.

        Args:
            library_id: Library ID
            batch_size: Items per request
            sort: Sort field
            desc: Sort descending
            filter_by: Filter string

        Yields:
            LibraryItemMinified for each item
        """
        all_items = []
        page = 0

        while True:
            response = self.get_library_items(
                library_id=library_id,
                limit=batch_size,
                page=page,
                sort=sort,
                desc=desc,
                filter_by=filter_by,
                minified=True,
            )

            all_items.extend(response.results)

            # Check if we've retrieved all items
            if len(all_items) >= response.total or len(response.results) == 0:
                break

            page += 1

        return all_items

    def get_library_stats(self, library_id: str, use_cache: bool = True) -> LibraryStats:
        """
        Get library statistics.

        Args:
            library_id: Library ID
            use_cache: Whether to use cached results

        Returns:
            LibraryStats
        """
        cache_key = f"stats_{library_id}"

        # Check cache
        if use_cache and self._cache:
            cached = self._cache.get("abs_stats", cache_key)
            if cached:
                return LibraryStats.model_validate(cached)

        data = self._get(f"/libraries/{library_id}/stats")
        stats = LibraryStats.model_validate(data)

        # Cache result
        if self._cache:
            self._cache.set("abs_stats", cache_key, stats.model_dump(), ttl_seconds=self._cache_ttl_seconds)

        return stats

    def get_library_authors(self, library_id: str, use_cache: bool = True) -> list[Author]:
        """
        Get all authors in a library.

        Args:
            library_id: Library ID
            use_cache: Whether to use cached results

        Returns:
            List of authors
        """
        cache_key = f"authors_{library_id}"

        # Check cache
        if use_cache and self._cache:
            cached = self._cache.get("abs_authors", cache_key)
            if cached:
                return [Author.model_validate(a) for a in cached]

        data = self._get(f"/libraries/{library_id}/authors")
        authors = [Author.model_validate(a) for a in data.get("authors", [])]

        # Cache result
        if self._cache:
            self._cache.set(
                "abs_authors", cache_key, [a.model_dump() for a in authors], ttl_seconds=self._cache_ttl_seconds
            )

        return authors

    def get_library_series(
        self,
        library_id: str,
        limit: int = 0,
        page: int = 0,
        sort: str | None = None,
        desc: bool = False,
    ) -> dict:
        """
        Get library series.

        Args:
            library_id: Library ID
            limit: Items per page
            page: Page number
            sort: Sort field
            desc: Sort descending

        Returns:
            Dict with results, total, limit, page
        """
        params = {"limit": limit, "page": page}
        if sort:
            params["sort"] = sort
        if desc:
            params["desc"] = 1

        return self._get(f"/libraries/{library_id}/series", params=params)

    def search_library(self, library_id: str, query: str, limit: int = 12) -> dict:
        """
        Search a library.

        Args:
            library_id: Library ID
            query: Search query
            limit: Max results

        Returns:
            Search results dict
        """
        params = {"q": query, "limit": limit}
        return self._get(f"/libraries/{library_id}/search", params=params)

    # =====================
    # Library Items
    # =====================

    def get_item(
        self,
        item_id: str,
        expanded: bool = True,
        include: str | None = None,
        use_cache: bool = True,
    ) -> LibraryItemExpanded:
        """
        Get a library item.

        Args:
            item_id: Item ID
            expanded: Return expanded item
            include: Include additional data (progress, rssfeed, authors)
            use_cache: Whether to use cached results

        Returns:
            LibraryItemExpanded
        """
        cache_key = f"item_{item_id}_exp{expanded}"

        # Check cache (only cache if no special includes)
        if use_cache and self._cache and not include:
            cached = self._cache.get("abs_items", cache_key)
            if cached:
                return LibraryItemExpanded.model_validate(cached)

        params = {"expanded": 1 if expanded else 0}
        if include:
            params["include"] = include

        data = self._get(f"/items/{item_id}", params=params)
        item = LibraryItemExpanded.model_validate(data)

        # Cache result (only if no special includes)
        if self._cache and not include:
            self._cache.set("abs_items", cache_key, item.model_dump(), ttl_seconds=self._cache_ttl_seconds)

        return item

    def batch_get_items(self, item_ids: list[str]) -> list[LibraryItemExpanded]:
        """
        Get multiple library items.

        Args:
            item_ids: List of item IDs

        Returns:
            List of LibraryItemExpanded
        """
        data = self._post("/items/batch/get", json={"libraryItemIds": item_ids})
        return [LibraryItemExpanded.model_validate(item) for item in data.get("libraryItems", [])]

    def batch_get_items_expanded(
        self,
        item_ids: list[str],
        use_cache: bool = True,
        max_workers: int = 10,
        progress_callback: Callable | None = None,
    ) -> list[dict]:
        """
        Get multiple library items with expanded data, using parallel requests.

        Uses ThreadPoolExecutor for concurrent fetching since this is typically
        hitting a local server without rate limits.

        Args:
            item_ids: List of item IDs
            use_cache: Use cached data if available
            max_workers: Number of parallel workers (default 10)
            progress_callback: Optional callback(completed, total) for progress updates

        Returns:
            List of expanded item dicts
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = {}
        cache_hits = 0
        to_fetch = []

        # First check cache for all items
        if use_cache and self._cache:
            for item_id in item_ids:
                cache_key = f"item_{item_id}_exp1"
                cached = self._cache.get("abs_items", cache_key)
                if cached:
                    results[item_id] = cached
                    cache_hits += 1
                else:
                    to_fetch.append(item_id)
        else:
            to_fetch = list(item_ids)

        # Fetch remaining items in parallel
        if to_fetch:

            def fetch_item(item_id: str) -> tuple[str, dict | None]:
                try:
                    # Direct request without rate limiting for speed
                    url = f"/api/items/{item_id}"
                    response = self._client.get(url, params={"expanded": 1})
                    if response.status_code == 200:
                        data = response.json()
                        # Cache the result
                        if self._cache:
                            cache_key = f"item_{item_id}_exp1"
                            self._cache.set("abs_items", cache_key, data, ttl_seconds=self._cache_ttl_seconds)
                        return (item_id, data)
                except Exception:
                    pass
                return (item_id, None)

            completed = cache_hits
            total = len(item_ids)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(fetch_item, item_id): item_id for item_id in to_fetch}

                for future in as_completed(futures):
                    item_id, data = future.result()
                    if data:
                        results[item_id] = data
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total)

        # Return in original order
        return [results.get(item_id) for item_id in item_ids if item_id in results]

    def scan_item(self, item_id: str) -> dict:
        """
        Scan a library item for changes.

        Args:
            item_id: Item ID

        Returns:
            Scan result
        """
        return self._post(f"/items/{item_id}/scan")

    def match_item(
        self,
        item_id: str,
        provider: str = "audible",
        title: str | None = None,
        author: str | None = None,
        asin: str | None = None,
        isbn: str | None = None,
        override_defaults: bool = False,
    ) -> dict:
        """
        Match a library item with metadata provider.

        Args:
            item_id: Item ID
            provider: Metadata provider
            title: Title to search
            author: Author to search
            asin: ASIN to search
            isbn: ISBN to search
            override_defaults: Override existing details

        Returns:
            Match result
        """
        body = {"provider": provider, "overrideDefaults": override_defaults}
        if title:
            body["title"] = title
        if author:
            body["author"] = author
        if asin:
            body["asin"] = asin
        if isbn:
            body["isbn"] = isbn

        return self._post(f"/items/{item_id}/match", json=body)

    # =====================
    # Authors
    # =====================

    def get_author(
        self,
        author_id: str,
        include: str | None = None,
        library_id: str | None = None,
    ) -> dict:
        """
        Get an author.

        Args:
            author_id: Author ID
            include: Include items, series
            library_id: Filter by library

        Returns:
            Author dict
        """
        params = {}
        if include:
            params["include"] = include
        if library_id:
            params["library"] = library_id

        return self._get(f"/authors/{author_id}", params=params if params else None)

    # =====================
    # Series
    # =====================

    def get_series(self, series_id: str, include: str | None = None) -> dict:
        """
        Get a series.

        Args:
            series_id: Series ID
            include: Include progress

        Returns:
            Series dict
        """
        params = {}
        if include:
            params["include"] = include

        return self._get(f"/series/{series_id}", params=params if params else None)

    # =====================
    # Search
    # =====================

    def search_books(
        self,
        title: str = "",
        author: str = "",
        provider: str = "audible",
    ) -> list[dict]:
        """
        Search for books using metadata provider.

        Args:
            title: Book title or ASIN
            author: Author name
            provider: Metadata provider

        Returns:
            List of search results
        """
        params = {"title": title, "author": author, "provider": provider}
        return self._get("/search/books", params=params)

    def search_authors(self, query: str) -> dict | None:
        """
        Search for an author.

        Args:
            query: Author name

        Returns:
            Author dict or None
        """
        return self._get("/search/authors", params={"q": query})

    # =====================
    # Enhanced Author Methods
    # =====================

    def get_author_with_items(
        self,
        author_id: str,
        include_series: bool = True,
        use_cache: bool = True,
    ) -> dict:
        """
        Get an author with their library items and series.

        This is useful for tracking favorite authors and finding
        all their books in your library.

        Args:
            author_id: Author ID
            include_series: Include series information
            use_cache: Use cached results

        Returns:
            Author dict with libraryItems and series arrays

        Example:
            author = client.get_author_with_items(author_id)
            print(f"{author['name']} has {len(author['libraryItems'])} books")
            for series in author.get('series', []):
                print(f"  Series: {series['name']}")
        """
        cache_key = f"author_items_{author_id}_{include_series}"

        if use_cache and self._cache:
            cached = self._cache.get("abs_authors", cache_key)
            if cached:
                logger.debug("Cache hit for author %s", author_id)
                return cached

        include_parts = ["items"]
        if include_series:
            include_parts.append("series")

        params = {"include": ",".join(include_parts)}
        result = self._get(f"/authors/{author_id}", params=params)

        if self._cache:
            self._cache.set("abs_authors", cache_key, result, ttl_seconds=self._cache_ttl_seconds)

        logger.debug(
            "Fetched author %s with %d items",
            result.get("name", author_id),
            len(result.get("libraryItems", [])),
        )
        return result

    # =====================
    # Enhanced Series Methods
    # =====================

    def get_series_with_progress(
        self,
        series_id: str,
        use_cache: bool = True,
    ) -> dict:
        """
        Get a series with progress information.

        Args:
            series_id: Series ID
            use_cache: Use cached results

        Returns:
            Series dict with progress info

        Example:
            series = client.get_series_with_progress(series_id)
            progress = series.get('progress', {})
            print(f"Finished: {len(progress.get('libraryItemIdsFinished', []))}")
        """
        cache_key = f"series_progress_{series_id}"

        if use_cache and self._cache:
            cached = self._cache.get("abs_series", cache_key)
            if cached:
                logger.debug("Cache hit for series %s", series_id)
                return cached

        result = self._get(f"/series/{series_id}", params={"include": "progress"})

        if self._cache:
            self._cache.set("abs_series", cache_key, result, ttl_seconds=self._cache_ttl_seconds)

        logger.debug("Fetched series %s", result.get("name", series_id))
        return result

    # =====================
    # Collection Management
    # =====================

    def get_collections(self) -> list[dict]:
        """
        Get all collections.

        Returns:
            List of collection dicts
        """
        result = self._get("/collections")
        collections = result.get("collections", [])
        logger.debug("Fetched %d collections", len(collections))
        return collections

    def get_collection(self, collection_id: str) -> dict:
        """
        Get a collection by ID.

        Args:
            collection_id: Collection ID

        Returns:
            Collection dict with books array
        """
        return self._get(f"/collections/{collection_id}")

    def create_collection(
        self,
        library_id: str,
        name: str,
        description: str | None = None,
        book_ids: list[str] | None = None,
    ) -> dict:
        """
        Create a new collection.

        Args:
            library_id: Library ID the collection belongs to
            name: Collection name
            description: Optional description
            book_ids: Optional list of book IDs to add

        Returns:
            Created collection dict

        Example:
            collection = client.create_collection(
                library_id="lib_xxx",
                name="Quality Upgrades Needed",
                description="Books that need quality upgrades from Audible"
            )
        """
        payload: dict[str, Any] = {
            "libraryId": library_id,
            "name": name,
        }
        if description:
            payload["description"] = description
        if book_ids:
            payload["books"] = book_ids

        result = self._post("/collections", json=payload)
        logger.info("Created collection '%s' (id=%s)", name, result.get("id"))
        return result

    def update_collection(
        self,
        collection_id: str,
        name: str | None = None,
        description: str | None = None,
        book_ids: list[str] | None = None,
    ) -> dict:
        """
        Update a collection.

        Args:
            collection_id: Collection ID
            name: New name (optional)
            description: New description (optional)
            book_ids: Replace book list (optional)

        Returns:
            Updated collection dict
        """
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if book_ids is not None:
            payload["books"] = book_ids

        result = self._request("PATCH", f"/collections/{collection_id}", json=payload)
        logger.info("Updated collection %s", collection_id)
        return result

    def delete_collection(self, collection_id: str) -> bool:
        """
        Delete a collection.

        Args:
            collection_id: Collection ID

        Returns:
            True if deleted successfully
        """
        self._request("DELETE", f"/collections/{collection_id}")
        logger.info("Deleted collection %s", collection_id)
        return True

    def add_book_to_collection(self, collection_id: str, book_id: str) -> dict:
        """
        Add a single book to a collection.

        Args:
            collection_id: Collection ID
            book_id: Library item ID to add

        Returns:
            Updated collection dict
        """
        result = self._post(f"/collections/{collection_id}/book", json={"id": book_id})
        logger.debug("Added book %s to collection %s", book_id, collection_id)
        return result

    def remove_book_from_collection(self, collection_id: str, book_id: str) -> dict:
        """
        Remove a book from a collection.

        Args:
            collection_id: Collection ID
            book_id: Library item ID to remove

        Returns:
            Updated collection dict
        """
        result = self._request("DELETE", f"/collections/{collection_id}/book/{book_id}")
        logger.debug("Removed book %s from collection %s", book_id, collection_id)
        return result

    def batch_add_to_collection(self, collection_id: str, book_ids: list[str]) -> dict:
        """
        Add multiple books to a collection.

        Args:
            collection_id: Collection ID
            book_ids: List of library item IDs to add

        Returns:
            Updated collection dict
        """
        result = self._post(f"/collections/{collection_id}/batch/add", json={"books": book_ids})
        logger.info("Added %d books to collection %s", len(book_ids), collection_id)
        return result

    def batch_remove_from_collection(self, collection_id: str, book_ids: list[str]) -> dict:
        """
        Remove multiple books from a collection.

        Args:
            collection_id: Collection ID
            book_ids: List of library item IDs to remove

        Returns:
            Updated collection dict
        """
        result = self._post(f"/collections/{collection_id}/batch/remove", json={"books": book_ids})
        logger.info("Removed %d books from collection %s", len(book_ids), collection_id)
        return result

    # =====================
    # Utility Methods
    # =====================

    def find_or_create_collection(
        self,
        library_id: str,
        name: str,
        description: str | None = None,
    ) -> dict:
        """
        Find a collection by name or create it if it doesn't exist.

        Useful for ensuring a collection exists before adding books.

        Args:
            library_id: Library ID
            name: Collection name to find or create
            description: Description if creating new

        Returns:
            Collection dict (existing or newly created)

        Example:
            collection = client.find_or_create_collection(
                library_id,
                "Upgrade Candidates - Low Quality"
            )
            client.batch_add_to_collection(collection['id'], book_ids)
        """
        collections = self.get_collections()

        # Find existing collection with same name in this library
        for col in collections:
            if col.get("name") == name and col.get("libraryId") == library_id:
                logger.debug("Found existing collection '%s'", name)
                return col

        # Create new collection
        return self.create_collection(library_id, name, description)
