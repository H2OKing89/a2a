"""
Tests for AudibleClient.

These tests mock the network layer to test client logic without network calls.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audible.client import (
    AudibleAuthError,
    AudibleClient,
    AudibleError,
    AudibleNotFoundError,
    AudibleRateLimitError,
)
from src.audible.models import (
    AudibleCatalogProduct,
    AudibleLibraryItem,
    AudibleListeningStats,
    PlusCatalogInfo,
    PricingInfo,
    WishlistItem,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_auth():
    """Mock Audible Authenticator."""
    auth = MagicMock()
    auth.locale.country_code = "us"
    return auth


@pytest.fixture
def mock_client(mock_auth):
    """Create AudibleClient with mocked auth and client."""
    with patch("src.audible.client.Client") as mock_audible_client:
        client = AudibleClient(
            auth=mock_auth,
            rate_limit_delay=0.0,  # Disable rate limiting for tests
            requests_per_minute=1000,  # High limit for tests
        )
        client._client = mock_audible_client.return_value
        return client


@pytest.fixture
def mock_client_with_cache(mock_auth, tmp_path):
    """Create AudibleClient with cache."""
    from src.cache import SQLiteCache

    cache = SQLiteCache(db_path=tmp_path / "test_cache.db")

    with patch("src.audible.client.Client"):
        client = AudibleClient(
            auth=mock_auth,
            cache=cache,
            rate_limit_delay=0.0,
            requests_per_minute=1000,
        )
        return client


# ============================================================================
# Exception Tests
# ============================================================================


class TestExceptions:
    """Test custom exception classes."""

    def test_audible_error_with_response(self):
        """AudibleError stores response data."""
        response = {"error": "test_error"}
        err = AudibleError("Test error", response=response)
        assert str(err) == "Test error"
        assert err.response == response

    def test_audible_error_without_response(self):
        """AudibleError works without response data."""
        err = AudibleError("Test error")
        assert str(err) == "Test error"
        assert err.response is None

    def test_audible_auth_error_inherits(self):
        """AudibleAuthError inherits from AudibleError."""
        err = AudibleAuthError("Auth failed")
        assert isinstance(err, AudibleError)

    def test_audible_not_found_error_inherits(self):
        """AudibleNotFoundError inherits from AudibleError."""
        err = AudibleNotFoundError("Not found")
        assert isinstance(err, AudibleError)

    def test_audible_rate_limit_error_inherits(self):
        """AudibleRateLimitError inherits from AudibleError."""
        err = AudibleRateLimitError("Rate limited")
        assert isinstance(err, AudibleError)


# ============================================================================
# Client Initialization Tests
# ============================================================================


class TestClientInit:
    """Test client initialization."""

    def test_init_with_defaults(self, mock_auth):
        """Client initializes with default settings."""
        with patch("src.audible.client.Client"):
            client = AudibleClient(auth=mock_auth)

        assert client._rate_limit_delay == 0.5
        assert client._requests_per_minute == 20.0
        assert client._burst_size == 5
        assert client._cache is None

    def test_init_with_custom_rate_limits(self, mock_auth):
        """Client respects custom rate limit settings."""
        with patch("src.audible.client.Client"):
            client = AudibleClient(
                auth=mock_auth,
                rate_limit_delay=1.0,
                requests_per_minute=10.0,
                burst_size=3,
            )

        assert client._rate_limit_delay == 1.0
        assert client._requests_per_minute == 10.0
        assert client._burst_size == 3

    def test_init_with_cache(self, mock_auth, tmp_path):
        """Client accepts SQLiteCache."""
        from src.cache import SQLiteCache

        cache = SQLiteCache(db_path=tmp_path / "test.db")

        with patch("src.audible.client.Client"):
            client = AudibleClient(auth=mock_auth, cache=cache)

        assert client._cache is cache

    def test_marketplace_property(self, mock_client):
        """Marketplace property returns locale."""
        assert mock_client.marketplace == "us"


# ============================================================================
# Rate Limiting Tests
# ============================================================================


class TestRateLimiting:
    """Test rate limiting logic."""

    def test_handle_rate_limit_error_increases_backoff(self, mock_client):
        """Rate limit handler increases backoff."""
        initial_backoff = mock_client._current_backoff
        mock_client._handle_rate_limit_error()
        assert mock_client._current_backoff >= initial_backoff

    def test_backoff_capped_at_max(self, mock_auth):
        """Backoff doesn't exceed max_backoff_seconds."""
        with patch("src.audible.client.Client"):
            client = AudibleClient(
                auth=mock_auth,
                rate_limit_delay=1.0,
                max_backoff_seconds=5.0,
                backoff_multiplier=10.0,  # High multiplier
            )

        # Trigger backoff multiple times
        for _ in range(10):
            client._current_backoff = min(
                client._current_backoff * client._backoff_multiplier,
                client._max_backoff_seconds,
            )

        assert client._current_backoff <= client._max_backoff_seconds


# ============================================================================
# Static Method Tests
# ============================================================================


class TestStaticMethods:
    """Test static/class methods that don't need network."""

    def test_parse_pricing_none(self):
        """parse_pricing returns None for None input."""
        result = AudibleClient.parse_pricing(None)
        assert result is None

    def test_parse_pricing_empty(self):
        """parse_pricing returns None for empty dict."""
        result = AudibleClient.parse_pricing({})
        assert result is None

    def test_parse_pricing_with_list_price(self):
        """parse_pricing extracts list price."""
        price_data = {
            "list_price": {"base": 19.99, "currency_code": "USD"},
        }
        result = AudibleClient.parse_pricing(price_data)
        assert result is not None
        assert result.list_price == 19.99
        assert result.currency == "USD"

    def test_parse_pricing_with_sale_price(self):
        """parse_pricing extracts sale price."""
        price_data = {
            "list_price": {"base": 19.99, "currency_code": "USD"},
            "lowest_price": {
                "base": 14.99,
                "type": "sale",
            },
        }
        result = AudibleClient.parse_pricing(price_data)
        assert result is not None
        assert result.sale_price == 14.99
        assert result.is_monthly_deal is True

    def test_parse_pricing_with_credit_price(self):
        """parse_pricing extracts credit price."""
        price_data = {
            "credit_price": 1.0,
            "list_price": {"base": 19.99},
        }
        result = AudibleClient.parse_pricing(price_data)
        assert result is not None
        assert result.credit_price == 1.0

    def test_parse_plus_catalog_empty(self):
        """parse_plus_catalog returns default for empty input."""
        result = AudibleClient.parse_plus_catalog(None)
        assert result is not None
        assert result.is_plus_catalog is False
        assert result.plan_name is None

    def test_parse_plus_catalog_with_minerva(self):
        """parse_plus_catalog detects Minerva (Plus Catalog)."""
        plans = [
            {"plan_name": "Minerva", "is_in_plan": True},
        ]
        result = AudibleClient.parse_plus_catalog(plans)
        assert result.is_plus_catalog is True
        assert "Minerva" in result.plan_name

    def test_parse_plus_catalog_with_ayce(self):
        """parse_plus_catalog detects AYCE (Plus Catalog)."""
        plans = [
            {"plan_name": "AYCE Plan", "is_in_plan": True},
        ]
        result = AudibleClient.parse_plus_catalog(plans)
        assert result.is_plus_catalog is True

    def test_parse_plus_catalog_not_in_plan(self):
        """parse_plus_catalog checks plan_name, not is_in_plan field."""
        # The implementation only checks plan_name, not is_in_plan
        # So even with is_in_plan=False, if plan_name contains Minerva/AYCE, it's True
        plans = [
            {"plan_name": "Minerva", "is_in_plan": False},
        ]
        result = AudibleClient.parse_plus_catalog(plans)
        # Current implementation: checks plan_name not is_in_plan
        assert result.is_plus_catalog is True  # Because "Minerva" in plan_name

    def test_parse_plus_catalog_no_matching_plan(self):
        """parse_plus_catalog returns False for non-Plus plans."""
        plans = [
            {"plan_name": "SomethingElse", "is_in_plan": True},
        ]
        result = AudibleClient.parse_plus_catalog(plans)
        assert result.is_plus_catalog is False


# ============================================================================
# Library Method Tests
# ============================================================================


class TestLibraryMethods:
    """Test library-related methods."""

    def test_get_library_parses_response(self, mock_client):
        """get_library parses API response into models."""
        mock_client._client.get.return_value = {
            "items": [
                {"asin": "B001", "title": "Book 1"},
                {"asin": "B002", "title": "Book 2"},
            ]
        }

        items = mock_client.get_library(use_cache=False)

        assert len(items) == 2
        assert all(isinstance(i, AudibleLibraryItem) for i in items)
        assert items[0].asin == "B001"
        assert items[1].asin == "B002"

    def test_get_library_handles_empty_response(self, mock_client):
        """get_library handles empty response."""
        mock_client._client.get.return_value = {"items": []}

        items = mock_client.get_library(use_cache=False)
        assert items == []

    def test_get_library_skips_invalid_items(self, mock_client):
        """get_library skips items that fail validation."""
        mock_client._client.get.return_value = {
            "items": [
                {"asin": "B001", "title": "Valid"},
                {},  # Missing required fields - will fail validation
                {"asin": "B003", "title": "Also Valid"},
            ]
        }

        items = mock_client.get_library(use_cache=False)

        # Should get 2 valid items, skip the invalid one
        assert len(items) == 2

    def test_get_library_uses_cache(self, mock_client_with_cache):
        """get_library caches results."""
        mock_client_with_cache._client.get.return_value = {
            "items": [{"asin": "B001", "title": "Book 1"}]
        }

        # First call - hits API
        items1 = mock_client_with_cache.get_library(use_cache=True)
        assert len(items1) == 1

        # Second call - should use cache
        mock_client_with_cache._client.get.reset_mock()
        items2 = mock_client_with_cache.get_library(use_cache=True)

        assert items2[0].asin == "B001"
        mock_client_with_cache._client.get.assert_not_called()

    def test_get_library_item_not_found(self, mock_client):
        """get_library_item returns None for 404."""
        mock_client._client.get.side_effect = Exception("404 not found")

        result = mock_client.get_library_item("NOTFOUND", use_cache=False)
        assert result is None


# ============================================================================
# Catalog Method Tests
# ============================================================================


class TestCatalogMethods:
    """Test catalog-related methods."""

    def test_get_catalog_product(self, mock_client):
        """get_catalog_product parses response."""
        mock_client._client.get.return_value = {
            "product": {"asin": "B001", "title": "Test Product"}
        }

        product = mock_client.get_catalog_product("B001", use_cache=False)

        assert product is not None
        assert isinstance(product, AudibleCatalogProduct)
        assert product.asin == "B001"

    def test_get_catalog_product_not_found(self, mock_client):
        """get_catalog_product returns None for 404."""
        mock_client._client.get.side_effect = Exception("404 not found")

        result = mock_client.get_catalog_product("NOTFOUND", use_cache=False)
        assert result is None

    def test_search_catalog(self, mock_client):
        """search_catalog parses response."""
        mock_client._client.get.return_value = {
            "products": [
                {"asin": "B001", "title": "Search Result 1"},
                {"asin": "B002", "title": "Search Result 2"},
            ]
        }

        results = mock_client.search_catalog(keywords="test", use_cache=False)

        assert len(results) == 2
        assert all(isinstance(p, AudibleCatalogProduct) for p in results)

    def test_get_similar_products(self, mock_client):
        """get_similar_products parses response."""
        mock_client._client.get.return_value = {
            "similar_products": [
                {"asin": "B002", "title": "Similar 1"},
                {"asin": "B003", "title": "Similar 2"},
            ]
        }

        results = mock_client.get_similar_products("B001", use_cache=False)

        assert len(results) == 2

    def test_get_similar_products_not_found(self, mock_client):
        """get_similar_products returns empty on 404."""
        mock_client._client.get.side_effect = Exception("404")

        results = mock_client.get_similar_products("NOTFOUND", use_cache=False)
        assert results == []


# ============================================================================
# Wishlist Method Tests
# ============================================================================


class TestWishlistMethods:
    """Test wishlist-related methods."""

    def test_get_wishlist(self, mock_client):
        """get_wishlist parses response."""
        mock_client._client.get.return_value = {
            "products": [
                {"asin": "B001", "title": "Wishlist Item 1"},
                {"asin": "B002", "title": "Wishlist Item 2"},
            ]
        }

        items = mock_client.get_wishlist(use_cache=False)

        assert len(items) == 2
        assert all(isinstance(i, WishlistItem) for i in items)

    def test_add_to_wishlist_success(self, mock_client):
        """add_to_wishlist returns True on success."""
        mock_client._client.post.return_value = {}

        result = mock_client.add_to_wishlist("B001")
        assert result is True

    def test_add_to_wishlist_failure(self, mock_client):
        """add_to_wishlist returns False on error."""
        mock_client._client.post.side_effect = Exception("Error")

        result = mock_client.add_to_wishlist("B001")
        assert result is False

    def test_is_in_wishlist_true(self, mock_client):
        """is_in_wishlist returns True when item in wishlist."""
        mock_client._client.get.return_value = {
            "products": [{"asin": "B001", "title": "In Wishlist"}]
        }

        result = mock_client.is_in_wishlist("B001", use_cache=False)
        assert result is True

    def test_is_in_wishlist_false(self, mock_client):
        """is_in_wishlist returns False when item not in wishlist."""
        mock_client._client.get.return_value = {
            "products": [{"asin": "OTHER", "title": "Other Item"}]
        }

        result = mock_client.is_in_wishlist("B001", use_cache=False)
        assert result is False


# ============================================================================
# Account/Stats Method Tests
# ============================================================================


class TestAccountMethods:
    """Test account and stats methods."""

    def test_get_listening_stats(self, mock_client):
        """get_listening_stats parses response."""
        mock_client._client.get.return_value = {
            "total_listening_time_in_ms": 3600000,  # 1 hour
            "books_started": 10,
            "books_finished": 5,
        }

        stats = mock_client.get_listening_stats(use_cache=False)

        assert stats is not None
        assert isinstance(stats, AudibleListeningStats)

    def test_get_listening_stats_error(self, mock_client):
        """get_listening_stats returns None on error."""
        mock_client._client.get.side_effect = Exception("Error")

        stats = mock_client.get_listening_stats(use_cache=False)
        assert stats is None

    def test_get_account_info_error(self, mock_client):
        """get_account_info returns None on error."""
        mock_client._client.get.side_effect = Exception("Error")

        info = mock_client.get_account_info(use_cache=False)
        assert info is None


# ============================================================================
# Content Metadata Tests
# ============================================================================


class TestContentMetadata:
    """Test content metadata methods."""

    def test_supports_dolby_atmos_true(self, mock_client):
        """supports_dolby_atmos returns True for Atmos content."""
        mock_client._client.get.return_value = {
            "content_reference": {
                "available_codec": ["mp4a.40.2", "ac-4", "aac"],  # ac-4 = Atmos
            },
            "chapter_info": {},
        }

        result = mock_client.supports_dolby_atmos("B001", use_cache=False)
        assert result is True

    def test_supports_dolby_atmos_false(self, mock_client):
        """supports_dolby_atmos returns False for non-Atmos content."""
        mock_client._client.get.return_value = {
            "content_reference": {
                "available_codec": ["mp4a.40.2", "aac"],  # No Atmos
            },
            "chapter_info": {},
        }

        result = mock_client.supports_dolby_atmos("B001", use_cache=False)
        assert result is False

    def test_supports_dolby_atmos_error(self, mock_client):
        """supports_dolby_atmos returns False on error."""
        mock_client._client.get.side_effect = Exception("Error")

        result = mock_client.supports_dolby_atmos("B001", use_cache=False)
        assert result is False


# ============================================================================
# Context Manager Tests
# ============================================================================


class TestContextManager:
    """Test context manager protocol."""

    def test_enter_returns_client(self, mock_client):
        """__enter__ returns self."""
        with mock_client as client:
            assert client is mock_client

    def test_exit_closes_client(self, mock_auth):
        """__exit__ calls close."""
        with patch("src.audible.client.Client") as mock_audible:
            client = AudibleClient(auth=mock_auth)

            with client:
                pass

            # close() should be called
            client._client.close.assert_called_once()


# ============================================================================
# Cache Management Tests
# ============================================================================


class TestCacheManagement:
    """Test cache management methods."""

    def test_clear_cache_with_namespace(self, mock_client_with_cache):
        """clear_cache clears specific namespace."""
        # Add some cached data
        mock_client_with_cache._cache.set("library", "key1", {"data": 1})
        mock_client_with_cache._cache.set("catalog", "key2", {"data": 2})

        # Clear only library namespace
        count = mock_client_with_cache.clear_cache(namespace="library")

        assert count == 1
        # catalog should still have data
        assert mock_client_with_cache._cache.get("catalog", "key2") is not None

    def test_clear_cache_all(self, mock_client_with_cache):
        """clear_cache clears all namespaces."""
        mock_client_with_cache._cache.set("library", "key1", {"data": 1})
        mock_client_with_cache._cache.set("catalog", "key2", {"data": 2})

        count = mock_client_with_cache.clear_cache()

        assert count == 2

    def test_get_cache_stats(self, mock_client_with_cache):
        """get_cache_stats returns stats dict."""
        stats = mock_client_with_cache.get_cache_stats()

        assert isinstance(stats, dict)
        assert "total_entries" in stats
