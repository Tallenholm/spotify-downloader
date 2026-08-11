"""Persistent product download orchestration built on the existing spotDL downloader."""

from typing import Any, Callable

from spotdl.product.discovery import DiscoveryService
from spotdl.product.models import ContentPreference, DownloadJobRecord, DownloadTrackRecord
from spotdl.product.resolver import ExplicitSourceResolver, SourceResolutionError
from spotdl.product.store import ProductStore
from spotdl.types.song import Song


class DownloadJobManager:
    """Coordinate exact-edition jobs while keeping core spotDL download logic intact."""

    def __init__(
        self,
        *,
        store: ProductStore,
        discovery: DiscoveryService,
        resolver: ExplicitSourceResolver,
        downloader_factory: Callable[[], Any],
        only_verified: bool = False,
    ):
        self.store = store
        self.discovery = discovery
        self.resolver = resolver
        self.downloader_factory = downloader_factory
        self.only_verified = only_verified
        self.store.recover_interrupted()

    def create_album_job(
        self, album_id: str, preference: ContentPreference = "explicit_only"
    ) -> DownloadJobRecord:
        album = self.discovery.album(album_id)
        return self.store.create_album_job(album, preference)

    @staticmethod
    def _song(job: DownloadJobRecord, track: DownloadTrackRecord) -> Song:
        """Build enough exact Spotify metadata to avoid a second fuzzy release lookup."""

        return Song.from_missing_data(
            name=track.name,
            artists=track.artists,
            artist=track.artists[0] if track.artists else "Unknown Artist",
            genres=[],
            disc_number=track.disc_number,
            disc_count=max((item.disc_number for item in job.tracks), default=1),
            album_name=job.title,
            album_artist=track.artists[0] if track.artists else "Unknown Artist",
            duration=track.duration,
            year=0,
            date="",
            track_number=track.track_number or track.position,
            tracks_count=len(job.tracks),
            song_id=track.track_id,
            explicit=track.explicit,
            publisher="",
            url=track.spotify_url,
            isrc=None,
            cover_url=None,
            copyright_text=None,
            album_id=job.source_id if job.kind == "album" else None,
            album_type="album" if job.kind == "album" else None,
        )

    async def run_job(self, job_id: str) -> DownloadJobRecord:
        job = self.store.get_job(job_id)
        if job is None:
            raise KeyError(f"Unknown download job: {job_id}")
        if job.state == "cancelled":
            return job

        downloader = self.downloader_factory()
        self.store.update_job_state(job_id, "resolving")
        needs_review = False
        failed = False

        for original_track in job.tracks:
            current_job = self.store.get_job(job_id)
            if current_job is None or current_job.state == "cancelled":
                break
            track = next(
                item
                for item in current_job.tracks
                if item.job_track_id == original_track.job_track_id
            )
            if track.state == "completed":
                continue

            song = self._song(current_job, track)
            try:
                self.store.update_track_state(track.job_track_id, "searching")
                source_url = self.resolver.resolve(
                    song,
                    preference=current_job.content_preference,
                    only_verified=self.only_verified,
                )
                song.download_url = source_url
                self.store.update_track_state(
                    track.job_track_id, "matched", source_url=source_url
                )
                self.store.update_track_state(track.job_track_id, "downloading")
                _, output_path = await downloader.pool_download(song)
                if output_path is None:
                    failed = True
                    self.store.update_track_state(
                        track.job_track_id,
                        "failed",
                        error_code="download_failed",
                        error_message="spotDL returned no output file",
                    )
                else:
                    self.store.update_track_state(
                        track.job_track_id,
                        "completed",
                        source_url=source_url,
                        output_path=str(output_path),
                    )
            except SourceResolutionError as exc:
                if exc.code == "no_explicit_source":
                    needs_review = True
                    self.store.update_track_state(
                        track.job_track_id,
                        "needs_review",
                        error_code=exc.code,
                        error_message=str(exc),
                    )
                else:
                    failed = True
                    self.store.update_track_state(
                        track.job_track_id,
                        "failed",
                        error_code=exc.code,
                        error_message=str(exc),
                    )
            except Exception as exc:
                failed = True
                self.store.update_track_state(
                    track.job_track_id,
                    "failed",
                    error_code="download_failed",
                    error_message=str(exc),
                )

        final_job = self.store.get_job(job_id)
        if final_job is None:
            raise RuntimeError(f"Download job disappeared: {job_id}")
        if final_job.state == "cancelled":
            return final_job
        if needs_review or any(
            track.state == "needs_review" for track in final_job.tracks
        ):
            self.store.update_job_state(job_id, "needs_review")
        elif failed or any(track.state == "failed" for track in final_job.tracks):
            self.store.update_job_state(job_id, "failed")
        else:
            self.store.update_job_state(job_id, "completed")

        completed = self.store.get_job(job_id)
        if completed is None:
            raise RuntimeError(f"Download job disappeared after completion: {job_id}")
        return completed

    def cancel(self, job_id: str) -> DownloadJobRecord:
        if self.store.get_job(job_id) is None:
            raise KeyError(f"Unknown download job: {job_id}")
        self.store.cancel_job(job_id)
        job = self.store.get_job(job_id)
        if job is None:
            raise RuntimeError(f"Download job disappeared after cancellation: {job_id}")
        return job

    def retry(self, job_id: str) -> DownloadJobRecord:
        if self.store.get_job(job_id) is None:
            raise KeyError(f"Unknown download job: {job_id}")
        self.store.reset_job_for_retry(job_id)
        job = self.store.get_job(job_id)
        if job is None:
            raise RuntimeError(f"Download job disappeared after retry: {job_id}")
        return job
