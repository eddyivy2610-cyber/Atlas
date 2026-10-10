/**
 * ============================================================================
 * FLOATING DIAGRAM CANVAS LEGEND COMPONENT
 * Interactive floating widget with collapsible state and multi-diagram modes
 * (Class, Architecture/Component, Package, Sequence).
 * ============================================================================
 */

export class LegendComponent {
  constructor(options = {}) {
    this.containerId = options.containerId || 'diagCanvasLegend';
    this.containerEl = document.getElementById(this.containerId);
    this.currentType = (options.defaultType || 'class').toLowerCase();
    this.isCollapsed = options.isCollapsed || false;
    this.onToggle = options.onToggle || null;

    if (this.containerEl) {
      this._bindEvents();
      this.render();
    }
  }

  _bindEvents() {
    // Delegated click for header toggle
    this.containerEl.addEventListener('click', (e) => {
      const toggleBtn = e.target.closest('#btnLegendToggle, .diag-legend-header');
      if (toggleBtn) {
        this.toggle();
      }
    });
  }

  toggle() {
    this.isCollapsed = !this.isCollapsed;
    this.containerEl.classList.toggle('is-collapsed', this.isCollapsed);
    if (this.onToggle) this.onToggle(this.isCollapsed);
  }

  collapse() {
    this.isCollapsed = true;
    this.containerEl.classList.add('is-collapsed');
  }

  expand() {
    this.isCollapsed = false;
    this.containerEl.classList.remove('is-collapsed');
  }

  setDiagramType(type) {
    this.currentType = (type || 'class').toLowerCase();
    this.render();
  }

  render() {
    if (!this.containerEl) return;

    this.containerEl.classList.toggle('is-collapsed', this.isCollapsed);

    const typeLabels = {
      class: 'Class Diagram',
      component: 'Architecture',
      architecture: 'Architecture',
      packages: 'Packages',
      package: 'Packages',
      sequence: 'Sequence'
    };

    const label = typeLabels[this.currentType] || 'Class Diagram';

    this.containerEl.innerHTML = `
      <div class="diag-legend-header" title="${this.isCollapsed ? 'Click to expand legend' : 'Click to collapse legend'}">
        <div class="diag-legend-title-group">
          <span class="diag-legend-icon">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="16" x2="12" y2="12"></line>
              <line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
          </span>
          <span class="diag-legend-title">Legend</span>
          <span class="diag-legend-type-pill">${label}</span>
        </div>
        <button class="diag-legend-toggle-btn" id="btnLegendToggle" title="${this.isCollapsed ? 'Expand' : 'Collapse'}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>
      </div>

      <div class="diag-legend-body">
        ${this._renderContentForType(this.currentType)}
      </div>
    `;
  }

  _renderContentForType(type) {
    switch (type) {
      case 'component':
      case 'architecture':
        return this._renderArchitectureLegend();
      case 'packages':
      case 'package':
        return this._renderPackageLegend();
      case 'sequence':
        return this._renderSequenceLegend();
      case 'class':
      default:
        return this._renderClassLegend();
    }
  }

  _renderClassLegend() {
    return `
      <div class="diag-legend-grid">
        <!-- Relationships Column -->
        <div class="diag-legend-col">
          <div class="diag-legend-col-title">Relationships</div>
          
          <div class="diag-legend-row" title="Inheritance: Closed empty triangle">
            <span class="legend-symbol-wrapper">
              <svg width="22" height="12" viewBox="0 0 22 12">
                <line x1="0" y1="6" x2="14" y2="6" stroke="var(--text-primary)" stroke-width="1.6" />
                <polygon points="14 1, 21 6, 14 11" fill="var(--bg-surface)" stroke="var(--text-primary)" stroke-width="1.6" />
              </svg>
            </span>
            <span class="legend-text">Inheritance</span>
          </div>

          <div class="diag-legend-row" title="Realization: Dashed line with empty triangle">
            <span class="legend-symbol-wrapper">
              <svg width="22" height="12" viewBox="0 0 22 12">
                <line x1="0" y1="6" x2="14" y2="6" stroke="var(--text-primary)" stroke-width="1.6" stroke-dasharray="3 2" />
                <polygon points="14 1, 21 6, 14 11" fill="var(--bg-surface)" stroke="var(--text-primary)" stroke-width="1.6" />
              </svg>
            </span>
            <span class="legend-text">Realization</span>
          </div>

          <div class="diag-legend-row" title="Composition: Solid diamond">
            <span class="legend-symbol-wrapper">
              <svg width="22" height="12" viewBox="0 0 22 12">
                <line x1="0" y1="6" x2="13" y2="6" stroke="var(--text-primary)" stroke-width="1.6" />
                <polygon points="13 6, 17 2, 21 6, 17 10" fill="var(--text-primary)" stroke="var(--text-primary)" stroke-width="1" />
              </svg>
            </span>
            <span class="legend-text">Composition</span>
          </div>

          <div class="diag-legend-row" title="Aggregation: Hollow diamond">
            <span class="legend-symbol-wrapper">
              <svg width="22" height="12" viewBox="0 0 22 12">
                <line x1="0" y1="6" x2="13" y2="6" stroke="var(--text-primary)" stroke-width="1.6" />
                <polygon points="13 6, 17 2, 21 6, 17 10" fill="var(--bg-surface)" stroke="var(--text-primary)" stroke-width="1.5" />
              </svg>
            </span>
            <span class="legend-text">Aggregation</span>
          </div>

          <div class="diag-legend-row" title="Dependency: Dashed line with open arrow">
            <span class="legend-symbol-wrapper">
              <svg width="22" height="12" viewBox="0 0 22 12">
                <line x1="0" y1="6" x2="16" y2="6" stroke="var(--text-primary)" stroke-width="1.6" stroke-dasharray="3 2" />
                <polyline points="15 2, 21 6, 15 10" fill="none" stroke="var(--text-primary)" stroke-width="1.6" />
              </svg>
            </span>
            <span class="legend-text">Dependency</span>
          </div>

          <div class="diag-legend-row" title="Association: Direct link">
            <span class="legend-symbol-wrapper">
              <svg width="22" height="12" viewBox="0 0 22 12">
                <line x1="1" y1="6" x2="21" y2="6" stroke="var(--text-primary)" stroke-width="1.6" />
              </svg>
            </span>
            <span class="legend-text">Association</span>
          </div>
        </div>

        <!-- Entity Types & Status Column -->
        <div class="diag-legend-col">
          <div class="diag-legend-col-title">Stereotypes & Status</div>

          <div class="diag-legend-row">
            <span class="legend-swatch legend-swatch--class"></span>
            <span class="legend-text">Class</span>
          </div>

          <div class="diag-legend-row">
            <span class="legend-swatch legend-swatch--interface"></span>
            <span class="legend-text">Interface</span>
          </div>

          <div class="diag-legend-row">
            <span class="legend-swatch legend-swatch--enum"></span>
            <span class="legend-text">Enum</span>
          </div>

          <div class="diag-legend-row">
            <span class="legend-swatch legend-swatch--service"></span>
            <span class="legend-text">Service</span>
          </div>

          <div class="diag-legend-row">
            <svg class="legend-status-icon legend-status-icon--verified" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="8 12 11 15 16 9"></polyline>
            </svg>
            <span class="legend-text">Verified (AST)</span>
          </div>

          <div class="diag-legend-row">
            <svg class="legend-status-icon legend-status-icon--changed" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polygon points="12 2, 22 20, 2 20"></polygon>
              <line x1="12" y1="9" x2="12" y2="13"></line>
              <circle cx="12" cy="17" r="1"></circle>
            </svg>
            <span class="legend-text">Structural Drift</span>
          </div>
        </div>
      </div>
    `;
  }

  _renderArchitectureLegend() {
    return `
      <div class="diag-legend-grid">
        <div class="diag-legend-col">
          <div class="diag-legend-col-title">Relationships</div>

          <div class="diag-legend-row" title="Direct call / use (solid line)">
            <span class="legend-symbol-wrapper">
              <svg width="24" height="12" viewBox="0 0 24 12">
                <line x1="0" y1="6" x2="18" y2="6" stroke="#2563EB" stroke-width="2" />
                <polyline points="15 2, 21 6, 15 10" fill="none" stroke="#2563EB" stroke-width="2" />
              </svg>
            </span>
            <span class="legend-text">Direct Call / Use</span>
          </div>

          <div class="diag-legend-row" title="Import / configuration (dashed line)">
            <span class="legend-symbol-wrapper">
              <svg width="24" height="12" viewBox="0 0 24 12">
                <line x1="0" y1="6" x2="18" y2="6" stroke="#64748B" stroke-width="1.8" stroke-dasharray="5 4" />
                <polyline points="15 2, 21 6, 15 10" fill="none" stroke="#64748B" stroke-width="1.8" />
              </svg>
            </span>
            <span class="legend-text">Import / Config</span>
          </div>

          <div class="diag-legend-row" title="Optional dependency (dotted line)">
            <span class="legend-symbol-wrapper">
              <svg width="24" height="12" viewBox="0 0 24 12">
                <line x1="0" y1="6" x2="18" y2="6" stroke="#64748B" stroke-width="1.8" stroke-dasharray="2 3" />
                <polyline points="15 2, 21 6, 15 10" fill="none" stroke="#64748B" stroke-width="1.8" />
              </svg>
            </span>
            <span class="legend-text">Optional Dep</span>
          </div>
        </div>

        <div class="diag-legend-col">
          <div class="diag-legend-col-title">Component Roles</div>

          <div class="diag-legend-row">
            <span class="legend-swatch" style="background:#7C3AED; border-radius:3px; width:10px; height:10px;"></span>
            <span class="legend-text">«entrypoint» Entry Point</span>
          </div>

          <div class="diag-legend-row">
            <span class="legend-swatch" style="background:#2563EB; border-radius:3px; width:10px; height:10px;"></span>
            <span class="legend-text">«controller» Controller</span>
          </div>

          <div class="diag-legend-row">
            <span class="legend-swatch" style="background:#16A34A; border-radius:3px; width:10px; height:10px;"></span>
            <span class="legend-text">«service» Application Service</span>
          </div>

          <div class="diag-legend-row">
            <span class="legend-swatch" style="background:#D97706; border-radius:3px; width:10px; height:10px;"></span>
            <span class="legend-text">«database» Data Persistence</span>
          </div>

          <div class="diag-legend-row">
            <span class="legend-swatch" style="background:#64748B; border-radius:3px; width:10px; height:10px;"></span>
            <span class="legend-text">«infrastructure» Config / Paths</span>
          </div>
        </div>
      </div>
    `;
  }

  _renderPackageLegend() {
    return `
      <div class="diag-legend-grid">
        <div class="diag-legend-col">
          <div class="diag-legend-col-title">Dependencies</div>

          <div class="diag-legend-row" title="Direct package dependency">
            <span class="legend-symbol-wrapper">
              <svg width="24" height="12" viewBox="0 0 24 12">
                <line x1="1" y1="6" x2="18" y2="6" stroke="var(--text-primary)" stroke-width="1.8" />
                <polygon points="17 2, 23 6, 17 10" fill="var(--text-primary)" />
              </svg>
            </span>
            <span class="legend-text">Package dependency</span>
          </div>

          <div class="diag-legend-row" title="Indirect or optional dependency">
            <span class="legend-symbol-wrapper">
              <svg width="24" height="12" viewBox="0 0 24 12">
                <line x1="1" y1="6" x2="18" y2="6" stroke="var(--text-primary)" stroke-width="1.8" stroke-dasharray="4 3" />
                <polyline points="15 2, 21 6, 15 10" fill="none" stroke="var(--text-primary)" stroke-width="1.8" />
              </svg>
            </span>
            <span class="legend-text">Optional dependency</span>
          </div>
        </div>

        <div class="diag-legend-col">
          <div class="diag-legend-col-title">Node</div>

          <div class="diag-legend-row" title="Package node with metrics">
            <span class="legend-symbol-wrapper" style="color: #3b82f6;">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
                <line x1="12" y1="22.08" x2="12" y2="12"/>
              </svg>
            </span>
            <div style="display: flex; flex-direction: column;">
              <span class="legend-text" style="font-weight: 600;">Package</span>
              <span style="font-size: 9.5px; color: var(--text-tertiary); line-height: 1.2;">Module count, dependency metrics and instability (I)</span>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  _renderSequenceLegend() {
    return `
      <div class="diag-legend-grid">
        <div class="diag-legend-col">
          <div class="diag-legend-col-title">Messages</div>

          <div class="diag-legend-row">
            <span class="legend-symbol-wrapper">
              <svg width="22" height="12" viewBox="0 0 22 12">
                <line x1="1" y1="6" x2="16" y2="6" stroke="var(--text-primary)" stroke-width="1.6" />
                <polygon points="16 2, 21 6, 16 10" fill="var(--text-primary)" stroke="var(--text-primary)" />
              </svg>
            </span>
            <span class="legend-text">Sync Call</span>
          </div>

          <div class="diag-legend-row">
            <span class="legend-symbol-wrapper">
              <svg width="22" height="12" viewBox="0 0 22 12">
                <line x1="1" y1="6" x2="16" y2="6" stroke="var(--text-primary)" stroke-width="1.6" stroke-dasharray="3 2" />
                <polyline points="15 2, 21 6, 15 10" fill="none" stroke="var(--text-primary)" stroke-width="1.6" />
              </svg>
            </span>
            <span class="legend-text">Reply / Return</span>
          </div>
        </div>

        <div class="diag-legend-col">
          <div class="diag-legend-col-title">Execution</div>

          <div class="diag-legend-row">
            <span class="legend-swatch legend-swatch--seq-act"></span>
            <span class="legend-text">Activation Bar</span>
          </div>

          <div class="diag-legend-row">
            <span class="legend-symbol-wrapper">
              <svg width="22" height="12" viewBox="0 0 22 12">
                <line x1="11" y1="0" x2="11" y2="12" stroke="var(--text-secondary)" stroke-width="1.4" stroke-dasharray="2 2" />
              </svg>
            </span>
            <span class="legend-text">Lifeline</span>
          </div>
        </div>
      </div>
    `;
  }
}
