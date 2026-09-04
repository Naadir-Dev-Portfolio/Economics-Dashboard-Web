import json
import logging
import math
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_health
import fetch_calendar as calendar
import fetch_data
import fetch_news
from data_quality import compute_stats, freshness, period_label, to_ms, validate_points, write_json, yoy
from source_providers import redact_credentials, sdmx_points

UTC = timezone.utc
NOW = datetime(2026, 9, 3, tzinfo=UTC)


class DataQualityTests(unittest.TestCase):
    def test_retry_logs_redact_api_credentials(self):
        record = logging.LogRecord('urllib3.connectionpool', logging.WARNING, __file__, 1,
                                   'Retrying %s', ('https://api.stlouisfed.org/fred/release/dates?api_key=test-secret&file_type=json',), None)
        redact_credentials(record)
        self.assertNotIn('test-secret', record.getMessage())
        self.assertIn('api_key=[REDACTED]&file_type=json', record.getMessage())

    def test_future_and_nonfinite_observations_are_rejected(self):
        for points in ([[to_ms('2026-09-30'), 70]], [[to_ms('2026-08-31'), math.nan]]):
            with self.assertRaises(ValueError):
                validate_points(points, NOW)

    def test_duplicates_are_not_silently_overwritten(self):
        with self.assertRaises(ValueError):
            validate_points([[0, 1], [0, 2]], NOW)
        self.assertEqual(validate_points([[1, 2], [0, 1], [1, 2]], NOW), [[0, 1], [1, 2]])

    def test_yoy_matches_calendar_periods_despite_missing_months(self):
        data = [[to_ms('2024-01-01'), 100], [to_ms('2024-03-01'), 200],
                [to_ms('2025-01-01'), 110], [to_ms('2025-02-01'), 190],
                [to_ms('2025-03-01'), 220]]
        self.assertEqual(yoy(data), [[to_ms('2025-01-01'), 10], [to_ms('2025-03-01'), 10]])

    def test_daily_changes_are_not_row_offsets(self):
        start = datetime(2025, 1, 1, tzinfo=UTC)
        points = [[int((start + timedelta(days=i)).timestamp() * 1000), 100 + i] for i in range(366)]
        stats = compute_stats(points, 'd')
        self.assertEqual(stats['chg_1y_pct'], 365)
        self.assertEqual(stats['chg_1m_pp'], 31)

    def test_quarterly_periods_and_lags(self):
        points = [[to_ms('2026-04-01'), 100]]
        series = {'frequency': 'q', 'stats': compute_stats(points, 'q')}
        self.assertEqual(period_label(points, 'q'), 'Q2 2026')
        self.assertEqual(freshness(series, now=NOW), 'current')
        self.assertIsNone(series['stats']['chg_1m_pct'])

    def test_expected_release_and_archival_status(self):
        series = {'frequency': 'm', 'stats': {'last_date': '2026-07-01'}, 'next_release': '2026-08-20'}
        self.assertEqual(freshness(series, now=NOW), 'stale')
        self.assertEqual(freshness(series, {'archived': True}, NOW), 'archived')

    def test_daily_freshness_uses_whole_calendar_days(self):
        now = datetime(2026, 9, 4, 23, 59, 59, tzinfo=UTC)
        series = {'frequency': 'd', 'stats': {'last_date': '2026-08-28'}}
        self.assertEqual(freshness(series, now=now), 'current')
        series['stats']['last_date'] = '2026-08-27'
        self.assertEqual(freshness(series, now=now), 'stale')

    def test_bis_policy_rates_allow_weekly_publication_but_still_expire(self):
        now = datetime(2026, 9, 4, tzinfo=UTC)
        configs = [s for s in fetch_data.SECTIONS['rates']['series'] if s.get('bis_policy')]
        self.assertEqual(len(configs), 4)
        for config in configs:
            series = {'frequency': 'd', 'stats': {'last_date': '2026-08-27'}}
            self.assertEqual(freshness(series, config, now), 'current')
            series['stats']['last_date'] = '2026-08-20'
            self.assertEqual(freshness(series, config, now), 'stale')

    def test_atomic_writer_preserves_good_file_on_bad_payload(self):
        cache = ROOT / '.cache'
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as directory:
            path = Path(directory) / 'sample.json'
            write_json(path, {'value': 1})
            with self.assertRaises(ValueError):
                write_json(path, {'value': math.nan})
            self.assertEqual(json.loads(path.read_text()), {'value': 1})
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_bis_missing_markers_and_unit_filter(self):
        rows = [{'TIME_PERIOD': '2026-07', 'OBS_VALUE': '2.5', 'UNIT_MEASURE': '771'},
                {'TIME_PERIOD': '2026-08', 'OBS_VALUE': 'NaN', 'UNIT_MEASURE': '771'},
                {'TIME_PERIOD': '2026-07', 'OBS_VALUE': '110', 'UNIT_MEASURE': '628'}]
        self.assertEqual(sdmx_points(rows, {'UNIT_MEASURE': '771'}), [[to_ms('2026-07-01'), 2.5]])


class NewsTests(unittest.TestCase):
    def test_empty_feeds_are_valid_but_html_and_invalid_xml_are_not(self):
        self.assertEqual(fetch_news.parse_feed('<rss><channel/></rss>', 'Test', ['UK']), [])
        self.assertEqual(fetch_news.parse_feed('<feed xmlns="http://www.w3.org/2005/Atom"/>', 'Test', ['UK']), [])
        for xml in ['<html/>', '<rss>', '<rss><channel><item/></channel></rss>']:
            with self.assertRaises(ValueError):
                fetch_news.parse_feed(xml, 'Test', ['UK'])

    def test_news_retention_and_health_distinguish_failure_from_empty_feed(self):
        (ROOT / '.cache').mkdir(exist_ok=True)
        headline = {'title': 'Economic release', 'source': 'Test', 'link': 'https://example.com/news',
                    'published': '2026-09-01T10:00:00+00:00', 'summary': 'Release', 'regions': ['UK']}
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as directory:
            data = Path(directory)
            write_json(data / 'news.json', {'items': [headline]})
            with patch.object(fetch_news, 'DATA_DIR', data), patch.object(fetch_news, 'SOURCES', [('Test', 'https://example.com/feed', ['UK'])]):
                with patch.object(fetch_news, 'fetch_url', return_value=None):
                    failed = fetch_news.run()
                self.assertEqual(failed['items'][0]['published'], headline['published'])
                self.assertEqual(failed['meta']['feed_status']['Test']['status'], 'error')
                with patch.object(build_health, 'load', return_value=failed):
                    health = build_health.build_news()
                self.assertEqual(health['status'], 'error')
                self.assertEqual(health['delivered'], 0)
                self.assertEqual(len(health['issues']), 1)
                with patch.object(fetch_news, 'fetch_url', return_value='<rss><channel/></rss>'):
                    empty = fetch_news.run()
                self.assertEqual(empty['meta']['by_source']['Test'], 0)
                self.assertEqual(empty['meta']['feed_status']['Test']['status'], 'ok')
                self.assertEqual(empty['items'][0]['published'], headline['published'])
                with patch.object(build_health, 'load', return_value=empty):
                    health = build_health.build_news()
                self.assertEqual(health['status'], 'ok')
                self.assertEqual(health['delivered'], 1)


class FetchTests(unittest.TestCase):
    def tearDown(self):
        fetch_data.fetch_ons.cache_clear()
        fetch_data._ONS_META.clear()

    def test_ons_metadata_follows_latest_date_not_array_order(self):
        payload = {'months': [
            {'date': '2026 MAY', 'label': '2026 APR-JUN', 'value': '4.9'},
            {'date': '2026 APR', 'label': '2026 MAR-MAY', 'value': '4.8'},
        ], 'description': {'releaseDate': '2026-08-17T23:00:00Z', 'nextRelease': '15 September 2026', 'monthLabelStyle': 'three month average'}}
        with patch.object(fetch_data, 'get', return_value=Mock(json=lambda: payload)):
            points = fetch_data.fetch_ons('TEST', 'lms', 'topic')
        self.assertEqual(points[-1], [to_ms('2026-05-01'), 4.9])
        self.assertEqual(fetch_data._ONS_META[('TEST', 'lms', 'm')]['period_label'], 'Apr-Jun 2026')

    def test_ons_cpi_is_not_transformed_twice(self):
        config = {'id': 'cpi', 'name': 'CPI', 'unit': '%', 'ons': 'TEST', 'ons_path': 'topic', 'fred': 'INDEX', 'fred_transform': 'yoy_pct'}
        points = [[to_ms('2026-06-01'), 2.7], [to_ms('2026-07-01'), 2.9]]
        with patch.object(fetch_data, 'fetch_ons', return_value=points), patch.object(fetch_data, 'fetch_fred', return_value=[]):
            result = fetch_data.fetch_one(config)
        self.assertEqual(result['stats']['last_value'], 2.9)

    def test_claims_counts_are_scaled_to_displayed_thousands(self):
        config = next(s for s in fetch_data.SECTIONS['employment']['series'] if s['id'] == 'us_claims')
        points = [[to_ms('2026-08-22'), 204000], [to_ms('2026-08-29'), 206000]]
        with patch.object(fetch_data, 'fetch_fred', return_value=points):
            result = fetch_data.fetch_one(config)
        self.assertEqual(result['unit'], 'k')
        self.assertEqual(result['stats']['last_value'], 206)

    def test_old_endpoints_and_truncated_history_are_rejected(self):
        config = {'id': 'example', 'name': 'Example', 'unit': '%', 'fred': 'EXAMPLE'}
        old = [[to_ms('2025-01-01'), 1], [to_ms('2026-07-01'), 2]]
        with patch.object(fetch_data, 'fetch_fred', return_value=old[:-1] + [[to_ms('2026-06-01'), 2]]):
            self.assertIsNone(fetch_data.fetch_one(config, {'schema_version': 2, 'data': old}))
        old = [[to_ms('2020-01-01') + i * 86400000, i + 1] for i in range(1800)]
        with patch.object(fetch_data, 'fetch_fred', return_value=old[-20:]):
            self.assertIsNone(fetch_data.fetch_one(config, {'schema_version': 2, 'data': old}))

    def test_failed_fetch_retains_observations_without_claiming_success(self):
        cache = ROOT / '.cache'
        cache.mkdir(exist_ok=True)
        config = {'test': {'title': 'Test', 'icon': 'test', 'blurb': '', 'series': [{'id': 'example', 'name': 'Example', 'unit': '%', 'fred': 'EXAMPLE'}]}}
        with tempfile.TemporaryDirectory(dir=cache) as directory:
            folder = Path(directory)
            previous = {'series': {'example': {'id': 'example', 'data': [[to_ms('2026-07-01'), 1], [to_ms('2026-08-01'), 2]],
                                                'frequency': 'm', 'last_success': '2026-08-20T00:00:00+00:00'}}}
            write_json(folder / 'test.json', previous)
            with patch.object(fetch_data, 'DATA_DIR', folder), patch.object(fetch_data, 'SECTIONS', config), patch.object(fetch_data, 'fetch_one', return_value=None), patch.dict('os.environ', {'ONLY_SECTION': '', 'SKIP_SECTIONS': ''}):
                result = fetch_data.run()
            item = json.loads((folder / 'test.json').read_text())['series']['example']
            self.assertEqual(item['data'], previous['series']['example']['data'])
            self.assertEqual(item['fetch_status'], 'retained')
            self.assertEqual(item['last_success'], '2026-08-20T00:00:00+00:00')
            self.assertEqual(result['totals']['fail'], 1)

    def test_explicit_definition_migration_does_not_splice_different_series(self):
        config = {'id': 'example', 'name': 'Revised definition', 'unit': '%', 'fred': 'EXAMPLE', 'history_version': 2}
        points = [[to_ms('2026-06-01'), 1], [to_ms('2026-07-01'), 2]]
        previous = {'schema_version': 2, 'data': [[to_ms('2026-08-01'), 9]], 'history_version': 1}
        with patch.object(fetch_data, 'fetch_fred', return_value=points):
            result = fetch_data.fetch_one(config, previous)
        self.assertEqual(result['data'], points)
        self.assertEqual(result['history_version'], 2)

    def test_yahoo_recent_tail_replaces_overlap_and_extends_daily_history(self):
        import pandas as pd
        history = pd.DataFrame({'Close': range(400)}, index=pd.date_range('2024-01-01', periods=400, tz='UTC'))
        recent = pd.DataFrame({'Close': [800, 900]}, index=pd.date_range(history.index[-1], periods=2))
        instrument = Mock()
        instrument.history.side_effect = [history, recent]
        instrument.get_history_metadata.return_value = {}
        with patch.dict(sys.modules, {'yfinance': Mock(Ticker=Mock(return_value=instrument))}):
            points = fetch_data.fetch_yahoo('TEST')
        self.assertEqual(len(points), 401)
        self.assertEqual([p[1] for p in points[-2:]], [800, 900])

    def test_timestamped_yahoo_quote_recovers_missing_daily_bar(self):
        import pandas as pd
        history = pd.DataFrame({'Close': range(400)}, index=pd.date_range('2024-01-01', periods=400, tz='UTC'))
        observed = history.index[-1] + timedelta(days=1, hours=15)
        for market_time in (observed.timestamp(), observed.tz_convert('Asia/Tokyo')):
            with self.subTest(timestamp_type=type(market_time).__name__):
                instrument = Mock()
                instrument.history.return_value = history
                instrument.get_history_metadata.return_value = {'symbol': 'TEST', 'regularMarketTime': market_time, 'exchangeTimezoneName': 'UTC', 'regularMarketPrice': 500}
                with patch.dict(sys.modules, {'yfinance': Mock(Ticker=Mock(return_value=instrument))}):
                    points = fetch_data.fetch_yahoo('TEST')
                self.assertEqual(points[-1], [to_ms(observed.date().isoformat()), 500])

    def test_yahoo_rejects_naive_future_and_mismatched_quotes(self):
        import pandas as pd
        history = pd.DataFrame({'Close': range(400)}, index=pd.date_range('2024-01-01', periods=400, tz='UTC'))
        for symbol, market_time in [('TEST', datetime(2026, 9, 3)),
                                    ('TEST', datetime.now(UTC) + timedelta(days=1)),
                                    ('OTHER', datetime(2026, 9, 3, tzinfo=UTC))]:
            with self.subTest(symbol=symbol, market_time=market_time):
                instrument = Mock()
                instrument.history.return_value = history
                instrument.get_history_metadata.return_value = {'symbol': symbol, 'regularMarketTime': market_time, 'exchangeTimezoneName': 'UTC', 'regularMarketPrice': 500}
                with patch.dict(sys.modules, {'yfinance': Mock(Ticker=Mock(return_value=instrument))}):
                    points = fetch_data.fetch_yahoo('TEST')
                self.assertEqual(len(points), 400)

    def test_health_does_not_count_stale_existing_series_as_delivered(self):
        config = {'test': {'series': [{'id': 'old', 'name': 'Old', 'fred': 'OLD'}, {'id': 'fresh', 'name': 'Fresh', 'fred': 'FRESH'}]}}
        payload = {'series': {
            'old': {'data': [[0, 1]], 'stats': {'last_date': '2020-01-01'}, 'frequency': 'm', 'method': 'fred', 'last_success': NOW.isoformat()},
            'fresh': {'data': [[to_ms('2026-07-01'), 1]], 'stats': {'last_date': '2026-07-01'}, 'frequency': 'm', 'method': 'fred', 'last_success': NOW.isoformat()},
        }}
        with patch.object(build_health, 'SECTIONS', config), patch.object(build_health, 'load', return_value=payload):
            source = build_health.build_series_sources(NOW)[0]
        self.assertEqual((source['delivered'], source['expected'], source['stale']), (1, 2, 1))
        self.assertEqual(source['status'], 'warning')


class CalendarTests(unittest.TestCase):
    def test_fred_release_api_requests_published_future_dates_without_exposing_key(self):
        future = (datetime.now(UTC) + timedelta(days=30)).date().isoformat()
        payload = {'release_dates': [{'release_id': 10, 'date': future}, {'release_id': 46, 'date': future}]}
        with patch.dict('os.environ', {'FRED_API_KEY': 'test-secret'}), patch.object(calendar, 'get', return_value=Mock(json=lambda: payload)) as request, patch.object(calendar, 'download_text') as html:
            events = calendar.fred_calendar_events('us_cpi')
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['source'], 'BLS via FRED')
        self.assertNotIn('test-secret', json.dumps(events))
        self.assertEqual(request.call_args.kwargs['params']['include_release_dates_with_no_data'], 'true')
        html.assert_not_called()

    def test_fred_release_api_failure_falls_back_without_logging_credentials(self):
        with patch.dict('os.environ', {'FRED_API_KEY': 'test-secret'}), patch.object(calendar, 'get', side_effect=ValueError('URL includes test-secret')), patch.object(calendar, 'download_text', return_value='html'), patch.object(calendar, 'parse_fred_calendar', return_value=[]) as parser, self.assertLogs('calendar', level='INFO') as logs:
            self.assertEqual(calendar.fred_calendar_events('us_cpi'), [])
        parser.assert_called_once()
        self.assertNotIn('test-secret', ''.join(logs.output))

    def test_fred_calendar_fallback_preserves_source_timezone_and_identity(self):
        html = '''<table><tbody>
          <tr><td colspan="2">Friday September 11, 2026</td></tr>
          <tr><td>7:30 am</td><td><a href="/release?rid=10">Consumer Price Index</a></td></tr>
          <tr><td>8:00 am</td><td><a href="/release?rid=46">Producer Price Index</a></td></tr>
          <tr><td colspan="2">Tuesday November 10, 2026</td></tr>
          <tr><td>7:30 am</td><td><a href="/release?rid=10">Consumer Price Index</a></td></tr>
        </tbody></table><p>All times are US Central Time.</p>'''
        events = calendar.parse_fred_calendar(html, 'us_cpi', calendar.FRED_CALENDAR_URL)
        self.assertEqual([e['datetime'] for e in events], ['2026-09-11T12:30:00+00:00', '2026-11-10T13:30:00+00:00'])
        self.assertEqual(events[0]['source'], 'BLS via FRED')
        with self.assertRaises(ValueError):
            calendar.parse_fred_calendar(html.replace('US Central Time', 'unknown time'), 'us_cpi', calendar.FRED_CALENDAR_URL)

    def test_blocked_bls_calendars_try_live_fred_before_stored_cache(self):
        expected = [{'source': 'BLS via FRED'}]
        with patch.object(calendar, 'download_text', side_effect=RuntimeError('blocked')), patch.object(calendar, 'fred_calendar_events', return_value=expected) as fallback:
            self.assertEqual(calendar.bls_events('us_cpi'), expected)
            fallback.assert_called_once_with('us_cpi')

    def test_boe_dst_and_provisional_dates(self):
        html = '<h2>2026 confirmed dates</h2><table><tr><td>Thursday 5 February</td></tr><tr><td>Thursday 6 August</td></tr></table><h2>2027 provisional dates</h2><table><tr><td>Thursday 4 February</td></tr></table>'
        events = calendar.parse_boe(html)
        self.assertIn('12:00:00+00:00', events[0]['datetime'])
        self.assertIn('11:00:00+00:00', events[1]['datetime'])
        self.assertEqual(events[2]['status'], 'provisional')

    def test_fomc_uses_final_meeting_day_and_cross_month(self):
        html = '<div class="panel"><h4 class="panel-heading">2026 FOMC Meetings</h4><div class="fomc-meeting"><div class="fomc-meeting__month">April/May</div><div class="fomc-meeting__date">30-1*</div></div></div>'
        self.assertEqual(calendar.parse_fomc(html)[0]['datetime'], '2026-05-01T18:00:00+00:00')

    def test_ecb_ignores_nonmonetary_and_first_day(self):
        html = '<main><dt>09/09/2026</dt><dd>Monetary policy meeting Day 1</dd><dt>10/09/2026</dt><dd>Monetary policy meeting Day 2</dd><dt>20/09/2026</dt><dd>Non-monetary policy meeting Day 2</dd></main>'
        events = calendar.parse_ecb(html)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['datetime'], '2026-09-10T12:15:00+00:00')

    def test_ons_release_title_aliases(self):
        html = '<a href="/release/a" data-gtm-release-date="20260915" data-gtm-release-time="07:00">UK Labour Market: August 2026</a><a href="/release/b" data-gtm-release-date="20260916" data-gtm-release-time="09:30">Private rent and house prices, UK: September 2026</a>'
        events = calendar.parse_ons_calendar(html)
        self.assertEqual([e['key'] for e in events], ['uk_labour', 'uk_hpi'])
        self.assertEqual(events[0]['datetime'], '2026-09-15T06:00:00+00:00')

    def test_ics_timezone_and_cancelled_events(self):
        content = 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:one\r\nSUMMARY:GDP (Advance Estimate)\r\nDTSTART;TZID=America/New_York:20261029T083000\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:two\r\nSUMMARY:GDP (Advance Estimate)\r\nSTATUS:CANCELLED\r\nDTSTART:20261030T123000Z\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'
        events = calendar.parse_ics(content, 'us_gdp', ['GDP ('], 'GDP', 'BEA', calendar.BEA_URL, 'growth')
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['datetime'], '2026-10-29T12:30:00+00:00')


if __name__ == '__main__':
    unittest.main()
