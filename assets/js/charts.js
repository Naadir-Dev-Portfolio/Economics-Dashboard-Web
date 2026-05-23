/**
 * charts.js
 *
 * Thin wrapper around ECharts for the dashboard's card charts.
 * Provides:
 *   - createCardChart(container, series, options) -> instance with .setRange()
 *   - Consistent dark theme tuned for the covert-ops palette
 *   - Range filtering: 1M / 6M / YTD / 1Y / 5Y / 10Y / MAX
 */
(function (global) {
  'use strict';

  const COLORS = {
    bg: 'transparent',
    grid: '#1c2330',
    axis: '#2d384a',
    text: '#8b95a4',
    textBright: '#e6edf3',
    line: '#39ffaf',
    fillTop: 'rgba(57, 255, 175, 0.30)',
    fillBot: 'rgba(57, 255, 175, 0.00)',
    pos: '#4ade80',
    neg: '#ff5b6a',
    amber: '#ffb454',
  };

  /** Range presets in milliseconds (approximate). */
  const RANGE_MS = {
    '1M':  31 * 86400000,
    '6M':  183 * 86400000,
    '1Y':  365 * 86400000,
    '5Y':  5 * 365 * 86400000,
    '10Y': 10 * 365 * 86400000,
  };

  function filterByRange(data, range) {
    if (!data || !data.length) return [];
    if (range === 'MAX' || !range) return data;
    const last = data[data.length - 1][0];
    if (range === 'YTD') {
      const lastDate = new Date(last);
      const start = Date.UTC(lastDate.getUTCFullYear(), 0, 1);
      return data.filter((d) => d[0] >= start);
    }
    const span = RANGE_MS[range];
    if (!span) return data;
    return data.filter((d) => d[0] >= last - span);
  }

  function pickLineColor(series, range) {
    const slice = filterByRange(series.data, range);
    if (slice.length < 2) return COLORS.line;
    const first = slice[0][1];
    const last = slice[slice.length - 1][1];
    if (last > first * 1.0005) return COLORS.pos;
    if (last < first * 0.9995) return COLORS.neg;
    return COLORS.line;
  }

  function buildOption(series, range) {
    const data = filterByRange(series.data, range);
    const color = pickLineColor(series, range);
    const fillTop = color.replace('rgb(', 'rgba(').replace(')', ', 0.28)') ||
                    `${color}45`;
    const isPercent = series.unit === '%' || series.unit === 'bps';
    const showZero = isPercent;

    return {
      backgroundColor: COLORS.bg,
      animation: true,
      animationDuration: 600,
      animationEasing: 'cubicOut',
      grid: { left: 38, right: 14, top: 12, bottom: 24, containLabel: false },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(10,15,23,0.96)',
        borderColor: '#2d384a',
        borderWidth: 1,
        textStyle: { color: COLORS.textBright, fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
        formatter: (params) => {
          if (!params || !params.length) return '';
          const p = params[0];
          const d = new Date(p.value[0]);
          const dateStr = d.toISOString().slice(0, 10);
          const val = p.value[1];
          const formatted = formatNumber(val, series.unit);
          return `<div style="font-size:10px;color:#8b95a4;letter-spacing:0.08em;margin-bottom:4px">${dateStr}</div>
                  <div style="font-size:13px;color:#e6edf3">${formatted}<span style="color:#8b95a4;margin-left:6px;font-size:10px">${series.unit || ''}</span></div>`;
        },
        axisPointer: { lineStyle: { color: '#2d384a', type: 'dashed' } },
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
          color: COLORS.text,
          fontSize: 10,
          fontFamily: 'JetBrains Mono, monospace',
          formatter: (v) => formatAxis(v, series.unit),
        },
        splitLine: { lineStyle: { color: COLORS.grid, type: 'solid' } },
        axisTick: { show: false },
      },
      series: [
        {
          type: 'line',
          showSymbol: false,
          smooth: 0.25,
          sampling: 'lttb',
          lineStyle: { color, width: 1.4 },
          itemStyle: { color },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: fillTop },
                { offset: 1, color: 'rgba(57,255,175,0.00)' },
              ],
            },
          },
          emphasis: { focus: 'series' },
          data,
          markLine: showZero ? {
            silent: true,
            symbol: 'none',
            lineStyle: { color: '#2d384a', type: 'dashed', width: 1 },
            data: [{ yAxis: 0 }],
            label: { show: false },
          } : undefined,
        },
      ],
    };
  }

  function formatNumber(v, unit) {
    if (v === null || v === undefined || isNaN(v)) return '—';
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
    if (v === null || v === undefined || isNaN(v)) return '';
    const abs = Math.abs(v);
    if (unit === '%' || unit === 'bps') return v.toFixed(1);
    if (abs >= 1e9) return (v / 1e9).toFixed(1) + 'B';
    if (abs >= 1e6) return (v / 1e6).toFixed(1) + 'M';
    if (abs >= 1e3) return (v / 1e3).toFixed(1) + 'k';
    if (abs >= 10)  return v.toFixed(0);
    return v.toFixed(2);
  }

  /**
   * Create a chart in the given container.
   * Returns an object with .setRange(range) and .dispose().
   */
  function createCardChart(container, series) {
    if (!series || !series.data || !series.data.length) return null;
    const instance = global.echarts.init(container, null, { renderer: 'canvas' });
    let currentRange = 'MAX';

    function render() {
      instance.setOption(buildOption(series, currentRange), { notMerge: true });
    }
    render();

    const onResize = () => instance.resize();
    window.addEventListener('resize', onResize);

    return {
      instance,
      setRange(r) {
        currentRange = r;
        render();
      },
      dispose() {
        window.removeEventListener('resize', onResize);
        instance.dispose();
      },
      resize: () => instance.resize(),
    };
  }

  global.ChartKit = {
    createCardChart,
    formatNumber,
    formatAxis,
    filterByRange,
    COLORS,
  };
})(window);
