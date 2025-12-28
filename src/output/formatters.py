"""
Output formatter implementations.

Provides a plugin-based output formatting system with support for:
- Table (Rich console tables)
- JSON (structured data)
- CSV (comma-separated values)

Usage:
    formatter = get_formatter(OutputFormat.TABLE)
    formatter.format_items(items, columns=["title", "bitrate", "tier"])
    formatter.output()  # Writes to console or file
"""

import csv
import json
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Any, TextIO

from rich.box import ROUNDED
from rich.console import Console
from rich.table import Table


class OutputFormat(str, Enum):
    """Supported output formats."""

    TABLE = "table"
    JSON = "json"
    CSV = "csv"


class OutputFormatter(ABC):
    """
    Base class for output formatters.

    Formatters convert data into a specific output format and handle
    output to console, file, or stream.
    """

    def __init__(
        self,
        output: Path | TextIO | None = None,
        console: Console | None = None,
    ):
        """
        Initialize formatter.

        Args:
            output: File path or stream to write to (None = stdout/console)
            console: Rich console instance (for table formatter)
        """
        self.output_target = output
        self.console = console or Console()
        self._data: list[dict[str, Any]] = []
        self._columns: list[str] = []
        self._title: str | None = None

    @abstractmethod
    def format_items(
        self,
        items: list[dict[str, Any]],
        columns: list[str] | None = None,
        title: str | None = None,
        column_formatters: dict[str, Callable[[Any], str]] | None = None,
    ) -> "OutputFormatter":
        """
        Format a list of items for output.

        Args:
            items: List of dictionaries to format
            columns: Column names to include (None = all)
            title: Optional title for the output
            column_formatters: Dict mapping column names to formatter functions

        Returns:
            Self for method chaining
        """
        pass

    @abstractmethod
    def output(self) -> None:
        """Write formatted output to target (console, file, or stream)."""
        pass

    def _get_output_stream(self) -> tuple[TextIO, bool]:
        """
        Get output stream and whether it should be closed.

        Returns:
            Tuple of (stream, should_close)
        """
        if self.output_target is None:
            return sys.stdout, False
        elif isinstance(self.output_target, Path):
            return open(self.output_target, "w", newline="", encoding="utf-8"), True  # noqa: SIM115
        else:
            return self.output_target, False


class TableFormatter(OutputFormatter):
    """
    Rich table formatter for console output.

    Produces colorful, well-formatted tables using Rich library.
    """

    def __init__(
        self,
        output: Path | TextIO | None = None,
        console: Console | None = None,
        box: Any = ROUNDED,
    ):
        super().__init__(output, console)
        self.box = box
        self._table: Table | None = None
        self._column_styles: dict[str, str] = {}

    def set_column_style(self, column: str, style: str) -> "TableFormatter":
        """
        Set style for a specific column.

        Args:
            column: Column name
            style: Rich style string (e.g., "bold cyan", "red")

        Returns:
            Self for method chaining
        """
        self._column_styles[column] = style
        return self

    def format_items(
        self,
        items: list[dict[str, Any]],
        columns: list[str] | None = None,
        title: str | None = None,
        column_formatters: dict[str, Callable[[Any], str]] | None = None,
    ) -> "TableFormatter":
        """Format items into a Rich table."""
        self._data = items
        self._title = title
        column_formatters = column_formatters or {}

        # Determine columns from first item if not specified
        if columns:
            self._columns = columns
        elif items:
            self._columns = list(items[0].keys())
        else:
            self._columns = []

        # Create table
        self._table = Table(title=title, box=self.box)

        # Add columns with optional styles
        for col in self._columns:
            style = self._column_styles.get(col)
            # Use title case for headers
            header = col.replace("_", " ").title()
            self._table.add_column(header, style=style)

        # Add rows
        for item in items:
            row_values = []
            for col in self._columns:
                value = item.get(col, "")
                if col in column_formatters:
                    value = column_formatters[col](value)
                row_values.append(str(value) if value is not None else "")
            self._table.add_row(*row_values)

        return self

    def output(self) -> None:
        """Output table to console or file."""
        if self._table is None:
            return

        if self.output_target is None:
            # Direct console output
            self.console.print(self._table)
        elif isinstance(self.output_target, Path):
            # Export to file (as plain text)
            with open(self.output_target, "w", encoding="utf-8") as f:
                temp_console = Console(file=f, force_terminal=False, width=200)
                temp_console.print(self._table)
        else:
            # Output to stream
            temp_console = Console(file=self.output_target, force_terminal=False, width=200)
            temp_console.print(self._table)


class JSONFormatter(OutputFormatter):
    """
    JSON formatter for structured data output.

    Produces valid JSON that can be piped to other tools.
    """

    def __init__(
        self,
        output: Path | TextIO | None = None,
        console: Console | None = None,
        indent: int = 2,
        compact: bool = False,
    ):
        super().__init__(output, console)
        self.indent = None if compact else indent
        self._formatted: str = ""

    def format_items(
        self,
        items: list[dict[str, Any]],
        columns: list[str] | None = None,
        title: str | None = None,
        column_formatters: dict[str, Callable[[Any], str]] | None = None,
    ) -> "JSONFormatter":
        """Format items as JSON."""
        self._data = items
        self._title = title
        self._columns = columns or []
        column_formatters = column_formatters or {}

        # Filter columns if specified
        if columns:
            filtered_items = []
            for item in items:
                filtered = {}
                for col in columns:
                    value = item.get(col)
                    if col in column_formatters:
                        value = column_formatters[col](value)
                    filtered[col] = value
                filtered_items.append(filtered)
            output_data = filtered_items
        else:
            output_data = items

        # Wrap in object with metadata
        result = {
            "count": len(output_data),
            "items": output_data,
        }
        if title:
            result["title"] = title

        self._formatted = json.dumps(result, indent=self.indent, default=str)
        return self

    def output(self) -> None:
        """Output JSON to console or file."""
        stream, should_close = self._get_output_stream()
        try:
            stream.write(self._formatted)
            stream.write("\n")
        finally:
            if should_close:
                stream.close()


class CSVFormatter(OutputFormatter):
    """
    CSV formatter for spreadsheet-compatible output.

    Produces standard CSV that can be opened in Excel, etc.
    """

    def __init__(
        self,
        output: Path | TextIO | None = None,
        console: Console | None = None,
        delimiter: str = ",",
        include_header: bool = True,
    ):
        super().__init__(output, console)
        self.delimiter = delimiter
        self.include_header = include_header
        self._formatted: str = ""

    def format_items(
        self,
        items: list[dict[str, Any]],
        columns: list[str] | None = None,
        title: str | None = None,
        column_formatters: dict[str, Callable[[Any], str]] | None = None,
    ) -> "CSVFormatter":
        """Format items as CSV."""
        self._data = items
        self._title = title
        column_formatters = column_formatters or {}

        # Determine columns from first item if not specified
        if columns:
            self._columns = columns
        elif items:
            self._columns = list(items[0].keys())
        else:
            self._columns = []

        # Build CSV
        string_buffer = StringIO()
        writer = csv.writer(string_buffer, delimiter=self.delimiter)

        # Write header
        if self.include_header:
            writer.writerow(self._columns)

        # Write rows
        for item in items:
            row = []
            for col in self._columns:
                value = item.get(col, "")
                if col in column_formatters:
                    value = column_formatters[col](value)
                row.append(value if value is not None else "")
            writer.writerow(row)

        self._formatted = string_buffer.getvalue()
        return self

    def output(self) -> None:
        """Output CSV to console or file."""
        stream, should_close = self._get_output_stream()
        try:
            stream.write(self._formatted)
        finally:
            if should_close:
                stream.close()


def get_formatter(
    format: OutputFormat | str,
    output: Path | TextIO | None = None,
    console: Console | None = None,
    **kwargs: Any,
) -> OutputFormatter:
    """
    Factory function to get appropriate formatter.

    Args:
        format: Output format (table, json, csv)
        output: Output target (None = stdout/console)
        console: Rich console instance
        **kwargs: Additional formatter-specific options

    Returns:
        OutputFormatter instance

    Raises:
        ValueError: If format is not supported
    """
    if isinstance(format, str):
        try:
            format = OutputFormat(format.lower())
        except ValueError:
            raise ValueError(f"Unsupported output format: {format}") from None

    formatters: dict[OutputFormat, type[OutputFormatter]] = {
        OutputFormat.TABLE: TableFormatter,
        OutputFormat.JSON: JSONFormatter,
        OutputFormat.CSV: CSVFormatter,
    }

    formatter_class = formatters.get(format)
    if formatter_class is None:
        raise ValueError(f"Unsupported output format: {format}") from None

    return formatter_class(output=output, console=console, **kwargs)
