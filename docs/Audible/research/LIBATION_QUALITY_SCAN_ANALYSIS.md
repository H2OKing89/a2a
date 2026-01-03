# Libation Quality Scan Analysis

> **⚠️ Note:** This is exploratory research documentation that informed PR #25's month-aware cache TTL implementation.
> The metadata endpoint integration and two-tier quality discovery features described here are **future planning** (v1.1+),
> not part of the current PR. This document captures findings from Libation PR #1527 for reference and future feature development.

**Date**: January 2, 2026,
**Source**: [Libation PR #1527](https://github.com/rmcrackan/Libation/pull/1527)  
**Purpose**: Extract techniques for improving a2a's quality analysis and Audible integration

---

## Executive Summary

Libation's "Scan for Higher Quality Books" feature reveals a simpler, faster approach to querying Audible for audio quality information. Their implementation uses a lightweight metadata endpoint instead of the heavier license-request approach currently used by a2a.

**Key Takeaway**: We can significantly speed up quality discovery by using the `/content/{asin}/metadata` endpoint as a fast path.

---

## 1. Audible API Endpoint Discovery

### 1.1 Content Metadata Endpoint (NEW - Not Currently Used by a2a)

> **⚠️ API Stability:** This endpoint is **not officially documented by Audible**. The specifications are community reverse-engineered
> from Libation and other projects. Audible may change this endpoint's behavior or deprecate it without notice.
> Use in production with caution and monitor for changes.

```bash
GET /1.0/content/{asin}/metadata
    ?response_groups=chapter_info,content_reference
    &quality=High
    &drm_type={Widevine|Adrm}
```

**Response Structure**:

```json
{
  "content_metadata": {
    "chapter_info": {
      "runtime_length_ms": 36000000,
      "runtime_length_sec": 36000,
      "chapters": [...]
    },
    "content_reference": {
      "content_size_in_bytes": 500000000,
      "codec": "mp4a.40.2"  // or "mp4a.40.42", "ec+3", "ac-4"
    }
  }
}
```

**DRM Types**:

| DRM Type | Typical Codec | Quality Range | Notes |
| ---------- | --------------- | --------------- | ------- |
| `Adrm` | AAC-LC (`mp4a.40.2`) | 64-128 kbps | Legacy Audible format |
| `Widevine` | HE-AAC (`mp4a.40.42`) or xHE-AAC | 114+ kbps | Modern streaming format |

**Advantages over License Requests**:

- Single GET request vs multiple POST requests
- No license generation overhead
- Faster response times
- Less likely to trigger rate limiting

### 1.2 Codec String Mappings

From Libation's `AudibleApi.Codecs`:

```csharp
AAC_LC = "mp4a.40.2"      // Standard AAC
xHE_AAC = "mp4a.40.42"    // High-Efficiency AAC v2 (often mislabeled)
EC_3 = "ec+3"             // Enhanced AC-3 (Dolby Digital Plus)
AC_4 = "ac-4"             // AC-4 (Dolby Atmos)
```

**a2a Current Mappings** (from `src/audible/models.py`):

```python
class AudioCodec(str, Enum):
    AAC_LC = "mp4a.40.2"
    HE_AAC = "mp4a.40.42"  # Note: Libation calls this xHE_AAC
    EC3 = "ec+3"
    AC4 = "ac-4"
```

✅ Our mappings align with Libation's findings.

---

## 2. Bitrate Calculation Method

### 2.1 Libation's Approach

```csharp
var bitrate = (int)(totalSize / 1024d * 1000 / totalLengthMs * 8); // in kbps
```

### 2.2 Correct Formula Derivation

**Units analysis:**
- `size_bytes * 8` → bits
- `runtime_ms / 1000` → seconds
- `bits / seconds / 1000` → kilobits per second (kbps)

**Correct formula:**

```python
bitrate_kbps = (content_size_bytes * 8) / (runtime_ms / 1000) / 1000
             = (content_size_bytes * 8000) / runtime_ms
```

Both forms are equivalent. Use the second for direct calculation without intermediate division.

### 2.3 Comparison with a2a's Current Approach

**a2a** uses license requests which return explicit bitrate in the response. The calculated approach is:

- ✅ Faster (single request)
- ⚠️ Less accurate (includes container overhead)
- ⚠️ Doesn't work well for VBR encodings

**Recommendation**: Use metadata endpoint for fast screening, license requests for accurate quality info.

---

## 3. Quality Tier Comparison Logic

### 3.1 Libation's "Significant Upgrade" Detection

```csharp
public bool IsSignificant =>
    AvailableBitrate > 0 &&
    Bitrate > 0 &&
    (AvailableBitrate - Bitrate) >= 32;  // 32 kbps threshold
```

They also factor in codec changes:

- AAC-LC → HE-AAC = significant even at same bitrate
- Any → Dolby Atmos = always significant

### 3.2 Proposed a2a Integration

Map to our existing `QualityTier` system:

```python
def is_significant_upgrade(current: AudioQuality, available: AudibleEnrichment) -> bool:
    """Determine if Audible has a significantly better version available."""

    # Atmos upgrade is always significant
    if available.has_atmos and not current.is_atmos:
        return True

    # Codec upgrade (AAC-LC → HE-AAC) is significant
    if current.codec == "aac" and available.actual_best_format in ("HE-AAC", "xHE-AAC"):
        return True

    # Bitrate improvement of 32+ kbps is significant
    current_bitrate = current.bitrate_kbps
    available_bitrate = available.actual_best_bitrate or 0

    if available_bitrate - current_bitrate >= 32:
        return True

    return False
```

---

## 4. Implementation Plan

### Phase 1: Add Metadata Endpoint Support

**File**: `src/audible/async_client.py`

```python
async def get_content_metadata(
    self,
    asin: str,
    drm_type: str = "Widevine",  # or "Adrm"
    quality: str = "High",
    use_cache: bool = True,
) -> ContentMetadata:
    """
    Fast quality check using content metadata endpoint.

    This is faster than license requests but less detailed.
    Use for initial screening, then license requests for accurate data.
    """
    response = await self._request(
        "GET",
        f"1.0/content/{asin}/metadata",
        response_groups="chapter_info,content_reference",
        quality=quality,
        drm_type=drm_type,
    )
    return ContentMetadata.model_validate(response)
```

**New Model** (add to `src/audible/models.py`):

```python
class ContentReference(BaseModel):
    """Content reference from metadata endpoint."""
    content_size_in_bytes: int = Field(default=0, alias="content_size_in_bytes")
    codec: str | None = None

    model_config = {"extra": "ignore", "populate_by_name": True}


class ContentMetadataResponse(BaseModel):
    """Response from /content/{asin}/metadata endpoint."""
    chapter_info: ChapterInfo | None = None
    content_reference: ContentReference | None = None

    model_config = {"extra": "ignore", "populate_by_name": True}

    @property
    def calculated_bitrate_kbps(self) -> int | None:
        """Calculate bitrate from size and runtime."""
        if not self.content_reference or not self.chapter_info:
            return None

        size_bytes = self.content_reference.content_size_in_bytes
        runtime_ms = self.chapter_info.runtime_length_ms

        if not size_bytes or not runtime_ms:
            return None

        return int((size_bytes * 8) / runtime_ms)

    @property
    def codec_name(self) -> str:
        """Human-readable codec name."""
        codec = self.content_reference.codec if self.content_reference else None
        return {
            "mp4a.40.2": "AAC-LC",
            "mp4a.40.42": "HE-AAC",
            "ec+3": "Dolby Digital Plus",
            "ac-4": "Dolby Atmos",
        }.get(codec or "", codec or "Unknown")
```

### Phase 2: Two-Tier Quality Discovery

```python
class AsyncAudibleEnrichmentService:

    async def fast_quality_check(
        self,
        asin: str,
        use_cache: bool = True,
    ) -> tuple[str | None, int | None]:
        """
        Fast quality check using metadata endpoint.

        Returns (codec, bitrate_kbps) or (None, None) if unavailable.

        Use this for batch scanning, then use full quality discovery
        for items that need detailed info.
        """
        for drm_type in ("Widevine", "Adrm"):
            try:
                metadata = await self._client.get_content_metadata(
                    asin, drm_type=drm_type, use_cache=use_cache
                )
                if metadata.content_reference:
                    return (
                        metadata.codec_name,
                        metadata.calculated_bitrate_kbps,
                    )
            except Exception:
                continue

        return None, None

    async def enrich_with_fast_quality(
        self,
        asin: str,
        use_cache: bool = True,
    ) -> AudibleEnrichment:
        """
        Enrichment with fast quality check instead of license requests.

        ~3x faster than full license-based quality discovery.
        """
        # Get catalog data (pricing, Plus status, etc.)
        enrichment = await self.enrich_single_with_quality(
            asin, use_cache=use_cache, discover_quality=False
        )

        if enrichment:
            # Add fast quality check
            codec, bitrate = await self.fast_quality_check(asin, use_cache)
            if codec and bitrate:
                enrichment.best_bitrate = bitrate
                # Update has_atmos based on codec
                enrichment.has_atmos = codec in ("Dolby Atmos", "Dolby Digital Plus")

        return enrichment
```

### Phase 3: CLI Integration

Add new option to quality scan:

```python
@quality_app.command("scan")
def scan_quality(
    library_id: str,
    fast_mode: bool = typer.Option(
        False, "--fast", "-f",
        help="Use fast quality check (less accurate but 3x faster)"
    ),
    ...
):
    """Scan library for quality and upgrade candidates."""
```

---

## 5. Rate Limiting Considerations

### 5.1 Libation's Issue

The PR has no rate limiting, which is risky for large libraries:

```csharp
// No delay between requests - potential issue!
for (int i = 0; i < Books.Count; i++)
{
    var resp = await cli.GetAsync(url, cts.Token);
}
```

### 5.2 a2a's Current Approach

We already have better handling via:

- SQLite caching with TTL
- Semaphore-based concurrency limits in `enrich_batch_with_quality()`

**Recommendation**: Keep our approach but add explicit rate limiting:

```python
# In async enrichment
async def _rate_limited_request(self, semaphore, delay_ms=100):
    async with semaphore:
        await asyncio.sleep(delay_ms / 1000)
        # ... make request
```

---

## 6. Feature Comparison

| Feature | Libation | a2a Current | a2a Proposed |
| --------- | ---------- | ------------- | -------------- |
| Quality Discovery | Metadata endpoint | License requests | Both (tiered) |
| Batch Scanning | Sequential | Concurrent (semaphore) | Keep concurrent |
| Caching | None | SQLite with TTL | Keep + add metadata cache |
| Rate Limiting | None | Semaphore only | Add explicit delays |
| Significant Upgrade | 32 kbps threshold | Tier comparison | Add bitrate threshold |
| Codec Comparison | Basic | Detailed | Keep detailed |
| Atmos Detection | Via codec | Via license + catalog | Add metadata check |
| Progress Tracking | UI events | Callback function | Keep callbacks |

---

## 7. Files to Modify

### New Files

- None (extend existing modules)

### Modified Files

1. `src/audible/models.py` - Add `ContentMetadataResponse` model
2. `src/audible/async_client.py` - Add `get_content_metadata()` method
3. `src/audible/enrichment.py` - Add `fast_quality_check()` method
4. `src/quality/analyzer.py` - Add `is_significant_upgrade()` logic
5. `src/cli/quality.py` - Add `--fast` option to scan command
6. `tests/test_audible_client.py` - Add tests for new endpoint

---

## 8. Migration Path

1. **v1.0**: Add metadata endpoint support alongside existing license requests
2. **v1.1**: Add `--fast` flag to CLI for optional fast mode
3. **v1.2**: Make fast mode default for initial scan, detailed for candidates only
4. **v2.0**: Deprecate pure license-request scanning for non-owned books

---

## 9. Resolved Questions

> **Status:** All questions from initial research have been resolved through implementation.

1. **Cache namespace**: Should metadata results share cache with license results?
   - ✅ **Resolved:** Separate namespaces implemented:
     - `content_metadata` - Raw metadata endpoint responses
     - `content_quality` - Parsed quality info from `fast_quality_check()`
     - `audible_enrichment_v2` - Full enrichment with quality data

2. **Widevine vs Adrm priority**: Which to query first?
   - ✅ **Resolved:** Widevine first, then Adrm for comparison
   - Implementation in `async_client.py:fast_quality_check()` tries Widevine first (modern HE-AAC/USAC formats, ~114 kbps), then Adrm (legacy AAC-LC, ~64-128 kbps)
   - Both results are collected to find the best available format

3. **Error handling**: What if metadata endpoint fails but license works?
   - ✅ **Resolved:** License requests deprecated as primary path
   - `fast_quality_check()` is now the default quality discovery method
   - `discover_content_quality()` (license-based) still exists but is not used by the enrichment service
   - If metadata fails for both DRM types, quality info is simply unavailable (graceful degradation)

4. **Owned vs catalog**: Does metadata endpoint work for non-owned books?
   - ✅ **Resolved:** Works for owned books; catalog books return limited data
   - For upgrade analysis, we only need quality info for books we own locally anyway
   - Non-owned catalog books use `available_codecs` from product API (less accurate but sufficient for purchase decisions)

---

## 10. References

- Libation PR: <https://github.com/rmcrackan/Libation/pull/1527>
- AudibleApi Codecs: `Source/AudibleApi/Codecs.cs`
- a2a Quality Models: `src/quality/models.py`
- a2a Audible Models: `src/audible/models.py`
