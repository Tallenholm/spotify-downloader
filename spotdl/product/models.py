"""Typed product-layer models used by the enhanced web experience."""

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

ContentPreference = Literal["explicit_only", "prefer_explicit", "any"]
ExplicitStatus = Literal["explicit", "clean", "non_explicit", "mixed_or_unknown"]
JobState = Literal[
    "queued",
    "resolving",
    "searching",
    "matched",
    "downloading",
    "transcoding",
    "tagging",
    "completed",
    "needs_review",
    "failed",
    "cancelled",
]


class CandidateDecision(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    REVIEW = "review"


class CandidateAssessment(BaseModel):
    accepted: bool
    decision: CandidateDecision
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class AlbumTrack(BaseModel):
    track_id: str
    name: str
    artists: List[str]
    duration: int
    track_number: int
    disc_number: int = 1
    explicit: bool = False
    spotify_url: str


class AlbumEdition(BaseModel):
    album_id: str
    name: str
    artists: List[str]
    artist_ids: List[str] = Field(default_factory=list)
    artwork_url: Optional[str] = None
    release_date: Optional[str] = None
    album_type: Optional[str] = None
    label: Optional[str] = None
    total_tracks: int = 0
    explicit_track_count: int = 0
    non_explicit_track_count: int = 0
    explicit_status: ExplicitStatus = "mixed_or_unknown"
    edition_tags: List[str] = Field(default_factory=list)
    spotify_url: str
    tracks: List[AlbumTrack] = Field(default_factory=list)
    sibling_album_ids: List[str] = Field(default_factory=list)
    grouping_confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class EditionFamily(BaseModel):
    family_key: str
    display_name: str
    artist_name: str
    editions: List[AlbumEdition]
    grouping_confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ArtistSummary(BaseModel):
    artist_id: str
    name: str
    spotify_url: str
    artwork_url: Optional[str] = None
    genres: List[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    content_preference: ContentPreference
    albums: List[AlbumEdition] = Field(default_factory=list)
    artists: List[ArtistSummary] = Field(default_factory=list)


class DownloadTrackRecord(BaseModel):
    job_track_id: str
    job_id: str
    track_id: str
    name: str
    artists: List[str]
    spotify_url: str
    explicit: bool
    position: int
    duration: int = 0
    track_number: int = 0
    disc_number: int = 1
    state: JobState = "queued"
    source_url: Optional[str] = None
    output_path: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class DownloadJobRecord(BaseModel):
    job_id: str
    kind: Literal["album", "track"]
    source_id: str
    title: str
    content_preference: ContentPreference
    state: JobState = "queued"
    created_at: str
    updated_at: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    recovery_note: Optional[str] = None
    tracks: List[DownloadTrackRecord] = Field(default_factory=list)
