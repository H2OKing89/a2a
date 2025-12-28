"""
Output formatting plugin architecture.

This module provides a pluggable output formatting system for CLI commands.
Supports multiple output formats: table (rich), JSON, CSV.
"""

from .formatters import CSVFormatter, JSONFormatter, OutputFormat, OutputFormatter, TableFormatter, get_formatter

__all__ = [
    "CSVFormatter",
    "JSONFormatter",
    "OutputFormat",
    "OutputFormatter",
    "TableFormatter",
    "get_formatter",
]
