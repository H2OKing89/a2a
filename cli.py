#!/usr/bin/env python3
"""
CLI for audiobook management tool.
"""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_settings, reload_settings
from src.abs import ABSClient
from src.audible import AudibleClient, AudibleAuthError
from src.cache import SQLiteCache
from src.utils import save_golden_sample

app = typer.Typer(
    name="audiobook-tool",
    help="Audiobook management tool using ABS and Audible APIs",
)

# Sub-app for Audible commands
audible_app = typer.Typer(help="Audible API commands")
app.add_typer(audible_app, name="audible")

console = Console()

# Global cache instance (lazy-loaded)
_cache: Optional[SQLiteCache] = None


def get_cache() -> Optional[SQLiteCache]:
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
    """Check connection status to ABS server."""
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
    namespace: Optional[str] = typer.Option(None, "--namespace", "-n", help="Specific namespace to clear"),
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
            cache_stats = cache.get_stats()
            
            # Format namespaces display
            namespaces_display = "\n".join(
                f"  {k}: {v}" for k, v in cache_stats.get('namespaces', {}).items()
            ) or "  (none)"
            
            console.print(Panel(
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
            ))
                
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def libraries():
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


@app.command()
def stats(library_id: str = typer.Argument(..., help="Library ID")):
    """Show library statistics."""
    try:
        with get_abs_client() as client:
            lib = client.get_library(library_id)
            stats = client.get_library_stats(library_id)
            
            console.print(Panel(
                f"[bold]{lib.name}[/bold]\n\n"
                f"Total Items: {stats.total_items}\n"
                f"Total Authors: {stats.total_authors}\n"
                f"Total Genres: {stats.total_genres}\n"
                f"Total Duration: {stats.total_duration / 3600:.1f} hours\n"
                f"Audio Tracks: {stats.num_audio_tracks}\n"
                f"Total Size: {stats.total_size / (1024**3):.2f} GB",
                title="Library Statistics",
            ))
            
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def items(
    library_id: str = typer.Argument(..., help="Library ID"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of items to show"),
    sort: Optional[str] = typer.Option(None, "--sort", "-s", help="Sort field"),
    desc: bool = typer.Option(False, "--desc", "-d", help="Sort descending"),
):
    """List library items."""
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


@app.command()
def item(
    item_id: str = typer.Argument(..., help="Item ID"),
):
    """Show details for a specific item."""
    try:
        with get_abs_client() as client:
            item = client.get_item(item_id, expanded=True)
            meta = item.media.metadata
            
            # Basic info
            console.print(Panel(
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
            ))
            
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


@app.command()
def search(
    library_id: str = typer.Argument(..., help="Library ID"),
    query: str = typer.Argument(..., help="Search query"),
):
    """Search a library."""
    try:
        with get_abs_client() as client:
            results = client.search_library(library_id, query)
            
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


@app.command()
def export(
    library_id: str = typer.Argument(..., help="Library ID"),
    output: Path = typer.Option(Path("library_export.json"), "--output", "-o", help="Output file"),
):
    """Export all library items to JSON."""
    import json
    
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
            
            def otp_callback():
                return typer.prompt("Enter OTP/2FA code")
            
            def cvf_callback():
                return typer.prompt("Enter CVF verification code")
            
            client = AudibleClient.from_login(
                email=email,
                password=password,
                locale=locale,
                auth_file=auth_file,
                cache_dir=settings.paths.cache_dir / "audible" if settings.audible.cache_enabled else None,
                otp_callback=otp_callback,
                cvf_callback=cvf_callback,
            )
        
        console.print(f"\n[green]✓[/green] Login successful!")
        console.print(f"  Marketplace: {client.marketplace}")
        console.print(f"  Credentials saved to: {auth_file}")
        
    except Exception as e:
        console.print(f"[red]✗[/red] Login failed: {e}")
        raise typer.Exit(1)


@audible_app.command("status")
def audible_status():
    """Check Audible connection status."""
    settings = get_settings()
    
    console.print(f"\n[bold]Audible Status[/bold]")
    console.print(f"Auth file: {settings.audible.auth_file}")
    console.print(f"Locale: {settings.audible.locale}")
    
    if not settings.audible.auth_file.exists():
        console.print(f"\n[yellow]⚠[/yellow] Auth file not found. Run 'audible login' first.")
        raise typer.Exit(1)
    
    try:
        with get_audible_client() as client:
            console.print(f"[green]✓[/green] Connected to marketplace: [bold]{client.marketplace}[/bold]")
            
            # Get library count
            items = client.get_library(num_results=1, use_cache=False)
            library_count = len(items)
            console.print(f"\n[bold]Account Status:[/bold]")
            console.print(f"  Library accessible: [green]Yes[/green] ({library_count}+ items)")
            
            # Cache stats
            cache_stats = client.get_cache_stats()
            if cache_stats.get("enabled"):
                console.print(f"\n[bold]Cache:[/bold] SQLite")
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
            categories = []
            for ladder in book.category_ladders:
                if ladder.ladder:
                    cats = [c.name for c in ladder.ladder if c.name]
                    if cats:
                        categories.append(" > ".join(cats))
            
            console.print(Panel(
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
                f"Categories:\n  " + "\n  ".join(categories[:3]) if categories else "N/A",
                title=f"Audible Book: {asin}",
            ))
            
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
            stats = cache.get_stats()
            
            # Format namespaces display
            namespaces_display = "\n".join(
                f"  {k}: {v}" for k, v in stats.get('namespaces', {}).items()
            ) or "  (none)"
            
            console.print(Panel(
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
            ))
                
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# =============================================================================
# Golden Sample Commands
# =============================================================================

@app.command("sample-abs")
def sample_abs(
    library_id: str = typer.Argument(..., help="Library ID"),
    item_id: Optional[str] = typer.Option(None, "--item", "-i", help="Specific item ID"),
    output_dir: Path = typer.Option(Path("./data/samples"), "--output", "-o", help="Output directory"),
):
    """
    Collect golden samples from ABS API.
    
    Saves raw API responses for testing and documentation.
    """
    settings = get_settings()
    
    try:
        with get_abs_client() as client:
            console.print(f"\n[bold]Collecting ABS Golden Samples[/bold]\n")
            
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


@app.command("sample-audible")
def sample_audible(
    asin: Optional[str] = typer.Option(None, "--asin", "-a", help="Specific ASIN to sample"),
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
            console.print(f"\n[bold]Collecting Audible Golden Samples[/bold]\n")
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


if __name__ == "__main__":
    app()
