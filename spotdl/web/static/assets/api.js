export class ApiError extends Error {
    status;
    detail;
    constructor(status, detail) {
        super(detail);
        this.status = status;
        this.detail = detail;
    }
}
async function request(path, init) {
    const response = await fetch(path, {
        ...init,
        headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    });
    if (!response.ok) {
        let detail = response.statusText;
        try {
            const body = await response.json();
            detail = body.detail ?? detail;
        }
        catch { /* response was not json */ }
        throw new ApiError(response.status, detail);
    }
    return response.json();
}
export const api = {
    search(query, type, preference, signal) {
        const params = new URLSearchParams({ q: query, type, content_preference: preference });
        return request(`/api/v1/search?${params}`, { signal });
    },
    album(id) { return request(`/api/v1/albums/${encodeURIComponent(id)}`); },
    artist(id) { return request(`/api/v1/artists/${encodeURIComponent(id)}`); },
    artistAlbums(id, preference) {
        const params = new URLSearchParams({ content_preference: preference });
        return request(`/api/v1/artists/${encodeURIComponent(id)}/albums?${params}`);
    },
    downloadAlbum(id, preference) {
        return request(`/api/v1/downloads/albums/${encodeURIComponent(id)}`, {
            method: 'POST', body: JSON.stringify({ content_preference: preference }),
        });
    },
    downloads() { return request('/api/v1/downloads'); },
    job(id) { return request(`/api/v1/downloads/${encodeURIComponent(id)}`); },
    cancel(id) { return request(`/api/v1/downloads/${encodeURIComponent(id)}/cancel`, { method: 'POST' }); },
    retry(id) { return request(`/api/v1/downloads/${encodeURIComponent(id)}/retry`, { method: 'POST' }); },
    settings() { return request('/api/v1/settings'); },
    saveSettings(content_preference) {
        return request('/api/v1/settings', {
            method: 'PATCH', body: JSON.stringify({ content_preference }),
        });
    },
};
