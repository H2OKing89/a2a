"""
Pydantic models for Audiobookshelf API responses.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Folder(BaseModel):
    """Library folder."""
    
    id: str
    full_path: str = Field(alias="fullPath")
    library_id: str = Field(alias="libraryId")
    added_at: Optional[int] = Field(default=None, alias="addedAt")


class LibrarySettings(BaseModel):
    """Library settings."""
    
    cover_aspect_ratio: int = Field(default=1, alias="coverAspectRatio")
    disable_watcher: bool = Field(default=False, alias="disableWatcher")
    skip_matching_media_with_asin: bool = Field(default=False, alias="skipMatchingMediaWithAsin")
    skip_matching_media_with_isbn: bool = Field(default=False, alias="skipMatchingMediaWithIsbn")
    auto_scan_cron_expression: Optional[str] = Field(default=None, alias="autoScanCronExpression")


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
    
    tag_album: Optional[str] = Field(default=None, alias="tagAlbum")
    tag_artist: Optional[str] = Field(default=None, alias="tagArtist")
    tag_genre: Optional[str] = Field(default=None, alias="tagGenre")
    tag_title: Optional[str] = Field(default=None, alias="tagTitle")
    tag_track: Optional[str] = Field(default=None, alias="tagTrack")
    tag_album_artist: Optional[str] = Field(default=None, alias="tagAlbumArtist")
    tag_composer: Optional[str] = Field(default=None, alias="tagComposer")
    tag_date: Optional[str] = Field(default=None, alias="tagDate")
    tag_encoder: Optional[str] = Field(default=None, alias="tagEncoder")


class AudioFile(BaseModel):
    """Audio file in a library item."""
    
    index: int
    ino: str
    metadata: FileMetadata
    added_at: int = Field(alias="addedAt")
    updated_at: int = Field(alias="updatedAt")
    track_num_from_meta: Optional[int] = Field(default=None, alias="trackNumFromMeta")
    disc_num_from_meta: Optional[int] = Field(default=None, alias="discNumFromMeta")
    track_num_from_filename: Optional[int] = Field(default=None, alias="trackNumFromFilename")
    disc_num_from_filename: Optional[int] = Field(default=None, alias="discNumFromFilename")
    manual_track_num: Optional[int] = Field(default=None, alias="manualTrackNum")
    invalid: bool = Field(default=False)
    exclude: bool = Field(default=False)
    error: Optional[str] = Field(default=None)
    format: Optional[str] = Field(default=None)
    duration: float = Field(default=0.0)
    bit_rate: int = Field(default=0, alias="bitRate")
    language: Optional[str] = Field(default=None)
    codec: Optional[str] = Field(default=None)
    time_base: Optional[str] = Field(default=None, alias="timeBase")
    channels: int = Field(default=2)
    channel_layout: Optional[str] = Field(default=None, alias="channelLayout")
    chapters: list[dict] = Field(default_factory=list)
    embedded_cover_art: Optional[str] = Field(default=None, alias="embeddedCoverArt")
    meta_tags: Optional[AudioMetaTags] = Field(default=None, alias="metaTags")
    mime_type: str = Field(default="audio/mpeg", alias="mimeType")


class AudioTrack(BaseModel):
    """Audio track for playback."""
    
    index: int
    start_offset: float = Field(alias="startOffset")
    duration: float
    title: str
    content_url: str = Field(alias="contentUrl")
    mime_type: str = Field(alias="mimeType")
    metadata: Optional[FileMetadata] = None


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
    sequence: Optional[str] = None


class AuthorMinified(BaseModel):
    """Minified author."""
    
    id: str
    name: str


class Author(BaseModel):
    """Full author model."""
    
    id: str
    asin: Optional[str] = None
    name: str
    description: Optional[str] = None
    image_path: Optional[str] = Field(default=None, alias="imagePath")
    added_at: int = Field(alias="addedAt")
    updated_at: int = Field(alias="updatedAt")
    num_books: Optional[int] = Field(default=None, alias="numBooks")


class Series(BaseModel):
    """Series model."""
    
    id: str
    name: str
    description: Optional[str] = None
    added_at: Optional[int] = Field(default=None, alias="addedAt")
    updated_at: Optional[int] = Field(default=None, alias="updatedAt")


class BookMetadata(BaseModel):
    """Book metadata."""
    
    title: str
    title_ignore_prefix: Optional[str] = Field(default=None, alias="titleIgnorePrefix")
    subtitle: Optional[str] = None
    authors: list[AuthorMinified] = Field(default_factory=list)
    narrators: list[str] = Field(default_factory=list)
    series: list[SeriesSequence] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    published_year: Optional[str] = Field(default=None, alias="publishedYear")
    published_date: Optional[str] = Field(default=None, alias="publishedDate")
    publisher: Optional[str] = None
    description: Optional[str] = None
    isbn: Optional[str] = None
    asin: Optional[str] = None
    language: Optional[str] = None
    explicit: bool = Field(default=False)
    abridged: Optional[bool] = None
    
    # Computed fields from API
    author_name: Optional[str] = Field(default=None, alias="authorName")
    author_name_lf: Optional[str] = Field(default=None, alias="authorNameLF")
    narrator_name: Optional[str] = Field(default=None, alias="narratorName")
    series_name: Optional[str] = Field(default=None, alias="seriesName")


class BookMedia(BaseModel):
    """Book media information."""
    
    library_item_id: Optional[str] = Field(default=None, alias="libraryItemId")
    metadata: BookMetadata
    cover_path: Optional[str] = Field(default=None, alias="coverPath")
    tags: list[str] = Field(default_factory=list)
    audio_files: list[AudioFile] = Field(default_factory=list, alias="audioFiles")
    chapters: list[BookChapter] = Field(default_factory=list)
    duration: float = Field(default=0.0)
    size: int = Field(default=0)
    tracks: list[AudioTrack] = Field(default_factory=list)
    ebook_file: Optional[dict] = Field(default=None, alias="ebookFile")
    
    # Minified fields
    num_tracks: Optional[int] = Field(default=None, alias="numTracks")
    num_audio_files: Optional[int] = Field(default=None, alias="numAudioFiles")
    num_chapters: Optional[int] = Field(default=None, alias="numChapters")
    ebook_file_format: Optional[str] = Field(default=None, alias="ebookFileFormat")


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
    
    num_files: Optional[int] = Field(default=None, alias="numFiles")
    size: Optional[int] = None


class LibraryItemExpanded(LibraryItem):
    """Expanded library item with full details."""
    
    last_scan: Optional[int] = Field(default=None, alias="lastScan")
    scan_version: Optional[str] = Field(default=None, alias="scanVersion")
    library_files: list[LibraryFile] = Field(default_factory=list, alias="libraryFiles")
    size: int = Field(default=0)


class LibraryItemsResponse(BaseModel):
    """Response from library items endpoint."""
    
    results: list[LibraryItemMinified]
    total: int
    limit: int
    page: int
    sort_by: Optional[str] = Field(default=None, alias="sortBy")
    sort_desc: Optional[bool] = Field(default=None, alias="sortDesc")
    filter_by: Optional[str] = Field(default=None, alias="filterBy")
    media_type: str = Field(alias="mediaType")
    minified: bool = Field(default=True)
    collapseseries: bool = Field(default=False)
    include: Optional[str] = None


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
    last_seen: Optional[int] = Field(default=None, alias="lastSeen")
    created_at: int = Field(alias="createdAt")
    permissions: UserPermissions = Field(default_factory=UserPermissions)
    libraries_accessible: list[str] = Field(default_factory=list, alias="librariesAccessible")
