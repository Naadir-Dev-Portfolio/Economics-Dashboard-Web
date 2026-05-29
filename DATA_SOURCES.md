# Data Sources

Every piece of data this dashboard shows, where it comes from, how it's pulled, and how reliable that pipeline is.

## What auto-updates vs what needs a hand once a year

| Category | Behaviour | Touched by GitHub Actions? |
|---|---|---|
| **All series data** (FRED, Yahoo, UK fuel, Land Registry HPI) | Self-updating every 6h | ✅ Yes |
| **Live newswire** | Self-updating hourly | ✅ Yes |
| **Live crypto + index tiles** | Browser fetches every 20s — no server work | ✅ Always live |
| **Hero TradingView chart** | TradingView's own live feed inside an iframe | ✅ Always live |
| **Monthly release calendar** (NFP, CPI, PCE, UK Labour, EU CPI, fuel survey) | **Self-extending forever** — computed from "first Friday of month at 8:30 ET" type rules | ✅ Yes |
| **FOMC meeting dates** | **Scraped live from federalreserve.gov on every refresh.** New years appear automatically. | ✅ Yes — scrape |
| **BoE MPC meeting dates** | Hardcoded list in `scripts/fetch_calendar.py` (BoE page is JS-rendered, no easy scrape). | ⚠️ Refresh annually each December |
| **ECB GovC meeting dates** | Hardcoded list in `scripts/fetch_calendar.py`. | ⚠️ Refresh annually each December |
| **Historical events** (1971-2025) | Hand-curated in `scripts/series_config.py` — historical, doesn't change. | n/a |
| **Education / Learn content** | Hand-curated in `data/education.json` — static content. | n/a |
| **TradingView symbol mappings** | Hardcoded in `assets/js/hero.js`. Changes only when TradingView retires a feed. | n/a |

**TL;DR:** The only thing requiring annual maintenance is two lists of ~8 dates each — BoE MPC and ECB GovC. The fix is roughly 1 minute each in December. Everything else is fully self-updating in perpetuity.

---

There are **seven distinct delivery mechanisms** in play:

| # | Mechanism | Used for | Lives in |
|---|---|---|---|
| 1 | **FRED API** | US/UK/EU/JP macro statistics (CPI, GDP, M2, rates, etc.) | `scripts/fetch_data.py` |
| 2 | **Yahoo Finance** via `yfinance` | Equity indices, commodities, FX historical | `scripts/fetch_data.py` |
| 3 | **gov.uk CSV scrape** | UK weekly pump-fuel prices (DESNZ) | `scripts/fetch_data.py` |
| 4 | **HM Land Registry CSV** | UK regional house prices monthly back to 1968 | `scripts/fetch_data.py` |
| 5 | **RSS aggregator** (Python) | Live news from BBC, Reuters, FT, Fed, BoE, ECB etc. | `scripts/fetch_news.py` |
| 6 | **CoinGecko REST API** (browser-side) | Real-time crypto prices in the live tiles | `assets/js/live-prices.js` |
| 7 | **TradingView Embedded Widget** | The hero chart — full interactive TradingView | `index.html` + `hero.js` |
| 8 | **Hardcoded schedules + patterns** | Central-bank meeting dates, monthly release pattern | `scripts/fetch_calendar.py` |

There's also an **8th — hand-curated content**: the historical events (`series_config.py → EVENTS`) and the education knowledge base (`data/education.json`).

---

## 1. FRED — Federal Reserve Economic Data

**URL:** https://fred.stlouisfed.org/ · **Auth:** Free API key required · **Rate limit:** Generous (120/min)

The St. Louis Fed maintains 800,000+ time series including not just US data but UK, EU, Japan and most G20 statistics via partner agencies (BIS, OECD, BoE, ECB).

**How we use it:** Each series in `scripts/series_config.py` with a `"fred"` field references a FRED series ID. The fetcher hits:

```
https://api.stlouisfed.org/fred/series/observations?series_id=<ID>&api_key=...&file_type=json
```

**Reliability:** ★★★★★ — Bulletproof. The Fed has the most stable economic data API in existence. Average uptime >99.9%.

**Maintenance:** Almost zero. Occasionally a FRED series is renamed or discontinued (we hit one of these — Switzerland's `IRSTCB01CHM156N` died, we swapped to `IR3TIB01CHM156N`). If a fetch returns 400, the script keeps the previous value from disk so the dashboard never goes blank.

### Series we pull from FRED (88 in total)

| Section | Series IDs |
|---|---|
| **Bonds** | DGS2, DGS5, DGS10, DGS30, DFII10, IRLTLT01GBM156N, IRLTLT01DEM156N, IRLTLT01FRM156N, IRLTLT01ITM156N, IRLTLT01JPM156N, IRLTLT01CAM156N, IRLTLT01AUM156N, T10Y2Y, T10Y3M |
| **Rates** | FEDFUNDS, INTGSBGBM193N, ECBDFR, IRSTCB01JPM156N, IRSTCB01CAM156N, IR3TIB01CHM156N, INTDSRAUM193N, SOFR, REAINTRATREARAT10Y |
| **Inflation** | CPIAUCSL, CPILFESL, PCEPI, PCEPILFE, GBRCPIALLMINMEI, CP0000EZ19M086NEST, JPNCPIALLMINMEI, DEUCPIALLMINMEI, FRACPIALLMINMEI, CANCPIALLMINMEI, AUSCPIALLQINMEI, PPIACO |
| **Money** | M2SL, M1SL, BOGMBASE, MABMM301GBM189N, MYAGM3EZM196N, MYAGM2JPM189N, WALCL, QUSPAMUSDA |
| **Housing** | QGBN628BIS, CSUSHPISA, USSTHPI, HOUST, ODCNPI03GBQ661N, QAUN628BIS, QJPN628BIS, QCAN628BIS, QCNN628BIS, QDER628BIS, QFRN628BIS, MORTGAGE30US, DRSFRMACBS |
| **Commodities** | DCOILWTICO, DCOILBRENTEU, GOLDAMGBD228NLBM, DHHNGSP, GASREGW, GASDESW |
| **FX** | DEXUSUK, DEXUSEU, DEXJPUS, DEXCHUS, DEXSZUS, DEXUSAL, DEXCAUS, DEXINUS, DEXBZUS, DEXMXUS, DTWEXBGS |
| **Employment** | UNRATE, LRHUTTTTGBM156S, LRHUTTTTEZM156S, LRHUTTTTDEM156S, LRHUTTTTFRM156S, LRHUTTTTJPM156S, LRHUTTTTCAM156S, LRHUTTTTAUM156S, SLUEM1524ZSCHN, PAYEMS, CIVPART, ICSA |
| **Macro** | GDPC1, NGDPRSAXDCGBQ, CLVMNACSCAB1GQDE, JPNRGDPEXP, INDPRO, RSXFS, GBRSLRTTO02IXOBSAM, USSLIND, UMCSENT, USREC |
| **Risk** | VIXCLS, STLFSI4, BAMLH0A0HYM2, BAMLC0A0CM, BAMLC0A2CAA, DRCCLACBS, BAMLH0A3HYC, NFCI |

**To check or change:** Open `scripts/series_config.py`. Every entry with a `fred` field. To find new series, search at https://fred.stlouisfed.org/.

---

## 2. Yahoo Finance via yfinance

**URL:** https://finance.yahoo.com · **Auth:** None · **Library:** `yfinance` (Python)

`yfinance` scrapes Yahoo's internal API. It's not officially sanctioned but it's the de-facto free source for global equity, commodity and FX historical data.

**How we use it:** Each series with a `"yahoo"` field has a Yahoo ticker. We download daily prices since 1970-01-01 and resample to monthly month-end.

**Reliability:** ★★★★ — Mostly stable but Yahoo occasionally changes their internal API and breaks `yfinance` for a few hours. The maintainers patch quickly. Errors are caught and the previous data preserved.

**Maintenance:** Update `yfinance` periodically (`pip install -U yfinance`). Already locked in `scripts/requirements.txt` with a minimum version.

### Series we pull from Yahoo (44 in total)

| Section | Tickers |
|---|---|
| **Markets** | ^GSPC, ^DJI, ^IXIC, ^RUT, ^FTSE, ^FTMC, ^GDAXI, ^FCHI, ^STOXX50E, ^IBEX, ^N225, ^HSI, 000001.SS, ^AXJO, ^BSESN, ^GSPTSE, ^BVSP |
| **Commodities** | CL=F, BZ=F, GC=F, SI=F, PL=F, NG=F, HG=F, ZW=F, ZC=F, KC=F, SB=F, UX=F |
| **FX** | GBPUSD=X, EURUSD=X, JPY=X, CNY=X, CHF=X, AUDUSD=X, CAD=X, INR=X, BRL=X, MXN=X, DX-Y.NYB |
| **Crypto** | BTC-USD, ETH-USD |
| **Volatility** | ^MOVE |

**Note:** For each series we also have a FRED fallback where available, so even if `yfinance` breaks we get the same data via FRED (just less frequently — FRED's price data is daily but lagged a few days vs Yahoo's near-real-time).

---

## 3. gov.uk DESNZ Weekly Road Fuel Prices

**URL:** https://www.gov.uk/government/statistics/weekly-road-fuel-prices · **Auth:** None

The Department for Energy Security and Net Zero publishes a CSV every Tuesday with average UK pump prices for unleaded petrol and diesel.

**How we use it:** `scripts/fetch_data.py → fetch_uk_fuel()`:
1. Fetches the gov.uk landing page
2. Uses regex to find the latest CSV URL (e.g. `https://assets.publishing.service.gov.uk/media/<hash>/weekly_road_fuel_prices_<date>.csv`)
3. Downloads + parses the CSV
4. Splits into two series (`uk_petrol`, `uk_diesel`)

**Coverage:** **2018-01 onwards, weekly** (~440 observations). The CSV file used to go back to 2003 but the current vintage starts 2018.

**Reliability:** ★★★★ — Stable for years. The risk is gov.uk redesigns the page and the CSV link pattern changes. Last verified working: 2026-05-25.

**Maintenance:** If you see the petrol/diesel cards going stale, open `scripts/fetch_data.py` and check the regex still matches the link on the live gov.uk page.

---

## 4. HM Land Registry UK House Price Index

**URL:** https://landregistry.data.gov.uk/ · **Auth:** None

The official UK HPI. Monthly average sale prices for **the UK, England, Wales, Scotland, Northern Ireland**, the 9 English regions, plus every county / borough / unitary authority. Goes back to **April 1968**.

**How we use it:** `scripts/fetch_data.py → fetch_uk_hpi_region()`:
1. Tries the last 6 monthly CSV URLs (e.g. `https://publicdata.landregistry.gov.uk/market-trend-data/house-price-index-data/UK-HPI-full-file-2026-03.csv`) to find the freshest
2. Downloads ~35 MB of CSV
3. Parses by `RegionName`, caches all 405 regions in memory on the first call
4. Returns the `AveragePrice` column for the requested region

**Coverage:** **1968-04 to most recent month** (~696 observations per region).

**Reliability:** ★★★★★ — This is an official government dataset published on schedule.

**Maintenance:** Zero. The URL pattern has been stable for years.

### Regions we expose

UK, England, Wales, Scotland, Northern Ireland, London, South East, South West, East Midlands, West Midlands, North West, North East, Yorkshire & The Humber, East of England.

Adding more is trivial — append entries to the `housing` section in `scripts/series_config.py` using `"uk_hpi": "Brighton and Hove"` or any other region name visible in the CSV.

---

## 5. RSS news aggregator

**URL:** various · **Auth:** None · **Code:** `scripts/fetch_news.py`

We pull 14 RSS feeds, dedupe by URL, score for keyword hits, and write 200 newsworthy items to `data/news.json` (plus the high-impact subset to `data/events_recent.json`).

| Source | URL | Region tags |
|---|---|---|
| BBC Business | feeds.bbci.co.uk/news/business/rss.xml | UK, GLOBAL |
| BBC World | feeds.bbci.co.uk/news/world/rss.xml | GLOBAL |
| Guardian Biz | theguardian.com/uk/business/rss | UK, GLOBAL |
| Guardian Econ | theguardian.com/business/economics/rss | UK, GLOBAL |
| Yahoo Finance | finance.yahoo.com/news/rssindex | US, GLOBAL |
| Reuters Biz | Google News reuters.com/business filter | GLOBAL |
| Reuters World | Google News reuters.com/world filter | GLOBAL |
| AP Economy | Google News apnews.com/economy filter | US, GLOBAL |
| Bloomberg | Google News bloomberg.com filter | GLOBAL |
| Federal Reserve | federalreserve.gov/feeds/press_monetary.xml | US |
| Bank of England | bankofengland.co.uk/rss/news | UK |
| ECB | ecb.europa.eu/rss/press.xml | EU |
| CNBC Markets | cnbc.com/id/15839069/device/rss/rss.html | US, GLOBAL |
| MarketWatch | feeds.marketwatch.com/marketwatch/topstories/ | US, GLOBAL |

**Reliability:** ★★★ — RSS is fundamentally fragile. Sources occasionally retire their feeds (Reuters did this in 2020, which is why we route through Google News). Federal Reserve and ECB endpoints change URL paths every few years. Failures are non-fatal: the script logs a warning and carries on.

**Maintenance:** If headlines stop refreshing, check the latest GH Actions run for "fetch failed" warnings. Edit the URL list in `scripts/fetch_news.py`.

### Keyword scoring

Each item gets tagged into categories (`monetary`, `inflation`, `geopolitical`, `crisis`, `oil`, `trade`, ...) via word-boundary keyword matching. Items that match a `MAJOR_TRIGGERS` keyword (`rate hike`, `invasion`, `ceasefire`, `strait of hormuz` etc.) get `impact: "high"` and get promoted to `events_recent.json` — the live geopolitical news that shows on the Event Timeline.

The `EXCLUDE_TERMS` list (`star wars`, `world cup`, `kardashian` etc.) suppresses entertainment / sports / celebrity matches.

To refine: edit `TAG_KEYWORDS`, `MAJOR_TRIGGERS`, and `EXCLUDE_TERMS` in `scripts/fetch_news.py`.

---

## 6. CoinGecko Simple Price API

**URL:** https://api.coingecko.com/api/v3/simple/price · **Auth:** None · **Rate limit:** ~30 calls/min on free tier

Used **client-side in the browser** (not via GitHub Actions) by `assets/js/live-prices.js` to power the realtime crypto tiles. Polled every 20 seconds while the dashboard is open.

```
GET https://api.coingecko.com/api/v3/simple/price
       ?ids=bitcoin,ethereum,solana,ripple,cosmos
       &vs_currencies=usd
       &include_24hr_change=true
```

**Reliability:** ★★★★ — CoinGecko is well-known and stable. CORS-enabled so it works from any browser without a proxy.

**Maintenance:** Zero. If they ever introduce mandatory auth on the free tier you'd need to either upgrade to their Pro plan or swap to CoinCap / Binance public REST. Both are drop-in replacements.

---

## 7. TradingView Embedded Widget

**URL:** https://www.tradingview.com/widget/ · **Auth:** None · **Mode:** Iframe-embedded JS widget

The hero chart isn't pulling its own data — TradingView's widget renders directly and we just pick the symbol. The widget supports candlesticks, indicators (RSI, MACD, moving averages), drawing tools, and timeframe switching from 1m → all-time.

**How we use it:** `assets/js/hero.js`:
- Loads `https://s3.tradingview.com/tv.js`
- Calls `new TradingView.widget({ symbol: 'FOREXCOM:SPX500', ... })`
- Recreates the widget when the dropdown changes

**Symbol prefixes we use** (all verified working in the free widget):

| Prefix | What | Examples |
|---|---|---|
| `FOREXCOM:` | CFD broker feed for indices | SPX500, UK100, GRXEUR (DAX), JPXJPY (Nikkei), HKG33 (Hang Seng) |
| `AMEX:` | NYSE-listed ETFs | SPY, DIA, IWM, EWC, EWZ, FXI |
| `NASDAQ:` | Nasdaq stocks/ETFs | QQQ |
| `TVC:` | TradingView aggregate feeds | US10Y, GB10Y, DE10Y, GOLD, UKOIL, USOIL, NATURALGAS, DXY, VIX |
| `FX:` | Major forex pairs | GBPUSD, EURUSD, USDJPY |
| `BINANCE:` | Crypto USDT pairs | BTCUSDT, ETHUSDT |
| `CBOT:`, `ICE:` | Agricultural futures | ZW1! (wheat), ZC1! (corn), KC1! (coffee), SB1! (sugar) |
| `CAPITALCOM:` | CFD broker fallback | EU50, ESP35, COPPER |
| `ECONOMICS:` | TradingView's macro feed | USINTR (Fed), GBINTR (BoE), EUINTR (ECB), USM2, USIRYY (US CPI), GBIRYY (UK CPI), USURATE, GBURATE, USGDPYY, GBGDPYY |

**Reliability:** ★★★★ — TradingView is rock solid. The risk is they restrict more symbols behind login (they already do this for `SP:SPX` and `DJ:DJI` direct — that's why we use the CFD/ETF proxies above). The "Open in TradingView" button on the hero opens the full chart on tradingview.com if anything stops working in the embed.

**Maintenance:** Zero unless TradingView adds new restrictions. Test by clicking through all the symbols in the hero dropdown.

---

## 8. Hardcoded schedules + computed patterns (calendar)

**Code:** `scripts/fetch_calendar.py`

The economic calendar has two ingredient types:

### a) Committee meeting dates — hardcoded

Once a year, each central bank publishes its meeting schedule. We hardcode them in Python constants:

- `FOMC_SCHEDULE` — Federal Reserve, 8 per year. Source: <https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm>
- `BOE_MPC_SCHEDULE` — Bank of England, 8 per year. Source: <https://www.bankofengland.co.uk/monetary-policy/decisions-and-minutes>
- `ECB_SCHEDULE` — European Central Bank Governing Council, 8 per year. Source: <https://www.ecb.europa.eu/press/calendars/mgcgc/>

**Maintenance:** **Refresh once a year, around December.** Open each source URL, copy the next year's dates, paste into the Python constants. The script already has 2026 and provisional 2027 dates so you've got time.

### b) Monthly releases — pattern-computed

For routine releases like NFP (first Friday), CPI (mid-month Wednesday), etc., we compute the next 6 months of dates from the published pattern. No maintenance — they just work forever, as long as the official agencies don't change their schedule conventions (which they rarely do).

Patterns encoded:
- US NFP — first Friday at 8:30 ET
- US CPI — 2nd Wednesday at 8:30 ET
- US PPI — day after US CPI
- US PCE — last full week, Thursday or Friday
- US Retail Sales — middle of month, Tue/Wed
- US M2 (H.6) — Tuesday around 25th, 16:00 ET
- UK CPI — 3rd Wednesday at 07:00 BST
- UK Labour Market — 2nd Tuesday at 07:00 BST
- UK GDP (monthly) — ~12th of month
- UK Retail Sales — 3rd Friday
- EU CPI Flash — last business day
- DESNZ UK fuel — every Monday

The exact rule for each lives in `monthly_pattern_events()` in `scripts/fetch_calendar.py`. To add another (e.g. EU PMI, US ADP), copy any existing block and adjust.

---

## Hand-curated content

Two things in this dashboard are written by hand and stored as JSON:

### Historical major events

**File:** `scripts/series_config.py` → `EVENTS = [...]`

42 events spanning 1971-2025: Nixon Shock, OPEC embargoes, Volcker, Black Monday, Plaza Accord, Asian crisis, dotcom, 9/11, GFC, COVID, Ukraine, SVB, etc.

These are static — they don't need refreshing. New "major" events from 2025 onwards arrive via the news aggregator (mechanism #5) and get auto-promoted to `data/events_recent.json` when they match high-impact keywords. The frontend merges both files on display.

### Education / Learn modal content

**File:** `data/education.json`

5 categories, 23 topics covering fundamentals, rates, bonds, inflation, money, stress signals, plus a full A-Z glossary. ~12,000 words of Markdown.

To expand: edit the JSON directly. Each topic has `id`, `title`, `tldr`, `body_md` (Markdown), and optional `related: ["topic-id-1", ...]` cross-refs. The modal supports search.

---

## Summary of pipelines

| Pipeline | Series count | Refresh cadence | Reliability |
|---|---|---|---|
| FRED | ~88 | Twice daily | ★★★★★ |
| Yahoo Finance | ~44 | Twice daily | ★★★★ |
| gov.uk DESNZ fuel | 2 | Twice daily | ★★★★ |
| Land Registry UK HPI | 14 | Twice daily | ★★★★★ |
| RSS news | up to 200 items | Hourly | ★★★ |
| CoinGecko (browser) | 5 crypto live tiles | Every 20s | ★★★★ |
| Yahoo (browser proxy) | 8 index/FX live tiles | Every 20s | ★★★ |
| TradingView widget | hero chart | Real-time | ★★★★ |
| Hardcoded committee schedule | 24 future meetings | Annual review needed | ★★★★★ |
| Pattern-computed releases | ~60 over 6 months | Twice daily | ★★★★★ |
| Hand-curated events | 42 historical | Static | ★★★★★ |
| Education content | 23 topics | Static | ★★★★★ |

---

## Where the security boundary sits

The only credential involved anywhere is the **FRED API key**. It's stored as a GitHub repository secret (`FRED_API_KEY`) and only injected into the workflow runner as an environment variable. It is **never** written to disk, never sent to the browser, and never appears in any file we commit.

Everything else is anonymous / unauthenticated public data.
