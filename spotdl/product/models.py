"""Typed product-layer models used by the enhanced web experience."""

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

ContentPreference = Literal["explicit_only", "prefer_explicit", "any"]
ExplicitStatus = Literal["explicit", "clean", "non_explicit", "mixed_or_unknown"]


class CandidateDecision(str, Enum):
    """Decision produced by the explicit-content candidate policy."""

    ACCEPT = "accept"
    REJECT = "reject"
    REVIEW = "review"


class CandidateAssessment(BaseModel):
    """Explain whether a provider result satisfies the requested content policy."""

    accepted: bool
    decision: CandidateDecision
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class AlbumTrack(BaseModel):
    """Track information required by the product UI and queue."""

    track_id: str
    name: str
    artists: List[str]
    duration: int
    track_number: int
    disc_number: int = 1
    explicit: bool = False
    spotify_url: str


class AlbumEdition(BaseModel):
    """One exact Spotify album edition."""

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
    """Likely sibling releases of the same album, kept as exact separate IDs."""

    family_key: str
    display_name: str
    artist_name: str
    editions: List[AlbumEdition]
    grouping_confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ArtistSummary(BaseModel):
    """Artist result for discovery views."""

    artist_id: str
    name: str
    spotify_url: str
    artwork_url: Optional[str] = None
    genres: List[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Versioned discovery response consumed by the React app."""

    query: str
    content_preference: ContentPreference
    albums: List[AlbumEdition] = Field(default_factory=list)
    artists: List[ArtistSummary] = Field(default_factory=list)
