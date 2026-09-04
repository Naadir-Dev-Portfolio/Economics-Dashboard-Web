/** Shared ECharts rendering and observation-aware formatting. */
(function (global) {
  'use strict';

  const DAY = 86400000;
  const COLORS = { line: '#ffffff', neg: '#ff4757', grid: '#242424', axis: '#333333', text: '#969696', accent: '#dc2626' };
  const RANGES = { '1M': 31, '6M': 183, '1Y': 365, '5Y': 1826, '10Y': 3653 };
  const FREQUENCIES = { d: 'Daily', w: 'Weekly', m: 'Monthly', q: 'Quarterly', a: 'Annual' };
  const indicatorCache = new WeakMap();
  const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function bounds(data, range) {
    const first = data[0][0], last = data[data.length - 1][0];
    const date = new Date(last);
    const start = range === 'YTD' ? Date.UTC(date.getUTCFullYear(), 0, 1) : last - (RANGES[range] || Infinity) * DAY;
    return [Math.max(first, start), last];
  }

  function filterByRange(data, range) {
    if (!data?.length) return [];
    const [start, end] = bounds(data, range);
    return data.filter(p => p[0] >= start && p[0] <= end);
  }

  function formatNumber(value, unit) {
    if (value == null || !Number.isFinite(Number(value))) return '\u2014';
    const v = Number(value), abs = Math.abs(v);
    if (unit === '%' || unit === 'bps') return v.toFixed(2);
    if (unit === 'rate') return v.toFixed(4);
    if (abs >= 1e12) return (v / 1e12).toFixed(2) + 'T';
    if (abs >= 1e9) return (v / 1e9).toFixed(2) + 'B';
    if (abs >= 1e6) return (v / 1e6).toFixed(2) + 'M';
    return v.toLocaleString('en-GB', { maximumFractionDigits: abs < 1 ? 4 : 2 });
  }

  function formatAxis(v, unit) {
    if (unit === '%' || unit === 'bps') return v.toFixed(1);
    const abs = Math.abs(v);
    if (abs >= 1e9) return (v / 1e9).toFixed(1) + 'B';
    if (abs >= 1e6) return (v / 1e6).toFixed(1) + 'M';
    if (abs >= 1e3) return (v / 1e3).toFixed(1) + 'k';
    return v.toFixed(abs >= 10 ? 0 : abs >= 1 ? 2 : 4);
  }

  function formatPeriod(series, timestamp) {
    const d = new Date(timestamp);
    if (!Number.isFinite(d.getTime())) return '';
    const y = d.getUTCFullYear(), m = d.getUTCMonth();
    const month = date => date.toLocaleDateString('en-GB', { month: 'short', timeZone: 'UTC' });
    if (series.period_type === 'three month average') {
      const start = new Date(Date.UTC(y, m - 1, 1)), end = new Date(Date.UTC(y, m + 1, 1));
      return month(start) + (start.getUTCFullYear() !== end.getUTCFullYear() ? ' ' + start.getUTCFullYear() : '') + '-' + month(end) + ' ' + end.getUTCFullYear();
    }
    if (series.frequency === 'q') return 'Q' + (Math.floor(m / 3) + 1) + ' ' + y;
    if (series.frequency === 'a') return String(y);
    return d.toLocaleDateString('en-GB', { ...(series.frequency !== 'm' ? { day: 'numeric' } : {}), month: 'short', year: 'numeric', timeZone: 'UTC' });
  }

  function freshnessState(series) {
    if (series.archived) return 'Historical only';
    if (!series.data?.length) return 'Unavailable';
    if (series.fetch_status === 'retained') return 'Previous data retained';
    const last = new Date(series.data[series.data.length - 1][0]);
    const month = last.getUTCMonth(), year = last.getUTCFullYear();
    let end = last.getTime();
    if (series.frequency === 'm') end = Date.UTC(year, month + 1, 0);
    if (series.frequency === 'q') end = Date.UTC(year, Math.floor(month / 3) * 3 + 3, 0);
    if (series.frequency === 'a') end = Date.UTC(year, 12, 0);
    const limit = series.max_age_days ?? ({ d: 7, w: 21, m: 100, q: 230, a: 800 }[series.frequency] || 100);
    if (series.freshness === 'invalid' || last.getTime() > Date.now()) return 'Invalid date';
    const today = Math.floor(Date.now() / DAY);
    if (series.freshness === 'stale' || today - Math.floor(end / DAY) > limit ||
        (series.next_release && today - Math.floor(Date.parse(series.next_release.slice(0, 10)) / DAY) > 2)) return 'Observation overdue';
    if (!series.last_success || Date.now() - Date.parse(series.last_success) > 36 * 3600000) return 'Refresh overdue';
    return '';
  }

  function observationLabel(series) {
    if (!series?.data?.length) return 'No observations';
    return series.period_label || formatPeriod(series, series.data[series.data.length - 1][0]);
  }

  function sourceSummary(series) {
    const parts = [series.source, FREQUENCIES[series.frequency], observationLabel(series)];
    if (series.published_at) {
      const published = new Date(series.published_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: series.method === 'ons' ? 'Europe/London' : 'UTC' });
      parts.push('published ' + published);
    }
    if (series.latest_quote_at) parts.push('latest quote ' + new Date(series.latest_quote_at).toISOString().slice(11, 16) + ' UTC');
    parts.push(freshnessState(series));
    return parts.filter(Boolean).join(' \u00b7 ');
  }

  function annualChange(series) {
    const absolute = series.unit === '%' || series.unit === 'bps';
    const value = series.stats?.[absolute ? 'chg_1y_pp' : 'chg_1y_pct'];
    return { value, unit: absolute ? (series.unit === '%' ? 'pp' : 'bps') : '%' };
  }

  function calculateIndicators(data) {
    if (indicatorCache.has(data)) return indicatorCache.get(data);
    if (!global.SMA || !global.RSI) return {};
    const values = data.map(p => p[1]);
    const align = result => result.map((value, i) => [data[data.length - result.length + i][0], value]);
    const result = {
      fast: align(global.SMA.calculate({ period: 20, values })),
      slow: align(global.SMA.calculate({ period: 50, values })),
      rsi: align(global.RSI.calculate({ period: 14, values })),
    };
    indicatorCache.set(data, result);
    return result;
  }

  function wheelView(view, extent, anchor, delta, mode = 0) {
    const pixels = delta * (mode === 1 ? 16 : mode === 2 ? 240 : 1);
    const factor = Math.exp(Math.max(-0.08, Math.min(0.08, pixels * 0.001)));
    const span = Math.min(extent[1] - extent[0], Math.max(DAY, (view[1] - view[0]) * factor));
    const fraction = Math.max(0, Math.min(1, (anchor - view[0]) / (view[1] - view[0] || 1)));
    const start = Math.max(extent[0], Math.min(extent[1] - span, anchor - span * fraction));
    return [start, start + span];
  }

  function buildCardOption(series, view, annotations, indicators = {}, fineZoom = false) {
    const data = series.data;
    const visible = data.filter(p => p[0] >= view[0] && p[0] <= view[1]);
    const down = visible.length > 1 && visible[visible.length - 1][1] < visible[0][1];
    const color = down ? COLORS.neg : COLORS.line;
    const annotationLines = annotations.filter(a => a.ts >= data[0][0] && a.ts <= data[data.length - 1][0]).map(a => ({
      xAxis: a.ts, lineStyle: { color: COLORS.accent, width: 1 },
      label: { show: true, formatter: a.label || a.title, position: 'insideEndTop', color: '#fff', fontSize: 9, backgroundColor: '#991b1b', padding: [2, 4] },
    }));
    const calculated = Object.values(indicators).some(Boolean) ? calculateIndicators(data) : {};
    const rsi = indicators.rsi && calculated.rsi?.length > 0;
    const option = {
      backgroundColor: 'transparent', animation: false, useUTC: true,
      grid: { left: 55, right: 22, top: 18, bottom: 66 },
      tooltip: {
        trigger: 'axis', confine: true,
        backgroundColor: '#090909', borderColor: '#444', textStyle: { color: '#fff', fontSize: 12 },
        axisPointer: { type: 'cross', label: { show: false } },
        formatter: params => {
          const p = params?.[0];
          if (!p) return '';
          return escapeHtml(formatPeriod(series, p.value[0])) + params.map(item => '<br>' + item.marker +
            escapeHtml(item.seriesName) + ': <strong>' + formatNumber(item.value[1], item.seriesId === 'rsi' ? '%' : series.unit) +
            '</strong>' + (item.seriesId === 'rsi' ? '' : ' ' + escapeHtml(series.unit))).join('');
        },
      },
      xAxis: {
        type: 'time', min: 'dataMin', max: 'dataMax', boundaryGap: [0, 0],
        axisLine: { lineStyle: { color: COLORS.axis } }, axisTick: { show: false },
        axisLabel: { color: COLORS.text, fontSize: 10, hideOverlap: true },
        splitLine: { show: true, lineStyle: { color: COLORS.grid, type: 'dashed' } },
      },
      yAxis: {
        type: 'value', scale: true, axisTick: { show: false }, axisLine: { show: false },
        axisLabel: { color: COLORS.text, fontSize: 10, formatter: v => formatAxis(v, series.unit) },
        splitLine: { lineStyle: { color: COLORS.grid } },
      },
      dataZoom: [
        { type: 'inside', xAxisIndex: rsi ? [0, 1] : 0, startValue: view[0], endValue: view[1], rangeMode: ['value', 'value'], filterMode: 'filter', zoomOnMouseWheel: !fineZoom, moveOnMouseMove: true, moveOnMouseWheel: false, minValueSpan: DAY },
        { type: 'slider', xAxisIndex: rsi ? [0, 1] : 0, startValue: view[0], endValue: view[1], rangeMode: ['value', 'value'], bottom: 5, height: 22, borderColor: '#363636', backgroundColor: '#151515', fillerColor: 'rgba(220,38,38,0.15)', handleSize: '120%', textStyle: { color: COLORS.text }, showDetail: false, brushSelect: true, minValueSpan: DAY },
      ],
      series: [{
        id: 'observations', name: series.name || 'Value', type: 'line', data, showSymbol: visible.length < 40, symbolSize: 4,
        smooth: false, sampling: 'lttb', lineStyle: { color, width: 1.5 }, itemStyle: { color },
        markLine: { silent: true, symbol: 'none', data: annotationLines },
      }],
    };
    for (const [key, name, color] of [['fast', 'SMA 20', '#22d3ee'], ['slow', 'SMA 50', '#fbbf24']]) {
      if (indicators[key] && calculated[key]?.length) option.series.push({
        id: key, name, type: 'line', data: calculated[key], showSymbol: false, sampling: 'lttb',
        lineStyle: { color, width: 1.5 }, itemStyle: { color },
      });
    }
    if (rsi) {
      option.grid = [{ ...option.grid, bottom: '39%' }, { left: 55, right: 22, top: '70%', bottom: 66 }];
      option.xAxis = [
        { ...option.xAxis, axisLabel: { show: false } },
        { ...option.xAxis, gridIndex: 1, min: data[0][0], max: data[data.length - 1][0] },
      ];
      option.yAxis = [option.yAxis, {
        ...option.yAxis, gridIndex: 1, min: 0, max: 100, interval: 50, name: 'RSI 14',
        nameTextStyle: { color: '#a3e635', fontSize: 10 },
        axisLabel: { color: COLORS.text, fontSize: 10 },
      }];
      option.axisPointer = { link: [{ xAxisIndex: 'all' }] };
      option.series.push({
        id: 'rsi', name: 'RSI 14', type: 'line', xAxisIndex: 1, yAxisIndex: 1,
        data: calculated.rsi, showSymbol: false, sampling: 'lttb',
        lineStyle: { color: '#a3e635', width: 1.3 }, itemStyle: { color: '#a3e635' },
        markLine: { silent: true, symbol: 'none', lineStyle: { color: '#737373', type: 'dashed' },
          label: { color: COLORS.text, fontSize: 9, position: 'insideEndTop' }, data: [{ yAxis: 30 }, { yAxis: 70 }] },
      });
    }
    return option;
  }

  function observeSize(container, instance) {
    if (global.ResizeObserver) {
      const observer = new ResizeObserver(() => instance.resize());
      observer.observe(container);
      return () => observer.disconnect();
    }
    const resize = () => instance.resize();
    global.addEventListener('resize', resize);
    return () => global.removeEventListener('resize', resize);
  }

  function createCardChart(container, series, opts = {}) {
    if (!series?.data?.length || !global.echarts) return null;
    global.echarts.getInstanceByDom(container)?.dispose();
    const instance = global.echarts.init(container, null, { renderer: 'canvas' });
    let view = bounds(series.data, opts.range || 'MAX');
    let annotations = opts.annotations || [];
    let indicators = opts.indicators || {};
    const render = () => instance.setOption(buildCardOption(series, view, annotations, indicators, opts.fineZoom), { notMerge: true });
    render();
    const stopResize = observeSize(container, instance);
    instance.on('datazoom', () => {
      const zoom = instance.getOption().dataZoom[0];
      const [first, last] = bounds(series.data, 'MAX');
      view = [zoom.startValue ?? first + (last - first) * zoom.start / 100, zoom.endValue ?? first + (last - first) * zoom.end / 100];
      opts.onZoom?.(view);
    });
    let wheelFrame = null, wheelDelta = 0, wheelAnchor = 0;
    // ECharts' native wheel multiplier is device-dependent. Normalize only the hero,
    // coalescing trackpad bursts and keeping each animation frame within an 8% step.
    const wheel = event => {
      const rect = container.getBoundingClientRect();
      const point = [event.clientX - rect.left, event.clientY - rect.top];
      if (!instance.containPixel({ gridIndex: indicators.rsi ? [0, 1] : 0 }, point) || !Number.isFinite(event.deltaY) || !event.deltaY) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      wheelAnchor = instance.convertFromPixel({ xAxisIndex: 0 }, point[0]);
      wheelDelta += event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 240 : 1);
      if (wheelFrame != null) return;
      wheelFrame = global.requestAnimationFrame(() => {
        wheelFrame = null;
        const next = wheelView(view, bounds(series.data, 'MAX'), wheelAnchor, wheelDelta);
        wheelDelta = 0;
        instance.dispatchAction({ type: 'dataZoom', startValue: next[0], endValue: next[1] });
      });
    };
    if (opts.fineZoom) container.addEventListener('wheel', wheel, { passive: false, capture: true });
    return {
      instance,
      setRange(range) { view = bounds(series.data, range); render(); opts.onZoom?.(view); },
      setDates(start, end) {
        const [first, last] = bounds(series.data, 'MAX');
        const next = [Math.max(first, Date.parse(start)), Math.min(last, Date.parse(end))];
        if (!next.every(Number.isFinite) || next[0] > next[1]) return false;
        view = next; render(); opts.onZoom?.(view); return true;
      },
      getView() { return [...view]; },
      setAnnotations(list) { annotations = list || []; render(); },
      setIndicators(next) { indicators = { ...next }; render(); },
      setSeries(next) { series = next; view = bounds(series.data, opts.range || 'MAX'); render(); },
      resize() { instance.resize(); },
      dispose() {
        stopResize();
        if (opts.fineZoom) container.removeEventListener('wheel', wheel, true);
        if (wheelFrame != null) global.cancelAnimationFrame(wheelFrame);
        instance.dispose();
      },
    };
  }

  function createSparkline(container, series, opts = {}) {
    if (!series?.data?.length || !global.echarts) return null;
    global.echarts.getInstanceByDom(container)?.dispose();
    const instance = global.echarts.init(container, null, { renderer: 'canvas' });
    const data = filterByRange(series.data, opts.range || '1Y');
    const color = data.length > 1 && data[data.length - 1][1] < data[0][1] ? COLORS.neg : COLORS.line;
    instance.setOption({
      animation: false, useUTC: true, grid: { left: 0, right: 0, top: 3, bottom: 3 },
      xAxis: { type: 'time', show: false, min: 'dataMin', max: 'dataMax' }, yAxis: { type: 'value', show: false, scale: true },
      series: [{ type: 'line', data, showSymbol: false, smooth: false, sampling: 'lttb', lineStyle: { color, width: 1.2 } }],
    });
    const stopResize = observeSize(container, instance);
    return { instance, resize: () => instance.resize(), dispose() { stopResize(); instance.dispose(); } };
  }

  global.ChartKit = { createCardChart, createSparkline, formatNumber, formatAxis, filterByRange,
    formatPeriod, observationLabel, sourceSummary, freshnessState, annualChange, escapeHtml,
    calculateIndicators, wheelView, FREQUENCIES, COLORS };
})(window);
