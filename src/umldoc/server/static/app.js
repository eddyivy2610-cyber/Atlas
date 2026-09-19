(() => {
  'use strict';

  const state = {
    scale: 1,
    translateX: 0,
    translateY: 0,
    isDragging: false,
    dragStartX: 0,
    dragStartY: 0,
    activeTool: 'select',
    activePanel: 'live',
    runInFlight: false,
    runTimer: null,
    runRequest: null,
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  function refreshIcons() {
    if (window.lucide) window.lucide.createIcons();
  }

  function setHidden(element, hidden) {
    if (element) element.hidden = hidden;
  }

  function setMenu(trigger, menu, open) {
    if (!trigger || !menu) return;
    trigger.setAttribute('aria-expanded', String(open));
    setHidden(menu, !open);
  }

  function closeMenus(except = null) {
    $$('[data-menu-trigger]').forEach((trigger) => {
      const menu = $('#' + trigger.dataset.menuTrigger);
      if (menu && menu !== except) setMenu(trigger, menu, false);
    });
  }

  function initMenus() {
    $$('[data-menu-trigger]').forEach((trigger) => {
      const menu = $('#' + trigger.dataset.menuTrigger);
      if (!menu) return;
      trigger.addEventListener('click', (event) => {
        event.stopPropagation();
        const open = menu.hidden;
        closeMenus(menu);
        setMenu(trigger, menu, open);
      });
      menu.addEventListener('click', (event) => event.stopPropagation());
    });

    document.addEventListener('click', () => { closeMenus(); closeSearch(); });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        closeMenus();
        closeSearch();
      }
    });

    $$('[data-view-mode]').forEach((item) => item.addEventListener('click', () => {
      $$('[data-view-mode]').forEach((option) => option.classList.toggle('is-selected', option === item));
      closeMenus();
    }));
  }

  function closeSearch() {
    const popover = $('#search-popover');
    const trigger = $('#search-toggle');
    if (!popover || !trigger) return;
    setHidden(popover, true);
    trigger.setAttribute('aria-expanded', 'false');
  }

  function initSearch() {
    const toggle = $('#search-toggle');
    const popover = $('#search-popover');
    const input = $('#search-input');
    const clear = $('#search-clear');
    if (!toggle || !popover || !input) return;

    toggle.addEventListener('click', (event) => {
      event.stopPropagation();
      closeMenus();
      const open = popover.hidden;
      setHidden(popover, !open);
      toggle.setAttribute('aria-expanded', String(open));
      if (open) window.setTimeout(() => input.focus(), 0);
    });
    popover.addEventListener('click', (event) => event.stopPropagation());
    clear?.addEventListener('click', () => { input.value = ''; filterNodes(''); input.focus(); });
    input.addEventListener('input', () => filterNodes(input.value));
  }

  function filterNodes(query) {
    const normalized = query.trim().toLowerCase();
    $$('.uml-node').forEach((node) => {
      const name = (node.dataset.nodeName || node.textContent || '').toLowerCase();
      const matches = !normalized || name.includes(normalized);
      node.classList.toggle('is-dimmed', !matches);
      node.classList.toggle('selected', Boolean(normalized && matches));
    });
  }

  function initModes() {
    $$('[data-mode]').forEach((button) => button.addEventListener('click', () => {
      $$('[data-mode]').forEach((mode) => {
        const active = mode === button;
        mode.classList.toggle('active', active);
        mode.setAttribute('aria-selected', String(active));
      });
      const simulation = button.dataset.mode === 'simulation';
      $('#selection-status').textContent = simulation ? 'simulation ready' : '0 selected';
    }));
  }

  function setActiveTool(tool) {
    state.activeTool = tool;
    $$('[data-tool]').forEach((button) => {
      const active = button.dataset.tool === tool;
      button.classList.toggle('active', active);
      if (button.hasAttribute('aria-pressed')) button.setAttribute('aria-pressed', String(active));
    });
  }

  function initTools() {
    $$('[data-tool]').forEach((button) => button.addEventListener('click', () => setActiveTool(button.dataset.tool)));
    document.addEventListener('keydown', (event) => {
      const shortcuts = { Escape: 'select', i: 'inspect', r: 'resize', n: 'note' };
      if (shortcuts[event.key]) setActiveTool(shortcuts[event.key]);
      if (event.key === '+' || event.key === '=') updateZoom(state.scale * 1.2);
      if (event.key === '-') updateZoom(state.scale / 1.2);
    });
  }

  function initPanelTabs() {
    $$('[data-panel-tab]').forEach((tab) => tab.addEventListener('click', () => {
      const panel = tab.dataset.panelTab;
      state.activePanel = panel;
      $$('[data-panel-tab]').forEach((item) => {
        const active = item === tab;
        item.classList.toggle('active', active);
        item.setAttribute('aria-selected', String(active));
      });
      setHidden($('#browse-view'), panel !== 'browse');
      setHidden($('#live-view'), panel !== 'live');
    }));
  }

  function updateTransform() {
    const layer = $('#diagram-layer');
    if (layer) layer.style.transform = `translate(${state.translateX}px, ${state.translateY}px) scale(${state.scale})`;
    const zoomValue = $('#zoom-value');
    if (zoomValue) zoomValue.textContent = `${Math.round(state.scale * 100)}%`;
  }

  function updateZoom(nextScale, center = null) {
    const bounded = Math.min(Math.max(nextScale, .55), 1.65);
    if (center) {
      const ratio = bounded / state.scale;
      state.translateX = center.x - (center.x - state.translateX) * ratio;
      state.translateY = center.y - (center.y - state.translateY) * ratio;
    }
    state.scale = bounded;
    updateTransform();
  }

  function fitDiagram() {
    state.scale = 1;
    state.translateX = 0;
    state.translateY = 0;
    updateTransform();
  }

  function initPanZoom() {
    const viewport = $('#graph-zone');
    if (!viewport) return;

    $$('[data-zoom-action]').forEach((button) => button.addEventListener('click', () => {
      const action = button.dataset.zoomAction;
      if (action === 'in') updateZoom(state.scale * 1.2);
      if (action === 'out') updateZoom(state.scale / 1.2);
      if (action === 'fit') fitDiagram();
    }));

    viewport.addEventListener('wheel', (event) => {
      event.preventDefault();
      const rect = viewport.getBoundingClientRect();
      updateZoom(state.scale * (event.deltaY < 0 ? 1.12 : .89), {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      });
    }, { passive: false });

    viewport.addEventListener('pointerdown', (event) => {
      if (event.target.closest('button, a, input')) return;
      state.isDragging = true;
      state.dragStartX = event.clientX - state.translateX;
      state.dragStartY = event.clientY - state.translateY;
      viewport.setPointerCapture?.(event.pointerId);
      viewport.classList.add('is-dragging');
    });
    viewport.addEventListener('pointermove', (event) => {
      if (!state.isDragging) return;
      state.translateX = event.clientX - state.dragStartX;
      state.translateY = event.clientY - state.dragStartY;
      updateTransform();
    });
    const stopDragging = (event) => {
      state.isDragging = false;
      viewport.releasePointerCapture?.(event.pointerId);
      viewport.classList.remove('is-dragging');
    };
    viewport.addEventListener('pointerup', stopDragging);
    viewport.addEventListener('pointercancel', stopDragging);
  }

  function selectNode(node) {
    $$('.uml-node').forEach((item) => item.classList.toggle('selected', item === node));
    const name = node.dataset.nodeName || 'node';
    const status = $('#selection-status');
    if (status) status.textContent = `${name} selected`;
  }

  function initNodes() {
    $$('.uml-node').forEach((node) => node.addEventListener('click', (event) => {
      event.stopPropagation();
      closeSearch();
      selectNode(node);
      if (state.activeTool === 'inspect') {
        const input = $('#search-input');
        if (input) { input.value = node.dataset.nodeName || ''; filterNodes(input.value); }
      }
    }));
  }

  function setStage(stageName, status, meta) {
    const order = ['extract', 'trace', 'verify', 'package'];
    const currentIndex = order.indexOf(stageName);
    $$('.stage').forEach((stage) => {
      const index = order.indexOf(stage.dataset.stage);
      const dot = $('.stage-dot', stage);
      const metaEl = $('.stage-meta', stage);
      stage.classList.toggle('complete', status === 'complete' ? index <= currentIndex : index < currentIndex);
      stage.classList.toggle('current', status === 'running' && index === currentIndex);
      stage.classList.toggle('pending', index > currentIndex);
      if (index < currentIndex || (status === 'complete' && index === currentIndex)) {
        if (dot) dot.innerHTML = '<i class="icon" data-lucide="check" aria-hidden="true"></i>';
      } else if (status === 'running' && index === currentIndex) {
        if (dot) dot.innerHTML = '<i class="icon" data-lucide="loader-circle" aria-hidden="true"></i>';
      } else if (dot) {
        dot.innerHTML = '';
      }
      if (metaEl && index === currentIndex && meta) metaEl.textContent = meta;
    });
    refreshIcons();
  }

  function setRunButton(loading) {
    const button = $('#run-button');
    const label = $('#run-button-label');
    if (!button || !label) return;
    button.disabled = loading;
    label.textContent = loading ? 'Running TinyDB…' : 'Run TinyDB';
  }

  function appendEvent(stage, status) {
    const body = $('#event-rows');
    if (!body) return;
    const row = document.createElement('tr');
    row.className = 'flash';
    row.innerHTML = `<td>now</td><td>${stage}</td><td class="${status === 'PASS' ? 'ok' : 'warn'}">${status}</td>`;
    body.appendChild(row);
    while (body.children.length > 5) body.firstElementChild.remove();
  }

  function renderHistory(history) {
    const list = $('#history-list');
    if (!list) return;
    if (!Array.isArray(history) || history.length === 0) {
      list.innerHTML = '<div class="history-item"><div><strong>No runs yet</strong><small>Run TinyDB to create a session record.</small></div><span class="history-status">idle</span></div>';
      return;
    }
    list.innerHTML = history.slice(0, 3).map((entry) => {
      const project = entry.project === 'click' ? 'Click' : 'TinyDB';
      const status = entry.status === 'SUCCESS' ? 'ready' : 'error';
      const statusClass = status === 'ready' ? '' : ' warn';
      return `<div class="history-item"><div><strong>${project} · latest</strong><small>${entry.timestamp || 'session run'} · ${entry.duration_ms || '—'}ms</small></div><span class="history-status${statusClass}">${status}</span></div>`;
    }).join('');
  }

  async function loadHistory() {
    try {
      const response = await fetch('/api/history', { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`History request failed (${response.status})`);
      renderHistory(await response.json());
    } catch (error) {
      const list = $('#history-list');
      if (list) list.innerHTML = '<div class="history-item"><div><strong>Session history unavailable</strong><small>Run data will appear after the next successful run.</small></div><span class="history-status warn">offline</span></div>';
    }
  }

  function clearRunTimer() {
    if (state.runTimer) window.clearInterval(state.runTimer);
    state.runTimer = null;
  }

  async function triggerLiveRun() {
    if (state.runInFlight) return;
    state.runInFlight = true;
    setRunButton(true);
    setHidden($('#run-error'), true);
    const stages = [
      ['extract', 'Extracting classes', 'running'],
      ['trace', 'Tracing runtime', 'running'],
      ['verify', 'Verifying model', 'running'],
      ['package', 'Packaging bundle', 'running'],
    ];
    let stageIndex = 0;
    setStage(stages[0][0], 'running', 'working');
    appendEvent('Run started', 'PASS');
    clearRunTimer();
    state.runTimer = window.setInterval(() => {
      stageIndex += 1;
      if (stageIndex < stages.length) {
        setStage(stages[stageIndex][0], 'running', 'working');
        appendEvent(stages[stageIndex][1], 'PASS');
      }
    }, 750);

    try {
      state.runRequest = fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ project: 'tinydb' }),
      });
      const response = await state.runRequest;
      const result = await response.json();
      if (!response.ok || result.status !== 'SUCCESS') throw new Error(result.error || 'The pipeline returned an error.');
      clearRunTimer();
      setStage('package', 'complete', `${result.duration_ms || '—'}ms`);
      appendEvent('Bundle ready', 'PASS');
      await loadHistory();
      const outputLink = $('.section-head a', $('#live-view'));
      if (outputLink && result.bundle_url) outputLink.href = result.bundle_url;
    } catch (error) {
      clearRunTimer();
      const errorMessage = $('#run-error');
      if (errorMessage) { errorMessage.textContent = error.message || 'Unable to run the pipeline.'; errorMessage.hidden = false; }
      appendEvent('Pipeline error', 'WARN');
      setStage('verify', 'running', 'blocked');
    } finally {
      state.runInFlight = false;
      setRunButton(false);
      state.runRequest = null;
    }
  }

  function initRunControls() {
    $$('[data-action="triggerLiveRun"]').forEach((button) => button.addEventListener('click', triggerLiveRun));
    $('#reset-events')?.addEventListener('click', () => {
      const rows = $('#event-rows');
      if (!rows) return;
      $$('.event-table tr', rows).forEach((row) => row.classList.remove('flash'));
      rows.querySelectorAll('tr').forEach((row, index) => { row.style.opacity = '0.35'; window.setTimeout(() => { row.style.opacity = '1'; }, 100 * (index + 1)); });
    });
    $('#show-history')?.addEventListener('click', loadHistory);
    document.addEventListener('keydown', (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') triggerLiveRun();
    });
  }

  function initPanelToggle() {
    $('#panel-toggle')?.addEventListener('click', () => {
      const panel = $('.run-panel');
      const collapsed = panel?.classList.toggle('is-collapsed');
      $('#panel-toggle')?.setAttribute('aria-label', collapsed ? 'Expand live run panel' : 'Collapse live run panel');
    });
  }

  function init() {
    refreshIcons();
    initMenus();
    initSearch();
    initModes();
    initTools();
    initPanelTabs();
    initPanZoom();
    initNodes();
    initRunControls();
    initPanelToggle();
    updateTransform();
    loadHistory();
  }

  window.triggerLiveRun = triggerLiveRun;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
