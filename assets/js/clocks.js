/**
 * clocks.js — topbar world clocks + sidebar market-hours tiles.
 */
(function (global) {
  'use strict';

  const EXCHANGES = [
    { id: 'LON', name: 'LONDON',    tz: 'Europe/London',     openH: 8,   closeH: 16.5 },
    { id: 'NYC', name: 'NEW YORK',  tz: 'America/New_York',  openH: 9.5, closeH: 16 },
    { id: 'FFM', name: 'FRANKFURT', tz: 'Europe/Berlin',     openH: 9,   closeH: 17.5 },
    { id: 'TYO', name: 'TOKYO',     tz: 'Asia/Tokyo',        openH: 9,   closeH: 15 },
    { id: 'HKG', name: 'HONG KONG', tz: 'Asia/Hong_Kong',    openH: 9.5, closeH: 16 },
    { id: 'SYD', name: 'SYDNEY',    tz: 'Australia/Sydney',  openH: 10,  closeH: 16 },
  ];

  function init() {
    // Sidebar market-hours tiles
    const grid = document.getElementById('clocks-grid');
    if (grid) {
      grid.innerHTML = '';
      EXCHANGES.forEach(ex => {
        const t = document.createElement('div');
        t.className = 'clock-tile';
        t.dataset.tz = ex.tz;
        t.dataset.id = ex.id;
        t.dataset.open  = ex.openH;
        t.dataset.close = ex.closeH;
        t.innerHTML = `
          <div class="ct-name">${ex.name}</div>
          <div class="ct-time">--:--</div>
          <div class="ct-status">—</div>
        `;
        grid.appendChild(t);
      });
    }

    tick();
    setInterval(tick, 1000);
  }

  function tick() {
    // Sidebar tiles (already had this logic)
    document.querySelectorAll('.clock-tile').forEach(t => {
      const tz = t.dataset.tz;
      const openH  = parseFloat(t.dataset.open);
      const closeH = parseFloat(t.dataset.close);
      try {
        const now = new Date();
        const time = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: tz, hour12: false }).format(now);
        t.querySelector('.ct-time').textContent = time;
        const parts = new Intl.DateTimeFormat('en-GB', { hour: 'numeric', minute: 'numeric', weekday: 'short', timeZone: tz, hour12: false }).formatToParts(now);
        let hour = 0, min = 0, weekday = '';
        parts.forEach(p => {
          if (p.type === 'hour')    hour = parseInt(p.value, 10);
          if (p.type === 'minute')  min  = parseInt(p.value, 10);
          if (p.type === 'weekday') weekday = p.value;
        });
        const localFrac = hour + min / 60;
        const isWeekend = weekday === 'Sat' || weekday === 'Sun';
        const isOpen = !isWeekend && localFrac >= openH && localFrac < closeH;
        const status = t.querySelector('.ct-status');
        status.textContent = isOpen ? 'OPEN' : 'CLOSED';
        status.className = 'ct-status ' + (isOpen ? 'open' : 'closed');
      } catch (_) { /* ignore */ }
    });

    // Topbar world clocks
    document.querySelectorAll('.wc').forEach(wc => {
      const tz = wc.dataset.tz;
      if (!tz) return;
      try {
        const now = new Date();
        const showSeconds = wc.classList.contains('wc-primary');
        const fmt = new Intl.DateTimeFormat('en-GB', {
          hour: '2-digit', minute: '2-digit',
          second: showSeconds ? '2-digit' : undefined,
          timeZone: tz, hour12: false,
        });
        const timeEl = wc.querySelector('.wc-time');
        if (timeEl) timeEl.textContent = fmt.format(now);
        const dateEl = wc.querySelector('.wc-date');
        if (dateEl) {
          dateEl.textContent = new Intl.DateTimeFormat('en-GB', {
            weekday: 'short', day: 'numeric', month: 'short',
            timeZone: tz,
          }).format(now);
        }
      } catch (_) { /* ignore */ }
    });
  }

  global.Clocks = { init };
})(window);
