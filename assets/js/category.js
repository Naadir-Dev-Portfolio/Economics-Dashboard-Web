/**
 * category.js — one panel per dashboard section.
 *
 * Layout per panel:
 *   ┌──────────────────────────────┐
 *   │ ICON · Title · short blurb   │
 *   ├──────────────────────────────┤
 *   │ FOCUSED CHART (200px)        │
 *   │ value, change, source        │
 *   ├──────────────────────────────┤
 *   │ chip carousel ─ scroll x ──→ │
 *   └──────────────────────────────┘
 *
 * Clicking a chip swaps the focused chart to that series. Click the "TV"
 * icon in the header to send the active series to the hero panel.
 */
(function (global) {
  'use strict';

  const ICON_MAP = {
    trending_up: '↗', show_chart: '~', account_balance: '◭',
    local_fire_department: '✦', savings: '$', home: '⌂',
    oil_barrel: '◉', currency_exchange: '⇄', groups: '◯',
    factory: '◰', warning: '!',
  };

  // first series in `order` becomes the panel's headline focus
  const panelHandles = new Map(); // section_key → {chart, sectionPayload, focusSid}

  function init(manifest, sectionData) {
    const grid = document.getElementById('matrix-grid');
    if (!grid) return;
    const tpl = document.getElementById('tpl-category');
    grid.innerHTML = '';

    Object.entries(manifest.sections).forEach(([key, meta]) => {
      const payload = sectionData[key];
      const frag = tpl.content.cloneNode(true);
      const panel = frag.querySelector('.cat-panel');
      panel.dataset.sectionKey = key;
      panel.id = `cat-${key}`;
      panel.querySelector('.cat-glyph').textContent = ICON_MAP[meta.icon] || '◆';
      panel.querySelector('.cat-title').textContent = meta.title;
      panel.querySelector('.cat-blurb').textContent = meta.blurb;

      // Header buttons
      panel.querySelector('.cat-toggle').addEventListener('click', () => {
        panel.classList.toggle('is-collapsed');
        // resize after expand
        const h = panelHandles.get(key);
        if (h?.chart) setTimeout(() => h.chart.resize(), 50);
      });
      panel.querySelector('.cat-tv').addEventListener('click', () => sendToHero(key));

      grid.appendChild(frag);

      if (payload && payload.series && Object.keys(payload.series).length) {
        const order = payload.order || Object.keys(payload.series);
        const firstSid = order.find(s => payload.series[s]);
        if (firstSid) {
          panelHandles.set(key, { sectionPayload: payload, focusSid: firstSid });
          renderFocus(key, firstSid);
          renderCarousel(key, payload, order, firstSid);
        }
      } else {
        const body = panel.querySelector('.cat-body');
        body.innerHTML = `<div style="padding:24px;color:#6e6e6e;font-family:monospace;font-size:11px;text-align:center;">no data</div>`;
      }
    });
  }

  function renderFocus(key, sid) {
    const panel = document.querySelector(`.cat-panel[data-section-key="${key}"]`);
    if (!panel) return;
    const handle = panelHandles.get(key);
    if (!handle) return;
    const series = handle.sectionPayload.series[sid];
    if (!series) return;

    panel.querySelector('.cat-focus-name').textContent = series.name;
    const stats = series.stats || {};
    panel.querySelector('.cat-focus-value').textContent = global.ChartKit.formatNumber(stats.last_value, series.unit);
    panel.querySelector('.cat-focus-unit').textContent = series.unit || '';
    const chg = stats.chg_1y_pct;
    const chgEl = panel.querySelector('.cat-focus-change');
    if (chg == null) {
      chgEl.textContent = ''; chgEl.className = 'cat-focus-change';
    } else {
      const cls = chg > 0 ? 'pos' : chg < 0 ? 'neg' : 'zero';
      const arrow = chg > 0 ? '▲' : chg < 0 ? '▼' : '·';
      chgEl.textContent = `${arrow} ${Math.abs(chg).toFixed(2)}% 1Y`;
      chgEl.className = `cat-focus-change ${cls}`;
    }
    panel.querySelector('.cat-focus-source').textContent = series.source || '';

    // Chart
    const chartEl = panel.querySelector('.cat-focus-chart');
    chartEl.innerHTML = '';
    if (handle.chart) handle.chart.dispose();
    const chart = global.ChartKit.createCardChart(chartEl, series, { range: '5Y' });
    handle.chart = chart;
    handle.focusSid = sid;
  }

  function renderCarousel(key, payload, order, activeSid) {
    const panel = document.querySelector(`.cat-panel[data-section-key="${key}"]`);
    if (!panel) return;
    const car = panel.querySelector('.cat-carousel');
    car.innerHTML = '';
    order.forEach(sid => {
      const series = payload.series[sid];
      if (!series) return;
      const chip = document.createElement('button');
      chip.className = 'chip' + (sid === activeSid ? ' is-active' : '');
      chip.dataset.sid = sid;
      const stats = series.stats || {};
      const chg = stats.chg_1y_pct;
      const chgCls = chg == null ? 'zero' : chg > 0 ? 'pos' : chg < 0 ? 'neg' : 'zero';
      const arrow = chg == null ? '·' : chg > 0 ? '▲' : chg < 0 ? '▼' : '·';
      chip.innerHTML = `
        <span class="chip-name">${escapeHtml(series.name)}</span>
        <span class="chip-spark"></span>
        <div style="display:flex;justify-content:space-between;align-items:baseline;gap:4px;">
          <span class="chip-val">${global.ChartKit.formatNumber(stats.last_value, series.unit)}</span>
          <span class="chip-chg ${chgCls}">${arrow} ${chg == null ? '—' : Math.abs(chg).toFixed(1) + '%'}</span>
        </div>
      `;
      chip.addEventListener('click', () => {
        car.querySelectorAll('.chip').forEach(c => c.classList.remove('is-active'));
        chip.classList.add('is-active');
        renderFocus(key, sid);
      });
      car.appendChild(chip);
      const sp = chip.querySelector('.chip-spark');
      global.ChartKit.createSparkline(sp, series, { range: '1Y' });
    });
  }

  function sendToHero(key) {
    const handle = panelHandles.get(key);
    if (!handle || !handle.focusSid) return;
    const sid = handle.focusSid;
    // Look up corresponding TV symbol if any
    const sel = document.getElementById('hero-symbol');
    if (!sel) return;
    // Try to find an option with a value mapped to this sid (via hero.js's TV_SYMBOL_TO_LOCAL — duplicated here for the sectionToSid case)
    const seriesName = handle.sectionPayload.series[sid]?.name || sid;
    // Best effort: find an option label that matches the series name
    for (const opt of sel.options) {
      if (opt.textContent && opt.textContent.toLowerCase().includes(seriesName.toLowerCase().split(' ')[0])) {
        sel.value = opt.value;
        if (global.Hero) global.Hero.setSymbol(opt.value);
        document.querySelector('.hero-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
    }
    // Fallback: just scroll to hero
    document.querySelector('.hero-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function collapseAll() {
    document.querySelectorAll('.cat-panel').forEach(p => p.classList.add('is-collapsed'));
  }
  function expandAll() {
    document.querySelectorAll('.cat-panel').forEach(p => {
      p.classList.remove('is-collapsed');
    });
    panelHandles.forEach(h => h.chart && h.chart.resize());
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  global.CategoryMatrix = { init, renderFocus, collapseAll, expandAll };
})(window);
