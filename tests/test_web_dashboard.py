"""Tests for the web dashboard generator and deployment."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import WebSettings
from src.web.dashboard import DashboardGenerator, DeploymentError, deploy_dashboard

# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture()
def sample_upgrade_data() -> dict:
    """Sample upgrade data matching the quality upgrades export format."""
    return {
        "summary": {
            "total_candidates": 3,
            "plus_catalog_count": 1,
            "monthly_deals_count": 0,
            "good_deals_count": 1,
            "already_owned_count": 1,
            "atmos_available_count": 0,
        },
        "upgrade_candidates": [
            {
                "item_id": "abs-item-1",
                "title": "The Great Book",
                "subtitle": "Collector's Archive Edition",
                "author": "Jane Author",
                "narrators": ["Ava Voices"],
                "primary_narrator": "Ava Voices",
                "series": [{"name": "Great Saga", "sequence": "1", "label": "Great Saga #1"}],
                "series_label": "Great Saga #1",
                "publisher": "Orbit",
                "language": "English",
                "published_year": "2022",
                "asin": "B001TEST01",
                "codec": "aac",
                "codec_mix": ["aac"],
                "bitrate_kbps": 64.0,
                "channels": 2,
                "channel_layout": "stereo",
                "format": "M4B",
                "format_mix": ["M4B"],
                "size_mb": 500.0,
                "duration_hours": 12.4,
                "file_count": 1,
                "primary_filename": "The Great Book.m4b",
                "path": "/audiobooks/Jane Author/The Great Book",
                "tier": "Poor",
                "quality_score": 18.2,
                "upgrade_priority": 650,
                "upgrade_reason": "Very low bitrate with a major Audible improvement available.",
                "is_current_atmos": False,
                "owned_on_audible": False,
                "is_plus_catalog": True,
                "plus_expiration": None,
                "is_monthly_deal": False,
                "list_price": 29.99,
                "sale_price": 20.99,
                "discount_percent": 30.0,
                "is_good_deal": False,
                "has_atmos_upgrade": False,
                "audible_best_bitrate": 128,
                "audible_best_codec": "AAC-LC",
                "delta_kbps": 64.0,
                "acquisition_recommendation": "FREE",
                "acquisition_label": "FREE",
                "audible_url": "https://www.audible.com/pd/B001TEST01",
                "cover_image_url": "https://m.media-amazon.com/images/I/test1.jpg",
            },
            {
                "item_id": "abs-item-2",
                "title": "Another Novel",
                "subtitle": "The Director's Cut",
                "author": "Bob Writer",
                "narrators": ["Ava Voices"],
                "primary_narrator": "Ava Voices",
                "series": [{"name": "Great Saga", "sequence": "2", "label": "Great Saga #2"}],
                "series_label": "Great Saga #2",
                "publisher": "Recorded Books",
                "language": "English",
                "published_date": "2021-10-03",
                "asin": "B002TEST02",
                "codec": "mp3",
                "codec_mix": ["mp3"],
                "bitrate_kbps": 96.0,
                "channels": 2,
                "channel_layout": "stereo",
                "format": "MP3",
                "format_mix": ["MP3"],
                "size_mb": 300.0,
                "duration_hours": 16.8,
                "file_count": 12,
                "primary_filename": "Part01.mp3",
                "path": "/audiobooks/Bob Writer/Another Novel",
                "tier": "Low",
                "quality_score": 31.0,
                "upgrade_priority": 400,
                "upgrade_reason": "Already owned on Audible with better quality available.",
                "is_current_atmos": False,
                "owned_on_audible": True,
                "is_plus_catalog": False,
                "plus_expiration": None,
                "is_monthly_deal": False,
                "list_price": 14.99,
                "sale_price": None,
                "discount_percent": None,
                "is_good_deal": False,
                "has_atmos_upgrade": False,
                "audible_best_bitrate": 128,
                "audible_best_codec": "AAC-LC",
                "delta_kbps": 32.0,
                "acquisition_recommendation": "OWNED",
                "acquisition_label": "OWNED",
                "audible_url": "https://www.audible.com/pd/B002TEST02",
                "cover_image_url": None,
            },
            {
                "item_id": "abs-item-3",
                "title": "Cheap Thrills",
                "subtitle": "Budget Upgrade Cut",
                "author": "Sam Deal",
                "narrators": ["Sam Reader"],
                "primary_narrator": "Sam Reader",
                "series": [],
                "series_label": None,
                "publisher": "Audible Studios",
                "language": "English",
                "asin": "B003TEST03",
                "codec": "aac",
                "codec_mix": ["aac"],
                "bitrate_kbps": 80.0,
                "channels": 2,
                "channel_layout": "stereo",
                "format": "M4B",
                "format_mix": ["M4B"],
                "size_mb": 200.0,
                "duration_hours": 7.2,
                "file_count": 1,
                "primary_filename": "Cheap Thrills.m4b",
                "path": "/audiobooks/Sam Deal/Cheap Thrills",
                "tier": "Low",
                "quality_score": 24.7,
                "upgrade_priority": 500,
                "upgrade_reason": "Discounted upgrade with a strong bitrate jump.",
                "is_current_atmos": False,
                "owned_on_audible": False,
                "is_plus_catalog": False,
                "plus_expiration": None,
                "is_monthly_deal": False,
                "list_price": 8.99,
                "sale_price": 6.99,
                "discount_percent": 22.2,
                "is_good_deal": True,
                "has_atmos_upgrade": False,
                "audible_best_bitrate": 128,
                "audible_best_codec": "AAC-LC",
                "delta_kbps": 48.0,
                "acquisition_recommendation": "GOOD_DEAL",
                "acquisition_label": "GOOD_DEAL ($6.99, 22% off)",
                "audible_url": "https://www.audible.com/pd/B003TEST03",
                "cover_image_url": "https://m.media-amazon.com/images/I/test3.jpg",
            },
        ],
    }


@pytest.fixture()
def empty_upgrade_data() -> dict:
    """Empty upgrade data with no candidates."""
    return {
        "summary": {
            "total_candidates": 0,
            "plus_catalog_count": 0,
            "monthly_deals_count": 0,
            "good_deals_count": 0,
            "already_owned_count": 0,
            "atmos_available_count": 0,
        },
        "upgrade_candidates": [],
    }


@pytest.fixture()
def web_settings() -> WebSettings:
    """Web settings for testing."""
    return WebSettings(
        ssh_host="test-server.example.com",
        ssh_user="testuser",
        path="/var/www/html/dashboard/",
        host="test-server.example.com/dashboard/index.html",
    )


# ═══════════════════════════════════════════════════════════════════════
# DashboardGenerator Tests
# ═══════════════════════════════════════════════════════════════════════


class TestDashboardGenerator:
    """Tests for DashboardGenerator."""

    def test_render_produces_valid_html(self, sample_upgrade_data):
        """Test that render produces a complete HTML document."""
        generator = DashboardGenerator(sample_upgrade_data)
        html = generator.render()

        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "Audiobook Upgrade Dashboard" in html

    def test_render_contains_candidate_data(self, sample_upgrade_data):
        """Test that rendered HTML contains embedded candidate data."""
        generator = DashboardGenerator(sample_upgrade_data)
        html = generator.render()

        assert "The Great Book" in html
        assert "Jane Author" in html
        assert "Another Novel" in html

    def test_render_contains_chart(self, sample_upgrade_data):
        """Test that chart.js integration is present."""
        generator = DashboardGenerator(sample_upgrade_data)
        html = generator.render()

        assert "chart.js" in html
        assert "tierChart" in html

    def test_render_with_empty_candidates(self, empty_upgrade_data):
        """Test rendering with no upgrade candidates."""
        generator = DashboardGenerator(empty_upgrade_data)
        html = generator.render()

        assert "<!DOCTYPE html>" in html
        assert "0" in html  # Should show 0 counts

    def test_tier_distribution_computation(self, sample_upgrade_data):
        """Test that tier distribution is correctly computed."""
        generator = DashboardGenerator(sample_upgrade_data)
        dist = generator._compute_tier_distribution()

        assert dist["Poor"] == 1
        assert dist["Low"] == 2
        assert dist["Excellent"] == 0
        assert dist["Better"] == 0
        assert dist["Good"] == 0

    def test_format_distribution_computation(self, sample_upgrade_data):
        """Test that format distribution is correctly computed."""
        generator = DashboardGenerator(sample_upgrade_data)
        dist = generator._compute_format_distribution()

        assert dist["M4B"] == 2
        assert dist["MP3"] == 1

    def test_recommendation_counts(self, sample_upgrade_data):
        """Test that recommendation counts are correct."""
        generator = DashboardGenerator(sample_upgrade_data)
        counts = generator._compute_recommendation_counts()

        assert counts["FREE"] == 1
        assert counts["OWNED"] == 1
        assert counts["GOOD_DEAL"] == 1

    def test_max_delta_computation(self, sample_upgrade_data):
        """Test max delta computation for bar scaling."""
        generator = DashboardGenerator(sample_upgrade_data)
        max_delta = generator._compute_max_delta()

        assert max_delta == 64.0

    def test_max_delta_with_empty_data(self, empty_upgrade_data):
        """Test max delta returns 1.0 for empty data (avoids division by zero)."""
        generator = DashboardGenerator(empty_upgrade_data)
        max_delta = generator._compute_max_delta()

        assert max_delta == 1.0

    def test_signal_counts_and_series_clusters(self, sample_upgrade_data):
        """Signal counts and series clusters should reflect richer dashboard metadata."""
        generator = DashboardGenerator(sample_upgrade_data)

        signal_counts = generator._compute_signal_counts()
        series_clusters = generator._compute_series_clusters()

        assert signal_counts["series_linked_count"] == 2
        assert signal_counts["narrated_count"] == 3
        assert signal_counts["multi_file_count"] == 1
        assert signal_counts["epic_count"] == 1
        assert signal_counts["legacy_mp3_count"] == 1
        assert series_clusters[0]["label"] == "Great Saga"
        assert series_clusters[0]["count"] == 2

    def test_save_creates_file(self, sample_upgrade_data, tmp_path):
        """Test that save writes an HTML file to disk."""
        generator = DashboardGenerator(sample_upgrade_data)
        output_path = tmp_path / "dashboard.html"

        result = generator.save(output_path)

        assert result == output_path
        assert output_path.exists()
        content = output_path.read_text()
        assert "<!DOCTYPE html>" in content
        assert len(content) > 1000

    def test_save_creates_parent_dirs(self, sample_upgrade_data, tmp_path):
        """Test that save creates parent directories if missing."""
        generator = DashboardGenerator(sample_upgrade_data)
        output_path = tmp_path / "nested" / "dir" / "dashboard.html"

        generator.save(output_path)

        assert output_path.exists()

    def test_cover_images_in_html(self, sample_upgrade_data):
        """Test that cover image URLs appear in rendered HTML."""
        generator = DashboardGenerator(sample_upgrade_data)
        html = generator.render()

        assert "test1.jpg" in html
        assert "test3.jpg" in html

    def test_audible_links_in_html(self, sample_upgrade_data):
        """Test that Audible URLs appear in rendered HTML."""
        generator = DashboardGenerator(sample_upgrade_data)
        html = generator.render()

        assert "B001TEST01" in html
        assert "B002TEST02" in html

    def test_render_contains_richer_metadata(self, sample_upgrade_data):
        """Test that additional audiobook metadata is embedded for the dashboard UI."""
        generator = DashboardGenerator(sample_upgrade_data)
        html = generator.render()

        assert "The Great Book.m4b" in html
        assert "Very low bitrate with a major Audible improvement available." in html
        assert "stereo" in html
        assert "Archive Edition" in html
        assert "Great Saga #1" in html
        assert "Ava Voices" in html

    def test_render_contains_signal_sections(self, sample_upgrade_data):
        """Advanced dashboard sections should render when metadata is available."""
        generator = DashboardGenerator(sample_upgrade_data)
        html = generator.render()

        assert "Metadata Signals" in html
        assert "Series Radar" in html
        assert "Narrator Heatmap" in html
        assert "detailDrawer" in html
        assert "cover-thumb" in html
        assert "drawerContent.scrollTop = 0;" in html
        assert "--nav-height: 56px;" in html

    def test_stat_cards_show_summary(self, sample_upgrade_data):
        """Test that hero stat cards reflect summary data."""
        generator = DashboardGenerator(sample_upgrade_data)
        html = generator.render()

        # Total candidates (stat values use data-count for animation)
        assert 'data-count="3"' in html


# ═══════════════════════════════════════════════════════════════════════
# deploy_dashboard Tests
# ═══════════════════════════════════════════════════════════════════════


class TestDeployDashboard:
    """Tests for deploy_dashboard."""

    def test_scp_command_construction(self, web_settings, tmp_path):
        """Test that SCP is called with correct arguments."""
        html_file = tmp_path / "dashboard.html"
        html_file.write_text("<html></html>")

        with patch("src.web.dashboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            deploy_dashboard(html_file, web_settings)

            # mkdir -p SSH call + SCP call = 2 calls
            assert mock_run.call_count == 2
            scp_call = mock_run.call_args_list[1]
            cmd = scp_call[0][0]

            assert cmd[0] == "scp"
            assert str(html_file) in cmd
            assert "testuser@test-server.example.com:/var/www/html/dashboard/index.html" in cmd

    def test_returns_public_url(self, web_settings, tmp_path):
        """Test that deploy returns the public URL."""
        html_file = tmp_path / "dashboard.html"
        html_file.write_text("<html></html>")

        with patch("src.web.dashboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            url = deploy_dashboard(html_file, web_settings)

            assert url == "https://test-server.example.com/dashboard/index.html"

    def test_scp_failure_raises_deployment_error(self, web_settings, tmp_path):
        """Test that SCP failure raises DeploymentError."""
        html_file = tmp_path / "dashboard.html"
        html_file.write_text("<html></html>")

        with patch("src.web.dashboard.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "scp", stderr="Permission denied")

            with pytest.raises(DeploymentError, match="SCP failed"):
                deploy_dashboard(html_file, web_settings)

    def test_missing_config_raises_deployment_error(self, tmp_path, monkeypatch):
        """Test that missing config raises DeploymentError."""
        monkeypatch.delenv("WEB_SERVER_SSH_HOST", raising=False)
        monkeypatch.delenv("WEB_SERVER_SSH_USER", raising=False)
        monkeypatch.delenv("WEB_SERVER_PATH", raising=False)
        monkeypatch.delenv("WEB_SERVER_HOST", raising=False)

        html_file = tmp_path / "dashboard.html"
        html_file.write_text("<html></html>")
        empty_settings = WebSettings()

        with pytest.raises(DeploymentError, match="not fully configured"):
            deploy_dashboard(html_file, empty_settings)

    @pytest.mark.parametrize(
        ("settings", "message"),
        [
            (
                WebSettings(
                    ssh_host="bad host;rm -rf /",
                    ssh_user="deploy",
                    path="/var/www/html/dashboard",
                    host="test-server.example.com/dashboard/index.html",
                ),
                "WEB_SERVER_SSH_HOST contains unsupported characters",
            ),
            (
                WebSettings(
                    ssh_host="test-server.example.com",
                    ssh_user="deploy",
                    path="/var/www/../etc/dashboard",
                    host="test-server.example.com/dashboard/index.html",
                ),
                "WEB_SERVER_PATH must not contain parent-directory traversal",
            ),
        ],
    )
    def test_invalid_deploy_target_raises_before_subprocess(self, settings, message, tmp_path):
        """Invalid SSH deployment settings should fail before any subprocess call is attempted."""
        html_file = tmp_path / "dashboard.html"
        html_file.write_text("<html></html>")

        with patch("src.web.dashboard.subprocess.run") as mock_run:
            with pytest.raises(DeploymentError, match=message):
                deploy_dashboard(html_file, settings)

            mock_run.assert_not_called()

    def test_scp_timeout_raises_deployment_error(self, web_settings, tmp_path):
        """Test that SCP timeout raises DeploymentError."""
        html_file = tmp_path / "dashboard.html"
        html_file.write_text("<html></html>")

        with patch("src.web.dashboard.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("scp", 30)

            with pytest.raises(DeploymentError, match="timed out"):
                deploy_dashboard(html_file, web_settings)

    def test_missing_html_file_raises_deployment_error(self, web_settings, tmp_path):
        """Deployment should fail clearly when the local dashboard file is missing."""
        missing_html = tmp_path / "missing-dashboard.html"

        with pytest.raises(DeploymentError, match="Dashboard file not found"):
            deploy_dashboard(missing_html, web_settings)


# ═══════════════════════════════════════════════════════════════════════
# WebSettings Tests
# ═══════════════════════════════════════════════════════════════════════


class TestWebSettings:
    """Tests for WebSettings configuration."""

    def test_defaults_are_none(self, monkeypatch):
        """Test that all WebSettings fields default to None."""
        monkeypatch.delenv("WEB_SERVER_SSH_HOST", raising=False)
        monkeypatch.delenv("WEB_SERVER_SSH_USER", raising=False)
        monkeypatch.delenv("WEB_SERVER_PATH", raising=False)
        monkeypatch.delenv("WEB_SERVER_HOST", raising=False)

        settings = WebSettings()
        assert settings.ssh_host is None
        assert settings.ssh_user is None
        assert settings.path is None
        assert settings.host is None

    def test_from_env_vars(self, monkeypatch):
        """Test that WebSettings loads from environment variables."""
        monkeypatch.setenv("WEB_SERVER_SSH_HOST", "my-server.com")
        monkeypatch.setenv("WEB_SERVER_SSH_USER", "deploy")
        monkeypatch.setenv("WEB_SERVER_PATH", "/var/www/")
        monkeypatch.setenv("WEB_SERVER_HOST", "my-server.com/dashboard/index.html")

        settings = WebSettings()
        assert settings.ssh_host == "my-server.com"
        assert settings.ssh_user == "deploy"
        assert settings.path == "/var/www/"
        assert settings.host == "my-server.com/dashboard/index.html"
