"""
Series matching service.

Uses rapidfuzz for fuzzy string matching to match Audiobookshelf series
with Audible catalog series and identify missing books.
"""

import logging
import re
from typing import TYPE_CHECKING, Any, Optional

from rapidfuzz import fuzz

from ..audible import PlusCatalogInfo, PricingInfo
from .models import (
    ABSSeriesBook,
    ABSSeriesInfo,
    AudibleSeriesBook,
    AudibleSeriesInfo,
    MatchConfidence,
    MatchResult,
    MissingBook,
    SeriesAnalysisReport,
    SeriesComparisonResult,
    SeriesMatchResult,
)

if TYPE_CHECKING:
    from ..abs import ABSClient
    from ..audible import AudibleClient
    from ..cache import SQLiteCache

logger = logging.getLogger(__name__)


def _score_to_confidence(score: float) -> MatchConfidence:
    """Convert fuzzy match score to confidence level."""
    if score >= 100:
        return MatchConfidence.EXACT
    elif score >= 90:
        return MatchConfidence.HIGH
    elif score >= 75:
        return MatchConfidence.MEDIUM
    elif score >= 60:
        return MatchConfidence.LOW
    return MatchConfidence.NO_MATCH


def _normalize_title(title: str) -> str:
    """Normalize title for better matching."""
    # Remove common prefixes/suffixes
    title = title.lower().strip()
    # Remove "the " prefix
    if title.startswith("the "):
        title = title[4:]
    # Remove series indicators like "(Series Name #1)"
    title = re.sub(r"\s*\([^)]*#\d+[^)]*\)", "", title)
    title = re.sub(r"\s*,?\s*(book|volume|part)\s*\d+", "", title, flags=re.IGNORECASE)
    return title.strip()


def _normalize_series_name(name: str) -> str:
    """Normalize series name for matching."""
    name = name.lower().strip()
    # Remove "the " prefix
    if name.startswith("the "):
        name = name[4:]
    # Remove common suffixes
    for suffix in [" series", " saga", " trilogy", " duology", " books"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()


class SeriesMatcher:
    """
    Service for matching ABS series with Audible catalog.

    Uses rapidfuzz for fuzzy string matching to handle slight naming
    differences between ABS and Audible.

    Example:
        matcher = SeriesMatcher(abs_client, audible_client, cache)
        result = matcher.compare_series(abs_series_info)
    """

    MAX_SERIES_FETCH = 10000  # Maximum series to fetch when no limit specified

    def __init__(
        self,
        abs_client: "ABSClient",
        audible_client: Optional["AudibleClient"] = None,
        cache: Optional["SQLiteCache"] = None,
        min_match_score: float = 60.0,
    ):
        """
        Initialize the matcher.

        Args:
            abs_client: ABS API client
            audible_client: Audible API client
            cache: Optional cache for storing results
            min_match_score: Minimum score (0-100) to consider a match
        """
        self._abs = abs_client
        self._audible = audible_client
        self._cache = cache
        self.min_match_score = min_match_score

    @staticmethod
    def _extract_price(price_data: dict[str, Any] | None) -> float | None:
        """
        Extract base list price from price dict.

        Uses shared PricingInfo model for consistent parsing.
        """
        pricing = PricingInfo.from_api_response(price_data)
        return pricing.list_price if pricing else None

    @staticmethod
    def _check_plus_catalog(product: Any) -> bool:
        """
        Check if product is in Plus Catalog.

        Checks both is_ayce attribute and plans array for consistency.
        """
        # Quick check via is_ayce attribute
        if getattr(product, "is_ayce", False):
            return True

        # Check plans if available (more reliable)
        plans = getattr(product, "plans", None)
        if plans:
            plus_info = PlusCatalogInfo.from_api_response(plans)
            return plus_info.is_plus_catalog

        return False

    # -------------------------------------------------------------------------
    # ABS Series Fetching
    # -------------------------------------------------------------------------

    def get_abs_series(
        self,
        library_id: str,
        limit: int = 0,
        use_cache: bool = True,
    ) -> list[ABSSeriesInfo]:
        """
        Get all series from an ABS library.

        Args:
            library_id: ABS library ID
            limit: Max series to fetch (0 = all)
            use_cache: Use cached results

        Returns:
            List of ABSSeriesInfo
        """
        cache_key = f"abs_series_{library_id}"

        if use_cache and self._cache:
            cached = self._cache.get("series_analysis", cache_key)
            if cached:
                return [ABSSeriesInfo.model_validate(s) for s in cached]

        # Fetch from ABS (use large limit if 0 to get all series)
        fetch_limit = limit if limit > 0 else self.MAX_SERIES_FETCH
        raw_series = self._abs.get_library_series(library_id, limit=fetch_limit)
        results = raw_series.get("results", [])

        series_list = []
        for raw in results:
            try:
                # Convert raw API response to our model
                books = []
                for book_data in raw.get("books", []):
                    media = book_data.get("media", {})
                    metadata = media.get("metadata", {})

                    # Get sequence from either book or series data
                    sequence = book_data.get("sequence")

                    books.append(
                        ABSSeriesBook(
                            id=book_data.get("id", ""),
                            title=metadata.get("title", "Unknown"),
                            sequence=sequence,
                            asin=metadata.get("asin"),
                            isbn=metadata.get("isbn"),
                            author_name=metadata.get("authorName", metadata.get("author_name")),
                            narrator_name=metadata.get("narratorName", metadata.get("narrator_name")),
                            duration=media.get("duration", 0.0),
                            added_at=book_data.get("addedAt", book_data.get("added_at")),
                        )
                    )

                series_info = ABSSeriesInfo.model_validate(
                    {
                        "id": raw.get("id", ""),
                        "name": raw.get("name", "Unknown"),
                        "nameIgnorePrefix": raw.get("nameIgnorePrefix"),
                        "description": raw.get("description"),
                        "addedAt": raw.get("addedAt"),
                        "totalDuration": raw.get("totalDuration", 0.0),
                        "books": books,
                    }
                )
                series_list.append(series_info)

            except Exception as e:
                logger.warning(f"Failed to parse series: {e}")
                continue

        # Cache results
        if self._cache:
            self._cache.set(
                "series_analysis",
                cache_key,
                [s.model_dump() for s in series_list],
                ttl_seconds=3600 * 24,  # 24 hour cache
            )

        return series_list

    # -------------------------------------------------------------------------
    # Audible Series Search
    # -------------------------------------------------------------------------

    def search_audible_series(
        self,
        series_name: str,
        author: str | None = None,
        max_results: int = 50,
        use_cache: bool = True,
    ) -> list[AudibleSeriesBook]:
        """
        Search Audible catalog for books in a series.

        Args:
            series_name: Name of the series to search
            author: Optional author filter
            max_results: Max results to return
            use_cache: Use cached results

        Returns:
            List of AudibleSeriesBook items
        """
        if not self._audible:
            return []
            
        # Search catalog with series as keyword
        search_results = self._audible.search_catalog(
            keywords=series_name,
            author=author,
            num_results=max_results,
            use_cache=use_cache,
        )

        # Filter and convert to our model
        series_books = []
        for product in search_results:
            # Check if this product is in the target series
            product_series = product.series or []
            in_series = False
            sequence = None

            for ps in product_series:
                # Fuzzy match series name
                score = fuzz.ratio(
                    _normalize_series_name(series_name),
                    _normalize_series_name(ps.title),
                )
                if score >= self.min_match_score:
                    in_series = True
                    sequence = ps.sequence
                    break

            if in_series:
                series_books.append(
                    AudibleSeriesBook(
                        asin=product.asin,
                        title=product.title,
                        subtitle=product.subtitle,
                        sequence=sequence,
                        author_name=product.primary_author,
                        narrator_name=product.primary_narrator,
                        runtime_minutes=product.runtime_length_min,
                        release_date=product.release_date,
                        is_in_library=False,  # Would need to check user library
                    )
                )

        return series_books

    def get_series_books_by_asin(
        self,
        asins: list[str],
        use_cache: bool = True,
    ) -> tuple[list[AudibleSeriesBook], str | None]:
        """
        Look up books by ASIN and extract series info.

        This is more reliable than search when we have ASINs from ABS.
        Returns both the series books found and the detected series ASIN.

        Args:
            asins: List of ASINs to look up
            use_cache: Use cached results

        Returns:
            Tuple of (list of AudibleSeriesBook, series_asin or None)
        """
        if not self._audible:
            return [], None

        series_asin: str | None = None
        _series_name: str | None = None  # Captured but not returned; kept for consistency
        all_series_books: dict[str, AudibleSeriesBook] = {}  # keyed by ASIN to avoid duplicates

        for asin in asins:
            if not asin:
                continue

            try:
                product = self._audible.get_catalog_product(asin, use_cache=use_cache)
                if not product:
                    continue

                # Check if it's in a series
                for ps in product.series or []:
                    if series_asin is None:
                        series_asin = ps.asin
                        _series_name = ps.title

                    # Add this book
                    all_series_books[product.asin] = AudibleSeriesBook(
                        asin=product.asin,
                        title=product.title,
                        subtitle=product.subtitle,
                        sequence=ps.sequence,
                        author_name=product.primary_author,
                        narrator_name=product.primary_narrator,
                        runtime_minutes=product.runtime_length_min,
                        release_date=product.release_date,
                        is_in_library=False,
                    )
                    break  # Use first series match

            except Exception as e:
                logger.warning(f"Failed to look up ASIN {asin}: {e}")
                continue

        return list(all_series_books.values()), series_asin

    def get_complete_series_from_sims(
        self,
        seed_asin: str,
        use_cache: bool = True,
    ) -> tuple[list[AudibleSeriesBook], str | None, str | None]:
        """
        Discover ALL books in a series using the /sims endpoint.

        This is the most powerful method for series discovery - given just
        ONE ASIN from a series, it returns ALL books in that series on Audible.

        Args:
            seed_asin: ASIN of any book in the series
            use_cache: Use cached results

        Returns:
            Tuple of (all series books, series_asin, series_name)
        """
        if not self._audible:
            return [], None, None

        series_asin: str | None = None
        series_name: str | None = None
        all_series_books: dict[str, AudibleSeriesBook] = {}  # keyed by ASIN to avoid duplicates

        # First, get the seed product to get series info
        try:
            seed_product = self._audible.get_catalog_product(seed_asin, use_cache=use_cache)
            if seed_product and seed_product.series:
                ps = seed_product.series[0]  # Use first series
                series_asin = ps.asin
                series_name = ps.title

                # Add the seed book itself with full metadata
                all_series_books[seed_product.asin] = AudibleSeriesBook(
                    asin=seed_product.asin,
                    title=seed_product.title,
                    subtitle=seed_product.subtitle,
                    sequence=ps.sequence,
                    author_name=seed_product.primary_author,
                    narrator_name=seed_product.primary_narrator,
                    runtime_minutes=seed_product.runtime_length_min,
                    release_date=seed_product.release_date,
                    is_in_library=False,
                    price=self._extract_price(seed_product.price),
                    is_in_plus_catalog=self._check_plus_catalog(seed_product),
                    language=seed_product.language,
                    publisher_name=seed_product.publisher_name,
                    summary=seed_product.merchandising_summary,
                )
        except Exception as e:
            logger.warning(f"Failed to look up seed ASIN {seed_asin}: {e}")

        # Now use /sims to get ALL other books in the series
        try:
            sims_products = self._audible.get_series_books_from_sims(seed_asin, use_cache=use_cache)

            for product in sims_products:
                if product.asin in all_series_books:
                    continue  # Skip duplicates

                # Find the series info for this product
                sequence = None
                for ps in product.series or []:
                    # Match to our detected series
                    if series_asin and ps.asin == series_asin:
                        sequence = ps.sequence
                        break
                    elif series_name and ps.title:
                        # Fuzzy match series name
                        score = fuzz.ratio(
                            _normalize_series_name(series_name),
                            _normalize_series_name(ps.title),
                        )
                        if score >= 80:
                            sequence = ps.sequence
                            if not series_asin:
                                series_asin = ps.asin
                            break

                # Add this book with full metadata
                all_series_books[product.asin] = AudibleSeriesBook(
                    asin=product.asin,
                    title=product.title,
                    subtitle=product.subtitle,
                    sequence=sequence,
                    author_name=product.primary_author,
                    narrator_name=product.primary_narrator,
                    runtime_minutes=product.runtime_length_min,
                    release_date=product.release_date,
                    is_in_library=False,
                    price=self._extract_price(product.price),
                    is_in_plus_catalog=self._check_plus_catalog(product),
                    language=product.language,
                    publisher_name=product.publisher_name,
                    summary=product.merchandising_summary,
                )

            logger.debug(
                f"Sims discovery found {len(all_series_books)} books for series "
                f"'{series_name}' (ASIN: {series_asin})"
            )

        except Exception as e:
            logger.warning(f"Failed to get sims for ASIN {seed_asin}: {e}")

        return list(all_series_books.values()), series_asin, series_name

    # -------------------------------------------------------------------------
    # Matching Logic
    # -------------------------------------------------------------------------

    def match_book(
        self,
        abs_book: ABSSeriesBook,
        audible_books: list[AudibleSeriesBook],
    ) -> MatchResult:
        """
        Match an ABS book to an Audible book.

        Uses multiple strategies:
        1. Exact ASIN match
        2. Title fuzzy match
        3. Title + author fuzzy match

        Args:
            abs_book: ABS book to match
            audible_books: List of potential Audible matches

        Returns:
            MatchResult with best match
        """
        best_match: AudibleSeriesBook | None = None
        best_score = 0.0
        match_method = None

        # Strategy 1: ASIN match (exact)
        if abs_book.asin:
            for aud_book in audible_books:
                if aud_book.asin == abs_book.asin:
                    return MatchResult(
                        abs_book=abs_book,
                        audible_book=aud_book,
                        match_score=100.0,
                        confidence=MatchConfidence.EXACT,
                        matched_by="asin",
                    )

        # Strategy 2: Title fuzzy match
        abs_title_norm = _normalize_title(abs_book.title)
        for aud_book in audible_books:
            aud_title_norm = _normalize_title(aud_book.title)
            score = fuzz.ratio(abs_title_norm, aud_title_norm)

            if score > best_score:
                best_score = score
                best_match = aud_book
                match_method = "title"

        # Strategy 3: Title + author (if we have author)
        if abs_book.author_name:
            abs_combined = f"{abs_title_norm} {abs_book.author_name.lower()}"
            for aud_book in audible_books:
                if aud_book.author_name:
                    aud_combined = f"{_normalize_title(aud_book.title)} {aud_book.author_name.lower()}"
                    score = fuzz.token_set_ratio(abs_combined, aud_combined)

                    if score > best_score:
                        best_score = score
                        best_match = aud_book
                        match_method = "title+author"

        # Return best match if above threshold
        if best_score >= self.min_match_score and best_match:
            return MatchResult(
                abs_book=abs_book,
                audible_book=best_match,
                match_score=best_score,
                confidence=_score_to_confidence(best_score),
                matched_by=match_method,
            )

        return MatchResult(
            abs_book=abs_book,
            audible_book=None,
            match_score=best_score,
            confidence=MatchConfidence.NO_MATCH,
            matched_by=None,
        )

    def match_series(
        self,
        abs_series: ABSSeriesInfo,
        audible_series_name: str | None = None,
    ) -> SeriesMatchResult:
        """
        Match an ABS series name to Audible.

        Args:
            abs_series: ABS series info
            audible_series_name: Optional known Audible series name

        Returns:
            SeriesMatchResult
        """
        if audible_series_name:
            score = fuzz.ratio(
                _normalize_series_name(abs_series.name),
                _normalize_series_name(audible_series_name),
            )
            return SeriesMatchResult(
                abs_series=abs_series,
                audible_series=AudibleSeriesInfo(title=audible_series_name),
                name_match_score=score,
                confidence=_score_to_confidence(score),
            )

        return SeriesMatchResult(
            abs_series=abs_series,
            audible_series=None,
            name_match_score=0.0,
            confidence=MatchConfidence.NO_MATCH,
        )

    def compare_series(
        self,
        abs_series: ABSSeriesInfo,
        use_cache: bool = True,
    ) -> SeriesComparisonResult:
        """
        Compare an ABS series with Audible catalog.

        This is the main entry point for series comparison. It:
        1. Uses /sims endpoint to discover ALL books in a series (best method)
        2. Falls back to ASIN lookup if sims fails
        3. Falls back to keyword search as last resort
        4. Matches ABS books to Audible books
        5. Identifies missing books with full metadata

        Args:
            abs_series: ABS series to analyze
            use_cache: Use cached Audible results

        Returns:
            SeriesComparisonResult
        """
        audible_books: list[AudibleSeriesBook] = []
        series_asin: str | None = None
        series_name: str | None = None

        # Get ASINs from ABS books
        abs_asins = [b.asin for b in abs_series.books if b.asin]

        # Strategy 1: Use /sims endpoint to discover ALL books in the series
        # This is the most reliable way to find missing books
        if abs_asins:
            # Use first available ASIN as seed
            seed_asin = abs_asins[0]
            audible_books, series_asin, series_name = self.get_complete_series_from_sims(seed_asin, use_cache=use_cache)
            if audible_books:
                logger.debug(
                    f"Sims discovery found {len(audible_books)} total books for '{abs_series.name}' "
                    f"(series: '{series_name}', ASIN: {series_asin})"
                )

        # Strategy 2: Fall back to ASIN lookup if sims didn't work
        if not audible_books and abs_asins:
            audible_books, series_asin = self.get_series_books_by_asin(abs_asins, use_cache=use_cache)
            logger.debug(f"ASIN lookup found {len(audible_books)} books for {abs_series.name}")

        # Strategy 3: Fall back to keyword search if ASIN lookup didn't work
        if not audible_books:
            primary_author = None
            if abs_series.books:
                primary_author = abs_series.books[0].author_name

            audible_books = self.search_audible_series(
                series_name=abs_series.name,
                author=primary_author,
                use_cache=use_cache,
            )
            logger.debug(f"Keyword search found {len(audible_books)} books for {abs_series.name}")

        # Create series match result
        if audible_books:
            # We found books - assume series match
            series_match = SeriesMatchResult(
                abs_series=abs_series,
                audible_series=AudibleSeriesInfo(
                    asin=series_asin,
                    title=series_name or abs_series.name,
                    book_count=len(audible_books),
                    books=audible_books,
                ),
                name_match_score=100.0,  # Since we found matching books
                confidence=MatchConfidence.HIGH if series_asin else MatchConfidence.MEDIUM,
            )
        else:
            series_match = SeriesMatchResult(
                abs_series=abs_series,
                audible_series=None,
                name_match_score=0.0,
                confidence=MatchConfidence.NO_MATCH,
            )

        # Match individual books
        matched_books: list[MatchResult] = []
        matched_asins: set[str] = set()

        for abs_book in abs_series.books:
            match_result = self.match_book(abs_book, audible_books)
            matched_books.append(match_result)
            if match_result.audible_book:
                matched_asins.add(match_result.audible_book.asin)

        # Find missing books (in Audible but not in ABS)
        missing_books: list[MissingBook] = []
        for aud_book in audible_books:
            if aud_book.asin not in matched_asins:
                missing_books.append(
                    MissingBook(
                        asin=aud_book.asin,
                        title=aud_book.title,
                        subtitle=aud_book.subtitle,
                        sequence=aud_book.sequence,
                        author_name=aud_book.author_name,
                        narrator_name=aud_book.narrator_name,
                        runtime_hours=aud_book.runtime_hours,
                        release_date=aud_book.release_date,
                        price=aud_book.price,
                        is_in_plus_catalog=aud_book.is_in_plus_catalog,
                        audible_url=f"https://www.audible.com/pd/{aud_book.asin}" if aud_book.asin else None,
                        language=aud_book.language,
                        publisher_name=aud_book.publisher_name,
                        summary=aud_book.summary,
                    )
                )

        return SeriesComparisonResult(
            series_match=series_match,
            matched_books=matched_books,
            missing_books=missing_books,
            abs_book_count=len(abs_series.books),
            audible_book_count=len(audible_books),
            matched_count=len([m for m in matched_books if m.audible_book]),
            missing_count=len(missing_books),
        )

    # -------------------------------------------------------------------------
    # Full Library Analysis
    # -------------------------------------------------------------------------

    def analyze_library(
        self,
        library_id: str,
        library_name: str | None = None,
        max_series: int = 0,
        use_cache: bool = True,
        progress_callback=None,
    ) -> SeriesAnalysisReport:
        """
        Analyze all series in an ABS library.

        Args:
            library_id: ABS library ID
            library_name: Optional library name for report
            max_series: Max series to analyze (0 = all)
            use_cache: Use cached results
            progress_callback: Optional callback(current, total, series_name)

        Returns:
            SeriesAnalysisReport
        """
        # Get all series from ABS
        all_series = self.get_abs_series(library_id, use_cache=use_cache)

        if max_series > 0:
            all_series = all_series[:max_series]

        # Analyze each series
        results: list[SeriesComparisonResult] = []
        total = len(all_series)

        for idx, series in enumerate(all_series):
            if progress_callback:
                progress_callback(idx, total, series.name)

            try:
                result = self.compare_series(series, use_cache=use_cache)
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to analyze series '{series.name}': {e}")
                continue

        # Build report
        report = SeriesAnalysisReport(
            library_id=library_id,
            library_name=library_name,
            series_results=results,
            total_series=len(results),
            series_matched=len([r for r in results if r.series_match.audible_series]),
            series_complete=len([r for r in results if r.is_complete]),
            total_missing_books=sum(r.missing_count for r in results),
            total_missing_hours=sum(r.total_missing_hours for r in results),
        )

        return report
