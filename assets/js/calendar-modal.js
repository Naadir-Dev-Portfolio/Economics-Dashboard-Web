/**
 * calendar-modal.js — the economic-calendar popup.
 *
 * Reads data/calendar.json. Two views:
 *   • MONTH — full calendar grid with month nav (default)
 *   • LIST  — grouped by day, every upcoming release
 *
 * Clicking a release pops the add-to-calendar mini-modal with:
 *   • Google Calendar quick-add link
 *   • Outlook quick-add link
 *   • Apple / Thunderbird .ics download
 *   • Link to the official source page
 */
(function (global) {
  'use strict';

  const state = {
    events: [],
    view: 'month',                              // default to month view
    cursor: new Date(),                          // current month being viewed
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

    // Month nav
    document.getElementById('cal-prev')?.addEventListener('click', () => shiftMonth(-1));
    document.getElementById('cal-next')?.addEventListener('click', () => shiftMonth(+1));
    document.getElementById('cal-today')?.addEventListener('click', () => { state.cursor = new Date(); render(); });

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
    state.cursor = new Date();
    render();
  }

  function shiftMonth(delta) {
    state.cursor = new Date(state.cursor.getFullYear(), state.cursor.getMonth() + delta, 1);
    render();
  }

  function render() {
    const body = document.getElementById('calendar-body');
    if (!body) return;
    updateMonthLabel();
    if (!state.events.length) {
      body.innerHTML = '<div class="modal-loading">› no events — run scripts/fetch_calendar.py</div>';
      return;
    }
    if (state.view === 'list') renderList(body);
    else renderMonth(body);
  }

  function updateMonthLabel() {
    const el = document.getElementById('cal-nav-month');
    if (el) el.textContent = state.cursor.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' }).toUpperCase();
  }

  // ─────────────────────────────────────────────────────── LIST view
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

  // ─────────────────────────────────────────────────────── MONTH view
  function renderMonth(body) {
    const year = state.cursor.getFullYear();
    const month = state.cursor.getMonth();
    const first = new Date(Date.UTC(year, month, 1));
    const last  = new Date(Date.UTC(year, month + 1, 0));
    const startWeekday = (first.getUTCDay() + 6) % 7;             // 0 = Monday
    const numWeeks = Math.ceil((startWeekday + last.getUTCDate()) / 7);
    const totalCells = numWeeks * 7;

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
      const evts = (eventsByDay[iso] || []).sort((a, b) => a.datetime.localeCompare(b.datetime));
      const shown = evts.slice(0, 3);
      const items = shown.map(e => {
        const eid = encodeURIComponent(e.id);
        const time = new Date(e.datetime).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false });
        const tag = e.tag || 'other';
        return `<span class="cm-evt tag-${tag}" data-event-id="${eid}" title="${escapeHtml(e.title)} · ${time}">
          <span class="cm-evt-time">${time}</span>
          <span class="cm-evt-title">${escapeHtml(e.title)}</span>
        </span>`;
      }).join('');
      const more = evts.length > 3 ? `<span class="cm-evt cm-evt-more" data-day="${iso}">+${evts.length-3} more</span>` : '';
      const countBadge = evts.length ? `<span class="cm-d-count">${evts.length}</span>` : '';
      return `<div class="cal-month-cell${inMonth ? '' : ' other-month'}${isToday ? ' is-today' : ''}" data-day="${iso}">
        <div class="cm-d"><span>${d.getUTCDate()}</span>${countBadge}</div>
        ${items}${more}
      </div>`;
    }).join('');

    const sixWeekClass = numWeeks === 6 ? ' is-six-weeks' : ' is-five-weeks';
    body.innerHTML = `<div class="cal-month-grid-wrap"><div class="cal-month${sixWeekClass}">${heads}${cells}</div></div>`;

    body.querySelectorAll('.cm-evt[data-event-id]').forEach(el => {
      el.addEventListener('click', (ev) => {
        ev.stopPropagation();
        const id = decodeURIComponent(el.dataset.eventId);
        openAddModal(state.events.find(e => e.id === id));
      });
    });
    body.querySelectorAll('.cm-evt-more').forEach(el => {
      el.addEventListener('click', (ev) => {
        ev.stopPropagation();
        // Show all events for that day via the list view filtered to that date.
        const day = el.dataset.day;
        const dayEvents = state.events.filter(e => e.datetime.slice(0,10) === day);
        if (!dayEvents.length) return;
        // Just open the first one — the list of the day already shows in the cell.
        openAddModal(dayEvents[0]);
      });
    });
  }

  // ─────────────────────────── ADD-TO-CALENDAR ───────────────────────────
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

    const fmt = (d) => d.toISOString().replace(/[-:]|\.\d{3}/g, '');
    const gcalUrl = 'https://www.google.com/calendar/render?action=TEMPLATE'
      + '&text=' + encodeURIComponent(event.title)
      + '&dates=' + fmt(dt) + '/' + fmt(dtEnd)
      + '&details=' + encodeURIComponent((event.description || '') + (event.source_url ? '\n\nSource: ' + event.source_url : ''))
      + '&location=' + encodeURIComponent(event.source || '');
    document.getElementById('evadd-google').href = gcalUrl;

    const outlookUrl = 'https://outlook.live.com/calendar/0/deeplink/compose?path=/calendar/action/compose&rru=addevent'
      + '&subject=' + encodeURIComponent(event.title)
      + '&startdt=' + dt.toISOString()
      + '&enddt=' + dtEnd.toISOString()
      + '&body=' + encodeURIComponent(event.description || '');
    document.getElementById('evadd-outlook').href = outlookUrl;

    document.getElementById('evadd-ics').onclick = () => downloadIcs(event);

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
