export const escapeHtml = (value) => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
export function explicitLabel(status) {
    return { explicit: 'E  EXPLICIT', clean: 'CLEAN', non_explicit: 'NO EXPLICIT CONTENT', mixed_or_unknown: 'EDITION UNKNOWN' }[status];
}
export function explicitBadge(status) {
    return `<span class="edition-badge edition-${status}">${explicitLabel(status)}</span>`;
}
export function formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.max(0, Math.round(seconds % 60));
    return `${mins}:${String(secs).padStart(2, '0')}`;
}
export function preferenceName(pref) {
    return pref === 'explicit_only' ? 'Explicit only' : pref === 'prefer_explicit' ? 'Prefer explicit' : 'Any version';
}
export function albumCard(album) {
    const art = album.artwork_url ? `<img loading="lazy" src="${escapeHtml(album.artwork_url)}" alt="${escapeHtml(album.name)} cover">` : `<div class="art-fallback">♪</div>`;
    const year = album.release_date?.slice(0, 4) ?? '—';
    const tags = album.edition_tags.filter(t => !['Explicit', 'Clean'].includes(t)).slice(0, 2).map(t => `<span class="soft-tag">${escapeHtml(t)}</span>`).join('');
    return `<article class="album-card" data-nav="/albums/${escapeHtml(album.album_id)}" tabindex="0" aria-label="Open ${escapeHtml(album.name)}">
    <div class="art-wrap">${art}<div class="art-overlay"><button class="round-action" data-download-album="${escapeHtml(album.album_id)}" aria-label="Download ${escapeHtml(album.name)}">↓</button></div></div>
    <div class="album-card-body"><div class="album-card-badges">${explicitBadge(album.explicit_status)}${tags}</div>
      <h3>${escapeHtml(album.name)}</h3><p>${escapeHtml(album.artists.join(', '))}</p>
      <div class="album-meta"><span>${escapeHtml(year)}</span><span>•</span><span>${album.total_tracks} tracks</span></div>
    </div></article>`;
}
export function artistCard(artist) {
    const art = artist.artwork_url ? `<img loading="lazy" src="${escapeHtml(artist.artwork_url)}" alt="${escapeHtml(artist.name)}">` : `<div class="art-fallback artist-fallback">✦</div>`;
    return `<article class="artist-card" data-nav="/artists/${escapeHtml(artist.artist_id)}" tabindex="0">${art}<h3>${escapeHtml(artist.name)}</h3><p>${escapeHtml(artist.genres.slice(0, 3).join(' · ') || 'Artist')}</p></article>`;
}
export function trackRow(track) {
    return `<div class="track-row"><div class="track-num">${track.track_number}</div><div class="track-title"><strong>${escapeHtml(track.name)}</strong><span>${escapeHtml(track.artists.join(', '))}</span></div>${track.explicit ? '<span class="tiny-e">E</span>' : '<span></span>'}<time>${formatDuration(track.duration)}</time></div>`;
}
function stateLabel(state) {
    return { queued: 'Queued', resolving: 'Resolving', searching: 'Finding source', matched: 'Matched', downloading: 'Downloading', transcoding: 'Converting', tagging: 'Tagging', completed: 'Complete', needs_review: 'Needs review', failed: 'Failed', cancelled: 'Cancelled' }[state];
}
export function jobCard(job) {
    const done = job.tracks.filter(t => t.state === 'completed').length;
    const progress = job.tracks.length ? Math.round((done / job.tracks.length) * 100) : 0;
    const statusClass = ['failed', 'needs_review', 'cancelled'].includes(job.state) ? ` state-${job.state}` : '';
    const problem = job.tracks.find(t => t.state === 'needs_review' || t.state === 'failed');
    return `<article class="job-card${statusClass}"><div class="job-head"><div><span class="eyebrow">${escapeHtml(job.kind.toUpperCase())}</span><h3>${escapeHtml(job.title)}</h3><p>${done}/${job.tracks.length} tracks · ${escapeHtml(stateLabel(job.state))}</p></div><span class="job-percent">${progress}%</span></div>
    <div class="progress"><span style="width:${progress}%"></span></div>
    ${problem ? `<div class="job-alert"><strong>${problem.state === 'needs_review' ? 'Explicit source needs review' : 'Download issue'}</strong><span>${escapeHtml(problem.error_message || problem.error_code || 'Attention required')}</span></div>` : ''}
    <div class="job-actions">${!['completed', 'cancelled'].includes(job.state) ? `<button class="ghost-button" data-cancel-job="${escapeHtml(job.job_id)}">Cancel</button>` : ''}${['failed', 'needs_review', 'cancelled'].includes(job.state) ? `<button class="primary-button compact" data-retry-job="${escapeHtml(job.job_id)}">Retry</button>` : ''}</div></article>`;
}
export const skeletonAlbums = (count = 6) => `<div class="album-grid">${Array.from({ length: count }, () => '<div class="album-card skeleton-card"><div class="skeleton art-skeleton"></div><div class="skeleton line wide"></div><div class="skeleton line"></div></div>').join('')}</div>`;
export function emptyState(title, body) {
    return `<div class="empty-state"><span class="empty-icon">⌁</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(body)}</p></div>`;
}
