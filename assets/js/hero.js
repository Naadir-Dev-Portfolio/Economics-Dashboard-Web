/** Hero selection is always an exact section/series identity. */
(function (global) {
  'use strict';
  const LOCAL_TO_TV = {
    'markets/sp500': 'SP:SPX', 'markets/dow': 'DJ:DJI', 'markets/nasdaq': 'NASDAQ:IXIC',
    'markets/russell': 'TVC:RUT', 'markets/ftse100': 'TVC:UKX', 'markets/ftse250': 'TVC:MCX',
    'markets/dax': 'XETR:DAX', 'markets/cac40': 'EURONEXT:PX1', 'markets/stoxx50': 'TVC:SX5E',
    'markets/nikkei': 'TVC:NI225', 'markets/hangseng': 'HSI:HSI', 'markets/shcomp': 'SSE:000001',
    'markets/asx200': 'ASX:XJO', 'markets/sensex': 'BSE:SENSEX', 'markets/tsx': 'TSX:TSX',
    'bonds/us_2y': 'TVC:US02Y', 'bonds/us_5y': 'TVC:US05Y', 'bonds/us_10y': 'TVC:US10Y',
    'bonds/us_30y': 'TVC:US30Y', 'bonds/uk_10y': 'TVC:GB10Y', 'bonds/de_10y': 'TVC:DE10Y',
    'bonds/fr_10y': 'TVC:FR10Y', 'bonds/it_10y': 'TVC:IT10Y', 'bonds/jp_10y': 'TVC:JP10Y',
    'commodities/oil_brent': 'NYMEX:BZ1!', 'commodities/oil_wti': 'NYMEX:CL1!',
    'commodities/natgas': 'NYMEX:NG1!', 'commodities/gold': 'COMEX:GC1!',
    'commodities/silver': 'COMEX:SI1!', 'commodities/copper': 'COMEX:HG1!',
    'fx/gbp_usd': 'FX:GBPUSD', 'fx/eur_usd': 'FX:EURUSD', 'fx/usd_jpy': 'FX:USDJPY',
    'fx/usd_chf': 'FX:USDCHF', 'fx/aud_usd': 'FX:AUDUSD', 'fx/usd_cad': 'FX:USDCAD',
    'fx/dxy': 'TVC:DXY', 'fx/btc_usd': 'COINBASE:BTCUSD', 'fx/eth_usd': 'COINBASE:ETHUSD',
    'fx/sol_usd': 'COINBASE:SOLUSD', 'fx/xrp_usd': 'COINBASE:XRPUSD', 'fx/atom_usd': 'COINBASE:ATOMUSD',
    'risk/vix': 'TVC:VIX', 'risk/move_index': 'TVC:MOVE',
  };
  const REGIONS = { GLOBAL: ['markets', 'sp500'], US: ['markets', 'sp500'], UK: ['markets', 'ftse100'], EU: ['markets', 'dax'], ASIA: ['markets', 'nikkei'] };
  const state = { mode: 'archive', key: '', symbol: null, series: null, data: {}, chart: null, widget: null, annotations: [], range: '5Y' };
  const indicators = { rsi: false, fast: false, slow: false };
  const INDICATORS = { rsi: ['RSI 14', 15], fast: ['SMA 20', 20], slow: ['SMA 50', 50] };
  const $ = id => document.getElementById(id);
  const iso = ts => new Date(ts).toISOString().slice(0, 10);

  function disposeChart() {
    state.chart?.dispose();
    state.chart = null;
    if (state.widget) global.HealthPanel?.setRuntimeStatus('tradingview', 'inactive', { message: 'Live chart closed' });
    try { state.widget?.remove?.(); } catch (_) { /* Third-party widget may already be removed. */ }
    state.widget = null;
    $('hero-chart').replaceChildren();
  }

  function syncDates(view) {
    if (!view) return;
    $('hero-date-from').value = iso(view[0]);
    $('hero-date-to').value = iso(view[1]);
    $('hero-date-from').setCustomValidity('');
    $('hero-date-to').setCustomValidity('');
  }

  function syncRangeButtons(active) {
    document.querySelectorAll('[data-hero-range]').forEach(button => {
      const selected = button.dataset.heroRange === active;
      button.classList.toggle('is-active', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
  }

  function render() {
    disposeChart();
    const archive = state.mode === 'archive';
    $('hero-mode-archive').disabled = !state.series;
    $('hero-mode-live').disabled = !state.symbol;
    for (const mode of ['archive', 'live']) {
      $('hero-mode-' + mode).classList.toggle('is-active', state.mode === mode);
      $('hero-mode-' + mode).setAttribute('aria-pressed', String(state.mode === mode));
    }
    $('hero-tools').hidden = !archive || !state.series;
    $('hero-open-tv').hidden = !state.symbol;
    if (state.symbol) $('hero-open-tv').href = 'https://www.tradingview.com/chart/?symbol=' + encodeURIComponent(state.symbol);
    const series = state.series;
    $('hero-name').textContent = series?.name || state.symbol || 'No data';
    $('hero-value').textContent = archive && series ? global.ChartKit.formatNumber(series.stats.last_value, series.unit) + ' ' + (series.unit || '') : '';
    $('hero-asof').textContent = archive && series ? global.ChartKit.observationLabel(series) : state.symbol || '';
    const change = series ? global.ChartKit.annualChange(series) : {};
    const changeEl = $('hero-change');
    changeEl.textContent = archive && change.value != null ? (change.value > 0 ? '+' : '') + change.value.toFixed(2) + ' ' + change.unit + ' 1Y' : '';
    changeEl.className = 'hero-change ' + (change.value < 0 ? 'neg' : 'pos');
    const source = $('hero-source');
    source.textContent = archive && series ? global.ChartKit.sourceSummary(series) : 'TradingView market feed';
    source.classList.toggle('is-warning', !!series && archive && !!global.ChartKit.freshnessState(series));
    source.title = series?.note || '';
    $('hero-chart').dataset.seriesKey = state.key;
    $('hero-chart').dataset.mode = state.mode;
    syncIndicators();

    if (archive && series) {
      const data = series.data;
      for (const input of [$('hero-date-from'), $('hero-date-to')]) {
        input.min = iso(data[0][0]);
        input.max = iso(data[data.length - 1][0]);
      }
      state.chart = global.ChartKit.createCardChart($('hero-chart'), series, {
        range: state.range, annotations: state.annotations, fineZoom: true, indicators,
        onZoom(view) { syncDates(view); syncRangeButtons(null); },
      });
      if (!state.chart) $('hero-chart').textContent = 'Chart renderer unavailable.';
      syncDates(state.chart?.getView());
      syncRangeButtons(state.range);
    } else if (state.symbol) {
      renderTradingView();
    }
    renderAnnotations();
  }

  function renderTradingView() {
    const container = $('hero-chart');
    if (!global.TradingView?.widget) {
      container.innerHTML = '<div class="chart-empty">TradingView is unavailable.</div>';
      global.HealthPanel?.setRuntimeStatus('tradingview', false);
      return;
    }
    const mount = document.createElement('div');
    mount.id = 'tv-hero-' + Date.now();
    mount.style.cssText = 'position:absolute;inset:0;width:100%;height:100%';
    container.appendChild(mount);
    try {
      state.widget = new global.TradingView.widget({
        container_id: mount.id, autosize: true, symbol: state.symbol, interval: 'D',
        timezone: 'Etc/UTC', theme: 'dark', style: '1', locale: 'en',
        enable_publishing: false, hide_side_toolbar: false, allow_symbol_change: false,
        withdateranges: true, backgroundColor: '#000000', gridColor: '#242424',
      });
      global.HealthPanel?.setRuntimeStatus('tradingview', 'embedded');
    } catch (_) {
      container.innerHTML = '<div class="chart-empty">TradingView is unavailable.</div>';
      global.HealthPanel?.setRuntimeStatus('tradingview', false);
    }
  }

  function loadLocal(section, sid, series) {
    const selected = series || state.data[section]?.series?.[sid];
    if (!selected?.data?.length) return;
    state.key = section + '/' + sid;
    state.series = selected;
    state.symbol = LOCAL_TO_TV[state.key] || null;
    state.mode = 'archive';
    state.range = '5Y';
    $('hero-symbol').value = state.key;
    render();
  }

  function setSymbol(symbol, label) {
    const match = Object.entries(LOCAL_TO_TV).find(([, tv]) => tv === symbol);
    if (match) {
      const [section, sid] = match[0].split('/');
      loadLocal(section, sid);
      setMode('live');
      return;
    }
    state.key = 'tv:' + symbol;
    state.symbol = symbol;
    state.series = null;
    state.mode = 'live';
    const select = $('hero-symbol');
    if (!Array.from(select.options).some(o => o.value === state.key)) select.add(new Option(label || symbol, state.key));
    select.value = state.key;
    render();
  }

  function setMode(mode) {
    if ((mode === 'archive' && !state.series) || (mode === 'live' && !state.symbol)) return;
    state.mode = mode;
    render();
  }

  function setRange(range) {
    state.range = range;
    state.chart?.setRange(range);
    syncRangeButtons(range);
  }

  function syncIndicators() {
    document.querySelectorAll('[data-indicator]').forEach(button => {
      const key = button.dataset.indicator;
      const [name, minimum] = INDICATORS[key];
      const available = !!global.SMA && !!global.RSI && state.series?.data?.length >= minimum;
      button.disabled = !available;
      button.setAttribute('aria-pressed', String(indicators[key]));
      button.classList.toggle('is-active', indicators[key]);
      const frequency = global.ChartKit.FREQUENCIES[state.series?.frequency]?.toLowerCase() || 'native-frequency';
      button.title = available ? name + ' (' + frequency + ' observations)' : name + ': needs at least ' + minimum + ' observations';
    });
    $('hero-chart').classList.toggle('has-rsi', state.mode === 'archive' && indicators.rsi && state.series?.data?.length >= 15);
  }

  function renderAnnotations() {
    $('hero-annotations').hidden = state.mode !== 'archive' || !state.annotations.length;
    $('ann-list').replaceChildren();
    state.annotations.forEach(annotation => {
      const chip = document.createElement('button');
      chip.className = 'ann-chip';
      chip.textContent = annotation.date + ' \u00b7 ' + annotation.title + ' \u00d7';
      chip.title = 'Remove annotation';
      chip.addEventListener('click', () => removeAnnotation(annotation.id));
      $('ann-list').appendChild(chip);
    });
  }

  function addAnnotation(event) {
    if (!state.series) return;
    const id = event.id || event.date + ':' + event.title;
    if (state.annotations.some(a => a.id === id)) return;
    state.annotations.push({ ...event, id, ts: Date.parse(event.date), label: event.title.slice(0, 36) });
    if (state.mode !== 'archive') setMode('archive');
    else { state.chart?.setAnnotations(state.annotations); renderAnnotations(); }
  }

  function removeAnnotation(id) {
    state.annotations = state.annotations.filter(a => a.id !== id);
    global.EventsTimeline?.notifyRemoved(id);
    state.chart?.setAnnotations(state.annotations);
    renderAnnotations();
  }

  function clearAnnotations() {
    state.annotations = [];
    global.EventsTimeline?.notifyCleared();
    state.chart?.setAnnotations([]);
    renderAnnotations();
  }

  function init(sectionData) {
    state.data = sectionData;
    try {
      const saved = JSON.parse(localStorage.getItem('heroIndicators') || '{}');
      Object.keys(indicators).forEach(key => { indicators[key] = saved?.[key] === true; });
    } catch (_) { /* Use defaults when storage is unavailable. */ }
    const select = $('hero-symbol');
    select.replaceChildren();
    Object.entries(sectionData).forEach(([section, payload]) => {
      if (!payload?.series) return;
      const group = document.createElement('optgroup');
      group.label = payload.meta?.title || section;
      (payload.order || Object.keys(payload.series)).forEach(sid => {
        const series = payload.series[sid];
        if (series) group.appendChild(new Option(series.name, section + '/' + sid));
      });
      select.appendChild(group);
    });
    select.addEventListener('change', () => {
      if (select.value.startsWith('tv:')) setSymbol(select.value.slice(3));
      else loadLocal(...select.value.split('/'));
    });
    $('hero-mode-archive').addEventListener('click', () => setMode('archive'));
    $('hero-mode-live').addEventListener('click', () => setMode('live'));
    document.querySelectorAll('[data-hero-range]').forEach(button => button.addEventListener('click', () => setRange(button.dataset.heroRange)));
    $('hero-reset').addEventListener('click', () => setRange('MAX'));
    document.querySelectorAll('[data-indicator]').forEach(button => button.addEventListener('click', () => {
      const key = button.dataset.indicator;
      indicators[key] = !indicators[key];
      syncIndicators();
      state.chart?.setIndicators(indicators);
      state.chart?.resize();
      try { localStorage.setItem('heroIndicators', JSON.stringify(indicators)); } catch (_) { /* Optional preference. */ }
    }));
    $('hero-export').addEventListener('click', () => {
      if (!state.series) return;
      const rows = ['date,value', ...state.series.data.map(([ts, value]) => iso(ts) + ',' + value)];
      const url = URL.createObjectURL(new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8' }));
      const a = document.createElement('a');
      a.href = url; a.download = state.series.id + '.csv'; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    for (const input of [$('hero-date-from'), $('hero-date-to')]) {
      input.addEventListener('change', () => {
        const valid = state.chart?.setDates($('hero-date-from').value, $('hero-date-to').value);
        input.setCustomValidity(valid ? '' : 'Choose a valid date range within the available observations.');
        if (!valid) input.reportValidity();
      });
    }
    const first = REGIONS.GLOBAL;
    if (sectionData[first[0]]?.series?.[first[1]]) loadLocal(...first);
    else if (select.options.length) loadLocal(...select.options[0].value.split('/'));
    global.lucide?.createIcons();
  }

  global.Hero = { init, setSymbol, setMode, loadLocal, addAnnotation, removeAnnotation, clearAnnotations,
    hasAnnotation: id => state.annotations.some(a => a.id === id),
    setRegion: region => { if (REGIONS[region]) loadLocal(...REGIONS[region]); } };
})(window);
