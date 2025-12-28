"""
Tests for output formatters.
"""

import json
import tempfile
from io import StringIO
from pathlib import Path

import pytest

from src.output import CSVFormatter, JSONFormatter, OutputFormat, TableFormatter, get_formatter


class TestOutputFormat:
    """Tests for OutputFormat enum."""

    def test_table_format(self):
        assert OutputFormat.TABLE.value == "table"

    def test_json_format(self):
        assert OutputFormat.JSON.value == "json"

    def test_csv_format(self):
        assert OutputFormat.CSV.value == "csv"


class TestGetFormatter:
    """Tests for get_formatter factory function."""

    def test_get_table_formatter(self):
        formatter = get_formatter(OutputFormat.TABLE)
        assert isinstance(formatter, TableFormatter)

    def test_get_json_formatter(self):
        formatter = get_formatter(OutputFormat.JSON)
        assert isinstance(formatter, JSONFormatter)

    def test_get_csv_formatter(self):
        formatter = get_formatter(OutputFormat.CSV)
        assert isinstance(formatter, CSVFormatter)

    def test_get_formatter_by_string(self):
        formatter = get_formatter("json")
        assert isinstance(formatter, JSONFormatter)

    def test_get_formatter_case_insensitive(self):
        formatter = get_formatter("JSON")
        assert isinstance(formatter, JSONFormatter)

    def test_get_formatter_invalid_format(self):
        with pytest.raises(ValueError, match="Unsupported output format"):
            get_formatter("xml")


class TestTableFormatter:
    """Tests for TableFormatter."""

    @pytest.fixture
    def sample_items(self):
        return [
            {"title": "Book 1", "bitrate": 128, "tier": "Good"},
            {"title": "Book 2", "bitrate": 256, "tier": "Excellent"},
        ]

    def test_format_items_basic(self, sample_items):
        formatter = TableFormatter()
        result = formatter.format_items(sample_items)
        assert result is formatter  # Method chaining
        assert formatter._table is not None
        assert formatter._data == sample_items

    def test_format_items_with_columns(self, sample_items):
        formatter = TableFormatter()
        formatter.format_items(sample_items, columns=["title", "tier"])
        assert formatter._columns == ["title", "tier"]

    def test_format_items_with_title(self, sample_items):
        formatter = TableFormatter()
        formatter.format_items(sample_items, title="Quality Report")
        assert formatter._title == "Quality Report"

    def test_set_column_style(self):
        formatter = TableFormatter()
        result = formatter.set_column_style("tier", "bold green")
        assert result is formatter  # Method chaining
        assert formatter._column_styles["tier"] == "bold green"

    def test_output_to_stream(self, sample_items):
        stream = StringIO()
        formatter = TableFormatter(output=stream)
        formatter.format_items(sample_items, columns=["title", "bitrate"])
        formatter.output()
        output = stream.getvalue()
        assert "Book 1" in output
        assert "128" in output

    def test_output_to_file(self, sample_items):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            path = Path(f.name)

        try:
            formatter = TableFormatter(output=path)
            formatter.format_items(sample_items)
            formatter.output()
            content = path.read_text()
            assert "Book 1" in content
        finally:
            path.unlink()

    def test_format_empty_items(self):
        formatter = TableFormatter()
        formatter.format_items([])
        assert formatter._data == []
        assert formatter._columns == []

    def test_column_formatters(self, sample_items):
        formatter = TableFormatter()
        stream = StringIO()
        formatter.output_target = stream
        formatter.format_items(
            sample_items,
            column_formatters={"bitrate": lambda x: f"{x} kbps"},
        )
        formatter.output()
        output = stream.getvalue()
        assert "128 kbps" in output


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    @pytest.fixture
    def sample_items(self):
        return [
            {"title": "Book 1", "bitrate": 128, "tier": "Good"},
            {"title": "Book 2", "bitrate": 256, "tier": "Excellent"},
        ]

    def test_format_items_basic(self, sample_items):
        formatter = JSONFormatter()
        result = formatter.format_items(sample_items)
        assert result is formatter  # Method chaining
        parsed = json.loads(formatter._formatted)
        assert parsed["count"] == 2
        assert len(parsed["items"]) == 2

    def test_format_items_with_columns(self, sample_items):
        formatter = JSONFormatter()
        formatter.format_items(sample_items, columns=["title", "tier"])
        parsed = json.loads(formatter._formatted)
        # Items should only have filtered columns
        assert "bitrate" not in parsed["items"][0]
        assert "title" in parsed["items"][0]

    def test_format_items_with_title(self, sample_items):
        formatter = JSONFormatter()
        formatter.format_items(sample_items, title="Quality Report")
        parsed = json.loads(formatter._formatted)
        assert parsed["title"] == "Quality Report"

    def test_output_to_stream(self, sample_items):
        stream = StringIO()
        formatter = JSONFormatter(output=stream)
        formatter.format_items(sample_items)
        formatter.output()
        output = stream.getvalue()
        parsed = json.loads(output)
        assert parsed["count"] == 2

    def test_output_to_file(self, sample_items):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            formatter = JSONFormatter(output=path)
            formatter.format_items(sample_items)
            formatter.output()
            content = json.loads(path.read_text())
            assert content["count"] == 2
        finally:
            path.unlink()

    def test_compact_json(self, sample_items):
        formatter = JSONFormatter(compact=True)
        formatter.format_items(sample_items)
        # Compact JSON should not have newlines in the middle
        assert "\n  " not in formatter._formatted

    def test_custom_indent(self, sample_items):
        formatter = JSONFormatter(indent=4)
        formatter.format_items(sample_items)
        # 4-space indent should create longer spacing
        assert "    " in formatter._formatted

    def test_format_empty_items(self):
        formatter = JSONFormatter()
        formatter.format_items([])
        parsed = json.loads(formatter._formatted)
        assert parsed["count"] == 0
        assert parsed["items"] == []


class TestCSVFormatter:
    """Tests for CSVFormatter."""

    @pytest.fixture
    def sample_items(self):
        return [
            {"title": "Book 1", "bitrate": 128, "tier": "Good"},
            {"title": "Book 2", "bitrate": 256, "tier": "Excellent"},
        ]

    def test_format_items_basic(self, sample_items):
        formatter = CSVFormatter()
        result = formatter.format_items(sample_items)
        assert result is formatter  # Method chaining
        lines = formatter._formatted.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows

    def test_format_items_with_columns(self, sample_items):
        formatter = CSVFormatter()
        formatter.format_items(sample_items, columns=["title", "tier"])
        lines = formatter._formatted.strip().split("\n")
        # Strip potential \r from line endings
        assert lines[0].rstrip("\r") == "title,tier"

    def test_format_items_no_header(self, sample_items):
        formatter = CSVFormatter(include_header=False)
        formatter.format_items(sample_items)
        lines = formatter._formatted.strip().split("\n")
        assert len(lines) == 2  # Only data rows, no header

    def test_output_to_stream(self, sample_items):
        stream = StringIO()
        formatter = CSVFormatter(output=stream)
        formatter.format_items(sample_items)
        formatter.output()
        output = stream.getvalue()
        assert "Book 1" in output
        assert "128" in output

    def test_output_to_file(self, sample_items):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            path = Path(f.name)

        try:
            formatter = CSVFormatter(output=path)
            formatter.format_items(sample_items)
            formatter.output()
            content = path.read_text()
            assert "Book 1" in content
        finally:
            path.unlink()

    def test_custom_delimiter(self, sample_items):
        formatter = CSVFormatter(delimiter=";")
        formatter.format_items(sample_items, columns=["title", "bitrate"])
        assert "title;bitrate" in formatter._formatted

    def test_format_empty_items(self):
        formatter = CSVFormatter()
        formatter.format_items([])
        # Empty items with no columns = only potential empty header line
        # Strip whitespace - result should be empty or just whitespace
        assert formatter._formatted.strip() == ""

    def test_handles_none_values(self):
        items = [{"title": "Book", "bitrate": None}]
        formatter = CSVFormatter()
        formatter.format_items(items)
        lines = formatter._formatted.strip().split("\n")
        # None should be converted to empty string
        assert "Book," in lines[1]

    def test_column_formatters(self, sample_items):
        formatter = CSVFormatter()
        formatter.format_items(
            sample_items,
            columns=["title", "bitrate"],
            column_formatters={"bitrate": lambda x: f"{x}kbps"},
        )
        assert "128kbps" in formatter._formatted
