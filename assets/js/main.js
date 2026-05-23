/**
 * main.js — MACRO//OPS dashboard orchestrator.
 *
 *   1. Pulls the manifest, builds section nav + section accordions.
 *   2. Lazy-loads each section's JSON when first expanded.
 *   3. Builds KPI strip + situation-report narrative from headline series.
 *   4. Wires expand/collapse all, events drawer, and section nav scroll.
 */
(function () {
  'use strict';

  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // Sections expanded by default. All others collapse on load.
  const DEFAULT_OPEN = new Set(['markets', 'bonds', 'rates']);

  // KPI strip headline series. [sectionKey, seriesId, label, optional unit override]
  const KPI_CONFIG = [
    ['markets',     'sp500',      'S&P 500'],
    ['markets',     'ftse100',    'FTSE 100'],
    ['bonds',       'us_10y',     'US 10Y'],
    ['bonds',       'uk_10y',     'UK 10Y'],
    ['rates',       'fed_funds',  'FED RATE'],
    ['rates',       'boe_rate',   'BOE RATE'],
    ['inflation',   'us_cpi_yoy', 'US CPI'],
    ['inflation',   'uk_cpi_yoy', 'UK CPI'],
    ['commodities', 'oil_brent',  'BRENT'],
    ['commodities', 'gold',       'GOLD'],
    ['fx',          'gbp_usd',    'GBP/USD'],
    ['fx',          'dxy',        'DXY'],
  ];

  const state = {
    manifest: null,
    sectionData: {},            // key -> JSON payload
    cardCharts: new Map(),      // cardEl -> ChartKit handle
    events: null,
  };

  // ━━━━━━━━━━━━━━━━━━━━━━━━ INIT ━━━━━━━━━━━━━━━━━━━━━━━━
  document.addEventListener('DOMContentLoaded', init);

  async function init() {
    wireTopbar();

    state.manifest = await DataLoader.manifest();
    if (!state.manifest) {
      renderManifestError();
      hideBootScreen();
      return;
    }

    renderLastUpdate(state.manifest.generated_at);
    renderSectionNav(state.manifest);
    renderSections(state.manifest);

    // Preload the sections that drive KPIs + the situation report.
    const kpiSections = Array.from(new Set(KPI_CONFIG.map((c) => c[0])));
    const preloaded = await DataLoader.preload(kpiSections);
    Object.assign(state.sectionData, preloaded);

    renderKPIStrip();
    renderNarrative();

    // Expand default sections (this also fetches+renders their cards).
    DEFAULT_OPEN.forEach(openSection);

    // Scroll-spy: highlight nav chip for the section in view.
    setupScrollSpy();

    hideBootScreen();
  }

  // ━━━━━━━━━━━━━━━━━━━━━━━━ BOOT ━━━━━━━━━━━━━━━━━━━━━━━━
  function hideBootScreen() {
    const boot = $('#boot-screen');
    setTimeout(() => {
      boot.classList.add('is-hidden');
      setTimeout(() => boot.remove(), 500);
    }, 700);
  }

  function renderManifestError() {
    const container = $('#sections-container');
    container.innerHTML = `
      <div style="padding:60px 20px;text-align:center;color:var(--tx-2);font-family:var(--ff-mono);">
        <div style="font-size:13px;color:var(--ac-amber);letter-spacing:0.2em;margin-bottom:12px;">
          ⚠  CHANNEL OFFLINE
        </div>
        <div style="font-size:13px;line-height:1.7;">
          data/manifest.json not found.<br/>
          Run <code style="color:var(--ac-cyan);">python scripts/fetch_data.py</code> locally
          or trigger the GitHub Action.
        </div>
      </div>`;
  }

  function renderLastUpdate(iso) {
    const el = $('#last-update');
    if (!iso) { el.textContent = '——'; return; }
    const d = new Date(iso);
    const now = Date.now();
    const ageHr = (now - d.getTime()) / 3600000;
    el.textContent = d.toISOString().slice(0, 16).replace('T', ' ') + 'Z';
    const status = $('#live-status');
    if (ageHr > 36) {
      status.classList.add('is-stale');
      status.querySelector('.status-label').textContent = 'STALE';
    }
  }

  // ━━━━━━━━━━━━━━━━━━━━━━━━ NAV ━━━━━━━━━━━━━━━━━━━━━━━━
  function renderSectionNav(manifest) {
    const nav = $('#section-nav');
    nav.innerHTML = '';
    Object.entries(manifest.sections).forEach(([key, meta]) => {
      const chip = document.createElement('button');
      chip.className = 'nav-chip';
      chip.dataset.target = key;
      chip.innerHTML = `<span>${meta.title}</span><span style="opacity:.5;font-size:9px;margin-left:2px;">${meta.series_count}</span>`;
      chip.addEventListener('click', () => {
        openSection(key);
        const target = $(`section[data-section-key="${key}"]`);
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      nav.appendChild(chip);
    });
  }

  // ━━━━━━━━━━━━━━━━━━━━━━━━ SECTIONS ━━━━━━━━━━━━━━━━━━━━━━━━
  function renderSections(manifest) {
    const container = $('#sections-container');
    const tpl = $('#tpl-section');
    container.innerHTML = '';

    Object.entries(manifest.sections).forEach(([key, meta]) => {
      const frag = tpl.content.cloneNode(true);
      const sectionEl = frag.querySelector('.section');
      sectionEl.dataset.sectionKey = key;
      sectionEl.classList.add('is-collapsed');

      sectionEl.querySelector('.section-icon').textContent = iconFor(meta.icon);
      sectionEl.querySelector('.section-title').textContent = meta.title;
      sectionEl.querySelector('.section-blurb').textContent = meta.blurb;
      sectionEl.querySelector('.section-count').textContent = `${meta.series_count} series`;

      sectionEl.querySelector('.section-head').addEventListener('click', () => {
        if (sectionEl.classList.contains('is-collapsed')) openSection(key);
        else closeSection(key);
      });

      container.appendChild(frag);
    });
  }

  async function openSection(key) {
    const sectionEl = $(`section[data-section-key="${key}"]`);
    if (!sectionEl) return;
    sectionEl.classList.remove('is-collapsed');

    const grid = sectionEl.querySelector('.cards-grid');
    if (grid.dataset.populated) {
      // already rendered; just resize charts on next paint
      Promise.resolve().then(() => {
        $$('.card', sectionEl).forEach((card) => {
          const h = state.cardCharts.get(card);
          if (h) h.resize();
        });
      });
      return;
    }

    // Fetch + render
    if (!state.sectionData[key]) {
      state.sectionData[key] = await DataLoader.section(key);
    }
    const payload = state.sectionData[key];
    if (!payload) {
      grid.innerHTML = `<div style="padding:18px;color:var(--tx-3);font-family:var(--ff-mono);font-size:12px;">No data loaded yet — run the fetcher.</div>`;
      grid.dataset.populated = '1';
      return;
    }

    const order = payload.order || Object.keys(payload.series);
    order.forEach((sid) => {
      const series = payload.series[sid];
      if (!series) return;
      const card = buildCard(series);
      grid.appendChild(card);
      mountChart(card, series);
    });

    grid.dataset.populated = '1';
    // Update nav chip count if some failed
    if (payload.meta && payload.meta.fetched_fail > 0) {
      const chip = $(`.nav-chip[data-target="${key}"]`);
      if (chip) chip.title = `${payload.meta.fetched_ok} ok / ${payload.meta.fetched_fail} missing`;
    }
  }

  function closeSection(key) {
    const sectionEl = $(`section[data-section-key="${key}"]`);
    if (sectionEl) sectionEl.classList.add('is-collapsed');
  }

  function buildCard(series) {
    const tpl = $('#tpl-card');
    const frag = tpl.content.cloneNode(true);
    const card = frag.querySelector('.card');
    card.dataset.seriesId = series.id;

    card.querySelector('.region-badge').textContent = series.region || '—';
    card.querySelector('.card-title').textContent = series.name;

    const stats = series.stats || {};
    const lastVal = stats.last_value;
    card.querySelector('.value-num').textContent = ChartKit.formatNumber(lastVal, series.unit);
    card.querySelector('.value-unit').textContent = series.unit || '';

    const chg = stats.chg_1y_pct;
    const chgEl = card.querySelector('.value-change');
    if (chg === null || chg === undefined) {
      chgEl.textContent = '';
    } else {
      const cls = chg > 0 ? 'pos' : chg < 0 ? 'neg' : 'zero';
      chgEl.classList.add(cls);
      const arrow = chg > 0 ? '▲' : chg < 0 ? '▼' : '·';
      chgEl.textContent = `${arrow} ${Math.abs(chg).toFixed(2)}% 1Y`;
    }

    card.querySelector('.card-source').textContent = series.source || '';

    // Wire range buttons
    const rangeButtons = card.querySelectorAll('.range-buttons button');
    rangeButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        rangeButtons.forEach((b) => b.classList.remove('is-active'));
        btn.classList.add('is-active');
        const h = state.cardCharts.get(card);
        if (h) h.setRange(btn.dataset.range);
      });
    });

    return card;
  }

  /**
   * Mount the chart inside an already-DOM-attached card. Called by openSection
   * right after appendChild — synchronous so it works even when the tab is
   * backgrounded (rAF gets throttled in hidden tabs / preview iframes).
   */
  function mountChart(card, series) {
    const chartEl = card.querySelector('.card-chart');
    const handle = ChartKit.createCardChart(chartEl, series);
    if (handle) {
      state.cardCharts.set(card, handle);
    } else {
      card.classList.add('has-error');
    }
  }

  function iconFor(name) {
    const map = {
      trending_up: '↗',
      show_chart: '~',
      account_balance: '◭',
      local_fire_department: '✦',
      savings: '$',
      home: '⌂',
      oil_barrel: '◉',
      currency_exchange: '⇄',
      groups: '◯',
      factory: '◰',
      warning: '!',
    };
    return map[name] || '◆';
  }

  // ━━━━━━━━━━━━━━━━━━━━━━━━ KPI strip ━━━━━━━━━━━━━━━━━━━━━━━━
  function renderKPIStrip() {
    const strip = $('#kpi-strip');
    strip.innerHTML = '';

    KPI_CONFIG.forEach(([sectionKey, sid, label]) => {
      const payload = state.sectionData[sectionKey];
      const tile = document.createElement('div');
      tile.className = 'kpi-tile';
      const series = payload && payload.series && payload.series[sid];
      if (!series) {
        tile.classList.add('is-empty');
        tile.innerHTML = `
          <div class="label">${label}</div>
          <div class="value">——</div>
          <div class="change">no data</div>`;
        strip.appendChild(tile);
        return;
      }

      const stats = series.stats || {};
      const val = ChartKit.formatNumber(stats.last_value, series.unit);
      const chg = stats.chg_1y_pct;
      let chgHTML = '';
      if (chg !== null && chg !== undefined) {
        const cls = chg > 0 ? 'pos' : chg < 0 ? 'neg' : 'zero';
        const arrow = chg > 0 ? '▲' : chg < 0 ? '▼' : '·';
        chgHTML = `<div class="change ${cls}">${arrow} ${Math.abs(chg).toFixed(2)}% 1Y</div>`;
      }
      tile.innerHTML = `
        <div class="label">${label}</div>
        <div class="value">${val}<span style="font-size:10px;color:var(--tx-3);margin-left:4px;letter-spacing:.06em;">${series.unit || ''}</span></div>
        ${chgHTML}`;
      tile.style.cursor = 'pointer';
      tile.addEventListener('click', () => {
        openSection(sectionKey);
        const sectionEl = $(`section[data-section-key="${sectionKey}"]`);
        if (sectionEl) sectionEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      strip.appendChild(tile);
    });
  }

  // ━━━━━━━━━━━━━━━━━━━━━━━━ Narrative ━━━━━━━━━━━━━━━━━━━━━━━━
  function renderNarrative() {
    const el = $('#narrative-text');
    const lines = [];

    const get = (sec, sid) => (state.sectionData[sec]?.series?.[sid]);

    const sp = get('markets', 'sp500');
    const ftse = get('markets', 'ftse100');
    const us10 = get('bonds', 'us_10y');
    const uk10 = get('bonds', 'uk_10y');
    const curve = get('bonds', 'curve_10y2y');
    const fed = get('rates', 'fed_funds');
    const boe = get('rates', 'boe_rate');
    const uscpi = get('inflation', 'us_cpi_yoy');
    const ukcpi = get('inflation', 'uk_cpi_yoy');
    const brent = get('commodities', 'oil_brent');
    const gold = get('commodities', 'gold');
    const dxy = get('fx', 'dxy');
    const gbp = get('fx', 'gbp_usd');

    if (sp && sp.stats) {
      const c = sp.stats.chg_1y_pct;
      lines.push(`<strong>S&P 500</strong> ${dirWord(c)} <span class="${dirCls(c)}">${signed(c)}%</span> YoY`);
    }
    if (ftse && ftse.stats) {
      const c = ftse.stats.chg_1y_pct;
      lines.push(`<strong>FTSE 100</strong> ${dirWord(c)} <span class="${dirCls(c)}">${signed(c)}%</span>`);
    }
    if (us10 && us10.stats) {
      lines.push(`US 10Y yield at <strong>${us10.stats.last_value?.toFixed(2)}%</strong>`);
    }
    if (uk10 && uk10.stats) {
      lines.push(`UK 10Y gilt at <strong>${uk10.stats.last_value?.toFixed(2)}%</strong>`);
    }
    if (curve && curve.stats) {
      const v = curve.stats.last_value;
      const inv = v < 0 ? '<span class="down">inverted</span>' : 'normal';
      lines.push(`yield curve ${inv} (${v.toFixed(0)} bps)`);
    }
    if (fed && fed.stats) {
      lines.push(`Fed Funds <strong>${fed.stats.last_value.toFixed(2)}%</strong>`);
    }
    if (boe && boe.stats) {
      lines.push(`BoE <strong>${boe.stats.last_value.toFixed(2)}%</strong>`);
    }
    if (uscpi && uscpi.stats) {
      const v = uscpi.stats.last_value;
      const hot = v > 3 ? '<span class="down">above target</span>' : v < 2 ? '<span class="up">below target</span>' : 'near target';
      lines.push(`US CPI <strong>${v.toFixed(1)}%</strong> (${hot})`);
    }
    if (ukcpi && ukcpi.stats) {
      const v = ukcpi.stats.last_value;
      lines.push(`UK CPI <strong>${v.toFixed(1)}%</strong>`);
    }
    if (brent && brent.stats) {
      lines.push(`Brent crude <strong>$${brent.stats.last_value.toFixed(2)}</strong>`);
    }
    if (gold && gold.stats) {
      lines.push(`Gold <strong>$${gold.stats.last_value.toFixed(0)}/oz</strong>`);
    }
    if (gbp && gbp.stats) {
      lines.push(`GBP/USD <strong>${gbp.stats.last_value.toFixed(4)}</strong>`);
    }
    if (dxy && dxy.stats) {
      const c = dxy.stats.chg_1y_pct;
      lines.push(`Dollar index ${dirWord(c)} ${signed(c)}% YoY`);
    }

    el.innerHTML = lines.length
      ? lines.join(' &nbsp;·&nbsp; ')
      : 'Run the fetcher to populate this report.';
  }

  function signed(v)  { return v == null ? '—' : (v >= 0 ? '+' : '') + v.toFixed(2); }
  function dirWord(v) {
    if (v == null) return '';
    return v > 0 ? '<span class="up">up</span>' : v < 0 ? '<span class="down">down</span>' : 'flat';
  }
  function dirCls(v)  { return v == null ? '' : v > 0 ? 'up' : v < 0 ? 'down' : ''; }

  // ━━━━━━━━━━━━━━━━━━━━━━━━ TOPBAR / EVENTS ━━━━━━━━━━━━━━━━━━━━━━━━
  function wireTopbar() {
    $('#btn-collapse-all').addEventListener('click', () => {
      $$('.section').forEach((s) => s.classList.add('is-collapsed'));
    });
    $('#btn-expand-all').addEventListener('click', async () => {
      const keys = $$('.section').map((s) => s.dataset.sectionKey);
      for (const k of keys) await openSection(k);
    });
    $('#btn-events').addEventListener('click', openEvents);
    $('#btn-close-events').addEventListener('click', closeEvents);
    $('#drawer-scrim').addEventListener('click', closeEvents);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeEvents(); });
  }

  async function openEvents() {
    if (!state.events) state.events = await DataLoader.events();
    if (!state.events) return;
    renderEvents(state.events.events);
    $('#events-drawer').classList.add('is-open');
    $('#drawer-scrim').hidden = false;
  }

  function closeEvents() {
    $('#events-drawer').classList.remove('is-open');
    $('#drawer-scrim').hidden = true;
  }

  function renderEvents(events) {
    const list = $('#events-list');
    list.innerHTML = '';
    // newest first
    [...events].reverse().forEach((e) => {
      const row = document.createElement('div');
      row.className = 'event-row';
      row.innerHTML = `
        <span class="event-dot tag-${e.tag}"></span>
        <div class="event-date">${e.date}</div>
        <div class="event-title">${e.title}</div>
        <div class="event-blurb">${e.blurb}</div>
        <span class="event-tag">${e.tag}</span>`;
      list.appendChild(row);
    });
  }

  // ━━━━━━━━━━━━━━━━━━━━━━━━ SCROLL SPY ━━━━━━━━━━━━━━━━━━━━━━━━
  function setupScrollSpy() {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const key = entry.target.dataset.sectionKey;
            $$('.nav-chip').forEach((c) => {
              c.classList.toggle('is-active', c.dataset.target === key);
            });
          }
        });
      },
      { rootMargin: '-40% 0% -55% 0%', threshold: 0 }
    );
    $$('.section').forEach((s) => observer.observe(s));
  }
})();
