import type { AlbumEdition, AlbumTrack, ArtistSummary, ContentPreference, DownloadJobRecord, DownloadTrackRecord, ExplicitStatus } from './types.js';

export const escapeHtml = (value: unknown): string => String(value ?? '')
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

export function explicitLabel(status: ExplicitStatus): string {
  return ({ explicit: 'E  EXPLICIT', clean: 'CLEAN', non_explicit: 'NO EXPLICIT CONTENT', mixed_or_unknown: 'EDITION UNKNOWN' } as const)[status];
}

export function explicitBadge(status: ExplicitStatus): string {
  return `<span class="edition-badge edition-${status}">${explicitLabel(status)}</span>`;
}

export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.max(0, Math.round(seconds % 60));
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

export function preferenceName(pref: ContentPreference): string {
  return pref === 'explicit_only' ? 'Explicit only' : pref === 'prefer_explicit' ? 'Prefer explicit' : 'Any version';
}

export function albumCard(album: AlbumEdition): string {
  const art = album.artwork_url ? `<img loading="lazy" src="${escapeHtml(album.artwork_url)}" alt="${escapeHtml(album.name)} cover">` : `<div class="art-fallback">♪</div>`;
  const year = album.release_date?.slice(0, 4) ?? '—';
  const tags = album.edition_tags.filter(t => !['Explicit','Clean'].includes(t)).slice(0,2).map(t => `<span class="soft-tag">${escapeHtml(t)}</span>`).join('');
  return `<article class="album-card" data-nav="/albums/${escapeHtml(album.album_id)}" tabindex="0" aria-label="Open ${escapeHtml(album.name)}">
    <div class="art-wrap">${art}<div class="art-overlay"><button class="round-action" data-download-album="${escapeHtml(album.album_id)}" aria-label="Download ${escapeHtml(album.name)}">↓</button></div></div>
    <div class="album-card-body"><div class="album-card-badges">${explicitBadge(album.explicit_status)}${tags}</div>
      <h3>${escapeHtml(album.name)}</h3><p>${escapeHtml(album.artists.join(', '))}</p>
      <div class="album-meta"><span>${escapeHtml(year)}</span><span>•</span><span>${album.total_tracks} tracks</span></div>
    </div></article>`;
}

export function artistCard(artist: ArtistSummary): string {
  const art = artist.artwork_url ? `<img loading="lazy" src="${escapeHtml(artist.artwork_url)}" alt="${escapeHtml(artist.name)}">` : `<div class="art-fallback artist-fallback">✦</div>`;
  return `<article class="artist-card" data-nav="/artists/${escapeHtml(artist.artist_id)}" tabindex="0">${art}<h3>${escapeHtml(artist.name)}</h3><p>${escapeHtml(artist.genres.slice(0,3).join(' · ') || 'Artist')}</p></article>`;
}

export function trackRow(track: {name:string; artists:string[]; track_number:number; duration:number; explicit:boolean}): string {
  return `<div class="track-row"><div class="track-num">${track.track_number}</div><div class="track-title"><strong>${escapeHtml(track.name)}</strong><span>${escapeHtml(track.artists.join(', '))}</span></div>${track.explicit ? '<span class="tiny-e">E</span>' : '<span></span>'}<time>${formatDuration(track.duration)}</time></div>`;
}

export function trackTable(tracks: AlbumTrack[], preference: ContentPreference): string {
  const rows = tracks.map(track => {
    const policy = track.explicit && preference === 'explicit_only'
      ? 'STRICT EXPLICIT'
      : track.explicit && preference === 'prefer_explicit'
        ? 'PREFER EXPLICIT'
        : track.explicit
          ? 'EXPLICIT'
          : 'NON-EXPLICIT';
    return `<div class="work-track-row">
      <span class="work-track-num">${track.track_number}</span>
      <div class="work-track-title"><strong>${escapeHtml(track.name)}</strong><span>${escapeHtml(track.artists.join(', '))}</span></div>
      <span class="work-track-explicit">${track.explicit ? '<b>E</b>' : ''}</span>
      <time>${formatDuration(track.duration)}</time>
      <span class="source-pending">Resolve on download</span>
      <span class="policy-tag ${track.explicit && preference === 'explicit_only' ? 'policy-strict' : ''}">${policy}</span>
    </div>`;
  }).join('');
  return `<div class="work-track-table" role="table" aria-label="Album tracks">
    <div class="work-track-head" role="row"><span>#</span><span>TITLE</span><span>E</span><span>TIME</span><span>SOURCE</span><span>SOURCE POLICY</span></div>
    ${rows}
  </div>`;
}

function stateLabel(state: DownloadTrackRecord['state']): string {
  return ({queued:'Queued',resolving:'Resolving',searching:'Finding source',matched:'Matched',downloading:'Downloading',transcoding:'Converting',tagging:'Tagging',completed:'Complete',needs_review:'Needs review',failed:'Failed',cancelled:'Cancelled'} as const)[state];
}

function progressForJob(job: DownloadJobRecord): number {
  const done = job.tracks.filter(t => t.state === 'completed').length;
  return job.tracks.length ? Math.round((done / job.tracks.length) * 100) : 0;
}

function activeJob(jobs: DownloadJobRecord[]): DownloadJobRecord | undefined {
  return jobs.find(job => !['completed','failed','cancelled'].includes(job.state));
}

export function queueRail(jobs: DownloadJobRecord[]): string {
  const active = jobs.filter(job => !['completed','failed','cancelled'].includes(job.state));
  const activeTracks = active.flatMap(job => job.tracks
    .filter(track => !['completed','cancelled'].includes(track.state))
    .map(track => ({...track, jobTitle: job.title}))
  ).slice(0, 7);
  const completed = jobs.reduce((count, job) => count + job.tracks.filter(track => track.state === 'completed').length, 0);
  const current = activeJob(jobs);
  const currentDone = current?.tracks.filter(track => track.state === 'completed').length ?? 0;
  const currentTotal = current?.tracks.length ?? 0;

  const trackRows = activeTracks.length ? activeTracks.map(track => `<div class="queue-track">
    <div class="queue-track-icon">${track.explicit ? '<b>E</b>' : '♪'}</div>
    <div class="queue-track-copy"><strong>${escapeHtml(track.name)}</strong><span>${escapeHtml(track.jobTitle)} · ${escapeHtml(stateLabel(track.state))}</span></div>
    <span class="queue-track-state state-${track.state}">${escapeHtml(stateLabel(track.state))}</span>
  </div>`).join('') : `<div class="queue-empty"><span>✓</span><strong>Queue clear</strong><p>Choose an exact album edition to start.</p></div>`;

  return `<aside class="queue-rail-inner">
    <div class="queue-rail-head"><div><span>DOWNLOAD QUEUE</span><b>${activeTracks.length}</b></div><button class="rail-icon" data-nav="/downloads" aria-label="Open downloads">↗</button></div>
    ${current ? `<div class="queue-current"><span class="status-dot"></span><div><strong>${escapeHtml(current.title)}</strong><span>${currentDone}/${currentTotal} complete · ${escapeHtml(stateLabel(current.state as DownloadTrackRecord['state']))}</span></div><b>${progressForJob(current)}%</b></div>` : ''}
    <div class="queue-track-list">${trackRows}</div>
    <div class="queue-stats"><div><strong>${active.length}</strong><span>Active jobs</span></div><div><strong>${completed}</strong><span>Tracks done</span></div><div><strong>${jobs.length}</strong><span>Total jobs</span></div></div>
    <button class="queue-open" data-nav="/downloads">Open full queue</button>
  </aside>`;
}

export function downloadRail(jobs: DownloadJobRecord[], preference: ContentPreference): string {
  const job = activeJob(jobs);
  const progress = job ? progressForJob(job) : 0;
  const done = job?.tracks.filter(track => track.state === 'completed').length ?? 0;
  const total = job?.tracks.length ?? 0;
  return `<div class="download-rail-inner">
    <div class="rail-policy"><span class="rail-policy-mark">E</span><div><strong>${preference === 'explicit_only' ? 'EXPLICIT ONLY' : preferenceName(preference).toUpperCase()}</strong><span>${preference === 'explicit_only' ? 'Clean substitutions blocked' : 'Content policy active'}</span></div></div>
    ${job ? `<div class="rail-current"><div class="rail-current-copy"><strong>${escapeHtml(job.title)}</strong><span>${done}/${total} tracks · ${escapeHtml(stateLabel(job.state as DownloadTrackRecord['state']))}</span></div><div class="rail-progress"><span style="width:${progress}%"></span></div><b>${progress}%</b></div>` : `<div class="rail-current rail-idle"><strong>No active downloads</strong><span>Your exact-edition queue is ready.</span></div>`}
    <button class="rail-action" data-nav="/downloads">Queue</button>
  </div>`;
}

export function jobCard(job: DownloadJobRecord): string {
  const done = job.tracks.filter(t => t.state === 'completed').length;
  const progress = progressForJob(job);
  const statusClass = ['failed','needs_review','cancelled'].includes(job.state) ? ` state-${job.state}` : '';
  const problem = job.tracks.find(t => t.state === 'needs_review' || t.state === 'failed');
  return `<article class="job-card${statusClass}"><div class="job-head"><div><span class="eyebrow">${escapeHtml(job.kind.toUpperCase())}</span><h3>${escapeHtml(job.title)}</h3><p>${done}/${job.tracks.length} tracks · ${escapeHtml(stateLabel(job.state as DownloadTrackRecord['state']))}</p></div><span class="job-percent">${progress}%</span></div>
    <div class="progress"><span style="width:${progress}%"></span></div>
    ${problem ? `<div class="job-alert"><strong>${problem.state === 'needs_review' ? 'Explicit source needs review' : 'Download issue'}</strong><span>${escapeHtml(problem.error_message || problem.error_code || 'Attention required')}</span></div>` : ''}
    <div class="job-actions">${!['completed','cancelled'].includes(job.state) ? `<button class="ghost-button" data-cancel-job="${escapeHtml(job.job_id)}">Cancel</button>` : ''}${['failed','needs_review','cancelled'].includes(job.state) ? `<button class="primary-button compact" data-retry-job="${escapeHtml(job.job_id)}">Retry</button>` : ''}</div></article>`;
}

export const skeletonAlbums = (count = 6): string => `<div class="album-grid">${Array.from({length:count},()=>'<div class="album-card skeleton-card"><div class="skeleton art-skeleton"></div><div class="skeleton line wide"></div><div class="skeleton line"></div></div>').join('')}</div>`;

export function emptyState(title: string, body: string): string {
  return `<div class="empty-state"><span class="empty-icon">⌁</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(body)}</p></div>`;
}