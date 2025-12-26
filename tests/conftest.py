"""Pytest configuration and shared fixtures."""

from pathlib import Path
from typing import Any, NoReturn
from unittest.mock import MagicMock

import httpx
import pytest

from src.abs.client import ABSClient
from src.audible.client import AudibleClient


@pytest.fixture
def test_data_dir() -> Path:
    """Path to test data directory."""
    return Path(__file__).parent / "data"


# ============================================================================
# ABS Client Mocks
# ============================================================================


@pytest.fixture
def mock_abs_client() -> ABSClient:
    """Mock ABS client for testing without network calls (success path)."""
    client = MagicMock(spec=ABSClient)
    client.get_libraries.return_value = []
    client.get_library_items.return_value = []
    return client


@pytest.fixture
def mock_abs_client_conn_error() -> ABSClient:
    """
    Mock ABS client that raises connection/timeout errors.

    Simulates network failures when attempting to connect to ABS server.
    All methods raise httpx.ConnectError.
    """
    client = MagicMock(spec=ABSClient)
    client.get_libraries.side_effect = httpx.ConnectError("Connection refused")
    client.get_library_items.side_effect = httpx.ConnectError("Connection refused")
    client.get_item.side_effect = httpx.ConnectError("Connection refused")
    client._get.side_effect = httpx.ConnectError("Connection refused")
    return client


@pytest.fixture
def mock_abs_client_timeout() -> ABSClient:
    """
    Mock ABS client that raises timeout errors.

    Simulates slow/unresponsive ABS server.
    All methods raise httpx.TimeoutException.
    """
    client = MagicMock(spec=ABSClient)
    client.get_libraries.side_effect = httpx.TimeoutException("Request timeout")
    client.get_library_items.side_effect = httpx.TimeoutException("Request timeout")
    client.get_item.side_effect = httpx.TimeoutException("Request timeout")
    return client


@pytest.fixture
def mock_abs_client_malformed_response() -> ABSClient:
    """
    Mock ABS client that returns malformed/incomplete data structures.

    Returns data missing required fields or with incorrect types.
    - get_libraries: returns dict instead of list
    - get_library_items: returns items with missing 'id' field
    - get_item: returns None or incomplete item structure
    """
    client = MagicMock(spec=ABSClient)
    client.get_libraries.return_value = {"error": "malformed"}  # Should be list
    client.get_library_items.return_value = [
        {"name": "Item1"},  # Missing 'id'
        {"id": None, "name": "Item2"},  # None id
    ]
    client.get_item.return_value = None
    return client


@pytest.fixture
def mock_abs_client_empty_and_rate_limited() -> ABSClient:
    """
    Mock ABS client that returns empty results and rate limit errors.

    - Initial calls return empty lists
    - Subsequent calls raise HTTPStatusError (429 Too Many Requests)
    """
    client = MagicMock(spec=ABSClient)

    # First call returns empty, second call raises rate limit
    def rate_limited_libraries() -> NoReturn:
        response = MagicMock()
        response.status_code = 429
        response.text = "Rate limit exceeded"
        raise httpx.HTTPStatusError("429 Too Many Requests", request=MagicMock(), response=response)

    client.get_libraries.side_effect = [[], rate_limited_libraries()]
    client.get_library_items.return_value = []
    return client


@pytest.fixture
def mock_abs_client_auth_error() -> ABSClient:
    """
    Mock ABS client that raises authentication errors.

    Simulates invalid API token or expired session.
    All methods raise HTTPStatusError with 401 Unauthorized.
    """
    client = MagicMock(spec=ABSClient)

    def auth_error() -> NoReturn:
        response = MagicMock()
        response.status_code = 401
        response.text = "Unauthorized"
        raise httpx.HTTPStatusError("401 Unauthorized", request=MagicMock(), response=response)

    client.get_libraries.side_effect = auth_error
    client.get_library_items.side_effect = auth_error
    client.get_item.side_effect = auth_error
    return client


# ============================================================================
# Audible Client Mocks
# ============================================================================


@pytest.fixture
def mock_audible_client() -> AudibleClient:
    """Mock Audible client for testing without network calls (success path)."""
    client = MagicMock(spec=AudibleClient)
    return client


@pytest.fixture
def mock_audible_client_conn_error() -> AudibleClient:
    """
    Mock Audible client that raises connection/timeout errors.

    Simulates network failures when attempting to connect to Audible API.
    All methods raise httpx.ConnectError.
    """
    client = MagicMock(spec=AudibleClient)
    client.get_product.side_effect = httpx.ConnectError("Connection refused")
    client.get_library.side_effect = httpx.ConnectError("Connection refused")
    return client


@pytest.fixture
def mock_audible_client_timeout() -> AudibleClient:
    """
    Mock Audible client that raises timeout errors.

    Simulates slow/unresponsive Audible API.
    All methods raise httpx.TimeoutException.
    """
    client = MagicMock(spec=AudibleClient)
    client.get_product.side_effect = httpx.TimeoutException("Request timeout")
    client.get_library.side_effect = httpx.TimeoutException("Request timeout")
    return client


@pytest.fixture
def mock_audible_client_malformed_response() -> AudibleClient:
    """
    Mock Audible client that returns malformed/incomplete product data.

    Returns data missing required fields (asin, title, price) or with incorrect types.
    """
    client = MagicMock(spec=AudibleClient)
    client.get_product.return_value = {
        # Missing 'asin', 'title', 'price' fields
        "authors": [],
        "invalid_field": "test",
    }
    client.get_library.return_value = {"items": None}  # Should be list
    return client


@pytest.fixture
def mock_audible_client_empty_and_rate_limited() -> AudibleClient:
    """
    Mock Audible client that returns empty results and rate limit errors.

    - Initial calls return empty/None
    - Subsequent calls raise HTTPStatusError (429 Too Many Requests)
    """
    client = MagicMock(spec=AudibleClient)

    def rate_limited() -> NoReturn:
        response = MagicMock()
        response.status_code = 429
        response.text = "Rate limit exceeded"
        raise httpx.HTTPStatusError("429 Too Many Requests", request=MagicMock(), response=response)

    client.get_product.side_effect = [None, rate_limited()]
    client.get_library.return_value = {"items": []}
    return client


@pytest.fixture
def mock_audible_client_auth_error() -> AudibleClient:
    """
    Mock Audible client that raises authentication errors.

    Simulates invalid/expired Audible auth tokens.
    All methods raise HTTPStatusError with 401 Unauthorized.
    """
    client = MagicMock(spec=AudibleClient)

    def auth_error() -> NoReturn:
        response = MagicMock()
        response.status_code = 401
        response.text = "Unauthorized - Invalid or expired token"
        raise httpx.HTTPStatusError("401 Unauthorized", request=MagicMock(), response=response)

    client.get_product.side_effect = auth_error
    client.get_library.side_effect = auth_error
    return client


@pytest.fixture
def sample_library_item() -> dict:
    """Sample ABS library item for testing (expanded format)."""
    return {
        "id": "test-item-123",
        "ino": "123456",
        "libraryId": "lib-001",
        "path": "/audiobooks/Test Author/Test Audiobook",
        "size": 100000000,
        "media": {
            "metadata": {
                "title": "Test Audiobook",
                "subtitle": None,
                "authorName": "Test Author",
                "narratorName": "Test Narrator",
                "seriesName": None,
                "genres": ["Fiction"],
                "publishedYear": "2023",
                "publisher": "Test Publisher",
                "description": "A test audiobook.",
                "isbn": None,
                "asin": "B0TEST12345",
                "language": "English",
                "explicit": False,
            },
            "audioFiles": [
                {
                    "ino": "789",
                    "metadata": {
                        "filename": "test.m4b",
                        "ext": ".m4b",
                        "path": "/audiobooks/test/test.m4b",
                        "size": 100000000,
                    },
                    "duration": 36000,
                    "format": "M4B",
                    "codec": "aac",
                    "bitRate": 128000,
                    "channels": 2,
                    "sampleRate": 44100,
                    "mimeType": "audio/mp4",
                }
            ],
            "chapters": [],
            "duration": 36000,
            "ebookFile": None,
        },
        "mediaType": "book",
        "addedAt": 1700000000000,
        "updatedAt": 1700000000000,
    }


@pytest.fixture
def sample_audible_product() -> dict:
    """Sample Audible product API response."""
    return {
        "asin": "B0TEST12345",
        "title": "Test Audiobook",
        "authors": [{"name": "Test Author", "asin": "B0AUTHOR01"}],
        "narrators": [{"name": "Test Narrator"}],
        "runtime_length_min": 600,
        "release_date": "2023-01-15",
        "publisher_name": "Test Publisher",
        "product_images": {
            "500": "https://example.com/cover.jpg",
        },
        "is_purchasability_suppressed": False,
        "plans": [],
        "price": {
            "lowest_price": {
                "base": 29.99,
                "type": "member",
            },
            "list_price": {
                "base": 39.99,
            },
        },
        "available_codecs": [
            {"name": "aax_22_32", "enhanced_codec": "LC"},
            {"name": "aax_44_128", "enhanced_codec": "LC"},
        ],
    }
