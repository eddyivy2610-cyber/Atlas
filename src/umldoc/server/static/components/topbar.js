/**
 * Dual Topbar System Controller
 * Handles Primary Topbar (Navigation, Theme, Profile) and 
 * Compact Secondary Topbar (Project, Segmented Diagram Switcher, Filter, Actions).
 */

export class TopbarComponent {
  constructor(options = {}) {
    this.container = options.container || document.querySelector('.app-header');
    this.onProjectChange = options.onProjectChange || (() => {});
    this.onDiagramTypeChange = options.onDiagramTypeChange || (() => {});
    this.onSearch = options.onSearch || (() => {});
    this.onLayoutToggle = options.onLayoutToggle || (() => {});
    this.onScopeChange = options.onScopeChange || (() => {});
    this.onRunPipeline = options.onRunPipeline || (() => {});
    this.onExport = options.onExport || (() => {});
    this.onViewChange = options.onViewChange || (() => {});
    this.onOpenSetup = options.onOpenSetup || (() => {});
    this.onDeleteWorkspace = options.onDeleteWorkspace || (() => {});
    this.onClearWorkspaces = options.onClearWorkspaces || (() => {});

    this.activeDropdown = null;
    this.currentTheme = localStorage.getItem('umldoc_theme') || 'light';
    this.currentDiagramType = 'class';
    this.currentLayout = 'TB';
    this.searchTimer = null;
    this.currentProject = options.currentProject || '';
    this.workspaces = [];
    this.workspaceFilter = '';
    
    this.init();
  }

  init() {
    this.applyTheme(this.currentTheme);
    this.bindEvents();
    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  bindEvents() {
    // 1. Dropdown menus
    this.container.querySelectorAll('[data-dropdown-target]').forEach(trigger => {
      trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        const targetId = trigger.dataset.dropdownTarget;
        this.toggleDropdown(targetId, trigger);
      });
    });

    document.addEventListener('click', (e) => {
      if (!e.target.closest('.nav-pill-dropdown') && !e.target.closest('.dropdown-menu')) {
        this.closeAllDropdowns();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.closeAllDropdowns();
      }
    });

    // 2. Theme toggle
    const themeBtn = this.container.querySelector('#themeToggleBtn');
    if (themeBtn) {
      themeBtn.addEventListener('click', () => {
        const nextTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        this.applyTheme(nextTheme);
      });
    }

    // 3. Segmented Diagram Switcher (Class, Sequence, Architecture, Packages)
    this.container.querySelectorAll('.segmented-btn[data-diag-type]').forEach(btn => {
      btn.addEventListener('click', () => {
        const type = btn.dataset.diagType;
        this.setView('diagrams');
        this.setDiagramType(type);
      });
    });

    // 3b. Dropdown Diagram Menu items
    this.container.querySelectorAll('#menuDiagrams [data-diagram-type]').forEach(btn => {
      btn.addEventListener('click', () => {
        this.closeAllDropdowns();
        this.setView('diagrams');
        this.setDiagramType(btn.dataset.diagramType);
      });
    });

    // 4. Filter search input with debounce
    const filterInput = this.container.querySelector('#filterSearchInput');
    if (filterInput) {
      filterInput.addEventListener('input', (e) => {
        clearTimeout(this.searchTimer);
        const q = e.target.value.trim();
        this.searchTimer = setTimeout(() => {
          this.onSearch(q);
        }, 180);
      });
    }

    // 5. Layout toggle (TB / LR)
    const layoutBtn = this.container.querySelector('#btnToggleLayout');
    if (layoutBtn) {
      layoutBtn.addEventListener('click', () => {
        this.currentLayout = this.currentLayout === 'TB' ? 'LR' : 'TB';
        const lbl = layoutBtn.querySelector('#layoutLabel');
        if (lbl) lbl.textContent = this.currentLayout;
        this.onLayoutToggle(this.currentLayout);
      });
    }

    // 6. Scope pill button
    const scopeBtn = this.container.querySelector('#btnScopeTrigger');
    if (scopeBtn) {
      scopeBtn.addEventListener('click', () => {
        this.onScopeChange('all');
      });
    }

    // 7. Execution and Action buttons
    const btnRun = this.container.querySelector('#btnRunPipeline');
    if (btnRun) {
      btnRun.addEventListener('click', () => {
        this.flashButton(btnRun);
        this.onRunPipeline();
      });
    }

    const btnRefresh = this.container.querySelector('#btnRefreshPipeline');
    if (btnRefresh) {
      btnRefresh.addEventListener('click', () => {
        this.spinIcon(btnRefresh);
        this.onProjectChange(this.currentProject || 'umldoc', this.currentPath || 'src/umldoc');
      });
    }

    const btnExport = this.container.querySelector('#btnExportBrief');
    if (btnExport) {
      btnExport.addEventListener('click', () => {
        this.onExport();
      });
    }

    // 8. Nav pill view switches
    this.container.querySelectorAll('.topbar-nav .nav-pill[data-view]').forEach(pill => {
      pill.addEventListener('click', () => {
        const view = pill.dataset.view;
        this.setView(view);
      });
    });

    // 8b. Report Anchor links (Jump directly to report section from topbar dropdowns)
    this.container.querySelectorAll('[data-report-anchor]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        this.closeAllDropdowns();
        const anchor = item.dataset.reportAnchor;
        this.setView('reports');
        if (anchor) {
          setTimeout(() => {
            const target = document.getElementById(anchor);
            if (target) {
              target.scrollIntoView({ behavior: 'smooth' });
            }
          }, 120);
        }
      });
    });

    // 9. Workspace selector dropdown & Setup triggers
    const btnOpenLocal = this.container.querySelector('#btnOpenLocalWorkspace');
    if (btnOpenLocal) {
      btnOpenLocal.addEventListener('click', (e) => {
        e.preventDefault();
        this.closeAllDropdowns();
        this.onOpenSetup();
      });
    }

    const btnNewWs = this.container.querySelector('#btnNewWorkspace');
    if (btnNewWs) {
      btnNewWs.addEventListener('click', (e) => {
        e.preventDefault();
        this.closeAllDropdowns();
        this.onOpenSetup();
      });
    }

    const btnNavBack = this.container.querySelector('#btnNavBack');
    if (btnNavBack) {
      btnNavBack.addEventListener('click', (e) => {
        e.preventDefault();
        this.onOpenSetup();
      });
    }

    const projectIdent = this.container.querySelector('#projectIdentifier');
    if (projectIdent) {
      projectIdent.style.cursor = 'pointer';
      projectIdent.title = 'Click to switch or scan workspace';
      projectIdent.addEventListener('click', () => {
        this.onOpenSetup();
      });
    }

    this.bindWorkspaceItems();
  }

  bindWorkspaceItems() {
    this.container.querySelectorAll('[data-workspace-select]').forEach(item => {
      item.onclick = (e) => {
        if (e.target.closest('[data-delete-workspace]')) return;
        e.preventDefault();
        const ws = item.dataset.workspaceSelect;
        const pth = item.dataset.workspacePath || '';
        this.setProject(ws);
        this.closeAllDropdowns();
        this.onProjectChange(ws, pth);
      };
    });

    this.container.querySelectorAll('[data-delete-workspace]').forEach(btn => {
      btn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        const wsId = btn.dataset.deleteWorkspace;
        this.onDeleteWorkspace(wsId);
      };
    });
  }

  setWorkspaces(workspaces) {
    this.workspaces = workspaces || [];
    this.renderWorkspacesMenu();
  }

  renderWorkspacesMenu() {
    const menu = document.getElementById('menuWorkspaces');
    if (!menu) return;

    const list = this.workspaces || [];
    const filter = (this.workspaceFilter || '').toLowerCase().trim();
    const filteredList = filter
      ? list.filter(w => (w.name || '').toLowerCase().includes(filter) || (w.id || '').toLowerCase().includes(filter) || (w.path || '').toLowerCase().includes(filter))
      : list;

    let searchHtml = '';
    if (list.length >= 4) {
      searchHtml = `
        <div class="ws-dropdown-search">
          <i data-lucide="search"></i>
          <input type="text" placeholder="Filter workspaces..." class="ws-dropdown-search-input" value="${this.workspaceFilter || ''}" />
        </div>
      `;
    }

    let itemsHtml = '';
    if (filteredList.length === 0) {
      itemsHtml = `<div class="ws-empty-notice">No workspaces match "${this.workspaceFilter}"</div>`;
    } else {
      itemsHtml = filteredList.map(ws => {
        const isActive = (this.currentProject || '').toLowerCase() === (ws.id || '').toLowerCase();
        const activeClass = isActive ? ' is-active' : '';
        const activeBadge = isActive ? '<span class="ws-item-active-badge">ACTIVE</span>' : '';
        const metaCount = (ws.classesCount !== undefined && ws.classesCount !== null) ? `<span class="ws-item-meta-count">${ws.classesCount} classes</span>` : '';
        const metaVerif = ws.verification ? `<span class="ws-item-meta-verif">${ws.verification}</span>` : '';
        const metaPath = `<span class="ws-item-meta-path" title="${ws.path || ws.id}">${ws.path || ws.id}</span>`;

        return `
          <div class="ws-dropdown-item${activeClass}" data-workspace-select="${ws.id}" data-workspace-path="${ws.path || ''}" title="Open ${ws.name || ws.id}">
            <div class="ws-item-icon">
              <i data-lucide="${ws.icon || 'folder'}"></i>
            </div>
            <div class="ws-item-body">
              <div class="ws-item-title-row">
                <span class="ws-item-name">${ws.name || ws.id}</span>
                ${activeBadge}
              </div>
              <div class="ws-item-meta">
                ${metaCount}
                ${metaVerif}
                ${metaPath}
              </div>
            </div>
            <button class="ws-item-del-btn" title="Remove from history" data-delete-workspace="${ws.id}">
              <i data-lucide="x"></i>
            </button>
          </div>
        `;
      }).join('');
    }

    menu.innerHTML = `
      <div class="ws-dropdown-header">
        <span>Workspaces History</span>
        <span class="ws-dropdown-header-count">${list.length}</span>
      </div>
      ${searchHtml}
      <div class="ws-dropdown-list">
        ${itemsHtml}
      </div>
      <div class="dropdown-divider"></div>
      <button class="dropdown-item ws-action-btn" id="btnNewWorkspace">
        <i data-lucide="plus-circle"></i>
        <span>+ New Workspace...</span>
      </button>
      <button class="dropdown-item ws-action-btn" id="btnOpenLocalWorkspace">
        <i data-lucide="folder-plus"></i>
        <span>Open Local Folder...</span>
      </button>
      <button class="dropdown-item ws-action-btn ws-action-clear" id="btnClearWorkspaceHistory">
        <i data-lucide="trash-2"></i>
        <span>Clear History</span>
      </button>
    `;

    // Wire search input filter
    const searchInput = menu.querySelector('.ws-dropdown-search-input');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        this.workspaceFilter = e.target.value;
        const listContainer = menu.querySelector('.ws-dropdown-list');
        if (listContainer) {
          const curFilter = this.workspaceFilter.toLowerCase().trim();
          const matches = curFilter
            ? this.workspaces.filter(w => (w.name || '').toLowerCase().includes(curFilter) || (w.id || '').toLowerCase().includes(curFilter) || (w.path || '').toLowerCase().includes(curFilter))
            : this.workspaces;

          if (matches.length === 0) {
            listContainer.innerHTML = `<div class="ws-empty-notice">No workspaces match "${this.workspaceFilter}"</div>`;
          } else {
            listContainer.innerHTML = matches.map(ws => {
              const isActive = (this.currentProject || '').toLowerCase() === (ws.id || '').toLowerCase();
              const activeClass = isActive ? ' is-active' : '';
              const activeBadge = isActive ? '<span class="ws-item-active-badge">ACTIVE</span>' : '';
              const metaCount = (ws.classesCount !== undefined && ws.classesCount !== null) ? `<span class="ws-item-meta-count">${ws.classesCount} classes</span>` : '';
              const metaVerif = ws.verification ? `<span class="ws-item-meta-verif">${ws.verification}</span>` : '';
              const metaPath = `<span class="ws-item-meta-path" title="${ws.path || ws.id}">${ws.path || ws.id}</span>`;

              return `
                <div class="ws-dropdown-item${activeClass}" data-workspace-select="${ws.id}" data-workspace-path="${ws.path || ''}" title="Open ${ws.name || ws.id}">
                  <div class="ws-item-icon">
                    <i data-lucide="${ws.icon || 'folder'}"></i>
                  </div>
                  <div class="ws-item-body">
                    <div class="ws-item-title-row">
                      <span class="ws-item-name">${ws.name || ws.id}</span>
                      ${activeBadge}
                    </div>
                    <div class="ws-item-meta">
                      ${metaCount}
                      ${metaVerif}
                      ${metaPath}
                    </div>
                  </div>
                  <button class="ws-item-del-btn" title="Remove from history" data-delete-workspace="${ws.id}">
                    <i data-lucide="x"></i>
                  </button>
                </div>
              `;
            }).join('');
          }
          if (window.lucide) window.lucide.createIcons();
          this.bindWorkspaceItems();
        }
      });
      searchInput.addEventListener('click', (e) => e.stopPropagation());
      searchInput.addEventListener('keydown', (e) => e.stopPropagation());
    }

    const btnNew = menu.querySelector('#btnNewWorkspace');
    if (btnNew) {
      btnNew.addEventListener('click', (e) => {
        e.preventDefault();
        this.closeAllDropdowns();
        this.onOpenSetup();
      });
    }

    const btnOpen = menu.querySelector('#btnOpenLocalWorkspace');
    if (btnOpen) {
      btnOpen.addEventListener('click', (e) => {
        e.preventDefault();
        this.closeAllDropdowns();
        this.onOpenSetup();
      });
    }

    const btnClear = menu.querySelector('#btnClearWorkspaceHistory');
    if (btnClear) {
      btnClear.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.onClearWorkspaces();
      });
    }

    if (window.lucide) window.lucide.createIcons();
    this.bindWorkspaceItems();
  }

  setView(view) {
    this.currentView = view;
    this.container.querySelectorAll('.topbar-nav .nav-pill').forEach(p => {
      if (p.dataset.view === view) {
        p.classList.add('nav-pill--active');
      } else {
        p.classList.remove('nav-pill--active');
      }
    });
    this.onViewChange(view);
  }

  setDiagramType(type) {
    this.currentDiagramType = type;
    this.container.querySelectorAll('.segmented-btn[data-diag-type]').forEach(btn => {
      if (btn.dataset.diagType === type) {
        btn.classList.add('segmented-btn--active');
      } else {
        btn.classList.remove('segmented-btn--active');
      }
    });
    this.onDiagramTypeChange(type);
  }

  toggleDropdown(id, trigger) {
    const menu = document.getElementById(id);
    if (!menu) return;

    const isOpen = menu.classList.contains('is-open');
    this.closeAllDropdowns();

    if (!isOpen) {
      menu.classList.add('is-open');
      trigger.classList.add('nav-pill--open');
      this.activeDropdown = menu;
    }
  }

  closeAllDropdowns() {
    this.container.querySelectorAll('.dropdown-menu').forEach(m => m.classList.remove('is-open'));
    this.container.querySelectorAll('.nav-pill').forEach(p => p.classList.remove('nav-pill--open'));
    this.activeDropdown = null;
  }

  applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('umldoc_theme', theme);
    const sunIcon = this.container.querySelector('#themeSunIcon');
    const moonIcon = this.container.querySelector('#themeMoonIcon');
    if (sunIcon && moonIcon) {
      if (theme === 'dark') {
        sunIcon.style.display = 'block';
        moonIcon.style.display = 'none';
      } else {
        sunIcon.style.display = 'none';
        moonIcon.style.display = 'block';
      }
    }
  }

  setProject(projectId, metadata = {}) {
    this.currentProject = projectId;
    const idEl = this.container.querySelector('#projectIdentifier');
    if (idEl) {
      idEl.textContent = projectId.toUpperCase().replace(/[-_]/g, '-');
    }

    const badgeClasses = this.container.querySelector('#badgeClassesCount');
    if (badgeClasses && metadata.classesCount !== undefined) {
      badgeClasses.textContent = `${metadata.classesCount} CLASSES`;
    }

    const badgeVerif = this.container.querySelector('#badgeVerificationStatus');
    if (badgeVerif && metadata.verification) {
      badgeVerif.textContent = metadata.verification;
      badgeVerif.classList.remove('vivid-badge--green', 'vivid-badge--yellow', 'vivid-badge--red');
      const vUpper = metadata.verification.toUpperCase();
      if (vUpper.includes('DRIFT') || vUpper.includes('MISMATCH') || vUpper.includes('CHANGED')) {
        badgeVerif.classList.add('vivid-badge--yellow');
      } else {
        badgeVerif.classList.add('vivid-badge--green');
      }
    }

    // Synchronize active workspace highlight in #menuWorkspaces
    const menu = document.getElementById('menuWorkspaces');
    if (menu) {
      menu.querySelectorAll('.ws-dropdown-item').forEach(item => {
        const wsId = item.dataset.workspaceSelect;
        const isActive = (wsId || '').toLowerCase() === (projectId || '').toLowerCase();
        if (isActive) {
          item.classList.add('is-active');
          if (!item.querySelector('.ws-item-active-badge')) {
            const titleRow = item.querySelector('.ws-item-title-row');
            if (titleRow) {
              const badge = document.createElement('span');
              badge.className = 'ws-item-active-badge';
              badge.textContent = 'ACTIVE';
              titleRow.appendChild(badge);
            }
          }
        } else {
          item.classList.remove('is-active');
          const badge = item.querySelector('.ws-item-active-badge');
          if (badge) badge.remove();
        }
      });
    }
  }

  flashButton(btn) {
    btn.style.transform = 'scale(0.96)';
    setTimeout(() => {
      btn.style.transform = '';
    }, 120);
  }

  spinIcon(btn) {
    const icon = btn.querySelector('svg') || btn.querySelector('i');
    if (icon) {
      icon.style.transition = 'transform 0.6s ease';
      icon.style.transform = 'rotate(360deg)';
      setTimeout(() => {
        icon.style.transition = 'none';
        icon.style.transform = 'rotate(0deg)';
      }, 600);
    }
  }
}
