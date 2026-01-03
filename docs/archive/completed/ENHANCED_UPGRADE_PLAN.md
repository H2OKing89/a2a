# Enhanced Upgrade Detection Plan

```bash
  ██████╗ ██████╗ ███╗   ███╗██████╗ ██╗     ███████╗████████╗███████╗
 ██╔════╝██╔═══██╗████╗ ████║██╔══██╗██║     ██╔════╝╚══██╔══╝██╔════╝
 ██║     ██║   ██║██╔████╔██║██████╔╝██║     █████╗     ██║   █████╗  
 ██║     ██║   ██║██║╚██╔╝██║██╔═══╝ ██║     ██╔══╝     ██║   ██╔══╝  
 ╚██████╗╚██████╔╝██║ ╚═╝ ██║██║     ███████╗███████╗   ██║   ███████╗
  ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚══════╝╚══════╝   ╚═╝   ╚══════╝
```

> **Status:** ✅ COMPLETE - All 5 Phases Implemented  
> **Completed:** January 2, 2026  
> **Related:** [Libation Quality Scan Analysis](./LIBATION_QUALITY_SCAN_ANALYSIS.md)

## Executive Summary

Our discovery with golden samples (Providence USAC, Harry Potter Atmos) revealed critical API limitations. Combined with research from **Libation PR #1527**, we now have a **much faster approach** for quality discovery using the `/content/{asin}/metadata` endpoint.

**Key Breakthrough:** The metadata endpoint provides codec and bitrate information in a single lightweight request (~3x faster than license requests).

---

## Current State Analysis

### What We Learned from Golden Samples

| Sample | Standard API Shows | Actual Format (Widevine) | Issue |
| --- | --- | --- | --- |
| **Providence** | 64 kbps AAC | 128 kbps xHE-AAC | 2x better than reported! |
| **Harry Potter** | 128 kbps AAC stereo | 768 kbps E-AC-3 5.1 Atmos | 6x better than reported! |

### API Limitations Discovered

1. **`available_codecs` doesn't expose USAC/xHE-AAC**
   - Only shows legacy AAX formats: `aax_22_32`, `aax_44_128`
   - Modern formats like USAC hidden in Widevine stream

2. **`has_dolby_atmos` flag IS reliable**
   - Correctly returns `true` for Atmos titles
   - This is the one API field we CAN trust for premium detection

3. **Bitrate in `available_codecs` is misleading**
   - Shows AAX container bitrate, not content bitrate
   - USAC @ 128kbps is perceptually ~224kbps but reports as 64kbps

---

## Quality Discovery Approaches

### Approach 1: License Request (Current - Slow)

Our current `discover_content_quality()` method makes POST requests to `/1.0/content/{asin}/licenserequest` which:

- Is slow (~500ms per request)
- Rate-limited aggressively by Audible
- Returns full download info (overkill for quality check)

### Approach 2: Metadata Endpoint (NEW - Fast) ⭐

Discovered via Libation PR #1527 - uses GET request to metadata endpoint:

```basg
GET /1.0/content/{asin}/metadata
    ?response_groups=chapter_info,content_reference
    &quality=High
    &drm_type={Widevine|Adrm}
```

**Benefits:**

- ~3x faster than license requests
- Single request returns codec + bitrate info
- Less aggressive rate limiting
- Same quality data as license response

### Approach Comparison

| Aspect | License Request | Metadata Endpoint |
| -------- | ----------------- | ------------------- |
| Method | POST | GET |
| Speed | ~500ms | ~150ms |
| Rate Limit | Aggressive | Less strict |
| Data | Full download info | Just quality info |
| Auth | Required | Required |

---

## Codec Reference Table

| API Codec | Format | Typical Bitrate | Quality Tier |
| ----------- | -------- | ----------------- | -------------- |
| `mp4a.40.2` | AAC-LC | 64-128 kbps | Standard |
| `mp4a.40.42` | HE-AAC v2 (xHE-AAC/USAC) | 64-128 kbps | High Efficiency |
| `ec+3` | Enhanced AC-3 (Dolby Digital Plus) | 192-768 kbps | Spatial Audio |
| `ac-4` | AC-4 (Dolby Atmos) | 256-768 kbps | Premium |

### Bitrate Calculation Formula

From Libation's implementation:

```python
bitrate_kbps = (content_size_bytes * 8) / runtime_ms
```

### Significant Upgrade Threshold

Libation uses **32 kbps** as the threshold for a "significant" upgrade:

```python
if new_bitrate - current_bitrate >= 32:
    return "SIGNIFICANT_UPGRADE"
```

This aligns with our finding that upgrades should be meaningful (not just 2-3 kbps).

---

## Two-Tier Quality Discovery

Based on Libation's implementation, we should use a two-tier approach:

### Tier 1: Fast Metadata Scan (Default)

Quick quality check using metadata endpoint:

- Returns codec type and content size
- Calculate bitrate from size/runtime
- Detects Atmos via `ec+3`/`ac-4` codec
- ~150ms per request

### Tier 2: Full License Discovery (On-Demand)

Detailed quality info using license requests:

- Full DRM type enumeration
- Multiple codec probing
- ~500ms+ per request
- Only when fast scan inconclusive

---

## Implementation Plan

### Phase 1: Enhance Local Analysis ✅ (Complete)

**Status:** Implemented in `scanner/mediainfo.py`

- [x] Detect E-AC-3/Atmos codec
- [x] Detect USAC/xHE-AAC codec  
- [x] Parse bitrate accurately
- [x] Detect channel count for surround
- [x] Add `codec_tier` field to Book model
- [x] Add `effective_quality` calculation for USAC (1.75x multiplier)

### Phase 2: Add Metadata Endpoint Support ✅ (Complete)

**Status:** Fully implemented and tested (24 tests passing)

**Implemented:**

- `ContentReference` and `ContentMetadata` models in `src/audible/models.py`
- `get_content_metadata()` method in both sync and async clients
- `fast_quality_check()` method for two-tier quality discovery
- `fast_quality_check_multiple()` for batch operations
- Integration with `AsyncAudibleEnrichmentService`
- CLI `--fast` flag on `quality upgrades` command
- Raw API samples collected in `docs/Audible/samples/content_metadata/`

#### Models (Implemented)

```python
# src/audible/models.py

class ContentReference(BaseModel):
    """Content reference from metadata endpoint."""

    codec: str | None = None  # mp4a.40.2, mp4a.40.42, ec+3, ac-4
    content_format: str | None = None  # M4A, M4A_XHE, M4A_EC3
    content_size_bytes: int = Field(default=0, alias="content_size_in_bytes")
    runtime_ms: int = Field(default=0, alias="runtime_length_ms")
    drm_type: str | None = None  # Adrm, Widevine

    model_config = {"extra": "ignore", "populate_by_name": True}

    @property
    def bitrate_kbps(self) -> float:
        """Calculate bitrate from size and runtime."""
        if self.runtime_ms > 0 and self.content_size_bytes > 0:
            return (self.content_size_bytes * 8) / self.runtime_ms
        return 0.0

    @property
    def is_atmos(self) -> bool:
        """Check if this is Dolby Atmos/spatial audio."""
        return self.codec in ("ec+3", "ac-4")

    @property
    def is_high_efficiency(self) -> bool:
        """Check if this is HE-AAC/USAC."""
        return self.codec == "mp4a.40.42"


class ContentMetadataResponse(BaseModel):
    """Response from /content/{asin}/metadata endpoint."""

    content_reference: ContentReference | None = Field(
        default=None,
        alias="content_reference"
    )
    chapter_info: ChapterInfo | None = None

    model_config = {"extra": "ignore", "populate_by_name": True}
```

#### Async Client Method

```python
# src/audible/async_client.py

async def get_content_metadata(
    self,
    asin: str,
    drm_type: str = "Widevine",  # or "Adrm"
    quality: str = "High",
    use_cache: bool = True,
) -> ContentMetadataResponse | None:
    """
    Get content metadata including quality info.

    This is FASTER than license requests for quality discovery.
    Uses the /content/{asin}/metadata endpoint discovered in Libation PR #1527.

    Args:
        asin: Audible ASIN
        drm_type: "Widevine" for modern formats, "Adrm" for legacy
        quality: "High" or "Normal"
        use_cache: Use cached results

    Returns:
        ContentMetadataResponse with codec and bitrate info
    """
    cache_key = f"metadata_{asin}_{drm_type}_{quality}"

    if use_cache and self._cache:
        cached = self._cache.get("content_metadata", cache_key)
        if cached:
            return ContentMetadataResponse.model_validate(cached)

    try:
        response = await self._request(
            "GET",
            f"1.0/content/{asin}/metadata",
            params={
                "response_groups": "chapter_info,content_reference",
                "quality": quality,
                "drm_type": drm_type,
            },
        )

        if response:
            result = ContentMetadataResponse.model_validate(response)

            if self._cache:
                self._cache.set(
                    "content_metadata",
                    cache_key,
                    result.model_dump(),
                    ttl_seconds=3600 * 24,  # 24 hour cache
                )

            return result

    except Exception as e:
        logger.debug(f"Failed to get content metadata for {asin}: {e}")

    return None
```

#### Fast Quality Check Method

```python
# src/audible/async_client.py

async def fast_quality_check(
    self,
    asin: str,
    use_cache: bool = True,
) -> ContentQualityInfo | None:
    """
    Fast quality check using metadata endpoint.

    This is ~3x faster than the full license request approach.
    Tries Widevine first (modern formats), falls back to Adrm (legacy).

    Args:
        asin: Audible ASIN
        use_cache: Use cached results

    Returns:
        ContentQualityInfo with best available format info
    """
    formats: list[AudioFormat] = []

    # Try Widevine first (modern formats: USAC, Atmos)
    widevine = await self.get_content_metadata(
        asin, drm_type="Widevine", use_cache=use_cache
    )
    if widevine and widevine.content_reference:
        ref = widevine.content_reference
        formats.append(AudioFormat(
            codec=ref.codec or "unknown",
            codec_name=_codec_to_name(ref.codec),
            drm_type="Widevine",
            bitrate_kbps=ref.bitrate_kbps,
            size_bytes=ref.content_size_bytes,
            runtime_ms=ref.runtime_ms,
            is_spatial=ref.is_atmos,
        ))

    # Also try Adrm for comparison (legacy format baseline)
    adrm = await self.get_content_metadata(
        asin, drm_type="Adrm", use_cache=use_cache
    )
    if adrm and adrm.content_reference:
        ref = adrm.content_reference
        formats.append(AudioFormat(
            codec=ref.codec or "unknown",
            codec_name=_codec_to_name(ref.codec),
            drm_type="Adrm",
            bitrate_kbps=ref.bitrate_kbps,
            size_bytes=ref.content_size_bytes,
            runtime_ms=ref.runtime_ms,
            is_spatial=ref.is_atmos,
        ))

    if formats:
        return ContentQualityInfo.from_formats(asin, formats)

    return None


def _codec_to_name(codec: str | None) -> str:
    """Convert codec ID to human-readable name."""
    return {
        "mp4a.40.2": "AAC-LC",
        "mp4a.40.42": "HE-AAC v2",
        "ec+3": "Dolby Digital Plus",
        "ac-4": "Dolby Atmos",
    }.get(codec or "", "Unknown")
```

### Phase 3: Smart Upgrade Logic ✅ (Complete)

**Status:** Implemented in `src/quality/analyzer.py`

- [x] 5% threshold tolerance (121.6 kbps acceptable)
- [x] Minimum 16 kbps upgrade delta
- [x] Priority levels: plus, high, medium, low, met
- [x] Phase 8 re-evaluation after enrichment
- [x] Special handling for USAC-encoded local files
- [x] Don't suggest upgrades for USAC files unless Atmos available
- [x] Add `effective_quality` to upgrade calculations

**Enhanced with Libation findings:**

- [x] Use 32 kbps as "significant upgrade" threshold (Libation-aligned)
- [x] Integrate fast metadata check into upgrade analysis

### Phase 4: Report Enhancements ✅ (Complete)

**Status:** Implemented in CLI output

- [x] Show codec tier badge (ATMOS, USAC, AAC, MP3)
- [x] Show effective quality vs raw bitrate for USAC
- [x] Add tooltip explaining why book isn't upgrade candidate
- [x] Filter upgrade list by codec type

### Phase 5: CLI Integration ✅ (Complete)

**Status:** Implemented in `src/cli/quality.py`

- [x] `--fast` flag on `quality upgrades` command (skips license requests)
- [x] `--plus-only` filter for Plus Catalog items
- [x] `--deals` filter for items under $9.00
- [x] `--monthly-deals` filter for monthly deal items
- [x] Priority boost based on acquisition recommendation
- [x] Async enrichment with progress display

Current CLI usage:

```bash
# Default mode - uses license requests for accurate quality discovery
python cli.py quality upgrades --library LIB_ID

# Fast mode - uses metadata endpoint (skips license requests, ~3x faster)
python cli.py quality upgrades --library LIB_ID --fast

# Filter options
python cli.py quality upgrades --library LIB_ID --plus-only     # FREE items only
python cli.py quality upgrades --library LIB_ID --monthly-deals # Monthly deals
python cli.py quality upgrades --library LIB_ID --deals         # Under $9.00
```

---

## Migration Path

### v1.0 ✅ (Complete)

- [x] Add `get_content_metadata()` method
- [x] Add `fast_quality_check()` method  
- [x] Keep existing `discover_content_quality()` as default
- [x] Add `--fast` CLI flag for quality upgrades

### v1.1 (Planned)

- [ ] Add `--fast` to `quality scan` command
- [ ] Consider making `--fast` the default
- [ ] Add `--full` flag for detailed license scanning

### v2.0 (Future)

- Remove pure license scanning as default
- `--full` flag for backward compatibility
- Document migration from license to metadata approach

---

## Algorithm: Enhanced Upgrade Detection

```python
def analyze_upgrade_potential(book: Book, api_data: dict) -> UpgradeOptions:
    """Analyze potential upgrade options from API data."""

    options = UpgradeOptions()

    # Atmos detection is RELIABLE
    if api_data.get('has_dolby_atmos'):
        options.atmos_available = True
        options.best_upgrade = 'ATMOS'

    # Plus Catalog = FREE upgrade
    if api_data.get('is_plus_catalog'):
        options.is_free = True
        options.priority_boost = 5.0

    # Use fast metadata check for bitrate (if available)
    metadata_quality = api_data.get('metadata_quality')  # From fast_quality_check()
    if metadata_quality:
        options.api_best_bitrate = metadata_quality.best_bitrate_kbps
        options.best_codec = metadata_quality.best_format.codec if metadata_quality.best_format else None
        options.has_atmos = metadata_quality.has_atmos

    return options


def should_upgrade(local: LocalQuality, api: UpgradeOptions) -> UpgradeDecision:
    """Make final upgrade decision with full context."""

    # Already have premium format
    if local.tier == 'ATMOS':
        return UpgradeDecision(
            is_candidate=False,
            priority='met',
            reason='Already have Dolby Atmos'
        )

    if local.tier == 'USAC':
        # USAC is high quality - only upgrade to Atmos
        if api.atmos_available:
            return UpgradeDecision(
                is_candidate=True,
                priority='low',
                reason='Atmos available (optional premium upgrade)'
            )
        return UpgradeDecision(
            is_candidate=False,
            priority='met',
            reason='USAC provides excellent quality'
        )

    # Check for significant upgrade (32 kbps threshold from Libation)
    bitrate_delta = (api.api_best_bitrate or 0) - local.effective_quality
    if bitrate_delta >= 32:
        return UpgradeDecision(
            is_candidate=True,
            priority='high',
            reason=f'+{bitrate_delta:.0f} kbps upgrade available'
        )

    # Standard threshold check with tolerance
    threshold = 128.0
    tolerance = 0.05  # 5%
    min_acceptable = threshold * (1 - tolerance)  # 121.6 kbps

    if local.effective_quality >= min_acceptable:
        return UpgradeDecision(
            is_candidate=False,
            priority='met',
            reason='Quality threshold met'
        )

    # Below threshold - calculate priority
    deficit = (threshold - local.effective_quality) / threshold
    if deficit > 0.2:
        priority = 'high'
    elif deficit > 0.1:
        priority = 'medium'
    else:
        priority = 'low'

    return UpgradeDecision(
        is_candidate=True,
        priority=priority,
        reason=f'{deficit*100:.0f}% below threshold'
    )
```

---

## Rate Limiting Considerations

From Libation's analysis, the metadata endpoint has different rate limiting than license requests:

```python
# Recommended rate limiting for metadata endpoint
METADATA_RATE_LIMIT = {
    "requests_per_second": 5,     # vs 2 for license
    "burst_size": 10,             # vs 5 for license
    "cooldown_after_429": 30,     # seconds
}
```

Consider implementing adaptive rate limiting:

```python
async def adaptive_quality_scan(
    asins: list[str],
    max_concurrent: int = 5,
) -> dict[str, ContentQualityInfo]:
    """Scan with adaptive rate limiting."""

    results = {}
    semaphore = asyncio.Semaphore(max_concurrent)

    async def scan_one(asin: str) -> tuple[str, ContentQualityInfo | None]:
        async with semaphore:
            try:
                result = await fast_quality_check(asin)
                return asin, result
            except RateLimitError:
                # Back off and retry
                await asyncio.sleep(30)
                return asin, await fast_quality_check(asin)

    tasks = [scan_one(asin) for asin in asins]
    for coro in asyncio.as_completed(tasks):
        asin, quality = await coro
        if quality:
            results[asin] = quality

    return results
```

---

## Test Cases (from Golden Samples)

### Test 1: Atmos Content (Harry Potter B0F14RPXHR)

```python
def test_atmos_not_upgrade_candidate():
    """User owns Atmos version - should NOT be upgrade candidate."""
    book = Book(
        asin='B0F14RPXHR',
        codec='E-AC-3',
        bitrate_kbps=768,
        has_dolby_atmos=True
    )

    result = is_upgrade_candidate(book)

    assert result.is_candidate == False
    assert result.priority == 'met'
    assert 'Atmos' in result.reason
```

### Test 2: USAC Content (Providence B0DJPYFJ2K)

```python
def test_usac_not_upgrade_candidate():
    """User owns USAC version - should NOT be upgrade candidate."""
    book = Book(
        asin='B0DJPYFJ2K',
        codec='xHE-AAC',
        bitrate_kbps=128,
        has_dolby_atmos=False
    )

    result = is_upgrade_candidate(book)

    assert result.is_candidate == False
    assert result.priority == 'met'
```

### Test 3: Fast Quality Check

```python
async def test_fast_quality_check():
    """Fast metadata endpoint returns quality info."""
    async with AsyncAudibleClient.from_file("auth.json") as client:
        quality = await client.fast_quality_check("B0DJPYFJ2K")

        assert quality is not None
        assert quality.best_bitrate_kbps > 0
        # Should detect USAC via Widevine
        assert quality.has_high_efficiency == True
```

### Test 4: Significant Upgrade Detection

```python
def test_significant_upgrade_threshold():
    """32 kbps delta should trigger significant upgrade."""
    local = LocalQuality(codec='AAC', bitrate_kbps=64)
    api = UpgradeOptions(api_best_bitrate=128)  # +64 kbps

    result = should_upgrade(local, api)

    assert result.is_candidate == True
    assert result.priority == 'high'
    assert '+64' in result.reason
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/audible/models.py` | Add `ContentReference`, `ContentMetadataResponse` |
| `src/audible/async_client.py` | Add `get_content_metadata()`, `fast_quality_check()` |
| `src/audible/enrichment.py` | Use `fast_quality_check()` in enrichment pipeline |
| `src/quality/analyzer.py` | Integrate fast metadata quality into analysis |
| `src/cli/quality.py` | Add `--fast`/`--full` flags |
| `tests/test_quality.py` | Add tests for metadata endpoint |

---

## Summary

### Key Principles

1. **Use metadata endpoint for fast quality discovery** (~3x faster than license requests)
2. **Trust local mediainfo over API bitrate** for quality assessment
3. **Detect premium codecs** (USAC, E-AC-3) and don't flag as upgrade candidates
4. **Use 32 kbps as significant upgrade threshold** (Libation-aligned)
5. **`has_dolby_atmos` is reliable** - use it!
6. **Two-tier approach:** Fast metadata → Full license only when needed

### Priority Order

1. Plus Catalog items (FREE!)
2. Legacy codecs (MP3)
3. Significant upgrades (32+ kbps delta)
4. Moderately below threshold (10-20% deficit)  
5. Slightly below threshold with big upgrade available
6. Skip: Near/above threshold, USAC, or Atmos content

---

## Appendix: Codec Detection Patterns

```python
# MediaInfo codec string patterns
ATMOS_PATTERNS = ['E-AC-3', 'EC-3', 'EAC3', 'DOLBY DIGITAL PLUS']
USAC_PATTERNS = ['USAC', 'XHE-AAC', 'XHE_AAC', 'XHEAAC', 'MP4A.40.42']
AAC_PATTERNS = ['AAC', 'MP4A']
MP3_PATTERNS = ['MP3', 'MPEG AUDIO', 'LAYER 3']

# API codec identifiers (from metadata endpoint)
API_CODEC_MAP = {
    'mp4a.40.2': CodecTier.AAC_HIGH,    # AAC-LC
    'mp4a.40.42': CodecTier.USAC,       # HE-AAC v2 / xHE-AAC
    'ec+3': CodecTier.ATMOS,            # Dolby Digital Plus
    'ac-4': CodecTier.ATMOS,            # Dolby AC-4
}

def detect_codec_tier(codec_string: str) -> CodecTier:
    """Detect codec tier from mediainfo codec string."""
    codec_upper = codec_string.upper()

    for pattern in ATMOS_PATTERNS:
        if pattern in codec_upper:
            return CodecTier.ATMOS

    for pattern in USAC_PATTERNS:
        if pattern in codec_upper:
            return CodecTier.USAC

    for pattern in MP3_PATTERNS:
        if pattern in codec_upper:
            return CodecTier.MP3

    for pattern in AAC_PATTERNS:
        if pattern in codec_upper:
            return CodecTier.AAC_HIGH  # Determine HQ/LQ by bitrate

    return CodecTier.UNKNOWN
```
