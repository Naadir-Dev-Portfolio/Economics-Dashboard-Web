/**
 * education-modal.js — the LEARN popup.
 *
 * Reads data/education.json: a tree of category → topic.
 * Renders the left rail of topics + a markdown-rendered right pane.
 */
(function (global) {
  'use strict';

  const state = {
    data: null,
    activeTopic: null,
    filter: '',
  };

  function init(data) {
    state.data = data;

    document.querySelectorAll('.nav-modal[data-modal="education"]').forEach(el => {
      el.addEventListener('click', (e) => { e.preventDefault(); open(); });
    });

    const modal = document.getElementById('modal-education');
    if (modal) {
      modal.querySelectorAll('[data-close-modal]').forEach(el => {
        el.addEventListener('click', () => { modal.hidden = true; });
      });
    }

    document.getElementById('edu-search')?.addEventListener('input', (e) => {
      state.filter = e.target.value.trim().toLowerCase();
      renderNav();
    });

    renderNav();
  }

  function open() {
    const modal = document.getElementById('modal-education');
    if (!modal) return;
    modal.hidden = false;
    // open first topic by default
    if (!state.activeTopic && state.data?.categories?.length) {
      const first = state.data.categories[0].topics?.[0];
      if (first) showTopic(state.data.categories[0].id, first.id);
    }
  }

  function renderNav() {
    const nav = document.getElementById('edu-nav');
    if (!nav) return;
    if (!state.data || !state.data.categories) {
      nav.innerHTML = '<div class="modal-loading">› no content loaded</div>';
      return;
    }
    const f = state.filter;
    const out = [];
    state.data.categories.forEach(cat => {
      const matching = (cat.topics || []).filter(t => {
        if (!f) return true;
        return (t.title + ' ' + (t.tldr || '') + ' ' + (t.body_md || '')).toLowerCase().includes(f);
      });
      if (!matching.length) return;
      out.push(`<div class="edu-nav-group">
        <div class="edu-nav-group-title"><span class="edu-glyph">${cat.glyph || '◆'}</span>${escapeHtml(cat.title)}</div>
        ${matching.map(t => `<a class="edu-topic ${state.activeTopic === t.id ? 'is-active' : ''}" data-cat="${cat.id}" data-topic="${t.id}">${escapeHtml(t.title)}</a>`).join('')}
      </div>`);
    });
    nav.innerHTML = out.join('') || '<div class="modal-loading">› no matches</div>';
    nav.querySelectorAll('.edu-topic').forEach(a => {
      a.addEventListener('click', () => showTopic(a.dataset.cat, a.dataset.topic));
    });
  }

  function showTopic(catId, topicId) {
    state.activeTopic = topicId;
    const cat = state.data?.categories?.find(c => c.id === catId);
    const topic = cat?.topics?.find(t => t.id === topicId);
    const content = document.getElementById('edu-content');
    if (!cat || !topic || !content) return;
    content.innerHTML = `
      <h1>${escapeHtml(topic.title)}</h1>
      <div class="edu-tldr">${escapeHtml(topic.tldr || '')}</div>
      ${markdownToHtml(topic.body_md || '')}
      ${(topic.related && topic.related.length) ? `
        <div class="edu-related">
          <div class="edu-related-title">RELATED</div>
          ${topic.related.map(rid => {
            const found = findTopic(rid);
            return found ? `<a data-cat="${found.catId}" data-topic="${rid}">${escapeHtml(found.title)}</a>` : '';
          }).join('')}
        </div>` : ''}
    `;
    content.scrollTop = 0;
    content.querySelectorAll('.edu-related a').forEach(a => {
      a.addEventListener('click', () => showTopic(a.dataset.cat, a.dataset.topic));
    });
    renderNav();
  }

  function findTopic(topicId) {
    for (const cat of (state.data?.categories || [])) {
      const t = (cat.topics || []).find(t => t.id === topicId);
      if (t) return { catId: cat.id, title: t.title };
    }
    return null;
  }

  // Tiny markdown renderer (paragraphs, headings, lists, bold, code).
  function markdownToHtml(md) {
    if (!md) return '';
    // Escape HTML first
    let s = md.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    // headings
    s = s.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    s = s.replace(/^## (.*$)/gim,  '<h2>$1</h2>');
    s = s.replace(/^# (.*$)/gim,   '<h1>$1</h1>');
    // bold / italic
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, '$1<em>$2</em>');
    // inline code
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    // lists
    s = s.replace(/((^[-*] .*(?:\n|$))+)/gm, (block) => {
      const items = block.trim().split(/\n/).map(l => l.replace(/^[-*]\s+/, '<li>') + '</li>').join('');
      return '<ul>' + items + '</ul>';
    });
    // numbered lists
    s = s.replace(/((^\d+\.\s.*(?:\n|$))+)/gm, (block) => {
      const items = block.trim().split(/\n/).map(l => l.replace(/^\d+\.\s+/, '<li>') + '</li>').join('');
      return '<ol>' + items + '</ol>';
    });
    // paragraphs
    s = s.split(/\n\s*\n/).map(chunk => {
      if (/^<(h\d|ul|ol|li|code)/.test(chunk.trim())) return chunk;
      return '<p>' + chunk.replace(/\n/g, '<br/>') + '</p>';
    }).join('\n');
    return s;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  global.EducationModal = { init, open };
})(window);
