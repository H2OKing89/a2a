"""
Audiobookshelf API client.
"""

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import httpx
from pydantic import ValidationError

from .models import (
    Author,
    AuthorSearchResponse,
    BookSearchResult,
    Collection,
    CollectionExpanded,
    LibrariesResponse,
    Library,
    LibraryItemExpanded,
    LibraryItemMinified,
    LibraryItemsResponse,
    LibraryStats,
    SearchResponse,
    SeriesListResponse,
    SeriesResponse,
    User,
)

# Import from cache module (SQLite-based)
if TYPE_CHECKING:
    from ..cache import SQLiteCache

logger = logging.getLogger(__name__)


class ABSError(Exception):
    """Base exception for ABS API errors."""

    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response

    def __str__(self) -> str:
        return self.message


class ABSConnectionError(ABSError):
    """Connection error."""

    pass


class ABSAuthError(ABSError):
    """Authentication error."""

    pass


class ABSNotFoundError(ABSError):
    """Resource not found error."""

    pass


def _http2_available() -> bool:
    """Check if HTTP/2 dependencies are installed."""
    try:
        import h2

        return True
    except ImportError:
        return False


def _is_localhost(host: str) -> bool:
    """Check if host is localhost or loopback address."""
    from urllib.parse import urlparse

    parsed = urlparse(host if "://" in host else f"http://{host}")
    hostname = parsed.hostname or ""
    return hostname in ("localhost", "127.0.0.1", "::1")


def _normalize_host(host: str) -> str:
    """
    Normalize host URL by adding scheme if missing.

    Default behavior:
    - Localhost: defaults to http:// (common for local dev)
    - Remote: defaults to https:// (secure by default)

    Note: allow_insecure_http only affects whether explicit http:// is accepted,
    NOT what scheme is defaulted to. "allow" != "prefer".

    Args:
        host: Host URL (may or may not have scheme)

    Returns:
        Normalized URL with scheme
    """
    host = host.rstrip("/")

    # Already has scheme - keep as-is
    if "://" in host:
        return host

    # Add scheme: localhost -> http, remote -> https
    # This ensures we default to secure even when allow_insecure_http is set
    if _is_localhost(host):
        return f"http://{host}"
    else:
        return f"https://{host}"


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
        # Security settings
        allow_insecure_http: bool = False,
        tls_ca_bundle: str | None = None,
        insecure_tls: bool = False,
    ):
        """
        Initialize the ABS client.

        Args:
            host: ABS server URL (e.g., https://abs.example.com or abs.example.com:13378)
            api_key: API token for authentication
            timeout: Request timeout in seconds
            rate_limit_delay: Delay between requests
            cache: SQLiteCache instance for caching API responses
            cache_ttl_hours: Cache TTL in hours (default 2)
            cache_dir: Deprecated - use cache parameter instead
            allow_insecure_http: Allow HTTP connections to non-localhost (localhost always allowed)
            tls_ca_bundle: Path to CA certificate bundle for self-signed certs
            insecure_tls: DANGEROUS - Disable SSL verification entirely
        """
        # Normalize host URL (add scheme if missing)
        self.host = _normalize_host(host)
        self.api_key = api_key
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0
        self._cache_ttl_seconds = cache_ttl_hours * 3600

        # Track security state for status display
        self._is_localhost = _is_localhost(self.host)
        self._is_https = self.host.startswith("https://")
        self._http2_available = _http2_available()
        self._http2_enabled = self._http2_available  # Will be confirmed after first request
        self._last_http_version: str | None = None  # Actual negotiated protocol
        self._insecure_tls = insecure_tls
        self._using_ca_bundle = bool(tls_ca_bundle)
        self._tls_ca_bundle_path = tls_ca_bundle

        # Validate tls_ca_bundle path early (fail fast with helpful message)
        if tls_ca_bundle:
            ca_path = Path(tls_ca_bundle)
            if not ca_path.exists():
                raise ABSConnectionError(
                    f"tls_ca_bundle path does not exist: {tls_ca_bundle}\n"
                    "Fix the path, or remove it to use the system trust store."
                )
            if not ca_path.is_file():
                raise ABSConnectionError(f"tls_ca_bundle must be a file, not a directory: {tls_ca_bundle}")
            try:
                ca_path.read_bytes()[:1]  # Check readability
            except PermissionError as e:
                raise ABSConnectionError(
                    f"tls_ca_bundle file is not readable: {tls_ca_bundle}\nCheck file permissions."
                ) from e

        # Security validation: HTTP only allowed for localhost or if explicitly enabled
        if not self._is_https and not self._is_localhost and not allow_insecure_http:
            raise ABSConnectionError(
                f"ABS host is HTTP but insecure HTTP is not allowed: {self.host}\n"
                "Options:\n"
                "  1. Use HTTPS in Audiobookshelf (recommended)\n"
                "  2. Set allow_insecure_http: true in config.yaml (not recommended)\n"
                "  3. Set ABS_ALLOW_INSECURE_HTTP=true environment variable"
            )

        # Log security info at DEBUG level (CLI handles user-facing messages)
        if not self._is_https:
            if self._is_localhost:
                logger.debug("Using HTTP for localhost; TLS recommended for remote hosts")
            else:
                logger.debug(
                    "Using HTTP connection to remote server: %s. API key will be sent in cleartext!", self.host
                )

        if insecure_tls:
            logger.warning(
                "SSL certificate verification is DISABLED. This is insecure and should only be used for testing."
            )

        # Determine TLS verification setting
        verify: bool | str = True
        if self._is_https:
            if insecure_tls:
                verify = False
            elif tls_ca_bundle:
                verify = tls_ca_bundle
                logger.debug("Using custom CA bundle: %s", tls_ca_bundle)

        # Create HTTP client with automatic HTTP/2 support
        self._client = httpx.Client(
            base_url=self.host,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
            verify=verify,
            http2=self._http2_available,
        )

        if self._http2_available:
            logger.debug("HTTP/2 support available (h2 library installed)")
        else:
            logger.debug("HTTP/2 not available; using HTTP/1.1 (install httpx[http2] for HTTP/2)")

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
        """Apply rate limiting between requests (skipped if delay is 0)."""
        if self.rate_limit_delay <= 0:
            return
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
            # Track actual negotiated HTTP version
            self._last_http_version = getattr(response, "http_version", None)
            if self._last_http_version == "HTTP/2":
                self._http2_enabled = True
            elif self._last_http_version:
                self._http2_enabled = False
        except httpx.ConnectError as e:
            logger.debug("ABS connection error: %s", e)
            error_str = str(e).lower()
            # Detect SSL certificate verification failures and give helpful hint
            if "certificate" in error_str or "ssl" in error_str or "verify" in error_str:
                raise ABSConnectionError(
                    f"SSL certificate verification failed for {self.host}\n"
                    "This usually means the server is using a self-signed or private CA certificate.\n"
                    "Options:\n"
                    "  1. Set tls_ca_bundle to your CA certificate file (recommended)\n"
                    "  2. Set ABS_INSECURE_TLS=1 to disable verification (testing only)"
                ) from e
            raise ABSConnectionError(f"Failed to connect to {self.host}: {e}") from e
        except httpx.TimeoutException as e:
            logger.debug("ABS timeout: %s", e)
            raise ABSConnectionError(f"Request timed out: {e}") from e

        # Handle redirects (301/302) - likely HTTP -> HTTPS
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location", "unknown")
            logger.debug("ABS redirect: %d to %s", response.status_code, location)
            if self.host.startswith("http://") and location.startswith("https://"):
                raise ABSConnectionError(
                    f"Server redirected HTTP to HTTPS. Update your ABS_HOST to use HTTPS: {location}"
                )
            raise ABSConnectionError(f"Server returned redirect {response.status_code} to: {location}")

        if response.status_code == 401:
            logger.debug("ABS auth error: 401 Unauthorized")
            raise ABSAuthError("Authentication failed. Check your API key.")
        elif response.status_code == 403:
            logger.debug("ABS auth error: 403 Forbidden")
            raise ABSAuthError("Access forbidden. Insufficient permissions.")
        elif response.status_code == 404:
            logger.debug("ABS resource not found: %s", endpoint)
            raise ABSNotFoundError(f"Resource not found: {endpoint}")
        elif response.status_code >= 400:
            logger.debug("ABS API error: %d for %s", response.status_code, endpoint)
            raise ABSError(
                f"API error: {response.status_code}",
                status_code=response.status_code,
                response=response.json() if response.content else None,
            )

        logger.debug("ABS API response: %d", response.status_code)

        if not response.content:
            return {}

        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ABSError(
                    f"Expected dict response, got {type(data).__name__}",
                    status_code=response.status_code,
                )
            return data
        except ValueError as e:
            # Server returned non-JSON response (likely HTML error page)
            content_preview = response.text[:500] if response.text else "(empty)"
            logger.debug(
                "ABS returned non-JSON response: %s - Content preview: %s",
                e,
                content_preview,
            )
            raise ABSError(
                f"Server returned invalid JSON response. "
                f"This usually means the server URL is incorrect or the server returned an error page. "
                f"Status: {response.status_code}, Content preview: {content_preview[:200]}",
                status_code=response.status_code,
            ) from e

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

    def get_library_series_parsed(
        self,
        library_id: str,
        limit: int = 0,
        page: int = 0,
        sort: str | None = None,
        desc: bool = False,
    ) -> SeriesListResponse:
        """
        Get library series with Pydantic model response.

        Args:
            library_id: Library ID
            limit: Items per page (0 = all)
            page: Page number
            sort: Sort field
            desc: Sort descending

        Returns:
            SeriesListResponse model
        """
        data = self.get_library_series(library_id, limit, page, sort, desc)
        return SeriesListResponse.model_validate(data)

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

    def search_library_parsed(self, library_id: str, query: str, limit: int = 12) -> SearchResponse:
        """
        Search a library with Pydantic model response.

        Args:
            library_id: Library ID
            query: Search query
            limit: Max results

        Returns:
            SearchResponse model
        """
        data = self.search_library(library_id, query, limit)
        return SearchResponse.model_validate(data)

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
                except Exception as e:
                    logger.debug("Failed to fetch item %s in batch: %s", item_id, e)
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

    def get_series_parsed(self, series_id: str, include: str | None = None) -> SeriesResponse:
        """
        Get a series with Pydantic model response.

        Args:
            series_id: Series ID
            include: Include progress

        Returns:
            SeriesResponse model
        """
        data = self.get_series(series_id, include)
        return SeriesResponse.model_validate(data)

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

    def search_books_parsed(
        self,
        title: str = "",
        author: str = "",
        provider: str = "audible",
    ) -> list[BookSearchResult]:
        """
        Search for books using metadata provider with Pydantic models.

        Args:
            title: Book title or ASIN
            author: Author name
            provider: Metadata provider

        Returns:
            List of BookSearchResult models
        """
        data = self.search_books(title, author, provider)
        results = []
        for item in data:
            try:
                results.append(BookSearchResult.model_validate(item))
            except ValidationError:
                logger.debug(f"Skipping invalid book search result: {item}")
        return results

    def search_authors(self, query: str) -> dict | None:
        """
        Search for an author.

        Args:
            query: Author name

        Returns:
            Author dict or None
        """
        return self._get("/search/authors", params={"q": query})

    def search_authors_parsed(self, query: str) -> AuthorSearchResponse:
        """
        Search for an author with Pydantic model response.

        Args:
            query: Author name

        Returns:
            AuthorSearchResponse model
        """
        data = self.search_authors(query)
        if data is None:
            return AuthorSearchResponse(results=[])
        # The search_authors endpoint returns a list directly
        if isinstance(data, list):
            return AuthorSearchResponse(results=data)
        return AuthorSearchResponse.model_validate(data)

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

    def get_collections(self) -> list[Collection]:
        """
        Get all collections.

        Returns:
            List of Collection models
        """
        result = self._get("/collections")
        collections = [Collection.model_validate(c) for c in result.get("collections", [])]
        logger.debug("Fetched %d collections", len(collections))
        return collections

    def get_collection(self, collection_id: str) -> CollectionExpanded:
        """
        Get a collection by ID.

        Args:
            collection_id: Collection ID

        Returns:
            CollectionExpanded model with books array
        """
        result = self._get(f"/collections/{collection_id}")
        return CollectionExpanded.model_validate(result)

    def create_collection(
        self,
        library_id: str,
        name: str,
        description: str | None = None,
        book_ids: list[str] | None = None,
    ) -> CollectionExpanded:
        """
        Create a new collection.

        Args:
            library_id: Library ID the collection belongs to
            name: Collection name
            description: Optional description
            book_ids: Optional list of book IDs to add

        Returns:
            Created CollectionExpanded model

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
        collection = CollectionExpanded.model_validate(result)
        logger.info("Created collection '%s' (id=%s)", name, collection.id)
        return collection

    def update_collection(
        self,
        collection_id: str,
        name: str | None = None,
        description: str | None = None,
        book_ids: list[str] | None = None,
    ) -> CollectionExpanded:
        """
        Update a collection.

        Args:
            collection_id: Collection ID
            name: New name (optional)
            description: New description (optional)
            book_ids: Replace book list (optional)

        Returns:
            Updated CollectionExpanded model
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
        return CollectionExpanded.model_validate(result)

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

    def add_book_to_collection(self, collection_id: str, book_id: str) -> CollectionExpanded:
        """
        Add a single book to a collection.

        Args:
            collection_id: Collection ID
            book_id: Library item ID to add

        Returns:
            Updated CollectionExpanded model
        """
        result = self._post(f"/collections/{collection_id}/book", json={"id": book_id})
        logger.debug("Added book %s to collection %s", book_id, collection_id)
        return CollectionExpanded.model_validate(result)

    def remove_book_from_collection(self, collection_id: str, book_id: str) -> CollectionExpanded:
        """
        Remove a book from a collection.

        Args:
            collection_id: Collection ID
            book_id: Library item ID to remove

        Returns:
            Updated CollectionExpanded model
        """
        result = self._request("DELETE", f"/collections/{collection_id}/book/{book_id}")
        logger.debug("Removed book %s from collection %s", book_id, collection_id)
        return CollectionExpanded.model_validate(result)

    def batch_add_to_collection(self, collection_id: str, book_ids: list[str]) -> CollectionExpanded:
        """
        Add multiple books to a collection.

        Args:
            collection_id: Collection ID
            book_ids: List of library item IDs to add

        Returns:
            Updated CollectionExpanded model
        """
        result = self._post(f"/collections/{collection_id}/batch/add", json={"books": book_ids})
        logger.info("Added %d books to collection %s", len(book_ids), collection_id)
        return CollectionExpanded.model_validate(result)

    def batch_remove_from_collection(self, collection_id: str, book_ids: list[str]) -> CollectionExpanded:
        """
        Remove multiple books from a collection.

        Args:
            collection_id: Collection ID
            book_ids: List of library item IDs to remove

        Returns:
            Updated CollectionExpanded model
        """
        result = self._post(f"/collections/{collection_id}/batch/remove", json={"books": book_ids})
        logger.info("Removed %d books from collection %s", len(book_ids), collection_id)
        return CollectionExpanded.model_validate(result)

    # =====================
    # Utility Methods
    # =====================

    def find_or_create_collection(
        self,
        library_id: str,
        name: str,
        description: str | None = None,
    ) -> Collection | CollectionExpanded:
        """
        Find a collection by name or create it if it doesn't exist.

        Useful for ensuring a collection exists before adding books.

        Args:
            library_id: Library ID
            name: Collection name to find or create
            description: Description if creating new

        Returns:
            Collection (if found) or CollectionExpanded (if created)

        Example:
            collection = client.find_or_create_collection(
                library_id,
                "Upgrade Candidates - Low Quality"
            )
            client.batch_add_to_collection(collection.id, book_ids)
        """
        collections = self.get_collections()

        # Find existing collection with same name in this library
        for col in collections:
            if col.name == name and col.library_id == library_id:
                logger.debug("Found existing collection '%s'", name)
                return col

        # Create new collection
        return self.create_collection(library_id, name, description)
