# 🎯 ABS FFprobe Metadata Investigation - Complete Report

**Date:** January 2, 2026  
**Audiobook:** He Who Fights with Monsters Vol 01 (ASIN: 1774248182)  
**File:** He Who Fights with Monsters A LitRPG Adventure vol_01.m4b

---

## ✅ Data Successfully Extracted

### 📂 Files Created

1. **`./tmp/abs.json`** (43 KB, 1595 lines)
   - Complete ABS API response for library item
   - Shows what metadata ABS is currently extracting

2. **`./tmp/abs_ffprobe.json`** (34 KB, 1455 lines)
   - Raw FFprobe output from ABS internal endpoint
   - Shows ALL metadata available from FFmpeg

### 🔗 Endpoints Used

- **ABS Item Metadata:**  
  `GET /api/items/{itemId}?expanded=1`

- **FFprobe Raw Data:**  
  `GET /api/items/{itemId}/ffprobe/{fileIno}`

---

## 🔍 Key Findings: Missing Metadata

### ❌ Critical Missing Fields

| Field | FFprobe Value | ABS Extracted | Impact |
| ------- | -------------- | --------------- | --------- |
| **sample_rate** | `"44100"` | `null` | ⚠️ HIGH - Basic audio property |
| **profile** | `"xHE-AAC"` | Not extracted | 🔥 CRITICAL - Quality assessment |
| **sample_fmt** | `"fltp"` | Not extracted | Low - Nice to have |
| **bits_per_sample** | `0` | Not extracted | Low - Quality info |
| **nb_frames** | `"4486877"` | Not extracted | Low - Frame count |

### 🎯 The Big Discovery: xHE-AAC Profile

**This is HUGE for your PR!**

The audiobook uses **xHE-AAC** (Extended High Efficiency AAC), which is:

- A modern audio codec designed for lower bitrates
- Can sound significantly better than standard AAC at the same bitrate
- Critical information for quality assessment tools
- **Currently NOT being extracted by ABS!**

At 118 kbps with xHE-AAC, this file likely sounds as good as or better than standard AAC at 192+ kbps.

---

## 📊 Complete FFprobe Audio Stream Data

```json
{
  "index": 0,
  "codec_name": "aac",
  "codec_long_name": "AAC (Advanced Audio Coding)",
  "profile": "xHE-AAC",              ← NOT EXTRACTED
  "codec_type": "audio",
  "codec_tag_string": "mp4a",
  "codec_tag": "0x6134706d",
  "sample_fmt": "fltp",               ← NOT EXTRACTED
  "sample_rate": "44100",             ← NOT EXTRACTED (available but ignored!)
  "channels": 2,                      ← ✅ Extracted
  "channel_layout": "stereo",         ← ✅ Extracted
  "bits_per_sample": 0,               ← NOT EXTRACTED
  "time_base": "1/44100",             ← ✅ Extracted
  "duration": "104183.760862",        ← ✅ Extracted
  "bit_rate": "118653",               ← ✅ Extracted
  "nb_frames": "4486877",             ← NOT EXTRACTED
  "sample_fmt": "fltp"                ← NOT EXTRACTED
}
```

---

## 🐛 Root Cause Analysis

### Why is sample_rate NULL?

1. **FFprobe returns it as a STRING:** `"44100"` (not an integer)
2. **ABS parser might be:**
   - Expecting an integer and failing to parse
   - Not mapping this field at all in the code
   - Silently failing on type conversion

### Why is profile missing?

The `profile` field provides critical codec variant information:

- `"LC"` = Low Complexity AAC (standard)
- `"HE-AAC"` = High Efficiency AAC v1
- `"xHE-AAC"` = Extended High Efficiency AAC (modern, best quality at low bitrate)

This is likely not mapped in the ABS audio file model.

---

## 🔧 Fix Recommendations for ABS PR

### 1. Add sample_rate Field

**Location:** Audio file parsing code (likely in `server/utils/audioProbe.js` or similar)

**Change:**

```javascript
// BEFORE: sample_rate not extracted

// AFTER: Parse sample_rate from FFprobe
audioFile.sampleRate = parseInt(stream.sample_rate) || null
```

**Model Update:**

```javascript
// AudioFile model needs new field
sampleRate: {
  type: DataTypes.INTEGER,
  allowNull: true
}
```

### 2. Add profile Field (CRITICAL!)

**Change:**

```javascript
// Extract codec profile
audioFile.profile = stream.profile || null
```

**Model Update:**

```javascript
profile: {
  type: DataTypes.STRING,
  allowNull: true
}
```

### 3. Optional Enhancements

```javascript
audioFile.sampleFmt = stream.sample_fmt || null
audioFile.bitsPerSample = stream.bits_per_sample || null
audioFile.nbFrames = stream.nb_frames || null
```

---

## 🎬 Testing Your Changes

### Test Case 1: Sample Rate Extraction

**Input:** FFprobe stream with `"sample_rate": "44100"`  
**Expected Output:** `audioFile.sampleRate = 44100`

### Test Case 2: Profile Detection

**Input:** FFprobe stream with `"profile": "xHE-AAC"`  
**Expected Output:** `audioFile.profile = "xHE-AAC"`

### Test Case 3: Type Conversion

**Input:** Various sample rates as strings: `"44100"`, `"48000"`, `"22050"`  
**Expected Output:** Correctly parsed integers

---

## 📚 Files to Investigate in ABS Repository

1. **Audio Probing:**
   - `server/utils/audioProbe.js` - FFprobe execution and parsing
   - `server/managers/AudioFileScanner.js` - Audio file scanning
   - `server/scanner/AudioFileScanner.js` - Alternative scanner location

2. **Models:**
   - `server/models/AudioFile.js` - Audio file data model
   - `server/models/Book.js` - Book/media model
   - Database migrations for adding new fields

3. **API Routes:**
   - `server/routers/ApiRouter.js` - API endpoint definitions
   - Check `/api/items/:id/ffprobe/:ino` implementation

---

## 🔬 Investigation Commands for Your Codespace

Once you're in the ABS repository:

```bash
# Find audio probing code
grep -r "sample_rate\|sampleRate" server/

# Find FFprobe execution
grep -r "ffprobe" server/

# Find audio file models
find server/ -name "*Audio*" -o -name "*audio*"

# Search for stream parsing
grep -r "stream.codec_name\|streams\[" server/
```

---

## 📋 PR Checklist

- [ ] Add `sampleRate` field to AudioFile model
- [ ] Add `profile` field to AudioFile model  
- [ ] Update FFprobe parsing to extract these fields
- [ ] Add database migration for new fields
- [ ] Update API documentation
- [ ] Add tests for new fields
- [ ] Test with various audio formats (AAC, MP3, FLAC, etc.)
- [ ] Test with various codecs (LC-AAC, HE-AAC, xHE-AAC)
- [ ] Verify backward compatibility

---

## 🎯 The Smoking Gun

**Before:** ABS shows `time_base: "1/44100"` but `sample_rate: null`  
**After:** FFprobe clearly shows `sample_rate: "44100"` is available  
**Conclusion:** The data exists, ABS just isn't extracting it!

Same story for `profile: "xHE-AAC"` - it's RIGHT THERE in the FFprobe output, but ABS ignores it.

---

## 📊 Impact Assessment

### High Priority (Fix Immediately)

- ✅ `sample_rate` - Basic audio property, should always be available
- ✅ `profile` - Critical for quality assessment and modern codec support

### Medium Priority (Nice to Have)

- `sample_fmt` - Useful for technical analysis
- `bits_per_sample` - Helpful for quality metrics

### Low Priority (Future Enhancement)

- `nb_frames` - Frame count, rarely needed

---

## 🚀 Next Steps

1. **Clone the ABS repository** in your Codespace
2. **Search for audio parsing code** using the commands above
3. **Identify the FFprobe parsing function** that processes streams
4. **Add the missing field extractions** (sample_rate, profile)
5. **Update the database model** to include new fields
6. **Test with this audiobook** (you have the exact data!)
7. **Create PR** with before/after comparisons

---

## 📁 Reference Files

All raw data is available in `./tmp/`:

- **abs.json** - Current ABS metadata extraction
- **abs_ffprobe.json** - Complete FFprobe output
- Use `jq` to query: `jq '.streams[0].sample_rate' tmp/abs_ffprobe.json`

---

## 💡 Pro Tips

1. **Test with multiple files** - Not all files use xHE-AAC
2. **Check for edge cases** - What if sample_rate is missing?
3. **Consider backward compatibility** - Existing DB might not have these fields
4. **Add validation** - Ensure sample_rate is a valid number (> 0)

---

## 🎉 You Have Everything You Need

✅ Raw FFprobe data showing what's available  
✅ ABS metadata showing what's currently extracted  
✅ Exact comparison showing what's missing  
✅ The problematic audiobook file to test against  
✅ API endpoint to verify your changes  

Good luck with your PR! This is a valuable contribution that will help users accurately assess audio quality, especially for modern codecs like xHE-AAC! 🚀
