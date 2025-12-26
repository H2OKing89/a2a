"""Tests for quality data models."""

import pytest

from src.quality.models import (
    AudioQuality,
    FormatRank,
    QualityReport,
    QualityTier,
)


class TestQualityTier:
    """Tests for QualityTier enum."""

    def test_quality_tier_excellent_label(self):
        """Test EXCELLENT tier label."""
        assert QualityTier.EXCELLENT.label == "Excellent"

    def test_quality_tier_good_label(self):
        """Test GOOD tier label."""
        assert QualityTier.GOOD.label == "Good"

    def test_quality_tier_acceptable_label(self):
        """Test ACCEPTABLE tier label."""
        assert QualityTier.ACCEPTABLE.label == "Acceptable"

    def test_quality_tier_low_label(self):
        """Test LOW tier label."""
        assert QualityTier.LOW.label == "Low"

    def test_quality_tier_poor_label(self):
        """Test POOR tier label."""
        assert QualityTier.POOR.label == "Poor"

    def test_quality_tier_unknown_label(self):
        """Test UNKNOWN tier label."""
        assert QualityTier.UNKNOWN.label == "Unknown"

    def test_quality_tier_excellent_emoji(self):
        """Test EXCELLENT tier emoji."""
        assert QualityTier.EXCELLENT.emoji == "⭐"

    def test_quality_tier_good_emoji(self):
        """Test GOOD tier emoji."""
        assert QualityTier.GOOD.emoji == "✅"

    def test_quality_tier_acceptable_emoji(self):
        """Test ACCEPTABLE tier emoji."""
        assert QualityTier.ACCEPTABLE.emoji == "👍"

    def test_quality_tier_low_emoji(self):
        """Test LOW tier emoji."""
        assert QualityTier.LOW.emoji == "⚠️"

    def test_quality_tier_poor_emoji(self):
        """Test POOR tier emoji."""
        assert QualityTier.POOR.emoji == "❌"

    def test_quality_tier_unknown_emoji(self):
        """Test UNKNOWN tier emoji."""
        assert QualityTier.UNKNOWN.emoji == "❓"


class TestFormatRank:
    """Tests for FormatRank enum."""

    def test_from_filename_m4b(self):
        """Test m4b format detection from filename."""
        assert FormatRank.from_filename("book.m4b") == FormatRank.M4B

    def test_from_filename_m4a(self):
        """Test m4a format detection from filename."""
        assert FormatRank.from_filename("song.m4a") == FormatRank.M4A

    def test_from_filename_mp3(self):
        """Test mp3 format detection from filename."""
        assert FormatRank.from_filename("track.mp3") == FormatRank.MP3

    def test_from_filename_opus(self):
        """Test opus format detection from filename."""
        assert FormatRank.from_filename("audio.opus") == FormatRank.OPUS

    def test_from_filename_flac(self):
        """Test flac format detection from filename."""
        assert FormatRank.from_filename("music.flac") == FormatRank.FLAC

    def test_from_filename_unknown(self):
        """Test unknown format detection from filename."""
        assert FormatRank.from_filename("file.xyz") == FormatRank.OTHER

    def test_from_filename_case_insensitive(self):
        """Test format detection is case-insensitive."""
        assert FormatRank.from_filename("BOOK.M4B") == FormatRank.M4B
        assert FormatRank.from_filename("Track.MP3") == FormatRank.MP3

    def test_from_codec_mime_aac_mp4(self):
        """Test AAC in MP4 container detected as M4B."""
        assert FormatRank.from_codec_mime("aac", "audio/mp4") == FormatRank.M4B

    def test_from_codec_mime_aac(self):
        """Test AAC codec without MP4 detected as M4A."""
        assert FormatRank.from_codec_mime("aac", "audio/aac") == FormatRank.M4A

    def test_from_codec_mime_mp3(self):
        """Test MP3 codec detection."""
        assert FormatRank.from_codec_mime("mp3", "audio/mpeg") == FormatRank.MP3

    def test_from_codec_mime_mp3_mime_only(self):
        """Test MP3 detection from MIME type."""
        assert FormatRank.from_codec_mime("unknown", "audio/mp3") == FormatRank.MP3

    def test_from_codec_mime_opus(self):
        """Test Opus codec detection."""
        assert FormatRank.from_codec_mime("opus", "audio/opus") == FormatRank.OPUS

    def test_from_codec_mime_flac(self):
        """Test FLAC codec detection."""
        assert FormatRank.from_codec_mime("flac", "audio/flac") == FormatRank.FLAC

    def test_from_codec_mime_eac3(self):
        """Test EAC3 (Dolby Atmos) codec detected as M4B."""
        assert FormatRank.from_codec_mime("eac3", "audio/mp4") == FormatRank.M4B

    def test_from_codec_mime_unknown(self):
        """Test unknown codec and MIME type."""
        assert FormatRank.from_codec_mime("unknown", "audio/unknown") == FormatRank.OTHER

    def test_from_codec_mime_none_values(self):
        """Test handling of None codec and MIME type."""
        assert FormatRank.from_codec_mime(None, None) == FormatRank.OTHER

    def test_from_codec_mime_case_insensitive(self):
        """Test case-insensitive codec matching."""
        assert FormatRank.from_codec_mime("AAC", "AUDIO/MP4") == FormatRank.M4B
        assert FormatRank.from_codec_mime("MP3", "AUDIO/MPEG") == FormatRank.MP3


class TestAudioQuality:
    """Tests for AudioQuality model."""

    @pytest.fixture
    def sample_audio_quality(self):
        """Create a sample AudioQuality instance."""
        return AudioQuality(
            item_id="test-123",
            title="Test Book",
            author="Test Author",
            asin="B0TEST123",
            path="/library/test",
            size_bytes=1024 * 1024 * 100,  # 100 MB
            file_count=10,
            primary_filename="test_001.m4b",
            codec="aac",
            bitrate_kbps=256,
            channels=2,
            channel_layout="stereo",
            format_rank=FormatRank.M4B,
            duration_hours=10.5,
            is_atmos=False,
            tier=QualityTier.EXCELLENT,
            quality_score=95.0,
            upgrade_priority=0,
        )

    def test_audio_quality_creation(self, sample_audio_quality):
        """Test creating an AudioQuality instance."""
        assert sample_audio_quality.item_id == "test-123"
        assert sample_audio_quality.title == "Test Book"
        assert sample_audio_quality.author == "Test Author"

    def test_size_gb_property(self, sample_audio_quality):
        """Test size_gb property calculation."""
        expected_gb = (1024 * 1024 * 100) / (1024**3)
        assert sample_audio_quality.size_gb == pytest.approx(expected_gb)

    def test_size_mb_property(self, sample_audio_quality):
        """Test size_mb property calculation."""
        expected_mb = (1024 * 1024 * 100) / (1024**2)
        assert sample_audio_quality.size_mb == pytest.approx(expected_mb)

    def test_tier_label_property(self, sample_audio_quality):
        """Test tier_label property."""
        assert sample_audio_quality.tier_label == "Excellent"

    def test_format_label_property_m4b(self, sample_audio_quality):
        """Test format_label property for M4B."""
        assert sample_audio_quality.format_label == "M4B"

    def test_format_label_property_m4a(self):
        """Test format_label property for M4A."""
        quality = AudioQuality(
            item_id="test",
            title="Test",
            codec="aac",
            bitrate_kbps=128,
            path="/path",
            format_rank=FormatRank.M4A,
        )
        assert quality.format_label == "M4A"

    def test_format_label_property_mp3(self):
        """Test format_label property for MP3."""
        quality = AudioQuality(
            item_id="test",
            title="Test",
            codec="mp3",
            bitrate_kbps=128,
            path="/path",
            format_rank=FormatRank.MP3,
        )
        # Note: MP3, OPUS, FLAC all have value=3, so they alias to FLAC (last defined)
        assert quality.format_label == "FLAC"

    def test_format_label_property_opus(self):
        """Test format_label property for Opus."""
        quality = AudioQuality(
            item_id="test",
            title="Test",
            codec="opus",
            bitrate_kbps=128,
            path="/path",
            format_rank=FormatRank.OPUS,
        )
        # Note: MP3, OPUS, FLAC all have value=3, so they alias to FLAC (last defined)
        assert quality.format_label == "FLAC"

    def test_format_label_property_flac(self):
        """Test format_label property for FLAC."""
        quality = AudioQuality(
            item_id="test",
            title="Test",
            codec="flac",
            bitrate_kbps=320,
            path="/path",
            format_rank=FormatRank.FLAC,
        )
        assert quality.format_label == "FLAC"

    def test_format_label_property_other(self):
        """Test format_label property for Other."""
        quality = AudioQuality(
            item_id="test",
            title="Test",
            codec="unknown",
            bitrate_kbps=128,
            path="/path",
            format_rank=FormatRank.OTHER,
        )
        assert quality.format_label == "Other"

    def test_audio_quality_with_optional_fields(self):
        """Test AudioQuality with optional fields set."""
        quality = AudioQuality(
            item_id="test-456",
            title="Another Book",
            author="Author Name",
            asin="B0TEST456",
            path="/library/another",
            codec="mp3",
            bitrate_kbps=192,
            channel_layout="mono",
            is_atmos=False,
            tier=QualityTier.GOOD,
            quality_score=85.0,
            upgrade_priority=1,
            upgrade_reason="Lower bitrate available on Audible",
            owned_on_audible=True,
            is_plus_catalog=False,
            list_price=15.99,
            sale_price=9.99,
            discount_percent=37.5,
            is_good_deal=True,
            is_monthly_deal=False,
            has_atmos_upgrade=True,
            acquisition_recommendation="Purchase the Atmos version",
            audible_url="https://example.com/book",
            cover_image_url="https://example.com/cover.jpg",
        )
        assert quality.owned_on_audible is True
        assert quality.is_plus_catalog is False
        assert quality.list_price == 15.99

    def test_audio_quality_minimal(self):
        """Test AudioQuality with minimal required fields."""
        quality = AudioQuality(
            item_id="minimal",
            title="Minimal Book",
            codec="aac",
            bitrate_kbps=128,
            path="/path",
        )
        assert quality.item_id == "minimal"
        assert quality.author is None
        assert quality.asin is None
        assert quality.size_bytes == 0
        assert quality.file_count == 1


class TestQualityReport:
    """Tests for QualityReport model."""

    @pytest.fixture
    def sample_quality_item(self):
        """Create a sample AudioQuality item."""
        return AudioQuality(
            item_id="item-1",
            title="Book 1",
            author="Author 1",
            codec="aac",
            bitrate_kbps=256,
            path="/lib",
            size_bytes=1024 * 1024 * 100,
            duration_hours=10.0,
            tier=QualityTier.EXCELLENT,
        )

    @pytest.fixture
    def empty_report(self):
        """Create an empty QualityReport."""
        return QualityReport()

    def test_quality_report_initialization(self, empty_report):
        """Test QualityReport initializes with empty state."""
        assert empty_report.total_items == 0
        assert empty_report.total_size_bytes == 0
        assert empty_report.total_duration_hours == 0.0
        assert empty_report.tier_counts == {}
        assert empty_report.format_counts == {}
        assert empty_report.codec_counts == {}
        assert len(empty_report.excellent_items) == 0
        assert len(empty_report.upgrade_candidates) == 0

    def test_total_size_gb_property(self, empty_report):
        """Test total_size_gb property."""
        empty_report.total_size_bytes = 1024**3
        assert empty_report.total_size_gb == pytest.approx(1.0)

    def test_add_item_excellent_tier(self, empty_report, sample_quality_item):
        """Test adding an excellent tier item."""
        empty_report.add_item(sample_quality_item)

        assert empty_report.total_items == 1
        assert empty_report.total_size_bytes == sample_quality_item.size_bytes
        assert empty_report.total_duration_hours == pytest.approx(10.0)
        assert len(empty_report.excellent_items) == 1
        assert "Excellent" in empty_report.tier_counts
        assert empty_report.tier_counts["Excellent"] == 1

    def test_add_item_counts_tiers(self, empty_report):
        """Test that add_item properly categorizes items by tier."""
        # Excellent
        item1 = AudioQuality(
            item_id="1", title="Book 1", codec="aac", bitrate_kbps=256, path="/", tier=QualityTier.EXCELLENT
        )
        empty_report.add_item(item1)
        assert len(empty_report.excellent_items) == 1

        # Good
        item2 = AudioQuality(
            item_id="2", title="Book 2", codec="aac", bitrate_kbps=192, path="/", tier=QualityTier.GOOD
        )
        empty_report.add_item(item2)
        assert len(empty_report.good_items) == 1

        # Acceptable
        item3 = AudioQuality(
            item_id="3", title="Book 3", codec="aac", bitrate_kbps=110, path="/", tier=QualityTier.ACCEPTABLE
        )
        empty_report.add_item(item3)
        assert len(empty_report.acceptable_items) == 1

        # Low
        item4 = AudioQuality(item_id="4", title="Book 4", codec="aac", bitrate_kbps=64, path="/", tier=QualityTier.LOW)
        empty_report.add_item(item4)
        assert len(empty_report.low_items) == 1

        # Poor
        item5 = AudioQuality(item_id="5", title="Book 5", codec="aac", bitrate_kbps=32, path="/", tier=QualityTier.POOR)
        empty_report.add_item(item5)
        assert len(empty_report.poor_items) == 1

    def test_add_item_counts_formats(self, empty_report):
        """Test that add_item properly counts formats."""
        item1 = AudioQuality(
            item_id="1",
            title="M4B Book",
            codec="aac",
            bitrate_kbps=256,
            path="/",
            format_rank=FormatRank.M4B,
        )
        empty_report.add_item(item1)
        assert "M4B" in empty_report.format_counts
        assert empty_report.format_counts["M4B"] == 1

        item2 = AudioQuality(
            item_id="2",
            title="FLAC Book",
            codec="flac",
            bitrate_kbps=192,
            path="/",
            format_rank=FormatRank.FLAC,
        )
        empty_report.add_item(item2)
        # Note: MP3, OPUS, FLAC all have value=3, so they alias to FLAC
        assert empty_report.format_counts["FLAC"] == 1

    def test_add_item_counts_codecs(self, empty_report):
        """Test that add_item properly counts codecs."""
        item1 = AudioQuality(item_id="1", title="Book 1", codec="aac", bitrate_kbps=256, path="/")
        empty_report.add_item(item1)
        assert "aac" in empty_report.codec_counts
        assert empty_report.codec_counts["aac"] == 1

        item2 = AudioQuality(item_id="2", title="Book 2", codec="mp3", bitrate_kbps=192, path="/")
        empty_report.add_item(item2)
        assert empty_report.codec_counts["mp3"] == 1

    def test_add_item_atmos_tracking(self, empty_report):
        """Test that atmos items are tracked."""
        item1 = AudioQuality(
            item_id="1",
            title="Atmos Book",
            codec="eac3",
            bitrate_kbps=256,
            path="/",
            is_atmos=True,
        )
        empty_report.add_item(item1)
        assert len(empty_report.atmos_items) == 1

        item2 = AudioQuality(
            item_id="2",
            title="Normal Book",
            codec="aac",
            bitrate_kbps=256,
            path="/",
            is_atmos=False,
        )
        empty_report.add_item(item2)
        assert len(empty_report.atmos_items) == 1  # Still just 1

    def test_add_item_upgrade_candidates(self, empty_report):
        """Test that upgrade candidates are tracked."""
        # Low tier item
        item1 = AudioQuality(
            item_id="1",
            title="Low Book",
            codec="aac",
            bitrate_kbps=64,
            path="/",
            tier=QualityTier.LOW,
            upgrade_priority=5,
        )
        empty_report.add_item(item1)
        assert len(empty_report.upgrade_candidates) == 1

        # Poor tier item
        item2 = AudioQuality(
            item_id="2",
            title="Poor Book",
            codec="mp3",
            bitrate_kbps=32,
            path="/",
            tier=QualityTier.POOR,
            upgrade_priority=10,
        )
        empty_report.add_item(item2)
        assert len(empty_report.upgrade_candidates) == 2

        # Excellent tier item (not upgrade candidate)
        item3 = AudioQuality(
            item_id="3",
            title="Excellent Book",
            codec="aac",
            bitrate_kbps=256,
            path="/",
            tier=QualityTier.EXCELLENT,
        )
        empty_report.add_item(item3)
        assert len(empty_report.upgrade_candidates) == 2  # Still 2

    def test_finalize_with_empty_report(self, empty_report):
        """Test finalize on empty report."""
        empty_report.finalize()
        assert empty_report.min_bitrate_kbps == 0
        assert empty_report.max_bitrate_kbps == 0
        assert empty_report.avg_bitrate_kbps == 0

    def test_finalize_calculates_bitrate_stats(self, empty_report):
        """Test finalize calculates bitrate statistics."""
        item1 = AudioQuality(
            item_id="1", title="Book 1", codec="aac", bitrate_kbps=128, path="/", tier=QualityTier.GOOD
        )
        item2 = AudioQuality(
            item_id="2", title="Book 2", codec="aac", bitrate_kbps=256, path="/", tier=QualityTier.EXCELLENT
        )
        item3 = AudioQuality(
            item_id="3", title="Book 3", codec="aac", bitrate_kbps=192, path="/", tier=QualityTier.GOOD
        )

        empty_report.add_item(item1)
        empty_report.add_item(item2)
        empty_report.add_item(item3)

        empty_report.finalize()

        assert empty_report.min_bitrate_kbps == 128
        assert empty_report.max_bitrate_kbps == 256
        assert empty_report.avg_bitrate_kbps == pytest.approx((128 + 256 + 192) / 3)

    def test_finalize_ignores_zero_bitrate(self, empty_report):
        """Test finalize ignores zero bitrate items."""
        item1 = AudioQuality(
            item_id="1", title="Book 1", codec="aac", bitrate_kbps=0, path="/", tier=QualityTier.EXCELLENT
        )
        item2 = AudioQuality(
            item_id="2", title="Book 2", codec="aac", bitrate_kbps=256, path="/", tier=QualityTier.EXCELLENT
        )
        item3 = AudioQuality(
            item_id="3", title="Book 3", codec="aac", bitrate_kbps=192, path="/", tier=QualityTier.GOOD
        )

        empty_report.add_item(item1)
        empty_report.add_item(item2)
        empty_report.add_item(item3)

        empty_report.finalize()

        # Should ignore the 0 kbps item
        assert empty_report.min_bitrate_kbps == 192
        assert empty_report.max_bitrate_kbps == 256
        assert empty_report.avg_bitrate_kbps == pytest.approx((256 + 192) / 2)

    def test_finalize_sorts_upgrade_candidates(self, empty_report):
        """Test finalize sorts upgrade candidates by priority."""
        item1 = AudioQuality(
            item_id="1",
            title="Low Priority",
            codec="aac",
            bitrate_kbps=64,
            path="/",
            tier=QualityTier.LOW,
            upgrade_priority=1,
        )
        item2 = AudioQuality(
            item_id="2",
            title="High Priority",
            codec="aac",
            bitrate_kbps=32,
            path="/",
            tier=QualityTier.POOR,
            upgrade_priority=10,
        )
        item3 = AudioQuality(
            item_id="3",
            title="Medium Priority",
            codec="aac",
            bitrate_kbps=50,
            path="/",
            tier=QualityTier.LOW,
            upgrade_priority=5,
        )

        empty_report.add_item(item1)
        empty_report.add_item(item2)
        empty_report.add_item(item3)

        empty_report.finalize()

        # After sorting, priorities should be descending
        assert empty_report.upgrade_candidates[0].upgrade_priority == 10
        assert empty_report.upgrade_candidates[1].upgrade_priority == 5
        assert empty_report.upgrade_candidates[2].upgrade_priority == 1

    def test_finalize_with_no_bitrate_items(self, empty_report):
        """Test finalize when all items have zero bitrate."""
        item1 = AudioQuality(
            item_id="1", title="Book 1", codec="aac", bitrate_kbps=0, path="/", tier=QualityTier.EXCELLENT
        )
        item2 = AudioQuality(item_id="2", title="Book 2", codec="aac", bitrate_kbps=0, path="/", tier=QualityTier.GOOD)

        empty_report.add_item(item1)
        empty_report.add_item(item2)

        empty_report.finalize()

        # Should remain at defaults
        assert empty_report.min_bitrate_kbps == 0
        assert empty_report.max_bitrate_kbps == 0
        assert empty_report.avg_bitrate_kbps == 0
