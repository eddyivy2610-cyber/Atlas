/**
 * Diagram & Workspace Control Strip Component
 * Controller for the project header, diagram type switcher, and canvas controls.
 */

export class DiagramControlStrip {
  constructor(options = {}) {
    this.container = options.container || document.querySelector('.diagram-control-strip');
    this.onDiagramTypeChange = options.onDiagramTypeChange || (() => {});
    this.onSearch = options.onSearch || (() => {});
    this.onScopeChange = options.onScopeChange || (() => {});
    this.onLayoutToggle = options.onLayoutToggle || (() => {});
    this.onRegenerate = options.onRegenerate || (() => {});
    this.onExport = options.onExport || (() => {});

    this.currentDiagramType = 'class';
    this.currentLayout = 'TB'; // Top-to-Bottom vs Left-to-Right
    this.searchDebounceTimer = null;

    this.init();
  }

  init() {
    this.bindEvents();
    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  bindEvents() {
    // 1. Diagram Type Switcher buttons
    this.container.querySelectorAll('.segmented-btn[data-diag-type]').forEach(btn => {
      btn.addEventListener('click', () => {
        const type = btn.dataset.diagType;
        this.setDiagramType(type);
      });
    });

    // 2. Search Input with debounce
    const searchInput = this.container.querySelector('#symbolSearchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        clearTimeout(this.searchDebounceTimer);
        const query = e.target.value.trim();
        this.searchDebounceTimer = setTimeout(() => {
          this.onSearch(query);
        }, 180);
      });
    }

    // 3. Layout Toggle (TB <-> LR)
    const layoutBtn = this.container.querySelector('#btnToggleLayout');
    if (layoutBtn) {
      layoutBtn.addEventListener('click', () => {
        this.currentLayout = this.currentLayout === 'TB' ? 'LR' : 'TB';
        const label = layoutBtn.querySelector('.layout-label');
        if (label) label.textContent = this.currentLayout;
        this.onLayoutToggle(this.currentLayout);
      });
    }

    // 4. Regenerate Button
    const btnRegen = this.container.querySelector('#btnRegenDiagram');
    if (btnRegen) {
      btnRegen.addEventListener('click', () => {
        this.spinIcon(btnRegen);
        this.onRegenerate();
      });
    }

    // 5. Export Button
    const btnExport = this.container.querySelector('#btnExportDiagram');
    if (btnExport) {
      btnExport.addEventListener('click', () => {
        this.onExport();
      });
    }

    // 6. Scope Trigger Pill
    const scopeBtn = this.container.querySelector('#btnScopeTrigger');
    if (scopeBtn) {
      scopeBtn.addEventListener('click', () => {
        this.onScopeChange('all');
      });
    }
  }

  setDiagramType(type) {
    this.currentDiagramType = type;
    this.container.querySelectorAll('.segmented-btn[data-diag-type]').forEach(b => {
      if (b.dataset.diagType === type) {
        b.classList.add('segmented-btn--active');
      } else {
        b.classList.remove('segmented-btn--active');
      }
    });

    // Update breadcrumb
    const diagBreadcrumb = this.container.querySelector('#diagBreadcrumb');
    if (diagBreadcrumb) {
      const typeLabels = {
        class: 'Class Diagram',
        sequence: 'Sequence Diagram',
        architecture: 'Architecture Graph',
        packages: 'Package Structure'
      };
      diagBreadcrumb.textContent = typeLabels[type] || 'Diagram';
    }

    this.onDiagramTypeChange(type);
  }

  setProjectInfo(info = {}) {
    const titleEl = this.container.querySelector('#controlStripProjectTitle');
    if (titleEl && info.title) {
      titleEl.textContent = info.title;
    }

    const breadcrumbProj = this.container.querySelector('#projectBreadcrumb');
    if (breadcrumbProj && info.projectName) {
      breadcrumbProj.textContent = info.projectName;
    }

    const classesStat = this.container.querySelector('#statClassesCount');
    if (classesStat && info.classesCount !== undefined) {
      classesStat.textContent = info.classesCount;
    }

    const relationsStat = this.container.querySelector('#statRelationsCount');
    if (relationsStat && info.relationsCount !== undefined) {
      relationsStat.textContent = info.relationsCount;
    }

    const fidelityStat = this.container.querySelector('#statFidelity');
    if (fidelityStat && info.fidelity !== undefined) {
      fidelityStat.textContent = info.fidelity;
    }

    const statusTag = this.container.querySelector('#tagVerificationStatus');
    if (statusTag && info.status) {
      statusTag.textContent = info.status.toUpperCase();
    }
  }

  spinIcon(btn) {
    const icon = btn.querySelector('svg');
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
