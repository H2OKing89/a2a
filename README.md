# 🎧 Audiobook to Audible (A2A)

[![CI](https://github.com/H2OKing89/a2a/actions/workflows/ci.yml/badge.svg)](https://github.com/H2OKing89/a2a/actions/workflows/ci.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A CLI tool for managing audiobook libraries via **Audiobookshelf (ABS)** and **Audible** APIs. Analyze audio quality in your ABS libraries and identify books that could be upgraded from Audible.

## ✨ Features

- **🔍 Quality Analysis**: Analyze audio quality (bitrate, codec, format) of your audiobook library
- **📊 Upgrade Recommendations**: Identify low-quality audiobooks that can be upgraded from Audible
- **🔗 Audible Integration**: Enrich your library with metadata from Audible
- **📚 Series Management**: Track and manage audiobook series across your library
- **💾 Smart Caching**: SQLite-based caching to minimize API calls
- **🎨 Rich CLI**: Beautiful terminal output with progress bars and styled tables

## 📋 Requirements

- Python 3.13 or higher
- [Audiobookshelf](https://www.audiobookshelf.org/) server (self-hosted)
- Audible account (for enrichment features)
- `mediainfo` system package (for audio analysis)

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/H2OKing89/a2a.git
cd a2a
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

### 3. Install dependencies

```bash
# Production only
make install

# With development tools
make install-dev
```

### 4. Install system dependencies

```bash
# Ubuntu/Debian
sudo apt install mediainfo

# macOS
brew install mediainfo

# Arch Linux
sudo pacman -S mediainfo
```

### 5. Configure the tool

Copy the example configuration and edit it:

```bash
cp config.yaml.example config.yaml
```

Or use environment variables (`.env` file):

```env
ABS_URL=http://your-audiobookshelf-server:13378
ABS_API_KEY=your-api-key
AUDIBLE_AUTH_FILE=data/audible_auth.json
```

## 📖 Usage

### Check ABS Connection

```bash
python cli.py status
```

### List Libraries

```bash
python cli.py abs libraries
```

### Analyze Audio Quality

```bash
python cli.py quality analyze <library-id>
```

### View Upgrade Candidates

```bash
python cli.py quality upgrades <library-id>
```

### Audible Authentication

```bash
python cli.py audible auth
```

### Series Management

```bash
python cli.py series list <library-id>
python cli.py series analyze <library-id>
```

## 🧰 Developer utilities

- `tools/dev.py` (make-like helper)
- `tools/dev_series_explore.py` (series matching exploration)

## 🏗️ Architecture

```basah
src/
├── abs/          # Audiobookshelf API client
├── audible/      # Audible API client
├── cache/        # SQLite caching layer
├── cli/          # CLI command modules
├── quality/      # Audio quality analysis
├── series/       # Series management
├── output/       # Output formatters
└── utils/        # Utility helpers
```

### Key Components

| Component | Description |
|-----------|-------------|
| `ABSClient` | Async/sync client for Audiobookshelf API |
| `AudibleClient` | Client for Audible API with authentication |
| `QualityAnalyzer` | Audio quality tier calculation |
| `SQLiteCache` | Unified caching with TTL and namespaces |

### Quality Tiers

| Tier | Criteria |
|------|----------|
| 🌟 Excellent | Dolby Atmos OR 256+ kbps |
| ✅ Good | M4B @ 128-255 kbps |
| ⚠️ Acceptable | M4B @ 110-127 kbps OR MP3 @ 128+ kbps |
| ❌ Low/Poor | Below thresholds |

## 🧪 Development

### Running Tests

```bash
# Run all tests
make test

# With coverage report
make coverage

# Run specific tests
pytest -k "test_quality"
```

### Code Quality

```bash
# Format code
make format

# Run linters
make lint

# Run all pre-commit hooks
make pre-commit
```

### Pre-commit Hooks

```bash
# Install hooks
make setup-hooks

# Update hooks to latest versions
make update-hooks
```

## 📁 Project Structure

```
a2a/
├── .github/              # GitHub configuration
│   ├── workflows/        # CI/CD workflows
│   └── copilot-instructions.md
├── src/                  # Source code
├── tests/                # Test suite
├── docs/                 # Documentation
├── data/                 # Runtime data (gitignored)
├── cli.py                # Main entry point
├── config.yaml           # Configuration file
├── pyproject.toml        # Project configuration
├── requirements.txt      # Production dependencies
└── requirements-dev.txt  # Development dependencies
```

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Audiobookshelf](https://www.audiobookshelf.org/) - Self-hosted audiobook server
- [audible](https://github.com/mkb79/audible) - Python Audible API client
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Terminal formatting

## 📞 Support

- 🐛 [Report bugs](https://github.com/H2OKing89/a2a/issues/new?template=bug_report.md)
- 💡 [Request features](https://github.com/H2OKing89/a2a/issues/new?template=feature_request.md)
- 📖 [Documentation](docs/)

---

Made with ❤️ for audiobook enthusiasts
