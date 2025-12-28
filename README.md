<div align="center">

# 🎧 Audiobook to Audible (A2A)

**A powerful CLI tool for managing audiobook libraries via Audiobookshelf and Audible APIs**

[![CI](https://github.com/H2OKing89/a2a/actions/workflows/ci.yml/badge.svg)](https://github.com/H2OKing89/a2a/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-usage">Usage</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-security">Security</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

*Analyze audio quality • Find upgrade candidates • Enrich with Audible metadata • Track series completion*

</div>

## ✨ Features

<table>
<tr>
<td width="50%">

### 🔍 Quality Analysis
Analyze audio quality (bitrate, codec, format) across your entire library with intelligent tier classification.

### 📊 Upgrade Recommendations  
Identify low-quality audiobooks and find matching Audible versions with pricing data.

### 🔗 Audible Integration
Seamless authentication, library access, catalog search, and metadata enrichment.

</td>
<td width="50%">

### 📚 Series Management
Track series completion, find missing books, and match ABS series with Audible catalogs.

### 💾 Smart Caching
SQLite-based caching with TTL and namespaces to minimize API calls and speed up operations.

### 🎨 Rich CLI Experience
Beautiful terminal output with progress bars, styled tables, spinners, and visual feedback.

</td>
</tr>
</table>

## 📋 Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Python** | 3.12+ | Tested on 3.12 and 3.13 |
| **Audiobookshelf** | Any | Self-hosted audiobook server |
| **Audible Account** | — | For enrichment features |
| **mediainfo** | Any | System package for audio analysis |

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/H2OKing89/a2a.git && cd a2a
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp config.yaml.example config.yaml
# Edit config.yaml with your ABS URL and API key

# Verify connection
python cli.py status
```

<details>
<summary><strong>📦 Detailed Installation</strong></summary>

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

Copy the example configuration:

```bash
cp config.yaml.example config.yaml
```

Or use environment variables (`.env` file):

```env
ABS_URL=https://your-audiobookshelf-server:13378
ABS_API_KEY=your-api-key
AUDIBLE_AUTH_FILE=data/audible_auth.json
```

</details>

## 📖 Usage

### Command Structure

```
cli.py
├── status              # Global status (ABS + Audible + Cache)
├── cache               # Manage unified SQLite cache
├── abs                 # 📚 Audiobookshelf commands
├── audible             # 🎧 Audible commands  
├── quality             # 💎 Quality analysis commands
└── series              # 📖 Series management commands
```

### Core Commands

<details open>
<summary><strong>📚 Audiobookshelf (ABS)</strong></summary>

```bash
# Check connection
python cli.py abs status

# List libraries
python cli.py abs libraries

# Browse items with filtering
python cli.py abs items <library-id> --limit 50

# Search your library
python cli.py abs search <library-id> "Harry Potter"

# View item details
python cli.py abs item <item-id>

# Export library to JSON
python cli.py abs export <library-id> -o library.json
```

| Command | Description |
|---------|-------------|
| `status` | Check ABS connection status |
| `libraries` | List all libraries |
| `stats` | Show library statistics |
| `items` | List library items |
| `item` | Show details for a specific item |
| `search` | Search a library |
| `export` | Export all library items to JSON |
| `authors` | List authors in the library |
| `series` | List series in the library |
| `collections` | Manage ABS collections |

</details>

<details>
<summary><strong>🎧 Audible</strong></summary>

```bash
# Authenticate (encrypted by default)
python cli.py audible login

# Check status and encryption
python cli.py audible status

# Browse your library
python cli.py audible library --limit 20

# Search Audible catalog
python cli.py audible search "Brandon Sanderson"

# View listening stats
python cli.py audible stats

# Get recommendations
python cli.py audible recommendations
```

| Command | Description |
|---------|-------------|
| `login` | Login to Audible and save credentials |
| `encrypt` | Encrypt existing Audible credentials |
| `status` | Check connection and encryption status |
| `library` | List your Audible library |
| `item` | Show details for an audiobook by ASIN |
| `search` | Search the Audible catalog |
| `export` | Export full library to JSON |
| `wishlist` | Manage your Audible wishlist |
| `stats` | Show listening statistics |
| `recommendations` | Show personalized recommendations |

</details>

<details>
<summary><strong>💎 Quality Analysis</strong></summary>

```bash
# Scan library for quality metrics
python cli.py quality scan <library-id>

# Find low-quality items (below threshold)
python cli.py quality low <library-id> --threshold 128

# Analyze single item
python cli.py quality item <item-id>

# Find upgrade candidates with Audible pricing
python cli.py quality upgrades <library-id>
```

| Command | Description |
|---------|-------------|
| `scan` | Scan library for audio quality analysis |
| `low` | List low quality audiobooks below threshold |
| `item` | Analyze quality of a specific item |
| `upgrades` | Find upgrade candidates with Audible pricing |

</details>

<details>
<summary><strong>📖 Series Management</strong></summary>

```bash
# List all series
python cli.py series list <library-id>

# Analyze series completion
python cli.py series analyze <library-id>
```

</details>

## 💎 Quality Tiers

A2A uses an intelligent tier system to classify audio quality:

| Tier | Icon | Criteria | Description |
|------|------|----------|-------------|
| **Excellent** | 💎 | Dolby Atmos OR 256+ kbps | Premium quality, spatial audio |
| **Better** | ✨ | M4B @ 128-255 kbps | High quality AAC in container |
| **Good** | 👍 | M4B @ 110-127 kbps OR MP3 @ 128+ kbps | Acceptable quality |
| **Low** | 👎 | M4B @ 64-109 kbps OR MP3 @ 110-127 kbps | Below recommended |
| **Poor** | 💩 | < 64 kbps OR MP3 < 110 kbps | Needs replacement |

> **Format Priority**: M4B/M4A (AAC) > MP3 at equivalent bitrates due to codec efficiency.

## 🏗️ Architecture

```
src/
├── abs/          # Audiobookshelf API client (sync + async)
├── audible/      # Audible API client with encryption
├── cache/        # SQLite caching layer (TTL, namespaces)
├── cli/          # Typer CLI command modules
├── quality/      # Audio quality analysis engine
├── series/       # Series matching and tracking
├── output/       # Report formatters (JSON, table, etc.)
└── utils/        # UI helpers, sample data generation
```

### Key Components

| Component | Description |
|-----------|-------------|
| `ABSClient` | Sync/async client for Audiobookshelf API with rate limiting |
| `AudibleClient` | Client for Audible API with encrypted credential storage |
| `QualityAnalyzer` | Audio quality tier calculation with configurable thresholds |
| `SeriesMatcher` | Fuzzy matching between ABS and Audible series |
| `SQLiteCache` | Unified caching with TTL, namespaces, and FTS support |

### Data Flow

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────────┐
│ ABS Library │────▶│ QualityAnalyzer │────▶│ AudioQuality     │
└─────────────┘     └─────────────────┘     └────────┬─────────┘
                                                     │
┌─────────────┐     ┌─────────────────┐              ▼
│   Audible   │────▶│ EnrichmentSvc   │────▶┌──────────────────┐
│   Catalog   │     └─────────────────┘     │ Upgrade Report   │
└─────────────┘                             └──────────────────┘
```

## 🔒 Security

<table>
<tr>
<td width="50%">

### ✅ Credential Protection
- **Encrypted storage**: AES-CBC encryption for Audible credentials
- **Secure permissions**: Auth files set to `600` (owner-only)
- **Password protection**: Via environment variable or prompt

</td>
<td width="50%">

### ✅ Network Security
- **HTTPS by default**: Auto-upgrades connections
- **Localhost exception**: HTTP allowed for local development
- **Custom CA support**: For self-signed certificates

</td>
</tr>
</table>

```bash
# Encrypt existing credentials
python cli.py audible encrypt

# Check encryption status
python cli.py audible status
```

> ⚠️ **Never commit** `config.yaml`, `data/audible_auth.json`, or `.env` files. Use the provided `.example` files as templates.

<details>
<summary><strong>🔐 Security Configuration</strong></summary>

```yaml
# config.yaml
abs:
  host: https://abs.example.com
  api_key: "..."
  allow_insecure_http: false      # Only localhost over HTTP
  tls_ca_bundle: "/path/to/ca.pem"  # For self-signed certs

audible:
  auth_file: ./data/audible_auth.json
  auth_encryption: json           # Encrypted JSON format
```

```bash
# Environment variables
export AUDIBLE_AUTH_PASSWORD="your-secure-password"
export ABS_INSECURE_TLS=1  # DANGEROUS: disable SSL verification
```

</details>

## 🧪 Development

### Running Tests

```bash
make test              # Run all tests
make coverage          # With HTML coverage report
pytest -k "quality"    # Run specific tests
pytest -v --tb=short   # Verbose with short tracebacks
```

### Code Quality

```bash
make format            # Black + isort
make lint              # flake8 + mypy + bandit
make pre-commit        # Run all pre-commit hooks
```

### Pre-commit Hooks

```bash
make setup-hooks       # Install git hooks
make update-hooks      # Update to latest versions
```

### Developer Utilities

Located in `tools/`:

| Script | Purpose |
|--------|---------|
| `dev.py` | Make-like task runner for systems without make |
| `dev_series_explore.py` | Series matching exploration/testing |

```bash
python tools/dev.py help
python tools/dev_series_explore.py --library-id <id>
```

## 📁 Project Structure

```
a2a/
├── .github/              # GitHub Actions, templates, Dependabot
│   ├── workflows/        # CI, release, pre-commit autoupdate
│   └── ISSUE_TEMPLATE/   # Bug report, feature request forms
├── src/                  # Source code modules
├── tests/                # Pytest test suite (577+ tests)
├── tools/                # Developer utilities
├── docs/                 # Design docs, audit reports
├── cli.py                # Main CLI entry point
├── config.yaml.example   # Configuration template
├── pyproject.toml        # Tool configuration (pytest, black, etc.)
└── Makefile              # Common development commands
```

## 🤝 Contributing

Contributions are welcome! Please read our guidelines:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Run** tests and linting (`make test && make lint`)
4. **Commit** with conventional commits (`feat:`, `fix:`, `docs:`)
5. **Push** and open a **Pull Request**

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards.

## 📜 License

This project is licensed under the **MIT License** - see [LICENSE](LICENSE) for details.

> ⚠️ **Note**: This project uses the [`audible`](https://github.com/mkb79/audible) library which is licensed under AGPL-3.0. For personal CLI use, this has minimal impact. Review the license if distributing.

## 🙏 Acknowledgments

<table>
<tr>
<td align="center" width="25%">
<a href="https://www.audiobookshelf.org/">
<img src="https://www.audiobookshelf.org/Logo.png" width="60" alt="Audiobookshelf"/><br/>
<sub><b>Audiobookshelf</b></sub>
</a>
</td>
<td align="center" width="25%">
<a href="https://github.com/mkb79/audible">
<img src="https://raw.githubusercontent.com/mkb79/audible/master/docs/source/_static/logo.png" width="60" alt="audible"/><br/>
<sub><b>audible</b></sub>
</a>
</td>
<td align="center" width="25%">
<a href="https://typer.tiangolo.com/">
<img src="https://typer.tiangolo.com/img/icon-white.svg" width="60" alt="Typer"/><br/>
<sub><b>Typer</b></sub>
</a>
</td>
<td align="center" width="25%">
<a href="https://rich.readthedocs.io/">
<img src="https://raw.githubusercontent.com/Textualize/rich/master/imgs/logo.svg" width="60" alt="Rich"/><br/>
<sub><b>Rich</b></sub>
</a>
</td>
</tr>
</table>

## 📞 Support

<p align="center">
<a href="https://github.com/H2OKing89/a2a/issues/new?template=bug_report.yml">🐛 Report Bug</a> •
<a href="https://github.com/H2OKing89/a2a/issues/new?template=feature_request.yml">💡 Request Feature</a> •
<a href="docs/">📖 Documentation</a>
</p>

---

<div align="center">

**Made with ❤️ for audiobook enthusiasts**

*Star ⭐ this repo if you find it useful!*

</div>
