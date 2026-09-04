const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function load(file, window = {}, globals = {}) {
  const context = vm.createContext({ window, Intl, Date, Option: class {}, console, setTimeout, clearTimeout, ...globals });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'assets/js', file), 'utf8'), context);
  return window;
}

test('reporting periods and percentage-point changes are unambiguous', () => {
  const kit = load('charts.js').ChartKit;
  assert.equal(kit.formatPeriod({ frequency: 'q' }, Date.UTC(2026, 3, 1)), 'Q2 2026');
  assert.equal(kit.formatPeriod({ frequency: 'm', period_type: 'three month average' }, Date.UTC(2026, 4, 1)), 'Apr-Jun 2026');
  assert.equal(kit.annualChange({ unit: '%', stats: { chg_1y_pp: -0.5, chg_1y_pct: -20 } }).value, -0.5);
  assert.equal(kit.annualChange({ unit: '%' }).unit, 'pp');
});

test('hero wheel zoom is cursor-anchored, incremental and bounded for every delta mode', () => {
  const { wheelView } = load('charts.js').ChartKit;
  const day = 86400000, extent = [0, 1000 * day], view = [100 * day, 200 * day];
  for (const mode of [0, 1, 2]) {
    for (const delta of [-5000, -80, -1, 1, 80, 5000]) {
      const next = wheelView(view, extent, 125 * day, delta, mode);
      const ratio = (next[1] - next[0]) / (view[1] - view[0]);
      assert.ok(ratio > .92 && ratio < 1.09, { mode, delta, ratio });
      assert.ok(Math.abs((125 * day - next[0]) / (next[1] - next[0]) - .25) < 1e-9);
    }
  }
  let tiny = [0, 2 * day];
  for (let i = 0; i < 100; i++) tiny = wheelView(tiny, extent, tiny[0], -1000);
  assert.equal(tiny[0], 0);
  assert.equal(tiny[1], day);
  const full = wheelView(extent, extent, extent[1], 5000);
  assert.deepEqual(Array.from(full), extent);
});

function indicatorWindow() {
  const window = {};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../assets/vendor/technicalindicators-3.1.0.js'), 'utf8'), { window });
  return window;
}

test('standard SMA and Wilder RSI are aligned to native observations, not the zoom window', () => {
  const window = indicatorWindow();
  let option;
  const instance = { setOption(value) { option = value; }, getOption: () => option, on() {}, resize() {}, dispose() {} };
  Object.assign(window, { echarts: { init: () => instance, getInstanceByDom: () => null }, addEventListener() {}, removeEventListener() {} });
  const kit = load('charts.js', window).ChartKit;
  const data = Array.from({ length: 100 }, (_, i) => [Date.UTC(2020, i, 1), i]);
  const indicators = kit.calculateIndicators(data);
  assert.equal(indicators.fast[0][0], data[19][0]);
  assert.equal(indicators.fast[0][1], 9.5);
  assert.equal(indicators.slow[0][0], data[49][0]);
  assert.equal(indicators.slow[0][1], 24.5);
  assert.equal(indicators.rsi[0][0], data[14][0]);
  assert.equal(indicators.rsi[0][1], 100);
  const chart = kit.createCardChart({}, { data, frequency: 'm', unit: 'GBP' }, { indicators: { rsi: true, fast: true, slow: true } });
  assert.equal(option.grid.length, 2);
  assert.deepEqual(Array.from(option.dataZoom[0].xAxisIndex), [0, 1]);
  assert.equal(option.yAxis[1].min, 0);
  assert.equal(option.yAxis[1].max, 100);
  const rsi = option.series.find(s => s.id === 'rsi').data;
  chart.setDates('2025-01-01', '2025-03-01');
  const before = Array.from(chart.getView());
  assert.strictEqual(option.series.find(s => s.id === 'rsi').data, rsi);
  chart.setIndicators({ fast: true });
  assert.deepEqual(Array.from(chart.getView()), before);
  assert.equal(option.series.length, 2);
  chart.setAnnotations([{ ts: Date.UTC(2025, 1, 1), title: 'Release' }]);
  assert.equal(option.series[0].markLine.data.length, 1);
  const reference = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28];
  assert.equal(kit.calculateIndicators(reference.map((v, i) => [i * 86400000, v])).rsi[0][1], 70.46);
  assert.equal(kit.calculateIndicators(data.slice(0, 10)).rsi.length, 0);
});

test('browser freshness uses the same UTC calendar days and release grace as Python', () => {
  const now = Date.parse('2026-09-04T23:59:59Z');
  class FixedDate extends Date { static now() { return now; } }
  const kit = load('charts.js', {}, { Date: FixedDate }).ChartKit;
  const series = { frequency: 'd', data: [[Date.parse('2026-08-28'), 5]], last_success: '2026-09-04T12:00:00Z' };
  assert.equal(kit.freshnessState(series), '');
  assert.equal(kit.freshnessState({ ...series, data: [[Date.parse('2026-08-27'), 5]] }), 'Observation overdue');
  assert.equal(kit.freshnessState({ ...series, max_age_days: 14, data: [[Date.parse('2026-08-27'), 5]] }), '');
  assert.equal(kit.freshnessState({ ...series, next_release: '2026-09-01T23:00:00Z' }), 'Observation overdue');
  assert.equal(kit.freshnessState({ ...series, next_release: '2026-09-02' }), '');
});

test('crypto quotes validate timestamps and back off without exceeding the retry cap', () => {
  const live = load('live-prices.js').LivePrices;
  assert.equal(live.retryDelay(1), 60000);
  assert.equal(live.retryDelay(2), 120000);
  assert.equal(live.retryDelay(100), 900000);
  assert.equal(live.retryDelay(1, 1800000), 1800000);
  assert.equal(live.retryDelay(1, Infinity), 60000);
  assert.equal(live.retryDelay(1, 9000000), 3600000);
  assert.ok(live.validQuote({ usd: 100, last_updated_at: Date.now() / 1000 }));
  assert.ok(!live.validQuote({ usd: 100, last_updated_at: Date.now() / 1000 + 1000 }));
  assert.ok(!live.validQuote({ usd: 100, last_updated_at: Date.now() / 1000 - 3600 }));
  assert.ok(!live.validQuote({ usd: '100', last_updated_at: Date.now() / 1000 }));
});

test('static data cache expires and retains the last good payload on network failure', async () => {
  let now = Date.now(), requests = 0, fail = false;
  class FixedDate extends Date { static now() { return now; } }
  const loader = load('data-loader.js', {}, {
    Date: FixedDate, AbortController, console: { warn() {} },
    fetch: async () => { requests++; if (fail) throw new Error('Offline'); return { ok: true, json: async () => ({ version: requests }) }; },
  }).DataLoader;
  assert.equal((await loader.health()).version, 1);
  assert.equal((await loader.health()).version, 1);
  now += 300001;
  assert.equal((await loader.health()).version, 2);
  now += 300001;
  fail = true;
  assert.equal((await loader.health()).version, 2);
  assert.equal(requests, 3);
});

test('archive retains all data, grids, bounded dates and interactive zoom', () => {
  let option;
  const instance = { setOption(value) { option = value; }, getOption: () => option, on() {}, resize() {}, dispose() {} };
  const kit = load('charts.js', { echarts: { init: () => instance, getInstanceByDom: () => null }, addEventListener() {}, removeEventListener() {} }).ChartKit;
  const data = Array.from({ length: 600 }, (_, i) => [Date.UTC(2024, 0, 1) + i * 86400000, i]);
  const chart = kit.createCardChart({}, { data, frequency: 'd', unit: 'USD' }, { range: '1M' });
  assert.equal(option.series[0].data.length, 600);
  assert.equal(option.xAxis.splitLine.show, true);
  assert.equal(option.xAxis.max, 'dataMax');
  assert.equal(option.series[0].smooth, false);
  assert.equal(option.dataZoom.length, 2);
  assert.equal(chart.setDates('2025-01-01', '2025-01-03'), true);
  assert.equal(chart.getView()[1] - chart.getView()[0], 2 * 86400000);
  assert.equal(chart.setDates('2025-01-03', '2025-01-01'), false);
});

test('calendar export preserves provisional status and actual UTC time', () => {
  const calendar = load('calendar-modal.js').CalendarModal;
  const value = calendar.makeIcs({ id: 'test', title: 'Policy; decision', datetime: '2027-02-04T12:00:00+00:00', source: 'Central bank', description: 'Line one\nLine two', source_url: 'https://example.com/schedule', status: 'provisional', verification: 'cached' });
  assert.ok(value.includes('STATUS:TENTATIVE\r\n'));
  assert.ok(value.includes('DTSTART:20270204T120000Z'));
  assert.ok(value.includes('Line one\\nLine two'));
  assert.ok(value.includes('\\nSource: https://example.com/schedule'));
  assert.ok(!value.includes('\\\\nSource'));
});
