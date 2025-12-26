## Code Quality & Pre-commit Hooks

This project uses [pre-commit](https://pre-commit.com/) to ensure code quality and consistency.

### Quick Setup

```bash
# Activate virtual environment
source .venv/bin/activate

# Run automated setup script
./setup-precommit.sh
```

### Manual Setup

```bash
# Install pre-commit
pip install pre-commit

# Or install all dev dependencies
pip install -r requirements-dev.txt

# Install git hooks
pre-commit install

# Run on all files (first run will download hook environments)
pre-commit run --all-files
```

### What Gets Checked

**File Cleanup:**
- Remove trailing whitespace
- Fix end of file
- Check YAML/JSON/TOML syntax
- Prevent large files (>1MB)
- Detect merge conflicts and private keys

**Python Code:**
- **black**: Auto-format code (120 char lines)
- **isort**: Sort and organize imports
- **flake8**: Linting with bugbear, comprehensions, simplify plugins
- **pyupgrade**: Upgrade to Python 3.13+ syntax

**Security & Quality:**
- **bandit**: Security vulnerability scanner
- **mypy**: Static type checking
- **pydocstyle**: Docstring style (Google convention)
- **codespell**: Spell checker

### Usage

Hooks run automatically on commit:
```bash
git add .
git commit -m "your message"
# Hooks run automatically, may auto-fix issues
```

Run manually on all files:
```bash
pre-commit run --all-files
```

Run specific hook:
```bash
pre-commit run black --all-files
pre-commit run mypy --all-files
```

Update to latest hook versions:
```bash
pre-commit autoupdate
```

### Skipping Hooks (Emergency Only)

Skip all hooks:
```bash
git commit --no-verify -m "emergency fix"
```

Skip specific hooks:
```bash
SKIP=black,flake8 git commit -m "message"
```

### Configuration

All tools are configured in `pyproject.toml`:
- Line length: 120 characters
- Python version: 3.13+
- Import style: black-compatible
- Type checking: lenient (warnings only)

See [PRE_COMMIT_SETUP.md](PRE_COMMIT_SETUP.md) for detailed documentation.

### CI Integration

The pre-commit configuration includes CI settings for automated PR checks and weekly hook updates.

### Development Workflow

1. Make code changes
2. Run tests: `pytest tests/ -v`
3. Commit changes: `git commit` (hooks run automatically)
4. Fix any issues flagged by hooks
5. Push: `git push`

### Common Issues

**Hooks too slow?**
```bash
# Skip slow hooks during development
SKIP=mypy,bandit git commit -m "WIP"
```

**Hook cache issues?**
```bash
pre-commit clean
pre-commit install --install-hooks
```

**Auto-fixes break code?**
Review changes before committing:
```bash
git diff  # See what hooks changed
git add -p  # Stage changes selectively
```
