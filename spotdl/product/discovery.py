"""Spotify discovery services for exact albums, artists, and edition families."""

from typing import Any, Dict, Iterable, List, Optional, Sequence

from spotdl.product.explicit import classify_edition, edition_tags, group_editions
from spotdl.product.models import (
    AlbumEdition,
    AlbumTrack,
    ArtistSummary,
    ContentPreference,
)
from spotdl.utils.spotify import SpotifyClient


class DiscoveryError(RuntimeError):
    """Raised when Spotify metadata required for discovery is unavailable."""


class DiscoveryService:
    """Discover and hydrate Spotify releases without coupling to a UI."""

    def __init__(self, spotify: Optional[Any] = None):
        self.spotify = spotify or SpotifyClient()

    def _collect_items(self, response: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not response:
            return []
        items = list(response.get("items", []))
        current = response
        while current and current.get("next"):
            current = self.spotify.next(current)
            if not current:
                break
            items.extend(current.get("items", []))
        return [item for item in items if isinstance(item, dict)]

    def _search(self, query: str, kind: str, limit: int) -> List[Dict[str, Any]]:
        try:
            response = self.spotify.search(query, type=kind, limit=limit)
        except TypeError:
            response = self.spotify.search(query, type=kind)
        if not response:
            return []
        container = response.get(f"{kind}s", {})
        return self._collect_items(container)[:limit]

    @staticmethod
    def _artwork(images: Sequence[Dict[str, Any]]) -> Optional[str]:
        usable = [image for image in images if image.get("url")]
        if not usable:
            return None
        best = max(
            usable,
            key=lambda image: (image.get("width") or 0) * (image.get("height") or 0),
        )
        return str(best["url"])

    def _tracks_for_album(self, album_id: str, album_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
        embedded = album_meta.get("tracks")
        if isinstance(embedded, dict) and embedded.get("items") is not None:
            tracks = self._collect_items(embedded)
            if tracks:
                return tracks
        return self._collect_items(self.spotify.album_tracks(album_id))

    def _hydrate_album(self, album_id: str) -> AlbumEdition:
        album_meta = self.spotify.album(album_id)
        if not album_meta:
            raise DiscoveryError(f"Album metadata unavailable: {album_id}")

        tracks_meta = self._tracks_for_album(album_id, album_meta)
        tracks: List[AlbumTrack] = []
        for track in tracks_meta:
            if track.get("is_local") or not track.get("id"):
                continue
            artists = [
                str(artist.get("name", "Unknown Artist"))
                for artist in track.get("artists", [])
                if isinstance(artist, dict)
            ]
            tracks.append(
                AlbumTrack(
                    track_id=str(track["id"]),
                    name=str(track.get("name", "Unknown Track")),
                    artists=artists or ["Unknown Artist"],
                    duration=int((track.get("duration_ms") or 0) / 1000),
                    track_number=int(track.get("track_number") or len(tracks) + 1),
                    disc_number=int(track.get("disc_number") or 1),
                    explicit=bool(track.get("explicit", False)),
                    spotify_url=str(
                        track.get("external_urls", {}).get(
                            "spotify", f"https://open.spotify.com/track/{track['id']}"
                        )
                    ),
                )
            )

        artists_meta = [
            artist for artist in album_meta.get("artists", []) if isinstance(artist, dict)
        ]
        artists = [str(artist.get("name", "Unknown Artist")) for artist in artists_meta]
        artist_ids = [str(artist["id"]) for artist in artists_meta if artist.get("id")]
        explicit_count = sum(track.explicit for track in tracks)
        status = classify_edition(
            [track.explicit for track in tracks],
            sibling_has_explicit=False,
            title=str(album_meta.get("name", "")),
        )

        spotify_url = album_meta.get("external_urls", {}).get("spotify")
        if not spotify_url:
            spotify_url = f"https://open.spotify.com/album/{album_id}"

        return AlbumEdition(
            album_id=str(album_meta.get("id") or album_id),
            name=str(album_meta.get("name", "Unknown Album")),
            artists=artists or ["Unknown Artist"],
            artist_ids=artist_ids,
            artwork_url=self._artwork(album_meta.get("images", [])),
            release_date=album_meta.get("release_date"),
            album_type=album_meta.get("album_type"),
            label=album_meta.get("label"),
            total_tracks=int(album_meta.get("total_tracks") or len(tracks)),
            explicit_track_count=int(explicit_count),
            non_explicit_track_count=max(len(tracks) - int(explicit_count), 0),
            explicit_status=status,
            edition_tags=edition_tags(str(album_meta.get("name", "")), status),
            spotify_url=str(spotify_url),
            tracks=tracks,
        )

    @staticmethod
    def _flatten_families(
        editions: Iterable[AlbumEdition], preference: ContentPreference
    ) -> List[AlbumEdition]:
        families = group_editions(list(editions))
        output: List[AlbumEdition] = []
        for family in families:
            if preference == "explicit_only":
                has_explicit = any(
                    edition.explicit_status == "explicit" for edition in family.editions
                )
                output.extend(
                    edition
                    for edition in family.editions
                    if not (has_explicit and edition.explicit_status == "clean")
                )
            else:
                output.extend(family.editions)
        return output

    def search_albums(
        self,
        query: str,
        *,
        preference: ContentPreference = "explicit_only",
        limit: int = 18,
    ) -> List[AlbumEdition]:
        """Search Spotify albums and return exact hydrated, edition-aware releases."""

        raw = self._search(query, "album", limit)
        editions: List[AlbumEdition] = []
        seen: set[str] = set()
        for item in raw:
            album_id = item.get("id")
            if not album_id or album_id in seen:
                continue
            seen.add(str(album_id))
            try:
                editions.append(self._hydrate_album(str(album_id)))
            except (DiscoveryError, KeyError, TypeError, ValueError):
                continue
        return self._flatten_families(editions, preference)

    def album(self, album_id: str) -> AlbumEdition:
        """Return one exact Spotify album edition by ID."""

        return self._hydrate_album(album_id)

    def search_artists(self, query: str, *, limit: int = 12) -> List[ArtistSummary]:
        """Search artists for the discovery UI."""

        artists: List[ArtistSummary] = []
        for item in self._search(query, "artist", limit):
            if not item.get("id"):
                continue
            artists.append(
                ArtistSummary(
                    artist_id=str(item["id"]),
                    name=str(item.get("name", "Unknown Artist")),
                    spotify_url=str(
                        item.get("external_urls", {}).get(
                            "spotify", f"https://open.spotify.com/artist/{item['id']}"
                        )
                    ),
                    artwork_url=self._artwork(item.get("images", [])),
                    genres=[str(genre) for genre in item.get("genres", [])],
                )
            )
        return artists

    def artist(self, artist_id: str) -> ArtistSummary:
        """Return an artist summary by exact Spotify ID."""

        item = self.spotify.artist(artist_id)
        if not item:
            raise DiscoveryError(f"Artist metadata unavailable: {artist_id}")
        return ArtistSummary(
            artist_id=str(item.get("id") or artist_id),
            name=str(item.get("name", "Unknown Artist")),
            spotify_url=str(
                item.get("external_urls", {}).get(
                    "spotify", f"https://open.spotify.com/artist/{artist_id}"
                )
            ),
            artwork_url=self._artwork(item.get("images", [])),
            genres=[str(genre) for genre in item.get("genres", [])],
        )

    def artist_albums(
        self,
        artist_id: str,
        *,
        preference: ContentPreference = "explicit_only",
        limit: int = 80,
    ) -> List[AlbumEdition]:
        """Return an artist's edition-aware discography."""

        response = self.spotify.artist_albums(
            artist_id, include_groups="album,single,compilation"
        )
        raw = self._collect_items(response)[:limit]
        editions: List[AlbumEdition] = []
        seen: set[str] = set()
        for item in raw:
            album_id = item.get("id")
            if not album_id or str(album_id) in seen:
                continue
            seen.add(str(album_id))
            try:
                editions.append(self._hydrate_album(str(album_id)))
            except (DiscoveryError, KeyError, TypeError, ValueError):
                continue
        return self._flatten_families(editions, preference)
