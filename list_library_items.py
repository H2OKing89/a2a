#!/usr/bin/env python3
"""
List all library items to find the audiobook.

This helps when search doesn't work as expected.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.abs.client import ABSClient
from src.config import get_settings


def main():
    """List all library items."""
    settings = get_settings()

    if not settings.abs.host or not settings.abs.api_key:
        print("❌ ABS credentials not configured in .env")
        sys.exit(1)

    if not settings.abs.library_id:
        print("❌ ABS_LIBRARY_ID not set in .env")
        sys.exit(1)

    print(f"📡 Connecting to ABS: {settings.abs.host}")
    print(f"📚 Library ID: {settings.abs.library_id}")

    try:
        with ABSClient(
            host=settings.abs.host,
            api_key=settings.abs.api_key,
        ) as client:
            print("📋 Fetching library items (first 100)...")

            # Get library items
            items = client.get_all_library_items(
                settings.abs.library_id,
                batch_size=100,
                sort="media.metadata.title",
            )

            print(f"\n✅ Found {len(items)} items\n")

            # Search for items containing keywords
            search_terms = ["vol_01", "Monsters", "shirtaloon", "1774248182"]

            matching = []
            for item in items:
                title = item.media.metadata.title if hasattr(item.media, "metadata") else ""
                rel_path = item.rel_path if hasattr(item, "rel_path") else ""

                if any(term.lower() in (title.lower() + " " + rel_path.lower()) for term in search_terms):
                    matching.append({"id": item.id, "title": title, "rel_path": rel_path})

            if matching:
                print("🎯 Matching items:\n")
                for i, m in enumerate(matching, 1):
                    print(f"  [{i}] {m['title']}")
                    print(f"      ID: {m['id']}")
                    print(f"      Path: {m['rel_path']}\n")
            else:
                print("No exact matches found. Showing first 20 items:\n")
                for i, item in enumerate(items[:20], 1):
                    title = item.media.metadata.title if hasattr(item.media, "metadata") else "Unknown"
                    rel_path = item.rel_path if hasattr(item, "rel_path") else ""
                    print(f"  [{i}] {title}")
                    print(f"      Path: {rel_path}\n")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
