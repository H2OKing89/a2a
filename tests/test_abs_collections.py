"""Tests for ABS collection and enhanced client methods."""

from unittest.mock import MagicMock, patch

import pytest

from src.abs.client import ABSClient
from src.abs.models import Collection, CollectionExpanded, SeriesProgress


class TestCollectionModel:
    """Test Collection model."""

    def test_collection_from_dict(self):
        """Test Collection model creation."""
        data = {
            "id": "col_1",
            "libraryId": "lib_1",
            "userId": "root",
            "name": "Favorites",
            "description": "My favorite books",
            "books": ["book_1", "book_2"],
            "lastUpdate": 1234567890,
            "createdAt": 1234567890,
        }

        collection = Collection.model_validate(data)

        assert collection.id == "col_1"
        assert collection.library_id == "lib_1"
        assert collection.name == "Favorites"
        assert collection.book_count == 2

    def test_collection_book_count(self):
        """Test book_count property."""
        collection = Collection(
            id="col_1",
            libraryId="lib_1",
            userId="root",
            name="Test",
            books=["b1", "b2", "b3"],
            lastUpdate=0,
            createdAt=0,
        )

        assert collection.book_count == 3


class TestCollectionExpandedModel:
    """Test CollectionExpanded model."""

    def test_collection_expanded_book_ids(self):
        """Test book_ids property extracts IDs from expanded books."""
        collection = CollectionExpanded(
            id="col_1",
            libraryId="lib_1",
            userId="root",
            name="Test",
            books=[
                {"id": "book_1", "title": "Book 1"},
                {"id": "book_2", "title": "Book 2"},
            ],
            lastUpdate=0,
            createdAt=0,
        )

        assert collection.book_ids == ["book_1", "book_2"]


class TestSeriesProgressModel:
    """Test SeriesProgress model."""

    def test_series_progress_from_dict(self):
        """Test SeriesProgress model creation."""
        data = {
            "libraryItemIds": ["li_1", "li_2", "li_3"],
            "libraryItemIdsFinished": ["li_1"],
            "isFinished": False,
        }

        progress = SeriesProgress.model_validate(data)

        assert progress.total_books == 3
        assert progress.finished_count == 1
        assert progress.is_finished is False

    def test_series_progress_percent(self):
        """Test progress_percent calculation."""
        progress = SeriesProgress(
            libraryItemIds=["li_1", "li_2", "li_3", "li_4"],
            libraryItemIdsFinished=["li_1", "li_2"],
            isFinished=False,
        )

        assert progress.progress_percent == 50.0

    def test_series_progress_percent_empty(self):
        """Test progress_percent with no books."""
        progress = SeriesProgress(
            libraryItemIds=[],
            libraryItemIdsFinished=[],
            isFinished=False,
        )

        assert progress.progress_percent == 0.0

    def test_series_progress_complete(self):
        """Test 100% completion."""
        progress = SeriesProgress(
            libraryItemIds=["li_1", "li_2"],
            libraryItemIdsFinished=["li_1", "li_2"],
            isFinished=True,
        )

        assert progress.progress_percent == 100.0
        assert progress.is_finished is True


class TestABSClientCollections:
    """Test ABSClient collection methods."""

    @pytest.fixture
    def mock_client(self):
        """Create ABSClient with mocked HTTP client."""
        with patch("src.abs.client.httpx.Client"):
            client = ABSClient(host="https://abs.example.com", api_key="test_key")
            return client

    def test_get_collections(self, mock_client):
        """Test get_collections method."""
        mock_client._get = MagicMock(
            return_value={
                "collections": [
                    {
                        "id": "col_1",
                        "libraryId": "lib_1",
                        "userId": "root",
                        "name": "Favorites",
                        "books": [],
                        "lastUpdate": 0,
                        "createdAt": 0,
                    }
                ]
            }
        )

        collections = mock_client.get_collections()

        assert len(collections) == 1
        assert collections[0].name == "Favorites"
        assert isinstance(collections[0], Collection)

    def test_create_collection(self, mock_client):
        """Test create_collection method."""
        mock_client._post = MagicMock(
            return_value={
                "id": "col_new",
                "libraryId": "lib_1",
                "userId": "root",
                "name": "New Collection",
                "books": [],
                "lastUpdate": 0,
                "createdAt": 0,
            }
        )

        result = mock_client.create_collection(
            library_id="lib_1",
            name="New Collection",
            description="Test",
        )

        assert result.id == "col_new"
        assert isinstance(result, CollectionExpanded)
        mock_client._post.assert_called_once()
        call_args = mock_client._post.call_args
        assert call_args[1]["json"]["name"] == "New Collection"
        assert call_args[1]["json"]["description"] == "Test"

    def test_find_or_create_collection_existing(self, mock_client):
        """Test find_or_create_collection finds existing."""
        existing_collection = Collection(
            id="col_1",
            libraryId="lib_1",
            userId="root",
            name="Existing",
            books=[],
            lastUpdate=0,
            createdAt=0,
        )
        mock_client.get_collections = MagicMock(return_value=[existing_collection])
        # Mock create_collection before the call to verify it's not invoked
        mock_client.create_collection = MagicMock()

        result = mock_client.find_or_create_collection("lib_1", "Existing")

        assert result.id == "col_1"
        assert isinstance(result, Collection)
        # create_collection should not be called
        mock_client.create_collection.assert_not_called()

    def test_find_or_create_collection_new(self, mock_client):
        """Test find_or_create_collection creates new."""
        mock_client.get_collections = MagicMock(return_value=[])
        new_collection = CollectionExpanded(
            id="col_new",
            libraryId="lib_1",
            userId="root",
            name="New",
            books=[],
            lastUpdate=0,
            createdAt=0,
        )
        mock_client.create_collection = MagicMock(return_value=new_collection)

        result = mock_client.find_or_create_collection("lib_1", "New")

        assert result.id == "col_new"
        assert isinstance(result, CollectionExpanded)
        mock_client.create_collection.assert_called_once_with("lib_1", "New", None)


class TestABSClientEnhancedMethods:
    """Test ABSClient enhanced methods."""

    @pytest.fixture
    def mock_client(self):
        """Create ABSClient with mocked HTTP client."""
        with patch("src.abs.client.httpx.Client"):
            client = ABSClient(host="https://abs.example.com", api_key="test_key")
            return client

    def test_get_author_with_items(self, mock_client):
        """Test get_author_with_items method."""
        mock_client._get = MagicMock(
            return_value={
                "id": "aut_1",
                "name": "Test Author",
                "libraryItems": [{"id": "li_1", "title": "Book 1"}],
                "series": [{"id": "ser_1", "name": "Series 1"}],
            }
        )

        result = mock_client.get_author_with_items("aut_1")

        assert result["name"] == "Test Author"
        assert len(result["libraryItems"]) == 1
        assert len(result["series"]) == 1
        mock_client._get.assert_called_with("/authors/aut_1", params={"include": "items,series"})

    def test_get_series_with_progress(self, mock_client):
        """Test get_series_with_progress method."""
        mock_client._get = MagicMock(
            return_value={
                "id": "ser_1",
                "name": "Test Series",
                "progress": {
                    "libraryItemIds": ["li_1", "li_2"],
                    "libraryItemIdsFinished": ["li_1"],
                    "isFinished": False,
                },
            }
        )

        result = mock_client.get_series_with_progress("ser_1")

        assert result["name"] == "Test Series"
        assert result["progress"]["libraryItemIds"] == ["li_1", "li_2"]
        mock_client._get.assert_called_with("/series/ser_1", params={"include": "progress"})
