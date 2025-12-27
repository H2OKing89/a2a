"""
Asynchronous Audiobookshelf API client.

Provides async versions of ABSClient methods for high-performance
concurrent operations like fetching multiple items at once.

Usage:
    import asyncio
    from src.abs import AsyncABSClient

    async def main():
        async with AsyncABSClient(host, api_key) as client:
            # Fetch multiple items concurrently
            items = await client.batch_get_items_async(item_ids)

            # Get library with all items
            library = await client.get_library_items_async(library_id)

    asyncio.run(main())
"""

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import httpx
from pydantic import ValidationError

from .client import ABSAuthError, ABSConnectionError, ABSError, ABSNotFoundError
from .models import (
    Author,
    Library,
    LibraryItemExpanded,
    LibraryStats,
    User,
)

if TYPE_CHECKING:
    from ..cache import SQLiteCache

logger = logging.getLogger(__name__)


class AsyncABSClient:
    """
    Asynchronous Audiobookshelf API client.

    Uses httpx.AsyncClient for concurrent requests with rate limiting
    and semaphore-based concurrency control.
    """

    def __init__(
        self,
        host: str,
        api_key: str,
        timeout: float = 30.0,
        rate_limit_delay: float = 0.1,
        max_concurrent_requests: int = 5,
        cache: Optional["SQLiteCache"] = None,
        cache_ttl_hours: float = 2.0,
    ):
        """
        Initialize the async ABS client.

        Args:
            host: ABS server URL (e.g., https://abs.example.com)
            api_key: API token for authentication
            timeout: Request timeout in seconds
            rate_limit_delay: Minimum delay between requests
            max_concurrent_requests: Max concurrent API calls
            cache: SQLiteCache instance for caching
            cache_ttl_hours: Cache TTL in hours
        """
        self.host = host.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_hours * 3600

        # Concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure async client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.host,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the async HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "AsyncABSClient":
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        loop = asyncio.get_running_loop()
        now = loop.time()
        elapsed = now - self._last_request_time
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = loop.time()

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict:
        """
        Make an async API request with rate limiting and semaphore.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            json: JSON body

        Returns:
            Response JSON as dict
        """
        async with self._semaphore:
            await self._rate_limit()

            client = await self._ensure_client()
            url = f"/api{endpoint}" if not endpoint.startswith("/api") else endpoint

            logger.debug("ABS async request: %s %s", method, url)

            try:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                )
            except httpx.ConnectError as e:
                logger.error("ABS async connection error: %s", e)
                raise ABSConnectionError(f"Failed to connect to {self.host}: {e}")
            except httpx.TimeoutException as e:
                logger.error("ABS async timeout: %s", e)
                raise ABSConnectionError(f"Request timed out: {e}")

            if response.status_code == 401:
                raise ABSAuthError("Authentication failed. Check your API key.")
            elif response.status_code == 403:
                raise ABSAuthError("Access forbidden. Insufficient permissions.")
            elif response.status_code == 404:
                raise ABSNotFoundError(f"Resource not found: {endpoint}")
            elif response.status_code >= 400:
                raise ABSError(
                    f"API error: {response.status_code}",
                    status_code=response.status_code,
                    response=response.json() if response.content else None,
                )

            if not response.content:
                return {}

            return response.json()

    async def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """Make an async GET request."""
        return await self._request("GET", endpoint, params=params)

    async def _post(self, endpoint: str, json: dict | None = None, params: dict | None = None) -> dict:
        """Make an async POST request."""
        return await self._request("POST", endpoint, json=json, params=params)

    # =====================
    # User / Auth
    # =====================

    async def get_me(self) -> User:
        """Get current user info."""
        data = await self._get("/me")
        return User.model_validate(data)

    async def authorize(self) -> dict:
        """Verify API key is valid."""
        return await self._post("/authorize")

    # =====================
    # Libraries
    # =====================

    async def get_libraries(self) -> list[Library]:
        """Get all libraries."""
        data = await self._get("/libraries")
        return [Library.model_validate(lib) for lib in data.get("libraries", [])]

    async def get_library(self, library_id: str) -> Library:
        """Get a single library."""
        data = await self._get(f"/libraries/{library_id}")
        return Library.model_validate(data)

    async def get_library_stats(self, library_id: str) -> LibraryStats:
        """Get library statistics."""
        data = await self._get(f"/libraries/{library_id}/stats")
        return LibraryStats.model_validate(data)

    async def get_library_items(
        self,
        library_id: str,
        limit: int = 0,
        page: int = 0,
        sort: str | None = None,
        desc: bool = False,
        filter_str: str | None = None,
        minified: bool = False,
        expanded: bool = False,
    ) -> dict:
        """
        Get library items with pagination.

        Args:
            library_id: Library ID
            limit: Items per page (0 for all)
            page: Page number
            sort: Sort field
            desc: Sort descending
            filter_str: Filter expression
            minified: Return minified items
            expanded: Return expanded items

        Returns:
            Dict with results, total, limit, page
        """
        params: dict[str, Any] = {"limit": limit, "page": page}
        if sort:
            params["sort"] = sort
        if desc:
            params["desc"] = 1
        if filter_str:
            params["filter"] = filter_str
        if minified:
            params["minified"] = 1
        if expanded:
            params["expanded"] = 1

        return await self._get(f"/libraries/{library_id}/items", params=params)

    async def get_library_series(
        self,
        library_id: str,
        limit: int = 0,
        page: int = 0,
    ) -> dict:
        """Get library series."""
        params = {"limit": limit, "page": page}
        return await self._get(f"/libraries/{library_id}/series", params=params)

    async def get_library_authors(self, library_id: str) -> list[Author]:
        """Get all authors in a library."""
        data = await self._get(f"/libraries/{library_id}/authors")
        return [Author.model_validate(a) for a in data.get("authors", [])]

    # =====================
    # Library Items
    # =====================

    async def get_item(
        self,
        item_id: str,
        expanded: bool = True,
        include: str | None = None,
    ) -> LibraryItemExpanded:
        """
        Get a library item.

        Args:
            item_id: Item ID
            expanded: Return expanded item
            include: Additional data to include

        Returns:
            LibraryItemExpanded
        """
        params: dict[str, Any] = {}
        if expanded:
            params["expanded"] = 1
        if include:
            params["include"] = include

        data = await self._get(f"/items/{item_id}", params=params)
        return LibraryItemExpanded.model_validate(data)

    async def batch_get_items(
        self,
        item_ids: list[str],
        expanded: bool = True,
    ) -> list[LibraryItemExpanded]:
        """
        Fetch multiple items concurrently.

        Args:
            item_ids: List of item IDs
            expanded: Return expanded items

        Returns:
            List of items (in order, with None for failures filtered out)
        """
        tasks = [self.get_item(item_id, expanded=expanded) for item_id in item_ids]

        results = []
        for coro in asyncio.as_completed(tasks):
            try:
                item = await coro
                results.append(item)
            except ABSNotFoundError:
                logger.debug("Item not found during batch fetch")
            except ABSError as e:
                logger.warning("Error fetching item during batch: %s", e)

        logger.debug("Batch fetched %d/%d items", len(results), len(item_ids))
        return results

    # =====================
    # Authors
    # =====================

    async def get_author(self, author_id: str, include: str | None = None) -> dict:
        """Get an author."""
        params = {"include": include} if include else None
        return await self._get(f"/authors/{author_id}", params=params)

    async def get_author_with_items(
        self,
        author_id: str,
        include_series: bool = True,
    ) -> dict:
        """
        Get an author with their library items and series.

        Args:
            author_id: Author ID
            include_series: Include series info

        Returns:
            Author dict with libraryItems and series
        """
        include_parts = ["items"]
        if include_series:
            include_parts.append("series")

        return await self.get_author(author_id, include=",".join(include_parts))

    # =====================
    # Series
    # =====================

    async def get_series(self, series_id: str, include: str | None = None) -> dict:
        """Get a series."""
        params = {"include": include} if include else None
        return await self._get(f"/series/{series_id}", params=params)

    async def get_series_with_progress(self, series_id: str) -> dict:
        """Get a series with progress info."""
        return await self.get_series(series_id, include="progress")

    # =====================
    # Collections
    # =====================

    async def get_collections(self) -> list[dict]:
        """Get all collections."""
        result = await self._get("/collections")
        return result.get("collections", [])

    async def get_collection(self, collection_id: str) -> dict:
        """Get a collection by ID."""
        return await self._get(f"/collections/{collection_id}")

    async def create_collection(
        self,
        library_id: str,
        name: str,
        description: str | None = None,
        book_ids: list[str] | None = None,
    ) -> dict:
        """Create a new collection."""
        payload: dict[str, Any] = {
            "libraryId": library_id,
            "name": name,
        }
        if description:
            payload["description"] = description
        if book_ids:
            payload["books"] = book_ids

        result = await self._post("/collections", json=payload)
        logger.info("Created collection '%s'", name)
        return result

    async def batch_add_to_collection(self, collection_id: str, book_ids: list[str]) -> dict:
        """Add multiple books to a collection."""
        result = await self._post(f"/collections/{collection_id}/batch/add", json={"books": book_ids})
        logger.info("Added %d books to collection %s", len(book_ids), collection_id)
        return result

    async def find_or_create_collection(
        self,
        library_id: str,
        name: str,
        description: str | None = None,
    ) -> dict:
        """Find or create a collection by name."""
        collections = await self.get_collections()

        for col in collections:
            if col.get("name") == name and col.get("libraryId") == library_id:
                logger.debug("Found existing collection '%s'", name)
                return col

        return await self.create_collection(library_id, name, description)

    # =====================
    # Search
    # =====================

    async def search_library(self, library_id: str, query: str, limit: int = 12) -> dict:
        """Search a library."""
        params = {"q": query, "limit": limit}
        return await self._get(f"/libraries/{library_id}/search", params=params)

    async def search_books(
        self,
        title: str = "",
        author: str = "",
        provider: str = "audible",
    ) -> list[dict]:
        """Search for books using metadata provider."""
        params = {"title": title, "author": author, "provider": provider}
        return await self._get("/search/books", params=params)
