"""
Asynchronous Audible API client.

Provides async versions of all AudibleClient methods for high-performance
concurrent operations like fetching multiple books at once.

Usage:
    import asyncio
    from src.audible import AsyncAudibleClient

    async def main():
        async with AsyncAudibleClient.from_file("auth.json") as client:
            # Fetch multiple books concurrently
            asins = ["B00123", "B00456", "B00789"]
            books = await client.get_multiple_products(asins)

            # Get library
            library = await client.get_library()

    asyncio.run(main())
"""

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, cast

from pydantic import ValidationError

import audible
from audible import Authenticator

from .encryption import get_encryption_config, load_auth
from .models import (
    LICENSE_TEST_CONFIGS,
    AudibleAccountInfo,
    AudibleCatalogProduct,
    AudibleLibraryItem,
    AudibleListeningStats,
    AudioFormat,
    CatalogSortBy,
    ContentMetadata,
    ContentQualityInfo,
    DrmType,
    LibrarySortBy,
    LibraryStatus,
    PlusCatalogInfo,
    PricingInfo,
    ResponseGroups,
    SimilarityType,
    WishlistItem,
    WishlistSortBy,
)

if TYPE_CHECKING:
    from ..cache import SQLiteCache


logger = logging.getLogger(__name__)


class AsyncAudibleError(Exception):
    """Base exception for async Audible API errors."""

    def __init__(self, message: str, response: dict | None = None) -> None:
        super().__init__(message, response)
        self.message = message
        self.response = response

    def __str__(self) -> str:
        return self.message


class AsyncAudibleAuthError(AsyncAudibleError):
    """Authentication error."""


class AsyncAudibleNotFoundError(AsyncAudibleError):
    """Resource not found error."""


# Response group constants
LIBRARY_RESPONSE_GROUPS = (
    "contributors,media,price,product_attrs,product_desc,product_details,"
    "product_extended_attrs,rating,series,category_ladders,is_downloaded,"
    "is_finished,percent_complete,pdf_url"
)

CATALOG_RESPONSE_GROUPS = (
    "contributors,media,price,product_attrs,product_desc,product_details,"
    "product_extended_attrs,product_plan_details,product_plans,rating,series,category_ladders,reviews,customer_rights"
)


class AsyncAudibleClient:
    """
    Asynchronous Audible API client.

    Uses httpx async client under the hood via audible.AsyncClient.
    Ideal for fetching multiple resources concurrently.

    Example:
        async with AsyncAudibleClient.from_file("auth.json") as client:
            # Concurrent fetches
            tasks = [client.get_catalog_product(asin) for asin in asins]
            products = await asyncio.gather(*tasks)
    """

    def __init__(
        self,
        auth: Authenticator,
        cache: Optional["SQLiteCache"] = None,
        cache_ttl_hours: float = 240.0,
        max_concurrent_requests: int = 5,
        request_delay: float = 0.2,
    ):
        """
        Initialize the async client.

        Args:
            auth: Audible Authenticator instance
            cache: Optional SQLiteCache for caching
            cache_ttl_hours: Cache TTL in hours
            max_concurrent_requests: Max concurrent API calls
            request_delay: Delay between requests in seconds
        """
        self._auth = auth
        self._client: audible.AsyncClient | None = None
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_hours * 3600
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._request_delay = request_delay
        self._last_request_time = 0.0

    @classmethod
    def from_file(
        cls,
        auth_file: str | Path,
        cache: Optional["SQLiteCache"] = None,
        cache_ttl_hours: float = 240.0,
        max_concurrent_requests: int = 5,
        request_delay: float = 0.2,
        auth_password: str | None = None,
    ) -> "AsyncAudibleClient":
        """
        Create async client from saved credentials file.

        Supports encrypted auth files. If the file is encrypted, a password
        must be provided via auth_password or AUDIBLE_AUTH_PASSWORD env var.

        Args:
            auth_file: Path to saved auth credentials
            cache: Optional SQLiteCache instance
            cache_ttl_hours: Cache TTL in hours
            max_concurrent_requests: Max concurrent requests
            request_delay: Delay between requests
            auth_password: Password for encrypted auth files (or use AUDIBLE_AUTH_PASSWORD env var)

        Returns:
            Configured AsyncAudibleClient

        Raises:
            AsyncAudibleAuthError: If credentials file is invalid/missing or encrypted without password
        """
        auth_path = Path(auth_file)
        if not auth_path.exists():
            raise AsyncAudibleAuthError(f"Auth file not found: {auth_file}")

        # Build encryption config (uses env var if no password provided)
        enc_config = get_encryption_config(password=auth_password)

        try:
            auth = load_auth(auth_path, enc_config)
        except ValueError as e:
            raise AsyncAudibleAuthError(str(e)) from e
        except Exception as e:
            raise AsyncAudibleAuthError(f"Failed to load auth: {e}") from e

        return cls(
            auth=auth,
            cache=cache,
            cache_ttl_hours=cache_ttl_hours,
            max_concurrent_requests=max_concurrent_requests,
            request_delay=request_delay,
        )

    async def __aenter__(self) -> "AsyncAudibleClient":
        """Async context manager entry."""
        self._client = audible.AsyncClient(auth=self._auth)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    async def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        loop = asyncio.get_running_loop()
        now = loop.time()
        elapsed = now - self._last_request_time
        if elapsed < self._request_delay:
            await asyncio.sleep(self._request_delay - elapsed)
        self._last_request_time = loop.time()

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> dict:
        """
        Make an async API request with rate limiting and semaphore.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "library", "catalog/products/B00123")
            **kwargs: Additional request parameters

        Returns:
            Response data as dict
        """
        if not self._client:
            raise AsyncAudibleError("Client not initialized. Use 'async with' context manager.")

        async with self._semaphore:
            await self._rate_limit()

            response: Any = None
            try:
                if method.upper() == "GET":
                    response = await self._client.get(path=path, params=kwargs)
                elif method.upper() == "POST":
                    response = await self._client.post(path=path, body=kwargs.get("json", {}))
                elif method.upper() == "DELETE":
                    response = await self._client.delete(path=path)
                else:
                    raise AsyncAudibleError(f"Unsupported method: {method}")

                return cast(dict[Any, Any], response)

            except audible.exceptions.NotFoundError as e:
                raise AsyncAudibleNotFoundError(str(e)) from e
            except Exception as e:
                raise AsyncAudibleError(str(e)) from e

    # -------------------------------------------------------------------------
    # Library Methods
    # -------------------------------------------------------------------------

    async def get_library(
        self,
        num_results: int = 1000,
        page: int = 1,
        sort_by: LibrarySortBy | str = LibrarySortBy.PURCHASE_DATE_DESC,
        status: LibraryStatus | str = LibraryStatus.ACTIVE,
        use_cache: bool = True,
    ) -> list[AudibleLibraryItem]:
        """
        Get the user's Audible library asynchronously.

        Args:
            num_results: Max results per page
            page: Page number
            sort_by: Sort order
            status: Filter by status
            use_cache: Whether to use cache

        Returns:
            List of library items
        """
        sort_value = sort_by.value if isinstance(sort_by, LibrarySortBy) else sort_by
        status_value = status.value if isinstance(status, LibraryStatus) else status
        cache_key = f"library_p{page}_n{num_results}_{sort_value}_{status_value}"

        # Check cache
        if use_cache and self._cache:
            cached = self._cache.get("library", cache_key)
            if cached:
                return [AudibleLibraryItem.model_validate(item) for item in cached]

        response = await self._request(
            "GET",
            "library",
            num_results=num_results,
            page=page,
            response_groups=LIBRARY_RESPONSE_GROUPS,
            sort_by=sort_value,
            status=status_value,
        )

        items_data = response.get("items", [])
        items = []
        for idx, item_data in enumerate(items_data):
            try:
                items.append(AudibleLibraryItem.model_validate(item_data))
            except ValidationError as e:
                logger.debug(
                    "Failed to validate library item at index %d: %s. Item data: %s",
                    idx,
                    str(e),
                    item_data.get("asin", "<unknown ASIN>"),
                )
                pass

        # Cache results
        if self._cache:
            self._cache.set("library", cache_key, [i.model_dump() for i in items], ttl_seconds=self._cache_ttl_seconds)

        return items

    async def get_all_library_items(
        self,
        use_cache: bool = True,
    ) -> list[AudibleLibraryItem]:
        """Get all library items with pagination."""
        all_items: list[AudibleLibraryItem] = []
        page = 1

        while True:
            items = await self.get_library(num_results=1000, page=page, use_cache=use_cache)
            if not items:
                break
            all_items.extend(items)
            if len(items) < 1000:
                break
            page += 1

        return all_items

    async def get_library_item(
        self,
        asin: str,
        use_cache: bool = True,
    ) -> AudibleLibraryItem | None:
        """Get a specific library item by ASIN."""
        cache_key = f"library_item_{asin}"

        if use_cache and self._cache:
            cached = self._cache.get("library", cache_key)
            if cached:
                return AudibleLibraryItem.model_validate(cached)

        try:
            response = await self._request(
                "GET",
                f"library/{asin}",
                response_groups=LIBRARY_RESPONSE_GROUPS,
            )

            item_data = response.get("item", response)
            item = AudibleLibraryItem.model_validate(item_data)

            if self._cache:
                self._cache.set("library", cache_key, item.model_dump(), ttl_seconds=self._cache_ttl_seconds)

            return item

        except AsyncAudibleNotFoundError:
            return None

    # -------------------------------------------------------------------------
    # Catalog Methods
    # -------------------------------------------------------------------------

    async def get_catalog_product(
        self,
        asin: str,
        use_cache: bool = True,
    ) -> AudibleCatalogProduct | None:
        """Get a catalog product by ASIN."""
        cache_key = f"catalog_{asin}"

        if use_cache and self._cache:
            cached = self._cache.get("catalog", cache_key)
            if cached:
                try:
                    return AudibleCatalogProduct.model_validate(cached)
                except ValidationError:
                    # Cached data is invalid, continue to fetch fresh
                    pass

        try:
            response = await self._request(
                "GET",
                f"catalog/products/{asin}",
                response_groups=CATALOG_RESPONSE_GROUPS,
            )

            product_data = response.get("product", response)
            product = AudibleCatalogProduct.model_validate(product_data)

            if self._cache:
                self._cache.set("catalog", cache_key, product.model_dump(), ttl_seconds=self._cache_ttl_seconds)

            return product

        except AsyncAudibleNotFoundError:
            return None
        except ValidationError as e:
            # Product data is malformed (e.g., missing title for delisted product)
            logger.debug("Invalid catalog product data for ASIN %s: %s", asin, str(e))
            return None

    async def get_multiple_products(
        self,
        asins: list[str],
        use_cache: bool = True,
    ) -> list[AudibleCatalogProduct]:
        """
        Get multiple catalog products concurrently.

        This is the main advantage of the async client - fetching
        many products at once without blocking.

        Args:
            asins: List of ASINs to fetch
            use_cache: Whether to use cache

        Returns:
            List of products (None entries filtered out)
        """
        tasks = [self.get_catalog_product(asin, use_cache=use_cache) for asin in asins]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        products = []
        for result in results:
            if isinstance(result, AudibleCatalogProduct):
                products.append(result)
            elif isinstance(result, Exception):
                logger.warning("Failed to fetch product: %s", result)

        return products

    async def search_catalog(
        self,
        keywords: str | None = None,
        title: str | None = None,
        author: str | None = None,
        narrator: str | None = None,
        num_results: int = 50,
        sort_by: CatalogSortBy | str = CatalogSortBy.RELEVANCE,
        use_cache: bool = True,
    ) -> list[AudibleCatalogProduct]:
        """Search the Audible catalog."""
        sort_value = sort_by.value if isinstance(sort_by, CatalogSortBy) else sort_by
        search_params = f"{keywords}|{title}|{author}|{narrator}|{sort_value}"
        cache_key = hashlib.md5(search_params.encode(), usedforsecurity=False).hexdigest()

        if use_cache and self._cache:
            cached = self._cache.get("search", cache_key)
            if cached:
                return [AudibleCatalogProduct.model_validate(p) for p in cached]

        params: dict[str, Any] = {
            "num_results": min(num_results, 50),
            "products_sort_by": sort_value,
            "response_groups": CATALOG_RESPONSE_GROUPS,
        }
        if keywords:
            params["keywords"] = keywords
        if title:
            params["title"] = title
        if author:
            params["author"] = author
        if narrator:
            params["narrator"] = narrator

        response = await self._request("GET", "catalog/products", **params)

        products_data = response.get("products", [])
        products = []
        for idx, prod_data in enumerate(products_data):
            try:
                products.append(AudibleCatalogProduct.model_validate(prod_data))
            except ValidationError as e:
                logger.debug(
                    "Failed to validate catalog product at index %d: %s. Product ASIN: %s",
                    idx,
                    str(e),
                    prod_data.get("asin", "<unknown ASIN>"),
                )
                pass

        if self._cache:
            self._cache.set(
                "search", cache_key, [p.model_dump() for p in products], ttl_seconds=self._cache_ttl_seconds
            )

        return products

    # -------------------------------------------------------------------------
    # Similar Products / Series Discovery
    # -------------------------------------------------------------------------

    async def get_similar_products(
        self,
        asin: str,
        similarity_type: SimilarityType | str = SimilarityType.IN_SAME_SERIES,
        num_results: int = 50,
        use_cache: bool = True,
    ) -> list[AudibleCatalogProduct]:
        """Get similar products using the /sims endpoint."""
        sim_value = similarity_type.value if isinstance(similarity_type, SimilarityType) else similarity_type
        cache_key = f"sims_{asin}_{sim_value}"

        if use_cache and self._cache:
            cached = self._cache.get("catalog", cache_key)
            if cached:
                return [AudibleCatalogProduct.model_validate(p) for p in cached]

        try:
            response = await self._request(
                "GET",
                f"catalog/products/{asin}/sims",
                similarity_type=sim_value,
                num_results=min(num_results, 50),
                response_groups=CATALOG_RESPONSE_GROUPS,
            )

            products_data = response.get("similar_products", [])
            products = []
            for idx, prod_data in enumerate(products_data):
                try:
                    products.append(AudibleCatalogProduct.model_validate(prod_data))
                except ValidationError as e:
                    logger.debug(
                        "Failed to validate similar product at index %d for ASIN %s: %s. Product ASIN: %s",
                        idx,
                        asin,
                        str(e),
                        prod_data.get("asin", "<unknown ASIN>"),
                    )
                    pass

            if self._cache:
                self._cache.set(
                    "catalog", cache_key, [p.model_dump() for p in products], ttl_seconds=self._cache_ttl_seconds
                )

            return products

        except AsyncAudibleNotFoundError:
            return []

    async def get_series_books(
        self,
        asin: str,
        use_cache: bool = True,
    ) -> list[AudibleCatalogProduct]:
        """Discover all books in a series."""
        return await self.get_similar_products(
            asin=asin,
            similarity_type=SimilarityType.IN_SAME_SERIES,
            num_results=50,
            use_cache=use_cache,
        )

    # -------------------------------------------------------------------------
    # Wishlist Methods
    # -------------------------------------------------------------------------

    async def get_wishlist(
        self,
        num_results: int = 50,
        page: int = 0,
        sort_by: WishlistSortBy | str = WishlistSortBy.DATE_ADDED_DESC,
        use_cache: bool = True,
    ) -> list[WishlistItem]:
        """Get wishlist items."""
        sort_value = sort_by.value if isinstance(sort_by, WishlistSortBy) else sort_by
        cache_key = f"wishlist_p{page}_{sort_value}"

        if use_cache and self._cache:
            cached = self._cache.get("library", cache_key)
            if cached:
                return [WishlistItem.model_validate(p) for p in cached]

        response = await self._request(
            "GET",
            "wishlist",
            num_results=min(num_results, 50),
            page=page,
            sort_by=sort_value,
            response_groups=ResponseGroups.WISHLIST_FULL,
        )

        products_data = response.get("products", [])
        products = []
        for idx, prod_data in enumerate(products_data):
            try:
                products.append(WishlistItem.model_validate(prod_data))
            except ValidationError as e:
                logger.debug(
                    "Failed to validate wishlist item at index %d: %s. Item ASIN: %s",
                    idx,
                    str(e),
                    prod_data.get("asin", "<unknown ASIN>"),
                )
                pass

        if self._cache:
            self._cache.set(
                "library", cache_key, [p.model_dump() for p in products], ttl_seconds=self._cache_ttl_seconds
            )

        return products

    async def add_to_wishlist(self, asin: str) -> bool:
        """Add a book to wishlist."""
        try:
            await self._request("POST", "wishlist", json={"asin": asin})
            if self._cache:
                self._cache.clear_namespace("library")
            return True
        except AsyncAudibleError:
            return False

    async def remove_from_wishlist(self, asin: str) -> bool:
        """Remove a book from wishlist."""
        try:
            await self._request("DELETE", f"wishlist/{asin}")
            if self._cache:
                self._cache.clear_namespace("library")
            return True
        except AsyncAudibleError:
            return False

    # -------------------------------------------------------------------------
    # Recommendations
    # -------------------------------------------------------------------------

    async def get_recommendations(
        self,
        num_results: int = 50,
        use_cache: bool = True,
    ) -> list[AudibleCatalogProduct]:
        """Get personalized recommendations."""
        cache_key = f"recommendations_{num_results}"

        if use_cache and self._cache:
            cached = self._cache.get("catalog", cache_key)
            if cached:
                return [AudibleCatalogProduct.model_validate(p) for p in cached]

        try:
            response = await self._request(
                "GET",
                "recommendations",
                num_results=min(num_results, 50),
                response_groups=ResponseGroups.RECOMMENDATIONS,
            )

            products_data = response.get("products", [])
            products = []
            for idx, prod_data in enumerate(products_data):
                try:
                    products.append(AudibleCatalogProduct.model_validate(prod_data))
                except ValidationError as e:
                    logger.debug(
                        "Failed to validate catalog product at index %d: %s. Product ASIN: %s",
                        idx,
                        str(e),
                        prod_data.get("asin", "<unknown ASIN>"),
                    )
                    pass

            if self._cache:
                self._cache.set(
                    "catalog", cache_key, [p.model_dump() for p in products], ttl_seconds=self._cache_ttl_seconds
                )

            return products

        except AsyncAudibleError:
            return []

    # -------------------------------------------------------------------------
    # Content Metadata
    # -------------------------------------------------------------------------

    async def get_content_metadata(
        self,
        asin: str,
        quality: str = "High",
        drm_type: str | None = None,
        use_cache: bool = True,
    ) -> ContentMetadata | None:
        """
        Get content metadata including chapter info and codecs.

        When drm_type is specified (Widevine or Adrm), the response includes
        actual codec and content size for quality/bitrate discovery. This is
        ~3x faster than license requests for quality checking.

        Args:
            asin: Audible ASIN
            quality: Quality level ("High" or "Normal")
            drm_type: Optional DRM type for quality discovery ("Widevine" or "Adrm")
                      - Widevine: Returns modern formats (HE-AAC, Atmos)
                      - Adrm: Returns legacy AAC-LC format
            use_cache: Use cached results

        Returns:
            ContentMetadata with chapter info and quality data
        """
        cache_key = f"content_meta_{asin}_{quality}_{drm_type or 'none'}"

        if use_cache and self._cache:
            cached = self._cache.get("content_metadata", cache_key)
            if cached:
                return ContentMetadata.model_validate(cached)

        try:
            # Build request params
            params: dict[str, str] = {
                "response_groups": "chapter_info,content_reference",
                "quality": quality,
            }
            if drm_type:
                params["drm_type"] = drm_type

            response = await self._request(
                "GET",
                f"content/{asin}/metadata",
                **params,
            )

            # Handle both response structures:
            # - Old: {"chapter_info": {...}, "content_reference": {...}}
            # - New with drm_type: {"content_metadata": {"chapter_info": {...}, "content_reference": {...}}}
            data = response.get("content_metadata", response)

            metadata = ContentMetadata(
                asin=asin,
                acr=data.get("content_reference", {}).get("acr"),
                chapter_info=data.get("chapter_info"),
                content_reference=data.get("content_reference"),
                drm_type=drm_type,
            )

            content_ref = data.get("content_reference", {})
            if "available_codec" in content_ref:
                metadata.available_codecs = content_ref["available_codec"]

            if self._cache:
                self._cache.set(
                    "content_metadata",
                    cache_key,
                    metadata.model_dump(),
                    ttl_seconds=self._cache_ttl_seconds,
                )

            return metadata

        except AsyncAudibleError:
            return None

    async def supports_dolby_atmos(self, asin: str, use_cache: bool = True) -> bool:
        """Check if a book supports Dolby Atmos."""
        metadata = await self.get_content_metadata(asin, use_cache=use_cache)
        return metadata.supports_atmos if metadata else False

    # -------------------------------------------------------------------------
    # Fast Quality Discovery (via Metadata Endpoint)
    # -------------------------------------------------------------------------

    async def fast_quality_check(
        self,
        asin: str,
        use_cache: bool = True,
    ) -> ContentQualityInfo | None:
        """
        Fast quality check using metadata endpoint (~3x faster than license requests).

        This method uses the /content/{asin}/metadata endpoint with drm_type parameter
        to discover the actual audio quality available. It's much faster than the
        license request approach because:
        - Single GET request vs multiple POST requests
        - Less aggressive rate limiting
        - Returns same codec/size data

        Discovered via Libation PR #1527.

        Args:
            asin: Audible ASIN
            use_cache: Use cached results

        Returns:
            ContentQualityInfo with best available format info, or None if failed
        """
        cache_key = f"fast_quality_{asin}"

        if use_cache and self._cache:
            cached = self._cache.get("content_quality", cache_key)
            if cached:
                return ContentQualityInfo.model_validate(cached)

        formats: list[AudioFormat] = []

        # Try Widevine first (modern formats: HE-AAC/USAC, Atmos)
        widevine = await self.get_content_metadata(asin, drm_type="Widevine", use_cache=use_cache)
        if widevine and widevine.parsed_content_ref:
            ref = widevine.parsed_content_ref
            if ref.bitrate_kbps > 0:
                formats.append(
                    AudioFormat(
                        codec=ref.codec or "unknown",
                        codec_name=ref.codec_name,
                        drm_type="Widevine",
                        bitrate_kbps=ref.bitrate_kbps,
                        size_bytes=ref.content_size_bytes,
                        runtime_ms=ref.runtime_ms,
                        is_spatial=ref.is_atmos,
                    )
                )

        # Also try Adrm for comparison (legacy AAC-LC format)
        adrm = await self.get_content_metadata(asin, drm_type="Adrm", use_cache=use_cache)
        if adrm and adrm.parsed_content_ref:
            ref = adrm.parsed_content_ref
            if ref.bitrate_kbps > 0:
                formats.append(
                    AudioFormat(
                        codec=ref.codec or "unknown",
                        codec_name=ref.codec_name,
                        drm_type="Adrm",
                        bitrate_kbps=ref.bitrate_kbps,
                        size_bytes=ref.content_size_bytes,
                        runtime_ms=ref.runtime_ms,
                        is_spatial=ref.is_atmos,
                    )
                )

        if formats:
            quality_info = ContentQualityInfo.from_formats(asin, formats)

            if self._cache:
                self._cache.set(
                    "content_quality",
                    cache_key,
                    quality_info.model_dump(),
                    ttl_seconds=self._cache_ttl_seconds,
                )

            return quality_info

        return None

    async def fast_quality_check_multiple(
        self,
        asins: list[str],
        use_cache: bool = True,
        max_concurrent: int = 10,
    ) -> dict[str, ContentQualityInfo]:
        """
        Fast quality check for multiple ASINs concurrently.

        Args:
            asins: List of Audible ASINs
            use_cache: Use cached results
            max_concurrent: Maximum concurrent requests

        Returns:
            Dict mapping ASIN to ContentQualityInfo
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def check_one(asin: str) -> tuple[str, ContentQualityInfo | None]:
            async with semaphore:
                result = await self.fast_quality_check(asin, use_cache=use_cache)
                return asin, result

        tasks = [check_one(asin) for asin in asins]
        results = await asyncio.gather(*tasks)

        return {asin: quality for asin, quality in results if quality is not None}

    # -------------------------------------------------------------------------
    # Content License / Quality Discovery (Full - Slower but More Detailed)
    # -------------------------------------------------------------------------

    async def request_content_license(
        self,
        asin: str,
        codecs: list[str],
        drm_types: list[str],
        *,
        spatial: bool = False,
        quality: str = "High",
    ) -> dict | None:
        """
        Request a content license to discover actual audio quality.

        This is the only reliable way to get actual bitrate/size info for
        modern Widevine/FairPlay formats. The catalog's available_codecs
        field only shows legacy AAX formats.

        Args:
            asin: Audible ASIN
            codecs: List of codec identifiers (mp4a.40.2, mp4a.40.42, ec+3, ac-4)
            drm_types: List of DRM types (Adrm, Widevine, FairPlay)
            spatial: Request spatial audio (for Dolby Atmos) (keyword-only)
            quality: Quality level (High, Normal)

        Returns:
            License response dict or None if codec not available
        """
        try:
            response = await self._request(
                "POST",
                f"1.0/content/{asin}/licenserequest",
                json={
                    "quality": quality,
                    "response_groups": "chapter_info,content_reference",
                    "consumption_type": "Download",
                    "spatial": spatial,
                    "supported_media_features": {
                        "codecs": codecs,
                        "drm_types": drm_types,
                    },
                },
            )
            return response if "content_license" in response else None
        except AsyncAudibleError as e:
            logger.debug(
                "License request failed for ASIN %s (codecs=%s, drm=%s, spatial=%s): %s",
                asin,
                codecs,
                drm_types,
                spatial,
                e,
            )
            return None

    async def get_audio_format(
        self,
        asin: str,
        config: dict,
    ) -> AudioFormat | None:
        """
        Discover a specific audio format via license request.

        Args:
            asin: Audible ASIN
            config: Format config dict with keys: name, codecs, drm_types, spatial

        Returns:
            AudioFormat if available, None otherwise
        """
        response = await self.request_content_license(
            asin=asin,
            codecs=config["codecs"],
            drm_types=config["drm_types"],
            spatial=config.get("spatial", False),
        )

        if not response:
            return None

        license_info = response.get("content_license", {})
        content_meta = license_info.get("content_metadata", {})
        content_ref = content_meta.get("content_reference", {})
        chapter_info = content_meta.get("chapter_info", {})

        actual_codec = content_ref.get("codec", config["codecs"][0])
        content_size = content_ref.get("content_size_in_bytes", 0)
        drm_type = license_info.get("drm_type", config["drm_types"][0])
        runtime_ms = chapter_info.get("runtime_length_ms", 0)

        # Calculate bitrate from size and runtime
        bitrate = 0.0
        if runtime_ms > 0 and content_size > 0:
            bitrate = (content_size * 8) / (runtime_ms / 1000) / 1000

        return AudioFormat(
            codec=actual_codec,
            codec_name=config["name"],
            drm_type=drm_type,
            bitrate_kbps=bitrate,
            size_bytes=content_size,
            runtime_ms=runtime_ms,
            is_spatial=config.get("spatial", False),
        )

    async def discover_content_quality(
        self,
        asin: str,
        *,
        use_cache: bool = True,
    ) -> ContentQualityInfo:
        """
        Discover all available audio formats and quality for an audiobook.

        This method tests multiple codec/DRM combinations via license requests
        to find the actual best quality available, including modern formats
        like Widevine HE-AAC (114 kbps) and Dolby Atmos.

        The catalog API's available_codecs field only shows legacy AAX formats
        (max ~64 kbps), so this is the only way to get accurate quality info.

        Args:
            asin: Audible ASIN
            use_cache: Use cached results (keyword-only)

        Returns:
            ContentQualityInfo with all discovered formats
        """
        cache_key = f"quality_{asin}"

        if use_cache and self._cache:
            cached = self._cache.get("content_quality", cache_key)
            if cached:
                return ContentQualityInfo.model_validate(cached)

        # Test all codec configurations concurrently
        tasks = [self.get_audio_format(asin, config) for config in LICENSE_TEST_CONFIGS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        formats = []
        for result in results:
            if isinstance(result, AudioFormat):
                formats.append(result)

        quality_info = ContentQualityInfo.from_formats(asin, formats)

        if self._cache:
            self._cache.set(
                "content_quality",
                cache_key,
                quality_info.model_dump(),
                ttl_seconds=self._cache_ttl_seconds,
            )

        return quality_info

    async def discover_multiple_quality(
        self,
        asins: list[str],
        *,
        use_cache: bool = True,
    ) -> dict[str, ContentQualityInfo]:
        """
        Discover content quality for multiple ASINs concurrently.

        Args:
            asins: List of Audible ASINs
            use_cache: Use cached results (keyword-only)

        Returns:
            Dict mapping ASIN to ContentQualityInfo
        """
        tasks = [self.discover_content_quality(asin, use_cache=use_cache) for asin in asins]
        results = await asyncio.gather(*tasks)

        quality_map = {}
        for asin, result in zip(asins, results, strict=True):
            if isinstance(result, ContentQualityInfo):
                quality_map[asin] = result

        return quality_map

    # -------------------------------------------------------------------------
    # Account & Stats
    # -------------------------------------------------------------------------

    async def get_listening_stats(
        self,
        use_cache: bool = True,
    ) -> AudibleListeningStats | None:
        """Get listening statistics."""
        cache_key = "listening_stats"

        if use_cache and self._cache:
            cached = self._cache.get("stats", cache_key)
            if cached:
                return AudibleListeningStats.model_validate(cached)

        try:
            response = await self._request(
                "GET",
                "stats/aggregates",
                response_groups="total_listening_stats",
            )

            stats = AudibleListeningStats.model_validate(response)

            if self._cache:
                self._cache.set("stats", cache_key, stats.model_dump(), ttl_seconds=self._cache_ttl_seconds)

            return stats

        except AsyncAudibleError:
            return None

    async def get_account_info(
        self,
        use_cache: bool = True,
    ) -> AudibleAccountInfo | None:
        """Get account information."""
        cache_key = "account_info"

        if use_cache and self._cache:
            cached = self._cache.get("account", cache_key)
            if cached:
                return AudibleAccountInfo.model_validate(cached)

        try:
            response = await self._request(
                "GET",
                "account/information",
                response_groups="customer_benefits,subscription_details,plan_summary",
            )

            info = AudibleAccountInfo.model_validate(response)

            if self._cache:
                self._cache.set("account", cache_key, info.model_dump(), ttl_seconds=self._cache_ttl_seconds)

            return info

        except AsyncAudibleError:
            return None

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_pricing(price_data: dict[str, Any] | None) -> PricingInfo | None:
        """Parse pricing data from API response."""
        return PricingInfo.from_api_response(price_data)

    @staticmethod
    def parse_plus_catalog(plans: list[dict[str, Any]] | None) -> PlusCatalogInfo:
        """Parse plans array for Plus Catalog info."""
        return PlusCatalogInfo.from_api_response(plans)
