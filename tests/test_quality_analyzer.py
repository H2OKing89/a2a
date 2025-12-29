"""Tests for quality analyzer."""

import pytest
from pydantic import ValidationError

from src.quality.analyzer import QualityAnalyzer
from src.quality.models import FormatRank, QualityTier


class TestQualityAnalyzer:
    """Tests for QualityAnalyzer class."""

    def test_analyzer_initialization(self):
        """Test analyzer initializes with default thresholds."""
        analyzer = QualityAnalyzer()
        assert analyzer.bitrate_excellent == 256
        assert analyzer.bitrate_good == 128
        assert analyzer.bitrate_acceptable == 110
        assert analyzer.bitrate_low == 64

    def test_analyzer_custom_threshold(self):
        """Test analyzer accepts custom thresholds."""
        analyzer = QualityAnalyzer(bitrate_acceptable=96)
        assert analyzer.bitrate_acceptable == 96

    def test_analyze_item_extracts_bitrate(self, sample_library_item):
        """Test that analyze_item extracts bitrate from item."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze_item(sample_library_item)

        assert result.bitrate_kbps == 128
        assert result.asin == "B0TEST12345"
        assert result.title == "Test Audiobook"
        assert result.author == "Test Author"

    def test_analyze_item_without_audio_files(self):
        """Test handling item without audio files."""
        analyzer = QualityAnalyzer()
        item = {
            "id": "test-123",
            "media": {"audioFiles": [], "metadata": {"title": "Empty Book", "asin": None}},
        }
        result = analyzer.analyze_item(item)

        assert result.bitrate_kbps == 0

    # ========================================================================
    # Negative Path / Error Handling Tests
    # ========================================================================

    def test_analyze_item_missing_media_key(self):
        """Test handling item with missing 'media' key."""
        analyzer = QualityAnalyzer()
        item = {
            "id": "test-123",
            # Missing 'media' key entirely
        }
        result = analyzer.analyze_item(item)

        # Should handle gracefully with defaults
        assert result.bitrate_kbps == 0
        assert result.title == "Unknown"
        assert result.asin is None

    def test_analyze_item_media_is_none(self):
        """Test handling item where media is None - should raise AttributeError."""
        analyzer = QualityAnalyzer()
        item = {
            "id": "test-456",
            "media": None,
        }

        # Analyzer doesn't handle None media - should raise AttributeError
        with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'get'"):
            analyzer.analyze_item(item)

    def test_analyze_item_missing_metadata(self):
        """Test handling item with missing media.metadata."""
        analyzer = QualityAnalyzer()
        item = {
            "id": "test-789",
            "media": {
                "audioFiles": [],
                # Missing 'metadata' key
            },
        }
        result = analyzer.analyze_item(item)

        assert result.title == "Unknown"
        assert result.author is None
        assert result.asin is None

    def test_analyze_item_malformed_audio_file_missing_bitrate(self):
        """Test handling audio file with missing bitRate field."""
        analyzer = QualityAnalyzer()
        item = {
            "id": "test-malformed",
            "media": {
                "metadata": {"title": "Malformed Book", "asin": "B0MALFORM1"},
                "audioFiles": [
                    {
                        "ino": "123",
                        "metadata": {"filename": "test.m4b"},
                        "duration": 3600,
                        "codec": "aac",
                        "channels": 2,
                        # Missing 'bitRate' field
                    }
                ],
            },
        }
        result = analyzer.analyze_item(item)

        # Should default to 0 when bitRate is missing
        assert result.bitrate_kbps == 0
        assert result.title == "Malformed Book"

    def test_analyze_item_malformed_audio_file_missing_codec(self):
        """Test handling audio file with missing codec field."""
        analyzer = QualityAnalyzer()
        item = {
            "id": "test-no-codec",
            "media": {
                "metadata": {"title": "No Codec Book"},
                "audioFiles": [
                    {
                        "metadata": {"filename": "test.m4b"},
                        "duration": 3600,
                        "bitRate": 128000,
                        "channels": 2,
                        # Missing 'codec' field
                    }
                ],
            },
        }
        result = analyzer.analyze_item(item)

        # Should default codec to "unknown"
        assert result.codec == "unknown"
        assert result.bitrate_kbps == 128

    def test_analyze_item_malformed_audio_file_missing_channels(self):
        """Test handling audio file with missing channels field."""
        analyzer = QualityAnalyzer()
        item = {
            "id": "test-no-channels",
            "media": {
                "metadata": {"title": "No Channels Book"},
                "audioFiles": [
                    {
                        "metadata": {"filename": "test.m4b"},
                        "duration": 3600,
                        "bitRate": 128000,
                        "codec": "aac",
                        # Missing 'channels' field
                    }
                ],
            },
        }
        result = analyzer.analyze_item(item)

        # Should default channels to 2
        assert result.channels == 2
        assert result.bitrate_kbps == 128

    def test_analyze_item_negative_bitrate(self):
        """Test handling audio file with negative bitrate value."""
        analyzer = QualityAnalyzer()
        item = {
            "id": "test-negative",
            "media": {
                "metadata": {"title": "Negative Bitrate Book"},
                "audioFiles": [
                    {
                        "metadata": {"filename": "test.m4b"},
                        "duration": 3600,
                        "bitRate": -128000,  # Invalid negative value
                        "codec": "aac",
                        "channels": 2,
                    }
                ],
            },
        }
        result = analyzer.analyze_item(item)

        # Negative bitrate converted to kbps should be negative
        # Analyzer should handle this (likely tier=POOR)
        assert result.bitrate_kbps == -128
        assert result.tier == QualityTier.POOR

    def test_analyze_item_extremely_large_bitrate(self):
        """Test handling audio file with unrealistically large bitrate."""
        analyzer = QualityAnalyzer()
        item = {
            "id": "test-huge",
            "media": {
                "metadata": {"title": "Huge Bitrate Book"},
                "audioFiles": [
                    {
                        "metadata": {"filename": "test.m4b"},
                        "duration": 3600,
                        "bitRate": 99999999000,  # Unrealistically large (99,999,999 kbps)
                        "codec": "aac",
                        "channels": 2,
                    }
                ],
            },
        }
        result = analyzer.analyze_item(item)

        # Should still calculate tier (EXCELLENT for very high bitrate)
        assert result.bitrate_kbps == 99999999
        assert result.tier == QualityTier.EXCELLENT

    def test_analyze_item_zero_bitrate(self):
        """Test handling audio file with zero bitrate."""
        analyzer = QualityAnalyzer()
        item = {
            "id": "test-zero",
            "media": {
                "metadata": {"title": "Zero Bitrate Book"},
                "audioFiles": [
                    {
                        "metadata": {"filename": "test.m4b"},
                        "duration": 3600,
                        "bitRate": 0,  # Zero bitrate
                        "codec": "aac",
                        "channels": 2,
                    }
                ],
            },
        }
        result = analyzer.analyze_item(item)

        assert result.bitrate_kbps == 0
        assert result.tier == QualityTier.POOR

    def test_analyze_item_null_codec(self):
        """Test handling audio file with None/null codec - should raise ValidationError."""
        analyzer = QualityAnalyzer()
        item = {
            "id": "test-null-codec",
            "media": {
                "metadata": {"title": "Null Codec Book"},
                "audioFiles": [
                    {
                        "metadata": {"filename": "test.m4b"},
                        "duration": 3600,
                        "bitRate": 128000,
                        "codec": None,  # Null codec
                        "channels": 2,
                    }
                ],
            },
        }

        # Codec field is now nullable, so None is allowed
        # Should not raise ValidationError
        result = analyzer.analyze_item(item)
        assert result is not None
        assert result.codec is None  # Codec should be None

    def test_analyze_item_null_channels(self):
        """Test handling audio file with None/null channels - should raise ValidationError."""
        analyzer = QualityAnalyzer()
        item = {
            "id": "test-null-channels",
            "media": {
                "metadata": {"title": "Null Channels Book"},
                "audioFiles": [
                    {
                        "metadata": {"filename": "test.m4b"},
                        "duration": 3600,
                        "bitRate": 128000,
                        "codec": "aac",
                        "channels": None,  # Null channels
                    }
                ],
            },
        }

        # Pydantic model requires channels to be an int, not None
        # Should raise ValidationError
        with pytest.raises(ValidationError):
            analyzer.analyze_item(item)

    def test_analyze_item_zero_duration_weighted_average(self):
        """Test bitrate calculation with zero total duration."""
        analyzer = QualityAnalyzer()
        item = {
            "id": "test-zero-duration",
            "media": {
                "metadata": {"title": "Zero Duration Book"},
                "audioFiles": [
                    {
                        "metadata": {"filename": "test.m4b"},
                        "duration": 0,  # Zero duration
                        "bitRate": 128000,
                        "codec": "aac",
                        "channels": 2,
                    }
                ],
            },
        }
        result = analyzer.analyze_item(item)

        # Should fallback to first file's bitrate when total_duration is 0
        assert result.bitrate_kbps == 128

    def test_is_atmos_true(self):
        """Test Atmos detection for EAC3 with surround."""
        analyzer = QualityAnalyzer()
        assert analyzer.is_atmos("eac3", 6) is True
        assert analyzer.is_atmos("truehd", 8) is True

    def test_is_atmos_false(self):
        """Test non-Atmos codecs."""
        analyzer = QualityAnalyzer()
        assert analyzer.is_atmos("aac", 2) is False
        assert analyzer.is_atmos("mp3", 2) is False
        assert analyzer.is_atmos("eac3", 2) is False  # Not enough channels

    def test_calculate_tier_excellent(self):
        """Test excellent tier classification."""
        analyzer = QualityAnalyzer()
        tier = analyzer.calculate_tier(bitrate_kbps=320, format_rank=FormatRank.M4B, is_atmos=False)
        assert tier == QualityTier.EXCELLENT

    def test_calculate_tier_good(self):
        """Test better tier classification (was good)."""
        analyzer = QualityAnalyzer()
        tier = analyzer.calculate_tier(bitrate_kbps=160, format_rank=FormatRank.M4B, is_atmos=False)
        assert tier == QualityTier.BETTER

    def test_calculate_tier_acceptable(self):
        """Test good tier classification (was acceptable)."""
        analyzer = QualityAnalyzer()
        tier = analyzer.calculate_tier(bitrate_kbps=115, format_rank=FormatRank.M4B, is_atmos=False)
        assert tier == QualityTier.GOOD

    def test_calculate_tier_low(self):
        """Test low tier classification."""
        analyzer = QualityAnalyzer()
        tier = analyzer.calculate_tier(bitrate_kbps=80, format_rank=FormatRank.M4B, is_atmos=False)
        assert tier == QualityTier.LOW

    def test_calculate_tier_poor(self):
        """Test poor tier classification."""
        analyzer = QualityAnalyzer()
        tier = analyzer.calculate_tier(bitrate_kbps=32, format_rank=FormatRank.MP3, is_atmos=False)
        assert tier == QualityTier.POOR

    def test_atmos_always_excellent(self):
        """Test that Atmos content is always excellent tier."""
        analyzer = QualityAnalyzer()
        # Even with low bitrate, Atmos should be excellent
        tier = analyzer.calculate_tier(bitrate_kbps=64, format_rank=FormatRank.M4B, is_atmos=True)
        assert tier == QualityTier.EXCELLENT

    def test_mp3_stricter_tiers(self):
        """Test that MP3 is rated more strictly than M4B."""
        analyzer = QualityAnalyzer()

        # Same bitrate (160kbps), different formats
        m4b_tier = analyzer.calculate_tier(160, FormatRank.M4B, False)
        mp3_tier = analyzer.calculate_tier(160, FormatRank.MP3, False)

        # M4B should be BETTER, MP3 should be GOOD
        assert m4b_tier == QualityTier.BETTER
        assert mp3_tier == QualityTier.GOOD
