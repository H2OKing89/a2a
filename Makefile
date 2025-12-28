.PHONY: help install install-dev test coverage lint format pre-commit clean version

# Default target
help:
	@echo "Available commands:"
	@echo "  make install       - Install production dependencies"
	@echo "  make install-dev   - Install development dependencies"
	@echo "  make test          - Run tests"
	@echo "  make coverage      - Run tests with coverage report"
	@echo "  make lint          - Run linters (flake8, mypy, bandit)"
	@echo "  make format        - Format code (black, isort)"
	@echo "  make pre-commit    - Run all pre-commit hooks"
	@echo "  make setup-hooks   - Setup pre-commit git hooks"
	@echo "  make clean         - Remove cache and build artifacts"
	@echo "  make version       - Show current version"
	@echo "  make bump-patch    - Bump patch version (0.1.0 -> 0.1.1)"
	@echo "  make bump-minor    - Bump minor version (0.1.0 -> 0.2.0)"
	@echo "  make bump-major    - Bump major version (0.1.0 -> 1.0.0)"

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

# Testing
test:
	pytest tests/ -v

coverage:
	pytest --cov=src --cov=cli --cov-report=html --cov-report=term-missing -v
	@echo "HTML coverage report: htmlcov/index.html"

# Code quality
lint:
	@echo "Running flake8..."
	flake8 src/ cli.py --max-line-length=120 --extend-ignore=E203,W503
	@echo "Running mypy..."
	mypy src/ --ignore-missing-imports
	@echo "Running bandit..."
	bandit -r src/ -c pyproject.toml

format:
	@echo "Running black..."
	black src/ cli.py tests/ --line-length=120
	@echo "Running isort..."
	isort src/ cli.py tests/ --profile=black --line-length=120

# Pre-commit
setup-hooks:
	pre-commit install
	@echo "Pre-commit hooks installed!"

pre-commit:
	pre-commit run --all-files

update-hooks:
	pre-commit autoupdate

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	rm -rf .pytest_cache/ .mypy_cache/ htmlcov/ .coverage
	@echo "Cleaned cache and build artifacts"

# Version management
version:
	@python tools/version.py

bump-patch:
	@python tools/version.py patch

bump-minor:
	@python tools/version.py minor

bump-major:
	@python tools/version.py major

release-patch: bump-patch
	@git add src/__init__.py
	@git commit -m "chore: bump version to $$(python tools/version.py | cut -d' ' -f3)"
	@git tag v$$(python tools/version.py | cut -d' ' -f3)
	@echo "✅ Version bumped and tagged. Run 'git push origin main --tags' to release."

# Quick commands
quick-test: format lint test
	@echo "Quick validation complete!"

ci: lint test
	@echo "CI checks complete!"
