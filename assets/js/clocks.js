/**
 * clocks.js — major exchange clocks and open/closed badges.
 */
(function (global) {
  'use strict';

  const EXCHANGES = [
    { id: 'LON', name: 'LONDON',   tz: 'Europe/London',   openH: 8,  closeH: 16 + 0.5 },
    { id: 'NYC', name: 'NEW YORK', tz: 'America/New_York', openH: 9.5, closeH: 16 },
    { id: 'TKY', name: 'TOKYO',    tz: 'Asia/Tokyo',      openH: 9,   closeH: 15 },
    { id: 'HKG', name: 'HONG KONG',tz: 'Asia/Hong_Kong',  openH: 9.5, closeH: 16 },
  ];

  function init() {
    const grid = document.getElementById('clocks-grid');
    if (!grid) return;
    grid.innerHTML = '';
    EXCHANGES.forEach(ex => {
      const t = document.createElement('div');
      t.className = 'clock-tile';
      t.dataset.tz = ex.tz;
      t.dataset.id = ex.id;
      t.dataset.open = ex.openH;
      t.dataset.close = ex.closeH;
      t.innerHTML = `
        <div class="ct-name">${ex.name}</div>
        <div class="ct-time">--:--</div>
        <div class="ct-status">—</div>
      `;
      grid.appendChild(t);
    });
    tick();
    setInterval(tick, 1000);

    // UTC clock in topbar
    setInterval(updateUTC, 1000);
    updateUTC();
  }

  function tick() {
    document.querySelectorAll('.clock-tile').forEach(t => {
      const tz = t.dataset.tz;
      const openH = parseFloat(t.dataset.open);
      const closeH = parseFloat(t.dataset.close);
      try {
        const now = new Date();
        const opts = { hour: '2-digit', minute: '2-digit', timeZone: tz, hour12: false };
        const time = new Intl.DateTimeFormat('en-GB', opts).format(now);
        t.querySelector('.ct-time').textContent = time;
        // Determine local hour-fraction in that tz
        const fmt = new Intl.DateTimeFormat('en-GB', { hour: 'numeric', minute: 'numeric', weekday: 'short', timeZone: tz, hour12: false });
        const parts = fmt.formatToParts(now);
        let hour = 0, min = 0, weekday = '';
        parts.forEach(p => {
          if (p.type === 'hour') hour = parseInt(p.value, 10);
          if (p.type === 'minute') min = parseInt(p.value, 10);
          if (p.type === 'weekday') weekday = p.value;
        });
        const localFrac = hour + min / 60;
        const isWeekend = weekday === 'Sat' || weekday === 'Sun';
        const isOpen = !isWeekend && localFrac >= openH && localFrac < closeH;
        const status = t.querySelector('.ct-status');
        if (isOpen) {
          status.textContent = 'OPEN';
          status.className = 'ct-status open';
        } else {
          status.textContent = 'CLOSED';
          status.className = 'ct-status closed';
        }
      } catch (e) {
        // ignore
      }
    });
  }

  function updateUTC() {
    const el = document.querySelector('#clock-utc .clock-time');
    if (!el) return;
    const now = new Date();
    el.textContent = now.toISOString().slice(11, 16);
  }

  global.Clocks = { init };
})(window);
