/**
 * data-loader.js
 *
 * Fetches the static JSON files written by scripts/fetch_data.py.
 * Caches in memory so each section is downloaded at most once per visit.
 */
(function (global) {
  'use strict';

  const cache = new Map();
  const inflight = new Map();

  const DATA_BASE = 'data';

  async function fetchJSON(path) {
    if (cache.has(path)) return cache.get(path);
    if (inflight.has(path)) return inflight.get(path);

    const p = fetch(`${path}?v=${Date.now()}`, { cache: 'no-store' })
      .then(async (r) => {
        if (!r.ok) throw new Error(`${path}: ${r.status}`);
        const json = await r.json();
        cache.set(path, json);
        inflight.delete(path);
        return json;
      })
      .catch((err) => {
        inflight.delete(path);
        console.warn('[data-loader]', err);
        return null;
      });
    inflight.set(path, p);
    return p;
  }

  const DataLoader = {
    manifest:  () => fetchJSON(`${DATA_BASE}/manifest.json`),
    section:   (key) => fetchJSON(`${DATA_BASE}/${key}.json`),
    events:    () => fetchJSON(`${DATA_BASE}/events.json`),

    /** Preload a list of sections in parallel (used for KPI strip). */
    preload: async (keys) => {
      const results = await Promise.all(keys.map((k) => DataLoader.section(k)));
      const out = {};
      keys.forEach((k, i) => { out[k] = results[i]; });
      return out;
    },

    clear: () => { cache.clear(); inflight.clear(); },
  };

  global.DataLoader = DataLoader;
})(window);
