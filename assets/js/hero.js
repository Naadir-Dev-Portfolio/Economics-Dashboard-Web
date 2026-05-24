/**
 * hero.js — the big chart panel.
 *
 * Two render modes:
 *   1. LIVE     → TradingView Advanced Chart widget (intraday candles, real-time)
 *   2. ARCHIVE  → ECharts line/area from local series, supports event annotations
 *
 * Annotations come from the Events panel. When the user checks an event, we:
 *   - flip the hero into ARCHIVE mode (if currently LIVE)
 *   - add a vertical line + label at the event's date
 *   - register an "annotation chip" in the hero foot which the user can click to remove
 */
(function (global) {
  'use strict';

  const TV_SYMBOL_TO_LOCAL = {
    'FOREXCOM:SPXUSD':  ['markets', 'sp500'],
    'OANDA:NAS100USD':  ['markets', 'nasdaq'],
    'OANDA:UK100GBP':   ['markets', 'ftse100'],
    'OANDA:DE30EUR':    ['markets', 'dax'],
    'OANDA:JP225USD':   ['markets', 'nikkei'],
    'OANDA:HK33HKD':    ['markets', 'hangseng'],
    'FOREXCOM:DJI':     ['markets', 'dow'],
    'TVC:US10Y':        ['bonds', 'us_10y'],
    'TVC:US02Y':        ['bonds', 'us_2y'],
    'TVC:GB10Y':        ['bonds', 'uk_10y'],
    'TVC:DE10Y':        ['bonds', 'de_10y'],
    'TVC:JP10Y':        ['bonds', 'jp_10y'],
    'TVC:UKOIL':        ['commodities', 'oil_brent'],
    'TVC:USOIL':        ['commodities', 'oil_wti'],
    'TVC:GOLD':         ['commodities', 'gold'],
    'TVC:SILVER':       ['commodities', 'silver'],
    'TVC:NATURALGAS':   ['commodities', 'natgas'],
    'COMEX:HG1!':       ['commodities', 'copper'],
    'FX:GBPUSD':        ['fx', 'gbp_usd'],
    'FX:EURUSD':        ['fx', 'eur_usd'],
    'FX:USDJPY':        ['fx', 'usd_jpy'],
    'TVC:DXY':          ['fx', 'dxy'],
    'BITSTAMP:BTCUSD':  ['fx', 'btc_usd'],
    'TVC:VIX':          ['risk', 'vix'],
  };

  const REGION_TO_SYMBOL = {
    GLOBAL: 'FOREXCOM:SPXUSD',
    US:     'FOREXCOM:SPXUSD',
    UK:     'OANDA:UK100GBP',
    EU:     'OANDA:DE30EUR',
    ASIA:   'OANDA:JP225USD',
  };

  const state = {
    mode: 'live',           // 'live' | 'archive'
    symbol: 'FOREXCOM:SPXUSD',
    tvWidget: null,
    archiveChart: null,
    annotations: [],        // [{id, ts, title, blurb, tag}]
    currentSeries: null,
    sectionData: null,      // injected by main.js
  };

  // ─────────────────────────────────────────────────────────────────
  function ensureTradingView(symbol) {
    const container = document.getElementById('hero-chart');
    if (!container) return;
    container.innerHTML = '';
    const div = document.createElement('div');
    div.id = 'tv_widget_' + Date.now();
    div.style.width = '100%';
    div.style.height = '100%';
    container.appendChild(div);

    if (!global.TradingView) {
      container.innerHTML = '<div style="padding:40px;color:#6e6e6e;font-family:monospace;font-size:12px;">TradingView script failed to load.</div>';
      return;
    }
    state.tvWidget = new global.TradingView.widget({
      width: '100%',
      height: '100%',
      symbol,
      interval: 'D',
      timezone: 'Etc/UTC',
      theme: 'dark',
      style: '1',         // candles
      locale: 'en',
      toolbar_bg: '#000000',
      enable_publishing: false,
      hide_side_toolbar: false,
      hide_top_toolbar: false,
      allow_symbol_change: true,
      withdateranges: true,
      details: false,
      hotlist: false,
      calendar: false,
      studies: [],
      container_id: div.id,
      autosize: true,
      backgroundColor: '#000000',
      gridColor: 'rgba(36, 36, 36, 1)',
    });
  }

  function renderArchive() {
    const container = document.getElementById('hero-chart');
    if (!container) return;
    container.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.style.cssText = 'width:100%;height:100%;position:relative;';
    container.appendChild(wrap);

    if (!state.currentSeries) {
      wrap.innerHTML = '<div style="padding:40px;color:#6e6e6e;font-family:monospace;font-size:12px;text-align:center;">No archive series for this symbol.<br/>Switch to LIVE for real-time data.</div>';
      return;
    }
    state.archiveChart = global.ChartKit.createCardChart(wrap, state.currentSeries, {
      range: 'MAX',
      annotations: state.annotations,
    });
  }

  // ─────────────────────────────────────────────────────────────────
  function setSymbol(symbol) {
    state.symbol = symbol;
    // Try to find the local series for archive overlay (and quote in header)
    const localRef = TV_SYMBOL_TO_LOCAL[symbol];
    if (localRef && state.sectionData) {
      const [section, sid] = localRef;
      const series = state.sectionData[section]?.series?.[sid];
      state.currentSeries = series || null;
      updateHeroQuote(series);
    } else {
      state.currentSeries = null;
      updateHeroQuote(null);
    }
    render();
  }

  function updateHeroQuote(series) {
    const nameEl   = document.getElementById('hero-name');
    const valueEl  = document.getElementById('hero-value');
    const changeEl = document.getElementById('hero-change');
    if (!series || !series.stats) {
      if (nameEl) nameEl.textContent = '—';
      if (valueEl) valueEl.textContent = '—';
      if (changeEl) { changeEl.textContent = ''; changeEl.className = 'hero-change'; }
      return;
    }
    nameEl.textContent = series.name;
    valueEl.textContent = global.ChartKit.formatNumber(series.stats.last_value, series.unit);
    const chg = series.stats.chg_1y_pct;
    if (chg == null) {
      changeEl.textContent = '';
      changeEl.className = 'hero-change';
      return;
    }
    const cls = chg > 0 ? 'pos' : chg < 0 ? 'neg' : 'zero';
    const arrow = chg > 0 ? '▲' : chg < 0 ? '▼' : '·';
    changeEl.textContent = `${arrow} ${Math.abs(chg).toFixed(2)}% 1Y`;
    changeEl.className = `hero-change ${cls}`;
  }

  function setMode(mode) {
    state.mode = mode;
    const btn = document.getElementById('hero-tv-toggle');
    if (btn) {
      btn.innerHTML = mode === 'live'
        ? '<span class="dot dot-pulse"></span> LIVE'
        : '<span class="dot"></span> ARCHIVE';
    }
    render();
  }

  function render() {
    if (state.mode === 'live') {
      ensureTradingView(state.symbol);
      // Annotations not supported on TradingView widget → hidden by default
      document.getElementById('hero-annotations').hidden = state.annotations.length === 0;
    } else {
      renderArchive();
      document.getElementById('hero-annotations').hidden = state.annotations.length === 0;
    }
    renderAnnotationChips();
  }

  function renderAnnotationChips() {
    const annBox = document.getElementById('hero-annotations');
    const list = document.getElementById('ann-list');
    if (!annBox || !list) return;
    list.innerHTML = '';
    if (!state.annotations.length) { annBox.hidden = true; return; }
    annBox.hidden = false;
    state.annotations.forEach(a => {
      const chip = document.createElement('span');
      chip.className = 'ann-chip';
      chip.innerHTML = `${a.date} · ${escapeHtml(a.title)}<span class="x">✕</span>`;
      chip.addEventListener('click', () => removeAnnotation(a.id));
      list.appendChild(chip);
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  // Public annotation API
  function addAnnotation(event) {
    const id = event.id || event.date + ':' + event.title;
    if (state.annotations.find(a => a.id === id)) return;
    const ts = new Date(event.date).getTime();
    state.annotations.push({
      id,
      ts,
      date: event.date,
      title: event.title,
      blurb: event.blurb,
      tag: event.tag,
      label: event.title.length > 30 ? event.title.slice(0, 28) + '…' : event.title,
    });
    // Flip to archive view so annotations are visible
    if (state.mode !== 'archive') setMode('archive');
    else render();
  }
  function removeAnnotation(id) {
    state.annotations = state.annotations.filter(a => a.id !== id);
    // Inform events timeline so the checkbox uncchecks
    if (global.EventsTimeline) global.EventsTimeline.notifyRemoved(id);
    render();
  }
  function clearAnnotations() {
    state.annotations = [];
    if (global.EventsTimeline) global.EventsTimeline.notifyCleared();
    render();
  }
  function hasAnnotation(id) {
    return !!state.annotations.find(a => a.id === id);
  }

  function init(sectionData) {
    state.sectionData = sectionData;

    // Symbol dropdown
    const sym = document.getElementById('hero-symbol');
    if (sym) {
      sym.addEventListener('change', () => setSymbol(sym.value));
    }

    // Live/Archive toggle
    const tvToggle = document.getElementById('hero-tv-toggle');
    if (tvToggle) {
      tvToggle.addEventListener('click', () => setMode(state.mode === 'live' ? 'archive' : 'live'));
    }

    // Set initial
    setSymbol(state.symbol);
  }

  function setRegion(region) {
    const symbol = REGION_TO_SYMBOL[region];
    if (!symbol) return;
    const sym = document.getElementById('hero-symbol');
    if (sym) sym.value = symbol;
    setSymbol(symbol);
  }

  global.Hero = {
    init,
    setSymbol,
    setMode,
    setRegion,
    addAnnotation,
    removeAnnotation,
    clearAnnotations,
    hasAnnotation,
  };
})(window);
