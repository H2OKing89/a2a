#!/usr/bin/env python3
"""
CLI for audiobook management tool.

Features beautiful rich console output with spinners, progress bars,
styled tables, and visual feedback.

This is the main entry point that assembles all subcommands from
the src/cli/ modules.
"""

import logging
import sys
from pathlib import Path
from typing import Any

import typer
from rich.box import ROUNDED
from rich.padding import Padding
from rich.text import Text
from rich.traceback import install
from rich.tree import Tree

# Install Rich traceback handler for better error display
install(show_locals=False, width=120, word_wrap=True)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.abs import ABSAuthError, ABSConnectionError, ABSError
from src.audible import AudibleAuthError
from src.cli.abs import abs_app
from src.cli.audible import audible_app
from src.cli.common import Icons, console, get_abs_client, get_audible_client, get_cache, ui
from src.cli.quality import quality_app
from src.cli.series import series_app
from src.config import get_settings
from src.utils.ui import Panel

# Create main app
app = typer.Typer(
    name="audiobook-tool",
    help="🎧 Audiobook management tool using ABS and Audible APIs",
    rich_markup_mode="rich",
)

# Register sub-apps
app.add_typer(abs_app, name="abs")
app.add_typer(audible_app, name="audible")
app.add_typer(quality_app, name="quality")
app.add_typer(series_app, name="series")

logger = logging.getLogger(__name__)


@app.command()
def status():
    """Show global status for ABS, Audible, and cache."""
    settings = get_settings()
    has_errors = False

    # Header
    ui.header("Audiobook Manager", subtitle="System Status", icon=Icons.AUDIOBOOK)

    # ABS Status
    ui.section("Audiobookshelf", icon=Icons.SERVER)
    console.print(f"  {Icons.LINK} Server: [accent]{settings.abs.host}[/accent]")

    try:
        with ui.spinner("Connecting to ABS server..."), get_abs_client() as client:
            # Show resolved/normalized host if different from input
            if client.host != settings.abs.host:
                console.print(f"  {Icons.LINK} Resolved: [accent]{client.host}[/accent]")

            # Display security status from client (after normalization)
            if client._is_https:
                ui.success("HTTPS secured")
                if client._using_ca_bundle:
                    ui.success(f"Using CA bundle: {client._tls_ca_bundle_path}")
                elif not client._insecure_tls:
                    ui.success("SSL verification enabled")
            elif client._is_localhost:
                console.print(f"  {Icons.BULLET} HTTP (localhost)")
            else:
                ui.warning("Insecure HTTP to remote server", details="API key in cleartext!")
                console.print(f"    [dim]{Icons.BULLET} Fix: Enable HTTPS in ABS or use a reverse proxy[/dim]")

            if client._insecure_tls:
                ui.warning("SSL verification disabled", details="Use tls_ca_bundle instead")

            # HTTP/2 availability
            if client._http2_available:
                ui.success("HTTP/2 available")

            user = client.get_me()
            libraries = client.get_libraries()

            # Show actual negotiated protocol after requests
            if client._last_http_version:
                if client._last_http_version == "HTTP/2":
                    ui.success("Negotiated HTTP/2")
                else:
                    console.print(f"  {Icons.BULLET} Using {client._last_http_version}")

        ui.success(f"Authenticated as [bold]{user.username}[/bold]")
        ui.success(f"{len(libraries)} libraries available")
    except (ABSError, ABSConnectionError, ABSAuthError) as e:
        # Expected errors - show friendly message only, no traceback
        ui.error("Connection failed", details=str(e))
        logger.debug("ABS connection failed: %s", e)
        has_errors = True
    except Exception as e:
        # Unexpected errors - log full exception for debugging
        ui.error("Connection failed", details=str(e))
        logger.exception("Unexpected ABS error")
        has_errors = True

    # Audible Status
    ui.section("Audible", icon=Icons.AUDIOBOOK)
    console.print(f"  {Icons.FILE} Auth file: [accent]{settings.audible.auth_file}[/accent]")
    if not settings.audible.auth_file.exists():
        ui.warning("Not authenticated", details="Run 'audible login' to authenticate")
    else:
        try:
            with ui.spinner("Connecting to Audible..."), get_audible_client() as client:
                client.get_library(num_results=1, use_cache=True)
            ui.success(f"Connected to marketplace: [bold]{client.marketplace}[/bold]")
            ui.success("Library accessible")
        except AudibleAuthError as e:
            ui.error("Auth failed", details=str(e))
            has_errors = True
        except Exception as e:
            ui.error("Error", details=str(e))
            has_errors = True

    # Cache Status
    ui.section("Cache", icon=Icons.CACHE)
    if not settings.cache.enabled:
        ui.warning("Caching disabled")
    else:
        cache = get_cache()
        if cache:
            cache_stats: dict[str, Any] = cache.get_stats()
            ui.success(f"SQLite: [bold]{cache_stats.get('db_size_mb', 0):.1f} MB[/bold]")
            ui.success(f"{cache_stats.get('total_entries', 0)} entries cached")
        else:
            ui.warning("Not initialized")

    console.print()

    if has_errors:
        raise typer.Exit(1)


@app.command("cache")
def cache_command(
    stats: bool = typer.Option(True, "--stats/--no-stats", help="Show cache statistics"),
    clear: bool = typer.Option(False, "--clear", help="Clear all cached data"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Remove expired entries"),
    namespace: str | None = typer.Option(None, "--namespace", "-n", help="Specific namespace to clear"),
):
    """Manage unified SQLite cache."""
    settings = get_settings()

    if not settings.cache.enabled:
        ui.warning("Caching is disabled in settings")
        raise typer.Exit(1)

    cache = get_cache()
    if not cache:
        ui.warning("Cache not initialized")
        raise typer.Exit(1)

    try:
        if clear:
            with ui.spinner("Clearing cache..."):
                if namespace:
                    count = cache.clear_namespace(namespace)
                    ui.success(f"Cleared {count} items from '{namespace}'")
                else:
                    count = cache.clear_all()
                    ui.success(f"Cleared {count} total cached items")
        elif cleanup:
            with ui.spinner("Cleaning up expired entries..."):
                count = cache.cleanup_expired()
            ui.success(f"Removed {count} expired items")
        elif stats:
            cache_stats: dict[str, Any] = cache.get_stats()

            # Build namespace tree
            namespace_tree = Tree(f"[bold cyan]{Icons.FOLDER} Namespaces[/bold cyan]")
            for k, v in cache_stats.get("namespaces", {}).items():
                namespace_tree.add(f"[cyan]{k}[/cyan]: {v} entries")

            # Stats panel
            stats_content = Text()
            stats_content.append("📂 DB Path: ", style="bold")
            stats_content.append(f"{cache_stats.get('db_path', 'N/A')}\n\n")

            stats_content.append("💾 DB Size: ", style="bold")
            stats_content.append(f"{cache_stats.get('db_size_mb', 0):.2f} MB\n\n", style="size")

            stats_content.append("📊 Entries\n", style="bold")
            stats_content.append(f"   Total: {cache_stats.get('total_entries', 0)}\n")
            stats_content.append(f"   In Memory: {cache_stats.get('memory_entries', 0)}\n")
            stats_content.append("   Expired: ", style="")
            stats_content.append(f"{cache_stats.get('expired_entries', 0)}\n", style="warning")

            stats_content.append("\n🔗 ASIN Mappings\n", style="bold")
            stats_content.append(f"   Total: {cache_stats.get('asin_mappings', 0)}\n")
            stats_content.append(f"   With Audible Match: {cache_stats.get('matched_items', 0)}\n")

            console.print(
                Panel(
                    stats_content,
                    title=f"{Icons.CACHE} Cache Statistics",
                    border_style="cyan",
                    box=ROUNDED,
                )
            )
            console.print(Padding(namespace_tree, (1, 4)))

    except Exception as e:
        ui.error("Error", details=str(e))
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
