"""
Pydantic models for Audiobookshelf API responses.
"""

from typing import Any

from pydantic import BaseModel, Field


class Folder(BaseModel):
    """Library folder."""

    id: str
    full_path: str = Field(alias="fullPath")
    library_id: str = Field(alias="libraryId")
    added_at: int | None = Field(default=None, alias="addedAt")


class LibrarySettings(BaseModel):
    """Library settings."""

    cover_aspect_ratio: int = Field(default=1, alias="coverAspectRatio")
    disable_watcher: bool = Field(default=False, alias="disableWatcher")
    skip_matching_media_with_asin: bool = Field(default=False, alias="skipMatchingMediaWithAsin")
    skip_matching_media_with_isbn: bool = Field(default=False, alias="skipMatchingMediaWithIsbn")
    auto_scan_cron_expression: str | None = Field(default=None, alias="autoScanCronExpression")


class Library(BaseModel):
    """ABS Library model."""

    id: str
    name: str
    folders: list[Folder] = Field(default_factory=list)
    display_order: int = Field(alias="displayOrder")
    icon: str
    media_type: str = Field(alias="mediaType")
    provider: str
    settings: LibrarySettings = Field(default_factory=LibrarySettings)
    created_at: int = Field(alias="createdAt")
    last_update: int = Field(alias="lastUpdate")

    @property
    def is_book_library(self) -> bool:
        return self.media_type == "book"

    @property
    def is_podcast_library(self) -> bool:
        return self.media_type == "podcast"


class FileMetadata(BaseModel):
    """File metadata."""

    filename: str
    ext: str
    path: str
    rel_path: str = Field(alias="relPath")
    size: int
    mtime_ms: int = Field(alias="mtimeMs")
    ctime_ms: int = Field(alias="ctimeMs")
    birthtime_ms: int = Field(default=0, alias="birthtimeMs")


class AudioMetaTags(BaseModel):
    """Audio file meta tags."""

    tag_album: str | None = Field(default=None, alias="tagAlbum")
    tag_artist: str | None = Field(default=None, alias="tagArtist")
    tag_genre: str | None = Field(default=None, alias="tagGenre")
    tag_title: str | None = Field(default=None, alias="tagTitle")
    tag_track: str | None = Field(default=None, alias="tagTrack")
    tag_album_artist: str | None = Field(default=None, alias="tagAlbumArtist")
    tag_composer: str | None = Field(default=None, alias="tagComposer")
    tag_date: str | None = Field(default=None, alias="tagDate")
    tag_encoder: str | None = Field(default=None, alias="tagEncoder")


class AudioFile(BaseModel):
    """Audio file in a library item."""

    index: int
    ino: str
    metadata: FileMetadata
    added_at: int = Field(alias="addedAt")
    updated_at: int = Field(alias="updatedAt")
    track_num_from_meta: int | None = Field(default=None, alias="trackNumFromMeta")
    disc_num_from_meta: int | None = Field(default=None, alias="discNumFromMeta")
    track_num_from_filename: int | None = Field(default=None, alias="trackNumFromFilename")
    disc_num_from_filename: int | None = Field(default=None, alias="discNumFromFilename")
    manual_track_num: int | None = Field(default=None, alias="manualTrackNum")
    invalid: bool = Field(default=False)
    exclude: bool = Field(default=False)
    error: str | None = Field(default=None)
    format: str | None = Field(default=None)
    duration: float = Field(default=0.0)
    bit_rate: int = Field(default=0, alias="bitRate")
    language: str | None = Field(default=None)
    codec: str | None = Field(default=None)
    time_base: str | None = Field(default=None, alias="timeBase")
    channels: int = Field(default=2)
    channel_layout: str | None = Field(default=None, alias="channelLayout")
    chapters: list[dict] = Field(default_factory=list)
    embedded_cover_art: str | None = Field(default=None, alias="embeddedCoverArt")
    meta_tags: AudioMetaTags | None = Field(default=None, alias="metaTags")
    mime_type: str = Field(default="audio/mpeg", alias="mimeType")


class AudioTrack(BaseModel):
    """Audio track for playback."""

    index: int
    start_offset: float = Field(alias="startOffset")
    duration: float
    title: str
    content_url: str = Field(alias="contentUrl")
    mime_type: str = Field(alias="mimeType")
    metadata: FileMetadata | None = None


class BookChapter(BaseModel):
    """Book chapter."""

    id: int
    start: float
    end: float
    title: str


class SeriesSequence(BaseModel):
    """Series with sequence number."""

    id: str
    name: str
    sequence: str | None = None


class AuthorMinified(BaseModel):
    """Minified author."""

    id: str
    name: str


class Author(BaseModel):
    """Full author model."""

    id: str
    asin: str | None = None
    name: str
    description: str | None = None
    image_path: str | None = Field(default=None, alias="imagePath")
    added_at: int = Field(alias="addedAt")
    updated_at: int = Field(alias="updatedAt")
    num_books: int | None = Field(default=None, alias="numBooks")


class Series(BaseModel):
    """Series model."""

    id: str
    name: str
    description: str | None = None
    added_at: int | None = Field(default=None, alias="addedAt")
    updated_at: int | None = Field(default=None, alias="updatedAt")


class BookMetadata(BaseModel):
    """Book metadata."""

    title: str
    title_ignore_prefix: str | None = Field(default=None, alias="titleIgnorePrefix")
    subtitle: str | None = None
    authors: list[AuthorMinified] = Field(default_factory=list)
    narrators: list[str] = Field(default_factory=list)
    series: list[SeriesSequence] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    published_year: str | None = Field(default=None, alias="publishedYear")
    published_date: str | None = Field(default=None, alias="publishedDate")
    publisher: str | None = None
    description: str | None = None
    isbn: str | None = None
    asin: str | None = None
    language: str | None = None
    explicit: bool = Field(default=False)
    abridged: bool | None = None

    # Computed fields from API
    author_name: str | None = Field(default=None, alias="authorName")
    author_name_lf: str | None = Field(default=None, alias="authorNameLF")
    narrator_name: str | None = Field(default=None, alias="narratorName")
    series_name: str | None = Field(default=None, alias="seriesName")


class BookMedia(BaseModel):
    """Book media information."""

    library_item_id: str | None = Field(default=None, alias="libraryItemId")
    metadata: BookMetadata
    cover_path: str | None = Field(default=None, alias="coverPath")
    tags: list[str] = Field(default_factory=list)
    audio_files: list[AudioFile] = Field(default_factory=list, alias="audioFiles")
    chapters: list[BookChapter] = Field(default_factory=list)
    duration: float = Field(default=0.0)
    size: int = Field(default=0)
    tracks: list[AudioTrack] = Field(default_factory=list)
    ebook_file: dict | None = Field(default=None, alias="ebookFile")

    # Minified fields
    num_tracks: int | None = Field(default=None, alias="numTracks")
    num_audio_files: int | None = Field(default=None, alias="numAudioFiles")
    num_chapters: int | None = Field(default=None, alias="numChapters")
    ebook_file_format: str | None = Field(default=None, alias="ebookFileFormat")


class LibraryFile(BaseModel):
    """Library file."""

    ino: str
    metadata: FileMetadata
    added_at: int = Field(alias="addedAt")
    updated_at: int = Field(alias="updatedAt")
    file_type: str = Field(alias="fileType")


class LibraryItem(BaseModel):
    """Library item base model."""

    id: str
    ino: str
    library_id: str = Field(alias="libraryId")
    folder_id: str = Field(alias="folderId")
    path: str
    rel_path: str = Field(alias="relPath")
    is_file: bool = Field(alias="isFile")
    mtime_ms: int = Field(alias="mtimeMs")
    ctime_ms: int = Field(alias="ctimeMs")
    birthtime_ms: int = Field(default=0, alias="birthtimeMs")
    added_at: int = Field(alias="addedAt")
    updated_at: int = Field(alias="updatedAt")
    is_missing: bool = Field(default=False, alias="isMissing")
    is_invalid: bool = Field(default=False, alias="isInvalid")
    media_type: str = Field(alias="mediaType")
    media: BookMedia

    @property
    def is_book(self) -> bool:
        return self.media_type == "book"


class LibraryItemMinified(LibraryItem):
    """Minified library item with fewer fields."""

    num_files: int | None = Field(default=None, alias="numFiles")
    size: int | None = None


class LibraryItemExpanded(LibraryItem):
    """Expanded library item with full details."""

    last_scan: int | None = Field(default=None, alias="lastScan")
    scan_version: str | None = Field(default=None, alias="scanVersion")
    library_files: list[LibraryFile] = Field(default_factory=list, alias="libraryFiles")
    size: int = Field(default=0)


class LibraryItemsResponse(BaseModel):
    """Response from library items endpoint."""

    results: list[LibraryItemMinified]
    total: int
    limit: int
    page: int
    sort_by: str | None = Field(default=None, alias="sortBy")
    sort_desc: bool | None = Field(default=None, alias="sortDesc")
    filter_by: str | None = Field(default=None, alias="filterBy")
    media_type: str = Field(alias="mediaType")
    minified: bool = Field(default=True)
    collapseseries: bool = Field(default=False)
    include: str | None = None


class LibrariesResponse(BaseModel):
    """Response from libraries endpoint."""

    libraries: list[Library]


class LibraryStats(BaseModel):
    """Library statistics."""

    total_items: int = Field(alias="totalItems")
    total_authors: int = Field(alias="totalAuthors")
    total_genres: int = Field(alias="totalGenres")
    total_duration: float = Field(alias="totalDuration")
    num_audio_tracks: int = Field(alias="numAudioTracks")
    total_size: int = Field(alias="totalSize")


class UserPermissions(BaseModel):
    """User permissions."""

    download: bool = Field(default=False)
    update: bool = Field(default=False)
    delete: bool = Field(default=False)
    upload: bool = Field(default=False)
    access_all_libraries: bool = Field(default=False, alias="accessAllLibraries")
    access_all_tags: bool = Field(default=False, alias="accessAllTags")
    access_explicit_content: bool = Field(default=False, alias="accessExplicitContent")


class User(BaseModel):
    """ABS User model."""

    id: str
    username: str
    type: str
    token: str
    media_progress: list[dict] = Field(default_factory=list, alias="mediaProgress")
    bookmarks: list[dict] = Field(default_factory=list)
    is_active: bool = Field(default=True, alias="isActive")
    is_locked: bool = Field(default=False, alias="isLocked")
    last_seen: int | None = Field(default=None, alias="lastSeen")
    created_at: int = Field(alias="createdAt")
    permissions: UserPermissions = Field(default_factory=UserPermissions)
    libraries_accessible: list[str] = Field(default_factory=list, alias="librariesAccessible")


class CollectionBase(BaseModel):
    """Base ABS Collection model (shared fields)."""

    id: str
    library_id: str = Field(alias="libraryId")
    user_id: str = Field(alias="userId")
    name: str
    description: str | None = None
    last_update: int = Field(alias="lastUpdate")
    created_at: int = Field(alias="createdAt")

    model_config = {"extra": "ignore", "populate_by_name": True}


class Collection(CollectionBase):
    """ABS Collection model with book IDs."""

    books: list[str] = Field(default_factory=list)  # List of library item IDs

    @property
    def book_count(self) -> int:
        """Number of books in collection."""
        return len(self.books)


class CollectionExpanded(CollectionBase):
    """Collection with expanded book data."""

    books: list[dict[str, Any]] = Field(default_factory=list)  # Full library item dicts

    @property
    def book_count(self) -> int:
        """Number of books in collection."""
        return len(self.books)

    @property
    def book_ids(self) -> list[str]:
        """Get book IDs from expanded books."""
        return [b.get("id", "") for b in self.books if isinstance(b, dict)]


class SeriesProgress(BaseModel):
    """Series progress tracking."""

    library_item_ids: list[str] = Field(default_factory=list, alias="libraryItemIds")
    library_item_ids_finished: list[str] = Field(default_factory=list, alias="libraryItemIdsFinished")
    is_finished: bool = Field(default=False, alias="isFinished")

    model_config = {"extra": "ignore", "populate_by_name": True}

    @property
    def total_books(self) -> int:
        """Total number of books in series."""
        return len(self.library_item_ids)

    @property
    def finished_count(self) -> int:
        """Number of finished books."""
        return len(self.library_item_ids_finished)

    @property
    def progress_percent(self) -> float:
        """Completion percentage."""
        if not self.library_item_ids:
            return 0.0
        return (len(self.library_item_ids_finished) / len(self.library_item_ids)) * 100


# =============================================================================
# API Response Models for dict-returning endpoints
# =============================================================================


class SeriesBook(BaseModel):
    """Book within a series response."""

    id: str
    library_id: str = Field(alias="libraryId")
    path: str | None = None
    added_at: int | None = Field(default=None, alias="addedAt")
    media: BookMedia | None = None
    sequence: str | None = None

    model_config = {"extra": "ignore", "populate_by_name": True}


class SeriesWithBooks(BaseModel):
    """Series with its books."""

    id: str
    name: str
    description: str | None = None
    added_at: int | None = Field(default=None, alias="addedAt")
    updated_at: int | None = Field(default=None, alias="updatedAt")
    progress: SeriesProgress | None = None
    books: list[SeriesBook] = Field(default_factory=list)

    model_config = {"extra": "ignore", "populate_by_name": True}

    @property
    def book_count(self) -> int:
        """Number of books in series."""
        return len(self.books)


class SeriesListResponse(BaseModel):
    """Response from GET /libraries/:id/series endpoint."""

    results: list[SeriesWithBooks]
    total: int
    limit: int
    page: int

    model_config = {"extra": "ignore", "populate_by_name": True}


class SearchResultBook(BaseModel):
    """Search result for a book."""

    library_item: LibraryItemMinified | None = Field(default=None, alias="libraryItem")
    match_key: str | None = Field(default=None, alias="matchKey")
    match_text: str | None = Field(default=None, alias="matchText")

    model_config = {"extra": "ignore", "populate_by_name": True}


class SearchResultSeries(BaseModel):
    """Search result for a series."""

    series: Series
    books: list[LibraryItemMinified] = Field(default_factory=list)

    model_config = {"extra": "ignore", "populate_by_name": True}


class SearchResultAuthor(BaseModel):
    """Search result for an author."""

    id: str
    name: str

    model_config = {"extra": "ignore", "populate_by_name": True}


class SearchResponse(BaseModel):
    """Response from library search endpoint."""

    book: list[SearchResultBook] = Field(default_factory=list)
    series: list[SearchResultSeries] = Field(default_factory=list)
    authors: list[SearchResultAuthor] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    narrators: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore", "populate_by_name": True}

    @property
    def total_results(self) -> int:
        """Total number of search results."""
        return len(self.book) + len(self.series) + len(self.authors) + len(self.tags)


class AuthorSearchResult(BaseModel):
    """Result from author search."""

    id: str
    name: str
    asin: str | None = None
    num_books: int = Field(default=0, alias="numBooks")

    model_config = {"extra": "ignore", "populate_by_name": True}


class AuthorSearchResponse(BaseModel):
    """Response from /search/authors endpoint."""

    results: list[AuthorSearchResult] = Field(default_factory=list)

    model_config = {"extra": "ignore", "populate_by_name": True}


class BookSearchResult(BaseModel):
    """Result from metadata provider book search."""

    title: str
    author: str | None = None
    asin: str | None = None
    isbn: str | None = None
    cover: str | None = None
    description: str | None = None
    publish_year: str | None = Field(default=None, alias="publishYear")
    publisher: str | None = None
    series: str | None = None
    sequence: str | None = None

    model_config = {"extra": "ignore", "populate_by_name": True}


class SeriesResponse(BaseModel):
    """Response from GET /series/:id endpoint."""

    id: str
    name: str
    description: str | None = None
    added_at: int | None = Field(default=None, alias="addedAt")
    updated_at: int | None = Field(default=None, alias="updatedAt")
    library_id: str | None = Field(default=None, alias="libraryId")
    books: list[SeriesBook] = Field(default_factory=list)
    progress: SeriesProgress | None = None

    model_config = {"extra": "ignore", "populate_by_name": True}

    @property
    def book_count(self) -> int:
        """Number of books in series."""
        return len(self.books)
