"""
Build data/health.json — per-data-source status for the sidebar health panel.

Walks every data file produced by the other fetchers and aggregates:
  - which method delivered each series (FRED / Yahoo / gov.uk fuel / Land Reg)
  - how many series each method delivered vs how many were expected
  - the freshness of the underlying data (latest observation date)
  - the freshness of the fetch itself (file's generated_at timestamp)

The frontend reads the resulting health.json to render the panel.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"
sys.path.insert(0, str(HERE))
from series_config import SECTIONS  # noqa: E402

UTC = timezone.utc
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("health")


# ───────────────────────── helpers ─────────────────────────
def load(name: str) -> dict | None:
    p = DATA / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log.warning("could not parse %s: %s", name, e)
        return None


def categorise(source_str: str) -> str:
    """Bucket the per-series 'source' string into one of the known methods."""
    if not source_str:
        return "unknown"
    s = source_str.upper()
    if "FRED" in s:                        return "fred"
    if "YAHOO" in s:                       return "yahoo"
    if "DESNZ" in s or "GOV.UK" in s:      return "uk_fuel"
    if "LAND REGISTRY" in s:               return "land_registry"
    return "unknown"


def expected_by_method() -> dict[str, int]:
    """How many series each method is *meant* to deliver, per config."""
    counts = {"fred": 0, "yahoo": 0, "uk_fuel": 0, "land_registry": 0}
    for section in SECTIONS.values():
        for s in section["series"]:
            if s.get("yahoo"):       counts["yahoo"] += 1
            elif s.get("fred"):      counts["fred"] += 1
            elif s.get("uk_fuel"):   counts["uk_fuel"] += 1
            elif s.get("uk_hpi"):    counts["land_registry"] += 1
    return counts


def categorise_status(delivered: int, expected: int, age_hours: float | None,
                      stale_hours: float) -> str:
    """ok / warning / error from delivered ratio + age."""
    if expected and delivered == 0:                            return "error"
    ratio = (delivered / expected) if expected else 1.0
    if ratio < 0.5:                                            return "error"
    if age_hours is not None and age_hours > stale_hours * 3:  return "error"
    if ratio < 0.9 or (age_hours is not None and age_hours > stale_hours):
        return "warning"
    return "ok"


def hours_since(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (datetime.now(UTC) - dt).total_seconds() / 3600.0


# ───────────────────────── source declarations ─────────────────────────
# Each entry is the static metadata; runtime counts/dates are filled in below.
SERVER_SOURCES = [
    {
        "id": "fred", "name": "FRED",
        "full_name": "Federal Reserve Economic Data (St. Louis Fed)",
        "type": "Python · scripts/fetch_data.py",
        "url": "https://fred.stlouisfed.org/",
        "icon": "◭",
        "method_key": "fred", "stale_hours": 18,
        "notes": "Authenticated API. Requires FRED_API_KEY repo secret. Covers rates, inflation, money, employment, GDP, housing.",
    },
    {
        "id": "yahoo", "name": "Yahoo Finance",
        "full_name": "Yahoo Finance (yfinance library)",
        "type": "Python · scripts/fetch_data.py",
        "url": "https://finance.yahoo.com/",
        "icon": "↗",
        "method_key": "yahoo", "stale_hours": 18,
        "notes": "No auth. yfinance scrapes Yahoo's internal API. Covers equity indices, commodities, FX, crypto.",
    },
    {
        "id": "uk_fuel", "name": "UK Fuel (DESNZ)",
        "full_name": "UK Department for Energy Security weekly road fuel prices",
        "type": "Python · CSV scrape",
        "url": "https://www.gov.uk/government/statistics/weekly-road-fuel-prices",
        "icon": "◉",
        "method_key": "uk_fuel", "stale_hours": 24,
        "notes": "Weekly CSV. Scrapes the gov.uk landing page for the latest publication.",
    },
    {
        "id": "land_registry", "name": "UK House Prices",
        "full_name": "HM Land Registry UK House Price Index",
        "type": "Python · CSV scrape",
        "url": "https://landregistry.data.gov.uk/",
        "icon": "⌂",
        "method_key": "land_registry", "stale_hours": 36,
        "notes": "Probes last 6 monthly CSV URLs to find the freshest. 405 regions parsed per fetch.",
    },
]

# Sources that come from their own JSON file rather than series aggregation.
FILE_SOURCES = [
    {
        "id": "news", "name": "News (RSS)",
        "full_name": "RSS aggregator: BBC / Reuters / FT / BoE / ECB / Fed / Guardian",
        "type": "Python · scripts/fetch_news.py",
        "url": "",
        "icon": "≡",
        "file": "news.json",
        "items_key": "items",
        "expected": 200,
        "stale_hours": 3,
        "include_subsources": True,
        "notes_fmt": "{alive}/{total} feeds responding. Hourly refresh in CI.",
    },
    {
        "id": "calendar", "name": "Economic Calendar",
        "full_name": "Computed release calendar (FOMC/BoE/ECB + monthly patterns)",
        "type": "Python · scripts/fetch_calendar.py",
        "url": "",
        "icon": "▦",
        "file": "calendar.json",
        "items_key": "events",
        "expected": 60,
        "stale_hours": 36,
        "notes": "Hardcoded committee dates + pattern-computed monthly releases for the next ~180 days.",
    },
]

# Browser-side sources — status set client-side; declared here for the UI.
RUNTIME_SOURCES = [
    {
        "id": "coingecko", "name": "CoinGecko (live)",
        "full_name": "CoinGecko Simple Price API — realtime crypto",
        "type": "Browser fetch · live-prices.js",
        "url": "https://api.coingecko.com/",
        "icon": "◆", "expected": 5,
        "notes": "Polled every 20s by the browser. Provides BTC / ETH / SOL / XRP / ATOM live prices.",
    },
    {
        "id": "yahoo_proxy", "name": "Yahoo Live (proxied)",
        "full_name": "Yahoo Finance via public CORS proxy",
        "type": "Browser fetch · live-prices.js",
        "url": "https://query1.finance.yahoo.com/",
        "icon": "↗", "expected": 7,
        "notes": "Polled every 20s. Index/FX live quotes via corsproxy.io / allorigins.win fallback.",
    },
    {
        "id": "tradingview", "name": "TradingView Widget",
        "full_name": "TradingView embedded widget — hero chart",
        "type": "Iframe · tradingview.com",
        "url": "https://www.tradingview.com/",
        "icon": "▶",
        "notes": "Loads the live chart in the hero panel. Failure shows TradingView's own error.",
    },
]


# ───────────────────────── builders ─────────────────────────
def aggregate_by_method(manifest: dict) -> dict[str, dict]:
    """Walk all section JSON files and bucket each series by source method."""
    by_method: dict[str, dict] = {}
    for section_key in manifest.get("sections", {}):
        section_data = load(f"{section_key}.json")
        if not section_data:
            continue
        for series in section_data.get("series", {}).values():
            method = categorise(series.get("source", ""))
            slot = by_method.setdefault(method, {"count": 0, "latest_data": None})
            slot["count"] += 1
            last_date = (series.get("stats") or {}).get("last_date")
            if last_date and (slot["latest_data"] is None or last_date > slot["latest_data"]):
                slot["latest_data"] = last_date
    return by_method


def build_server_source(spec: dict, by_method: dict, expected: dict,
                        last_fetch: str | None, fetch_age_h: float | None) -> dict:
    """Render a Python-fetched source (FRED / Yahoo / fuel / Land Registry)."""
    bucket = by_method.get(spec["method_key"], {})
    delivered = bucket.get("count", 0)
    exp = expected.get(spec["method_key"], 0)
    return {
        **{k: spec[k] for k in ("id", "name", "full_name", "type", "url", "icon", "notes")},
        "delivered": delivered,
        "expected": exp,
        "latest_data": bucket.get("latest_data"),
        "last_fetch": last_fetch,
        "status": categorise_status(delivered, exp, fetch_age_h, spec["stale_hours"]),
    }


def build_file_source(spec: dict) -> dict:
    """Render a source that lives in its own JSON file (news, calendar)."""
    data = load(spec["file"]) or {}
    items = data.get(spec["items_key"]) or []
    meta = data.get("meta") or {}
    fetched_at = meta.get("generated_at")
    age_h = hours_since(fetched_at)
    out = {
        **{k: spec[k] for k in ("id", "name", "full_name", "type", "url", "icon")},
        "delivered": len(items),
        "expected": spec["expected"],
        "latest_data": (fetched_at or "")[:10] or None,
        "last_fetch": fetched_at,
        "status": categorise_status(len(items), spec["expected"], age_h, spec["stale_hours"]),
    }
    if spec.get("include_subsources"):
        sub = meta.get("by_source") or {}
        alive = sum(1 for v in sub.values() if v)
        out["sub_sources"] = sub
        out["notes"] = spec["notes_fmt"].format(alive=alive, total=len(sub))
    else:
        out["notes"] = spec["notes"]
    return out


def build_runtime_source(spec: dict) -> dict:
    """Browser-side source — frontend overrides status at runtime."""
    return {**spec, "runtime": True}


def tally_status(sources: list[dict]) -> dict[str, int]:
    counts = {"ok": 0, "warning": 0, "error": 0, "runtime": 0}
    for s in sources:
        if s.get("runtime"):
            counts["runtime"] += 1
        st = s.get("status")
        if st in counts:
            counts[st] += 1
    counts["total"] = len(sources)
    return counts


# ───────────────────────── entrypoint ─────────────────────────
def build() -> dict:
    manifest = load("manifest.json") or {"sections": {}}
    last_fetch = manifest.get("generated_at")
    fetch_age_h = hours_since(last_fetch)

    by_method = aggregate_by_method(manifest)
    expected = expected_by_method()

    sources = (
        [build_server_source(s, by_method, expected, last_fetch, fetch_age_h) for s in SERVER_SOURCES]
        + [build_file_source(s) for s in FILE_SOURCES]
        + [build_runtime_source(s) for s in RUNTIME_SOURCES]
    )

    out = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "totals": tally_status(sources),
        "sources": sources,
    }
    (DATA / "health.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info(
        "wrote health.json — %d sources (%d ok / %d warn / %d err / %d runtime)",
        len(sources), out["totals"]["ok"], out["totals"]["warning"],
        out["totals"]["error"], out["totals"]["runtime"],
    )
    return out


if __name__ == "__main__":
    build()
