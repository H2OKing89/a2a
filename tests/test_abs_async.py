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

    def test_client_has_rate_lock(self):
        """Test client initializes with rate lock for thread safety."""
        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
        )

        import asyncio

        assert hasattr(client, "_rate_lock")
        assert isinstance(client._rate_lock, asyncio.Lock)

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


class TestAsyncABSClientCaching:
    """Test async client caching behavior."""

    @pytest.mark.asyncio
    async def test_get_library_stats_uses_cache(self):
        """Test get_library_stats uses cache."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = {
            "totalItems": 100,
            "totalAuthors": 50,
            "totalGenres": 10,
            "totalDuration": 360000,
            "numAudioTracks": 100,
            "totalSize": 1024000000,
        }

        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
            cache=mock_cache,
        )

        stats = await client.get_library_stats("lib_1", use_cache=True)

        assert stats.total_items == 100
        mock_cache.get.assert_called_once_with("abs_stats", "stats_lib_1")
        await client.close()

    @pytest.mark.asyncio
    async def test_get_library_stats_bypasses_cache(self):
        """Test get_library_stats can bypass cache."""
        mock_cache = MagicMock()

        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
            cache=mock_cache,
        )

        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "totalItems": 100,
                "totalAuthors": 50,
                "totalGenres": 10,
                "totalDuration": 360000,
                "numAudioTracks": 100,
                "totalSize": 1024000000,
            }

            stats = await client.get_library_stats("lib_1", use_cache=False)

            assert stats.total_items == 100
            mock_cache.get.assert_not_called()
            mock_get.assert_called_once()

        await client.close()

    @pytest.mark.asyncio
    async def test_get_library_stats_sets_cache(self):
        """Test get_library_stats sets cache after fetch."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = None  # Cache miss

        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
            cache=mock_cache,
            cache_ttl_hours=2.0,
        )

        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "totalItems": 100,
                "totalAuthors": 50,
                "totalGenres": 10,
                "totalDuration": 360000,
                "numAudioTracks": 100,
                "totalSize": 1024000000,
            }

            await client.get_library_stats("lib_1", use_cache=True)

            # Check cache.set was called with TTL
            mock_cache.set.assert_called_once()
            call_args = mock_cache.set.call_args
            assert call_args[0][0] == "abs_stats"
            assert call_args[0][1] == "stats_lib_1"
            assert call_args[1]["ttl_seconds"] == 7200  # 2 hours

        await client.close()

    @pytest.mark.asyncio
    async def test_get_item_uses_cache(self):
        """Test get_item uses cache."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = {
            "id": "item_1",
            "ino": "123",
            "libraryId": "lib_1",
            "folderId": "folder_1",
            "path": "/audiobooks/test",
            "relPath": "test",
            "isFile": False,
            "mtimeMs": 1234567890000,
            "ctimeMs": 1234567890000,
            "birthtimeMs": 1234567890000,
            "addedAt": 1234567890000,
            "updatedAt": 1234567890000,
            "mediaType": "book",
            "media": {
                "id": "media_1",
                "metadata": {"title": "Test Book"},
                "coverPath": None,
                "tags": [],
            },
        }

        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
            cache=mock_cache,
        )

        item = await client.get_item("item_1", use_cache=True)

        assert item.id == "item_1"
        mock_cache.get.assert_called_once_with("abs_items", "item_item_1_expTrue")
        await client.close()

    @pytest.mark.asyncio
    async def test_get_item_no_cache_when_include(self):
        """Test get_item doesn't use cache when include is specified."""
        mock_cache = MagicMock()

        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
            cache=mock_cache,
        )

        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "id": "item_1",
                "ino": "123",
                "libraryId": "lib_1",
                "folderId": "folder_1",
                "path": "/audiobooks/test",
                "relPath": "test",
                "isFile": False,
                "mtimeMs": 1234567890000,
                "ctimeMs": 1234567890000,
                "birthtimeMs": 1234567890000,
                "addedAt": 1234567890000,
                "updatedAt": 1234567890000,
                "mediaType": "book",
                "media": {
                    "id": "media_1",
                    "metadata": {"title": "Test Book"},
                    "coverPath": None,
                    "tags": [],
                },
            }

            await client.get_item("item_1", include="progress", use_cache=True)

            # Cache should not be used when include is specified
            mock_cache.get.assert_not_called()
            mock_cache.set.assert_not_called()

        await client.close()

    @pytest.mark.asyncio
    async def test_get_author_with_items_uses_cache(self):
        """Test get_author_with_items uses cache."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = {
            "id": "author_1",
            "name": "Test Author",
            "libraryItems": [{"id": "item_1"}],
            "series": [{"id": "series_1"}],
        }

        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
            cache=mock_cache,
        )

        author = await client.get_author_with_items("author_1", use_cache=True)

        assert author["id"] == "author_1"
        mock_cache.get.assert_called_once_with("abs_authors", "author_items_author_1_True")
        await client.close()

    @pytest.mark.asyncio
    async def test_get_series_with_progress_uses_cache(self):
        """Test get_series_with_progress uses cache."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = {
            "id": "series_1",
            "name": "Test Series",
            "progress": {"finishedCount": 5},
        }

        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
            cache=mock_cache,
        )

        series = await client.get_series_with_progress("series_1", use_cache=True)

        assert series["id"] == "series_1"
        mock_cache.get.assert_called_once_with("abs_series", "series_progress_series_1")
        await client.close()

    @pytest.mark.asyncio
    async def test_no_cache_when_none(self):
        """Test methods work without cache."""
        client = AsyncABSClient(
            host="https://abs.example.com",
            api_key="test_key",
            cache=None,  # No cache
        )

        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "totalItems": 100,
                "totalAuthors": 50,
                "totalGenres": 10,
                "totalDuration": 360000,
                "numAudioTracks": 100,
                "totalSize": 1024000000,
            }

            # Should not raise, just fetch directly
            stats = await client.get_library_stats("lib_1")
            assert stats.total_items == 100

        await client.close()
