/**
 * health-panel.js — sidebar data-source health-check.
 *
 * Renders one row per data source with a status dot (green/amber/red),
 * delivered/expected count, and last-refresh age. Tap any row to expand
 * full details (full name, URL, source type, sub-source breakdown, notes).
 *
 * Browser-side sources (CoinGecko, Yahoo proxy, TradingView) report their
 * status at runtime — LivePrices pings setRuntimeStatus() on each
 * successful or failed poll.
 */
(function (global) {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);

  // Runtime status for browser-side sources, updated by other modules.
  const runtimeStatus = {
    coingecko:    { status: 'pending', last_ok: null },
    yahoo_proxy:  { status: 'pending', last_ok: null },
    tradingview:  { status: 'pending', last_ok: null },
  };
  let healthData = null;

  function init(health) {
    healthData = health || { sources: [] };
    render();
    // Re-render every 60s to keep the "last refresh" relative times current.
    setInterval(render, 60_000);
  }

  /** Called from live-prices.js after each poll. */
  function setRuntimeStatus(id, ok) {
    const slot = runtimeStatus[id];
    if (!slot) return;
    if (ok) {
      slot.status = 'ok';
      slot.last_ok = new Date().toISOString();
    } else if (slot.status !== 'ok') {
      slot.status = 'error';
    }
    render();
  }

  function render() {
    const wrap = $('#health-panel');
    if (!wrap || !healthData) return;

    const sources = (healthData.sources || []).map(s => {
      if (s.runtime) {
        const rt = runtimeStatus[s.id];
        return { ...s, status: rt ? rt.status : 'pending', last_ok: rt?.last_ok };
      }
      return s;
    });

    // Header summary
    const ok = sources.filter(s => s.status === 'ok').length;
    const warn = sources.filter(s => s.status === 'warning').length;
    const err = sources.filter(s => s.status === 'error').length;
    const pending = sources.filter(s => s.status === 'pending').length;

    const headerHtml = `
      <div class="hc-summary">
        <span class="hc-pill hc-pill-ok"   title="Healthy">  ●  ${ok} </span>
        <span class="hc-pill hc-pill-warn" title="Warning">  ●  ${warn}</span>
        <span class="hc-pill hc-pill-err"  title="Error">    ●  ${err} </span>
        ${pending ? `<span class="hc-pill hc-pill-pending" title="Pending — not yet polled">●  ${pending}</span>` : ''}
      </div>
    `;

    const rowsHtml = sources.map(s => buildRow(s)).join('');
    wrap.innerHTML = headerHtml + `<div class="hc-rows">${rowsHtml}</div>`;
    // Wire row clicks for expand/collapse
    wrap.querySelectorAll('.hc-row').forEach(row => {
      row.addEventListener('click', () => row.classList.toggle('is-expanded'));
    });
  }

  function buildRow(s) {
    const dotClass = `hc-dot hc-dot-${s.status || 'pending'}`;
    const counts = (s.expected != null && s.delivered != null)
      ? `${s.delivered}/${s.expected}`
      : (s.runtime ? 'live' : '—');
    const age = relativeTime(s.last_fetch || s.last_ok);
    return `
      <div class="hc-row" data-id="${s.id}">
        <div class="hc-row-main">
          <span class="${dotClass}" title="${labelForStatus(s.status)}"></span>
          <span class="hc-glyph">${escapeHtml(s.icon || '·')}</span>
          <span class="hc-name">${escapeHtml(s.name)}</span>
          <span class="hc-count">${counts}</span>
          <span class="hc-chevron">›</span>
        </div>
        <div class="hc-row-detail">
          <div class="hc-detail-line"><span class="hc-key">Type</span><span>${escapeHtml(s.type || '—')}</span></div>
          <div class="hc-detail-line"><span class="hc-key">Last</span><span>${age || '—'}</span></div>
          ${s.latest_data ? `<div class="hc-detail-line"><span class="hc-key">Data thru</span><span>${escapeHtml(s.latest_data)}</span></div>` : ''}
          ${s.url ? `<div class="hc-detail-line"><span class="hc-key">URL</span><a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">${escapeHtml(hostOf(s.url))}</a></div>` : ''}
          ${renderSubSources(s.sub_sources)}
          <div class="hc-notes">${escapeHtml(s.notes || '')}</div>
        </div>
      </div>
    `;
  }

  function renderSubSources(sub) {
    if (!sub || !Object.keys(sub).length) return '';
    const items = Object.entries(sub).map(([name, count]) => {
      const isAlive = count > 0;
      return `<span class="hc-sub ${isAlive ? 'is-ok' : 'is-down'}">${escapeHtml(name)}<span>${count}</span></span>`;
    }).join('');
    return `<div class="hc-sub-list">${items}</div>`;
  }

  function labelForStatus(s) {
    return ({ ok: 'Healthy', warning: 'Warning', error: 'Error', pending: 'Pending' }[s]) || 'Unknown';
  }

  function relativeTime(iso) {
    if (!iso) return null;
    const t = new Date(iso).getTime();
    if (isNaN(t)) return null;
    const diff = (Date.now() - t) / 1000;
    if (diff < 60)      return Math.floor(diff) + 's ago';
    if (diff < 3600)    return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400)   return Math.floor(diff / 3600) + 'h ago';
    if (diff < 86400*7) return Math.floor(diff / 86400) + 'd ago';
    return new Date(iso).toISOString().slice(0, 10);
  }

  function hostOf(url) {
    try { return new URL(url).hostname.replace(/^www\./, ''); }
    catch (_) { return url; }
  }
  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  global.HealthPanel = { init, setRuntimeStatus };
})(window);
