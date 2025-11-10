// Lightweight client for Research endpoints (backend API)
// Base: http://localhost:8000

const BASE = 'http://localhost:8000';

function normalizeResearch(payload) {
    // Accept either {success, research} or direct object shape
    const r = payload?.research ?? payload?.data ?? payload;
    if (!r || typeof r !== 'object') return null;

    // Duration: prefer r.duration (seconds). Fallback to difference of datetime_end-start
    let durationSec = null;
    if (typeof r.duration === 'number') durationSec = r.duration;
    else if (r.datetime_start && r.datetime_end) {
        const s = Date.parse(r.datetime_start);
        const e = Date.parse(r.datetime_end);
        if (!Number.isNaN(s) && !Number.isNaN(e) && e > s) durationSec = (e - s) / 1000;
    }

    return {
        id: r.id ?? null,
        slug: r.slug ?? r.id ?? null,
        title: r.title ?? r.query ?? 'Untitled Research',
        query: r.query ?? '',
        status: r.status ?? 'completed',
        durationSec,
        model: r.model ?? r.metadata?.model ?? '',
        resources_used: Array.isArray(r.resources_used) ? r.resources_used : [],
        datetime_start: r.datetime_start ?? (r.created_at ? new Date(r.created_at * 1000).toISOString() : null),
        datetime_end: r.datetime_end ?? null,
        tags: Array.isArray(r.tags) ? r.tags : (r.tags === null ? [] : []),
        answer: r.answer ?? null,
        metadata: r.metadata ?? {},
        created_at: typeof r.created_at === 'number' ? r.created_at : (r.datetime_start ? Date.parse(r.datetime_start) / 1000 : null),
        updated_at: typeof r.updated_at === 'number' ? r.updated_at : null,
        raw: r,
    };
}

export async function fetchResearches(options = {}) {
    const { status = 'completed', limit = 20, offset = 0 } = options;
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (limit != null) params.set('limit', String(limit));
    if (offset != null) params.set('offset', String(offset));

    const res = await fetch(`${BASE}/api/research/sessions?${params.toString()}`);
    if (!res.ok) throw new Error(`Failed to load researches: ${res.status}`);
    const json = await res.json();

    if (json?.success === false) throw new Error(json?.error || 'Failed to load researches');
    const list = json?.researches ?? json?.results ?? [];
    if (!Array.isArray(list)) throw new Error('Malformed researches response');
    return list.map((r) => normalizeResearch(r)).filter(Boolean);
}

export async function fetchResearch(slug) {
    const res = await fetch(`${BASE}/api/research/sessions/${encodeURIComponent(slug)}`);
    if (!res.ok) throw new Error(`Failed to load research: ${res.status}`);
    const json = await res.json();
    if (json?.success === false) throw new Error(json?.error || 'Research not found');
    const norm = normalizeResearch(json?.research ?? json);
    if (!norm) {
        throw new Error('Malformed research response');
    }
    return norm;
}

export async function searchResearches(q, limit = 50) {
    const params = new URLSearchParams({ q, limit: String(limit) });
    const res = await fetch(`${BASE}/api/research/search?${params.toString()}`);
    if (!res.ok) throw new Error(`Search failed: ${res.status}`);
    const json = await res.json();
    if (json?.success === false) throw new Error(json?.error || 'Search failed');
    const list = json?.results ?? [];
    if (!Array.isArray(list)) throw new Error('Malformed search response');
    return list.map((r) => normalizeResearch(r)).filter(Boolean);
}

export async function getStats() {
    const res = await fetch(`${BASE}/api/research/stats`);
    if (!res.ok) throw new Error(`Failed to load stats: ${res.status}`);
    const json = await res.json();
    if (json?.success === false) throw new Error(json?.error || 'Failed to load stats');
    return json?.stats ?? null;
}

export async function deleteResearch(slug) {
    const res = await fetch(`${BASE}/api/research/sessions/${encodeURIComponent(slug)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`Failed to delete research: ${res.status}`);
    const json = await res.json();
    if (json?.success === false) throw new Error(json?.error || 'Failed to delete research');
    return true;
}
