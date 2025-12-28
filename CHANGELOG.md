# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
