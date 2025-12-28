#!/usr/bin/env python3
"""
Test script to check Audible API for bitrate, codecs, and pricing.
Beautiful terminal output with Rich library.

Run from: scripts/ directory or project root
  cd scripts && python test_audible_codecs.py
  python scripts/test_audible_codecs.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path so we can import src modules when running from scripts/
script_dir = Path(__file__).parent
project_root = script_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from src.audible import AsyncAudibleClient

console = Console()


def format_runtime(minutes: int) -> str:
    """Convert minutes to human-readable format like '19h 26m'."""
    if not minutes:
        return "Unknown"
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024**3:
        return f"{size_bytes / (1024**2):.1f} MB"
    return f"{size_bytes / (1024**3):.2f} GB"


def create_header() -> Panel:
    """Create a beautiful header panel."""
    title = Text()
    title.append("🎧 ", style="bold")
    title.append("Audible", style="bold cyan")
    title.append(" Audiobook Quality & Codec Checker", style="bold white")

    subtitle = Text("Analyze audio formats, bitrates, and pricing", style="dim italic")

    content = Group(
        Align.center(title),
        Align.center(subtitle),
    )

    return Panel(
        content,
        box=box.DOUBLE_EDGE,
        border_style="cyan",
        padding=(1, 2),
    )


def create_book_header(title: str, asin: str) -> Panel:
    """Create a panel for the book title."""
    header = Text()
    header.append("📖 ", style="bold")
    header.append(title, style="bold white")
    header.append(f"\n", style="")
    header.append(f"ASIN: {asin}", style="dim cyan")

    return Panel(
        header,
        box=box.ROUNDED,
        border_style="blue",
        padding=(0, 2),
    )


def create_metadata_panel(authors: list, narrators: list, runtime: int, format_type: str) -> Panel:
    """Create a panel showing book metadata."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="dim")
    table.add_column("Value", style="white")

    table.add_row("👤 Authors", ", ".join(authors) if authors else "Unknown")

    if len(narrators) > 4:
        narrator_text = ", ".join(narrators[:4]) + f" [dim](+{len(narrators)-4} more)[/dim]"
    else:
        narrator_text = ", ".join(narrators) if narrators else "Unknown"
    table.add_row("🎙️ Narrators", narrator_text)

    table.add_row("⏱️ Runtime", format_runtime(runtime))
    table.add_row("📚 Format", format_type or "Unknown")

    return Panel(
        table,
        title="[bold cyan]Book Details[/bold cyan]",
        border_style="cyan",
        box=box.ROUNDED,
    )


def create_pricing_panel(price_data: dict) -> Panel:
    """Create a beautiful pricing panel."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Type", style="dim")
    table.add_column("Price", justify="right")

    if "list_price" in price_data:
        list_info = price_data["list_price"]
        if isinstance(list_info, dict):
            price = list_info.get("base", 0)
            table.add_row("List Price", f"[white]${price:.2f}[/white]")

    if "lowest_price" in price_data:
        lowest_info = price_data["lowest_price"]
        if isinstance(lowest_info, dict):
            price = lowest_info.get("base", 0)
            table.add_row("Member Price", f"[green]${price:.2f}[/green]")

    if "credit_price" in price_data:
        credit = price_data["credit_price"]
        if isinstance(credit, (int, float)):
            table.add_row("Credits", f"[yellow]{int(credit)} credit[/yellow]")

    return Panel(
        table,
        title="[bold green]💰 Pricing[/bold green]",
        border_style="green",
        box=box.ROUNDED,
    )


def create_formats_table(formats: list) -> Table:
    """Create a beautiful table of available formats."""
    table = Table(
        title="[bold magenta]🎵 Available Audio Formats[/bold magenta]",
        box=box.ROUNDED,
        border_style="magenta",
        header_style="bold magenta",
        row_styles=["", "dim"],
        padding=(0, 1),
    )

    table.add_column("", justify="center", width=3)
    table.add_column("Format", style="cyan", min_width=12)
    table.add_column("Bitrate", justify="right", style="yellow")
    table.add_column("Size", justify="right", style="green")
    table.add_column("DRM", style="dim")
    table.add_column("Quality", justify="center")

    for fmt in formats:
        is_atmos = fmt["is_atmos"]
        icon = "⭐" if is_atmos else ""

        # Quality indicator bar
        bitrate = fmt["bitrate"]
        if bitrate >= 700:
            quality = "[bold green]████████[/bold green] Excellent"
        elif bitrate >= 200:
            quality = "[green]██████[/green][dim]██[/dim] Very Good"
        elif bitrate >= 128:
            quality = "[yellow]████[/yellow][dim]████[/dim] Good"
        else:
            quality = "[red]██[/red][dim]██████[/dim] Low"

        name_style = "bold cyan" if is_atmos else "cyan"

        table.add_row(
            icon,
            f"[{name_style}]{fmt['name']}[/{name_style}]",
            f"{fmt['bitrate']:.0f} kbps",
            format_size(fmt["size"]),
            fmt["drm"],
            quality,
        )

    return table


def create_summary_panel(formats: list, asin: str) -> Panel:
    """Create a summary panel with recommendations."""
    if not formats:
        return Panel(
            "[red]No formats could be retrieved[/red]",
            title="[bold]📊 Summary[/bold]",
            border_style="red",
        )

    best_quality = max(formats, key=lambda x: x["bitrate"])
    smallest = min(formats, key=lambda x: x["size"])
    has_atmos = any(f["is_atmos"] for f in formats)

    content = []

    # Format count
    count_text = Text()
    count_text.append(f"  📦 ", style="bold")
    count_text.append(f"{len(formats)} format(s) available", style="white")
    content.append(count_text)

    # Atmos highlight
    if has_atmos:
        atmos_format = next(f for f in formats if f["is_atmos"])
        atmos_text = Text()
        atmos_text.append("  ⭐ ", style="bold yellow")
        atmos_text.append("Dolby Atmos available! ", style="bold yellow")
        atmos_text.append(f"({format_size(atmos_format['size'])} @ {atmos_format['bitrate']:.0f} kbps)", style="dim")
        content.append(atmos_text)

    # Best quality
    best_text = Text()
    best_text.append("  🏆 ", style="bold")
    best_text.append("Best quality: ", style="dim")
    best_text.append(f"{best_quality['name']}", style="bold cyan")
    best_text.append(f" @ {best_quality['bitrate']:.0f} kbps", style="green")
    content.append(best_text)

    # Smallest
    small_text = Text()
    small_text.append("  💾 ", style="bold")
    small_text.append("Smallest size: ", style="dim")
    small_text.append(f"{smallest['name']}", style="bold cyan")
    small_text.append(f" @ {format_size(smallest['size'])}", style="green")
    content.append(small_text)

    # Recommendation
    content.append(Text())  # spacer
    rec_text = Text()
    rec_text.append("  💡 ", style="bold")
    if has_atmos:
        rec_text.append("Recommendation: ", style="dim")
        rec_text.append("Get the Dolby Atmos version for the best experience!", style="italic green")
    else:
        rec_text.append("Recommendation: ", style="dim")
        rec_text.append(f"Use {best_quality['name']} for optimal quality.", style="italic")
    content.append(rec_text)

    return Panel(
        Group(*content),
        title="[bold white]📊 Analysis Summary[/bold white]",
        border_style="white",
        box=box.DOUBLE,
        padding=(1, 2),
    )


async def analyze_audiobook(client: AsyncAudibleClient, asin: str, progress: Progress, task) -> None:
    """Analyze a single audiobook and display results."""

    progress.update(task, description=f"[cyan]Fetching catalog info for {asin}...")

    # Get catalog product
    response = await client._request(
        "GET",
        f"catalog/products/{asin}",
        response_groups="contributors,media,price,product_attrs,product_desc,product_details,product_extended_attrs,rating,series,category_ladders,reviews,customer_rights",
    )

    product_data = response.get("product", response)
    from src.audible.models import AudibleCatalogProduct

    product = AudibleCatalogProduct.model_validate(product_data)

    progress.update(task, advance=25)

    if not product:
        console.print("[red]Failed to fetch product info[/red]")
        return

    # Extract info
    authors = [a.name for a in product.authors] if product.authors else []
    narrators = [n.name for n in product.narrators] if product.narrators else []

    # Test codec availability
    progress.update(task, description=f"[cyan]Testing audio formats...")

    # Import shared license test configs from library
    from src.audible.models import LICENSE_TEST_CONFIGS

    available_formats = []

    for _, config in enumerate(LICENSE_TEST_CONFIGS):
        progress.update(task, description=f"[cyan]Testing {config['name']}...")

        try:
            license_response = await client._request(
                "POST",
                f"1.0/content/{asin}/licenserequest",
                json={
                    "quality": "High",
                    "response_groups": "chapter_info,content_reference",
                    "consumption_type": "Download",
                    "spatial": config.get("spatial", False),
                    "supported_media_features": {"codecs": config["codecs"], "drm_types": config["drm_types"]},
                },
            )

            if "content_license" in license_response:
                license_info = license_response["content_license"]
                content_meta = license_info.get("content_metadata", {})
                content_ref = content_meta.get("content_reference", {})
                chapter_info = content_meta.get("chapter_info", {})

                actual_codec = content_ref.get("codec", config["codecs"][0])
                content_size = content_ref.get("content_size_in_bytes", 0)
                drm_type = license_info.get("drm_type", config["drm_types"][0])
                runtime_ms = chapter_info.get("runtime_length_ms", 0)

                bitrate = 0
                if runtime_ms > 0:
                    bitrate = (content_size * 8) / (runtime_ms / 1000) / 1000

                available_formats.append(
                    {
                        "codec": actual_codec,
                        "name": config["name"],
                        "size": content_size,
                        "bitrate": bitrate,
                        "drm": drm_type,
                        "is_atmos": actual_codec in ["ec+3", "ac-4"],
                    }
                )
        except Exception:
            pass

        progress.update(task, advance=15)

    progress.update(task, description="[green]Complete!")
    progress.update(task, advance=100 - progress.tasks[task].completed)

    # Display results
    console.print()
    console.print(create_book_header(product.title, asin))
    console.print()

    # Side by side: metadata and pricing
    metadata_panel = create_metadata_panel(authors, narrators, product.runtime_length_min, product.format_type)
    pricing_panel = create_pricing_panel(product.price) if product.price else Panel("[dim]No pricing info[/dim]")

    console.print(Columns([metadata_panel, pricing_panel], equal=True, expand=True))
    console.print()

    # Formats table
    if available_formats:
        console.print(create_formats_table(available_formats))
    else:
        console.print(Panel("[red]No audio formats could be retrieved[/red]", border_style="red"))

    console.print()
    console.print(create_summary_panel(available_formats, asin))
    console.print()


async def main():
    """Main entry point."""
    # Support running from scripts/ or project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Load config for auth file and password
    from src.config import get_settings

    settings = get_settings()
    auth_password = settings.audible.auth_password

    # Resolve auth file path (may be relative to project_root)
    auth_file = Path(settings.audible.auth_file)
    if not auth_file.is_absolute():
        auth_file = project_root / auth_file

    if not auth_file.exists():
        console.print(
            Panel(
                f"[red]Auth file not found: {auth_file}[/red]\n" "[dim]Please run authentication first.[/dim]",
                title="[red]Error[/red]",
                border_style="red",
            )
        )
        return

    asins = [
        "B0DM2PBNPZ",  # Test ASIN
    ]

    console.print()
    console.print(create_header())
    console.print()

    async with AsyncAudibleClient.from_file(auth_file, auth_password=auth_password) as client:
        for asin in asins:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=30),
                TaskProgressColumn(),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"[cyan]Analyzing {asin}...", total=100)
                await analyze_audiobook(client, asin, progress, task)

            console.print(Rule(style="dim"))

    # Footer
    footer = Text()
    footer.append("\n✅ ", style="bold green")
    footer.append("Analysis complete! ", style="bold white")
    footer.append("Thank you for using the Audible Quality Checker.", style="dim")
    console.print(Align.center(footer))
    console.print()


if __name__ == "__main__":
    asyncio.run(main())
