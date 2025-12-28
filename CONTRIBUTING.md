# Contributing to A2A

Thank you for your interest in contributing to A2A! This document provides guidelines and information for contributors.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before contributing.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:

   ```bash
   git clone https://github.com/YOUR-USERNAME/a2a.git
   cd a2a
   ```

3. **Add the upstream remote**:

   ```bash
   git remote add upstream https://github.com/H2OKing89/a2a.git
   ```

## Development Setup

### Prerequisites

- Python 3.11 or higher
- `mediainfo` system package
- Git

### Environment Setup

1. **Create a virtual environment**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   ```

2. **Install dependencies**:

   ```bash
   make install-dev
   ```

3. **Install pre-commit hooks**:

   ```bash
   make setup-hooks
   ```

4. **Verify your setup**:

   ```bash
   make test
   ```

## Making Changes

### Branch Naming Convention

Use descriptive branch names:

- `feature/add-new-command` - New features
- `fix/resolve-cache-issue` - Bug fixes
- `docs/update-readme` - Documentation
- `refactor/simplify-client` - Code refactoring
- `test/add-quality-tests` - Test additions

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or modifying tests
- `chore`: Maintenance tasks

**Examples:**

```
feat(quality): add support for FLAC format analysis
fix(audible): handle rate limiting gracefully
docs(readme): add installation instructions for Windows
test(abs): add integration tests for library endpoints
```

## Code Style

### Python Style Guide

- **Line length**: 120 characters
- **Formatting**: [Black](https://black.readthedocs.io/)
- **Import sorting**: [isort](https://pycqa.github.io/isort/)
- **Docstrings**: [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)

### Running Formatters

```bash
# Format all code
make format

# Check formatting without changes
black --check src/ tests/ cli.py
isort --check-only src/ tests/ cli.py
```

### Linting

```bash
# Run all linters
make lint
```

This runs:

- `flake8` - Style guide enforcement
- `mypy` - Type checking
- `bandit` - Security analysis

### Pydantic Models

When creating Pydantic models for API responses:

```python
from pydantic import BaseModel, Field

class MyModel(BaseModel):
    """Model description."""

    my_field: str = Field(alias="myField")
    optional_field: str | None = None

    model_config = {"extra": "ignore"}
```

### Type Hints

Type hints are encouraged but not strictly required:

```python
def analyze_quality(items: list[LibraryItem]) -> QualityReport:
    """Analyze quality of library items."""
    ...
```

## Testing

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make coverage

# Run specific tests
pytest tests/test_quality_analyzer.py
pytest -k "test_cache"

# Run with verbose output
pytest -v
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use pytest fixtures from `conftest.py`

**Example test:**

```python
import pytest
from src.quality.analyzer import QualityAnalyzer

class TestQualityAnalyzer:
    """Tests for QualityAnalyzer."""

    def test_analyze_high_bitrate(self, mock_abs_client):
        """Test that high bitrate items are marked excellent."""
        analyzer = QualityAnalyzer(mock_abs_client)
        result = analyzer.analyze(item_with_high_bitrate)
        assert result.tier == "EXCELLENT"
```

### Test Coverage

Aim for meaningful test coverage:

- Cover happy paths and error cases
- Test edge cases
- Mock external dependencies (APIs, file system)

## Pull Request Process

### Before Submitting

1. **Update your branch**:

   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all checks**:

   ```bash
   make pre-commit
   make test
   ```

3. **Update documentation** if needed

### Submitting a PR

1. Push your changes to your fork
2. Open a Pull Request against `main`
3. Fill out the PR template completely
4. Link any related issues

### PR Requirements

- [ ] All CI checks pass
- [ ] Tests added for new functionality
- [ ] Documentation updated if needed
- [ ] Code follows project style guide
- [ ] Commits follow conventional commits format

### Review Process

1. A maintainer will review your PR
2. Address any requested changes
3. Once approved, the PR will be merged

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

- **Environment**: OS, Python version
- **Steps to reproduce**
- **Expected behavior**
- **Actual behavior**
- **Error messages/logs**
- **Configuration** (sanitized)

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md).

### Feature Requests

When requesting features, please include:

- **Use case**: Why do you need this?
- **Proposed solution**: How should it work?
- **Alternatives considered**: Other approaches you've thought of

Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md).

## Questions?

- Check the [documentation](docs/)
- Search [existing issues](https://github.com/H2OKing89/a2a/issues)
- Open a [discussion](https://github.com/H2OKing89/a2a/discussions)

---

Thank you for contributing! 🎧
