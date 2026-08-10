import { api, ApiError } from './api.js';
import type { ContentPreference } from './types.js';
import { albumCard, artistCard, emptyState, escapeHtml, explicitBadge, jobCard, preferenceName, skeletonAlbums, trackRow } from './ui.js';

const root = document.querySelector<HTMLDivElement>('#app')!;
if (!root) throw new Error('Missing #app');

const state: { preference: ContentPreference; searchAbort?: AbortController; poll?: number } = { preference: 'explicit_only' };

function shell(content: string, active: string): string {
  const nav = [
    ['/', 'Home', '⌂'], ['/search', 'Discover', '⌕'], ['/downloads', 'Downloads', '↓'], ['/history', 'History', '◴'], ['/settings', 'Settings', '⚙']
  ].map(([href,label,icon]) => `<button class="nav-item ${active === href ? 'active':''}" data-nav="${href}"><span>${icon}</span>${label}</button>`).join('');
  return `<div class="app-shell"><aside class="sidebar"><div class="brand"><div class="brand-mark">S</div><div><strong>spotDL</strong><span>BLACK LABEL</span></div></div><nav>${nav}</nav><div class="sidebar-card"><span class="status-dot"></span><div><strong>Local engine</strong><span>Private by default</span></div></div></aside><main class="main"><header class="mobile-head"><div class="brand"><div class="brand-mark">S</div><strong>spotDL</strong></div><button class="icon-button" data-nav="/settings">⚙</button></header>${content}</main></div>`;
}

function navigate(path: string) {
  history.pushState({}, '', path);
  render();
}

function searchHero(compact = false): string {
  return `<form id="global-search" class="search-box ${compact ? 'compact-search':''}"><span>⌕</span><input id="search-input" autocomplete="off" placeholder="Search artists or albums…" aria-label="Search artists or albums"><button type="submit">Search</button></form>`;
}

function preferenceControl(): string {
  return `<div class="preference-control" role="group" aria-label="Content preference">${(['explicit_only','prefer_explicit','any'] as ContentPreference[]).map(pref => `<button class="pref ${state.preference===pref?'active':''}" data-pref="${pref}">${pref==='explicit_only'?'<b>E</b> ':''}${preferenceName(pref)}</button>`).join('')}</div>`;
}

async function renderHome() {
  root.innerHTML = shell(`<section class="hero"><div class="hero-orb orb-one"></div><div class="hero-orb orb-two"></div><div class="hero-copy"><span class="kicker">YOUR MUSIC. THE RIGHT VERSION.</span><h1>Find the album.<br><em>Keep it explicit.</em></h1><p>Search Spotify’s catalog, separate explicit and clean editions, and send the exact release to spotDL’s proven download engine.</p>${searchHero()}${preferenceControl()}</div><div class="hero-stat"><span>E</span><div><strong>Strict explicit mode</strong><small>Clean substitutions are rejected, not hidden.</small></div></div></section><section class="section"><div class="section-head"><div><span class="eyebrow">BUILT DIFFERENT</span><h2>Exact edition intelligence</h2></div></div><div class="feature-grid"><article><span class="feature-icon">E</span><h3>Explicit-first discovery</h3><p>Clean counterparts move out of the way when the explicit sibling exists.</p></article><article><span class="feature-icon">◎</span><h3>Exact album identity</h3><p>Downloads stay pinned to the Spotify album ID you actually selected.</p></article><article><span class="feature-icon">✓</span><h3>No fake success</h3><p>If an explicit source cannot be verified, the track stops for review.</p></article></div></section>`, '/');
  bindSearch();
}

async function performSearch(query: string, tab: 'all'|'album'|'artist'='all') {
  state.searchAbort?.abort();
  state.searchAbort = new AbortController();
  const area = document.querySelector<HTMLDivElement>('#results');
  if (!area) return;
  area.innerHTML = skeletonAlbums();
  try {
    const data = await api.search(query, tab, state.preference, state.searchAbort.signal);
    const albums = data.albums.length ? `<div class="section-head"><h2>Albums</h2><span>${data.albums.length} releases</span></div><div class="album-grid">${data.albums.map(albumCard).join('')}</div>` : '';
    const artists = data.artists.length ? `<div class="section-head spaced"><h2>Artists</h2></div><div class="artist-grid">${data.artists.map(artistCard).join('')}</div>` : '';
    area.innerHTML = albums + artists || emptyState('Nothing matched', 'Try a different artist or album name.');
  } catch (error) {
    if ((error as Error).name === 'AbortError') return;
    area.innerHTML = emptyState('Search hit a snag', error instanceof ApiError ? error.detail : 'The local engine did not return results.');
  }
}

async function renderSearch() {
  const q = new URLSearchParams(location.search).get('q') ?? '';
  root.innerHTML = shell(`<section class="page"><div class="page-head"><span class="kicker">DISCOVER</span><h1>Find the exact release.</h1><p>Explicit, clean, deluxe, remastered — see the edition before it ever reaches your download queue.</p></div>${searchHero(true)}<div class="toolbar">${preferenceControl()}<div class="microcopy"><span class="status-dot"></span> Exact Spotify album IDs</div></div><div id="results">${q ? skeletonAlbums() : emptyState('Start with an artist or album', 'We’ll separate sibling editions and highlight the explicit release.')}</div></section>`, '/search');
  const input = document.querySelector<HTMLInputElement>('#search-input'); if (input) input.value = q;
  bindSearch(); if (q) await performSearch(q);
}

async function renderAlbum(id: string) {
  root.innerHTML = shell(`<section class="page">${skeletonAlbums(1)}</section>`, '/search');
  try {
    const album = await api.album(id);
    const art = album.artwork_url ? `<img src="${escapeHtml(album.artwork_url)}" alt="${escapeHtml(album.name)} cover">` : '<div class="album-hero-fallback">♪</div>';
    const explicitTracks = album.explicit_track_count ? `${album.explicit_track_count} explicit track${album.explicit_track_count===1?'':'s'}` : 'No explicit tracks';
    root.innerHTML = shell(`<section class="album-hero"><div class="album-hero-art">${art}</div><div class="album-hero-copy"><div class="album-card-badges">${explicitBadge(album.explicit_status)}${album.edition_tags.filter(x=>!['Explicit','Clean'].includes(x)).map(x=>`<span class="soft-tag">${escapeHtml(x)}</span>`).join('')}</div><span class="eyebrow">${escapeHtml(album.album_type?.toUpperCase() || 'ALBUM')}</span><h1>${escapeHtml(album.name)}</h1><button class="artist-link" data-nav="${album.artist_ids[0] ? `/artists/${escapeHtml(album.artist_ids[0])}` : '/search'}">${escapeHtml(album.artists.join(', '))}</button><p>${escapeHtml(album.release_date?.slice(0,4) || '')} · ${album.total_tracks} tracks · ${escapeHtml(explicitTracks)}${album.label ? ` · ${escapeHtml(album.label)}`:''}</p><div class="hero-actions"><button class="primary-button large" data-download-album="${escapeHtml(album.album_id)}">↓ Download exact album</button><a class="ghost-button link-button" href="${escapeHtml(album.spotify_url)}" target="_blank" rel="noreferrer">Open Spotify ↗</a></div><div class="exact-id"><span>EXACT EDITION ID</span><code>${escapeHtml(album.album_id)}</code></div></div></section><section class="track-section"><div class="section-head"><div><span class="eyebrow">TRACKLIST</span><h2>${album.total_tracks} songs</h2></div><span>${preferenceName(state.preference)}</span></div><div class="track-list">${album.tracks.map(trackRow).join('')}</div></section>`, '/search');
  } catch (error) { root.innerHTML = shell(`<section class="page">${emptyState('Album unavailable', error instanceof ApiError ? error.detail : 'Metadata could not be loaded.')}</section>`, '/search'); }
}

async function renderArtist(id: string) {
  root.innerHTML = shell(`<section class="page">${skeletonAlbums()}</section>`, '/search');
  try {
    const [artist, albums] = await Promise.all([api.artist(id), api.artistAlbums(id, state.preference)]);
    const art = artist.artwork_url ? `<img src="${escapeHtml(artist.artwork_url)}" alt="${escapeHtml(artist.name)}">` : '<div class="artist-big-fallback">✦</div>';
    root.innerHTML = shell(`<section class="artist-hero">${art}<div><span class="kicker">ARTIST</span><h1>${escapeHtml(artist.name)}</h1><p>${escapeHtml(artist.genres.join(' · ') || 'Spotify artist')}</p></div></section><section class="page artist-releases"><div class="toolbar">${preferenceControl()}</div><div class="section-head"><div><span class="eyebrow">DISCOGRAPHY</span><h2>Releases</h2></div><span>${albums.length} shown</span></div><div class="album-grid">${albums.map(albumCard).join('') || emptyState('No releases', 'No matching editions were found.')}</div></section>`, '/search');
  } catch (error) { root.innerHTML = shell(`<section class="page">${emptyState('Artist unavailable', error instanceof ApiError ? error.detail : 'Artist metadata could not be loaded.')}</section>`, '/search'); }
}

async function renderDownloads(history = false) {
  root.innerHTML = shell(`<section class="page"><div class="page-head"><span class="kicker">${history?'HISTORY':'DOWNLOADS'}</span><h1>${history?'What you’ve pulled down.':'The queue, without the mystery.'}</h1><p>${history?'Completed and past download jobs live here.':'Every job exposes the selected edition and whether its source passed explicit checks.'}</p></div><div id="jobs">${skeletonAlbums(2)}</div></section>`, history?'/history':'/downloads');
  const load = async () => {
    try {
      const jobs = await api.downloads();
      const visible = history ? jobs.filter(j=>['completed','failed','cancelled'].includes(j.state)) : jobs.filter(j=>!['completed'].includes(j.state));
      const area = document.querySelector<HTMLDivElement>('#jobs'); if (area) area.innerHTML = `<div class="job-grid">${visible.map(jobCard).join('')}</div>` || emptyState('Nothing here yet', history?'Finished jobs will show up here.':'Pick an album and its progress will show up here.');
      if (!history && jobs.some(j=>!['completed','failed','cancelled','needs_review'].includes(j.state))) state.poll = window.setTimeout(load, 1200);
    } catch (error) { const area=document.querySelector<HTMLDivElement>('#jobs'); if(area) area.innerHTML=emptyState('Queue unavailable', error instanceof ApiError?error.detail:'Could not load downloads.'); }
  };
  await load();
}

async function renderSettings() {
  root.innerHTML = shell(`<section class="page narrow"><div class="page-head"><span class="kicker">SETTINGS</span><h1>Set the rule once.</h1><p>Your content preference controls edition discovery and strict source matching.</p></div><div class="settings-card"><span class="eyebrow">CONTENT POLICY</span><h2>Preferred version</h2><div class="settings-options">${(['explicit_only','prefer_explicit','any'] as ContentPreference[]).map(pref=>`<button class="setting-option ${state.preference===pref?'selected':''}" data-save-pref="${pref}"><span class="setting-radio"></span><div><strong>${preferenceName(pref)}</strong><p>${pref==='explicit_only'?'Hide clean siblings when an explicit edition exists. Explicit tracks must resolve to an explicit-compatible source.':pref==='prefer_explicit'?'Rank explicit editions first, but allow a visible fallback when certainty is unavailable.':'Do not filter by explicit status; use spotDL-style matching.'}</p></div></button>`).join('')}</div></div><div class="settings-card"><span class="eyebrow">PRIVACY</span><h2>Local by design</h2><p class="settings-copy">Search and download orchestration run against the local spotDL engine. There is no product account, cloud library, or remote telemetry layer in this build.</p></div></section>`, '/settings');
}

function bindSearch() {
  document.querySelector<HTMLFormElement>('#global-search')?.addEventListener('submit', event => {
    event.preventDefault(); const query = document.querySelector<HTMLInputElement>('#search-input')?.value.trim();
    if (query) navigate(`/search?q=${encodeURIComponent(query)}`);
  });
}

async function render() {
  if (state.poll) { clearTimeout(state.poll); state.poll = undefined; }
  const path = location.pathname;
  if (path === '/') return renderHome();
  if (path === '/search') return renderSearch();
  if (path.startsWith('/albums/')) return renderAlbum(path.split('/')[2]);
  if (path.startsWith('/artists/')) return renderArtist(path.split('/')[2]);
  if (path === '/downloads') return renderDownloads(false);
  if (path === '/history') return renderDownloads(true);
  if (path === '/settings') return renderSettings();
  root.innerHTML = shell(`<section class="page">${emptyState('Page not found', 'That view does not exist.')}</section>`, '');
}

document.addEventListener('click', async event => {
  const target = event.target as HTMLElement;
  const nav = target.closest<HTMLElement>('[data-nav]');
  if (nav) { event.preventDefault(); navigate(nav.dataset.nav!); return; }
  const pref = target.closest<HTMLElement>('[data-pref]');
  if (pref) { state.preference = pref.dataset.pref as ContentPreference; await api.saveSettings(state.preference); render(); return; }
  const savePref = target.closest<HTMLElement>('[data-save-pref]');
  if (savePref) { state.preference = savePref.dataset.savePref as ContentPreference; await api.saveSettings(state.preference); render(); return; }
  const download = target.closest<HTMLElement>('[data-download-album]');
  if (download) { event.stopPropagation(); const button = download as HTMLButtonElement; const original = button.textContent; button.disabled = true; button.textContent = 'Queued ✓'; try { await api.downloadAlbum(download.dataset.downloadAlbum!, state.preference); window.setTimeout(()=>navigate('/downloads'), 350); } catch { button.textContent='Try again'; button.disabled=false; window.setTimeout(()=>button.textContent=original,1500); } return; }
  const cancel = target.closest<HTMLElement>('[data-cancel-job]'); if(cancel){ await api.cancel(cancel.dataset.cancelJob!); render(); return; }
  const retry = target.closest<HTMLElement>('[data-retry-job]'); if(retry){ await api.retry(retry.dataset.retryJob!); render(); return; }
});

document.addEventListener('keydown', event => { if (event.key === 'Enter') { const el = event.target as HTMLElement; if (el.matches('[data-nav][tabindex="0"]')) navigate(el.dataset.nav!); } });
window.addEventListener('popstate', render);

(async () => {
  try { state.preference = (await api.settings()).content_preference; } catch { state.preference = 'explicit_only'; }
  await render();
})();
