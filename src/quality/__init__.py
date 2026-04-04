"""
Audio quality analysis module.

Provides quality scoring and tier classification for audiobooks.
"""

from .analyzer import QualityAnalyzer
from .models import AudioQuality, FormatRank, QualityReport, QualitySeriesEntry, QualityTier
from .services import EnrichedUpgradeCandidate, UpgradeFinderResult, UpgradeFinderService

__all__ = [
    "QualityTier",
    "FormatRank",
    "AudioQuality",
    "QualitySeriesEntry",
    "QualityReport",
    "QualityAnalyzer",
    # Services
    "UpgradeFinderService",
    "UpgradeFinderResult",
    "EnrichedUpgradeCandidate",
]
