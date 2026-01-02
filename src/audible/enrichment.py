"""
Audible enrichment service.

Provides rich metadata enrichment for audiobooks by combining:
- Catalog data (pricing, availability, quality)
- Library data (ownership status)
- Plus Catalog info (free listening availability)
- Actual audio quality via license requests

This module is used by multiple features:
- Quality analysis (upgrade candidates)
- Series matching (missing books pricing)
- Any feature needing rich Audible metadata
"""

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional, cast

from pydantic import BaseModel, Field, ValidationError

from .client import AudibleClient
from .models import ContentQualityInfo, PlusCatalogInfo, PricingInfo

if TYPE_CHECKING:
    from ..cache import SQLiteCache
    from .async_client import AsyncAudibleClient
else:
    # Import for exception handling at runtime
    from .async_client import AsyncAudibleError


logger = logging.getLogger(__name__)


class AudibleEnrichment(BaseModel):
    """
    Full Audible enrichment data for an audiobook.

    Combines pricing, Plus Catalog status, quality info, and ownership
    into a single model for easy consumption.
    """

    asin: str = Field(description="Audible ASIN")
    title: str | None = Field(default=None, description="Title from Audible")

    # Ownership
    owned: bool = Field(default=False, description="User owns this on Audible")
    origin_type: str | None = Field(default=None, description="How acquired (Purchase, Ayce, etc)")

    # Pricing
    pricing: PricingInfo | None = Field(default=None, description="Pricing info")

    # Plus Catalog
    plus_catalog: PlusCatalogInfo = Field(default_factory=PlusCatalogInfo)

    # Quality available (from catalog API - may be incomplete)
    has_atmos: bool = Field(default=False, description="Dolby Atmos version available")
    best_bitrate: int | None = Field(default=None, description="Best available bitrate from catalog (kbps)")
    available_codecs: list[str] = Field(default_factory=list, description="Available codecs from catalog")

    # Actual quality from license requests (most accurate)
    actual_quality: ContentQualityInfo | None = Field(
        default=None, description="Actual quality info from license requests"
    )

    # API reliability
    api_quality_reliable: bool = Field(default=True, description="Whether API quality info is reliable")

    # URLs and images
    audible_url: str | None = Field(default=None, description="URL to Audible product page")
    cover_image_url: str | None = Field(default=None, description="URL to 500x500 cover image")

    model_config = {"extra": "ignore"}

    @property
    def actual_best_bitrate(self) -> int | None:
        """
        Get the actual best bitrate from license requests.

        This is more accurate than best_bitrate which comes from the catalog API
        and only shows legacy AAX formats (max ~64 kbps).
        """
        if self.actual_quality and self.actual_quality.best_bitrate_kbps > 0:
            return int(self.actual_quality.best_bitrate_kbps)
        return self.best_bitrate

    @property
    def actual_best_format(self) -> str | None:
        """Get the best format name from license request quality discovery."""
        if self.actual_quality and self.actual_quality.best_format:
            return self.actual_quality.best_format.codec_name
        return None

    @property
    def best_available_label(self) -> str:
        """Get a human-readable label for the best available quality."""
        if self.actual_quality:
            if self.actual_quality.has_atmos:
                return "Dolby Atmos"
            if self.actual_quality.best_format:
                fmt = self.actual_quality.best_format
                return f"{fmt.codec_name} @ {int(fmt.bitrate_kbps)} kbps"
        if self.has_atmos:
            return "Dolby Atmos"
        if self.best_bitrate:
            return f"{self.best_bitrate} kbps"
        return "Unknown"

    @property
    def acquisition_recommendation(self) -> str:
        """
        Get acquisition recommendation.

        Returns:
            Recommendation string: FREE, MONTHLY_DEAL, GOOD_DEAL, CREDIT, EXPENSIVE, OWNED, or N/A
        """
        if self.owned:
            return "OWNED"

        if self.plus_catalog.is_plus_catalog:
            if self.plus_catalog.is_expiring_soon:
                return f"FREE (expires {self.plus_catalog.expiration_display})"
            return "FREE"

        if self.pricing:
            # Monthly deals (type=sale) with big discounts
            if self.pricing.is_monthly_deal:
                discount = self.pricing.discount_percent or 0
                if discount >= 50:
                    return f"MONTHLY_DEAL (${self.pricing.effective_price:.2f}, {discount:.0f}% off)"

            if self.pricing.is_good_deal:
                discount = self.pricing.discount_percent or 0
                if discount > 0:
                    return f"GOOD_DEAL (${self.pricing.effective_price:.2f}, {discount:.0f}% off)"
                return f"GOOD_DEAL (${self.pricing.effective_price:.2f})"
            elif self.pricing.credit_price == 1.0:
                return "CREDIT"
            else:
                return f"EXPENSIVE (${self.pricing.effective_price:.2f})"

        return "N/A"

    @property
    def priority_boost(self) -> float:
        """
        Priority multiplier for upgrade sorting.

        Higher boost = more urgent to acquire.
        """
        boost = 1.0

        # Plus Catalog items get highest priority (FREE!)
        if self.plus_catalog.is_plus_catalog:
            boost = 5.0
            # Extra boost for expiring soon
            if self.plus_catalog.is_expiring_soon:
                days = self.plus_catalog.days_until_expiration or 30
                # More urgent as expiration approaches
                boost += (30 - days) / 6  # Up to +5 for same-day

        # Monthly deals with big discounts (50%+) - time limited!
        elif self.pricing and self.pricing.is_monthly_deal:
            discount = self.pricing.discount_percent or 0
            if discount >= 70:
                boost = 4.0  # Almost as good as free!
            elif discount >= 50:
                boost = 3.5
            elif self.pricing.is_good_deal:
                boost = 3.0

        # Good deals get priority
        elif self.pricing and self.pricing.is_good_deal:
            boost = 2.5
            discount = self.pricing.discount_percent or 0
            if discount >= 50:
                boost = 3.0

        # Atmos upgrade available
        if self.has_atmos:
            boost += 0.5

        # Already owned - no need to acquire
        if self.owned:
            boost = 0.1  # Still show but deprioritize

        return boost


class AudibleEnrichmentService:
    """
    Service for enriching audiobooks with Audible data.

    Uses caching to avoid repeated API calls. Can be used by any feature
    that needs rich Audible metadata (quality analysis, series matching, etc.).

    Note: Cache TTL is calculated to not extend past month boundaries since
    Audible's monthly deals reset on the 1st of each month.
    """

    CACHE_NAMESPACE = "audible_enrichment"
    CACHE_TTL_SECONDS = 3600 * 6  # 6 hours base (actual TTL may be shorter near month end)

    def __init__(
        self,
        client: AudibleClient,
        cache: Optional["SQLiteCache"] = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ):
        """
        Initialize enrichment service.

        Args:
            client: Authenticated AudibleClient
            cache: Optional SQLiteCache for caching enrichment results
            progress_callback: Optional callback(current, total, message)
        """
        self._client = client
        self._cache = cache
        self._progress = progress_callback
        self._library_asins: set[str] | None = None

        # Stats for timing
        self._cache_hits = 0
        self._api_calls = 0

    @property
    def stats(self) -> dict[str, int]:
        """Get enrichment stats."""
        return {
            "cache_hits": self._cache_hits,
            "api_calls": self._api_calls,
        }

    def _load_library_asins(self) -> set[str]:
        """Load all ASINs from user's Audible library."""
        if self._library_asins is None:
            library = self._client.get_all_library_items(use_cache=True)
            self._library_asins = {item.asin for item in library}
        return self._library_asins

    def _get_catalog_product(self, asin: str) -> dict[str, Any]:
        """Get product data from Audible catalog API."""
        return cast(
            dict[str, Any],
            self._client._request(
                "GET",
                f"1.0/catalog/products/{asin}",
                response_groups="contributors,media,product_attrs,product_desc,product_details,product_extended_attrs,series,category_ladders,customer_rights,price",
            ),
        )

    def enrich_single(self, asin: str, use_cache: bool = True) -> AudibleEnrichment | None:
        """
        Enrich a single ASIN with Audible data.

        Args:
            asin: Audible ASIN
            use_cache: Use cached data if available

        Returns:
            AudibleEnrichment or None if not found
        """
        cache_key = f"enrich_{asin}"

        # Check cache first (no rate limiting!)
        if use_cache and self._cache:
            cached = self._cache.get(self.CACHE_NAMESPACE, cache_key)
            if cached:
                self._cache_hits += 1
                enrichment = AudibleEnrichment.model_validate(cached)
                # Update ownership from current library (may have changed)
                library_asins = self._load_library_asins()
                enrichment.owned = asin in library_asins
                return enrichment

        # Check ownership
        library_asins = self._load_library_asins()
        owned = asin in library_asins

        # Get catalog data via raw API for plans field
        self._api_calls += 1
        try:
            response = self._get_catalog_product(asin)
            if not response:
                logger.debug("No catalog response for ASIN %s", asin)
                return None

            product = response.get("product", response)
        except Exception as e:
            logger.debug(
                "Failed to get catalog product for ASIN %s: %s",
                asin,
                str(e),
            )
            return None

        if not product:
            return None

        # Parse data
        enrichment = AudibleEnrichment(
            asin=asin,
            title=product.get("title"),
            owned=owned,
        )

        # Audible URL
        enrichment.audible_url = f"https://www.audible.com/pd/{asin}"

        # Cover image URL (from product_images)
        product_images = cast(dict[str, Any], product.get("product_images", {}))
        if product_images:
            # Prefer 500px, fall back to largest available
            enrichment.cover_image_url = cast(
                str | None,
                product_images.get("500")
                or product_images.get("1024")
                or product_images.get("252")
                or next(iter(product_images.values()), None),
            )

        # Pricing - use shared parsing
        enrichment.pricing = PricingInfo.from_api_response(cast(dict[str, Any] | None, product.get("price")))

        # Plus Catalog from plans - use shared parsing
        enrichment.plus_catalog = PlusCatalogInfo.from_api_response(
            cast(list[dict[str, Any]], product.get("plans", []))
        )

        # Available codecs
        available_codecs = cast(list[dict[str, Any]], product.get("available_codecs", []))
        enrichment.available_codecs = [cast(str, c.get("name", "")) for c in available_codecs]

        # Check for Atmos
        enrichment.has_atmos = product.get("has_dolby_atmos", False)

        # For spatial audio detection via asset_details
        asset_details = product.get("asset_details", [])
        for asset in asset_details:
            if asset.get("is_spatial"):
                enrichment.has_atmos = True
                break

        # Best bitrate from codecs
        # The "name" field has format like "aax_44_128" or "mp4_44_128" where:
        #   - "aax" or "mp4" = format
        #   - "44" or "22" = sample rate (44.1kHz or 22.05kHz)
        #   - "128" or "64" = bitrate in kbps
        # The "enhanced_codec" field has format like "LC_128_44100_stereo" where:
        #   - "LC" = codec type (AAC-LC)
        #   - "128" = bitrate (second part)
        #   - "44100" = sample rate
        #   - "stereo" = channel layout
        for codec in available_codecs:
            # Method 1: Parse from "name" field (most reliable)
            # Format: "aax_44_128" -> bitrate is the last number
            codec_name = codec.get("name", "")
            if "_" in codec_name:
                parts = codec_name.split("_")
                # Last numeric part is typically the bitrate
                for part in reversed(parts):
                    if part.isdigit():
                        bitrate = int(part)
                        # Filter out sample rates (22050, 44100) - bitrates are typically <= 320
                        if bitrate <= 320 and bitrate > (enrichment.best_bitrate or 0):
                            enrichment.best_bitrate = bitrate
                        break

            # Method 2: Parse from "enhanced_codec" field as fallback
            # Format: "LC_128_44100_stereo" -> bitrate is typically second part
            enhanced_codec = codec.get("enhanced_codec", "")
            if "_" in enhanced_codec and not enrichment.best_bitrate:
                parts = enhanced_codec.split("_")
                if len(parts) >= 2 and parts[1].isdigit():
                    bitrate = int(parts[1])
                    if bitrate <= 320 and bitrate > (enrichment.best_bitrate or 0):
                        enrichment.best_bitrate = bitrate

        # API reliability - unreliable for Atmos/USAC
        if enrichment.has_atmos:
            enrichment.api_quality_reliable = False

        # Cache result (ownership excluded since it's checked separately)
        # Use month-boundary-aware TTL to avoid stale pricing across month resets
        if self._cache:
            from ..cache.sqlite_cache import calculate_pricing_ttl_seconds

            ttl = calculate_pricing_ttl_seconds(self.CACHE_TTL_SECONDS)
            self._cache.set(self.CACHE_NAMESPACE, cache_key, enrichment.model_dump(), ttl_seconds=ttl)

        return enrichment

    def enrich_batch(
        self,
        asins: list[str],
        use_cache: bool = True,
    ) -> dict[str, AudibleEnrichment]:
        """
        Enrich multiple ASINs with Audible data.

        Args:
            asins: List of ASINs to enrich
            use_cache: Use cached data if available

        Returns:
            Dict mapping ASIN to enrichment data
        """
        results = {}
        total = len(asins)

        # Preload library for ownership check
        self._load_library_asins()

        for i, asin in enumerate(asins):
            if self._progress:
                self._progress(i + 1, total, f"Enriching {asin}...")

            enrichment = self.enrich_single(asin, use_cache=use_cache)
            if enrichment:
                results[asin] = enrichment

        return results


class AsyncAudibleEnrichmentService:
    """
    Async service for enriching audiobooks with Audible data including actual quality.

    This service uses the async client to make license requests and discover
    the actual best available audio quality (including modern formats like
    Widevine HE-AAC at ~114 kbps and Dolby Atmos).

    The catalog API's available_codecs field only shows legacy AAX formats
    (max ~64 kbps), so license requests are required for accurate quality info.

    Note: Cache TTL is calculated to not extend past month boundaries since
    Audible's monthly deals reset on the 1st of each month.

    Example:
        async with AsyncAudibleClient.from_file("auth.json") as client:
            service = AsyncAudibleEnrichmentService(client, cache)
            enrichments = await service.enrich_batch_with_quality(asins)
    """

    CACHE_NAMESPACE = "audible_enrichment_v2"  # New namespace for quality-enriched data
    CACHE_TTL_SECONDS = 3600 * 6  # 6 hours base (actual TTL may be shorter near month end)

    def __init__(
        self,
        async_client: "AsyncAudibleClient",
        cache: Optional["SQLiteCache"] = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ):
        """
        Initialize async enrichment service.

        Args:
            async_client: Authenticated AsyncAudibleClient (must be in context)
            cache: Optional SQLiteCache for caching enrichment results
            progress_callback: Optional callback(current, total, message)
        """
        self._client = async_client
        self._cache = cache
        self._progress = progress_callback
        self._library_asins: set[str] | None = None

        # Stats
        self._cache_hits = 0
        self._api_calls = 0
        self._quality_discoveries = 0

    @property
    def stats(self) -> dict[str, int]:
        """Get enrichment stats."""
        return {
            "cache_hits": self._cache_hits,
            "api_calls": self._api_calls,
            "quality_discoveries": self._quality_discoveries,
        }

    async def _load_library_asins(self) -> set[str]:
        """Load all ASINs from user's Audible library."""
        if self._library_asins is None:
            library = await self._client.get_all_library_items(use_cache=True)
            self._library_asins = {item.asin for item in library}
        return self._library_asins

    async def enrich_single_with_quality(
        self,
        asin: str,
        use_cache: bool = True,
        discover_quality: bool = True,
    ) -> AudibleEnrichment | None:
        """
        Enrich a single ASIN with Audible data including actual quality.

        Args:
            asin: Audible ASIN
            use_cache: Use cached data if available
            discover_quality: Make license requests to discover actual quality

        Returns:
            AudibleEnrichment or None if not found
        """
        cache_key = f"enrich_v2_{asin}"

        # Check cache first
        if use_cache and self._cache:
            cached = self._cache.get(self.CACHE_NAMESPACE, cache_key)
            if cached:
                self._cache_hits += 1
                enrichment = AudibleEnrichment.model_validate(cached)
                # Update ownership from current library (may have changed)
                library_asins = await self._load_library_asins()
                enrichment.owned = asin in library_asins
                return enrichment

        # Check ownership
        library_asins = await self._load_library_asins()
        owned = asin in library_asins

        # Get catalog product
        self._api_calls += 1
        try:
            product = await self._client.get_catalog_product(asin, use_cache=use_cache)
        except (AsyncAudibleError, ValidationError) as e:
            logger.debug("Failed to get catalog product for ASIN %s: %s", asin, str(e))
            return None

        if not product:
            return None

        # Build enrichment from catalog data
        enrichment = AudibleEnrichment(
            asin=asin,
            title=product.title,
            owned=owned,
        )

        # Audible URL
        enrichment.audible_url = f"https://www.audible.com/pd/{asin}"

        # Cover image URL
        if product.product_images:
            enrichment.cover_image_url = (
                product.product_images.get("500")
                or product.product_images.get("1024")
                or product.product_images.get("252")
                or next(iter(product.product_images.values()), None)
            )

        # Pricing
        enrichment.pricing = PricingInfo.from_api_response(product.price)

        # Plus Catalog - check is_ayce attribute and plans if available
        if product.is_ayce:
            enrichment.plus_catalog = PlusCatalogInfo(is_plus_catalog=True, plan_name="AYCE")
        elif hasattr(product, "plans") and product.plans:
            enrichment.plus_catalog = PlusCatalogInfo.from_api_response(product.plans)

        # Check for Atmos flag
        enrichment.has_atmos = getattr(product, "has_dolby_atmos", False) or product.is_ayce

        # Parse catalog bitrate from available_codecs as fallback (mirrors sync path)
        # Note: model_extra can be None even when attribute exists, so use `or {}`
        model_extra = getattr(product, "model_extra", None) or {}
        available_codecs = model_extra.get("available_codecs", []) if isinstance(model_extra, dict) else []
        if available_codecs:
            for codec in available_codecs:
                codec_name = codec.get("name", "")
                if "_" in codec_name:
                    parts = codec_name.split("_")
                    for part in reversed(parts):
                        if part.isdigit():
                            bitrate = int(part)
                            if bitrate <= 320 and bitrate > (enrichment.best_bitrate or 0):
                                enrichment.best_bitrate = bitrate
                            break

                enhanced_codec = codec.get("enhanced_codec", "")
                if "_" in enhanced_codec and not enrichment.best_bitrate:
                    parts = enhanced_codec.split("_")
                    if len(parts) >= 2 and parts[1].isdigit():
                        bitrate = int(parts[1])
                        if bitrate <= 320 and bitrate > (enrichment.best_bitrate or 0):
                            enrichment.best_bitrate = bitrate

        # Discover actual quality via license requests
        if discover_quality:
            self._quality_discoveries += 1
            try:
                quality_info = await self._client.discover_content_quality(asin, use_cache=use_cache)
                enrichment.actual_quality = quality_info
                enrichment.has_atmos = quality_info.has_atmos or enrichment.has_atmos
                if quality_info.best_bitrate_kbps > 0:
                    enrichment.best_bitrate = int(quality_info.best_bitrate_kbps)
            except (AsyncAudibleError, ValidationError) as e:
                logger.debug("Failed to discover quality for ASIN %s: %s", asin, str(e))

        # API reliability flag
        if enrichment.has_atmos or (enrichment.actual_quality and enrichment.actual_quality.has_atmos):
            enrichment.api_quality_reliable = False

        # Cache result with month-boundary-aware TTL
        if self._cache:
            from ..cache.sqlite_cache import calculate_pricing_ttl_seconds

            ttl = calculate_pricing_ttl_seconds(self.CACHE_TTL_SECONDS)
            self._cache.set(
                self.CACHE_NAMESPACE,
                cache_key,
                enrichment.model_dump(),
                ttl_seconds=ttl,
            )

        return enrichment

    async def enrich_batch_with_quality(
        self,
        asins: list[str],
        use_cache: bool = True,
        discover_quality: bool = True,
        max_concurrent: int = 5,
    ) -> dict[str, AudibleEnrichment]:
        """
        Enrich multiple ASINs with Audible data including actual quality.

        This method fetches catalog data and makes license requests concurrently
        for efficient batch processing. Progress is reported as each item completes.

        Args:
            asins: List of ASINs to enrich
            use_cache: Use cached data if available
            discover_quality: Make license requests to discover actual quality
            max_concurrent: Max concurrent enrichment operations

        Returns:
            Dict mapping ASIN to enrichment data
        """
        # Preload library
        await self._load_library_asins()

        results: dict[str, AudibleEnrichment] = {}
        total = len(asins)
        completed = 0
        semaphore = asyncio.Semaphore(max_concurrent)

        async def enrich_one(asin: str) -> tuple[str, AudibleEnrichment | None]:
            nonlocal completed
            async with semaphore:
                result = await self.enrich_single_with_quality(
                    asin, use_cache=use_cache, discover_quality=discover_quality
                )
                # Update progress after completion (not at start)
                completed += 1
                if self._progress:
                    self._progress(completed, total, f"Enriched {asin}")
                return asin, result

        # Create all tasks
        tasks = [enrich_one(asin) for asin in asins]

        # Run concurrently with as_completed for live progress updates
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                if isinstance(result, tuple):
                    asin, enrichment = result
                    if enrichment:
                        results[asin] = enrichment
            except Exception as e:
                logger.warning("Enrichment failed: %s", e)

        return results
