/**
 * ribbon.js — autoscrolling sparkline strip.
 *
 * Renders the most-watched series as small tiles in a CSS-marquee strip.
 * Each tile is a clickable surface — clicking it loads that symbol in the hero.
 */
(function (global) {
  'use strict';

  const RIBBON_SERIES = [
    ['markets',     'sp500'],
    ['markets',     'ftse100'],
    ['markets',     'dax'],
    ['markets',     'nikkei'],
    ['markets',     'hangseng'],
    ['markets',     'nasdaq'],
    ['bonds',       'us_10y'],
    ['bonds',       'uk_10y'],
    ['bonds',       'de_10y'],
    ['rates',       'fed_funds'],
    ['rates',       'boe_rate'],
    ['rates',       'ecb_rate'],
    ['commodities', 'oil_brent'],
    ['commodities', 'oil_wti'],
    ['commodities', 'gold'],
    ['commodities', 'natgas'],
    ['commodities', 'copper'],
    ['fx',          'gbp_usd'],
    ['fx',          'eur_usd'],
    ['fx',          'usd_jpy'],
    ['fx',          'dxy'],
    ['fx',          'btc_usd'],
    ['risk',        'vix'],
    ['inflation',   'us_cpi_yoy'],
    ['inflation',   'uk_cpi_yoy'],
  ];


  const sparklines = [];
  let paused = false;

  function init(sectionData) {
    const track = document.getElementById('ribbon-track');
    if (!track) return;
    track.innerHTML = '';

    const tiles = [];
    RIBBON_SERIES.forEach(([sec, sid]) => {
      const series = sectionData[sec]?.series?.[sid];
      if (!series) return;
      tiles.push(buildTile(series, sid));
    });

    if (!tiles.length) {
      track.innerHTML = '<div style="padding:30px;color:#6e6e6e;font-family:monospace;font-size:11px;">no data</div>';
      return;
    }

    // Duplicate the tiles so the CSS keyframe (which translates -50%) loops seamlessly.
    tiles.forEach(t => track.appendChild(t.cloneNode(true)));
    tiles.forEach(t => track.appendChild(t.cloneNode(true)));

    // Initialize sparklines on the tiles now in DOM
    Array.from(track.querySelectorAll('.ribbon-tile')).forEach(tile => {
      const sec = tile.dataset.section;
      const sid = tile.dataset.sid;
      const series = sectionData[sec]?.series?.[sid];
      if (!series) return;
      const sp = tile.querySelector('.rt-spark');
      const handle = global.ChartKit.createSparkline(sp, series, { range: '1Y' });
      if (handle) sparklines.push(handle);
      tile.addEventListener('click', () => {
        if (global.Hero) {
          global.Hero.loadLocal(sec, sid, series);
          document.querySelector('.hero-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    });

    // Pause button
    const pauseBtn = document.getElementById('ribbon-pause');
    if (pauseBtn) {
      pauseBtn.addEventListener('click', () => {
        paused = !paused;
        document.getElementById('ribbon').classList.toggle('is-paused', paused);
        pauseBtn.firstElementChild.textContent = paused ? '▶' : '⏸';
      });
    }
  }

  function buildTile(series, sid) {
    const tile = document.createElement('div');
    tile.className = 'ribbon-tile';
    tile.dataset.section = sectionFromSid(sid);
    tile.dataset.sid = sid;

    const stats = series.stats || {};
    const val = global.ChartKit.formatNumber(stats.last_value, series.unit);
    const { value: chg, unit: changeUnit } = global.ChartKit.annualChange(series);
    let chgHTML = '<span class="rt-chg zero">—</span>';
    if (chg != null) {
      const cls = chg > 0 ? 'pos' : chg < 0 ? 'neg' : 'zero';
      const arrow = chg > 0 ? '▲' : chg < 0 ? '▼' : '·';
      chgHTML = `<span class="rt-chg ${cls}">${arrow} ${Math.abs(chg).toFixed(2)} ${changeUnit}</span>`;
    }
    tile.innerHTML = `
      <div class="rt-name">${escapeHtml(series.name)}</div>
      <div class="rt-spark"></div>
      <div class="rt-vals"><span class="rt-val">${val}</span>${chgHTML}</div>
    `;
    tile.title = global.ChartKit.sourceSummary(series);
    return tile;
  }

  // Build a reverse lookup once
  const _sidToSec = (() => {
    const m = {};
    RIBBON_SERIES.forEach(([sec, sid]) => { m[sid] = sec; });
    return m;
  })();
  function sectionFromSid(sid) { return _sidToSec[sid] || ''; }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  global.Ribbon = { init };
})(window);
