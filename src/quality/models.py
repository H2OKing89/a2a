"""
Quality analysis data models.
"""

from enum import IntEnum
from typing import Optional
from pydantic import BaseModel, Field


class QualityTier(IntEnum):
    """
    Audio quality tiers.
    
    Lower number = higher quality.
    """
    EXCELLENT = 1   # Dolby Atmos OR m4b @ 256+ kbps
    GOOD = 2        # m4b @ 128-255 kbps
    ACCEPTABLE = 3  # m4b @ 110-127 kbps OR mp3 @ 128+ kbps
    LOW = 4         # m4b @ 64-109 kbps OR mp3 @ 110-127 kbps
    POOR = 5        # Any format < 64 kbps OR mp3 < 110 kbps
    UNKNOWN = 99    # Unable to determine
    
    @property
    def label(self) -> str:
        """Human-readable tier label."""
        return {
            QualityTier.EXCELLENT: "Excellent",
            QualityTier.GOOD: "Good",
            QualityTier.ACCEPTABLE: "Acceptable",
            QualityTier.LOW: "Low",
            QualityTier.POOR: "Poor",
            QualityTier.UNKNOWN: "Unknown",
        }.get(self, "Unknown")
    
    @property
    def emoji(self) -> str:
        """Emoji indicator for tier."""
        return {
            QualityTier.EXCELLENT: "⭐",
            QualityTier.GOOD: "✅",
            QualityTier.ACCEPTABLE: "👍",
            QualityTier.LOW: "⚠️",
            QualityTier.POOR: "❌",
            QualityTier.UNKNOWN: "❓",
        }.get(self, "❓")


class FormatRank(IntEnum):
    """
    Audio format ranking.
    
    Lower number = better format.
    """
    M4B = 1   # Best - single file with chapters
    M4A = 2   # Good - AAC audio
    MP3 = 3   # Lower - older format, less efficient
    OPUS = 3  # Equal to MP3
    FLAC = 3  # Equal to MP3 (lossless but large)
    OTHER = 4 # Unknown formats
    
    @classmethod
    def from_filename(cls, filename: str) -> "FormatRank":
        """Determine format rank from filename."""
        lower = filename.lower()
        if lower.endswith('.m4b'):
            return cls.M4B
        elif lower.endswith('.m4a'):
            return cls.M4A
        elif lower.endswith('.mp3'):
            return cls.MP3
        elif lower.endswith('.opus'):
            return cls.OPUS
        elif lower.endswith('.flac'):
            return cls.FLAC
        else:
            return cls.OTHER
    
    @classmethod
    def from_codec_mime(cls, codec: str, mime_type: str) -> "FormatRank":
        """Determine format rank from codec and MIME type."""
        codec_lower = codec.lower() if codec else ""
        mime_lower = mime_type.lower() if mime_type else ""
        
        # AAC in MP4 container = m4b/m4a
        if codec_lower == "aac" and "mp4" in mime_lower:
            return cls.M4B
        elif codec_lower == "aac":
            return cls.M4A
        elif codec_lower == "mp3" or "mp3" in mime_lower:
            return cls.MP3
        elif codec_lower == "opus":
            return cls.OPUS
        elif codec_lower == "flac":
            return cls.FLAC
        elif codec_lower == "eac3":  # Dolby Atmos uses EAC3
            return cls.M4B  # Treat as top tier format
        else:
            return cls.OTHER


class AudioQuality(BaseModel):
    """Quality analysis result for a single audiobook."""
    
    # Item identification
    item_id: str = Field(description="ABS library item ID")
    title: str = Field(description="Book title")
    author: Optional[str] = Field(default=None, description="Author name")
    asin: Optional[str] = Field(default=None, description="Audible ASIN")
    
    # File info
    path: str = Field(description="File path in library")
    size_bytes: int = Field(default=0, description="Total size in bytes")
    file_count: int = Field(default=1, description="Number of audio files")
    primary_filename: Optional[str] = Field(default=None, description="Primary audio filename")
    
    # Audio properties
    codec: str = Field(description="Audio codec (aac, mp3, eac3, etc.)")
    bitrate_kbps: float = Field(description="Bitrate in kbps")
    channels: int = Field(default=2, description="Number of audio channels")
    channel_layout: Optional[str] = Field(default=None, description="Channel layout (stereo, 5.1, etc.)")
    format_rank: FormatRank = Field(default=FormatRank.OTHER, description="Format quality rank")
    duration_hours: float = Field(default=0, description="Duration in hours")
    
    # Quality assessment
    is_atmos: bool = Field(default=False, description="Is Dolby Atmos audio")
    tier: QualityTier = Field(default=QualityTier.UNKNOWN, description="Quality tier")
    quality_score: float = Field(default=0.0, description="Quality score 0-100")
    
    # Upgrade potential
    upgrade_priority: int = Field(default=0, description="Upgrade priority (higher = more urgent)")
    upgrade_reason: Optional[str] = Field(default=None, description="Reason for upgrade recommendation")
    
    # Audible enrichment
    owned_on_audible: Optional[bool] = Field(default=None, description="Whether owned on Audible")
    is_plus_catalog: bool = Field(default=False, description="Available in Plus Catalog (FREE)")
    plus_expiration: Optional[str] = Field(default=None, description="Plus Catalog expiration date")
    list_price: Optional[float] = Field(default=None, description="Audible list price (USD)")
    sale_price: Optional[float] = Field(default=None, description="Audible sale price (USD)")
    discount_percent: Optional[float] = Field(default=None, description="Discount percentage")
    is_good_deal: bool = Field(default=False, description="Under $9.00 threshold")
    is_monthly_deal: bool = Field(default=False, description="Monthly deal (type=sale)")
    has_atmos_upgrade: bool = Field(default=False, description="Atmos version available on Audible")
    acquisition_recommendation: Optional[str] = Field(default=None, description="Buy recommendation")
    audible_url: Optional[str] = Field(default=None, description="URL to Audible product page")
    cover_image_url: Optional[str] = Field(default=None, description="URL to 500x500 cover image")
    
    @property
    def size_gb(self) -> float:
        """Size in gigabytes."""
        return self.size_bytes / (1024 ** 3)
    
    @property
    def size_mb(self) -> float:
        """Size in megabytes."""
        return self.size_bytes / (1024 ** 2)
    
    @property
    def tier_label(self) -> str:
        """Human-readable tier label."""
        return self.tier.label
    
    @property
    def format_label(self) -> str:
        """Human-readable format label."""
        return {
            FormatRank.M4B: "M4B",
            FormatRank.M4A: "M4A",
            FormatRank.MP3: "MP3",
            FormatRank.OPUS: "Opus",
            FormatRank.FLAC: "FLAC",
            FormatRank.OTHER: "Other",
        }.get(self.format_rank, "Unknown")


class QualityReport(BaseModel):
    """Summary report of library quality analysis."""
    
    # Summary counts
    total_items: int = Field(default=0)
    total_size_bytes: int = Field(default=0)
    total_duration_hours: float = Field(default=0)
    
    # Tier breakdown
    tier_counts: dict[str, int] = Field(default_factory=dict)
    
    # Format breakdown
    format_counts: dict[str, int] = Field(default_factory=dict)
    codec_counts: dict[str, int] = Field(default_factory=dict)
    
    # Bitrate stats
    min_bitrate_kbps: float = Field(default=0)
    max_bitrate_kbps: float = Field(default=0)
    avg_bitrate_kbps: float = Field(default=0)
    
    # Items by tier
    excellent_items: list[AudioQuality] = Field(default_factory=list)
    good_items: list[AudioQuality] = Field(default_factory=list)
    acceptable_items: list[AudioQuality] = Field(default_factory=list)
    low_items: list[AudioQuality] = Field(default_factory=list)
    poor_items: list[AudioQuality] = Field(default_factory=list)
    
    # Special categories
    atmos_items: list[AudioQuality] = Field(default_factory=list)
    upgrade_candidates: list[AudioQuality] = Field(default_factory=list)
    
    @property
    def total_size_gb(self) -> float:
        """Total size in GB."""
        return self.total_size_bytes / (1024 ** 3)
    
    def add_item(self, item: AudioQuality) -> None:
        """Add an item to the report."""
        self.total_items += 1
        self.total_size_bytes += item.size_bytes
        self.total_duration_hours += item.duration_hours
        
        # Tier counts
        tier_name = item.tier.label
        self.tier_counts[tier_name] = self.tier_counts.get(tier_name, 0) + 1
        
        # Format counts
        fmt = item.format_label
        self.format_counts[fmt] = self.format_counts.get(fmt, 0) + 1
        
        # Codec counts
        self.codec_counts[item.codec] = self.codec_counts.get(item.codec, 0) + 1
        
        # Add to tier lists
        if item.tier == QualityTier.EXCELLENT:
            self.excellent_items.append(item)
        elif item.tier == QualityTier.GOOD:
            self.good_items.append(item)
        elif item.tier == QualityTier.ACCEPTABLE:
            self.acceptable_items.append(item)
        elif item.tier == QualityTier.LOW:
            self.low_items.append(item)
        elif item.tier == QualityTier.POOR:
            self.poor_items.append(item)
        
        # Special categories
        if item.is_atmos:
            self.atmos_items.append(item)
        
        if item.tier in (QualityTier.LOW, QualityTier.POOR):
            self.upgrade_candidates.append(item)
    
    def finalize(self) -> None:
        """Calculate final statistics after all items added."""
        all_items = (
            self.excellent_items + self.good_items + 
            self.acceptable_items + self.low_items + self.poor_items
        )
        
        if all_items:
            bitrates = [i.bitrate_kbps for i in all_items if i.bitrate_kbps > 0]
            if bitrates:
                self.min_bitrate_kbps = min(bitrates)
                self.max_bitrate_kbps = max(bitrates)
                self.avg_bitrate_kbps = sum(bitrates) / len(bitrates)
        
        # Sort upgrade candidates by priority (descending)
        self.upgrade_candidates.sort(key=lambda x: x.upgrade_priority, reverse=True)
