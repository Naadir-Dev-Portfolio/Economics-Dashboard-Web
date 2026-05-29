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


# ─────────────────────────────────────────────────────────────────
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
    if "FRED" in s:                              return "fred"
    if "YAHOO" in s:                             return "yahoo"
    if "DESNZ" in s or "GOV.UK" in s:            return "uk_fuel"
    if "LAND REGISTRY" in s:                     return "land_registry"
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
    if expected and delivered == 0:               return "error"
    ratio = (delivered / expected) if expected else 1.0
    if ratio < 0.5:                               return "error"
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


# ─────────────────────────────────────────────────────────────────
def build() -> dict:
    manifest = load("manifest.json") or {"sections": {}}
    manifest_generated_at = manifest.get("generated_at")
    fetch_age_h = hours_since(manifest_generated_at)

    # Walk all section files to attribute series → method.
    by_method: dict[str, dict] = {}
    for section_key in manifest.get("sections", {}):
        section_data = load(f"{section_key}.json")
        if not section_data:
            continue
        for sid, series in section_data.get("series", {}).items():
            method = categorise(series.get("source", ""))
            slot = by_method.setdefault(method, {"count": 0, "latest_data": None})
            slot["count"] += 1
            last_date = (series.get("stats") or {}).get("last_date")
            if last_date and (slot["latest_data"] is None or last_date > slot["latest_data"]):
                slot["latest_data"] = last_date

    expected = expected_by_method()
    sources = []

    # ── FRED ──
    delivered = by_method.get("fred", {}).get("count", 0)
    sources.append({
        "id": "fred",
        "name": "FRED",
        "full_name": "Federal Reserve Economic Data (St. Louis Fed)",
        "type": "Python · scripts/fetch_data.py",
        "url": "https://fred.stlouisfed.org/",
        "icon": "◭",
        "delivered": delivered,
        "expected": expected["fred"],
        "latest_data": by_method.get("fred", {}).get("latest_data"),
        "last_fetch": manifest_generated_at,
        "status": categorise_status(delivered, expected["fred"], fetch_age_h, stale_hours=18),
        "notes": "Authenticated API. Requires FRED_API_KEY repo secret. Covers rates, inflation, money, employment, GDP, housing.",
    })

    # ── Yahoo Finance ──
    delivered = by_method.get("yahoo", {}).get("count", 0)
    sources.append({
        "id": "yahoo",
        "name": "Yahoo Finance",
        "full_name": "Yahoo Finance (yfinance library)",
        "type": "Python · scripts/fetch_data.py",
        "url": "https://finance.yahoo.com/",
        "icon": "↗",
        "delivered": delivered,
        "expected": expected["yahoo"],
        "latest_data": by_method.get("yahoo", {}).get("latest_data"),
        "last_fetch": manifest_generated_at,
        "status": categorise_status(delivered, expected["yahoo"], fetch_age_h, stale_hours=18),
        "notes": "No auth. yfinance scrapes Yahoo's internal API. Covers equity indices, commodities, FX, crypto.",
    })

    # ── UK fuel (DESNZ) ──
    delivered = by_method.get("uk_fuel", {}).get("count", 0)
    sources.append({
        "id": "uk_fuel",
        "name": "UK Fuel (DESNZ)",
        "full_name": "UK Department for Energy Security weekly road fuel prices",
        "type": "Python · CSV scrape",
        "url": "https://www.gov.uk/government/statistics/weekly-road-fuel-prices",
        "icon": "◉",
        "delivered": delivered,
        "expected": expected["uk_fuel"],
        "latest_data": by_method.get("uk_fuel", {}).get("latest_data"),
        "last_fetch": manifest_generated_at,
        "status": categorise_status(delivered, expected["uk_fuel"], fetch_age_h, stale_hours=24),
        "notes": "Weekly CSV. Scrapes the gov.uk landing page for the latest publication.",
    })

    # ── Land Registry HPI ──
    delivered = by_method.get("land_registry", {}).get("count", 0)
    sources.append({
        "id": "land_registry",
        "name": "UK House Prices",
        "full_name": "HM Land Registry UK House Price Index",
        "type": "Python · CSV scrape",
        "url": "https://landregistry.data.gov.uk/",
        "icon": "⌂",
        "delivered": delivered,
        "expected": expected["land_registry"],
        "latest_data": by_method.get("land_registry", {}).get("latest_data"),
        "last_fetch": manifest_generated_at,
        "status": categorise_status(delivered, expected["land_registry"], fetch_age_h, stale_hours=36),
        "notes": "Probes last 6 monthly CSV URLs to find the freshest. 405 regions parsed per fetch.",
    })

    # ── News RSS ──
    news = load("news.json") or {}
    news_count = len((news.get("items") or []))
    news_at = (news.get("meta") or {}).get("generated_at")
    news_age = hours_since(news_at)
    news_sources = (news.get("meta") or {}).get("by_source") or {}
    news_alive = sum(1 for v in news_sources.values() if v)
    sources.append({
        "id": "news",
        "name": "News (RSS)",
        "full_name": "RSS aggregator: BBC / Reuters / FT / BoE / ECB / Fed / Guardian",
        "type": "Python · scripts/fetch_news.py",
        "url": "",
        "icon": "≡",
        "delivered": news_count,
        "expected": 200,                                        # hard cap on items kept
        "latest_data": (news_at or "")[:10] or None,
        "last_fetch": news_at,
        "status": categorise_status(news_count, 200, news_age, stale_hours=3),
        "sub_sources": news_sources,
        "notes": f"{news_alive}/{len(news_sources)} feeds responding. Hourly refresh in CI.",
    })

    # ── Calendar ──
    cal = load("calendar.json") or {}
    cal_count = len((cal.get("events") or []))
    cal_at = (cal.get("meta") or {}).get("generated_at")
    cal_age = hours_since(cal_at)
    sources.append({
        "id": "calendar",
        "name": "Economic Calendar",
        "full_name": "Computed release calendar (FOMC/BoE/ECB + monthly patterns)",
        "type": "Python · scripts/fetch_calendar.py",
        "url": "",
        "icon": "▦",
        "delivered": cal_count,
        "expected": 60,
        "latest_data": (cal_at or "")[:10] or None,
        "last_fetch": cal_at,
        "status": categorise_status(cal_count, 60, cal_age, stale_hours=36),
        "notes": "Hardcoded committee dates + pattern-computed monthly releases for the next ~180 days.",
    })

    # ── Browser-side runtime sources (status set client-side; we just declare them) ──
    sources.append({
        "id": "coingecko",
        "name": "CoinGecko (live)",
        "full_name": "CoinGecko Simple Price API — realtime crypto",
        "type": "Browser fetch · live-prices.js",
        "url": "https://api.coingecko.com/",
        "icon": "◆",
        "runtime": True,
        "expected": 5,
        "notes": "Polled every 20s by the browser. Provides BTC / ETH / SOL / XRP / ATOM live prices.",
    })
    sources.append({
        "id": "yahoo_proxy",
        "name": "Yahoo Live (proxied)",
        "full_name": "Yahoo Finance via public CORS proxy",
        "type": "Browser fetch · live-prices.js",
        "url": "https://query1.finance.yahoo.com/",
        "icon": "↗",
        "runtime": True,
        "expected": 7,
        "notes": "Polled every 20s. Index/FX live quotes via corsproxy.io / allorigins.win fallback.",
    })
    sources.append({
        "id": "tradingview",
        "name": "TradingView Widget",
        "full_name": "TradingView embedded widget — hero chart",
        "type": "Iframe · tradingview.com",
        "url": "https://www.tradingview.com/",
        "icon": "▶",
        "runtime": True,
        "notes": "Loads the live chart in the hero panel. Failure shows TradingView's own error.",
    })

    out = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "totals": {
            "ok":      sum(1 for s in sources if s.get("status") == "ok"),
            "warning": sum(1 for s in sources if s.get("status") == "warning"),
            "error":   sum(1 for s in sources if s.get("status") == "error"),
            "runtime": sum(1 for s in sources if s.get("runtime")),
            "total":   len(sources),
        },
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
