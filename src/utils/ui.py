"""
Rich UI utilities for beautiful console output.

Provides consistent, visually appealing feedback across the CLI with
spinners, progress bars, panels, tables, and styled messages.

Usage:
    from src.utils.ui import console, ui

    # Status messages
    ui.success("Operation completed!")
    ui.error("Something went wrong", details="Connection refused")
    ui.warning("Cache expired")
    ui.info("Processing 42 items...")

    # Spinners for operations
    with ui.spinner("Connecting to server...") as status:
        connect()
        status.update("Fetching data...")
        fetch()
    ui.success("Done!")

    # Progress bars
    with ui.progress() as progress:
        task = progress.add_task("Downloading", total=100)
        for i in range(100):
            progress.advance(task)

    # Styled headers
    ui.header("Audiobook Manager", subtitle="v1.0.0")

    # Rich layout components (re-exported for convenience)
    from src.utils.ui import Columns, Group, Padding, Live
    ui.section("Library Status")

    # Tables
    table = ui.create_table("My Table", columns=["Name", "Value"])
    table.add_row("foo", "bar")
    console.print(table)
"""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from rich.box import DOUBLE, ROUNDED, SIMPLE
from rich.columns import Columns
from rich.console import Console, Group
from rich.live import Live
from rich.logging import RichHandler
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.rule import Rule
from rich.status import Status
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich.tree import Tree

# =============================================================================
# Custom Theme
# =============================================================================

AUDIOBOOK_THEME = Theme(
    {
        # Status colors
        "success": "bold green",
        "error": "bold red",
        "warning": "bold yellow",
        "info": "bold cyan",
        "debug": "dim",
        "muted": "dim white",
        # UI elements
        "header": "bold magenta",
        "subheader": "bold blue",
        "accent": "bold cyan",
        "highlight": "bold yellow",
        "link": "underline blue",
        # Quality tiers
        "tier.excellent": "bold bright_blue",
        "tier.better": "dark_green",
        "tier.good": "green",
        "tier.low": "red",
        "tier.poor": "bold red",
        "tier.unknown": "dim",
        # Data types
        "asin": "cyan",
        "title": "bold white",
        "author": "italic white",
        "duration": "green",
        "size": "blue",
        "bitrate": "yellow",
        # Status indicators
        "status.connected": "green",
        "status.disconnected": "red",
        "status.pending": "yellow",
        "status.cached": "cyan",
    }
)

# =============================================================================
# Global Console
# =============================================================================

console = Console(theme=AUDIOBOOK_THEME, highlight=True, emoji=True)

# =============================================================================
# Icons & Symbols
# =============================================================================


class Icons:
    """Unicode icons for consistent visual feedback."""

    # Status
    SUCCESS = "✓"
    ERROR = "✗"
    WARNING = "⚠"
    INFO = "ℹ"
    QUESTION = "?"
    PENDING = "○"

    # Actions
    ARROW_RIGHT = "→"
    ARROW_LEFT = "←"
    ARROW_UP = "↑"
    ARROW_DOWN = "↓"
    BULLET = "•"
    STAR = "★"
    STAR_EMPTY = "☆"

    # Media
    BOOK = "📚"
    AUDIOBOOK = "🎧"
    MUSIC = "🎵"
    MIC = "🎙️"
    SPEAKER = "🔊"

    # Quality
    QUALITY_HIGH = "💎"
    QUALITY_GOOD = "✨"
    QUALITY_OK = "👍"
    QUALITY_LOW = "👎"
    QUALITY_BAD = "💩"

    # System
    FOLDER = "📁"
    FILE = "📄"
    LINK = "🔗"
    LOCK = "🔒"
    UNLOCK = "🔓"
    CLOUD = "☁️"
    SERVER = "🖥️"
    DATABASE = "🗄️"
    CACHE = "💾"
    GEAR = "⚙️"
    CLOCK = "🕐"

    # People
    USER = "👤"
    USERS = "👥"
    AUTHOR = "✍️"
    NARRATOR = "🗣️"

    # Finance
    MONEY = "💰"
    CREDIT = "💳"
    GIFT = "🎁"

    # Actions
    SEARCH = "🔍"
    DOWNLOAD = "⬇️"
    UPLOAD = "⬆️"
    SYNC = "🔄"
    PLAY = "▶"
    PAUSE = "⏸"
    STOP = "⏹"

    # Decorative
    SPARKLE = "✨"
    FIRE = "🔥"
    ROCKET = "🚀"
    TROPHY = "🏆"
    HEART = "❤️"
    THUMBS_UP = "👍"
    THUMBS_DOWN = "👎"


# =============================================================================
# UI Helper Class
# =============================================================================


class UIHelper:
    """Central UI helper for consistent visual output."""

    def __init__(self, console: Console):
        self.console = console
        self.icons = Icons

    # -------------------------------------------------------------------------
    # Status Messages
    # -------------------------------------------------------------------------

    def success(self, message: str, details: str | None = None, prefix: str = Icons.SUCCESS) -> None:
        """Print a success message."""
        text = Text()
        text.append(f"{prefix} ", style="success")
        text.append_text(Text.from_markup(message))
        if details:
            text.append(f"\n   {details}", style="muted")
        self.console.print(text)

    def error(self, message: str, details: str | None = None, prefix: str = Icons.ERROR) -> None:
        """Print an error message."""
        text = Text()
        text.append(f"{prefix} ", style="error")
        text.append_text(Text.from_markup(f"[error]{message}[/error]"))
        if details:
            text.append(f"\n   {details}", style="muted")
        self.console.print(text)

    def warning(self, message: str, details: str | None = None, prefix: str = Icons.WARNING) -> None:
        """Print a warning message."""
        text = Text()
        text.append(f"{prefix} ", style="warning")
        text.append_text(Text.from_markup(message))
        if details:
            text.append(f"\n   {details}", style="muted")
        self.console.print(text)

    def info(self, message: str, details: str | None = None, prefix: str = Icons.INFO) -> None:
        """Print an info message."""
        text = Text()
        text.append(f"{prefix} ", style="info")
        text.append_text(Text.from_markup(message))
        if details:
            text.append(f"\n   {details}", style="muted")
        self.console.print(text)

    def debug(self, message: str) -> None:
        """Print a debug message (dimmed)."""
        self.console.print(f"[debug]{message}[/debug]")

    def muted(self, message: str) -> None:
        """Print a muted/dim message."""
        self.console.print(f"[muted]{message}[/muted]")

    # -------------------------------------------------------------------------
    # Headers & Sections
    # -------------------------------------------------------------------------

    def header(
        self,
        title: str,
        subtitle: str | None = None,
        icon: str | None = None,
        style: str = "header",
    ) -> None:
        """Print a styled header banner."""
        icon_str = f"{icon} " if icon else ""
        header_text = f"{icon_str}{title}"

        content = Text()
        content.append(header_text, style=style)
        if subtitle:
            content.append(f"\n{subtitle}", style="muted")

        panel = Panel(
            content,
            box=DOUBLE,
            border_style=style,
            padding=(1, 2),
        )
        self.console.print()
        self.console.print(panel)
        self.console.print()

    def section(self, title: str, icon: str | None = None, style: str = "subheader") -> None:
        """Print a section header with rule."""
        icon_str = f"{icon} " if icon else ""
        self.console.print()
        self.console.print(Rule(f"{icon_str}{title}", style=style, align="left"))
        self.console.print()

    def subsection(self, title: str) -> None:
        """Print a subsection header."""
        self.console.print(f"\n[bold]{title}[/bold]")

    def divider(self, style: str = "dim") -> None:
        """Print a horizontal divider."""
        self.console.print(Rule(style=style))

    def newline(self, count: int = 1) -> None:
        """Print newlines."""
        for _ in range(count):
            self.console.print()

    # -------------------------------------------------------------------------
    # Progress & Spinners
    # -------------------------------------------------------------------------

    @contextmanager
    def spinner(
        self,
        message: str,
        spinner_name: str = "dots",
        style: str = "info",
    ) -> Generator[Status]:
        """Context manager for spinner with status updates."""
        with self.console.status(f"[{style}]{message}[/{style}]", spinner=spinner_name) as status:
            yield status

    def progress(
        self,
        *columns: ProgressColumn,
        transient: bool = False,
        expand: bool = True,
    ) -> Progress:
        """Create a progress bar with sensible defaults."""
        if not columns:
            columns = (
                SpinnerColumn(spinner_name="dots2", style="info"),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40, style="info", complete_style="success", finished_style="success"),
                TaskProgressColumn(),
                TextColumn("[muted]•[/muted]"),
                TimeElapsedColumn(),
                TextColumn("[muted]•[/muted]"),
                TimeRemainingColumn(),
            )
        return Progress(*columns, console=self.console, transient=transient, expand=expand)

    def download_progress(self) -> Progress:
        """Create a download-specific progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=self.console,
        )

    def simple_progress(self) -> Progress:
        """Create a simple compact progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            console=self.console,
            transient=True,
        )

    # -------------------------------------------------------------------------
    # Tables
    # -------------------------------------------------------------------------

    def create_table(
        self,
        title: str | None = None,
        columns: list[str] | None = None,
        show_header: bool = True,
        show_lines: bool = False,
        box_style: Any = ROUNDED,
        header_style: str = "bold cyan",
        border_style: str = "dim",
        expand: bool = False,
        row_styles: list[str] | None = None,
    ) -> Table:
        """Create a styled table."""
        table = Table(
            title=title,
            show_header=show_header,
            show_lines=show_lines,
            box=box_style,
            header_style=header_style,
            border_style=border_style,
            expand=expand,
            row_styles=row_styles or ["", "dim"],
        )

        if columns:
            for col in columns:
                table.add_column(col)

        return table

    def key_value_table(
        self,
        data: dict[str, Any],
        title: str | None = None,
        key_style: str = "bold cyan",
        value_style: str = "white",
    ) -> Table:
        """Create a two-column key-value table."""
        table = Table(
            title=title,
            show_header=False,
            box=SIMPLE,
            padding=(0, 1),
            expand=False,
        )
        table.add_column("Key", style=key_style, no_wrap=True)
        table.add_column("Value", style=value_style)

        for key, value in data.items():
            table.add_row(key, str(value) if value is not None else "[dim]N/A[/dim]")

        return table

    # -------------------------------------------------------------------------
    # Panels & Cards
    # -------------------------------------------------------------------------

    def panel(
        self,
        content: str | Text,
        title: str | None = None,
        subtitle: str | None = None,
        style: str = "cyan",
        box_style: Any = ROUNDED,
        padding: tuple[int, int] = (1, 2),
    ) -> Panel:
        """Create a styled panel."""
        return Panel(
            content,
            title=title,
            subtitle=subtitle,
            border_style=style,
            box=box_style,
            padding=padding,
        )

    def info_panel(self, content: str, title: str | None = None) -> Panel:
        """Create an info-styled panel."""
        return self.panel(content, title=title, style="info")

    def success_panel(self, content: str, title: str | None = None) -> Panel:
        """Create a success-styled panel."""
        return self.panel(content, title=title, style="success")

    def error_panel(self, content: str, title: str | None = None) -> Panel:
        """Create an error-styled panel."""
        return self.panel(content, title=title, style="error")

    def warning_panel(self, content: str, title: str | None = None) -> Panel:
        """Create a warning-styled panel."""
        return self.panel(content, title=title, style="warning")

    def stats_panel(
        self,
        stats: dict[str, Any],
        title: str | None = None,
        icon: str | None = None,
    ) -> Panel:
        """Create a stats display panel."""
        lines = []
        for key, value in stats.items():
            if isinstance(value, float):
                value = f"{value:.2f}"
            lines.append(f"[bold]{key}:[/bold] {value}")

        icon_str = f"{icon} " if icon else ""
        return self.panel(
            "\n".join(lines),
            title=f"{icon_str}{title}" if title else None,
            style="cyan",
        )

    # -------------------------------------------------------------------------
    # Trees
    # -------------------------------------------------------------------------

    def tree(self, label: str, style: str = "bold cyan", guide_style: str = "dim") -> Tree:
        """Create a styled tree for hierarchical data."""
        return Tree(label, style=style, guide_style=guide_style)

    # -------------------------------------------------------------------------
    # Specialized Displays
    # -------------------------------------------------------------------------

    def quality_badge(self, tier: str) -> Text:
        """Create a quality tier badge."""
        tier_styles = {
            "excellent": ("tier.excellent", "💎 EXCELLENT"),
            "better": ("tier.better", "✨ BETTER"),
            "good": ("tier.good", "👍 GOOD"),
            "low": ("tier.low", "👎 LOW"),
            "poor": ("tier.poor", "💩 POOR"),
            "unknown": ("tier.unknown", "? UNKNOWN"),
        }
        style, label = tier_styles.get(tier.lower(), ("tier.unknown", f"? {tier.upper()}"))
        return Text(label, style=style)

    def connection_status(self, connected: bool, name: str) -> Text:
        """Display connection status."""
        text = Text()
        if connected:
            text.append(f"{Icons.SUCCESS} ", style="status.connected")
            text.append(name, style="bold")
            text.append(" connected", style="status.connected")
        else:
            text.append(f"{Icons.ERROR} ", style="status.disconnected")
            text.append(name, style="bold")
            text.append(" disconnected", style="status.disconnected")
        return text

    def rating_stars(self, rating: float, max_stars: int = 5) -> Text:
        """Display rating as stars."""
        full_stars = int(rating)
        empty_stars = max_stars - full_stars
        text = Text()
        text.append(Icons.STAR * full_stars, style="yellow")
        text.append(Icons.STAR_EMPTY * empty_stars, style="dim")
        text.append(f" {rating:.1f}", style="muted")
        return text

    def duration_display(self, hours: float) -> Text:
        """Format duration nicely."""
        if hours < 1:
            minutes = int(hours * 60)
            return Text(f"{minutes}m", style="duration")
        elif hours < 24:
            return Text(f"{hours:.1f}h", style="duration")
        else:
            days = int(hours / 24)
            remaining_hours = hours % 24
            return Text(f"{days}d {remaining_hours:.0f}h", style="duration")

    def size_display(self, bytes_size: int) -> Text:
        """Format file size nicely."""
        if bytes_size < 1024:
            return Text(f"{bytes_size} B", style="size")
        elif bytes_size < 1024**2:
            return Text(f"{bytes_size / 1024:.1f} KB", style="size")
        elif bytes_size < 1024**3:
            return Text(f"{bytes_size / (1024**2):.1f} MB", style="size")
        else:
            return Text(f"{bytes_size / (1024**3):.2f} GB", style="size")

    def bitrate_display(self, kbps: int) -> Text:
        """Format bitrate with quality indication."""
        if kbps >= 256:
            return Text(f"{kbps}k", style="tier.excellent")
        elif kbps >= 128:
            return Text(f"{kbps}k", style="tier.good")
        elif kbps >= 96:
            return Text(f"{kbps}k", style="tier.acceptable")
        else:
            return Text(f"{kbps}k", style="tier.low")

    def timestamp(self, dt: datetime | None = None) -> Text:
        """Display a formatted timestamp."""
        if dt is None:
            dt = datetime.now()
        return Text(dt.strftime("%Y-%m-%d %H:%M:%S"), style="muted")

    # -------------------------------------------------------------------------
    # Interactive / Confirmation
    # -------------------------------------------------------------------------

    def confirm(self, message: str, default: bool = False) -> bool:
        """Ask for confirmation with styled prompt."""
        default_hint = "[Y/n]" if default else "[y/N]"
        response = self.console.input(f"[bold]{message}[/bold] {default_hint} ").strip().lower()
        if not response:
            return default
        return response in ("y", "yes", "1", "true")

    def prompt(self, message: str, default: str | None = None) -> str:
        """Get user input with styled prompt."""
        default_hint = f" [{default}]" if default else ""
        response = self.console.input(f"[bold]{message}[/bold]{default_hint}: ").strip()
        return response if response else (default or "")

    # -------------------------------------------------------------------------
    # Markdown
    # -------------------------------------------------------------------------

    def markdown(self, text: str) -> None:
        """Print markdown-formatted text."""
        self.console.print(Markdown(text))


# =============================================================================
# Rich Logging Handler
# =============================================================================


def get_rich_handler(
    level: int = 20,  # INFO
    show_time: bool = True,
    show_path: bool = False,
    rich_tracebacks: bool = True,
    tracebacks_show_locals: bool = False,
    markup: bool = True,
    log_time_format: str = "[%X]",
) -> RichHandler:
    """
    Create a Rich logging handler for beautiful log output.

    Args:
        level: Log level
        show_time: Show timestamp
        show_path: Show file path
        rich_tracebacks: Use rich tracebacks
        tracebacks_show_locals: Show local variables in tracebacks
        markup: Enable rich markup in log messages
        log_time_format: Time format string

    Returns:
        Configured RichHandler
    """
    return RichHandler(
        level=level,
        console=console,
        show_time=show_time,
        show_path=show_path,
        rich_tracebacks=rich_tracebacks,
        tracebacks_show_locals=tracebacks_show_locals,
        markup=markup,
        log_time_format=log_time_format,
    )


# =============================================================================
# Singleton UI Instance
# =============================================================================

ui = UIHelper(console)

# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "console",
    "ui",
    "Icons",
    "UIHelper",
    "AUDIOBOOK_THEME",
    "get_rich_handler",
    # Progress classes for custom use
    "Progress",
    "SpinnerColumn",
    "BarColumn",
    "TextColumn",
    "TaskProgressColumn",
    "TimeElapsedColumn",
    "TimeRemainingColumn",
    "MofNCompleteColumn",
    # Other rich exports
    "Table",
    "Panel",
    "Tree",
    "Text",
    "Rule",
    "Columns",
    "Group",
    "Padding",
    "Live",
    "Markdown",
]
