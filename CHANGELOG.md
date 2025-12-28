# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2025-12-28

### Added
- Async batch enrichment service for Audible quality discovery
- License-request based audio quality detection (discovers actual bitrates like Widevine HE-AAC ~114 kbps, Dolby Atmos)
- New CLI flag `--fast` for `quality upgrades` to skip license requests
- New models: `AudioFormat`, `ContentQualityInfo`, `LICENSE_TEST_CONFIGS` for quality analysis
- ASIN column in `quality upgrades` output table
- "Best Available" quality display in upgrade recommendations
- `AsyncAudibleEnrichmentService` for concurrent enrichment with quality discovery

### Fixed
- Missing Audible pricing in `quality upgrades` (added `price` to catalog response groups)
- Progress bar stuck at 0% during async batch enrichment (now updates live per completion)
- Malformed catalog product responses causing crashes (now handles ValidationError gracefully)
- Rate limit delay not applied from config in async client (now passes `settings.audible.rate_limit_delay`)

### Changed
- Improved `quality upgrades` table layout: removed Priority/Owned columns, simplified Recommendation text
- Enhanced UX with live progress updates during quality discovery
- Better codec/bitrate parsing from catalog API responses (handles multiple format variations)

### Performance
- Concurrent async quality discovery with configurable semaphore limits
- Caching for enrichment results (6-hour TTL)
- Progress reporting via callback for better user feedback

## [0.1.0] - 2025-12-28

### Added
- Initial release of A2A (Audiobook to Audible) CLI tool
- Audiobookshelf (ABS) API client with async support
- Audible API client with authentication and rate limiting
- Audio quality analysis with tier classification
- SQLite-based caching layer with TTL and namespaces
- Series management and tracking
- Rich CLI with progress bars and styled tables
- Comprehensive test suite
- Pre-commit hooks for code quality
- CI/CD pipeline with GitHub Actions
- Dependabot configuration for dependency updates

### Quality Tiers
- EXCELLENT: Dolby Atmos OR 256+ kbps
- GOOD: M4B @ 128-255 kbps
- ACCEPTABLE: M4B @ 110-127 kbps OR MP3 @ 128+ kbps
- LOW/POOR: Below thresholds

## [0.1.0] - 2025-12-28

### Added
- Core project structure
- ABS client implementation (`src/abs/`)
- Audible client implementation (`src/audible/`)
- Quality analyzer (`src/quality/`)
- Cache system (`src/cache/`)
- CLI commands for:
  - `abs` - Audiobookshelf management
  - `audible` - Audible integration
  - `quality` - Audio quality analysis
  - `series` - Series management
- Configuration via `config.yaml` and environment variables
- Pydantic models for API responses
- Custom exception hierarchy
- Output formatters for reports

### Infrastructure
- pytest test suite with fixtures
- Black + isort code formatting
- flake8 + mypy + bandit linting
- Pre-commit hooks
- GitHub Actions CI workflow
- Dependabot for dependency updates

---

[Unreleased]: https://github.com/H2OKing89/a2a/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/H2OKing89/a2a/releases/tag/v0.1.0
