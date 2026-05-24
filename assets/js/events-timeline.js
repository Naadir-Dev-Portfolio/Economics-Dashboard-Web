/**
 * events-timeline.js — the interactive events panel.
 *
 * Each event has a checkbox. Checking it tells Hero to add an annotation
 * to the archive chart; unchecking removes it. Major events auto-styled.
 */
(function (global) {
  'use strict';

  const state = { events: [], filter: 'recent' };

  function init(events) {
    state.events = (events || []).slice().sort((a, b) => b.date.localeCompare(a.date));
    bindFilters();
    render();
  }

  function bindFilters() {
    document.querySelectorAll('[data-events-filter]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('[data-events-filter]').forEach(b => b.classList.remove('is-active'));
        btn.classList.add('is-active');
        state.filter = btn.dataset.eventsFilter;
        render();
      });
    });
  }

  function filterEvents() {
    if (state.filter === 'all') return state.events;
    if (state.filter === 'major') return state.events.filter(e => e.impact === 'high');
    if (state.filter === 'recent') {
      const cutoff = new Date();
      cutoff.setFullYear(cutoff.getFullYear() - 3);
      return state.events.filter(e => new Date(e.date) >= cutoff);
    }
    return state.events;
  }

  function render() {
    const list = document.getElementById('events-list');
    if (!list) return;
    list.innerHTML = '';
    const tpl = document.getElementById('tpl-event');
    const events = filterEvents();
    if (!events.length) {
      list.innerHTML = '<div class="sub-loading">› no events match filter</div>';
      return;
    }
    events.forEach(e => {
      const frag = tpl.content.cloneNode(true);
      const row = frag.querySelector('.event-row');
      const id = eventId(e);
      row.dataset.eventId = id;
      row.classList.add(`tag-${e.tag || 'misc'}`);
      if (e.impact === 'high') row.classList.add('is-major');
      const cb = row.querySelector('.event-check');
      cb.checked = global.Hero ? global.Hero.hasAnnotation(id) : false;
      cb.addEventListener('change', (ev) => {
        ev.stopPropagation();
        if (cb.checked) global.Hero.addAnnotation({ ...e, id });
        else global.Hero.removeAnnotation(id);
      });
      // Click the row body (not the checkbox) → toggle
      row.addEventListener('click', (ev) => {
        if (ev.target === cb) return;
        ev.preventDefault();
        cb.checked = !cb.checked;
        cb.dispatchEvent(new Event('change'));
      });
      row.querySelector('.event-date').textContent = e.date;
      row.querySelector('.event-title').textContent = e.title;
      row.querySelector('.event-blurb').textContent = e.blurb || '';
      row.querySelector('.event-tag').textContent = e.tag || '';
      list.appendChild(frag);
    });
  }

  function eventId(e) { return `${e.date}:${e.title}`; }

  // Called by Hero when an annotation is removed via chip click
  function notifyRemoved(id) {
    const row = document.querySelector(`[data-event-id="${cssEscape(id)}"]`);
    if (row) {
      const cb = row.querySelector('.event-check');
      if (cb) cb.checked = false;
    }
  }
  function notifyCleared() {
    document.querySelectorAll('.event-check').forEach(cb => cb.checked = false);
  }

  function cssEscape(s) {
    if (global.CSS && global.CSS.escape) return global.CSS.escape(s);
    return String(s).replace(/[^a-zA-Z0-9_-]/g, c => '\\' + c);
  }

  global.EventsTimeline = { init, render, notifyRemoved, notifyCleared };
})(window);
