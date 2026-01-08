# ABS Metadata Extraction Guide

## ✅ Completed

You now have the **complete raw FFmpeg metadata dump** for the audiobook saved in:

```bash
./tmp/abs.json
```

**Audiobook Details:**

- **Title:** He Who Fights with Monsters: A LitRPG Adventure (Vol 01)
- **ASIN:** 1774248182
- **File:** He Who Fights with Monsters A LitRPG Adventure vol_01 (2021) (Shirtaloon) {ASIN.1774248182}.m4b
- **Size:** 1.46 GB
- **Duration:** 28.94 hours (104,183 seconds)
- **Narrator:** Heath Miller

## 🔧 FFmpeg Metadata Extracted

The API is returning the following FFmpeg metadata:

### Audio Codec Information

```json
{
  "format": "QuickTime / MOV",
  "codec": "aac",
  "bitrate": 118653,           // 118 kbps
  "channels": 2,
  "channel_layout": "stereo",
  "time_base": "1/44100",
  "mime_type": "audio/mp4"
}
```

### Important Discovery: Missing Field

⚠️ **`sample_rate` is NOT being extracted!**

The FFmpeg metadata includes:

- `time_base`: "1/44100" (which implies 44100 Hz sample rate)
- BUT the parsed `sample_rate` field is `null`

This suggests the ABS API is:

1. **Detecting the time_base correctly** (1/44100)
2. **NOT converting/storing the sample_rate** as a separate field

### Embedded Metadata Tags

```json
{
  "tag_album": "He Who Fights with Monsters: A LitRPG Adventure: He Who Fights with Monsters, Book 1",
  "tag_artist": "Shirtaloon; Travis Deverell",
  "tag_genre": "Action & Adventure, Epic, Urban",
  "tag_title": "He Who Fights with Monsters: A LitRPG Adventure",
  "tag_album_artist": "Shirtaloon; Travis Deverell",
  "tag_composer": "Heath Miller",
  "tag_date": "2021",
  "tag_encoder": null,
  "tag_track": null
}
```

### Cover Art

- **Embedded Cover:** `"mjpeg"` ✅ (detected)

### Chapters

- **Total Chapters:** 115
- **Chapter Data:** All chapter metadata is extracted with start/end times and titles

## 📊 The Issue: Missing Data

Looking at the FFmpeg output, the ABS API **IS extracting** most metadata but:

### What's Being Extracted ✅

- Format, Codec, Bitrate
- Channel information
- Duration
- Language
- Time base
- Embedded metadata tags
- Chapters with titles/timestamps

### What's Missing or Could Be Enhanced ❌

1. **Sample Rate** - The `time_base` shows "1/44100" but `sample_rate` field is null
2. **Possible missing fields from FFmpeg:**
   - Audio bit depth (16-bit, 24-bit, 32-bit)
   - Frame size
   - Compression level
   - Other codec-specific parameters

## 🔍 Next Steps for Audiobookshelf PR

Based on this raw metadata, here's what you should investigate in the ABS codebase:

### 1. Find the FFmpeg Metadata Parsing Code

Look for the audio file parsing in Audiobookshelf:

```bash
- Usually in: src/scanner or src/providers/metadata
- Search for: ffprobe, mediainfo, getMetadata
- Look for: AudioFile model/parsing
```

### 2. Check the Sample Rate Extraction

```bash
# Search for sample_rate handling
grep -r "sampleRate\|sample_rate" src/
grep -r "timeBase\|time_base" src/
```

### 3. Add Missing Fields

The `sample_rate` should be extracted from:

- `time_base` (calculate 1/timebase)
- FFmpeg's `sample_rate` field directly (if available)
- Audio stream configuration

### 4. Test Your Changes

Create a test using this metadata:

```json
{
  "asin": "1774248182",
  "time_base": "1/44100",
  "expected_sample_rate": 44100
}
```

## 📝 Files Created for You

1. **`fetch_raw_metadata.py`** - Interactive search and fetch script
2. **`fetch_by_id.py`** - Direct fetch by item ID
3. **`list_library_items.py`** - Browse all library items
4. **`show_metadata.py`** - Pretty print the metadata
5. **`tmp/abs.json`** - The complete raw metadata dump (1595 lines)

## 🚀 Usage Examples

### Search and fetch interactively

```bash
python fetch_raw_metadata.py "He Who Fights with Monsters"
```

### Fetch directly by ID

```bash
python fetch_by_id.py 089b48d1-d3a1-4a77-b9b5-eb19ea68af0e
```

### List all library items with search

```bash
python list_library_items.py
```

### View the formatted metadata

```bash
python show_metadata.py
```

### Query specific fields from JSON

```bash
# Get audio codec info
jq '.media.audio_files[0] | {codec, bitrate: .bit_rate, channels}' tmp/abs.json

# Get embedded metadata tags
jq '.media.audio_files[0].meta_tags' tmp/abs.json

# Get all chapters
jq '.media.audio_files[0].chapters' tmp/abs.json
```

## 🔗 Environment Configuration

Your `.env` is already set up with:

- ✅ ABS_HOST: <https://audiobookshelf.kingpaging.com>
- ✅ ABS_API_KEY: (configured)
- ✅ ABS_LIBRARY_ID: d00f643c-7973-42dd-9139-2708e68e0b4e

This allows the scripts to authenticate and fetch data directly.

## 💡 PR Investigation Notes

When you look at the ABS source code, pay attention to:

1. **FFmpeg command execution** - How are probes being run?
2. **Response parsing** - How is the JSON parsed from FFmpeg?
3. **Field mapping** - Which FFmpeg fields are being mapped to which model fields?
4. **Version compatibility** - Are there version-specific FFmpeg output formats?

The fact that `time_base` is being extracted but not `sample_rate` suggests the parsing is selective - investigate why certain fields are skipped.

Good luck with your PR! 🎉
