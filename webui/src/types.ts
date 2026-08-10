export type ContentPreference = 'explicit_only' | 'prefer_explicit' | 'any';
export type ExplicitStatus = 'explicit' | 'clean' | 'non_explicit' | 'mixed_or_unknown';
export type JobState = 'queued' | 'resolving' | 'searching' | 'matched' | 'downloading' | 'transcoding' | 'tagging' | 'completed' | 'needs_review' | 'failed' | 'cancelled';

export interface AlbumTrack {
  track_id: string;
  name: string;
  artists: string[];
  duration: number;
  track_number: number;
  disc_number: number;
  explicit: boolean;
  spotify_url: string;
}

export interface AlbumEdition {
  album_id: string;
  name: string;
  artists: string[];
  artist_ids: string[];
  artwork_url?: string | null;
  release_date?: string | null;
  album_type?: string | null;
  label?: string | null;
  total_tracks: number;
  explicit_track_count: number;
  non_explicit_track_count: number;
  explicit_status: ExplicitStatus;
  edition_tags: string[];
  spotify_url: string;
  tracks: AlbumTrack[];
  sibling_album_ids: string[];
  grouping_confidence: number;
}

export interface ArtistSummary {
  artist_id: string;
  name: string;
  spotify_url: string;
  artwork_url?: string | null;
  genres: string[];
}

export interface SearchResponse {
  query: string;
  content_preference: ContentPreference;
  albums: AlbumEdition[];
  artists: ArtistSummary[];
}

export interface DownloadTrackRecord {
  job_track_id: string;
  job_id: string;
  track_id: string;
  name: string;
  artists: string[];
  spotify_url: string;
  explicit: boolean;
  position: number;
  duration: number;
  track_number: number;
  disc_number: number;
  state: JobState;
  source_url?: string | null;
  output_path?: string | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface DownloadJobRecord {
  job_id: string;
  kind: 'album' | 'track';
  source_id: string;
  title: string;
  content_preference: ContentPreference;
  state: JobState;
  created_at: string;
  updated_at: string;
  error_code?: string | null;
  error_message?: string | null;
  recovery_note?: string | null;
  tracks: DownloadTrackRecord[];
}
