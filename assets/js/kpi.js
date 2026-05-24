/**
 * kpi.js — the always-visible headline KPI cards.
 *
 * Each tile shows: label · value+unit · YoY change · 1Y sparkline.
 * Click → loads the underlying TradingView symbol into the hero panel.
 */
(function (global) {
  'use strict';

  // [sectionKey, seriesId, label, optional TradingView symbol, region badge]
  const KPI_DEFS = [
    ['rates',       'fed_funds',     'FED RATE',    'TVC:US10Y',    'US'],
    ['rates',       'boe_rate',      'BOE RATE',    'TVC:GB10Y',    'UK'],
    ['rates',       'ecb_rate',      'ECB RATE',    'TVC:DE10Y',    'EU'],
    ['commodities', 'oil_brent',     'BRENT',       'TVC:UKOIL',    'GLOBAL'],
    ['commodities', 'oil_wti',       'WTI',         'TVC:USOIL',    'US'],
    ['commodities', 'uk_petrol',     'UK PETROL',   null,           'UK'],
    ['commodities', 'uk_diesel',     'UK DIESEL',   null,           'UK'],
    ['commodities', 'gold',          'GOLD',        'TVC:GOLD',     'GLOBAL'],
  ];

  function init(sectionData) {
    const row = document.getElementById('kpi-row');
    if (!row) return;
    row.innerHTML = '';

    KPI_DEFS.forEach(([sec, sid, label, tvSymbol, region]) => {
      const series = sectionData[sec]?.series?.[sid];
      const tile = document.createElement('div');
      tile.className = 'kpi-tile' + (series ? '' : ' is-empty');

      if (!series) {
        tile.innerHTML = `
          <div class="kpi-label">${label}<span class="kpi-region">${region}</span></div>
          <div class="kpi-row-vals"><span class="kpi-value">——</span></div>
          <div class="kpi-change">no data</div>
          <div class="kpi-spark"></div>`;
        row.appendChild(tile);
        return;
      }

      const stats = series.stats || {};
      const val = global.ChartKit.formatNumber(stats.last_value, series.unit);
      const chg = stats.chg_1y_pct;
      let chgHTML = '<span class="kpi-change zero">——</span>';
      if (chg != null) {
        const cls = chg > 0 ? 'pos' : chg < 0 ? 'neg' : 'zero';
        const arrow = chg > 0 ? '▲' : chg < 0 ? '▼' : '·';
        chgHTML = `<span class="kpi-change ${cls}">${arrow} ${Math.abs(chg).toFixed(2)}% 1Y</span>`;
      }

      tile.innerHTML = `
        <div class="kpi-label">${label}<span class="kpi-region">${region}</span></div>
        <div class="kpi-row-vals">
          <span class="kpi-value">${val}</span>
          <span class="kpi-unit">${series.unit || ''}</span>
        </div>
        ${chgHTML}
        <div class="kpi-spark"></div>`;
      tile.title = series.note || series.name;

      // Click → load in hero
      if (tvSymbol) {
        tile.addEventListener('click', () => {
          const sel = document.getElementById('hero-symbol');
          if (sel) {
            // Add the option if it isn't already in the dropdown
            let opt = Array.from(sel.options).find(o => o.value === tvSymbol);
            if (!opt) {
              opt = document.createElement('option');
              opt.value = tvSymbol;
              opt.textContent = series.name;
              sel.appendChild(opt);
            }
            sel.value = tvSymbol;
          }
          if (global.Hero) global.Hero.setSymbol(tvSymbol);
          document.querySelector('.hero-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
      } else {
        // No TV symbol → click loads the local archive series into the hero
        tile.addEventListener('click', () => {
          if (global.Hero) {
            global.Hero.loadLocal(sec, sid, series);
          }
          document.querySelector('.hero-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
      }

      row.appendChild(tile);
      const spark = tile.querySelector('.kpi-spark');
      global.ChartKit.createSparkline(spark, series, { range: '1Y' });
    });
  }

  global.KPI = { init };
})(window);
