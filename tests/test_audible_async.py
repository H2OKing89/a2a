"""Tests for async Audible client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.audible.async_client import AsyncAudibleClient, AsyncAudibleError


class TestAsyncAudibleClient:
    """Test AsyncAudibleClient initialization and basic operations."""

    @pytest.fixture
    def mock_auth(self):
        """Mock Audible authenticator."""
        auth = MagicMock()
        auth.locale.country_code = "us"
        return auth

    @pytest.fixture
    def mock_async_client(self):
        """Mock audible.AsyncClient."""
        with patch("src.audible.async_client.audible.AsyncClient") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_client_initialization(self, mock_auth, mock_async_client):
        """Test client can be initialized with auth."""
        client = AsyncAudibleClient(auth=mock_auth)
        assert client.auth == mock_auth
        assert client.max_concurrent == 5

    @pytest.mark.asyncio
    async def test_client_initialization_custom_concurrency(self, mock_auth):
        """Test client initialization with custom max_concurrent."""
        client = AsyncAudibleClient(auth=mock_auth, max_concurrent=10)
        assert client.max_concurrent == 10

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
    async def test_get_library_basic(self, mock_auth):
        """Test get_library returns items from API."""
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
                assert "items" in result
                assert len(result["items"]) == 2

    @pytest.mark.asyncio
    async def test_get_multiple_products(self, mock_auth):
        """Test batch fetching multiple products."""
        asins = ["B001", "B002", "B003"]
        mock_responses = [{"product": {"asin": asin, "title": f"Book {asin}"}} for asin in asins]

        with patch("src.audible.async_client.audible.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)

            # Mock get to return different response for each ASIN
            async def mock_get(path, **kwargs):
                for asin, resp in zip(asins, mock_responses):
                    if asin in path:
                        return resp
                return {}

            mock_instance.get = AsyncMock(side_effect=mock_get)
            mock_client_class.return_value = mock_instance

            async with AsyncAudibleClient(auth=mock_auth, max_concurrent=2) as client:
                results = await client.get_multiple_products(asins)

                assert len(results) == 3
                assert all("product" in r for r in results)

    @pytest.mark.asyncio
    async def test_get_multiple_products_with_errors(self, mock_auth):
        """Test batch fetching handles errors gracefully."""
        asins = ["B001", "B002", "B003"]

        with patch("src.audible.async_client.audible.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)

            # Second request fails
            async def mock_get(path, **kwargs):
                if "B002" in path:
                    raise AsyncAudibleError("Not found")
                asin = path.split("/")[-1].split("?")[0]
                return {"product": {"asin": asin, "title": f"Book {asin}"}}

            mock_instance.get = AsyncMock(side_effect=mock_get)
            mock_client_class.return_value = mock_instance

            async with AsyncAudibleClient(auth=mock_auth) as client:
                results = await client.get_multiple_products(asins)

                # Should return results for successful requests
                assert len(results) == 2  # B001 and B003
                assert all("product" in r for r in results)

    @pytest.mark.asyncio
    async def test_rate_limiting(self, mock_auth):
        """Test that semaphore limits concurrent requests."""
        asins = [f"B{i:03d}" for i in range(10)]
        call_count = {"current": 0, "max": 0}

        with patch("src.audible.async_client.audible.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)

            async def mock_get(path, **kwargs):
                call_count["current"] += 1
                call_count["max"] = max(call_count["max"], call_count["current"])
                await asyncio.sleep(0.01)  # Simulate API delay
                asin = path.split("/")[-1].split("?")[0]
                result = {"product": {"asin": asin}}
                call_count["current"] -= 1
                return result

            mock_instance.get = AsyncMock(side_effect=mock_get)
            mock_client_class.return_value = mock_instance

            max_concurrent = 3
            async with AsyncAudibleClient(auth=mock_auth, max_concurrent=max_concurrent) as client:
                results = await client.get_multiple_products(asins)

                assert len(results) == 10
                # Verify we never exceeded max_concurrent
                assert call_count["max"] <= max_concurrent

    @pytest.mark.asyncio
    async def test_get_wishlist(self, mock_auth):
        """Test get_wishlist returns wishlist items."""
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
                assert "products" in result

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
                # Should return False when no codec info (simplified mock)
                result = await client.supports_dolby_atmos("B001")
                assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_client_without_auth_from_file(self):
        """Test client initialization from auth file."""
        with patch("src.audible.async_client.Authenticator") as mock_auth_class:
            mock_auth = MagicMock()
            mock_auth_class.from_file.return_value = mock_auth

            client = AsyncAudibleClient(auth_file="test.json")
            assert client.auth == mock_auth
            mock_auth_class.from_file.assert_called_once_with("test.json")
