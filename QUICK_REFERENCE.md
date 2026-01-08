# 🚀 Quick Reference Card

## 📂 Data Files Location

```bash
./tmp/abs.json          - ABS API metadata (what's currently extracted)
./tmp/abs_ffprobe.json  - Raw FFprobe data (what's available from FFmpeg)
```

## 🔑 The Missing Data

### CRITICAL: Profile Field

```json
// FFprobe has this:
"profile": "xHE-AAC"

// ABS extracts: NOTHING
```

### CRITICAL: Sample Rate

```json
// FFprobe has this:
"sample_rate": "44100"

// ABS extracts: null
```

## 🎯 Quick Investigation Commands

### View specific fields

```bash
# Sample rate from FFprobe
jq '.streams[0].sample_rate' tmp/abs_ffprobe.json

# Profile from FFprobe  
jq '.streams[0].profile' tmp/abs_ffprobe.json

# What ABS extracted (audio_files[0])
jq '.media.audio_files[0] | {sample_rate, profile, codec, bit_rate}' tmp/abs.json
```

### Run comparison

```bash
python compare_metadata.py
```

## 🔍 Files to Find in ABS Repo

Search for these in the audiobookshelf repository:

```bash
# Audio probing
find . -name "*audioProbe*" -o -name "*AudioFileScanner*"

# Stream parsing
grep -r "stream.codec_name" server/

# Sample rate mentions
grep -r "sample_rate\|sampleRate" server/
```

## 🛠️ The Fix (Pseudocode)

```javascript
// In FFprobe parsing code (likely server/utils/audioProbe.js):

// Find the audio stream parsing section
const audioStream = streams.find(s => s.codec_type === 'audio')

// ADD THESE:
audioFile.sampleRate = parseInt(audioStream.sample_rate) || null
audioFile.profile = audioStream.profile || null

// Model update needed:
// - Add sampleRate: INTEGER field
// - Add profile: STRING field
```

## 📊 Test This Audiobook

**Item ID:** `089b48d1-d3a1-4a77-b9b5-eb19ea68af0e`  
**File INO:** `-356910253284297770`  
**ASIN:** `1774248182`  
**File:** He Who Fights with Monsters vol_01.m4b

**Expected Results After Fix:**

- `sampleRate: 44100`
- `profile: "xHE-AAC"`

## 📚 Full Documentation

Read `ABS_INVESTIGATION_REPORT.md` for complete details!
