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
    panelHandles.forEach(handle => { handle.chart?.dispose(); handle.sparks?.forEach(spark => spark?.dispose()); });
    panelHandles.clear();
    grid.innerHTML = '';

    Object.entries(manifest.sections).forEach(([key, meta]) => {
      const payload = sectionData[key];
      const frag = tpl.content.cloneNode(true);
      const panel = frag.querySelector('.cat-panel');
      panel.dataset.sectionKey = key;
      panel.id = `cat-${key}`;
      panel.querySelector('.cat-glyph').textContent = ICON_MAP[meta.icon] || '◆';
      panel.querySelector('.cat-title').textContent = meta.title;
      const blurbEl = panel.querySelector('.cat-blurb');
      blurbEl.textContent = meta.blurb;
      // CSS tooltip renders instantly on hover via the data-tooltip
      // attribute. We deliberately do NOT set the native `title` here
      // — the browser's built-in title tooltip has a 1-2s delay that
      // competes with our styled one. aria-label keeps it accessible
      // for screen readers without triggering the native tooltip.
      blurbEl.setAttribute('aria-label', meta.blurb);
      blurbEl.setAttribute('data-tooltip', meta.blurb);

      // Header buttons
      panel.querySelector('.cat-toggle').addEventListener('click', () => {
        panel.classList.toggle('is-collapsed');
        // resize after expand
        const h = panelHandles.get(key);
        if (h?.chart) setTimeout(() => h.chart.resize(), 50);
      });
      panel.querySelector('.cat-tv').addEventListener('click', () => sendToHero(key));
      panel.querySelectorAll('[data-card-range]').forEach(button => {
        button.addEventListener('click', () => {
          panelHandles.get(key)?.chart?.setRange(button.dataset.cardRange);
          panel.querySelectorAll('[data-card-range]').forEach(b => b.classList.toggle('is-active', b === button));
        });
      });
      panel.querySelector('.cat-export').addEventListener('click', (ev) => {
        ev.stopPropagation();
        exportFocusedSeries(key, ev.currentTarget);
      });

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
    const { value: chg, unit: changeUnit } = global.ChartKit.annualChange(series);
    const chgEl = panel.querySelector('.cat-focus-change');
    if (chg == null) {
      chgEl.textContent = ''; chgEl.className = 'cat-focus-change';
    } else {
      const cls = chg > 0 ? 'pos' : chg < 0 ? 'neg' : 'zero';
      const arrow = chg > 0 ? '▲' : chg < 0 ? '▼' : '·';
      chgEl.textContent = `${arrow} ${Math.abs(chg).toFixed(2)} ${changeUnit} 1Y`;
      chgEl.className = `cat-focus-change ${cls}`;
    }
    const source = panel.querySelector('.cat-focus-source');
    source.textContent = global.ChartKit.sourceSummary(series);
    source.title = series.note || '';
    source.classList.toggle('is-warning', !!global.ChartKit.freshnessState(series));

    // Chart
    const chartEl = panel.querySelector('.cat-focus-chart');
    if (handle.chart) handle.chart.dispose();
    chartEl.innerHTML = '';
    chartEl.dataset.seriesKey = key + '/' + sid;
    const chart = global.ChartKit.createCardChart(chartEl, series, { range: '5Y' });
    handle.chart = chart;
    handle.focusSid = sid;
    panel.querySelectorAll('[data-card-range]').forEach(b => b.classList.toggle('is-active', b.dataset.cardRange === '5Y'));
  }

  function renderCarousel(key, payload, order, activeSid) {
    const panel = document.querySelector(`.cat-panel[data-section-key="${key}"]`);
    if (!panel) return;
    const car = panel.querySelector('.cat-carousel');
    car.innerHTML = '';
    const handle = panelHandles.get(key);
    handle.sparks = [];
    order.forEach(sid => {
      const series = payload.series[sid];
      if (!series) return;
      const chip = document.createElement('button');
      chip.className = 'chip' + (sid === activeSid ? ' is-active' : '');
      chip.dataset.sid = sid;
      const stats = series.stats || {};
      const { value: chg, unit: changeUnit } = global.ChartKit.annualChange(series);
      const chgCls = chg == null ? 'zero' : chg > 0 ? 'pos' : chg < 0 ? 'neg' : 'zero';
      const arrow = chg == null ? '·' : chg > 0 ? '▲' : chg < 0 ? '▼' : '·';
      chip.innerHTML = `
        <span class="chip-name">${escapeHtml(series.name)}</span>
        <span class="chip-spark"></span>
        <div style="display:flex;justify-content:space-between;align-items:baseline;gap:4px;">
          <span class="chip-val">${global.ChartKit.formatNumber(stats.last_value, series.unit)}</span>
          <span class="chip-chg ${chgCls}">${arrow} ${chg == null ? '—' : Math.abs(chg).toFixed(1) + ' ' + changeUnit}</span>
        </div>
      `;
      chip.addEventListener('click', () => {
        car.querySelectorAll('.chip').forEach(c => c.classList.remove('is-active'));
        chip.classList.add('is-active');
        renderFocus(key, sid);
      });
      car.appendChild(chip);
      const sp = chip.querySelector('.chip-spark');
      chip.title = global.ChartKit.sourceSummary(series);
      handle.sparks.push(global.ChartKit.createSparkline(sp, series, { range: '1Y' }));
    });
  }

  /**
   * Export the currently-focused series in this section as a CSV download.
   * Filename: <series_id>_<section>_<YYYY-MM-DD>.csv
   * Contents: an iso-date,value row per observation — the most granular
   * data we hold (monthly for FRED macro, weekly for fuel, daily for any
   * Yahoo-sourced series).
   */
  function exportFocusedSeries(key, buttonEl) {
    const handle = panelHandles.get(key);
    if (!handle?.focusSid) return;
    const sid = handle.focusSid;
    const series = handle.sectionPayload.series[sid];
    if (!series || !Array.isArray(series.data) || !series.data.length) return;

    const header = [
      `# ${series.name}${series.unit ? ' (' + series.unit + ')' : ''}`,
      series.note ? `# ${series.note}` : null,
      series.source ? `# Source: ${series.source}` : null,
      `# Exported from Naadir's Macro Economic Ops Dashboard on ${new Date().toISOString().slice(0,19)}Z`,
      'date,value',
    ].filter(Boolean).join('\n');

    const rows = series.data.map(([ts, v]) => {
      const d = new Date(ts).toISOString().slice(0, 10);
      return `${d},${v}`;
    }).join('\n');

    const csv = header + '\n' + rows + '\n';
    const today = new Date().toISOString().slice(0, 10);
    const filename = `${sid}_${key}_${today}.csv`;

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);

    // Brief green flash on the button so the user gets confirmation
    if (buttonEl) {
      buttonEl.classList.add('is-flash');
      setTimeout(() => buttonEl.classList.remove('is-flash'), 700);
    }
  }

  function sendToHero(key) {
    const handle = panelHandles.get(key);
    if (!handle || !handle.focusSid) return;
    const sid = handle.focusSid;
    const series = handle.sectionPayload.series[sid];
    global.Hero?.loadLocal(key, sid, series);
    document.querySelector('.hero-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
