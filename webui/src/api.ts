import type { AlbumEdition, ArtistSummary, ContentPreference, DownloadJobRecord, SearchResponse } from './types.js';

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json() as { detail?: string };
      detail = body.detail ?? detail;
    } catch { /* response was not json */ }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  search(query: string, type: 'all' | 'album' | 'artist', preference: ContentPreference, signal?: AbortSignal) {
    const params = new URLSearchParams({ q: query, type, content_preference: preference });
    return request<SearchResponse>(`/api/v1/search?${params}`, { signal });
  },
  album(id: string) { return request<AlbumEdition>(`/api/v1/albums/${encodeURIComponent(id)}`); },
  artist(id: string) { return request<ArtistSummary>(`/api/v1/artists/${encodeURIComponent(id)}`); },
  artistAlbums(id: string, preference: ContentPreference) {
    const params = new URLSearchParams({ content_preference: preference });
    return request<AlbumEdition[]>(`/api/v1/artists/${encodeURIComponent(id)}/albums?${params}`);
  },
  downloadAlbum(id: string, preference: ContentPreference) {
    return request<DownloadJobRecord>(`/api/v1/downloads/albums/${encodeURIComponent(id)}`, {
      method: 'POST', body: JSON.stringify({ content_preference: preference }),
    });
  },
  downloads() { return request<DownloadJobRecord[]>('/api/v1/downloads'); },
  job(id: string) { return request<DownloadJobRecord>(`/api/v1/downloads/${encodeURIComponent(id)}`); },
  cancel(id: string) { return request<DownloadJobRecord>(`/api/v1/downloads/${encodeURIComponent(id)}/cancel`, { method: 'POST' }); },
  retry(id: string) { return request<DownloadJobRecord>(`/api/v1/downloads/${encodeURIComponent(id)}/retry`, { method: 'POST' }); },
  settings() { return request<{content_preference: ContentPreference}>('/api/v1/settings'); },
  saveSettings(content_preference: ContentPreference) {
    return request<{content_preference: ContentPreference}>('/api/v1/settings', {
      method: 'PATCH', body: JSON.stringify({ content_preference }),
    });
  },
};
