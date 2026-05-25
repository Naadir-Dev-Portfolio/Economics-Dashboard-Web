/**
 * main.js — MACRO//OPS orchestrator.
 *
 *   1. Boot screen + sanity check (manifest present?).
 *   2. Load all section data + events + news in parallel.
 *   3. Init hero, ribbon, news, events, clocks, category matrix.
 *   4. Wire region toggle, expand/collapse, situation report.
 */
(function () {
  'use strict';

  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  const state = {
    manifest: null,
    sectionData: {},
    events: [],
    news: { items: [] },
    narrative: null,
    region: 'GLOBAL',
  };

  document.addEventListener('DOMContentLoaded', boot);

  async function boot() {
    state.manifest = await DataLoader.manifest();
    if (!state.manifest) {
      showManifestError();
      hideBootScreen();
      return;
    }

    // Pull every section + events + news in parallel
    const keys = Object.keys(state.manifest.sections);
    const [sectionResults, events, news, narrative] = await Promise.all([
      Promise.all(keys.map(k => DataLoader.section(k))),
      DataLoader.events(),
      DataLoader.news(),
      DataLoader.narrative(),
    ]);
    keys.forEach((k, i) => { state.sectionData[k] = sectionResults[i]; });
    state.events = events && events.events ? events.events : [];
    state.news = news || { items: [] };
    state.narrative = narrative || null;

    initModules();
    wireTopbar();
    wireSidebar();
    renderReport();
    renderFooterUpdate();
    hideBootScreen();
  }

  function wireSidebar() {
    const shell = document.querySelector('.app-shell');
    const isMobile = () => window.matchMedia('(max-width: 980px)').matches;

    // Apply persisted state
    try {
      const collapsed = localStorage.getItem('navCollapsed') === '1';
      if (collapsed && !isMobile()) shell.classList.add('nav-collapsed');
    } catch (_) {}

    const toggle = () => {
      if (isMobile()) {
        shell.classList.toggle('nav-mobile-open');
      } else {
        shell.classList.toggle('nav-collapsed');
        try { localStorage.setItem('navCollapsed', shell.classList.contains('nav-collapsed') ? '1' : '0'); } catch (_) {}
      }
    };
    $('#sidebar-toggle')?.addEventListener('click', toggle);
    $('#nav-collapse')?.addEventListener('click', toggle);

    // Nav-item click → scroll to target + expand the section if it's a cat-panel
    $$('.nav-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const id = item.dataset.target;
        const el = document.getElementById(id);
        if (!el) return;
        if (id.startsWith('cat-')) {
          el.classList.remove('is-collapsed');
          // resize chart on next paint
          setTimeout(() => window.dispatchEvent(new Event('resize')), 60);
        }
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        if (isMobile()) shell.classList.remove('nav-mobile-open');
      });
    });

    // Scroll-spy: highlight active nav-item
    const targets = $$('.nav-item').map(i => i.dataset.target).filter(Boolean);
    const els = targets.map(id => document.getElementById(id)).filter(Boolean);
    if ('IntersectionObserver' in window && els.length) {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach(e => {
            if (e.isIntersecting) {
              const id = e.target.id;
              $$('.nav-item').forEach(i => i.classList.toggle('is-active', i.dataset.target === id));
            }
          });
        },
        { rootMargin: '-30% 0% -55% 0%', threshold: 0 }
      );
      els.forEach(el => observer.observe(el));
    }
  }

  function initModules() {
    window.Hero.init(state.sectionData);
    window.KPI.init(state.sectionData);
    window.NewsFeed.init(state.news);
    window.EventsTimeline.init(state.events);
    window.Ribbon.init(state.sectionData);
    window.Clocks.init();
    window.CategoryMatrix.init(state.manifest, state.sectionData);
  }

  function wireTopbar() {
    $$('.region-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        $$('.region-btn').forEach(b => b.classList.remove('is-active'));
        btn.classList.add('is-active');
        state.region = btn.dataset.region;
        applyRegion();
      });
    });
    $('#btn-collapse-all')?.addEventListener('click', () => window.CategoryMatrix.collapseAll());
    $('#btn-expand-all')?.addEventListener('click', () => window.CategoryMatrix.expandAll());

    // Live status pill
    const status = $('#live-status');
    if (state.manifest?.generated_at) {
      const ageHr = (Date.now() - new Date(state.manifest.generated_at).getTime()) / 3600000;
      if (ageHr > 36) {
        status.classList.add('is-stale');
        status.querySelector('.status-label').textContent = 'STALE';
      }
    }
  }

  function applyRegion() {
    window.Hero.setRegion(state.region);
    window.NewsFeed.setRegion(state.region);
    renderReport();
  }

  // ─────────────────────────────────────────────────────────────────
  // SITUATION REPORT — auto-generated from current data
  // ─────────────────────────────────────────────────────────────────
  function renderReport() {
    const tag = $('#report-time');
    const body = $('#report-body');
    if (!body) return;

    if (tag && state.manifest?.generated_at) {
      tag.textContent = new Date(state.manifest.generated_at).toISOString().slice(0, 16).replace('T', ' ') + 'Z';
    }

    // Prefer server-generated narrative if available
    if (state.narrative && state.narrative.text) {
      body.innerHTML = state.narrative.text;
      return;
    }

    body.innerHTML = buildClientNarrative();
  }

  function buildClientNarrative() {
    const get = (sec, sid) => state.sectionData[sec]?.series?.[sid];

    const region = state.region;
    const equity = region === 'UK' ? get('markets','ftse100')
                : region === 'EU' ? get('markets','dax')
                : region === 'ASIA' ? get('markets','nikkei')
                : get('markets','sp500');
    const bond = region === 'UK' ? get('bonds','uk_10y')
              : region === 'EU' ? get('bonds','de_10y')
              : region === 'ASIA' ? get('bonds','jp_10y')
              : get('bonds','us_10y');
    const rate = region === 'UK' ? get('rates','boe_rate')
              : region === 'EU' ? get('rates','ecb_rate')
              : region === 'ASIA' ? get('rates','boj_rate')
              : get('rates','fed_funds');
    const cpi = region === 'UK' ? get('inflation','uk_cpi_yoy')
             : region === 'EU' ? get('inflation','eu_cpi_yoy')
             : region === 'ASIA' ? get('inflation','jp_cpi_yoy')
             : get('inflation','us_cpi_yoy');

    const oil = get('commodities','oil_brent');
    const gold = get('commodities','gold');
    const dxy = get('fx','dxy');
    const gbp = get('fx','gbp_usd');
    const curve = get('bonds','curve_10y2y');
    const vix = get('risk','vix');

    const lines = [];
    if (equity?.stats) {
      const c = equity.stats.chg_1y_pct;
      lines.push(`<strong>${equity.name}</strong> ${dir(c)} ${signed(c)}% YoY`);
    }
    if (bond?.stats) {
      lines.push(`${bond.name.replace('-Year', 'Y').replace(' Treasury','')} <strong>${bond.stats.last_value.toFixed(2)}%</strong>`);
    }
    if (rate?.stats) {
      lines.push(`policy rate <strong>${rate.stats.last_value.toFixed(2)}%</strong>`);
    }
    if (cpi?.stats) {
      const v = cpi.stats.last_value;
      const hot = v > 3 ? '<span class="alert">hot</span>' : v < 2 ? '<span class="up">cool</span>' : 'near target';
      lines.push(`CPI <strong>${v.toFixed(1)}%</strong> (${hot})`);
    }
    if (curve?.stats) {
      const v = curve.stats.last_value;
      lines.push(v < 0
        ? `yield curve <span class="alert">inverted</span> (${v.toFixed(0)}bps)`
        : `curve normal ${v.toFixed(0)}bps`);
    }
    if (oil?.stats) {
      const c = oil.stats.chg_1y_pct;
      lines.push(`Brent <strong>$${oil.stats.last_value.toFixed(1)}</strong> ${dir(c)} ${signed(c)}% YoY`);
    }
    if (gold?.stats) {
      lines.push(`gold <strong>$${gold.stats.last_value.toFixed(0)}/oz</strong>`);
    }
    if (region !== 'UK' && dxy?.stats) {
      const c = dxy.stats.chg_1y_pct;
      lines.push(`DXY ${dir(c)} ${signed(c)}% YoY`);
    }
    if (region === 'UK' && gbp?.stats) {
      lines.push(`GBP/USD <strong>${gbp.stats.last_value.toFixed(4)}</strong>`);
    }
    if (vix?.stats) {
      const v = vix.stats.last_value;
      const tag = v > 25 ? '<span class="alert">elevated</span>' : v > 18 ? 'moderate' : '<span class="up">calm</span>';
      lines.push(`VIX <strong>${v.toFixed(1)}</strong> (${tag})`);
    }
    return lines.join(' &nbsp;·&nbsp; ');
  }

  function signed(v) { return v == null ? '—' : (v >= 0 ? '+' : '') + v.toFixed(2); }
  function dir(v) {
    if (v == null) return '';
    return v > 0 ? '<span class="up">up</span>' : v < 0 ? '<span class="down">down</span>' : 'flat';
  }

  function renderFooterUpdate() {
    const el = $('#footer-update');
    if (!el) return;
    el.textContent = state.manifest?.generated_at
      ? new Date(state.manifest.generated_at).toISOString().slice(0, 16).replace('T', ' ') + 'Z'
      : '—';
  }

  // ─────────────────────────────────────────────────────────────────
  function showManifestError() {
    const main = $('.main-grid');
    if (main) main.innerHTML = `
      <div style="grid-column:1/-1;padding:60px 20px;text-align:center;color:#989898;font-family:'JetBrains Mono', monospace;">
        <div style="font-size:13px;color:#dc2626;letter-spacing:0.22em;margin-bottom:10px;">⚠  CHANNEL OFFLINE</div>
        <div style="font-size:13px;line-height:1.7;">
          data/manifest.json not found.<br/>
          Run <code style="color:#fff;">python scripts/fetch_data.py</code> or trigger the GitHub Action.
        </div>
      </div>`;
  }

  function hideBootScreen() {
    const boot = $('#boot-screen');
    if (!boot) return;
    setTimeout(() => {
      boot.classList.add('is-hidden');
      setTimeout(() => boot.remove(), 500);
    }, 1000);
  }
})();
