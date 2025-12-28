"""
Quality analyzer for audiobook libraries.
"""

import logging
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

import httpx
from pydantic import ValidationError

from ..abs import ABSAuthError, ABSConnectionError, ABSError, ABSNotFoundError
from .models import AudioQuality, FormatRank, QualityReport, QualityTier

if TYPE_CHECKING:
    from ..config import QualitySettings

logger = logging.getLogger(__name__)

# Default bitrate thresholds (kbps) - can be overridden via config
BITRATE_EXCELLENT = 256
BITRATE_GOOD = 128
BITRATE_ACCEPTABLE = 110
BITRATE_LOW = 64

# Default Atmos detection settings
ATMOS_CODECS = {"eac3", "truehd", "ac3"}  # Dolby codecs
ATMOS_CHANNELS_MIN = 6  # 5.1 or higher

# Default premium formats
PREMIUM_FORMATS = {"m4b", "m4a"}


class QualityAnalyzer:
    """
    Analyzes audiobook quality based on bitrate, format, and codec.

    Tier Logic:
    -----------
    EXCELLENT:
        - Dolby Atmos (eac3/truehd + 5.1+) - trumps all
        - OR: Any format @ 256+ kbps

    GOOD:
        - m4b/m4a @ 128-255 kbps

    ACCEPTABLE:
        - m4b/m4a @ 110-127 kbps
        - OR: mp3 @ 128+ kbps

    LOW:
        - m4b/m4a @ 64-109 kbps
        - OR: mp3 @ 110-127 kbps

    POOR:
        - Any format < 64 kbps
        - OR: mp3 < 110 kbps

    Example:
        analyzer = QualityAnalyzer()

        # Analyze single item
        quality = analyzer.analyze_item(abs_item_data)
        print(f"{quality.title}: {quality.tier.label} ({quality.bitrate_kbps} kbps)")

        # Scan full library
        report = analyzer.scan_library(abs_client, library_id)
        print(f"Upgrade candidates: {len(report.upgrade_candidates)}")

        # Using configuration
        from src.config import get_settings
        settings = get_settings()
        analyzer = QualityAnalyzer.from_config(settings.quality)
    """

    def __init__(
        self,
        bitrate_excellent: float = BITRATE_EXCELLENT,
        bitrate_good: float = BITRATE_GOOD,
        bitrate_acceptable: float = BITRATE_ACCEPTABLE,
        bitrate_low: float = BITRATE_LOW,
        atmos_codecs: set[str] | None = None,
        atmos_min_channels: int = ATMOS_CHANNELS_MIN,
        premium_formats: set[str] | None = None,
    ):
        """
        Initialize analyzer with custom thresholds.

        Args:
            bitrate_excellent: Minimum kbps for excellent tier (default 256)
            bitrate_good: Minimum kbps for good tier (default 128)
            bitrate_acceptable: Minimum kbps for acceptable tier (default 110)
            bitrate_low: Minimum kbps for low tier (default 64)
            atmos_codecs: Set of codec names indicating Atmos capability
            atmos_min_channels: Minimum channels for Atmos detection (default 6)
            premium_formats: Set of formats considered premium (default m4b, m4a)
        """
        self.bitrate_excellent = bitrate_excellent
        self.bitrate_good = bitrate_good
        self.bitrate_acceptable = bitrate_acceptable
        self.bitrate_low = bitrate_low
        self.atmos_codecs = atmos_codecs or ATMOS_CODECS
        self.atmos_min_channels = atmos_min_channels
        self.premium_formats = premium_formats or PREMIUM_FORMATS

    @classmethod
    def from_config(cls, config: "QualitySettings") -> "QualityAnalyzer":
        """
        Create analyzer from QualitySettings configuration.

        Args:
            config: QualitySettings instance from config.py

        Returns:
            Configured QualityAnalyzer

        Example:
            from src.config import get_settings
            settings = get_settings()
            analyzer = QualityAnalyzer.from_config(settings.quality)
        """
        return cls(
            bitrate_excellent=config.get_tier_threshold("excellent"),
            bitrate_good=config.get_tier_threshold("better"),
            bitrate_acceptable=config.get_tier_threshold("good"),
            bitrate_low=config.get_tier_threshold("low"),
            atmos_codecs=set(config.atmos_codecs),
            atmos_min_channels=config.atmos_min_channels,
            premium_formats=set(config.premium_formats),
        )

    def is_atmos(self, codec: str, channels: int, channel_layout: str | None = None) -> bool:
        """
        Check if audio is Dolby Atmos.

        Detection criteria:
        - Codec is in atmos_codecs set (default: eac3, truehd, ac3)
        - Channels >= atmos_min_channels (default: 6 for 5.1+)
        """
        if not codec:
            return False

        codec_lower = codec.lower()

        # Check codec and channel count against configured thresholds
        if codec_lower in self.atmos_codecs and channels >= self.atmos_min_channels:
            return True

        # Also check channel layout for "atmos" mention
        if channel_layout and "atmos" in channel_layout.lower():
            return True

        return False

    def is_premium_format(self, format_rank: FormatRank) -> bool:
        """Check if format is considered premium based on configuration."""
        format_name = format_rank.name.lower()
        return format_name in self.premium_formats

    def calculate_tier(
        self,
        bitrate_kbps: float,
        format_rank: FormatRank,
        is_atmos: bool = False,
    ) -> QualityTier:
        """
        Calculate quality tier based on bitrate, format, and Atmos status.

        Args:
            bitrate_kbps: Bitrate in kbps
            format_rank: Format ranking (M4B, MP3, etc.)
            is_atmos: Whether audio is Dolby Atmos

        Returns:
            Quality tier
        """
        # Rule 1: Atmos trumps all
        if is_atmos:
            return QualityTier.EXCELLENT

        # Rule 2: 256+ kbps is always excellent
        if bitrate_kbps >= self.bitrate_excellent:
            return QualityTier.EXCELLENT

        # Rules based on format (using configurable format sets)
        is_premium = self.is_premium_format(format_rank)
        is_mp3_format = format_rank in (FormatRank.MP3, FormatRank.OPUS, FormatRank.FLAC)

        if is_premium:
            # M4B/M4A tiers (premium formats)
            if bitrate_kbps >= self.bitrate_good:  # 128+
                return QualityTier.BETTER
            elif bitrate_kbps >= self.bitrate_acceptable:  # 110-127
                return QualityTier.GOOD
            elif bitrate_kbps >= self.bitrate_low:  # 64-109
                return QualityTier.LOW
            else:  # <64
                return QualityTier.POOR

        elif is_mp3_format:
            # MP3 tiers (stricter - one tier lower than m4b at same bitrate)
            if bitrate_kbps >= self.bitrate_good:  # 128+
                return QualityTier.GOOD  # MP3 128+ = Good (not Better)
            elif bitrate_kbps >= self.bitrate_acceptable:  # 110-127
                return QualityTier.LOW
            else:  # <110
                return QualityTier.POOR

        else:
            # Unknown format - use generic bitrate rules
            if bitrate_kbps >= self.bitrate_good:
                return QualityTier.GOOD
            elif bitrate_kbps >= self.bitrate_low:
                return QualityTier.LOW
            else:
                return QualityTier.POOR

    def calculate_score(
        self,
        bitrate_kbps: float,
        format_rank: FormatRank,
        is_atmos: bool = False,
    ) -> float:
        """
        Calculate quality score 0-100.

        Components:
        - Bitrate: 0-60 points (scaled to 256 kbps max)
        - Format: 0-30 points (m4b=30, m4a=25, mp3=15, other=10)
        - Atmos bonus: +10 points
        """
        score = 0.0

        # Bitrate component (0-60 points)
        bitrate_score = min(60, (bitrate_kbps / 256) * 60)
        score += bitrate_score

        # Format component (0-30 points)
        format_scores = {
            FormatRank.M4B: 30,
            FormatRank.M4A: 25,
            FormatRank.MP3: 15,
            FormatRank.OPUS: 15,
            FormatRank.FLAC: 20,  # Lossless gets some credit
            FormatRank.OTHER: 10,
        }
        score += format_scores.get(format_rank, 10)

        # Atmos bonus (10 points)
        if is_atmos:
            score += 10

        return min(100, score)

    def calculate_upgrade_priority(
        self,
        tier: QualityTier,
        bitrate_kbps: float,
        size_bytes: int,
        has_asin: bool,
    ) -> tuple[int, str | None]:
        """
        Calculate upgrade priority and reason.

        Higher priority = more urgent upgrade.

        Factors:
        - Tier (POOR=100, LOW=50, ACCEPTABLE=10, GOOD=0, EXCELLENT=0)
        - Has ASIN (easier to find on Audible, +20)
        - Large file with low bitrate (wasted space, +10)

        Returns:
            (priority, reason)
        """
        priority = 0
        reasons = []

        # Tier-based priority
        if tier == QualityTier.POOR:
            priority += 100
            reasons.append(f"Very low quality ({bitrate_kbps:.0f} kbps)")
        elif tier == QualityTier.LOW:
            priority += 50
            reasons.append(f"Below acceptable quality ({bitrate_kbps:.0f} kbps)")
        elif tier == QualityTier.GOOD:
            priority += 10
            reasons.append(f"Could be improved ({bitrate_kbps:.0f} kbps)")
        else:
            # Better/Excellent - no upgrade needed
            return 0, None

        # ASIN bonus (easier to find replacement)
        if has_asin:
            priority += 20
            reasons.append("Has ASIN (easy to find on Audible)")

        # Large file with low bitrate (wasted space) - check efficiency
        size_gb = size_bytes / (1024**3)
        efficiency = bitrate_kbps / max(1, size_gb * 100)
        if efficiency < 1.0:  # Low bitrate per GB indicates wasted space
            priority += 10
            reasons.append(f"Low efficiency ({size_gb:.1f} GB @ {bitrate_kbps:.0f} kbps)")

        reason = "; ".join(reasons) if reasons else None
        return priority, reason

    def analyze_item(self, item_data: dict) -> AudioQuality:
        """
        Analyze a single ABS library item.

        Args:
            item_data: Expanded item data from ABS API

        Returns:
            AudioQuality analysis result
        """
        media = item_data.get("media", {})
        metadata = media.get("metadata", {})
        audio_files = media.get("audioFiles", [])

        # Basic info
        item_id = item_data.get("id", "")
        title = metadata.get("title", "Unknown")
        author = metadata.get("authorName")
        asin = metadata.get("asin")
        path = item_data.get("path", "")
        size_bytes = item_data.get("size", 0)

        # Aggregate audio properties from all files
        total_duration = 0
        total_bitrate_weighted = 0
        file_count = len(audio_files)
        primary_filename = None

        # Use first/largest file for codec detection
        primary_codec = "unknown"
        primary_channels = 2
        primary_channel_layout = None
        primary_format = FormatRank.OTHER

        for i, af in enumerate(audio_files):
            duration = af.get("duration", 0)
            bitrate = af.get("bitRate", 0) / 1000  # Convert to kbps

            total_duration += duration
            total_bitrate_weighted += bitrate * duration

            if i == 0:
                # Primary file properties
                primary_codec = af.get("codec", "unknown")
                primary_channels = af.get("channels", 2)
                primary_channel_layout = af.get("channelLayout")
                primary_filename = af.get("metadata", {}).get("filename")
                mime_type = af.get("mimeType", "")

                # Determine format from filename or codec/mime
                if primary_filename:
                    primary_format = FormatRank.from_filename(primary_filename)
                else:
                    primary_format = FormatRank.from_codec_mime(primary_codec, mime_type)

        # Calculate average bitrate
        if total_duration > 0:
            avg_bitrate = total_bitrate_weighted / total_duration
        elif audio_files:
            # Fallback to first file's bitrate
            avg_bitrate = audio_files[0].get("bitRate", 0) / 1000
        else:
            avg_bitrate = 0

        # Detect Atmos
        is_atmos = self.is_atmos(primary_codec, primary_channels, primary_channel_layout)

        # Calculate tier and score
        tier = self.calculate_tier(avg_bitrate, primary_format, is_atmos)
        score = self.calculate_score(avg_bitrate, primary_format, is_atmos)

        # Calculate upgrade priority
        priority, reason = self.calculate_upgrade_priority(tier, avg_bitrate, size_bytes, bool(asin))

        return AudioQuality(
            item_id=item_id,
            title=title,
            author=author,
            asin=asin,
            path=path,
            size_bytes=size_bytes,
            file_count=file_count,
            primary_filename=primary_filename,
            codec=primary_codec,
            bitrate_kbps=avg_bitrate,
            channels=primary_channels,
            channel_layout=primary_channel_layout,
            format_rank=primary_format,
            duration_hours=total_duration / 3600,
            is_atmos=is_atmos,
            tier=tier,
            quality_score=score,
            upgrade_priority=priority,
            upgrade_reason=reason,
        )

    def scan_library(
        self,
        abs_client,
        library_id: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> QualityReport:
        """
        Scan an entire library and generate quality report.

        Args:
            abs_client: ABSClient instance
            library_id: Library ID to scan
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            QualityReport with all items analyzed
        """
        report = QualityReport()

        # Get all items (minified first for IDs)
        items_resp = abs_client._get(f"/libraries/{library_id}/items", params={"limit": 0})  # Get all
        items = items_resp.get("results", [])
        total = len(items)

        # Analyze each item
        for i, item in enumerate(items):
            item_id = item.get("id")

            # Fetch expanded item data
            try:
                full_item = abs_client._get(f"/items/{item_id}", params={"expanded": 1})
                quality = self.analyze_item(full_item)
                report.add_item(quality)
            except ABSAuthError:
                # Auth errors are critical - re-raise
                raise
            except ABSNotFoundError:
                # Item deleted/moved - log and continue
                logger.warning(f"Item not found, skipping: {item_id}")
            except ValidationError as e:
                # Data validation error - log details and continue
                logger.exception(f"Validation error for item {item_id}: {e}")
            except (ABSConnectionError, httpx.TimeoutException, httpx.ConnectError) as e:
                # Transient network errors - log and continue
                logger.error(f"Network error fetching item {item_id}: {e}")
            except ABSError as e:
                # Other ABS API errors - log and continue
                logger.error(f"ABS API error for item {item_id}: {e}")

            # Progress callback
            if progress_callback:
                progress_callback(i + 1, total)

        # Finalize statistics
        report.finalize()

        return report

    def scan_library_streaming(
        self,
        abs_client,
        library_id: str,
    ) -> Iterator[AudioQuality]:
        """
        Stream quality analysis results as they're processed.

        Yields AudioQuality objects one at a time.
        Useful for large libraries where you want incremental output.

        Args:
            abs_client: ABSClient instance
            library_id: Library ID to scan

        Yields:
            AudioQuality for each item
        """
        # Get all items
        items_resp = abs_client._get(f"/libraries/{library_id}/items", params={"limit": 0})
        items = items_resp.get("results", [])

        for item in items:
            item_id = item.get("id")

            try:
                full_item = abs_client._get(f"/items/{item_id}", params={"expanded": 1})
                yield self.analyze_item(full_item)
            except ABSAuthError:
                # Auth errors are critical - re-raise
                raise
            except ABSNotFoundError:
                # Item deleted/moved - skip silently in streaming mode
                logger.debug(f"Item not found, skipping: {item_id}")
                continue
            except ValidationError as e:
                # Data validation error - log and skip
                logger.error(f"Validation error for item {item_id}: {e}", exc_info=True)
                continue
            except (ABSConnectionError, httpx.TimeoutException, httpx.ConnectError) as e:
                # Transient network errors - log and skip
                logger.error(f"Network error fetching item {item_id}: {e}", exc_info=True)
                continue
            except ABSError as e:
                # Other ABS API errors - log and skip
                logger.error(f"ABS API error for item {item_id}: {e}", exc_info=True)
                continue
            except Exception:
                # Unexpected errors (e.g., bugs in analyze_item) - log with full traceback
                logger.exception(f"Unexpected error processing item {item_id}")
                continue
