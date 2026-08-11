from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from spotdl.product.models import AlbumEdition, ArtistSummary, DownloadJobRecord
from spotdl.product.services import ProductServices
from spotdl.product.store import ProductStore, utc_now
from spotdl.web.product_api import router


class FakeDiscovery:
    def search_albums(self, query, *, preference, limit=18):
        return [
            AlbumEdition(
                album_id="explicit-album",
                name=f"{query} Album",
                artists=["Example Artist"],
                spotify_url="https://open.spotify.com/album/explicit-album",
                explicit_status="explicit",
                edition_tags=["Explicit"],
            )
        ]

    def search_artists(self, query, *, limit=12):
        return [
            ArtistSummary(
                artist_id="artist-1",
                name=f"{query} Artist",
                spotify_url="https://open.spotify.com/artist/artist-1",
            )
        ]

    def album(self, album_id):
        return AlbumEdition(
            album_id=album_id,
            name="Exact Album",
            artists=["Example Artist"],
            spotify_url=f"https://open.spotify.com/album/{album_id}",
            explicit_status="explicit",
        )

    def artist(self, artist_id):
        return ArtistSummary(
            artist_id=artist_id,
            name="Example Artist",
            spotify_url=f"https://open.spotify.com/artist/{artist_id}",
        )

    def artist_albums(self, artist_id, *, preference, limit=80):
        return self.search_albums(artist_id, preference=preference)


class FakeJobs:
    def __init__(self):
        self.cancelled = []
        self.retried = []

    def create_album_job(self, album_id, preference):
        now = utc_now()
        return DownloadJobRecord(
            job_id="job-1",
            kind="album",
            source_id=album_id,
            title="Exact Album",
            content_preference=preference,
            state="queued",
            created_at=now,
            updated_at=now,
        )

    async def run_job(self, _job_id):
        return None

    def cancel(self, job_id):
        self.cancelled.append(job_id)
        return self.create_album_job("explicit-album", "explicit_only").model_copy(
            update={"job_id": job_id, "state": "cancelled"}
        )

    def retry(self, job_id):
        self.retried.append(job_id)
        return self.create_album_job("explicit-album", "explicit_only").model_copy(
            update={"job_id": job_id}
        )


def make_client(tmp_path: Path):
    app = FastAPI()
    app.include_router(router)
    store = ProductStore(tmp_path / "product.db")
    store.set_setting("content_preference", "explicit_only")
    app.state.product_services = ProductServices(
        store=store,
        discovery=FakeDiscovery(),
        jobs=FakeJobs(),
    )
    return TestClient(app), store


def test_search_defaults_to_explicit_only(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.get("/api/v1/search", params={"q": "Example", "type": "all"})

    assert response.status_code == 200
    data = response.json()
    assert data["content_preference"] == "explicit_only"
    assert data["albums"][0]["explicit_status"] == "explicit"
    assert data["artists"][0]["artist_id"] == "artist-1"


def test_invalid_content_preference_is_rejected(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.get(
        "/api/v1/search",
        params={"q": "Example", "content_preference": "sometimes"},
    )

    assert response.status_code == 422


def test_exact_album_endpoint_preserves_requested_id(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.get("/api/v1/albums/album-123")

    assert response.status_code == 200
    assert response.json()["album_id"] == "album-123"


def test_create_album_download_returns_exact_album_job(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.post(
        "/api/v1/downloads/albums/album-123",
        json={"content_preference": "explicit_only"},
    )

    assert response.status_code == 202
    assert response.json()["source_id"] == "album-123"
    assert response.json()["content_preference"] == "explicit_only"


def test_settings_round_trip(tmp_path):
    client, store = make_client(tmp_path)

    response = client.patch(
        "/api/v1/settings", json={"content_preference": "prefer_explicit"}
    )

    assert response.status_code == 200
    assert response.json()["content_preference"] == "prefer_explicit"
    assert store.get_setting("content_preference") == "prefer_explicit"
