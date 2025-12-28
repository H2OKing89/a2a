"""
Quality analysis services.

Provides high-level business operations for quality analysis:
- Finding upgrade candidates
- Enriching quality data with Audible metadata
- Generating quality reports
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from ..audible import AudibleEnrichment, AudibleEnrichmentService
from .analyzer import QualityAnalyzer
from .models import AudioQuality, QualityReport

if TYPE_CHECKING:
    from ..abs import ABSClient
    from ..audible import AudibleClient
    from ..cache import SQLiteCache


logger = logging.getLogger(__name__)


class EnrichedUpgradeCandidate(BaseModel):
    """
    An upgrade candidate with full quality and Audible enrichment data.

    Combines AudioQuality analysis with AudibleEnrichment pricing/availability.
    """

    # Quality data
    item_id: str = Field(description="ABS library item ID")
    title: str
    author: str | None = None
    asin: str | None = None
    bitrate_kbps: float
    format_label: str
    codec: str | None = None
    size_mb: float
    size_gb: float
    duration_hours: float
    path: str | None = None
    tier_label: str
    quality_score: float
    upgrade_priority: int
    upgrade_reason: str | None = None

    # Audible enrichment
    owned_on_audible: bool = False
    is_plus_catalog: bool = False
    plus_expiration: str | None = None
    list_price: float | None = None
    sale_price: float | None = None
    discount_percent: float | None = None
    is_good_deal: bool = False
    is_monthly_deal: bool = False
    has_atmos_upgrade: bool = False
    acquisition_recommendation: str | None = None
    audible_url: str | None = None
    cover_image_url: str | None = None

    model_config = {"extra": "ignore"}

    @classmethod
    def from_quality(cls, quality: AudioQuality) -> "EnrichedUpgradeCandidate":
        """Create from AudioQuality analysis result."""
        return cls(
            item_id=quality.item_id,
            title=quality.title,
            author=quality.author,
            asin=quality.asin,
            bitrate_kbps=quality.bitrate_kbps,
            format_label=quality.format_label,
            codec=quality.codec,
            size_mb=quality.size_mb,
            size_gb=quality.size_gb,
            duration_hours=quality.duration_hours,
            path=quality.path,
            tier_label=quality.tier_label,
            quality_score=quality.quality_score,
            upgrade_priority=quality.upgrade_priority,
            upgrade_reason=quality.upgrade_reason,
        )

    def apply_enrichment(self, enrichment: AudibleEnrichment) -> None:
        """Apply Audible enrichment data to this candidate."""
        self.owned_on_audible = enrichment.owned
        self.is_plus_catalog = enrichment.plus_catalog.is_plus_catalog
        self.plus_expiration = enrichment.plus_catalog.expiration_display
        if enrichment.pricing:
            self.list_price = enrichment.pricing.list_price
            self.sale_price = enrichment.pricing.sale_price
            self.discount_percent = enrichment.pricing.discount_percent
            self.is_good_deal = enrichment.pricing.is_good_deal
            self.is_monthly_deal = enrichment.pricing.is_monthly_deal
        self.has_atmos_upgrade = enrichment.has_atmos
        self.acquisition_recommendation = enrichment.acquisition_recommendation
        self.audible_url = enrichment.audible_url
        self.cover_image_url = enrichment.cover_image_url

        # Boost priority based on acquisition opportunity
        self.upgrade_priority = int(self.upgrade_priority * enrichment.priority_boost)


@dataclass
class UpgradeFinderResult:
    """Result of the upgrade finder operation."""

    # Candidates (filtered if options were specified)
    candidates: list[EnrichedUpgradeCandidate] = field(default_factory=list)

    # Summary stats
    total_scanned: int = 0
    total_below_threshold: int = 0
    total_with_asin: int = 0
    total_enriched: int = 0

    # Category counts
    plus_catalog_count: int = 0
    monthly_deals_count: int = 0
    good_deals_count: int = 0
    already_owned_count: int = 0
    atmos_available_count: int = 0

    # Timing
    scan_time_seconds: float = 0.0
    enrichment_time_seconds: float = 0.0
    total_time_seconds: float = 0.0

    # Enrichment stats
    cache_hits: int = 0
    api_calls: int = 0

    def calculate_stats(self) -> None:
        """Calculate summary stats from candidates."""
        self.plus_catalog_count = sum(1 for c in self.candidates if c.is_plus_catalog)
        self.monthly_deals_count = sum(1 for c in self.candidates if c.is_monthly_deal)
        self.good_deals_count = sum(1 for c in self.candidates if c.is_good_deal)
        self.already_owned_count = sum(1 for c in self.candidates if c.owned_on_audible)
        self.atmos_available_count = sum(1 for c in self.candidates if c.has_atmos_upgrade)


class UpgradeFinderService:
    """
    Service for finding audiobook upgrade candidates.

    Encapsulates the complete workflow:
    1. Scan ABS library for low quality items
    2. Filter to items with ASINs (can be looked up on Audible)
    3. Enrich with Audible pricing/availability data
    4. Sort by priority and apply filters

    Example:
        with get_abs_client() as abs_client:
            service = UpgradeFinderService(
                abs_client=abs_client,
                audible_client=audible_client,
                cache=cache,
            )
            result = service.find_upgrades(
                library_id="lib_xxx",
                bitrate_threshold=110,
                plus_only=True,
            )
            for candidate in result.candidates:
                print(f"{candidate.title}: {candidate.acquisition_recommendation}")
    """

    def __init__(
        self,
        abs_client: "ABSClient",
        audible_client: "AudibleClient | None" = None,
        cache: "SQLiteCache | None" = None,
    ) -> None:
        """
        Initialize the upgrade finder service.

        Args:
            abs_client: Authenticated ABS client
            audible_client: Optional Audible client for enrichment
            cache: Optional cache for both ABS and enrichment data
        """
        self._abs = abs_client
        self._audible = audible_client
        self._cache = cache
        self._analyzer = QualityAnalyzer()

    def find_upgrades(
        self,
        library_id: str,
        bitrate_threshold: int = 110,
        plus_only: bool = False,
        deals_only: bool = False,
        monthly_deals_only: bool = False,
        exclude_owned: bool = False,
        limit: int | None = None,
        scan_progress_callback: Callable[[int, int], None] | None = None,
        enrichment_progress_callback: Callable[[int, int], None] | None = None,
    ) -> UpgradeFinderResult:
        """
        Find upgrade candidates in a library.

        Args:
            library_id: ABS library ID to scan
            bitrate_threshold: Minimum bitrate (kbps) - items below are candidates
            plus_only: Only return Plus Catalog (free) items
            deals_only: Only return items under $9
            monthly_deals_only: Only return monthly deal items
            exclude_owned: Exclude items already owned on Audible
            limit: Max number of candidates to return (after filtering)
            scan_progress_callback: Called during quality scan (completed, total)
            enrichment_progress_callback: Called during enrichment (completed, total)

        Returns:
            UpgradeFinderResult with candidates and stats
        """
        import time

        result = UpgradeFinderResult()
        start_time = time.time()

        # Phase 1: Get all items and scan quality
        phase1_start = time.time()
        items_resp: dict[str, Any] = self._abs._get(f"/libraries/{library_id}/items", params={"limit": 0})
        all_items = items_resp.get("results", [])
        item_ids = [item.get("id") for item in all_items if item.get("id")]
        result.total_scanned = len(item_ids)

        # Fetch expanded items in parallel
        expanded_items = self._abs.batch_get_items_expanded(
            item_ids,
            use_cache=True,
            max_workers=20,
            progress_callback=scan_progress_callback,
        )

        # Analyze quality and filter candidates
        candidates: list[EnrichedUpgradeCandidate] = []
        for full_item in expanded_items:
            if not full_item:
                continue

            quality = self._analyzer.analyze_item(full_item)

            if quality.bitrate_kbps < bitrate_threshold:
                result.total_below_threshold += 1
                if quality.asin:
                    result.total_with_asin += 1
                    candidates.append(EnrichedUpgradeCandidate.from_quality(quality))

        result.scan_time_seconds = time.time() - phase1_start
        logger.info(
            "Phase 1 complete: %d items below threshold, %d with ASIN, took %.1fs",
            result.total_below_threshold,
            result.total_with_asin,
            result.scan_time_seconds,
        )

        # Phase 2: Enrich with Audible data (if client available)
        if self._audible and candidates:
            phase2_start = time.time()
            enrichment_service = AudibleEnrichmentService(self._audible, cache=self._cache)
            asins = [c.asin for c in candidates if c.asin]

            enrichments: dict[str, AudibleEnrichment] = {}
            for i, asin in enumerate(asins):
                if enrichment_progress_callback:
                    enrichment_progress_callback(i + 1, len(asins))

                try:
                    enrichment = enrichment_service.enrich_single(asin)
                    if enrichment:
                        enrichments[asin] = enrichment
                except Exception as e:
                    logger.warning("Failed to enrich ASIN %s: %s", asin, e)

            # Apply enrichment to candidates
            for candidate in candidates:
                if candidate.asin and candidate.asin in enrichments:
                    candidate.apply_enrichment(enrichments[candidate.asin])
                    result.total_enriched += 1

            stats = enrichment_service.stats
            result.cache_hits = stats["cache_hits"]
            result.api_calls = stats["api_calls"]
            result.enrichment_time_seconds = time.time() - phase2_start
            logger.info(
                "Phase 2 complete: %d enriched, %d cache hits, %d API calls, took %.1fs",
                result.total_enriched,
                result.cache_hits,
                result.api_calls,
                result.enrichment_time_seconds,
            )

        # Apply filters
        if plus_only:
            candidates = [c for c in candidates if c.is_plus_catalog]
        if monthly_deals_only:
            candidates = [c for c in candidates if c.is_monthly_deal]
        if deals_only:
            candidates = [c for c in candidates if c.is_good_deal]
        if exclude_owned:
            candidates = [c for c in candidates if not c.owned_on_audible]

        # Sort by priority (highest first)
        candidates.sort(key=lambda x: x.upgrade_priority, reverse=True)

        # Apply limit
        if limit:
            candidates = candidates[:limit]

        result.candidates = candidates
        result.calculate_stats()
        result.total_time_seconds = time.time() - start_time

        return result

    def scan_quality(
        self,
        library_id: str,
        limit: int | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> QualityReport:
        """
        Scan a library and generate a quality report.

        Args:
            library_id: ABS library ID to scan
            limit: Max number of items to scan (None = all)
            progress_callback: Called during scan (completed, total)

        Returns:
            QualityReport with tier distribution and upgrade candidates
        """
        # Get all items
        items_resp: dict[str, Any] = self._abs._get(f"/libraries/{library_id}/items", params={"limit": 0})
        all_items = items_resp.get("results", [])

        if limit:
            all_items = all_items[:limit]

        item_ids = [item.get("id") for item in all_items if item.get("id")]

        # Fetch expanded items in parallel
        expanded_items = self._abs.batch_get_items_expanded(
            item_ids,
            use_cache=True,
            max_workers=20,
            progress_callback=progress_callback,
        )

        # Build report
        report = QualityReport()
        for full_item in expanded_items:
            if full_item:
                try:
                    quality = self._analyzer.analyze_item(full_item)
                    report.add_item(quality)
                except Exception as e:
                    logger.warning(f"Failed to analyze item: {e}")

        report.finalize()
        return report
