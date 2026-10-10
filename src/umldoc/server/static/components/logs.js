/**
 * ============================================================================
 * LOGS & ISSUES COMPONENT (Reused & Modernized from Original Atlas UI)
 * Collapsible bottom drawer with tab bar, search filter, issue tracker,
 * and docking status strip.
 * ============================================================================
 */

export class LogsComponent {
  constructor(options = {}) {
    this.panelId = options.panelId || 'bottomPanel';
    this.statusBarId = options.statusBarId || 'bottomStatusBar';
    this.onStateChange = options.onStateChange || null;

    this.panelEl = document.getElementById(this.panelId);
    this.statusEl = document.getElementById(this.statusBarId);

    this.activeTab = 'logs'; // 'logs' | 'issues' | 'activity'
    this.isOpen = false;
    this.levelFilter = 'all';
    this.searchQuery = '';

    this.logs = [];
    this.issues = [];
    this.activities = [];

    this._initElements();
    this._bindEvents();
    this._renderInitialState();
  }

  _initElements() {
    if (!this.panelEl) {
      console.warn(`LogsComponent: Panel #${this.panelId} not found in DOM.`);
      return;
    }

    // Tabs
    this.tabButtons = this.panelEl.querySelectorAll('[data-bptab]');
    this.tabLogs = this.panelEl.querySelector('#bpTabLogs');
    this.tabIssues = this.panelEl.querySelector('#bpTabIssues');
    this.tabActivity = this.panelEl.querySelector('#bpTabActivity');

    // Badges
    this.badgeIssues = this.panelEl.querySelector('#bpIssuesBadge');
    this.badgeActivity = this.panelEl.querySelector('#bpActivityBadge');

    // Controls
    this.levelSelectBtn = this.panelEl.querySelector('#bpLogLevelSelect');
    this.levelMenu = this.panelEl.querySelector('#bpLevelMenu');
    this.searchInput = this.panelEl.querySelector('#bpSearchInput');
    this.clearBtn = this.panelEl.querySelector('#btnClearLogs');
    this.closeBtn = this.panelEl.querySelector('#closeBottomPanel');

    // Status bar triggers
    if (this.statusEl) {
      this.toggleBtn = this.statusEl.querySelector('#btnToggleBottomPanel');
      this.statusTextEl = this.statusEl.querySelector('#sbStatusText');
      this.statusDotEl = this.statusEl.querySelector('#sbStatusDot');
      this.sbLogsTrigger = this.statusEl.querySelector('#sbBtnLogs');
      this.sbIssuesTrigger = this.statusEl.querySelector('#sbBtnIssues');
      this.sbIssuesBadge = this.statusEl.querySelector('#sbIssuesBadge');
      this.sbLogsBadge = this.statusEl.querySelector('#sbLogsBadge');
    }
  }

  _bindEvents() {
    // Tab switching
    if (this.tabButtons) {
      this.tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
          const tab = btn.dataset.bptab;
          if (tab) this.switchTab(tab);
        });
      });
    }

    // Level selector toggle & items
    if (this.levelSelectBtn && this.levelMenu) {
      this.levelSelectBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.levelMenu.classList.toggle('is-open');
      });

      this.levelMenu.querySelectorAll('.bp-level-item').forEach(item => {
        item.addEventListener('click', (e) => {
          e.stopPropagation();
          const level = item.dataset.level || 'all';
          this.setLevelFilter(level);
          this.levelMenu.classList.remove('is-open');
        });
      });

      document.addEventListener('click', (e) => {
        if (!this.levelMenu.contains(e.target) && !this.levelSelectBtn.contains(e.target)) {
          this.levelMenu.classList.remove('is-open');
        }
      });
    }

    // Search filter
    if (this.searchInput) {
      this.searchInput.addEventListener('input', (e) => {
        this.searchQuery = (e.target.value || '').trim().toLowerCase();
        this.filterLogs();
      });
    }

    // Clear logs
    if (this.clearBtn) {
      this.clearBtn.addEventListener('click', () => {
        this.clearLogs();
      });
    }

    // Close / Collapse panel
    if (this.closeBtn) {
      this.closeBtn.addEventListener('click', () => {
        this.close();
      });
    }

    // Toggle button in status bar
    if (this.toggleBtn) {
      this.toggleBtn.addEventListener('click', () => {
        this.toggle();
      });
    }

    // Direct tab open from status bar
    if (this.sbLogsTrigger) {
      this.sbLogsTrigger.addEventListener('click', () => {
        if (!this.isOpen || this.activeTab !== 'logs') {
          this.open('logs');
        } else {
          this.close();
        }
      });
    }

    if (this.sbIssuesTrigger) {
      this.sbIssuesTrigger.addEventListener('click', () => {
        if (!this.isOpen || this.activeTab !== 'issues') {
          this.open('issues');
        } else {
          this.close();
        }
      });
    }
  }

  _renderInitialState() {
    this.updateBadges();
    this.isOpen = this.panelEl && !this.panelEl.classList.contains('panel--hidden');
    this._syncToggleButtons();
  }

  toggle(forceOpen) {
    if (!this.panelEl) return;
    const shouldOpen = (typeof forceOpen === 'boolean') ? forceOpen : !this.isOpen;
    if (shouldOpen) {
      this.open(this.activeTab);
    } else {
      this.close();
    }
  }

  open(tab = 'logs') {
    if (!this.panelEl) return;
    this.isOpen = true;
    this.panelEl.classList.remove('panel--hidden');
    this.switchTab(tab);
    this._syncToggleButtons();
    if (this.onStateChange) this.onStateChange({ isOpen: true, tab: this.activeTab });
  }

  close() {
    if (!this.panelEl) return;
    this.isOpen = false;
    this.panelEl.classList.add('panel--hidden');
    this._syncToggleButtons();
    if (this.onStateChange) this.onStateChange({ isOpen: false, tab: this.activeTab });
  }

  _syncToggleButtons() {
    if (this.toggleBtn) {
      this.toggleBtn.classList.toggle('is-expanded', this.isOpen);
      const chevron = this.toggleBtn.querySelector('svg, i');
      if (chevron) {
        chevron.style.transform = this.isOpen ? 'rotate(180deg)' : 'rotate(0deg)';
      }
    }
    if (this.sbLogsTrigger) {
      this.sbLogsTrigger.classList.toggle('status-pill--active', this.isOpen && this.activeTab === 'logs');
    }
    if (this.sbIssuesTrigger) {
      this.sbIssuesTrigger.classList.toggle('status-pill--active', this.isOpen && this.activeTab === 'issues');
    }
  }

  switchTab(tab) {
    this.activeTab = tab;

    // Update tab bar buttons
    if (this.tabButtons) {
      this.tabButtons.forEach(btn => {
        btn.classList.toggle('bp-tab--active', btn.dataset.bptab === tab);
      });
    }

    // Toggle tab panes
    if (this.tabLogs) this.tabLogs.style.display = (tab === 'logs') ? 'flex' : 'none';
    if (this.tabIssues) this.tabIssues.style.display = (tab === 'issues') ? 'flex' : 'none';
    if (this.tabActivity) this.tabActivity.style.display = (tab === 'activity') ? 'flex' : 'none';

    this._syncToggleButtons();
  }

  setLevelFilter(level) {
    this.levelFilter = level.toLowerCase();

    // Update level label
    if (this.levelSelectBtn) {
      const label = (this.levelFilter === 'all') ? 'All levels' : this.levelFilter.toUpperCase();
      this.levelSelectBtn.innerHTML = `
        ${label}
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      `;
    }

    // Highlight selected item in menu
    if (this.levelMenu) {
      this.levelMenu.querySelectorAll('.bp-level-item').forEach(item => {
        item.classList.toggle('is-selected', (item.dataset.level || 'all').toLowerCase() === this.levelFilter);
      });
    }

    this.filterLogs();
  }

  /**
   * Appends a log item to the panel
   * @param {Object|string} logOrLevel - Log object or level string ('info'|'success'|'running'|'warn'|'error')
   * @param {string} [node] - Subsystem or node name
   * @param {string} [msg] - Log message
   * @param {string} [status] - Custom pill label
   */
  addLog(logOrLevel, node, msg, status) {
    let entry;
    if (typeof logOrLevel === 'object') {
      entry = {
        id: 'log-' + Date.now() + '-' + Math.random().toString(36).substr(2, 4),
        time: logOrLevel.time || this._now(),
        level: (logOrLevel.level || 'info').toLowerCase(),
        node: logOrLevel.node || 'System',
        msg: logOrLevel.msg || '',
        status: (logOrLevel.status || logOrLevel.level || 'INFO').toUpperCase()
      };
    } else {
      entry = {
        id: 'log-' + Date.now() + '-' + Math.random().toString(36).substr(2, 4),
        time: this._now(),
        level: (logOrLevel || 'info').toLowerCase(),
        node: node || 'System',
        msg: msg || '',
        status: (status || logOrLevel || 'INFO').toUpperCase()
      };
    }

    this.logs.push(entry);

    // Remove empty placeholder if present
    const empty = this.tabLogs ? this.tabLogs.querySelector('#bpEmptyState') : null;
    if (empty) empty.remove();

    // Create DOM row
    if (this.tabLogs) {
      const row = this._createLogRowElement(entry);
      this.tabLogs.appendChild(row);

      // Auto scroll
      this.tabLogs.scrollTop = this.tabLogs.scrollHeight;
    }

    this.updateBadges();

    // If filter is active, check visibility
    this._checkRowVisibility(entry);

    return entry;
  }

  _createLogRowElement(entry) {
    const row = document.createElement('div');
    row.className = 'bp-log-row';
    row.dataset.id = entry.id;
    row.dataset.level = entry.level;
    row.dataset.text = `${entry.node} ${entry.msg}`.toLowerCase();

    const iconSvg = this._getIconSvg(entry.level);

    row.innerHTML = `
      <span class="bp-log-time">${this._escape(entry.time)}</span>
      <span class="bp-log-icon bp-log-icon--${this._escape(entry.level)}">${iconSvg}</span>
      <span class="bp-log-node" title="${this._escape(entry.node)}">${this._escape(entry.node)}</span>
      <span class="bp-log-msg" title="${this._escape(entry.msg)}">${this._escape(entry.msg)}</span>
      <span class="bp-status-pill bp-status-pill--${this._escape(entry.level)}">${this._escape(entry.status)}</span>
    `;

    return row;
  }

  _getIconSvg(level) {
    switch (level) {
      case 'success':
        return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
      case 'running':
        return `<svg class="spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>`;
      case 'warn':
        return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`;
      case 'error':
        return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
      case 'info':
      default:
        return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }
  }

  filterLogs() {
    if (!this.tabLogs) return;
    const rows = this.tabLogs.querySelectorAll('.bp-log-row');
    rows.forEach(row => {
      const level = row.dataset.level || '';
      const text = row.dataset.text || '';

      const matchLevel = (this.levelFilter === 'all') || (level === this.levelFilter);
      const matchSearch = (!this.searchQuery) || text.includes(this.searchQuery);

      row.style.display = (matchLevel && matchSearch) ? 'flex' : 'none';
    });
  }

  _checkRowVisibility(entry) {
    if (!this.tabLogs) return;
    const row = this.tabLogs.querySelector(`[data-id="${entry.id}"]`);
    if (!row) return;

    const matchLevel = (this.levelFilter === 'all') || (entry.level === this.levelFilter);
    const text = `${entry.node} ${entry.msg}`.toLowerCase();
    const matchSearch = (!this.searchQuery) || text.includes(this.searchQuery);

    row.style.display = (matchLevel && matchSearch) ? 'flex' : 'none';
  }

  clearLogs() {
    this.logs = [];
    if (this.tabLogs) {
      this.tabLogs.innerHTML = `
        <div class="bp-log-row" id="bpEmptyState" style="justify-content:center;opacity:0.5;">
          <span class="bp-log-msg">Logs cleared — ready for pipeline execution.</span>
        </div>
      `;
    }
    this.updateBadges();
  }

  /**
   * Sets issues and populates the Issues tab
   * @param {Array<Object>} issuesList
   */
  setIssues(issuesList = []) {
    this.issues = Array.isArray(issuesList) ? issuesList : [];
    if (!this.tabIssues) return;

    if (this.issues.length === 0) {
      this.tabIssues.innerHTML = `
        <div class="bp-empty-list" id="bpIssuesEmpty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            <path d="m9 12 2 2 4-4"></path>
          </svg>
          <span>No structural drift or signature mismatches detected. Models and source code are in sync.</span>
        </div>
      `;
    } else {
      let html = '<div class="bp-issue-list">';
      this.issues.forEach(item => {
        const severity = (item.severity || 'error').toLowerCase();
        const badgeClass = severity === 'warn' ? 'bp-issue-badge--warn' : 'bp-issue-badge--error';
        const badgeText = item.type || (severity === 'warn' ? 'DRIFT' : 'MISMATCH');

        html += `
          <div class="bp-issue-row">
            <span class="bp-issue-badge ${badgeClass}">${this._escape(badgeText)}</span>
            <span class="bp-issue-title">${this._escape(item.title || item.name || 'Structural Drift')}</span>
            <span class="bp-issue-desc">${this._escape(item.desc || item.detail || '')}</span>
            ${item.file ? `<span class="bp-issue-file">${this._escape(item.file)}</span>` : ''}
          </div>
        `;
      });
      html += '</div>';
      this.tabIssues.innerHTML = html;
    }

    this.updateBadges();
  }

  /**
   * Sets activity items and populates Activity tab
   * @param {Array<Object>} activityList
   */
  setActivity(activityList = []) {
    this.activities = Array.isArray(activityList) ? activityList : [];
    if (!this.tabActivity) return;

    if (this.activities.length === 0) {
      this.tabActivity.innerHTML = `
        <div class="bp-empty-list" id="bpActivityEmpty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
          </svg>
          <span>No workspace activity recorded yet. Run a pipeline build to view event logs.</span>
        </div>
      `;
    } else {
      let html = '<div class="bp-log-list">';
      this.activities.forEach(act => {
        const status = (act.status || 'SUCCESS').toUpperCase();
        const level = status === 'SUCCESS' ? 'success' : status === 'ERROR' ? 'error' : 'info';
        const iconSvg = this._getIconSvg(level);

        html += `
          <div class="bp-log-row">
            <span class="bp-log-time">${this._escape(act.time || this._now())}</span>
            <span class="bp-log-icon bp-log-icon--${level}">${iconSvg}</span>
            <span class="bp-log-node">${this._escape(act.project || act.action || 'Pipeline Run')}</span>
            <span class="bp-log-msg">${this._escape(act.desc || `Run executed in ${act.duration || 0}ms`)}</span>
            <span class="bp-status-pill bp-status-pill--${level}">${status}</span>
          </div>
        `;
      });
      html += '</div>';
      this.tabActivity.innerHTML = html;
    }

    this.updateBadges();
  }

  /**
   * Update all counter badges in tabs and status bar
   */
  updateBadges() {
    const issuesCount = this.issues.length;
    const activityCount = this.activities.length;
    const logsCount = this.logs.length;

    if (this.badgeIssues) {
      this.badgeIssues.textContent = issuesCount;
      this.badgeIssues.style.display = issuesCount > 0 ? 'inline-flex' : 'none';
    }

    if (this.badgeActivity) {
      this.badgeActivity.textContent = activityCount;
      this.badgeActivity.style.display = activityCount > 0 ? 'inline-flex' : 'none';
    }

    if (this.sbIssuesBadge) {
      this.sbIssuesBadge.textContent = issuesCount;
      this.sbIssuesBadge.style.display = issuesCount > 0 ? 'inline-flex' : 'none';
    }

    if (this.sbLogsBadge) {
      this.sbLogsBadge.textContent = logsCount;
    }
  }

  /**
   * Updates status bar text and indicator
   * @param {string} text
   * @param {'success'|'running'|'warn'|'error'} [statusType]
   */
  setStatus(text, statusType = 'success') {
    if (this.statusTextEl) {
      this.statusTextEl.textContent = text;
    }
    if (this.statusDotEl) {
      const colors = {
        success: '#16a34a',
        running: '#090C9B',
        warn: '#d97706',
        error: '#dc2626'
      };
      this.statusDotEl.style.backgroundColor = colors[statusType] || '#16a34a';
    }
  }

  _now() {
    return new Date().toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  }

  _escape(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
}
