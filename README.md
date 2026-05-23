# MACRO//OPS — Global Economics Dashboard

[![Refresh data](https://github.com/Naadir/Economics-Dashboard-Web/actions/workflows/update-data.yml/badge.svg)](.github/workflows/update-data.yml)

A live, self-updating economics command center. Static site hosted on GitHub Pages; data refreshed twice daily by GitHub Actions.

135+ time series across:

| Section | What's inside |
|---|---|
| **Markets** | S&P 500, FTSE 100/250, Dow, NASDAQ, Russell 2000, DAX, CAC, IBEX, Euro Stoxx, Nikkei, Hang Seng, Shanghai, ASX, Sensex, TSX, Bovespa |
| **Bonds** | 2/5/10/30-year US treasuries, US 10Y real (TIPS), UK gilts, German bunds, French OATs, Italian BTPs, Japan JGB, Canada, Australia, plus 10Y-2Y and 10Y-3M curves |
| **Rates** | Fed Funds, BoE, ECB, BoJ, BoC, SNB, RBA, SOFR, US 10Y real |
| **Inflation** | US CPI / Core CPI / PCE / Core PCE, UK, Eurozone, Japan, Germany, France, Canada, Australia, plus US PPI |
| **Money & Liquidity** | US M2 (level + YoY), M1, monetary base, Fed balance sheet, UK M4, Eurozone M3, Japan M2, US private credit-to-GDP |
| **Housing** | UK / US (Case-Shiller + FHFA) / Australia / Japan / Canada / China / Germany / France HPI, US + UK housing starts, US 30Y mortgage rate, US delinquency |
| **Commodities** | WTI & Brent crude, gold, silver, platinum, natural gas, copper, wheat, corn, coffee, sugar, uranium, US retail petrol & diesel |
| **FX** | GBP, EUR, JPY, CNY, CHF, AUD, CAD, INR, BRL, MXN vs USD, DXY dollar index, BTC, ETH |
| **Employment** | Unemployment for US/UK/Eurozone/Germany/France/Japan/Canada/Australia/China, US nonfarm payrolls, participation, jobless claims |
| **Macro** | US/UK/Germany/Japan real GDP (+ YoY), US industrial production, retail sales, UK retail, leading index, consumer sentiment, NBER recessions |
| **Risk** | VIX, MOVE index, St. Louis Fed Stress, Chicago NFCI, HY OAS, IG OAS, AA spread, credit-card delinquency, CCC junk spread |

Plus a hand-curated timeline of 42 major economic events from 1971 (Nixon Shock) to 2025.

---

## How it works

```
┌────────────────────────┐    ┌─────────────────────┐    ┌──────────────────┐
│ GitHub Actions (cron)  │ ─▶ │ scripts/fetch_data  │ ─▶ │ data/*.json      │
│ runs 06:30 & 18:30 UTC │    │ (FRED + Yahoo)      │    │ committed back   │
└────────────────────────┘    └─────────────────────┘    └────────┬─────────┘
                                                                  │
                                                                  ▼
                                                  ┌────────────────────────────┐
                                                  │ GitHub Pages serves        │
                                                  │ index.html + assets + data │
                                                  │ ECharts renders client-side│
                                                  └────────────────────────────┘
```

Frontend is pure HTML/CSS/vanilla-JS — no build step, no bundler, no framework. Each section lazy-loads its JSON only when expanded.

---

## Local development

```bash
# 1. Install Python deps (one-off)
pip install -r scripts/requirements.txt

# 2. Set your FRED API key (free: https://fred.stlouisfed.org/docs/api/api_key.html)
export FRED_API_KEY="your_key_here"           # macOS / Linux
$env:FRED_API_KEY = "your_key_here"           # PowerShell

# 3. Seed the data
python scripts/fetch_data.py

# 4. Serve the static site
python -m http.server 8000
# → open http://localhost:8000
```

Useful env vars while iterating on series:

| Variable | Effect |
|---|---|
| `ONLY_SECTION=bonds` | fetch only that section |
| `SKIP_SECTIONS=housing,fx` | skip those sections |

---

## Deploying to GitHub Pages

1. Push to GitHub.
2. **Settings → Pages** → Source: `Deploy from a branch` → Branch: `main` / `/ (root)`.
3. **Settings → Secrets and variables → Actions** → New repository secret named **`FRED_API_KEY`** (get a free key at <https://fred.stlouisfed.org/docs/api/api_key.html>).
4. **Actions** tab → enable workflows → run **"Refresh economic data"** manually once. Subsequent runs are scheduled at 06:30 and 18:30 UTC daily.

The dashboard lives at `https://<user>.github.io/<repo>/`.

---

## Adding a new series

Open [`scripts/series_config.py`](scripts/series_config.py) and append to the relevant section's `series` list:

```python
{"id": "us_savings_rate", "name": "US Personal Savings Rate",
 "region": "US", "unit": "%", "fred": "PSAVERT"},
```

Then re-run the fetcher. The frontend picks up new entries automatically.

Adding an entire new section: add a new key under `SECTIONS = { ... }` with `title`, `icon`, `blurb`, and a `series` list. Add an icon glyph in `assets/js/main.js` → `iconFor()`.

Adding a major economic event: append to `EVENTS = [...]` at the bottom of the same file.

---

## Stack

- **Charts** — [Apache ECharts](https://echarts.apache.org/) (CDN, no build)
- **Fonts** — Inter + JetBrains Mono (Google Fonts)
- **Data sources** — [FRED](https://fred.stlouisfed.org/) (St. Louis Fed), Yahoo Finance via [yfinance](https://github.com/ranaroussi/yfinance)
- **Automation** — GitHub Actions
- **Hosting** — GitHub Pages

---

## Note

For research and education. Not investment advice.

Built by [Naadir](https://github.com/Naadir).
