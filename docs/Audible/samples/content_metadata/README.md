# Audible Content Metadata Endpoint

## Endpoint

```bash
GET /1.0/content/{asin}/metadata
```

### Query Parameters

| Parameter | Type | Values | Description |
| ----------- | ------ | -------- | -------------  |
| `response_groups` | string | `chapter_info,content_reference,content_url,always-returned` | Data groups to include |
| `quality` | string | `High`, `Normal` | Audio quality preference |
| `drm_type` | string | `Widevine`, `Adrm`, `FairPlay`, `Hls`, `Dash`, `HlsCmaf` | DRM/codec selection |
| `chapter_titles_type` | string | `Tree`, `Flat` | Chapter structure format |
| `acr` | string | Audio Content Reference | (optional) |

**Note**: `PlayReady` and `Mpeg` drm_types return 404 errors.

---

## Comprehensive DRM Type Analysis

### B0F154ZCSN - Harry Potter Full-Cast (9.6 hours) - HAS ATMOS

| drm_type | codec | format | bitrate | size | notes |
| ---------- | ------- | -------- | --------- | ------ | ------- |
| **Widevine** | `ac-4` | M4A_AC4 | **325.7 kbps** | 1344.7 MB | 🎧 **DOLBY ATMOS** |
| Widevine (Normal) | `ac-4` | M4A_AC4 | 101.7 kbps | 420.0 MB | Atmos @ lower quality |
| **FairPlay** | `ec+3` | M4A_EC3 | **769.0 kbps** | 3174.4 MB | 🎵 **DOLBY DIGITAL PLUS** |
| Dash | `mp4a.40.42` | M4A_XHE | 133.2 kbps | 550.0 MB | HE-AAC v2 |
| HlsCmaf | `mp4a.40.42` | M4A_XHE | 133.2 kbps | 550.0 MB | HE-AAC v2 |
| Adrm | `mp4a.40.2` | AAX_44_128 | 128.9 kbps | 532.0 MB | Standard AAC |
| Hls | `mp4a.40.2` | M4A_AAX_44 | 128.0 kbps | 528.4 MB | Standard AAC |
| none | `mp4a.40.2` | M4A_AAX_44 | 128.0 kbps | 528.4 MB | Default |

### 1774248182 - He Who Fights with Monsters (28.9 hours) - NO ATMOS

| drm_type | codec | format | bitrate | size | notes |
| ---------- | ------- | -------- | --------- | ------ | ------- |
| **Widevine** | `mp4a.40.42` | M4A_XHE | **128.2 kbps** | 1592.7 MB | Best available |
| Widevine (Normal) | `mp4a.40.42` | M4A_XHE | 28.7 kbps | 356.8 MB | Low quality |
| FairPlay | `mp4a.40.42` | M4A_XHE | 122.4 kbps | 1520.3 MB | HE-AAC v2 |
| Dash | `mp4a.40.42` | M4A_XHE | 122.3 kbps | 1518.6 MB | HE-AAC v2 |
| HlsCmaf | `mp4a.40.42` | M4A_XHE | 122.3 kbps | 1518.6 MB | HE-AAC v2 |
| Adrm | `mp4a.40.2` | AAX_22_64 | 64.7 kbps | 803.4 MB | Low quality AAC |
| Hls | `mp4a.40.2` | M4A_AAX_22 | 64.0 kbps | 794.9 MB | Low quality AAC |
| none | `mp4a.40.2` | M4A_AAX_22 | 64.0 kbps | 794.9 MB | Default |

---

## Key Findings

### DRM Type Priority for Quality Discovery

1. **Widevine** - Returns best available: Atmos (ac-4) if available, otherwise HE-AAC v2
2. **FairPlay** - Returns Dolby Digital Plus (ec+3) for Atmos titles, HE-AAC v2 for others  
3. **Dash/HlsCmaf** - Returns HE-AAC v2 (similar quality to Widevine for non-Atmos)
4. **Adrm** - Returns legacy AAX format (lower quality)
5. **Hls/none** - Returns standard AAC (M4A_AAX format)

### Quality Parameter Impact

- `quality=High` returns full bitrate version
- `quality=Normal` returns significantly lower bitrate (useful for previews)

### Codec Hierarchy (Best to Lowest)

| Codec | Name | Typical Bitrate | Description |
| ------- | ------ | ----------------- | ------------- |
| `ec+3` | Dolby Digital Plus | 700-800 kbps | Highest quality spatial audio |
| `ac-4` | Dolby AC-4 (Atmos) | 300-350 kbps | Immersive object-based audio |
| `mp4a.40.42` | HE-AAC v2 / xHE-AAC | 110-130 kbps | High efficiency, good quality |
| `mp4a.40.2` | AAC-LC | 64-128 kbps | Standard (varies by content) |

---

## Response Schema

### Wrapper Structure (when drm_type specified)

```json
{
  "content_metadata": {
    "chapter_info": { ... },
    "content_reference": { ... }
  },
  "response_groups": ["chapter_info", "content_reference"]
}
```

### `chapter_info` Object

```json
{
  "brandIntroDurationMs": 3924,
  "brandOutroDurationMs": 4945,
  "is_accurate": true,
  "runtime_length_ms": 104106044,
  "runtime_length_sec": 104106,
  "chapters": [
    {
      "length_ms": 19765,
      "start_offset_ms": 0,
      "start_offset_sec": 0,
      "title": "Opening Credits"
    }
  ]
}
```

### `content_reference` Object

```json
{
  "acr": "CR!ABC123...",
  "asin": "1774248182",
  "codec": "mp4a.40.42",
  "content_format": "M4A_XHE",
  "content_size_in_bytes": 1670110291,
  "file_version": "1",
  "marketplace": "AF2M0KC94RCEA",
  "sku": "BK_AKOU_038971",
  "tempo": "1.0",
  "version": "104375279"
}
```

---

## Codec Reference

| Codec ID | Name | Description |
| ---------- | ------ | ------------- |
| `mp4a.40.2` | AAC-LC | Standard AAC Low Complexity |
| `mp4a.40.42` | HE-AAC v2 / xHE-AAC / USAC | High Efficiency AAC (Widevine) |
| `ec+3` | Dolby Digital Plus | Enhanced AC-3 spatial audio |
| `ac-4` | Dolby AC-4 | Dolby Atmos / Immersive audio |

## Content Format Reference

| Format | Codec | Sample Rate | Typical Bitrate |
| -------- | ------- | ------------- | ----------------- |
| `M4A_AC4` | ac-4 | 48kHz | 300-350 kbps |
| `M4A_XHE` | mp4a.40.42 | 44.1kHz | 110-130 kbps |
| `AAX_44_128` | mp4a.40.2 | 44.1kHz | ~128 kbps |
| `AAX_22_64` | mp4a.40.2 | 22.05kHz | ~64 kbps |
| `M4A_AAX_44` | mp4a.40.2 | 44.1kHz | ~128 kbps |
| `M4A_AAX_22` | mp4a.40.2 | 22.05kHz | ~64 kbps |

---

## Bitrate Calculation

```python
bitrate_kbps = (content_size_in_bytes * 8) / (runtime_length_ms / 1000) / 1000
```

---

## Sample Comparisons

### B0F154ZCSN - Harry Potter Full-Cast (Dolby Atmos)

| drm_type | Codec | Format | Bitrate | Size | Duration |
| ---------- | ------- | -------- | --------- | ------ | ---------- |
| Widevine | ac-4 | M4A_AC4 | **325.7 kbps** | 1344.7 MB | 9.6 hrs |
| Adrm | mp4a.40.2 | AAX_44_128 | 128.9 kbps | 532.0 MB | 9.6 hrs |
| default | mp4a.40.2 | M4A_AAX_44 | 128.0 kbps | 528.4 MB | 9.6 hrs |

### 1774248182 - He Who Fights with Monsters (HE-AAC)

| drm_type | Codec | Format | Bitrate | Size | Duration |
| ---------- | ------- | -------- | --------- | ------ | ---------- |
| Widevine | mp4a.40.42 | M4A_XHE | **128.2 kbps** | 1592.7 MB | 28.9 hrs |
| Adrm | mp4a.40.2 | AAX_22_64 | 64.7 kbps | 803.4 MB | 28.9 hrs |
| default | mp4a.40.2 | M4A_AAX_22 | 64.0 kbps | 794.9 MB | 28.9 hrs |

---

## Usage Notes

1. **Always request `drm_type=Widevine`** for quality discovery - it returns the best available format
2. **Atmos titles** return `ac-4` codec with 300+ kbps bitrate
3. **Non-Atmos titles** return `mp4a.40.42` (HE-AAC v2) with ~110-130 kbps via Widevine
4. **Adrm** returns legacy AAX format (usually lower quality than Widevine)
5. **Response wrapper**: When `drm_type` is specified, data is nested under `content_metadata`
6. **FairPlay** returns highest quality for Atmos titles (Dolby Digital Plus @ 769 kbps!)

---

## Raw Samples

Complete raw API responses are saved in the `raw/` subdirectory:

```text
raw/
├── B0F154ZCSN_drm_Widevine_all_groups.json     # Atmos (ac-4) @ 325 kbps
├── B0F154ZCSN_drm_FairPlay_all_groups.json     # DD+ (ec+3) @ 769 kbps  
├── B0F154ZCSN_drm_Dash_all_groups.json         # HE-AAC v2 @ 133 kbps
├── B0F154ZCSN_drm_HlsCmaf_all_groups.json      # HE-AAC v2 @ 133 kbps
├── B0F154ZCSN_drm_Adrm_all_groups.json         # AAC-LC @ 128 kbps
├── B0F154ZCSN_drm_Hls_all_groups.json          # AAC-LC @ 128 kbps
├── B0F154ZCSN_drm_none_all_groups.json         # Default AAC-LC
├── B0F154ZCSN_drm_Widevine_quality_Normal.json # Atmos @ lower quality
├── 1774248182_drm_Widevine_all_groups.json     # HE-AAC v2 @ 128 kbps
├── 1774248182_drm_FairPlay_all_groups.json     # HE-AAC v2 @ 122 kbps
├── 1774248182_drm_Dash_all_groups.json         # HE-AAC v2 @ 122 kbps
├── 1774248182_drm_HlsCmaf_all_groups.json      # HE-AAC v2 @ 122 kbps
├── 1774248182_drm_Adrm_all_groups.json         # AAC-LC @ 64 kbps
├── 1774248182_drm_Hls_all_groups.json          # AAC-LC @ 64 kbps
├── 1774248182_drm_none_all_groups.json         # Default AAC-LC
└── 1774248182_drm_Widevine_quality_Normal.json # HE-AAC v2 @ low quality
```

### Failed DRM Types

These drm_types return 404 errors and are not available:

- `PlayReady`
- `Mpeg`

---

## Directory Structure

This directory contains two sets of samples:

### `raw/` subdirectory
- **Purpose:** Reference for comprehensive DRM testing (what formats exist)
- **Coverage:** 2 ASINs × 8 DRM variants each (16 files)
- **Use case:** Understanding all possible codec/DRM combinations

### Root directory
- **Purpose:** Curated examples with pricing context (monthly deals, Plus Catalog)
- **Coverage:** 4 ASINs × 2-3 DRM variants each (10 files)
- **Use case:** Demonstrating pricing edge cases and common formats

**Note:** The 8 files that exist in both locations are identical data. However, they serve different documentation purposes:
- `raw/` files document technical DRM capabilities
- Root files provide context for pricing analysis (monthly sales, Plus Catalog)

Both directories should be retained as they serve complementary documentation goals.

---

## Source

- Discovered via [Libation PR #1527](https://github.com/rmcrackan/Libation/pull/1527)
- Endpoint documented in upstream audible-api docs: `misc_external_api.rst` (lines 449-457)
- Samples collected: 2026-01-02
