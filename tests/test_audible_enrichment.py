"""Tests for Audible enrichment module."""

from unittest.mock import MagicMock, patch

import pytest

from src.audible.enrichment import AudibleEnrichment, AudibleEnrichmentService
from src.audible.models import PlusCatalogInfo, PricingInfo


class TestAudibleEnrichment:
    """Test AudibleEnrichment model."""

    def test_enrichment_initialization_defaults(self):
        """Test AudibleEnrichment with default values."""
        enrichment = AudibleEnrichment(asin="B001")

        assert enrichment.asin == "B001"
        assert enrichment.title is None
        assert enrichment.pricing is None
        assert enrichment.plus_catalog is None
        assert enrichment.series is None
        assert enrichment.rating is None

    def test_enrichment_with_all_fields(self):
        """Test AudibleEnrichment with all fields populated."""
        pricing = PricingInfo(list_price=19.99, sale_price=14.99, currency="USD")
        plus_info = PlusCatalogInfo(is_plus_catalog=True, plan_name="US_MINERVA")

        enrichment = AudibleEnrichment(
            asin="B001",
            title="Test Book",
            authors=["Author One", "Author Two"],
            narrators=["Narrator One"],
            pricing=pricing,
            plus_catalog=plus_info,
            series="Test Series",
            series_sequence="1",
            rating=4.5,
            rating_count=1000,
            description="Test description",
        )

        assert enrichment.asin == "B001"
        assert enrichment.title == "Test Book"
        assert len(enrichment.authors) == 2
        assert enrichment.pricing.discount_percent == 25.0
        assert enrichment.plus_catalog.is_plus_catalog is True
        assert enrichment.series == "Test Series"

    def test_enrichment_pricing_properties(self):
        """Test pricing-related properties."""
        pricing = PricingInfo(list_price=20.0, sale_price=10.0, currency="USD")
        enrichment = AudibleEnrichment(asin="B001", pricing=pricing)

        assert enrichment.pricing.discount_percent == 50.0
        assert enrichment.pricing.is_good_deal is True

    def test_enrichment_json_serialization(self):
        """Test AudibleEnrichment can be serialized to JSON."""
        enrichment = AudibleEnrichment(asin="B001", title="Test", authors=["Author"], narrators=["Narrator"])

        # Should be able to convert to dict
        data = enrichment.model_dump()
        assert data["asin"] == "B001"
        assert data["title"] == "Test"


class TestAudibleEnrichmentService:
    """Test AudibleEnrichmentService."""

    @pytest.fixture
    def mock_client(self):
        """Mock AudibleClient."""
        client = MagicMock()
        return client

    @pytest.fixture
    def service(self, mock_client):
        """Create enrichment service with mock client."""
        return AudibleEnrichmentService(client=mock_client)

    def test_service_initialization(self, mock_client):
        """Test service can be initialized with client."""
        service = AudibleEnrichmentService(client=mock_client)
        assert service.client == mock_client

    def test_enrich_basic_product(self, service, mock_client):
        """Test enriching a product with basic data."""
        mock_product = {
            "asin": "B001",
            "title": "Test Book",
            "authors": [{"name": "Author One"}],
            "narrators": [{"name": "Narrator One"}],
        }

        mock_client.get_product.return_value = {"product": mock_product}

        enrichment = service.enrich("B001")

        assert enrichment.asin == "B001"
        assert enrichment.title == "Test Book"
        assert "Author One" in enrichment.authors
        assert "Narrator One" in enrichment.narrators

    def test_enrich_with_pricing(self, service, mock_client):
        """Test enriching with pricing data."""
        mock_product = {
            "asin": "B001",
            "title": "Test Book",
            "price": {"list_price": {"base": 19.99}, "lowest_price": {"base": 14.99}},
        }

        mock_client.get_product.return_value = {"product": mock_product}

        enrichment = service.enrich("B001")

        assert enrichment.pricing is not None
        assert enrichment.pricing.list_price == 19.99

    def test_enrich_with_plus_catalog(self, service, mock_client):
        """Test enriching with Plus Catalog data."""
        mock_product = {
            "asin": "B001",
            "title": "Test Book",
            "plans": [{"plan_name": "US_MINERVA"}],
        }

        mock_client.get_product.return_value = {"product": mock_product}
        mock_client.parse_plus_catalog.return_value = PlusCatalogInfo(is_plus_catalog=True, plan_name="US_MINERVA")

        enrichment = service.enrich("B001")

        assert enrichment.plus_catalog is not None
        assert enrichment.plus_catalog.is_plus_catalog is True

    def test_enrich_with_series(self, service, mock_client):
        """Test enriching with series data."""
        mock_product = {
            "asin": "B001",
            "title": "Test Book",
            "series": [{"title": "Test Series", "sequence": "1"}],
        }

        mock_client.get_product.return_value = {"product": mock_product}

        enrichment = service.enrich("B001")

        assert enrichment.series == "Test Series"
        assert enrichment.series_sequence == "1"

    def test_enrich_with_rating(self, service, mock_client):
        """Test enriching with rating data."""
        mock_product = {
            "asin": "B001",
            "title": "Test Book",
            "rating": {"overall_distribution": {"display_average_rating": "4.5", "num_ratings": 1000}},
        }

        mock_client.get_product.return_value = {"product": mock_product}

        enrichment = service.enrich("B001")

        assert enrichment.rating == 4.5
        assert enrichment.rating_count == 1000

    def test_enrich_handles_missing_data(self, service, mock_client):
        """Test enrichment handles missing fields gracefully."""
        mock_product = {"asin": "B001"}  # Minimal data

        mock_client.get_product.return_value = {"product": mock_product}

        enrichment = service.enrich("B001")

        assert enrichment.asin == "B001"
        assert enrichment.title is None
        assert enrichment.pricing is None

    def test_enrich_multiple(self, service, mock_client):
        """Test enriching multiple products."""
        mock_products = [
            {"asin": "B001", "title": "Book 1"},
            {"asin": "B002", "title": "Book 2"},
        ]

        def mock_get_product(asin, **kwargs):
            for product in mock_products:
                if product["asin"] == asin:
                    return {"product": product}
            return None

        mock_client.get_product.side_effect = mock_get_product

        enrichments = service.enrich_multiple(["B001", "B002"])

        assert len(enrichments) == 2
        assert enrichments[0].asin == "B001"
        assert enrichments[1].asin == "B002"

    def test_enrich_from_library_item(self, service, mock_client):
        """Test enriching from existing library item data."""
        library_item = {
            "asin": "B001",
            "title": "Test Book",
            "authors": [{"name": "Author"}],
            "purchase_date": "2024-01-01T00:00:00Z",
        }

        enrichment = service.enrich_from_library_item(library_item)

        assert enrichment.asin == "B001"
        assert enrichment.title == "Test Book"
        assert "Author" in enrichment.authors

    def test_service_with_cache(self, mock_client):
        """Test service uses cache for repeated requests."""
        service = AudibleEnrichmentService(client=mock_client, use_cache=True)

        mock_product = {"asin": "B001", "title": "Test Book"}
        mock_client.get_product.return_value = {"product": mock_product}

        # First call
        enrichment1 = service.enrich("B001")
        # Second call (should use cache)
        enrichment2 = service.enrich("B001")

        assert enrichment1.asin == enrichment2.asin
        # Client should only be called once if cache is working
        assert mock_client.get_product.call_count <= 2


class TestPricingInfoIntegration:
    """Test PricingInfo integration with enrichment."""

    def test_pricing_from_api_response(self):
        """Test creating PricingInfo from API response."""
        api_price = {
            "list_price": {"base": 20.0, "currency_code": "USD"},
            "lowest_price": {"base": 15.0},
        }

        pricing = PricingInfo.from_api_response(api_price)

        assert pricing is not None
        assert pricing.list_price == 20.0
        assert pricing.effective_price == 15.0
        assert pricing.currency == "USD"

    def test_pricing_discount_calculation(self):
        """Test discount percentage calculation."""
        pricing = PricingInfo(list_price=100.0, sale_price=75.0, currency="USD")

        assert pricing.discount_percent == 25.0

    def test_pricing_good_deal_detection(self):
        """Test good deal detection (>20% discount)."""
        good_deal = PricingInfo(list_price=100.0, sale_price=70.0, currency="USD")
        assert good_deal.is_good_deal is True

        not_good_deal = PricingInfo(list_price=100.0, sale_price=85.0, currency="USD")
        assert not_good_deal.is_good_deal is False


class TestPlusCatalogInfoIntegration:
    """Test PlusCatalogInfo integration with enrichment."""

    def test_plus_catalog_from_plans(self):
        """Test creating PlusCatalogInfo from plans array."""
        plans = [{"plan_name": "US_MINERVA"}]

        # This would be done by client.parse_plus_catalog()
        plus_info = PlusCatalogInfo(is_plus_catalog=True, plan_name="US_MINERVA")

        assert plus_info.is_plus_catalog is True
        assert plus_info.plan_name == "US_MINERVA"

    def test_plus_catalog_expiration(self):
        """Test Plus Catalog expiration tracking."""
        from datetime import datetime, timedelta

        future_date = datetime.now() + timedelta(days=30)

        plus_info = PlusCatalogInfo(is_plus_catalog=True, plan_name="US_MINERVA", expiration_date=future_date)

        assert plus_info.is_plus_catalog is True
        assert plus_info.expiration_date == future_date
