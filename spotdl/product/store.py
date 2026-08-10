"""SQLite persistence for product settings, queue state, and history."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from spotdl.product.models import (
    AlbumEdition,
    ContentPreference,
    DownloadJobRecord,
    DownloadTrackRecord,
    JobState,
)

ACTIVE_STATES = {"resolving", "searching", "matched", "downloading", "transcoding", "tagging"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProductStore:
    """Own the local product database and its small, explicit schema."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        try:
            self.connection.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        self._init_schema()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS download_jobs (
                job_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                source_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content_preference TEXT NOT NULL,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error_code TEXT,
                error_message TEXT,
                recovery_note TEXT
            );
            CREATE TABLE IF NOT EXISTS download_tracks (
                job_track_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES download_jobs(job_id) ON DELETE CASCADE,
                track_id TEXT NOT NULL,
                name TEXT NOT NULL,
                artists_json TEXT NOT NULL,
                spotify_url TEXT NOT NULL,
                explicit INTEGER NOT NULL,
                position INTEGER NOT NULL,
                duration INTEGER NOT NULL DEFAULT 0,
                track_number INTEGER NOT NULL DEFAULT 0,
                disc_number INTEGER NOT NULL DEFAULT 1,
                state TEXT NOT NULL,
                source_url TEXT,
                output_path TEXT,
                error_code TEXT,
                error_message TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_download_tracks_job
                ON download_tracks(job_id, position);
            CREATE TABLE IF NOT EXISTS manual_overrides (
                job_track_id TEXT PRIMARY KEY REFERENCES download_tracks(job_track_id) ON DELETE CASCADE,
                source_url TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def set_setting(self, key: str, value: str) -> None:
        self.connection.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.connection.commit()

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.connection.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        return str(row["value"]) if row else default

    def create_album_job(
        self, album: AlbumEdition, preference: ContentPreference
    ) -> DownloadJobRecord:
        now = utc_now()
        job_id = uuid.uuid4().hex
        with self.connection:
            self.connection.execute(
                "INSERT INTO download_jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    job_id,
                    "album",
                    album.album_id,
                    album.name,
                    preference,
                    "queued",
                    now,
                    now,
                    None,
                    None,
                    None,
                ),
            )
            for position, track in enumerate(album.tracks, start=1):
                self.connection.execute(
                    "INSERT INTO download_tracks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        uuid.uuid4().hex,
                        job_id,
                        track.track_id,
                        track.name,
                        json.dumps(track.artists, ensure_ascii=False),
                        track.spotify_url,
                        int(track.explicit),
                        position,
                        track.duration,
                        track.track_number,
                        track.disc_number,
                        "queued",
                        None,
                        None,
                        None,
                        None,
                    ),
                )
        job = self.get_job(job_id)
        if job is None:
            raise RuntimeError("Failed to persist new album job")
        return job

    def _track_from_row(self, row: sqlite3.Row) -> DownloadTrackRecord:
        return DownloadTrackRecord(
            job_track_id=row["job_track_id"],
            job_id=row["job_id"],
            track_id=row["track_id"],
            name=row["name"],
            artists=json.loads(row["artists_json"]),
            spotify_url=row["spotify_url"],
            explicit=bool(row["explicit"]),
            position=row["position"],
            duration=row["duration"],
            track_number=row["track_number"],
            disc_number=row["disc_number"],
            state=row["state"],
            source_url=row["source_url"],
            output_path=row["output_path"],
            error_code=row["error_code"],
            error_message=row["error_message"],
        )

    def get_job(self, job_id: str) -> Optional[DownloadJobRecord]:
        row = self.connection.execute(
            "SELECT * FROM download_jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        if row is None:
            return None
        track_rows = self.connection.execute(
            "SELECT * FROM download_tracks WHERE job_id=? ORDER BY position", (job_id,)
        ).fetchall()
        return DownloadJobRecord(
            job_id=row["job_id"],
            kind=row["kind"],
            source_id=row["source_id"],
            title=row["title"],
            content_preference=row["content_preference"],
            state=row["state"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            recovery_note=row["recovery_note"],
            tracks=[self._track_from_row(track) for track in track_rows],
        )

    def list_jobs(self, limit: int = 100) -> List[DownloadJobRecord]:
        rows = self.connection.execute(
            "SELECT job_id FROM download_jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            job
            for row in rows
            if (job := self.get_job(row["job_id"])) is not None
        ]

    def update_job_state(
        self,
        job_id: str,
        state: JobState,
        *,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        recovery_note: Optional[str] = None,
    ) -> None:
        self.connection.execute(
            "UPDATE download_jobs SET state=?, updated_at=?, error_code=?, error_message=?, "
            "recovery_note=COALESCE(?, recovery_note) WHERE job_id=?",
            (state, utc_now(), error_code, error_message, recovery_note, job_id),
        )
        self.connection.commit()

    def update_track_state(
        self,
        job_track_id: str,
        state: JobState,
        *,
        source_url: Optional[str] = None,
        output_path: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        self.connection.execute(
            "UPDATE download_tracks SET state=?, source_url=COALESCE(?, source_url), "
            "output_path=COALESCE(?, output_path), error_code=?, error_message=? "
            "WHERE job_track_id=?",
            (state, source_url, output_path, error_code, error_message, job_track_id),
        )
        self.connection.commit()

    def recover_interrupted(self) -> int:
        placeholders = ",".join("?" for _ in ACTIVE_STATES)
        rows = self.connection.execute(
            f"SELECT job_id FROM download_jobs WHERE state IN ({placeholders})",
            tuple(ACTIVE_STATES),
        ).fetchall()
        if not rows:
            return 0
        with self.connection:
            for row in rows:
                job_id = row["job_id"]
                self.connection.execute(
                    "UPDATE download_jobs SET state='queued', updated_at=?, recovery_note=? WHERE job_id=?",
                    (utc_now(), "Recovered after application restart", job_id),
                )
                self.connection.execute(
                    f"UPDATE download_tracks SET state='queued' WHERE job_id=? AND state IN ({placeholders})",
                    (job_id, *tuple(ACTIVE_STATES)),
                )
        return len(rows)

    def reset_job_for_retry(self, job_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE download_jobs SET state='queued', updated_at=?, error_code=NULL, "
                "error_message=NULL WHERE job_id=?",
                (utc_now(), job_id),
            )
            self.connection.execute(
                "UPDATE download_tracks SET state='queued', error_code=NULL, error_message=NULL "
                "WHERE job_id=? AND state IN ('failed','needs_review','cancelled')",
                (job_id,),
            )

    def cancel_job(self, job_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE download_jobs SET state='cancelled', updated_at=? WHERE job_id=?",
                (utc_now(), job_id),
            )
            self.connection.execute(
                "UPDATE download_tracks SET state='cancelled' WHERE job_id=? AND state != 'completed'",
                (job_id,),
            )
