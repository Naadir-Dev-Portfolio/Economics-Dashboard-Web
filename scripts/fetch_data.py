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
from datetime import datetime, timezone
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


def compute_stats(data: list[list]) -> dict[str, Any]:
    """Latest value plus 1m / 1y / 5y / max changes."""
    if not data:
        return {}
    latest_ts, latest_val = data[-1]
    stats: dict[str, Any] = {
        "last_value": round(latest_val, 4),
        "last_date": datetime.fromtimestamp(latest_ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
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
    stats["min_date"] = datetime.fromtimestamp(
        data[vals.index(min(vals))][0] / 1000, tz=timezone.utc
    ).strftime("%Y-%m-%d")
    stats["max_date"] = datetime.fromtimestamp(
        data[vals.index(max(vals))][0] / 1000, tz=timezone.utc
    ).strftime("%Y-%m-%d")
    return stats


# ──────────────────────────────────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────────────────────────────────
def fetch_one(s: dict) -> dict | None:
    """Fetch a single series and return the JSON-ready dict, or None on failure."""
    sid = s["id"]
    data: list[list] = []
    source = None

    if s.get("yahoo"):
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
