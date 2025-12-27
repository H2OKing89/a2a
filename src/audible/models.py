"""
Pydantic models for Audible API responses.

Based on the Audible API response structures with response_groups:
- contributors, media, product_attrs, product_desc, product_details
- rating, sample, series, categories, etc.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

# =============================================================================
# API Enums - Centralized API constants for type safety and discoverability
# =============================================================================


class SimilarityType(str, Enum):
    """
    Similarity types for /catalog/products/{asin}/sims endpoint.

    Used to discover related books based on different criteria.
    """

    IN_SAME_SERIES = "InTheSameSeries"  # Other books in the same series
    BY_SAME_AUTHOR = "ByTheSameAuthor"  # Other books by the same author
    BY_SAME_NARRATOR = "ByTheSameNarrator"  # Other books by the same narrator
    NEXT_IN_SERIES = "NextInSameSeries"  # Next book in the series only
    RAW_SIMILARITIES = "RawSimilarities"  # General recommendations


class LibrarySortBy(str, Enum):
    """
    Sort options for /library endpoint.

    Prefix with - for descending order.
    """

    AUTHOR = "Author"
    AUTHOR_DESC = "-Author"
    LENGTH = "Length"
    LENGTH_DESC = "-Length"
    NARRATOR = "Narrator"
    NARRATOR_DESC = "-Narrator"
    PURCHASE_DATE = "PurchaseDate"
    PURCHASE_DATE_DESC = "-PurchaseDate"
    TITLE = "Title"
    TITLE_DESC = "-Title"


class CatalogSortBy(str, Enum):
    """
    Sort options for /catalog/products endpoint.

    Prefix with - for descending order.
    """

    RELEASE_DATE = "ReleaseDate"
    RELEASE_DATE_DESC = "-ReleaseDate"
    TITLE = "Title"
    TITLE_DESC = "-Title"
    AVG_RATING = "AvgRating"
    BEST_SELLERS = "BestSellers"
    RUNTIME_LENGTH = "RuntimeLength"
    RUNTIME_LENGTH_DESC = "-RuntimeLength"
    RELEVANCE = "Relevance"


class WishlistSortBy(str, Enum):
    """Sort options for /wishlist endpoint."""

    AUTHOR = "Author"
    AUTHOR_DESC = "-Author"
    DATE_ADDED = "DateAdded"
    DATE_ADDED_DESC = "-DateAdded"
    PRICE = "Price"
    PRICE_DESC = "-Price"
    RATING = "Rating"
    RATING_DESC = "-Rating"
    TITLE = "Title"
    TITLE_DESC = "-Title"


class ReviewSortBy(str, Enum):
    """Sort options for reviews."""

    MOST_HELPFUL = "MostHelpful"
    MOST_RECENT = "MostRecent"


class LibraryStatus(str, Enum):
    """Status filter for library items."""

    ACTIVE = "Active"  # Default - owned books
    REVOKED = "Revoked"  # Returned/refunded books


class ContentQuality(str, Enum):
    """Audio quality for content/download requests."""

    HIGH = "High"
    NORMAL = "Normal"


class AudioCodec(str, Enum):
    """
    Audio codecs supported by Audible.

    Used in content license requests to specify desired format.
    """

    AAC_LC = "mp4a.40.2"  # AAC-LC (standard)
    HE_AAC = "mp4a.40.42"  # HE-AAC (high efficiency)
    EC3 = "ec+3"  # Enhanced AC-3 (Dolby Digital Plus)
    AC4 = "ac-4"  # AC-4 (Dolby Atmos)


class DrmType(str, Enum):
    """DRM types for content delivery."""

    ADRM = "Adrm"  # Audible DRM (standard AAX)
    MPEG = "Mpeg"
    PLAY_READY = "PlayReady"
    HLS = "Hls"
    DASH = "Dash"
    FAIR_PLAY = "FairPlay"
    WIDEVINE = "Widevine"
    HLS_CMAF = "HlsCmaf"


class PlusPlan(str, Enum):
    """
    Audible subscription plans for Plus Catalog filtering.

    US Minerva = Audible Plus (US)
    AllYouCanEat = General Plus access
    Rodizio = Audible Escape (romance-focused)
    """

    US_MINERVA = "US Minerva"  # Audible Plus (US)
    ALL_YOU_CAN_EAT = "AllYouCanEat"  # General Plus
    RODIZIO = "Rodizio"  # Audible Escape
    RODIZIO_FREE_BASIC = "RodizioFreeBasic"
    AYCE_ROMANCE = "AyceRomance"
    AMAZON_ENGLISH = "AmazonEnglish"
    ENTERPRISE = "Enterprise"


# =============================================================================
# Response Group Constants - Centralized for consistency
# =============================================================================


class ResponseGroups:
    """
    Standard response groups for different API operations.

    These control what data is returned from the Audible API.
    Use comma-separated strings when making requests.
    """

    # Library response groups
    LIBRARY_BASIC = "contributors,media,product_attrs,product_details,rating,series"

    LIBRARY_FULL = (
        "contributors,media,price,product_attrs,product_desc,product_details,"
        "product_extended_attrs,rating,series,category_ladders,is_downloaded,"
        "is_finished,percent_complete,pdf_url"
    )

    LIBRARY_WITH_PLANS = (
        "contributors,media,price,product_attrs,product_details,product_extended_attrs,"
        "product_plan_details,product_plans,rating,series,category_ladders"
    )

    # Catalog response groups
    CATALOG_BASIC = "contributors,media,product_attrs,product_details,rating,series"

    CATALOG_FULL = (
        "contributors,media,product_attrs,product_desc,product_details,"
        "product_extended_attrs,rating,series,category_ladders,reviews,customer_rights"
    )

    CATALOG_WITH_PRICE = (
        "contributors,media,price,product_attrs,product_desc,product_details,"
        "product_extended_attrs,product_plan_details,product_plans,rating,series,category_ladders"
    )

    # Wishlist response groups
    WISHLIST_FULL = (
        "contributors,media,price,product_attrs,product_desc,product_extended_attrs,"
        "product_plan_details,product_plans,rating,sample,sku,customer_rights,relationships"
    )

    # Recommendations response groups
    RECOMMENDATIONS = (
        "contributors,media,price,product_attrs,product_desc,product_extended_attrs,"
        "product_plan_details,product_plans,rating,sample,sku"
    )

    # Account/stats response groups
    ACCOUNT_FULL = (
        "delinquency_status,customer_benefits,customer_segments,"
        "subscription_details_payment_instrument,plan_summary,subscription_details"
    )

    LISTENING_STATS = "total_listening_stats"


# =============================================================================
# Pricing and Plus Catalog Models (shared across features)
# =============================================================================


class PricingInfo(BaseModel):
    """
    Pricing information from Audible.

    Parses the price dict from API responses into a structured model.
    Used by quality analysis, series matching, and other features.
    """

    list_price: float | None = Field(default=None, description="Regular list price in USD")
    sale_price: float | None = Field(default=None, description="Current sale/member price")
    credit_price: float = Field(default=1.0, description="Price in credits")
    currency: str = Field(default="USD", description="Currency code")
    price_type: str | None = Field(default=None, description="Price type: sale, member, list")
    is_monthly_deal: bool = Field(default=False, description="Is a monthly deal (type=sale)")

    model_config = {"extra": "ignore"}

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

    @classmethod
    def from_api_response(cls, price_data: dict[str, Any] | None) -> "PricingInfo | None":
        """
        Parse pricing data from Audible API response.

        Args:
            price_data: The 'price' dict from API response

        Returns:
            PricingInfo or None if no price data
        """
        if not price_data:
            return None

        pricing = cls()

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


class PlusCatalogInfo(BaseModel):
    """
    Audible Plus Catalog information.

    Plus Catalog books are free to listen with an Audible membership.
    """

    is_plus_catalog: bool = Field(default=False, description="In Plus Catalog (free)")
    plan_name: str | None = Field(default=None, description="Plan name (US Minerva = Plus)")
    expiration_date: datetime | None = Field(default=None, description="When removed from Plus")

    model_config = {"extra": "ignore"}

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

    @classmethod
    def from_api_response(cls, plans: list[dict[str, Any]] | None) -> "PlusCatalogInfo":
        """
        Parse plans array for Plus Catalog info.

        Plus Catalog is indicated by plan_name containing 'Minerva'.

        Args:
            plans: The 'plans' array from API response

        Returns:
            PlusCatalogInfo (always returns, with defaults if no Plus)
        """
        info = cls()

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


# =============================================================================
# Core Audible Models
# =============================================================================


class AudibleAuthor(BaseModel):
    """Author/contributor information."""

    asin: str | None = None
    name: str

    model_config = {"extra": "ignore"}


class AudibleNarrator(BaseModel):
    """Narrator information."""

    name: str

    model_config = {"extra": "ignore"}


class AudibleSeries(BaseModel):
    """Series information."""

    asin: str | None = None
    title: str
    sequence: str | None = None
    url: str | None = None

    model_config = {"extra": "ignore"}


class AudibleRating(BaseModel):
    """Rating information."""

    # Distribution dicts can contain int, float, or string values
    overall_distribution: dict[str, Any] | None = Field(default=None, alias="overall_distribution")
    performance_distribution: dict[str, Any] | None = Field(default=None, alias="performance_distribution")
    story_distribution: dict[str, Any] | None = Field(default=None, alias="story_distribution")
    num_reviews: int | None = Field(default=None, alias="num_reviews")

    model_config = {"extra": "ignore", "populate_by_name": True}


class AudibleCategory(BaseModel):
    """Category/genre information."""

    id: str | None = Field(default=None, alias="category_id")
    name: str | None = Field(default=None, alias="name")
    root: str | None = None

    model_config = {"extra": "ignore", "populate_by_name": True}


class AudibleCategoryLadder(BaseModel):
    """Category hierarchy (ladder)."""

    ladder: list[AudibleCategory] = Field(default_factory=list)
    root: str | None = None

    model_config = {"extra": "ignore"}


class AudiblePlan(BaseModel):
    """Plan/subscription info."""

    plan_name: str | None = None
    is_in_plan: bool = Field(default=False, alias="is_in_plan")

    model_config = {"extra": "ignore", "populate_by_name": True}


class AudibleBook(BaseModel):
    """
    Core audiobook metadata from Audible.

    This model is used for both library items and catalog products.
    """

    # Core identifiers
    asin: str
    title: str
    subtitle: str | None = None

    # Authors and narrators
    authors: list[AudibleAuthor] = Field(default_factory=list)
    narrators: list[AudibleNarrator] = Field(default_factory=list)

    # Publisher info
    publisher_name: str | None = None
    publisher_summary: str | None = None

    # Release info
    release_date: str | None = None
    issue_date: str | None = None

    # Runtime
    runtime_length_min: int | None = None
    format_type: str | None = None

    # Language
    language: str | None = None

    # Series (can be None from API, defaults to empty list)
    series: list[AudibleSeries] | None = Field(default_factory=list)

    # Categories (can be None from API, defaults to empty list)
    category_ladders: list[AudibleCategoryLadder] | None = Field(default_factory=list)

    # Ratings
    rating: AudibleRating | None = None

    # Images
    product_images: dict[str, str] | None = None

    # Pricing
    price: dict[str, Any] | None = None

    # Sample URL
    sample_url: str | None = None

    # Extended attributes
    is_ayce: bool = Field(default=False, alias="is_ayce")  # All You Can Eat (included in subscription)
    is_adult_product: bool = Field(default=False, alias="is_adult_product")

    # Audible Plus catalog
    is_listenable: bool = Field(default=False, alias="is_listenable")

    # Content info
    content_type: str | None = None
    content_delivery_type: str | None = None

    # Merchandising summary (short description)
    merchandising_summary: str | None = None

    model_config = {"extra": "ignore", "populate_by_name": True}

    @property
    def runtime_hours(self) -> float | None:
        """Get runtime in hours."""
        if self.runtime_length_min:
            return round(self.runtime_length_min / 60, 2)
        return None

    @property
    def primary_author(self) -> str | None:
        """Get primary author name."""
        if self.authors:
            return self.authors[0].name
        return None

    @property
    def primary_narrator(self) -> str | None:
        """Get primary narrator name."""
        if self.narrators:
            return self.narrators[0].name
        return None

    @property
    def primary_series(self) -> AudibleSeries | None:
        """Get primary series."""
        if self.series:
            return self.series[0]
        return None


class AudibleLibraryItem(AudibleBook):
    """
    Library-specific audiobook item with ownership/status info.

    Extends AudibleBook with library-specific fields.
    """

    # Library-specific fields
    purchase_date: str | None = None
    origin_type: str | None = None

    # Status flags (can be None from API)
    is_downloaded: bool | None = Field(default=False, alias="is_downloaded")
    is_finished: bool | None = Field(default=False, alias="is_finished")
    is_playable: bool | None = Field(default=True, alias="is_playable")
    is_archived: bool | None = Field(default=False, alias="is_archived")
    is_visible: bool | None = Field(default=True, alias="is_visible")
    is_removable: bool | None = Field(default=False, alias="is_removable")
    is_returnable: bool | None = Field(default=False, alias="is_returnable")

    # Listening progress
    percent_complete: float | None = Field(default=None, alias="percent_complete")

    # PDF availability
    pdf_url: str | None = None

    model_config = {"extra": "ignore", "populate_by_name": True}


class AudibleCatalogProduct(AudibleBook):
    """
    Catalog product with additional catalog-specific fields.

    Used for search results and product lookups.
    """

    # Availability
    sku: str | None = None
    sku_lite: str | None = None

    # Reviews
    reviews: list[dict] | None = None

    # Customer rights (if authenticated)
    customer_rights: dict | None = None

    # Relationships (similar products, etc.)
    relationships: list[dict] | None = None

    model_config = {"extra": "ignore", "populate_by_name": True}


class AudibleLibraryResponse(BaseModel):
    """Response from GET /1.0/library."""

    items: list[AudibleLibraryItem] = Field(default_factory=list)
    response_groups: list[str] | None = None
    total_results: int | None = Field(default=None, alias="total_results")

    model_config = {"extra": "ignore", "populate_by_name": True}


class AudibleCatalogResponse(BaseModel):
    """Response from GET /1.0/catalog/products."""

    products: list[AudibleCatalogProduct] = Field(default_factory=list)
    total_results: int | None = Field(default=None, alias="total_results")

    model_config = {"extra": "ignore", "populate_by_name": True}


class AudibleListeningStats(BaseModel):
    """User listening statistics from /1.0/stats/aggregates."""

    # Total stats
    total_listening_time_ms: int | None = Field(default=None, alias="totalListeningTimeMs")
    total_finished_titles: int | None = Field(default=None, alias="totalFinishedTitles")

    # Daily/monthly breakdowns if requested
    daily_listening_stats: list[dict] | None = None
    monthly_listening_stats: list[dict] | None = None

    model_config = {"extra": "ignore", "populate_by_name": True}

    @property
    def total_hours(self) -> float | None:
        """Total listening time in hours."""
        if self.total_listening_time_ms:
            return round(self.total_listening_time_ms / (1000 * 60 * 60), 2)
        return None


class AudibleAccountInfo(BaseModel):
    """Account information from /1.0/account/information."""

    customer_id: str | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    marketplace: str | None = None

    # Subscription details
    subscription_details: dict | None = None
    plan_summary: dict | None = None

    model_config = {"extra": "ignore", "populate_by_name": True}


# =============================================================================
# Wishlist Models
# =============================================================================


class WishlistItem(AudibleBook):
    """
    Wishlist item with additional wishlist-specific fields.

    Extends AudibleBook with date added and availability info.
    """

    # When added to wishlist
    date_added: str | None = Field(default=None, alias="date_added")

    # Availability info
    available_date: str | None = None
    is_preorderable: bool = Field(default=False, alias="is_preorderable")

    # Plans (for Plus Catalog detection)
    plans: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "ignore", "populate_by_name": True}

    @property
    def is_plus_catalog(self) -> bool:
        """Check if item is in Plus Catalog."""
        if self.is_ayce:
            return True
        for plan in self.plans:
            plan_name = plan.get("plan_name", "")
            if "Minerva" in plan_name or "AYCE" in plan_name.upper():
                return True
        return False


class WishlistResponse(BaseModel):
    """Response from GET /1.0/wishlist."""

    products: list[WishlistItem] = Field(default_factory=list)
    total_results: int | None = Field(default=None, alias="total_results")

    model_config = {"extra": "ignore", "populate_by_name": True}


# =============================================================================
# Content/Download Models
# =============================================================================


class ContentMetadata(BaseModel):
    """
    Content metadata from /content/{asin}/metadata endpoint.

    Contains chapter info, available codecs, and quality info.
    """

    asin: str | None = None
    acr: str | None = None  # Audio Content Reference

    # Chapter info
    chapter_info: dict[str, Any] | None = None

    # Content reference (URLs, etc.)
    content_reference: dict[str, Any] | None = None

    # Available formats
    available_codecs: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore", "populate_by_name": True}

    @property
    def supports_atmos(self) -> bool:
        """Check if Dolby Atmos (AC-4) is available."""
        return "ac-4" in self.available_codecs or "ec+3" in self.available_codecs

    @property
    def supports_high_quality(self) -> bool:
        """Check if high quality AAC is available."""
        return "mp4a.40.2" in self.available_codecs or "mp4a.40.42" in self.available_codecs


class ChapterInfo(BaseModel):
    """Chapter information for an audiobook."""

    brandIntroDurationMs: int | None = Field(default=None, alias="brandIntroDurationMs")
    brandOutroDurationMs: int | None = Field(default=None, alias="brandOutroDurationMs")
    is_accurate: bool | None = Field(default=None, alias="is_accurate")
    runtime_length_ms: int | None = Field(default=None, alias="runtime_length_ms")
    runtime_length_sec: int | None = Field(default=None, alias="runtime_length_sec")
    chapters: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "ignore", "populate_by_name": True}

    @property
    def chapter_count(self) -> int:
        """Number of chapters."""
        return len(self.chapters)

    @property
    def runtime_hours(self) -> float | None:
        """Runtime in hours."""
        if self.runtime_length_sec:
            return round(self.runtime_length_sec / 3600, 2)
        if self.runtime_length_ms:
            return round(self.runtime_length_ms / (1000 * 3600), 2)
        return None
