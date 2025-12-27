"""
Pydantic models for series tracking and matching.

These models represent series data from both ABS and Audible,
as well as matching results.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class MatchConfidence(str, Enum):
    """Match confidence level based on fuzzy match score."""

    EXACT = "exact"  # 100% match
    HIGH = "high"  # 90-99% match
    MEDIUM = "medium"  # 75-89% match
    LOW = "low"  # 60-74% match
    NO_MATCH = "no_match"  # Below 60%


class ABSSeriesBook(BaseModel):
    """A book within an ABS series."""

    id: str
    title: str
    sequence: str | None = None
    asin: str | None = None
    isbn: str | None = None
    author_name: str | None = None
    narrator_name: str | None = None
    duration: float = 0.0
    added_at: int | None = None

    model_config = {"extra": "ignore"}


class ABSSeriesInfo(BaseModel):
    """Series information from Audiobookshelf."""

    id: str
    name: str
    name_ignore_prefix: str | None = Field(default=None, alias="nameIgnorePrefix")
    description: str | None = None
    added_at: int | None = Field(default=None, alias="addedAt")
    total_duration: float = Field(default=0.0, alias="totalDuration")
    books: list[ABSSeriesBook] = Field(default_factory=list)

    model_config = {"extra": "ignore", "populate_by_name": True}

    @property
    def book_count(self) -> int:
        """Number of books in series."""
        return len(self.books)

    @property
    def sequences(self) -> list[str]:
        """Get list of sequence numbers."""
        return [b.sequence for b in self.books if b.sequence]

    @property
    def asins(self) -> set[str]:
        """Get set of ASINs in series."""
        return {b.asin for b in self.books if b.asin}


class AudibleSeriesBook(BaseModel):
    """A book within an Audible series."""

    asin: str
    title: str
    subtitle: str | None = None
    sequence: str | None = None
    author_name: str | None = None
    narrator_name: str | None = None
    runtime_minutes: int | None = None
    release_date: str | None = None
    is_in_library: bool = False
    # Pricing info
    price: float | None = None
    is_in_plus_catalog: bool = False
    # Additional metadata
    language: str | None = None
    publisher_name: str | None = None
    summary: str | None = None

    model_config = {"extra": "ignore"}

    @property
    def runtime_hours(self) -> float | None:
        """Runtime in hours."""
        if self.runtime_minutes:
            return round(self.runtime_minutes / 60, 2)
        return None


class AudibleSeriesInfo(BaseModel):
    """Series information from Audible catalog."""

    asin: str | None = None
    title: str
    url: str | None = None
    book_count: int | None = None
    books: list[AudibleSeriesBook] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class MatchResult(BaseModel):
    """Result of matching a single ABS book to Audible."""

    abs_book: ABSSeriesBook
    audible_book: AudibleSeriesBook | None = None
    match_score: float = 0.0  # 0-100
    confidence: MatchConfidence = MatchConfidence.NO_MATCH
    matched_by: str | None = None  # "asin", "title", "title+author"


class MissingBook(BaseModel):
    """A book from Audible that's missing from ABS."""

    asin: str
    title: str
    subtitle: str | None = None
    sequence: str | None = None
    author_name: str | None = None
    narrator_name: str | None = None
    runtime_hours: float | None = None
    release_date: str | None = None
    # Pricing/availability
    price: float | None = None
    is_in_plus_catalog: bool = False
    audible_url: str | None = None
    # Additional metadata for richer display
    language: str | None = None
    publisher_name: str | None = None
    summary: str | None = None  # Short description

    model_config = {"extra": "ignore"}


class SeriesMatchResult(BaseModel):
    """Result of matching an ABS series to Audible."""

    abs_series: ABSSeriesInfo
    audible_series: AudibleSeriesInfo | None = None
    name_match_score: float = 0.0  # 0-100
    confidence: MatchConfidence = MatchConfidence.NO_MATCH


class SeriesComparisonResult(BaseModel):
    """Complete comparison of ABS series vs Audible series."""

    # Series info
    series_match: SeriesMatchResult

    # Book-level analysis
    matched_books: list[MatchResult] = Field(default_factory=list)
    missing_books: list[MissingBook] = Field(default_factory=list)

    # Summary stats
    abs_book_count: int = 0
    audible_book_count: int = 0
    matched_count: int = 0
    missing_count: int = 0

    # Warnings for data quality issues
    warnings: list[str] = Field(default_factory=list)

    # Calculated at creation time
    analyzed_at: datetime = Field(default_factory=_utcnow)

    model_config = {"extra": "ignore"}

    @property
    def completion_percentage(self) -> float:
        """Percentage of Audible series owned."""
        if self.audible_book_count == 0:
            return 100.0 if self.abs_book_count > 0 else 0.0
        return round((self.matched_count / self.audible_book_count) * 100, 1)

    @property
    def is_complete(self) -> bool:
        """Whether all Audible books are owned."""
        return self.missing_count == 0

    @property
    def total_missing_hours(self) -> float:
        """Total hours of missing content."""
        return sum(b.runtime_hours or 0 for b in self.missing_books)


class SeriesAnalysisReport(BaseModel):
    """Full report of series analysis across a library."""

    library_id: str
    library_name: str | None = None
    analyzed_at: datetime = Field(default_factory=_utcnow)

    # Results
    series_results: list[SeriesComparisonResult] = Field(default_factory=list)

    # Summary
    total_series: int = 0
    series_matched: int = 0
    series_complete: int = 0
    total_missing_books: int = 0
    total_missing_hours: float = 0.0

    model_config = {"extra": "ignore"}

    @property
    def incomplete_series(self) -> list[SeriesComparisonResult]:
        """Get series with missing books."""
        return [s for s in self.series_results if not s.is_complete]

    @property
    def completion_rate(self) -> float:
        """Overall series completion rate."""
        if self.total_series == 0:
            return 0.0
        return round((self.series_complete / self.total_series) * 100, 1)
