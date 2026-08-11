from spotdl.product.models import AlbumEdition, AlbumTrack
from spotdl.product.store import ProductStore


def make_album() -> AlbumEdition:
    return AlbumEdition(
        album_id="album-explicit",
        name="Example Album",
        artists=["Example Artist"],
        artist_ids=["artist-1"],
        spotify_url="https://open.spotify.com/album/album-explicit",
        explicit_status="explicit",
        explicit_track_count=1,
        non_explicit_track_count=1,
        total_tracks=2,
        tracks=[
            AlbumTrack(
                track_id="track-1",
                name="Explicit Track",
                artists=["Example Artist"],
                duration=200,
                track_number=1,
                disc_number=1,
                explicit=True,
                spotify_url="https://open.spotify.com/track/track-1",
            ),
            AlbumTrack(
                track_id="track-2",
                name="Regular Track",
                artists=["Example Artist"],
                duration=180,
                track_number=2,
                disc_number=1,
                explicit=False,
                spotify_url="https://open.spotify.com/track/track-2",
            ),
        ],
    )


def test_job_survives_store_reopen_with_exact_album_and_preference(tmp_path):
    path = tmp_path / "product.db"
    store = ProductStore(path)
    album = make_album()
    job = store.create_album_job(album, "explicit_only")
    store.close()

    reopened = ProductStore(path)
    persisted = reopened.get_job(job.job_id)

    assert persisted is not None
    assert persisted.source_id == "album-explicit"
    assert persisted.content_preference == "explicit_only"
    assert persisted.state == "queued"
    assert [track.track_id for track in persisted.tracks] == ["track-1", "track-2"]
    assert persisted.tracks[0].duration == 200
    assert persisted.tracks[0].track_number == 1
    assert persisted.tracks[0].disc_number == 1


def test_recover_interrupted_jobs_returns_active_tracks_to_queue(tmp_path):
    store = ProductStore(tmp_path / "product.db")
    job = store.create_album_job(make_album(), "explicit_only")
    store.update_job_state(job.job_id, "downloading")
    store.update_track_state(job.tracks[0].job_track_id, "downloading")

    recovered = store.recover_interrupted()
    persisted = store.get_job(job.job_id)

    assert recovered == 1
    assert persisted is not None
    assert persisted.state == "queued"
    assert persisted.tracks[0].state == "queued"
    assert persisted.recovery_note == "Recovered after application restart"


def test_settings_are_persistent(tmp_path):
    path = tmp_path / "product.db"
    store = ProductStore(path)
    store.set_setting("content_preference", "prefer_explicit")
    store.close()

    reopened = ProductStore(path)

    assert reopened.get_setting("content_preference") == "prefer_explicit"
