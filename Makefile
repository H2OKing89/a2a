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

release-patch:
	@echo "🔍 Checking release preconditions..."
	@# Check for uncommitted changes
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "❌ Error: Working tree is not clean. Commit or stash changes first."; \
		git status --short; \
		exit 1; \
	fi
	@# Check current branch (main or repo-polish for now)
	@CURRENT_BRANCH=$$(git branch --show-current); \
	if [ "$$CURRENT_BRANCH" != "main" ] && [ "$$CURRENT_BRANCH" != "repo-polish" ]; then \
		echo "❌ Error: Not on release branch (current: $$CURRENT_BRANCH)"; \
		echo "   Switch to 'main' before releasing: git checkout main"; \
		exit 1; \
	fi
	@echo "✅ Working tree clean, on branch $$(git branch --show-current)"
	@# Bump version and capture new version string
	@echo "📦 Bumping patch version..."
	@python tools/version.py patch > /dev/null
	@NEW_VERSION=$$(python tools/version.py | cut -d' ' -f3); \
	echo "   New version: $$NEW_VERSION"; \
	if [ -z "$$NEW_VERSION" ]; then \
		echo "❌ Error: Failed to determine new version"; \
		exit 1; \
	fi; \
	echo "💾 Committing version bump..."; \
	git add src/__init__.py || { echo "❌ Error: git add failed"; exit 1; }; \
	git commit -m "chore: bump version to $$NEW_VERSION" || { echo "❌ Error: git commit failed"; exit 1; }; \
	echo "🏷️  Creating tag v$$NEW_VERSION..."; \
	git tag "v$$NEW_VERSION" || { echo "❌ Error: git tag failed (does tag already exist?)"; exit 1; }; \
	echo ""; \
	echo "✅ Release v$$NEW_VERSION complete!"; \
	echo ""; \
	echo "📤 Next step: Push to remote with:"; \
	echo "   git push origin $$(git branch --show-current) --tags"

# Quick commands
quick-test: format lint test
	@echo "Quick validation complete!"

ci: lint test
	@echo "CI checks complete!"
