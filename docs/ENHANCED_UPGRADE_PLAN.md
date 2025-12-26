# Enhanced Upgrade Detection Plan

## Executive Summary

Our discovery with golden samples (Providence USAC, Harry Potter Atmos) revealed critical API limitations. This document outlines an enhanced upgrade detection system that properly handles modern codecs and avoids false positives.

---

## Current State Analysis

### What We Learned from Golden Samples

| Sample | Standard API Shows | Actual Format (Widevine) | Issue |
|--------|-------------------|--------------------------|-------|
| **Providence** | 64 kbps AAC | 128 kbps xHE-AAC | 2x better than reported! |
| **Harry Potter** | 128 kbps AAC stereo | 768 kbps E-AC-3 5.1 Atmos | 6x better than reported! |

### API Limitations Discovered

1. **`available_codecs` doesn't expose USAC/xHE-AAC**
   - Only shows legacy AAC formats (LC_32, LC_64, LC_128)
   - USAC availability is hidden
   
2. **`best_available_bitrate` is misleading for modern formats**
   - Shows 64 kbps for USAC content (actual 128 kbps)
   - Shows 128 kbps for Atmos content (actual 768 kbps)

3. **Reliable API signals:**
   - ✅ `has_dolby_atmos` - Works correctly!
   - ✅ `asset_details[].is_spatial` - Works correctly!
   - ❌ `best_available_bitrate` - Unreliable for modern formats
   - ❌ `available_codecs` - Missing USAC/Atmos info

---

## Codec Reference Table

| Codec ID | Name | Efficiency | Typical Bitrate | Notes |
|----------|------|------------|-----------------|-------|
| `mp4a.40.42` | xHE-AAC/USAC | ~2x LC-AAC | 64-128 kbps | Modern efficient codec |
| `ec+3` | E-AC-3/DD+ | N/A | 768 kbps | Dolby Atmos carrier |
| `LC_128_44100_stereo` | AAC-LC | Baseline | 128 kbps | Standard quality |
| `LC_64_22050_stereo` | AAC-LC | Baseline | 64 kbps | Lower quality |
| `MP3` | MP3 | ~0.7x AAC | Various | Legacy format |

### Quality Equivalencies

```
128 kbps xHE-AAC ≈ 200-256 kbps AAC-LC (equivalent perceptual quality)
768 kbps E-AC-3 = Premium spatial audio (incomparable - different use case)
64 kbps AAC-LC ≈ 45 kbps xHE-AAC (if converted)
```

---

## Enhanced Upgrade Detection Algorithm

### Phase 1: Local File Analysis (Primary)

```python
def analyze_local_quality(mediainfo: dict) -> LocalQuality:
    """Analyze local file to determine true quality."""
    codec = mediainfo.get('codec', '').upper()
    bitrate = mediainfo.get('bitrate_kbps')
    channels = mediainfo.get('channels', 2)
    
    # Detect premium formats
    if 'E-AC-3' in codec or 'EC-3' in codec:
        return LocalQuality(
            tier='ATMOS',
            effective_quality=768,
            is_premium=True,
            upgrade_possible=False  # Already best
        )
    
    if 'USAC' in codec or 'XHE' in codec:
        # USAC is ~2x efficient
        effective_quality = bitrate * 2 if bitrate else 256
        return LocalQuality(
            tier='USAC',
            effective_quality=effective_quality,
            is_premium=True,
            upgrade_possible=False  # USAC is excellent
        )
    
    # Standard AAC
    return LocalQuality(
        tier='AAC',
        effective_quality=bitrate,
        is_premium=False,
        upgrade_possible=True
    )
```

### Phase 2: API Enrichment (Secondary)

```python
def check_upgrade_availability(api_data: dict) -> UpgradeOptions:
    """Check what upgrades are available via API."""
    
    options = UpgradeOptions()
    
    # Atmos detection is RELIABLE
    if api_data.get('has_dolby_atmos'):
        options.atmos_available = True
        options.best_upgrade = 'ATMOS'
    
    # Plus Catalog = FREE upgrade
    if api_data.get('is_plus_catalog'):
        options.is_free = True
        options.priority_boost = 5.0
    
    # Bitrate upgrade (only trust for non-Atmos, non-USAC)
    api_bitrate = api_data.get('best_available_bitrate', 0)
    if not options.atmos_available:
        options.api_best_bitrate = api_bitrate
        # But don't trust it fully - could be USAC hidden
    
    return options
```

### Phase 3: Smart Upgrade Decision

```python
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
    
    # Standard AAC - check upgrade options
    threshold = 128.0
    tolerance = 0.05  # 5%
    min_acceptable = threshold * (1 - tolerance)  # 121.6 kbps
    
    if local.effective_quality >= min_acceptable:
        # Near threshold - only major upgrades
        if api.atmos_available:
            return UpgradeDecision(
                is_candidate=True,
                priority='medium',
                reason='Atmos upgrade available'
            )
        return UpgradeDecision(
            is_candidate=False,
            priority='met',
            reason='Quality threshold met'
        )
    
    # Below threshold - upgrade candidate
    if api.is_free:
        return UpgradeDecision(
            is_candidate=True,
            priority='plus',
            reason='Plus Catalog - FREE!'
        )
    
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

## Implementation Plan

<<<<<<< HEAD
### Phase 1: Enhance Local Analysis ✅ (Complete)
=======
### Phase 1: Enhance Local Analysis ✅ (Mostly Done)
>>>>>>> d107b4b (feat: Remove obsolete scraper output and enhance upgrade card functionality)

**Status:** Implemented in `scanner/mediainfo.py`

- [x] Detect E-AC-3/Atmos codec
- [x] Detect USAC/xHE-AAC codec  
- [x] Parse bitrate accurately
- [x] Detect channel count for surround
<<<<<<< HEAD
- [x] Add `codec_tier` field to Book model
- [x] Add `effective_quality` calculation for USAC (1.75x multiplier)
=======

**Enhancements Needed:**
- [ ] Add `codec_tier` field to MediaInfo model
- [ ] Add `effective_quality` calculation for USAC
>>>>>>> d107b4b (feat: Remove obsolete scraper output and enhance upgrade card functionality)

### Phase 2: Improve API Integration ⚠️ (Partial)

**Status:** Basic implementation exists

- [x] `has_dolby_atmos` detection
- [x] `is_plus_catalog` detection
- [x] Parse `available_codecs`

<<<<<<< HEAD
**Future Enhancements:**
=======
**Enhancements Needed:**
>>>>>>> d107b4b (feat: Remove obsolete scraper output and enhance upgrade card functionality)
- [ ] Add `api_quality_reliable` flag (false for Atmos/USAC titles)
- [ ] Track `asset_details` for spatial info
- [ ] Consider Widevine integration for true quality detection

<<<<<<< HEAD
### Phase 3: Smart Upgrade Logic ✅ (Complete)
=======
### Phase 3: Smart Upgrade Logic ✅ (Recently Done)
>>>>>>> d107b4b (feat: Remove obsolete scraper output and enhance upgrade card functionality)

**Status:** Implemented in `analysis/quality.py`

- [x] 5% threshold tolerance (121.6 kbps acceptable)
<<<<<<< HEAD
- [x] 10% deficit threshold for guaranteed flagging
- [x] Minimum 16 kbps upgrade delta
- [x] Priority levels: plus, high, medium, low, met
- [x] Phase 8 re-evaluation after enrichment
- [x] Special handling for USAC-encoded local files (NOT flagged)
- [x] Don't suggest upgrades for USAC files unless Atmos available
- [x] Add `effective_bitrate_kbps` to upgrade calculations

### Phase 4: Report Enhancements ✅ (Complete)

**Status:** Implemented in templates

- [x] Show codec tier badge (ATMOS, USAC, AAC, MP3) - `codec_tier_badge` macro
- [x] Show effective quality vs raw bitrate for USAC - `effective_bitrate` macro
- [x] Add tooltip explaining why book isn't upgrade candidate - `upgrade_reason_badge` macro
- [x] Filter upgrade list by priority/codec type - Filter tabs in upgrades section
=======
- [x] Minimum 16 kbps upgrade delta
- [x] Priority levels: plus, high, medium, low, met
- [x] Phase 8 re-evaluation after enrichment

**Enhancements Needed:**
- [ ] Special handling for USAC-encoded local files
- [ ] Don't suggest upgrades for USAC files unless Atmos available
- [ ] Add `effective_quality` to upgrade calculations

### Phase 4: Report Enhancements 🔲 (Todo)

**Changes Needed:**
- [ ] Show codec tier badge (ATMOS, USAC, AAC, MP3)
- [ ] Show effective quality vs raw bitrate for USAC
- [ ] Add tooltip explaining why book isn't upgrade candidate
- [ ] Filter upgrade list by codec type
>>>>>>> d107b4b (feat: Remove obsolete scraper output and enhance upgrade card functionality)

---

## Data Model Enhancements

### Book Model Additions

```python
@dataclass
class Book:
    # Existing fields...
    
    # New fields
    codec_tier: str | None = None  # 'ATMOS', 'USAC', 'AAC', 'MP3'
    effective_quality_kbps: float | None = None  # Quality-adjusted bitrate
    api_quality_reliable: bool = True  # False if USAC/Atmos detected
    upgrade_notes: str | None = None  # Explanation for user
```

### Codec Tier Enum

```python
class CodecTier(Enum):
    ATMOS = "atmos"      # E-AC-3 Dolby Atmos - Premium
    USAC = "usac"        # xHE-AAC/USAC - Efficient
    AAC_HIGH = "aac_hq"  # AAC-LC >= 128kbps
    AAC_LOW = "aac_lq"   # AAC-LC < 128kbps  
    MP3 = "mp3"          # Legacy
    UNKNOWN = "unknown"
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
        has_dolby_atmos=True  # From API
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
    assert 'USAC' in result.reason or 'quality' in result.reason
```

### Test 3: Near-Threshold AAC (125.6 kbps)

```python
def test_near_threshold_not_candidate():
    """125.6 kbps is within 5% tolerance - NOT upgrade candidate."""
    book = Book(
        asin='B0EXAMPLE',
        codec='AAC',
        bitrate_kbps=125.6,
        best_available_kbps=128  # Only +2.4 kbps available
    )
    
    result = is_upgrade_candidate(book)
    
    assert result.is_candidate == False
    assert result.priority == 'met'
```

### Test 4: Low Bitrate with USAC Available (Unknown)

```python
def test_low_bitrate_usac_unknown():
    """64 kbps AAC but USAC might be available (API doesn't tell us)."""
    book = Book(
        asin='B0DJPYFJ2K',  # Providence
        codec='AAC',
        bitrate_kbps=64,
        api_best_bitrate=64  # API doesn't know about USAC!
    )
    
    result = is_upgrade_candidate(book)
    
    # This is tricky - API says no upgrade but USAC exists
    # We SHOULD flag it but note the uncertainty
    assert result.is_candidate == True
    assert result.priority in ['high', 'medium']
    # Could add: result.notes = 'Re-download may provide better codec'
```

---

## Future Considerations

### Widevine Integration

If we ever get access to ContentReference data:

```python
def get_true_quality_widevine(content_ref: dict) -> TrueQuality:
    """Parse ContentReference for true quality info."""
    codec = content_ref.get('codec', '')
    content_format = content_ref.get('content_format', '')
    
    if codec == 'ec+3' or content_format == 'M4A_EC3':
        return TrueQuality(tier='ATMOS', bitrate=768)
    
    if codec == 'mp4a.40.42' or content_format == 'M4A_XHE':
        return TrueQuality(tier='USAC', bitrate=128)
    
    # Standard AAC
    return TrueQuality(tier='AAC', bitrate=None)
```

### Recommendation Engine

```python
def get_upgrade_recommendation(book: Book) -> Recommendation:
    """Smart recommendation based on all factors."""
    
    if book.codec_tier == 'ATMOS':
        return Recommendation(
            action='KEEP',
            message='Premium Dolby Atmos - Best available quality!',
            badge='🎧 ATMOS'
        )
    
    if book.codec_tier == 'USAC':
        if book.has_atmos_available:
            return Recommendation(
                action='OPTIONAL_UPGRADE',
                message='USAC quality is excellent. Atmos available for immersive experience.',
                badge='✨ USAC'
            )
        return Recommendation(
            action='KEEP',
            message='xHE-AAC provides excellent efficiency and quality.',
            badge='✨ USAC'
        )
    
    # Continue with standard logic...
```

---

## Summary

### Key Principles

1. **Trust local mediainfo over API bitrate** for quality assessment
2. **Detect premium codecs** (USAC, E-AC-3) and don't flag as upgrade candidates
3. **Use 5% threshold tolerance** to avoid noisy upgrades
4. **Require minimum 16 kbps delta** for meaningful upgrades
5. **`has_dolby_atmos` is reliable** - use it!
6. **API bitrate is unreliable** for modern codecs

### Priority Order

1. Plus Catalog items (FREE!) 
2. Legacy codecs (MP3)
3. Significantly below threshold (>20% deficit)
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
