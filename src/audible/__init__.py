"""
Audible API client module.

Provides a comprehensive client for the Audible API with:
- Library management (get owned books, status, progress)
- Catalog search and product lookup
- Wishlist management (add, remove, list)
- Series discovery via similarity search
- Recommendations
- Content metadata (chapters, audio quality, Dolby Atmos support)
- Pricing and Plus Catalog parsing
- Enrichment service for metadata aggregation
- Async client for concurrent operations
- Logging configuration
- Marketplace/locale utilities
- Activation bytes for DRM tools
"""

from .async_client import AsyncAudibleAuthError, AsyncAudibleClient, AsyncAudibleError, AsyncAudibleNotFoundError
from .client import AudibleAuthError, AudibleClient, AudibleError, AudibleNotFoundError
from .enrichment import AudibleEnrichment, AudibleEnrichmentService
from .logging import (
    LogContext,
    configure_logging,
    enable_debug_logging,
    enable_request_logging,
    get_logger,
    set_level,
    silence_audible_package,
)
from .models import (  # Core models; Wishlist models; Content/quality models; Pricing and Plus Catalog; API Enums
    AudibleAccountInfo,
    AudibleAuthor,
    AudibleBook,
    AudibleCatalogProduct,
    AudibleCatalogResponse,
    AudibleLibraryItem,
    AudibleLibraryResponse,
    AudibleListeningStats,
    AudibleNarrator,
    AudibleSeries,
    AudioCodec,
    CatalogSortBy,
    ChapterInfo,
    ContentMetadata,
    ContentQuality,
    DrmType,
    LibrarySortBy,
    LibraryStatus,
    PlusCatalogInfo,
    PlusPlan,
    PricingInfo,
    ResponseGroups,
    ReviewSortBy,
    SimilarityType,
    WishlistItem,
    WishlistResponse,
    WishlistSortBy,
)
from .utils import (
    MARKETPLACES,
    DeviceInfo,
    MarketplaceInfo,
    deregister_device,
    get_activation_bytes,
    get_activation_bytes_from_file,
    get_auth_info,
    get_device_info,
    get_marketplace,
    get_marketplace_for_domain,
    is_auth_valid,
    list_marketplaces,
    refresh_auth,
)

__all__ = [
    # Sync Client and exceptions
    "AudibleClient",
    "AudibleError",
    "AudibleAuthError",
    "AudibleNotFoundError",
    # Async Client and exceptions
    "AsyncAudibleClient",
    "AsyncAudibleError",
    "AsyncAudibleAuthError",
    "AsyncAudibleNotFoundError",
    # Core models
    "AudibleBook",
    "AudibleAuthor",
    "AudibleNarrator",
    "AudibleSeries",
    "AudibleLibraryItem",
    "AudibleLibraryResponse",
    "AudibleCatalogProduct",
    "AudibleCatalogResponse",
    "AudibleListeningStats",
    "AudibleAccountInfo",
    # Wishlist models
    "WishlistItem",
    "WishlistResponse",
    # Content/quality models
    "ChapterInfo",
    "ContentMetadata",
    # Pricing and Plus Catalog
    "PricingInfo",
    "PlusCatalogInfo",
    # Enrichment service
    "AudibleEnrichment",
    "AudibleEnrichmentService",
    # API Enums - for type-safe API usage
    "SimilarityType",
    "LibrarySortBy",
    "CatalogSortBy",
    "WishlistSortBy",
    "ReviewSortBy",
    "LibraryStatus",
    "ContentQuality",
    "AudioCodec",
    "DrmType",
    "PlusPlan",
    "ResponseGroups",
    # Logging utilities
    "configure_logging",
    "get_logger",
    "set_level",
    "enable_debug_logging",
    "enable_request_logging",
    "silence_audible_package",
    "LogContext",
    # Marketplace/locale utilities
    "MarketplaceInfo",
    "MARKETPLACES",
    "get_marketplace",
    "list_marketplaces",
    "get_marketplace_for_domain",
    # Activation bytes and device utilities
    "get_activation_bytes",
    "get_activation_bytes_from_file",
    "DeviceInfo",
    "get_device_info",
    "deregister_device",
    "refresh_auth",
    "is_auth_valid",
    "get_auth_info",
]
