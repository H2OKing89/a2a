#!/usr/bin/env python3
"""
CLI for audiobook management tool.
"""

import logging
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.abs import ABSClient
from src.audible import AudibleAuthError, AudibleBook, AudibleClient, AudibleEnrichmentService
from src.cache import SQLiteCache
from src.config import get_settings
from src.quality import QualityAnalyzer, QualityReport, QualityTier
from src.series import ABSSeriesInfo, MatchConfidence, SeriesAnalysisReport, SeriesComparisonResult, SeriesMatcher
from src.utils import save_golden_sample

app = typer.Typer(
    name="audiobook-tool",
    help="Audiobook management tool using ABS and Audible APIs",
)

# Sub-app for ABS commands
abs_app = typer.Typer(help="Audiobookshelf API commands")
app.add_typer(abs_app, name="abs")

# Sub-app for Audible commands
audible_app = typer.Typer(help="Audible API commands")
app.add_typer(audible_app, name="audible")

# Sub-app for Quality commands
quality_app = typer.Typer(help="Audio quality analysis commands")
app.add_typer(quality_app, name="quality")

# Sub-app for Series commands
series_app = typer.Typer(help="Series tracking and collection management")
app.add_typer(series_app, name="series")

console = Console()
logger = logging.getLogger(__name__)


# Global cache instance (lazy-loaded)
_cache: SQLiteCache | None = None


def get_default_library_id() -> str | None:
    """Get the default library ID from settings."""
    return get_settings().abs.library_id


def resolve_library_id(library_id: str | None) -> str:
    """Resolve library ID, using default if not provided."""
    if library_id:
        return library_id

    default_id = get_default_library_id()
    if default_id:
        return default_id

    console.print("[red]Error:[/red] No library ID provided and ABS_LIBRARY_ID not set in .env")
    console.print("[dim]Hint: Set ABS_LIBRARY_ID in .env or pass --library/-l option[/dim]")
    raise typer.Exit(1)


def get_cache() -> SQLiteCache | None:
    """Get shared SQLite cache instance."""
    global _cache
    settings = get_settings()

    if not settings.cache.enabled:
        return None

    if _cache is None:
        _cache = SQLiteCache(
            db_path=settings.cache.db_path,
            default_ttl_hours=settings.cache.default_ttl_hours,
            max_memory_entries=settings.cache.max_memory_entries,
        )

    return _cache


def get_abs_client() -> ABSClient:
    """Get configured ABS client."""
    settings = get_settings()

    cache = get_cache() if settings.abs.cache_enabled else None

    return ABSClient(
        host=settings.abs.host,
        api_key=settings.abs.api_key,
        rate_limit_delay=settings.rate_limit.base_delay,
        cache=cache,
        cache_ttl_hours=settings.cache.abs_ttl_hours if cache else settings.abs.cache_ttl_hours,
    )


def get_audible_client() -> AudibleClient:
    """Get configured Audible client."""
    settings = get_settings()

    cache = get_cache() if settings.audible.cache_enabled else None

    return AudibleClient.from_file(
        auth_file=settings.audible.auth_file,
        cache=cache,
        cache_ttl_hours=settings.cache.audible_ttl_hours if cache else settings.audible.cache_ttl_days * 24,
        rate_limit_delay=settings.audible.rate_limit_delay,
        requests_per_minute=settings.audible.requests_per_minute,
        burst_size=settings.audible.burst_size,
        backoff_multiplier=settings.audible.backoff_multiplier,
        max_backoff_seconds=settings.audible.max_backoff_seconds,
    )


@app.command()
def status():
    """Show global status for ABS, Audible, and cache."""
    settings = get_settings()
    has_errors = False

    console.print("\n[bold cyan]═══ System Status ═══[/bold cyan]\n")

    # ABS Status
    console.print("[bold]Audiobookshelf[/bold]")
    console.print(f"  Server: {settings.abs.host}")
    try:
        with get_abs_client() as client:
            user = client.get_me()
            libraries = client.get_libraries()
            console.print(f"  [green]✓[/green] Connected as [bold]{user.username}[/bold]")
            console.print(f"  [green]✓[/green] {len(libraries)} libraries available")
    except Exception as e:
        console.print(f"  [red]✗[/red] Connection failed: {e}")
        # Log full exception and stack trace for debugging while keeping concise CLI output
        logger.exception("ABS connection failed")
        has_errors = True

    console.print()

    # Audible Status
    console.print("[bold]Audible[/bold]")
    console.print(f"  Auth file: {settings.audible.auth_file}")
    if not settings.audible.auth_file.exists():
        console.print("  [yellow]⚠[/yellow] Not authenticated (run 'audible login')")
    else:
        try:
            with get_audible_client() as client:
                client.get_library(num_results=1, use_cache=True)  # Verify connectivity
                console.print(f"  [green]✓[/green] Connected to marketplace: [bold]{client.marketplace}[/bold]")
                console.print("  [green]✓[/green] Library accessible")
        except AudibleAuthError as e:
            console.print(f"  [red]✗[/red] Auth failed: {e}")
            has_errors = True
        except Exception as e:
            console.print(f"  [red]✗[/red] Error: {e}")
            has_errors = True

    console.print()

    # Cache Status
    console.print("[bold]Cache[/bold]")
    if not settings.cache.enabled:
        console.print("  [yellow]⚠[/yellow] Caching disabled")
    else:
        cache = get_cache()
        if cache:
            cache_stats: dict[str, Any] = cache.get_stats()
            console.print(f"  [green]✓[/green] SQLite: {cache_stats.get('db_size_mb', 0):.1f} MB")
            console.print(f"  [green]✓[/green] {cache_stats.get('total_entries', 0)} entries")
        else:
            console.print("  [yellow]⚠[/yellow] Not initialized")

    console.print()

    if has_errors:
        raise typer.Exit(1)


@abs_app.command("status")
def abs_status():
    """Check ABS connection status."""
    settings = get_settings()

    console.print(f"\n[bold]ABS Server:[/bold] {settings.abs.host}")

    try:
        with get_abs_client() as client:
            user = client.get_me()

            console.print(f"[green]✓[/green] Connected as: [bold]{user.username}[/bold] ({user.type})")
            console.print(f"  Active: {user.is_active}, Locked: {user.is_locked}")

            # Get libraries
            libraries = client.get_libraries()
            console.print(f"\n[bold]Libraries:[/bold] {len(libraries)}")

            for lib in libraries:
                icon = "📚" if lib.is_book_library else "🎙️"
                console.print(f"  {icon} {lib.name} ({lib.id}) - {lib.media_type}")

    except Exception as e:
        console.print(f"[red]✗[/red] Connection failed: {e}")
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
        console.print("[yellow]Caching is disabled in settings[/yellow]")
        raise typer.Exit(1)

    cache = get_cache()
    if not cache:
        console.print("[yellow]Cache not initialized[/yellow]")
        raise typer.Exit(1)

    try:
        if clear:
            if namespace:
                count = cache.clear_namespace(namespace)
                console.print(f"[green]✓[/green] Cleared {count} items from '{namespace}'")
            else:
                count = cache.clear_all()
                console.print(f"[green]✓[/green] Cleared {count} total cached items")
        elif cleanup:
            count = cache.cleanup_expired()
            console.print(f"[green]✓[/green] Removed {count} expired items")
        elif stats:
            cache_stats: dict[str, Any] = cache.get_stats()

            # Format namespaces display
            namespaces_display = (
                "\n".join(f"  {k}: {v}" for k, v in cache_stats.get("namespaces", {}).items()) or "  (none)"
            )

            console.print(
                Panel(
                    f"[bold cyan]SQLite Cache[/bold cyan]\n\n"
                    f"DB Path: {cache_stats.get('db_path', 'N/A')}\n"
                    f"DB Size: {cache_stats.get('db_size_mb', 0):.2f} MB\n\n"
                    f"[bold]Entries:[/bold]\n"
                    f"  Total: {cache_stats.get('total_entries', 0)}\n"
                    f"  In Memory: {cache_stats.get('memory_entries', 0)}\n"
                    f"  Expired: {cache_stats.get('expired_entries', 0)}\n\n"
                    f"[bold]ASIN Mappings:[/bold]\n"
                    f"  Total: {cache_stats.get('asin_mappings', 0)}\n"
                    f"  With Audible Match: {cache_stats.get('matched_items', 0)}\n\n"
                    f"[bold]Namespaces:[/bold]\n{namespaces_display}",
                    title="Cache Statistics",
                )
            )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@abs_app.command("libraries")
def abs_libraries():
    """List all libraries."""
    try:
        with get_abs_client() as client:
            libs = client.get_libraries()

            table = Table(title="Libraries")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="bold")
            table.add_column("Type")
            table.add_column("Provider")
            table.add_column("Folders")

            for lib in libs:
                folders = ", ".join(f.full_path for f in lib.folders)
                table.add_row(
                    lib.id,
                    lib.name,
                    lib.media_type,
                    lib.provider,
                    folders,
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@abs_app.command("stats")
def abs_stats(
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
):
    """Show library statistics."""
    library_id = resolve_library_id(library_id)
    try:
        with get_abs_client() as client:
            lib = client.get_library(library_id)
            stats = client.get_library_stats(library_id)

            console.print(
                Panel(
                    f"[bold]{lib.name}[/bold]\n\n"
                    f"Total Items: {stats.total_items}\n"
                    f"Total Authors: {stats.total_authors}\n"
                    f"Total Genres: {stats.total_genres}\n"
                    f"Total Duration: {stats.total_duration / 3600:.1f} hours\n"
                    f"Audio Tracks: {stats.num_audio_tracks}\n"
                    f"Total Size: {stats.total_size / (1024**3):.2f} GB",
                    title="Library Statistics",
                )
            )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@abs_app.command("items")
def abs_items(
    library_id: str | None = typer.Option(
        None, "--library", "-L", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of items to show"),
    sort: str | None = typer.Option(None, "--sort", "-s", help="Sort field"),
    desc: bool = typer.Option(False, "--desc", "-d", help="Sort descending"),
):
    """List library items."""
    library_id = resolve_library_id(library_id)
    try:
        with get_abs_client() as client:
            response = client.get_library_items(
                library_id=library_id,
                limit=limit,
                sort=sort,
                desc=desc,
            )

            table = Table(title=f"Library Items ({response.total} total)")
            table.add_column("ID", style="cyan", max_width=25)
            table.add_column("Title", style="bold", max_width=40)
            table.add_column("Author", max_width=25)
            table.add_column("Duration", justify="right")
            table.add_column("Size", justify="right")

            for item in response.results:
                meta = item.media.metadata
                duration_hrs = item.media.duration / 3600 if item.media.duration else 0
                size_mb = (item.size or 0) / (1024**2)

                table.add_row(
                    item.id,
                    meta.title[:40],
                    (meta.author_name or "")[:25],
                    f"{duration_hrs:.1f}h",
                    f"{size_mb:.0f} MB",
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@abs_app.command("item")
def abs_item(
    item_id: str = typer.Argument(..., help="Item ID"),
):
    """Show details for a specific item."""
    try:
        with get_abs_client() as client:
            item = client.get_item(item_id, expanded=True)
            meta = item.media.metadata

            # Basic info
            console.print(
                Panel(
                    f"[bold]{meta.title}[/bold]\n"
                    f"Subtitle: {meta.subtitle or 'N/A'}\n\n"
                    f"Author: {meta.author_name or 'Unknown'}\n"
                    f"Narrator: {meta.narrator_name or 'Unknown'}\n"
                    f"Series: {meta.series_name or 'N/A'}\n\n"
                    f"Publisher: {meta.publisher or 'N/A'}\n"
                    f"Published: {meta.published_year or 'N/A'}\n\n"
                    f"ASIN: {meta.asin or 'N/A'}\n"
                    f"ISBN: {meta.isbn or 'N/A'}\n\n"
                    f"Duration: {item.media.duration / 3600:.1f} hours\n"
                    f"Size: {item.size / (1024**3):.2f} GB\n"
                    f"Audio Files: {len(item.media.audio_files)}\n"
                    f"Chapters: {len(item.media.chapters)}",
                    title="Library Item",
                )
            )

            # Audio files info
            if item.media.audio_files:
                table = Table(title="Audio Files")
                table.add_column("#", justify="right")
                table.add_column("Filename", max_width=50)
                table.add_column("Codec")
                table.add_column("Bitrate", justify="right")
                table.add_column("Duration", justify="right")

                for af in item.media.audio_files:
                    table.add_row(
                        str(af.index),
                        af.metadata.filename[:50],
                        af.codec or "?",
                        f"{af.bit_rate // 1000}k" if af.bit_rate else "?",
                        f"{af.duration / 60:.1f}m",
                    )

                console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@abs_app.command("search")
def abs_search(
    query: str = typer.Argument(..., help="Search query"),
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
):
    """Search a library."""
    library_id = resolve_library_id(library_id)
    try:
        with get_abs_client() as client:
            results: dict[str, Any] = client.search_library(library_id, query)

            books = results.get("book", [])
            authors = results.get("authors", [])
            series = results.get("series", [])

            if books:
                table = Table(title=f"Books ({len(books)})")
                table.add_column("Title", style="bold")
                table.add_column("Author")
                table.add_column("Match")

                for book in books:
                    item = book.get("libraryItem", {})
                    meta = item.get("media", {}).get("metadata", {})
                    table.add_row(
                        meta.get("title", "?"),
                        meta.get("authorName", "?"),
                        book.get("matchText", ""),
                    )

                console.print(table)

            if authors:
                console.print(f"\n[bold]Authors:[/bold] {', '.join(a.get('name', '?') for a in authors)}")

            if series:
                console.print(f"\n[bold]Series:[/bold] {', '.join(s.get('name', '?') for s in series)}")

            if not books and not authors and not series:
                console.print("[yellow]No results found[/yellow]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@abs_app.command("export")
def abs_export(
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
    output: Path = typer.Option(Path("library_export.json"), "--output", "-o", help="Output file"),
):
    """Export all library items to JSON."""
    import json

    library_id = resolve_library_id(library_id)
    try:
        with get_abs_client() as client:
            console.print(f"Fetching all items from library {library_id}...")

            items = client.get_all_library_items(library_id)

            console.print(f"Retrieved {len(items)} items")

            # Convert to dicts for JSON export
            export_data = {
                "library_id": library_id,
                "total_items": len(items),
                "items": [item.model_dump(by_alias=True) for item in items],
            }

            with open(output, "w") as f:
                json.dump(export_data, f, indent=2)

            console.print(f"[green]✓[/green] Exported to {output}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@abs_app.command("authors")
def abs_authors(
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
    limit: int = typer.Option(50, "--limit", "-n", help="Number of authors to show"),
    sort: str = typer.Option("numBooks", "--sort", "-s", help="Sort by: name, numBooks, addedAt"),
    reverse: bool = typer.Option(True, "--reverse/--no-reverse", help="Reverse sort order"),
):
    """List authors in the library."""
    library_id = resolve_library_id(library_id)
    try:
        with get_abs_client() as client:
            authors = client.get_library_authors(library_id)

            # Sort authors
            if sort == "name":
                authors.sort(key=lambda a: a.name.lower() if a.name else "", reverse=reverse)
            elif sort == "numBooks":
                authors.sort(key=lambda a: a.num_books or 0, reverse=reverse)
            elif sort == "addedAt":
                authors.sort(key=lambda a: a.added_at or 0, reverse=reverse)

            # Limit results
            authors = authors[:limit]

            table = Table(
                title=f"📚 Authors ({len(authors)} shown)",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("#", style="dim", width=4)
            table.add_column("Name", style="bold", max_width=35)
            table.add_column("Books", justify="right", style="green")
            table.add_column("ID", style="dim cyan", max_width=20)

            for i, author in enumerate(authors, 1):
                table.add_row(
                    str(i),
                    author.name or "Unknown",
                    str(author.num_books or 0),
                    author.id[:20] if author.id else "",
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@abs_app.command("series")
def abs_series(
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
    limit: int = typer.Option(50, "--limit", "-n", help="Number of series to show"),
    sort: str = typer.Option("numBooks", "--sort", "-s", help="Sort by: name, numBooks, addedAt"),
    reverse: bool = typer.Option(True, "--reverse/--no-reverse", help="Reverse sort order"),
):
    """List series in the library."""
    library_id = resolve_library_id(library_id)
    try:
        with get_abs_client() as client:
            series_list = client.get_library_series(library_id, limit=500)

            # Sort series
            if sort == "name":
                series_list.sort(key=lambda s: s.get("name", "").lower(), reverse=reverse)
            elif sort == "numBooks":
                series_list.sort(key=lambda s: s.get("numBooks", 0), reverse=reverse)
            elif sort == "addedAt":
                series_list.sort(key=lambda s: s.get("addedAt", 0), reverse=reverse)

            # Limit results
            series_list = series_list[:limit]

            table = Table(
                title=f"📖 Series ({len(series_list)} shown)",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("#", style="dim", width=4)
            table.add_column("Series Name", style="bold", max_width=40)
            table.add_column("Books", justify="right", style="green")
            table.add_column("ID", style="dim cyan", max_width=20)

            for i, series in enumerate(series_list, 1):
                table.add_row(
                    str(i),
                    series.get("name", "Unknown"),
                    str(series.get("numBooks", 0)),
                    (series.get("id") or "")[:20],
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@abs_app.command("collections")
def abs_collections(
    action: str = typer.Argument("list", help="Action: list, show, create, add, remove"),
    collection_id: str | None = typer.Option(None, "--id", "-i", help="Collection ID (for show/add/remove)"),
    name: str | None = typer.Option(None, "--name", "-n", help="Collection name (for create)"),
    book_id: str | None = typer.Option(None, "--book", "-b", help="Book ID (for add/remove)"),
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (for create, default: ABS_LIBRARY_ID from .env)"
    ),
    description: str | None = typer.Option(None, "--desc", "-d", help="Description (for create)"),
):
    """Manage ABS collections.

    \b
    Actions:
      list   - List all collections
      show   - Show collection details (requires --id)
      create - Create new collection (requires --name, --library)
      add    - Add book to collection (requires --id, --book)
      remove - Remove book from collection (requires --id, --book)

    \b
    Examples:
      abs collections list
      abs collections show --id abc123
      abs collections create --name "Favorites" --library lib123
      abs collections add --id abc123 --book book456
    """
    try:
        with get_abs_client() as client:
            if action == "list":
                collections = client.get_collections()

                if not collections:
                    console.print("[yellow]No collections found[/yellow]")
                    return

                table = Table(
                    title="📁 Collections",
                    show_header=True,
                    header_style="bold cyan",
                )
                table.add_column("Name", style="bold", max_width=30)
                table.add_column("Books", justify="right", style="green")
                table.add_column("Library", max_width=20)
                table.add_column("ID", style="dim cyan", max_width=24)

                for coll in collections:
                    books = coll.get("books", [])
                    table.add_row(
                        coll.get("name", "?"),
                        str(len(books)),
                        (coll.get("libraryId") or "")[:20],
                        coll.get("id", ""),
                    )

                console.print(table)

            elif action == "show":
                if not collection_id:
                    console.print("[red]Error:[/red] --id required for 'show'")
                    raise typer.Exit(1)

                coll = client.get_collection(collection_id)
                books = coll.get("books", [])

                # Header panel
                console.print(
                    Panel(
                        f"[bold]{coll.get('name', 'Unknown')}[/bold]\n\n"
                        f"ID: [cyan]{coll.get('id')}[/cyan]\n"
                        f"Library: {coll.get('libraryId', 'N/A')}\n"
                        f"Description: {coll.get('description') or '(none)'}\n"
                        f"Books: [green]{len(books)}[/green]",
                        title="📁 Collection Details",
                    )
                )

                if books:
                    book_table = Table(show_header=True, header_style="bold")
                    book_table.add_column("#", style="dim", width=4)
                    book_table.add_column("Title", style="bold", max_width=50)
                    book_table.add_column("ID", style="dim cyan", max_width=24)

                    for i, book in enumerate(books, 1):
                        # Handle both expanded and non-expanded book data
                        title = book.get("title") or book.get("media", {}).get("metadata", {}).get("title", "?")
                        book_id_val = book.get("id", "")
                        book_table.add_row(str(i), title[:50], book_id_val)

                    console.print(book_table)

            elif action == "create":
                if not name:
                    console.print("[red]Error:[/red] --name required for 'create'")
                    raise typer.Exit(1)

                lib_id = library_id or resolve_library_id(None)
                result = client.create_collection(
                    library_id=lib_id,
                    name=name,
                    description=description,
                )

                console.print(f"[green]✓[/green] Created collection '[bold]{name}[/bold]'")
                console.print(f"  ID: [cyan]{result.get('id')}[/cyan]")

            elif action == "add":
                if not collection_id or not book_id:
                    console.print("[red]Error:[/red] --id and --book required for 'add'")
                    raise typer.Exit(1)

                client.add_book_to_collection(collection_id, book_id)
                console.print(f"[green]✓[/green] Added book [cyan]{book_id}[/cyan] to collection")

            elif action == "remove":
                if not collection_id or not book_id:
                    console.print("[red]Error:[/red] --id and --book required for 'remove'")
                    raise typer.Exit(1)

                client.remove_book_from_collection(collection_id, book_id)
                console.print(f"[green]✓[/green] Removed book [cyan]{book_id}[/cyan] from collection")

            else:
                console.print(f"[red]Error:[/red] Unknown action '{action}'")
                console.print("Valid actions: list, show, create, add, remove")
                raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# =============================================================================
# Audible Commands
# =============================================================================


@audible_app.command("login")
def audible_login(
    locale: str = typer.Option("us", "--locale", "-l", help="Marketplace locale (us, uk, de, etc.)"),
    external: bool = typer.Option(False, "--external", "-e", help="Use external browser for login"),
):
    """
    Login to Audible and save credentials.

    First-time setup - will prompt for email/password or open browser.
    """
    settings = get_settings()
    auth_file = settings.audible.auth_file

    console.print(f"\n[bold]Audible Login[/bold] (marketplace: {locale})")
    console.print(f"Credentials will be saved to: {auth_file}\n")

    try:
        if external:
            console.print("[yellow]Opening browser for login...[/yellow]")
            client = AudibleClient.from_login_external(
                locale=locale,
                auth_file=auth_file,
                cache_dir=settings.paths.cache_dir / "audible" if settings.audible.cache_enabled else None,
            )
        else:
            email = typer.prompt("Email")
            password = typer.prompt("Password", hide_input=True)

            def otp_callback() -> str:
                return str(typer.prompt("Enter OTP/2FA code"))

            def cvf_callback() -> str:
                return str(typer.prompt("Enter CVF verification code"))

            client = AudibleClient.from_login(
                email=email,
                password=password,
                locale=locale,
                auth_file=auth_file,
                cache_dir=settings.paths.cache_dir / "audible" if settings.audible.cache_enabled else None,
                otp_callback=otp_callback,
                cvf_callback=cvf_callback,
            )

        console.print("\n[green]✓[/green] Login successful!")
        console.print(f"  Marketplace: {client.marketplace}")
        console.print(f"  Credentials saved to: {auth_file}")

    except Exception as e:
        console.print(f"[red]✗[/red] Login failed: {e}")
        raise typer.Exit(1)


@audible_app.command("status")
def audible_status():
    """Check Audible connection status."""
    settings = get_settings()

    console.print("\n[bold]Audible Status[/bold]")
    console.print(f"Auth file: {settings.audible.auth_file}")
    console.print(f"Locale: {settings.audible.locale}")

    if not settings.audible.auth_file.exists():
        console.print("\n[yellow]⚠[/yellow] Auth file not found. Run 'audible login' first.")
        raise typer.Exit(1)

    try:
        with get_audible_client() as client:
            console.print(f"[green]✓[/green] Connected to marketplace: [bold]{client.marketplace}[/bold]")

            # Get library count
            items = client.get_library(num_results=1, use_cache=False)
            library_count = len(items)
            console.print("\n[bold]Account Status:[/bold]")
            console.print(f"  Library accessible: [green]Yes[/green] ({library_count}+ items)")

            # Cache stats
            cache_stats: dict[str, Any] = client.get_cache_stats()
            if cache_stats.get("enabled"):
                console.print("\n[bold]Cache:[/bold] SQLite")
                console.print(f"  Total entries: {cache_stats.get('total_entries', 0)}")
                console.print(f"  Memory entries: {cache_stats.get('memory_entries', 0)}")
                console.print(f"  DB size: {cache_stats.get('db_size_mb', 0):.2f} MB")

    except AudibleAuthError as e:
        console.print(f"[red]✗[/red] Auth failed: {e}")
        console.print("Try running 'audible login' to refresh credentials.")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)


@audible_app.command("library")
def audible_library(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of items to show"),
    sort: str = typer.Option("-PurchaseDate", "--sort", "-s", help="Sort by field"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache"),
):
    """List your Audible library."""
    try:
        with get_audible_client() as client:
            items = client.get_library(
                num_results=limit,
                sort_by=sort,
                use_cache=not no_cache,
            )

            table = Table(title=f"Audible Library ({len(items)} items)")
            table.add_column("ASIN", style="cyan", max_width=12)
            table.add_column("Title", style="bold", max_width=40)
            table.add_column("Author", max_width=25)
            table.add_column("Duration", justify="right")
            table.add_column("Progress", justify="right")

            for item in items:
                duration = f"{item.runtime_hours:.1f}h" if item.runtime_hours else "?"
                progress = f"{item.percent_complete:.0f}%" if item.percent_complete else "-"

                table.add_row(
                    item.asin,
                    (item.title or "?")[:40],
                    (item.primary_author or "?")[:25],
                    duration,
                    progress,
                )

            console.print(table)

    except AudibleAuthError as e:
        console.print(f"[red]✗[/red] Auth failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@audible_app.command("item")
def audible_item(
    asin: str = typer.Argument(..., help="Audible ASIN"),
    catalog: bool = typer.Option(False, "--catalog", "-c", help="Look up in catalog (not just library)"),
):
    """Show details for an audiobook by ASIN."""
    try:
        with get_audible_client() as client:
            book: AudibleBook | None = None
            if catalog:
                book = client.get_catalog_product(asin)
            else:
                book = client.get_library_item(asin)
                if not book:
                    # Fall back to catalog
                    book = client.get_catalog_product(asin)

            if not book:
                console.print(f"[yellow]Not found:[/yellow] {asin}")
                raise typer.Exit(1)

            # Build series string
            series_str = "N/A"
            if book.series:
                s = book.series[0]
                series_str = f"{s.title}" + (f" #{s.sequence}" if s.sequence else "")

            # Build categories string
            categories: list[str] = []
            for ladder in book.category_ladders:
                if ladder.ladder:
                    cats = [c.name for c in ladder.ladder if c.name]
                    if cats:
                        categories.append(" > ".join(cats))

            console.print(
                Panel(
                    (
                        f"[bold]{book.title}[/bold]\n"
                        f"Subtitle: {book.subtitle or 'N/A'}\n\n"
                        f"Author: {book.primary_author or 'Unknown'}\n"
                        f"Narrator: {book.primary_narrator or 'Unknown'}\n"
                        f"Series: {series_str}\n\n"
                        f"Publisher: {book.publisher_name or 'N/A'}\n"
                        f"Release Date: {book.release_date or 'N/A'}\n"
                        f"Language: {book.language or 'N/A'}\n\n"
                        f"Duration: {book.runtime_hours or 0:.1f} hours\n"
                        f"Format: {book.format_type or 'N/A'}\n\n"
                        f"Categories:\n  " + "\n  ".join(categories[:3])
                        if categories
                        else "N/A"
                    ),
                    title=f"Audible Book: {asin}",
                )
            )

            # Description
            if book.publisher_summary:
                summary = book.publisher_summary[:500]
                if len(book.publisher_summary) > 500:
                    summary += "..."
                console.print(Panel(summary, title="Description"))

    except AudibleAuthError as e:
        console.print(f"[red]✗[/red] Auth failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@audible_app.command("search")
def audible_search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results"),
):
    """Search the Audible catalog."""
    try:
        with get_audible_client() as client:
            products = client.search_catalog(
                keywords=query,
                num_results=limit,
            )

            if not products:
                console.print("[yellow]No results found[/yellow]")
                raise typer.Exit(0)

            table = Table(title=f"Search Results: '{query}'")
            table.add_column("ASIN", style="cyan")
            table.add_column("Title", style="bold", max_width=40)
            table.add_column("Author", max_width=25)
            table.add_column("Duration", justify="right")

            for prod in products:
                duration = f"{prod.runtime_hours:.1f}h" if prod.runtime_hours else "?"

                table.add_row(
                    prod.asin,
                    (prod.title or "?")[:40],
                    (prod.primary_author or "?")[:25],
                    duration,
                )

            console.print(table)

    except AudibleAuthError as e:
        console.print(f"[red]✗[/red] Auth failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@audible_app.command("export")
def audible_export(
    output: Path = typer.Option(Path("audible_library.json"), "--output", "-o", help="Output file"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache"),
):
    """Export full Audible library to JSON."""
    import json

    try:
        with get_audible_client() as client:
            console.print("Fetching Audible library...")

            items = client.get_all_library_items(use_cache=not no_cache)

            console.print(f"Retrieved {len(items)} items")

            export_data = {
                "marketplace": client.marketplace,
                "total_items": len(items),
                "items": [item.model_dump() for item in items],
            }

            with open(output, "w") as f:
                json.dump(export_data, f, indent=2)

            console.print(f"[green]✓[/green] Exported to {output}")

    except AudibleAuthError as e:
        console.print(f"[red]✗[/red] Auth failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@audible_app.command("cache")
def audible_cache(
    clear: bool = typer.Option(False, "--clear", help="Clear all cached data"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Remove expired entries"),
):
    """Manage Audible API cache."""
    settings = get_settings()

    if not settings.cache.enabled:
        console.print("[yellow]Caching is disabled in settings[/yellow]")
        raise typer.Exit(1)

    cache = get_cache()
    if not cache:
        console.print("[yellow]Cache not initialized[/yellow]")
        raise typer.Exit(1)

    try:
        if clear:
            # Clear Audible namespaces
            count = 0
            for ns in ["library", "catalog", "search", "stats", "account"]:
                count += cache.clear_namespace(ns)
            console.print(f"[green]✓[/green] Cleared {count} cached Audible items")
        elif cleanup:
            count = cache.cleanup_expired()
            console.print(f"[green]✓[/green] Removed {count} expired items")
        else:
            stats: dict[str, Any] = cache.get_stats()

            # Format namespaces display
            namespaces_display = "\n".join(f"  {k}: {v}" for k, v in stats.get("namespaces", {}).items()) or "  (none)"

            console.print(
                Panel(
                    f"Backend: [bold]{stats.get('backend', 'sqlite')}[/bold]\n"
                    f"DB Path: {stats.get('db_path', 'N/A')}\n"
                    f"DB Size: {stats.get('db_size_mb', 0):.2f} MB\n\n"
                    f"Total Entries: {stats.get('total_entries', 0)}\n"
                    f"Memory Entries: {stats.get('memory_entries', 0)}\n"
                    f"Expired Entries: {stats.get('expired_entries', 0)}\n\n"
                    f"ASIN Mappings: {stats.get('asin_mappings', 0)}\n"
                    f"Matched Items: {stats.get('matched_items', 0)}\n\n"
                    f"[bold]Namespaces:[/bold]\n{namespaces_display}",
                    title="Cache Statistics",
                )
            )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@audible_app.command("wishlist")
def audible_wishlist(
    action: str = typer.Argument("list", help="Action: list, add, remove"),
    asin: str | None = typer.Option(None, "--asin", "-a", help="ASIN (for add/remove)"),
    limit: int = typer.Option(50, "--limit", "-l", help="Number of items to show"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache"),
):
    """Manage your Audible wishlist.

    \b
    Actions:
      list   - Show wishlist items (default)
      add    - Add book to wishlist (requires --asin)
      remove - Remove book from wishlist (requires --asin)

    \b
    Examples:
      audible wishlist
      audible wishlist add --asin B08G9PRS1K
      audible wishlist remove --asin B08G9PRS1K
    """
    try:
        with get_audible_client() as client:
            if action == "list":
                items = client.get_all_wishlist(use_cache=not no_cache)

                if not items:
                    console.print("[yellow]Your wishlist is empty[/yellow]")
                    console.print("[dim]Add books with: audible wishlist add --asin <ASIN>[/dim]")
                    return

                # Limit results
                display_items = items[:limit]

                table = Table(
                    title=f"💜 Wishlist ({len(items)} items)",
                    show_header=True,
                    header_style="bold magenta",
                )
                table.add_column("ASIN", style="cyan", width=12)
                table.add_column("Title", style="bold", max_width=40)
                table.add_column("Author", max_width=25)
                table.add_column("Duration", justify="right")
                table.add_column("Price", justify="right", style="green")
                table.add_column("Rating", justify="right")

                for item in display_items:
                    # Format duration
                    duration = f"{item.runtime_hours:.1f}h" if item.runtime_hours else "-"

                    # Format price
                    price = "-"
                    if item.list_price:
                        price = f"${item.list_price:.2f}"

                    # Format rating
                    rating = "-"
                    if item.rating:
                        stars = "★" * int(item.rating) + "☆" * (5 - int(item.rating))
                        rating = f"{stars[:5]} {item.rating:.1f}"

                    table.add_row(
                        item.asin,
                        (item.title or "?")[:40],
                        (item.primary_author or "?")[:25],
                        duration,
                        price,
                        rating,
                    )

                console.print(table)

                if len(items) > limit:
                    console.print(f"[dim]Showing {limit} of {len(items)} items. Use --limit to show more.[/dim]")

            elif action == "add":
                if not asin:
                    console.print("[red]Error:[/red] --asin required for 'add'")
                    raise typer.Exit(1)

                # First verify the book exists
                book = client.get_catalog_product(asin)
                if not book:
                    console.print(f"[red]Error:[/red] Book not found: {asin}")
                    raise typer.Exit(1)

                success = client.add_to_wishlist(asin)
                if success:
                    console.print(f"[green]✓[/green] Added to wishlist: [bold]{book.title}[/bold]")
                    console.print(f"  Author: {book.primary_author or 'Unknown'}")
                else:
                    console.print(f"[yellow]Could not add {asin} (may already be in wishlist)[/yellow]")

            elif action == "remove":
                if not asin:
                    console.print("[red]Error:[/red] --asin required for 'remove'")
                    raise typer.Exit(1)

                success = client.remove_from_wishlist(asin)
                if success:
                    console.print(f"[green]✓[/green] Removed [cyan]{asin}[/cyan] from wishlist")
                else:
                    console.print(f"[yellow]Could not remove {asin} (may not be in wishlist)[/yellow]")

            else:
                console.print(f"[red]Error:[/red] Unknown action '{action}'")
                console.print("Valid actions: list, add, remove")
                raise typer.Exit(1)

    except AudibleAuthError as e:
        console.print(f"[red]✗[/red] Auth failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@audible_app.command("stats")
def audible_stats():
    """Show your Audible listening statistics and account info."""
    try:
        with get_audible_client() as client:
            console.print("\n[bold cyan]═══ Audible Statistics ═══[/bold cyan]\n")

            # Get listening stats
            stats = client.get_listening_stats()
            if stats:
                listening_hours = (
                    stats.total_listening_time_ms / (1000 * 60 * 60) if stats.total_listening_time_ms else 0
                )

                console.print(
                    Panel(
                        f"[bold]📊 Listening Activity[/bold]\n\n"
                        f"Total Listening Time: [green]{listening_hours:.1f} hours[/green]\n"
                        f"Books Listened: [green]{stats.distinct_titles_listened or 0}[/green]\n"
                        f"Authors Explored: [green]{stats.distinct_authors_listened or 0}[/green]\n"
                        f"Listening Streak: [yellow]{stats.current_listening_streak or 0}[/yellow] days\n"
                        f"Longest Streak: [yellow]{stats.longest_listening_streak or 0}[/yellow] days",
                        title="📈 Listening Stats",
                        border_style="cyan",
                    )
                )
            else:
                console.print("[yellow]Listening stats not available[/yellow]")

            # Get account info
            account = client.get_account_info()
            if account:
                console.print()

                # Format subscription info
                sub_status = "[green]Active[/green]" if account.is_active_member else "[dim]Inactive[/dim]"

                benefits_list = []
                if account.benefits:
                    benefits_list = [b.benefit_id for b in account.benefits[:5]]
                benefits_str = ", ".join(benefits_list) if benefits_list else "(none)"

                console.print(
                    Panel(
                        f"[bold]👤 Account Details[/bold]\n\n"
                        f"Membership: {sub_status}\n"
                        f"Plan: [bold]{account.plan_name or 'N/A'}[/bold]\n"
                        f"Credits: [yellow]{account.credits_available or 0}[/yellow]\n"
                        f"Benefits: {benefits_str}",
                        title="💳 Account Info",
                        border_style="magenta",
                    )
                )
            else:
                console.print("[yellow]Account info not available[/yellow]")

    except AudibleAuthError as e:
        console.print(f"[red]✗[/red] Auth failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@audible_app.command("recommendations")
def audible_recommendations(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of recommendations to show"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache"),
):
    """Show personalized book recommendations."""
    try:
        with get_audible_client() as client:
            items = client.get_recommendations(num_results=min(limit, 50), use_cache=not no_cache)

            if not items:
                console.print("[yellow]No recommendations available[/yellow]")
                return

            table = Table(
                title=f"✨ Recommended For You ({len(items)} books)",
                show_header=True,
                header_style="bold yellow",
            )
            table.add_column("ASIN", style="cyan", width=12)
            table.add_column("Title", style="bold", max_width=35)
            table.add_column("Author", max_width=25)
            table.add_column("Duration", justify="right")
            table.add_column("Rating", justify="right")
            table.add_column("In Library", justify="center")

            for item in items:
                # Format duration
                duration = f"{item.runtime_hours:.1f}h" if item.runtime_hours else "-"

                # Format rating with stars
                rating = "-"
                if item.rating:
                    full_stars = int(item.rating)
                    rating = f"{'★' * full_stars}{'☆' * (5 - full_stars)} {item.rating:.1f}"

                # Check if in library (if we have that info)
                in_lib = "[green]✓[/green]" if getattr(item, "is_downloaded", False) else "[dim]-[/dim]"

                table.add_row(
                    item.asin,
                    (item.title or "?")[:35],
                    (item.primary_author or "?")[:25],
                    duration,
                    rating,
                    in_lib,
                )

            console.print(table)
            console.print("\n[dim]💡 Add to wishlist: audible wishlist add --asin <ASIN>[/dim]")

    except AudibleAuthError as e:
        console.print(f"[red]✗[/red] Auth failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# =============================================================================
# Golden Sample Commands
# =============================================================================


@abs_app.command("sample")
def abs_sample(
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
    item_id: str | None = typer.Option(None, "--item", "-i", help="Specific item ID"),
    output_dir: Path = typer.Option(Path("./data/samples"), "--output", "-o", help="Output directory"),
):
    """
    Collect golden samples from ABS API.

    Saves raw API responses for testing and documentation.
    """
    library_id = resolve_library_id(library_id)
    try:
        with get_abs_client() as client:
            console.print("\n[bold]Collecting ABS Golden Samples[/bold]\n")

            # Sample: Library list
            console.print("  Fetching libraries...")
            libraries = client.get_libraries()
            path = save_golden_sample(
                data=[lib.model_dump() for lib in libraries],
                name="libraries",
                source="abs",
                output_dir=output_dir,
            )
            console.print(f"    [green]✓[/green] {path.name}")

            # Sample: Library stats
            console.print("  Fetching library stats...")
            stats = client.get_library_stats(library_id)
            path = save_golden_sample(
                data=stats.model_dump(),
                name="library_stats",
                source="abs",
                output_dir=output_dir,
                metadata={"library_id": library_id},
            )
            console.print(f"    [green]✓[/green] {path.name}")

            # Sample: Library items (first page)
            console.print("  Fetching library items (first 10)...")
            items_response = client.get_library_items(library_id, limit=10)
            path = save_golden_sample(
                data={
                    "total": items_response.total,
                    "results": [item.model_dump() for item in items_response.results],
                },
                name="library_items",
                source="abs",
                output_dir=output_dir,
                metadata={"library_id": library_id},
            )
            console.print(f"    [green]✓[/green] {path.name}")

            # Sample: Specific item (expanded)
            if item_id:
                console.print(f"  Fetching item {item_id}...")
                item = client.get_item(item_id, expanded=True)
                path = save_golden_sample(
                    data=item.model_dump(),
                    name="library_item_expanded",
                    source="abs",
                    output_dir=output_dir,
                    metadata={"item_id": item_id},
                )
                console.print(f"    [green]✓[/green] {path.name}")
            elif items_response.results:
                # Use first item from list
                first_item_id = items_response.results[0].id
                console.print(f"  Fetching item {first_item_id}...")
                item = client.get_item(first_item_id, expanded=True)
                path = save_golden_sample(
                    data=item.model_dump(),
                    name="library_item_expanded",
                    source="abs",
                    output_dir=output_dir,
                    metadata={"item_id": first_item_id},
                )
                console.print(f"    [green]✓[/green] {path.name}")

            console.print(f"\n[green]✓[/green] Samples saved to {output_dir}/")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@audible_app.command("sample")
def audible_sample(
    asin: str | None = typer.Option(None, "--asin", "-a", help="Specific ASIN to sample"),
    output_dir: Path = typer.Option(Path("./data/samples"), "--output", "-o", help="Output directory"),
):
    """
    Collect golden samples from Audible API.

    Requires prior authentication via 'audible login'.
    """
    settings = get_settings()

    if not settings.audible.auth_file.exists():
        console.print("[yellow]⚠[/yellow] Audible not authenticated. Run 'audible login' first.")
        raise typer.Exit(1)

    try:
        with get_audible_client() as client:
            console.print("\n[bold]Collecting Audible Golden Samples[/bold]\n")
            console.print(f"  Marketplace: {client.marketplace}\n")

            # Sample: Library (first page)
            console.print("  Fetching library (first 10)...")
            library_items = client.get_library(num_results=10, use_cache=False)
            path = save_golden_sample(
                data=[item.model_dump() for item in library_items],
                name="library",
                source="audible",
                output_dir=output_dir,
                metadata={"marketplace": client.marketplace},
            )
            console.print(f"    [green]✓[/green] {path.name}")

            # Sample: Specific library item
            sample_asin = asin or (library_items[0].asin if library_items else None)
            if sample_asin:
                console.print(f"  Fetching library item {sample_asin}...")
                item = client.get_library_item(sample_asin, use_cache=False)
                if item:
                    path = save_golden_sample(
                        data=item.model_dump(),
                        name="library_item",
                        source="audible",
                        output_dir=output_dir,
                        metadata={"asin": sample_asin},
                    )
                    console.print(f"    [green]✓[/green] {path.name}")

                # Sample: Catalog product
                console.print(f"  Fetching catalog product {sample_asin}...")
                product = client.get_catalog_product(sample_asin, use_cache=False)
                if product:
                    path = save_golden_sample(
                        data=product.model_dump(),
                        name="catalog_product",
                        source="audible",
                        output_dir=output_dir,
                        metadata={"asin": sample_asin},
                    )
                    console.print(f"    [green]✓[/green] {path.name}")

            # Sample: Search results
            console.print("  Fetching search results (query: 'fantasy')...")
            search_results = client.search_catalog(keywords="fantasy", num_results=5, use_cache=False)
            path = save_golden_sample(
                data=[p.model_dump() for p in search_results],
                name="catalog_search",
                source="audible",
                output_dir=output_dir,
                metadata={"query": "fantasy"},
            )
            console.print(f"    [green]✓[/green] {path.name}")

            console.print(f"\n[green]✓[/green] Samples saved to {output_dir}/")

    except AudibleAuthError as e:
        console.print(f"[red]✗[/red] Auth failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# =============================================================================
# Quality Analysis Commands
# =============================================================================


@quality_app.command("scan")
def quality_scan(
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
    limit: int = typer.Option(0, "--limit", "-n", help="Limit number of items to scan (0 = all)"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Save report to JSON file"),
):
    """
    Scan library for audio quality analysis.

    Analyzes all audiobooks and generates a quality report showing
    items by tier (Excellent, Good, Acceptable, Low, Poor).
    """
    try:
        with get_abs_client() as client:
            # Get library ID from settings or pick first if not specified
            if not library_id:
                library_id = get_default_library_id()
            if not library_id:
                libraries = client.get_libraries()
                if not libraries:
                    console.print("[red]No libraries found[/red]")
                    raise typer.Exit(1)
                library_id = libraries[0].id

            # Get item count
            items_resp: dict[str, Any] = client._get(f"/libraries/{library_id}/items", params={"limit": 0})
            total_items = len(items_resp.get("results", []))

            if limit > 0:
                total_items = min(limit, total_items)

            console.print(f"\nScanning {total_items} items...\n")

            # Create analyzer and report
            analyzer = QualityAnalyzer()
            report = QualityReport()

            # Scan with progress bar
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Analyzing...", total=total_items)

                items = items_resp.get("results", [])[:total_items] if limit else items_resp.get("results", [])

                for item in items:
                    item_id = item.get("id")
                    try:
                        full_item: dict[str, Any] = client._get(f"/items/{item_id}", params={"expanded": 1})
                        quality = analyzer.analyze_item(full_item)
                        report.add_item(quality)
                    except Exception as e:
                        console.print(f"[yellow]Warning:[/yellow] Failed to analyze {item_id}: {e}")

                    progress.advance(task)

            report.finalize()

            # Display summary
            console.print(
                Panel(
                    f"[bold]Total Items:[/bold] {report.total_items}\n"
                    f"[bold]Total Size:[/bold] {report.total_size_gb:.2f} GB\n"
                    f"[bold]Total Duration:[/bold] {report.total_duration_hours:.1f} hours\n\n"
                    f"[bold]Bitrate Range:[/bold] {report.min_bitrate_kbps:.0f} - {report.max_bitrate_kbps:.0f} kbps\n"
                    f"[bold]Average Bitrate:[/bold] {report.avg_bitrate_kbps:.0f} kbps",
                    title="Quality Scan Complete",
                )
            )

            # Tier breakdown table
            tier_table = Table(title="Quality Tiers")
            tier_table.add_column("Tier", style="bold")
            tier_table.add_column("Count", justify="right")
            tier_table.add_column("Percentage", justify="right")

            tier_order = ["Excellent", "Good", "Acceptable", "Low", "Poor"]
            tier_colors = {"Excellent": "green", "Good": "blue", "Acceptable": "cyan", "Low": "yellow", "Poor": "red"}

            for tier_name in tier_order:
                count = report.tier_counts.get(tier_name, 0)
                pct = (count / report.total_items * 100) if report.total_items else 0
                color = tier_colors.get(tier_name, "white")
                tier_table.add_row(f"[{color}]{tier_name}[/{color}]", str(count), f"{pct:.1f}%")

            console.print(tier_table)

            # Format breakdown
            format_table = Table(title="Format Distribution")
            format_table.add_column("Format", style="bold")
            format_table.add_column("Count", justify="right")

            for fmt, count in sorted(report.format_counts.items(), key=lambda x: -x[1]):
                format_table.add_row(fmt, str(count))

            console.print(format_table)

            # Upgrade candidates summary
            if report.upgrade_candidates:
                console.print(f"\n[yellow]⚠ {len(report.upgrade_candidates)} items need upgrades[/yellow]")
                console.print("Run [bold]quality low[/bold] to see details.")

            # Save report if requested
            if output:
                import json

                output.parent.mkdir(parents=True, exist_ok=True)

                report_data = {
                    "summary": {
                        "total_items": report.total_items,
                        "total_size_gb": round(report.total_size_gb, 2),
                        "total_duration_hours": round(report.total_duration_hours, 1),
                        "min_bitrate_kbps": round(report.min_bitrate_kbps, 0),
                        "max_bitrate_kbps": round(report.max_bitrate_kbps, 0),
                        "avg_bitrate_kbps": round(report.avg_bitrate_kbps, 0),
                    },
                    "tier_counts": report.tier_counts,
                    "format_counts": report.format_counts,
                    "codec_counts": report.codec_counts,
                    "upgrade_candidates": [
                        {
                            "title": item.title,
                            "author": item.author,
                            "asin": item.asin,
                            "bitrate_kbps": round(item.bitrate_kbps, 0),
                            "format": item.format_label,
                            "size_mb": round(item.size_mb, 1),
                            "path": item.path,
                            "tier": item.tier_label,
                            "upgrade_priority": item.upgrade_priority,
                            "upgrade_reason": item.upgrade_reason,
                        }
                        for item in report.upgrade_candidates
                    ],
                }

                with open(output, "w") as f:
                    json.dump(report_data, f, indent=2)

                console.print(f"\n[green]✓[/green] Report saved to {output}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@quality_app.command("low")
def quality_low(
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
    threshold: int = typer.Option(110, "--threshold", "-t", help="Bitrate threshold in kbps"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max items to show"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Export to JSON file"),
):
    """
    List low quality audiobooks below bitrate threshold.

    Default threshold is 110 kbps (Acceptable minimum).
    """
    try:
        with get_abs_client() as client:
            # Get library ID from settings or pick first if not specified
            if not library_id:
                library_id = get_default_library_id()
            if not library_id:
                libraries = client.get_libraries()
                if not libraries:
                    console.print("[red]No libraries found[/red]")
                    raise typer.Exit(1)
                library_id = libraries[0].id

            # Get all items
            items_resp: dict[str, Any] = client._get(f"/libraries/{library_id}/items", params={"limit": 0})
            all_items = items_resp.get("results", [])

            console.print(f"Scanning {len(all_items)} items for quality < {threshold} kbps...\n")

            analyzer = QualityAnalyzer()
            low_quality_items = []

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Scanning...", total=len(all_items))

                for item in all_items:
                    item_id = item.get("id")
                    try:
                        full_item: dict[str, Any] = client._get(f"/items/{item_id}", params={"expanded": 1})
                        quality = analyzer.analyze_item(full_item)

                        if quality.bitrate_kbps < threshold:
                            low_quality_items.append(quality)
                    except Exception as e:
                        logger.error(
                            f"Failed to analyze item {item_id}: {e}",
                            exc_info=True,
                            extra={
                                "item_id": item_id,
                                "item_title": item.get("media", {}).get("metadata", {}).get("title"),
                            },
                        )

                    progress.advance(task)

            # Sort by bitrate (lowest first)
            low_quality_items.sort(key=lambda x: x.bitrate_kbps)

            if not low_quality_items:
                console.print(f"[green]✓[/green] No items below {threshold} kbps threshold!")
                return

            console.print(f"\n[yellow]Found {len(low_quality_items)} items below {threshold} kbps[/yellow]\n")

            # Display table
            table = Table(title=f"Low Quality Items (< {threshold} kbps)")
            table.add_column("Bitrate", justify="right", style="red")
            table.add_column("Format", style="cyan")
            table.add_column("Title", max_width=40)
            table.add_column("Author", max_width=20)
            table.add_column("ASIN", style="dim")
            table.add_column("Size", justify="right")

            for item in low_quality_items[:limit]:
                asin_display = item.asin or "-"
                size_display = f"{item.size_mb:.0f} MB" if item.size_mb < 1000 else f"{item.size_gb:.1f} GB"

                table.add_row(
                    f"{item.bitrate_kbps:.0f}",
                    item.format_label,
                    item.title[:40],
                    (item.author or "Unknown")[:20],
                    asin_display,
                    size_display,
                )

            console.print(table)

            if len(low_quality_items) > limit:
                console.print(
                    f"\n[dim]Showing {limit} of {len(low_quality_items)} items. Use --limit to show more.[/dim]"
                )

            # Export if requested
            if output:
                import json

                output.parent.mkdir(parents=True, exist_ok=True)

                export_data = [
                    {
                        "title": item.title,
                        "author": item.author,
                        "asin": item.asin,
                        "bitrate_kbps": round(item.bitrate_kbps, 0),
                        "format": item.format_label,
                        "codec": item.codec,
                        "size_mb": round(item.size_mb, 1),
                        "path": item.path,
                        "tier": item.tier_label,
                        "upgrade_priority": item.upgrade_priority,
                        "upgrade_reason": item.upgrade_reason,
                    }
                    for item in low_quality_items
                ]

                with open(output, "w") as f:
                    json.dump(export_data, f, indent=2)

                console.print(f"\n[green]✓[/green] Exported {len(low_quality_items)} items to {output}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@quality_app.command("item")
def quality_item(
    item_id: str = typer.Argument(..., help="Item ID or ASIN"),
):
    """
    Analyze quality of a specific item.
    """
    try:
        with get_abs_client() as client:
            # Try to get item directly, or search by ASIN
            try:
                full_item: dict[str, Any] = client._get(f"/items/{item_id}", params={"expanded": 1})
            except Exception:
                # Try searching by ASIN
                libraries = client.get_libraries()
                if not libraries:
                    console.print("[red]Item not found[/red]")
                    raise typer.Exit(1)

                # Search in first library
                results: dict[str, Any] = client._get(
                    f"/libraries/{libraries[0].id}/search", params={"q": item_id, "limit": 1}
                )
                books = results.get("book", [])
                if not books:
                    console.print("[red]Item not found[/red]")
                    raise typer.Exit(1)

                item_id = books[0].get("libraryItem", {}).get("id")
                full_item = client._get(f"/items/{item_id}", params={"expanded": 1})

            # Analyze
            analyzer = QualityAnalyzer()
            quality = analyzer.analyze_item(full_item)

            # Display results
            tier_color = {
                QualityTier.EXCELLENT: "green",
                QualityTier.GOOD: "blue",
                QualityTier.ACCEPTABLE: "cyan",
                QualityTier.LOW: "yellow",
                QualityTier.POOR: "red",
            }.get(quality.tier, "white")

            atmos_badge = " [magenta]🎧 DOLBY ATMOS[/magenta]" if quality.is_atmos else ""

            console.print(
                Panel(
                    f"[bold]{quality.title}[/bold]{atmos_badge}\n"
                    f"Author: {quality.author or 'Unknown'}\n"
                    f"ASIN: {quality.asin or 'N/A'}\n\n"
                    f"[bold]Quality Tier:[/bold] [{tier_color}]{quality.tier_label}[/{tier_color}] ({quality.tier.emoji})\n"
                    f"[bold]Quality Score:[/bold] {quality.quality_score:.0f}/100\n\n"
                    f"[bold]Audio Details:[/bold]\n"
                    f"  Codec: {quality.codec}\n"
                    f"  Bitrate: {quality.bitrate_kbps:.0f} kbps\n"
                    f"  Format: {quality.format_label}\n"
                    f"  Channels: {quality.channels} ({quality.channel_layout or 'stereo'})\n"
                    f"  Duration: {quality.duration_hours:.1f} hours\n\n"
                    f"[bold]File Info:[/bold]\n"
                    f"  Size: {quality.size_mb:.0f} MB ({quality.size_gb:.2f} GB)\n"
                    f"  Files: {quality.file_count}\n"
                    f"  Path: {quality.path}",
                    title="Quality Analysis",
                )
            )

            if quality.upgrade_reason:
                console.print(f"\n[yellow]⚠ Upgrade Recommended:[/yellow] {quality.upgrade_reason}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@quality_app.command("upgrades")
def quality_upgrades(
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
    threshold: int = typer.Option(110, "--threshold", "-t", help="Bitrate threshold in kbps"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max items to show"),
    plus_only: bool = typer.Option(False, "--plus-only", "-p", help="Show only Plus Catalog items (FREE)"),
    deals_only: bool = typer.Option(False, "--deals", "-d", help="Show only items under $9.00"),
    monthly_deals: bool = typer.Option(False, "--monthly-deals", "-m", help="Show only monthly deal items"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Export to JSON file"),
):
    """
    Find upgrade candidates enriched with Audible pricing data.

    Shows low quality items along with:
    - Whether you own it on Audible
    - Plus Catalog availability (FREE!)
    - Monthly deals (up to 80% off!)
    - Current pricing and discounts
    - Buy recommendation (FREE, MONTHLY_DEAL, GOOD_DEAL, CREDIT, etc)
    """
    import time

    start_time = time.time()

    try:
        with get_abs_client() as abs_client:
            audible_client = get_audible_client()
            cache = get_cache()  # Get shared cache for enrichment

            # Get library ID from settings or pick first if not specified
            if not library_id:
                library_id = get_default_library_id()
            if not library_id:
                libraries = abs_client.get_libraries()
                if not libraries:
                    console.print("[red]No libraries found[/red]")
                    raise typer.Exit(1)
                library_id = libraries[0].id
                console.print(f"Using library: [bold]{libraries[0].name}[/bold]\n")

            # Get all items
            items_resp: dict[str, Any] = abs_client._get(f"/libraries/{library_id}/items", params={"limit": 0})
            all_items = items_resp.get("results", [])
            item_ids = [item.get("id") for item in all_items if item.get("id")]

            console.print(f"Phase 1: Scanning {len(item_ids)} items for quality < {threshold} kbps...\n")

            analyzer = QualityAnalyzer()
            upgrade_candidates = []

            # Phase 1: Find low quality items with ASIN (using parallel batch fetch)
            phase1_start = time.time()
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("[cyan]{task.fields[elapsed]}[/cyan]"),
                console=console,
            ) as progress:
                task = progress.add_task("Scanning quality...", total=len(item_ids), elapsed="")

                def update_progress(completed: int, total: int):
                    elapsed = time.time() - phase1_start
                    progress.update(task, completed=completed, elapsed=f"{elapsed:.1f}s")

                # Fetch all items in parallel with caching
                expanded_items = abs_client.batch_get_items_expanded(
                    item_ids,
                    use_cache=True,
                    max_workers=20,  # Use 20 workers for local server
                    progress_callback=update_progress,
                )

                # Analyze quality for each item
                for full_item in expanded_items:
                    if full_item:
                        quality = analyzer.analyze_item(full_item)

                        # Filter: below threshold AND has ASIN for Audible lookup
                        if quality.bitrate_kbps < threshold and quality.asin:
                            upgrade_candidates.append(quality)

            phase1_time = time.time() - phase1_start

            if not upgrade_candidates:
                console.print(f"[green]✓[/green] No upgrade candidates found below {threshold} kbps with ASIN!")
                return

            console.print(f"\n[yellow]Found {len(upgrade_candidates)} upgrade candidates with ASINs[/yellow]")
            console.print(f"[dim]Phase 1 completed in {phase1_time:.1f}s[/dim]")

            # Phase 2: Enrich with Audible data
            console.print(f"\nPhase 2: Fetching Audible pricing for {len(upgrade_candidates)} items...\n")

            enrichment_service = AudibleEnrichmentService(audible_client, cache=cache)
            asins = [c.asin for c in upgrade_candidates if c.asin]

            enrichments = {}
            phase2_start = time.time()
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("[cyan]{task.fields[elapsed]}[/cyan]"),
                console=console,
            ) as progress:
                task = progress.add_task("Enriching...", total=len(asins), elapsed="")

                for asin in asins:
                    try:
                        enrichment = enrichment_service.enrich_single(asin)
                        if enrichment:
                            enrichments[asin] = enrichment
                    except Exception as e:
                        # Find the title for this ASIN from upgrade_candidates
                        candidate_title = next((c.title for c in upgrade_candidates if c.asin == asin), "Unknown")
                        logger.error(
                            f"Failed to enrich ASIN {asin}: {e}",
                            exc_info=True,
                            extra={"asin": asin, "title": candidate_title},
                        )

                    elapsed = time.time() - phase2_start
                    progress.update(task, advance=1, elapsed=f"{elapsed:.1f}s")

            phase2_time = time.time() - phase2_start
            stats = enrichment_service.stats
            console.print(
                f"[dim]Phase 2 completed in {phase2_time:.1f}s (cache hits: {stats['cache_hits']}, API calls: {stats['api_calls']})[/dim]"
            )

            # Merge enrichment into quality objects
            for candidate in upgrade_candidates:
                if candidate.asin and candidate.asin in enrichments:
                    enrichment = enrichments[candidate.asin]
                    candidate.owned_on_audible = enrichment.owned
                    candidate.is_plus_catalog = enrichment.plus_catalog.is_plus_catalog
                    candidate.plus_expiration = enrichment.plus_catalog.expiration_display
                    if enrichment.pricing:
                        candidate.list_price = enrichment.pricing.list_price
                        candidate.sale_price = enrichment.pricing.sale_price
                        candidate.discount_percent = enrichment.pricing.discount_percent
                        candidate.is_good_deal = enrichment.pricing.is_good_deal
                        candidate.is_monthly_deal = enrichment.pricing.is_monthly_deal
                    candidate.has_atmos_upgrade = enrichment.has_atmos
                    candidate.acquisition_recommendation = enrichment.acquisition_recommendation
                    candidate.audible_url = enrichment.audible_url
                    candidate.cover_image_url = enrichment.cover_image_url
                    # Boost priority based on acquisition opportunity
                    candidate.upgrade_priority = int(candidate.upgrade_priority * enrichment.priority_boost)

            # Filter if requested
            if plus_only:
                upgrade_candidates = [c for c in upgrade_candidates if c.is_plus_catalog]
                console.print(f"[cyan]Filtering to Plus Catalog: {len(upgrade_candidates)} items[/cyan]")

            if monthly_deals:
                upgrade_candidates = [c for c in upgrade_candidates if getattr(c, "is_monthly_deal", False)]
                console.print(f"[cyan]Filtering to monthly deals: {len(upgrade_candidates)} items[/cyan]")

            if deals_only:
                upgrade_candidates = [c for c in upgrade_candidates if c.is_good_deal]
                console.print(f"[cyan]Filtering to good deals (<$9): {len(upgrade_candidates)} items[/cyan]")

            # Sort by priority (highest first)
            upgrade_candidates.sort(key=lambda x: x.upgrade_priority, reverse=True)

            if not upgrade_candidates:
                console.print("[yellow]No items match the selected filters[/yellow]")
                return

            # Display table
            console.print()
            table = Table(title=f"Upgrade Candidates ({len(upgrade_candidates)} items)")
            table.add_column("Priority", justify="right", style="bold")
            table.add_column("kbps", justify="right")
            table.add_column("Title", max_width=35)
            table.add_column("Recommendation", style="bold")
            table.add_column("Price", justify="right")
            table.add_column("Owned", justify="center")
            table.add_column("Atmos", justify="center")

            for item in upgrade_candidates[:limit]:
                # Determine recommendation color
                rec = item.acquisition_recommendation or "N/A"
                if rec.startswith("FREE"):
                    rec_style = "[green bold]"
                elif rec.startswith("MONTHLY_DEAL"):
                    rec_style = "[magenta bold]"
                elif rec.startswith("GOOD_DEAL"):
                    rec_style = "[cyan]"
                elif rec == "OWNED":
                    rec_style = "[dim]"
                else:
                    rec_style = "[white]"

                # Price display
                if item.sale_price:
                    if item.discount_percent and item.discount_percent > 0:
                        price_display = f"${item.sale_price:.2f} ({item.discount_percent:.0f}% off)"
                    else:
                        price_display = f"${item.sale_price:.2f}"
                elif item.list_price:
                    price_display = f"${item.list_price:.2f}"
                else:
                    price_display = "-"

                # Owned badge
                owned_display = "✓" if item.owned_on_audible else ""

                # Atmos badge
                atmos_display = "[magenta]🎧[/magenta]" if item.has_atmos_upgrade else ""

                table.add_row(
                    str(item.upgrade_priority),
                    f"{item.bitrate_kbps:.0f}",
                    item.title[:35],
                    f"{rec_style}{rec}[/]" if rec_style else rec,
                    price_display,
                    owned_display,
                    atmos_display,
                )

            console.print(table)

            if len(upgrade_candidates) > limit:
                console.print(
                    f"\n[dim]Showing {limit} of {len(upgrade_candidates)} items. Use --limit to show more.[/dim]"
                )

            # Summary stats
            plus_count = sum(1 for c in upgrade_candidates if c.is_plus_catalog)
            deals_count = sum(1 for c in upgrade_candidates if c.is_good_deal)
            owned_count = sum(1 for c in upgrade_candidates if c.owned_on_audible)
            atmos_count = sum(1 for c in upgrade_candidates if c.has_atmos_upgrade)

            console.print("\n[bold]Summary:[/bold]")
            console.print(f"  [green]Plus Catalog (FREE):[/green] {plus_count}")
            console.print(f"  [cyan]Good Deals (<$9):[/cyan] {deals_count}")
            console.print(f"  [dim]Already Owned:[/dim] {owned_count}")
            console.print(f"  [magenta]Atmos Available:[/magenta] {atmos_count}")

            total_time = time.time() - start_time
            console.print(f"\n[dim]Total time: {total_time:.1f}s[/dim]")

            # Export if requested
            if output:
                import json

                output.parent.mkdir(parents=True, exist_ok=True)

                monthly_deals_count = sum(1 for c in upgrade_candidates if getattr(c, "is_monthly_deal", False))

                export_data = {
                    "summary": {
                        "total_candidates": len(upgrade_candidates),
                        "plus_catalog_count": plus_count,
                        "monthly_deals_count": monthly_deals_count,
                        "good_deals_count": deals_count,
                        "already_owned_count": owned_count,
                        "atmos_available_count": atmos_count,
                    },
                    "upgrade_candidates": [
                        {
                            "title": item.title,
                            "author": item.author,
                            "asin": item.asin,
                            "bitrate_kbps": round(item.bitrate_kbps, 0),
                            "format": item.format_label,
                            "size_mb": round(item.size_mb, 1),
                            "path": item.path,
                            "tier": item.tier_label,
                            "upgrade_priority": item.upgrade_priority,
                            "owned_on_audible": item.owned_on_audible,
                            "is_plus_catalog": item.is_plus_catalog,
                            "plus_expiration": item.plus_expiration,
                            "is_monthly_deal": getattr(item, "is_monthly_deal", False),
                            "list_price": round(item.list_price, 2) if item.list_price else None,
                            "sale_price": round(item.sale_price, 2) if item.sale_price else None,
                            "discount_percent": round(item.discount_percent, 1) if item.discount_percent else None,
                            "is_good_deal": item.is_good_deal,
                            "has_atmos_upgrade": item.has_atmos_upgrade,
                            "acquisition_recommendation": item.acquisition_recommendation,
                            "audible_url": getattr(item, "audible_url", None),
                            "cover_image_url": getattr(item, "cover_image_url", None),
                        }
                        for item in upgrade_candidates
                    ],
                }

                with open(output, "w") as f:
                    json.dump(export_data, f, indent=2)

                console.print(f"\n[green]✓[/green] Exported {len(upgrade_candidates)} items to {output}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import traceback

        traceback.print_exc()
        raise typer.Exit(1)


# ============================================================================
# SERIES COMMANDS
# ============================================================================


@series_app.command("list")
def series_list(
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
    limit: int = typer.Option(None, "--limit", "-n", help="Max series to show"),
):
    """List all series in a library."""
    library_id = resolve_library_id(library_id)
    try:
        with get_abs_client() as abs_client:
            matcher = SeriesMatcher(abs_client=abs_client, audible_client=None)
            series_list_data = matcher.get_abs_series(library_id)

            if not series_list_data:
                console.print("[yellow]No series found in library[/yellow]")
                return

            # Sort by book count (descending)
            series_list_data.sort(key=lambda s: len(s.books), reverse=True)

            if limit:
                series_list_data = series_list_data[:limit]

            table = Table(title=f"Series in Library ({len(series_list_data)} total)")
            table.add_column("#", style="dim")
            table.add_column("Series Name", style="bold")
            table.add_column("Books", justify="right")
            table.add_column("Duration", justify="right")
            table.add_column("With ASIN", justify="right")

            for i, series in enumerate(series_list_data, 1):
                total_duration = sum(b.duration or 0 for b in series.books)
                hours = total_duration / 3600
                with_asin = sum(1 for b in series.books if b.asin)

                table.add_row(
                    str(i),
                    series.name,
                    str(len(series.books)),
                    f"{hours:.1f}h",
                    f"{with_asin}/{len(series.books)}",
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@series_app.command("analyze")
def series_analyze(
    series_name: str = typer.Argument(..., help="Series name to analyze"),
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table or json"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file (default: stdout for json)"),
):
    """Analyze a specific series and find missing books."""
    library_id = resolve_library_id(library_id)
    try:
        with get_abs_client() as abs_client, get_audible_client() as audible_client:
            matcher = SeriesMatcher(abs_client=abs_client, audible_client=audible_client)

            # Find the series
            all_series = matcher.get_abs_series(library_id)

            if not all_series:
                console.print("[yellow]No series found in this library[/yellow]")
                console.print(
                    "[dim]Hint: Series are detected from book metadata. Make sure your books have series information.[/dim]"
                )
                raise typer.Exit(1)

            target_series = None

            for s in all_series:
                if s.name.lower() == series_name.lower():
                    target_series = s
                    break

            if not target_series:
                # Try fuzzy match
                from rapidfuzz import fuzz

                best_match = None
                best_score = 0
                similar_series: list[tuple[str, int]] = []

                for s in all_series:
                    score = fuzz.ratio(s.name.lower(), series_name.lower())
                    if score > best_score:
                        best_score = score
                        best_match = s
                    if score > 50:
                        similar_series.append((s.name, score))

                if best_match and best_score > 70:
                    console.print(
                        f"[yellow]Exact match not found. Using '{best_match.name}' (score: {best_score})[/yellow]"
                    )
                    target_series = best_match
                else:
                    console.print(f"[red]Series '{series_name}' not found in library[/red]")

                    # Show similar matches if any
                    if similar_series:
                        similar_series.sort(key=lambda x: x[1], reverse=True)
                        console.print("\n[yellow]Did you mean one of these?[/yellow]")
                        for name, score in similar_series[:5]:
                            console.print(f"  • {name} [dim](similarity: {score:.0f}%)[/dim]")

                    console.print(
                        "\n[dim]Hint: Run [cyan]python cli.py series list[/cyan] to see all available series[/dim]"
                    )
                    raise typer.Exit(1)

            # Analyze the series
            console.print(f"\n[bold]Analyzing:[/bold] {target_series.name}")
            console.print(f"  Books in ABS: {len(target_series.books)}")

            result = matcher.compare_series(target_series)

            # JSON output format
            if format.lower() == "json":
                import json

                export_data = {
                    "series_name": result.series_match.abs_series.name,
                    "audible_series_asin": (
                        result.series_match.audible_series.asin if result.series_match.audible_series else None
                    ),
                    "match_confidence": result.series_match.confidence.value,
                    "in_library": result.abs_book_count,
                    "on_audible": result.audible_book_count,
                    "completion_percentage": result.completion_percentage,
                    "is_complete": result.is_complete,
                    "matched_books": [
                        {
                            "title": m.abs_book.title,
                            "asin": m.abs_book.asin,
                            "sequence": m.abs_book.sequence,
                            "audible_asin": m.audible_book.asin if m.audible_book else None,
                            "match_confidence": m.confidence.value,
                            "matched_by": m.matched_by,
                        }
                        for m in result.matched_books
                    ],
                    "missing_books": [
                        {
                            "title": b.title,
                            "asin": b.asin,
                            "sequence": b.sequence,
                            "runtime_hours": b.runtime_hours,
                            "release_date": b.release_date,
                            "author": b.author_name,
                            "narrator": b.narrator_name,
                            "price": b.price,
                            "is_in_plus_catalog": b.is_in_plus_catalog,
                            "audible_url": b.audible_url,
                        }
                        for b in result.missing_books
                    ],
                }

                json_output = json.dumps(export_data, indent=2)
                if output:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with open(output, "w") as f:
                        f.write(json_output)
                    console.print(f"[green]✓[/green] Exported to {output}")
                else:
                    print(json_output)
                return

            # Table output format (default)
            series_name = result.series_match.abs_series.name
            match_confidence = result.series_match.confidence
            audible_series = result.series_match.audible_series

            console.print(f"\n[bold cyan]═══ {series_name} ═══[/bold cyan]")
            console.print(f"Match Confidence: {match_confidence.value}")

            if audible_series and audible_series.asin:
                console.print(f"Audible Series ASIN: {audible_series.asin}")

            console.print("\n[bold]Collection Status:[/bold]")
            console.print(f"  Your Library: {result.abs_book_count} books")
            console.print(f"  On Audible: {result.audible_book_count} books")
            console.print(f"  Completion: {result.completion_percentage:.1f}%")

            # Matched books
            if result.matched_books and verbose:
                console.print(f"\n[bold green]Matched Books ({len(result.matched_books)}):[/bold green]")
                for match in result.matched_books:
                    confidence_color = {
                        MatchConfidence.EXACT: "green",
                        MatchConfidence.HIGH: "cyan",
                        MatchConfidence.MEDIUM: "yellow",
                        MatchConfidence.LOW: "red",
                    }.get(match.confidence, "white")

                    seq = f"#{match.abs_book.sequence}" if match.abs_book.sequence else ""
                    console.print(f"  [{confidence_color}]✓[/{confidence_color}] {match.abs_book.title} {seq}")

            # Missing books
            if result.missing_books:
                console.print(f"\n[bold red]Missing Books ({len(result.missing_books)}):[/bold red]")
                for book in result.missing_books:
                    seq = f"#{book.sequence}" if book.sequence else ""
                    duration = f"({book.runtime_hours:.1f}h)" if book.runtime_hours else ""
                    console.print(f"  [red]✗[/red] {book.title} {seq} {duration}")

            # Unmatched ABS books (in ABS but couldn't match to any Audible book)
            # Find them by comparing matched books with all ABS books
            matched_abs_ids = {m.abs_book.id for m in result.matched_books}
            unmatched_abs = [b for b in target_series.books if b.id not in matched_abs_ids]

            if unmatched_abs and verbose:
                console.print(f"\n[bold yellow]Unmatched ABS Books ({len(unmatched_abs)}):[/bold yellow]")
                for book in unmatched_abs:
                    seq = f"#{book.sequence}" if book.sequence else ""
                    console.print(f"  [yellow]?[/yellow] {book.title} {seq}")

    except typer.Exit:
        raise  # Re-raise typer exits without catching
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import traceback

        traceback.print_exc()
        raise typer.Exit(1) from e


@series_app.command("report")
def series_report(
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
    min_books: int = typer.Option(2, "--min-books", "-m", help="Minimum books in series to analyze"),
    limit: int = typer.Option(None, "--limit", "-n", help="Max series to analyze"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table or json"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file (default: stdout for json)"),
    incomplete_only: bool = typer.Option(False, "--incomplete", "-i", help="Only show incomplete series"),
):
    """Generate a full series analysis report for a library."""
    import json
    import time

    library_id = resolve_library_id(library_id)
    start_time = time.time()

    try:
        with get_abs_client() as abs_client, get_audible_client() as audible_client:
            matcher = SeriesMatcher(abs_client=abs_client, audible_client=audible_client)

            console.print(f"\n[bold]Analyzing library series...[/bold]")

            # Get all series
            all_series = matcher.get_abs_series(library_id)
            all_series = [s for s in all_series if len(s.books) >= min_books]
            all_series.sort(key=lambda s: len(s.books), reverse=True)

            if limit:
                all_series = all_series[:limit]

            console.print(f"Found {len(all_series)} series with {min_books}+ books")

            # Analyze each series
            results: list[SeriesComparisonResult] = []

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Analyzing series...", total=len(all_series))

                for series in all_series:
                    progress.update(task, description=f"Analyzing: {series.name[:30]}...")

                    try:
                        result = matcher.compare_series(series)
                        results.append(result)
                    except Exception as e:
                        logger.warning(f"Failed to analyze series '{series.name}': {e}")

                    progress.advance(task)

            # Calculate summary stats BEFORE filtering
            all_results = results  # Keep reference for summary
            total_in_library = sum(r.abs_book_count for r in all_results)
            total_on_audible = sum(r.audible_book_count for r in all_results if r.audible_book_count)
            total_missing = sum(len(r.missing_books) for r in all_results)
            complete_series_count = sum(1 for r in all_results if r.is_complete)

            # Detect warnings for data quality issues
            asin_to_series: dict[str, list[str]] = {}
            for r in all_results:
                if r.series_match.audible_series and r.series_match.audible_series.asin:
                    asin = r.series_match.audible_series.asin
                    series_name = r.series_match.abs_series.name
                    if asin not in asin_to_series:
                        asin_to_series[asin] = []
                    asin_to_series[asin].append(series_name)

            # Add warnings to each result
            for r in all_results:
                warnings = []

                # Check for duplicate ASIN (multiple ABS series → same Audible series)
                if r.series_match.audible_series and r.series_match.audible_series.asin:
                    asin = r.series_match.audible_series.asin
                    if len(asin_to_series.get(asin, [])) > 1:
                        other_series = [s for s in asin_to_series[asin] if s != r.series_match.abs_series.name]
                        warnings.append(f"DUPLICATE_ASIN: Also matched by '{other_series[0]}'")

                # Check for missing metadata (no Audible match)
                if not r.series_match.audible_series or not r.series_match.audible_series.asin:
                    warnings.append("MISSING_METADATA: No Audible series found (check ABS metadata)")

                # Check for potential duplicates in library (>100% completion)
                if r.completion_percentage > 100:
                    warnings.append(
                        f"POTENTIAL_DUPES: Library has {r.abs_book_count} books but Audible shows {r.audible_book_count}"
                    )

                r.warnings = warnings

            # Filter if needed
            if incomplete_only:
                results = [r for r in results if not r.is_complete]

            # Sort by completion percentage
            results.sort(key=lambda r: r.completion_percentage)

            elapsed = time.time() - start_time

            # Build export data (used for both JSON format and file export)
            export_data = {
                "summary": {
                    "series_analyzed": len(all_results),
                    "series_shown": len(results),
                    "complete_series": complete_series_count,
                    "total_in_library": total_in_library,
                    "total_on_audible": total_on_audible,
                    "total_missing": total_missing,
                    "analysis_time_seconds": elapsed,
                },
                "series": [
                    {
                        "name": (
                            r.series_match.audible_series.title
                            if r.series_match.audible_series and r.series_match.audible_series.title
                            else r.series_match.abs_series.name
                        ),
                        "abs_name": r.series_match.abs_series.name,
                        "audible_asin": (r.series_match.audible_series.asin if r.series_match.audible_series else None),
                        "in_library": r.abs_book_count,
                        "on_audible": r.audible_book_count,
                        "completion_percentage": r.completion_percentage,
                        "is_complete": r.is_complete,
                        "match_confidence": r.series_match.confidence.value,
                        "warnings": r.warnings,
                        "matched_books": [
                            {
                                "title": m.abs_book.title,
                                "sequence": m.abs_book.sequence,
                                "asin": m.audible_book.asin if m.audible_book else None,
                                "confidence": m.confidence.value,
                            }
                            for m in r.matched_books
                        ],
                        "missing_books": [
                            {
                                "title": b.title,
                                "sequence": b.sequence,
                                "asin": b.asin,
                                "runtime_hours": b.runtime_hours,
                                "release_date": b.release_date,
                                "author": b.author_name,
                                "narrator": b.narrator_name,
                                "price": b.price,
                                "is_in_plus_catalog": b.is_in_plus_catalog,
                                "audible_url": b.audible_url,
                            }
                            for b in r.missing_books
                        ],
                    }
                    for r in results
                ],
            }

            # JSON output format
            if format.lower() == "json":
                json_output = json.dumps(export_data, indent=2)
                if output:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with open(output, "w") as f:
                        f.write(json_output)
                    console.print(f"[green]✓[/green] Exported to {output}")
                else:
                    print(json_output)
                return

            # Table output format (default)
            table = Table(title=f"Series Analysis Report ({len(results)} series)")
            table.add_column("Series", style="bold")
            table.add_column("In Library", justify="right")
            table.add_column("On Audible", justify="right")
            table.add_column("Complete", justify="right")
            table.add_column("Missing", justify="right")
            table.add_column("Warnings", style="yellow")

            for result in results:
                # Use Audible series name as source of truth
                if result.series_match.audible_series and result.series_match.audible_series.title:
                    series_name = result.series_match.audible_series.title
                else:
                    series_name = result.series_match.abs_series.name

                completion_style = (
                    "green"
                    if result.completion_percentage >= 100
                    else "yellow" if result.completion_percentage >= 75 else "red"
                )

                # Build warning indicators
                warning_indicators = []
                for w in result.warnings:
                    if w.startswith("DUPLICATE_ASIN"):
                        warning_indicators.append("⚠️ DUP")
                    elif w.startswith("MISSING_METADATA"):
                        warning_indicators.append("⚠️ META")
                    elif w.startswith("POTENTIAL_DUPES"):
                        warning_indicators.append("🔍 DUPE?")
                warning_str = " ".join(warning_indicators)

                table.add_row(
                    series_name[:40],
                    str(result.abs_book_count),
                    str(result.audible_book_count) if result.audible_book_count else "?",
                    f"[{completion_style}]{result.completion_percentage:.0f}%[/{completion_style}]",
                    str(len(result.missing_books)),
                    warning_str,
                )

            console.print(table)

            # Summary stats (use pre-calculated values from all_results)
            console.print(f"\n[bold]Summary:[/bold]")
            console.print(f"  Total series analyzed: {len(all_results)}")
            if incomplete_only:
                console.print(f"  Incomplete series shown: {len(results)}")
            console.print(f"  Complete series: [green]{complete_series_count}[/green]")
            console.print(f"  Books in library: {total_in_library}")
            console.print(f"  Books on Audible: {total_on_audible}")
            console.print(f"  Missing books: [red]{total_missing}[/red]")

            console.print(f"\n[dim]Analysis completed in {elapsed:.1f}s[/dim]")

            # Export to file if requested (for table format)
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                with open(output, "w") as f:
                    json.dump(export_data, f, indent=2)
                console.print(f"\n[green]✓[/green] Exported report to {output}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import traceback

        traceback.print_exc()
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
