"""Tests for SQLite cache."""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from src.cache.sqlite_cache import (
    PRICING_NAMESPACES,
    SQLiteCache,
    calculate_pricing_ttl_seconds,
    get_seconds_until_next_month,
)


class TestPricingTTL:
    """Tests for month-boundary-aware pricing TTL."""

    def test_get_seconds_until_next_month(self):
        """Test calculation of seconds until next month."""
        # Mock current time to a known date
        with patch("src.cache.sqlite_cache.datetime") as mock_datetime:
            # Set to Jan 15, 2026 12:00 UTC
            mock_now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            seconds = get_seconds_until_next_month()

            # Should be ~16.5 days until Feb 1
            assert seconds > 0
            # Roughly 16 days * 24 hours * 3600 seconds
            expected_min = 15 * 24 * 3600
            expected_max = 18 * 24 * 3600
            assert expected_min < seconds < expected_max

    def test_calculate_pricing_ttl_respects_month_boundary(self):
        """Test that pricing TTL doesn't exceed month boundary."""
        with patch("src.cache.sqlite_cache.get_seconds_until_next_month") as mock_month:
            # Simulate 2 hours until month end
            mock_month.return_value = 2 * 3600  # 2 hours

            # Request 6 hours, should get ~1 hour (2 hours - 1 hour buffer)
            requested_ttl = 6 * 3600  # 6 hours
            actual_ttl = calculate_pricing_ttl_seconds(requested_ttl)

            # Should be capped to 1 hour (2 hours - 1 hour buffer)
            assert actual_ttl == 1 * 3600

    def test_calculate_pricing_ttl_uses_requested_when_far_from_month_end(self):
        """Test that requested TTL is used when far from month end."""
        with patch("src.cache.sqlite_cache.get_seconds_until_next_month") as mock_month:
            # Simulate 20 days until month end
            mock_month.return_value = 20 * 24 * 3600

            requested_ttl = 6 * 3600  # 6 hours
            actual_ttl = calculate_pricing_ttl_seconds(requested_ttl)

            # Should use requested TTL since it's well within month boundary
            assert actual_ttl == requested_ttl

    def test_pricing_namespaces_defined(self):
        """Test that pricing namespaces are properly defined."""
        assert "audible_enrichment" in PRICING_NAMESPACES
        assert "audible_enrichment_v2" in PRICING_NAMESPACES
        assert "catalog" in PRICING_NAMESPACES
        assert "search" in PRICING_NAMESPACES
        assert "library" in PRICING_NAMESPACES

    def test_calculate_pricing_ttl_near_month_end(self):
        """Test TTL behavior within 1 hour of month end."""
        with patch("src.cache.sqlite_cache.get_seconds_until_next_month") as mock_month:
            # Simulate 30 minutes until month end
            mock_month.return_value = 30 * 60  # 30 minutes

            requested_ttl = 6 * 3600  # 6 hours
            actual_ttl = calculate_pricing_ttl_seconds(requested_ttl)

            # Should use remaining time (30 min), not fall back to 6 hours
            assert actual_ttl == 30 * 60

    def test_calculate_pricing_ttl_very_close_to_month_end(self):
        """Test TTL clamps to minimum 60 seconds near month boundary."""
        with patch("src.cache.sqlite_cache.get_seconds_until_next_month") as mock_month:
            # Simulate 10 seconds until month end
            mock_month.return_value = 10

            requested_ttl = 6 * 3600  # 6 hours
            actual_ttl = calculate_pricing_ttl_seconds(requested_ttl)

            # Should clamp to minimum 60 seconds
            assert actual_ttl == 60

    """Tests for SQLiteCache class."""

    @pytest.fixture
    def temp_cache(self, tmp_path: Path) -> SQLiteCache:
        """Create a temporary cache for testing."""
        cache_path: Path = tmp_path / "test_cache.db"
        return SQLiteCache(cache_path)

    def test_cache_initialization(self, temp_cache):
        """Test cache initializes correctly."""
        assert temp_cache is not None
        assert temp_cache.db_path.exists()

    def test_set_and_get_dict(self, temp_cache):
        """Test basic set and get operations with dict data."""
        temp_cache.set("test_ns", "key1", {"value": 123})
        result = temp_cache.get("test_ns", "key1")

        assert result == {"value": 123}

    def test_get_nonexistent_key(self, temp_cache):
        """Test getting a key that doesn't exist."""
        result = temp_cache.get("test_ns", "nonexistent")
        assert result is None

    def test_namespace_isolation(self, temp_cache):
        """Test that namespaces are isolated."""
        temp_cache.set("ns1", "key", {"data": "value1"})
        temp_cache.set("ns2", "key", {"data": "value2"})

        assert temp_cache.get("ns1", "key") == {"data": "value1"}
        assert temp_cache.get("ns2", "key") == {"data": "value2"}

    def test_cache_overwrite(self, temp_cache):
        """Test overwriting existing key."""
        temp_cache.set("test_ns", "key", {"data": "original"})
        temp_cache.set("test_ns", "key", {"data": "updated"})

        assert temp_cache.get("test_ns", "key") == {"data": "updated"}

    def test_ttl_expiration(self, temp_cache):
        """Test TTL expiration (with very short TTL)."""
        temp_cache.set("test_ns", "expiring", {"data": "value"}, ttl_seconds=1)
        assert temp_cache.get("test_ns", "expiring") == {"data": "value"}

        time.sleep(1.1)
        assert temp_cache.get("test_ns", "expiring") is None

    def test_delete_key(self, temp_cache):
        """Test deleting a specific key."""
        temp_cache.set("test_ns", "to_delete", {"data": "value"})
        assert temp_cache.get("test_ns", "to_delete") == {"data": "value"}

        temp_cache.delete("test_ns", "to_delete")
        assert temp_cache.get("test_ns", "to_delete") is None

    def test_clear_namespace(self, temp_cache):
        """Test clearing all keys in a namespace."""
        temp_cache.set("clear_ns", "key1", {"data": "value1"})
        temp_cache.set("clear_ns", "key2", {"data": "value2"})
        temp_cache.set("other_ns", "key1", {"data": "other_value"})

        temp_cache.clear_namespace("clear_ns")

        assert temp_cache.get("clear_ns", "key1") is None
        assert temp_cache.get("clear_ns", "key2") is None
        assert temp_cache.get("other_ns", "key1") == {"data": "other_value"}

    def test_complex_values(self, temp_cache):
        """Test storing complex nested data structures."""
        complex_data = {
            "string": "hello",
            "number": 42,
            "float": 3.14,
            "list": [1, 2, 3],
            "nested": {"a": {"b": {"c": "deep"}}},
            "bool": True,
            "null": None,
        }

        temp_cache.set("test_ns", "complex", complex_data)
        result = temp_cache.get("test_ns", "complex")

        assert result == complex_data

    def test_list_data(self, temp_cache):
        """Test storing list data (e.g., library items)."""
        items = [
            {"id": "1", "title": "Book 1"},
            {"id": "2", "title": "Book 2"},
        ]

        temp_cache.set("test_ns", "items", items)
        result = temp_cache.get("test_ns", "items")

        assert result == items

    def test_metadata_extraction(self, temp_cache, sample_library_item):
        """Test that metadata is extracted from audiobook items."""
        temp_cache.set("abs_items", "test_item", sample_library_item)
        result = temp_cache.get("abs_items", "test_item")

        assert result == sample_library_item

    def test_clear_pricing_caches(self, temp_cache):
        """Test clearing pricing-related caches for monthly deal refresh."""
        # Add data to pricing namespaces
        temp_cache.set("audible_enrichment", "key1", {"price": 9.99})
        temp_cache.set("audible_enrichment_v2", "key2", {"price": 14.99})
        temp_cache.set("catalog", "key3", {"title": "Book"})
        temp_cache.set("search", "key4", {"results": []})
        temp_cache.set("library", "key5", {"owned": True})
        # Non-pricing namespace should survive
        temp_cache.set("abs_items", "key6", {"data": "keep"})

        # Clear pricing caches
        cleared = temp_cache.clear_pricing_caches()

        # Verify pricing caches cleared
        assert temp_cache.get("audible_enrichment", "key1") is None
        assert temp_cache.get("audible_enrichment_v2", "key2") is None
        assert temp_cache.get("catalog", "key3") is None
        assert temp_cache.get("search", "key4") is None
        assert temp_cache.get("library", "key5") is None

        # Non-pricing namespace should still exist
        assert temp_cache.get("abs_items", "key6") == {"data": "keep"}

        # Verify cleared counts
        assert sum(cleared.values()) == 5
