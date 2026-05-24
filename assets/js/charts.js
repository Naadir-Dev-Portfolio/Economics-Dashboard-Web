/**
 * charts.js — small chart factory.
 *
 * Provides:
 *   ChartKit.createCardChart(el, series)      → big focused chart (cat panel)
 *   ChartKit.createSparkline(el, series, opt) → tiny chip/ribbon spark
 *   ChartKit.formatNumber / formatAxis / filterByRange
 *
 * Theme: black canvas, white primary line, red signal when direction is down.
 */
(function (global) {
  'use strict';

  const COLORS = {
    bg: 'transparent',
    grid: '#1a1a1a',
    axis: '#2a2a2a',
    text: '#6e6e6e',
    textBright: '#ffffff',
    line: '#ffffff',
    pos: '#e5e5e5',
    neg: '#ff4757',
    accent: '#dc2626',
    accentLine: 'rgba(220,38,38,0.45)',
    fillTop: 'rgba(255,255,255,0.18)',
    fillBot: 'rgba(255,255,255,0.00)',
    fillTopNeg: 'rgba(255,71,87,0.25)',
    fillBotNeg: 'rgba(255,71,87,0.00)',
  };

  const RANGE_MS = {
    '1M': 31 * 86400000,
    '6M': 183 * 86400000,
    '1Y': 365 * 86400000,
    '5Y': 5 * 365 * 86400000,
    '10Y': 10 * 365 * 86400000,
  };

  function filterByRange(data, range) {
    if (!data || !data.length) return [];
    if (range === 'MAX' || !range) return data;
    const last = data[data.length - 1][0];
    if (range === 'YTD') {
      const d = new Date(last);
      return data.filter(p => p[0] >= Date.UTC(d.getUTCFullYear(), 0, 1));
    }
    const span = RANGE_MS[range];
    return span ? data.filter(p => p[0] >= last - span) : data;
  }

  function pickDirection(data) {
    if (!data || data.length < 2) return 1;
    return data[data.length - 1][1] >= data[0][1] ? 1 : -1;
  }

  function buildCardOption(series, range, annotations = []) {
    const data = filterByRange(series.data, range);
    const direction = pickDirection(data);
    const lineColor = direction >= 0 ? COLORS.line : COLORS.neg;
    const fillTop = direction >= 0 ? COLORS.fillTop : COLORS.fillTopNeg;
    const fillBot = direction >= 0 ? COLORS.fillBot : COLORS.fillBotNeg;
    const showZero = series.unit === '%' || series.unit === 'bps';

    // Filter annotations to those within the visible range.
    const inRange = (ts) => data.length && ts >= data[0][0] && ts <= data[data.length - 1][0];
    const annMarkLines = annotations.filter(a => inRange(a.ts)).map(a => ({
      xAxis: a.ts,
      lineStyle: { color: COLORS.accent, width: 1, type: 'solid', opacity: 0.7 },
      label: {
        show: true,
        position: 'insideEndTop',
        formatter: a.label || a.title,
        color: '#ffffff',
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 9,
        backgroundColor: 'rgba(220,38,38,0.85)',
        padding: [2, 5],
        borderRadius: 1,
      },
    }));

    return {
      backgroundColor: COLORS.bg,
      animation: true,
      animationDuration: 480,
      animationEasing: 'cubicOut',
      grid: { left: 42, right: 14, top: 10, bottom: 22 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(0,0,0,0.96)',
        borderColor: '#2a2a2a',
        borderWidth: 1,
        textStyle: { color: COLORS.textBright, fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
        formatter: (params) => {
          if (!params || !params.length) return '';
          const p = params[0];
          const dateStr = new Date(p.value[0]).toISOString().slice(0, 10);
          const val = formatNumber(p.value[1], series.unit);
          return `<div style="font-size:10px;color:#6e6e6e;letter-spacing:.08em;margin-bottom:3px">${dateStr}</div>
                  <div style="font-size:13px;color:#ffffff">${val}<span style="color:#6e6e6e;margin-left:6px;font-size:10px">${series.unit || ''}</span></div>`;
        },
        axisPointer: { lineStyle: { color: '#303030', type: 'dashed' } },
      },
      xAxis: {
        type: 'time',
        axisLine: { lineStyle: { color: COLORS.axis } },
        axisLabel: { color: COLORS.text, fontSize: 10, fontFamily: 'JetBrains Mono, monospace' },
        splitLine: { show: false },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        scale: !showZero,
        axisLine: { show: false },
        axisLabel: {
          color: COLORS.text, fontSize: 10, fontFamily: 'JetBrains Mono, monospace',
          formatter: (v) => formatAxis(v, series.unit),
        },
        splitLine: { lineStyle: { color: COLORS.grid } },
        axisTick: { show: false },
      },
      series: [{
        type: 'line', showSymbol: false, smooth: 0.2, sampling: 'lttb',
        lineStyle: { color: lineColor, width: 1.4 },
        itemStyle: { color: lineColor },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [{ offset: 0, color: fillTop }, { offset: 1, color: fillBot }],
          },
        },
        data,
        markLine: {
          silent: true, symbol: 'none',
          lineStyle: { color: COLORS.axis, type: 'dashed', width: 1 },
          data: [
            ...(showZero ? [{ yAxis: 0 }] : []),
            ...annMarkLines,
          ],
          label: { show: false },
        },
      }],
    };
  }

  function buildSparkOption(series, range = '1Y') {
    const data = filterByRange(series.data, range);
    const direction = pickDirection(data);
    const color = direction >= 0 ? COLORS.line : COLORS.neg;
    return {
      backgroundColor: 'transparent',
      animation: false,
      grid: { left: 0, right: 0, top: 2, bottom: 2 },
      tooltip: { show: false },
      xAxis: { type: 'time', show: false },
      yAxis: { type: 'value', scale: true, show: false },
      series: [{
        type: 'line', showSymbol: false, smooth: 0.2, sampling: 'lttb',
        lineStyle: { color, width: 1.2 },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: direction >= 0
              ? [{ offset: 0, color: 'rgba(255,255,255,0.22)' }, { offset: 1, color: 'rgba(255,255,255,0)' }]
              : [{ offset: 0, color: 'rgba(255,71,87,0.28)' }, { offset: 1, color: 'rgba(255,71,87,0)' }],
          },
        },
        data,
      }],
    };
  }

  function formatNumber(v, unit) {
    if (v == null || isNaN(v)) return '—';
    const abs = Math.abs(v);
    if (unit === '%' || unit === 'bps') return v.toFixed(2);
    if (abs >= 1e12) return (v / 1e12).toFixed(2) + 'T';
    if (abs >= 1e9)  return (v / 1e9).toFixed(2) + 'B';
    if (abs >= 1e6)  return (v / 1e6).toFixed(2) + 'M';
    if (abs >= 1e3)  return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
    if (abs >= 1)    return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    return v.toFixed(4);
  }

  function formatAxis(v, unit) {
    if (v == null || isNaN(v)) return '';
    const abs = Math.abs(v);
    if (unit === '%' || unit === 'bps') return v.toFixed(1);
    if (abs >= 1e9) return (v / 1e9).toFixed(1) + 'B';
    if (abs >= 1e6) return (v / 1e6).toFixed(1) + 'M';
    if (abs >= 1e3) return (v / 1e3).toFixed(1) + 'k';
    if (abs >= 10)  return v.toFixed(0);
    return v.toFixed(2);
  }

  function createCardChart(container, series, opts = {}) {
    if (!series || !series.data || !series.data.length) return null;
    const instance = global.echarts.init(container, null, { renderer: 'canvas' });
    let currentRange = opts.range || 'MAX';
    let annotations = opts.annotations || [];

    const render = () => {
      instance.setOption(buildCardOption(series, currentRange, annotations), { notMerge: true });
    };
    render();
    const onResize = () => instance.resize();
    window.addEventListener('resize', onResize);

    return {
      instance,
      setRange(r) { currentRange = r; render(); },
      setAnnotations(list) { annotations = list || []; render(); },
      setSeries(s) { series = s; render(); },
      dispose() { window.removeEventListener('resize', onResize); instance.dispose(); },
      resize: () => instance.resize(),
    };
  }

  function createSparkline(container, series, opts = {}) {
    if (!series || !series.data || !series.data.length) return null;
    const instance = global.echarts.init(container, null, { renderer: 'canvas' });
    const range = opts.range || '1Y';
    instance.setOption(buildSparkOption(series, range), { notMerge: true });
    const onResize = () => instance.resize();
    window.addEventListener('resize', onResize);
    return {
      instance,
      resize: () => instance.resize(),
      dispose() { window.removeEventListener('resize', onResize); instance.dispose(); },
    };
  }

  global.ChartKit = {
    createCardChart,
    createSparkline,
    formatNumber,
    formatAxis,
    filterByRange,
    COLORS,
  };
})(window);
