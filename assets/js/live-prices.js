/**
 * live-prices.js — realtime price tiles.
 *
 * Two feeds:
 *   • CoinGecko (no auth, browser-friendly) for crypto
 *   • Yahoo Finance via a public CORS proxy for indices / FX / commodities
 *
 * Polls every 20 s. When a tile's price changes we flash white-on-up,
 * red-on-down. The change-line shows a green ▲ or red ▼ arrow but the
 * change number itself stays in the neutral text colour, per user request.
 *
 * Falls back gracefully when the proxy is rate-limited (keeps the last
 * known value, just stops the flash animations).
 */
(function (global) {
  'use strict';

  // [id, label, region, kind, sourceId, unit, tvSymbol]
  // kind: 'yahoo' or 'coingecko'
  const MAJOR = [
    { id: 'sp500',   label: 'S&P 500',   region: 'US',     kind: 'yahoo',     src: '^GSPC',   unit: 'pts',   tv: 'FOREXCOM:SPX500' },
    { id: 'ftse100', label: 'FTSE 100',  region: 'UK',     kind: 'yahoo',     src: '^FTSE',   unit: 'pts',   tv: 'FOREXCOM:UK100' },
    { id: 'nasdaq',  label: 'NASDAQ',    region: 'US',     kind: 'yahoo',     src: '^IXIC',   unit: 'pts',   tv: 'FOREXCOM:NSXUSD' },
    { id: 'dax',     label: 'DAX',       region: 'DE',     kind: 'yahoo',     src: '^GDAXI',  unit: 'pts',   tv: 'FOREXCOM:GRXEUR' },
    { id: 'gold',    label: 'Gold',      region: 'GLOBAL', kind: 'yahoo',     src: 'GC=F',    unit: '$/oz',  tv: 'TVC:GOLD' },
    { id: 'brent',   label: 'Brent',     region: 'GLOBAL', kind: 'yahoo',     src: 'BZ=F',    unit: '$/bbl', tv: 'TVC:UKOIL' },
    { id: 'gbpusd',  label: 'GBP/USD',   region: 'FX',     kind: 'yahoo',     src: 'GBPUSD=X', unit: '',     tv: 'FX:GBPUSD' },
    { id: 'btc',     label: 'BTC',       region: 'CRYPTO', kind: 'coingecko', src: 'bitcoin', unit: 'USD',   tv: 'BINANCE:BTCUSDT' },
  ];

  const CRYPTO = [
    { id: 'btc',  label: 'Bitcoin',  region: 'BTC',  kind: 'coingecko', src: 'bitcoin',  unit: 'USD', tv: 'BINANCE:BTCUSDT' },
    { id: 'eth',  label: 'Ethereum', region: 'ETH',  kind: 'coingecko', src: 'ethereum', unit: 'USD', tv: 'BINANCE:ETHUSDT' },
    { id: 'sol',  label: 'Solana',   region: 'SOL',  kind: 'coingecko', src: 'solana',   unit: 'USD', tv: 'BINANCE:SOLUSDT' },
    { id: 'xrp',  label: 'XRP',      region: 'XRP',  kind: 'coingecko', src: 'ripple',   unit: 'USD', tv: 'BINANCE:XRPUSDT' },
    { id: 'atom', label: 'Cosmos',   region: 'ATOM', kind: 'coingecko', src: 'cosmos',   unit: 'USD', tv: 'BINANCE:ATOMUSDT' },
  ];

  const POLL_MS = 20_000;
  const lastPrice = {};       // tile id → previous numeric price (for flash detection)
  const tilesByKey = new Map();
  let poller = null;

  function init(sectionData) {
    const majorRow = document.getElementById('live-major');
    const cryptoRow = document.getElementById('live-crypto');
    if (!majorRow || !cryptoRow) return;
    majorRow.innerHTML = '';
    cryptoRow.innerHTML = '';

    [...MAJOR, ...CRYPTO].forEach(tile => {
      // Best-effort seed from local cached data so tiles render before the
      // first poll arrives.
      let seed = null;
      if (tile.id === 'sp500')   seed = sectionData?.markets?.series?.sp500;
      if (tile.id === 'ftse100') seed = sectionData?.markets?.series?.ftse100;
      if (tile.id === 'nasdaq')  seed = sectionData?.markets?.series?.nasdaq;
      if (tile.id === 'dax')     seed = sectionData?.markets?.series?.dax;
      if (tile.id === 'gold')    seed = sectionData?.commodities?.series?.gold;
      if (tile.id === 'brent')   seed = sectionData?.commodities?.series?.oil_brent;
      if (tile.id === 'gbpusd')  seed = sectionData?.fx?.series?.gbp_usd;
      if (tile.id === 'btc')     seed = sectionData?.fx?.series?.btc_usd;
      const el = buildTile(tile, seed);
      (CRYPTO.includes(tile) ? cryptoRow : majorRow).appendChild(el);
      tilesByKey.set(tile.id + (CRYPTO.includes(tile) ? '-c' : '-m'), el);
    });

    // Kick off the polling loop
    refresh();
    if (poller) clearInterval(poller);
    poller = setInterval(refresh, POLL_MS);
  }

  function buildTile(spec, seed) {
    const el = document.createElement('article');
    el.className = 'live-tile';
    el.dataset.id = spec.id;
    el.dataset.tv = spec.tv || '';
    el.dataset.kind = spec.kind;
    const seedPrice = seed?.stats?.last_value;
    el.innerHTML = `
      <div class="lt-label">${escapeHtml(spec.label)}<span class="lt-region">${spec.region}</span></div>
      <div class="lt-row">
        <span class="lt-value">${seedPrice != null ? formatPrice(seedPrice, spec) : '—'}</span>
        <span class="lt-unit">${spec.unit}</span>
      </div>
      <div class="lt-chg">
        <span class="lt-arrow">·</span>
        <span class="lt-chg-num">—</span>
      </div>
    `;
    el.addEventListener('click', () => {
      if (spec.tv && global.Hero) {
        const sel = document.getElementById('hero-symbol');
        if (sel) {
          let opt = Array.from(sel.options).find(o => o.value === spec.tv);
          if (!opt) {
            opt = document.createElement('option');
            opt.value = spec.tv;
            opt.textContent = spec.label;
            sel.appendChild(opt);
          }
          sel.value = spec.tv;
        }
        global.Hero.setSymbol(spec.tv);
        document.querySelector('.hero-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
    return el;
  }

  function formatPrice(v, spec) {
    if (v == null || isNaN(v)) return '—';
    if (spec.region === 'FX')      return v.toFixed(4);
    if (spec.region === 'CRYPTO' || spec.region === 'BTC' || spec.region === 'ETH'
        || spec.region === 'SOL' || spec.region === 'XRP' || spec.region === 'ATOM') {
      if (v > 1000) return v.toLocaleString(undefined, {maximumFractionDigits: 0});
      if (v > 10)   return v.toFixed(2);
      return v.toFixed(4);
    }
    if (v > 1000) return v.toLocaleString(undefined, {maximumFractionDigits: 0});
    return v.toLocaleString(undefined, {maximumFractionDigits: 2});
  }

  // ────────── data fetching ──────────
  async function refresh() {
    try {
      const [cg, yh] = await Promise.all([fetchCoinGecko(), fetchYahoo()]);
      applyResults(cg || {}, yh || {});
      const last = document.getElementById('live-last');
      if (last) last.textContent = 'last tick ' + new Date().toLocaleTimeString('en-GB', { hour12: false });
    } catch (e) {
      console.warn('[live-prices] poll failed', e);
    }
  }

  async function fetchCoinGecko() {
    const ids = [...new Set([...MAJOR, ...CRYPTO].filter(t => t.kind === 'coingecko').map(t => t.src))];
    if (!ids.length) return {};
    const url = `https://api.coingecko.com/api/v3/simple/price?ids=${ids.join(',')}&vs_currencies=usd&include_24hr_change=true`;
    try {
      const r = await fetch(url, { cache: 'no-store' });
      if (!r.ok) { global.HealthPanel?.setRuntimeStatus('coingecko', false); return {}; }
      const j = await r.json();
      global.HealthPanel?.setRuntimeStatus('coingecko', Object.keys(j).length > 0);
      return j;
    } catch (_) {
      global.HealthPanel?.setRuntimeStatus('coingecko', false);
      return {};
    }
  }

  // Yahoo Finance public quote endpoint; needs a CORS proxy from browsers.
  const CORS_PROXIES = [
    (u) => `https://corsproxy.io/?${encodeURIComponent(u)}`,
    (u) => `https://api.allorigins.win/raw?url=${encodeURIComponent(u)}`,
  ];

  async function fetchYahoo() {
    const symbols = [...new Set([...MAJOR, ...CRYPTO].filter(t => t.kind === 'yahoo').map(t => t.src))];
    if (!symbols.length) return {};
    const target = `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${encodeURIComponent(symbols.join(','))}`;
    for (const proxy of CORS_PROXIES) {
      try {
        const r = await fetch(proxy(target), { cache: 'no-store' });
        if (!r.ok) continue;
        const json = await r.json();
        const list = json?.quoteResponse?.result || [];
        if (!list.length) continue;
        const map = {};
        list.forEach(q => { map[q.symbol] = q; });
        global.HealthPanel?.setRuntimeStatus('yahoo_proxy', true);
        return map;
      } catch (_) { /* try next */ }
    }
    global.HealthPanel?.setRuntimeStatus('yahoo_proxy', false);
    return {};
  }

  function applyResults(cgData, yhData) {
    [...MAJOR, ...CRYPTO].forEach(spec => {
      let price = null, change = null;
      if (spec.kind === 'coingecko') {
        const row = cgData[spec.src];
        if (row) {
          price = row.usd;
          change = row.usd_24h_change;
        }
      } else if (spec.kind === 'yahoo') {
        const row = yhData[spec.src];
        if (row) {
          price = row.regularMarketPrice;
          change = row.regularMarketChangePercent;
        }
      }
      if (price == null) return;
      const inCrypto = CRYPTO.includes(spec);
      const key = spec.id + (inCrypto ? '-c' : '-m');
      const el = tilesByKey.get(key);
      if (!el) return;
      updateTile(el, spec, price, change);
    });
  }

  function updateTile(el, spec, price, change24h) {
    const valEl = el.querySelector('.lt-value');
    const chgArrow = el.querySelector('.lt-arrow');
    const chgNum = el.querySelector('.lt-chg-num');
    const chgRow = el.querySelector('.lt-chg');

    const prev = lastPrice[el.dataset.id];
    if (prev != null && !isNaN(prev) && price !== prev) {
      el.classList.remove('is-flash-up', 'is-flash-down');
      void el.offsetWidth;  // restart animation
      el.classList.add(price > prev ? 'is-flash-up' : 'is-flash-down');
    }
    lastPrice[el.dataset.id] = price;

    valEl.textContent = formatPrice(price, spec);

    if (change24h != null && !isNaN(change24h)) {
      const cls = change24h > 0 ? 'up' : change24h < 0 ? 'down' : '';
      const arrow = change24h > 0 ? '▲' : change24h < 0 ? '▼' : '·';
      chgArrow.className = 'lt-arrow ' + cls;
      chgArrow.textContent = arrow;
      chgNum.textContent = `${change24h >= 0 ? '+' : ''}${change24h.toFixed(2)}% 24h`;
      chgRow.classList.toggle('neg', change24h < 0);
    } else {
      chgArrow.textContent = '·';
      chgNum.textContent = '—';
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  global.LivePrices = { init };
})(window);
