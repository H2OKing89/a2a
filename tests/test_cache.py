"""Tests for SQLite cache."""

import time
from pathlib import Path
from typing import Any

import pytest

from src.cache.sqlite_cache import SQLiteCache


class TestSQLiteCache:
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
