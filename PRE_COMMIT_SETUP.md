# Pre-commit Setup and Usage

## Installation

1. **Install pre-commit package:**
   ```bash
   pip install pre-commit
   # or install all dev dependencies
   pip install -r requirements-dev.txt
   ```

2. **Install git hooks:**
   ```bash
   pre-commit install
   ```

3. **Install commit-msg hook (optional):**
   ```bash
   pre-commit install --hook-type commit-msg
   ```

## Usage

### Automatic (Recommended)
Once installed, pre-commit hooks run automatically on `git commit`. If any hook fails, the commit is blocked and you'll need to fix the issues.

### Manual Execution

Run on all files:
```bash
pre-commit run --all-files
```

Run on staged files only:
```bash
pre-commit run
```

Run specific hook:
```bash
pre-commit run black --all-files
pre-commit run mypy --all-files
```

Update hooks to latest versions:
```bash
pre-commit autoupdate
```

### Skip Hooks (Not Recommended)

Skip all hooks for a commit:
```bash
git commit --no-verify -m "message"
```

Skip specific hooks via environment variable:
```bash
SKIP=black,flake8 git commit -m "message"
```

## Included Hooks

### File Cleanup
- **trailing-whitespace**: Remove trailing whitespace
- **end-of-file-fixer**: Ensure files end with newline
- **check-yaml**: Validate YAML syntax
- **check-json**: Validate JSON syntax
- **check-toml**: Validate TOML syntax
- **check-added-large-files**: Prevent large files (>1MB)
- **check-merge-conflict**: Detect merge conflict markers
- **detect-private-key**: Prevent committing private keys
- **mixed-line-ending**: Ensure consistent line endings (LF)

### Python Code Quality
- **black**: Code formatter (120 char line length)
- **isort**: Import sorting
- **pyupgrade**: Upgrade Python syntax to 3.13+
- **flake8**: Linting with plugins:
  - flake8-bugbear: Bug and design problems
  - flake8-comprehensions: List/dict comprehensions
  - flake8-simplify: Code simplification suggestions

### Security & Type Checking
- **bandit**: Security vulnerability scanner
- **mypy**: Static type checker
- **pydocstyle**: Docstring style checker (Google convention)

### Other
- **codespell**: Spell checker for code and docs
- **pretty-format-yaml**: YAML formatter
- **reorder-python-imports**: Requirements.txt sorting

## Configuration

All tool configurations are in `pyproject.toml`:

- **[tool.black]**: Line length, target version
- **[tool.isort]**: Import sorting style
- **[tool.mypy]**: Type checking rules
- **[tool.bandit]**: Security scan exclusions
- **[tool.pydocstyle]**: Docstring conventions

## Troubleshooting

### Hook fails with "file not found"
Reinstall hooks:
```bash
pre-commit uninstall
pre-commit install
```

### Hooks too slow
Skip slower hooks in local development:
```bash
SKIP=mypy,bandit git commit -m "message"
```

### Update hook versions
```bash
pre-commit autoupdate
git add .pre-commit-config.yaml
git commit -m "chore: update pre-commit hooks"
```

### Clean hook cache
```bash
pre-commit clean
pre-commit install --install-hooks
```

## CI Integration

The configuration includes `ci:` section for pre-commit.ci integration:
- Auto-fixes on PRs
- Weekly autoupdate
- Consistent with local checks

## Customization

### Enable pytest hook
Uncomment the pytest hook in `.pre-commit-config.yaml` to run tests on every commit:
```yaml
- repo: local
  hooks:
    - id: pytest-check
      name: pytest
      entry: pytest
      language: system
      pass_filenames: false
      always_run: true
      args: [tests/, -v, --tb=short]
```

### Adjust tool settings
Edit `pyproject.toml` to customize:
- Line length: `[tool.black]` and `[tool.isort]`
- Type checking strictness: `[tool.mypy]`
- Docstring requirements: `[tool.pydocstyle]`
- Security scan rules: `[tool.bandit]`
