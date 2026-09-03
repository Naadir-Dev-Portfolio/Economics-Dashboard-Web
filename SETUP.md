# Setup and Operations

## Existing Deployment

Keep GitHub Pages configured as **Deploy from a branch: main / (root)**. The refresh workflow explicitly requests and verifies a Pages build after committing data.

Schedules remain unchanged:
- Full data: 06:30 and 18:30 UTC.
- News, calendars and health: hourly.
- Manual runs: Actions > Refresh economic data > Run workflow > all, data or news.

The workflow uses `contents: write` for data commits and `pages: write` for publishing. No personal access token or new scheduled task is required.

## First-Time Setup

1. In Settings > Pages, select branch **main**, folder **/ (root)**.
2. Enable repository Actions.
3. Add `FRED_API_KEY` as an Actions repository secret. Obtain a key from the [FRED account page](https://fredaccount.stlouisfed.org/apikeys). The authenticated API is preferred; public CSV is a fallback.
4. Run the workflow manually and inspect its data-quality summary and Pages step.

Organization policies or branch protections may refuse bot commits or Pages writes. Keep protections and explicitly authorize the intended workflow through the repository settings if necessary.

## Local Run

Run inside this project:

```bash
python -m pip install -r scripts/requirements.txt
python scripts/fetch_data.py
python scripts/fetch_news.py
python scripts/fetch_calendar.py
python scripts/build_health.py
python scripts/validate_data.py
python scripts/validate_data.py --report
python -m http.server 8000
```

Open [the local dashboard](http://localhost:8000). HTTP is required because the browser loads JSON files; opening the HTML directly is insufficient.

Set `FRED_API_KEY` in your shell for the authenticated API. Never put keys in tracked files, JavaScript or public URLs. The browser never receives the key.

For debugging, set `ONLY_SECTION` to a configuration section key and remove it afterward. `SKIP_SECTIONS` accepts comma-separated keys. Untouched section counts remain in the manifest.

## Failure Behaviour

- Requests use bounded timeouts and retries.
- Invalid/truncated responses cannot replace good stored data.
- Failed series retain observations and their actual last-success timestamp.
- Corrupt artifacts stop publication.
- Valid partial updates publish before source-quality failures are reported.
- Refresh jobs remain serialized; push races retry and failed rebases are aborted.
- An explicit Pages build is checked against the published commit.
- Unannounced calendar dates are not invented; provisional/cached dates stay labelled.

GitHub documents that [GITHUB_TOKEN pushes do not trigger branch-based Pages builds](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site). The workflow uses the [Pages build endpoint](https://docs.github.com/en/rest/pages/pages#request-a-github-pages-build).

## Future Maintenance

Routine annual BoE/ECB date edits are no longer required. Upstream schema changes, discontinued datasets, persistent blocking, TradingView symbol changes, repository permissions and scheduling policies can still require attention.

The data-frame and Yahoo client versions are pinned to the tested releases. Upgrade these deliberately and run the regression suite; scheduled refreshes must not silently pick up incompatible client changes.

The BLS fallback verified on 3 September 2026 covers announced releases through December 2026. It is used only on source failure and must not be extrapolated. The source is retried automatically and health reporting exposes missing coverage.

Data Health and the Actions summary identify affected sources. Monthly/quarterly reporting lag is not the same as a stale pipeline. See [DATA_SOURCES.md](DATA_SOURCES.md).

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend.test.cjs
```

Optional browser tests need Python Playwright and Edge. Their profile, screenshots and downloads stay inside the repository's ignored `.cache/` folder.
