# CLAUDE.md - AI Assistant Guide for A2A

**Version:** 0.1.0
**Last Updated:** 2025-12-28

This document provides comprehensive guidance for AI assistants working on the **Audiobook to Audible (A2A)** project. It covers codebase structure, development workflows, conventions, and best practices.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Codebase Structure](#codebase-structure)
- [Core Modules](#core-modules)
- [Development Workflows](#development-workflows)
- [Code Conventions](#code-conventions)
- [Testing Strategy](#testing-strategy)
- [Configuration Management](#configuration-management)
- [Common Tasks](#common-tasks)
- [Key Files Reference](#key-files-reference)
- [CI/CD & Automation](#cicd--automation)

---

## Project Overview

### Purpose
A2A is a **production-quality CLI tool** for managing audiobook libraries via:
- **Audiobookshelf (ABS)** - Self-hosted audiobook server
- **Audible API** - Amazon's audiobook service

### Core Use Cases
1. **Quality Analysis** - Scan audiobook libraries for bitrate, codec, format quality
2. **Upgrade Discovery** - Identify low-quality books with better Audible versions
3. **Series Management** - Track series completion and find missing books
4. **Metadata Enrichment** - Enhance ABS library with Audible metadata

### Technical Stack
- **Python 3.12+** (modern syntax with `|` union types)
- **CLI Framework:** Typer with Rich for beautiful terminal UI
- **Data Validation:** Pydantic with strict type checking
- **HTTP Client:** httpx with HTTP/2 and async support
- **Caching:** SQLite with FTS5 full-text search
- **Testing:** pytest with 577+ test cases

### Statistics
- **~15,208 lines** of production code
- **~7,757 lines** of test code
- **577+ test cases** with comprehensive fixtures
- **120 character** line length
- **Python 3.12+** required

---

## Codebase Structure

### Directory Layout

```
a2a/
├── cli.py                      # Main CLI entry point (Typer app)
├── src/                        # Source code modules
│   ├── __init__.py            # Package version (0.1.0)
│   ├── config.py              # Pydantic settings (299 lines)
│   ├── abs/                   # Audiobookshelf client
│   │   ├── client.py          # Sync client (1,465 lines)
│   │   ├── async_client.py    # Async client (726 lines)
│   │   ├── models.py          # Pydantic models (553 lines)
│   │   └── logging.py         # Logging configuration
│   ├── audible/               # Audible client
│   │   ├── client.py          # Sync client (1,563 lines)
│   │   ├── async_client.py    # Async client (899 lines)
│   │   ├── models.py          # Pydantic models (800 lines)
│   │   ├── encryption.py      # Credential encryption (AES-CBC)
│   │   ├── enrichment.py      # Metadata enrichment service
│   │   └── utils.py           # Marketplace utilities
│   ├── cache/                 # SQLite caching layer
│   │   └── sqlite_cache.py    # Cache with TTL (971 lines)
│   ├── cli/                   # Typer CLI commands
│   │   ├── common.py          # Shared utilities
│   │   ├── abs.py             # ABS commands (958 lines)
│   │   ├── audible.py         # Audible commands (1,156 lines)
│   │   ├── quality.py         # Quality analysis (1,109 lines)
│   │   ├── series.py          # Series management (761 lines)
│   │   └── async_utils.py     # Async helpers
│   ├── quality/               # Quality analysis engine
│   │   ├── analyzer.py        # Quality analyzer (512 lines)
│   │   ├── models.py          # Quality data models
│   │   └── services.py        # Quality services
│   ├── series/                # Series matching
│   │   ├── matcher.py         # Fuzzy matching (927 lines)
│   │   └── models.py          # Series models
│   ├── output/                # Report formatters
│   │   └── formatters.py      # JSON, table formatters
│   └── utils/                 # Utilities
│       ├── ui.py              # Rich UI components (727 lines)
│       ├── security.py        # Security utilities
│       ├── logging.py         # Logging setup
│       └── samples.py         # Sample data generation
├── tests/                      # Test suite
│   ├── conftest.py            # Pytest fixtures (311 lines)
│   ├── test_abs_client.py     # ABS client tests
│   ├── test_audible_client.py # Audible client tests
│   ├── test_quality_analyzer.py
│   ├── test_series_matcher.py # Series matching tests
│   └── ...                    # 20+ more test files
├── tools/                      # Developer utilities
│   ├── dev.py                 # Make-like task runner
│   └── dev_series_explore.py  # Series exploration tool
├── docs/                       # Documentation
│   ├── ABS/                   # API documentation (30+ files)
│   ├── DESIGN_AUDIT.md        # Architecture analysis
│   ├── SECURITY_AUDIT.md      # Security assessment
│   └── ...                    # More design docs
├── .github/                    # GitHub workflows
│   ├── workflows/             # CI, release, pre-commit
│   └── ISSUE_TEMPLATE/        # Bug/feature templates
├── config.yaml.example         # Configuration template
├── .env.example               # Environment variables
├── pyproject.toml             # Tool configuration
├── Makefile                   # Development automation
└── requirements.txt           # Production dependencies
```

### Module Hierarchy

```
ABSClient → SQLiteCache ← AudibleClient
    ↓                           ↓
QualityAnalyzer → AudioQuality  EnrichmentService
    ↓                           ↓
SeriesMatcher ← ABS + Audible Data
    ↓
CLI Commands (Typer)
```

---

## Core Modules

### 1. **src/abs/** - Audiobookshelf Integration

**Purpose:** Interact with self-hosted Audiobookshelf server

**Key Components:**
- `ABSClient` - Synchronous HTTP client with context manager support
- `AsyncABSClient` - Async client for concurrent operations
- 40+ Pydantic models for API responses

**Security Features:**
- HTTPS enforcement (HTTP only allowed for localhost)
- Custom CA bundle support for self-signed certificates
- SSL verification controls
- API key redaction in logs

**Error Hierarchy:**
```python
ABSError (base)
├── ABSConnectionError    # Network failures
├── ABSAuthError         # Authentication issues
└── ABSNotFoundError     # 404 errors
```

**Example Usage:**
```python
from src.abs import ABSClient
from src.config import get_settings

settings = get_settings()
with ABSClient(settings.abs) as client:
    libraries = client.get_libraries()
    items = client.get_library_items(library_id)
```

### 2. **src/audible/** - Audible API Client

**Purpose:** Access Audible library, catalog, and metadata

**Key Features:**
- Built on `audible` library with extensive enhancements
- **Encrypted credential storage** (AES-CBC with PBKDF2)
- **Rate limiting** with exponential backoff
- **Plus Catalog detection** (free with subscription)
- **Pricing parsing** (list price, sale price, credit price)
- **Dolby Atmos detection** (codec + channels analysis)

**Key Models:**
```python
AudibleBook              # Base model
AudibleLibraryItem       # With ownership info
AudibleCatalogProduct    # Catalog search results
PricingInfo              # Parses complex price structures
PlusCatalogInfo          # Plus Catalog membership
```

**Example Usage:**
```python
from src.audible import AudibleClient

with AudibleClient() as client:
    # Search catalog
    results = client.search_catalog("Brandon Sanderson", num_results=20)

    # Get library
    library = client.get_library(num_results=100)
```

### 3. **src/cache/** - SQLite Caching Layer

**Purpose:** Minimize API calls and speed up operations

**Features:**
- **Unified cache** for both ABS and Audible data
- **TTL-based expiration** (configurable per namespace)
- **Namespace isolation** (`abs_items`, `audible_library`, etc.)
- **Full-text search** via FTS5 (title, author)
- **ASIN mapping table** for cross-referencing
- **Memory cache layer** for hot data (LRU-style)
- **WAL mode** for better concurrent access

**Example Usage:**
```python
from src.cache import SQLiteCache

cache = SQLiteCache(db_path="./data/cache/cache.db")

# Cache with TTL
cache.set(namespace="abs_items", key=item_id, value=item_data, ttl_hours=2.0)

# Retrieve
item = cache.get(namespace="abs_items", key=item_id)

# Search
results = cache.search_fts(query="Harry Potter", namespace="abs_items")
```

### 4. **src/quality/** - Audio Quality Analysis

**Purpose:** Analyze audio quality and identify upgrade candidates

**Quality Tier System:**

| Tier | Icon | Criteria | Priority |
|------|------|----------|----------|
| **EXCELLENT** | 💎 | Dolby Atmos OR 256+ kbps | N/A |
| **BETTER** | ✨ | M4B @ 128-255 kbps | N/A |
| **GOOD** | 👍 | M4B @ 110-127 OR MP3 @ 128+ | Low |
| **LOW** | 👎 | M4B @ 64-109 OR MP3 @ 110-127 | Medium |
| **POOR** | 💩 | < 64 kbps OR MP3 < 110 | High |

**Features:**
- Weighted bitrate calculation across multiple audio files
- Format ranking (M4B > M4A > FLAC > MP3)
- Dolby Atmos detection (codec + channel analysis)
- Upgrade priority scoring

**Example Usage:**
```python
from src.quality import QualityAnalyzer

analyzer = QualityAnalyzer(abs_client)
quality = analyzer.analyze_item(abs_item_data)

print(f"Tier: {quality.tier}")
print(f"Bitrate: {quality.bitrate_kbps} kbps")
print(f"Is Atmos: {quality.is_atmos}")
```

### 5. **src/series/** - Series Matching

**Purpose:** Match ABS series with Audible catalog, find missing books

**Features:**
- **Fuzzy matching** via `rapidfuzz` (handles naming variations)
- **Title normalization** (removes "The", series markers, book numbers)
- **Confidence scoring:** EXACT, HIGH, MEDIUM, LOW, NO_MATCH
- **Missing book detection**
- **Plus Catalog filtering** (find free upgrades)
- **Author verification** for disambiguation

**Example Usage:**
```python
from src.series import SeriesMatcher

matcher = SeriesMatcher(abs_client, audible_client)
matches = matcher.match_series(abs_series, audible_results)

for match in matches:
    print(f"{match.abs_series.name} → {match.audible_series.name}")
    print(f"Confidence: {match.confidence}")
```

### 6. **src/cli/** - Typer CLI Commands

**Command Hierarchy:**
```
cli.py (main app)
├── status              # Global status (ABS + Audible + Cache)
├── cache               # Cache management
├── abs/                # Audiobookshelf commands
│   ├── status
│   ├── libraries
│   ├── items
│   ├── search
│   └── ...
├── audible/            # Audible commands
│   ├── login
│   ├── library
│   ├── search
│   └── ...
├── quality/            # Quality analysis
│   ├── scan
│   ├── low
│   └── upgrades
└── series/             # Series management
    ├── list
    └── analyze
```

**Common Utilities (`cli/common.py`):**
- `get_abs_client()` - Factory for ABS client
- `get_audible_client()` - Factory for Audible client
- `get_cache()` - Factory for cache instance
- `resolve_library_id()` - Resolves library ID from args or config
- Formatters: `format_duration()`, `format_size()`, `format_bitrate()`

**Async Utilities (`cli/async_utils.py`):**
- `@async_command` - Decorator for async Typer commands
- `gather_with_progress()` - Parallel operations with progress bars
- `AsyncBatchProcessor` - Batch processing with concurrency control

---

## Development Workflows

### Setup & Installation

```bash
# Clone and navigate
git clone https://github.com/H2OKing89/a2a.git
cd a2a

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Install dependencies
make install-dev           # Production + dev dependencies
# or
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
make setup-hooks

# Install system dependencies
sudo apt install mediainfo  # Ubuntu/Debian
brew install mediainfo      # macOS

# Configure
cp config.yaml.example config.yaml
# Edit config.yaml with your ABS URL and API key

# Verify setup
python cli.py status
make test
```

### Makefile Commands

```bash
make help              # Show all available commands
make install           # Install production dependencies
make install-dev       # Install dev dependencies
make test              # Run pytest
make coverage          # Run tests with HTML coverage report
make lint              # Run flake8 + mypy + bandit
make format            # Run black + isort
make pre-commit        # Run all pre-commit hooks
make setup-hooks       # Install git hooks
make update-hooks      # Update pre-commit hooks
make clean             # Remove cache/build artifacts
make version           # Show current version
make bump-patch        # Bump patch version (0.1.0 → 0.1.1)
make bump-minor        # Bump minor version (0.1.0 → 0.2.0)
make bump-major        # Bump major version (0.1.0 → 1.0.0)
make release-patch     # Create tagged release (bump + tag)
```

### Pre-commit Hooks

Automatically run on `git commit`:

1. **File cleanup** - Trailing whitespace, EOF fixer
2. **YAML/JSON validation** - Syntax checking
3. **Formatting** - black (120 line length), isort
4. **Linting** - flake8 with plugins (bugbear, comprehensions, simplify)
5. **Security** - bandit security scanner
6. **Syntax** - pyupgrade (Python 3.13+)
7. **Spell check** - codespell

**Manual run:**
```bash
make pre-commit           # Run all hooks
pre-commit run --all-files
```

---

## Code Conventions

### Naming Conventions

- **Files:** `snake_case.py`
- **Classes:** `PascalCase` (e.g., `ABSClient`, `QualityAnalyzer`)
- **Functions/Methods:** `snake_case` (e.g., `get_libraries`, `analyze_item`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `BITRATE_EXCELLENT`, `ATMOS_CODECS`)
- **Private methods:** `_leading_underscore` (e.g., `_get`, `_extract_metadata`)
- **Type variables:** `T`, `ModelT`, `ResponseT`

### Import Organization

Use **isort with black profile** (automatically enforced):

```python
# Standard library
import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

# Third-party
import typer
from rich.console import Console
from pydantic import BaseModel, Field

# Local
from src.abs import ABSClient
from src.config import get_settings
from src.quality import QualityAnalyzer

# TYPE_CHECKING imports to avoid circular dependencies
if TYPE_CHECKING:
    from src.audible import AudibleClient
```

### Type Hints

Modern Python 3.12+ syntax:

```python
# Use | instead of Union
def get_item(item_id: str) -> dict[str, Any] | None:
    """Modern union syntax."""
    pass

# Use list, dict instead of List, Dict
def process_items(items: list[str]) -> dict[str, int]:
    """Built-in generics."""
    pass

# Optional is still acceptable but prefer | None
from typing import Optional
def legacy_style(value: Optional[str]) -> None:
    """Older style - avoid in new code."""
    pass
```

### Pydantic Models

Standard pattern for API models:

```python
from pydantic import BaseModel, Field

class MyModel(BaseModel):
    """Model description."""

    # Use alias for camelCase API fields
    my_field: str = Field(alias="myField")
    optional_field: str | None = None
    default_value: int = Field(default=0)

    # Allow extra fields from API (ignore them)
    model_config = {"extra": "ignore", "populate_by_name": True}

    # Computed properties
    @property
    def computed_value(self) -> float:
        """Derived value."""
        return self.default_value * 2.0

    # Factory methods for complex parsing
    @classmethod
    def from_api_response(cls, data: dict) -> "MyModel":
        """Parse complex API response."""
        # Custom parsing logic
        return cls(**data)
```

### Error Handling

Use custom exception hierarchy:

```python
# Define custom exceptions
class MyModuleError(Exception):
    """Base exception for my module."""
    pass

class MyConnectionError(MyModuleError):
    """Network connection error."""
    pass

# Usage in code
def fetch_data(url: str) -> dict:
    """Fetch data with proper error handling."""
    try:
        response = httpx.get(url)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError as e:
        raise MyConnectionError(f"Failed to connect: {e}") from e
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise MyNotFoundError(f"Resource not found: {url}") from e
        raise MyModuleError(f"HTTP error: {e}") from e
    except Exception as e:
        logger.exception("Unexpected error")
        raise
```

### Logging

Use module-level loggers:

```python
import logging

logger = logging.getLogger(__name__)

def my_function():
    """Function with proper logging."""
    logger.debug("Starting operation")
    logger.info("Processing 100 items")
    logger.warning("Rate limit approaching")
    logger.error("Failed to connect", exc_info=True)

    # Structured logging context
    from src.abs.logging import LogContext
    with LogContext(request_id="abc-123"):
        logger.info("Request completed")
```

### Context Managers

Use context managers for resource cleanup:

```python
# Client usage
with get_abs_client() as client:
    libraries = client.get_libraries()

# UI spinners
from src.utils.ui import UI
ui = UI()
with ui.spinner("Loading..."):
    data = fetch_data()

# File operations
from pathlib import Path
config_path = Path("config.yaml")
with config_path.open() as f:
    data = yaml.safe_load(f)
```

### Docstrings

Use **Google style** (enforced by pydocstyle):

```python
def analyze_item(item_data: dict, threshold: float = 100.0) -> AudioQuality:
    """
    Analyze a single ABS library item for audio quality.

    This function evaluates bitrate, codec, format, and spatial audio
    to assign a quality tier and upgrade priority.

    Args:
        item_data: Expanded item data from ABS API (must include media.audio_files)
        threshold: Minimum bitrate in kbps for acceptable quality (default: 100.0)

    Returns:
        AudioQuality instance with tier, score, and upgrade recommendations

    Raises:
        ValueError: If item_data is missing required fields

    Example:
        >>> analyzer = QualityAnalyzer(abs_client)
        >>> quality = analyzer.analyze_item(abs_item_data, threshold=128.0)
        >>> print(f"Tier: {quality.tier}, Score: {quality.quality_score}")
        Tier: GOOD, Score: 75.5
    """
    pass
```

---

## Testing Strategy

### Test Organization

```
tests/
├── conftest.py                # Shared fixtures
├── test_abs_client.py         # ABS client unit tests
├── test_abs_async.py          # ABS async tests
├── test_audible_client.py     # Audible client tests
├── test_audible_encryption.py # Encryption tests
├── test_quality_analyzer.py   # Quality analysis tests
├── test_series_matcher.py     # Series matching tests
├── test_cache.py              # Cache tests
└── test_cli.py                # CLI integration tests
```

### Running Tests

```bash
# Run all tests
make test
pytest

# Run with coverage
make coverage
pytest --cov=src --cov-report=html

# Run specific tests
pytest tests/test_quality_analyzer.py
pytest -k "test_cache"

# Run with markers
pytest -m integration         # Integration tests only
pytest -m "not slow"          # Skip slow tests

# Verbose output
pytest -v --tb=short

# Debug output
pytest -vv -s
```

### Test Fixtures (conftest.py)

Common fixtures available in all tests:

```python
# Mock clients
mock_abs_client                    # Success path
mock_abs_client_conn_error         # Connection failures
mock_abs_client_timeout            # Timeout simulation
mock_abs_client_auth_error         # Authentication failures
mock_abs_client_malformed_response # Bad data handling

mock_audible_client                # Success path
mock_audible_client_rate_limit     # Rate limiting

# Sample data
sample_library_item()              # ABS library item
sample_audible_product()           # Audible catalog product
sample_audio_file()                # Audio file metadata

# Cache
temp_cache                         # Temporary SQLite cache
```

### Writing Tests

```python
import pytest
from src.quality.analyzer import QualityAnalyzer
from src.quality.models import QualityTier

class TestQualityAnalyzer:
    """Tests for QualityAnalyzer."""

    def test_analyze_excellent_tier(self, mock_abs_client, sample_library_item):
        """Test that Dolby Atmos items are marked EXCELLENT."""
        # Arrange
        item = sample_library_item(
            codec="eac3",
            channels=8,
            bitrate=192_000
        )
        analyzer = QualityAnalyzer(mock_abs_client)

        # Act
        result = analyzer.analyze_item(item)

        # Assert
        assert result.tier == QualityTier.EXCELLENT
        assert result.is_atmos is True
        assert result.upgrade_priority == 0

    @pytest.mark.parametrize("bitrate,expected_tier", [
        (256_000, QualityTier.EXCELLENT),
        (192_000, QualityTier.BETTER),
        (64_000, QualityTier.LOW),
    ])
    def test_bitrate_tiers(self, bitrate, expected_tier):
        """Test tier assignment for different bitrates."""
        # Test implementation
        pass

    @pytest.mark.asyncio
    async def test_async_operation(self):
        """Test async functionality."""
        result = await async_function()
        assert result is not None
```

### Test Coverage

Current coverage targets:
- **Overall:** ~33% (goal: 80%+)
- **Core modules:** 60%+ (abs, audible, quality, cache)
- **CLI commands:** 40%+ (integration tests)

### Markers

```python
# Available markers (pyproject.toml)
@pytest.mark.slow              # Slow tests (skippable)
@pytest.mark.integration       # Requires external services
@pytest.mark.asyncio           # Async tests
```

---

## Configuration Management

### Configuration Layers (Priority Order)

1. **Environment variables** (highest priority)
2. **config.yaml** (user configuration)
3. **Defaults** (in Pydantic models)

### config.yaml Structure

```yaml
abs:
  host: https://abs.example.com
  api_key: "your-api-key"
  library_id: "lib-123"           # Optional default
  rate_limit_delay: 0
  allow_insecure_http: false
  tls_ca_bundle: "/path/to/ca.pem"  # For self-signed certs

audible:
  auth_file: ./data/audible_auth.json
  auth_encryption: json           # Encrypted format
  locale: us
  rate_limit_delay: 0.5
  requests_per_minute: 20.0
  burst_size: 5

cache:
  enabled: true
  db_path: ./data/cache/cache.db
  default_ttl_hours: 2.0
  abs_ttl_hours: 2.0
  audible_ttl_hours: 240.0        # 10 days

quality:
  bitrate_threshold_kbps: 100.0

paths:
  data_dir: ./data
  cache_dir: ./data/cache
  reports_dir: ./data/reports
```

### Environment Variables

```bash
# .env file or shell export

# ABS settings
ABS_URL=http://localhost:13378
ABS_API_KEY=your_key
ABS_LIBRARY_ID=lib-123
ABS_INSECURE_TLS=1              # DANGEROUS: disable SSL verification

# Audible settings
AUDIBLE_AUTH_FILE=./data/audible_auth.json
AUDIBLE_AUTH_PASSWORD=your_encryption_password
AUDIBLE_LOCALE=us

# Cache settings
CACHE_ENABLED=true
CACHE_DB_PATH=./data/cache/cache.db
```

### Settings Access

```python
from src.config import get_settings, reload_settings

# Get singleton instance (cached)
settings = get_settings()

# Access nested settings
print(settings.abs.host)
print(settings.audible.locale)
print(settings.cache.db_path)

# Reload from file (e.g., after config change)
settings = reload_settings(config_path=Path("custom_config.yaml"))
```

### Security Settings

**IMPORTANT:** Never commit these files:
- `config.yaml` (contains API keys)
- `data/audible_auth.json` (encrypted credentials)
- `.env` (environment variables)

Always use `.example` files as templates.

**Credential Encryption:**
```bash
# Encrypt existing Audible credentials
export AUDIBLE_AUTH_PASSWORD="your-secure-password"
python cli.py audible encrypt

# Check encryption status
python cli.py audible status
```

---

## Common Tasks

### Adding a New CLI Command

1. **Create command in appropriate sub-app:**

```python
# In src/cli/abs.py
@abs_app.command("my-command")
def my_new_command(
    library_id: str = typer.Argument(..., help="Library ID"),
    limit: int = typer.Option(50, "--limit", "-l", help="Result limit"),
    output: str = typer.Option("table", "--output", "-o", help="Output format"),
):
    """
    Brief description of what the command does.

    Longer explanation if needed.
    """
    ui = UI()

    try:
        with ui.spinner("Loading data..."):
            with get_abs_client() as client:
                data = client.some_method(library_id, limit=limit)

        # Display results
        if output == "json":
            print(orjson.dumps(data, option=orjson.OPT_INDENT_2).decode())
        else:
            # Create Rich table
            table = ui.create_table("Results", ["Column1", "Column2"])
            for item in data:
                table.add_row(item["field1"], item["field2"])
            ui.print(table)

    except ABSError as e:
        ui.error(f"ABS error: {e}")
        raise typer.Exit(1)
```

2. **Add tests:**

```python
# In tests/test_cli.py
def test_my_new_command(cli_runner, mock_abs_client):
    """Test the new command."""
    result = cli_runner.invoke(app, ["abs", "my-command", "lib-123"])
    assert result.exit_code == 0
    assert "expected output" in result.stdout
```

3. **Update documentation if needed**

### Adding a New Pydantic Model

1. **Define model in appropriate models.py:**

```python
# In src/abs/models.py or src/audible/models.py
from pydantic import BaseModel, Field

class MyNewModel(BaseModel):
    """Description of the model."""

    # Fields with API aliases
    field_name: str = Field(alias="fieldName")
    optional_field: int | None = None
    list_field: list[str] = Field(default_factory=list)

    # Configuration
    model_config = {
        "extra": "ignore",
        "populate_by_name": True,  # Accept both fieldName and field_name
    }

    # Computed properties
    @property
    def computed_value(self) -> str:
        """Derived value."""
        return f"{self.field_name}_computed"
```

2. **Add tests:**

```python
# In tests/test_models.py
def test_my_new_model():
    """Test model parsing."""
    data = {"fieldName": "test", "optional_field": 42}
    model = MyNewModel(**data)

    assert model.field_name == "test"
    assert model.optional_field == 42
    assert model.computed_value == "test_computed"
```

### Adding a New API Client Method

1. **Add method to client class:**

```python
# In src/abs/client.py or src/audible/client.py
def get_new_resource(
    self,
    resource_id: str,
    include_details: bool = False,
) -> MyNewModel:
    """
    Fetch a new resource from the API.

    Args:
        resource_id: ID of the resource to fetch
        include_details: Whether to include extended details

    Returns:
        MyNewModel instance

    Raises:
        ABSNotFoundError: If resource doesn't exist
        ABSConnectionError: If network error occurs
    """
    params = {}
    if include_details:
        params["expanded"] = "1"

    # Use _get helper (handles auth, rate limiting, errors)
    response = self._get(f"/api/resources/{resource_id}", params=params)

    # Parse and return
    return MyNewModel(**response)
```

2. **Add tests:**

```python
# In tests/test_abs_client.py
def test_get_new_resource(mock_abs_client):
    """Test fetching new resource."""
    result = mock_abs_client.get_new_resource("res-123", include_details=True)
    assert isinstance(result, MyNewModel)
    assert result.field_name == "expected_value"
```

### Adding a New Quality Analyzer Rule

1. **Update quality tier logic:**

```python
# In src/quality/analyzer.py
def _calculate_tier(self, quality_data: dict) -> QualityTier:
    """Calculate quality tier with new rule."""
    bitrate = quality_data["bitrate_kbps"]
    codec = quality_data["codec"]
    format_ext = quality_data["format"]

    # New rule: Check for new premium codec
    if codec == "new_premium_codec":
        return QualityTier.EXCELLENT

    # Existing rules...
    if self._is_atmos(quality_data) or bitrate >= 256:
        return QualityTier.EXCELLENT

    # ... rest of tier logic
```

2. **Add configuration if needed:**

```python
# In src/config.py
class QualitySettings(BaseSettings):
    """Quality settings."""

    # Add new threshold
    new_codec_threshold: float = Field(default=192.0)
    premium_codecs: list[str] = Field(
        default_factory=lambda: ["eac3", "truehd", "new_premium_codec"]
    )
```

3. **Add tests:**

```python
# In tests/test_quality_analyzer.py
def test_new_premium_codec_tier():
    """Test that new premium codec gets EXCELLENT tier."""
    quality_data = {
        "codec": "new_premium_codec",
        "bitrate_kbps": 128.0,
        "format": "m4b",
    }
    tier = analyzer._calculate_tier(quality_data)
    assert tier == QualityTier.EXCELLENT
```

### Working with Cache

```python
from src.cache import SQLiteCache
from src.config import get_settings

settings = get_settings()
cache = SQLiteCache(db_path=settings.cache.db_path)

# Store data
cache.set(
    namespace="my_namespace",
    key="item_123",
    value={"title": "Book Title", "author": "Author Name"},
    ttl_hours=24.0,
)

# Retrieve data
item = cache.get(namespace="my_namespace", key="item_123")

# Check if cached
if cache.exists(namespace="my_namespace", key="item_123"):
    print("Item is cached")

# Clear namespace
cache.clear_namespace("my_namespace")

# Full-text search
results = cache.search_fts(
    query="Book Title",
    namespace="my_namespace",
    limit=10,
)
```

---

## Key Files Reference

### Essential Reading

| File | Purpose | Lines |
|------|---------|-------|
| `cli.py` | Main CLI entry point | 261 |
| `src/config.py` | Settings management | 299 |
| `src/abs/client.py` | ABS sync client | 1,465 |
| `src/audible/client.py` | Audible sync client | 1,563 |
| `src/cache/sqlite_cache.py` | SQLite cache | 971 |
| `src/quality/analyzer.py` | Quality analysis | 512 |
| `src/series/matcher.py` | Series matching | 927 |
| `tests/conftest.py` | Test fixtures | 311 |

### Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Tool configuration (pytest, black, mypy) |
| `.flake8` | Flake8 linting rules |
| `.pre-commit-config.yaml` | Pre-commit hooks |
| `config.yaml.example` | Configuration template |
| `.env.example` | Environment variables template |
| `requirements.txt` | Production dependencies |
| `requirements-dev.txt` | Development dependencies |

### Documentation

| File | Purpose |
|------|---------|
| `README.md` | User-facing documentation |
| `CONTRIBUTING.md` | Contribution guidelines |
| `SECURITY.md` | Security policy |
| `CODE_OF_CONDUCT.md` | Community standards |
| `CHANGELOG.md` | Release notes |
| `docs/DESIGN_AUDIT.md` | Architecture analysis |
| `docs/SECURITY_AUDIT.md` | Security assessment |

---

## CI/CD & Automation

### GitHub Actions Workflows

**`.github/workflows/ci.yml`** - Main CI pipeline:
- **Test job:** Matrix testing on Python 3.12 & 3.13
- **Lint job:** black, isort, flake8
- **Security job:** bandit security scanner
- **Type-check job:** mypy (informational, failures allowed)
- **Coverage:** Codecov integration

**`.github/workflows/dependency-review.yml`:**
- Scans PRs for vulnerable dependencies
- Runs on pull_request events

**`.github/workflows/pre-commit-autoupdate.yml`:**
- Weekly automatic hook updates
- Creates PR with updates

**`.github/workflows/release.yml`:**
- Triggered on tag push (`v*`)
- Creates GitHub release with changelog

### Pre-commit Hooks

**Auto-runs on `git commit`:**

1. **trailing-whitespace** - Remove trailing spaces
2. **end-of-file-fixer** - Ensure newline at EOF
3. **check-yaml** - Validate YAML syntax
4. **check-json** - Validate JSON syntax
5. **check-added-large-files** - Prevent large file commits
6. **check-merge-conflict** - Detect merge conflict markers
7. **black** - Code formatting (120 chars)
8. **isort** - Import sorting
9. **flake8** - Linting (with plugins)
10. **bandit** - Security scanning
11. **pyupgrade** - Python syntax upgrades (3.13+)
12. **codespell** - Spell checking

**Update hooks:**
```bash
make update-hooks
pre-commit autoupdate
```

### Release Process

**Semantic Versioning:** `MAJOR.MINOR.PATCH`

**Create a release:**
```bash
# Ensure clean working tree on main branch
git status

# Bump version and create tag
make release-patch         # 0.1.0 → 0.1.1

# Push to trigger release workflow
git push origin main --tags
```

**Manual version bump:**
```bash
make bump-patch            # 0.1.0 → 0.1.1
make bump-minor            # 0.1.0 → 0.2.0
make bump-major            # 0.1.0 → 1.0.0
```

**Version is stored in:** `src/__init__.py`

```python
__version__ = "0.1.0"
```

### Deployment Checklist

Before releasing:

- [ ] All tests pass (`make test`)
- [ ] Linting passes (`make lint`)
- [ ] Pre-commit hooks pass (`make pre-commit`)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped
- [ ] Clean working tree
- [ ] On main branch

---

## Best Practices for AI Assistants

### When Working on This Project

1. **Always read files before editing** - Never propose changes to code you haven't seen
2. **Run tests frequently** - Use `make test` after changes
3. **Follow existing patterns** - Maintain consistency with codebase style
4. **Add tests for new features** - Test coverage is important
5. **Update documentation** - Keep docs in sync with code changes
6. **Use type hints** - Follow modern Python 3.12+ syntax
7. **Handle errors properly** - Use custom exception hierarchy
8. **Respect security boundaries** - Never commit secrets, use encryption
9. **Keep it simple** - Don't over-engineer, minimal changes for requirements
10. **Format before committing** - Run `make format` and `make lint`

### Common Pitfalls to Avoid

❌ **Don't:**
- Commit `config.yaml`, `data/`, `.env` files
- Use Union/Optional instead of modern `|` syntax
- Skip tests for new functionality
- Hardcode API keys or credentials
- Ignore security warnings from bandit
- Use `print()` for logging (use `logger`)
- Create new files unnecessarily
- Over-engineer simple features

✅ **Do:**
- Use `get_settings()` for configuration
- Use context managers for clients (`with get_abs_client()`)
- Add docstrings to public functions
- Use Pydantic models for data validation
- Cache API responses when possible
- Handle rate limiting gracefully
- Write clear commit messages (conventional commits)
- Ask for clarification when uncertain

### Getting Help

- **Documentation:** Check `docs/` directory
- **Examples:** Look at existing similar code
- **Tests:** Review test files for usage patterns
- **Issues:** Search GitHub issues for similar problems
- **Code search:** Use grep to find examples of pattern usage

---

## Appendix

### Quality Tier Reference

```python
from src.quality.models import QualityTier

# Tier enum values
QualityTier.EXCELLENT  # 💎 Dolby Atmos OR 256+ kbps
QualityTier.BETTER     # ✨ M4B @ 128-255 kbps
QualityTier.GOOD       # 👍 M4B @ 110-127 OR MP3 @ 128+
QualityTier.LOW        # 👎 M4B @ 64-109 OR MP3 @ 110-127
QualityTier.POOR       # 💩 < 64 kbps OR MP3 < 110
```

### Dolby Atmos Detection

```python
# Codecs that indicate Atmos capability
ATMOS_CODECS = ["eac3", "truehd", "ac3"]

# Minimum channels for Atmos (5.1+ or 7.1+)
ATMOS_MIN_CHANNELS = 6

# Detection logic
is_atmos = codec.lower() in ATMOS_CODECS and channels >= ATMOS_MIN_CHANNELS
```

### Format Ranking

```python
# Format preference (for equal bitrates)
FORMAT_RANKS = {
    "m4b": 1,    # Best (AAC in audiobook container)
    "m4a": 2,    # Very good (AAC)
    "flac": 3,   # Good (lossless but large)
    "mp3": 4,    # Acceptable (lossy)
    "ogg": 5,    # Lower priority
    "opus": 6,   # Lower priority
}
```

### Cache Namespaces

```python
# Predefined cache namespaces
"abs_items"           # ABS library items
"abs_libraries"       # ABS libraries
"audible_library"     # Audible library items
"audible_catalog"     # Audible catalog search results
"quality_analysis"    # Quality analysis results
"series_matches"      # Series matching results
```

### Environment Variable Reference

```bash
# ABS
ABS_URL                       # ABS server URL
ABS_API_KEY                   # ABS API key
ABS_LIBRARY_ID                # Default library ID
ABS_ALLOW_INSECURE_HTTP       # Allow HTTP (localhost only)
ABS_TLS_CA_BUNDLE             # Custom CA bundle path
ABS_INSECURE_TLS              # DANGEROUS: disable SSL verification

# Audible
AUDIBLE_AUTH_FILE             # Path to auth file
AUDIBLE_AUTH_PASSWORD         # Encryption password
AUDIBLE_LOCALE                # Marketplace (us, uk, de, etc.)
AUDIBLE_RATE_LIMIT_DELAY      # Delay between requests (seconds)
AUDIBLE_REQUESTS_PER_MINUTE   # Rate limit

# Cache
CACHE_ENABLED                 # Enable/disable cache
CACHE_DB_PATH                 # SQLite database path
CACHE_DEFAULT_TTL_HOURS       # Default TTL
CACHE_ABS_TTL_HOURS          # ABS data TTL
CACHE_AUDIBLE_TTL_HOURS      # Audible data TTL

# General
DEBUG                         # Enable debug logging
VERBOSE                       # Enable verbose output
```

---

**End of CLAUDE.md**

*For questions or updates, consult the maintainers or open an issue on GitHub.*
