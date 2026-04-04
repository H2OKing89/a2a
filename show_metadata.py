#!/usr/bin/env python3
"""
Display comprehensive FFmpeg metadata from abs.json
"""

import json
from pathlib import Path


def main():
    """Load and display metadata."""
    json_path = Path("./tmp/abs.json")

    if not json_path.exists():
        print("❌ File not found: ./tmp/abs.json")
        print("   Run: python fetch_by_id.py <item_id>")
        return

    with open(json_path) as f:
        data = json.load(f)

    # Extract main info
    metadata = data.get("media", {}).get("metadata", {})
    audio_files = data.get("media", {}).get("audio_files", [])

    print("=" * 80)
    print("📖 BOOK METADATA")
    print("=" * 80)
    print(f"Title:        {metadata.get('title')}")
    print(f"Authors:      {', '.join([a.get('name') for a in metadata.get('authors', [])])}")
    print(f"Narrators:    {', '.join(metadata.get('narrators', []))}")
    print(f"Publisher:    {metadata.get('publisher')}")
    print(f"Published:    {metadata.get('published_year')}")
    print(
        f"Series:       {', '.join([s.get('name') + ' #' + (s.get('sequence') or '?') for s in metadata.get('series', [])])}"
    )
    print(f"ASIN:         {metadata.get('asin')}")
    print(f"ISBN:         {metadata.get('isbn')}")
    print(f"Duration:     {data.get('media', {}).get('duration', 0) / 3600:.2f} hours")
    print(f"Total Size:   {data.get('size', 0) / (1024**3):.2f} GB")

    print("\n" + "=" * 80)
    print(f"🎵 AUDIO FILES ({len(audio_files)} file{'s' if len(audio_files) != 1 else ''})")
    print("=" * 80)

    for i, audio_file in enumerate(audio_files, 1):
        file_meta = audio_file.get("metadata", {})
        print(f"\n📁 File {i}: {file_meta.get('filename')}")
        print(f"   Size: {file_meta.get('size', 0) / (1024**3):.2f} GB")
        print(f"   Path: {file_meta.get('rel_path')}")

        print(f"\n🔧 FFmpeg Metadata:")
        print(f"   Format:           {audio_file.get('format')}")
        print(f"   Codec:            {audio_file.get('codec')}")
        print(f"   Bitrate:          {audio_file.get('bit_rate')} bps ({audio_file.get('bit_rate', 0) // 1000} kbps)")
        print(f"   Channels:         {audio_file.get('channels')}")
        print(f"   Channel Layout:   {audio_file.get('channel_layout')}")
        print(f"   Time Base:        {audio_file.get('time_base')}")
        print(f"   Language:         {audio_file.get('language')}")
        print(f"   Duration:         {audio_file.get('duration', 0) / 3600:.2f} hours")
        print(f"   MIME Type:        {audio_file.get('mime_type')}")
        print(f"   Embedded Cover:   {audio_file.get('embedded_cover_art')}")
        print(f"   Sample Rate:      {audio_file.get('sample_rate', 'Not detected')}")

        # Embedded meta tags
        meta_tags = audio_file.get("meta_tags", {})
        if meta_tags and any(meta_tags.values()):
            print(f"\n📝 Embedded Metadata Tags:")
            for tag_key, tag_val in meta_tags.items():
                if tag_val:
                    # Remove 'tag_' prefix for display
                    display_key = tag_key.replace("tag_", "").replace("_", " ").title()
                    print(f"   {display_key}: {tag_val}")

        # Chapters
        chapters = audio_file.get("chapters", [])
        if chapters:
            print(f"\n📚 Chapters ({len(chapters)} total):")
            for j, chapter in enumerate(chapters[:5], 1):  # Show first 5
                start = chapter.get("start", 0)
                end = chapter.get("end", 0)
                duration = (end - start) / 60
                print(f"   {j}. {chapter.get('title')} ({duration:.1f} min)")
            if len(chapters) > 5:
                print(f"   ... and {len(chapters) - 5} more")

    print("\n" + "=" * 80)
    print("💾 RAW JSON SAVED TO: ./tmp/abs.json")
    print("=" * 80)


if __name__ == "__main__":
    main()
