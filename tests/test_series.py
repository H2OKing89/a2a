"""
Tests for series matching module.
"""

from datetime import datetime

import pytest

from src.series.matcher import (
    _normalize_series_name,
    _normalize_title,
    _score_to_confidence,
)
from src.series.models import (
    ABSSeriesBook,
    ABSSeriesInfo,
    AudibleSeriesBook,
    AudibleSeriesInfo,
    MatchConfidence,
    MatchResult,
    MissingBook,
    SeriesComparisonResult,
    SeriesMatchResult,
)


class TestNormalizeFunctions:
    """Tests for normalization helper functions."""

    def test_normalize_title_basic(self):
        """Test basic title normalization."""
        assert _normalize_title("The Great Book") == "great book"
        assert _normalize_title("  Some Title  ") == "some title"

    def test_normalize_title_removes_series_info(self):
        """Test that series info is removed from titles."""
        assert _normalize_title("Book Name (Series #1)") == "book name"
        assert _normalize_title("Book Name, Book 2") == "book name"
        assert _normalize_title("Book Name Volume 3") == "book name"

    def test_normalize_series_name_basic(self):
        """Test basic series name normalization."""
        assert _normalize_series_name("The Dark Tower") == "dark tower"
        assert _normalize_series_name("Harry Potter Series") == "harry potter"
        assert _normalize_series_name("Lord of the Rings Saga") == "lord of the rings"
        assert _normalize_series_name("Foundation Trilogy") == "foundation"

    def test_score_to_confidence(self):
        """Test score to confidence conversion."""
        assert _score_to_confidence(100) == MatchConfidence.EXACT
        assert _score_to_confidence(95) == MatchConfidence.HIGH
        assert _score_to_confidence(80) == MatchConfidence.MEDIUM
        assert _score_to_confidence(65) == MatchConfidence.LOW
        assert _score_to_confidence(50) == MatchConfidence.NO_MATCH

    def test_score_to_confidence_boundaries(self):
        """Test exact boundary values for confidence transitions."""
        # Exact boundaries
        assert _score_to_confidence(90) == MatchConfidence.HIGH  # 90 is HIGH, not EXACT
        assert _score_to_confidence(75) == MatchConfidence.MEDIUM  # 75 is MEDIUM
        assert _score_to_confidence(60) == MatchConfidence.LOW  # 60 is LOW

        # Just below boundaries
        assert _score_to_confidence(89.9) == MatchConfidence.MEDIUM
        assert _score_to_confidence(74.9) == MatchConfidence.LOW
        assert _score_to_confidence(59.9) == MatchConfidence.NO_MATCH


class TestABSSeriesInfo:
    """Tests for ABSSeriesInfo model."""

    def test_basic_creation(self):
        """Test basic series info creation."""
        series = ABSSeriesInfo(
            id="ser_123",
            name="Harry Potter",
            books=[
                ABSSeriesBook(id="book_1", title="Philosopher's Stone", sequence="1"),
                ABSSeriesBook(id="book_2", title="Chamber of Secrets", sequence="2"),
            ],
        )

        assert series.id == "ser_123"
        assert series.name == "Harry Potter"
        assert series.book_count == 2
        assert series.sequences == ["1", "2"]

    def test_asins_property(self):
        """Test ASINs extraction."""
        series = ABSSeriesInfo(
            id="ser_123",
            name="Test Series",
            books=[
                ABSSeriesBook(id="b1", title="Book 1", asin="B001"),
                ABSSeriesBook(id="b2", title="Book 2", asin=None),
                ABSSeriesBook(id="b3", title="Book 3", asin="B003"),
            ],
        )

        assert series.asins == {"B001", "B003"}

    def test_empty_series(self):
        """Test series with no books."""
        series = ABSSeriesInfo(id="ser_empty", name="Empty Series")

        assert series.book_count == 0
        assert series.sequences == []
        assert series.asins == set()


class TestAudibleSeriesBook:
    """Tests for AudibleSeriesBook model."""

    def test_runtime_hours_property(self):
        """Test runtime conversion to hours."""
        book = AudibleSeriesBook(
            asin="B001",
            title="Test Book",
            runtime_minutes=180,
        )

        assert book.runtime_hours == 3.0

    def test_runtime_hours_none(self):
        """Test runtime when not available."""
        book = AudibleSeriesBook(
            asin="B001",
            title="Test Book",
        )

        assert book.runtime_hours is None


class TestSeriesComparisonResult:
    """Tests for SeriesComparisonResult model."""

    def test_completion_percentage(self):
        """Test completion percentage calculation."""
        result = SeriesComparisonResult(
            series_match=SeriesMatchResult(
                abs_series=ABSSeriesInfo(id="ser_1", name="Test"),
                confidence=MatchConfidence.HIGH,
            ),
            abs_book_count=3,
            audible_book_count=5,
            matched_count=3,
            missing_count=2,
        )

        assert result.completion_percentage == 60.0
        assert not result.is_complete

    def test_is_complete(self):
        """Test complete series detection."""
        result = SeriesComparisonResult(
            series_match=SeriesMatchResult(
                abs_series=ABSSeriesInfo(id="ser_1", name="Test"),
                confidence=MatchConfidence.HIGH,
            ),
            abs_book_count=5,
            audible_book_count=5,
            matched_count=5,
            missing_count=0,
        )

        assert result.is_complete
        assert result.completion_percentage == 100.0

    def test_total_missing_hours(self):
        """Test total missing hours calculation."""
        result = SeriesComparisonResult(
            series_match=SeriesMatchResult(
                abs_series=ABSSeriesInfo(id="ser_1", name="Test"),
                confidence=MatchConfidence.HIGH,
            ),
            missing_books=[
                MissingBook(asin="B001", title="Book 1", runtime_hours=5.0),
                MissingBook(asin="B002", title="Book 2", runtime_hours=6.5),
                MissingBook(asin="B003", title="Book 3"),  # No runtime
            ],
            missing_count=3,
        )

        assert result.total_missing_hours == 11.5

    def test_zero_audible_books(self):
        """Test edge case with no Audible books found."""
        result = SeriesComparisonResult(
            series_match=SeriesMatchResult(
                abs_series=ABSSeriesInfo(id="ser_1", name="Test"),
                confidence=MatchConfidence.NO_MATCH,
            ),
            abs_book_count=3,
            audible_book_count=0,
            matched_count=0,
            missing_count=0,
        )

        # If we have ABS books but no Audible books, consider 100% complete
        # (we can't be missing something that doesn't exist in Audible)
        assert result.completion_percentage == 100.0


class TestMatchResult:
    """Tests for MatchResult model."""

    def test_exact_asin_match(self):
        """Test exact ASIN match."""
        result = MatchResult(
            abs_book=ABSSeriesBook(id="b1", title="Test", asin="B001"),
            audible_book=AudibleSeriesBook(asin="B001", title="Test"),
            match_score=100.0,
            confidence=MatchConfidence.EXACT,
            matched_by="asin",
        )

        assert result.confidence == MatchConfidence.EXACT
        assert result.matched_by == "asin"

    def test_no_match(self):
        """Test no match result."""
        result = MatchResult(
            abs_book=ABSSeriesBook(id="b1", title="Unknown Book"),
            audible_book=None,
            match_score=0.0,
            confidence=MatchConfidence.NO_MATCH,
        )

        assert result.audible_book is None
        assert result.confidence == MatchConfidence.NO_MATCH
