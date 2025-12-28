"""
Audible CLI commands.

Commands for interacting with the Audible API:
- login: Authenticate with Audible
- status: Check connection status
- library: List your library
- item: Show audiobook details
- search: Search the catalog
- export: Export library to JSON
- cache: Manage cache
- wishlist: Manage your wishlist
- stats: Show listening statistics
- recommendations: Get personalized recommendations
- sample: Collect golden samples
"""

import json
from pathlib import Path
from typing import Any

import typer
from rich.box import ROUNDED
from rich.text import Text

from src.audible import (
    AudibleAuthError,
    AudibleBook,
    AudibleClient,
    get_encryption_config,
    is_file_encrypted,
    load_auth,
    save_auth,
)
from src.cli.common import Icons, console, get_audible_client, get_cache, ui
from src.config import get_settings
from src.utils import save_golden_sample
from src.utils.ui import Panel, Table

# Create Audible sub-app
audible_app = typer.Typer(help="🎧 Audible API commands")


@audible_app.command("login")
def audible_login(
    locale: str = typer.Option("us", "--locale", "-l", help="Marketplace locale (us, uk, de, etc.)"),
    external: bool = typer.Option(False, "--external", "-e", help="Use external browser for login"),
    encrypt: bool = typer.Option(True, "--encrypt/--no-encrypt", help="Encrypt credentials (prompts for password)"),
):
    """
    Login to Audible and save credentials.

    First-time setup - will prompt for email/password or open browser.
    By default, credentials are encrypted with a password you provide.
    """
    settings = get_settings()
    auth_file = settings.audible.auth_file

    console.print(f"\n[bold]Audible Login[/bold] (marketplace: {locale})")
    console.print(f"Credentials will be saved to: {auth_file}\n")

    # Get encryption password if encrypting
    auth_password = None
    if encrypt:
        # Check env var first
        auth_password = settings.audible.auth_password
        if not auth_password:
            console.print("[bold]Credential Encryption[/bold]")
            console.print("[muted]Your credentials will be encrypted with a password.[/muted]")
            console.print("[muted]You'll need this password each time you use Audible commands.[/muted]")
            console.print("[muted]Tip: Set AUDIBLE_AUTH_PASSWORD env var to avoid prompts.[/muted]\n")
            auth_password = typer.prompt("Encryption password", hide_input=True)
            confirm = typer.prompt("Confirm password", hide_input=True)
            if auth_password != confirm:
                console.print("[red]✗[/red] Passwords do not match")
                raise typer.Exit(1)
            console.print()

    try:
        if external:
            console.print("[yellow]Opening browser for login...[/yellow]")
            client = AudibleClient.from_login_external(
                locale=locale,
                auth_file=auth_file,
                auth_password=auth_password,
                auth_encryption=settings.audible.auth_encryption,
                auth_kdf_iterations=settings.audible.auth_kdf_iterations,
                cache_dir=settings.paths.cache_dir / "audible" if settings.cache.enabled else None,
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
                auth_password=auth_password,
                auth_encryption=settings.audible.auth_encryption,
                auth_kdf_iterations=settings.audible.auth_kdf_iterations,
                cache_dir=settings.paths.cache_dir / "audible" if settings.cache.enabled else None,
                otp_callback=otp_callback,
                cvf_callback=cvf_callback,
            )

        console.print("\n[green]✓[/green] Login successful!")
        console.print(f"  Marketplace: {client.marketplace}")
        console.print(f"  Credentials saved to: {auth_file}")
        if auth_password:
            console.print("  Encryption: [success]Enabled[/success]")
        else:
            console.print("  Encryption: [warning]Disabled[/warning]")
            console.print("\n[muted]Tip: Run 'audible encrypt' to encrypt your credentials.[/muted]")

    except Exception as e:
        console.print(f"[red]✗[/red] Login failed: {e}")
        raise typer.Exit(1) from e


@audible_app.command("encrypt")
def audible_encrypt(
    force: bool = typer.Option(False, "--force", "-f", help="Re-encrypt even if already encrypted"),
):
    """
    Encrypt existing Audible credentials.

    Encrypts your auth file with AES encryption using a password you provide.
    The password is derived using PBKDF2 with 50,000 iterations for security.

    You can also set AUDIBLE_AUTH_PASSWORD environment variable to avoid prompts.
    """
    settings = get_settings()
    auth_file = settings.audible.auth_file

    ui.header("Audible", subtitle="Encrypt Credentials", icon=Icons.AUDIOBOOK)

    if not auth_file.exists():
        ui.error("Auth file not found", details=f"No credentials at {auth_file}")
        console.print("[muted]Run 'audible login' first.[/muted]")
        raise typer.Exit(1)

    # Check current encryption status
    already_encrypted = is_file_encrypted(auth_file)
    if already_encrypted and not force:
        ui.success("Credentials are already encrypted!")
        console.print("[muted]Use --force to re-encrypt with a new password.[/muted]")
        return

    if already_encrypted:
        console.print("[yellow]Credentials are currently encrypted.[/yellow]")
        console.print("You'll need the current password to re-encrypt.\n")
        current_password = typer.prompt("Current encryption password", hide_input=True)
    else:
        current_password = None
        console.print("[yellow]Credentials are currently stored in plaintext.[/yellow]\n")

    # Get new encryption password
    new_password = settings.audible.auth_password
    if not new_password:
        console.print("[bold]New Encryption Password[/bold]")
        console.print("[muted]Choose a strong password. You'll need it for all Audible commands.[/muted]")
        console.print("[muted]Tip: Set AUDIBLE_AUTH_PASSWORD env var to avoid prompts.[/muted]\n")
        new_password = typer.prompt("New encryption password", hide_input=True)
        confirm = typer.prompt("Confirm password", hide_input=True)
        if new_password != confirm:
            ui.error("Passwords do not match")
            raise typer.Exit(1)

    try:
        with ui.spinner("Encrypting credentials..."):
            # Load existing auth (with current password if encrypted)
            current_enc = get_encryption_config(password=current_password, use_env_password=False)
            auth = load_auth(auth_file, current_enc)

            # Save with new encryption
            new_enc = get_encryption_config(
                password=new_password,
                encryption=settings.audible.auth_encryption,  # type: ignore[arg-type]
                kdf_iterations=settings.audible.auth_kdf_iterations,
                use_env_password=False,
            )
            save_auth(auth, auth_file, new_enc)

        ui.success("Credentials encrypted successfully!")
        console.print(f"  {Icons.FILE} File: {auth_file}")
        console.print(f"  {Icons.SUCCESS} Encryption: [success]Enabled[/success]")
        console.print(f"  {Icons.BULLET} KDF iterations: {settings.audible.auth_kdf_iterations:,}")
        console.print()
        console.print("[muted]Remember your password! Set AUDIBLE_AUTH_PASSWORD to avoid prompts.[/muted]")

    except ValueError as e:
        ui.error(f"Failed to encrypt credentials at {auth_file}", details=str(e))
        raise typer.Exit(1) from e
    except Exception as e:
        ui.error(f"Failed to encrypt credentials at {auth_file}", details=str(e))
        raise typer.Exit(1) from e


@audible_app.command("status")
def audible_status():
    """Check Audible connection status."""
    settings = get_settings()

    ui.header("Audible", subtitle="Connection Status", icon=Icons.AUDIOBOOK)

    console.print(f"  {Icons.FILE} Auth file: [accent]{settings.audible.auth_file}[/accent]")
    console.print(f"  {Icons.LINK} Locale: [accent]{settings.audible.locale}[/accent]")

    if not settings.audible.auth_file.exists():
        ui.warning("Auth file not found", details="Run 'audible login' first")
        raise typer.Exit(1)

    # Check encryption status
    encrypted = is_file_encrypted(settings.audible.auth_file)
    if encrypted:
        console.print(f"  {Icons.SUCCESS} Encryption: [success]Enabled[/success]")
    else:
        console.print(f"  {Icons.WARNING} Encryption: [warning]Disabled[/warning]")
        console.print()
        ui.warning(
            "Auth file is NOT encrypted",
            details="Your credentials are stored in plaintext. Run 'audible encrypt' to encrypt them.",
        )

    try:
        with ui.spinner("Connecting to Audible...") as status, get_audible_client() as client:
            status.update("Verifying library access...")
            items = client.get_library(num_results=1, use_cache=False)
            library_count = len(items)
            cache_stats: dict[str, Any] = client.get_cache_stats()

        ui.success(f"Connected to marketplace: [bold]{client.marketplace}[/bold]")

        console.print()
        ui.subsection(f"{Icons.USER} Account Status")
        console.print(f"    {Icons.BOOK} Library accessible: [success]Yes[/success] ({library_count}+ items)")

        # Cache stats with nice formatting
        if cache_stats.get("enabled"):
            console.print()
            ui.subsection(f"{Icons.CACHE} Cache Status")
            console.print(f"    {Icons.BULLET} Total entries: [accent]{cache_stats.get('total_entries', 0)}[/accent]")
            console.print(f"    {Icons.BULLET} Memory entries: [accent]{cache_stats.get('memory_entries', 0)}[/accent]")
            console.print(f"    {Icons.BULLET} DB size: [size]{cache_stats.get('db_size_mb', 0):.2f} MB[/size]")

    except AudibleAuthError as e:
        ui.error("Auth failed", details=str(e))
        console.print("[muted]Try running 'audible login' to refresh credentials.[/muted]")
        raise typer.Exit(1) from e
    except Exception as e:
        ui.error("Error", details=str(e))
        raise typer.Exit(1) from e


@audible_app.command("library")
def audible_library(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of items to show"),
    sort: str = typer.Option("-PurchaseDate", "--sort", "-s", help="Sort by field"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache"),
):
    """List your Audible library."""
    try:
        with ui.spinner("Fetching Audible library..."), get_audible_client() as client:
            items = client.get_library(
                num_results=limit,
                sort_by=sort,
                use_cache=not no_cache,
            )

        table = ui.create_table(
            title=f"{Icons.AUDIOBOOK} Audible Library ({len(items)} items)",
            box_style=ROUNDED,
        )
        table.add_column("ASIN", style="asin", max_width=12, no_wrap=True)
        table.add_column("Title", style="title", max_width=40)
        table.add_column("Author", style="author", max_width=25)
        table.add_column("Duration", justify="right", style="duration")
        table.add_column("Progress", justify="right")

        for item in items:
            duration = f"{item.runtime_hours:.1f}h" if item.runtime_hours else "-"

            # Progress with visual bar
            if item.percent_complete:
                pct = item.percent_complete
                bar_filled = int(pct / 10)
                bar = f"[green]{'█' * bar_filled}[/green][dim]{'░' * (10 - bar_filled)}[/dim]"
                progress = f"{bar} {pct:.0f}%"
            else:
                progress = "[dim]-[/dim]"

            table.add_row(
                item.asin,
                (item.title or "?")[:40],
                (item.primary_author or "?")[:25],
                duration,
                progress,
            )

        console.print()
        console.print(table)

    except AudibleAuthError as e:
        ui.error("Auth failed", details=str(e))
        raise typer.Exit(1) from e
    except Exception as e:
        ui.error("Error", details=str(e))
        raise typer.Exit(1) from e


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
            if book.category_ladders:
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
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


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
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@audible_app.command("export")
def audible_export(
    output: Path = typer.Option(Path("audible_library.json"), "--output", "-o", help="Output file"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache"),
):
    """Export full Audible library to JSON."""
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
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


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
        raise typer.Exit(1) from e


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
                    if item.overall_rating:
                        stars = "★" * int(item.overall_rating) + "☆" * (5 - int(item.overall_rating))
                        rating = f"{stars[:5]} {item.overall_rating:.1f}"

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
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@audible_app.command("stats")
def audible_stats():
    """Show your Audible listening statistics and account info."""
    try:
        with ui.spinner("Fetching Audible statistics...") as status, get_audible_client() as client:
            stats = client.get_listening_stats()
            status.update("Fetching account info...")
            account = client.get_account_info()

        ui.header("Audible Statistics", icon=Icons.AUDIOBOOK)

        # Listening Stats Panel
        if stats:
            listening_hours = stats.total_listening_time_ms / (1000 * 60 * 60) if stats.total_listening_time_ms else 0

            stats_text = Text()
            stats_text.append(f"\n{Icons.CLOCK} Total Listening Time: ", style="bold")
            stats_text.append(f"{listening_hours:.1f} hours\n", style="duration")

            stats_text.append(f"{Icons.BOOK} Books Listened: ", style="bold")
            stats_text.append(f"{stats.distinct_titles_listened or 0}\n", style="accent")

            stats_text.append(f"{Icons.AUTHOR} Authors Explored: ", style="bold")
            stats_text.append(f"{stats.distinct_authors_listened or 0}\n", style="accent")

            stats_text.append(f"\n{Icons.FIRE} Current Streak: ", style="bold")
            stats_text.append(f"{stats.current_listening_streak or 0} days\n", style="warning")

            stats_text.append(f"{Icons.TROPHY} Longest Streak: ", style="bold")
            stats_text.append(f"{stats.longest_listening_streak or 0} days\n", style="warning")

            console.print(
                Panel(
                    stats_text,
                    title="📊 Listening Activity",
                    border_style="cyan",
                    box=ROUNDED,
                    padding=(0, 2),
                )
            )
        else:
            ui.warning("Listening stats not available")

        # Account Info Panel
        if account:
            console.print()

            sub_status = "[success]✓ Active[/success]" if account.is_active_member else "[dim]Inactive[/dim]"

            benefits_list = []
            if account.benefits:
                benefits_list = [b.benefit_id for b in account.benefits[:5]]
            benefits_str = ", ".join(benefits_list) if benefits_list else "[dim](none)[/dim]"

            account_text = Text()
            account_text.append(f"\n{Icons.USER} Membership: ", style="bold")
            account_text.append_text(Text.from_markup(sub_status))
            account_text.append("\n")

            account_text.append(f"{Icons.CREDIT} Plan: ", style="bold")
            account_text.append(f"{account.plan_name or 'N/A'}\n", style="accent")

            account_text.append(f"{Icons.GIFT} Credits: ", style="bold")
            account_text.append(f"{account.credits_available or 0}\n", style="warning")

            account_text.append(f"\n{Icons.SPARKLE} Benefits:\n", style="bold")
            account_text.append(f"    {benefits_str}\n")

            console.print(
                Panel(
                    account_text,
                    title="💳 Account Info",
                    border_style="magenta",
                    box=ROUNDED,
                    padding=(0, 2),
                )
            )
        else:
            ui.warning("Account info not available")

    except AudibleAuthError as e:
        ui.error("Auth failed", details=str(e))
        raise typer.Exit(1) from e
    except Exception as e:
        ui.error("Error", details=str(e))
        raise typer.Exit(1) from e


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
                if item.overall_rating:
                    full_stars = int(item.overall_rating)
                    rating = f"{'★' * full_stars}{'☆' * (5 - full_stars)} {item.overall_rating:.1f}"

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
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


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
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
