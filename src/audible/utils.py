"""
Audible utilities including locale information and activation bytes.

This module provides:
- Marketplace/locale information
- Activation bytes retrieval (for DRM removal)
- Device registration helpers
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from audible import Authenticator

logger = logging.getLogger(__name__)


# =============================================================================
# Locale/Marketplace Information
# =============================================================================


@dataclass
class MarketplaceInfo:
    """Information about an Audible marketplace."""

    country_code: str
    domain: str
    marketplace_id: str
    name: str
    currency: str
    language: str


# Known Audible marketplaces
MARKETPLACES: dict[str, MarketplaceInfo] = {
    "us": MarketplaceInfo(
        country_code="us",
        domain="audible.com",
        marketplace_id="AF2M0KC94RCEA",
        name="United States",
        currency="USD",
        language="en_US",
    ),
    "uk": MarketplaceInfo(
        country_code="uk",
        domain="audible.co.uk",
        marketplace_id="A2I9A3Q2GNFNGQ",
        name="United Kingdom",
        currency="GBP",
        language="en_GB",
    ),
    "de": MarketplaceInfo(
        country_code="de",
        domain="audible.de",
        marketplace_id="AN7V1F1VY261K",
        name="Germany",
        currency="EUR",
        language="de_DE",
    ),
    "fr": MarketplaceInfo(
        country_code="fr",
        domain="audible.fr",
        marketplace_id="A2728XDNODOQ8T",
        name="France",
        currency="EUR",
        language="fr_FR",
    ),
    "ca": MarketplaceInfo(
        country_code="ca",
        domain="audible.ca",
        marketplace_id="A2CQZ5RBY40XE",
        name="Canada",
        currency="CAD",
        language="en_CA",
    ),
    "au": MarketplaceInfo(
        country_code="au",
        domain="audible.com.au",
        marketplace_id="AN7EY7DTAW63G",
        name="Australia",
        currency="AUD",
        language="en_AU",
    ),
    "it": MarketplaceInfo(
        country_code="it",
        domain="audible.it",
        marketplace_id="A2N7FU2W2BU2ZC",
        name="Italy",
        currency="EUR",
        language="it_IT",
    ),
    "in": MarketplaceInfo(
        country_code="in",
        domain="audible.in",
        marketplace_id="AJO3FBRUE6J4S",
        name="India",
        currency="INR",
        language="en_IN",
    ),
    "jp": MarketplaceInfo(
        country_code="jp",
        domain="audible.co.jp",
        marketplace_id="A1QAP3MOU4173J",
        name="Japan",
        currency="JPY",
        language="ja_JP",
    ),
    "es": MarketplaceInfo(
        country_code="es",
        domain="audible.es",
        marketplace_id="ATVPDKIKX0DER",
        name="Spain",
        currency="EUR",
        language="es_ES",
    ),
}


def get_marketplace(locale: str) -> MarketplaceInfo | None:
    """
    Get marketplace information for a locale.

    Args:
        locale: Locale code (us, uk, de, fr, etc.)

    Returns:
        MarketplaceInfo or None if unknown
    """
    return MARKETPLACES.get(locale.lower())


def list_marketplaces() -> list[MarketplaceInfo]:
    """Get list of all known marketplaces."""
    return list(MARKETPLACES.values())


def get_marketplace_for_domain(domain: str) -> MarketplaceInfo | None:
    """
    Get marketplace info from domain.

    Args:
        domain: Domain like "audible.com" or "audible.co.uk"

    Returns:
        MarketplaceInfo or None
    """
    domain = domain.lower().replace("www.", "")
    for marketplace in MARKETPLACES.values():
        if marketplace.domain == domain:
            return marketplace
    return None


# =============================================================================
# Activation Bytes (for DRM removal tools)
# =============================================================================


def get_activation_bytes(auth: Authenticator) -> str | None:
    """
    Get activation bytes for the authenticated account.

    Activation bytes are needed by tools like ffmpeg or inAudible
    to convert AAX files to other formats.

    Args:
        auth: Authenticated Audible authenticator

    Returns:
        Activation bytes as hex string, or None on failure

    Example:
        auth = Authenticator.from_file("auth.json")
        bytes = get_activation_bytes(auth)
        # Use with: ffmpeg -activation_bytes {bytes} -i book.aax book.m4b
    """
    try:
        from audible.activation_bytes import get_activation_bytes as _get_bytes

        return _get_bytes(auth)
    except ImportError:
        logger.warning("activation_bytes module not available")
        return None
    except Exception as e:
        logger.error("Failed to get activation bytes: %s", e)
        return None


def get_activation_bytes_from_file(auth_file: str | Path) -> str | None:
    """
    Get activation bytes from an auth file.

    Args:
        auth_file: Path to saved auth credentials

    Returns:
        Activation bytes as hex string, or None on failure
    """
    try:
        auth = Authenticator.from_file(str(auth_file))
        return get_activation_bytes(auth)
    except Exception as e:
        logger.error("Failed to load auth for activation bytes: %s", e)
        return None


# =============================================================================
# Device Registration
# =============================================================================


@dataclass
class DeviceInfo:
    """Information about a registered Audible device."""

    device_name: str
    device_serial_number: str
    device_type: str


def get_device_info(auth: Authenticator) -> DeviceInfo | None:
    """
    Get information about the registered device.

    Args:
        auth: Authenticated Audible authenticator

    Returns:
        DeviceInfo or None
    """
    try:
        return DeviceInfo(
            device_name=auth.device_info.get("device_name", "Unknown"),
            device_serial_number=auth.device_info.get("device_serial_number", "Unknown"),
            device_type=auth.device_info.get("device_type", "Unknown"),
        )
    except Exception as e:
        logger.error("Failed to get device info: %s", e)
        return None


def deregister_device(auth: Authenticator) -> bool:
    """
    Deregister the current device.

    This should be done when you no longer need access from this device.
    Note: You have a limited number of device registrations.

    Args:
        auth: Authenticated Audible authenticator

    Returns:
        True if successful
    """
    try:
        auth.deregister_device()
        return True
    except Exception as e:
        logger.error("Failed to deregister device: %s", e)
        return False


# =============================================================================
# Auth File Utilities
# =============================================================================


def refresh_auth(auth: Authenticator) -> bool:
    """
    Refresh authentication tokens.

    Args:
        auth: Authenticator to refresh

    Returns:
        True if successful
    """
    try:
        auth.refresh_access_token()
        return True
    except Exception as e:
        logger.error("Failed to refresh auth: %s", e)
        return False


def is_auth_valid(auth_file: str | Path) -> bool:
    """
    Check if an auth file is valid and not expired.

    Args:
        auth_file: Path to auth file

    Returns:
        True if valid
    """
    try:
        auth = Authenticator.from_file(str(auth_file))
        # Try to refresh - this will fail if invalid
        auth.refresh_access_token()
        return True
    except Exception:
        return False


def get_auth_info(auth_file: str | Path) -> dict[str, Any] | None:
    """
    Get information about an auth file.

    Args:
        auth_file: Path to auth file

    Returns:
        Dict with locale, device info, etc.
    """
    try:
        auth = Authenticator.from_file(str(auth_file))
        device = get_device_info(auth)
        marketplace = get_marketplace(auth.locale.country_code)

        return {
            "locale": auth.locale.country_code,
            "marketplace": marketplace.name if marketplace else "Unknown",
            "domain": marketplace.domain if marketplace else "Unknown",
            "device_name": device.device_name if device else "Unknown",
            "device_type": device.device_type if device else "Unknown",
        }
    except Exception as e:
        logger.error("Failed to get auth info: %s", e)
        return None
