"""
Audible enrichment service.

Provides rich metadata enrichment for audiobooks by combining:
- Catalog data (pricing, availability, quality)
- Library data (ownership status)
- Plus Catalog info (free listening availability)

This module is used by multiple features:
- Quality analysis (upgrade candidates)
- Series matching (missing books pricing)
- Any feature needing rich Audible metadata
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional, cast

from pydantic import BaseModel, Field

from .client import AudibleClient
from .models import PlusCatalogInfo, PricingInfo

if TYPE_CHECKING:
    from ..cache import SQLiteCache


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

    # Quality available
    has_atmos: bool = Field(default=False, description="Dolby Atmos version available")
    best_bitrate: int | None = Field(default=None, description="Best available bitrate (kbps)")
    available_codecs: list[str] = Field(default_factory=list, description="Available codecs")

    # API reliability
    api_quality_reliable: bool = Field(default=True, description="Whether API quality info is reliable")

    # URLs and images
    audible_url: str | None = Field(default=None, description="URL to Audible product page")
    cover_image_url: str | None = Field(default=None, description="URL to 500x500 cover image")

    model_config = {"extra": "ignore"}

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
    """

    CACHE_NAMESPACE = "audible_enrichment"
    CACHE_TTL_SECONDS = 3600 * 6  # 6 hours (prices change)

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
            product = response.get("product", response)
        except Exception:
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
        for codec in available_codecs:
            codec_name = codec.get("enhanced_codec", "")
            # Parse bitrate from codec name like "LC_128_44100_stereo"
            if "_" in codec_name:
                parts = codec_name.split("_")
                for part in parts:
                    if part.isdigit():
                        bitrate = int(part)
                        if bitrate > (enrichment.best_bitrate or 0):
                            enrichment.best_bitrate = bitrate
                        break

        # API reliability - unreliable for Atmos/USAC
        if enrichment.has_atmos:
            enrichment.api_quality_reliable = False

        # Cache result (ownership excluded since it's checked separately)
        if self._cache:
            self._cache.set(
                self.CACHE_NAMESPACE, cache_key, enrichment.model_dump(), ttl_seconds=self.CACHE_TTL_SECONDS
            )

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
