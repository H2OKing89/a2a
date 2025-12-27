"""Tests for ABS async client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.abs.async_client import AsyncABSClient
from src.abs.client import ABSAuthError, ABSConnectionError, ABSNotFoundError


class TestAsyncABSClient:
    """Test AsyncABSClient initialization and basic methods."""

    def test_client_initialization(self):
        """Test client initializes with correct parameters."""
        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
        )

        assert client.host == "https://abs.example.com"
        assert client.api_key == "test_key"
        assert client._client is None  # Not initialized until used

    def test_client_initialization_trailing_slash(self):
        """Test host trailing slash is stripped."""
        client = AsyncABSClient(
            host="https://abs.example.com/",
            api_key="test_key",
        )

        assert client.host == "https://abs.example.com"

    def test_client_custom_concurrency(self):
        """Test custom max_concurrent_requests."""
        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
            max_concurrent_requests=10,
        )

        assert client._semaphore._value == 10

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        async with AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
        ) as client:
            assert client._client is not None

        # Client should be closed after context exit
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close(self):
        """Test explicit close."""
        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
        )
        await client._ensure_client()
        assert client._client is not None

        await client.close()
        assert client._client is None


class TestAsyncABSClientRequests:
    """Test async request handling."""

    @pytest.fixture
    def mock_response(self):
        """Create a mock response."""
        response = MagicMock()
        response.status_code = 200
        response.content = b'{"test": "data"}'
        response.json.return_value = {"test": "data"}
        return response

    @pytest.mark.asyncio
    async def test_get_libraries(self):
        """Test get_libraries returns list."""
        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
        )

        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "libraries": [
                    {
                        "id": "lib_1",
                        "name": "Main",
                        "displayOrder": 1,
                        "icon": "book",
                        "mediaType": "book",
                        "provider": "audible",
                        "createdAt": 1234567890,
                        "lastUpdate": 1234567890,
                    }
                ]
            }

            libraries = await client.get_libraries()

            assert len(libraries) == 1
            assert libraries[0].id == "lib_1"
            assert libraries[0].name == "Main"

        await client.close()

    @pytest.mark.asyncio
    async def test_get_collections(self):
        """Test get_collections returns list."""
        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
        )

        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "collections": [
                    {
                        "id": "col_1",
                        "libraryId": "lib_1",
                        "userId": "root",
                        "name": "Favorites",
                        "description": None,
                        "books": [],
                        "lastUpdate": 1234567890,
                        "createdAt": 1234567890,
                    }
                ]
            }

            collections = await client.get_collections()

            assert len(collections) == 1
            assert collections[0]["id"] == "col_1"
            assert collections[0]["name"] == "Favorites"

        await client.close()

    @pytest.mark.asyncio
    async def test_create_collection(self):
        """Test create_collection."""
        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
        )

        with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {
                "id": "col_new",
                "libraryId": "lib_1",
                "userId": "root",
                "name": "New Collection",
                "description": "Test description",
                "books": [],
                "lastUpdate": 1234567890,
                "createdAt": 1234567890,
            }

            result = await client.create_collection(
                library_id="lib_1",
                name="New Collection",
                description="Test description",
            )

            assert result["id"] == "col_new"
            assert result["name"] == "New Collection"
            mock_post.assert_called_once()

        await client.close()


class TestAsyncABSClientExceptions:
    """Test async exception classes."""

    def test_abs_connection_error(self):
        """Test ABSConnectionError."""
        error = ABSConnectionError("Connection failed")
        assert str(error) == "Connection failed"

    def test_abs_auth_error(self):
        """Test ABSAuthError."""
        error = ABSAuthError("Auth failed")
        assert str(error) == "Auth failed"

    def test_abs_not_found_error(self):
        """Test ABSNotFoundError."""
        error = ABSNotFoundError("Not found")
        assert str(error) == "Not found"
