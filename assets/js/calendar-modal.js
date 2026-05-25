/**
 * calendar-modal.js — the economic-calendar popup.
 *
 * Reads data/calendar.json. Two views:
 *   • LIST  — grouped by day, every upcoming release
 *   • MONTH — calendar grid of the next month
 *
 * Clicking a row pops the add-to-calendar mini-modal with:
 *   • Google Calendar quick-add link
 *   • Outlook quick-add link
 *   • Apple / Thunderbird .ics download
 *   • Link to the official source page
 */
(function (global) {
  'use strict';

  const state = {
    events: [],
    view: 'list',
  };

  function init(calendar) {
    state.events = (calendar && calendar.events) || [];

    // Open triggers
    document.getElementById('btn-open-calendar')?.addEventListener('click', open);
    document.querySelectorAll('.nav-modal[data-modal="calendar"]').forEach(el => {
      el.addEventListener('click', (e) => { e.preventDefault(); open(); });
    });

    // View toggle
    document.querySelectorAll('.cv-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.cv-btn').forEach(b => b.classList.remove('is-active'));
        btn.classList.add('is-active');
        state.view = btn.dataset.view;
        render();
      });
    });

    // Close handlers (shared modal scrim + close button)
    bindModalClose('modal-calendar');
    bindModalClose('modal-event-add');
  }

  function bindModalClose(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.querySelectorAll('[data-close-modal]').forEach(el => {
      el.addEventListener('click', () => { modal.hidden = true; });
    });
  }

  function open() {
    const modal = document.getElementById('modal-calendar');
    if (!modal) return;
    modal.hidden = false;
    render();
  }

  function render() {
    const body = document.getElementById('calendar-body');
    if (!body) return;
    if (!state.events.length) {
      body.innerHTML = '<div class="modal-loading">› no events — run scripts/fetch_calendar.py</div>';
      return;
    }
    if (state.view === 'list') renderList(body);
    else renderMonth(body);
  }

  function renderList(body) {
    const now = Date.now();
    const future = state.events.filter(e => new Date(e.datetime).getTime() >= now - 3_600_000)
                               .sort((a, b) => a.datetime.localeCompare(b.datetime));
    if (!future.length) {
      body.innerHTML = '<div class="modal-loading">› no upcoming events</div>';
      return;
    }
    const groups = {};
    future.forEach(e => {
      const d = e.datetime.slice(0, 10);
      (groups[d] = groups[d] || []).push(e);
    });
    const out = ['<div class="cal-list">'];
    Object.keys(groups).sort().forEach(day => {
      const human = new Date(day + 'T00:00:00Z').toLocaleDateString('en-GB', {
        weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
      });
      const rel = relativeDay(day);
      out.push(`<div class="cal-day-head"><span class="cal-day-date">${human}</span><span class="cal-day-rel">${rel}</span></div>`);
      groups[day].forEach(e => {
        const local = new Date(e.datetime);
        const time = local.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false });
        const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        const eid = encodeURIComponent(e.id);
        out.push(`<div class="cal-row" data-event-id="${eid}">
          <div><div class="cal-row-time">${time}</div><div class="cal-row-tz">${tz}</div></div>
          <div class="cal-row-region">${e.region}</div>
          <div>
            <div class="cal-row-title">${escapeHtml(e.title)}</div>
            <div class="cal-row-source">${escapeHtml(e.source || '')}</div>
          </div>
          <div class="cal-row-add">+ ADD</div>
        </div>`);
      });
    });
    out.push('</div>');
    body.innerHTML = out.join('');
    body.querySelectorAll('.cal-row').forEach(row => {
      const id = decodeURIComponent(row.dataset.eventId);
      row.addEventListener('click', () => openAddModal(state.events.find(e => e.id === id)));
    });
  }

  function relativeDay(iso) {
    const t = new Date(iso + 'T12:00:00Z').getTime();
    const days = Math.round((t - Date.now()) / 86_400_000);
    if (days === 0) return 'TODAY';
    if (days === 1) return 'TOMORROW';
    if (days < 7)   return `in ${days} days`;
    if (days < 30)  return `in ${Math.round(days/7)} weeks`;
    return `in ${Math.round(days/30)} months`;
  }

  function renderMonth(body) {
    const now = new Date();
    const year = now.getFullYear(), month = now.getMonth();
    const first = new Date(Date.UTC(year, month, 1));
    const last  = new Date(Date.UTC(year, month + 1, 0));
    const startWeekday = (first.getUTCDay() + 6) % 7;   // 0 = Monday
    const totalCells = Math.ceil((startWeekday + last.getUTCDate()) / 7) * 7;

    const days = [];
    for (let i = 0; i < totalCells; i++) {
      const d = new Date(Date.UTC(year, month, 1 - startWeekday + i));
      days.push(d);
    }

    const eventsByDay = {};
    state.events.forEach(e => {
      const k = e.datetime.slice(0, 10);
      (eventsByDay[k] = eventsByDay[k] || []).push(e);
    });

    const heads = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
      .map(d => `<div class="cal-month-head">${d}</div>`).join('');
    const todayKey = new Date().toISOString().slice(0, 10);
    const cells = days.map(d => {
      const iso = d.toISOString().slice(0, 10);
      const inMonth = d.getUTCMonth() === month;
      const isToday = iso === todayKey;
      const evts = eventsByDay[iso] || [];
      const items = evts.slice(0, 4).map(e => {
        const eid = encodeURIComponent(e.id);
        return `<span class="cm-evt" data-event-id="${eid}" title="${escapeHtml(e.title)}">${escapeHtml(e.title)}</span>`;
      }).join('');
      const more = evts.length > 4 ? `<span class="cm-evt" style="background:transparent;border-left:none;color:var(--tx-3)">+${evts.length-4} more</span>` : '';
      return `<div class="cal-month-cell${inMonth ? '' : ' other-month'}${isToday ? ' is-today' : ''}">
        <div class="cm-d">${d.getUTCDate()}</div>${items}${more}
      </div>`;
    }).join('');
    body.innerHTML = `<div class="cal-month">${heads}${cells}</div>`;
    body.querySelectorAll('[data-event-id]').forEach(el => {
      const id = decodeURIComponent(el.dataset.eventId);
      el.addEventListener('click', () => openAddModal(state.events.find(e => e.id === id)));
    });
  }

  // ─────────────────────────── ADD-TO-CAL ───────────────────────────
  function openAddModal(event) {
    if (!event) return;
    const modal = document.getElementById('modal-event-add');
    if (!modal) return;

    const dt = new Date(event.datetime);
    const dtEnd = new Date(dt.getTime() + 30 * 60_000);
    document.getElementById('evadd-tag').textContent = `${event.region} · ${(event.tag || '').toUpperCase()}`;
    document.getElementById('evadd-title').textContent = event.title;
    document.getElementById('evadd-when').textContent =
      dt.toLocaleString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })
      + ' · ' + Intl.DateTimeFormat().resolvedOptions().timeZone;
    document.getElementById('evadd-desc').textContent = event.description || '';

    // Google Calendar quick add
    const fmt = (d) => d.toISOString().replace(/[-:]|\.\d{3}/g, '');
    const gcalUrl = 'https://www.google.com/calendar/render?action=TEMPLATE'
      + '&text=' + encodeURIComponent(event.title)
      + '&dates=' + fmt(dt) + '/' + fmt(dtEnd)
      + '&details=' + encodeURIComponent((event.description || '') + (event.source_url ? '\n\nSource: ' + event.source_url : ''))
      + '&location=' + encodeURIComponent(event.source || '');
    document.getElementById('evadd-google').href = gcalUrl;

    // Outlook web
    const outlookUrl = 'https://outlook.live.com/calendar/0/deeplink/compose?path=/calendar/action/compose&rru=addevent'
      + '&subject=' + encodeURIComponent(event.title)
      + '&startdt=' + dt.toISOString()
      + '&enddt=' + dtEnd.toISOString()
      + '&body=' + encodeURIComponent(event.description || '');
    document.getElementById('evadd-outlook').href = outlookUrl;

    // .ics download
    document.getElementById('evadd-ics').onclick = () => downloadIcs(event);

    // Source link
    const src = document.getElementById('evadd-source');
    if (event.source_url) {
      src.href = event.source_url;
      src.style.opacity = '1';
      try {
        document.getElementById('evadd-source-host').textContent = new URL(event.source_url).hostname.replace(/^www\./,'');
      } catch (_) { document.getElementById('evadd-source-host').textContent = '—'; }
    } else {
      src.href = '#';
      src.style.opacity = '0.4';
      document.getElementById('evadd-source-host').textContent = '—';
    }

    modal.hidden = false;
  }

  function downloadIcs(event) {
    const dt = new Date(event.datetime);
    const dtEnd = new Date(dt.getTime() + 30 * 60_000);
    const fmt = (d) => d.toISOString().replace(/[-:]|\.\d{3}/g, '');
    const lines = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//macroeconops//calendar//EN',
      'BEGIN:VEVENT',
      'UID:' + event.id + '@macroeconops',
      'DTSTAMP:' + fmt(new Date()),
      'DTSTART:' + fmt(dt),
      'DTEND:'   + fmt(dtEnd),
      'SUMMARY:' + escapeIcs(event.title),
      'DESCRIPTION:' + escapeIcs((event.description || '') + (event.source_url ? '\\n\\nSource: ' + event.source_url : '')),
      'LOCATION:' + escapeIcs(event.source || ''),
      'STATUS:CONFIRMED',
      'END:VEVENT',
      'END:VCALENDAR',
    ];
    const blob = new Blob([lines.join('\r\n')], { type: 'text/calendar;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = event.id.replace(/[^a-zA-Z0-9_-]/g, '_') + '.ics';
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function escapeIcs(s) {
    return String(s).replace(/[\\,;]/g, m => '\\' + m).replace(/\n/g, '\\n');
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  global.CalendarModal = { init, open };
})(window);
