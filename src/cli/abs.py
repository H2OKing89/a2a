"""
Audiobookshelf (ABS) CLI commands.

Commands for interacting with the Audiobookshelf API:
- status: Check ABS connection status
- libraries: List all libraries
- stats: Show library statistics
- items: List library items
- item: Show item details
- search: Search a library
- export: Export library to JSON
- authors: List authors
- series: List series
- collections: Manage collections
- sample: Collect golden samples
"""

import json
from pathlib import Path
from typing import Any

import typer
from rich.box import ROUNDED
from rich.padding import Padding
from rich.text import Text

from src.abs import ABSAuthError, ABSConnectionError, ABSError
from src.cli.common import Icons, console, get_abs_client, resolve_library_id, ui
from src.config import get_settings
from src.utils import save_golden_sample
from src.utils.ui import Panel, Table

# Create ABS sub-app
abs_app = typer.Typer(help="📚 Audiobookshelf API commands")


@abs_app.command("status")
def abs_status():
    """Check ABS connection status."""
    settings = get_settings()

    ui.header("Audiobookshelf", subtitle=settings.abs.host, icon=Icons.SERVER)

    try:
        with ui.spinner("Connecting...") as status, get_abs_client() as client:
            # Show resolved/normalized host (what we're actually connecting to)
            if client.host != settings.abs.host:
                console.print(f"  {Icons.LINK} Resolved: [accent]{client.host}[/accent]")

            # Display security status from client (after normalization)
            if client._is_https:
                ui.success("Connection secured with HTTPS")
                if client._using_ca_bundle:
                    ui.success(f"Using custom CA bundle: {client._tls_ca_bundle_path}")
                elif not client._insecure_tls:
                    ui.success("SSL certificate verification enabled")
            elif client._is_localhost:
                console.print(f"  {Icons.BULLET} Using HTTP for localhost [dim](OK for local development)[/dim]")
            else:
                ui.warning(
                    "Using insecure HTTP to remote server",
                    details="API key sent in cleartext!",
                )
                console.print(
                    f"    [dim]{Icons.BULLET} Fix: Put ABS behind a reverse proxy (Caddy/Nginx/Traefik) "
                    "with HTTPS, or enable HTTPS in ABS directly.[/dim]"
                )

            if client._insecure_tls:
                ui.warning(
                    "SSL certificate verification is DISABLED",
                    details="This is insecure. Use tls_ca_bundle for self-signed certificates instead.",
                )

            # HTTP/2 status: show availability vs actual negotiation
            if client._http2_available:
                ui.success("HTTP/2 support available")
            else:
                console.print(f"  {Icons.BULLET} HTTP/2 not available [dim](install httpx[http2])[/dim]")

            status.update("Fetching user info...")
            user = client.get_me()
            status.update("Fetching libraries...")
            libraries = client.get_libraries()

            # Now show actual negotiated protocol (after requests)
            if client._last_http_version:
                if client._last_http_version == "HTTP/2":
                    ui.success("Negotiated HTTP/2 with server")
                else:
                    console.print(
                        f"  {Icons.BULLET} Using {client._last_http_version} "
                        "[dim](server may not support HTTP/2)[/dim]"
                    )

        ui.success(f"Authenticated as: [bold]{user.username}[/bold] ({user.type})")
        console.print(f"    {Icons.BULLET} Active: {user.is_active}, Locked: {user.is_locked}")

        # Libraries tree
        ui.subsection(f"{Icons.BOOK} Libraries ({len(libraries)})")
        tree = ui.tree("Available Libraries")
        for lib in libraries:
            icon = Icons.BOOK if lib.is_book_library else Icons.MIC
            tree.add(f"{icon} [bold]{lib.name}[/bold] [dim]({lib.id})[/dim] - {lib.media_type}")
        console.print(Padding(tree, (0, 4)))

    except (ABSError, ABSConnectionError, ABSAuthError) as e:
        # Expected errors - show friendly message only, no traceback
        ui.error("Connection failed", details=str(e))
        raise typer.Exit(1)
    except Exception as e:
        # Unexpected errors - show traceback for debugging
        ui.error("Connection failed", details=str(e))
        raise typer.Exit(1) from e


@abs_app.command("libraries")
def abs_libraries():
    """List all libraries."""
    try:
        with ui.spinner("Fetching libraries..."), get_abs_client() as client:
            libs = client.get_libraries()

        table = ui.create_table(
            title=f"{Icons.BOOK} Libraries",
            show_lines=False,
            box_style=ROUNDED,
        )
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="bold white")
        table.add_column("Type", style="accent")
        table.add_column("Provider")
        table.add_column("Folders", style="muted")

        for lib in libs:
            icon = Icons.BOOK if lib.is_book_library else Icons.MIC
            folders = ", ".join(f.full_path for f in lib.folders)
            table.add_row(
                lib.id,
                f"{icon} {lib.name}",
                lib.media_type,
                lib.provider,
                folders[:50] + "..." if len(folders) > 50 else folders,
            )

        console.print()
        console.print(table)

    except Exception as e:
        ui.error("Error", details=str(e))
        raise typer.Exit(1) from e


@abs_app.command("stats")
def abs_stats(
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
):
    """Show library statistics."""
    library_id = resolve_library_id(library_id)
    try:
        with ui.spinner("Fetching library statistics..."), get_abs_client() as client:
            lib = client.get_library(library_id)
            stats = client.get_library_stats(library_id)

        # Build stats display
        stats_text = Text()
        stats_text.append(f"\n{Icons.BOOK} Total Items: ", style="bold")
        stats_text.append(f"{stats.total_items}\n", style="accent")

        stats_text.append(f"{Icons.AUTHOR} Total Authors: ", style="bold")
        stats_text.append(f"{stats.total_authors}\n", style="accent")

        stats_text.append("🏷️  Total Genres: ", style="bold")
        stats_text.append(f"{stats.total_genres}\n", style="accent")

        stats_text.append(f"\n{Icons.CLOCK} Total Duration: ", style="bold")
        stats_text.append(f"{stats.total_duration / 3600:.1f} hours\n", style="duration")

        stats_text.append(f"{Icons.MUSIC} Audio Tracks: ", style="bold")
        stats_text.append(f"{stats.num_audio_tracks}\n", style="accent")

        stats_text.append(f"\n{Icons.DATABASE} Total Size: ", style="bold")
        stats_text.append(f"{stats.total_size / (1024**3):.2f} GB\n", style="size")

        console.print(
            Panel(
                stats_text,
                title=f"{Icons.BOOK} [bold]{lib.name}[/bold]",
                subtitle="Library Statistics",
                border_style="cyan",
                box=ROUNDED,
                padding=(1, 2),
            )
        )

    except Exception as e:
        ui.error("Error", details=str(e))
        raise typer.Exit(1) from e


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
        with ui.spinner("Fetching library items..."), get_abs_client() as client:
            response = client.get_library_items(
                library_id=library_id,
                limit=limit,
                sort=sort,
                desc=desc,
            )

        table = ui.create_table(
            title=f"{Icons.BOOK} Library Items ({response.total} total)",
            box_style=ROUNDED,
        )
        table.add_column("ID", style="cyan", max_width=25, no_wrap=True)
        table.add_column("Title", style="bold white", max_width=40)
        table.add_column("Author", style="author", max_width=25)
        table.add_column("Duration", justify="right", style="duration")
        table.add_column("Size", justify="right", style="size")

        for item in response.results:
            meta = item.media.metadata
            duration_hrs = item.media.duration / 3600 if item.media.duration else 0
            size_mb = (item.size or 0) / (1024**2)

            table.add_row(
                item.id,
                meta.title[:40] if meta.title else "?",
                (meta.author_name or "Unknown")[:25],
                f"{duration_hrs:.1f}h",
                f"{size_mb:.0f} MB",
            )

        console.print()
        console.print(table)
        console.print(f"\n[muted]Showing {len(response.results)} of {response.total} items[/muted]")

    except Exception as e:
        ui.error("Error", details=str(e))
        raise typer.Exit(1) from e


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
                audio_table = Table(title="Audio Files")
                audio_table.add_column("#", justify="right")
                audio_table.add_column("Filename", max_width=50)
                audio_table.add_column("Codec")
                audio_table.add_column("Bitrate", justify="right")
                audio_table.add_column("Duration", justify="right")

                for af in item.media.audio_files:
                    audio_table.add_row(
                        str(af.index),
                        af.metadata.filename[:50],
                        af.codec or "?",
                        f"{af.bit_rate // 1000}k" if af.bit_rate else "?",
                        f"{af.duration / 60:.1f}m",
                    )

                console.print(audio_table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


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
        raise typer.Exit(1) from e


@abs_app.command("export")
def abs_export(
    library_id: str | None = typer.Option(
        None, "--library", "-l", help="Library ID (default: ABS_LIBRARY_ID from .env)"
    ),
    output: Path = typer.Option(Path("library_export.json"), "--output", "-o", help="Output file"),
):
    """Export all library items to JSON."""
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
        raise typer.Exit(1) from e


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
        raise typer.Exit(1) from e


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
        raise typer.Exit(1) from e


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
                    table.add_row(
                        coll.name or "?",
                        str(coll.book_count),
                        (coll.library_id or "")[:20],
                        coll.id or "",
                    )

                console.print(table)

            elif action == "show":
                if not collection_id:
                    console.print("[red]Error:[/red] --id required for 'show'")
                    raise typer.Exit(1)

                coll = client.get_collection(collection_id)

                # Header panel
                console.print(
                    Panel(
                        f"[bold]{coll.name or 'Unknown'}[/bold]\n\n"
                        f"ID: [cyan]{coll.id}[/cyan]\n"
                        f"Library: {coll.library_id or 'N/A'}\n"
                        f"Description: {coll.description or '(none)'}\n"
                        f"Books: [green]{coll.book_count}[/green]",
                        title="📁 Collection Details",
                    )
                )

                if coll.books:
                    book_table = Table(show_header=True, header_style="bold")
                    book_table.add_column("#", style="dim", width=4)
                    book_table.add_column("Title", style="bold", max_width=50)
                    book_table.add_column("ID", style="dim cyan", max_width=24)

                    for i, book in enumerate(coll.books, 1):
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
                console.print(f"  ID: [cyan]{result.id}[/cyan]")

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
        raise typer.Exit(1) from e


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
        raise typer.Exit(1) from e
