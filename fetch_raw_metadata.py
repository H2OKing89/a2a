#!/usr/bin/env python3
"""
Fetch raw metadata from ABS for a specific audiobook.

This script searches for an audiobook in your ABS library and saves
the complete raw metadata (including all FFmpeg metadata) to a JSON file.

Usage:
    python fetch_raw_metadata.py "He Who Fights with Monsters A LitRPG Adventure vol_01"
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.abs.client import ABSClient
from src.config import get_settings


def main():
    """Fetch and save raw metadata."""
    if len(sys.argv) < 2:
        print("Usage: python fetch_raw_metadata.py <search_query>")
        print("\nExample:")
        print("  python fetch_raw_metadata.py 'He Who Fights with Monsters vol_01'")
        sys.exit(1)

    search_query = sys.argv[1]

    # Load settings from environment
    settings = get_settings()

    if not settings.abs.host or not settings.abs.api_key:
        print("❌ ABS credentials not configured in .env")
        print("   Set ABS_HOST and ABS_API_KEY in .env file")
        sys.exit(1)

    if not settings.abs.library_id:
        print("❌ ABS_LIBRARY_ID not set in .env")
        print("   Set ABS_LIBRARY_ID to search the library")
        sys.exit(1)

    print(f"📡 Connecting to ABS: {settings.abs.host}")
    print(f"📚 Library ID: {settings.abs.library_id}")
    print(f"🔍 Searching for: '{search_query}'")

    try:
        # Create client
        with ABSClient(
            host=settings.abs.host,
            api_key=settings.abs.api_key,
        ) as client:
            # Search for the book
            results = client.search_library(settings.abs.library_id, search_query, limit=20)

            # Check if we found anything
            books = results.get("book", [])
            if not books:
                print(f"❌ No books found matching '{search_query}'")
                print("\n🔎 Available results:")
                if results.get("series"):
                    print(f"   Series: {len(results.get('series', []))}")
                if results.get("authors"):
                    print(f"   Authors: {len(results.get('authors', []))}")
                if results.get("tags"):
                    print(f"   Tags: {len(results.get('tags', []))}")
                sys.exit(1)

            print(f"\n✅ Found {len(books)} book(s)")

            # Display search results
            for i, book in enumerate(books, 1):
                item = book.get("libraryItem", {})
                media = item.get("media", {})
                metadata = media.get("metadata", {})
                title = metadata.get("title", "Unknown")
                print(f"\n  [{i}] {title}")
                if item.get("id"):
                    print(f"      ID: {item['id']}")

            # Ask user which one
            if len(books) > 1:
                choice = input("\nWhich one? (number): ").strip()
                try:
                    idx = int(choice) - 1
                    if idx < 0 or idx >= len(books):
                        print(f"❌ Invalid choice: {choice}")
                        sys.exit(1)
                except ValueError:
                    print(f"❌ Invalid input: {choice}")
                    sys.exit(1)
            else:
                idx = 0

            book = books[idx]
            item_id = book.get("libraryItem", {}).get("id")
            if not item_id:
                print("❌ Could not get item ID from search results")
                sys.exit(1)

            print(f"\n📦 Fetching full metadata for item: {item_id}")

            # Fetch the full expanded item (this includes all FFmpeg metadata)
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
            print(f"\n📊 Metadata summary:")
            print(f"   Title: {data.get('media', {}).get('metadata', {}).get('title')}")
            print(f"   Audio Files: {len(data.get('media', {}).get('audioFiles', []))}")
            print(f"   Total Size: {data.get('size', 0) / (1024**3):.2f} GB")
            print(f"   Duration: {data.get('media', {}).get('duration', 0) / 3600:.2f} hours")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
