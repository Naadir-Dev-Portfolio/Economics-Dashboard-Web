"""
Pull RSS / Atom feeds from major economic/financial sources, dedupe, tag,
score for "major-event" promotion, and write:

  data/news.json           — newest-first list of news items
  data/events_recent.json  — items the keyword scorer flagged as major

Designed to run hourly in GH Actions, using the shared bounded HTTP retries
and atomic JSON writer.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from data_quality import write_json
from source_providers import get

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("news")

# ─── Sources ─────────────────────────────────────────────────────────────
# (source label, RSS URL, default region tags)
SOURCES = [
    ("BBC Business",   "https://feeds.bbci.co.uk/news/business/rss.xml",                  ["UK", "GLOBAL"]),
    ("BBC World",      "https://feeds.bbci.co.uk/news/world/rss.xml",                     ["GLOBAL"]),
    ("Guardian Biz",   "https://www.theguardian.com/uk/business/rss",                     ["UK", "GLOBAL"]),
    ("Guardian Econ",  "https://www.theguardian.com/business/economics/rss",              ["UK", "GLOBAL"]),
    ("Yahoo Finance",  "https://finance.yahoo.com/news/rssindex",                         ["US", "GLOBAL"]),
    ("Reuters Biz",    "https://news.google.com/rss/search?q=when:24h+source:reuters.com+business&hl=en-US&gl=US&ceid=US:en", ["GLOBAL"]),
    ("Reuters World",  "https://news.google.com/rss/search?q=when:24h+source:reuters.com+world&hl=en-US&gl=US&ceid=US:en",   ["GLOBAL"]),
    ("AP Economy",     "https://news.google.com/rss/search?q=when:24h+source:apnews.com+economy&hl=en-US&gl=US&ceid=US:en",  ["US", "GLOBAL"]),
    ("Bloomberg",      "https://news.google.com/rss/search?q=when:24h+source:bloomberg.com&hl=en-US&gl=US&ceid=US:en",       ["GLOBAL"]),
    ("Federal Reserve","https://www.federalreserve.gov/feeds/press_monetary.xml",         ["US"]),
    ("Bank of England","https://www.bankofengland.co.uk/rss/news",                        ["UK"]),
    ("ECB",            "https://www.ecb.europa.eu/rss/press.xml",                         ["EU"]),
    ("CNBC Markets",   "https://www.cnbc.com/id/15839069/device/rss/rss.html",            ["US", "GLOBAL"]),
    ("MarketWatch",    "http://feeds.marketwatch.com/marketwatch/topstories/",            ["US", "GLOBAL"]),
]

# ─── Major-event keyword scoring ─────────────────────────────────────────
# Tags are keyed off SPECIFIC economic terms. We require word boundaries
# (regex \b) so "war" alone won't match "Star Wars".
TAG_KEYWORDS = {
    "monetary":     ["rate hike", "rate cut", "rate decision", "interest rate", "quantitative easing",
                     "quantitative tightening", "fed cuts", "fed raises", "fed holds",
                     "boe cuts", "boe raises", "boe holds", "ecb cuts", "ecb raises", "ecb holds",
                     "boj raises", "fomc", "monetary policy"],
    "rates":        ["policy rate", "base rate", "bond yield", "treasury yield", "gilt yield",
                     "bund yield", "10-year yield", "10y yield", "yield curve"],
    "oil":          ["oil price", "crude oil", "opec", "brent crude", "wti crude", "oil supply",
                     "oil demand", "oil exports"],
    "crisis":       ["bailout", "sovereign default", "bank collapse", "market crash", "bank run",
                     "credit crunch", "financial crisis", "liquidity crisis"],
    "geopolitical": ["invasion", "missile strike", "military strike", "war on", "war in",
                     "ceasefire", "sanctions on", "imposes sanctions", "blockade", "strait of hormuz",
                     "us-iran", "iran deal", "russia-ukraine", "nato",
                     "trade deal", "summit"],
    "trade":        ["tariff", "import tariff", "export ban", "trade war", "wto"],
    "fx":           ["dollar surges", "dollar falls", "yuan devaluation", "yen weakens",
                     "pound sterling", "currency intervention", "fx intervention"],
    "markets":      ["s&p 500", "ftse 100", "dax", "nikkei 225", "nasdaq", "sell-off",
                     "stock rally", "record high", "record low", "circuit breaker"],
    "credit":       ["credit downgrade", "credit upgrade", "ratings cut", "moody's downgrade",
                     "s&p downgrade", "fitch downgrade", "junk rating"],
    "inflation":    ["cpi", "inflation rate", "deflation", "core inflation", "headline inflation",
                     "cost of living"],
    "fiscal":       ["budget deficit", "fiscal stimulus", "tax cut", "tax hike", "government spending",
                     "debt ceiling"],
}

# Triggers that automatically promote impact = "high"
MAJOR_TRIGGERS = {
    "rate hike", "rate cut", "rate decision",
    "bailout", "sovereign default", "bank collapse", "market crash", "financial crisis",
    "invasion", "missile strike", "ceasefire", "sanctions on", "strait of hormuz", "iran deal",
    "tariff", "trade war",
    "record high", "record low",
    "credit downgrade", "ratings cut", "moody's downgrade", "fitch downgrade",
}

# Hard exclusions — if a headline mentions any of these alongside no economic
# keywords, don't promote it. Reduces "Star Wars" / sport / weather noise.
EXCLUDE_TERMS = {
    "star wars", "mandalorian", "tesla model",
    "shark attack", "weather", "wildfire", "earthquake",
    "world cup", "olympics", "football", "tennis",
    "netflix", "disney+", "youtube", "tiktok",
    "celebrity", "kardashian",
}

# ─── HTTP ────────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 MacroOps/1.0 (+https://github.com/Naadir-Dev-Portfolio)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

def fetch_url(url: str, timeout: int = 25) -> str | None:
    try:
        r = get(url, headers=HEADERS, timeout=timeout)
        # Be lenient with encoding. Many feeds claim UTF-8 but embed cp1252
        # smart quotes via HTML entities, while some genuinely serve UTF-8.
        # Try strict UTF-8 first; on errors, fall back to Windows-1252.
        raw = r.content
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("cp1252", errors="replace")
    except Exception as e:
        log.warning("fetch failed: %s — %s", url, e)
        return None

# ─── Parsing ─────────────────────────────────────────────────────────────
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc":   "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "media":   "http://search.yahoo.com/mrss/",
}

def parse_feed(xml: str, source: str, regions: list[str]) -> list[dict]:
    out = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        raise ValueError(f'Invalid feed XML: {e}') from e
    if root.tag != '{' + NS['atom'] + '}feed' and not (root.tag == 'rss' and root.find('channel') is not None):
        raise ValueError('Response is not an RSS or Atom feed')

    # RSS 2.0
    items = root.findall(".//item")
    if items:
        for it in items:
            entry = parse_rss_item(it, source, regions)
            if entry: out.append(entry)
        if not out:
            raise ValueError('RSS entries have no usable titles and links')
        return out

    # Atom
    entries = root.findall("atom:entry", NS)
    if entries:
        for e in entries:
            entry = parse_atom_entry(e, source, regions)
            if entry: out.append(entry)
        if not out:
            raise ValueError('Atom entries have no usable titles and links')
        return out

    return out

def text_of(el, tag: str, ns: dict | None = None) -> str:
    if ns:
        node = el.find(tag, ns)
    else:
        node = el.find(tag)
    if node is None:
        return ""
    return (node.text or "").strip()

def parse_rss_item(item, source: str, regions: list[str]) -> dict | None:
    title = text_of(item, "title")
    link = text_of(item, "link")
    pub = text_of(item, "pubDate") or text_of(item, "dc:date", NS)
    desc = text_of(item, "description")
    if not title or not link:
        return None
    published = parse_date(pub)
    return {
        "title": clean(title),
        "link": link.strip(),
        "source": source,
        "published": published,
        "summary": clean(strip_html(desc))[:280],
        "regions": regions,
    }

def parse_atom_entry(entry, source: str, regions: list[str]) -> dict | None:
    title = text_of(entry, "atom:title", NS)
    link_el = entry.find("atom:link", NS)
    link = link_el.get("href", "").strip() if link_el is not None else ""
    pub = text_of(entry, "atom:updated", NS) or text_of(entry, "atom:published", NS)
    desc = text_of(entry, "atom:summary", NS) or text_of(entry, "atom:content", NS)
    if not title or not link:
        return None
    published = parse_date(pub)
    return {
        "title": clean(title),
        "link": link,
        "source": source,
        "published": published,
        "summary": clean(strip_html(desc))[:280],
        "regions": regions,
    }

def parse_date(s: str) -> str:
    if not s:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:
        pass
    try:
        if s.endswith("Z"): s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s).astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

def strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "")

def clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    # Decode common HTML entities
    s = (s.replace("&amp;", "&").replace("&quot;", '"').replace("&#039;", "'")
           .replace("&#39;", "'").replace("&apos;", "'").replace("&lt;", "<").replace("&gt;", ">")
           .replace("&nbsp;", " "))
    # Some feeds (Google News re-encoded Bloomberg) leave U+FFFD where a
    # smart-quote should be. Best-effort: treat as an apostrophe inside a
    # word (e.g. "Doesn�t" → "Doesn't") and a regular hyphen elsewhere.
    if "�" in s:
        s = re.sub(r"(?<=\w)�(?=\w)", "'", s)
        s = s.replace("�", "—")
    return s

# ─── Scoring ─────────────────────────────────────────────────────────────
def tag_and_score(item: dict) -> tuple[list[str], int]:
    text = (item["title"] + " " + item.get("summary", "")).lower()
    # Hard exclude obvious noise (entertainment, sport, weather, …)
    if any(term in text for term in EXCLUDE_TERMS):
        return [], 0
    tags = []
    score = 0
    for tag, kws in TAG_KEYWORDS.items():
        matched = False
        for kw in kws:
            if kw in text:
                matched = True
                if kw in MAJOR_TRIGGERS:
                    score += 3
                else:
                    score += 1
        if matched and tag not in tags:
            tags.append(tag)
    return tags, score

# ─── Main ────────────────────────────────────────────────────────────────
def run() -> dict:
    started = datetime.now(timezone.utc)
    all_items: list[dict] = []
    seen = set()
    by_source = {}
    feed_status = {}
    try:
        previous = json.loads((DATA_DIR / 'news.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        previous = {}
    checked = started.isoformat(timespec='seconds')

    for label, url, regions in SOURCES:
        report = {'url': url, 'checked_at': checked, 'status': 'ok', 'last_success': checked}
        try:
            xml = fetch_url(url)
            if not xml:
                raise ValueError('HTTP request failed after retries')
            items = parse_feed(xml, label, regions)
            by_source[label] = len(items)
        except ValueError as error:
            by_source[label] = 0
            report.update(status='error', error=str(error), last_success=previous.get('meta', {}).get('feed_status', {}).get(label, {}).get('last_success'))
            log.warning('%s: %s; retaining previous headlines', label, error)
            items = []
        if not items:
            items = [item for item in previous.get('items', []) if item.get('source') == label]
        feed_status[label] = report
        for it in items:
            host = urlparse(it["link"]).netloc + urlparse(it["link"]).path
            key = (host, it["title"].lower()[:80])
            if key in seen:
                continue
            seen.add(key)
            tags, score = tag_and_score(it)
            it["tags"] = tags
            it["score"] = score
            it["impact"] = "high" if score >= 4 else "med" if score >= 2 else "low"
            all_items.append(it)

    # Sort newest first
    all_items.sort(key=lambda x: x["published"], reverse=True)
    all_items = all_items[:200]

    payload = {
        "meta": {
            "generated_at": started.isoformat(timespec="seconds"),
            "count": len(all_items),
            "by_source": by_source,
            "feed_status": feed_status,
        },
        "items": all_items,
    }
    write_json(DATA_DIR / 'news.json', payload)
    log.info("wrote news.json — %d items; %d responding feeds", len(all_items), sum(r['status'] == 'ok' for r in feed_status.values()))

    # Recent events — promote high/med items, dedupe by a more aggressive title match
    recent_events = []
    title_seen = set()
    for it in all_items:
        if it["impact"] == "low":
            continue
        norm = re.sub(r"\W+", " ", it["title"].lower())[:60]
        if norm in title_seen:
            continue
        title_seen.add(norm)
        recent_events.append({
            "date": it["published"][:10],
            "title": it["title"],
            "blurb": it.get("summary", "")[:200],
            "tag": it["tags"][0] if it["tags"] else "markets",
            "impact": it["impact"],
            "source": it["source"],
            "link": it["link"],
        })
    events_payload = {
        "meta": {
            "generated_at": started.isoformat(timespec="seconds"),
            "count": len(recent_events),
        },
        "events": recent_events[:80],
    }
    write_json(DATA_DIR / 'events_recent.json', events_payload)
    log.info("wrote events_recent.json — %d promoted events", len(recent_events))

    return payload


if __name__ == "__main__":
    run()
