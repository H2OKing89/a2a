"""
Audible API client using the audible Python library.

Handles authentication, rate limiting, and provides high-level methods
for common operations like library retrieval and catalog lookups.
"""

import hashlib
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from pydantic import ValidationError

import audible
from audible import Authenticator, Client

from .models import (
    AudibleAccountInfo,
    AudibleBook,
    AudibleCatalogProduct,
    AudibleCatalogResponse,
    AudibleLibraryItem,
    AudibleLibraryResponse,
    AudibleListeningStats,
)

if TYPE_CHECKING:
    from ..cache import SQLiteCache


class AudibleError(Exception):
    """Base exception for Audible API errors."""

    def __init__(self, message: str, response: dict | None = None):
        super().__init__(message)
        self.response = response


class AudibleAuthError(AudibleError):
    """Authentication error."""


class AudibleNotFoundError(AudibleError):
    """Resource not found error."""


class AudibleRateLimitError(AudibleError):
    """Rate limit exceeded."""


# Standard response groups for different operations
LIBRARY_RESPONSE_GROUPS = (
    "contributors,"
    "media,"
    "price,"
    "product_attrs,"
    "product_desc,"
    "product_details,"
    "product_extended_attrs,"
    "rating,"
    "series,"
    "category_ladders,"
    "is_downloaded,"
    "is_finished,"
    "percent_complete,"
    "pdf_url"
)

CATALOG_RESPONSE_GROUPS = (
    "contributors,"
    "media,"
    "product_attrs,"
    "product_desc,"
    "product_details,"
    "product_extended_attrs,"
    "rating,"
    "series,"
    "category_ladders,"
    "reviews,"
    "customer_rights"
)


class AudibleClient:
    """
    Audible API client with caching and rate limiting.

    Authentication is handled via the audible library using file-based
    credential storage. First-time auth requires interactive login.

    Example:
        # First-time setup (interactive)
        client = AudibleClient.from_login(
            email="user@example.com",
            password="...",
            locale="us",
            auth_file="./data/audible_auth.json"
        )

        # Subsequent usage (load saved credentials)
        client = AudibleClient.from_file("./data/audible_auth.json")

        # Get library
        library = client.get_library()
    """

    def __init__(
        self,
        auth: Authenticator,
        cache: Optional["SQLiteCache"] = None,
        cache_ttl_hours: float = 240.0,  # 10 days default
        rate_limit_delay: float = 0.5,
        requests_per_minute: float = 20.0,
        burst_size: int = 5,
        backoff_multiplier: float = 2.0,
        max_backoff_seconds: float = 60.0,
        # Deprecated: kept for backwards compatibility
        cache_dir: Path | None = None,
        cache_ttl_days: int = 10,
    ):
        """
        Initialize the client with an Authenticator.

        Args:
            auth: Audible Authenticator instance
            cache: SQLiteCache instance for caching API responses
            cache_ttl_hours: TTL for cached items in hours (default 240 = 10 days)
            rate_limit_delay: Base delay between requests in seconds
            requests_per_minute: Maximum requests per minute
            burst_size: Number of requests before enforcing burst delay
            backoff_multiplier: Multiplier on rate limit errors
            max_backoff_seconds: Maximum backoff delay
            cache_dir: Deprecated - use cache parameter instead
            cache_ttl_days: Deprecated - use cache_ttl_hours instead
        """
        self._auth = auth
        self._client = Client(auth=auth)

        # Rate limiting configuration
        self._rate_limit_delay = rate_limit_delay
        self._requests_per_minute = requests_per_minute
        self._burst_size = burst_size
        self._backoff_multiplier = backoff_multiplier
        self._max_backoff_seconds = max_backoff_seconds

        # Rate limiting state
        self._last_request_time = 0.0
        self._request_count = 0
        self._current_backoff = rate_limit_delay
        self._minute_start = time.time()
        self._requests_this_minute = 0

        # Cache TTL in seconds
        # Prefer new parameter, fall back to deprecated
        if cache_ttl_hours != 240.0:
            self._cache_ttl_seconds = cache_ttl_hours * 3600
        else:
            self._cache_ttl_seconds = cache_ttl_days * 24 * 3600

        # Setup caching - prefer new SQLiteCache
        self._cache: Optional["SQLiteCache"] = cache
        if cache is None and cache_dir:
            # Legacy support: create SQLiteCache from cache_dir
            from ..cache import SQLiteCache

            db_path = Path(cache_dir) / "cache.db"
            self._cache = SQLiteCache(
                db_path=db_path,
                default_ttl_hours=cache_ttl_hours if cache_ttl_hours != 240.0 else cache_ttl_days * 24,
            )

    @classmethod
    def from_file(
        cls,
        auth_file: str | Path,
        cache: Optional["SQLiteCache"] = None,
        cache_ttl_hours: float = 240.0,
        rate_limit_delay: float = 0.5,
        requests_per_minute: float = 20.0,
        burst_size: int = 5,
        backoff_multiplier: float = 2.0,
        max_backoff_seconds: float = 60.0,
        # Deprecated parameters
        cache_dir: Path | None = None,
        cache_ttl_days: int = 10,
    ) -> "AudibleClient":
        """
        Create client from saved credentials file.

        Args:
            auth_file: Path to saved auth credentials
            cache: SQLiteCache instance for caching
            cache_ttl_hours: TTL for cached items in hours
            rate_limit_delay: Base delay between requests
            requests_per_minute: Max requests per minute
            burst_size: Requests before burst delay
            backoff_multiplier: Backoff multiplier on errors
            max_backoff_seconds: Maximum backoff delay
            cache_dir: Deprecated - use cache parameter instead
            cache_ttl_days: Deprecated - use cache_ttl_hours instead

        Returns:
            Configured AudibleClient

        Raises:
            AudibleAuthError: If credentials file is invalid/missing
        """
        auth_path = Path(auth_file)
        if not auth_path.exists():
            raise AudibleAuthError(f"Auth file not found: {auth_file}. " "Run initial authentication first.")

        try:
            auth = Authenticator.from_file(str(auth_path))
        except Exception as e:
            raise AudibleAuthError(f"Failed to load auth from {auth_file}: {e}") from e

        return cls(
            auth=auth,
            cache=cache,
            cache_ttl_hours=cache_ttl_hours,
            rate_limit_delay=rate_limit_delay,
            requests_per_minute=requests_per_minute,
            burst_size=burst_size,
            backoff_multiplier=backoff_multiplier,
            max_backoff_seconds=max_backoff_seconds,
            cache_dir=cache_dir,
            cache_ttl_days=cache_ttl_days,
        )

    @classmethod
    def from_login(
        cls,
        email: str,
        password: str,
        locale: str = "us",
        auth_file: str | Path | None = None,
        cache: Optional["SQLiteCache"] = None,
        cache_ttl_hours: float = 240.0,
        rate_limit_delay: float = 0.5,
        requests_per_minute: float = 20.0,
        burst_size: int = 5,
        backoff_multiplier: float = 2.0,
        max_backoff_seconds: float = 60.0,
        otp_callback: Callable | None = None,
        cvf_callback: Callable | None = None,
        captcha_callback: Callable | None = None,
        # Deprecated parameters
        cache_dir: Path | None = None,
        cache_ttl_days: int = 10,
    ) -> "AudibleClient":
        """
        Create client via interactive login.

        This requires user interaction for 2FA, CAPTCHA, etc.
        Credentials will be saved to auth_file if provided.

        Args:
            email: Amazon/Audible email
            password: Account password
            locale: Marketplace locale (us, uk, de, fr, etc.)
            auth_file: Path to save credentials for future use
            cache: SQLiteCache instance for caching
            cache_ttl_hours: TTL for cached items in hours
            rate_limit_delay: Base delay between requests
            requests_per_minute: Max requests per minute
            burst_size: Requests before burst delay
            backoff_multiplier: Backoff multiplier on errors
            max_backoff_seconds: Maximum backoff delay
            otp_callback: Callback for OTP/2FA codes
            cvf_callback: Callback for CVF (verification code)
            captcha_callback: Callback for CAPTCHA solving
            cache_dir: Deprecated - use cache parameter instead
            cache_ttl_days: Deprecated - use cache_ttl_hours instead

        Returns:
            Configured AudibleClient
        """
        try:
            auth = Authenticator.from_login(
                username=email,
                password=password,
                locale=locale,
                otp_callback=otp_callback,
                cvf_callback=cvf_callback,
                captcha_callback=captcha_callback,
            )
        except Exception as e:
            raise AudibleAuthError(f"Login failed: {e}")

        # Save credentials for future use
        if auth_file:
            auth_path = Path(auth_file)
            auth_path.parent.mkdir(parents=True, exist_ok=True)
            auth.to_file(str(auth_path))

        return cls(
            auth=auth,
            cache=cache,
            cache_ttl_hours=cache_ttl_hours,
            rate_limit_delay=rate_limit_delay,
            requests_per_minute=requests_per_minute,
            burst_size=burst_size,
            backoff_multiplier=backoff_multiplier,
            max_backoff_seconds=max_backoff_seconds,
            cache_dir=cache_dir,
            cache_ttl_days=cache_ttl_days,
        )

    @classmethod
    def from_login_external(
        cls,
        locale: str = "us",
        auth_file: str | Path | None = None,
        cache: Optional["SQLiteCache"] = None,
        cache_ttl_hours: float = 240.0,
        rate_limit_delay: float = 0.5,
        requests_per_minute: float = 20.0,
        burst_size: int = 5,
        backoff_multiplier: float = 2.0,
        max_backoff_seconds: float = 60.0,
        # Deprecated parameters
        cache_dir: Path | None = None,
        cache_ttl_days: int = 10,
    ) -> "AudibleClient":
        """
        Create client via external browser login.

        Opens a browser for login, avoiding issues with CAPTCHA/2FA.

        Args:
            locale: Marketplace locale
            auth_file: Path to save credentials
            cache: SQLiteCache instance for caching
            cache_ttl_hours: TTL for cached items in hours
            rate_limit_delay: Base delay between requests
            requests_per_minute: Max requests per minute
            burst_size: Requests before burst delay
            backoff_multiplier: Backoff multiplier on errors
            max_backoff_seconds: Maximum backoff delay
            cache_dir: Deprecated - use cache parameter instead
            cache_ttl_days: Deprecated - use cache_ttl_hours instead

        Returns:
            Configured AudibleClient
        """
        try:
            auth = Authenticator.from_login_external(locale=locale)
        except Exception as e:
            raise AudibleAuthError(f"External login failed: {e}")

        # Save credentials
        if auth_file:
            auth_path = Path(auth_file)
            auth_path.parent.mkdir(parents=True, exist_ok=True)
            auth.to_file(str(auth_path))

        return cls(
            auth=auth,
            cache=cache,
            cache_ttl_hours=cache_ttl_hours,
            rate_limit_delay=rate_limit_delay,
            requests_per_minute=requests_per_minute,
            burst_size=burst_size,
            backoff_multiplier=backoff_multiplier,
            max_backoff_seconds=max_backoff_seconds,
            cache_dir=cache_dir,
            cache_ttl_days=cache_ttl_days,
        )

    def save_auth(self, auth_file: str | Path) -> None:
        """Save current auth credentials to file."""
        auth_path = Path(auth_file)
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        self._auth.to_file(str(auth_path))

    @property
    def marketplace(self) -> str:
        """Current marketplace/locale."""
        return self._auth.locale.country_code

    def _rate_limit(self) -> None:
        """
        Apply advanced rate limiting between requests.

        Implements:
        - Base delay between requests
        - Per-minute request cap
        - Burst limiting
        - Exponential backoff recovery
        """
        now = time.time()

        # Reset minute counter if a minute has passed
        if now - self._minute_start >= 60:
            self._minute_start = now
            self._requests_this_minute = 0
            # Gradually recover backoff
            self._current_backoff = max(self._rate_limit_delay, self._current_backoff / self._backoff_multiplier)

        # Check requests per minute limit
        if self._requests_this_minute >= self._requests_per_minute:
            wait_time = 60 - (now - self._minute_start)
            if wait_time > 0:
                time.sleep(wait_time)
                self._minute_start = time.time()
                self._requests_this_minute = 0

        # Apply burst limiting
        self._request_count += 1
        if self._request_count >= self._burst_size:
            self._request_count = 0
            time.sleep(self._current_backoff)
        else:
            # Apply base delay
            elapsed = now - self._last_request_time
            if elapsed < self._rate_limit_delay:
                time.sleep(self._rate_limit_delay - elapsed)

        self._last_request_time = time.time()
        self._requests_this_minute += 1

    def _handle_rate_limit_error(self) -> None:
        """Apply exponential backoff on rate limit errors."""
        self._current_backoff = min(self._current_backoff * self._backoff_multiplier, self._max_backoff_seconds)
        time.sleep(self._current_backoff)

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict:
        """
        Make an API request with rate limiting.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "1.0/library")
            **kwargs: Additional arguments for the request

        Returns:
            Response data as dict
        """
        self._rate_limit()

        try:
            if method.upper() == "GET":
                response = self._client.get(endpoint, **kwargs)
            elif method.upper() == "POST":
                response = self._client.post(endpoint, **kwargs)
            else:
                response = self._client._request(method, endpoint, **kwargs)
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "unauthorized" in error_msg.lower():
                raise AudibleAuthError(f"Authentication failed: {e}")
            elif "404" in error_msg:
                raise AudibleNotFoundError(f"Resource not found: {endpoint}")
            elif "429" in error_msg or "rate" in error_msg.lower():
                # Apply backoff and retry once
                self._handle_rate_limit_error()
                try:
                    if method.upper() == "GET":
                        response = self._client.get(endpoint, **kwargs)
                    elif method.upper() == "POST":
                        response = self._client.post(endpoint, **kwargs)
                    else:
                        response = self._client._request(method, endpoint, **kwargs)
                except Exception:
                    raise AudibleRateLimitError(f"Rate limited: {e}")
            else:
                raise AudibleError(f"API error: {e}")

        return response

    # -------------------------------------------------------------------------
    # Library Methods
    # -------------------------------------------------------------------------

    def get_library(
        self,
        num_results: int = 1000,
        page: int = 1,
        response_groups: str | None = None,
        sort_by: str = "-PurchaseDate",
        use_cache: bool = True,
    ) -> list[AudibleLibraryItem]:
        """
        Get the user's Audible library.

        Args:
            num_results: Max results per page (max 1000)
            page: Page number
            response_groups: Override default response groups
            sort_by: Sort order (-PurchaseDate, Title, Author, etc.)
            use_cache: Whether to use cached results

        Returns:
            List of library items
        """
        cache_key = f"library_p{page}_n{num_results}_{sort_by}"

        # Check cache
        if use_cache and self._cache:
            cached = self._cache.get("library", cache_key)
            if cached:
                return [AudibleLibraryItem.model_validate(item) for item in cached]

        # Make API request
        response = self._request(
            "GET",
            "1.0/library",
            num_results=num_results,
            page=page,
            response_groups=response_groups or LIBRARY_RESPONSE_GROUPS,
            sort_by=sort_by,
        )

        # Parse items
        items_data = response.get("items", [])
        items = []
        for item_data in items_data:
            try:
                items.append(AudibleLibraryItem.model_validate(item_data))
            except ValidationError:
                # Skip items that don't parse correctly
                pass

        # Cache results
        if self._cache:
            self._cache.set("library", cache_key, [i.model_dump() for i in items], ttl_seconds=self._cache_ttl_seconds)

        return items

    def get_all_library_items(
        self,
        use_cache: bool = True,
    ) -> list[AudibleLibraryItem]:
        """
        Get all items from the user's library (handles pagination).

        Args:
            use_cache: Whether to use cached results

        Returns:
            Complete list of library items
        """
        all_items = []
        page = 1

        while True:
            items = self.get_library(
                num_results=1000,
                page=page,
                use_cache=use_cache,
            )

            if not items:
                break

            all_items.extend(items)

            # If we got fewer than requested, we're done
            if len(items) < 1000:
                break

            page += 1

        return all_items

    def get_library_item(
        self,
        asin: str,
        response_groups: str | None = None,
        use_cache: bool = True,
    ) -> AudibleLibraryItem | None:
        """
        Get a specific library item by ASIN.

        Args:
            asin: Audible ASIN
            response_groups: Override default response groups
            use_cache: Whether to use cached results

        Returns:
            Library item or None if not found
        """
        cache_key = f"item_{asin}"

        # Check cache
        if use_cache and self._cache:
            cached = self._cache.get("library", cache_key)
            if cached:
                return AudibleLibraryItem.model_validate(cached)

        try:
            response = self._request(
                "GET",
                f"1.0/library/{asin}",
                response_groups=response_groups or LIBRARY_RESPONSE_GROUPS,
            )

            item = AudibleLibraryItem.model_validate(response.get("item", response))

            # Cache result
            if self._cache:
                self._cache.set("library", cache_key, item.model_dump(), ttl_seconds=self._cache_ttl_seconds)

            return item

        except AudibleNotFoundError:
            return None

    # -------------------------------------------------------------------------
    # Catalog Methods
    # -------------------------------------------------------------------------

    def get_catalog_product(
        self,
        asin: str,
        response_groups: str | None = None,
        use_cache: bool = True,
    ) -> AudibleCatalogProduct | None:
        """
        Get product details from the catalog by ASIN.

        This can be used to look up any Audible product, not just
        items in your library.

        Args:
            asin: Audible ASIN
            response_groups: Override default response groups
            use_cache: Whether to use cached results

        Returns:
            Catalog product or None if not found
        """
        # Check cache
        if use_cache and self._cache:
            cached = self._cache.get("catalog", asin)
            if cached:
                return AudibleCatalogProduct.model_validate(cached)

        try:
            response = self._request(
                "GET",
                f"1.0/catalog/products/{asin}",
                response_groups=response_groups or CATALOG_RESPONSE_GROUPS,
            )

            product = AudibleCatalogProduct.model_validate(response.get("product", response))

            # Cache result
            if self._cache:
                self._cache.set("catalog", asin, product.model_dump(), ttl_seconds=self._cache_ttl_seconds)

            return product

        except AudibleNotFoundError:
            return None

    def search_catalog(
        self,
        keywords: str | None = None,
        title: str | None = None,
        author: str | None = None,
        narrator: str | None = None,
        publisher: str | None = None,
        num_results: int = 50,
        page: int = 1,
        sort_by: str = "Relevance",
        response_groups: str | None = None,
        use_cache: bool = True,
    ) -> list[AudibleCatalogProduct]:
        """
        Search the Audible catalog.

        Args:
            keywords: General search keywords
            title: Filter by title
            author: Filter by author
            narrator: Filter by narrator
            publisher: Filter by publisher
            num_results: Max results (max 50)
            page: Page number
            sort_by: Sort order (Relevance, -ReleaseDate, BestSellers, etc.)
            response_groups: Override default response groups
            use_cache: Whether to use cached results

        Returns:
            List of matching products
        """
        # Build cache key from search params
        search_params = f"{keywords}|{title}|{author}|{narrator}|{publisher}|{sort_by}|p{page}"
        cache_key = hashlib.md5(search_params.encode()).hexdigest()

        # Check cache
        if use_cache and self._cache:
            cached = self._cache.get("search", cache_key)
            if cached:
                return [AudibleCatalogProduct.model_validate(p) for p in cached]

        # Build request params
        params = {
            "num_results": min(num_results, 50),
            "page": page,
            "products_sort_by": sort_by,
            "response_groups": response_groups or CATALOG_RESPONSE_GROUPS,
        }

        if keywords:
            params["keywords"] = keywords
        if title:
            params["title"] = title
        if author:
            params["author"] = author
        if narrator:
            params["narrator"] = narrator
        if publisher:
            params["publisher"] = publisher

        response = self._request("GET", "1.0/catalog/products", **params)

        # Parse products
        products_data = response.get("products", [])
        products = []
        for prod_data in products_data:
            try:
                products.append(AudibleCatalogProduct.model_validate(prod_data))
            except ValidationError:
                pass

        # Cache results
        if self._cache:
            self._cache.set(
                "search", cache_key, [p.model_dump() for p in products], ttl_seconds=self._cache_ttl_seconds
            )

        return products

    # -------------------------------------------------------------------------
    # Similar Products / Series Discovery
    # -------------------------------------------------------------------------

    def get_similar_products(
        self,
        asin: str,
        similarity_type: str = "InTheSameSeries",
        num_results: int = 50,
        response_groups: str | None = None,
        use_cache: bool = True,
    ) -> list[AudibleCatalogProduct]:
        """
        Get similar products for an ASIN using the /sims endpoint.

        This is especially useful for discovering ALL books in a series,
        even ones we don't own yet.

        Args:
            asin: Product ASIN to find similar products for
            similarity_type: Type of similarity. Options:
                - "InTheSameSeries" - Other books in the same series (best for series discovery)
                - "AuthorBasedSims" - Other books by the same author
                - "ListenerAlsoLiked" - Listener recommendations
                - "ClubPickRecommendation" - Book club picks
            num_results: Maximum results to return
            response_groups: Override default response groups
            use_cache: Whether to use cached results

        Returns:
            List of similar products
        """
        cache_key = f"sims_{asin}_{similarity_type}"

        # Check cache
        if use_cache and self._cache:
            cached = self._cache.get("catalog", cache_key)
            if cached:
                return [AudibleCatalogProduct.model_validate(p) for p in cached]

        try:
            response = self._request(
                "GET",
                f"1.0/catalog/products/{asin}/sims",
                similarity_type=similarity_type,
                num_results=min(num_results, 50),
                response_groups=response_groups or CATALOG_RESPONSE_GROUPS,
            )

            # Parse similar products
            products_data = response.get("similar_products", [])
            products = []
            for prod_data in products_data:
                try:
                    products.append(AudibleCatalogProduct.model_validate(prod_data))
                except ValidationError:
                    pass

            # Cache results
            if self._cache:
                self._cache.set(
                    "catalog", cache_key, [p.model_dump() for p in products], ttl_seconds=self._cache_ttl_seconds
                )

            return products

        except AudibleNotFoundError:
            return []
        except AudibleError as e:
            # Log but don't fail - return empty list
            logging.getLogger(__name__).warning("Failed to get similar products for %s: %s", asin, e)
            return []

    def get_series_books_from_sims(
        self,
        asin: str,
        use_cache: bool = True,
    ) -> list[AudibleCatalogProduct]:
        """
        Discover all books in a series using the /sims endpoint.

        This is the most reliable way to find ALL books in a series,
        including ones not in your library. Uses "InTheSameSeries"
        similarity type.

        Args:
            asin: ASIN of any book in the series
            use_cache: Whether to use cached results

        Returns:
            List of all books in the series (as catalog products)
        """
        return self.get_similar_products(
            asin=asin,
            similarity_type="InTheSameSeries",
            num_results=50,  # Most series have fewer than 50 books
            use_cache=use_cache,
        )

    # -------------------------------------------------------------------------
    # Account & Stats Methods
    # -------------------------------------------------------------------------

    def get_listening_stats(
        self,
        use_cache: bool = True,
    ) -> AudibleListeningStats | None:
        """
        Get user's listening statistics.

        Returns:
            Listening stats or None on error
        """
        cache_key = "listening_stats"

        # Check cache
        if use_cache and self._cache:
            cached = self._cache.get("stats", cache_key)
            if cached:
                return AudibleListeningStats.model_validate(cached)

        try:
            response = self._request(
                "GET",
                "1.0/stats/aggregates",
                response_groups="total_listening_stats",
            )

            stats = AudibleListeningStats.model_validate(response)

            # Cache result
            if self._cache:
                self._cache.set("stats", cache_key, stats.model_dump(), ttl_seconds=self._cache_ttl_seconds)

            return stats

        except AudibleError:
            return None

    def get_account_info(
        self,
        use_cache: bool = True,
    ) -> AudibleAccountInfo | None:
        """
        Get user account information.

        Returns:
            Account info or None on error
        """
        cache_key = "account_info"

        # Check cache
        if use_cache and self._cache:
            cached = self._cache.get("account", cache_key)
            if cached:
                return AudibleAccountInfo.model_validate(cached)

        try:
            response = self._request(
                "GET",
                "1.0/account/information",
                response_groups="customer_benefits,subscription_details,plan_summary",
            )

            info = AudibleAccountInfo.model_validate(response)

            # Cache result
            if self._cache:
                self._cache.set("account", cache_key, info.model_dump(), ttl_seconds=self._cache_ttl_seconds)

            return info

        except AudibleError:
            return None

    # -------------------------------------------------------------------------
    # Wishlist Methods
    # -------------------------------------------------------------------------

    def get_wishlist(
        self,
        num_results: int = 50,
        page: int = 0,  # Wishlist uses 0-based pages
        sort_by: str = "-DateAdded",
        use_cache: bool = True,
    ) -> list[AudibleCatalogProduct]:
        """
        Get the user's wishlist.

        Args:
            num_results: Max results (max 50)
            page: Page number (0-based)
            sort_by: Sort order (-DateAdded, Title, -Price, etc.)
            use_cache: Whether to use cached results

        Returns:
            List of wishlist items
        """
        cache_key = f"wishlist_p{page}_{sort_by}"

        # Check cache
        if use_cache and self._cache:
            cached = self._cache.get("library", cache_key)
            if cached:
                return [AudibleCatalogProduct.model_validate(p) for p in cached]

        response = self._request(
            "GET",
            "1.0/wishlist",
            num_results=min(num_results, 50),
            page=page,
            sort_by=sort_by,
            response_groups=CATALOG_RESPONSE_GROUPS,
        )

        products_data = response.get("products", [])
        products = []
        for prod_data in products_data:
            try:
                products.append(AudibleCatalogProduct.model_validate(prod_data))
            except ValidationError:
                pass

        # Cache results
        if self._cache:
            self._cache.set(
                "library", cache_key, [p.model_dump() for p in products], ttl_seconds=self._cache_ttl_seconds
            )

        return products

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def clear_cache(self, namespace: str | None = None) -> int:
        """
        Clear cached data.

        Args:
            namespace: Specific namespace to clear (None = all)

        Returns:
            Number of items cleared
        """
        if not self._cache:
            return 0

        if namespace:
            return self._cache.clear_namespace(namespace)
        else:
            return self._cache.clear_all()

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        if not self._cache:
            return {"enabled": False}

        stats = self._cache.get_stats()
        stats["enabled"] = True
        return stats

    def close(self) -> None:
        """Close the client and cleanup."""
        if self._client:
            self._client.close()

    def __enter__(self) -> "AudibleClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
