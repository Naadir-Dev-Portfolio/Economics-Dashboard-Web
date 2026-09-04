"""Build source health from individual observations, not file timestamps."""
from datetime import datetime, timezone
from pathlib import Path
import json
import logging

from data_quality import freshness, write_json
from series_config import SECTIONS

DATA = Path(__file__).resolve().parent.parent / 'data'
UTC = timezone.utc
log = logging.getLogger('health')

SOURCE_SPECS = {
    'fred': ('FRED', 'Federal Reserve Economic Data', 'https://fred.stlouisfed.org/', 'API with public CSV fallback.'),
    'yahoo': ('Yahoo Finance', 'Yahoo Finance daily history', 'https://finance.yahoo.com/', 'Daily market observations; exchange holidays do not create new observations.'),
    'ons': ('ONS', 'Office for National Statistics', 'https://www.ons.gov.uk/', 'Official reporting periods, publication dates and next releases are retained.'),
    'bis': ('BIS', 'Bank for International Settlements', 'https://data.bis.org/', 'National consumer prices and daily central-bank policy rates. Policy-rate observations are published weekly, with a 14-day observation-age allowance; successful refreshes are still required within 36 hours.'),
    'boe': ('Bank of England', 'Bank of England monetary statistics', 'https://www.bankofengland.co.uk/', 'Structured monetary-statistics CSV.'),
    'ecb': ('ECB', 'European Central Bank monetary statistics', 'https://data.ecb.europa.eu/', 'Seasonally adjusted euro-area M3.'),
    'eurostat': ('Eurostat', 'European statistical office', 'https://ec.europa.eu/eurostat/', 'Euro-area unemployment, seasonally adjusted.'),
    'uk_fuel': ('UK Fuel (DESNZ)', 'Department for Energy Security and Net Zero', 'https://www.gov.uk/government/statistics/weekly-road-fuel-prices', 'Weekly road-fuel observations.'),
    'land_registry': ('UK House Prices', 'HM Land Registry', 'https://www.gov.uk/government/collections/uk-house-price-index-reports', 'Monthly observations published with a reporting lag.'),
}

RUNTIME_SOURCES = [
    {'id': 'coingecko', 'name': 'CoinGecko', 'url': 'https://www.coingecko.com/', 'notes': 'Optional crypto quotes, polled once per minute while visible. Rate limits trigger progressively longer retries; timestamped snapshots remain available.'},
    {'id': 'tradingview', 'name': 'TradingView', 'url': 'https://www.tradingview.com/', 'notes': 'Optional embedded market chart. Loading the iframe does not verify its quotes.'},
]


def load(name):
    try:
        return json.loads((DATA / name).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def hours_since(iso, now=None):
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        return ((now or datetime.now(UTC)) - dt.astimezone(UTC)).total_seconds() / 3600
    except (ValueError, TypeError):
        return None


def primary_method(config):
    for field, method in [('bis_cpi', 'bis'), ('bis_policy', 'bis'), ('boe_money', 'boe'),
                          ('ecb_money', 'ecb'), ('eurostat', 'eurostat'), ('ons', 'ons'),
                          ('yahoo', 'yahoo'), ('fred', 'fred'), ('uk_fuel', 'uk_fuel'),
                          ('uk_hpi', 'land_registry')]:
        if config.get(field):
            return method
    return 'unknown'


def build_series_sources(now=None):
    now = now or datetime.now(UTC)
    buckets = {}
    for section, spec in SECTIONS.items():
        series = load(section + '.json').get('series', {})
        for config in spec['series']:
            item = series.get(config['id'], {})
            method = item.get('method') or primary_method(config)
            bucket = buckets.setdefault(method, {
                'expected': 0, 'delivered': 0, 'available': 0, 'stale': 0,
                'retained': 0, 'archived': 0, 'missing': 0, 'issues': [],
                'last_fetch': None, 'latest_data': None,
            })
            if item.get('data'):
                bucket['available'] += 1
            for field, value in [('last_fetch', item.get('last_checked')),
                                 ('latest_data', item.get('stats', {}).get('last_date'))]:
                if value and (not bucket[field] or value > bucket[field]):
                    bucket[field] = value
            if config.get('archived'):
                bucket['archived'] += 1
                continue
            bucket['expected'] += 1
            state = freshness(item, config, now)
            age = hours_since(item.get('last_success'), now)
            reasons = []
            if state in ('missing', 'invalid'):
                bucket['missing'] += 1
                reasons.append(state)
            elif state == 'stale':
                bucket['stale'] += 1
                reasons.append('overdue observation')
            if item.get('fetch_status') == 'retained':
                bucket['retained'] += 1
                reasons.append('fetch failed; previous data retained')
            elif age is None or age > 36:
                reasons.append('refresh overdue')
            if reasons:
                bucket['issues'].append({'id': config['id'], 'section': section,
                                         'name': config['name'], 'reason': '; '.join(reasons),
                                         'period': item.get('period_label'), 'last_success': item.get('last_success')})
            else:
                bucket['delivered'] += 1
    result = []
    for method, bucket in buckets.items():
        name, full_name, url, notes = SOURCE_SPECS.get(method, (method, method, '', 'Unclassified source.'))
        status = 'ok' if bucket['delivered'] == bucket['expected'] else 'warning' if bucket['delivered'] else 'error'
        result.append({'id': method, 'name': name, 'full_name': full_name, 'url': url,
                       'type': 'Scheduled data fetch', 'icon': '', 'status': status, **bucket,
                       'notes': notes + f" {bucket['archived']} historical-only series excluded from current-data counts."})
    return result


def build_calendar(now=None):
    now = now or datetime.now(UTC)
    payload = load('calendar.json')
    meta = payload.get('meta', {})
    reports = meta.get('sources', {})
    issues = []
    for key, source in reports.items():
        future = [e for e in payload.get('events', []) if e.get('key') == key and datetime.fromisoformat(e['datetime']) > now]
        if source.get('status') != 'ok' or not future:
            issues.append({'name': key, 'reason': 'verified cache' if future else 'no published future dates',
                           'period': source.get('through'), 'last_success': source.get('last_verified')})
    age = hours_since(meta.get('generated_at'), now)
    status = 'error' if not reports or age is None or age > 72 else 'warning' if issues or age > 36 else 'ok'
    return {'id': 'calendar', 'name': 'Economic Calendar', 'full_name': 'Official release calendars',
            'type': 'Scheduled calendar fetch', 'url': '', 'icon': '', 'status': status,
            'delivered': len(reports) - len(issues), 'expected': len(reports),
            'last_fetch': meta.get('generated_at'), 'issues': issues,
            'notes': 'Published dates only. Cached and provisional entries retain their verification status; unannounced dates are not estimated.'}


def build_news(now=None):
    payload = load('news.json')
    meta = payload.get('meta', {})
    subs = meta.get('by_source', {})
    reports = meta.get('feed_status', {})
    age = hours_since(meta.get('generated_at'), now)
    alive = sum(report.get('status') == 'ok' for report in reports.values()) if reports else sum(bool(v) for v in subs.values())
    expected = len(reports or subs)
    issues = [{'name': name, 'reason': report.get('error', 'Feed unavailable'), 'last_success': report.get('last_success')}
              for name, report in reports.items() if report.get('status') != 'ok']
    status = 'error' if not alive or age is None or age > 24 else 'warning' if age > 3 or alive < expected else 'ok'
    return {'id': 'news', 'name': 'News (RSS)', 'full_name': 'RSS news feeds', 'url': '', 'icon': '',
            'type': 'Hourly news fetch', 'last_fetch': meta.get('generated_at'), 'status': status,
            'delivered': alive, 'expected': expected, 'sub_sources': subs, 'feed_status': reports, 'issues': issues,
            'notes': f"{len(payload.get('items', []))} articles. Feed health measures successful HTTP/XML responses, not article count; failed feeds retain previously fetched headlines with original timestamps."}


def build():
    sources = build_series_sources() + [build_calendar(), build_news()]
    sources += [{**s, 'runtime': True, 'type': 'Optional browser feed'} for s in RUNTIME_SOURCES]
    totals = {key: sum(s.get('status') == key for s in sources) for key in ('ok', 'warning', 'error')}
    totals.update({'runtime': len(RUNTIME_SOURCES), 'total': len(sources)})
    out = {'generated_at': datetime.now(UTC).isoformat(timespec='seconds'), 'schema_version': 2,
           'totals': totals, 'sources': sources}
    write_json(DATA / 'health.json', out, indent=2)
    print(f"Health: {totals['ok']} healthy, {totals['warning']} warnings, {totals['error']} errors.")
    return out


if __name__ == '__main__':
    build()
