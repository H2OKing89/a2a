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
    library_id: str | None = Field(default=None, description="Default library ID")
    rate_limit_delay: float = Field(default=0.0, description="Delay between requests (0 = disabled)")

    # Security settings
    allow_insecure_http: bool = Field(
        default=False,
        description="Allow HTTP connections (only localhost is allowed by default)",
    )
    tls_ca_bundle: str | None = Field(
        default=None,
        description="Path to CA certificate bundle for self-signed certs",
    )
    insecure_tls: bool = Field(
        default=False,
        description="DANGEROUS: Disable SSL verification entirely (env var ABS_INSECURE_TLS only)",
    )


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

    # Auth file encryption settings
    auth_password: str | None = Field(
        default=None,
        description="Password for encrypting auth file (recommended for security)",
    )
    auth_encryption: str = Field(
        default="json",
        description="Encryption format for auth file ('json' or 'bytes')",
    )
    auth_kdf_iterations: int = Field(
        default=50_000,
        description="PBKDF2 iterations for auth file encryption (max 65535)",
    )

    # Rate limiting
    rate_limit_delay: float = Field(default=0.5, description="Base delay between requests in seconds")
    requests_per_minute: float = Field(default=20.0, description="Maximum requests per minute")
    burst_size: int = Field(default=5, description="Number of requests before burst delay")
    backoff_multiplier: float = Field(default=2.0, description="Backoff multiplier on rate limit errors")
    max_backoff_seconds: float = Field(default=60.0, description="Maximum backoff delay in seconds")


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


class QualityTierConfig(BaseSettings):
    """Configuration for a single quality tier."""

    model_config = SettingsConfigDict(extra="ignore")

    min_bitrate: float = Field(description="Minimum bitrate for this tier (kbps)")
    formats: list[str] = Field(default_factory=list, description="Formats this tier applies to (empty = all)")
    atmos_override: bool = Field(default=False, description="Atmos detection overrides bitrate requirement")


class QualitySettings(BaseSettings):
    """Audio quality thresholds and tier configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    # Legacy thresholds (kept for backwards compatibility)
    bitrate_threshold_kbps: float = Field(default=100.0)
    ultra_bitrate_kbps: float = Field(default=256.0)
    high_bitrate_kbps: float = Field(default=128.0)
    medium_bitrate_kbps: float = Field(default=96.0)
    low_bitrate_kbps: float = Field(default=64.0)

    # Quality scoring weights (must sum to 1.0)
    weight_bitrate: float = Field(default=0.4)
    weight_codec: float = Field(default=0.3)
    weight_spatial: float = Field(default=0.2)
    weight_metadata: float = Field(default=0.1)

    # Tier-based configuration (new)
    tiers: dict[str, QualityTierConfig] = Field(
        default_factory=lambda: {
            "excellent": QualityTierConfig(min_bitrate=256.0, atmos_override=True),
            "better": QualityTierConfig(min_bitrate=128.0, formats=["m4b", "m4a"]),
            "good": QualityTierConfig(min_bitrate=110.0, formats=["m4b", "m4a"]),
            "acceptable": QualityTierConfig(min_bitrate=128.0, formats=["mp3"]),
            "low": QualityTierConfig(min_bitrate=64.0),
            "poor": QualityTierConfig(min_bitrate=0.0),
        },
        description="Quality tier definitions",
    )

    # Atmos detection settings
    atmos_codecs: list[str] = Field(
        default_factory=lambda: ["eac3", "truehd", "ac3"],
        description="Codecs that indicate Dolby Atmos capability",
    )
    atmos_min_channels: int = Field(default=6, description="Minimum channels for Atmos (5.1+)")

    # Premium formats (get tier bonus)
    premium_formats: list[str] = Field(
        default_factory=lambda: ["m4b", "m4a"],
        description="Formats considered premium quality",
    )

    def get_tier_threshold(self, tier: str) -> float:
        """Get the minimum bitrate for a tier."""
        if tier in self.tiers:
            return self.tiers[tier].min_bitrate
        # Fall back to legacy settings
        legacy_map = {
            "excellent": self.ultra_bitrate_kbps,
            "better": self.high_bitrate_kbps,
            "good": self.medium_bitrate_kbps,
            "low": self.low_bitrate_kbps,
            "poor": 0.0,
        }
        return legacy_map.get(tier, 0.0)


class EnrichmentSettings(BaseSettings):
    """Audible enrichment settings."""

    enabled: bool = Field(default=True)
    requests_per_minute: float = Field(default=20.0)
    burst_size: int = Field(default=5)
    backoff_multiplier: float = Field(default=2.0)
    max_backoff_seconds: float = Field(default=60.0, description="Maximum backoff delay in seconds")


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
                abs_yaml = yaml_config["abs"]
                # Enforce insecure_tls as env-only: strip from YAML and warn
                if "insecure_tls" in abs_yaml:
                    import logging

                    logging.getLogger(__name__).warning(
                        "insecure_tls found in config.yaml - this setting is env-var only for safety. "
                        "Use ABS_INSECURE_TLS=1 environment variable instead. Ignoring YAML value."
                    )
                    del abs_yaml["insecure_tls"]
                config_data["abs"] = ABSSettings(**abs_yaml)  # type: ignore
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
