"""Tests for async Audible client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.audible.async_client import AsyncAudibleAuthError, AsyncAudibleClient, AsyncAudibleError


class TestAsyncAudibleClient:
    """Test AsyncAudibleClient initialization and basic operations."""

    @pytest.fixture
    def mock_auth(self):
        """Mock Audible authenticator."""
        auth = MagicMock()
        auth.locale.country_code = "us"
        return auth

    @pytest.mark.asyncio
    async def test_client_initialization(self, mock_auth):
        """Test client can be initialized with auth."""
        client = AsyncAudibleClient(auth=mock_auth)
        # The client stores auth as _auth (private)
        assert client._auth == mock_auth
        # Default max concurrent is 5
        assert client._semaphore._value == 5

    @pytest.mark.asyncio
    async def test_client_initialization_custom_concurrency(self, mock_auth):
        """Test client initialization with custom max_concurrent_requests."""
        client = AsyncAudibleClient(auth=mock_auth, max_concurrent_requests=10)
        assert client._semaphore._value == 10

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_auth):
        """Test async context manager protocol."""
        with patch("src.audible.async_client.audible.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_instance

            async with AsyncAudibleClient(auth=mock_auth) as client:
                assert client is not None
                assert isinstance(client, AsyncAudibleClient)

            # Verify __aexit__ was called
            mock_instance.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_library_returns_list(self, mock_auth):
        """Test get_library returns list of AudibleLibraryItem."""
        mock_response = {
            "items": [
                {"asin": "B001", "title": "Book 1"},
                {"asin": "B002", "title": "Book 2"},
            ]
        }

        with patch("src.audible.async_client.audible.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_instance

            async with AsyncAudibleClient(auth=mock_auth) as client:
                result = await client.get_library()
                # Returns a list of AudibleLibraryItem, not raw dict
                assert isinstance(result, list)
                assert len(result) == 2
                assert result[0].asin == "B001"
                assert result[1].asin == "B002"

    @pytest.mark.asyncio
    async def test_get_wishlist_returns_list(self, mock_auth):
        """Test get_wishlist returns list of WishlistItem."""
        mock_response = {
            "products": [
                {"asin": "B001", "title": "Wishlist Book 1"},
            ]
        }

        with patch("src.audible.async_client.audible.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_instance

            async with AsyncAudibleClient(auth=mock_auth) as client:
                result = await client.get_wishlist()
                # Returns list of WishlistItem
                assert isinstance(result, list)
                assert len(result) == 1
                assert result[0].asin == "B001"

    @pytest.mark.asyncio
    async def test_supports_dolby_atmos(self, mock_auth):
        """Test Dolby Atmos detection."""
        mock_metadata = {
            "content_delivery_type": "MultiPartBook",
            "content_metadata": {
                "chapter_info": {
                    "runtime_length_ms": 1000,
                    "content_reference": {"content_format": "MP4", "content_id": "123"},
                }
            },
        }

        with patch("src.audible.async_client.audible.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.get = AsyncMock(return_value=mock_metadata)
            mock_client_class.return_value = mock_instance

            async with AsyncAudibleClient(auth=mock_auth) as client:
                result = await client.supports_dolby_atmos("B001")
                assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_client_from_file_missing(self, tmp_path):
        """Test client creation from auth file using from_file class method."""
        auth_file = tmp_path / "nonexistent.json"

        with pytest.raises(AsyncAudibleAuthError, match="Auth file not found"):
            AsyncAudibleClient.from_file(str(auth_file))

    @pytest.mark.asyncio
    async def test_client_from_file_success(self):
        """Test client from_file with valid auth file."""
        with (
            patch("src.audible.async_client.Authenticator") as mock_auth_class,
            patch("src.audible.async_client.Path") as mock_path,
        ):
            mock_auth = MagicMock()
            mock_auth_class.from_file.return_value = mock_auth
            mock_path.return_value.exists.return_value = True

            client = AsyncAudibleClient.from_file("test.json")
            assert client._auth == mock_auth


class TestAsyncAudibleClientRateLimiting:
    """Test rate limiting behavior."""

    @pytest.fixture
    def mock_auth(self):
        """Mock Audible authenticator."""
        auth = MagicMock()
        auth.locale.country_code = "us"
        return auth

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent(self, mock_auth):
        """Test that semaphore limits concurrent requests."""
        max_concurrent = 3
        client = AsyncAudibleClient(auth=mock_auth, max_concurrent_requests=max_concurrent)

        assert client._semaphore._value == max_concurrent

    @pytest.mark.asyncio
    async def test_request_delay_configured(self, mock_auth):
        """Test request delay is configurable."""
        client = AsyncAudibleClient(auth=mock_auth, request_delay=0.5)
        assert client._request_delay == 0.5


class TestAsyncAudibleClientExceptions:
    """Test exception classes."""

    def test_async_audible_error(self):
        """Test AsyncAudibleError."""
        error = AsyncAudibleError("Test error", response={"error": "test"})
        assert str(error) == "Test error"
        assert error.response == {"error": "test"}

    def test_async_audible_auth_error(self):
        """Test AsyncAudibleAuthError."""
        error = AsyncAudibleAuthError("Auth failed")
        assert str(error) == "Auth failed"
        assert isinstance(error, AsyncAudibleError)
