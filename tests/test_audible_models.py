"""Tests for Audible API models.

Tests the Pydantic models used to parse Audible API responses,
including handling of None values and flexible field types.
"""

import pytest

from src.audible.models import (
    AudibleAuthor,
    AudibleBook,
    AudibleCatalogProduct,
    AudibleCategory,
    AudibleCategoryLadder,
    AudibleLibraryItem,
    AudibleNarrator,
    AudibleRating,
    AudibleSeries,
)


class TestAudibleAuthor:
    """Tests for AudibleAuthor model."""

    def test_author_with_asin(self):
        """Test author with ASIN."""
        author = AudibleAuthor(asin="B001ABC123", name="Test Author")
        assert author.asin == "B001ABC123"
        assert author.name == "Test Author"

    def test_author_without_asin(self):
        """Test author without ASIN (None)."""
        author = AudibleAuthor(name="Anonymous Author")
        assert author.asin is None
        assert author.name == "Anonymous Author"

    def test_author_extra_fields_ignored(self):
        """Test that extra fields are ignored."""
        author = AudibleAuthor(name="Test", extra_field="ignored")
        assert author.name == "Test"
        assert not hasattr(author, "extra_field")


class TestAudibleRating:
    """Tests for AudibleRating model with flexible value types."""

    def test_rating_with_int_values(self):
        """Test rating with integer values."""
        rating = AudibleRating(
            overall_distribution={"5": 100, "4": 50, "3": 25},
            num_reviews=175,
        )
        assert rating.overall_distribution["5"] == 100
        assert rating.num_reviews == 175

    def test_rating_with_float_average(self):
        """Test rating with float average_rating (real API behavior)."""
        rating = AudibleRating(
            overall_distribution={
                "5": 100,
                "4": 50,
                "average_rating": 4.833333333333333,
                "display_average_rating": "4.8",
            }
        )
        # Should accept mixed types in the dict
        assert rating.overall_distribution["average_rating"] == 4.833333333333333
        assert rating.overall_distribution["display_average_rating"] == "4.8"

    def test_rating_with_none_distributions(self):
        """Test rating with None distributions."""
        rating = AudibleRating(
            overall_distribution=None,
            performance_distribution=None,
            story_distribution=None,
        )
        assert rating.overall_distribution is None
        assert rating.performance_distribution is None
        assert rating.story_distribution is None

    def test_rating_defaults(self):
        """Test rating defaults to None."""
        rating = AudibleRating()
        assert rating.overall_distribution is None
        assert rating.num_reviews is None


class TestAudibleSeries:
    """Tests for AudibleSeries model."""

    def test_series_full(self):
        """Test series with all fields."""
        series = AudibleSeries(
            asin="B00SERIES1",
            title="Epic Fantasy Series",
            sequence="1",
            url="https://audible.com/series/...",
        )
        assert series.asin == "B00SERIES1"
        assert series.title == "Epic Fantasy Series"
        assert series.sequence == "1"

    def test_series_minimal(self):
        """Test series with just title."""
        series = AudibleSeries(title="Standalone")
        assert series.title == "Standalone"
        assert series.asin is None
        assert series.sequence is None


class TestAudibleBook:
    """Tests for AudibleBook base model."""

    def test_book_minimal(self):
        """Test book with minimal required fields."""
        book = AudibleBook(asin="B00TEST123", title="Test Book")
        assert book.asin == "B00TEST123"
        assert book.title == "Test Book"

    def test_book_with_none_series(self):
        """Test book handles None series (API can return None instead of [])."""
        book = AudibleBook(
            asin="B00TEST123",
            title="Test Book",
            series=None,  # API sometimes returns None
        )
        # Should not raise, series defaults to empty list or accepts None
        assert book.series is None or book.series == []

    def test_book_with_none_category_ladders(self):
        """Test book handles None category_ladders."""
        book = AudibleBook(
            asin="B00TEST123",
            title="Test Book",
            category_ladders=None,  # API sometimes returns None
        )
        assert book.category_ladders is None or book.category_ladders == []

    def test_book_with_empty_lists(self):
        """Test book with explicit empty lists."""
        book = AudibleBook(
            asin="B00TEST123",
            title="Test Book",
            authors=[],
            narrators=[],
            series=[],
            category_ladders=[],
        )
        assert book.authors == []
        assert book.narrators == []

    def test_book_runtime_hours_property(self):
        """Test runtime_hours calculation."""
        book = AudibleBook(
            asin="B00TEST123",
            title="Test Book",
            runtime_length_min=600,  # 10 hours
        )
        assert book.runtime_hours == 10.0

    def test_book_runtime_hours_none(self):
        """Test runtime_hours when no duration."""
        book = AudibleBook(asin="B00TEST123", title="Test Book")
        assert book.runtime_hours is None

    def test_book_primary_author(self):
        """Test primary_author property."""
        book = AudibleBook(
            asin="B00TEST123",
            title="Test Book",
            authors=[
                AudibleAuthor(name="First Author"),
                AudibleAuthor(name="Second Author"),
            ],
        )
        assert book.primary_author == "First Author"

    def test_book_primary_author_none(self):
        """Test primary_author when no authors."""
        book = AudibleBook(asin="B00TEST123", title="Test Book")
        assert book.primary_author is None


class TestAudibleLibraryItem:
    """Tests for AudibleLibraryItem with nullable boolean fields."""

    def test_library_item_minimal(self):
        """Test library item with minimal fields."""
        item = AudibleLibraryItem(asin="B00TEST123", title="Test Book")
        assert item.asin == "B00TEST123"
        assert item.title == "Test Book"

    def test_library_item_boolean_defaults(self):
        """Test boolean fields have correct defaults."""
        item = AudibleLibraryItem(asin="B00TEST123", title="Test Book")
        # These should have sensible defaults
        assert item.is_downloaded is False or item.is_downloaded is None
        assert item.is_finished is False or item.is_finished is None

    def test_library_item_none_booleans(self):
        """Test library item accepts None for boolean fields (real API behavior)."""
        item = AudibleLibraryItem(
            asin="B00TEST123",
            title="Test Book",
            is_downloaded=None,
            is_finished=None,
            is_playable=None,
            is_archived=None,
            is_visible=None,
            is_removable=None,
            is_returnable=None,
        )
        # Should not raise - all these can be None from API
        assert item.is_downloaded is None
        assert item.is_finished is None

    def test_library_item_true_booleans(self):
        """Test library item with True boolean values."""
        item = AudibleLibraryItem(
            asin="B00TEST123",
            title="Test Book",
            is_downloaded=True,
            is_finished=True,
            is_playable=True,
        )
        assert item.is_downloaded is True
        assert item.is_finished is True
        assert item.is_playable is True

    def test_library_item_with_none_series_and_categories(self):
        """Test library item handles None for inherited list fields."""
        item = AudibleLibraryItem(
            asin="B00TEST123",
            title="Test Book",
            series=None,
            category_ladders=None,
        )
        # Should not raise validation error
        assert item.series is None or item.series == []
        assert item.category_ladders is None or item.category_ladders == []

    def test_library_item_with_percent_complete(self):
        """Test library item with listening progress."""
        item = AudibleLibraryItem(
            asin="B00TEST123",
            title="Test Book",
            percent_complete=75.5,
        )
        assert item.percent_complete == 75.5

    def test_library_item_full_api_response(self):
        """Test parsing a realistic API response structure."""
        data = {
            "asin": "B0D6CW3X79",
            "title": "86--EIGHTY-SIX, Vol. 10",
            "authors": [{"name": "Asato Asato"}],
            "narrators": [{"name": "Some Narrator"}],
            "publisher_name": "Yen Audio",
            "runtime_length_min": 456,
            "series": None,  # API returns None for non-series books
            "category_ladders": None,  # API sometimes returns None
            "rating": {
                "overall_distribution": {
                    "average_rating": 4.8,
                    "display_average_rating": "4.8",
                    "5": 100,
                },
            },
            "is_downloaded": None,
            "is_finished": None,
            "is_playable": None,
            "is_archived": None,
            "is_visible": None,
            "is_removable": None,
            "is_returnable": None,
            "percent_complete": None,
        }
        item = AudibleLibraryItem.model_validate(data)
        assert item.asin == "B0D6CW3X79"
        assert item.title == "86--EIGHTY-SIX, Vol. 10"
        assert item.primary_author == "Asato Asato"
        assert item.runtime_hours == 7.6


class TestAudibleCatalogProduct:
    """Tests for AudibleCatalogProduct model."""

    def test_catalog_product_minimal(self):
        """Test catalog product with minimal fields."""
        product = AudibleCatalogProduct(asin="B00TEST123", title="Test Book")
        assert product.asin == "B00TEST123"

    def test_catalog_product_with_sku(self):
        """Test catalog product with SKU."""
        product = AudibleCatalogProduct(
            asin="B00TEST123",
            title="Test Book",
            sku="AU_123456",
            sku_lite="123456",
        )
        assert product.sku == "AU_123456"
        assert product.sku_lite == "123456"

    def test_catalog_product_inherits_book_features(self):
        """Test catalog product inherits AudibleBook properties."""
        product = AudibleCatalogProduct(
            asin="B00TEST123",
            title="Test Book",
            runtime_length_min=300,
            authors=[AudibleAuthor(name="Author Name")],
        )
        assert product.runtime_hours == 5.0
        assert product.primary_author == "Author Name"
