"""Structured official-source adapters used by the refresh pipeline."""
import csv
import io
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as browser_requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from data_quality import to_ms


def redact_credentials(record):
    # urllib3 retry warnings can include the full credential-bearing query URL.
    record.msg = re.sub(r'([?&]api_key=)[^&\s\'"<>]+', r'\1[REDACTED]', record.getMessage())
    record.args = ()
    return True


logging.getLogger('urllib3.connectionpool').addFilter(redact_credentials)

SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'Mozilla/5.0 MacroOps/2.0 (public economic data)'})
SESSION.mount('https://', HTTPAdapter(max_retries=Retry(
    total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['GET'],
    respect_retry_after_header=False,
)))


def get(url, **kwargs):
    response = SESSION.get(url, timeout=kwargs.pop('timeout', 45), **kwargs)
    response.raise_for_status()
    return response


@lru_cache(maxsize=128)
def csv_rows(url):
    return list(csv.DictReader(io.StringIO(get(url, timeout=90).content.decode('utf-8-sig'))))


def period_timestamp(period):
    if '-Q' in period:
        year, quarter = period.split('-Q')
        return to_ms(f'{year}-{(int(quarter) - 1) * 3 + 1:02d}-01')
    if len(period) == 7:
        period += '-01'
    if len(period) == 4:
        period += '-01-01'
    return to_ms(period)


def sdmx_points(rows, filters=None):
    out = []
    for row in rows:
        if any(row.get(k) != v for k, v in (filters or {}).items()):
            continue
        if str(row.get('OBS_VALUE', '')).strip().lower() in ('none', '', '.', 'nan', 'na'):
            continue
        out.append([period_timestamp(row['TIME_PERIOD']), float(row['OBS_VALUE'])])
    return sorted(out)


def bis_cpi(country):
    # 771 is year-on-year percent change; 628 is the index and must not be mixed in.
    url = 'https://stats.bis.org/api/v1/data/WS_LONG_CPI/M.JP+DE+FR+CA+AU.771?format=csv'
    data = sdmx_points(csv_rows(url), {'REF_AREA': country, 'UNIT_MEASURE': '771'})
    return data, {'source': f'BIS national CPI ({country}, YoY)', 'source_url': 'https://data.bis.org/topics/CPI', 'frequency': 'm'}


def bis_policy(country):
    url = 'https://stats.bis.org/api/v1/data/WS_CBPOL/D.GB+JP+CA+AU?format=csv&startPeriod=1970-01-01&detail=dataonly'
    return sdmx_points(csv_rows(url), {'REF_AREA': country}), {
        'source': f'BIS central bank policy rate ({country})', 'source_url': 'https://data.bis.org/topics/CBPOL', 'frequency': 'd',
    }


RBA_CASH_RATE_URL = 'https://www.rba.gov.au/statistics/cash-rate/'


def rba_cash_rate_points(html, through=None):
    """Expand the RBA's effective-date table into a daily target-rate series."""
    through = through or datetime.now(timezone.utc).date()
    decisions = {}
    soup = BeautifulSoup(html, 'html.parser')
    for row in soup.select('table tbody tr'):
        cells = row.find_all(['th', 'td'], recursive=False)
        if len(cells) < 3:
            continue
        try:
            effective = datetime.strptime(cells[0].get_text(' ', strip=True), '%d %b %Y').date()
        except ValueError:
            continue
        target = cells[2].get_text(' ', strip=True).replace(',', '')
        if effective <= through and re.fullmatch(r'[+-]?\d+(?:\.\d+)?', target):
            decisions[effective] = float(target)
    ordered = sorted(decisions.items())
    if len(ordered) < 20:
        raise ValueError('RBA cash-rate table did not contain enough history')
    if (through - ordered[-1][0]).days > 90:
        raise ValueError('RBA cash-rate decision table is overdue')

    data = []
    decision = 0
    current = ordered[0][1]
    day = ordered[0][0]
    while day <= through:
        while decision + 1 < len(ordered) and ordered[decision + 1][0] <= day:
            decision += 1
            current = ordered[decision][1]
        data.append([to_ms(day.isoformat()), current])
        day += timedelta(days=1)
    return data


def rba_cash_rate():
    response = None
    for attempt in range(3):
        try:
            response = browser_requests.get(RBA_CASH_RATE_URL, impersonate='chrome', timeout=90, headers={
                'Accept': 'text/html,application/xhtml+xml',
                'Referer': 'https://www.rba.gov.au/statistics/',
            })
            response.raise_for_status()
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return rba_cash_rate_points(response.text), {
        'source': 'Reserve Bank of Australia cash rate target',
        'source_url': RBA_CASH_RATE_URL,
        'frequency': 'd',
    }


def boe_money(code):
    from datetime import datetime
    url = ('https://www.bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp?csv.x=yes'
           f'&Datefrom=01/Jan/1970&Dateto=now&SeriesCodes={code}&UsingCodes=Y&CSVF=TN&VPD=Y&VFD=N')
    data = []
    for row in csv_rows(url):
        if row.get(code) not in ('', None):
            dt = datetime.strptime(row['DATE'], '%d %b %Y').replace(day=1)
            data.append([to_ms(dt.date().isoformat()), float(row[code])])
    return data, {'source': f'Bank of England ({code})', 'source_url': url, 'frequency': 'm'}


def ecb_money():
    url = 'https://data-api.ecb.europa.eu/service/data/BSI/M.U2.Y.V.M30.X.1.U2.2300.Z01.E?format=csvdata'
    rows = csv_rows(url)
    if rows and any(r.get('UNIT_MULT') != '6' for r in rows):
        raise ValueError('ECB M3 no longer reports EUR millions')
    return [[ts, v / 1000] for ts, v in sdmx_points(rows)], {
        'source': 'ECB M3 (seasonally adjusted)', 'source_url': url, 'frequency': 'm',
    }


def euro_unemployment():
    url = ('https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_m'
           '?lang=EN&geo=EA21&sex=T&age=TOTAL&unit=PC_ACT&s_adj=SA')
    payload = get(url).json()
    # This query has exactly one category on every axis except time.
    if any(size != 1 for axis, size in zip(payload['id'], payload['size']) if axis != 'time'):
        raise ValueError('Eurostat query returned multiple series')
    indices = payload['dimension']['time']['category']['index']
    values = payload['value']
    data = [[period_timestamp(period), float(values[str(index)])] for period, index in indices.items() if str(index) in values]
    return sorted(data), {'source': 'Eurostat unemployment (EA21, SA)', 'source_url': url, 'frequency': 'm'}
