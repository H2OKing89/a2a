#!/usr/bin/env python3
"""
Development task runner - alternative to make for systems without make installed.

Usage:
    python dev.py <command>

Commands:
    help          - Show this help message
    install       - Install production dependencies
    install-dev   - Install development dependencies
    test          - Run tests
    coverage      - Run tests with coverage
    lint          - Run all linters
    format        - Format code with black and isort
    pre-commit    - Run all pre-commit hooks
    setup-hooks   - Install pre-commit git hooks
    clean         - Remove cache and build artifacts
"""

import subprocess
import sys
from pathlib import Path


def run(cmd: str, check: bool = True) -> int:
    """Run shell command and return exit code."""
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        print(f"❌ Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    return result.returncode


def install():
    """Install production dependencies."""
    return run("pip install -r requirements.txt")


def install_dev():
    """Install development dependencies."""
    run("pip install -r requirements.txt")
    return run("pip install -r requirements-dev.txt")


def test():
    """Run tests."""
    return run("pytest tests/ -v")


def coverage():
    """Run tests with coverage."""
    run("pytest --cov=src --cov=cli --cov-report=html --cov-report=term-missing -v")
    print("\n📊 HTML coverage report: htmlcov/index.html")
    return 0


def lint():
    """Run all linters."""
    print("🔍 Running linters...\n")

    print("Running flake8...")
    run("flake8 src/ cli.py --max-line-length=120 --extend-ignore=E203,W503", check=False)

    print("\nRunning mypy...")
    run("mypy src/ --ignore-missing-imports", check=False)

    print("\nRunning bandit...")
    run("bandit -r src/ -c pyproject.toml", check=False)

    return 0


def format_code():
    """Format code with black and isort."""
    print("🎨 Formatting code...\n")

    print("Running black...")
    run("black src/ cli.py tests/ --line-length=120")

    print("\nRunning isort...")
    run("isort src/ cli.py tests/ --profile=black --line-length=120")

    return 0


def pre_commit():
    """Run all pre-commit hooks."""
    return run("pre-commit run --all-files", check=False)


def setup_hooks():
    """Install pre-commit git hooks."""
    run("pre-commit install")
    print("✅ Pre-commit hooks installed!")
    return 0


def update_hooks():
    """Update pre-commit hooks to latest versions."""
    return run("pre-commit autoupdate")


def clean():
    """Remove cache and build artifacts."""
    import shutil

    print("🧹 Cleaning cache and build artifacts...")

    patterns = [
        "**/__pycache__",
        "**/*.pyc",
        "**/*.pyo",
        ".pytest_cache",
        ".mypy_cache",
        "htmlcov",
        ".coverage",
    ]

    for pattern in patterns:
        for path in Path(".").rglob(pattern.replace("**/", "")):
            if path.is_file():
                path.unlink()
                print(f"  Removed {path}")
            elif path.is_dir():
                shutil.rmtree(path)
                print(f"  Removed {path}/")

    print("✨ Cleanup complete!")
    return 0


def quick_test():
    """Quick validation: format, lint, test."""
    format_code()
    lint()
    test()
    print("\n✅ Quick validation complete!")
    return 0


def ci():
    """CI checks: lint and test."""
    lint()
    test()
    print("\n✅ CI checks complete!")
    return 0


def show_help():
    """Show help message."""
    print(__doc__)
    return 0


COMMANDS = {
    "help": show_help,
    "install": install,
    "install-dev": install_dev,
    "test": test,
    "coverage": coverage,
    "lint": lint,
    "format": format_code,
    "pre-commit": pre_commit,
    "setup-hooks": setup_hooks,
    "update-hooks": update_hooks,
    "clean": clean,
    "quick-test": quick_test,
    "ci": ci,
}


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        show_help()
        return 1

    command = sys.argv[1]

    if command not in COMMANDS:
        print(f"❌ Unknown command: {command}\n")
        show_help()
        return 1

    return COMMANDS[command]()


if __name__ == "__main__":
    sys.exit(main())
