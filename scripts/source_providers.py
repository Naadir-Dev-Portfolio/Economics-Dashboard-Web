"""Structured official-source adapters used by the refresh pipeline."""
import csv
import io
import logging
import re
from functools import lru_cache

import requests
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
