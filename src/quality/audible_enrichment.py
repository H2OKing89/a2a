"""
Audible enrichment for quality upgrade candidates.

Enriches audiobook quality data with Audible catalog information:
- Ownership status
- Pricing (list, sale, member)
- Plus Catalog availability and expiration
- Atmos/USAC availability
- Cover images and Audible URLs
"""

import hashlib
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field

from ..audible import AudibleClient

if TYPE_CHECKING:
    from ..cache import SQLiteCache


class PricingInfo(BaseModel):
    """Pricing information from Audible."""

    list_price: float | None = Field(default=None, description="Regular list price in USD")
    sale_price: float | None = Field(default=None, description="Current sale/member price")
    credit_price: float = Field(default=1.0, description="Price in credits")
    currency: str = Field(default="USD", description="Currency code")
    price_type: str | None = Field(default=None, description="Price type: sale, member, list")
    is_monthly_deal: bool = Field(default=False, description="Is a monthly deal (type=sale)")

    @property
    def discount_percent(self) -> float | None:
        """Calculate discount percentage."""
        if self.list_price and self.sale_price and self.list_price > 0:
            return round((1 - self.sale_price / self.list_price) * 100, 1)
        return None

    @property
    def is_good_deal(self) -> bool:
        """Check if price is under $9.00 threshold."""
        if self.sale_price is not None:
            return self.sale_price < 9.00
        if self.list_price is not None:
            return self.list_price < 9.00
        return False

    @property
    def effective_price(self) -> float | None:
        """Get the effective (best) price."""
        return self.sale_price or self.list_price


class PlusCatalogInfo(BaseModel):
    """Audible Plus Catalog information."""

    is_plus_catalog: bool = Field(default=False, description="In Plus Catalog (free)")
    plan_name: str | None = Field(default=None, description="Plan name (US Minerva = Plus)")
    expiration_date: datetime | None = Field(default=None, description="When removed from Plus")

    @property
    def is_expiring_soon(self) -> bool:
        """Check if expiring within 30 days."""
        if not self.expiration_date:
            return False
        now = datetime.now(timezone.utc)
        days_until = (self.expiration_date - now).days
        return 0 < days_until <= 30

    @property
    def days_until_expiration(self) -> int | None:
        """Days until expiration, None if not expiring."""
        if not self.expiration_date:
            return None
        now = datetime.now(timezone.utc)
        return max(0, (self.expiration_date - now).days)

    @property
    def expiration_display(self) -> str | None:
        """Human-readable expiration date."""
        if not self.expiration_date:
            return None
        return self.expiration_date.strftime("%Y-%m-%d")


class AudibleEnrichment(BaseModel):
    """Full Audible enrichment data for an audiobook."""

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
                discount = self.pricing.discount_percent
                if discount and discount >= 50:
                    return f"MONTHLY_DEAL (${self.pricing.effective_price:.2f}, {discount:.0f}% off)"

            if self.pricing.is_good_deal:
                discount = self.pricing.discount_percent
                if discount and discount > 0:
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
            discount = self.pricing.discount_percent
            if discount and discount >= 50:
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
    Service for enriching upgrade candidates with Audible data.

    Uses caching to avoid repeated API calls.
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
    def stats(self) -> dict:
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

    def _parse_plans(self, plans: list[dict]) -> PlusCatalogInfo:
        """
        Parse plans array for Plus Catalog info.

        Plus Catalog is indicated by plan_name containing 'Minerva'.
        """
        info = PlusCatalogInfo()

        if not plans:
            return info

        for plan in plans:
            plan_name = plan.get("plan_name", "")
            end_date_str = plan.get("end_date", "")

            # US Minerva = Plus Catalog
            if "Minerva" in plan_name or "AYCE" in plan_name.upper():
                info.is_plus_catalog = True
                info.plan_name = plan_name

                # Parse expiration date
                if end_date_str:
                    try:
                        # Handle ISO format with microseconds
                        end_date_str = end_date_str.replace("Z", "+00:00")
                        if ".000" in end_date_str:
                            # Remove extra decimal places
                            end_date_str = end_date_str.split(".")[0] + "+00:00"
                        end_date = datetime.fromisoformat(end_date_str)

                        # Check if it's a "forever" date (9999, 2099)
                        if end_date.year < 2099:
                            info.expiration_date = end_date
                    except (ValueError, TypeError):
                        pass

                break  # Found Plus Catalog, done

        return info

    def _parse_pricing(self, price_data: dict | None) -> PricingInfo | None:
        """Parse pricing data from API response."""
        if not price_data:
            return None

        pricing = PricingInfo()

        # Credit price
        pricing.credit_price = price_data.get("credit_price", 1.0)

        # List price
        list_price_data = price_data.get("list_price", {})
        if list_price_data:
            pricing.list_price = list_price_data.get("base")
            pricing.currency = list_price_data.get("currency_code", "USD")

        # Sale/member price (lowest_price)
        lowest_price_data = price_data.get("lowest_price", {})
        if lowest_price_data:
            pricing.sale_price = lowest_price_data.get("base")
            pricing.price_type = lowest_price_data.get("type")
            # Monthly deals have type "sale" (not "member")
            pricing.is_monthly_deal = pricing.price_type == "sale"

        return pricing

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
            response = self._client._request(
                "GET",
                f"1.0/catalog/products/{asin}",
                response_groups="contributors,media,product_attrs,product_desc,product_details,product_extended_attrs,series,category_ladders,customer_rights,price",
            )
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
        product_images = product.get("product_images", {})
        if product_images:
            # Prefer 500px, fall back to largest available
            enrichment.cover_image_url = (
                product_images.get("500")
                or product_images.get("1024")
                or product_images.get("252")
                or next(iter(product_images.values()), None)
            )

        # Pricing
        enrichment.pricing = self._parse_pricing(product.get("price"))

        # Plus Catalog from plans
        enrichment.plus_catalog = self._parse_plans(product.get("plans", []))

        # Available codecs
        available_codecs = product.get("available_codecs", [])
        enrichment.available_codecs = [c.get("name", "") for c in available_codecs]

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
