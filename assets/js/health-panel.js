/**
 * health-panel.js — sidebar data-source health-check.
 *
 * Renders one row per data source with a status dot (green/amber/red),
 * delivered/expected count, and last-refresh age. Tap any row to expand
 * full details (full name, URL, source type, sub-source breakdown, notes).
 *
 * Browser-side sources (CoinGecko and TradingView) report their
 * status at runtime — LivePrices pings setRuntimeStatus() on each
 * successful or failed poll.
 */
(function (global) {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);

  // Runtime status for browser-side sources, updated by other modules.
  const runtimeStatus = {
    coingecko:    { status: 'waiting', last_ok: null },
    tradingview:  { status: 'pending', last_ok: null },
  };
  let healthData = null;
  let poller = null;
  // Preserve which rows the user has expanded across the 60s re-renders.
  const expandedIds = new Set();

  function init(health) {
    healthData = health || { sources: [] };
    render();
    // Re-render every 60s to keep the "last refresh" relative times current.
    if (!poller) poller = setInterval(async () => {
      if (document.hidden) return;
      const latest = await global.DataLoader.health();
      if (latest) healthData = latest;
      render();
      global.dispatchEvent(new CustomEvent('data-health-updated', { detail: healthData }));
    }, 60_000);
  }

  /** Called from live-prices.js after each poll. */
  function setRuntimeStatus(id, ok, details = {}) {
    const slot = runtimeStatus[id];
    if (!slot) return;
    slot.last_attempt = new Date().toISOString();
    if (ok === 'embedded') {
      slot.status = 'embedded';
    } else if (ok === 'inactive' || ok === 'waiting') {
      slot.status = ok;
    } else if (ok === true) {
      slot.status = 'ok';
      slot.last_ok = new Date().toISOString();
    } else {
      slot.status = slot.last_ok || details.retry_at ? 'warning' : 'error';
    }
    slot.message = details.message || '';
    slot.retry_at = details.retry_at || null;
    render();
  }

  function render() {
    const wrap = $('#health-panel');
    if (!wrap || !healthData) return;

    const sources = (healthData.sources || []).filter(s => s.id !== 'yahoo_proxy').map(s => {
      if (s.runtime) {
        const rt = runtimeStatus[s.id];
        const status = rt?.status === 'ok' && Date.now() - Date.parse(rt.last_ok) > 5 * 60000 ? 'warning' : rt?.status || 'pending';
        return { ...s, status, last_ok: rt?.last_ok, message: rt?.message, retry_at: rt?.retry_at };
      }
      const limit = s.id === 'news' ? 3 : 36;
      const overdue = !s.last_fetch || Date.now() - Date.parse(s.last_fetch) > limit * 3600000;
      return overdue && s.status === 'ok' ? { ...s, status: 'warning', message: 'Scheduled refresh overdue' } : s;
    });

    // Header summary
    const scheduled = sources.filter(s => !s.runtime);
    const ok = scheduled.filter(s => s.status === 'ok').length;
    const warn = scheduled.filter(s => s.status === 'warning').length;
    const err = scheduled.filter(s => s.status === 'error').length;

    const headerHtml = `
      <div class="hc-summary">
        <span class="hc-pill hc-pill-ok"   title="Healthy">  ●  ${ok} </span>
        <span class="hc-pill hc-pill-warn" title="Warning">  ●  ${warn}</span>
        <span class="hc-pill hc-pill-err"  title="Error">    ●  ${err} </span>
      </div>
    `;

    wrap.innerHTML = '<div class="hc-group">Scheduled data</div>' + headerHtml +
      `<div class="hc-rows">${scheduled.map(buildRow).join('')}</div>` +
      '<div class="hc-group">Optional browser feeds</div>' +
      `<div class="hc-rows">${sources.filter(s => s.runtime).map(buildRow).join('')}</div>`;
    // Re-apply user-toggled expanded state (survives 60s re-render).
    wrap.querySelectorAll('.hc-row').forEach(row => {
      if (expandedIds.has(row.dataset.id)) row.classList.add('is-expanded');
      row.addEventListener('click', () => {
        const id = row.dataset.id;
        if (expandedIds.has(id)) { expandedIds.delete(id); row.classList.remove('is-expanded'); }
        else                     { expandedIds.add(id);    row.classList.add('is-expanded'); }
      });
    });
  }

  function buildRow(s) {
    const dotClass = `hc-dot hc-dot-${s.status || 'pending'}`;
    const counts = (s.expected != null && s.delivered != null)
      ? `${s.delivered}/${s.expected}`
      : (s.runtime ? labelForStatus(s.status) : '—');
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
          <div class="hc-detail-line"><span class="hc-key">Status</span><span>${escapeHtml(s.message || labelForStatus(s.status))}</span></div>
          ${s.retry_at ? `<div class="hc-detail-line"><span class="hc-key">Retry</span><span>${escapeHtml(new Date(s.retry_at).toLocaleTimeString('en-GB'))}</span></div>` : ''}
          <div class="hc-detail-line"><span class="hc-key">Type</span><span>${escapeHtml(s.type || '—')}</span></div>
          <div class="hc-detail-line"><span class="hc-key">Last</span><span>${age || '—'}</span></div>
          ${s.latest_data ? `<div class="hc-detail-line"><span class="hc-key">Data thru</span><span>${escapeHtml(s.latest_data)}</span></div>` : ''}
          ${s.url ? `<div class="hc-detail-line"><span class="hc-key">URL</span><a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">${escapeHtml(hostOf(s.url))}</a></div>` : ''}
          ${renderSubSources(s.sub_sources, s.feed_status)}
          ${s.issues?.length ? '<ul class="hc-issues">' + s.issues.map(issue => '<li>' + escapeHtml(issue.name) + ': ' + escapeHtml(issue.reason) + (issue.period ? ' · ' + escapeHtml(issue.period) : '') + '</li>').join('') + '</ul>' : ''}
          <div class="hc-notes">${escapeHtml(s.notes || '')}</div>
        </div>
      </div>
    `;
  }

  function renderSubSources(sub, reports = {}) {
    if (!sub || !Object.keys(sub).length) return '';
    const items = Object.entries(sub).map(([name, count]) => {
      const isAlive = reports[name] ? reports[name].status === 'ok' : count > 0;
      return `<span class="hc-sub ${isAlive ? 'is-ok' : 'is-down'}">${escapeHtml(name)}<span>${count}</span></span>`;
    }).join('');
    return `<div class="hc-sub-list">${items}</div>`;
  }

  function labelForStatus(s) {
    return ({ ok: 'Healthy', warning: 'Warning', error: 'Unavailable', pending: 'Not opened', waiting: 'Waiting', inactive: 'Inactive', embedded: 'Embedded' }[s]) || 'Unknown';
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
