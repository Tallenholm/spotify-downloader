from spotdl.product.discovery import DiscoveryService


class FakeSpotify:
    def __init__(self):
        self.albums = {
            "explicit": self._album("explicit", "Example Album", [True, False], "artist-1"),
            "clean": self._album("clean", "Example Album", [False, False], "artist-1"),
            "instrumental": self._album(
                "instrumental", "Instrumental Works", [False, False], "artist-1"
            ),
        }

    @staticmethod
    def _album(album_id, name, explicit_flags, artist_id):
        tracks = [
            {
                "id": f"{album_id}-track-{index}",
                "name": f"Track {index}",
                "artists": [{"id": artist_id, "name": "Example Artist"}],
                "duration_ms": 180000,
                "track_number": index,
                "disc_number": 1,
                "explicit": explicit,
                "is_local": False,
                "external_urls": {"spotify": f"https://open.spotify.com/track/{album_id}-{index}"},
            }
            for index, explicit in enumerate(explicit_flags, start=1)
        ]
        return {
            "id": album_id,
            "name": name,
            "artists": [{"id": artist_id, "name": "Example Artist"}],
            "images": [{"url": f"https://img.test/{album_id}.jpg", "width": 640, "height": 640}],
            "release_date": "2026-01-01",
            "album_type": "album",
            "label": "Example Records",
            "total_tracks": len(tracks),
            "external_urls": {"spotify": f"https://open.spotify.com/album/{album_id}"},
            "tracks": {"items": tracks, "next": None},
        }

    def search(self, query, type=None, limit=None):  # pylint: disable=redefined-builtin
        assert query == "Example"
        assert type == "album"
        return {"albums": {"items": list(self.albums.values()), "next": None}}

    def album(self, album_id):
        return self.albums[album_id]

    def album_tracks(self, album_id):
        return self.albums[album_id]["tracks"]

    def next(self, _response):
        return None


def test_explicit_only_hides_clean_sibling_but_keeps_non_explicit_release():
    service = DiscoveryService(FakeSpotify())

    result = service.search_albums("Example", preference="explicit_only")

    ids = [edition.album_id for edition in result]
    assert "explicit" in ids
    assert "clean" not in ids
    assert "instrumental" in ids
    statuses = {edition.album_id: edition.explicit_status for edition in result}
    assert statuses["explicit"] == "explicit"
    assert statuses["instrumental"] == "non_explicit"


def test_prefer_explicit_keeps_clean_sibling_after_explicit_version():
    service = DiscoveryService(FakeSpotify())

    result = service.search_albums("Example", preference="prefer_explicit")

    ids = [edition.album_id for edition in result]
    assert ids.index("explicit") < ids.index("clean")


def test_album_lookup_preserves_exact_spotify_album_id_and_track_flags():
    service = DiscoveryService(FakeSpotify())

    album = service.album("explicit")

    assert album.album_id == "explicit"
    assert album.spotify_url.endswith("/explicit")
    assert [track.explicit for track in album.tracks] == [True, False]
