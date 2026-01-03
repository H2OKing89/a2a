# Copilot Instructions for A2A (Audiobook to Audible)

## Project Overview
CLI tool for audiobook library management via **Audiobookshelf (ABS)** and **Audible** APIs. Analyzes audio quality in ABS libraries and identifies upgrade candidates from Audible.

## Architecture

### Module Structure & Data Flow
```
cli.py              → Entry point, assembles Typer subcommands from src/cli/
src/cli/            → Command implementations (abs.py, audible.py, quality.py, series.py)
src/abs/            → ABS API client (sync + async)
src/audible/        → Audible API client (sync + async) + enrichment service
src/quality/        → Quality tier analysis (analyzer.py, models.py)
src/series/         → Series matching with rapidfuzz
src/cache/          → SQLite caching layer (shared by both API clients)
src/config.py       → Pydantic-settings configuration
```

**Data Flow**: `ABSClient` → `QualityAnalyzer` → `AudibleEnrichmentService` → `SQLiteCache`

### Client Pattern (Both ABS and Audible)
```python
# Always use context managers for clients
from src.cli.common import get_abs_client, get_audible_client

with get_abs_client() as client:
    items = client.get_library_items(library_id)

# Clients support optional cache injection
client = ABSClient(host, api_key, cache=get_cache())
```

## Code Conventions

### Pydantic Models (Critical Pattern)
```python
# API responses use camelCase aliases, Python uses snake_case
class AudioFile(BaseModel):
    bit_rate: int = Field(default=0, alias="bitRate")
    channel_layout: str | None = Field(default=None, alias="channelLayout")

    model_config = {"extra": "ignore", "populate_by_name": True}
```
- Always `extra="ignore"` - APIs return undocumented fields
- See [src/abs/models.py](../src/abs/models.py) and [src/audible/models.py](../src/audible/models.py)

### Configuration (Layered)
```python
from src.config import get_settings
settings = get_settings()  # Singleton, loads config.yaml → .env → env vars

# Subsystem settings:
settings.abs.host          # ABSSettings
settings.audible.locale    # AudibleSettings  
settings.cache.db_path     # CacheSettings
settings.cache.pricing_ttl_hours  # TTL for pricing/deal data (default 6h, respects month boundaries)
settings.quality.bitrate_threshold_kbps  # QualitySettings
```

### Error Hierarchy
```python
# ABS: ABSError → ABSConnectionError, ABSAuthError, ABSNotFoundError
# Audible: AudibleError → AudibleAuthError, AudibleNotFoundError, AudibleRateLimitError
```

### Quality Tiers ([src/quality/models.py](../src/quality/models.py))
```python
QualityTier.EXCELLENT  # Dolby Atmos OR 256+ kbps
QualityTier.BETTER     # m4b @ 128-255 kbps  
QualityTier.GOOD       # m4b @ 110-127 kbps OR mp3 @ 128+ kbps
QualityTier.LOW        # m4b @ 64-109 kbps OR mp3 @ 110-127 kbps
QualityTier.POOR       # < 64 kbps
```

## Developer Workflow

```bash
make install-dev       # Setup with dev dependencies
python cli.py status   # Verify ABS/Audible connections
make test              # pytest (use -k "pattern" for specific tests)
make format            # black + isort (120 char line length)
make lint              # flake8 + mypy + bandit
```

### CLI Structure
```bash
python cli.py abs libraries      # List ABS libraries
python cli.py quality scan -l ID # Scan library for quality
python cli.py audible library    # Show Audible library
python cli.py series analyze ID  # Series completion analysis
```

## Testing Patterns

### Mock Fixtures ([tests/conftest.py](../tests/conftest.py))
```python
def test_something(mock_abs_client):              # Success path
def test_connection(mock_abs_client_conn_error):  # Network failure
def test_timeout(mock_abs_client_timeout):        # Timeout handling
def test_bad_data(mock_abs_client_malformed_response):  # Invalid API data
```

## Key Implementation Details

### Enrichment Service ([src/audible/enrichment.py](../src/audible/enrichment.py))
Combines catalog data, library ownership, Plus Catalog status, and pricing into `AudibleEnrichment` model. Used by quality analysis and series matching.

### Series Matching ([src/series/matcher.py](../src/series/matcher.py))
Uses rapidfuzz for fuzzy string matching between ABS and Audible series names. Handles title normalization (removes "The ", "Series", book numbers).

### SQLite Cache ([src/cache/sqlite_cache.py](../src/cache/sqlite_cache.py))
```python
cache.set("audible_library", asin, data, ttl_hours=240)  # Namespace + TTL
cache.search_by_title("Project Hail Mary")  # Full-text search
cache.clear_pricing_caches()  # Clear all pricing namespaces (no params)
```

**Month-Boundary-Aware TTL**: Pricing/deal caches in the Audible enrichment service automatically use month-aware TTL via `calculate_pricing_ttl_seconds()`, expiring before month end since Audible's monthly deals reset on the 1st. When month boundaries approach, TTL is capped to prevent stale deals carrying over to the next month. Developers building custom pricing caches can invoke `calculate_pricing_ttl_seconds()` directly:
```python
from src.cache import calculate_pricing_ttl_seconds

ttl_sec = calculate_pricing_ttl_seconds(requested_ttl_seconds=3600)  # 1 hour → capped to month boundary
cache.set("audible_deals", asin, deal_data, ttl_seconds=ttl_sec)
```
`clear_pricing_caches()` takes no parameters and clears all `PRICING_NAMESPACES` internally.

### Async Clients
Both clients have async variants (`AsyncABSClient`, `AsyncAudibleClient`) for concurrent operations. Use `async with` context managers.
