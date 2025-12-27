"""
Tests for SeriesMatcher.

These tests use mocked clients to test the matching logic without network calls.
"""

from unittest.mock import Mock

import pytest

from src.series.matcher import (
    SeriesMatcher,
    _normalize_series_name,
    _normalize_title,
    _score_to_confidence,
)
from src.series.models import (
    ABSSeriesBook,
    ABSSeriesInfo,
    AudibleSeriesBook,
    MatchConfidence,
)


# ============================================================================
# Module-level Function Tests
# ============================================================================


class TestScoreToConfidence:
    """Test _score_to_confidence function."""

    def test_exact_match(self):
        """100 score returns EXACT confidence."""
        assert _score_to_confidence(100) == MatchConfidence.EXACT
        assert _score_to_confidence(100.0) == MatchConfidence.EXACT

    def test_high_confidence(self):
        """90-99 score returns HIGH confidence."""
        assert _score_to_confidence(99) == MatchConfidence.HIGH
        assert _score_to_confidence(95) == MatchConfidence.HIGH
        assert _score_to_confidence(90) == MatchConfidence.HIGH

    def test_medium_confidence(self):
        """75-89 score returns MEDIUM confidence."""
        assert _score_to_confidence(89) == MatchConfidence.MEDIUM
        assert _score_to_confidence(80) == MatchConfidence.MEDIUM
        assert _score_to_confidence(75) == MatchConfidence.MEDIUM

    def test_low_confidence(self):
        """60-74 score returns LOW confidence."""
        assert _score_to_confidence(74) == MatchConfidence.LOW
        assert _score_to_confidence(65) == MatchConfidence.LOW
        assert _score_to_confidence(60) == MatchConfidence.LOW

    def test_no_match(self):
        """Below 60 returns NO_MATCH."""
        assert _score_to_confidence(59) == MatchConfidence.NO_MATCH
        assert _score_to_confidence(30) == MatchConfidence.NO_MATCH
        assert _score_to_confidence(0) == MatchConfidence.NO_MATCH


class TestNormalizeTitle:
    """Test _normalize_title function."""

    def test_lowercase(self):
        """Converts to lowercase."""
        assert "project hail mary" in _normalize_title("Project Hail Mary")

    def test_removes_the_prefix(self):
        """Removes 'the ' prefix."""
        result = _normalize_title("The Martian")
        assert not result.startswith("the")
        assert "martian" in result

    def test_removes_book_number(self):
        """Removes 'book X' patterns."""
        result = _normalize_title("The Great Adventure, Book 3")
        assert "book 3" not in result
        assert "book" not in result

    def test_removes_volume_number(self):
        """Removes 'volume X' patterns."""
        result = _normalize_title("Saga Title Volume 5")
        assert "volume 5" not in result
        assert "volume" not in result

    def test_removes_part_number(self):
        """Removes 'part X' patterns."""
        result = _normalize_title("Adventure Part 2")
        assert "part 2" not in result

    def test_removes_series_indicator_parens(self):
        """Removes series info in parentheses."""
        result = _normalize_title("Book Title (Series Name #1)")
        assert "#1" not in result
        assert "series name" not in result.lower()

    def test_strips_whitespace(self):
        """Strips leading/trailing whitespace."""
        result = _normalize_title("  Some Title  ")
        assert result == "some title"


class TestNormalizeSeriesName:
    """Test _normalize_series_name function."""

    def test_lowercase(self):
        """Converts to lowercase."""
        assert _normalize_series_name("The Expanse") == "expanse"

    def test_removes_the_prefix(self):
        """Removes 'the ' prefix."""
        result = _normalize_series_name("The Dresden Files")
        assert not result.startswith("the")

    def test_removes_series_suffix(self):
        """Removes ' series' suffix."""
        result = _normalize_series_name("Harry Potter Series")
        assert "series" not in result
        assert result == "harry potter"

    def test_removes_saga_suffix(self):
        """Removes ' saga' suffix."""
        result = _normalize_series_name("Dune Saga")
        assert "saga" not in result
        assert result == "dune"

    def test_removes_trilogy_suffix(self):
        """Removes ' trilogy' suffix."""
        result = _normalize_series_name("Lord of the Rings Trilogy")
        assert "trilogy" not in result

    def test_removes_duology_suffix(self):
        """Removes ' duology' suffix."""
        result = _normalize_series_name("Some Duology")
        assert "duology" not in result
        assert result == "some"

    def test_removes_books_suffix(self):
        """Removes ' books' suffix."""
        result = _normalize_series_name("Series Name Books")
        assert "books" not in result
        assert result == "series name"

    def test_combined_normalization(self):
        """Handles multiple normalizations."""
        result = _normalize_series_name("The Fantasy Series")
        assert result == "fantasy"


# ============================================================================
# SeriesMatcher Tests
# ============================================================================


class TestSeriesMatcher:
    """Test SeriesMatcher class."""

    @pytest.fixture
    def mock_abs_client(self):
        """Mock ABS client."""
        return Mock()

    @pytest.fixture
    def mock_audible_client(self):
        """Mock Audible client."""
        return Mock()

    @pytest.fixture
    def mock_cache(self, tmp_path):
        """Provide a real SQLiteCache for testing."""
        from src.cache import SQLiteCache

        return SQLiteCache(db_path=tmp_path / "test_cache.db")

    @pytest.fixture
    def matcher(self, mock_abs_client, mock_audible_client, mock_cache):
        """Create a SeriesMatcher instance."""
        return SeriesMatcher(
            abs_client=mock_abs_client,
            audible_client=mock_audible_client,
            cache=mock_cache,
            min_match_score=60.0,
        )

    # -------------------------------------------------------------------------
    # Initialization Tests
    # -------------------------------------------------------------------------

    def test_init_with_defaults(self, mock_abs_client, mock_audible_client):
        """Matcher initializes with default min_match_score."""
        matcher = SeriesMatcher(mock_abs_client, mock_audible_client)
        assert matcher.min_match_score == 60.0

    def test_init_with_custom_score(self, mock_abs_client, mock_audible_client):
        """Matcher accepts custom min_match_score."""
        matcher = SeriesMatcher(mock_abs_client, mock_audible_client, min_match_score=80.0)
        assert matcher.min_match_score == 80.0

    def test_init_with_cache(self, mock_abs_client, mock_audible_client, mock_cache):
        """Matcher accepts cache."""
        matcher = SeriesMatcher(mock_abs_client, mock_audible_client, cache=mock_cache)
        assert matcher._cache is mock_cache

    # -------------------------------------------------------------------------
    # Price Extraction Tests
    # -------------------------------------------------------------------------

    def test_extract_price_none(self, matcher):
        """_extract_price returns None for None input."""
        result = SeriesMatcher._extract_price(None)
        assert result is None

    def test_extract_price_empty(self, matcher):
        """_extract_price returns None for empty dict."""
        result = SeriesMatcher._extract_price({})
        assert result is None

    def test_extract_price_with_list_price(self, matcher):
        """_extract_price extracts list_price.base."""
        price_data = {"list_price": {"base": 24.99}}
        result = SeriesMatcher._extract_price(price_data)
        assert result == 24.99

    # -------------------------------------------------------------------------
    # Plus Catalog Check Tests
    # -------------------------------------------------------------------------

    def test_check_plus_catalog_is_ayce_true(self, matcher):
        """_check_plus_catalog returns True for is_ayce=True."""
        product = Mock()
        product.is_ayce = True
        assert SeriesMatcher._check_plus_catalog(product) is True

    def test_check_plus_catalog_is_ayce_false(self, matcher):
        """_check_plus_catalog checks plans when is_ayce=False."""
        product = Mock()
        product.is_ayce = False
        product.plans = [{"plan_name": "Minerva", "is_in_plan": True}]
        assert SeriesMatcher._check_plus_catalog(product) is True

    def test_check_plus_catalog_no_ayce_no_plans(self, matcher):
        """_check_plus_catalog returns False when no Plus indicators."""
        product = Mock()
        product.is_ayce = False
        product.plans = None
        assert SeriesMatcher._check_plus_catalog(product) is False

    # -------------------------------------------------------------------------
    # ABS Series Fetching Tests
    # -------------------------------------------------------------------------

    def test_get_abs_series_basic(self, matcher, mock_abs_client):
        """get_abs_series fetches and parses series."""
        mock_abs_client.get_library_series.return_value = {
            "results": [
                {
                    "id": "ser-1",
                    "name": "Test Series",
                    "totalDuration": 50000,
                    "books": [
                        {
                            "id": "book-1",
                            "sequence": "1",
                            "media": {"metadata": {"title": "Book One", "asin": "B001"}, "duration": 25000},
                        },
                        {
                            "id": "book-2",
                            "sequence": "2",
                            "media": {"metadata": {"title": "Book Two", "asin": "B002"}, "duration": 25000},
                        },
                    ],
                }
            ]
        }

        result = matcher.get_abs_series("lib-123", use_cache=False)

        assert len(result) == 1
        assert result[0].name == "Test Series"
        assert len(result[0].books) == 2
        assert result[0].books[0].title == "Book One"
        assert result[0].books[0].asin == "B001"

    def test_get_abs_series_uses_cache(self, matcher, mock_abs_client, mock_cache):
        """get_abs_series returns cached results."""
        # Pre-populate cache
        cache_data = [
            {
                "id": "ser-cached",
                "name": "Cached Series",
                "total_duration": 10000,
                "books": [],
            }
        ]
        mock_cache.set("series_analysis", "abs_series_lib-123", cache_data)

        result = matcher.get_abs_series("lib-123", use_cache=True)

        assert len(result) == 1
        assert result[0].name == "Cached Series"
        mock_abs_client.get_library_series.assert_not_called()

    def test_get_abs_series_handles_empty(self, matcher, mock_abs_client):
        """get_abs_series handles empty results."""
        mock_abs_client.get_library_series.return_value = {"results": []}

        result = matcher.get_abs_series("lib-123", use_cache=False)

        assert result == []

    def test_get_abs_series_skips_invalid(self, matcher, mock_abs_client):
        """get_abs_series skips invalid entries."""
        mock_abs_client.get_library_series.return_value = {
            "results": [
                {
                    "id": "ser-1",
                    "name": "Valid Series",
                    "books": [],
                },
                None,  # Invalid entry
                {},  # Missing required fields
            ]
        }

        result = matcher.get_abs_series("lib-123", use_cache=False)

        # Should get at least the valid one
        assert len(result) >= 1

    # -------------------------------------------------------------------------
    # Audible Series Search Tests
    # -------------------------------------------------------------------------

    def test_search_audible_series(self, matcher, mock_audible_client):
        """search_audible_series searches and filters by series."""
        # Create mock product with series info
        mock_series = Mock()
        mock_series.title = "The Test Series"
        mock_series.sequence = "1"

        mock_product = Mock()
        mock_product.asin = "B001"
        mock_product.title = "Series Book One"
        mock_product.subtitle = "Subtitle"
        mock_product.series = [mock_series]
        mock_product.primary_author = "Author Name"
        mock_product.primary_narrator = "Narrator Name"
        mock_product.runtime_length_min = 500
        mock_product.release_date = None

        mock_audible_client.search_catalog.return_value = [mock_product]

        result = matcher.search_audible_series("Test Series", use_cache=False)

        assert len(result) == 1
        assert result[0].asin == "B001"
        assert result[0].sequence == "1"

    def test_search_audible_series_no_match(self, matcher, mock_audible_client):
        """search_audible_series filters out non-matching series."""
        # Product in different series
        mock_series = Mock()
        mock_series.title = "Completely Different Series"
        mock_series.sequence = "1"

        mock_product = Mock()
        mock_product.asin = "B001"
        mock_product.series = [mock_series]

        mock_audible_client.search_catalog.return_value = [mock_product]

        result = matcher.search_audible_series("Target Series", use_cache=False)

        assert len(result) == 0

    # -------------------------------------------------------------------------
    # ASIN Lookup Tests
    # -------------------------------------------------------------------------

    def test_get_series_books_by_asin(self, matcher, mock_audible_client):
        """get_series_books_by_asin looks up ASINs and extracts series info."""
        mock_series = Mock()
        mock_series.asin = "ser-123"
        mock_series.title = "The Series"
        mock_series.sequence = "1"

        mock_product = Mock()
        mock_product.asin = "B001"
        mock_product.title = "Book One"
        mock_product.subtitle = None
        mock_product.series = [mock_series]
        mock_product.primary_author = "Author"
        mock_product.primary_narrator = "Narrator"
        mock_product.runtime_length_min = 300
        mock_product.release_date = None

        mock_audible_client.get_catalog_product.return_value = mock_product

        books, series_asin = matcher.get_series_books_by_asin(["B001"], use_cache=False)

        assert len(books) == 1
        assert books[0].asin == "B001"
        assert series_asin == "ser-123"

    def test_get_series_books_by_asin_no_audible_client(self, mock_abs_client, mock_cache):
        """get_series_books_by_asin handles None audible client."""
        matcher = SeriesMatcher(mock_abs_client, None, cache=mock_cache)
        matcher._audible = None  # Ensure it's None

        books, series_asin = matcher.get_series_books_by_asin(["B001"], use_cache=False)

        assert books == []
        assert series_asin is None

    def test_get_series_books_by_asin_empty_asins(self, matcher, mock_audible_client):
        """get_series_books_by_asin handles empty ASIN list."""
        books, series_asin = matcher.get_series_books_by_asin([], use_cache=False)

        assert books == []
        assert series_asin is None
        mock_audible_client.get_catalog_product.assert_not_called()

    def test_get_series_books_by_asin_skips_none_asin(self, matcher, mock_audible_client):
        """get_series_books_by_asin skips None/empty ASINs."""
        books, series_asin = matcher.get_series_books_by_asin([None, ""], use_cache=False)

        # Should skip None and empty strings, not call API
        mock_audible_client.get_catalog_product.assert_not_called()

    def test_get_series_books_by_asin_handles_lookup_error(self, matcher, mock_audible_client):
        """get_series_books_by_asin handles lookup errors gracefully."""
        mock_audible_client.get_catalog_product.side_effect = Exception("API Error")

        books, series_asin = matcher.get_series_books_by_asin(["B001"], use_cache=False)

        assert books == []
        assert series_asin is None


# ============================================================================
# Model Creation Tests
# ============================================================================


class TestABSSeriesBook:
    """Test ABSSeriesBook model."""

    def test_create_minimal(self):
        """Create with minimal required fields."""
        book = ABSSeriesBook(id="book-1", title="Test Book")
        assert book.id == "book-1"
        assert book.title == "Test Book"
        assert book.sequence is None
        assert book.asin is None

    def test_create_with_all_fields(self):
        """Create with all fields."""
        book = ABSSeriesBook(
            id="book-1",
            title="Test Book",
            sequence="1",
            asin="B001",
            isbn="1234567890",
            author_name="Author",
            narrator_name="Narrator",
            duration=36000,
            added_at=1700000000,
        )
        assert book.sequence == "1"
        assert book.asin == "B001"
        assert book.isbn == "1234567890"


class TestABSSeriesInfo:
    """Test ABSSeriesInfo model."""

    def test_create_minimal(self):
        """Create with minimal required fields."""
        series = ABSSeriesInfo(id="ser-1", name="Test Series")
        assert series.id == "ser-1"
        assert series.name == "Test Series"
        assert series.books == []

    def test_create_with_books(self):
        """Create with books."""
        book = ABSSeriesBook(id="book-1", title="Book One")
        series = ABSSeriesInfo(id="ser-1", name="Test Series", books=[book])
        assert len(series.books) == 1
        assert series.books[0].title == "Book One"


class TestAudibleSeriesBook:
    """Test AudibleSeriesBook model."""

    def test_create_minimal(self):
        """Create with minimal required fields."""
        book = AudibleSeriesBook(asin="B001", title="Test Book")
        assert book.asin == "B001"
        assert book.title == "Test Book"
        assert book.is_in_library is False

    def test_create_with_all_fields(self):
        """Create with all fields."""
        book = AudibleSeriesBook(
            asin="B001",
            title="Test Book",
            subtitle="A Subtitle",
            sequence="2",
            author_name="Author",
            narrator_name="Narrator",
            runtime_minutes=480,
            release_date=None,
            is_in_library=True,
            price=19.99,
            is_in_plus_catalog=True,
        )
        assert book.subtitle == "A Subtitle"
        assert book.sequence == "2"
        assert book.is_in_library is True
        assert book.price == 19.99
        assert book.is_in_plus_catalog is True
