/** Shared ECharts rendering and observation-aware formatting. */
(function (global) {
  'use strict';

  const DAY = 86400000;
  const COLORS = { line: '#ffffff', neg: '#ff4757', grid: '#242424', axis: '#333333', text: '#969696', accent: '#dc2626' };
  const RANGES = { '1M': 31, '6M': 183, '1Y': 365, '5Y': 1826, '10Y': 3653 };
  const FREQUENCIES = { d: 'Daily', w: 'Weekly', m: 'Monthly', q: 'Quarterly', a: 'Annual' };
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
    if (series.freshness === 'stale' || (Date.now() - end) / DAY > limit ||
        (series.next_release && (Date.now() - Date.parse(series.next_release)) / DAY > 3)) return 'Observation overdue';
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

  function buildCardOption(series, view, annotations) {
    const data = series.data;
    const visible = data.filter(p => p[0] >= view[0] && p[0] <= view[1]);
    const down = visible.length > 1 && visible[visible.length - 1][1] < visible[0][1];
    const color = down ? COLORS.neg : COLORS.line;
    const annotationLines = annotations.filter(a => a.ts >= data[0][0] && a.ts <= data[data.length - 1][0]).map(a => ({
      xAxis: a.ts, lineStyle: { color: COLORS.accent, width: 1 },
      label: { show: true, formatter: a.label || a.title, position: 'insideEndTop', color: '#fff', fontSize: 9, backgroundColor: '#991b1b', padding: [2, 4] },
    }));
    return {
      backgroundColor: 'transparent', animation: false, useUTC: true,
      grid: { left: 55, right: 22, top: 18, bottom: 66 },
      tooltip: {
        trigger: 'axis', confine: true,
        backgroundColor: '#090909', borderColor: '#444', textStyle: { color: '#fff', fontSize: 12 },
        axisPointer: { type: 'cross', label: { show: false } },
        formatter: params => {
          const p = params?.[0];
          if (!p) return '';
          return escapeHtml(formatPeriod(series, p.value[0])) + '<br><strong>' + formatNumber(p.value[1], series.unit) + '</strong> ' + escapeHtml(series.unit);
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
        { type: 'inside', xAxisIndex: 0, startValue: view[0], endValue: view[1], filterMode: 'filter', zoomOnMouseWheel: true, moveOnMouseMove: true, moveOnMouseWheel: false, minValueSpan: DAY },
        { type: 'slider', xAxisIndex: 0, startValue: view[0], endValue: view[1], bottom: 5, height: 22, borderColor: '#363636', backgroundColor: '#151515', fillerColor: 'rgba(220,38,38,0.15)', handleSize: '120%', textStyle: { color: COLORS.text }, showDetail: false, brushSelect: true, minValueSpan: DAY },
      ],
      series: [{
        id: 'observations', type: 'line', data, showSymbol: visible.length < 40, symbolSize: 4,
        smooth: false, sampling: 'lttb', lineStyle: { color, width: 1.5 }, itemStyle: { color },
        markLine: { silent: true, symbol: 'none', data: annotationLines },
      }],
    };
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
    const render = () => instance.setOption(buildCardOption(series, view, annotations), { notMerge: true });
    render();
    const stopResize = observeSize(container, instance);
    instance.on('datazoom', () => {
      const zoom = instance.getOption().dataZoom[0];
      const [first, last] = bounds(series.data, 'MAX');
      view = [zoom.startValue ?? first + (last - first) * zoom.start / 100, zoom.endValue ?? first + (last - first) * zoom.end / 100];
      opts.onZoom?.(view);
    });
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
      setSeries(next) { series = next; view = bounds(series.data, opts.range || 'MAX'); render(); },
      resize() { instance.resize(); },
      dispose() { stopResize(); instance.dispose(); },
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
    formatPeriod, observationLabel, sourceSummary, freshnessState, annualChange, escapeHtml, FREQUENCIES, COLORS };
})(window);
