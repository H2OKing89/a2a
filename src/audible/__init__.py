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
from .encryption import (
    AuthFileEncryption,
    get_auth_password_from_env,
    get_encryption_config,
    get_file_encryption_style,
    is_file_encrypted,
    load_auth,
    save_auth,
)
from .enrichment import AsyncAudibleEnrichmentService, AudibleEnrichment, AudibleEnrichmentService
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
    LICENSE_TEST_CONFIGS,
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
    AudioFormat,
    CatalogSortBy,
    ChapterInfo,
    ContentMetadata,
    ContentQuality,
    ContentQualityInfo,
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
    "AudioFormat",
    "ContentQualityInfo",
    "LICENSE_TEST_CONFIGS",
    # Pricing and Plus Catalog
    "PricingInfo",
    "PlusCatalogInfo",
    # Encryption utilities
    "AuthFileEncryption",
    "get_encryption_config",
    "load_auth",
    "save_auth",
    "is_file_encrypted",
    "get_file_encryption_style",
    "get_auth_password_from_env",
    # Enrichment service
    "AudibleEnrichment",
    "AudibleEnrichmentService",
    "AsyncAudibleEnrichmentService",
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
