# Refactoring Plan: Move Audible Enrichment to `./audible/`

## Problem Statement

The `src/quality/audible_enrichment.py` module contains reusable Audible API parsing logic (pricing, Plus catalog, metadata) that is currently tightly coupled to the quality analysis feature. The series matcher (`src/series/matcher.py`) has duplicated inline price parsing code. This refactoring will centralize Audible data enrichment for use across all features.

## Current State Analysis

### `src/quality/audible_enrichment.py` contains:

**1. Reusable Models** (should move to `audible/models.py`):
- `PricingInfo` - Pricing breakdown (list, sale, member price, discounts)
- `PlusCatalogInfo` - Plus catalog status + expiration
- `AudibleEnrichment` - Full metadata (pricing, plus, atmos, ownership)

**2. Reusable Service** (should move to `audible/enrichment.py`):
- `AudibleEnrichmentService._parse_pricing()` - Parse price dict → `PricingInfo`
- `AudibleEnrichmentService._parse_plans()` - Parse plans → `PlusCatalogInfo`
- `AudibleEnrichmentService.enrich_single()` - Get full metadata for one ASIN

**3. Quality-Specific Logic** (stays in `quality/`):
- `AudibleEnrichment.acquisition_recommendation` - Upgrade recommendations
- `AudibleEnrichment.priority_boost` - Prioritization for upgrades

### `src/series/matcher.py` has duplicated inline price parsing:
- Lines 353-356 and 405-408 manually parse `price.get("list_price", {}).get("base")`
- Uses `is_ayce` for Plus catalog check (incomplete - doesn't check `plans` array)

## Proposed Structure

```
src/audible/
├── __init__.py          # Add: PricingInfo, PlusCatalogInfo exports
├── client.py            # Existing - add parse_pricing(), get_enriched_product()
├── models.py            # Add: PricingInfo, PlusCatalogInfo, ProductEnrichment
└── enrichment.py        # NEW: AudibleEnrichmentService (moved from quality/)

src/quality/
├── audible_enrichment.py  # DEPRECATED → re-export from audible.enrichment
└── ...

src/series/
├── matcher.py           # Use audible.models.PricingInfo instead of inline parsing
└── ...
```

## Step-by-Step Implementation

| Step | Action | Details |
|------|--------|---------|
| 1 | Move models | Move `PricingInfo`, `PlusCatalogInfo` to `audible/models.py` |
| 2 | Add parsing to client | Add `parse_pricing()`, `parse_plus_catalog()` as static methods to `AudibleClient` |
| 3 | Create enrichment module | Move `AudibleEnrichmentService` to `audible/enrichment.py` |
| 4 | Update quality imports | Update `quality/audible_enrichment.py` to re-export from `audible/` for backwards compat |
| 5 | Update series matcher | Use `AudibleClient.parse_pricing()` instead of inline parsing |
| 6 | Update `AudibleCatalogProduct` | Add typed `pricing: PricingInfo` field instead of `price: dict` |

## Detailed Changes

### Step 1: Move Models to `audible/models.py`

```python
# Add to src/audible/models.py

class PricingInfo(BaseModel):
    """Pricing information from Audible."""
    list_price: float | None = None
    sale_price: float | None = None
    credit_price: float = 1.0
    currency: str = "USD"
    price_type: str | None = None
    is_monthly_deal: bool = False

    @property
    def discount_percent(self) -> float | None: ...
    @property
    def is_good_deal(self) -> bool: ...
    @property
    def effective_price(self) -> float | None: ...


class PlusCatalogInfo(BaseModel):
    """Audible Plus Catalog information."""
    is_plus_catalog: bool = False
    plan_name: str | None = None
    expiration_date: datetime | None = None

    @property
    def is_expiring_soon(self) -> bool: ...
    @property
    def days_until_expiration(self) -> int | None: ...
```

### Step 2: Add Parsing Methods to `AudibleClient`

```python
# Add to src/audible/client.py

@staticmethod
def parse_pricing(price_data: dict[str, Any] | None) -> PricingInfo | None:
    """Parse pricing data from API response."""
    ...

@staticmethod  
def parse_plus_catalog(plans: list[dict[str, Any]]) -> PlusCatalogInfo:
    """Parse plans array for Plus Catalog info."""
    ...
```

### Step 3: Update Series Matcher

Replace inline parsing:
```python
# Before (duplicated in two places)
seed_price = None
if seed_product.price and isinstance(seed_product.price, dict):
    seed_price = seed_product.price.get("list_price", {}).get("base")

# After
pricing = AudibleClient.parse_pricing(seed_product.price)
seed_price = pricing.effective_price if pricing else None
is_plus = AudibleClient.parse_plus_catalog(seed_product.plans).is_plus_catalog
```

## Benefits

1. **DRY** - No duplicate price parsing code across features
2. **Consistency** - Same pricing model used everywhere
3. **Testability** - Price/Plus parsing can be unit tested in one place
4. **Extensibility** - Easy to add more pricing features (credits, gift price, etc.)
5. **Plus Catalog Accuracy** - Series matcher will correctly detect Plus books via `plans` array

## Migration Path

1. Add new models and methods (non-breaking)
2. Update series matcher to use new methods
3. Deprecate `quality/audible_enrichment.py` models with re-exports
4. Future: Remove deprecated re-exports after all code migrated

## Testing

- Unit tests for `PricingInfo` properties (discount calculation, good deal threshold)
- Unit tests for `PlusCatalogInfo` properties (expiration logic)
- Integration tests for `parse_pricing()` with real API response samples
- Verify series matcher correctly shows Plus catalog status for missing books
