"""
Fetch every series declared in series_config.SECTIONS and write JSON to data/.

Sources
-------
* FRED  — official macro statistics (requires FRED_API_KEY env var)
* Yahoo Finance — equities, commodities, FX (via yfinance, no key required)

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
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

# Allow running from repo root or from scripts/.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from series_config import SECTIONS, EVENTS  # noqa: E402

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
    dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def fetch_fred(series_id: str, frequency: str | None = None) -> list[list]:
    """Pull a series from FRED. Returns [[ts_ms, value], ...]."""
    if not FRED_API_KEY:
        log.warning("FRED_API_KEY not set — skipping %s", series_id)
        return []
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": START_DATE,
    }
    if frequency:
        params["frequency"] = frequency
    for attempt in range(3):
        try:
            r = requests.get(FRED_URL, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(2 + attempt * 2)
                continue
            r.raise_for_status()
            break
        except requests.RequestException as e:
            log.warning("FRED %s attempt %d failed: %s", series_id, attempt + 1, e)
            time.sleep(1 + attempt)
    else:
        return []

    obs = r.json().get("observations", [])
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


# ── Bank of England Bank Rate (the policy rate) ──
# We previously used FRED's INTGSBGBM193N which (a) was actually a 20-year
# gilt yield, not the policy rate, and (b) stopped updating in mid-2025
# when the IMF discontinued it. So we now fetch from the BoE directly.
#
# RESILIENCE: three independent strategies, tried in order. Each can fail
# without the dashboard going blank (we keep previous data via the
# pipeline's preserve-on-failure logic):
#
#   1. Bank-Rate.asp strict scrape — fastest, exact regex with align=
#   2. Bank-Rate.asp loose scrape  — same page, attribute-agnostic regex
#                                    (survives a CSS/layout refresh as long
#                                     as the table cells still exist)
#   3. IADB CSV endpoint           — completely different URL/format,
#                                    structured CSV (DATE,VALUE), daily
#                                    granularity for IUDBEDR series
#
# Each result is validated: ≥10 observations, latest rate 0-25%, latest
# observation within the last 24 months. Strategies that produce data
# failing the sanity check are skipped rather than trusted.
_BOE_MONTHS = {'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,
               'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12}
_BOE_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
_BOE_HTML_URL = "https://www.bankofengland.co.uk/boeapps/database/Bank-Rate.asp"
_BOE_CSV_URL  = ("https://www.bankofengland.co.uk/boeapps/iadb/"
                 "fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/1975&Dateto=now"
                 "&SeriesCodes=IUDBEDR&UsingCodes=Y&CSVF=TN&VPD=Y&VFD=N")

_boe_html_cache: dict[str, str] = {}


def _boe_fetch_html() -> str:
    """Fetch the Bank-Rate.asp page once per process and cache it."""
    if "html" not in _boe_html_cache:
        try:
            r = requests.get(_BOE_HTML_URL, timeout=30,
                             headers={"User-Agent": _BOE_UA})
            r.raise_for_status()
            _boe_html_cache["html"] = r.text
        except requests.RequestException as e:
            log.warning("BoE Bank-Rate.asp fetch failed: %s", e)
            _boe_html_cache["html"] = ""
    return _boe_html_cache["html"]


def _boe_parse_2digit_year(yy_or_yyyy: str) -> int | None:
    """'25' → 2025, '95' → 1995, '2025' → 2025. Returns None if unparseable."""
    try:
        n = int(yy_or_yyyy)
    except (TypeError, ValueError):
        return None
    if n < 100:
        # Two-digit: <50 → 2000s, else 1900s. Handles 1950-2049 unambiguously,
        # which covers every observation in BoE history (oldest table row is 1975).
        return 2000 + n if n < 50 else 1900 + n
    return n


def _boe_change_points_from_pairs(pairs: list[tuple]) -> list[tuple]:
    """Turn (dd, mon, yy, rate) tuples into [(date, float), ...] sorted oldest first."""
    from datetime import date as _date
    out: list[tuple] = []
    for dd, mon, yy, rate in pairs:
        m = _BOE_MONTHS.get(mon)
        if not m:
            continue
        year = _boe_parse_2digit_year(yy)
        if year is None:
            continue
        try:
            out.append((_date(year, m, int(dd)), float(rate)))
        except (ValueError, TypeError):
            continue
    out.sort()
    return out


def _boe_strategy_strict_html() -> list[tuple]:
    """Tightest pattern — `<td align="left">DATE</td><td align="right">RATE</td>`.
    Fastest and most specific; first to try."""
    html = _boe_fetch_html()
    if not html:
        return []
    import re as _re
    pairs = _re.findall(
        r'<td align="left">\s*(\d{1,2})\s+([A-Z][a-z]{2})\s+(\d{2})\s*</td>\s*'
        r'<td align="right">\s*(\d+(?:\.\d+)?)\s*</td>',
        html,
    )
    return _boe_change_points_from_pairs(pairs)


def _boe_strategy_loose_html() -> list[tuple]:
    """Attribute-agnostic pattern — any pair of `<td>DATE</td>...<td>RATE</td>`.
    Survives a CSS refresh that strips `align=` attributes or adds classes."""
    html = _boe_fetch_html()
    if not html:
        return []
    import re as _re
    # Allow 2- or 4-digit year, any td attributes, optional whitespace
    pairs = _re.findall(
        r'<td[^>]*>\s*(\d{1,2})\s+([A-Z][a-z]{2})\s+(\d{2,4})\s*</td>'
        r'\s*<td[^>]*>\s*(\d+(?:\.\d+)?)\s*</td>',
        html,
    )
    return _boe_change_points_from_pairs(pairs)


def _boe_strategy_iadb_csv() -> list[tuple]:
    """Completely different endpoint: IADB CSV exporter for series IUDBEDR.
    Returns daily values; we collapse to change points."""
    try:
        r = requests.get(_BOE_CSV_URL, timeout=30,
                         headers={"User-Agent": _BOE_UA},
                         allow_redirects=True)
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning("BoE IADB CSV fetch failed: %s", e)
        return []

    from datetime import date as _date
    rows: list[tuple] = []
    for line in r.text.splitlines():
        line = line.strip()
        if not line or line.upper().startswith("DATE"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            v = float(parts[1])
        except ValueError:
            continue
        # CSV date format: "02 Jan 2024"
        dparts = parts[0].split()
        if len(dparts) != 3:
            continue
        m = _BOE_MONTHS.get(dparts[1])
        if not m:
            continue
        year = _boe_parse_2digit_year(dparts[2])
        if year is None:
            continue
        try:
            rows.append((_date(year, m, int(dparts[0])), v))
        except (ValueError, TypeError):
            continue

    rows.sort()
    # Collapse daily series to change points only
    changes: list[tuple] = []
    last = None
    for d, v in rows:
        if v != last:
            changes.append((d, v))
            last = v
    return changes


def _boe_forward_fill_monthly(changes: list[tuple]) -> list[list]:
    """Step-function forward-fill: emit one point per month from the earliest
    change to today, with the value in force at the end of that month."""
    if not changes:
        return []
    from datetime import date as _date, timedelta as _td
    out: list[list] = []
    first = changes[0][0]
    cursor = _date(first.year, first.month, 1)
    today = _date.today()
    change_idx = 0
    current_rate: float | None = None
    while cursor <= today:
        next_month = (_date(cursor.year + 1, 1, 1)
                      if cursor.month == 12
                      else _date(cursor.year, cursor.month + 1, 1))
        eom = next_month - _td(days=1)
        while change_idx < len(changes) and changes[change_idx][0] <= eom:
            current_rate = changes[change_idx][1]
            change_idx += 1
        if current_rate is not None:
            out.append([_to_ms(cursor.isoformat()), current_rate])
        cursor = next_month
    return out


def _boe_sanity_ok(monthly: list[list]) -> tuple[bool, str]:
    """Reject obviously wrong outputs. Returns (ok, reason)."""
    if not monthly:
        return False, "no observations"
    if len(monthly) < 10:
        return False, f"only {len(monthly)} observations (need ≥10)"
    last_ts, last_rate = monthly[-1]
    if not (0 <= last_rate <= 25):
        return False, f"latest rate {last_rate}% outside plausible 0-25 range"
    from datetime import date as _date, datetime as _dt, timezone as _tz
    last_date = _dt.fromtimestamp(last_ts / 1000, tz=_tz.utc).date()
    age_days = (_date.today() - last_date).days
    if age_days > 730:
        return False, f"latest observation is {age_days} days old"
    return True, ""


def fetch_boe_bank_rate() -> list[list]:
    """Resilient BoE Bank Rate fetcher. See module-top comments for design.

    Tries three independent parsing strategies; first one that produces
    sanity-passing data wins. All three would need to break before the
    dashboard's BoE figure goes stale.
    """
    _boe_html_cache.clear()  # fresh fetch each call (idempotent within run)
    strategies = (
        ("strict-html", _boe_strategy_strict_html),
        ("loose-html",  _boe_strategy_loose_html),
        ("iadb-csv",    _boe_strategy_iadb_csv),
    )
    for name, fn in strategies:
        try:
            changes = fn()
        except Exception as e:
            log.warning("BoE strategy '%s' raised: %s", name, e)
            continue
        if not changes:
            log.info("BoE strategy '%s' returned no data — trying next", name)
            continue
        monthly = _boe_forward_fill_monthly(changes)
        ok, reason = _boe_sanity_ok(monthly)
        if ok:
            log.info("BoE Bank Rate: strategy '%s' → %d change points → %d monthly obs (current %.2f%%)",
                     name, len(changes), len(monthly), monthly[-1][1])
            return monthly
        log.warning("BoE strategy '%s' parsed %d changes but failed sanity: %s",
                    name, len(changes), reason)
    log.error("All BoE Bank Rate strategies failed — keeping prior data if any.")
    return []


# ── ONS (Office for National Statistics) time series ──
# Direct ONS data is typically 3+ months fresher than the OECD-aggregated
# equivalents on FRED. Pattern: ons.gov.uk/{topic_path}/timeseries/{id}/{dataset}/data
_ONS_MONTH = {'JAN':1,'FEB':2,'MAR':3,'APR':4,'MAY':5,'JUN':6,'JUL':7,'AUG':8,'SEP':9,'OCT':10,'NOV':11,'DEC':12}

def fetch_ons(series_id: str, dataset: str, topic_path: str) -> list[list]:
    """Pull a monthly ONS time series. Returns [[ts_ms, value], ...]."""
    url = f"https://www.ons.gov.uk/{topic_path}/timeseries/{series_id}/{dataset}/data"
    try:
        r = requests.get(url, timeout=30, headers={"Accept": "application/json"})
        r.raise_for_status()
        payload = r.json()
    except (requests.RequestException, ValueError) as e:
        log.warning("ONS %s failed: %s", series_id, e)
        return []

    months = payload.get("months") or []
    out: list[list] = []
    for obs in months:
        date_str = (obs.get("date") or "").strip()
        val_str  = (obs.get("value") or "").strip()
        if not date_str or not val_str:
            continue
        parts = date_str.split()
        if len(parts) != 2:
            continue
        try:
            year = int(parts[0])
            mnum = _ONS_MONTH.get(parts[1].upper()[:3])
            if not mnum:
                continue
            val = float(val_str)
        except (ValueError, TypeError):
            continue
        iso = f"{year:04d}-{mnum:02d}-01"
        out.append([_to_ms(iso), val])
    out.sort(key=lambda r: r[0])
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
            r = requests.get(url, timeout=120, stream=False,
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
        r = requests.get(page_url, timeout=30,
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
        r2 = requests.get(csv_url, timeout=30,
                          headers={"User-Agent": "Mozilla/5.0 MacroOps/1.0"})
        r2.raise_for_status()
    except requests.RequestException as e:
        log.warning("UK fuel CSV fetch failed: %s", e)
        return []

    text = r2.content.decode("utf-8-sig", errors="replace")
    rows = [ln.split(",") for ln in text.splitlines() if ln.strip()]
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


def fetch_yahoo(ticker: str) -> list[list]:
    """Pull a ticker from Yahoo Finance via yfinance and downsample to month-end."""
    try:
        import yfinance as yf  # imported lazily so script still loads without it
    except ImportError:
        log.warning("yfinance not installed — skipping %s", ticker)
        return []

    try:
        df = yf.download(
            ticker,
            start=START_DATE,
            progress=False,
            auto_adjust=True,
            threads=False,
        )
    except Exception as e:  # network or yfinance internal
        log.warning("Yahoo %s failed: %s", ticker, e)
        return []

    if df is None or df.empty:
        return []

    # yfinance may return MultiIndex columns when threads/multi-ticker is involved.
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)

    col = "Close" if "Close" in df.columns else df.columns[0]
    s = df[col].dropna()
    if s.empty:
        return []

    # Month-end resample for compact long-term storage.
    monthly = s.resample("ME").last().dropna()
    out: list[list] = []
    for ts, val in monthly.items():
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        ts_ms = int(ts.tz_localize("UTC").timestamp() * 1000) if ts.tzinfo is None else int(ts.timestamp() * 1000)
        out.append([ts_ms, v])
    return out


# ──────────────────────────────────────────────────────────────────────────
# Transforms & stats
# ──────────────────────────────────────────────────────────────────────────
def apply_transform(data: list[list], transform: str) -> list[list]:
    """Apply YoY percent change or other transforms."""
    if transform == "yoy_pct":
        # Pair every observation with the one ~12 periods earlier (works for monthly).
        if len(data) < 13:
            return []
        out = []
        # For monthly data, lag 12. For quarterly, lag 4. Inferred from cadence.
        # Median months between consecutive points:
        if len(data) >= 2:
            avg_gap_days = (data[-1][0] - data[0][0]) / (1000 * 86400 * (len(data) - 1))
            lag = 12 if avg_gap_days < 45 else (4 if avg_gap_days < 100 else 1)
        else:
            lag = 12
        for i in range(lag, len(data)):
            prev = data[i - lag][1]
            if prev == 0:
                continue
            pct = (data[i][1] / prev - 1.0) * 100.0
            out.append([data[i][0], round(pct, 4)])
        return out
    return data


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

def _date_str(ms: int) -> str:
    """ms epoch → YYYY-MM-DD (safe for pre-1970 dates on Windows)."""
    return (_EPOCH + timedelta(milliseconds=ms)).strftime("%Y-%m-%d")


def compute_stats(data: list[list]) -> dict[str, Any]:
    """Latest value plus 1m / 1y / 5y / max changes."""
    if not data:
        return {}
    latest_ts, latest_val = data[-1]
    stats: dict[str, Any] = {
        "last_value": round(latest_val, 4),
        "last_date": _date_str(latest_ts),
        "n_points": len(data),
    }

    def _change(periods_back: int) -> float | None:
        if len(data) <= periods_back:
            return None
        prev = data[-1 - periods_back][1]
        if prev == 0:
            return None
        return round((latest_val / prev - 1.0) * 100.0, 3)

    stats["chg_1m_pct"] = _change(1)
    stats["chg_3m_pct"] = _change(3)
    stats["chg_1y_pct"] = _change(12)
    stats["chg_5y_pct"] = _change(60)
    if len(data) > 1:
        first = data[0][1]
        if first:
            stats["chg_max_pct"] = round((latest_val / first - 1.0) * 100.0, 2)

    vals = [d[1] for d in data]
    stats["min"] = round(min(vals), 4)
    stats["max"] = round(max(vals), 4)
    stats["min_date"] = _date_str(data[vals.index(min(vals))][0])
    stats["max_date"] = _date_str(data[vals.index(max(vals))][0])
    return stats


# ──────────────────────────────────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────────────────────────────────
def fetch_one(s: dict) -> dict | None:
    """Fetch a single series and return the JSON-ready dict, or None on failure."""
    sid = s["id"]
    data: list[list] = []
    source = None

    if s.get("boe_scrape"):
        log.info("  → %s via BoE Bank Rate scrape", sid)
        data = fetch_boe_bank_rate()
        if data:
            source = "Bank of England — Bank Rate (IADB)"

    if (not data) and s.get("ons"):
        log.info("  → %s via ONS (%s)", sid, s["ons"])
        data = fetch_ons(s["ons"], s.get("ons_dataset", "lms"), s.get("ons_path", "employmentandlabourmarket"))
        if data:
            source = f"ONS ({s['ons']})"

    if (not data) and s.get("yahoo"):
        log.info("  → %s via Yahoo (%s)", sid, s["yahoo"])
        data = fetch_yahoo(s["yahoo"])
        if data:
            source = f"Yahoo Finance ({s['yahoo']})"

    if (not data) and s.get("fred"):
        log.info("  → %s via FRED (%s)", sid, s["fred"])
        data = fetch_fred(s["fred"], frequency=s.get("freq"))
        if data:
            source = f"FRED ({s['fred']})"

    if (not data) and s.get("uk_fuel"):
        log.info("  → %s via UK gov.uk fuel CSV", sid)
        data = fetch_uk_fuel(s["uk_fuel"])
        if data:
            source = "gov.uk DESNZ weekly road fuel prices"

    if (not data) and s.get("uk_hpi"):
        log.info("  → %s via UK HPI (%s)", sid, s["uk_hpi"])
        data = fetch_uk_hpi_region(s["uk_hpi"])
        if data:
            source = "HM Land Registry UK House Price Index"

    if not data:
        log.error("  ✗ no data for %s", sid)
        return None

    if s.get("scale"):
        data = [[ts, v * s["scale"]] for ts, v in data]
    if s.get("transform"):
        data = apply_transform(data, s["transform"])
        if not data:
            log.error("  ✗ transform produced empty series for %s", sid)
            return None

    return {
        "id": sid,
        "name": s["name"],
        "region": s.get("region"),
        "unit": s.get("unit"),
        "note": s.get("note"),
        "source": source,
        "stats": compute_stats(data),
        "data": data,
    }


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
    section_status: dict[str, dict[str, Any]] = {}
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
                res = fetch_one(s)
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
                    new_series[s["id"]] = prev
                fail += 1

        section_status[section_key] = {"ok": ok, "fail": fail}
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
        out_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        log.info("  wrote %s  (%d ok, %d fail)", out_path.name, ok, fail)

    # Events file
    events_payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "count": len(EVENTS),
        },
        "events": sorted(EVENTS, key=lambda e: e["date"]),
    }
    (DATA_DIR / "events.json").write_text(
        json.dumps(events_payload, separators=(",", ":")), encoding="utf-8"
    )
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
        "totals": {"ok": total_ok, "fail": total_fail},
    }
    (DATA_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    log.info(
        "DONE in %ss — %d ok, %d fail",
        manifest["duration_sec"],
        total_ok,
        total_fail,
    )
    return manifest


if __name__ == "__main__":
    run()
