"""
Tests for fast quality discovery using metadata endpoint.

These tests verify the new Phase 2 implementation that uses
/content/{asin}/metadata with drm_type parameter for faster
quality discovery (~3x faster than license requests).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.audible.models import (
    AudioFormat,
    ContentMetadata,
    ContentQualityInfo,
    ContentReference,
)


class TestContentReference:
    """Tests for ContentReference model."""

    def test_bitrate_calculation(self):
        """Test bitrate calculation from size and runtime."""
        ref = ContentReference(
            codec="mp4a.40.2",
            content_size_bytes=100_000_000,  # 100 MB
            runtime_ms=3_600_000,  # 1 hour
        )
        # Expected: (100_000_000 * 8) / (3_600_000 / 1000) / 1000 = ~222 kbps
        assert abs(ref.bitrate_kbps - 222.22) < 1

    def test_bitrate_zero_runtime(self):
        """Test bitrate returns 0 when runtime is 0."""
        ref = ContentReference(
            codec="mp4a.40.2",
            content_size_bytes=100_000_000,
            runtime_ms=0,
        )
        assert ref.bitrate_kbps == 0.0

    def test_bitrate_zero_size(self):
        """Test bitrate returns 0 when size is 0."""
        ref = ContentReference(
            codec="mp4a.40.2",
            content_size_bytes=0,
            runtime_ms=3_600_000,
        )
        assert ref.bitrate_kbps == 0.0

    def test_is_atmos_ec3(self):
        """Test Atmos detection for ec+3 codec."""
        ref = ContentReference(codec="ec+3")
        assert ref.is_atmos is True

    def test_is_atmos_ac4(self):
        """Test Atmos detection for ac-4 codec."""
        ref = ContentReference(codec="ac-4")
        assert ref.is_atmos is True

    def test_is_atmos_aac(self):
        """Test Atmos is False for AAC codec."""
        ref = ContentReference(codec="mp4a.40.2")
        assert ref.is_atmos is False

    def test_is_high_efficiency(self):
        """Test HE-AAC detection."""
        ref = ContentReference(codec="mp4a.40.42")
        assert ref.is_high_efficiency is True
        assert ref.is_standard_aac is False

    def test_is_standard_aac(self):
        """Test standard AAC detection."""
        ref = ContentReference(codec="mp4a.40.2")
        assert ref.is_standard_aac is True
        assert ref.is_high_efficiency is False

    def test_codec_name_aac_lc(self):
        """Test codec name for AAC-LC."""
        ref = ContentReference(codec="mp4a.40.2")
        assert ref.codec_name == "AAC-LC"

    def test_codec_name_he_aac(self):
        """Test codec name for HE-AAC v2."""
        ref = ContentReference(codec="mp4a.40.42")
        assert ref.codec_name == "HE-AAC v2"

    def test_codec_name_dolby_plus(self):
        """Test codec name for Dolby Digital Plus."""
        ref = ContentReference(codec="ec+3")
        assert ref.codec_name == "Dolby Digital Plus"

    def test_codec_name_atmos(self):
        """Test codec name for Dolby AC-4."""
        ref = ContentReference(codec="ac-4")
        assert ref.codec_name == "Dolby AC-4 (Atmos)"

    def test_codec_name_unknown(self):
        """Test codec name for unknown codec."""
        ref = ContentReference(codec="unknown")
        assert ref.codec_name == "Unknown"

    def test_from_api_response(self):
        """Test parsing from API response dict."""
        api_data = {
            "codec": "mp4a.40.42",
            "content_format": "M4A_XHE",
            "content_size_in_bytes": 150_000_000,
            "runtime_length_ms": 5_400_000,
            "acr": "some-acr-id",
        }
        ref = ContentReference.model_validate(api_data)

        assert ref.codec == "mp4a.40.42"
        assert ref.content_format == "M4A_XHE"
        assert ref.content_size_bytes == 150_000_000
        assert ref.runtime_ms == 5_400_000
        assert ref.acr == "some-acr-id"
        assert ref.is_high_efficiency is True


class TestContentMetadata:
    """Tests for enhanced ContentMetadata model."""

    def test_parses_content_reference(self):
        """Test that content_reference is parsed into structured model."""
        metadata = ContentMetadata(
            asin="B0TEST123",
            content_reference={
                "codec": "mp4a.40.42",
                "content_size_in_bytes": 100_000_000,
                "runtime_length_ms": 3_600_000,
            },
        )

        assert metadata.parsed_content_ref is not None
        assert metadata.parsed_content_ref.codec == "mp4a.40.42"
        assert metadata.bitrate_kbps > 0

    def test_bitrate_property(self):
        """Test bitrate property delegates to parsed_content_ref."""
        metadata = ContentMetadata(
            asin="B0TEST123",
            content_reference={
                "codec": "mp4a.40.2",
                "content_size_in_bytes": 100_000_000,
                "runtime_length_ms": 3_600_000,
            },
        )

        assert abs(metadata.bitrate_kbps - 222.22) < 1

    def test_codec_property(self):
        """Test codec property delegates to parsed_content_ref."""
        metadata = ContentMetadata(
            asin="B0TEST123",
            content_reference={"codec": "ec+3"},
        )

        assert metadata.codec == "ec+3"

    def test_supports_atmos_from_parsed(self):
        """Test supports_atmos uses parsed content reference."""
        metadata = ContentMetadata(
            asin="B0TEST123",
            content_reference={"codec": "ec+3"},
        )

        assert metadata.supports_atmos is True

    def test_supports_atmos_from_codecs_list(self):
        """Test supports_atmos falls back to available_codecs."""
        metadata = ContentMetadata(
            asin="B0TEST123",
            available_codecs=["ac-4"],
        )

        assert metadata.supports_atmos is True

    def test_drm_type_stored(self):
        """Test drm_type is stored in metadata."""
        metadata = ContentMetadata(
            asin="B0TEST123",
            drm_type="Widevine",
        )

        assert metadata.drm_type == "Widevine"


class TestContentQualityInfoFromFormats:
    """Tests for ContentQualityInfo.from_formats()."""

    def test_best_format_selection(self):
        """Test that best format is selected by bitrate."""
        formats = [
            AudioFormat(
                codec="mp4a.40.2",
                codec_name="AAC-LC",
                drm_type="Adrm",
                bitrate_kbps=64,
                size_bytes=50_000_000,
                runtime_ms=3_600_000,
                is_spatial=False,
            ),
            AudioFormat(
                codec="mp4a.40.42",
                codec_name="HE-AAC v2",
                drm_type="Widevine",
                bitrate_kbps=128,
                size_bytes=100_000_000,
                runtime_ms=3_600_000,
                is_spatial=False,
            ),
        ]

        quality = ContentQualityInfo.from_formats("B0TEST123", formats)

        assert quality.best_bitrate_kbps == 128
        assert quality.best_format is not None
        assert quality.best_format.codec == "mp4a.40.42"

    def test_atmos_detection(self):
        """Test Atmos detection from formats."""
        formats = [
            AudioFormat(
                codec="ec+3",
                codec_name="Dolby Digital Plus",
                drm_type="Widevine",
                bitrate_kbps=768,
                size_bytes=500_000_000,
                runtime_ms=3_600_000,
                is_spatial=True,
            ),
        ]

        quality = ContentQualityInfo.from_formats("B0TEST123", formats)

        assert quality.has_atmos is True

    def test_empty_formats(self):
        """Test handling of empty formats list."""
        quality = ContentQualityInfo.from_formats("B0TEST123", [])

        assert quality.best_bitrate_kbps == 0
        assert quality.best_format is None
        assert quality.has_atmos is False


# Integration-style tests that would require mocking the async client
class TestFastQualityCheckIntegration:
    """Integration tests for fast_quality_check (mocked)."""

    @pytest.mark.asyncio
    async def test_fast_quality_check_widevine_success(self):
        """Test fast quality check returns Widevine format info."""
        from src.audible.async_client import AsyncAudibleClient

        # Create mock client
        mock_client = MagicMock(spec=AsyncAudibleClient)
        mock_client._cache = None
        mock_client._cache_ttl_seconds = 3600

        # Mock metadata response
        widevine_metadata = ContentMetadata(
            asin="B0TEST123",
            content_reference={
                "codec": "mp4a.40.42",
                "content_size_in_bytes": 150_000_000,
                "runtime_length_ms": 5_400_000,
            },
            drm_type="Widevine",
        )
        adrm_metadata = ContentMetadata(
            asin="B0TEST123",
            content_reference={
                "codec": "mp4a.40.2",
                "content_size_in_bytes": 100_000_000,
                "runtime_length_ms": 5_400_000,
            },
            drm_type="Adrm",
        )

        mock_client.get_content_metadata = AsyncMock(side_effect=[widevine_metadata, adrm_metadata])

        # Call fast_quality_check using the real implementation
        # but with our mocked get_content_metadata
        result = await AsyncAudibleClient.fast_quality_check(mock_client, "B0TEST123", use_cache=False)

        assert result is not None
        assert result.asin == "B0TEST123"
        assert len(result.formats) == 2
        # Widevine format should have higher bitrate
        assert result.best_format.drm_type == "Widevine"
