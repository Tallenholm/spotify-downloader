# Premium Explicit-Album UI v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a premium local-first spotDL web experience that makes explicit album editions easy to discover and download, refuses clearly clean/censored source substitutions for Spotify tracks marked explicit, and preserves the proven spotDL downloader/CLI behavior.

**Architecture:** Keep the existing Python downloader/providers and place a versioned product layer around them: explicit-edition discovery and policy services, a persistent SQLite-backed download queue, and a `/api/v1` FastAPI router. Replace the server-rendered web surface with a React + TypeScript + Vite SPA compiled into `spotdl/web/static`, while leaving the CLI and core download pipeline intact.

**Tech Stack:** Python 3.10-3.14, FastAPI/Pydantic, stdlib SQLite, existing spotDL provider/downloader stack, React, TypeScript, Vite, Vitest, React Testing Library.

## Global Constraints

- Base is spotDL v4.5.2 at `cd4a4203f5b12bd6dbbdf22d7674807858d35e05`.
- Preserve the MIT license notice and upstream attribution.
- Do not implement direct Spotify audio extraction, DRM circumvention, or cloud user accounts.
- Existing CLI behavior remains available.
- `explicit_only` must never silently accept a clearly clean/radio/censored source for a Spotify track whose `Song.explicit` value is `True`.
- Clean and genuinely non-explicit releases are distinct classifications.
- Exact album downloads are keyed to the selected Spotify album ID.
- Any ambiguous strict explicit match becomes a visible review/failure state rather than a green success.
- Completion claims require commands, test results, failures, and unresolved limitations.

---

### Task 1: Explicit Content Policy and Edition Models

**Files:**
- Create: `spotdl/product/__init__.py`
- Create: `spotdl/product/models.py`
- Create: `spotdl/product/explicit.py`
- Modify: `spotdl/types/options.py`
- Modify: `spotdl/utils/config.py`
- Test: `tests/product/test_explicit.py`

**Interfaces:**
- Produces `ContentPreference = Literal["explicit_only", "prefer_explicit", "any"]`.
- Produces `AlbumEdition`, `EditionFamily`, `CandidateDecision`, `CandidateAssessment` Pydantic models.
- Produces `classify_edition(...)`, `group_editions(...)`, and `assess_candidate(song, result, preference)`.
- Adds downloader option `content_preference` with default `"explicit_only"` in this fork.

- [ ] **Step 1: Write failing policy tests**

```python
from spotdl.product.explicit import assess_candidate, classify_edition
from spotdl.types.result import Result
from spotdl.types.song import Song


def test_explicit_track_rejects_clean_result(explicit_song):
    result = Result(
        source="YouTubeMusic", url="https://example.test/clean", verified=True,
        name=f"{explicit_song.name} (Clean)", duration=explicit_song.duration,
        author=explicit_song.artist, result_id="clean", explicit=False,
    )
    assessment = assess_candidate(explicit_song, result, "explicit_only")
    assert assessment.accepted is False
    assert assessment.reason == "explicit_required_clean_candidate"


def test_non_explicit_release_is_not_called_clean():
    status = classify_edition([False, False, False], sibling_has_explicit=False)
    assert status == "non_explicit"
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `uv run pytest tests/product/test_explicit.py -q`
Expected: FAIL because `spotdl.product.explicit` does not exist.

- [ ] **Step 3: Implement models and deterministic classification**

`spotdl/product/models.py` defines typed models and `spotdl/product/explicit.py` uses explicit flags plus normalized title tokens. Hard-clean tokens are `clean`, `edited`, `censored`, `radio edit`, and `radio version`. An explicit `Result.explicit is True` is positive evidence; `False` is negative evidence; `None` remains unknown.

- [ ] **Step 4: Add `content_preference` to typed/default downloader options**

Add the key to both `DownloaderOptions` and `DownloaderOptionalOptions`, and to `DOWNLOADER_OPTIONS`:

```python
content_preference: str
# ...
"content_preference": "explicit_only",
```

No existing key is removed or renamed.

- [ ] **Step 5: Run focused tests**

Run: `uv run pytest tests/product/test_explicit.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add spotdl/product spotdl/types/options.py spotdl/utils/config.py tests/product/test_explicit.py
git commit -m "feat: add explicit content policy models"
```

---

### Task 2: Album and Artist Discovery with Edition Families

**Files:**
- Create: `spotdl/product/discovery.py`
- Test: `tests/product/test_discovery.py`

**Interfaces:**
- Produces `DiscoveryService.search(query, kind, limit)`.
- Produces `DiscoveryService.album(album_id)` and `DiscoveryService.artist(artist_id)`.
- Produces `DiscoveryService.artist_albums(artist_id)` returning grouped `EditionFamily` objects.
- Uses `Album.from_url(..., fetch_songs=False)` so track explicit flags are available without re-fetching every track as a full `Song`.

- [ ] **Step 1: Write failing edition grouping tests**

Construct fake Spotify responses containing an explicit and clean sibling album plus a genuinely non-explicit album. Assert that the first two share a family, explicit ranks first, clean is hidden by `explicit_only`, and the non-explicit release remains visible.

- [ ] **Step 2: Run focused tests**

Run: `uv run pytest tests/product/test_discovery.py -q`
Expected: FAIL because `DiscoveryService` does not exist.

- [ ] **Step 3: Implement resilient Spotify search helpers**

Call the runtime `SpotifyClient()` facade. Search albums/artists with the official-compatible parameters when supported and fall back to the backend's simpler call signature on `TypeError`. Never assume the official API backend.

- [ ] **Step 4: Implement exact album hydration**

For each selected album ID, hydrate metadata and tracks from Spotify. Preserve `album_id`, Spotify URL, artwork, release date, label, track order, and per-track `explicit` flags.

- [ ] **Step 5: Implement family grouping/ranking**

Normalize edition names by removing only recognized edition suffix tokens. Group only when primary artist identity and normalized title agree. Keep uncertain releases separate. Ranking order in `explicit_only`: explicit > non-explicit > mixed/unknown; hide clean siblings when a confident explicit sibling exists.

- [ ] **Step 6: Run tests and commit**

Run: `uv run pytest tests/product/test_discovery.py tests/product/test_explicit.py -q`

```bash
git add spotdl/product/discovery.py tests/product/test_discovery.py
git commit -m "feat: add explicit album discovery"
```

---

### Task 3: Strict Explicit-Aware Provider Matching

**Files:**
- Modify: `spotdl/providers/audio/base.py`
- Modify: `spotdl/download/downloader.py`
- Test: `tests/product/test_provider_policy.py`

**Interfaces:**
- `AudioProvider.search(song, only_verified=False, content_preference="any") -> Optional[str]`.
- `AudioProvider.filter_content_candidates(song, results, preference) -> tuple[list[Result], list[CandidateAssessment]]`.
- `Downloader.search()` passes `self.settings["content_preference"]`.

- [ ] **Step 1: Write failing provider-policy tests**

Use a tiny fake `AudioProvider` returning two same-song candidates: a high-score clean result and a slightly lower explicit result. Assert `explicit_only` returns the explicit URL. Assert a list containing only a clearly clean candidate returns `None`.

- [ ] **Step 2: Run focused tests**

Run: `uv run pytest tests/product/test_provider_policy.py -q`
Expected: FAIL because the provider does not accept content preference.

- [ ] **Step 3: Filter every result set before match ordering**

Apply `assess_candidate` to ISRC results and normal search results before early-return logic. This is critical: a single verified ISRC result must not bypass strict content policy.

- [ ] **Step 4: Preserve behavior for non-explicit tracks and `any`**

When `song.explicit` is not `True`, retain upstream ordering/selection behavior. With preference `any`, do not content-filter results.

- [ ] **Step 5: Pass preference from downloader**

```python
url = audio_provider.search(
    song,
    self.settings["only_verified_results"],
    self.settings["content_preference"],
)
```

- [ ] **Step 6: Run provider + existing matching tests**

Run: `uv run pytest tests/product/test_provider_policy.py -q`
Run: `uv run pytest tests/test_matching.py -q`
Expected: focused policy tests PASS; record any live-network fixture drift separately rather than weakening strict behavior.

- [ ] **Step 7: Commit**

```bash
git add spotdl/providers/audio/base.py spotdl/download/downloader.py tests/product/test_provider_policy.py
git commit -m "feat: enforce explicit source matching"
```

---

### Task 4: Persistent Download Queue and History

**Files:**
- Create: `spotdl/product/store.py`
- Create: `spotdl/product/jobs.py`
- Test: `tests/product/test_store.py`
- Test: `tests/product/test_jobs.py`

**Interfaces:**
- `ProductStore(path: Path)` owns SQLite schema/migrations.
- `DownloadJobManager(store, downloader_factory)` creates album/track jobs and schedules them.
- Job states: `queued`, `resolving`, `searching`, `matched`, `downloading`, `transcoding`, `tagging`, `completed`, `needs_review`, `failed`, `cancelled`.
- Restart recovery moves interrupted active work back to `queued` with a recovery note.

- [ ] **Step 1: Write failing SQLite persistence tests**

Create a temporary database, insert a job and tracks, close/reopen it, and assert the job survives with exact album ID and content preference.

- [ ] **Step 2: Implement schema**

Use stdlib `sqlite3` with tables `settings`, `download_jobs`, `download_tracks`, and `manual_overrides`. Enable foreign keys and WAL where supported. Store timestamps in UTC ISO-8601.

- [ ] **Step 3: Write failing job state tests**

Assert allowed transitions, cancellation, retry, and restart recovery. Invalid transitions raise `ValueError` rather than silently corrupting state.

- [ ] **Step 4: Implement manager and sequential per-job track orchestration**

Album jobs hydrate the exact selected Spotify album ID. Each track is handed to the existing Downloader. A strict lookup failure becomes `needs_review` with `no_explicit_source` when appropriate. Other exceptions become `failed` with stable error codes.

- [ ] **Step 5: Run tests and commit**

Run: `uv run pytest tests/product/test_store.py tests/product/test_jobs.py -q`

```bash
git add spotdl/product/store.py spotdl/product/jobs.py tests/product/test_store.py tests/product/test_jobs.py
git commit -m "feat: add persistent download queue"
```

---

### Task 5: Versioned Product API

**Files:**
- Create: `spotdl/web/product_api.py`
- Modify: `spotdl/utils/web.py`
- Modify: `spotdl/console/web.py`
- Test: `tests/web/test_product_api.py`

**Interfaces:**
- `GET /api/v1/search?q=&type=&content_preference=`
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

- [ ] **Step 1: Write API contract tests**

Use FastAPI `TestClient` with dependency/service injection. Test explicit-only search filtering, exact album detail, queue creation, retry/cancel, and settings validation without network access.

- [ ] **Step 2: Add product services to application state**

Extend `ApplicationState` with `product_store`, `discovery`, and `jobs` references initialized by `console.web.web()` before server startup.

- [ ] **Step 3: Implement typed Pydantic request/response contracts**

Reject invalid content preferences with HTTP 422. Return stable error payloads with `code`, `message`, and optional `details`.

- [ ] **Step 4: Wire router without removing legacy `/api/*` endpoints**

Include the new router alongside `spotdl.web.api.router`. Legacy APIs remain for compatibility during the migration.

- [ ] **Step 5: Run tests and commit**

Run: `uv run pytest tests/web/test_product_api.py tests/product -q`

```bash
git add spotdl/web/product_api.py spotdl/utils/web.py spotdl/console/web.py tests/web/test_product_api.py
git commit -m "feat: add product api"
```

---

### Task 6: React/Vite Premium Application Shell

**Files:**
- Create: `webui/package.json`
- Create: `webui/tsconfig.json`
- Create: `webui/vite.config.ts`
- Create: `webui/index.html`
- Create: `webui/src/main.tsx`
- Create: `webui/src/App.tsx`
- Create: `webui/src/styles.css`
- Create: `webui/src/api/client.ts`
- Create: `webui/src/types.ts`
- Create: `webui/src/components/AppShell.tsx`
- Create: `webui/src/components/ExplicitBadge.tsx`
- Create: `webui/src/components/AlbumCard.tsx`
- Create: `webui/src/components/TrackTable.tsx`
- Create: `webui/src/test/setup.ts`
- Test: `webui/src/components/AlbumCard.test.tsx`

**Interfaces:**
- The frontend consumes only `/api/v1` JSON.
- Production build output is `spotdl/web/static` so PyInstaller continues bundling one web-static directory.

- [ ] **Step 1: Scaffold Vite manually with React + TypeScript**

Use current stable React/Vite packages and commit the generated lockfile. Configure `build.outDir = "../spotdl/web/static"` and `emptyOutDir = true`.

- [ ] **Step 2: Add test runner**

Configure Vitest + jsdom + Testing Library. Add scripts `dev`, `build`, `test`, `test:run`, and `typecheck`.

- [ ] **Step 3: Write failing album-card tests**

Verify `E EXPLICIT`, `CLEAN`, `NO EXPLICIT CONTENT`, deluxe/remaster tags, artwork alt text, and download action accessibility.

- [ ] **Step 4: Build the dark-first design system**

Implement CSS variables for surfaces, typography, spacing, focus rings, motion, responsive breakpoints, skeletons, error states, and badges. Avoid framework-admin-dashboard aesthetics.

- [ ] **Step 5: Build responsive shell/navigation**

Desktop sidebar + compact mobile header. Routes: Home, Search, Albums, Artists, Downloads, History, Settings.

- [ ] **Step 6: Run frontend checks and commit**

Run: `cd webui && npm run typecheck && npm run test:run && npm run build`
Expected: PASS and generated `spotdl/web/static/index.html` plus hashed assets.

```bash
git add webui spotdl/web/static
git commit -m "feat: add premium React web shell"
```

---

### Task 7: Explicit Discovery, Album, Download, and Settings Screens

**Files:**
- Create: `webui/src/pages/HomePage.tsx`
- Create: `webui/src/pages/SearchPage.tsx`
- Create: `webui/src/pages/ArtistPage.tsx`
- Create: `webui/src/pages/AlbumPage.tsx`
- Create: `webui/src/pages/DownloadsPage.tsx`
- Create: `webui/src/pages/HistoryPage.tsx`
- Create: `webui/src/pages/SettingsPage.tsx`
- Create: `webui/src/hooks/useDownloads.ts`
- Test: `webui/src/pages/SearchPage.test.tsx`
- Test: `webui/src/pages/AlbumPage.test.tsx`
- Test: `webui/src/pages/DownloadsPage.test.tsx`

**Interfaces:**
- Search supports All/Albums/Songs/Artists tabs and content-preference control.
- Album page always displays the exact Spotify album ID/edition and per-track explicit markers.
- Downloads page surfaces `needs_review` as an actionable state, never success.

- [ ] **Step 1: Implement API client methods for all v1 endpoints**

Use `fetch`, typed JSON decoding, `AbortController` for superseded searches, and a single `ApiError` type containing status/code/message.

- [ ] **Step 2: Implement debounced discovery UI**

Album-first results display artwork, artist, year, edition tags, explicit status, track count, and immediate download action. `explicit_only` is selected by default.

- [ ] **Step 3: Implement Artist/Album detail flows**

Artist page groups release families without merging low-confidence editions. Album page shows sibling edition selector and promotes explicit sibling where available.

- [ ] **Step 4: Implement download queue/history UI**

Poll the lightweight job endpoint on an interval while active jobs exist. Show job/track state, failures, exact album ID, retry/cancel, and explicit-source review state.

- [ ] **Step 5: Implement settings UI**

Persist `explicit_only`, `prefer_explicit`, or `any` through `/api/v1/settings`; explain the behavior in plain language.

- [ ] **Step 6: Run tests/build and commit**

Run: `cd webui && npm run typecheck && npm run test:run && npm run build`

```bash
git add webui spotdl/web/static
git commit -m "feat: add explicit album product experience"
```

---

### Task 8: Make the New SPA the Default Web UI and Update Build/CI

**Files:**
- Modify: `spotdl/console/web.py`
- Modify: `scripts/build.py`
- Modify: `.github/workflows/tests.yml`
- Create: `.github/workflows/webui.yml`
- Test: `tests/web/test_spa.py`

**Interfaces:**
- `/api/*` and `/api/v1/*` remain FastAPI routes.
- All non-API browser paths return the React `index.html` through `SPAStaticFiles`.

- [ ] **Step 1: Write SPA routing test**

Assert `/`, `/search`, `/albums/test`, and `/downloads` serve the SPA while `/api/version` still returns JSON.

- [ ] **Step 2: Remove the old server-rendered router from default registration**

Keep its source files for one migration cycle, but do not register `spotdl.web.routes.router` on the default app. Mount the built SPA at `/` after API routers.

- [ ] **Step 3: Update PyInstaller inputs**

Continue bundling `spotdl/web/static`; legacy Jinja components are no longer required by the default surface and may remain bundled temporarily if release compatibility demands it.

- [ ] **Step 4: Add frontend CI**

CI installs Node, runs `npm ci`, `npm run typecheck`, `npm run test:run`, and `npm run build`, then fails if the generated production build is missing.

- [ ] **Step 5: Run backend + frontend verification and commit**

Run: `uv run pytest tests/product tests/web -q`
Run: `cd webui && npm ci && npm run typecheck && npm run test:run && npm run build`

```bash
git add spotdl/console/web.py scripts/build.py .github/workflows tests/web webui spotdl/web/static
git commit -m "feat: make premium UI the default web app"
```

---

### Task 9: Regression, Real-World Explicit Validation, Packaging, and Handoff

**Files:**
- Create: `docs/EXPLICIT_CONTENT.md`
- Create: `docs/superpowers/verification/2026-08-10-explicit-ui-v1.md`
- Modify: `README.md`

**Interfaces:**
- Verification document is the evidence record for completion.

- [ ] **Step 1: Run the upstream-style Python suite**

Run: `uv run pytest -q --record-mode=none --disable-recording --ignore tests/providers/lyrics --ignore tests/utils/test_github.py --ignore tests/utils/test_ffmpeg.py --ignore tests/utils/test_metadata.py --ignore tests/test_matching.py --ignore tests/providers/audio/test_youtube.py --ignore tests/console/test_entry_point.py --ignore tests/test_init.py`

Record exact pass/fail counts.

- [ ] **Step 2: Run focused matching tests**

Run: `uv run pytest tests/product/test_provider_policy.py tests/test_matching.py -q`
Record live/network-dependent failures separately and do not claim them as passing.

- [ ] **Step 3: Validate real explicit/clean sibling releases**

Use at least two known artists with clean/explicit sibling releases and one genuinely non-explicit album. Record Spotify album IDs, classifications, and whether explicit-only search produces the intended result.

- [ ] **Step 4: Exercise a clearly clean candidate against an explicit Spotify track**

Record candidate metadata and demonstrate strict rejection. Exercise a valid explicit candidate and show successful selection. Exercise an ambiguous case and show `needs_review`.

- [ ] **Step 5: Verify queue restart persistence**

Create a queued/in-progress album job, restart the app/store, and demonstrate recovery to a safe resumable state.

- [ ] **Step 6: Build frontend and Python executable**

Run: `cd webui && npm ci && npm run build`
Run: `uv run python scripts/build.py`
Record artifact path/size and any platform-specific limitations.

- [ ] **Step 7: Update documentation**

README gets screenshots/feature copy only after the feature is actually working. `docs/EXPLICIT_CONTENT.md` defines the three content modes, clean vs non-explicit semantics, strict matching limitations, and manual override behavior.

- [ ] **Step 8: Write the evidence report and commit**

The report lists inspected scope, commands, results, unresolved limitations, and any intentionally skipped tests.

```bash
git add README.md docs/EXPLICIT_CONTENT.md docs/superpowers/verification/2026-08-10-explicit-ui-v1.md
git commit -m "docs: verify explicit album experience"
```

- [ ] **Step 9: Final review before merge**

Compare the branch to `master`, inspect every changed file, verify no accidental upstream attribution/license removal, verify generated frontend assets are present, and only then prepare the PR/merge.
