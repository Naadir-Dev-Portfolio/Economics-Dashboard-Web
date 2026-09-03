"""Published release dates only. Failed sources retain explicitly verified dates.

Unannounced dates remain unknown. Cached and provisional entries retain their
status and verification date, including in the browser and calendar exports.
"""
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
import json
import logging
import os
import re

from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date
from icalendar import Calendar

from source_providers import get
from data_quality import write_json

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data'
UTC = timezone.utc
ET, UK, CET = (ZoneInfo(z) for z in ('America/New_York', 'Europe/London', 'Europe/Berlin'))
LOOKAHEAD_DAYS = 365
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
log = logging.getLogger('calendar')

FOMC_URL = 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'
BOE_URL = 'https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates'
ECB_URL = 'https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html'
ONS_URL = 'https://www.ons.gov.uk/releasecalendar'
BLS_URL = 'https://www.bls.gov/schedule/news_release/bls.ics'
BEA_URL = 'https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics'
CENSUS_URL = 'https://www.census.gov/economic-indicators/calendar-listview.html'
FRED_CALENDAR_URL = 'https://fred.stlouisfed.org/releases/calendar'
FRED_RELEASE_URL = 'https://api.stlouisfed.org/fred/release/dates'


def to_utc(day, clock, zone):
    return datetime.combine(day, clock, tzinfo=zone).astimezone(UTC)


def event(key, title, when, region, source, url, *, status='confirmed', tag='growth', description=''):
    if when.tzinfo is None:
        raise ValueError('Calendar event has no timezone')
    when = when.astimezone(UTC)
    return {
        'id': f'{key}-{when.date()}', 'key': key, 'title': title,
        'datetime': when.isoformat(), 'region': region, 'tag': tag,
        'source': source, 'source_url': url, 'status': status,
        'description': description or title,
        'verified_at': datetime.now(UTC).isoformat(timespec='seconds'), 'verification': 'live',
    }


def parse_fomc(html):
    soup = BeautifulSoup(html, 'html.parser')
    result = []
    for panel in soup.select('.panel'):
        heading = panel.select_one('.panel-heading')
        year_match = re.search(r'(20\d{2})\s+FOMC Meetings', heading.get_text(' ', strip=True) if heading else '')
        if not year_match:
            continue
        year = int(year_match[1])
        for row in panel.select('.fomc-meeting'):
            month_el, days_el = row.select_one('.fomc-meeting__month'), row.select_one('.fomc-meeting__date')
            if not month_el or not days_el:
                continue
            months = month_el.get_text(' ', strip=True).split('/')
            days = re.findall(r'\d+', days_el.get_text(' ', strip=True))
            if not days:
                continue
            try:
                day = parse_date(f'{months[-1]} {days[-1]} {year}').date()
            except (ValueError, OverflowError):
                continue
            result.append(event('fomc', 'FOMC Rate Decision', to_utc(day, time(14), ET), 'US', 'Federal Reserve', FOMC_URL, tag='monetary'))
    if 'each meeting date is tentative' in soup.get_text(' ', strip=True).lower():
        future = sorted((e for e in result if datetime.fromisoformat(e['datetime']) > datetime.now(UTC)), key=lambda e: e['datetime'])
        # The next meeting is confirmed at the preceding meeting; later dates
        # remain tentative under the Fed's published scheduling policy.
        for item in future[1:]:
            item['status'] = 'provisional'
    return result


def parse_boe(html):
    soup = BeautifulSoup(html, 'html.parser')
    result = []
    for heading in soup.select('h2, h3'):
        title = heading.get_text(' ', strip=True)
        year = re.search(r'(20\d{2})\s+(?:confirmed|provisional)\s+dates', title, re.I)
        if not year:
            continue
        table = heading.find_next('table')
        if table is None:
            continue
        for row in table.select('tr'):
            cells = row.select('td')
            if not cells:
                continue
            try:
                day = parse_date(f"{cells[0].get_text(' ', strip=True)} {year[1]}").date()
            except ValueError:
                continue
            result.append(event('boe_mpc', 'BoE Monetary Policy Decision', to_utc(day, time(12), UK), 'UK', 'Bank of England', BOE_URL, tag='monetary', status='provisional' if 'provisional' in title.lower() else 'confirmed'))
    return result


def parse_ecb(html):
    result = []
    for term in BeautifulSoup(html, 'html.parser').select('main dt'):
        detail = term.find_next_sibling('dd')
        text = detail.get_text(' ', strip=True).lower() if detail else ''
        if 'monetary policy meeting' not in text or 'day 2' not in text or 'non-monetary' in text:
            continue
        day = datetime.strptime(term.get_text(strip=True), '%d/%m/%Y').date()
        result.append(event('ecb_meeting', 'ECB Rate Decision', to_utc(day, time(14, 15), CET), 'EU', 'European Central Bank', ECB_URL, tag='monetary'))
    return result


def parse_ics(content, key, needles, title, source, url, tag):
    result = []
    for component in Calendar.from_ical(content).walk('VEVENT'):
        summary = str(component.get('SUMMARY', ''))
        if not any(n.lower() in summary.lower() for n in needles):
            continue
        if str(component.get('STATUS', '')).upper() == 'CANCELLED' or not component.get('DTSTART'):
            continue
        when = component.decoded('DTSTART')
        if not isinstance(when, datetime):
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=ET)
        result.append(event(key, title, when, 'US', source, url, tag=tag, description=summary))
    return result


@lru_cache(maxsize=16)
def download_text(url):
    return get(url, timeout=30).text


BLS_TYPES = {
    'us_nfp': ('Employment Situation', 'US Non-Farm Payrolls', 'employment', 'empsit'),
    'us_cpi': ('Consumer Price Index', 'US CPI Release', 'inflation', 'cpi'),
    'us_ppi': ('Producer Price Index', 'US PPI Release', 'inflation', 'ppi'),
}
FRED_RELEASES = {'us_nfp': 50, 'us_cpi': 10, 'us_ppi': 46}


def parse_fred_calendar(html, key, url):
    """FRED publishes source release dates in US Central time, not ingestion times."""
    soup = BeautifulSoup(html, 'html.parser')
    if 'All times are US Central Time.' not in soup.get_text(' ', strip=True):
        raise ValueError('FRED calendar timezone could not be verified')
    link = soup.select_one(f'a[href="/release?rid={FRED_RELEASES[key]}"]')
    table = link.find_parent('table') if link else None
    if table is None:
        return []
    _, title, tag, _ = BLS_TYPES[key]
    result, day = [], None
    for row in table.select('tbody tr'):
        cells = row.select('td')
        if len(cells) == 1:
            day = None
            try:
                day = datetime.strptime(cells[0].get_text(' ', strip=True), '%A %B %d, %Y').date()
            except ValueError:
                continue
        elif len(cells) == 2 and day and cells[1].select_one(f'a[href="/release?rid={FRED_RELEASES[key]}"]'):
            try:
                clock = datetime.strptime(cells[0].get_text(' ', strip=True), '%I:%M %p').time()
            except ValueError:
                continue
            result.append(event(key, title, to_utc(day, clock, ZoneInfo('America/Chicago')),
                                'US', 'BLS via FRED', url, tag=tag,
                                description=f'{title}. Official BLS release schedule republished by the Federal Reserve.'))
    return result


def fred_calendar_events(key):
    now = datetime.now(UTC)
    params = {'rid': FRED_RELEASES[key], 'vs': now.replace(day=1).date().isoformat(),
              've': (now + timedelta(days=LOOKAHEAD_DAYS)).date().isoformat()}
    url = FRED_CALENDAR_URL + '?' + urlencode(params)
    api_key = os.environ.get('FRED_API_KEY', '').strip()
    if api_key:
        try:
            response = get(FRED_RELEASE_URL, params={
                'api_key': api_key, 'file_type': 'json', 'release_id': FRED_RELEASES[key],
                'realtime_start': params['vs'], 'realtime_end': params['ve'],
                'include_release_dates_with_no_data': 'true', 'sort_order': 'asc', 'limit': 1000,
            }, timeout=20).json()
            _, title, tag, _ = BLS_TYPES[key]
            result = []
            for row in response.get('release_dates', []):
                if row.get('release_id') != FRED_RELEASES[key]:
                    continue
                day = datetime.strptime(row['date'], '%Y-%m-%d').date()
                # These three BLS releases are published at 08:30 Eastern.
                # The API supplies announced dates; no recurrence is inferred.
                result.append(event(key, title, to_utc(day, time(8, 30), ET),
                                    'US', 'BLS via FRED', url, tag=tag,
                                    description=f'{title}. BLS release date from the Federal Reserve release API; scheduled for 08:30 Eastern.'))
            if any(datetime.fromisoformat(e['datetime']) > now for e in result):
                return result
        except Exception as exc:
            # Exception URLs can contain the credential, so log only the type.
            log.info('%s: FRED release API unavailable (%s); checking public calendar', key, type(exc).__name__)
    return parse_fred_calendar(download_text(url), key, url)


def bls_events(key):
    needle, title, tag, path = BLS_TYPES[key]
    try:
        found = parse_ics(download_text(BLS_URL), key, [needle], title, 'BLS', BLS_URL, tag)
        if any(datetime.fromisoformat(e['datetime']) > datetime.now(UTC) for e in found):
            return found
    except Exception:
        pass
    url = f'https://www.bls.gov/schedule/news_release/{path}.htm'
    result = []
    try:
        soup = BeautifulSoup(download_text(url), 'html.parser')
        for row in soup.select('tr'):
            cells = row.select('td')
            if len(cells) < 3:
                continue
            try:
                when = parse_date(cells[1].get_text(' ', strip=True) + ' ' + cells[2].get_text(' ', strip=True)).replace(tzinfo=ET)
                result.append(event(key, title, when, 'US', 'BLS', url, tag=tag))
            except ValueError:
                continue
    except Exception as exc:
        log.info('%s: direct BLS schedule unavailable (%s); checking FRED calendar', key, type(exc).__name__)
    if any(datetime.fromisoformat(e['datetime']) > datetime.now(UTC) for e in result):
        return result
    return fred_calendar_events(key)


ONS_TYPES = {
    'uk_cpi': (('consumer price inflation, uk:',), 'UK CPI Release', 'inflation'),
    'uk_labour': (('uk labour market:', 'uk labour market '), 'UK Labour Market', 'employment'),
    'uk_gdp': (('gdp monthly estimate, uk:',), 'UK Monthly GDP', 'growth'),
    'uk_retail': (('retail sales, great britain:', 'retail sales; great britain:'), 'UK Retail Sales', 'growth'),
    'uk_hpi': (('private rent and house prices, uk:', 'uk house price index:'), 'UK House Price Index', 'housing'),
}


def parse_ons_calendar(html):
    soup = BeautifulSoup(html, 'html.parser')
    result = []
    for link in soup.select('a[data-gtm-release-date]'):
        title = link.get_text(' ', strip=True)
        for key, (needles, name, tag) in ONS_TYPES.items():
            if not any(needle in title.lower() for needle in needles):
                continue
            day = datetime.strptime(link['data-gtm-release-date'], '%Y%m%d').date()
            clock = time.fromisoformat(link['data-gtm-release-time'])
            result.append(event(key, name, to_utc(day, clock, UK), 'UK', 'ONS', 'https://www.ons.gov.uk' + link['href'], tag=tag, description=title))
    return result


@lru_cache(maxsize=1)
def ons_events():
    result = []
    for page in range(1, 4):
        # ONS currently labels its chronological order "date-newest".
        url = f'{ONS_URL}?release-type=type-upcoming&sort=date-newest&limit=100&page={page}'
        html = download_text(url)
        result.extend(parse_ons_calendar(html))
        if len(BeautifulSoup(html, 'html.parser').select('a[data-gtm-release-date]')) < 100:
            break
    return result


def parse_census(html):
    result = []
    for row in BeautifulSoup(html, 'html.parser').select('tr'):
        if 'Advance Monthly Sales for Retail and Food Services' not in row.get_text():
            continue
        date_cell = row.select_one('td[sorttable_customkey]')
        if not date_cell:
            continue
        stamp = date_cell['sorttable_customkey']
        if re.fullmatch(r'\d{12}', stamp):
            when = datetime.strptime(stamp, '%Y%m%d%H%M').replace(tzinfo=ET)
            result.append(event('us_retail', 'US Retail Sales', when, 'US', 'US Census Bureau', CENSUS_URL))
    return result


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def run():
    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    horizon = now + timedelta(days=LOOKAHEAD_DAYS)
    previous = read_json(DATA_DIR / 'calendar.json')
    seed = read_json(ROOT / 'scripts/calendar_verified.json')
    cached = previous.get('events', [])
    for key, dates in seed.get('schedules', {}).items():
        _, title, tag, path = BLS_TYPES[key]
        for day in dates:
            item = event(key, title, to_utc(datetime.fromisoformat(day).date(), time(8, 30), ET), 'US', 'BLS', f'https://www.bls.gov/schedule/news_release/{path}.htm', tag=tag)
            item['verified_at'] = seed['verified_at']
            cached.append(item)
    sources = {
        'fomc': (FOMC_URL, lambda: parse_fomc(download_text(FOMC_URL))),
        'boe_mpc': (BOE_URL, lambda: parse_boe(download_text(BOE_URL))),
        'ecb_meeting': (ECB_URL, lambda: parse_ecb(download_text(ECB_URL))),
        **{key: (BLS_URL, lambda key=key: bls_events(key)) for key in BLS_TYPES},
        **{key: (ONS_URL, lambda key=key: [e for e in ons_events() if e['key'] == key]) for key in ONS_TYPES},
        'us_pce': (BEA_URL, lambda: parse_ics(download_text(BEA_URL), 'us_pce', ['Personal Income and Outlays'], 'US PCE Price Index', 'BEA', BEA_URL, 'inflation')),
        'us_gdp': (BEA_URL, lambda: parse_ics(download_text(BEA_URL), 'us_gdp', ['GDP (Advance Estimate)', 'GDP (Second Estimate)', 'GDP (Third Estimate)'], 'US GDP Release', 'BEA', BEA_URL, 'growth')),
        'us_retail': (CENSUS_URL, lambda: parse_census(download_text(CENSUS_URL))),
    }
    events, reports = [], {}
    for key, (url, fetch) in sources.items():
        status = 'ok'
        try:
            found = fetch()
            if not any(datetime.fromisoformat(e['datetime']) > now for e in found):
                raise ValueError('No upcoming published dates')
        except Exception as exc:
            log.warning('%s: %s; retaining only previously verified dates', key, type(exc).__name__)
            found = [{**e, 'verification': 'cached'} for e in cached if e.get('key') == key and e.get('verified_at') and e.get('status') in ('confirmed', 'provisional')]
            status = 'cached' if any(datetime.fromisoformat(e['datetime']) > now for e in found) else 'unavailable'
        unique = {}
        for e in found:
            if start <= datetime.fromisoformat(e['datetime']) <= horizon:
                old = unique.get(e['id'])
                if not old or e['verified_at'] > old['verified_at']:
                    unique[e['id']] = e
        selected = list(unique.values())
        events.extend(selected)
        reports[key] = {'status': status, 'source_url': url, 'count': len(selected),
                        'providers': sorted({e['source'] for e in selected}),
                        'last_verified': max((e['verified_at'] for e in selected), default=None),
                        'through': max((e['datetime'][:10] for e in selected), default=None)}
        log.info('%s: %s, %s dates', key, status, len(selected))
    events.sort(key=lambda e: e['datetime'])
    payload = {'meta': {'generated_at': now.isoformat(timespec='seconds'), 'schema_version': 2,
                        'lookahead_days': LOOKAHEAD_DAYS, 'count': len(events), 'sources': reports,
                        'unconfirmed_keys': ['us_m2', 'uk_fuel', 'eu_cpi'],
                        'policy': 'Published dates only; missing dates are not estimated.'}, 'events': events}
    write_json(DATA_DIR / 'calendar.json', payload)
    return payload


if __name__ == '__main__':
    run()
