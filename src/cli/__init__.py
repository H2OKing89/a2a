"""
CLI module for audiobook management tool.

This module contains subcommands organized by domain:
- abs: Audiobookshelf API commands
- audible: Audible API commands
- quality: Audio quality analysis commands
- series: Series tracking commands
"""

from src.cli.common import (
    console,
    get_abs_client,
    get_audible_client,
    get_cache,
    get_default_library_id,
    resolve_library_id,
    ui,
)

__all__ = [
    "console",
    "get_abs_client",
    "get_audible_client",
    "get_cache",
    "get_default_library_id",
    "resolve_library_id",
    "ui",
]
