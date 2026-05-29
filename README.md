<div align="center">

<img src="./repo-card.png" alt="Economics Dashboard Web project card" width="100%" />
<br /><br />

<p><strong>Interactive browser-based economics dashboard — live macro data, yield curves, housing, employment and inflation. Currently in development.</strong></p>

<p>Built for individuals who want a Bloomberg-terminal-style read on the UK and global economy without the Bloomberg subscription — and as an open reference for anyone building their own data-driven dashboards.</p>

<p>
  <a href="#overview">Overview</a> |
  <a href="#what-problem-it-solves">What It Solves</a> |
  <a href="#feature-highlights">Features</a> |
  <a href="#screenshots">Screenshots</a> |
  <a href="#quick-start">Quick Start</a> |
  <a href="#tech-stack">Tech Stack</a>
</p>

<h3><strong>Made by Naadir | May 2026</strong></h3>

</div>

---

## Overview

A single-page dashboard that pulls together more than 160 macro time series — equity indices, bond yields, central bank rates, inflation, money supply, housing, commodities, FX, employment, GDP and risk indicators — and renders them in one cohesive UK-first view. The data refreshes itself on a schedule, the page hosts as static files, and there is no backend to run.

The workflow is built around three jobs running on GitHub Actions cron. Twice a day a Python pipeline pulls fresh observations from FRED, Yahoo Finance, the UK Land Registry's full HPI CSV, the gov.uk DESNZ weekly fuel survey and the ONS time-series API, then commits the resulting JSON back to the repository. Every hour a separate job aggregates 14 RSS news feeds and rebuilds the economic event calendar by scraping federalreserve.gov for the next FOMC dates and computing the rest of the monthly release schedule from published patterns. The browser then fetches static JSON, polls CoinGecko and Yahoo for real-time prices every 20 seconds, and embeds a TradingView widget for the live hero chart.

The practical outcome: instead of opening five different sites to check the macro picture — FRED for inflation, Yahoo for the FTSE, the Bank of England PDF for the next MPC, gov.uk for fuel prices, the Land Registry for house prices — everything sits on one page with a coherent narrative, an interactive event timeline, downloadable CSVs, an economic calendar that exports to Google or Outlook, and an in-app glossary for when the terminology gets in the way.

## What Problem It Solves

- Removes the tab-juggling between FRED, Yahoo Finance, ONS, gov.uk, the Bank of England and the ECB just to assemble a coherent macro picture.
- Replaces the once-and-forgotten "static screenshots in a blog post" approach with data that refreshes itself in perpetuity via GitHub Actions, with zero ongoing maintenance.
- Closes the visibility gap on UK regional housing — most public dashboards stop at "UK average" while Land Registry already publishes 14 distinct regions back to 1968.
- Compared with subscription tools (Bloomberg, Refinitiv, Trading Economics) it costs nothing, runs in any browser, and the code is fully auditable; compared with hand-rolling the same in Excel it stays current without anybody touching it.

### At a glance

| Track | Analyse | Compare |
|---|---|---|
| 162 macro time series across markets, rates, inflation, housing, commodities, FX, employment, GDP and risk | Hero TradingView chart with archive-mode event annotations, yield-curve inversions, KPI countdowns to the next central-bank decision | 14 UK regions of house prices side-by-side from 1968; UK vs US vs Eurozone inflation, rates, unemployment and GDP |
| Live realtime prices for the major indices and 5 crypto assets, polled every 20 s | Live RSS newswire from BBC, Reuters, FT, BoE, ECB, Fed, Bloomberg, AP, MarketWatch, CNBC, Guardian | Headline UK unemployment alongside age-band breakdowns (16-19, 20-24, 25-34, 55+) and gender splits |
| Per-source data-health panel showing last-fetch age, delivered/expected counts and runtime status | Auto-generated economic calendar covering the next 12 months of FOMC, BoE, ECB, NFP, CPI, PCE, retail and UK labour releases | "as of [date]" stamp on every chart so the publication lag of each source is always visible |

## Feature Highlights

- **Live realtime price tiles**, eight headline tiles (S&P, FTSE, Nasdaq, DAX, gold, Brent, GBP/USD, BTC) plus an expandable crypto strip with ETH/SOL/XRP/ATOM polled every 20 s from CoinGecko and a Yahoo CORS-proxied feed, with flash-on-tick animations.
- **162 time series with proper provenance**, sourced from FRED, Yahoo Finance, HM Land Registry, gov.uk DESNZ and the ONS direct API — choosing the freshest available source per series (e.g. ONS direct for UK unemployment beats the OECD-aggregated FRED version by ~3 months).
- **Interactive event timeline pinned to the chart**, 42 historical economic events (1971 Nixon Shock through 2025 tariffs) plus auto-promoted current events from the live news feed, each one clickable to draw a vertical annotation on the hero chart.
- **Self-updating economic calendar**, FOMC dates scraped from federalreserve.gov, BoE and ECB schedules hardcoded with an annual-refresh reminder banner, monthly releases (NFP, CPI, PCE, UK labour, EU CPI flash) all pattern-computed forward 12 months. Every event exports to Google Calendar, Outlook or .ics with one click.
- **Per-source health dashboard**, sidebar panel with green/amber/red status dots and an expandable detail row showing source URL, type, last-fetch age, delivered-vs-expected count and notes for each of the 9 data pipelines.
- **Built-in glossary and knowledge base**, 5 categories of macro education content (Fundamentals, Rates, Bonds, Inflation, Money, Stress Signals) plus a 60-term A-Z glossary, searchable in-app — for when "OAS spread" or "M2 YoY" needs explaining.
- **CSV export on every chart**, downloads the currently-focused series with commented-metadata headers and the most granular data the source provides.

### Core capabilities

| Area | What it gives you |
|---|---|
| **Markets** | Live + historical data for equity indices, bond yields, commodities, FX and crypto; TradingView hero chart with full intraday granularity; symbol switcher for 60+ instruments. |
| **Macro** | Inflation, rates, money supply, GDP and employment with UK + US age-bracket and gender splits; countdown timers to the next FOMC / BoE / ECB / NFP / CPI release. |
| **Housing** | UK average house prices and 13 regional breakdowns (London, South East, etc.) back to April 1968 from HM Land Registry, plus weekly UK pump petrol and diesel prices from DESNZ. |
| **Research** | Hand-curated 1971-2025 event timeline; auto-extending calendar exporting to Google/Outlook/.ics; in-app glossary; per-chart CSV download; full data-source health monitor. |

## Screenshots

<details>
<summary><strong>Open screenshot gallery</strong></summary>

<br />

<div align="center">
  <img src="./portfolio/Screen1.png" alt="Main dashboard view with hero TradingView chart, KPI strip and live tiles" width="88%" />
  <br /><br />
  <img src="./portfolio/Screen2.png" alt="Drill-down category panels and the data-health sidebar" width="88%" />
  <br /><br />
  <img src="./portfolio/Screen3.png" alt="Economic calendar modal in month view with one-click event export" width="88%" />
</div>

</details>

## Quick Start

```bash
# Clone the repo
git clone https://github.com/Naadir-Dev-Portfolio/Economics-Dashboard-Web.git
cd Economics-Dashboard-Web

# Install Python dependencies (for the data fetchers — only needed if running locally)
pip install -r scripts/requirements.txt

# Seed the data files (one-off; the GitHub Action does this on its schedule)
export FRED_API_KEY="your_key_here"           # macOS / Linux
$env:FRED_API_KEY = "your_key_here"            # PowerShell
python scripts/fetch_data.py
python scripts/fetch_news.py
python scripts/fetch_calendar.py
python scripts/build_health.py

# Serve the static site
python -m http.server 8000
# open http://localhost:8000
```

The dashboard runs entirely from static files (`index.html` + `assets/` + `data/*.json`), so any HTTP server works — GitHub Pages, Netlify, an S3 bucket, `python -m http.server` for local dev. The FRED API key is free (sign up at https://fred.stlouisfed.org/docs/api/api_key.html, takes 30 seconds) and is needed by the Python fetchers but never touches the browser. For full GitHub Actions auto-refresh setup, see [`SETUP.md`](./SETUP.md). For where every value comes from and how reliable each pipeline is, see [`DATA_SOURCES.md`](./DATA_SOURCES.md).

## Tech Stack

<details>
<summary><strong>Open tech stack</strong></summary>

<br />

| Category | Tools |
|---|---|
| **Primary stack** | `HTML. Javascript` | `CSS` | `Python` |
| **UI / App layer** | Vanilla HTML/CSS/JS — no framework, no build step. Apache ECharts for category and KPI charts, TradingView embedded widget for the hero chart, custom CSS-grid layout with covert-ops dark theme and full mobile responsive pass. |
| **Data / Storage** | Static JSON files in `data/` committed back to the repo on each refresh. No database. Per-section, per-source files plus `manifest.json`, `events.json`, `news.json`, `calendar.json`, `health.json` and `education.json`. |
| **Automation / Integration** | GitHub Actions cron (every hour for news, twice daily for full refresh); FRED REST API; `yfinance` library (Yahoo Finance); HM Land Registry full-file CSV scrape; gov.uk DESNZ weekly fuel CSV scrape; ONS direct time-series API; federalreserve.gov FOMC calendar scrape; RSS aggregator pulling from 14 news sources; CoinGecko REST + Yahoo via CORS-proxy for browser-side live tiles; TradingView embedded widget. |
| **Platform** | Web — hosted on GitHub Pages (cross-platform browser). Mobile-first responsive layout down to 375px viewport. |

</details>

## Architecture & Data

<details>
<summary><strong>Open architecture and data details</strong></summary>

<br />

### Application model

A GitHub Actions workflow fires on cron (06:30 and 18:30 UTC for the full pipeline, every hour for news only). The runner installs the Python requirements and runs four scripts: `fetch_data.py` pulls 162 time series from FRED / Yahoo / Land Registry / DESNZ / ONS into per-section JSON files; `fetch_news.py` aggregates 14 RSS feeds, dedupes by URL and keyword-scores items for the "major event" promotion; `fetch_calendar.py` scrapes federalreserve.gov for live FOMC dates and computes 12 months of monthly releases from published patterns; `build_health.py` walks every output file and produces `health.json` summarising per-source delivery and freshness. The runner then commits all the regenerated JSON back to `main`, which triggers GitHub Pages to redeploy.

In the browser, `main.js` boots, loads the static JSON in parallel, and hands each subsystem its slice — `hero.js` mounts the TradingView widget, `kpi.js` renders the headline tile carousel with countdown timers reading `calendar.json`, `live-prices.js` starts a 20-second poll loop against CoinGecko (no auth) and Yahoo Finance via a CORS proxy, `news.js` populates the marquee ticker and side panel, `events-timeline.js` wires the interactive annotations, `calendar-modal.js` renders the month-grid popup with iCal export, `education-modal.js` renders the searchable knowledge base, and `health-panel.js` drives the data-health sidebar. ECharts is loaded lazily for the category panels.

### Project structure

```text
Economics-Dashboard-Web/
+-- index.html                      Single-page dashboard
+-- assets/
|   +-- css/main.css                Dark-theme stylesheet + responsive breakpoints
|   +-- js/                         12 modules — one per panel/feature
|   |   +-- main.js                 Boot + orchestration
|   |   +-- data-loader.js          Cached JSON fetcher
|   |   +-- hero.js                 TradingView widget + archive overlay
|   |   +-- kpi.js                  Headline carousel + release countdowns
|   |   +-- live-prices.js          CoinGecko / Yahoo proxy polling
|   |   +-- charts.js               ECharts factory
|   |   +-- category.js             Drill-down matrix + CSV export
|   |   +-- ribbon.js               Auto-scrolling sparkline strip
|   |   +-- news.js                 RSS feed + top-bar ticker
|   |   +-- events-timeline.js      Interactive annotations
|   |   +-- calendar-modal.js       Month grid + .ics export
|   |   +-- education-modal.js      Glossary / knowledge base
|   |   +-- health-panel.js         Per-source status sidebar
|   |   +-- clocks.js               Multi-zone world clocks
|   +-- img/logo.png                Lion logo (favicon + topbar + boot screen)
+-- data/                           Auto-regenerated each refresh
|   +-- manifest.json               Section index + last-refresh stamp
|   +-- markets.json, bonds.json,   One file per category
|   |   rates.json, inflation.json,
|   |   money.json, housing.json,
|   |   commodities.json, fx.json,
|   |   employment.json, macro.json,
|   |   risk.json
|   +-- events.json                 Historical curated event timeline
|   +-- news.json                   200 latest aggregated RSS items
|   +-- calendar.json               Next 12 months of economic events
|   +-- health.json                 Per-source status snapshot
|   +-- education.json              Glossary + knowledge base
+-- scripts/
|   +-- series_config.py            Declarative list of every series
|   +-- fetch_data.py               Main data pipeline
|   +-- fetch_news.py               RSS aggregator
|   +-- fetch_calendar.py           Economic-calendar builder + FOMC scraper
|   +-- build_health.py             Health snapshot generator
|   +-- refresh_committee_dates.py  Interactive annual BoE/ECB update helper
|   +-- requirements.txt            requests, pandas, yfinance, python-dateutil
+-- .github/workflows/update-data.yml   Cron + commit-back workflow
+-- README.md                       This file
+-- SETUP.md                        GitHub Actions / Pages setup walkthrough
+-- DATA_SOURCES.md                 Per-pipeline reliability catalogue
+-- repo-card.png
+-- portfolio/
    +-- economics-dashboard-web.json
    +-- Screen1.png
    +-- Screen2.png
    +-- Screen3.png
```

### Data / system notes

- All data persists as plain JSON in the repository — no database, no server-side state. The pipeline is `git`-native: each refresh is a commit, history is a complete audit trail of how the dashboard's view of the world changed over time.
- The only credential the system uses is the FRED API key, stored as a GitHub repository secret (`FRED_API_KEY`) and injected only into the Action runner environment. It is never written to disk, never sent to the browser, and never appears in committed code. Every other data source is anonymous.
- Each chart shows an "as of [date]" stamp so users can never mistake a stale value for a current one. The data-health sidebar reports per-source freshness with green/amber/red status, and a top-of-page banner auto-shows if the two hand-curated date lists (BoE MPC, ECB Governing Council) are within 90 days of running out — telling the user exactly which one-line script to run to refresh them.

</details>

## Contact

Questions, feedback, or collaboration: `naadir.dev.mail@gmail.com`

<sub>HTML. Javascript | CSS | Python</sub>
