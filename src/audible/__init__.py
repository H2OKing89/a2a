"""
Audible API client module.
"""

from .client import AudibleClient, AudibleError, AudibleAuthError, AudibleNotFoundError
from .models import (
    AudibleBook,
    AudibleAuthor,
    AudibleNarrator,
    AudibleSeries,
    AudibleLibraryItem,
    AudibleLibraryResponse,
    AudibleCatalogProduct,
)
from .cache import AudibleCache

__all__ = [
    "AudibleClient",
    "AudibleError",
    "AudibleAuthError",
    "AudibleNotFoundError",
    "AudibleBook",
    "AudibleAuthor",
    "AudibleNarrator",
    "AudibleSeries",
    "AudibleLibraryItem",
    "AudibleLibraryResponse",
    "AudibleCatalogProduct",
    "AudibleCache",
]
