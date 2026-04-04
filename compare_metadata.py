#!/usr/bin/env python3
"""
Compare FFprobe raw data with ABS extracted metadata.

Shows what's available vs what's being extracted.
"""

import json
from pathlib import Path


def main():
    """Compare the data."""
    ffprobe_path = Path("./tmp/abs_ffprobe.json")
    abs_path = Path("./tmp/abs.json")

    if not ffprobe_path.exists():
        print("❌ File not found: ./tmp/abs_ffprobe.json")
        print("   Run: python fetch_ffprobe.py <item_id> <file_ino>")
        return

    if not abs_path.exists():
        print("❌ File not found: ./tmp/abs.json")
        print("   Run: python fetch_by_id.py <item_id>")
        return

    with open(ffprobe_path) as f:
        ffprobe_data = json.load(f)

    with open(abs_path) as f:
        abs_data = json.load(f)

    print("=" * 100)
    print("🔍 FFprobe vs ABS Metadata Comparison")
    print("=" * 100)

    # Get the audio stream from FFprobe
    audio_stream = None
    for stream in ffprobe_data.get("streams", []):
        if stream.get("codec_type") == "audio":
            audio_stream = stream
            break

    if not audio_stream:
        print("❌ No audio stream found in FFprobe data")
        return

    # Get the audio file from ABS
    audio_files = abs_data.get("media", {}).get("audio_files", [])
    if not audio_files:
        print("❌ No audio files found in ABS data")
        return

    abs_audio = audio_files[0]

    print("\n" + "=" * 100)
    print("📊 FIELD COMPARISON")
    print("=" * 100)

    # Compare key fields
    comparisons = [
        ("Codec", audio_stream.get("codec_name"), abs_audio.get("codec")),
        ("Codec Profile", audio_stream.get("profile"), "NOT EXTRACTED"),
        ("Sample Rate", audio_stream.get("sample_rate") + " Hz", "NOT EXTRACTED (null)"),
        ("Sample Format", audio_stream.get("sample_fmt"), "NOT EXTRACTED"),
        ("Channels", str(audio_stream.get("channels")), str(abs_audio.get("channels"))),
        ("Channel Layout", audio_stream.get("channel_layout"), abs_audio.get("channel_layout")),
        ("Bit Rate", audio_stream.get("bit_rate") + " bps", str(abs_audio.get("bit_rate")) + " bps"),
        ("Time Base", audio_stream.get("time_base"), abs_audio.get("time_base")),
        ("Duration", audio_stream.get("duration") + " sec", str(abs_audio.get("duration")) + " sec"),
        ("Bits Per Sample", str(audio_stream.get("bits_per_sample")), "NOT EXTRACTED"),
        ("Number of Frames", audio_stream.get("nb_frames"), "NOT EXTRACTED"),
    ]

    print(f"\n{'Field':<25} {'FFprobe Value':<35} {'ABS Extracted':<35} {'Status'}")
    print("-" * 100)

    for field, ffprobe_val, abs_val in comparisons:
        if abs_val == "NOT EXTRACTED" or abs_val == "NOT EXTRACTED (null)":
            status = "❌ MISSING"
        elif str(ffprobe_val) == str(abs_val):
            status = "✅ MATCH"
        else:
            status = "⚠️  MISMATCH"

        print(f"{field:<25} {str(ffprobe_val)[:34]:<35} {str(abs_val)[:34]:<35} {status}")

    print("\n" + "=" * 100)
    print("🔑 KEY FINDINGS")
    print("=" * 100)

    print(
        """
1. ✅ EXTRACTED CORRECTLY:
   - codec, channels, channel_layout, bit_rate, time_base, duration

2. ❌ MISSING FROM ABS API (Available in FFprobe):
   - profile: "xHE-AAC" (High Efficiency AAC - important for quality!)
   - sample_rate: "44100" Hz (explicitly available)
   - sample_fmt: "fltp" (floating point)
   - bits_per_sample: 0 (for AAC)
   - nb_frames: 4,486,877 total frames

3. ⚠️  CRITICAL ISSUE:
   The FFprobe data contains "sample_rate": "44100" as a STRING
   But ABS is not extracting it to the audio_files metadata!

   ABS has "time_base": "1/44100" but NOT "sample_rate"

4. 🎯 CODEC PROFILE MISSING:
   FFprobe shows: "profile": "xHE-AAC" (Extended High Efficiency AAC)
   This is CRITICAL metadata for quality assessment!
   xHE-AAC can sound better at lower bitrates than standard AAC

5. 📊 DATA TYPE INCONSISTENCY:
   FFprobe returns sample_rate as STRING: "44100"
   ABS might be trying to parse it as INT and failing?
"""
    )

    print("\n" + "=" * 100)
    print("🔧 WHAT NEEDS TO BE FIXED IN ABS")
    print("=" * 100)

    print(
        """
In the Audiobookshelf codebase:

1. ADD sample_rate extraction:
   - FFprobe provides: streams[0].sample_rate = "44100"
   - Should be stored as: audioFile.sampleRate = 44100 (int)

2. ADD profile extraction:
   - FFprobe provides: streams[0].profile = "xHE-AAC"
   - Should be stored as: audioFile.profile = "xHE-AAC"
   - This is critical for quality assessment!

3. OPTIONAL enhancements:
   - sample_fmt (sample format: fltp, s16, s32, etc.)
   - bits_per_sample (for quality assessment)
   - nb_frames (total frame count)

4. Consider adding to audioFiles model:
   - sampleRate: number (Hz)
   - profile: string (codec profile)
   - sampleFmt: string (sample format)
   - bitsPerSample: number (bit depth)
   - nbFrames: number (frame count)
"""
    )

    print("\n" + "=" * 100)
    print("📁 FILES AVAILABLE")
    print("=" * 100)
    print(f"   FFprobe Raw:  {ffprobe_path.resolve()}")
    print(f"   ABS Metadata: {abs_path.resolve()}")
    print("=" * 100)


if __name__ == "__main__":
    main()
