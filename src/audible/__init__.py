"""
Audible API client module.
"""

from .cache import AudibleCache
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
    "AudibleCache",
]
