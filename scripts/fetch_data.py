"""
Fetch every series declared in series_config.SECTIONS and write JSON to data/.

Sources
-------
* FRED  — official macro statistics (API key preferred; public CSV fallback)
* Yahoo Finance — equities, commodities, FX (via yfinance, no key required)
* Official ONS, BIS, ECB, BoE, Eurostat and UK government endpoints

Output
------
data/<section>.json  — one file per dashboard section
data/events.json     — hand-curated event timeline
data/manifest.json   — global metadata (last_updated, success/failure counts)

Resilient by design: a single failing series does not abort the run.
Existing files are kept on partial failure (we merge new + old on disk).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from functools import lru_cache
import csv
import io
import math
from zoneinfo import ZoneInfo

import requests

# Allow running from repo root or from scripts/.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from series_config import SECTIONS, EVENTS  # noqa: E402
from data_quality import (SCHEMA_VERSION, validate_points, frequency_of, freshness,
                          period_label, compute_stats, yoy, write_json, to_ms)
from source_providers import (get, bis_cpi, bis_policy, boe_money, ecb_money,
                              euro_unemployment)

DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

FRED_API_KEY = os.environ.get("FRED_API_KEY", "").strip()
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
START_DATE = "1970-01-01"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fetch")


# ──────────────────────────────────────────────────────────────────────────
# Fetch helpers
# ──────────────────────────────────────────────────────────────────────────
def _to_ms(date_str: str) -> int:
    """Date-string (YYYY-MM-DD) -> UTC ms epoch."""
    return to_ms(date_str)


@lru_cache(maxsize=192)
def fetch_fred(series_id: str, frequency: str | None = None) -> list[list]:
    """Pull a series from FRED. Returns [[ts_ms, value], ...]."""
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": START_DATE,
    }
    if frequency:
        params["frequency"] = frequency
    if FRED_API_KEY:
        try:
            obs = get(FRED_URL, params=params).json().get('observations', [])
        except (requests.RequestException, ValueError):
            # Do not log the exception URL: it contains the API key.
            log.warning('FRED API unavailable for %s; trying its public CSV', series_id)
            obs = []
    else:
        obs = []
    if not obs:
        try:
            response = get('https://fred.stlouisfed.org/graph/fredgraph.csv', params={'id': series_id, 'cosd': START_DATE})
            rows = csv.DictReader(io.StringIO(response.text))
            obs = [{'date': r.get('observation_date', r.get('DATE')), 'value': r.get(series_id)} for r in rows]
        except (requests.RequestException, ValueError):
            log.warning('FRED CSV unavailable for %s', series_id)
            return []
    out: list[list] = []
    for o in obs:
        v = o.get("value")
        if v in (".", "", None):
            continue
        try:
            val = float(v)
        except (TypeError, ValueError):
            continue
        out.append([_to_ms(o["date"]), val])
    return out




# ── ONS (Office for National Statistics) time series ──
# Direct ONS data is typically 3+ months fresher than the OECD-aggregated
# equivalents on FRED. Pattern: ons.gov.uk/{topic_path}/timeseries/{id}/{dataset}/data
_ONS_MONTH = {'JAN':1,'FEB':2,'MAR':3,'APR':4,'MAY':5,'JUN':6,'JUL':7,'AUG':8,'SEP':9,'OCT':10,'NOV':11,'DEC':12}
_ONS_META = {}

@lru_cache(maxsize=32)
def fetch_ons(series_id: str, dataset: str, topic_path: str, frequency='m') -> list[list]:
    """Preserve the publisher's reporting period and release metadata."""
    uri = f"/{topic_path}/timeseries/{series_id.lower()}/{dataset.lower()}"
    url = f"https://www.ons.gov.uk{uri}/data"
    try:
        try:
            payload = get(url, headers={'Accept': 'application/json'}).json()
        except (requests.RequestException, ValueError):
            payload = get('https://api.beta.ons.gov.uk/v1/data', params={'uri': uri}).json()
    except (requests.RequestException, ValueError) as e:
        log.warning("ONS %s failed: %s", series_id, e)
        return []

    months = payload.get({'q': 'quarters', 'a': 'years'}.get(frequency, 'months')) or []
    out: list[list] = []
    labels = {}
    for obs in months:
        date_str = (obs.get("date") or "").strip()
        val_str  = (obs.get("value") or "").strip()
        if not date_str or not val_str:
            continue
        parts = date_str.split()
        if len(parts) not in (1, 2):
            continue
        try:
            year = int(parts[0])
            mnum = (int(parts[1][1:]) - 1) * 3 + 1 if frequency == 'q' else 1 if frequency == 'a' else _ONS_MONTH.get(parts[1].upper()[:3])
            if not mnum:
                continue
            val = float(val_str)
        except (ValueError, TypeError):
            continue
        iso = f"{year:04d}-{mnum:02d}-01"
        timestamp = _to_ms(iso)
        out.append([timestamp, val])
        labels[timestamp] = obs.get('label', '')
    out.sort(key=lambda r: r[0])
    if out:
        desc = payload.get('description', {})
        label = labels[out[-1][0]]
        parts = label.split(' ', 1)
        label = f'{parts[1].title()} {parts[0]}' if len(parts) == 2 else label
        next_release = None
        try:
            next_release = datetime.strptime(desc.get('nextRelease', ''), '%d %B %Y').date().isoformat()
        except ValueError:
            pass
        _ONS_META[(series_id, dataset, frequency)] = {
            'period_label': label, 'published_at': desc.get('releaseDate'),
            'next_release': next_release, 'source_url': f'https://www.ons.gov.uk{uri}',
            'frequency': frequency, 'period_type': desc.get('monthLabelStyle', frequency),
        }
    return out


_UK_HPI_CACHE: dict[str, list[list]] = {}

def fetch_uk_hpi_region(region_name: str) -> list[list]:
    """Fetch monthly UK HPI average prices for one region from Land Registry.

    The full UK HPI CSV (~35MB) is downloaded once per run and cached in
    ``_UK_HPI_CACHE`` keyed by region name. Recent ~6 months of URLs are
    probed to find the freshest published file.
    """
    if region_name in _UK_HPI_CACHE:
        return _UK_HPI_CACHE[region_name]
    if "_loaded" in _UK_HPI_CACHE:
        return _UK_HPI_CACHE.get(region_name, [])

    import csv as _csv
    import io as _io
    from datetime import date as _date

    today = _date.today()
    csv_text = None
    used_url = None
    for back in range(6):
        m = today.month - back
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        url = f"https://publicdata.landregistry.gov.uk/market-trend-data/house-price-index-data/UK-HPI-full-file-{y}-{m:02d}.csv"
        try:
            r = get(url, timeout=120, stream=False,
                             headers={"User-Agent": "Mozilla/5.0 MacroOps/1.0"})
            if r.status_code == 200 and len(r.content) > 1_000_000:
                csv_text = r.content.decode("utf-8", errors="replace")
                used_url = url
                break
        except requests.RequestException:
            continue

    if not csv_text:
        log.warning("UK HPI: no published CSV found in last 6 months")
        _UK_HPI_CACHE["_loaded"] = []
        return []

    log.info("UK HPI: loaded %s (%.1f MB)", used_url, len(csv_text) / 1e6)

    reader = _csv.DictReader(_io.StringIO(csv_text))
    by_region: dict[str, list[list]] = {}
    for row in reader:
        rname = row.get("RegionName", "").strip()
        if not rname:
            continue
        price = row.get("AveragePrice", "").strip()
        date_str = row.get("Date", "").strip()
        if not price or not date_str:
            continue
        try:
            d, m_, y_ = date_str.split("/")
            iso = f"{y_}-{m_.zfill(2)}-{d.zfill(2)}"
            ts = _to_ms(iso)
            v = float(price)
        except (ValueError, KeyError):
            continue
        by_region.setdefault(rname, []).append([ts, v])

    for k, v in by_region.items():
        v.sort(key=lambda r: r[0])
        _UK_HPI_CACHE[k] = v
    _UK_HPI_CACHE["_loaded"] = []  # marker
    log.info("UK HPI: parsed %d regions", len(by_region))
    return _UK_HPI_CACHE.get(region_name, [])


_UK_FUEL_CACHE: dict[str, list[list]] = {}

def fetch_uk_fuel(column: str) -> list[list]:
    """Scrape the gov.uk DESNZ weekly road fuel CSV and return one column.

    ``column`` is either ``"petrol"`` or ``"diesel"``.
    Returns [[ts_ms, pence_per_litre], ...] sorted by date.
    """
    if column in _UK_FUEL_CACHE:
        return _UK_FUEL_CACHE[column]

    page_url = "https://www.gov.uk/government/statistics/weekly-road-fuel-prices"
    try:
        r = get(page_url, timeout=30,
                         headers={"User-Agent": "Mozilla/5.0 MacroOps/1.0"})
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning("gov.uk fuel page fetch failed: %s", e)
        return []

    import re as _re
    m = _re.search(r"https://assets\.publishing\.service\.gov\.uk/media/[a-f0-9]+/[^\"]+\.csv", r.text)
    if not m:
        log.warning("could not find UK fuel CSV link")
        return []

    csv_url = m.group(0)
    try:
        r2 = get(csv_url, timeout=30,
                          headers={"User-Agent": "Mozilla/5.0 MacroOps/1.0"})
        r2.raise_for_status()
    except requests.RequestException as e:
        log.warning("UK fuel CSV fetch failed: %s", e)
        return []

    text = r2.content.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        return []

    header = [c.strip().lower() for c in rows[0]]
    # Find petrol / diesel pump-price columns
    petrol_idx = next((i for i, h in enumerate(header) if "ulsp" in h and "pump" in h), None)
    diesel_idx = next((i for i, h in enumerate(header) if "ulsd" in h and "pump" in h), None)

    petrol_data, diesel_data = [], []
    for row in rows[1:]:
        if len(row) < max(petrol_idx or 0, diesel_idx or 0) + 1:
            continue
        date_str = row[0].strip()
        # DD/MM/YYYY -> YYYY-MM-DD
        try:
            d, m_, y = date_str.split("/")
            iso = f"{y}-{m_.zfill(2)}-{d.zfill(2)}"
            ts = _to_ms(iso)
        except Exception:
            continue
        if petrol_idx is not None:
            try: petrol_data.append([ts, float(row[petrol_idx])])
            except Exception: pass
        if diesel_idx is not None:
            try: diesel_data.append([ts, float(row[diesel_idx])])
            except Exception: pass

    petrol_data.sort(key=lambda r: r[0])
    diesel_data.sort(key=lambda r: r[0])
    _UK_FUEL_CACHE["petrol"] = petrol_data
    _UK_FUEL_CACHE["diesel"] = diesel_data
    log.info("UK fuel CSV: %d petrol, %d diesel observations", len(petrol_data), len(diesel_data))
    return _UK_FUEL_CACHE.get(column, [])


_YAHOO_META = {}


def fetch_yahoo(ticker: str) -> list[list]:
    """Keep daily observations at their real trading dates, including history."""
    _YAHOO_META.pop(ticker, None)
    try:
        import yfinance as yf  # imported lazily so script still loads without it
    except ImportError:
        log.warning("yfinance not installed — skipping %s", ticker)
        return []

    try:
        instrument = yf.Ticker(ticker)
        df = instrument.history(period='max', interval='1d', auto_adjust=True, timeout=30, raise_errors=True)
    except Exception as e:  # network or yfinance internal
        log.warning("Yahoo %s failed: %s", ticker, e)
        return []

    if df is None or df.empty:
        return []

    # Yahoo's long-history cache can lag its recent-price endpoint by a day.
    # Refresh the overlapping daily tail, keeping provider revisions.
    try:
        import pandas as pd
        recent = instrument.history(period='1mo', interval='1d', auto_adjust=True, timeout=30, raise_errors=True)
        if recent is not None and not recent.empty:
            df = pd.concat([df, recent])
            df = df[~df.index.duplicated(keep='last')].sort_index()
    except Exception as exc:
        log.warning('Yahoo recent tail unavailable for %s: %s', ticker, type(exc).__name__)

    # yfinance may return MultiIndex columns when threads/multi-ticker is involved.
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)

    col = "Close" if "Close" in df.columns else df.columns[0]
    s = df[col].dropna()
    if s.empty:
        return []

    out: list[list] = []
    for ts, val in s.items():
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        # A daily bar belongs to the exchange's local trading date.
        ts_ms = _to_ms(ts.strftime('%Y-%m-%d'))
        if math.isfinite(v):
            out.append([ts_ms, v])
    if len(out) < 365:
        log.warning('Yahoo %s returned only %d daily observations; rejecting truncated history', ticker, len(out))
        return []
    try:
        meta = instrument.get_history_metadata()
        observed = datetime.fromtimestamp(meta['regularMarketTime'], timezone.utc)
        trading_day = observed.astimezone(ZoneInfo(meta['exchangeTimezoneName'])).date()
        timestamp = _to_ms(trading_day.isoformat())
        price = float(meta['regularMarketPrice'])
        if meta.get('symbol') == ticker and timestamp > out[-1][0] and math.isfinite(price) and observed <= datetime.now(timezone.utc) + timedelta(minutes=5):
            # A timestamped exchange quote can precede Yahoo's daily-bar cache.
            out.append([timestamp, price])
            _YAHOO_META[ticker] = {'latest_quote_at': observed.isoformat(timespec='seconds')}
    except Exception as exc:
        log.debug('Yahoo quote metadata unavailable for %s: %s', ticker, type(exc).__name__)
    return out


# ──────────────────────────────────────────────────────────────────────────
# Transforms & stats
# ──────────────────────────────────────────────────────────────────────────
def apply_transform(data: list[list], transform: str) -> list[list]:
    return yoy(data) if transform == 'yoy_pct' else data


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

def _date_str(ms: int) -> str:
    """ms epoch → YYYY-MM-DD (safe for pre-1970 dates on Windows)."""
    return (_EPOCH + timedelta(milliseconds=ms)).strftime("%Y-%m-%d")




# ──────────────────────────────────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────────────────────────────────
def fetch_one(s: dict, previous: dict | None = None) -> dict | None:
    """Fetch a single series and return the JSON-ready dict, or None on failure."""
    sid = s['id']
    providers = []
    def ons_result():
        dataset, freq = s.get('ons_dataset', 'lms'), s.get('freq', 'm')
        data = fetch_ons(s['ons'], dataset, s['ons_path'], freq)
        return data, {'source': f"ONS ({s['ons']})", **_ONS_META.get((s['ons'], dataset, freq), {})}

    if s.get('bis_cpi'):
        providers.append(('bis', lambda: bis_cpi(s['bis_cpi'])))
    if s.get('bis_policy'):
        providers.append(('bis', lambda: bis_policy(s['bis_policy'])))
    if s.get('boe_money'):
        providers.append(('boe', lambda: boe_money(s['boe_money'])))
    if s.get('ecb_money'):
        providers.append(('ecb', ecb_money))
    if s.get('eurostat'):
        providers.append(('eurostat', euro_unemployment))
    if s.get('ons'):
        providers.append(('ons', ons_result))
    if s.get('yahoo'):
        providers.append(('yahoo', lambda: (fetch_yahoo(s['yahoo']), {'source': f"Yahoo Finance ({s['yahoo']})", 'frequency': 'd', 'source_url': f"https://finance.yahoo.com/quote/{s['yahoo']}/history/", **_YAHOO_META.get(s['yahoo'], {})})))
    if s.get('fred'):
        providers.append(('fred', lambda: (fetch_fred(s['fred'], s.get('freq')), {'source': f"FRED ({s['fred']})", 'source_url': f"https://fred.stlouisfed.org/series/{s['fred']}"})))
    if s.get('uk_fuel'):
        providers.append(('uk_fuel', lambda: (fetch_uk_fuel(s['uk_fuel']), {'source': 'gov.uk DESNZ weekly road fuel prices', 'frequency': 'w', 'source_url': 'https://www.gov.uk/government/statistics/weekly-road-fuel-prices'})))
    if s.get('uk_hpi'):
        providers.append(('land_registry', lambda: (fetch_uk_hpi_region(s['uk_hpi']), {'source': 'HM Land Registry UK House Price Index', 'frequency': 'm', 'source_url': 'https://www.gov.uk/government/collections/uk-house-price-index-reports'})))

    best = None
    for method, provider in providers:
        try:
            log.info('  %s via %s', sid, method)
            raw, meta = provider()
            data = validate_points(raw)
            scale = s.get(f'{method}_scale', s.get('scale', 1))
            data = [[ts, value * scale] for ts, value in data]
            transform = s.get(f'{method}_transform', s.get('transform'))
            if transform:
                data = validate_points(apply_transform(data, transform))
            if len(data) < s.get('min_points', 2):
                raise ValueError('Insufficient history')
            if previous and previous.get('schema_version') == SCHEMA_VERSION and previous.get('history_version', 1) == s.get('history_version', 1):
                old = previous.get('data', [])
                if old and data[-1][0] < old[-1][0]:
                    raise ValueError('Provider returned an older endpoint than the stored data')
                if old and data[0][0] > old[0][0] + 100 * 86400000 and len(data) < len(old) * 0.8:
                    raise ValueError('Provider truncated the stored history')
            frequency = meta.get('frequency') or s.get('freq') or frequency_of(data)
            checked = datetime.now(timezone.utc).isoformat(timespec='seconds')
            result = {
                'id': sid, 'name': s['name'], 'region': s.get('region'), 'unit': s.get('unit'), 'note': s.get('note'),
                **meta, 'method': method, 'frequency': frequency, 'schema_version': SCHEMA_VERSION,
                'history_version': s.get('history_version', 1),
                'stats': compute_stats(data, frequency), 'data': data,
                'period_label': meta.get('period_label') or period_label(data, frequency),
                'last_checked': checked, 'last_success': checked, 'fetch_status': 'ok',
                'archived': bool(s.get('archived')), 'max_age_days': s.get('max_age_days', 150 if meta.get('period_type') == 'three month average' else {'d': 7, 'w': 21, 'm': 100, 'q': 230, 'a': 800}[frequency]),
            }
            result['freshness'] = freshness(result, s)
            if not best or data[-1][0] > best['data'][-1][0]:
                best = result
            if result['freshness'] in ('current', 'archived'):
                return result
            log.warning('  %s: source returned an overdue observation (%s)', sid, result['period_label'])
        except Exception as exc:
            # Network errors may contain credential-bearing URLs; log only their type.
            reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            log.warning('  %s via %s rejected: %s', sid, method, reason)
    return best


def load_existing(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def run() -> dict:
    """Fetch everything and write JSON files. Returns the manifest dict."""
    started = datetime.now(timezone.utc)
    old_manifest = load_existing(DATA_DIR / 'manifest.json')
    section_status = {k: {field: v.get(field, 0) for field in ('ok', 'fail', 'stale', 'archived')} for k, v in old_manifest.get('sections', {}).items()}
    total_ok = 0
    total_fail = 0

    only = os.environ.get("ONLY_SECTION", "").strip()  # for debugging
    skip = set(os.environ.get("SKIP_SECTIONS", "").split(","))

    for section_key, section_meta in SECTIONS.items():
        if only and only != section_key:
            continue
        if section_key in skip:
            continue

        log.info("── Section: %s ──", section_key)
        out_path = DATA_DIR / f"{section_key}.json"
        existing = load_existing(out_path)
        existing_series = existing.get("series", {}) if isinstance(existing, dict) else {}

        new_series: dict[str, Any] = {}
        ok, fail = 0, 0
        for s in section_meta["series"]:
            try:
                res = fetch_one(s, existing_series.get(s['id']))
            except Exception as e:  # pragma: no cover
                log.exception("Unhandled error on %s: %s", s.get("id"), e)
                res = None
            if res:
                new_series[s["id"]] = res
                ok += 1
            else:
                # Preserve previous data on failure.
                prev = existing_series.get(s["id"])
                if prev:
                    log.info("  ↺ keeping previous data for %s", s["id"])
                    prev = dict(prev)
                    # Legacy month-end bars in the future are not real observations.
                    valid = [p for p in prev.get('data', []) if _date_str(p[0]) <= started.date().isoformat()]
                    if valid:
                        prev['data'] = validate_points(valid)
                        prev['stats'] = compute_stats(prev['data'], prev.get('frequency'))
                        prev['last_checked'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
                        prev['last_success'] = prev.get('last_success')
                        prev['fetch_status'] = 'retained'
                        prev['freshness'] = freshness(prev, s)
                        new_series[s['id']] = prev
                fail += 1

        stale = sum(v.get('freshness') in ('stale', 'invalid', 'missing') for v in new_series.values())
        archived = sum(v.get('archived', False) for v in new_series.values())
        section_status[section_key] = {"ok": ok, "fail": fail, 'stale': stale, 'archived': archived}
        total_ok += ok
        total_fail += fail

        payload = {
            "meta": {
                "section": section_key,
                "title": section_meta["title"],
                "icon": section_meta["icon"],
                "blurb": section_meta["blurb"],
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "fetched_ok": ok,
                "fetched_fail": fail,
            },
            "series": new_series,
            "order": [s["id"] for s in section_meta["series"]],
        }
        write_json(out_path, payload)
        log.info("  wrote %s  (%d ok, %d fail)", out_path.name, ok, fail)

    # Events file
    events_payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "count": len(EVENTS),
        },
        "events": sorted(EVENTS, key=lambda e: e["date"]),
    }
    write_json(DATA_DIR / 'events.json', events_payload)
    log.info("Wrote events.json (%d events)", len(EVENTS))

    # Manifest
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duration_sec": round((datetime.now(timezone.utc) - started).total_seconds(), 1),
        "sections": {
            key: {
                "title": SECTIONS[key]["title"],
                "icon": SECTIONS[key]["icon"],
                "blurb": SECTIONS[key]["blurb"],
                "file": f"data/{key}.json",
                "series_count": len(SECTIONS[key]["series"]),
                **section_status.get(key, {"ok": 0, "fail": 0}),
            }
            for key in SECTIONS.keys()
        },
        'schema_version': SCHEMA_VERSION,
        "totals": {field: sum(x.get(field, 0) for x in section_status.values()) for field in ('ok', 'fail', 'stale', 'archived')},
    }
    write_json(DATA_DIR / 'manifest.json', manifest, indent=2)
    log.info(
        "DONE in %ss — %d ok, %d fail",
        manifest["duration_sec"],
        total_ok,
        total_fail,
    )
    return manifest


if __name__ == "__main__":
    run()
