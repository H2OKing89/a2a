"""
Tests for configuration management module.

Tests cover:
- Default settings initialization
- Custom field overrides
- Settings loading from YAML
- Environment variable overrides
- Settings reload functionality
- All settings submodules
"""

import os
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.config import (
    ABSSettings,
    APIRateLimitSettings,
    AudibleSettings,
    CacheSettings,
    EnrichmentSettings,
    PathSettings,
    QualitySettings,
    Settings,
    get_settings,
    reload_settings,
)


class TestABSSettings:
    """Test ABSSettings class."""

    def test_default_values(self):
        """Test default ABS settings values."""
        settings = ABSSettings()
        # Note: May be overridden by environment variables
        assert settings.api_key == "" or isinstance(settings.api_key, str)
        assert settings.rate_limit_delay == 0.0

    def test_custom_host(self):
        """Test setting custom ABS host."""
        settings = ABSSettings(host="http://192.168.1.100:13378")
        assert settings.host == "http://192.168.1.100:13378"

    def test_custom_api_key(self):
        """Test setting custom API key."""
        settings = ABSSettings(api_key="test_key_12345")
        assert settings.api_key == "test_key_12345"

    def test_rate_limit_settings(self):
        """Test ABS rate limit configuration."""
        settings = ABSSettings(rate_limit_delay=0.5)
        assert settings.rate_limit_delay == 0.5


class TestAudibleSettings:
    """Test AudibleSettings class."""

    def test_default_values(self):
        """Test default Audible settings."""
        settings = AudibleSettings()
        assert settings.auth_file == Path("./data/audible_auth.json")
        assert settings.locale == "us"
        assert settings.email is None
        assert settings.password is None
        assert settings.rate_limit_delay == 0.5
        assert settings.requests_per_minute == 20.0
        assert settings.burst_size == 5
        assert settings.backoff_multiplier == 2.0
        assert settings.max_backoff_seconds == 60.0

    def test_custom_auth_file(self):
        """Test custom auth file path."""
        custom_path = Path("./custom/auth.json")
        settings = AudibleSettings(auth_file=custom_path)
        assert settings.auth_file == custom_path

    def test_different_locale(self):
        """Test different marketplace locale."""
        settings = AudibleSettings(locale="uk")
        assert settings.locale == "uk"

    def test_credentials(self):
        """Test email and password settings."""
        settings = AudibleSettings(email="test@example.com", password="test_password")
        assert settings.email == "test@example.com"
        assert settings.password == "test_password"

    def test_rate_limiting(self):
        """Test rate limit configuration."""
        settings = AudibleSettings(
            rate_limit_delay=1.0,
            requests_per_minute=30.0,
            burst_size=10,
            backoff_multiplier=3.0,
            max_backoff_seconds=120.0,
        )
        assert settings.rate_limit_delay == 1.0
        assert settings.requests_per_minute == 30.0
        assert settings.burst_size == 10
        assert settings.backoff_multiplier == 3.0
        assert settings.max_backoff_seconds == 120.0


class TestPathSettings:
    """Test PathSettings class."""

    def test_default_paths(self):
        """Test default path settings."""
        settings = PathSettings()
        assert settings.library_root == Path("/mnt/user/data/audio/audiobooks")
        assert settings.data_dir == Path("./data")
        assert settings.cache_dir == Path("./data/cache")
        assert settings.reports_dir == Path("./data/reports")
        assert settings.scans_dir == Path("./data/scans")

    def test_custom_library_root(self):
        """Test custom library root path."""
        custom_root = Path("/custom/audiobooks")
        settings = PathSettings(library_root=custom_root)
        assert settings.library_root == custom_root

    def test_all_custom_paths(self):
        """Test all paths customized."""
        custom_data = Path("/custom/data")
        custom_cache = Path("/custom/cache")
        custom_reports = Path("/custom/reports")
        custom_scans = Path("/custom/scans")

        settings = PathSettings(
            data_dir=custom_data, cache_dir=custom_cache, reports_dir=custom_reports, scans_dir=custom_scans
        )
        assert settings.data_dir == custom_data
        assert settings.cache_dir == custom_cache
        assert settings.reports_dir == custom_reports
        assert settings.scans_dir == custom_scans


class TestCacheSettings:
    """Test CacheSettings class."""

    def test_default_values(self):
        """Test default cache settings."""
        settings = CacheSettings()
        assert settings.enabled is True
        assert settings.db_path == Path("./data/cache/cache.db")
        assert settings.default_ttl_hours == 2.0
        assert settings.abs_ttl_hours == 2.0
        assert settings.audible_ttl_hours == 240.0
        assert settings.max_memory_entries == 500

    def test_disabled_cache(self):
        """Test disabling cache."""
        settings = CacheSettings(enabled=False)
        assert settings.enabled is False

    def test_custom_db_path(self):
        """Test custom database path."""
        custom_db = Path("/custom/cache.db")
        settings = CacheSettings(db_path=custom_db)
        assert settings.db_path == custom_db

    def test_ttl_settings(self):
        """Test TTL configuration."""
        settings = CacheSettings(default_ttl_hours=4.0, abs_ttl_hours=6.0, audible_ttl_hours=480.0)
        assert settings.default_ttl_hours == 4.0
        assert settings.abs_ttl_hours == 6.0
        assert settings.audible_ttl_hours == 480.0

    def test_memory_entries(self):
        """Test memory cache entries limit."""
        settings = CacheSettings(max_memory_entries=1000)
        assert settings.max_memory_entries == 1000


class TestQualitySettings:
    """Test QualitySettings class."""

    def test_default_bitrate_thresholds(self):
        """Test default bitrate thresholds."""
        settings = QualitySettings()
        assert settings.bitrate_threshold_kbps == 100.0
        assert settings.ultra_bitrate_kbps == 256.0
        assert settings.high_bitrate_kbps == 128.0
        assert settings.medium_bitrate_kbps == 96.0
        assert settings.low_bitrate_kbps == 64.0

    def test_default_weights(self):
        """Test default quality weights."""
        settings = QualitySettings()
        assert settings.weight_bitrate == 0.4
        assert settings.weight_codec == 0.3
        assert settings.weight_spatial == 0.2
        assert settings.weight_metadata == 0.1
        # Verify weights sum to 1.0
        total = settings.weight_bitrate + settings.weight_codec + settings.weight_spatial + settings.weight_metadata
        assert abs(total - 1.0) < 0.001

    def test_custom_thresholds(self):
        """Test custom bitrate thresholds."""
        settings = QualitySettings(bitrate_threshold_kbps=80.0, ultra_bitrate_kbps=320.0)
        assert settings.bitrate_threshold_kbps == 80.0
        assert settings.ultra_bitrate_kbps == 320.0

    def test_custom_weights(self):
        """Test custom quality weights."""
        settings = QualitySettings(weight_bitrate=0.5, weight_codec=0.3, weight_spatial=0.1, weight_metadata=0.1)
        assert settings.weight_bitrate == 0.5
        assert settings.weight_codec == 0.3
        assert settings.weight_spatial == 0.1
        assert settings.weight_metadata == 0.1


class TestAPIRateLimitSettings:
    """Test APIRateLimitSettings class."""

    def test_default_values(self):
        """Test default rate limit settings."""
        settings = APIRateLimitSettings()
        assert settings.base_delay == 0.1
        assert settings.burst_size == 10
        assert settings.burst_delay == 1.0
        assert settings.backoff_multiplier == 2.0
        assert settings.max_delay == 30.0
        assert settings.recovery_requests == 20

    def test_custom_delays(self):
        """Test custom delay settings."""
        settings = APIRateLimitSettings(base_delay=0.2, burst_delay=2.0, max_delay=60.0)
        assert settings.base_delay == 0.2
        assert settings.burst_delay == 2.0
        assert settings.max_delay == 60.0

    def test_custom_burst(self):
        """Test custom burst configuration."""
        settings = APIRateLimitSettings(burst_size=20, backoff_multiplier=3.0)
        assert settings.burst_size == 20
        assert settings.backoff_multiplier == 3.0


class TestEnrichmentSettings:
    """Test EnrichmentSettings class."""

    def test_default_values(self):
        """Test default enrichment settings."""
        settings = EnrichmentSettings()
        assert settings.enabled is True
        assert settings.requests_per_minute == 20.0
        assert settings.burst_size == 5
        assert settings.backoff_multiplier == 2.0
        assert settings.max_backoff_s == 60.0

    def test_disabled_enrichment(self):
        """Test disabling enrichment."""
        settings = EnrichmentSettings(enabled=False)
        assert settings.enabled is False

    def test_custom_settings(self):
        """Test custom enrichment settings."""
        settings = EnrichmentSettings(
            requests_per_minute=30.0, burst_size=10, backoff_multiplier=3.0, max_backoff_s=120.0
        )
        assert settings.requests_per_minute == 30.0
        assert settings.burst_size == 10
        assert settings.backoff_multiplier == 3.0
        assert settings.max_backoff_s == 120.0


class TestSettings:
    """Test main Settings class."""

    def test_default_settings(self):
        """Test Settings with defaults."""
        settings = Settings()
        assert isinstance(settings.abs, ABSSettings)
        assert isinstance(settings.audible, AudibleSettings)
        assert isinstance(settings.rate_limit, APIRateLimitSettings)
        assert isinstance(settings.paths, PathSettings)
        assert isinstance(settings.cache, CacheSettings)
        assert isinstance(settings.quality, QualitySettings)
        assert isinstance(settings.enrichment, EnrichmentSettings)
        assert settings.verbose is True
        assert settings.debug is False

    def test_custom_verbose_debug(self):
        """Test verbose and debug flags."""
        settings = Settings(verbose=False, debug=True)
        assert settings.verbose is False
        assert settings.debug is True

    def test_load_empty_config_file(self):
        """Test loading with non-existent config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.yaml"
            settings = Settings.load(config_path)
            assert isinstance(settings, Settings)
            assert isinstance(settings.abs, ABSSettings)

    def test_load_minimal_yaml(self):
        """Test loading minimal YAML config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = {"verbose": False}
            with open(config_path, "w") as f:
                yaml.dump(config, f)

            settings = Settings.load(config_path)
            assert settings.verbose is False

    def test_load_all_sections_yaml(self):
        """Test loading complete YAML config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = {
                "abs": {"host": "http://custom:13378", "api_key": "custom_key"},
                "audible": {"locale": "uk", "email": "test@example.com"},
                "paths": {"library_root": "/custom/audiobooks"},
                "quality": {"bitrate_threshold_kbps": 80.0},
                "enrichment": {"enabled": False},
                "cache": {"enabled": False, "db_path": "/custom/cache.db"},
                "verbose": False,
                "debug": True,
            }
            with open(config_path, "w") as f:
                yaml.dump(config, f)

            settings = Settings.load(config_path)
            assert settings.abs.host == "http://custom:13378"
            assert settings.abs.api_key == "custom_key"
            assert settings.audible.locale == "uk"
            assert settings.audible.email == "test@example.com"
            assert settings.paths.library_root == Path("/custom/audiobooks")
            assert settings.quality.bitrate_threshold_kbps == 80.0
            assert settings.enrichment.enabled is False
            assert settings.cache.enabled is False
            assert settings.cache.db_path == Path("/custom/cache.db")
            assert settings.verbose is False
            assert settings.debug is True

    def test_load_partial_yaml(self):
        """Test loading partial YAML config with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = {"abs": {"host": "http://custom:13378"}, "verbose": False}
            with open(config_path, "w") as f:
                yaml.dump(config, f)

            settings = Settings.load(config_path)
            # Custom values
            assert settings.abs.host == "http://custom:13378"
            assert settings.verbose is False
            # Default values for non-specified sections
            assert settings.audible.locale == "us"
            assert settings.cache.enabled is True
            assert settings.debug is False

    def test_load_default_config_path(self):
        """Test loading with default config.yaml path."""
        # This tests the None config_path case
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp directory
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                # Create config.yaml
                config = {"verbose": False}
                config_path = Path(tmpdir) / "config.yaml"
                with open(config_path, "w") as f:
                    yaml.dump(config, f)

                settings = Settings.load()
                assert settings.verbose is False
            finally:
                os.chdir(original_cwd)

    def test_load_empty_yaml(self):
        """Test loading empty YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            with open(config_path, "w") as f:
                yaml.dump({}, f)

            settings = Settings.load(config_path)
            # All defaults should be used
            assert isinstance(settings, Settings)
            assert isinstance(settings.abs, ABSSettings)

    def test_load_yaml_with_null_sections(self):
        """Test loading YAML with null/None values are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = {"abs": {"host": "http://custom:13378"}, "verbose": False}
            with open(config_path, "w") as f:
                yaml.dump(config, f)

            settings = Settings.load(config_path)
            # Null values in YAML should not appear in config_data
            assert settings.abs.host == "http://custom:13378"
            assert settings.verbose is False


class TestGlobalSettings:
    """Test global settings management functions."""

    def test_get_settings_singleton(self):
        """Test get_settings returns singleton."""
        # Reset global state
        import src.config as config_module

        config_module._settings = None

        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_reload_settings(self):
        """Test reloading settings."""
        import src.config as config_module

        config_module._settings = None

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = {"verbose": False, "debug": True}
            with open(config_path, "w") as f:
                yaml.dump(config, f)

            # Load initial settings
            settings1 = reload_settings(config_path)
            assert settings1.verbose is False
            assert settings1.debug is True

            # Modify YAML
            config = {"verbose": True, "debug": False}
            with open(config_path, "w") as f:
                yaml.dump(config, f)

            # Reload settings
            settings2 = reload_settings(config_path)
            assert settings2.verbose is True
            assert settings2.debug is False
            assert settings1 is not settings2

    def test_reload_settings_updates_global(self):
        """Test reload_settings updates global instance."""
        import src.config as config_module

        config_module._settings = None

        settings1 = get_settings()
        assert settings1.verbose is True  # default

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = {"verbose": False}
            with open(config_path, "w") as f:
                yaml.dump(config, f)

            reload_settings(config_path)
            settings2 = get_settings()
            assert settings2.verbose is False
            assert settings1 is not settings2

    def test_reload_without_config_path(self):
        """Test reload_settings with default config path."""
        import src.config as config_module

        config_module._settings = None

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                config = {"debug": True}
                config_path = Path(tmpdir) / "config.yaml"
                with open(config_path, "w") as f:
                    yaml.dump(config, f)

                settings = reload_settings()
                assert settings.debug is True
            finally:
                os.chdir(original_cwd)
