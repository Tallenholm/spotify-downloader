"""Explicit-release classification and provider-candidate policy."""

import re
from typing import Iterable, List, Optional, Sequence, Tuple

from spotdl.product.models import (
    AlbumEdition,
    CandidateAssessment,
    CandidateDecision,
    ContentPreference,
    EditionFamily,
    ExplicitStatus,
)
from spotdl.types.result import Result
from spotdl.types.song import Song

CLEAN_MARKERS: Tuple[str, ...] = (
    "clean",
    "edited",
    "censored",
    "radio edit",
    "radio version",
)

EDITION_MARKERS: Tuple[Tuple[str, str], ...] = (
    ("deluxe", "Deluxe"),
    ("expanded", "Expanded"),
    ("anniversary", "Anniversary"),
    ("remaster", "Remastered"),
    ("reissue", "Reissue"),
    ("live", "Live"),
    ("clean", "Clean"),
    ("edited", "Clean"),
    ("explicit", "Explicit"),
)


def _normalized_text(value: str) -> str:
    """Normalize free text for conservative marker matching."""

    value = value.casefold().replace("–", "-").replace("—", "-")
    value = re.sub(r"[^\w\s-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def has_clean_marker(value: str) -> bool:
    """Return True when a title clearly identifies a clean/edited variant."""

    normalized = _normalized_text(value)
    return any(marker in normalized for marker in CLEAN_MARKERS)


def edition_tags(name: str, explicit_status: ExplicitStatus) -> List[str]:
    """Derive user-facing edition tags without changing release identity."""

    normalized = _normalized_text(name)
    tags: List[str] = []
    for marker, label in EDITION_MARKERS:
        if marker in normalized and label not in tags:
            tags.append(label)

    if explicit_status == "explicit" and "Explicit" not in tags:
        tags.insert(0, "Explicit")
    elif explicit_status == "clean" and "Clean" not in tags:
        tags.insert(0, "Clean")

    return tags or ["Standard"]


def classify_edition(
    explicit_flags: Iterable[Optional[bool]],
    *,
    sibling_has_explicit: bool,
    title: str = "",
) -> ExplicitStatus:
    """Classify an album edition without confusing clean and non-explicit music."""

    flags = list(explicit_flags)
    if any(flag is True for flag in flags):
        return "explicit"

    if has_clean_marker(title):
        return "clean"

    if flags and all(flag is False for flag in flags):
        return "clean" if sibling_has_explicit else "non_explicit"

    return "mixed_or_unknown"


def assess_candidate(
    song: Song,
    result: Result,
    preference: ContentPreference,
) -> CandidateAssessment:
    """Assess whether a provider result is compatible with explicit policy."""

    if preference == "any" or song.explicit is not True:
        return CandidateAssessment(
            accepted=True,
            decision=CandidateDecision.ACCEPT,
            reason="content_policy_not_required",
            confidence=1.0,
        )

    clean_title = has_clean_marker(result.name)
    if result.explicit is False or clean_title:
        return CandidateAssessment(
            accepted=False,
            decision=CandidateDecision.REJECT,
            reason="explicit_required_clean_candidate",
            confidence=1.0 if result.explicit is False else 0.95,
        )

    if result.explicit is True:
        return CandidateAssessment(
            accepted=True,
            decision=CandidateDecision.ACCEPT,
            reason="explicit_candidate",
            confidence=1.0,
        )

    if preference == "prefer_explicit":
        return CandidateAssessment(
            accepted=True,
            decision=CandidateDecision.REVIEW,
            reason="explicit_unknown_fallback",
            confidence=0.45,
        )

    return CandidateAssessment(
        accepted=False,
        decision=CandidateDecision.REVIEW,
        reason="explicit_required_unknown_candidate",
        confidence=0.25,
    )


def filter_candidates(
    song: Song,
    results: Sequence[Result],
    preference: ContentPreference,
) -> Tuple[List[Result], List[CandidateAssessment]]:
    """Filter provider results while retaining assessments for diagnostics."""

    accepted: List[Result] = []
    assessments: List[CandidateAssessment] = []
    for result in results:
        assessment = assess_candidate(song, result, preference)
        assessments.append(assessment)
        if assessment.accepted:
            accepted.append(result)
    return accepted, assessments


def _family_key(edition: AlbumEdition) -> str:
    """Create a deliberately conservative grouping key."""

    name = _normalized_text(edition.name)
    removable = (
        "deluxe",
        "expanded",
        "anniversary",
        "remastered",
        "remaster",
        "reissue",
        "clean",
        "edited",
        "explicit",
    )
    for token in removable:
        name = re.sub(rf"\b{re.escape(token)}\b", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" -")
    artist = edition.artist_ids[0] if edition.artist_ids else _normalized_text(edition.artists[0])
    return f"{artist}:{name}"


def group_editions(editions: Sequence[AlbumEdition]) -> List[EditionFamily]:
    """Group confident sibling editions while retaining exact Spotify album IDs."""

    groups: dict[str, List[AlbumEdition]] = {}
    for edition in editions:
        groups.setdefault(_family_key(edition), []).append(edition)

    families: List[EditionFamily] = []
    for key, siblings in groups.items():
        has_explicit = any(item.explicit_track_count > 0 for item in siblings)
        hydrated: List[AlbumEdition] = []
        sibling_ids = [item.album_id for item in siblings]
        for item in siblings:
            status = classify_edition(
                [track.explicit for track in item.tracks],
                sibling_has_explicit=has_explicit,
                title=item.name,
            )
            hydrated.append(
                item.model_copy(
                    update={
                        "explicit_status": status,
                        "edition_tags": edition_tags(item.name, status),
                        "sibling_album_ids": [
                            album_id for album_id in sibling_ids if album_id != item.album_id
                        ],
                    }
                )
            )

        hydrated.sort(
            key=lambda item: {
                "explicit": 0,
                "non_explicit": 1,
                "mixed_or_unknown": 2,
                "clean": 3,
            }[item.explicit_status]
        )
        families.append(
            EditionFamily(
                family_key=key,
                display_name=hydrated[0].name,
                artist_name=hydrated[0].artists[0] if hydrated[0].artists else "Unknown Artist",
                editions=hydrated,
                grouping_confidence=1.0,
            )
        )

    return families
