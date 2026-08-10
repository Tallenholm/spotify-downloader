# Premium Explicit-Album UI v1 Design

Date: 2026-08-10
Repository: `Tallenholm/spotify-downloader`
Base: spotDL v4.5.2 (`cd4a4203f5b12bd6dbbdf22d7674807858d35e05`)

## 1. North Star

Transform the spotDL fork into a product that is materially better to use, easier to trust, and easier to extend while preserving the mature download engine until replacement is justified by evidence.

The first milestone has two signature outcomes:

1. A premium, modern, responsive interface that feels like a real music application rather than a utility page.
2. A strict, first-class explicit-edition workflow that makes it easy to discover and download explicit album editions without silently substituting clean audio.

## 2. Product Principles

- **Strict means strict.** In `explicit_only`, an explicitly marked Spotify track must never silently complete with a clearly clean/censored source.
- **Exact editions over fuzzy names.** Album downloads are tied to the selected Spotify album ID and exact tracklist.
- **Preserve proven internals.** Keep spotDL's downloader, providers, metadata, tagging, lyrics, sync, and FFmpeg machinery unless a targeted change is required.
- **Transparent decisions.** Expose source, provider, match confidence, explicit requirement, warnings, and failure reason.
- **Fail visibly, never deceptively.** Wrong-edition or uncertain matches become visible failures/review items, not green success states.
- **Premium by default.** Common actions are obvious, defaults are excellent, advanced detail is available without clutter.

## 3. Scope

### In scope

- New React + TypeScript + Vite frontend.
- FastAPI JSON API plus SSE/WebSocket progress transport.
- Search across songs, albums, and artists.
- Artist discography browsing.
- Explicit-content preference with `explicit_only`, `prefer_explicit`, and `any` modes.
- Album-edition grouping and classification.
- Exact-album download by Spotify album ID.
- Track-level explicit-aware matching policy.
- Manual source resolution when strict matching cannot verify a suitable source.
- Persistent queue and basic download history.
- Rich per-job diagnostics.
- Responsive dark-first UI.
- Regression protection for existing spotDL behavior.
- Existing CLI preserved unless an internal compatibility adapter is required.

### Out of scope for v1

- Mobile apps.
- Cloud accounts or hosted user data.
- Full streaming-service playback.
- Replacing yt-dlp or FFmpeg.
- Full provider rewrite.
- Plex/Navidrome-class media server features.
- ML recommendations.
- DRM circumvention or direct Spotify audio extraction.

## 4. Architecture

```text
React/Vite Frontend
        |
        v
FastAPI Product API
        |
        +-----------------------------+
        |                             |
        v                             v
Discovery Service              Download Orchestrator
        |                             |
        v                             v
Spotify Client                 Existing spotDL Downloader
        |                             |
        v                             v
Edition Resolver               Audio Providers / yt-dlp
                                      |
                                      v
                               FFmpeg / Metadata / Lyrics
```

### 4.1 Frontend

A new frontend lives in `webui/` and communicates only through documented HTTP/streaming contracts. It must not import Python internals.

The existing server-rendered web UI remains available during migration for behavior comparison until the replacement reaches parity.

### 4.2 Product API

Initial contract:

- `GET /api/v1/search?q=&type=`
- `GET /api/v1/artists/{artist_id}`
- `GET /api/v1/artists/{artist_id}/albums`
- `GET /api/v1/albums/{album_id}`
- `POST /api/v1/downloads/albums/{album_id}`
- `POST /api/v1/downloads/tracks/{track_id}`
- `GET /api/v1/downloads`
- `GET /api/v1/downloads/{job_id}`
- `POST /api/v1/downloads/{job_id}/retry`
- `POST /api/v1/downloads/{job_id}/cancel`
- `GET /api/v1/settings`
- `PATCH /api/v1/settings`
- progress stream via SSE or WebSocket.

Responses use stable versioned JSON models rather than Jinja fragments.

## 5. Explicit Data Model

spotDL already stores `Song.explicit: bool`; this remains the authoritative track-level requested-content flag when Spotify supplies it.

Runtime track classification:

- `explicit`
- `clean`
- `unknown`

Introduce an album-edition representation:

```text
AlbumEdition
- album_id
- name
- artists[]
- artwork_url
- release_date
- album_type
- total_tracks
- explicit_track_count
- non_explicit_track_count
- explicit_status
- edition_tags[]
- spotify_url
- sibling_album_ids[]
- grouping_confidence
```

Album-level `explicit_status`:

- `explicit`: one or more tracks are explicitly marked and the selected edition is not identified as a clean counterpart.
- `clean`: no tracks are explicit and a sibling explicit edition is confidently detected, or release metadata clearly marks the edition as clean/edited.
- `non_explicit`: no explicit tracks and no evidence of an alternate explicit edition.
- `mixed_or_unknown`: metadata is incomplete or contradictory.

The distinction between `clean` and `non_explicit` is mandatory. An album containing no profanity must not be mislabeled as censored.

Informational edition tags may include: Standard, Explicit, Clean, Deluxe, Expanded, Anniversary, Remastered, Reissue, Live, Single, EP.

## 6. Explicit Preference Behavior

### `explicit_only`

- Explicit editions are promoted and visibly labeled.
- Clean counterpart editions are hidden by default.
- Genuinely non-explicit albums remain discoverable in artist discographies and are labeled `No explicit content`, not `Clean`.
- If a same-release explicit edition exists, it ranks above the clean sibling.
- A Spotify track marked explicit requires an explicit-compatible source match.
- Clearly clean/radio/censored source candidates are rejected.
- Ambiguous candidates produce `needs_review` rather than silent fallback.

### `prefer_explicit`

- Explicit editions rank first.
- Clean editions remain visible.
- Source matching strongly prefers explicit-compatible candidates.
- A clean fallback is allowed only with a visible warning or explicit user action.

### `any`

- No explicit-content filtering.
- Existing matching behavior remains available.

## 7. Edition Resolver

The resolver groups likely sibling editions while preserving separate Spotify album IDs.

Signals:

- normalized album title
- primary artist IDs
- track count
- normalized track names and order
- release-date proximity
- aggregate duration similarity
- UPC when available
- explicit-track distribution
- release-name tokens such as `Deluxe`, `Clean`, `Edited`, `Remaster`, `Anniversary`, `Expanded`

Low-confidence candidates are never auto-merged. Ambiguous releases stay separate.

## 8. Explicit-Aware Source Matching

The matcher gains a policy layer that can reject otherwise-good candidates when they violate requested content requirements.

Candidate evidence includes:

- normalized title similarity
- artist similarity
- duration delta
- official/topic channel signals
- album/release text
- markers such as `clean`, `radio edit`, `edited`, `censored`
- source metadata when available
- existing spotDL matching score

Hard negatives in `explicit_only` include clearly identified clean/radio/censored versions.

Weak heuristics never become false certainty. If explicit compatibility cannot be established with reasonable confidence, the result is `needs_review`.

## 9. Manual Resolution

A strict-match failure offers:

- Retry
- Search more candidates
- Choose source manually
- Skip track

Candidate view shows title, provider/channel, duration, match score, explicit compatibility assessment, acceptance/rejection reasons, and direct source link when available.

Manual policy overrides are explicit user actions and recorded in history.

## 10. UI Information Architecture

Primary navigation:

- Home
- Search
- Albums
- Artists
- Downloads
- History
- Settings

### Home

- global search / URL paste field
- active downloads
- recent searches
- recently viewed albums
- recent completions/failures

### Search

Tabs: All, Albums, Songs, Artists.

Filters include content preference, release type, year, and sort.

Album cards prominently show edition badges such as `E EXPLICIT`, `CLEAN`, `DELUXE`, and `REMASTER`.

### Artist page

- large artist header
- Albums
- Singles & EPs
- grouped release families where safe
- edition cards with explicit/clean labels
- `Explicit only` filtering that never hides genuinely non-explicit albums merely because they contain no profanity

### Album page

- large artwork
- title and artist
- release date and label
- edition tags
- explicit status
- exact Spotify edition ID/link
- track count
- format/quality/output summary
- primary `Download album` action
- track table with per-track `E` markers
- alternate-edition selector when sibling editions exist

### Downloads

Per-job state machine:

- queued
- resolving
- searching
- matched
- downloading
- transcoding
- tagging
- completed
- needs_review
- failed
- cancelled

Controls include cancel, retry, retry failed, clear completed, plus pause/resume where supported.

Each track can expand into diagnostics showing source, provider, confidence, explicit requirement, and failure reason.

## 11. Visual Direction

The interface should feel closer to a premium music app than an admin dashboard.

Requirements:

- dark-first design
- large, crisp album artwork
- strong typography hierarchy
- minimal chrome
- restrained motion
- polished empty/loading/error states
- responsive desktop/tablet layouts
- keyboard-accessible controls
- visible focus states
- WCAG-conscious contrast
- no debug terminology in primary user-facing flows

## 12. Persistence

Use lightweight local SQLite persistence for product state.

Minimum entities:

- settings
- download jobs
- per-track job state
- manual overrides
- recent searches
- basic history

The database must not become a prerequisite for the existing CLI during the first migration step; compatibility is maintained through adapters/default behavior.

## 13. Error Handling

Errors use stable machine-readable codes plus human-readable messages.

Initial codes:

- `metadata_unavailable`
- `album_not_found`
- `edition_ambiguous`
- `no_explicit_source`
- `provider_rate_limited`
- `source_unavailable`
- `ffmpeg_failure`
- `tagging_failure`
- `output_conflict`
- `cancelled`

The frontend maps each code to an actionable recovery path.

## 14. Testing Strategy

### Backend unit tests

- album edition classification
- clean vs non-explicit distinction
- sibling-edition grouping
- strict explicit policy
- explicit-source rejection rules
- ambiguous candidate handling
- manual override persistence

### API tests

- search contract
- album details
- artist discography
- download creation
- job state progression
- retry/cancel behavior
- settings persistence

### Frontend tests

- explicit-only filter
- album edition badges
- album selection
- queue rendering
- needs-review flow
- settings changes
- loading/error/empty states

### Regression requirement

Existing spotDL tests remain green unless a behavior change is intentional, documented, and replaced with equivalent or stronger coverage.

### End-to-end scenarios

- artist with explicit and clean versions of the same album
- album with only some explicit tracks
- standard + deluxe + clean + explicit variants
- album with no explicit content and no censored counterpart
- explicit Spotify track with a clearly clean candidate
- explicit Spotify track with ambiguous candidates
- manual source override
- mixed-content playlist
- active queue across restart
- provider failure and retry
- Windows browser/frontend flow

## 15. Performance Requirements

- Search results should feel immediate after backend metadata is available.
- UI interactions must never block on download/transcode work.
- Artwork uses lazy loading and sensible caching.
- Queue updates are incremental rather than full-page refreshes.
- Backend provider operations remain bounded and cancellable where feasible.
- Frontend production bundles are code-split where that materially improves startup.

## 16. Security Requirements

- Validate user-provided search strings and URLs server-side.
- Constrain download output to configured output paths.
- Frontend never constructs shell commands.
- Provider/FFmpeg execution stays behind backend interfaces.
- API inputs use typed validation.
- Local-first default deployment; remote exposure is not enabled implicitly.
- Preserve MIT license notice and upstream copyright attribution as required.

## 17. Quality Gates

This milestone is not considered complete until all of the following are demonstrated with evidence:

- New UI builds successfully in production mode.
- Backend API tests pass.
- Frontend tests pass.
- Existing spotDL regression suite remains green or documented intentional deviations are covered.
- Explicit-only search behavior is verified against real explicit/clean sibling releases.
- Explicit source policy is verified against at least one clearly censored candidate and one valid explicit candidate.
- `needs_review` is exercised end-to-end.
- Album downloads preserve the selected Spotify album ID and edition.
- Queue state survives application restart.
- Windows build/runtime flow is tested.
- Scope, commands run, results, failures, and unresolved limitations are recorded before any claim of completion.

## 18. Implementation Order

1. Introduce typed product API models and explicit-content settings.
2. Build album/artist discovery and edition resolver.
3. Add strict explicit-aware matching policy and `needs_review` state.
4. Add persistent queue/history layer.
5. Build the React/Vite application shell and design system.
6. Implement Search, Artist, Album, Downloads, History, and Settings screens.
7. Connect live progress and manual-resolution flows.
8. Add frontend/backend/e2e coverage.
9. Run regression, performance, packaging, and Windows verification.
10. Replace the old web UI entry point only after parity and verification.

## 19. Success Definition

A user can search an artist, immediately identify the exact explicit album edition, inspect its tracklist, download that exact edition, watch each track progress through a transparent queue, and be warned rather than deceived if the system cannot confidently obtain an explicit-compatible source.

The finished v1 should be clearly more polished and trustworthy than upstream spotDL's current web experience while retaining the reliability of its mature downloader core.