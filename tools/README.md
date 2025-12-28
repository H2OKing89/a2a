# Developer Utilities

This directory contains development and exploration scripts that are **not part of the library API**.

## Scripts


### `dev.py`
Development task runner (make-like helper for systems without GNU make).

```bash
python tools/dev.py help        # Show available commands
python tools/dev.py install-dev # Install dev dependencies
python tools/dev.py test        # Run tests
python tools/dev.py coverage    # Run tests with coverage
python tools/dev.py lint        # Run all linters
python tools/dev.py format      # Format code with black/isort
```


### `dev_series_explore.py`
Series matching exploration and testing script.

```bash
python tools/dev_series_explore.py --library-id <id> --max-series 5
python tools/dev_series_explore.py --list-series <library-id>
python tools/dev_series_explore.py --test-match "Harry Potter"
```

## Note

These are **scratch scripts / development harnesses** for contributors and maintainers. They're not installed with the package and may change without notice.
