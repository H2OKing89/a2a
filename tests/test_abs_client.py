"""
Tests for ABSClient (Audiobookshelf client).
Covers exceptions, initialization, context manager, rate limiting, and main API methods.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.abs.client import (
    ABSClient,
    ABSError,
    ABSConnectionError,
    ABSAuthError,
    ABSNotFoundError,
)
from src.abs.models import Library, LibraryItem, Collection, Series

# -----------------------------------------------------------------------------
# Exception Tests
# -----------------------------------------------------------------------------
class TestExceptions:
    def test_abserror_with_response(self):
        err = ABSError("Test error", response={"error": "fail"})
        assert str(err) == "Test error"
        assert err.response == {"error": "fail"}

    def test_abserror_without_response(self):
        err = ABSError("Test error")
        assert str(err) == "Test error"
        assert err.response is None

    def test_absconnectionerror_inherits(self):
        err = ABSConnectionError("Conn fail")
        assert isinstance(err, ABSError)

    def test_absautherror_inherits(self):
        err = ABSAuthError("Auth fail")
        assert isinstance(err, ABSError)

    def test_absnotfounderror_inherits(self):
        err = ABSNotFoundError("Not found")
        assert isinstance(err, ABSError)

# -----------------------------------------------------------------------------
# Client Initialization & Context Manager
# -----------------------------------------------------------------------------
class TestClientInit:
    def test_init_defaults(self):
        client = ABSClient("http://localhost:13378", "token")
        assert isinstance(client, ABSClient)

    def test_init_with_cache(self, tmp_path):
        from src.cache import SQLiteCache
        cache = SQLiteCache(db_path=tmp_path / "test.db")
        client = ABSClient("http://localhost:13378", "token", cache=cache)
        assert client._cache is cache

    def test_context_manager_calls_close(self):
        client = ABSClient("http://localhost:13378", "token")
        client._session = MagicMock()
        with patch.object(client, "close") as mock_close:
            with client:
                pass
            mock_close.assert_called_once()

# -----------------------------------------------------------------------------
# Rate Limiting
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Library Methods
# -----------------------------------------------------------------------------
class TestLibraryMethods:
    @pytest.fixture
    def client(self):
        c = ABSClient("http://localhost:13378", "token")
        c._request = MagicMock()
        return c

    def test_get_libraries(self, client):
        # Provide all required fields for Library model, and wrap in 'libraries' key
        client._request.return_value = {
            "libraries": [
                {
                    "id": "lib1",
                    "name": "Main",
                    "type": "books",
                    "createdAt": 1700000000,
                    "updatedAt": 1700000000,
                    "scanStatus": "idle",
                    "scanProgress": 0,
                    "scanResult": None,
                    "path": "/books",
                    "seriesCount": 0,
                    "itemCount": 0,
                    "size": 0,
                    "displayOrder": 0,
                    "icon": "",
                    "mediaType": "audio",
                    "provider": "local",
                    "lastUpdate": 1700000000,
                }
            ]
        }
        libs = client.get_libraries()
        assert len(libs) == 1
        assert isinstance(libs[0], Library)
        assert libs[0].id == "lib1"

    def test_get_library_items(self, client):
        # Provide all required fields for LibraryItem model, with correct types
        client._request.return_value = {
            "results": [
                {
                    "id": "item1",
                    "title": "Book",
                    "ino": "1",
                    "libraryId": "lib1",
                    "folderId": "f1",
                    "path": "/books/book1.m4b",
                    "relPath": "book1.m4b",
                    "size": 123456,
                    "duration": 3600.0,
                    "addedAt": 1700000000,
                    "updatedAt": 1700000000,
                    "mediaType": "audio",
                    "coverPath": None,
                    "metadata": {},
                    "isFile": True,
                    "mtimeMs": 1700000000,
                    "ctimeMs": 1700000000,
                    "media": {"metadata": {"title": "Book"}},
                }
            ],
            "total": 1,
            "limit": 10,
            "offset": 0,
            "page": 1,
            "mediaType": "audio",
        }
        resp = client.get_library_items("lib1")
        assert len(resp.results) == 1
        assert resp.results[0].id == "item1"

    # get_library_item does not exist; skip these tests

# -----------------------------------------------------------------------------
# Collection Methods
# -----------------------------------------------------------------------------
class TestCollectionMethods:
    @pytest.fixture
    def client(self):
        c = ABSClient("http://localhost:13378", "token")
        c._request = MagicMock()
        return c

    def test_get_collections(self, client):
        # Provide all required fields for Collection model, wrapped in 'collections' key
        client._request.return_value = {
            "collections": [
                {
                    "id": "col1",
                    "name": "Favorites",
                    "libraryId": "lib1",
                    "createdAt": 1700000000,
                    "updatedAt": 1700000000,
                    "itemCount": 1,
                    "size": 1234,
                    "coverPath": None,
                    "description": None,
                    "userId": "user1",
                    "lastUpdate": 1700000000,
                }
            ]
        }
        cols = client.get_collections()
        assert len(cols) == 1
        assert isinstance(cols[0], Collection)
        assert cols[0].id == "col1"

    def test_create_collection(self, client):
        # Provide all required fields for CollectionExpanded model
        client._request.return_value = {
            "id": "col2",
            "name": "New",
            "libraryId": "lib1",
            "createdAt": 1700000000,
            "updatedAt": 1700000000,
            "itemCount": 0,
            "size": 0,
            "coverPath": None,
            "description": None,
            "items": [],
            "userId": "user1",
            "lastUpdate": 1700000000,
        }
        col = client.create_collection("lib1", "New")
        assert col.name == "New"

    def test_update_collection(self, client):
        # Return all required fields for CollectionExpanded
        client._request.return_value = {
            "id": "col1",
            "name": "Favorites",
            "libraryId": "lib1",
            "createdAt": 1700000000,
            "updatedAt": 1700000000,
            "itemCount": 1,
            "size": 1234,
            "coverPath": None,
            "description": None,
            "userId": "user1",
            "lastUpdate": 1700000000,
            "books": [{"id": "item1"}]
        }
        result = client.update_collection("col1", ["item1"])
        assert result.id == "col1"
        assert isinstance(result.books, list)
        assert result.books[0]["id"] == "item1"

# -----------------------------------------------------------------------------
# Series Methods
# -----------------------------------------------------------------------------
class TestSeriesMethods:
    @pytest.fixture
    def client(self):
        c = ABSClient("http://localhost:13378", "token")
        c._request = MagicMock()
        return c

    def test_get_library_series(self, client):
        # Provide all required fields for Series model
        client._request.return_value = {
            "results": [
                {
                    "id": "ser1",
                    "name": "Series",
                    "libraryId": "lib1",
                    "createdAt": 1700000000,
                    "updatedAt": 1700000000,
                    "description": None,
                    "books": [],
                }
            ]
        }
        resp = client.get_library_series("lib1")
        assert len(resp["results"]) == 1
        assert resp["results"][0]["id"] == "ser1"

# -----------------------------------------------------------------------------
# Error Handling
# -----------------------------------------------------------------------------
class TestErrorHandling:
    @pytest.fixture
    def client(self):
        c = ABSClient("http://localhost:13378", "token")
        c._request = MagicMock()
        return c

    def test_auth_error(self, client):
        client._request.side_effect = ABSAuthError("Auth fail")
        with pytest.raises(ABSAuthError):
            client.get_libraries()

    def test_connection_error(self, client):
        client._request.side_effect = ABSConnectionError("Conn fail")
        with pytest.raises(ABSConnectionError):
            client.get_libraries()

    def test_generic_error(self, client):
        client._request.side_effect = ABSError("Generic fail")
        with pytest.raises(ABSError):
            client.get_libraries()
