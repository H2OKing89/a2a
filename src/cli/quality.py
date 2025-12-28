"""
Audio Quality CLI commands.

Commands for analyzing and managing audiobook quality:
- scan: Scan library for quality analysis
- low: List low quality audiobooks
- item: Analyze quality of a specific item
- upgrades: Find upgrade candidates with Audible pricing
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

import typer
from rich.box import ROUNDED
from rich.text import Text

from src.audible import AudibleEnrichmentService
from src.cli.common import Icons, console, get_abs_client, get_audible_client, get_cache, get_default_library_id, ui
from src.quality import QualityAnalyzer, QualityReport, QualityTier
from src.utils.ui import BarColumn, Panel, Progress, SpinnerColumn, Table, TaskProgressColumn, TextColumn

logger = logging.getLogger(__name__)

# Create Quality sub-app
quality_app = typer.Typer(help="💎 Audio quality analysis commands")


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
    items by tier (Excellent, Better, Good, Low, Poor).
    """
    try:
        with get_abs_client() as client:
            # Get library ID from settings or pick first if not specified
            if not library_id:
                library_id = get_default_library_id()
            if not library_id:
                libraries = client.get_libraries()
                if not libraries:
                    ui.error("No libraries found")
                    raise typer.Exit(1)
                library_id = libraries[0].id

            # Get item count
            items_resp: dict[str, Any] = client._get(f"/libraries/{library_id}/items", params={"limit": 0})
            total_items = len(items_resp.get("results", []))

            if limit > 0:
                total_items = min(limit, total_items)

            ui.header("Quality Scan", subtitle=f"Analyzing {total_items} audiobooks", icon=Icons.QUALITY_HIGH)

            # Create analyzer and report
            analyzer = QualityAnalyzer()
            report = QualityReport()

            # Get item IDs to scan
            items = items_resp.get("results", [])[:total_items] if limit else items_resp.get("results", [])
            item_ids = [item.get("id") for item in items if item.get("id")]

            # Fetch expanded items in parallel with progress
            with ui.progress() as progress:
                task = progress.add_task(f"{Icons.SEARCH} Analyzing quality...", total=len(item_ids))

                def progress_callback(completed: int, _total: int) -> None:
                    progress.update(task, completed=completed)

                # batch_get_items_expanded uses parallel requests + caching
                expanded_items = client.batch_get_items_expanded(
                    item_ids,
                    use_cache=True,
                    max_workers=20,  # Parallel requests to local server
                    progress_callback=progress_callback,
                )

                # Analyze each item
                for full_item in expanded_items:
                    if full_item:
                        try:
                            quality = analyzer.analyze_item(full_item)
                            report.add_item(quality)
                        except Exception as e:
                            ui.warning("Failed to analyze item", details=str(e))

            report.finalize()

            # Build summary panel
            summary_text = Text()
            summary_text.append(f"\n{Icons.BOOK} Total Items: ", style="bold")
            summary_text.append(f"{report.total_items}\n", style="accent")

            summary_text.append(f"{Icons.DATABASE} Total Size: ", style="bold")
            summary_text.append(f"{report.total_size_gb:.2f} GB\n", style="size")

            summary_text.append(f"{Icons.CLOCK} Total Duration: ", style="bold")
            summary_text.append(f"{report.total_duration_hours:.1f} hours\n", style="duration")

            summary_text.append(f"\n{Icons.MUSIC} Bitrate Range: ", style="bold")
            summary_text.append(
                f"{report.min_bitrate_kbps:.0f} - {report.max_bitrate_kbps:.0f} kbps\n", style="bitrate"
            )

            summary_text.append(f"{Icons.MUSIC} Average Bitrate: ", style="bold")
            summary_text.append(f"{report.avg_bitrate_kbps:.0f} kbps\n", style="bitrate")

            console.print(
                Panel(
                    summary_text,
                    title=f"{Icons.SUCCESS} Quality Scan Complete",
                    border_style="success",
                    box=ROUNDED,
                )
            )

            # Tier breakdown table with visual bars
            tier_table = ui.create_table(
                title=f"{Icons.QUALITY_HIGH} Quality Tiers",
                box_style=ROUNDED,
            )
            tier_table.add_column("Tier", style="bold")
            tier_table.add_column("Count", justify="right")
            tier_table.add_column("Distribution", min_width=25)
            tier_table.add_column("%", justify="right")

            tier_order = ["Excellent", "Better", "Good", "Low", "Poor"]
            tier_styles = {
                "Excellent": ("tier.excellent", Icons.QUALITY_HIGH),
                "Better": ("tier.better", Icons.QUALITY_GOOD),
                "Good": ("tier.good", Icons.QUALITY_OK),
                "Low": ("tier.low", Icons.QUALITY_LOW),
                "Poor": ("tier.poor", Icons.QUALITY_BAD),
            }

            for tier_name in tier_order:
                count = report.tier_counts.get(tier_name, 0)
                pct = (count / report.total_items * 100) if report.total_items else 0
                style, icon = tier_styles.get(tier_name, ("white", ""))

                # Visual distribution bar
                bar_width = int(pct / 5)  # Max 20 chars
                bar = f"[{style}]{'█' * bar_width}[/{style}][dim]{'░' * (20 - bar_width)}[/dim]"

                tier_table.add_row(f"[{style}]{icon} {tier_name}[/{style}]", str(count), bar, f"{pct:.1f}%")

            console.print(tier_table)

            # Format breakdown
            format_table = ui.create_table(
                title=f"{Icons.FILE} Format Distribution",
                box_style=ROUNDED,
            )
            format_table.add_column("Format", style="bold cyan")
            format_table.add_column("Count", justify="right")

            for fmt, count in sorted(report.format_counts.items(), key=lambda x: -x[1]):
                format_table.add_row(fmt, str(count))

            console.print(format_table)

            # Upgrade candidates summary
            if report.upgrade_candidates:
                console.print()
                ui.warning(
                    f"{len(report.upgrade_candidates)} items need upgrades", details="Run 'quality low' to see details."
                )

            # Save report if requested
            if output:
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

    Default threshold is 110 kbps (Good minimum).
    """
    try:
        with get_abs_client() as client:
            # Get library ID from settings or pick first if not specified
            if not library_id:
                library_id = get_default_library_id()
            if not library_id:
                libraries = client.get_libraries()
                if not libraries:
                    ui.error("No libraries found")
                    raise typer.Exit(1)
                library_id = libraries[0].id

            # Get all items
            items_resp: dict[str, Any] = client._get(f"/libraries/{library_id}/items", params={"limit": 0})
            all_items = items_resp.get("results", [])
            item_ids = [item.get("id") for item in all_items if item.get("id")]

            console.print(f"Scanning {len(item_ids)} items for quality < {threshold} kbps...\n")

            analyzer = QualityAnalyzer()
            low_quality_items = []

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Scanning...", total=len(item_ids))

                def progress_callback(completed: int, _total: int) -> None:
                    progress.update(task, completed=completed)

                # Use batch fetch for parallel requests + caching
                expanded_items = client.batch_get_items_expanded(
                    item_ids,
                    use_cache=True,
                    max_workers=20,
                    progress_callback=progress_callback,
                )

                # Analyze each item and filter by threshold
                for full_item in expanded_items:
                    if full_item:
                        try:
                            quality = analyzer.analyze_item(full_item)
                            if quality.bitrate_kbps < threshold:
                                low_quality_items.append(quality)
                        except Exception as e:
                            # Extract item ID for logging
                            item_id = full_item.get("id", "unknown")
                            item_title = full_item.get("media", {}).get("metadata", {}).get("title", "Unknown")
                            logger.exception(
                                "Failed to analyze item %s: %s",
                                item_id,
                                e,
                                extra={"item_id": item_id, "item_title": item_title},
                            )

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
    raw: bool = typer.Option(False, "--raw", "-r", help="Show raw JSON data with syntax highlighting"),
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
                    ui.error("Item not found", details="No libraries available to search")
                    raise typer.Exit(1)

                # Search in first library
                results: dict[str, Any] = client._get(
                    f"/libraries/{libraries[0].id}/search", params={"q": item_id, "limit": 1}
                )
                books = results.get("book", [])
                if not books:
                    ui.error("Item not found", details=f"ID: {item_id}")
                    raise typer.Exit(1)

                item_id = books[0].get("libraryItem", {}).get("id")
                full_item = client._get(f"/items/{item_id}", params={"expanded": 1})

            # Analyze
            analyzer = QualityAnalyzer()
            quality = analyzer.analyze_item(full_item)

            if raw:
                # Show raw quality analysis data with syntax highlighting
                ui.json(quality.model_dump(), title=f"Quality Analysis: {quality.title}")
                return

            # Display results
            tier_color = {
                QualityTier.EXCELLENT: "bright_blue",
                QualityTier.BETTER: "dark_green",
                QualityTier.GOOD: "green",
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
    start_time = time.time()

    try:
        with get_abs_client() as abs_client, get_audible_client() as audible_client:
            cache = get_cache()  # Get shared cache for enrichment

            # Get library ID from settings or pick first if not specified
            if not library_id:
                library_id = get_default_library_id()
            if not library_id:
                libraries = abs_client.get_libraries()
                if not libraries:
                    ui.error("No libraries found")
                    raise typer.Exit(1)
                library_id = libraries[0].id
                ui.info(f"Using library: [bold]{libraries[0].name}[/bold]")

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

                def update_progress(completed: int, _total: int):
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
                        logger.exception(
                            "Failed to enrich ASIN %s: %s",
                            asin,
                            e,
                            extra={"asin": asin, "title": candidate_title},
                        )

                    elapsed = time.time() - phase2_start
                    progress.update(task, advance=1, elapsed=f"{elapsed:.1f}s")

            phase2_time = time.time() - phase2_start
            stats = enrichment_service.stats
            console.print(
                f"[dim]Phase 2 completed in {phase2_time:.1f}s "
                f"(cache hits: {stats['cache_hits']}, API calls: {stats['api_calls']})[/dim]"
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
                ui.info(f"Filtering to good deals (<$9): {len(upgrade_candidates)} items")

            # Sort by priority (highest first)
            upgrade_candidates.sort(key=lambda x: x.upgrade_priority, reverse=True)

            if not upgrade_candidates:
                ui.warning("No items match the selected filters")
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
        ui.print_exception()
        raise typer.Exit(1)
