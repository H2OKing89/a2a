"""
Pydantic models for Audible API responses.

Based on the Audible API response structures with response_groups:
- contributors, media, product_attrs, product_desc, product_details
- rating, sample, series, categories, etc.
"""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


class AudibleAuthor(BaseModel):
    """Author/contributor information."""
    
    asin: Optional[str] = None
    name: str
    
    model_config = {"extra": "ignore"}


class AudibleNarrator(BaseModel):
    """Narrator information."""
    
    name: str
    
    model_config = {"extra": "ignore"}


class AudibleSeries(BaseModel):
    """Series information."""
    
    asin: Optional[str] = None
    title: str
    sequence: Optional[str] = None
    url: Optional[str] = None
    
    model_config = {"extra": "ignore"}


class AudibleRating(BaseModel):
    """Rating information."""
    
    overall_distribution: Optional[dict[str, int]] = Field(default=None, alias="overall_distribution")
    performance_distribution: Optional[dict[str, int]] = Field(default=None, alias="performance_distribution")
    story_distribution: Optional[dict[str, int]] = Field(default=None, alias="story_distribution")
    num_reviews: Optional[int] = Field(default=None, alias="num_reviews")
    
    model_config = {"extra": "ignore", "populate_by_name": True}


class AudibleCategory(BaseModel):
    """Category/genre information."""
    
    id: Optional[str] = Field(default=None, alias="category_id")
    name: Optional[str] = Field(default=None, alias="name")
    root: Optional[str] = None
    
    model_config = {"extra": "ignore", "populate_by_name": True}


class AudibleCategoryLadder(BaseModel):
    """Category hierarchy (ladder)."""
    
    ladder: list[AudibleCategory] = Field(default_factory=list)
    root: Optional[str] = None
    
    model_config = {"extra": "ignore"}


class AudiblePlan(BaseModel):
    """Plan/subscription info."""
    
    plan_name: Optional[str] = None
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
    subtitle: Optional[str] = None
    
    # Authors and narrators
    authors: list[AudibleAuthor] = Field(default_factory=list)
    narrators: list[AudibleNarrator] = Field(default_factory=list)
    
    # Publisher info
    publisher_name: Optional[str] = None
    publisher_summary: Optional[str] = None
    
    # Release info
    release_date: Optional[str] = None
    issue_date: Optional[str] = None
    
    # Runtime
    runtime_length_min: Optional[int] = None
    format_type: Optional[str] = None
    
    # Language
    language: Optional[str] = None
    
    # Series
    series: list[AudibleSeries] = Field(default_factory=list)
    
    # Categories
    category_ladders: list[AudibleCategoryLadder] = Field(default_factory=list)
    
    # Ratings
    rating: Optional[AudibleRating] = None
    
    # Images
    product_images: Optional[dict[str, str]] = None
    
    # Pricing
    price: Optional[dict[str, Any]] = None
    
    # Sample URL
    sample_url: Optional[str] = None
    
    # Extended attributes
    is_ayce: bool = Field(default=False, alias="is_ayce")  # All You Can Eat (included in subscription)
    is_adult_product: bool = Field(default=False, alias="is_adult_product")
    
    # Audible Plus catalog
    is_listenable: bool = Field(default=False, alias="is_listenable")
    
    # Content info
    content_type: Optional[str] = None
    content_delivery_type: Optional[str] = None
    
    # Merchandising summary (short description)
    merchandising_summary: Optional[str] = None
    
    model_config = {"extra": "ignore", "populate_by_name": True}
    
    @property
    def runtime_hours(self) -> Optional[float]:
        """Get runtime in hours."""
        if self.runtime_length_min:
            return round(self.runtime_length_min / 60, 2)
        return None
    
    @property
    def primary_author(self) -> Optional[str]:
        """Get primary author name."""
        if self.authors:
            return self.authors[0].name
        return None
    
    @property
    def primary_narrator(self) -> Optional[str]:
        """Get primary narrator name."""
        if self.narrators:
            return self.narrators[0].name
        return None
    
    @property
    def primary_series(self) -> Optional[AudibleSeries]:
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
    purchase_date: Optional[str] = None
    origin_type: Optional[str] = None
    
    # Status flags
    is_downloaded: bool = Field(default=False, alias="is_downloaded")
    is_finished: bool = Field(default=False, alias="is_finished")
    is_playable: bool = Field(default=True, alias="is_playable")
    is_archived: bool = Field(default=False, alias="is_archived")
    is_visible: bool = Field(default=True, alias="is_visible")
    is_removable: bool = Field(default=False, alias="is_removable")
    is_returnable: bool = Field(default=False, alias="is_returnable")
    
    # Listening progress
    percent_complete: Optional[float] = Field(default=None, alias="percent_complete")
    
    # PDF availability
    pdf_url: Optional[str] = None
    
    model_config = {"extra": "ignore", "populate_by_name": True}


class AudibleCatalogProduct(AudibleBook):
    """
    Catalog product with additional catalog-specific fields.
    
    Used for search results and product lookups.
    """
    
    # Availability
    sku: Optional[str] = None
    sku_lite: Optional[str] = None
    
    # Reviews
    reviews: Optional[list[dict]] = None
    
    # Customer rights (if authenticated)
    customer_rights: Optional[dict] = None
    
    # Relationships (similar products, etc.)
    relationships: Optional[list[dict]] = None
    
    model_config = {"extra": "ignore", "populate_by_name": True}


class AudibleLibraryResponse(BaseModel):
    """Response from GET /1.0/library."""
    
    items: list[AudibleLibraryItem] = Field(default_factory=list)
    response_groups: Optional[list[str]] = None
    total_results: Optional[int] = Field(default=None, alias="total_results")
    
    model_config = {"extra": "ignore", "populate_by_name": True}


class AudibleCatalogResponse(BaseModel):
    """Response from GET /1.0/catalog/products."""
    
    products: list[AudibleCatalogProduct] = Field(default_factory=list)
    total_results: Optional[int] = Field(default=None, alias="total_results")
    
    model_config = {"extra": "ignore", "populate_by_name": True}


class AudibleListeningStats(BaseModel):
    """User listening statistics from /1.0/stats/aggregates."""
    
    # Total stats
    total_listening_time_ms: Optional[int] = Field(default=None, alias="totalListeningTimeMs")
    total_finished_titles: Optional[int] = Field(default=None, alias="totalFinishedTitles")
    
    # Daily/monthly breakdowns if requested
    daily_listening_stats: Optional[list[dict]] = None
    monthly_listening_stats: Optional[list[dict]] = None
    
    model_config = {"extra": "ignore", "populate_by_name": True}
    
    @property
    def total_hours(self) -> Optional[float]:
        """Total listening time in hours."""
        if self.total_listening_time_ms:
            return round(self.total_listening_time_ms / (1000 * 60 * 60), 2)
        return None


class AudibleAccountInfo(BaseModel):
    """Account information from /1.0/account/information."""
    
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    marketplace: Optional[str] = None
    
    # Subscription details
    subscription_details: Optional[dict] = None
    plan_summary: Optional[dict] = None
    
    model_config = {"extra": "ignore", "populate_by_name": True}
