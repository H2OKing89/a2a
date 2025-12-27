# Audible Module Refactoring - COMPLETED ✅

## Summary

Centralized all Audible API functionality into `src/audible/` module for reuse across features (quality analysis, series matching, etc.).

## Implementation Status

| Step | Status | Description |
|------|--------|-------------|
| 1. Move models | ✅ DONE | `PricingInfo`, `PlusCatalogInfo` moved to `audible/models.py` |
| 2. Add parsing to client | ✅ DONE | `parse_pricing()`, `parse_plus_catalog()` static methods added |
| 3. Create enrichment module | ✅ DONE | `audible/enrichment.py` created with `AudibleEnrichmentService` |
| 4. Backwards compatibility | ✅ DONE | `quality/audible_enrichment.py` re-exports with deprecation warning |
| 5. Update series matcher | ✅ DONE | Uses `PricingInfo.from_api_response()` and `_check_plus_catalog()` |
| 6. Add API enums | ✅ DONE | `SimilarityType`, `LibrarySortBy`, `CatalogSortBy`, etc. |
| 7. Add Wishlist support | ✅ DONE | `get_wishlist()`, `add_to_wishlist()`, `remove_from_wishlist()` |
| 8. Add Recommendations | ✅ DONE | `get_recommendations()` endpoint |
| 9. Add Content metadata | ✅ DONE | `get_content_metadata()`, `supports_dolby_atmos()` |
| 10. Add Async client | ✅ DONE | `AsyncAudibleClient` for concurrent operations |
| 11. Add Logging module | ✅ DONE | `configure_logging()`, `get_logger()`, `LogContext` |
| 12. Add Utilities | ✅ DONE | Marketplace info, activation bytes, device management |

## New Module Structure

```
src/audible/
├── __init__.py          # Exports all models, enums, and services
├── client.py            # AudibleClient - sync API client
├── async_client.py      # AsyncAudibleClient - async API client
├── models.py            # All Pydantic models and API enums
├── enrichment.py        # AudibleEnrichment + AudibleEnrichmentService
├── logging.py           # Logging configuration and utilities
└── utils.py             # Marketplace info, activation bytes, device utils
```

## API Enums Added

| Enum | Purpose | Values |
|------|---------|--------|
| `SimilarityType` | /sims endpoint | `IN_SAME_SERIES`, `BY_SAME_AUTHOR`, `BY_SAME_NARRATOR`, `NEXT_IN_SERIES`, `RAW_SIMILARITIES` |
| `LibrarySortBy` | /library sorting | `AUTHOR`, `LENGTH`, `NARRATOR`, `PURCHASE_DATE`, `TITLE` (+ DESC variants) |
| `CatalogSortBy` | /catalog sorting | `RELEASE_DATE`, `TITLE`, `AVG_RATING`, `BEST_SELLERS`, `RELEVANCE`, etc. |
| `WishlistSortBy` | /wishlist sorting | `AUTHOR`, `DATE_ADDED`, `PRICE`, `RATING`, `TITLE` (+ DESC variants) |
| `LibraryStatus` | Library filter | `ACTIVE` (owned), `REVOKED` (returned) |
| `ContentQuality` | Audio quality | `HIGH`, `NORMAL` |
| `AudioCodec` | Audio formats | `AAC_LC`, `HE_AAC`, `EC3` (Dolby Digital+), `AC4` (Dolby Atmos) |
| `DrmType` | DRM types | `ADRM`, `FAIR_PLAY`, `WIDEVINE`, etc. |
| `PlusPlan` | Plus plans | `US_MINERVA`, `ALL_YOU_CAN_EAT`, `RODIZIO`, etc. |
| `ResponseGroups` | API response groups | Pre-built strings for common use cases |

## New Models Added

| Model | Purpose |
|-------|---------|
| `PricingInfo` | Pricing with discount calculation, good deal detection |
| `PlusCatalogInfo` | Plus Catalog status with expiration tracking |
| `WishlistItem` | Wishlist item with Plus Catalog detection |
| `WishlistResponse` | Wishlist API response |
| `ContentMetadata` | Content info with codec/Atmos detection |
| `ChapterInfo` | Chapter details for audiobooks |

## New Client Methods

### Wishlist Management
```python
client.get_wishlist(sort_by=WishlistSortBy.DATE_ADDED_DESC)
client.get_all_wishlist()  # Handles pagination
client.add_to_wishlist(asin)
client.remove_from_wishlist(asin)
client.is_in_wishlist(asin)
```

### Recommendations
```python
client.get_recommendations(num_results=50)
```

### Content/Quality Info
```python
client.get_content_metadata(asin)  # Chapters, codecs, etc.
client.get_chapter_info(asin)
client.supports_dolby_atmos(asin)  # Quick Atmos check
```

### Enhanced Existing Methods
```python
# Now accept enums for type safety
client.get_library(sort_by=LibrarySortBy.TITLE, status=LibraryStatus.ACTIVE)
client.search_catalog(sort_by=CatalogSortBy.BEST_SELLERS)
client.get_similar_products(asin, similarity_type=SimilarityType.BY_SAME_AUTHOR)
```

## Usage Examples

### Type-safe API calls
```python
from src.audible import (
    AudibleClient,
    SimilarityType,
    LibrarySortBy,
    PricingInfo,
)

with get_audible_client() as client:
    # Get library sorted by title
    items = client.get_library(sort_by=LibrarySortBy.TITLE)

    # Find other books by same author
    similar = client.get_similar_products(
        asin="B00123",
        similarity_type=SimilarityType.BY_SAME_AUTHOR
    )

    # Parse pricing
    pricing = PricingInfo.from_api_response(product.price)
    if pricing and pricing.is_good_deal:
        print(f"On sale: ${pricing.effective_price}")
```

### Wishlist management
```python
# Add to wishlist
client.add_to_wishlist("B00123")

# Check wishlist for Plus Catalog items
wishlist = client.get_all_wishlist()
plus_items = [item for item in wishlist if item.is_plus_catalog]
```

### Check Dolby Atmos support
```python
if client.supports_dolby_atmos(asin):
    print("🎵 Dolby Atmos available!")
```

## Async Client

For concurrent operations (batch fetches, multiple API calls):

```python
import asyncio
from src.audible import AsyncAudibleClient

async def fetch_multiple_books():
    async with AsyncAudibleClient() as client:
        # Fetch multiple products concurrently
        asins = ["B00123", "B00456", "B00789"]
        products = await client.get_multiple_products(asins)

        # Or use individual async methods
        library = await client.get_library()
        wishlist = await client.get_wishlist()

        # Rate limiting built-in (respects max_concurrent)
        for item in library[:10]:
            content = await client.get_content_metadata(item["asin"])

# Run async code
asyncio.run(fetch_multiple_books())
```

Key features:
- `get_multiple_products()` - Batch fetch with semaphore-based rate limiting
- All sync client methods available as async equivalents
- Automatic connection pooling via `httpx.AsyncClient`

## Logging Module

Integrated with the `audible` package's internal logging:

```python
from src.audible import configure_logging, get_logger, LogContext

# Configure logging (file + console)
configure_logging(
    level="debug",           # debug, info, warning, error
    console=True,            # Print to stdout
    file_path="logs/audible.log",  # Optional file output
    capture_audible=True     # Capture audible package logs
)

# Get a logger for your module
logger = get_logger("my_feature")
logger.info("Starting analysis")

# Use context manager for scoped logging
with LogContext(operation="library_sync", asin="B00123"):
    # All logs in this block include operation and asin
    logger.debug("Fetching item")
```

Environment variable support:
- `AUDIBLE_LOG_LEVEL` - Set log level (debug/info/warning/error)
- `AUDIBLE_LOG_FILE` - Path for file logging

## Utilities Module

### Marketplace Information

```python
from src.audible import (
    get_marketplace,
    list_marketplaces,
    get_marketplace_for_domain,
)

# Get US marketplace
us = get_marketplace("us")
print(us.name)       # "United States"
print(us.domain)     # "audible.com"
print(us.currency)   # "USD"
print(us.api_domain) # "api.audible.com"

# Get all 10 supported marketplaces
for locale, mp in list_marketplaces():
    print(f"{locale}: {mp.name}")

# Lookup by domain
uk = get_marketplace_for_domain("audible.co.uk")
```

Supported marketplaces: us, uk, de, fr, ca, au, it, in, jp, es

### Activation Bytes (for DRM tools)

```python
from src.audible import get_activation_bytes, get_auth_info

# Get activation bytes for ffmpeg/inAudible
auth = Authenticator.from_file("data/audible_auth.json")
bytes_hex = get_activation_bytes(auth)
print(f"ffmpeg -activation_bytes {bytes_hex} ...")

# Check auth file info
info = get_auth_info("data/audible_auth.json")
print(f"Locale: {info['locale']}")
print(f"Device: {info['device_name']}")
print(f"Expires: {info['expires']}")
```

### Device Management

```python
from src.audible import get_device_info, deregister_device

# Get current device info
device = get_device_info(auth)

# Deregister (use with caution)
# deregister_device(auth)
```

## Import Path

Use the centralized audible module for enrichment:
```python
from src.audible import AudibleEnrichment, AudibleEnrichmentService, PricingInfo, PlusCatalogInfo
```

## Benefits

1. **DRY** - No duplicate parsing code across features
2. **Type Safety** - Enums prevent typos in API parameters
3. **Discoverability** - IDE autocomplete shows available options
4. **Consistency** - Same models used everywhere
5. **Testability** - Centralized parsing can be unit tested once
6. **Extensibility** - Easy to add new features (orders, collections, etc.)
7. **Async Support** - Concurrent operations for batch processing
8. **Logging** - Integrated with audible package internals
9. **Multi-market** - Easy support for international markets

## Testing

All 81 tests pass:
```bash
make test  # pytest with coverage
```

Test coverage includes:
- Unit tests for `PricingInfo` properties (discount calculation, good deal threshold)
- Unit tests for `PlusCatalogInfo` properties (expiration logic)
- Integration tests for `parse_pricing()` with real API response samples
- Import tests for all new modules (async, logging, utils)
- Auth file validation tests
