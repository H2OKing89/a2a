"""
Series tracking and matching module.

Provides functionality to match Audiobookshelf series with Audible collections
and identify missing audiobooks.
"""

from .matcher import SeriesMatcher
from .models import (
    ABSSeriesBook,
    ABSSeriesInfo,
    AudibleSeriesBook,
    AudibleSeriesInfo,
    MatchConfidence,
    MatchResult,
    MissingBook,
    SeriesAnalysisReport,
    SeriesComparisonResult,
    SeriesMatchResult,
)

__all__ = [
    # Models
    "ABSSeriesInfo",
    "ABSSeriesBook",
    "AudibleSeriesInfo",
    "AudibleSeriesBook",
    "MatchConfidence",
    "SeriesMatchResult",
    "MatchResult",
    "MissingBook",
    "SeriesComparisonResult",
    "SeriesAnalysisReport",
    # Service
    "SeriesMatcher",
]
