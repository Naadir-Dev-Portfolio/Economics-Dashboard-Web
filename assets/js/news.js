/**
 * news.js — live newswire panel + the top-bar ticker.
 *
 * Reads data/news.json (produced by scripts/fetch_news.py via GH Actions).
 * Falls back to a friendly "syncing" state if not yet seeded.
 */
(function (global) {
  'use strict';

  const state = { items: [], region: 'GLOBAL' };
  let poller = null;

  function init(news) {
    if (news && news.items) state.items = news.items;
    render();
    if (!poller) poller = setInterval(async () => {
      if (document.hidden) return;
      const latest = await global.DataLoader.news();
      if (latest?.items) { state.items = latest.items; render(); }
    }, 5 * 60000);
  }

  function setRegion(region) { state.region = region; render(); }

  function timeAgo(iso) {
    if (!iso) return '';
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return Math.floor(diff) + 's';
    if (diff < 3600) return Math.floor(diff / 60) + 'm';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h';
    if (diff < 86400 * 7) return Math.floor(diff / 86400) + 'd';
    return new Date(iso).toISOString().slice(0, 10);
  }

  function filterItems() {
    if (state.region === 'GLOBAL') return state.items;
    const tagMap = { UK: 'UK', US: 'US', EU: 'EU', ASIA: 'ASIA' };
    const want = tagMap[state.region];
    if (!want) return state.items;
    return state.items.filter(it => !it.regions || it.regions.includes(want) || it.regions.includes('GLOBAL'));
  }

  function render() {
    const list = document.getElementById('news-list');
    const count = document.getElementById('news-count');
    if (!list) return;

    const items = filterItems().slice(0, 50);
    if (count) count.textContent = items.length ? `${items.length} items` : 'awaiting';

    if (!items.length) {
      list.innerHTML = '<div class="sub-loading">› newswire syncing — fetch_news.py runs hourly</div>';
      seedTicker([{ source: 'system', title: 'channel synchronising — news arrives via GitHub Actions hourly' }]);
      return;
    }

    list.innerHTML = '';
    const tpl = document.getElementById('tpl-news');
    items.forEach(it => {
      const frag = tpl.content.cloneNode(true);
      const row = frag.querySelector('.news-row');
      row.querySelector('.news-source').textContent = it.source || '';
      row.querySelector('.news-time').textContent = timeAgo(it.published);
      row.querySelector('.news-title').textContent = it.title;
      if (it.link) {
        row.addEventListener('click', () => global.open(it.link, '_blank', 'noopener'));
        row.style.cursor = 'pointer';
      }
      list.appendChild(frag);
    });

    seedTicker(items.slice(0, 18));
  }

  function seedTicker(items) {
    const track = document.getElementById('ticker-track');
    if (!track) return;
    track.innerHTML = '';
    if (!items || !items.length) {
      track.innerHTML = '<span class="ticker-item ticker-pending">› channel synchronising</span>';
      return;
    }
    // Duplicate the items so the marquee loop is seamless
    const all = items.concat(items);
    all.forEach(it => {
      const span = document.createElement('span');
      span.className = 'ticker-item';
      span.innerHTML = `<span class="src">${escapeHtml(it.source || '')}</span>${escapeHtml(it.title)}`;
      if (it.link) {
        span.style.cursor = 'pointer';
        span.addEventListener('click', () => global.open(it.link, '_blank', 'noopener'));
      }
      track.appendChild(span);
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  global.NewsFeed = { init, setRegion };
})(window);
