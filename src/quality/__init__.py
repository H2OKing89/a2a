"""
Audio quality analysis module.

Provides quality scoring and tier classification for audiobooks.
"""

# Re-export from new audible module for backwards compatibility (no warning)
from ..audible.enrichment import AudibleEnrichment, AudibleEnrichmentService
from ..audible.models import PlusCatalogInfo, PricingInfo
from .analyzer import QualityAnalyzer
from .models import AudioQuality, FormatRank, QualityReport, QualityTier

__all__ = [
    "QualityTier",
    "FormatRank",
    "AudioQuality",
    "QualityReport",
    "QualityAnalyzer",
    "PricingInfo",
    "PlusCatalogInfo",
    "AudibleEnrichment",
    "AudibleEnrichmentService",
]
