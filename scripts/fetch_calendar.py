"""
Build data/calendar.json — the next ~180 days of high-impact economic events.

A mix of:
  * Hardcoded central-bank committee meetings (FOMC, BoE MPC, ECB GovC)
    — these are published once a year; refresh the *_SCHEDULE constants
    around December for the next year.
  * Pattern-based monthly releases (BLS NFP, US/UK CPI, etc.) — computed
    dynamically from "first Friday of month at 8:30 ET" type rules.

Outputs ISO-8601 datetimes in UTC. The frontend handles localisation.
"""

from __future__ import annotations

import calendar as _cal
import json
import logging
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("calendar")

UTC = timezone.utc
ET  = ZoneInfo("America/New_York")
UK  = ZoneInfo("Europe/London")
CET = ZoneInfo("Europe/Berlin")

LOOKAHEAD_DAYS = 180

# ─── Central-bank committee schedules ──────────────────────────────────
# Refresh annually. Source links commented per row.

FOMC_SCHEDULE = [
    # 2026 — federalreserve.gov/monetarypolicy/fomccalendars.htm
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-10",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    # 2027 (provisional)
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09",
    "2027-07-28", "2027-09-22", "2027-11-03", "2027-12-15",
]
FOMC_TIME_ET = time(14, 0)        # Statement at 2 PM ET

BOE_MPC_SCHEDULE = [
    # 2026 — bankofengland.co.uk/monetary-policy/decisions-and-minutes
    "2026-02-05", "2026-03-19", "2026-05-07", "2026-06-18",
    "2026-08-06", "2026-09-17", "2026-11-05", "2026-12-17",
    # 2027 (provisional, monthly Thursday around the 5th/17th)
    "2027-02-04", "2027-03-18", "2027-05-06", "2027-06-17",
    "2027-08-05", "2027-09-16", "2027-11-04", "2027-12-16",
]
BOE_TIME_UK = time(12, 0)         # Announcement at noon UK time

ECB_SCHEDULE = [
    # 2026 — ecb.europa.eu/press/calendars
    "2026-01-22", "2026-03-05", "2026-04-16", "2026-06-04",
    "2026-07-23", "2026-09-10", "2026-10-22", "2026-12-17",
    # 2027
    "2027-01-21", "2027-03-04", "2027-04-22", "2027-06-03",
    "2027-07-22", "2027-09-09", "2027-10-21", "2027-12-16",
]
ECB_TIME_CET = time(13, 15)       # Statement at 13:15 CET, presser 13:45 CET


# ─── Helpers for the pattern-based monthly releases ────────────────────
def nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """Return the n-th weekday (0=Mon, 6=Sun) of the given month."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def last_business_day(year: int, month: int) -> date:
    """Last business day (Mon-Fri) of the month."""
    _, days = _cal.monthrange(year, month)
    d = date(year, month, days)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def to_utc(d: date, t: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(d, t, tzinfo=tz).astimezone(UTC)


# ─── Event builders ────────────────────────────────────────────────────
def fomc_events() -> list[dict]:
    out = []
    for s in FOMC_SCHEDULE:
        d = date.fromisoformat(s)
        out.append({
            "id": f"fomc-{s}",
            "key": "fomc",
            "title": "FOMC Rate Decision",
            "region": "US",
            "tag": "monetary",
            "datetime": to_utc(d, FOMC_TIME_ET, ET).isoformat(),
            "description": "Federal Open Market Committee policy decision, statement and (in Mar/Jun/Sep/Dec) Summary of Economic Projections.",
            "source": "Federal Reserve",
            "source_url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
        })
    return out


def boe_events() -> list[dict]:
    out = []
    for s in BOE_MPC_SCHEDULE:
        d = date.fromisoformat(s)
        out.append({
            "id": f"boe-{s}",
            "key": "boe_mpc",
            "title": "BoE Monetary Policy Decision",
            "region": "UK",
            "tag": "monetary",
            "datetime": to_utc(d, BOE_TIME_UK, UK).isoformat(),
            "description": "Bank of England Monetary Policy Committee Bank Rate decision and minutes.",
            "source": "Bank of England",
            "source_url": "https://www.bankofengland.co.uk/monetary-policy/decisions-and-minutes",
        })
    return out


def ecb_events() -> list[dict]:
    out = []
    for s in ECB_SCHEDULE:
        d = date.fromisoformat(s)
        out.append({
            "id": f"ecb-{s}",
            "key": "ecb_meeting",
            "title": "ECB Rate Decision",
            "region": "EU",
            "tag": "monetary",
            "datetime": to_utc(d, ECB_TIME_CET, CET).isoformat(),
            "description": "European Central Bank Governing Council monetary policy decision and press conference.",
            "source": "European Central Bank",
            "source_url": "https://www.ecb.europa.eu/press/calendars/mgcgc/",
        })
    return out


def monthly_pattern_events(today: date, months: int = 6) -> list[dict]:
    """Generate forecast event dates from known monthly release patterns."""
    out = []
    for offset in range(months + 1):
        year  = today.year + (today.month - 1 + offset) // 12
        month = (today.month - 1 + offset) % 12 + 1

        # ── US Non-Farm Payrolls — first Friday at 8:30 ET ──
        d = nth_weekday_of_month(year, month, 4, 1)
        out.append({
            "id": f"us-nfp-{d.isoformat()}",
            "key": "us_nfp",
            "title": "US Non-Farm Payrolls",
            "region": "US", "tag": "employment",
            "datetime": to_utc(d, time(8, 30), ET).isoformat(),
            "description": "Bureau of Labor Statistics — Employment Situation. Headline NFP, unemployment rate (U-3, U-6), wage growth, participation rate.",
            "source": "BLS",
            "source_url": "https://www.bls.gov/schedule/news_release/empsit.htm",
        })

        # ── US CPI — typically Wednesday in 2nd full week, 8:30 ET ──
        d = nth_weekday_of_month(year, month, 2, 2)  # 2nd Wednesday
        out.append({
            "id": f"us-cpi-{d.isoformat()}",
            "key": "us_cpi",
            "title": "US CPI Release",
            "region": "US", "tag": "inflation",
            "datetime": to_utc(d, time(8, 30), ET).isoformat(),
            "description": "Bureau of Labor Statistics — Consumer Price Index (headline + core). Watched for inflation trajectory.",
            "source": "BLS",
            "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
        })

        # ── US PPI — usually Thursday after CPI ──
        d_ppi = d + timedelta(days=1)
        if d_ppi.weekday() >= 5:
            d_ppi += timedelta(days=(7 - d_ppi.weekday()))
        out.append({
            "id": f"us-ppi-{d_ppi.isoformat()}",
            "key": "us_ppi",
            "title": "US PPI Release",
            "region": "US", "tag": "inflation",
            "datetime": to_utc(d_ppi, time(8, 30), ET).isoformat(),
            "description": "BLS — Producer Price Index (final demand).",
            "source": "BLS",
            "source_url": "https://www.bls.gov/schedule/news_release/ppi.htm",
        })

        # ── US PCE — last business day +27 (~end of month following) at 8:30 ET ──
        d_pce = nth_weekday_of_month(year, month, 4, 5) if nth_weekday_of_month(year, month, 4, 5).month == month else nth_weekday_of_month(year, month, 4, 4)
        out.append({
            "id": f"us-pce-{d_pce.isoformat()}",
            "key": "us_pce",
            "title": "US PCE Price Index",
            "region": "US", "tag": "inflation",
            "datetime": to_utc(d_pce, time(8, 30), ET).isoformat(),
            "description": "BEA — Personal Consumption Expenditures price index (the Fed's preferred inflation gauge).",
            "source": "BEA",
            "source_url": "https://www.bea.gov/data/personal-consumption-expenditures-price-index",
        })

        # ── US Retail Sales — typically around the 15th, 8:30 ET ──
        # Take the Tuesday/Wednesday closest to the 15th
        target = date(year, month, 15)
        while target.weekday() not in (1, 2):  # Tue/Wed
            target += timedelta(days=1)
        out.append({
            "id": f"us-retail-{target.isoformat()}",
            "key": "us_retail",
            "title": "US Retail Sales",
            "region": "US", "tag": "growth",
            "datetime": to_utc(target, time(8, 30), ET).isoformat(),
            "description": "Census Bureau — Advance Monthly Sales for Retail and Food Services.",
            "source": "Census Bureau",
            "source_url": "https://www.census.gov/retail/marts/www/marts_current.pdf",
        })

        # ── US M2 (H.6 release) — usually Tuesday around the 25th, 16:00 ET ──
        target = date(year, month, 25)
        while target.weekday() != 1:  # Tuesday
            target += timedelta(days=1)
        out.append({
            "id": f"us-m2-{target.isoformat()}",
            "key": "us_m2",
            "title": "US Money Supply (H.6)",
            "region": "US", "tag": "money",
            "datetime": to_utc(target, time(16, 0), ET).isoformat(),
            "description": "Federal Reserve H.6 release — M1, M2 money stock and components.",
            "source": "Federal Reserve",
            "source_url": "https://www.federalreserve.gov/releases/h6/",
        })

        # ── UK CPI — 3rd Wednesday of month at 07:00 BST ──
        d = nth_weekday_of_month(year, month, 2, 3)
        out.append({
            "id": f"uk-cpi-{d.isoformat()}",
            "key": "uk_cpi",
            "title": "UK CPI Release",
            "region": "UK", "tag": "inflation",
            "datetime": to_utc(d, time(7, 0), UK).isoformat(),
            "description": "Office for National Statistics — Consumer Prices Index, including CPIH and RPI.",
            "source": "ONS",
            "source_url": "https://www.ons.gov.uk/economy/inflationandpriceindices",
        })

        # ── UK Labour Market — usually Tuesday in 2nd full week at 07:00 ──
        d = nth_weekday_of_month(year, month, 1, 2)  # 2nd Tuesday
        out.append({
            "id": f"uk-labour-{d.isoformat()}",
            "key": "uk_labour",
            "title": "UK Labour Market",
            "region": "UK", "tag": "employment",
            "datetime": to_utc(d, time(7, 0), UK).isoformat(),
            "description": "ONS — Employment, unemployment, vacancies and wage growth.",
            "source": "ONS",
            "source_url": "https://www.ons.gov.uk/employmentandlabourmarket",
        })

        # ── UK GDP — monthly, ~6 weeks lag, around the 12th ──
        target = date(year, month, 12)
        if target.weekday() >= 5:
            target += timedelta(days=(7 - target.weekday()))
        out.append({
            "id": f"uk-gdp-{target.isoformat()}",
            "key": "uk_gdp",
            "title": "UK Monthly GDP",
            "region": "UK", "tag": "growth",
            "datetime": to_utc(target, time(7, 0), UK).isoformat(),
            "description": "ONS — Monthly UK GDP estimate (preliminary).",
            "source": "ONS",
            "source_url": "https://www.ons.gov.uk/economy/grossdomesticproductgdp",
        })

        # ── UK Retail Sales — usually Friday in 3rd/4th week, 07:00 ──
        d = nth_weekday_of_month(year, month, 4, 3)  # 3rd Friday
        out.append({
            "id": f"uk-retail-{d.isoformat()}",
            "key": "uk_retail",
            "title": "UK Retail Sales",
            "region": "UK", "tag": "growth",
            "datetime": to_utc(d, time(7, 0), UK).isoformat(),
            "description": "ONS — UK Retail Sales index.",
            "source": "ONS",
            "source_url": "https://www.ons.gov.uk/businessindustryandtrade/retailindustry",
        })

        # ── EU CPI Flash — last business day of month at 11:00 CET ──
        d = last_business_day(year, month)
        out.append({
            "id": f"eu-cpi-{d.isoformat()}",
            "key": "eu_cpi",
            "title": "Eurozone CPI Flash",
            "region": "EU", "tag": "inflation",
            "datetime": to_utc(d, time(11, 0), CET).isoformat(),
            "description": "Eurostat — Eurozone flash HICP estimate (preliminary).",
            "source": "Eurostat",
            "source_url": "https://ec.europa.eu/eurostat/web/hicp",
        })

    # Weekly DESNZ UK pump fuel survey — every Monday at ~10:00 UK time
    d = today
    for _ in range(60):  # ~14 weeks
        d += timedelta(days=1)
        if d.weekday() == 0:  # Monday
            out.append({
                "id": f"uk-fuel-{d.isoformat()}",
                "key": "uk_fuel",
                "title": "UK Weekly Road Fuel Prices",
                "region": "UK", "tag": "energy",
                "datetime": to_utc(d, time(10, 0), UK).isoformat(),
                "description": "DESNZ — Weekly average UK pump prices for unleaded petrol and diesel.",
                "source": "DESNZ",
                "source_url": "https://www.gov.uk/government/statistics/weekly-road-fuel-prices",
            })
            if len({e["datetime"][:10] for e in out if e["key"] == "uk_fuel"}) > 12:
                break

    return out


# ─── Main ───────────────────────────────────────────────────────────────
def run() -> dict:
    today = date.today()
    horizon = today + timedelta(days=LOOKAHEAD_DAYS)

    all_events = []
    all_events.extend(fomc_events())
    all_events.extend(boe_events())
    all_events.extend(ecb_events())
    all_events.extend(monthly_pattern_events(today, months=6))

    # Filter to events between today and the horizon
    today_utc = datetime.combine(today, time(0, 0), tzinfo=UTC)
    end_utc = datetime.combine(horizon, time(23, 59), tzinfo=UTC)
    filtered = []
    seen_ids = set()
    for e in all_events:
        dt = datetime.fromisoformat(e["datetime"])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        if dt < today_utc or dt > end_utc:
            continue
        if e["id"] in seen_ids:
            continue
        seen_ids.add(e["id"])
        filtered.append(e)

    filtered.sort(key=lambda e: e["datetime"])

    payload = {
        "meta": {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "lookahead_days": LOOKAHEAD_DAYS,
            "count": len(filtered),
        },
        "events": filtered,
    }
    (DATA_DIR / "calendar.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    log.info("wrote calendar.json — %d events through %s", len(filtered), horizon.isoformat())
    return payload


if __name__ == "__main__":
    run()
