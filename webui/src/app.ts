import { api, ApiError } from './api.js';
import type { ContentPreference, DownloadJobRecord } from './types.js';
import {
  albumCard,
  artistCard,
  downloadRail,
  emptyState,
  escapeHtml,
  explicitBadge,
  jobCard,
  preferenceName,
  queueRail,
  skeletonAlbums,
  trackTable,
} from './ui.js';

const root = document.querySelector<HTMLDivElement>('#app')!;
if (!root) throw new Error('Missing #app');

const state: {
  preference: ContentPreference;
  jobs: DownloadJobRecord[];
  searchAbort?: AbortController;
  poll?: number;
} = { preference: 'explicit_only', jobs: [] };

const icon = {
  home: '<svg viewBox="0 0 24 24"><path d="M3 11.5 12 4l9 7.5v8a1 1 0 0 1-1 1h-5.5v-6h-5v6H4a1 1 0 0 1-1-1z"/></svg>',
  discover: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg>',
  albums: '<svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="3"/><circle cx="12" cy="12" r="3"/></svg>',
  artists: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="3.5"/><path d="M5.5 20c.7-4 3-6 6.5-6s5.8 2 6.5 6"/></svg>',
  queue: '<svg viewBox="0 0 24 24"><path d="M5 7h10M5 12h10M5 17h7"/><path d="m17 15 3 2-3 2z"/></svg>',
  history: '<svg viewBox="0 0 24 24"><path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.5"/><path d="M4 4v4.5h4.5M12 8v5l3 2"/></svg>',
  settings: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1a7 7 0 0 0-1.8-1L14.4 3h-4.8l-.4 3.1a7 7 0 0 0-1.8 1L5 6.1 3 9.5 5 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a7 7 0 0 0 1.8 1l.4 3.1h4.8l.4-3.1a7 7 0 0 0 1.8-1l2.4 1 2-3.4-2-1.5c.1-.3.1-.7.1-1z"/></svg>',
};

function navItem(href: string, label: string, svg: string, active: string, extra = ''): string {
  return `<button class="studio-nav ${active === href ? 'active' : ''}" data-nav="${href}">${svg}<span>${label}</span>${extra}</button>`;
}

function sidebar(active: string): string {
  const activeCount = state.jobs.filter(job => !['completed','failed','cancelled'].includes(job.state)).length;
  return `<aside class="studio-sidebar">
    <div class="studio-brand"><div class="studio-brand-name">spotDL</div><div class="studio-brand-sub">✣ BLACK LABEL</div></div>
    <div class="nav-section"><span>HOME</span>${navItem('/', 'Home', icon.home, active)}${navItem('/search', 'Discover', icon.discover, active)}</div>
    <div class="nav-section"><span>LIBRARY</span>${navItem('/search?type=album', 'Albums', icon.albums, active)}${navItem('/search?type=artist', 'Artists', icon.artists, active)}</div>
    <div class="nav-section"><span>DOWNLOADS</span>${navItem('/downloads', 'Queue', icon.queue, active, activeCount ? `<b class="nav-count">${activeCount}</b>` : '')}${navItem('/history', 'History', icon.history, active)}</div>
    <div class="nav-section"><span>TOOLS</span>${navItem('/settings', 'Settings', icon.settings, active)}</div>
    <button class="explicit-mode-card" data-nav="/settings"><div><span class="explicit-mode-mark">E</span><strong>${state.preference === 'explicit_only' ? 'EXPLICIT ONLY MODE' : preferenceName(state.preference).toUpperCase()}</strong></div><p>${state.preference === 'explicit_only' ? 'Explicit tracks must resolve to an explicit-compatible source.' : 'Your edition preference is active.'}</p><span>Change in Settings →</span></button>
  </aside>`;
}

function topbar(): string {
  return `<header class="studio-topbar">
    <form id="chrome-search" class="chrome-search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg><input autocomplete="off" aria-label="Search music" placeholder="Search artists, albums, or paste a Spotify URL…"></form>
    <button class="top-policy ${state.preference === 'explicit_only' ? 'strict' : ''}" data-nav="/settings"><span>E</span>${preferenceName(state.preference)}</button>
    <button class="top-queue" data-nav="/downloads">${icon.queue}<span>Queue</span></button>
    <button class="top-settings" data-nav="/settings" aria-label="Settings">${icon.settings}</button>
  </header>`;
}

function shell(content: string, active: string): string {
  return `<div class="studio-shell">
    ${sidebar(active)}
    <section class="studio-workspace">${topbar()}<main class="studio-main">${content}</main></section>
    <aside id="queue-rail" class="queue-rail">${queueRail(state.jobs)}</aside>
    <footer id="download-rail" class="download-rail">${downloadRail(state.jobs, state.preference)}</footer>
  </div>`;
}

function activeRoute(path: string): string {
  if (path.startsWith('/albums/') || path.startsWith('/artists/')) return '/search';
  return path;
}

function navigate(path: string) {
  history.pushState({}, '', path);
  void render();
}

function searchBox(value = ''): string {
  return `<form id="page-search" class="page-search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg><input value="${escapeHtml(value)}" autocomplete="off" placeholder="Search Spotify’s catalog…" aria-label="Search Spotify catalog"><button type="submit">Search</button></form>`;
}

function preferenceControl(): string {
  return `<div class="preference-control" role="group" aria-label="Content preference">${(['explicit_only','prefer_explicit','any'] as ContentPreference[]).map(pref => `<button class="pref ${state.preference===pref?'active':''}" data-pref="${pref}">${pref==='explicit_only'?'<b>E</b> ':''}${preferenceName(pref)}</button>`).join('')}</div>`;
}

async function refreshJobs(): Promise<void> {
  try {
    state.jobs = await api.downloads();
    const queue = document.querySelector<HTMLElement>('#queue-rail');
    const rail = document.querySelector<HTMLElement>('#download-rail');
    if (queue) queue.innerHTML = queueRail(state.jobs);
    if (rail) rail.innerHTML = downloadRail(state.jobs, state.preference);
  } catch {
    // The primary pages already surface API failures. Chrome stays usable if polling fails.
  }
  if (state.poll) clearTimeout(state.poll);
  if (state.jobs.some(job => !['completed','failed','cancelled','needs_review'].includes(job.state))) {
    state.poll = window.setTimeout(() => void refreshJobs(), 1400);
  }
}

async function renderHome() {
  const active = state.jobs.find(job => !['completed','failed','cancelled'].includes(job.state));
  root.innerHTML = shell(`<section class="home-workbench">
    <div class="home-copy"><h1>Your music.<br><em>The right version.</em></h1><p>Find exact Spotify album editions, keep explicit releases explicit, and send them through spotDL’s proven download engine without guessing what you got.</p>${searchBox()}${preferenceControl()}</div>
    <div class="home-status"><div><span class="status-dot"></span><strong>Local engine ready</strong></div><p>${active ? `Currently working on ${escapeHtml(active.title)}.` : 'Nothing leaves this app except the provider requests needed to resolve your music.'}</p><button data-nav="${active ? '/downloads' : '/search'}">${active ? 'Open active queue' : 'Discover music'} →</button></div>
  </section>
  <section class="workbench-section"><div class="workbench-heading"><div><span>WHY THIS FORK EXISTS</span><h2>Edition intelligence before download.</h2></div></div><div class="intelligence-strip"><article><b>E</b><div><strong>Explicit-first discovery</strong><span>Clean sibling releases move out of the way when the explicit edition exists.</span></div></article><article><b>◎</b><div><strong>Exact album identity</strong><span>The selected Spotify album ID stays attached to the queue.</span></div></article><article><b>✓</b><div><strong>No fake success</strong><span>Ambiguous explicit matches stop for review instead of silently going green.</span></div></article></div></section>`, '/');
  bindSearchForms();
}

async function performSearch(query: string, tab: 'all'|'album'|'artist'='all') {
  state.searchAbort?.abort();
  state.searchAbort = new AbortController();
  const area = document.querySelector<HTMLDivElement>('#results');
  if (!area) return;
  area.innerHTML = skeletonAlbums();
  try {
    const data = await api.search(query, tab, state.preference, state.searchAbort.signal);
    const albums = data.albums.length ? `<div class="results-heading"><h2>Albums</h2><span>${data.albums.length} releases</span></div><div class="album-grid">${data.albums.map(albumCard).join('')}</div>` : '';
    const artists = data.artists.length ? `<div class="results-heading artists-heading"><h2>Artists</h2></div><div class="artist-grid">${data.artists.map(artistCard).join('')}</div>` : '';
    area.innerHTML = albums + artists || emptyState('Nothing matched', 'Try a different artist or album name.');
  } catch (error) {
    if ((error as Error).name === 'AbortError') return;
    area.innerHTML = emptyState('Search hit a snag', error instanceof ApiError ? error.detail : 'The local engine did not return results.');
  }
}

async function renderSearch() {
  const params = new URLSearchParams(location.search);
  const q = params.get('q') ?? '';
  const tab = (params.get('type') === 'album' || params.get('type') === 'artist' ? params.get('type') : 'all') as 'all'|'album'|'artist';
  root.innerHTML = shell(`<section class="discover-page"><div class="compact-heading"><h1>Discover the exact release.</h1><p>Explicit, clean, deluxe, remastered — know the edition before it hits the queue.</p></div>${searchBox(q)}<div class="discover-toolbar"><div class="search-tabs"><button class="${tab==='all'?'active':''}" data-search-type="all">All</button><button class="${tab==='album'?'active':''}" data-search-type="album">Albums</button><button class="${tab==='artist'?'active':''}" data-search-type="artist">Artists</button></div>${preferenceControl()}</div><div id="results">${q ? skeletonAlbums() : emptyState('Start with an artist or album', 'Sibling editions will be separated and the explicit release promoted.')}</div></section>`, '/search');
  bindSearchForms();
  if (q) await performSearch(q, tab);
}

async function renderAlbum(id: string) {
  root.innerHTML = shell(`<section class="album-workspace">${skeletonAlbums(1)}</section>`, '/search');
  try {
    const album = await api.album(id);
    const art = album.artwork_url ? `<img src="${escapeHtml(album.artwork_url)}" alt="${escapeHtml(album.name)} cover">` : '<div class="album-hero-fallback">♪</div>';
    const year = album.release_date?.slice(0,4) || '';
    const explicitTracks = album.explicit_track_count ? `${album.explicit_track_count} explicit track${album.explicit_track_count===1?'':'s'}` : 'No explicit tracks';
    const strictCopy = state.preference === 'explicit_only' ? 'Clean substitutions blocked' : `${preferenceName(state.preference)} policy`;
    root.innerHTML = shell(`<section class="album-workspace">
      <div class="breadcrumb"><button data-nav="/search">Search results</button><span>›</span><span>${escapeHtml(album.artists[0] || 'Artist')}</span><span>›</span><strong>${escapeHtml(album.name)}</strong></div>
      <div class="album-command"><div class="album-command-art">${art}</div><div class="album-command-copy"><div class="album-badges">${explicitBadge(album.explicit_status)}${album.edition_tags.filter(tag=>!['Explicit','Clean'].includes(tag)).map(tag=>`<span class="soft-tag">${escapeHtml(tag)}</span>`).join('')}</div><h1>${escapeHtml(album.name)}</h1><button class="album-artist" data-nav="${album.artist_ids[0] ? `/artists/${escapeHtml(album.artist_ids[0])}` : '/search'}">${escapeHtml(album.artists.join(', '))} →</button><p>${year ? `${escapeHtml(year)} · ` : ''}${album.total_tracks} tracks · ${escapeHtml(explicitTracks)}${album.label ? ` · ${escapeHtml(album.label)}` : ''}</p><div class="album-actions"><button class="primary-button album-download" data-download-album="${escapeHtml(album.album_id)}">↓ Download album</button><a class="ghost-button link-button" href="${escapeHtml(album.spotify_url)}" target="_blank" rel="noreferrer">Open Spotify ↗</a></div></div>
      <aside class="integrity-panel"><span>EDITION INTEGRITY</span><div class="integrity-row"><b>${album.explicit_status === 'explicit' ? 'E' : '•'}</b><div><strong>${album.explicit_status === 'explicit' ? 'Explicit edition selected' : 'Exact edition selected'}</strong><span>${escapeHtml(strictCopy)}</span></div></div><div class="integrity-row"><b>◎</b><div><strong>Exact Spotify identity</strong><span>${escapeHtml(album.album_id)}</span></div></div><div class="integrity-row"><b>✓</b><div><strong>${Math.round(album.grouping_confidence * 100)}% edition grouping</strong><span>${album.sibling_album_ids.length} sibling edition${album.sibling_album_ids.length===1?'':'s'} detected</span></div></div></aside></div>
      <div class="track-panel"><div class="track-panel-head"><div><h2>Tracks</h2><span>${album.total_tracks} songs</span></div><div class="track-policy"><span class="status-dot"></span>${preferenceName(state.preference)} source policy</div></div>${trackTable(album.tracks, state.preference)}</div>
    </section>`, '/search');
  } catch (error) {
    root.innerHTML = shell(`<section class="studio-error">${emptyState('Album unavailable', error instanceof ApiError ? error.detail : 'Metadata could not be loaded.')}</section>`, '/search');
  }
}

async function renderArtist(id: string) {
  root.innerHTML = shell(`<section class="discover-page">${skeletonAlbums()}</section>`, '/search');
  try {
    const [artist, albums] = await Promise.all([api.artist(id), api.artistAlbums(id, state.preference)]);
    const art = artist.artwork_url ? `<img src="${escapeHtml(artist.artwork_url)}" alt="${escapeHtml(artist.name)}">` : '<div class="artist-big-fallback">✦</div>';
    root.innerHTML = shell(`<section class="artist-workspace"><div class="artist-command">${art}<div><span>ARTIST</span><h1>${escapeHtml(artist.name)}</h1><p>${escapeHtml(artist.genres.join(' · ') || 'Spotify artist')}</p></div></div><div class="discover-toolbar">${preferenceControl()}</div><div class="results-heading"><h2>Releases</h2><span>${albums.length} shown</span></div><div class="album-grid">${albums.map(albumCard).join('') || emptyState('No releases', 'No matching editions were found.')}</div></section>`, '/search');
  } catch (error) {
    root.innerHTML = shell(`<section class="studio-error">${emptyState('Artist unavailable', error instanceof ApiError ? error.detail : 'Artist metadata could not be loaded.')}</section>`, '/search');
  }
}

async function renderDownloads(history = false) {
  root.innerHTML = shell(`<section class="queue-page"><div class="compact-heading"><h1>${history ? 'Download history.' : 'Download queue.'}</h1><p>${history ? 'Completed, failed, and cancelled jobs stay visible.' : 'Every job exposes the exact edition and its strict-source state.'}</p></div><div id="jobs">${skeletonAlbums(2)}</div></section>`, history ? '/history' : '/downloads');
  const visible = history ? state.jobs.filter(job => ['completed','failed','cancelled'].includes(job.state)) : state.jobs.filter(job => job.state !== 'completed');
  const area = document.querySelector<HTMLDivElement>('#jobs');
  if (area) area.innerHTML = visible.length ? `<div class="job-grid">${visible.map(jobCard).join('')}</div>` : emptyState('Nothing here yet', history ? 'Finished jobs will show up here.' : 'Pick an album and its progress will show up here.');
}

async function renderSettings() {
  root.innerHTML = shell(`<section class="settings-page"><div class="compact-heading"><h1>Make the rule permanent.</h1><p>Your content preference controls edition discovery and the source resolver.</p></div><div class="settings-grid"><div class="settings-card"><span>CONTENT POLICY</span><h2>Preferred version</h2><div class="settings-options">${(['explicit_only','prefer_explicit','any'] as ContentPreference[]).map(pref=>`<button class="setting-option ${state.preference===pref?'selected':''}" data-save-pref="${pref}"><span class="setting-radio"></span><div><strong>${preferenceName(pref)}</strong><p>${pref==='explicit_only'?'Hide clean sibling editions when explicit exists. Explicit tracks must resolve to an explicit-compatible source.':pref==='prefer_explicit'?'Rank explicit editions first, with visible fallbacks when certainty is unavailable.':'Do not filter by explicit status; preserve spotDL-style matching.'}</p></div></button>`).join('')}</div></div><div class="settings-card settings-note"><span>LOCAL-FIRST</span><h2>No account layer.</h2><p>Search and download orchestration run against the local spotDL engine. This fork does not add a cloud library or remote telemetry service.</p><div class="settings-facts"><div><b>FastAPI</b><span>Local application API</span></div><div><b>SQLite</b><span>Queue + history</span></div><div><b>spotDL</b><span>Downloader engine</span></div></div></div></div></section>`, '/settings');
}

function bindSearchForms() {
  const submit = (form: HTMLFormElement, selector: string) => {
    form.addEventListener('submit', event => {
      event.preventDefault();
      const query = form.querySelector<HTMLInputElement>(selector)?.value.trim();
      if (query) navigate(`/search?q=${encodeURIComponent(query)}`);
    });
  };
  const chrome = document.querySelector<HTMLFormElement>('#chrome-search');
  const page = document.querySelector<HTMLFormElement>('#page-search');
  if (chrome) submit(chrome, 'input');
  if (page) submit(page, 'input');
}

async function render() {
  if (state.poll) { clearTimeout(state.poll); state.poll = undefined; }
  const path = location.pathname;
  const route = activeRoute(path);
  if (path === '/') await renderHome();
  else if (path === '/search') await renderSearch();
  else if (path.startsWith('/albums/')) await renderAlbum(path.split('/')[2]);
  else if (path.startsWith('/artists/')) await renderArtist(path.split('/')[2]);
  else if (path === '/downloads') await renderDownloads(false);
  else if (path === '/history') await renderDownloads(true);
  else if (path === '/settings') await renderSettings();
  else root.innerHTML = shell(`<section class="studio-error">${emptyState('Page not found', 'That view does not exist.')}</section>`, route);
  bindSearchForms();
  void refreshJobs();
}

document.addEventListener('click', async event => {
  const target = event.target as HTMLElement;
  const nav = target.closest<HTMLElement>('[data-nav]');
  if (nav) { event.preventDefault(); navigate(nav.dataset.nav!); return; }
  const searchType = target.closest<HTMLElement>('[data-search-type]');
  if (searchType) {
    const params = new URLSearchParams(location.search);
    const type = searchType.dataset.searchType!;
    if (type === 'all') params.delete('type'); else params.set('type', type);
    navigate(`/search?${params.toString()}`);
    return;
  }
  const pref = target.closest<HTMLElement>('[data-pref]');
  if (pref) { state.preference = pref.dataset.pref as ContentPreference; await api.saveSettings(state.preference); await render(); return; }
  const savePref = target.closest<HTMLElement>('[data-save-pref]');
  if (savePref) { state.preference = savePref.dataset.savePref as ContentPreference; await api.saveSettings(state.preference); await render(); return; }
  const download = target.closest<HTMLElement>('[data-download-album]');
  if (download) {
    event.stopPropagation();
    const button = download as HTMLButtonElement;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Queued ✓';
    try {
      await api.downloadAlbum(download.dataset.downloadAlbum!, state.preference);
      await refreshJobs();
      window.setTimeout(() => navigate('/downloads'), 300);
    } catch {
      button.textContent = 'Try again';
      button.disabled = false;
      window.setTimeout(() => { button.textContent = original; }, 1500);
    }
    return;
  }
  const cancel = target.closest<HTMLElement>('[data-cancel-job]');
  if (cancel) { await api.cancel(cancel.dataset.cancelJob!); await refreshJobs(); await renderDownloads(false); return; }
  const retry = target.closest<HTMLElement>('[data-retry-job]');
  if (retry) { await api.retry(retry.dataset.retryJob!); await refreshJobs(); await renderDownloads(false); return; }
});

document.addEventListener('keydown', event => {
  if (event.key === 'Enter') {
    const element = event.target as HTMLElement;
    if (element.matches('[data-nav][tabindex="0"]')) navigate(element.dataset.nav!);
  }
});
window.addEventListener('popstate', () => void render());

(async () => {
  try { state.preference = (await api.settings()).content_preference; } catch { state.preference = 'explicit_only'; }
  try { state.jobs = await api.downloads(); } catch { state.jobs = []; }
  await render();
})();