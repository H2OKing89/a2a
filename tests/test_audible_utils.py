"""Tests for Audible utilities module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audible.utils import (
    MARKETPLACES,
    DeviceInfo,
    MarketplaceInfo,
    deregister_device,
    get_activation_bytes,
    get_activation_bytes_from_file,
    get_auth_info,
    get_device_info,
    get_marketplace,
    get_marketplace_for_domain,
    is_auth_valid,
    list_marketplaces,
    refresh_auth,
)


class TestMarketplaceInfo:
    """Test marketplace information and lookups."""

    def test_marketplaces_constant_exists(self):
        """Test MARKETPLACES constant is defined."""
        assert isinstance(MARKETPLACES, dict)
        assert len(MARKETPLACES) > 0

    def test_us_marketplace_exists(self):
        """Test US marketplace is defined."""
        assert "us" in MARKETPLACES
        us = MARKETPLACES["us"]
        assert us.code == "us"
        assert us.name == "United States"
        assert us.domain == "audible.com"
        assert us.currency == "USD"

    def test_all_required_marketplaces(self):
        """Test all 10 required marketplaces exist."""
        required = ["us", "uk", "de", "fr", "ca", "au", "it", "in", "jp", "es"]
        for code in required:
            assert code in MARKETPLACES, f"Missing marketplace: {code}"

    def test_marketplace_info_structure(self):
        """Test MarketplaceInfo has required fields."""
        mp = MARKETPLACES["us"]
        assert hasattr(mp, "code")
        assert hasattr(mp, "name")
        assert hasattr(mp, "domain")
        assert hasattr(mp, "currency")
        assert hasattr(mp, "api_domain")

    def test_get_marketplace_valid(self):
        """Test get_marketplace with valid code."""
        us = get_marketplace("us")
        assert us is not None
        assert us.code == "us"
        assert us.name == "United States"

    def test_get_marketplace_invalid(self):
        """Test get_marketplace with invalid code."""
        result = get_marketplace("invalid")
        assert result is None

    def test_get_marketplace_case_insensitive(self):
        """Test get_marketplace is case insensitive."""
        us_lower = get_marketplace("us")
        us_upper = get_marketplace("US")
        assert us_lower == us_upper

    def test_list_marketplaces(self):
        """Test list_marketplaces returns all marketplaces."""
        marketplaces = list_marketplaces()
        assert isinstance(marketplaces, list)
        assert len(marketplaces) >= 10
        assert all(isinstance(item, tuple) for item in marketplaces)
        assert all(isinstance(item[1], MarketplaceInfo) for item in marketplaces)

    def test_get_marketplace_for_domain_valid(self):
        """Test lookup by domain."""
        us = get_marketplace_for_domain("audible.com")
        assert us is not None
        assert us.code == "us"

        uk = get_marketplace_for_domain("audible.co.uk")
        assert uk is not None
        assert uk.code == "uk"

    def test_get_marketplace_for_domain_invalid(self):
        """Test lookup by invalid domain."""
        result = get_marketplace_for_domain("invalid.com")
        assert result is None

    def test_all_marketplaces_have_unique_domains(self):
        """Test all marketplaces have unique domains."""
        domains = [mp.domain for mp in MARKETPLACES.values()]
        assert len(domains) == len(set(domains)), "Duplicate domains found"


class TestActivationBytes:
    """Test activation bytes functions."""

    @pytest.fixture
    def mock_auth(self):
        """Mock Audible authenticator."""
        auth = MagicMock()
        auth.adp_token = "mock_adp_token"
        return auth

    def test_get_activation_bytes(self, mock_auth):
        """Test get_activation_bytes returns hex string."""
        with patch("src.audible.utils.activation_bytes") as mock_ab:
            mock_ab.extract.return_value = b"\x01\x02\x03\x04"

            result = get_activation_bytes(mock_auth)

            assert isinstance(result, str)
            mock_ab.extract.assert_called_once()

    def test_get_activation_bytes_from_file(self):
        """Test get_activation_bytes_from_file."""
        with (
            patch("src.audible.utils.Authenticator") as mock_auth_class,
            patch("src.audible.utils.activation_bytes") as mock_ab,
        ):
            mock_auth = MagicMock()
            mock_auth_class.from_file.return_value = mock_auth
            mock_ab.extract.return_value = b"\xaa\xbb\xcc\xdd"

            result = get_activation_bytes_from_file("test.json")

            assert isinstance(result, str)
            mock_auth_class.from_file.assert_called_once_with("test.json")

    def test_get_activation_bytes_error_handling(self, mock_auth):
        """Test activation bytes handles errors."""
        with patch("src.audible.utils.activation_bytes") as mock_ab:
            mock_ab.extract.side_effect = RuntimeError("Test error")

            with pytest.raises(RuntimeError, match="Test error"):
                get_activation_bytes(mock_auth)


class TestAuthInfo:
    """Test auth file information functions."""

    @pytest.fixture
    def mock_auth(self):
        """Mock Audible authenticator with realistic data."""
        auth = MagicMock()
        auth.locale.country_code = "us"
        auth.device_info = {"device_name": "Test Device", "device_type": "A2CZJZGLK2JJVM"}
        auth.access_token_expires = 1700000000  # Some future timestamp
        return auth

    def test_is_auth_valid_with_valid_file(self):
        """Test is_auth_valid with valid auth file."""
        with (
            patch("src.audible.utils.Authenticator") as mock_auth_class,
            patch("src.audible.utils.Path.exists") as mock_exists,
        ):
            mock_exists.return_value = True
            mock_auth = MagicMock()
            mock_auth_class.from_file.return_value = mock_auth

            result = is_auth_valid("test.json")

            assert isinstance(result, bool)

    def test_is_auth_valid_with_missing_file(self):
        """Test is_auth_valid with missing file."""
        with patch("src.audible.utils.Path.exists") as mock_exists:
            mock_exists.return_value = False

            result = is_auth_valid("missing.json")

            assert result is False

    def test_get_auth_info(self, mock_auth):
        """Test get_auth_info returns auth details."""
        with patch("src.audible.utils.Authenticator") as mock_auth_class:
            mock_auth_class.from_file.return_value = mock_auth

            info = get_auth_info("test.json")

            assert isinstance(info, dict)
            assert "locale" in info
            assert info["locale"] == "us"
            assert "device_name" in info

    def test_get_auth_info_handles_missing_fields(self):
        """Test get_auth_info handles missing optional fields."""
        with patch("src.audible.utils.Authenticator") as mock_auth_class:
            mock_auth = MagicMock()
            mock_auth.locale.country_code = "us"
            mock_auth.device_info = {}  # Empty device info
            mock_auth_class.from_file.return_value = mock_auth

            info = get_auth_info("test.json")

            assert "locale" in info
            # Should handle missing fields gracefully


class TestDeviceInfo:
    """Test device information functions."""

    @pytest.fixture
    def mock_auth(self):
        """Mock Audible authenticator with device info."""
        auth = MagicMock()
        auth.device_info = {
            "device_name": "iPhone",
            "device_type": "A2CZJZGLK2JJVM",
            "device_serial_number": "123456",
        }
        return auth

    def test_get_device_info(self, mock_auth):
        """Test get_device_info returns DeviceInfo."""
        info = get_device_info(mock_auth)

        assert isinstance(info, DeviceInfo)
        assert info.name == "iPhone"
        assert info.type == "A2CZJZGLK2JJVM"
        assert info.serial == "123456"

    def test_get_device_info_partial_data(self):
        """Test get_device_info with partial device data."""
        auth = MagicMock()
        auth.device_info = {"device_name": "Test"}

        info = get_device_info(auth)

        assert info.name == "Test"
        assert info.type is None
        assert info.serial is None

    def test_deregister_device(self, mock_auth):
        """Test deregister_device calls API."""
        with patch("src.audible.utils.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.deregister_device = MagicMock()
            mock_client_class.return_value = mock_client

            deregister_device(mock_auth)

            mock_client.deregister_device.assert_called_once()

    def test_refresh_auth(self, mock_auth):
        """Test refresh_auth saves updated auth."""
        with patch("src.audible.utils.Path.exists") as mock_exists:
            mock_exists.return_value = True
            mock_auth.to_file = MagicMock()

            refresh_auth(mock_auth, "test.json")

            mock_auth.to_file.assert_called_once_with("test.json", encryption=False)

    def test_refresh_auth_with_encryption(self, mock_auth):
        """Test refresh_auth with encryption."""
        with patch("src.audible.utils.Path.exists") as mock_exists:
            mock_exists.return_value = True
            mock_auth.to_file = MagicMock()

            refresh_auth(mock_auth, "test.json", encrypt=True, password="secret")

            mock_auth.to_file.assert_called_once_with("test.json", encryption=True, password="secret")


class TestRealAuthFile:
    """Test utilities with real auth file (if exists)."""

    @pytest.fixture
    def auth_file_path(self):
        """Path to test auth file."""
        return Path("data/audible_auth.json")

    def test_real_auth_file_if_exists(self, auth_file_path):
        """Test with real auth file if it exists."""
        if auth_file_path.exists():
            # Test is_auth_valid
            assert is_auth_valid(str(auth_file_path)) is True

            # Test get_auth_info
            info = get_auth_info(str(auth_file_path))
            assert "locale" in info
            assert len(info["locale"]) == 2

            # Test get_activation_bytes_from_file
            activation = get_activation_bytes_from_file(str(auth_file_path))
            assert isinstance(activation, str)
            assert len(activation) == 8  # 4 bytes = 8 hex chars
        else:
            pytest.skip("Real auth file not found")

    def test_marketplace_for_real_auth(self, auth_file_path):
        """Test getting marketplace from real auth."""
        if auth_file_path.exists():
            info = get_auth_info(str(auth_file_path))
            locale = info.get("locale")

            if locale:
                mp = get_marketplace(locale)
                assert mp is not None
                assert mp.code == locale.lower()
        else:
            pytest.skip("Real auth file not found")
