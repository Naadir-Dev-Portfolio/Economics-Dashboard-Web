/**
 * kpi.js — the always-visible headline KPI cards.
 *
 * Each tile shows: label · value+unit · YoY change · 1Y sparkline · countdown
 * to the next official release for that indicator (from data/calendar.json).
 *
 * Click → loads the underlying TradingView symbol in the hero panel.
 *
 * Colour rule (user request 2026-05): when a value is UP, the change number
 * text stays white; only the ▲ arrow is green. When DOWN, full red.
 */
(function (global) {
  'use strict';

  // [sectionKey, seriesId, label, optional TradingView symbol, region badge,
  //  calendar event key for the countdown]
  const KPI_DEFS = [
    ['rates',       'fed_funds',     'FED RATE',       'ECONOMICS:USINTR',  'US',     'fomc'],
    ['rates',       'boe_rate',      'BOE RATE',       'ECONOMICS:GBINTR',  'UK',     'boe_mpc'],
    ['rates',       'ecb_rate',      'ECB RATE',       'ECONOMICS:EUINTR',  'EU',     'ecb_meeting'],
    ['money',       'us_m2',         'US M2',          'ECONOMICS:USM2',    'US',     'us_m2'],
    ['inflation',   'us_cpi_yoy',    'US CPI',         'ECONOMICS:USIRYY',  'US',     'us_cpi'],
    ['inflation',   'uk_cpi_yoy',    'UK CPI',         'ECONOMICS:GBIRYY',  'UK',     'uk_cpi'],
    ['employment',  'us_unrate',     'US UNEMPLOYMENT','ECONOMICS:USURATE', 'US',     'us_nfp'],
    ['employment',  'uk_unrate',     'UK UNEMPLOYMENT','ECONOMICS:GBURATE', 'UK',     'uk_labour'],
    ['commodities', 'oil_brent',     'BRENT',          'TVC:UKOIL',         'GLOBAL', null],
    ['commodities', 'oil_wti',       'WTI',            'TVC:USOIL',         'US',     null],
    ['commodities', 'uk_petrol',     'UK PETROL',      null,                'UK',     'uk_fuel'],
    ['commodities', 'uk_diesel',     'UK DIESEL',      null,                'UK',     'uk_fuel'],
    ['commodities', 'gold',          'GOLD',           'TVC:GOLD',          'GLOBAL', null],
    ['risk',        'vix',           'VIX',            'TVC:VIX',           'US',     null],
  ];

  let calendarEvents = [];  // injected by main.js

  function init(sectionData, calendar) {
    calendarEvents = (calendar && calendar.events) || [];

    const row = document.getElementById('kpi-row');
    if (!row) return;
    row.innerHTML = '';

    KPI_DEFS.forEach(([sec, sid, label, tvSymbol, region, calKey]) => {
      const series = sectionData[sec]?.series?.[sid];
      const tile = document.createElement('div');
      tile.className = 'kpi-tile' + (series ? '' : ' is-empty');
      tile.dataset.calKey = calKey || '';

      if (!series) {
        tile.innerHTML = `
          <div class="kpi-label">${label}<span class="kpi-region">${region}</span></div>
          <div class="kpi-row-vals"><span class="kpi-value">——</span></div>
          <div class="kpi-change">no data</div>
          <div class="kpi-spark"></div>
          <div class="kpi-countdown"><span class="cd-label">NEXT</span><span class="cd-val">—</span></div>`;
        row.appendChild(tile);
        return;
      }

      const stats = series.stats || {};
      const val = global.ChartKit.formatNumber(stats.last_value, series.unit);
      const chg = stats.chg_1y_pct;
      let chgHTML;
      if (chg == null) {
        chgHTML = '<span class="kpi-change zero">——</span>';
      } else {
        const cls = chg > 0 ? 'up' : chg < 0 ? 'down' : '';
        const arrow = chg > 0 ? '▲' : chg < 0 ? '▼' : '·';
        const ngcls = chg < 0 ? 'neg' : '';
        chgHTML = `<span class="kpi-change ${ngcls}"><span class="kpi-arrow ${cls}">${arrow}</span>${Math.abs(chg).toFixed(2)}% 1Y</span>`;
      }

      tile.innerHTML = `
        <div class="kpi-label">${label}<span class="kpi-region">${region}</span></div>
        <div class="kpi-row-vals">
          <span class="kpi-value">${val}</span>
          <span class="kpi-unit">${series.unit || ''}</span>
        </div>
        ${chgHTML}
        <div class="kpi-spark"></div>
        <div class="kpi-countdown" data-cal-key="${calKey || ''}">
          <span class="cd-label">NEXT</span>
          <span class="cd-val">—</span>
        </div>
      `;
      tile.title = series.note || series.name;

      if (tvSymbol) {
        tile.addEventListener('click', () => {
          const sel = document.getElementById('hero-symbol');
          if (sel) {
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
          document.querySelector('.hero-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
      } else {
        tile.addEventListener('click', () => {
          if (global.Hero) global.Hero.loadLocal(sec, sid, series);
          document.querySelector('.hero-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
      }

      row.appendChild(tile);
      const spark = tile.querySelector('.kpi-spark');
      global.ChartKit.createSparkline(spark, series, { range: '1Y' });
    });

    wireScroll();
    refreshCountdowns();
    setInterval(refreshCountdowns, 60_000);  // tick every minute
  }

  function wireScroll() {
    const row = document.getElementById('kpi-row');
    const l = document.getElementById('kpi-scroll-l');
    const r = document.getElementById('kpi-scroll-r');
    if (!row) return;
    const step = () => Math.max(200, row.clientWidth * 0.7);
    l?.addEventListener('click', () => row.scrollBy({ left: -step(), behavior: 'smooth' }));
    r?.addEventListener('click', () => row.scrollBy({ left:  step(), behavior: 'smooth' }));
    const updateBtns = () => {
      const max = row.scrollWidth - row.clientWidth;
      if (l) l.disabled = row.scrollLeft <= 2;
      if (r) r.disabled = row.scrollLeft >= max - 2;
    };
    row.addEventListener('scroll', updateBtns);
    setTimeout(updateBtns, 100);
    window.addEventListener('resize', updateBtns);
  }

  function refreshCountdowns() {
    const now = Date.now();
    document.querySelectorAll('.kpi-countdown').forEach(cd => {
      const key = cd.dataset.calKey;
      if (!key) { cd.innerHTML = '<span class="cd-label">NEXT</span><span class="cd-val">market-hours</span>'; return; }
      const next = calendarEvents
        .filter(e => e.key === key && new Date(e.datetime).getTime() > now)
        .sort((a, b) => a.datetime.localeCompare(b.datetime))[0];
      if (!next) { cd.innerHTML = '<span class="cd-label">NEXT</span><span class="cd-val">tbd</span>'; return; }

      const t = new Date(next.datetime).getTime();
      const diffMs = t - now;
      const days = Math.floor(diffMs / 86_400_000);
      const hours = Math.floor((diffMs % 86_400_000) / 3_600_000);
      const mins  = Math.floor((diffMs % 3_600_000) / 60_000);
      let label;
      if (diffMs < 60_000) label = 'imminent';
      else if (days >= 1)  label = `${days}d ${String(hours).padStart(2,'0')}h ${String(mins).padStart(2,'0')}m`;
      else                 label = `${String(hours).padStart(2,'0')}h ${String(mins).padStart(2,'0')}m`;
      cd.classList.toggle('is-imminent', diffMs < 24 * 3_600_000);
      const localStr = new Date(next.datetime).toLocaleString('en-GB', {
        weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
      });
      cd.innerHTML = `
        <span class="cd-label">NEXT</span>
        <span class="cd-val" title="${escapeHtml(next.title)} · ${localStr}">${label}</span>
      `;
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  global.KPI = { init };
})(window);
