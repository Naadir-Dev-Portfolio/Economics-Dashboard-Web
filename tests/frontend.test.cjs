const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function load(file, window = {}) {
  const context = vm.createContext({ window, Intl, Date, Option: class {}, console, setTimeout, clearTimeout });
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
