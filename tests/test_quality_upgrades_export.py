"""Tests for quality upgrades dashboard export helpers."""

import pytest

from src.cli.quality import _build_upgrade_export_data, _normalize_acquisition_recommendation
from src.quality import AudioQuality, FormatRank, QualitySeriesEntry, QualityTier


@pytest.mark.parametrize(
    ("recommendation", "expected"),
    [
        ("FREE", "FREE"),
        ("FREE (expires Apr 30)", "FREE"),
        ("MONTHLY_DEAL ($4.19, 86% off)", "MONTHLY_DEAL"),
        ("GOOD_DEAL ($8.82, 41% off)", "GOOD_DEAL"),
        ("OWNED", "OWNED"),
        ("EXPENSIVE ($24.99)", "EXPENSIVE"),
        (None, "N/A"),
    ],
)
def test_normalize_acquisition_recommendation(recommendation, expected):
    """Recommendation keys should be stable for dashboard filters and counts."""
    assert _normalize_acquisition_recommendation(recommendation) == expected


def test_build_upgrade_export_data_includes_rich_metadata():
    """Dashboard export should include summary counts and richer audiobook metadata."""
    candidates = [
        AudioQuality(
            item_id="abs-1",
            title="Alpha",
            subtitle="The Clean Room Edit",
            author="Author One",
            narrators=["Narrator One"],
            series=[QualitySeriesEntry(name="Alpha Saga", sequence="1")],
            publisher="Orbit",
            language="English",
            published_year="2024",
            asin="B001",
            path="/library/Author One/Alpha",
            size_bytes=550 * 1024 * 1024,
            file_count=1,
            primary_filename="Alpha.m4b",
            codec="aac",
            codec_mix=["aac"],
            bitrate_kbps=64,
            channels=2,
            channel_layout="stereo",
            format_rank=FormatRank.M4B,
            format_mix=["M4B"],
            duration_hours=11.7,
            tier=QualityTier.POOR,
            quality_score=17.4,
            upgrade_priority=900,
            upgrade_reason="Huge bitrate jump available.",
            owned_on_audible=False,
            is_plus_catalog=True,
            plus_expiration="Apr 30",
            list_price=29.99,
            sale_price=19.99,
            discount_percent=33.3,
            is_good_deal=False,
            is_monthly_deal=False,
            has_atmos_upgrade=False,
            audible_best_bitrate=128,
            audible_best_codec="AAC-LC",
            acquisition_recommendation="FREE (expires Apr 30)",
            audible_url="https://example.com/alpha",
            cover_image_url="https://example.com/alpha.jpg",
        ),
        AudioQuality(
            item_id="abs-2",
            title="Beta",
            subtitle="Volume Two",
            author="Author Two",
            narrators=["Narrator Two", "Guest Voice"],
            series=[QualitySeriesEntry(name="Alpha Saga", sequence="2")],
            publisher="Penguin Audio",
            language="English",
            published_date="2023-08-14",
            asin="B002",
            path="/library/Author Two/Beta",
            size_bytes=320 * 1024 * 1024,
            file_count=8,
            primary_filename="Disc01.mp3",
            codec="mp3",
            codec_mix=["mp3"],
            bitrate_kbps=80,
            channels=2,
            channel_layout="stereo",
            format_rank=FormatRank.MP3,
            format_mix=["MP3"],
            duration_hours=8.2,
            tier=QualityTier.LOW,
            quality_score=28.0,
            upgrade_priority=480,
            upgrade_reason="Monthly deal with meaningful improvement.",
            owned_on_audible=False,
            is_plus_catalog=False,
            plus_expiration=None,
            list_price=24.99,
            sale_price=4.19,
            discount_percent=86.0,
            is_good_deal=True,
            is_monthly_deal=True,
            has_atmos_upgrade=False,
            audible_best_bitrate=131,
            audible_best_codec="HE-AAC",
            acquisition_recommendation="MONTHLY_DEAL ($4.19, 86% off)",
            audible_url="https://example.com/beta",
            cover_image_url=None,
        ),
    ]

    export_data = _build_upgrade_export_data(candidates)

    assert export_data["summary"] == {
        "total_candidates": 2,
        "plus_catalog_count": 1,
        "monthly_deals_count": 1,
        "good_deals_count": 1,
        "already_owned_count": 0,
        "atmos_available_count": 0,
    }

    first_item = export_data["upgrade_candidates"][0]
    second_item = export_data["upgrade_candidates"][1]

    assert first_item["primary_filename"] == "Alpha.m4b"
    assert first_item["duration_hours"] == 11.7
    assert first_item["channel_layout"] == "stereo"
    assert first_item["subtitle"] == "The Clean Room Edit"
    assert first_item["primary_narrator"] == "Narrator One"
    assert first_item["series_label"] == "Alpha Saga #1"
    assert first_item["publisher"] == "Orbit"
    assert first_item["codec_mix"] == ["aac"]
    assert first_item["format_mix"] == ["M4B"]
    assert first_item["upgrade_reason"] == "Huge bitrate jump available."
    assert first_item["acquisition_recommendation"] == "FREE"
    assert first_item["acquisition_label"] == "FREE (expires Apr 30)"
    assert second_item["acquisition_recommendation"] == "MONTHLY_DEAL"
    assert second_item["delta_kbps"] == 51
    assert second_item["series"][0]["name"] == "Alpha Saga"
    assert second_item["primary_narrator"] == "Narrator Two"
