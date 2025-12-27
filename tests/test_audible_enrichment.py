"""Tests for Audible enrichment module."""

from datetime import datetime, timedelta, timezone
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
        # plus_catalog has a default factory
        assert enrichment.plus_catalog is not None
        assert enrichment.plus_catalog.is_plus_catalog is False

    def test_enrichment_with_pricing(self):
        """Test AudibleEnrichment with pricing data."""
        pricing = PricingInfo(list_price=19.99, sale_price=14.99, currency="USD")

        enrichment = AudibleEnrichment(
            asin="B001",
            title="Test Book",
            pricing=pricing,
        )

        assert enrichment.asin == "B001"
        assert enrichment.title == "Test Book"
        assert enrichment.pricing.list_price == 19.99
        assert enrichment.pricing.sale_price == 14.99

    def test_enrichment_with_plus_catalog(self):
        """Test AudibleEnrichment with Plus Catalog info."""
        plus_info = PlusCatalogInfo(is_plus_catalog=True, plan_name="US_MINERVA")

        enrichment = AudibleEnrichment(
            asin="B001",
            title="Test Book",
            plus_catalog=plus_info,
        )

        assert enrichment.plus_catalog.is_plus_catalog is True
        assert enrichment.plus_catalog.plan_name == "US_MINERVA"

    def test_enrichment_acquisition_recommendation_owned(self):
        """Test acquisition recommendation for owned book."""
        enrichment = AudibleEnrichment(asin="B001", owned=True)
        assert enrichment.acquisition_recommendation == "OWNED"

    def test_enrichment_acquisition_recommendation_free(self):
        """Test acquisition recommendation for Plus Catalog book."""
        plus_info = PlusCatalogInfo(is_plus_catalog=True)
        enrichment = AudibleEnrichment(asin="B001", plus_catalog=plus_info)
        assert enrichment.acquisition_recommendation == "FREE"

    def test_enrichment_json_serialization(self):
        """Test AudibleEnrichment can be serialized to JSON."""
        enrichment = AudibleEnrichment(asin="B001", title="Test")

        # Should be able to convert to dict
        data = enrichment.model_dump()
        assert data["asin"] == "B001"
        assert data["title"] == "Test"

    def test_enrichment_has_atmos_field(self):
        """Test has_atmos field."""
        enrichment = AudibleEnrichment(asin="B001", has_atmos=True)
        assert enrichment.has_atmos is True

        enrichment2 = AudibleEnrichment(asin="B002")
        assert enrichment2.has_atmos is False


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
        assert service._client == mock_client

    def test_service_enrich_single(self, service, mock_client):
        """Test enriching a single ASIN calls the right methods."""
        # The implementation calls _get_catalog_product internally
        # Mock that method directly on the service
        with patch.object(service, "_get_catalog_product") as mock_get:
            mock_get.return_value = {
                "product": {
                    "asin": "B001",
                    "title": "Test Book",
                    "price": {"list_price": {"base": 15.0}},
                    "plans": [],
                }
            }
            result = service.enrich_single("B001")

        # Result is AudibleEnrichment
        assert isinstance(result, AudibleEnrichment)
        assert result.asin == "B001"
        assert result.title == "Test Book"

    def test_service_enrich_single_returns_none_on_error(self, service, mock_client):
        """Test enrich_single returns None when API fails."""
        with patch.object(service, "_get_catalog_product") as mock_get:
            mock_get.side_effect = Exception("API error")
            result = service.enrich_single("B001")

        assert result is None

    def test_service_enrich_batch(self, service, mock_client):
        """Test enriching multiple ASINs."""
        # Mock the enrich_single method for batch test
        with patch.object(service, "enrich_single") as mock_enrich:
            mock_enrich.side_effect = [
                AudibleEnrichment(asin="B001", title="Book 1"),
                AudibleEnrichment(asin="B002", title="Book 2"),
            ]
            results = service.enrich_batch(["B001", "B002"])

        # Result is dict mapping ASIN to AudibleEnrichment
        assert isinstance(results, dict)
        assert len(results) == 2
        assert "B001" in results
        assert "B002" in results


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
        assert pricing.sale_price == 15.0
        assert pricing.currency == "USD"

    def test_pricing_discount_calculation(self):
        """Test discount percentage calculation."""
        pricing = PricingInfo(list_price=100.0, sale_price=75.0, currency="USD")

        assert pricing.discount_percent == 25.0

    def test_pricing_good_deal_detection(self):
        """Test good deal detection (price under $9.00)."""
        # Good deal: price under $9.00
        good_deal = PricingInfo(list_price=10.0, sale_price=8.99, currency="USD")
        assert good_deal.is_good_deal is True

        # Not a good deal: price >= $9.00
        not_good_deal = PricingInfo(list_price=20.0, sale_price=15.0, currency="USD")
        assert not_good_deal.is_good_deal is False

    def test_pricing_effective_price(self):
        """Test effective price is sale_price or list_price."""
        # With sale price
        pricing1 = PricingInfo(list_price=20.0, sale_price=15.0)
        assert pricing1.effective_price == 15.0

        # Without sale price
        pricing2 = PricingInfo(list_price=20.0)
        assert pricing2.effective_price == 20.0


class TestPlusCatalogInfoIntegration:
    """Test PlusCatalogInfo integration with enrichment."""

    def test_plus_catalog_default(self):
        """Test PlusCatalogInfo default values."""
        plus_info = PlusCatalogInfo()
        assert plus_info.is_plus_catalog is False
        assert plus_info.plan_name is None
        assert plus_info.expiration_date is None

    def test_plus_catalog_with_plan(self):
        """Test PlusCatalogInfo with plan name."""
        plus_info = PlusCatalogInfo(is_plus_catalog=True, plan_name="US_MINERVA")

        assert plus_info.is_plus_catalog is True
        assert plus_info.plan_name == "US_MINERVA"

    def test_plus_catalog_expiration(self):
        """Test Plus Catalog expiration tracking."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)

        plus_info = PlusCatalogInfo(is_plus_catalog=True, plan_name="US_MINERVA", expiration_date=future_date)

        assert plus_info.is_plus_catalog is True
        assert plus_info.expiration_date == future_date

    def test_plus_catalog_is_expiring_soon(self):
        """Test is_expiring_soon property."""

        # Expiring in 5 days (timezone-aware) - should be "soon"
        soon_date = datetime.now(timezone.utc) + timedelta(days=5)
        plus_soon = PlusCatalogInfo(is_plus_catalog=True, expiration_date=soon_date)
        assert plus_soon.is_expiring_soon is True

        # Expiring in 30 days - implementation uses <= 30, so this IS "soon"
        border_date = datetime.now(timezone.utc) + timedelta(days=30)
        plus_border = PlusCatalogInfo(is_plus_catalog=True, expiration_date=border_date)
        assert plus_border.is_expiring_soon is True

        # Expiring in 31 days - NOT "soon" (use 32 to avoid edge case rounding)
        later_date = datetime.now(timezone.utc) + timedelta(days=32)
        plus_later = PlusCatalogInfo(is_plus_catalog=True, expiration_date=later_date)
        assert plus_later.is_expiring_soon is False

        # No expiration
        plus_no_exp = PlusCatalogInfo(is_plus_catalog=True)
        assert plus_no_exp.is_expiring_soon is False
