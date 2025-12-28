"""
Audiobookshelf API client module.
"""

from .async_client import AsyncABSClient
from .client import ABSAuthError, ABSClient, ABSConnectionError, ABSError, ABSNotFoundError
from .logging import LogContext, configure_logging, enable_debug_logging, get_logger, set_level
from .models import (
    AudioFile,
    Author,
    AuthorSearchResponse,
    AuthorSearchResult,
    BookMetadata,
    BookSearchResult,
    Collection,
    CollectionExpanded,
    Library,
    LibraryItem,
    LibraryItemExpanded,
    LibraryItemMinified,
    SearchResponse,
    SearchResultBook,
    Series,
    SeriesListResponse,
    SeriesProgress,
    SeriesResponse,
    SeriesWithBooks,
)

__all__ = [
    # Clients
    "ABSClient",
    "AsyncABSClient",
    # Exceptions
    "ABSError",
    "ABSAuthError",
    "ABSConnectionError",
    "ABSNotFoundError",
    # Models
    "Library",
    "LibraryItem",
    "LibraryItemMinified",
    "LibraryItemExpanded",
    "BookMetadata",
    "AudioFile",
    "Author",
    "Series",
    "Collection",
    "CollectionExpanded",
    "SeriesProgress",
    # Response models
    "SeriesListResponse",
    "SeriesWithBooks",
    "SearchResponse",
    "SearchResultBook",
    "SeriesResponse",
    "AuthorSearchResponse",
    "AuthorSearchResult",
    "BookSearchResult",
    # Logging
    "configure_logging",
    "get_logger",
    "set_level",
    "enable_debug_logging",
    "LogContext",
]
