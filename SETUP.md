# Setup — getting the dashboard running on autopilot

This guide assumes you've never touched GitHub Actions or repository secrets. By the end you'll have a self-updating dashboard refreshing twice a day with **zero** ongoing maintenance.

Total time: **about 8 minutes**.

---

## What you're setting up

There are three moving pieces:

1. **GitHub Pages** — serves the static dashboard (`index.html`, CSS, JS) at a public URL.
2. **GitHub Actions** — a free CI service. It runs the Python data-fetcher scripts on a schedule, then commits the refreshed `data/*.json` files back to the repo.
3. **A FRED API key** — free, from the St. Louis Fed. Required for ~80% of the macro series. Without it, those series won't refresh (but Yahoo, CoinGecko, Land Registry and gov.uk data still will).

The whole pipeline:

```
   ┌──────────────────────┐    ┌─────────────────────┐    ┌──────────────────┐
   │ GitHub Actions cron  │ ─▶ │ scripts/fetch_*.py  │ ─▶ │ data/*.json      │
   │ 06:30 + 18:30 UTC    │    │ (FRED + Yahoo +     │    │ committed back   │
   │ (news hourly)        │    │  CoinGecko + ...)   │    │ to main branch   │
   └──────────────────────┘    └─────────────────────┘    └────────┬─────────┘
                                                                   │
                                                                   ▼
                                                ┌────────────────────────────────┐
                                                │ GitHub Pages serves            │
                                                │ index.html + data/*.json       │
                                                │ Browser fetches and renders    │
                                                └────────────────────────────────┘
```

---

## Step 1 — Get a FRED API key (2 min)

The Federal Reserve Bank of St. Louis runs **FRED** (Federal Reserve Economic Data), the single best source of macro time-series. It's free, and you get instant access.

1. Open <https://fredaccount.stlouisfed.org/login/secure/>
2. Click **Create New Account**. Use any email — they don't spam.
3. Once logged in, go to <https://fredaccount.stlouisfed.org/apikeys>
4. Click **Request API Key**.
5. Tick the "I agree" box and submit. You'll see a 32-character hex string like `abcdef0123456789...`.

**Copy that string.** You'll need it in Step 3.

---

## Step 2 — Make sure GitHub Pages is on (1 min)

1. Open your repo on github.com (`Naadir-Dev-Portfolio/Economics-Dashboard-Web`).
2. Click **Settings** (top-right of the repo header).
3. In the left sidebar click **Pages**.
4. Under **Build and deployment** → **Source**, choose **Deploy from a branch**.
5. Set **Branch** to `main`, folder `/ (root)`. Click **Save**.

Wait ~30 seconds. Refresh the Pages settings page — you should see a green tick and the URL:

> Your site is live at **https://naadir-dev-portfolio.github.io/Economics-Dashboard-Web/**

If it's already configured (because we set it up earlier), skip this step.

---

## Step 3 — Add the FRED API key as a repo secret (1 min)

This is the bit that lets GitHub Actions use your key without ever leaking it in code or logs.

1. Same repo **Settings** page.
2. Left sidebar: **Secrets and variables → Actions**.
3. Click **New repository secret**.
4. **Name:** `FRED_API_KEY` (exactly that — uppercase, with the underscore).
5. **Value:** paste the 32-char string from Step 1.
6. Click **Add secret**.

You're done. The string is now encrypted on GitHub's side and only accessible to the workflows in this repo.

> ⚠ Never paste the key into `index.html`, a Python file, or commit it to git. Always use the secret.

---

## Step 4 — Run the data fetcher for the first time (1 min)

The workflow is already in `.github/workflows/update-data.yml`. We just need to trigger it once manually so the data folder is populated; after that it'll run on its own schedule.

1. In the repo, click the **Actions** tab.
2. If you see "Workflows aren't being run on this repository", click the green **I understand my workflows, enable them** button.
3. In the left sidebar click **Refresh economic data**.
4. Top right: click **Run workflow** dropdown → **Run workflow** (leave the inputs default to `all`).
5. Wait ~90 seconds. Refresh the page. You should see a green tick next to the run.

That run:
- Fetched ~150 economic time series from FRED, Yahoo Finance, gov.uk DESNZ (fuel) and Land Registry (UK HPI)
- Fetched live news headlines from BBC / Reuters / Guardian / Fed / BoE / ECB
- Generated the next 6 months of upcoming release dates into `data/calendar.json`
- Committed all the updated JSON back to `main`

---

## Step 5 — Verify the dashboard is live (1 min)

Open <https://naadir-dev-portfolio.github.io/Economics-Dashboard-Web/>.

Check:
- ✓ The boot screen shows the lion logo, then fades out
- ✓ Live price tiles populate with values (S&P, FTSE, gold, BTC etc.)
- ✓ The 14 KPI cards show numbers (not "—")
- ✓ Click any card — the hero TradingView chart loads
- ✓ Click the **calendar icon** in the topbar — month grid opens with upcoming releases

If anything stays at "—", check the Actions run log (Step 4, click the run, then "refresh" job) and look for warnings. The most common cause is a typo'd secret name — it has to be exactly `FRED_API_KEY`.

---

## What runs and when (after setup)

| When | What runs | Why |
|---|---|---|
| **06:30 UTC** daily | Full fetch (data + news + calendar) | UK market open warm-up |
| **18:30 UTC** daily | Full fetch (data + news + calendar) | After US market close |
| **Every hour on the hour** | News + calendar only | Quick refresh of headlines without hammering FRED |
| **On every push** | Full fetch | So config changes propagate immediately |

All commits show up under user **`github-actions[bot]`** in the repo history with messages like `chore(data): scheduled refresh 2026-05-25 06:30Z [all]`.

---

## How to change the schedule

Edit `.github/workflows/update-data.yml`. The relevant lines:

```yaml
on:
  schedule:
    - cron: "30 6,18 * * *"   # full refresh: data + news + calendar
    - cron: "0 */1 * * *"     # hourly news + calendar refresh
```

[Crontab Guru](https://crontab.guru/) is helpful if you want to change these. Commit, push, and the new schedule applies on the next tick.

---

## Manually triggering a refresh

Any time:

1. Actions tab → **Refresh economic data** workflow → **Run workflow**.
2. Pick `all` / `data` / `news` from the dropdown.
3. Hit go.

Or from your terminal:

```bash
gh workflow run "Refresh economic data" --repo Naadir-Dev-Portfolio/Economics-Dashboard-Web
```

---

## Adding the FRED key with the gh CLI (alternative)

If you prefer the command line:

```bash
gh secret set FRED_API_KEY --repo Naadir-Dev-Portfolio/Economics-Dashboard-Web
# paste the key when prompted, hit Enter
```

---

## Troubleshooting

### "Live tiles show prices but KPI cards still say —"

The crypto / Yahoo-proxied prices populate from the browser. The KPI cards rely on `data/*.json`. If those are empty, the GitHub Action hasn't run yet (or it ran without the FRED key).

Fix: check **Actions** tab. Look at the latest run. If it succeeded but didn't commit, look at the log of the `Fetch market & macro data` step — you'll see `FRED_API_KEY not set — skipping ...` warnings. Re-check that the secret name is *exactly* `FRED_API_KEY`.

### "The calendar countdown says 'tbd'"

That indicator doesn't have an event in `data/calendar.json`. Some series are market-driven (oil, gold, BTC) and have no scheduled release date — they show "market-hours" instead. For things like CPI, NFP, FOMC, this means `scripts/fetch_calendar.py` hasn't run yet or failed silently. Run it once manually via Actions.

### "The deployed dashboard is stale"

The static files are cached aggressively by GitHub Pages. Force-refresh with `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac). The dashboard itself adds `?v=<timestamp>` to data file URLs so JSON updates are picked up on every load.

### "I want to test the fetcher locally first"

```bash
# install Python deps
pip install -r scripts/requirements.txt

# set the key in your shell
export FRED_API_KEY="your_key_here"          # macOS / Linux
$env:FRED_API_KEY = "your_key_here"          # PowerShell

# run the three fetchers
python scripts/fetch_data.py
python scripts/fetch_news.py
python scripts/fetch_calendar.py

# serve the static site
python -m http.server 8000
# open http://localhost:8000
```

---

## What lives where

| Folder / file | Purpose |
|---|---|
| `index.html` | Single-page dashboard |
| `assets/css/main.css` | Theme & layout |
| `assets/js/*.js` | Frontend modules — one per panel |
| `data/*.json` | Cached time-series + news + calendar + education content |
| `scripts/fetch_data.py` | Pulls FRED + Yahoo + gov.uk + Land Registry |
| `scripts/fetch_news.py` | RSS aggregator |
| `scripts/fetch_calendar.py` | Builds the economic-release calendar |
| `scripts/series_config.py` | Declarative list of every series we track |
| `.github/workflows/update-data.yml` | The cron + commit-back workflow |

---

## Done

That's it. The dashboard now refreshes itself twice a day. You don't need to touch anything unless you want to add new data series (`scripts/series_config.py`), change the look (`assets/css/main.css`), or extend the education content (`data/education.json`).

Questions: just open an issue on the repo or message me directly.
