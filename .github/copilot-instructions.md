# Copilot Instructions for Audiobook Management Tool

## Project Overview
CLI tool for managing audiobook libraries via **Audiobookshelf (ABS)** and **Audible** APIs. Core use case: analyze audio quality in ABS libraries and identify books that could be upgraded from Audible.

## Architecture

### Module Structure
```
src/
├── abs/          # Audiobookshelf API client
├── audible/      # Audible API client  
├── cache/        # SQLite caching layer (shared by both clients)
├── quality/      # Audio quality analysis (analyzer, enrichment, models)
└── utils/        # Helpers (sample data generation)
```

### Key Data Flow
1. `ABSClient` fetches library items from Audiobookshelf server
2. `QualityAnalyzer` evaluates each item's audio quality (bitrate, codec, format)
3. `AudibleClient` enriches data with Audible metadata for upgrade candidates
4. `SQLiteCache` provides unified caching across both API clients

### Client Pattern
Both API clients follow the same pattern:
- Constructor injection for `SQLiteCache` instance (optional)
- Context manager support (`with get_abs_client() as client:`)
- Rate limiting built into `_request()` methods
- Pydantic models for all API responses

## Code Conventions

### Pydantic Models
- Use `Field(alias="camelCase")` for API responses, snake_case for Python attributes
- Always set `model_config = {"extra": "ignore"}` to handle unknown API fields
- See [src/abs/models.py](src/abs/models.py) for ABS response models
- See [src/audible/models.py](src/audible/models.py) for Audible response models

### Configuration
- Settings via `pydantic-settings` in [src/config.py](src/config.py)
- Layered: `config.yaml` → `.env` → environment variables
- Access via `get_settings()` singleton
- Each subsystem has its own settings class (`ABSSettings`, `AudibleSettings`, `CacheSettings`)

### Error Handling
Custom exceptions per client:
- ABS: `ABSError`, `ABSConnectionError`, `ABSAuthError`, `ABSNotFoundError`
- Audible: `AudibleError`, `AudibleAuthError`, `AudibleRateLimitError`

### Quality Tier Logic
Defined in [src/quality/models.py](src/quality/models.py#L10):
- `EXCELLENT`: Dolby Atmos OR 256+ kbps
- `GOOD`: m4b @ 128-255 kbps
- `ACCEPTABLE`: m4b @ 110-127 kbps OR mp3 @ 128+ kbps
- `LOW/POOR`: Below thresholds

## Developer Workflow

### Setup & Run
```bash
make install-dev    # Install all dependencies
python cli.py status  # Test ABS connection
python cli.py quality analyze <library-id>  # Analyze quality
```

### Testing
```bash
make test           # Run pytest
make coverage       # With coverage report
pytest -k "test_quality"  # Run specific tests
```

### Code Quality
```bash
make format         # black + isort
make lint           # flake8 + mypy + bandit
make pre-commit     # Run all hooks
```

### Configuration (120 char line length)
- Black and isort configured for Python 3.13
- Type hints encouraged but `disallow_untyped_defs = false`

## Testing Patterns

### Fixtures ([tests/conftest.py](tests/conftest.py))
Mock clients available for different scenarios:
- `mock_abs_client` - Success path
- `mock_abs_client_conn_error` - Connection failures
- `mock_abs_client_timeout` - Timeout simulation
- `mock_abs_client_malformed_response` - Bad data handling

### Sample Data
Golden samples in `data/samples/` for testing without live APIs.
Use `src/utils/samples.py` to generate new samples.

## Key Files for Reference
- [cli.py](cli.py) - Typer CLI entry point with subcommands (`audible`, `quality`, `abs`)
- [src/cache/sqlite_cache.py](src/cache/sqlite_cache.py) - Caching with TTL, namespaces, FTS
- [src/quality/analyzer.py](src/quality/analyzer.py) - Quality tier calculation logic
- [config.yaml](config.yaml) - Default configuration values
