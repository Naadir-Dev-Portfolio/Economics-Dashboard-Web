# Data Sources and Reliability

## Schedule

The existing workflow polls all series at **06:30 and 18:30 UTC**, and news/calendars hourly. Polling does not create new economic observations: monthly, quarterly and annual releases keep their native frequency.

After tests and artifact validation, generated JSON is committed to `main`. The workflow explicitly requests and checks the GitHub Pages build. A successful fetch and a successful deployment are separate checks.

## Sources

The authoritative configuration is `scripts/series_config.py` (166 series). Saved metadata includes provider, source URL, frequency, reporting period, last check, last successful fetch and freshness state.

| Source | Use | Details |
| --- | --- | --- |
| FRED | US/international macro statistics | Authenticated API preferred; public CSV fallback. |
| Yahoo Finance / yfinance | Indices, futures, FX and crypto | Full daily history plus overlapping recent history. A timestamped exchange quote can fill a missing current daily bar. No month-end resampling. |
| ONS | UK CPI, unemployment, GDP and retail | Official JSON with beta-endpoint fallback; reporting labels, publication dates and next-release dates retained. |
| BIS | National CPI and policy rates | Structured SDMX CSV; explicit country/unit filtering and missing-value handling. |
| Bank of England | UK M4 and annual growth | Official CSV, series LPMAUYN. |
| ECB | Euro-area M3 | Official CSV; EUR millions converted to billions. |
| Eurostat | Euro-area unemployment | EA21, total ages/sex, seasonally adjusted; empty or ambiguous dimension selections rejected. |
| HM Land Registry | UK average and regional house prices | Latest published full monthly CSV, downloaded once per refresh. |
| DESNZ | UK petrol/diesel | Weekly observations from the current official pump-price CSV. |

Yahoo futures are not spot prices. Optional TradingView feeds may differ by exchange, rollover and latency; the archive always displays the exact selected stored series.

## Interpretation

- Daily values use actual trading dates, never future month-end labels.
- ONS unemployment indexed in May can represent **April-June**; the publisher's reporting period is displayed.
- GDP dated April 1 represents **Q2**, not a daily measurement.
- Observation period, publication date and pipeline refresh time are distinct.
- Annual transformations match the same calendar period one year earlier, not fixed row offsets. Already-transformed ONS CPI is not transformed twice.
- Changes in percentage indicators use **percentage points**; basis-point series use basis-point changes. Other annual changes use percentages.
- Units and ratios are explicitly scaled. Monthly effective federal funds is not the FOMC target range.

Two discontinued series remain visibly marked **Historical only**: Japan M2 ending in 2017 and the UK dwelling-starts index ending in 2020. They are excluded from current-source counts. The discontinued US Leading Index was replaced by the correctly named Chicago Fed National Activity Index.

## Validation

`data_quality.py` rejects future dates, non-finite values, conflicting duplicates and empty responses. The fetcher also rejects older endpoints and materially truncated history. Deliberate definition changes require a `history_version` change; different economic definitions are not spliced.

Failed requests retain previous valid observations with `fetch_status: retained`; their last-success time does not advance. Health distinguishes overdue observations, failed refreshes, missing data and historical-only series. A new file timestamp alone cannot make an old observation healthy.

Freshness thresholds account for native frequency and reporting lag. Monthly/quarterly ages run from the period's end. Available next-release dates provide another overdue check. These thresholds are heuristics, not proof every upstream release has arrived.

Writes are atomic. `validate_data.py` checks artifacts before publication. Source-health reporting follows publication so individual outages raise a workflow failure without withholding other valid updates.

## Published Calendar

| Events | Official source |
| --- | --- |
| FOMC | [Federal Reserve](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) |
| BoE MPC | [Bank of England](https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates) |
| ECB | [Governing Council calendar](https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html) |
| US payrolls/CPI/PPI | [BLS ICS](https://www.bls.gov/schedule/news_release/bls.ics), individual release pages, then the [Federal Reserve release calendar](https://fred.stlouisfed.org/releases/calendar) |
| US GDP/PCE | [BEA ICS](https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics) |
| US retail | [Census calendar](https://www.census.gov/economic-indicators/calendar-listview.html) |
| UK CPI/labour/GDP/retail/house prices | [ONS calendar](https://www.ons.gov.uk/releasecalendar) |

Lookahead is at most 365 days, limited to published dates. No guessed first-Friday or second-Wednesday rules remain. Unannounced dates, including unsupported M2/fuel countdowns, are shown as not announced.

Named US, UK and European time zones handle daylight saving. Provisional dates stay provisional in the display and exports. Cached events retain their verification date.

BLS returned HTTP 403 locally and on GitHub on 3 September 2026. The live Federal Reserve calendar provides the same published dates and times, labelled `BLS via FRED`. US Central time is converted with daylight-saving rules. If both official sources fail, only previously verified dates survive; `calendar_verified.json` supplies a last-resort checked September-December 2026 seed. Live feeds are retried on every run, and cached status and missing coverage remain visible. No dates are extrapolated.

BoE/ECB dates now update automatically. `refresh_committee_dates.py` is only a compatibility alias for the automatic fetcher.

## Browser and Tests

Optional CoinGecko/proxied Yahoo quotes show actual quote timestamps. Failed requests do not create fake ticks; polls time out and cannot overlap.

The default hero is the stored-data archive. Pinned ECharts and Lucide bundles, with licenses, are served locally. TradingView remains optional; a loaded cross-origin iframe does not prove that its quotes are healthy.

```bash
python -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend.test.cjs
python scripts/validate_data.py
python scripts/validate_data.py --report
```

Browser checks require Python Playwright, Edge and a local HTTP server. Run `python tests/browser_smoke.py http://127.0.0.1:4173/`. They block optional external feeds and test every selection, routing, chart pixels, zoom, date ranges, exports and mobile layout. Artifacts stay in `.cache/browser/`.

External APIs and statistical definitions can change. The pipeline retries, validates and reports those changes; it cannot promise zero maintenance forever.
