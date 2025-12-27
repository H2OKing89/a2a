"""
Series CLI commands.

Commands for analyzing and tracking series:
- list: List all series in a library
- analyze: Analyze a specific series and find missing books
- report: Generate full series analysis report
"""

import json
import logging
import time
from pathlib import Path

import typer

from src.cli.common import (
    console,
    get_abs_client,
    get_audible_client,
    resolve_library_id,
)
from src.series import MatchConfidence, SeriesComparisonResult, SeriesMatcher
from src.utils.ui import (
    BarColumn,
    Progress,
    SpinnerColumn,
    Table,
    TaskProgressColumn,
    TextColumn,
)

logger = logging.getLogger(__name__)

# Create Series sub-app
series_app = typer.Typer(help="📖 Series tracking and collection management")


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
                    "[dim]Hint: Series are detected from book metadata. "
                    "Make sure your books have series information.[/dim]"
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
            series_name_display = result.series_match.abs_series.name
            match_confidence = result.series_match.confidence
            audible_series = result.series_match.audible_series

            console.print(f"\n[bold cyan]═══ {series_name_display} ═══[/bold cyan]")
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
    library_id = resolve_library_id(library_id)
    start_time = time.time()

    try:
        with get_abs_client() as abs_client, get_audible_client() as audible_client:
            matcher = SeriesMatcher(abs_client=abs_client, audible_client=audible_client)

            console.print("\n[bold]Analyzing library series...[/bold]")

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
                        f"POTENTIAL_DUPES: Library has {r.abs_book_count} books "
                        f"but Audible shows {r.audible_book_count}"
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
            console.print("\n[bold]Summary:[/bold]")
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
