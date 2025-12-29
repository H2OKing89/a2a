"""
Tests for FormatRank enum to prevent aliasing regression.

This catches the "MP3 = 3, OPUS = 3, FLAC = 3" aliasing bug where
FormatRank.OPUS is FormatRank.MP3 (same object) breaks format_label.
"""

import pytest

from src.quality.models import FormatRank


def test_format_rank_values_are_unique():
    """Enum values must be unique to avoid aliasing."""
    values = [fmt.value for fmt in FormatRank]
    assert len(values) == len(set(values)), "FormatRank has duplicate values (aliasing bug)"


def test_format_rank_members_are_distinct():
    """Each format should be a distinct enum member."""
    assert FormatRank.MP3 is not FormatRank.OPUS, "MP3 and OPUS should not alias"
    assert FormatRank.MP3 is not FormatRank.FLAC, "MP3 and FLAC should not alias"
    assert FormatRank.OPUS is not FormatRank.FLAC, "OPUS and FLAC should not alias"


def test_format_rank_score_equivalence():
    """MP3, OPUS, FLAC should have equal rank_score (but be distinct enums)."""
    assert FormatRank.MP3.rank_score == 3
    assert FormatRank.OPUS.rank_score == 3
    assert FormatRank.FLAC.rank_score == 3

    # But they're different enums
    assert FormatRank.MP3 != FormatRank.OPUS
    assert FormatRank.MP3 != FormatRank.FLAC


def test_format_rank_ordering():
    """Verify rank_score ordering (lower = better)."""
    assert FormatRank.M4B.rank_score < FormatRank.M4A.rank_score
    assert FormatRank.M4A.rank_score < FormatRank.MP3.rank_score
    assert FormatRank.MP3.rank_score < FormatRank.OTHER.rank_score


def test_format_labels_all_unique():
    """Each format should have its own label (not collapsed by aliasing)."""
    from src.quality.models import AudioQuality

    # Create test items with each format
    formats = {
        FormatRank.M4B: "M4B",
        FormatRank.M4A: "M4A",
        FormatRank.MP3: "MP3",
        FormatRank.OPUS: "Opus",
        FormatRank.FLAC: "FLAC",
        FormatRank.OTHER: "Other",
    }

    for format_rank, expected_label in formats.items():
        item = AudioQuality(
            item_id="test",
            title="Test",
            path="/test",
            codec="test",
            bitrate_kbps=128,
            format_rank=format_rank,
        )
        assert item.format_label == expected_label, f"{format_rank} label mismatch"


def test_from_filename_classification():
    """Test filename-based format detection."""
    assert FormatRank.from_filename("book.m4b") == FormatRank.M4B
    assert FormatRank.from_filename("book.m4a") == FormatRank.M4A
    assert FormatRank.from_filename("book.mp3") == FormatRank.MP3
    assert FormatRank.from_filename("book.opus") == FormatRank.OPUS
    assert FormatRank.from_filename("book.flac") == FormatRank.FLAC
    assert FormatRank.from_filename("book.wav") == FormatRank.OTHER


def test_from_codec_mime_classification():
    """Test codec/MIME-based format detection."""
    assert FormatRank.from_codec_mime("aac", "audio/mp4") == FormatRank.M4B
    assert FormatRank.from_codec_mime("aac", "audio/aac") == FormatRank.M4A
    assert FormatRank.from_codec_mime("mp3", "audio/mpeg") == FormatRank.MP3
    assert FormatRank.from_codec_mime("opus", "audio/opus") == FormatRank.OPUS
    assert FormatRank.from_codec_mime("flac", "audio/flac") == FormatRank.FLAC
    assert FormatRank.from_codec_mime("eac3", "audio/mp4") == FormatRank.M4B  # Dolby Atmos
