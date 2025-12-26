"""
Audiobookshelf API client.
"""

import time
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
from urllib.parse import urljoin

import httpx
from pydantic import ValidationError

from .models import (
    Library,
    LibrariesResponse,
    LibraryItem,
    LibraryItemExpanded,
    LibraryItemMinified,
    LibraryItemsResponse,
    LibraryStats,
    User,
    Author,
    Series,
)

# Import from cache module (SQLite-based)
if TYPE_CHECKING:
    from ..cache import SQLiteCache


class ABSError(Exception):
    """Base exception for ABS API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[dict] = None):
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
        cache_dir: Optional[Path] = None,
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
        params: Optional[dict] = None,
        json: Optional[dict] = None,
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
        
        try:
            response = self._client.request(
                method=method,
                url=url,
                params=params,
                json=json,
            )
        except httpx.ConnectError as e:
            raise ABSConnectionError(f"Failed to connect to {self.host}: {e}")
        except httpx.TimeoutException as e:
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
    
    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make a GET request."""
        return self._request("GET", endpoint, params=params)
    
    def _post(self, endpoint: str, json: Optional[dict] = None, params: Optional[dict] = None) -> dict:
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
    
    def clear_cache(self, namespace: Optional[str] = None) -> int:
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
        sort: Optional[str] = None,
        desc: bool = False,
        filter_by: Optional[str] = None,
        minified: bool = True,
        collapseseries: bool = False,
        include: Optional[str] = None,
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
        sort: Optional[str] = None,
        desc: bool = False,
        filter_by: Optional[str] = None,
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
            self._cache.set("abs_authors", cache_key, [a.model_dump() for a in authors], ttl_seconds=self._cache_ttl_seconds)
        
        return authors
    
    def get_library_series(
        self,
        library_id: str,
        limit: int = 0,
        page: int = 0,
        sort: Optional[str] = None,
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
        include: Optional[str] = None,
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
        progress_callback: Optional[callable] = None,
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
            def fetch_item(item_id: str) -> tuple[str, Optional[dict]]:
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
        title: Optional[str] = None,
        author: Optional[str] = None,
        asin: Optional[str] = None,
        isbn: Optional[str] = None,
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
        include: Optional[str] = None,
        library_id: Optional[str] = None,
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
    
    def get_series(self, series_id: str, include: Optional[str] = None) -> dict:
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
    
    def search_authors(self, query: str) -> Optional[dict]:
        """
        Search for an author.
        
        Args:
            query: Author name
            
        Returns:
            Author dict or None
        """
        return self._get("/search/authors", params={"q": query})
