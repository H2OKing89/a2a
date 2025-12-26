"""
Pydantic models for Audible API responses.

Based on the Audible API response structures with response_groups:
- contributors, media, product_attrs, product_desc, product_details
- rating, sample, series, categories, etc.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


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
