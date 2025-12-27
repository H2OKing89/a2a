"""Tests for CLI structure and commands.

Tests the restructured CLI with:
- Global commands (status, cache)
- ABS sub-app commands
- Audible sub-app commands
- Quality sub-app commands
"""

# Import the CLI app
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))
from cli import abs_app, app, audible_app, quality_app

runner = CliRunner()


class TestCLIStructure:
    """Test CLI structure and command registration."""

    def test_main_app_has_status_command(self):
        """Test that status is registered on main app."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "status" in result.output
        assert "Show global status" in result.output

    def test_main_app_has_cache_command(self):
        """Test that cache is registered on main app."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "cache" in result.output

    def test_main_app_has_abs_subapp(self):
        """Test that abs sub-app is registered."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "abs" in result.output
        assert "Audiobookshelf" in result.output

    def test_main_app_has_audible_subapp(self):
        """Test that audible sub-app is registered."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "audible" in result.output
        assert "Audible" in result.output

    def test_main_app_has_quality_subapp(self):
        """Test that quality sub-app is registered."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "quality" in result.output


class TestABSSubApp:
    """Test ABS sub-app commands."""

    def test_abs_help_shows_commands(self):
        """Test abs --help shows all expected commands."""
        result = runner.invoke(app, ["abs", "--help"])
        assert result.exit_code == 0
        # Check all expected commands are present
        expected_commands = [
            "status",
            "libraries",
            "stats",
            "items",
            "item",
            "search",
            "export",
            "sample",
            "authors",
            "series",
            "collections",
        ]
        for cmd in expected_commands:
            assert cmd in result.output, f"Command '{cmd}' not found in abs --help"

    def test_abs_status_command_exists(self):
        """Test abs status command is accessible."""
        result = runner.invoke(app, ["abs", "status", "--help"])
        assert result.exit_code == 0
        assert "ABS connection status" in result.output

    def test_abs_libraries_command_exists(self):
        """Test abs libraries command is accessible."""
        result = runner.invoke(app, ["abs", "libraries", "--help"])
        assert result.exit_code == 0
        assert "List all libraries" in result.output

    def test_abs_stats_requires_library_id(self):
        """Test abs stats requires library_id argument."""
        result = runner.invoke(app, ["abs", "stats", "--help"])
        assert result.exit_code == 0
        assert "LIBRARY_ID" in result.output

    def test_abs_items_requires_library_id(self):
        """Test abs items requires library_id argument."""
        result = runner.invoke(app, ["abs", "items", "--help"])
        assert result.exit_code == 0
        assert "LIBRARY_ID" in result.output

    def test_abs_item_requires_item_id(self):
        """Test abs item requires item_id argument."""
        result = runner.invoke(app, ["abs", "item", "--help"])
        assert result.exit_code == 0
        assert "ITEM_ID" in result.output

    def test_abs_search_requires_library_and_query(self):
        """Test abs search requires library_id and query."""
        result = runner.invoke(app, ["abs", "search", "--help"])
        assert result.exit_code == 0
        assert "LIBRARY_ID" in result.output
        assert "QUERY" in result.output

    def test_abs_export_requires_library_id(self):
        """Test abs export requires library_id."""
        result = runner.invoke(app, ["abs", "export", "--help"])
        assert result.exit_code == 0
        assert "LIBRARY_ID" in result.output

    def test_abs_sample_requires_library_id(self):
        """Test abs sample requires library_id."""
        result = runner.invoke(app, ["abs", "sample", "--help"])
        assert result.exit_code == 0
        assert "LIBRARY_ID" in result.output


class TestAudibleSubApp:
    """Test Audible sub-app commands."""

    def test_audible_help_shows_commands(self):
        """Test audible --help shows all expected commands."""
        result = runner.invoke(app, ["audible", "--help"])
        assert result.exit_code == 0
        expected_commands = [
            "login",
            "status",
            "library",
            "item",
            "search",
            "export",
            "cache",
            "sample",
            "wishlist",
            "stats",
            "recommendations",
        ]
        for cmd in expected_commands:
            assert cmd in result.output, f"Command '{cmd}' not found in audible --help"

    def test_audible_status_command_exists(self):
        """Test audible status command is accessible."""
        result = runner.invoke(app, ["audible", "status", "--help"])
        assert result.exit_code == 0
        assert "Audible connection status" in result.output

    def test_audible_login_command_exists(self):
        """Test audible login command is accessible."""
        result = runner.invoke(app, ["audible", "login", "--help"])
        assert result.exit_code == 0
        assert "Login to Audible" in result.output

    def test_audible_library_command_exists(self):
        """Test audible library command is accessible."""
        result = runner.invoke(app, ["audible", "library", "--help"])
        assert result.exit_code == 0
        assert "List your Audible library" in result.output

    def test_audible_item_requires_asin(self):
        """Test audible item requires ASIN argument."""
        result = runner.invoke(app, ["audible", "item", "--help"])
        assert result.exit_code == 0
        assert "ASIN" in result.output

    def test_audible_search_requires_query(self):
        """Test audible search requires query argument."""
        result = runner.invoke(app, ["audible", "search", "--help"])
        assert result.exit_code == 0
        assert "QUERY" in result.output

    def test_audible_sample_command_exists(self):
        """Test audible sample command is accessible."""
        result = runner.invoke(app, ["audible", "sample", "--help"])
        assert result.exit_code == 0
        assert "Collect golden samples" in result.output


class TestQualitySubApp:
    """Test Quality sub-app commands."""

    def test_quality_help_shows_commands(self):
        """Test quality --help shows all expected commands."""
        result = runner.invoke(app, ["quality", "--help"])
        assert result.exit_code == 0
        expected_commands = ["scan", "low", "item", "upgrades"]
        for cmd in expected_commands:
            assert cmd in result.output, f"Command '{cmd}' not found in quality --help"

    def test_quality_scan_command_exists(self):
        """Test quality scan command is accessible."""
        result = runner.invoke(app, ["quality", "scan", "--help"])
        assert result.exit_code == 0

    def test_quality_low_command_exists(self):
        """Test quality low command is accessible."""
        result = runner.invoke(app, ["quality", "low", "--help"])
        assert result.exit_code == 0

    def test_quality_item_command_exists(self):
        """Test quality item command is accessible."""
        result = runner.invoke(app, ["quality", "item", "--help"])
        assert result.exit_code == 0

    def test_quality_upgrades_command_exists(self):
        """Test quality upgrades command is accessible."""
        result = runner.invoke(app, ["quality", "upgrades", "--help"])
        assert result.exit_code == 0


class TestGlobalStatus:
    """Test global status command."""

    @patch("cli.get_abs_client")
    @patch("cli.get_audible_client")
    @patch("cli.get_cache")
    def test_global_status_shows_all_services(self, mock_cache, mock_audible, mock_abs):
        """Test global status shows ABS, Audible, and Cache info."""
        # Mock ABS client
        abs_client = MagicMock()
        abs_client.__enter__ = MagicMock(return_value=abs_client)
        abs_client.__exit__ = MagicMock(return_value=False)
        abs_client.get_me.return_value = MagicMock(username="testuser")
        abs_client.get_libraries.return_value = [MagicMock(), MagicMock()]
        mock_abs.return_value = abs_client

        # Mock Audible client
        audible_client = MagicMock()
        audible_client.__enter__ = MagicMock(return_value=audible_client)
        audible_client.__exit__ = MagicMock(return_value=False)
        audible_client.marketplace = "us"
        audible_client.get_library.return_value = [MagicMock()]
        mock_audible.return_value = audible_client

        # Mock cache
        cache = MagicMock()
        cache.get_stats.return_value = {
            "db_size_mb": 10.5,
            "total_entries": 100,
        }
        mock_cache.return_value = cache

        result = runner.invoke(app, ["status"])

        # Check output contains all sections
        assert "Audiobookshelf" in result.output
        assert "Audible" in result.output
        assert "Cache" in result.output

    @patch("cli.get_abs_client")
    @patch("cli.get_audible_client")
    @patch("cli.get_cache")
    def test_global_status_handles_abs_failure(self, mock_cache, mock_audible, mock_abs):
        """Test global status handles ABS connection failure gracefully."""
        # Mock ABS client failure
        abs_client = MagicMock()
        abs_client.__enter__ = MagicMock(return_value=abs_client)
        abs_client.__exit__ = MagicMock(return_value=False)
        abs_client.get_me.side_effect = Exception("Connection refused")
        mock_abs.return_value = abs_client

        # Mock Audible client success
        audible_client = MagicMock()
        audible_client.__enter__ = MagicMock(return_value=audible_client)
        audible_client.__exit__ = MagicMock(return_value=False)
        audible_client.marketplace = "us"
        audible_client.get_library.return_value = [MagicMock()]
        mock_audible.return_value = audible_client

        # Mock cache
        cache = MagicMock()
        cache.get_stats.return_value = {"db_size_mb": 10.5, "total_entries": 100}
        mock_cache.return_value = cache

        result = runner.invoke(app, ["status"])

        # Should still show output with failure indicator
        assert "Connection failed" in result.output or "✗" in result.output


class TestCacheCommand:
    """Test cache management command."""

    def test_cache_help(self):
        """Test cache --help shows options."""
        result = runner.invoke(app, ["cache", "--help"])
        assert result.exit_code == 0
        assert "--stats" in result.output or "stats" in result.output
        assert "--clear" in result.output
        assert "--cleanup" in result.output


class TestCommandSymmetry:
    """Test that abs and audible sub-apps have symmetric structure."""

    def test_both_have_status(self):
        """Both sub-apps should have status command."""
        abs_result = runner.invoke(app, ["abs", "status", "--help"])
        audible_result = runner.invoke(app, ["audible", "status", "--help"])
        assert abs_result.exit_code == 0
        assert audible_result.exit_code == 0

    def test_both_have_item(self):
        """Both sub-apps should have item command."""
        abs_result = runner.invoke(app, ["abs", "item", "--help"])
        audible_result = runner.invoke(app, ["audible", "item", "--help"])
        assert abs_result.exit_code == 0
        assert audible_result.exit_code == 0

    def test_both_have_search(self):
        """Both sub-apps should have search command."""
        abs_result = runner.invoke(app, ["abs", "search", "--help"])
        audible_result = runner.invoke(app, ["audible", "search", "--help"])
        assert abs_result.exit_code == 0
        assert audible_result.exit_code == 0

    def test_both_have_export(self):
        """Both sub-apps should have export command."""
        abs_result = runner.invoke(app, ["abs", "export", "--help"])
        audible_result = runner.invoke(app, ["audible", "export", "--help"])
        assert abs_result.exit_code == 0
        assert audible_result.exit_code == 0

    def test_both_have_sample(self):
        """Both sub-apps should have sample command."""
        abs_result = runner.invoke(app, ["abs", "sample", "--help"])
        audible_result = runner.invoke(app, ["audible", "sample", "--help"])
        assert abs_result.exit_code == 0
        assert audible_result.exit_code == 0


class TestNewABSCommands:
    """Test new ABS commands (authors, series, collections)."""

    def test_abs_authors_command_exists(self):
        """Test abs authors command is accessible."""
        result = runner.invoke(app, ["abs", "authors", "--help"])
        assert result.exit_code == 0
        assert "authors" in result.output.lower()
        assert "--limit" in result.output
        assert "--sort" in result.output

    def test_abs_series_command_exists(self):
        """Test abs series command is accessible."""
        result = runner.invoke(app, ["abs", "series", "--help"])
        assert result.exit_code == 0
        assert "series" in result.output.lower()
        assert "--limit" in result.output
        assert "--sort" in result.output

    def test_abs_collections_command_exists(self):
        """Test abs collections command is accessible."""
        result = runner.invoke(app, ["abs", "collections", "--help"])
        assert result.exit_code == 0
        assert "collections" in result.output.lower()
        # Check for all actions mentioned
        assert "list" in result.output
        assert "show" in result.output
        assert "create" in result.output
        assert "add" in result.output
        assert "remove" in result.output

    def test_abs_collections_has_required_options(self):
        """Test abs collections has all required options."""
        result = runner.invoke(app, ["abs", "collections", "--help"])
        assert result.exit_code == 0
        assert "--id" in result.output
        assert "--name" in result.output
        assert "--book" in result.output
        assert "--library" in result.output


class TestNewAudibleCommands:
    """Test new Audible commands (wishlist, stats, recommendations)."""

    def test_audible_wishlist_command_exists(self):
        """Test audible wishlist command is accessible."""
        result = runner.invoke(app, ["audible", "wishlist", "--help"])
        assert result.exit_code == 0
        assert "wishlist" in result.output.lower()
        # Check for all actions mentioned
        assert "list" in result.output
        assert "add" in result.output
        assert "remove" in result.output

    def test_audible_wishlist_has_required_options(self):
        """Test audible wishlist has required options."""
        result = runner.invoke(app, ["audible", "wishlist", "--help"])
        assert result.exit_code == 0
        assert "--asin" in result.output
        assert "--limit" in result.output
        assert "--no-cache" in result.output

    def test_audible_stats_command_exists(self):
        """Test audible stats command is accessible."""
        result = runner.invoke(app, ["audible", "stats", "--help"])
        assert result.exit_code == 0
        assert "listening statistics" in result.output.lower() or "statistics" in result.output.lower()

    def test_audible_recommendations_command_exists(self):
        """Test audible recommendations command is accessible."""
        result = runner.invoke(app, ["audible", "recommendations", "--help"])
        assert result.exit_code == 0
        assert "recommendation" in result.output.lower()
        assert "--limit" in result.output
        assert "--no-cache" in result.output

    def test_audible_help_includes_new_commands(self):
        """Test audible --help includes all new commands."""
        result = runner.invoke(app, ["audible", "--help"])
        assert result.exit_code == 0
        new_commands = ["wishlist", "stats", "recommendations"]
        for cmd in new_commands:
            assert cmd in result.output, f"New command '{cmd}' not found in audible --help"

    def test_abs_help_includes_new_commands(self):
        """Test abs --help includes all new commands."""
        result = runner.invoke(app, ["abs", "--help"])
        assert result.exit_code == 0
        new_commands = ["authors", "series", "collections"]
        for cmd in new_commands:
            assert cmd in result.output, f"New command '{cmd}' not found in abs --help"
