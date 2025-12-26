#!/bin/bash
# Pre-commit setup and verification script

set -e

echo "🔧 Setting up pre-commit hooks..."

# Check if we're in a git repository
if [ ! -d .git ]; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Virtual environment not activated. Activating..."
    if [ -f .venv/bin/activate ]; then
        source .venv/bin/activate
    else
        echo "❌ Error: Virtual environment not found at .venv/"
        exit 1
    fi
fi

# Install pre-commit if not already installed
if ! command -v pre-commit &> /dev/null; then
    echo "📦 Installing pre-commit..."
    pip install pre-commit
else
    echo "✓ pre-commit is already installed"
fi

# Install development dependencies
echo "📦 Installing development dependencies..."
pip install -r requirements-dev.txt -q

# Install git hooks
echo "🔗 Installing git hooks..."
pre-commit install

# Run autoupdate to get latest hook versions
echo "🔄 Updating hooks to latest versions..."
pre-commit autoupdate

# Run all hooks on all files as a test
echo ""
echo "🧪 Testing all hooks on existing files..."
echo "This may take a few minutes on first run..."
echo ""

if pre-commit run --all-files; then
    echo ""
    echo "✅ All pre-commit hooks passed!"
else
    echo ""
    echo "⚠️  Some hooks failed or modified files."
    echo "This is normal on first run - hooks auto-fix issues."
    echo ""
    echo "Run the following to see what changed:"
    echo "  git status"
    echo ""
    echo "Review changes and commit them:"
    echo "  git add -A"
    echo "  git commit -m 'style: apply pre-commit formatting'"
fi

echo ""
echo "✨ Pre-commit setup complete!"
echo ""
echo "Usage:"
echo "  • Hooks run automatically on 'git commit'"
echo "  • Run manually: pre-commit run --all-files"
echo "  • Update hooks: pre-commit autoupdate"
echo "  • Skip hooks: git commit --no-verify"
echo ""
echo "See PRE_COMMIT_SETUP.md for more information."
