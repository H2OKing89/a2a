"""
Audio Quality CLI commands.

Commands for analyzing and managing audiobook quality:
- scan: Scan library for quality analysis
- low: List low quality audiobooks
- item: Analyze quality of a specific item
- upgrades: Find upgrade candidates with Audible pricing
"""

import asyncio
import json
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Any

import typer
from rich.box import ROUNDED
from rich.text import Text

from src.audible import AsyncAudibleClient, AsyncAudibleEnrichmentService, AudibleEnrichmentService
from src.cli.common import Icons, console, get_abs_client, get_audible_client, get_cache, get_default_library_id, ui
from src.config import get_settings
from src.quality import QualityAnalyzer, QualityReport, QualityTier
from src.utils.ui import BarColumn, Panel, Progress, SpinnerColumn, Table, TaskProgressColumn, TextColumn

logger = logging.getLogger(__name__)


# =============================================================================
# Upgrade Filtering Logic
# =============================================================================


class UpgradeTier(str, Enum):
    """Upgrade significance tiers."""

    NOISE = "noise"  # Not worth showing (Δkbps < 8 or Δ% < 10%)
    MINOR = "minor"  # Passes hard gate but fails band threshold
    WORTH = "worth"  # Passes band threshold - meaningful upgrade
    BIG = "big"  # Δkbps ≥ 24 OR Δ% ≥ 25% - definitely show


def _get_band_requirements(cur_kbps: float) -> tuple[int, float]:
    """
    Get (min_delta_kbps, min_delta_pct) thresholds for current bitrate band.

    Lower bitrates have more lenient thresholds since small improvements
    are more noticeable. Higher bitrates need bigger jumps to matter.
    """
    if cur_kbps < 48:
        return 16, 0.25  # Very low: need big jump or 25%
    if cur_kbps < 80:
        return 12, 0.20  # Low: 12 kbps or 20%
    if cur_kbps < 110:
        return 16, 0.15  # Medium: 16 kbps or 15%
    if cur_kbps < 128:
        return 18, 0.15  # Good: 18 kbps or 15%
    return 24, 0.20  # High: need 24 kbps or 20%


# Cost multipliers - lower = more lenient, higher = stricter
COST_MULTIPLIERS = {
    "OWNED": 0.7,  # Free redownload - be lenient
    "FREE": 0.5,  # Plus Catalog - very lenient
    "MONTHLY_DEAL": 0.9,  # Good deal - slightly lenient
    "GOOD_DEAL": 0.95,  # Under $9 - nearly normal
    "CREDIT": 1.2,  # Credits are precious - be strict
    "EXPENSIVE": 1.4,  # Full price - very strict
    "N/A": 1.3,  # Unknown - strict
}


def classify_upgrade(
    cur_kbps: float,
    best_kbps: float | None,
    best_codec: str | None,
    recommendation: str | None,
) -> tuple[UpgradeTier, int, float]:
    """
    Classify an upgrade into tiers and return (tier, delta_kbps, delta_pct).

    Args:
        cur_kbps: Current file bitrate
        best_kbps: Best available bitrate on Audible (None if unknown)
        best_codec: Best available codec on Audible (e.g., "AAC-LC", "HE-AAC v2")
        recommendation: Acquisition recommendation (OWNED, CREDIT, etc.)

    Returns:
        (UpgradeTier, delta_kbps, delta_percent)
    """
    # No Audible data available
    if best_kbps is None:
        return UpgradeTier.NOISE, 0, 0.0

    delta = int(best_kbps - cur_kbps)
    pct = delta / max(cur_kbps, 1)

    # Sanity check: "upgrade" must actually be higher bitrate
    if delta <= 0:
        return UpgradeTier.NOISE, delta, pct

    # Hard noise gate: Δkbps < 8 OR Δ% < 10%
    if delta < 8 or pct < 0.10:
        return UpgradeTier.NOISE, delta, pct

    # Special case: AAC-LC ≤72k ceiling (that's all Audible offers for this title)
    # Only show if current is truly low (≤52 kbps)
    if best_codec == "AAC-LC" and best_kbps <= 72 and cur_kbps >= 52:
        return UpgradeTier.NOISE, delta, pct

    # Check for "Big" upgrade first (always show regardless of cost)
    if delta >= 24 or pct >= 0.25:
        return UpgradeTier.BIG, delta, pct

    # Get band-based requirements
    req_delta, req_pct = _get_band_requirements(cur_kbps)

    # Apply cost multiplier
    rec_key = "N/A"
    if recommendation:
        rec_simple = recommendation.split(" (")[0]  # Strip price details
        if rec_simple in COST_MULTIPLIERS:
            rec_key = rec_simple
        elif rec_simple.startswith("FREE"):
            rec_key = "FREE"
        elif rec_simple.startswith("MONTHLY_DEAL"):
            rec_key = "MONTHLY_DEAL"
        elif rec_simple.startswith("GOOD_DEAL"):
            rec_key = "GOOD_DEAL"

    mult = COST_MULTIPLIERS.get(rec_key, 1.0)
    adj_req_delta = int(round(req_delta * mult))
    adj_req_pct = req_pct * mult

    # Check if it meets adjusted thresholds
    if delta >= adj_req_delta or pct >= adj_req_pct:
        return UpgradeTier.WORTH, delta, pct

    # Passes hard gate but not band threshold
    return UpgradeTier.MINOR, delta, pct


def should_show_upgrade(
    cur_kbps: float,
    best_kbps: float | None,
    best_codec: str | None,
    recommendation: str | None,
    show_minor: bool = False,
) -> bool:
    """
    Determine if an upgrade should be shown in the output.

    Args:
        cur_kbps: Current file bitrate
        best_kbps: Best available bitrate on Audible
        best_codec: Best available codec on Audible
        recommendation: Acquisition recommendation
        show_minor: If True, also show MINOR tier upgrades

    Returns:
        True if upgrade should be displayed
    """
    tier, _, _ = classify_upgrade(cur_kbps, best_kbps, best_codec, recommendation)

    if tier == UpgradeTier.NOISE:
        return False
    if tier == UpgradeTier.MINOR:
        return show_minor
    # WORTH and BIG always shown
    return True


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
    fast: bool = typer.Option(False, "--fast", "-f", help="Skip license requests (faster but less accurate bitrate)"),
    show_minor: bool = typer.Option(False, "--show-minor", help="Include minor upgrades (8-16 kbps improvement)"),
    show_all: bool = typer.Option(False, "--show-all", "-a", help="Show ALL candidates (disable smart filtering)"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Export to JSON file"),
):
    """
    Find upgrade candidates enriched with Audible pricing data.

    Shows low quality items along with:
    - Whether you own it on Audible
    - Plus Catalog availability (FREE!)
    - Monthly deals (up to 80% off!)
    - Current pricing and discounts
    - ACTUAL best audio quality via license requests (unless --fast)
    - Buy recommendation (FREE, MONTHLY_DEAL, GOOD_DEAL, CREDIT, etc)
    """
    start_time = time.time()

    try:
        with get_abs_client() as abs_client:
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

            # Phase 2: Enrich with Audible data using async for actual quality discovery
            if fast:
                console.print(
                    f"\nPhase 2: Fetching Audible pricing for {len(upgrade_candidates)} items (fast mode)...\n"
                )
            else:
                console.print(
                    f"\nPhase 2: Fetching Audible pricing & actual quality for {len(upgrade_candidates)} items...\n"
                )

            asins = [c.asin for c in upgrade_candidates if c.asin]

            # Run async enrichment
            enrichments = asyncio.run(
                _async_enrich_upgrades(
                    asins=asins,
                    cache=cache,
                    discover_quality=not fast,
                    console=console,
                )
            )

            phase2_time = time.time() - phase1_time - start_time

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
                    # Use actual_best_bitrate which comes from metadata endpoint
                    candidate.audible_best_bitrate = enrichment.actual_best_bitrate
                    candidate.audible_best_codec = enrichment.actual_best_format
                    candidate.acquisition_recommendation = enrichment.acquisition_recommendation
                    candidate.audible_url = enrichment.audible_url
                    candidate.cover_image_url = enrichment.cover_image_url
                    # Boost priority based on acquisition opportunity
                    candidate.upgrade_priority = int(candidate.upgrade_priority * enrichment.priority_boost)

            # Smart upgrade filtering (unless --show-all)
            total_before_filter = len(upgrade_candidates)
            filtered_out = {"noise": 0, "minor": 0, "no_improvement": 0}

            if not show_all:
                filtered_candidates = []
                for c in upgrade_candidates:
                    # Skip items with no Audible quality data
                    if not c.audible_best_bitrate:
                        filtered_candidates.append(c)  # Keep - can't evaluate
                        continue

                    # Skip if Audible quality is same or worse
                    if c.audible_best_bitrate <= c.bitrate_kbps:
                        filtered_out["no_improvement"] += 1
                        continue

                    # Apply smart filtering
                    if should_show_upgrade(
                        cur_kbps=c.bitrate_kbps,
                        best_kbps=c.audible_best_bitrate,
                        best_codec=c.audible_best_codec,
                        recommendation=c.acquisition_recommendation or "",
                        show_minor=show_minor,
                    ):
                        filtered_candidates.append(c)
                    else:
                        tier, _, _ = classify_upgrade(
                            c.bitrate_kbps,
                            c.audible_best_bitrate,
                            c.audible_best_codec,
                            c.acquisition_recommendation or "",
                        )
                        if tier == UpgradeTier.NOISE:
                            filtered_out["noise"] += 1
                        else:
                            filtered_out["minor"] += 1

                upgrade_candidates = filtered_candidates

                # Show filtering summary
                total_filtered = sum(filtered_out.values())
                if total_filtered > 0:
                    filter_details = []
                    if filtered_out["noise"]:
                        filter_details.append(f"{filtered_out['noise']} noise")
                    if filtered_out["minor"]:
                        filter_details.append(f"{filtered_out['minor']} minor")
                    if filtered_out["no_improvement"]:
                        filter_details.append(f"{filtered_out['no_improvement']} no-improvement")
                    console.print(
                        f"[dim]Smart filter: Hiding {total_filtered} low-value upgrades "
                        f"({', '.join(filter_details)}). Use --show-all to see all.[/dim]"
                    )

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
            table.add_column("Current", justify="right", style="dim")
            table.add_column("Best Avail", justify="center")
            table.add_column("Δ", justify="right", style="green")
            table.add_column("Title", max_width=30)
            table.add_column("Author", max_width=18)
            table.add_column("ASIN", style="dim")
            table.add_column("Recommendation", style="bold")
            table.add_column("Price")

            for item in upgrade_candidates[:limit]:
                # Determine recommendation color and simplify text
                rec = item.acquisition_recommendation or "N/A"
                # Strip price info from recommendation (e.g., "MONTHLY_DEAL ($7.99, 87% off)" -> "MONTHLY_DEAL")
                rec_simple = rec.split(" (")[0] if " (" in rec else rec
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

                # Author display (first author only)
                author_display = item.author.split(",")[0].strip()[:20] if item.author else "-"

                # Current quality display (codec + bitrate)
                # Map codec names to short display names
                codec_map = {
                    "aac": "AAC",
                    "mp3": "MP3",
                    "opus": "Opus",
                    "flac": "FLAC",
                    "eac3": "Atmos",
                    "ac3": "AC3",
                }
                cur_codec = codec_map.get((item.codec or "").lower(), item.codec or "")
                current_display = f"{cur_codec} {item.bitrate_kbps:.0f}k" if cur_codec else f"{item.bitrate_kbps:.0f}k"

                # Best available quality display
                # Show Atmos badge if available, otherwise show codec + bitrate from Audible
                if item.has_atmos_upgrade:
                    quality_display = "[magenta]🎧 Atmos[/magenta]"
                elif item.audible_best_bitrate and item.audible_best_codec:
                    # Show codec name + bitrate (e.g., "HE-AAC 128k")
                    codec_short = item.audible_best_codec.replace(" v2", "")
                    quality_display = f"{codec_short} {item.audible_best_bitrate}k"
                elif item.audible_best_bitrate:
                    quality_display = f"{item.audible_best_bitrate}k"
                else:
                    quality_display = "-"

                # Delta display (improvement)
                if item.audible_best_bitrate and item.audible_best_bitrate > item.bitrate_kbps:
                    delta = item.audible_best_bitrate - item.bitrate_kbps
                    delta_display = f"+{delta:.0f}"
                else:
                    delta_display = "-"

                table.add_row(
                    current_display,
                    quality_display,
                    delta_display,
                    item.title[:30],
                    author_display,
                    item.asin or "-",
                    f"{rec_style}{rec_simple}[/]" if rec_style else rec_simple,
                    price_display,
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


async def _async_enrich_upgrades(
    asins: list[str],
    cache,
    discover_quality: bool = True,
    console=None,
):
    """
    Async helper to enrich ASINs with actual quality via license requests.

    Args:
        asins: List of ASINs to enrich
        cache: SQLiteCache instance
        discover_quality: Whether to make license requests for actual quality
        console: Rich console for output

    Returns:
        Dict mapping ASIN to AudibleEnrichment
    """
    settings = get_settings()
    auth_file = Path(settings.audible.auth_file)
    auth_password = settings.audible.auth_password

    phase2_start = time.time()
    enrichments = {}

    async with AsyncAudibleClient.from_file(
        auth_file,
        cache=cache,
        auth_password=auth_password,
        request_delay=settings.audible.rate_limit_delay,
        max_concurrent_requests=5,
    ) as client:
        # Progress tracking with callback
        total = len(asins)
        progress_ctx = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[cyan]{task.fields[elapsed]}[/cyan]"),
            console=console,
        )

        with progress_ctx as progress:
            task = progress.add_task("Enriching with quality discovery...", total=total, elapsed="")

            def update_progress(completed: int, total_items: int, message: str) -> None:
                elapsed = time.time() - phase2_start
                progress.update(task, completed=completed, elapsed=f"{elapsed:.1f}s")

            service = AsyncAudibleEnrichmentService(client, cache=cache, progress_callback=update_progress)

            # Process with concurrent enrichment - progress updates live
            enrichments = await service.enrich_batch_with_quality(
                asins,
                use_cache=True,
                discover_quality=discover_quality,
                max_concurrent=5,  # Limit concurrent API calls
            )

        stats = service.stats
        if console:
            console.print(
                f"[dim]Phase 2 completed in {time.time() - phase2_start:.1f}s "
                f"(cache hits: {stats['cache_hits']}, API calls: {stats['api_calls']}, "
                f"quality discoveries: {stats['quality_discoveries']})[/dim]"
            )

    return enrichments
