/**
 * data-loader.js — fetches static JSON files written by the Python scripts.
 *
 * Caches in memory; cache-busts the request URL so the browser respects
 * recent GH Action commits.
 */
(function (global) {
  'use strict';

  const cache = new Map();
  const inflight = new Map();
  const BASE = 'data';

  async function fetchJSON(path) {
    const cached = cache.get(path);
    if (cached && Date.now() - cached.at < 5 * 60000) return cached.data;
    if (inflight.has(path)) return inflight.get(path);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    const p = fetch(`${path}?v=${Date.now()}`, { cache: 'no-store', signal: controller.signal })
      .then(async r => {
        if (!r.ok) throw new Error(`${path}: ${r.status}`);
        const json = await r.json();
        cache.set(path, { data: json, at: Date.now() });
        inflight.delete(path);
        return json;
      })
      .catch(err => {
        inflight.delete(path);
        console.warn('[data-loader]', err);
        return cached?.data || null;
      }).finally(() => clearTimeout(timeout));
    inflight.set(path, p);
    return p;
  }

  async function mergedEvents() {
    const [hist, recent] = await Promise.all([
      fetchJSON(`${BASE}/events.json`),
      fetchJSON(`${BASE}/events_recent.json`),
    ]);
    const histArr = hist?.events || [];
    const recentArr = recent?.events || [];
    // Dedupe by (date, normalized title prefix)
    const seen = new Set();
    const norm = t => (t || '').toLowerCase().replace(/\W+/g, ' ').trim().slice(0, 60);
    const merged = [];
    for (const e of [...recentArr, ...histArr]) {
      const key = `${e.date}::${norm(e.title)}`;
      if (seen.has(key)) continue;
      seen.add(key);
      merged.push(e);
    }
    merged.sort((a, b) => b.date.localeCompare(a.date));
    return { meta: { count: merged.length }, events: merged };
  }

  global.DataLoader = {
    manifest:  () => fetchJSON(`${BASE}/manifest.json`),
    section:   (key) => fetchJSON(`${BASE}/${key}.json`),
    events:    () => mergedEvents(),
    news:      () => fetchJSON(`${BASE}/news.json`),
    narrative: () => fetchJSON(`${BASE}/narrative.json`),
    calendar:  () => fetchJSON(`${BASE}/calendar.json`),
    education: () => fetchJSON(`${BASE}/education.json`),
    health:    () => fetchJSON(`${BASE}/health.json`),
    clear:     () => { cache.clear(); inflight.clear(); },
  };
})(window);
