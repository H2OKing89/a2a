#!/usr/bin/env python3
"""
Fetch raw FFprobe data from ABS API endpoint.

This retrieves the actual FFprobe output that ABS uses to parse metadata.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.abs.client import ABSClient
from src.config import get_settings


def main():
    """Fetch FFprobe data."""
    if len(sys.argv) < 3:
        print("Usage: python fetch_ffprobe.py <item_id> <file_ino>")
        print("\nExample:")
        print("  python fetch_ffprobe.py 089b48d1-d3a1-4a77-b9b5-eb19ea68af0e -356910253284297770")
        sys.exit(1)

    item_id = sys.argv[1]
    file_ino = sys.argv[2]

    settings = get_settings()

    if not settings.abs.host or not settings.abs.api_key:
        print("❌ ABS credentials not configured in .env")
        sys.exit(1)

    print(f"📡 Connecting to ABS: {settings.abs.host}")
    print(f"📦 Item ID: {item_id}")
    print(f"📄 File INO: {file_ino}")

    try:
        with ABSClient(
            host=settings.abs.host,
            api_key=settings.abs.api_key,
        ) as client:
            # Fetch FFprobe data using the undocumented endpoint
            endpoint = f"/items/{item_id}/ffprobe/{file_ino}"
            print(f"🔍 Fetching: {endpoint}")

            data = client._get(endpoint)

            # Save to JSON
            output_path = Path("./tmp/abs_ffprobe.json")
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                json.dump(data, f, indent=2, default=str)

            print(f"✅ Raw FFprobe data saved to: {output_path.resolve()}")

            # Show summary
            if isinstance(data, dict):
                print(f"\n📊 FFprobe Data Summary:")

                # Format info
                format_info = data.get("format", {})
                if format_info:
                    print(f"\n🎬 Format:")
                    print(f"   Format Name: {format_info.get('format_name')}")
                    print(f"   Format Long Name: {format_info.get('format_long_name')}")
                    print(f"   Duration: {float(format_info.get('duration', 0)) / 3600:.2f} hours")
                    print(f"   Size: {int(format_info.get('size', 0)) / (1024**3):.2f} GB")
                    print(f"   Bit Rate: {int(format_info.get('bit_rate', 0)) // 1000} kbps")

                    tags = format_info.get("tags", {})
                    if tags:
                        print(f"\n   Format Tags:")
                        for key, val in list(tags.items())[:10]:
                            print(f"      {key}: {val}")
                        if len(tags) > 10:
                            print(f"      ... and {len(tags) - 10} more tags")

                # Streams info
                streams = data.get("streams", [])
                if streams:
                    print(f"\n🎵 Streams ({len(streams)} total):")
                    for i, stream in enumerate(streams, 1):
                        print(f"\n   Stream {i}:")
                        print(f"      Codec Type: {stream.get('codec_type')}")
                        print(f"      Codec Name: {stream.get('codec_name')}")
                        print(f"      Codec Long Name: {stream.get('codec_long_name')}")

                        if stream.get("codec_type") == "audio":
                            print(f"      Sample Rate: {stream.get('sample_rate')} Hz")
                            print(f"      Channels: {stream.get('channels')}")
                            print(f"      Channel Layout: {stream.get('channel_layout')}")
                            print(f"      Bit Rate: {stream.get('bit_rate')}")
                            print(f"      Sample Fmt: {stream.get('sample_fmt')}")
                            print(f"      Time Base: {stream.get('time_base')}")

                        if stream.get("codec_type") == "video":
                            print(f"      Width: {stream.get('width')}")
                            print(f"      Height: {stream.get('height')}")

                # Chapters
                chapters = data.get("chapters", [])
                if chapters:
                    print(f"\n📚 Chapters: {len(chapters)} total")

            else:
                print(f"\n⚠️  Unexpected data type: {type(data)}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
