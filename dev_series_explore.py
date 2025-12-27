#!/usr/bin/env python3
"""
Series matching exploration script.

This script is for testing and exploring the series matching feature
before integrating it into the main CLI.

Usage:
    python dev_series_explore.py --library-id <id> [--max-series 5]
    python dev_series_explore.py --list-series <library-id>
    python dev_series_explore.py --test-match "Harry Potter"
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

from rapidfuzz import fuzz
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.abs import ABSClient
from src.audible import AudibleClient
from src.cache import SQLiteCache
from src.config import get_settings
from src.series import SeriesMatcher

console = Console()
logger = logging.getLogger(__name__)


def get_cache() -> SQLiteCache | None:
    """Get shared cache instance."""
    settings = get_settings()
    if not settings.cache.enabled:
        return None
    return SQLiteCache(
        db_path=settings.cache.db_path,
        default_ttl_hours=settings.cache.default_ttl_hours,
    )


def get_clients():
    """Get configured ABS and Audible clients."""
    settings = get_settings()
    cache = get_cache()

    abs_client = ABSClient(
        host=settings.abs.host,
        api_key=settings.abs.api_key,
        cache=cache,
    )

    audible_client = AudibleClient.from_file(
        auth_file=settings.audible.auth_file,
        cache=cache,
    )

    return abs_client, audible_client, cache


def list_libraries():
    """List available ABS libraries."""
    abs_client, _, _ = get_clients()

    console.print("\n[bold cyan]Available Libraries[/bold cyan]\n")

    with abs_client:
        libraries = abs_client.get_libraries()

        table = Table(show_header=True)
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Type")
        table.add_column("Items")

        for lib in libraries:
            if lib.is_book_library:
                stats = abs_client.get_library_stats(lib.id)
                table.add_row(
                    lib.id,
                    lib.name,
                    lib.media_type,
                    str(stats.total_items),
                )

        console.print(table)


def list_series(library_id: str, limit: int = 20):
    """List series in a library."""
    abs_client, audible_client, cache = get_clients()

    console.print(f"\n[bold cyan]Series in Library: {library_id}[/bold cyan]\n")

    with abs_client:
        matcher = SeriesMatcher(abs_client, audible_client, cache)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Fetching series...", total=None)
            series_list = matcher.get_abs_series(library_id, limit=limit)

        table = Table(show_header=True)
        table.add_column("#", style="dim")
        table.add_column("Name", style="bold")
        table.add_column("Books", justify="right")
        table.add_column("Duration", justify="right")
        table.add_column("Has ASIN")

        for idx, series in enumerate(series_list, 1):
            has_asin = "✓" if series.asins else "✗"
            duration_hrs = round(series.total_duration / 3600, 1) if series.total_duration else 0

            table.add_row(
                str(idx),
                series.name[:50],
                str(series.book_count),
                f"{duration_hrs}h",
                has_asin,
            )

        console.print(table)
        console.print(f"\n[dim]Showing {len(series_list)} series[/dim]")


def test_audible_search(query: str, author: str | None = None):
    """Test Audible catalog search."""
    _, audible_client, _cache = get_clients()

    console.print(f"\n[bold cyan]Audible Search: '{query}'[/bold cyan]")
    if author:
        console.print(f"[dim]Author filter: {author}[/dim]")
    console.print()

    with audible_client:
        results = audible_client.search_catalog(
            keywords=query,
            author=author,
            num_results=20,
        )

        table = Table(show_header=True)
        table.add_column("ASIN", style="cyan")
        table.add_column("Title", style="bold")
        table.add_column("Author")
        table.add_column("Series")
        table.add_column("Runtime", justify="right")

        for product in results:
            series_str = ""
            if product.series:
                series_str = f"{product.series[0].title} #{product.series[0].sequence or '?'}"

            runtime = f"{product.runtime_hours}h" if product.runtime_hours else "?"

            table.add_row(
                product.asin,
                product.title[:40],
                (product.primary_author or "?")[:20],
                series_str[:25],
                runtime,
            )

        console.print(table)
        console.print(f"\n[dim]Found {len(results)} results[/dim]")


def analyze_single_series(library_id: str, series_name: str):
    """Analyze a single series."""
    abs_client, audible_client, cache = get_clients()

    console.print(f"\n[bold cyan]Analyzing Series: '{series_name}'[/bold cyan]\n")

    with abs_client:
        matcher = SeriesMatcher(abs_client, audible_client, cache)

        # Find the series
        all_series = matcher.get_abs_series(library_id)
        target_series = None

        for series in all_series:
            if fuzz.ratio(series.name.lower(), series_name.lower()) >= 80:
                target_series = series
                break

        if not target_series:
            console.print(f"[red]Series '{series_name}' not found[/red]")
            return

        console.print(f"[green]Found series: {target_series.name}[/green]")
        console.print(f"Books in ABS: {target_series.book_count}\n")

        # Show ABS books
        console.print("[bold]ABS Books:[/bold]")
        for book in target_series.books:
            seq = f"#{book.sequence}" if book.sequence else ""
            asin = f"[cyan]{book.asin}[/cyan]" if book.asin else "[dim]no ASIN[/dim]"
            console.print(f"  {seq:5} {book.title[:50]:50} {asin}")

        console.print()

        # Compare with Audible
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Searching Audible catalog...", total=None)
            result = matcher.compare_series(target_series)

        # Show results
        console.print(f"\n[bold]Comparison Results:[/bold]")
        console.print(f"  Audible books found: {result.audible_book_count}")
        console.print(f"  Matched books: {result.matched_count}")
        console.print(f"  Missing books: {result.missing_count}")
        console.print(f"  Completion: {result.completion_percentage}%")

        if result.missing_books:
            console.print(f"\n[bold yellow]Missing Books ({len(result.missing_books)}):[/bold yellow]")

            table = Table(show_header=True, box=None)
            table.add_column("Seq", style="dim")
            table.add_column("Title", style="bold")
            table.add_column("Author")
            table.add_column("Duration")
            table.add_column("ASIN", style="cyan")

            for book in sorted(result.missing_books, key=lambda x: x.sequence or "999"):
                table.add_row(
                    f"#{book.sequence}" if book.sequence else "?",
                    book.title[:40],
                    (book.author_name or "?")[:20],
                    f"{book.runtime_hours or '?'}h",
                    book.asin,
                )

            console.print(table)
        else:
            console.print(f"\n[bold green]✓ Series is complete![/bold green]")


def full_library_analysis(library_id: str, max_series: int = 0, output_file: str | None = None):
    """Run full library series analysis."""
    abs_client, audible_client, cache = get_clients()

    console.print(f"\n[bold cyan]Full Library Series Analysis[/bold cyan]\n")

    with abs_client:
        # Get library name
        lib = abs_client.get_library(library_id)
        console.print(f"Library: [bold]{lib.name}[/bold]")

        matcher = SeriesMatcher(abs_client, audible_client, cache)

        # Run analysis with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing series...", total=None)

            def update_progress(current: int, total: int, name: str) -> None:
                progress.update(task, completed=current, total=total, description=f"Analyzing: {name[:30]}")

            report = matcher.analyze_library(
                library_id=library_id,
                library_name=lib.name,
                max_series=max_series,
                progress_callback=update_progress,
            )

        # Summary
        console.print(f"\n[bold]Analysis Summary:[/bold]")
        console.print(f"  Total series analyzed: {report.total_series}")
        console.print(f"  Series with Audible match: {report.series_matched}")
        console.print(f"  Complete series: {report.series_complete}")
        console.print(f"  Total missing books: {report.total_missing_books}")
        console.print(f"  Total missing hours: {report.total_missing_hours:.1f}h")
        console.print(f"  Completion rate: {report.completion_rate}%")

        # Top incomplete series
        if report.incomplete_series:
            console.print(f"\n[bold yellow]Incomplete Series ({len(report.incomplete_series)}):[/bold yellow]")

            table = Table(show_header=True)
            table.add_column("Series", style="bold")
            table.add_column("Owned", justify="right")
            table.add_column("Missing", justify="right", style="yellow")
            table.add_column("Completion", justify="right")

            # Sort by missing count
            sorted_incomplete = sorted(
                report.incomplete_series,
                key=lambda x: x.missing_count,
                reverse=True,
            )[:20]

            for result in sorted_incomplete:
                table.add_row(
                    result.series_match.abs_series.name[:40],
                    str(result.matched_count),
                    str(result.missing_count),
                    f"{result.completion_percentage}%",
                )

            console.print(table)

        # Save report
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert to JSON-serializable format
            report_dict = {
                "library_id": report.library_id,
                "library_name": report.library_name,
                "analyzed_at": report.analyzed_at.isoformat(),
                "summary": {
                    "total_series": report.total_series,
                    "series_matched": report.series_matched,
                    "series_complete": report.series_complete,
                    "total_missing_books": report.total_missing_books,
                    "total_missing_hours": report.total_missing_hours,
                    "completion_rate": report.completion_rate,
                },
                "incomplete_series": [
                    {
                        "name": r.series_match.abs_series.name,
                        "abs_books": r.abs_book_count,
                        "audible_books": r.audible_book_count,
                        "matched": r.matched_count,
                        "missing": r.missing_count,
                        "completion": r.completion_percentage,
                        "missing_books": [
                            {
                                "asin": b.asin,
                                "title": b.title,
                                "sequence": b.sequence,
                                "runtime_hours": b.runtime_hours,
                            }
                            for b in r.missing_books
                        ],
                    }
                    for r in report.incomplete_series
                ],
            }

            with open(output_path, "w") as f:
                json.dump(report_dict, f, indent=2)

            console.print(f"\n[green]Report saved to: {output_path}[/green]")


def save_series_sample(library_id: str, output_file: str = "data/samples/abs_series_sample.json"):
    """Save raw series data as a golden sample."""
    abs_client, _, _ = get_clients()

    with abs_client:
        raw_series = abs_client.get_library_series(library_id, limit=10)

        sample_data = {
            "_meta": {
                "name": "library_series",
                "source": "abs",
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "library_id": library_id,
            },
            "data": raw_series,
        }

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(sample_data, f, indent=2)

        console.print(f"[green]Sample saved to: {output_path}[/green]")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Series matching exploration")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command")

    # List libraries
    subparsers.add_parser("libraries", help="List available libraries")

    # List series
    list_parser = subparsers.add_parser("list-series", help="List series in library")
    list_parser.add_argument("library_id", help="Library ID")
    list_parser.add_argument("--limit", type=int, default=20, help="Max series to show")

    # Search Audible
    search_parser = subparsers.add_parser("search", help="Test Audible search")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--author", help="Author filter")

    # Analyze single series
    analyze_parser = subparsers.add_parser("analyze", help="Analyze single series")
    analyze_parser.add_argument("library_id", help="Library ID")
    analyze_parser.add_argument("series_name", help="Series name")

    # Full analysis
    full_parser = subparsers.add_parser("full", help="Full library analysis")
    full_parser.add_argument("library_id", help="Library ID")
    full_parser.add_argument("--max-series", type=int, default=0, help="Max series to analyze")
    full_parser.add_argument("--output", "-o", help="Output JSON file")

    # Save sample
    sample_parser = subparsers.add_parser("save-sample", help="Save series sample data")
    sample_parser.add_argument("library_id", help="Library ID")
    sample_parser.add_argument("--output", "-o", default="data/samples/abs_series_sample.json")

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    try:
        if args.command == "libraries":
            list_libraries()
        elif args.command == "list-series":
            list_series(args.library_id, args.limit)
        elif args.command == "search":
            test_audible_search(args.query, args.author)
        elif args.command == "analyze":
            analyze_single_series(args.library_id, args.series_name)
        elif args.command == "full":
            full_library_analysis(args.library_id, args.max_series, args.output)
        elif args.command == "save-sample":
            save_series_sample(args.library_id, args.output)
        else:
            parser.print_help()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if args.debug:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
