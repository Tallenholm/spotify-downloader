from pathlib import Path

import pytest

from spotdl.product.jobs import DownloadJobManager
from spotdl.product.models import AlbumEdition, AlbumTrack
from spotdl.product.resolver import SourceResolutionError
from spotdl.product.store import ProductStore


def make_album() -> AlbumEdition:
    return AlbumEdition(
        album_id="album-explicit",
        name="Example Album",
        artists=["Example Artist"],
        spotify_url="https://open.spotify.com/album/album-explicit",
        explicit_status="explicit",
        total_tracks=2,
        explicit_track_count=1,
        non_explicit_track_count=1,
        tracks=[
            AlbumTrack(
                track_id="track-1",
                name="Explicit Track",
                artists=["Example Artist"],
                duration=200,
                track_number=1,
                explicit=True,
                spotify_url="https://open.spotify.com/track/track-1",
            ),
            AlbumTrack(
                track_id="track-2",
                name="Regular Track",
                artists=["Example Artist"],
                duration=180,
                track_number=2,
                explicit=False,
                spotify_url="https://open.spotify.com/track/track-2",
            ),
        ],
    )


class FakeDiscovery:
    def album(self, album_id):
        assert album_id == "album-explicit"
        return make_album()


class FakeResolver:
    def __init__(self, fail_explicit=False):
        self.fail_explicit = fail_explicit

    def resolve(self, song, *, preference, only_verified=False):
        if self.fail_explicit and song.explicit:
            raise SourceResolutionError("no_explicit_source", "no explicit source")
        return f"https://audio.test/{song.song_id}"


class FakeDownloader:
    async def pool_download(self, song):
        assert song.download_url == f"https://audio.test/{song.song_id}"
        return song, Path(f"/music/{song.song_id}.mp3")


@pytest.mark.asyncio
async def test_album_job_uses_exact_album_tracks_and_completes(tmp_path):
    store = ProductStore(tmp_path / "product.db")
    manager = DownloadJobManager(
        store=store,
        discovery=FakeDiscovery(),
        resolver=FakeResolver(),
        downloader_factory=lambda: FakeDownloader(),
    )

    created = manager.create_album_job("album-explicit", "explicit_only")
    await manager.run_job(created.job_id)
    completed = store.get_job(created.job_id)

    assert completed is not None
    assert completed.state == "completed"
    assert [track.state for track in completed.tracks] == ["completed", "completed"]
    assert completed.tracks[0].source_url == "https://audio.test/track-1"


@pytest.mark.asyncio
async def test_strict_explicit_lookup_failure_becomes_needs_review(tmp_path):
    store = ProductStore(tmp_path / "product.db")
    manager = DownloadJobManager(
        store=store,
        discovery=FakeDiscovery(),
        resolver=FakeResolver(fail_explicit=True),
        downloader_factory=lambda: FakeDownloader(),
    )

    created = manager.create_album_job("album-explicit", "explicit_only")
    await manager.run_job(created.job_id)
    job = store.get_job(created.job_id)

    assert job is not None
    assert job.state == "needs_review"
    assert job.tracks[0].state == "needs_review"
    assert job.tracks[0].error_code == "no_explicit_source"
    assert job.tracks[1].state == "completed"


def test_cancel_and_retry_are_persisted(tmp_path):
    store = ProductStore(tmp_path / "product.db")
    manager = DownloadJobManager(
        store=store,
        discovery=FakeDiscovery(),
        resolver=FakeResolver(),
        downloader_factory=lambda: FakeDownloader(),
    )
    created = manager.create_album_job("album-explicit", "explicit_only")

    manager.cancel(created.job_id)
    cancelled = store.get_job(created.job_id)
    assert cancelled is not None and cancelled.state == "cancelled"

    manager.retry(created.job_id)
    retried = store.get_job(created.job_id)
    assert retried is not None and retried.state == "queued"
    assert all(track.state == "queued" for track in retried.tracks)
