"""
Audible API client module.
"""

from .client import AudibleAuthError, AudibleClient, AudibleError, AudibleNotFoundError
from .models import (
    AudibleAuthor,
    AudibleBook,
    AudibleCatalogProduct,
    AudibleLibraryItem,
    AudibleLibraryResponse,
    AudibleNarrator,
    AudibleSeries,
)

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
]
