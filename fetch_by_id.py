#!/usr/bin/env python3
"""
Fetch raw metadata for a specific item ID.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.abs.client import ABSClient
from src.config import get_settings


def main():
    """Fetch and save raw metadata."""
    if len(sys.argv) < 2:
        print("Usage: python fetch_by_id.py <item_id>")
        print("\nExample:")
        print("  python fetch_by_id.py 089b48d1-d3a1-4a77-b9b5-eb19ea68af0e")
        sys.exit(1)

    item_id = sys.argv[1]

    settings = get_settings()

    if not settings.abs.host or not settings.abs.api_key:
        print("❌ ABS credentials not configured in .env")
        sys.exit(1)

    print(f"📡 Connecting to ABS: {settings.abs.host}")
    print(f"📦 Fetching item: {item_id}")

    try:
        with ABSClient(
            host=settings.abs.host,
            api_key=settings.abs.api_key,
        ) as client:
            # Fetch the full expanded item with all metadata
            item = client.get_item(item_id, expanded=True, use_cache=False)

            # Save to JSON
            output_path = Path("./tmp/abs.json")
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert to dict (handles Pydantic models)
            if hasattr(item, "model_dump"):
                data = item.model_dump()
            else:
                data = item

            with open(output_path, "w") as f:
                json.dump(data, f, indent=2, default=str)

            print(f"✅ Raw metadata saved to: {output_path.resolve()}")

            # Show metadata summary
            metadata = data.get("media", {}).get("metadata", {})
            audio_files = data.get("media", {}).get("audioFiles", [])

            print(f"\n📊 Metadata summary:")
            print(f"   Title: {metadata.get('title')}")
            print(f"   Author: {metadata.get('authorName')}")
            print(f"   ASIN: {metadata.get('asin')}")
            print(f"   Audio Files: {len(audio_files)}")
            print(f"   Total Size: {data.get('size', 0) / (1024**3):.2f} GB")
            print(f"   Duration: {data.get('media', {}).get('duration', 0) / 3600:.2f} hours")

            # Show FFmpeg metadata from first audio file
            if audio_files:
                print(f"\n🔧 FFmpeg metadata from first audio file:")
                first_file = audio_files[0]
                print(f"   Codec: {first_file.get('codec')}")
                print(f"   Bitrate: {first_file.get('bitRate')} bps ({first_file.get('bitRate', 0) // 1000} kbps)")
                print(f"   Channels: {first_file.get('channels')}")
                print(f"   Channel Layout: {first_file.get('channelLayout')}")
                print(f"   Sample Rate: {first_file.get('sampleRate', 'N/A')}")
                print(f"   Duration: {first_file.get('duration', 0) / 3600:.2f} hours")
                print(f"   MIME Type: {first_file.get('mimeType')}")
                print(f"   Time Base: {first_file.get('timeBase')}")

                # Show metadata tags if available
                meta_tags = first_file.get("metaTags")
                if meta_tags:
                    print(f"\n   Embedded Meta Tags:")
                    for key, val in meta_tags.items():
                        if val:
                            print(f"      {key}: {val}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
