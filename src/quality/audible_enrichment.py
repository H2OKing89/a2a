"""
Audible enrichment for quality upgrade candidates.

DEPRECATED: This module has been moved to src/audible/enrichment.py
This file re-exports for backwards compatibility.

Please update imports to use:
    from src.audible.enrichment import AudibleEnrichment, AudibleEnrichmentService
    from src.audible.models import PricingInfo, PlusCatalogInfo
"""

import warnings

# Re-export from new locations for backwards compatibility
from ..audible import AudibleEnrichment, AudibleEnrichmentService, PlusCatalogInfo, PricingInfo

__all__ = [
    "PricingInfo",
    "PlusCatalogInfo",
    "AudibleEnrichment",
    "AudibleEnrichmentService",
]

# Emit deprecation warning on import
warnings.warn(
    "src.quality.audible_enrichment is deprecated. "
    "Import from src.audible.enrichment and src.audible.models instead.",
    DeprecationWarning,
    stacklevel=2,
)
