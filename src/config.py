"""
Configuration management using pydantic-settings.
Loads from config.yaml, .env, and environment variables.
"""

from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file at module import
load_dotenv()


class ABSSettings(BaseSettings):
    """Audiobookshelf API settings."""

    model_config = SettingsConfigDict(
        env_prefix="ABS_",
        extra="ignore",
    )

    host: str = Field(default="http://localhost:13378", description="ABS server URL")
    api_key: str = Field(default="", description="ABS API key/token")

    # Caching settings
    cache_enabled: bool = Field(default=True, description="Enable response caching")
    cache_ttl_hours: float = Field(default=2.0, description="Cache TTL in hours")


class AudibleSettings(BaseSettings):
    """Audible API settings."""

    model_config = SettingsConfigDict(
        env_prefix="AUDIBLE_",
        extra="ignore",
    )

    # Authentication
    auth_file: Path = Field(
        default=Path("./data/audible_auth.json"),
        description="Path to saved Audible credentials",
    )
    locale: str = Field(default="us", description="Audible marketplace locale (us, uk, de, etc.)")

    # Optional email/password for programmatic login
    email: str | None = Field(default=None, description="Audible/Amazon email")
    password: str | None = Field(default=None, description="Audible/Amazon password")

    # Rate limiting
    rate_limit_delay: float = Field(default=0.5, description="Base delay between requests in seconds")
    requests_per_minute: float = Field(default=20.0, description="Maximum requests per minute")
    burst_size: int = Field(default=5, description="Number of requests before burst delay")
    backoff_multiplier: float = Field(default=2.0, description="Backoff multiplier on rate limit errors")
    max_backoff_seconds: float = Field(default=60.0, description="Maximum backoff delay in seconds")

    # Caching
    cache_enabled: bool = Field(default=True, description="Enable response caching")
    cache_ttl_days: int = Field(default=10, description="Cache TTL in days")


class APIRateLimitSettings(BaseSettings):
    """Rate limiting settings for API calls."""

    model_config = SettingsConfigDict(
        env_prefix="API_RATE_LIMIT_",
        extra="ignore",
    )

    base_delay: float = Field(default=0.1, description="Base delay between requests")
    burst_size: int = Field(default=10, description="Number of requests before burst delay")
    burst_delay: float = Field(default=1.0, description="Delay after burst")
    backoff_multiplier: float = Field(default=2.0, description="Backoff multiplier on errors")
    max_delay: float = Field(default=30.0, description="Maximum delay between requests")
    recovery_requests: int = Field(default=20, description="Requests before reducing delay")


class PathSettings(BaseSettings):
    """Path configuration settings."""

    library_root: Path = Field(default=Path("/mnt/user/data/audio/audiobooks"))
    data_dir: Path = Field(default=Path("./data"))
    cache_dir: Path = Field(default=Path("./data/cache"))
    reports_dir: Path = Field(default=Path("./data/reports"))
    scans_dir: Path = Field(default=Path("./data/scans"))


class CacheSettings(BaseSettings):
    """Unified cache settings (SQLite backend)."""

    model_config = SettingsConfigDict(
        env_prefix="CACHE_",
        extra="ignore",
    )

    enabled: bool = Field(default=True, description="Enable caching globally")
    db_path: Path = Field(default=Path("./data/cache/cache.db"), description="SQLite database path")
    default_ttl_hours: float = Field(default=2.0, description="Default TTL for cached items")
    abs_ttl_hours: float = Field(default=2.0, description="TTL for ABS data")
    audible_ttl_hours: float = Field(default=240.0, description="TTL for Audible data (10 days default)")
    max_memory_entries: int = Field(default=500, description="Max entries in memory cache layer")


class QualitySettings(BaseSettings):
    """Audio quality thresholds."""

    model_config = SettingsConfigDict(extra="ignore")

    bitrate_threshold_kbps: float = Field(default=100.0)
    ultra_bitrate_kbps: float = Field(default=256.0)
    high_bitrate_kbps: float = Field(default=128.0)
    medium_bitrate_kbps: float = Field(default=96.0)
    low_bitrate_kbps: float = Field(default=64.0)
    weight_bitrate: float = Field(default=0.4)
    weight_codec: float = Field(default=0.3)
    weight_spatial: float = Field(default=0.2)
    weight_metadata: float = Field(default=0.1)


class EnrichmentSettings(BaseSettings):
    """Audible enrichment settings."""

    enabled: bool = Field(default=True)
    requests_per_minute: float = Field(default=20.0)
    burst_size: int = Field(default=5)
    backoff_multiplier: float = Field(default=2.0)
    max_backoff_s: float = Field(default=60.0)
    cache_ttl_days: int = Field(default=10)


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    abs: ABSSettings = Field(default_factory=ABSSettings)
    audible: AudibleSettings = Field(default_factory=AudibleSettings)
    rate_limit: APIRateLimitSettings = Field(default_factory=APIRateLimitSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    quality: QualitySettings = Field(default_factory=QualitySettings)
    enrichment: EnrichmentSettings = Field(default_factory=EnrichmentSettings)

    verbose: bool = Field(default=True)
    debug: bool = Field(default=False)

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Settings":
        """Load settings from config.yaml and environment."""
        config_data: dict[str, Any] = {}

        if config_path is None:
            config_path = Path("config.yaml")

        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                yaml_content: Any = yaml.safe_load(f)
                yaml_config: dict[str, Any] = yaml_content or {}

            # Map yaml structure to settings
            if "paths" in yaml_config:
                config_data["paths"] = PathSettings(**yaml_config["paths"])  # type: ignore
            if "quality" in yaml_config:
                config_data["quality"] = QualitySettings(**yaml_config["quality"])  # type: ignore
            if "enrichment" in yaml_config:
                config_data["enrichment"] = EnrichmentSettings(**yaml_config["enrichment"])  # type: ignore
            if "cache" in yaml_config:
                config_data["cache"] = CacheSettings(**yaml_config["cache"])  # type: ignore
            if "audible" in yaml_config:
                config_data["audible"] = AudibleSettings(**yaml_config["audible"])  # type: ignore
            if "abs" in yaml_config:
                config_data["abs"] = ABSSettings(**yaml_config["abs"])  # type: ignore
            if "verbose" in yaml_config:
                config_data["verbose"] = yaml_config["verbose"]
            if "debug" in yaml_config:
                config_data["debug"] = yaml_config["debug"]

        # Load ABS settings from environment (merge with yaml if present)
        if "abs" not in config_data:
            config_data["abs"] = ABSSettings()

        # Load Audible settings - merge env with yaml
        if "audible" not in config_data:
            config_data["audible"] = AudibleSettings()

        config_data["rate_limit"] = APIRateLimitSettings()

        return cls(**config_data)  # type: ignore


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def reload_settings(config_path: Path | None = None) -> Settings:
    """Reload settings from config."""
    global _settings
    _settings = Settings.load(config_path)
    return _settings
