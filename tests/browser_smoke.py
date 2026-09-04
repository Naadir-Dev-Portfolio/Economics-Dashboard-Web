"""Local browser regression checks; screenshots stay in .cache/browser/."""
from datetime import date
import json
from pathlib import Path
import sys
import tempfile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache' / 'browser'
OUT.mkdir(parents=True, exist_ok=True)
URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:4173/'
errors = []
requests = []
results = {}


def ready(page):
    page.wait_for_function("document.querySelector('#hero-chart')?.dataset.seriesKey === 'markets/sp500'")
    page.locator('#boot-screen').wait_for(state='detached', timeout=20000)


def canvas_pixels(page):
    return page.evaluate("""() => {
      let count = 0;
      for (const canvas of document.querySelectorAll('#hero-chart canvas')) {
        const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
        for (let i = 3; i < data.length; i += 4) if (data[i] > 0) count++;
      }
      return count;
    }""")


with tempfile.TemporaryDirectory(dir=OUT, prefix='profile-') as profile, sync_playwright() as playwright:
    context = playwright.chromium.launch_persistent_context(
        profile, channel='msedge', headless=True,
        viewport={'width': 1440, 'height': 1100},
        accept_downloads=True, downloads_path=str(OUT / 'downloads'),
    )
    try:
        # Stored-data charts must work with all optional external feeds unavailable.
        context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(URL) else route.abort())
        page = context.pages[0]
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append(request.url))
        page.goto(URL, wait_until='domcontentloaded')
        ready(page)
        results['desktop_canvas_pixels'] = canvas_pixels(page)
        assert results['desktop_canvas_pixels'] > 1000
        option = page.evaluate("echarts.getInstanceByDom(document.getElementById('hero-chart')).getOption()")
        assert option['xAxis'][0]['splitLine']['show']
        assert option['xAxis'][0]['max'] == 'dataMax'
        assert len(option['dataZoom']) == 2
        page.screenshot(path=str(OUT / 'desktop.png'))
        labels = page.locator('#kpi-row .kpi-tile').evaluate_all('(tiles) => tiles.map(tile => tile.dataset.seriesKey)')
        assert labels[:7] == ['commodities/oil_brent', 'commodities/oil_wti', 'commodities/uk_petrol', 'rates/fed_funds', 'rates/boe_rate', 'rates/ecb_rate', 'money/us_m2'], labels
        assert page.locator('.hc-row[data-id="yahoo_proxy"]').count() == 0
        assert 'Scheduled data' in page.locator('#health-panel').inner_text()
        assert 'Optional browser feeds' in page.locator('#health-panel').inner_text()
        assert 'Not opened' in page.locator('.hc-row[data-id="tradingview"]').inner_text()
        clocks = page.locator('.clock-tile').evaluate_all("""tiles => tiles.map(tile => ({
          open: tile.querySelector('.ct-status').classList.contains('open'),
          color: getComputedStyle(tile.querySelector('.ct-time')).color,
          classes: tile.querySelector('.ct-time').className,
        }))""")
        for clock in clocks:
            assert ('open' if clock['open'] else 'closed') in clock['classes']
            assert clock['color'] == ('rgb(74, 222, 128)' if clock['open'] else 'rgb(255, 71, 87)'), clock
        results['kpi_order_and_clock_colours'] = 'passed'

        selections = page.locator('#hero-symbol option').evaluate_all('(options) => options.map(option => option.value)')
        for selection in selections:
            page.select_option('#hero-symbol', selection)
            assert page.locator('#hero-chart').get_attribute('data-series-key') == selection
            assert page.locator('#hero-name').inner_text().strip()
        results['exact_series_selections'] = len(selections)

        for section, sid, name in [
            ('employment', 'uk_unrate', 'UK Unemployment Rate'),
            ('macro', 'uk_gdp', 'UK Real GDP'),
            ('housing', 'uk_avg_price', 'UK Average House Price'),
            ('fx', 'eth_usd', 'Ethereum'),
            ('inflation', 'uk_cpi_yoy', 'UK CPI'),
        ]:
            page.locator(f'#cat-{section} .chip[data-sid="{sid}"]').click()
            page.locator(f'#cat-{section} .cat-tv').click()
            assert page.locator('#hero-chart').get_attribute('data-series-key') == f'{section}/{sid}'
            assert name in page.locator('#hero-name').inner_text()
        results['card_routing'] = 'passed'

        page.select_option('#hero-symbol', 'employment/uk_unrate')
        assert 'Apr-Jun 2026' in page.locator('#hero-asof').inner_text()
        assert page.locator('#hero-mode-live').is_disabled()
        page.select_option('#hero-symbol', 'macro/us_gdp')
        assert 'Q2 2026' in page.locator('#hero-asof').inner_text()

        page.select_option('#hero-symbol', 'fx/btc_usd')
        points = page.evaluate("echarts.getInstanceByDom(document.getElementById('hero-chart')).getOption().series[0].data")
        assert len(points) > 3000
        assert page.locator('#hero-date-to').input_value() <= date.today().isoformat()
        page.locator('[data-hero-range="1M"]').click()
        page.locator('#hero-date-from').fill('2026-08-01')
        page.locator('#hero-date-to').fill('2026-08-03')
        page.locator('#hero-date-to').blur()
        assert page.locator('#hero-date-from').input_value() == '2026-08-01'
        assert page.locator('#hero-date-to').input_value() == '2026-08-03'
        instance_id = page.evaluate("echarts.getInstanceByDom(document.getElementById('hero-chart')).id")
        page.evaluate("Hero.addAnnotation({date:'2026-08-02',title:'Regression marker'})")
        assert page.evaluate("echarts.getInstanceByDom(document.getElementById('hero-chart')).id") == instance_id
        assert page.locator('#hero-date-from').input_value() == '2026-08-01'
        page.evaluate('Hero.clearAnnotations()')
        page.locator('#hero-reset').click()
        before = page.locator('#hero-date-from').input_value()
        box = page.locator('#hero-chart').bounding_box()
        page.mouse.move(box['x'] + box['width'] * .6, box['y'] + box['height'] * .4)
        page.mouse.wheel(0, -700)
        page.wait_for_timeout(500)
        after = page.locator('#hero-date-from').input_value()
        assert before != after, 'Wheel zoom did not change the visible date range'
        results['wheel_zoom'] = {'before': before, 'after': after}
        page.locator('[data-hero-range="1Y"]').click()
        before_pan = page.locator('#hero-date-from').input_value()
        page.mouse.move(box['x'] + box['width'] * .45, box['y'] + box['height'] * .4)
        page.mouse.down()
        page.mouse.move(box['x'] + box['width'] * .6, box['y'] + box['height'] * .4, steps=10)
        page.mouse.up()
        page.wait_for_timeout(300)
        assert page.locator('#hero-date-from').input_value() != before_pan, 'Drag pan did not change the visible date range'
        results['drag_pan'] = 'passed'
        view = page.evaluate("echarts.getInstanceByDom(document.getElementById('hero-chart')).getOption().dataZoom[0]")
        for key in ['rsi', 'fast', 'slow']:
            page.locator(f'[data-indicator="{key}"]').click()
            assert page.locator(f'[data-indicator="{key}"]').get_attribute('aria-pressed') == 'true'
        option = page.evaluate("echarts.getInstanceByDom(document.getElementById('hero-chart')).getOption()")
        assert len(option['grid']) == 2 and len(option['series']) == 4
        assert option['dataZoom'][0]['startValue'] == view['startValue']
        assert option['dataZoom'][0]['endValue'] == view['endValue']
        assert option['dataZoom'][0]['xAxisIndex'] == [0, 1]
        averages = next(s['data'] for s in option['series'] if s['id'] == 'fast')
        assert averages[0][0] == points[19][0]
        assert abs(averages[0][1] - sum(p[1] for p in points[:20]) / 20) < 1e-6
        rsi_values = next(s['data'] for s in option['series'] if s['id'] == 'rsi')
        assert rsi_values[0][0] == points[14][0]
        assert all(0 <= p[1] <= 100 for p in rsi_values)
        for delta in [-10000, 10000, -20, 20]:
            box = page.locator('#hero-chart').bounding_box()
            page.mouse.move(box['x'] + box['width'] * .5, box['y'] + box['height'] * .4)
            before_zoom = page.evaluate("echarts.getInstanceByDom(document.getElementById('hero-chart')).getOption().dataZoom[0]")
            page.mouse.wheel(0, delta)
            page.wait_for_timeout(150)
            after_zoom = page.evaluate("echarts.getInstanceByDom(document.getElementById('hero-chart')).getOption().dataZoom[0]")
            ratio = (after_zoom['endValue'] - after_zoom['startValue']) / (before_zoom['endValue'] - before_zoom['startValue'])
            assert .92 < ratio < 1.09, (delta, ratio)
            assert (ratio < 1) == (delta < 0), (delta, ratio)
        assert page.evaluate("echarts.getInstanceByDom(document.getElementById('hero-chart')).getOption().series.find(s => s.id === 'rsi').data") == rsi_values
        page.locator('[data-indicator="rsi"]').click()
        assert len(page.evaluate("echarts.getInstanceByDom(document.getElementById('hero-chart')).getOption().grid")) == 1
        page.locator('[data-indicator="rsi"]').click()
        results['indicators_and_fine_wheel'] = 'passed'
        page.mouse.move(0, 0)
        page.locator('#hero-panel').screenshot(path=str(OUT / 'desktop-hero.png'))
        with page.expect_download() as download_info:
            page.locator('#hero-export').click()
        download_info.value.save_as(str(OUT / 'bitcoin.csv'))
        page.locator('#hero-mode-live').click()
        assert page.locator('#hero-tools').is_hidden()
        assert 'unavailable' in page.locator('#hero-chart').inner_text()
        page.locator('#hero-mode-archive').click()
        assert page.locator('#hero-chart').get_attribute('data-series-key') == 'fx/btc_usd'
        assert page.locator('#hero-annotations').is_hidden()
        page.evaluate("HealthPanel.setRuntimeStatus('coingecko', true); HealthPanel.setRuntimeStatus('coingecko', false)")
        assert page.locator('.hc-row[data-id="coingecko"] .hc-dot').get_attribute('class').endswith('warning')
        results['offline_and_degraded_states'] = 'passed'
        assert not any('corsproxy.io' in url or 'allorigins.win' in url or '/v7/finance/quote' in url for url in requests)
        healthy = page.evaluate('DataLoader.health()')
        notice = {'sources': [{'id': 'bis', 'name': 'BIS', 'status': 'warning', 'issues': [{'name': 'Example rate', 'reason': 'overdue observation'}]}]}
        page.evaluate("detail => dispatchEvent(new CustomEvent('data-health-updated', {detail}))", notice)
        assert page.locator('#stale-banner').is_visible()
        assert 'Example rate' in page.locator('#stale-body').inner_text()
        page.locator('#stale-dismiss').click()
        page.evaluate("detail => dispatchEvent(new CustomEvent('data-health-updated', {detail}))", notice)
        assert page.locator('#stale-banner').is_hidden()
        page.evaluate("detail => dispatchEvent(new CustomEvent('data-health-updated', {detail}))", healthy)
        assert page.locator('#stale-banner').is_hidden()
        results['health_notice_refresh_and_dismissal'] = 'passed'

        page.locator('#btn-open-calendar').click()
        page.locator('.cv-btn[data-view="list"]').click()
        assert 'official calendars' in page.locator('#calendar-status').inner_text()
        assert page.locator('.cal-row').count() > 5
        page.locator('.cal-row').first.click()
        assert 'Verified:' in page.locator('#evadd-desc').inner_text()
        with page.expect_download() as download_info:
            page.locator('#evadd-ics').click()
        download_info.value.save_as(str(OUT / 'release.ics'))
        results['calendar_export'] = 'passed'
        page.locator('#modal-event-add [data-close-modal]').last.click()
        page.locator('#modal-calendar').screenshot(path=str(OUT / 'calendar.png'))
        page.locator('#modal-calendar [data-close-modal]').last.click()

        page.set_viewport_size({'width': 390, 'height': 844})
        page.reload(wait_until='domcontentloaded')
        ready(page)
        page.select_option('#hero-symbol', 'fx/eth_usd')
        page.locator('#hero-panel').scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        results['mobile_canvas_pixels'] = canvas_pixels(page)
        assert results['mobile_canvas_pixels'] > 1000
        dimensions = page.evaluate("({width:innerWidth, scroll:document.documentElement.scrollWidth})")
        assert dimensions['scroll'] <= dimensions['width'] + 1, dimensions
        hero = page.locator('#hero-panel').bounding_box()
        for selector in ['#hero-symbol', '#hero-date-from', '#hero-date-to', '#hero-export', '[data-indicator="rsi"]', '[data-indicator="slow"]']:
            box = page.locator(selector).bounding_box()
            assert box['x'] >= hero['x'] and box['x'] + box['width'] <= hero['x'] + hero['width'] + 1, (selector, box, hero)
        for key in ['rsi', 'fast', 'slow']:
            assert page.locator(f'[data-indicator="{key}"]').get_attribute('aria-pressed') == 'true'
        assert len(page.evaluate("echarts.getInstanceByDom(document.getElementById('hero-chart')).getOption().grid")) == 2
        page.locator('#hero-panel').screenshot(path=str(OUT / 'mobile-hero.png'))
        page.screenshot(path=str(OUT / 'mobile.png'))
        assert not errors, errors
        results['page_errors'] = errors
        print(json.dumps(results, indent=2))
        (OUT / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    finally:
        context.close()
