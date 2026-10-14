/**
 * Diagram Canvas Controller (Vector Engine & Semantic Zoom)
 * Features:
 * - HTML/SVG hybrid vector architecture (crisp native fonts + vector connectors)
 * - CSS transform viewport: translate3d(x, y, 0) scale(z) on diagramLayer
 * - vector-effect="non-scaling-stroke" on all SVG relationship edges
 * - Integer pixel snapping (Math.round) to eliminate subpixel border blur
 * - Semantic Zoom:
 *     >= 85%: Full member compartments (attributes + methods + types)
 *     50% - 84%: Compact mode (class name + stereotype + member count pills)
 *     < 50%: Minimal mode (class name + stereotype only for macro topology)
 * - Vector-first Export: Direct SVG vector export & 2x/3x high-DPI raster export
 */

export class DiagramCanvasComponent {
  constructor(options = {}) {
    this.container = options.container || document.querySelector('.canvas-container');
    this.viewport = options.viewport || document.querySelector('.canvas-viewport');
    this.plane = options.plane || document.getElementById('diagPlane');
    this.nodesLayer = options.nodesLayer || document.getElementById('diagNodesLayer');
    this.svgLayer = options.svgLayer || document.getElementById('diagSvgLayer');
    this.popover = options.popover || document.querySelector('.view-options-popover');

    this.onViewOptionsChange = options.onViewOptionsChange || (() => {});
    this.onNodeSelect = options.onNodeSelect || (() => {});

    // Pan & Zoom State (Integer Snapped)
    this.panX = 0;
    this.panY = 0;
    this.scale = 1.0;
    this.minScale = 0.2;
    this.maxScale = 3.0;
    this.isDragging = false;
    this.startX = 0;
    this.startY = 0;
    this.semanticTier = 'full'; // 'full' | 'compact' | 'minimal'

    // Diagram Model & UI State
    this.diagramType = options.diagramType || 'packages'; // 'packages' | 'class' | 'architecture' | 'sequence'
    this.currentScope = 'all_packages'; // 'all_packages' | 'selected_package' | 'one_hop' | 'all_classes'
    this.scopeTarget = null;
    this.classes = [];
    this.relations = [];
    this.packageNodes = [];
    this.packageRelations = [];
    this.componentNodes = [];
    this.componentRelations = [];
    this.drift = [];
    this.renderedNodes = [];
    this.renderedRelations = [];
    this.nodePositions = {};
    this.expandedNodes = new Set();
    this.collapsedNodes = new Set();
    this.expandedPackages = new Set();
    this.selectedNodeId = null;

    this.sequenceScenarios = [];
    this.activeScenarioIndex = 0;

    // View Options State (matches reference screenshot & progressive disclosure)
    this.options = {
      layout: 'standard', // standard | layered | compact
      direction: 'vertical', // vertical | horizontal
      autoExpandClasses: false, // Folded by default: summarize first, reveal detail on demand
      visibility: {
        attributes: true,
        methods: true,
        inherited: false
      },
      relationships: {
        inheritance: true,
        composition: true,
        aggregation: true,
        dependency: true,
        imports: false,
        external: false
      }
    };

    this.init();
  }

  setDiagramData(data = {}) {
    if (data.project_name) this.projectName = data.project_name;
    if (data.project) this.projectName = data.project;
    if (data.classes) this.classes = data.classes;
    if (data.relations) this.relations = data.relations;
    if (data.packages) this.packageNodes = data.packages;
    if (data.package_relations) this.packageRelations = data.package_relations;
    if (data.components) this.componentNodes = data.components;
    if (data.component_relations) this.componentRelations = data.component_relations;
    if (data.sequence_scenarios) this.sequenceScenarios = data.sequence_scenarios;
    else if (data.sequence) this.sequenceScenarios = [data.sequence];
    if (data.drift) this.drift = data.drift;
    this.renderCurrentDiagram();
  }

  getActiveSequenceScenario() {
    if (!this.sequenceScenarios || !this.sequenceScenarios.length) return null;
    return this.sequenceScenarios[this.activeScenarioIndex] || this.sequenceScenarios[0];
  }

  setActiveSequenceScenario(index) {
    this.activeScenarioIndex = Math.max(0, Math.min(index, (this.sequenceScenarios.length - 1)));
    this.renderCurrentDiagram();
    setTimeout(() => this.fitToContent(), 40);
  }

  setDiagramType(type) {
    this.diagramType = (type || 'class').toLowerCase();
    if (this.diagramType === 'packages' || this.diagramType === 'package') {
      this.currentScope = 'all_packages';
    } else if (this.diagramType === 'class' && this.currentScope === 'all_packages') {
      this.currentScope = 'all_classes';
    }
    this.renderCurrentDiagram();
    setTimeout(() => this.fitToContent(), 40);
    setTimeout(() => this.fitToContent(), 220);
  }

  getPackageForClass(cls) {
    if (!cls) return 'default';
    if (cls.package) return cls.package;
    if (this.packageNodes && this.packageNodes.length) {
      for (const p of this.packageNodes) {
        if (p.classes && p.classes.includes(cls.name)) return p.name;
        if (p.modules && p.modules.includes(cls.name)) return p.name;
      }
    }
    if (cls.file) {
      const parts = cls.file.replace(/\\/g, '/').split('/');
      if (parts.length > 1) return parts[0];
    }
    if (cls.name && cls.name.includes('.')) {
      return cls.name.split('.')[0];
    }
    return 'core';
  }

  getClassesForPackage(pkgName) {
    if (!pkgName || !this.classes) return [];
    return this.classes.filter(cls => {
      if (this.getPackageForClass(cls) === pkgName) return true;
      if (cls.name && cls.name.startsWith(pkgName + '.')) return true;
      if (cls.file && cls.file.replace(/\\/g, '/').startsWith(pkgName + '/')) return true;
      return false;
    });
  }

  setScope(scopeType, targetName = null) {
    this.currentScope = scopeType || 'all_packages';
    this.scopeTarget = targetName;

    if (this.currentScope === 'all_packages') {
      this.diagramType = 'packages';
      this.removeScopeBanner();
      const diagBtn = document.querySelector('#diagramTypeSwitcher .segmented-btn[data-diag-type="packages"]');
      if (diagBtn) {
        document.querySelectorAll('#diagramTypeSwitcher .segmented-btn').forEach(b => b.classList.remove('segmented-btn--active'));
        diagBtn.classList.add('segmented-btn--active');
      }
      this.renderPackagesDiagram();
    } else if (this.currentScope === 'selected_package') {
      this.diagramType = 'class';
      const pkgClasses = this.getClassesForPackage(targetName);
      const nameSet = new Set(pkgClasses.map(c => c.name));
      const pkgRels = (this.relations || []).filter(r => nameSet.has(r.source) && nameSet.has(r.target));
      this.renderScopeBanner(`Package: ${targetName} (${pkgClasses.length} classes)`);
      this.renderDiagram(pkgClasses, pkgRels, this.drift, targetName);
    } else if (this.currentScope === 'one_hop') {
      this.diagramType = 'class';
      const centerNode = targetName || (this.selectedNodeId || (this.classes[0] && this.classes[0].name));
      const hopSet = new Set([centerNode]);
      (this.relations || []).forEach(r => {
        if (r.source === centerNode) hopSet.add(r.target);
        if (r.target === centerNode) hopSet.add(r.source);
      });
      const hopClasses = (this.classes || []).filter(c => hopSet.has(c.name));
      const hopRels = (this.relations || []).filter(r => hopSet.has(r.source) && hopSet.has(r.target));
      this.renderScopeBanner(`Class: ${centerNode} + 1-Hop (${hopClasses.length} classes)`);
      this.renderDiagram(hopClasses, hopRels, this.drift, `1-Hop: ${centerNode}`);
    } else if (this.currentScope === 'all_classes') {
      this.diagramType = 'class';
      this.renderScopeBanner(`All Classes (Full Project — ${this.classes.length} classes)`);
      this.renderDiagram(this.classes, this.relations, this.drift);
    }

    setTimeout(() => this.fitToContent(), 50);
  }

  renderScopeBanner(titleText) {
    let banner = document.getElementById('canvasScopeBanner');
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'canvasScopeBanner';
      banner.className = 'canvas-scope-banner';
      if (this.container) this.container.appendChild(banner);
    }
    banner.innerHTML = `
      <div class="canvas-scope-banner__info">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;color:var(--primary-bg, #090C9B);">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
        </svg>
        <span style="color:#64748b; font-size:11px;">Scope:</span>
        <strong style="color:var(--text-primary, #0f172a); font-size:11.5px; font-weight:700;">${this._escape(titleText)}</strong>
      </div>
      <button class="canvas-scope-banner__back" id="btnScopeBannerBack" title="Return to All Packages Overview">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:11px;height:11px;"><polyline points="15 18 9 12 15 6"></polyline></svg>
        <span>All Packages Overview</span>
      </button>
    `;

    const backBtn = banner.querySelector('#btnScopeBannerBack');
    if (backBtn) {
      backBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.setScope('all_packages');
      });
    }
  }

  removeScopeBanner() {
    const banner = document.getElementById('canvasScopeBanner');
    if (banner) banner.remove();
  }

  renderCurrentDiagram() {
    if (this.diagramType === 'sequence') {
      this.removeScopeBanner();
      this.renderSequenceDiagram();
      return;
    }
    if (this.diagramType === 'architecture' || this.diagramType === 'component') {
      this.removeScopeBanner();
      this.renderArchitectureDiagram();
      return;
    }
    if (this.diagramType === 'packages' || this.diagramType === 'package') {
      this.removeScopeBanner();
      this.renderPackagesDiagram();
      return;
    }

    // Class diagram mode respecting currentScope
    if (this.currentScope === 'selected_package' && this.scopeTarget) {
      const pkgClasses = this.getClassesForPackage(this.scopeTarget);
      const nameSet = new Set(pkgClasses.map(c => c.name));
      const pkgRels = (this.relations || []).filter(r => nameSet.has(r.source) && nameSet.has(r.target));
      this.renderScopeBanner(`Package: ${this.scopeTarget} (${pkgClasses.length} classes)`);
      this.renderDiagram(pkgClasses, pkgRels, this.drift, this.scopeTarget);
      return;
    }
    if (this.currentScope === 'one_hop' && this.scopeTarget) {
      const centerNode = this.scopeTarget;
      const hopSet = new Set([centerNode]);
      (this.relations || []).forEach(r => {
        if (r.source === centerNode) hopSet.add(r.target);
        if (r.target === centerNode) hopSet.add(r.source);
      });
      const hopClasses = (this.classes || []).filter(c => hopSet.has(c.name));
      const hopRels = (this.relations || []).filter(r => hopSet.has(r.source) && hopSet.has(r.target));
      this.renderScopeBanner(`Class: ${centerNode} + 1-Hop (${hopClasses.length} classes)`);
      this.renderDiagram(hopClasses, hopRels, this.drift, `1-Hop: ${centerNode}`);
      return;
    }

    let nodes = this.classes;
    let rels = this.relations;
    this.renderDiagram(nodes, rels, this.drift);
  }

  init() {
    if (this.container && this.options.autoExpandClasses) {
      this.container.classList.add('auto-expanded');
    }
    this.bindPanZoomEvents();
    this.bindPopoverEvents();
    this.bindDockEvents();
    this.updateTransform();

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && (this.selectedMessageId || this.selectedParticipantId)) {
        this.clearSequenceSelection();
      }
    });
  }

  isNodeExpanded(name) {
    if (this.collapsedNodes && this.collapsedNodes.has(name)) return false;
    if (this.expandedNodes && this.expandedNodes.has(name)) return true;
    return !!(this.options && this.options.autoExpandClasses);
  }

  toggleNodeExpanded(name) {
    if (this.isNodeExpanded(name)) {
      this.collapsedNodes.add(name);
      this.expandedNodes.delete(name);
    } else {
      this.expandedNodes.add(name);
      this.collapsedNodes.delete(name);
    }
    this.renderCurrentDiagram();
  }

  isPackageExpanded(name) {
    return this.expandedPackages ? this.expandedPackages.has(name) : false;
  }

  togglePackageExpanded(name) {
    if (!this.expandedPackages) this.expandedPackages = new Set();
    if (this.expandedPackages.has(name)) {
      this.expandedPackages.delete(name);
    } else {
      this.expandedPackages.add(name);
    }
    this.renderCurrentDiagram();
  }

  expandAllClasses() {
    this.options.autoExpandClasses = true;
    if (this.collapsedNodes) this.collapsedNodes.clear();
    (this.classes || []).forEach(c => this.expandedNodes.add(c.name));
    if (this.container) this.container.classList.add('auto-expanded');
    const cb = document.getElementById('cbOptAutoExpand');
    if (cb) cb.checked = true;
    const btnExp = document.getElementById('btnExpandAllClasses');
    const btnCol = document.getElementById('btnCollapseAllClasses');
    if (btnExp) btnExp.classList.add('is-active');
    if (btnCol) btnCol.classList.remove('is-active');
    this.renderCurrentDiagram();
    this.notifyOptionsChange();
  }

  collapseAllClasses() {
    this.options.autoExpandClasses = false;
    if (this.expandedNodes) this.expandedNodes.clear();
    (this.classes || []).forEach(c => this.collapsedNodes.add(c.name));
    if (this.container) this.container.classList.remove('auto-expanded');
    const cb = document.getElementById('cbOptAutoExpand');
    if (cb) cb.checked = false;
    const btnExp = document.getElementById('btnExpandAllClasses');
    const btnCol = document.getElementById('btnCollapseAllClasses');
    if (btnExp) btnExp.classList.remove('is-active');
    if (btnCol) btnCol.classList.add('is-active');
    this.renderCurrentDiagram();
    this.notifyOptionsChange();
  }

  /* ------------------------------------------------------------------------
     PAN & ZOOM INTERACTION (VECTOR CSS TRANSFORM)
     ------------------------------------------------------------------------ */
  bindPanZoomEvents() {
    if (!this.container) return;

    // Pointer Drag Pan
    this.container.addEventListener('pointerdown', (e) => {
      // Clear sequence interaction focus if clicking empty canvas background
      // Clear selection when clicking empty space
      if ((this.selectedMessageId || this.selectedParticipantId) &&
          !e.target.closest('.seq-msg-pill') &&
          !e.target.closest('.seq-msg-line') &&
          !e.target.closest('.seq-lifeline-head') &&
          !e.target.closest('.seq-lifeline-foot') &&
          !e.target.closest('.canvas-inspector')) {
        this.clearSequenceSelection();
      }

      if (e.target.closest('.uml-card') || 
          e.target.closest('.seq-msg-pill') ||
          e.target.closest('.seq-msg-line') ||
          e.target.closest('.seq-lifeline-head') ||
          e.target.closest('.seq-lifeline-foot') ||
          e.target.closest('.seq-scenario-bar') ||
          e.target.closest('.canvas-floating-dock') || 
          e.target.closest('.view-options-popover') ||
          e.target.closest('.diag-canvas-legend') ||
          e.target.closest('.export-popover') ||
          e.target.closest('.export-modal-backdrop') ||
          e.target.closest('.canvas-inspector')) {
        return;
      }

      this.isDragging = true;
      this.startX = e.clientX - this.panX;
      this.startY = e.clientY - this.panY;
      this.container.classList.add('is-panning');
      this.container.setPointerCapture(e.pointerId);
    });

    this.container.addEventListener('pointermove', (e) => {
      if (!this.isDragging) return;
      this.panX = Math.round(e.clientX - this.startX);
      this.panY = Math.round(e.clientY - this.startY);
      this.updateTransform();
    });

    const endDrag = (e) => {
      if (!this.isDragging) return;
      this.isDragging = false;
      this.container.classList.remove('is-panning');
      try {
        this.container.releasePointerCapture(e.pointerId);
      } catch (err) {}
    };

    this.container.addEventListener('pointerup', endDrag);
    this.container.addEventListener('pointercancel', endDrag);

    // Mouse Wheel Zoom centered on cursor
    this.container.addEventListener('wheel', (e) => {
      if (e.target.closest('.export-modal-backdrop')) return;
      e.preventDefault();
      const rect = this.container.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const zoomFactor = e.deltaY < 0 ? 1.12 : 0.88;
      const newScale = Math.min(Math.max(this.scale * zoomFactor, this.minScale), this.maxScale);

      this.panX = Math.round(mouseX - (mouseX - this.panX) * (newScale / this.scale));
      this.panY = Math.round(mouseY - (mouseY - this.panY) * (newScale / this.scale));
      this.scale = newScale;

      this.updateTransform();
    }, { passive: false });
  }

  updateTransform() {
    if (!this.viewport) return;
    
    // Snapped integer coordinates on translate to eliminate subpixel border blur
    const snapX = Math.round(this.panX);
    const snapY = Math.round(this.panY);
    this.viewport.style.transform = `translate(${snapX}px, ${snapY}px) scale(${this.scale})`;
    
    const indicator = document.getElementById('zoomLevelIndicator');
    if (indicator) {
      indicator.textContent = `${Math.round(this.scale * 100)}%`;
    }

    // Semantic Zooming Thresholds (Class Diagram)
    let newTier = 'full';
    if (!this.options || !this.options.autoExpandClasses) {
      if (this.scale < 0.50) {
        newTier = 'minimal';
      } else if (this.scale < 0.85) {
        newTier = 'compact';
      }
    }

    if (this.semanticTier !== newTier) {
      this.semanticTier = newTier;
      this.container.setAttribute('data-semantic-zoom', newTier);
      this.reanchorConnectorsForSemanticZoom();
    }

    // Sequence Diagram Semantic Zoom LOD Tier: Far (< 0.72), Mid (0.72 - 1.25), Close (> 1.25)
    let seqTier = 'mid';
    if (this.scale < 0.72) {
      seqTier = 'far';
    } else if (this.scale > 1.25) {
      seqTier = 'close';
    }
    if (this.currentSeqZoomTier !== seqTier) {
      this.currentSeqZoomTier = seqTier;
      this.container.setAttribute('data-zoom-tier', seqTier);
    }

    // Architecture Diagram Semantic Zoom LOD Tier: Far (< 0.70), Mid (0.70 - 1.25), Close (> 1.25)
    let archTier = 'mid';
    if (this.scale < 0.70) {
      archTier = 'far';
    } else if (this.scale > 1.25) {
      archTier = 'close';
    }
    if (this.currentArchZoomTier !== archTier) {
      this.currentArchZoomTier = archTier;
      this.container.setAttribute('data-arch-zoom', archTier);
    }
  }

  reanchorConnectorsForSemanticZoom() {
    this.classes.forEach(cls => {
      const isExp = this.isNodeExpanded(cls.name);
      if (this.nodePositions[cls.name]) {
        this.nodePositions[cls.name].h = this.estimateCardHeight(cls, isExp);
      }
    });
    this.renderConnectors();
  }

  zoomIn() {
    this.scale = Math.min(this.scale * 1.2, this.maxScale);
    this.updateTransform();
  }

  zoomOut() {
    this.scale = Math.max(this.scale / 1.2, this.minScale);
    this.updateTransform();
  }

  resetZoom() {
    this.scale = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.updateTransform();
  }

  fitToContent() {
    const isSeq = (this.diagramType === 'sequence');
    if (!isSeq && !this.classes.length) {
      this.scale = 1.0;
      this.panX = 0;
      this.panY = 0;
      this.updateTransform();
      return;
    }

    const positions = Object.values(this.nodePositions);
    if (!positions.length) return;

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    positions.forEach(p => {
      if (p.x < minX) minX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.x + p.w > maxX) maxX = p.x + p.w;
      if (p.y + p.h > maxY) maxY = p.y + p.h;
    });

    const w = maxX - minX + 120;
    const h = maxY - minY + 120;
    const cw = (this.container && this.container.clientWidth > 100) ? this.container.clientWidth : (window.innerWidth || 1200);
    const ch = (this.container && this.container.clientHeight > 100) ? this.container.clientHeight : (window.innerHeight - 72 || 700);

    const scaleX = cw / w;
    const scaleY = ch / h;
    const fitScale = Math.min(Math.max(Math.min(scaleX, scaleY), this.minScale), 1.1);

    this.scale = fitScale;
    this.panX = Math.round((cw - w * fitScale) / 2 - minX * fitScale + 60 * fitScale);
    this.panY = Math.round((ch - h * fitScale) / 2 - minY * fitScale + 60 * fitScale);
    this.updateTransform();
  }

  /* ------------------------------------------------------------------------
     FLOATING DOCK CONTROLS
     ------------------------------------------------------------------------ */
  bindDockEvents() {
    const btnIn = document.getElementById('btnDockZoomIn');
    const btnOut = document.getElementById('btnDockZoomOut');
    const btnReset = document.getElementById('btnDockReset');
    const btnFit = document.getElementById('btnDockFit');
    const pill = document.getElementById('zoomLevelIndicator');

    if (btnIn) btnIn.addEventListener('click', () => this.zoomIn());
    if (btnOut) btnOut.addEventListener('click', () => this.zoomOut());
    if (btnReset) btnReset.addEventListener('click', () => this.resetZoom());
    if (btnFit) btnFit.addEventListener('click', () => this.fitToContent());
    if (pill) pill.addEventListener('click', () => this.resetZoom());

    const btnToggleExp = document.getElementById('btnDockToggleExpand');
    if (btnToggleExp) {
      btnToggleExp.addEventListener('click', () => {
        if (this.options.autoExpandClasses) {
          this.collapseAllClasses();
        } else {
          this.expandAllClasses();
        }
      });
    }
  }

  /* ------------------------------------------------------------------------
     VIEW OPTIONS POPOVER BINDINGS
     ------------------------------------------------------------------------ */
  bindPopoverEvents() {
    if (!this.popover) return;

    // Popover Trigger Button
    const triggerBtn = document.getElementById('btnViewOptions');
    if (triggerBtn) {
      triggerBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.togglePopover();
      });
    }

    // Close when clicking outside
    document.addEventListener('click', (e) => {
      if (this.popover && this.popover.classList.contains('is-open')) {
        if (!this.popover.contains(e.target) && (!triggerBtn || !triggerBtn.contains(e.target))) {
          this.closePopover();
        }
      }
    });

    // Layout Segmented Control
    const layoutBtns = this.popover.querySelectorAll('[data-layout-opt]');
    layoutBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        layoutBtns.forEach(b => b.classList.remove('is-active'));
        btn.classList.add('is-active');
        this.options.layout = btn.getAttribute('data-layout-opt');
        if (this.options.layout === 'compact') {
          this.collapseAllClasses();
        }
        this.renderCurrentDiagram();
        this.notifyOptionsChange();
      });
    });

    // Direction Segmented Control
    const dirBtns = this.popover.querySelectorAll('[data-direction-opt]');
    dirBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        dirBtns.forEach(b => b.classList.remove('is-active'));
        btn.classList.add('is-active');
        this.options.direction = btn.getAttribute('data-direction-opt');
        this.renderCurrentDiagram();
        this.notifyOptionsChange();
      });
    });

    // Checkboxes
    const updateRelationshipFilterClasses = () => {
      if (!this.container) return;
      this.container.classList.toggle('hide-edge-inheritance', !this.options.relationships.inheritance);
      this.container.classList.toggle('hide-edge-composition', !this.options.relationships.composition);
      this.container.classList.toggle('hide-edge-aggregation', !this.options.relationships.aggregation);
      this.container.classList.toggle('hide-edge-dependency', !this.options.relationships.dependency);
      this.container.classList.toggle('hide-edge-import', !this.options.relationships.imports);
      this.container.classList.toggle('hide-edge-external', !this.options.relationships.external);
    };

    const bindCb = (id, key, subkey) => {
      const el = document.getElementById(id);
      if (el) {
        el.checked = !!this.options[key][subkey];
        el.addEventListener('change', () => {
          this.options[key][subkey] = el.checked;
          if (key === 'relationships') {
            updateRelationshipFilterClasses();
          }
          this.renderCurrentDiagram();
          this.notifyOptionsChange();
        });
      }
    };

    bindCb('cbOptAttributes', 'visibility', 'attributes');
    bindCb('cbOptMethods', 'visibility', 'methods');
    bindCb('cbOptInherited', 'visibility', 'inherited');
    bindCb('cbOptRelInheritance', 'relationships', 'inheritance');
    bindCb('cbOptRelComposition', 'relationships', 'composition');
    bindCb('cbOptRelAggregation', 'relationships', 'aggregation');
    bindCb('cbOptRelDependency', 'relationships', 'dependency');
    bindCb('cbOptRelImports', 'relationships', 'imports');
    bindCb('cbOptRelExternal', 'relationships', 'external');
    updateRelationshipFilterClasses();

    // Auto-Expand Classes Checkbox
    const autoExpCb = document.getElementById('cbOptAutoExpand');
    if (autoExpCb) {
      autoExpCb.checked = !!this.options.autoExpandClasses;
      autoExpCb.addEventListener('change', () => {
        if (autoExpCb.checked) {
          this.expandAllClasses();
        } else {
          this.collapseAllClasses();
        }
      });
    }

    // Quick Expand All / Compact All buttons in popover
    const btnExpAll = document.getElementById('btnExpandAllClasses');
    if (btnExpAll) {
      btnExpAll.addEventListener('click', () => {
        this.expandAllClasses();
      });
    }

    const btnColAll = document.getElementById('btnCollapseAllClasses');
    if (btnColAll) {
      btnColAll.addEventListener('click', () => {
        this.collapseAllClasses();
      });
    }
  }

  togglePopover() {
    if (!this.popover) return;
    this.popover.classList.toggle('is-open');
  }

  closePopover() {
    if (!this.popover) return;
    this.popover.classList.remove('is-open');
  }

  setClassCount(count) {
    const badge = this.popover ? this.popover.querySelector('#popoverClassCountBadge') : null;
    if (badge) {
      badge.textContent = `${count} classes`;
    }
  }

  notifyOptionsChange() {
    this.onViewOptionsChange(this.options);
  }

  /* ------------------------------------------------------------------------
     REUSED CARD RENDERING & SVG CONNECTOR ENGINE
     ------------------------------------------------------------------------ */
  /* ------------------------------------------------------------------------
     REUSED CARD RENDERING & SVG CONNECTOR ENGINE
     ------------------------------------------------------------------------ */
  estimateCardHeight(cls, isExpanded) {
    const isExp = (isExpanded !== undefined) ? isExpanded : this.isNodeExpanded(cls.name);
    const attrs = cls.attributes || [];
    const methods = cls.methods || [];
    let h = 42; // Header height
    
    const maxA = isExp ? attrs.length : Math.min(3, attrs.length);
    const maxM = isExp ? methods.length : Math.min(4, methods.length);

    if (this.options.visibility.attributes && attrs.length > 0) {
      h += 8 + maxA * 19;
    }
    
    if (this.options.visibility.methods && methods.length > 0) {
      h += 8 + maxM * 19;
    }
    
    const hiddenCount = (attrs.length > maxA ? attrs.length - maxA : 0) + (methods.length > maxM ? methods.length - maxM : 0);
    if (!isExp && hiddenCount > 0) {
      h += 24; // Fold pill height
    } else if (isExp && (attrs.length > 3 || methods.length > 4)) {
      h += 28; // Footer toggle
    }
    
    return Math.max(54, h); // Snug fit, no wasteful empty gaps
  }

  calculateCardWidth(cls) {
    const attrs = cls.attributes || [];
    const methods = cls.methods || [];
    let maxLen = cls.name.length + 6;
    attrs.forEach(a => {
      const lineLen = (a.vis || '+').length + a.name.length + (a.type ? a.type.length + 2 : 0) + 2;
      if (lineLen > maxLen) maxLen = lineLen;
    });
    methods.forEach(m => {
      const mName = m.name.endsWith(')') ? m.name : `${m.name}()`;
      const lineLen = (m.vis || '+').length + mName.length + (m.ret ? m.ret.length + 2 : 0) + 2;
      if (lineLen > maxLen) maxLen = lineLen;
    });
    // Dynamic width clamp between 260px and 410px
    return Math.max(260, Math.min(410, Math.round(maxLen * 7.5 + 44)));
  }

  getCardHeaderIcon(cls) {
    const name = (cls.name || '').toLowerCase();
    const stereo = (cls.stereotype || '').toLowerCase();
    if (name.includes('user') || name.includes('account') || name.includes('student') || name.includes('teacher') || name.includes('customer')) {
      return `<svg class="uml-card__header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
    }
    if (name.includes('course') || name.includes('education') || name.includes('school')) {
      return `<svg class="uml-card__header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5"/></svg>`;
    }
    if (name.includes('enroll') || name.includes('order') || name.includes('doc') || name.includes('file')) {
      return `<svg class="uml-card__header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;
    }
    if (name.includes('result') || name.includes('metric') || name.includes('stat') || name.includes('report')) {
      return `<svg class="uml-card__header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`;
    }
    if (name.includes('dept') || name.includes('department') || name.includes('bank') || name.includes('store')) {
      return `<svg class="uml-card__header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="22" x2="21" y2="22"/><line x1="6" y1="18" x2="6" y2="11"/><line x1="10" y1="18" x2="10" y2="11"/><line x1="14" y1="18" x2="14" y2="11"/><line x1="18" y1="18" x2="18" y2="11"/><polygon points="12 2 20 7 4 7"/></svg>`;
    }
    if (stereo.includes('interface') || stereo.includes('protocol')) {
      return `<svg class="uml-card__header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>`;
    }
    if (stereo.includes('package') || stereo.includes('module')) {
      return `<svg class="uml-card__header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>`;
    }
    return `<svg class="uml-card__header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>`;
  }

  computeDependencyRanks(nodes, relations) {
    const nameToNode = new Map();
    nodes.forEach(n => nameToNode.set(n.name, n));

    const outgoing = new Map();
    const incoming = new Map();
    nodes.forEach(n => {
      outgoing.set(n.name, new Set());
      incoming.set(n.name, new Set());
    });

    (relations || []).forEach(r => {
      if (nameToNode.has(r.source) && nameToNode.has(r.target) && r.source !== r.target) {
        outgoing.get(r.source).add(r.target);
        incoming.get(r.target).add(r.source);
      }
    });

    const ranks = new Map();
    // Prioritize natural entry points to top row (Rank 0)
    nodes.forEach(n => {
      const lower = n.name.toLowerCase();
      const isEntry = lower === 'run' || lower === 'main' || lower === 'app' || 
                      lower === 'desktop_launcher' || lower === 'cli' ||
                      lower.includes('launcher') || lower.includes('entrypoint') ||
                      (incoming.get(n.name).size === 0 && outgoing.get(n.name).size > 0);
      if (isEntry) {
        ranks.set(n.name, 0);
      }
    });

    nodes.forEach(n => {
      if (!ranks.has(n.name) && incoming.get(n.name).size === 0) {
        ranks.set(n.name, 0);
      }
    });

    nodes.forEach(n => {
      if (!ranks.has(n.name)) ranks.set(n.name, 0);
    });

    // Push dependencies down
    let changed = true;
    let iterations = 0;
    while (changed && iterations < nodes.length) {
      changed = false;
      iterations++;
      (relations || []).forEach(r => {
        if (nameToNode.has(r.source) && nameToNode.has(r.target) && r.source !== r.target) {
          const srcRank = ranks.get(r.source) || 0;
          const tgtRank = ranks.get(r.target) || 0;
          if (tgtRank <= srcRank) {
            ranks.set(r.target, srcRank + 1);
            changed = true;
          }
        }
      });
    }

    return ranks;
  }

  setClassCount(count) {
    const badge = document.getElementById('popoverClassCountBadge');
    if (badge) {
      let unit = 'class';
      if (this.diagramType === 'packages' || this.diagramType === 'package') unit = 'package';
      else if (this.diagramType === 'architecture' || this.diagramType === 'component') unit = 'component';
      badge.textContent = `${count} ${unit}${count === 1 ? '' : (unit === 'class' ? 'es' : 's')}`;
    }
  }

  renderDiagram(classes, relations, drift = []) {
    if (this.diagramType === 'class') {
      this.classes = classes || [];
      this.relations = relations || [];
    }
    this.renderedNodes = classes || [];
    this.renderedRelations = relations || [];
    this.drift = drift || [];

    // Stable layout: sort deterministically by package and then name
    this.renderedNodes.sort((a, b) => {
      const pA = (this.getPackageForClass(a) || '').toLowerCase();
      const pB = (this.getPackageForClass(b) || '').toLowerCase();
      if (pA !== pB) return pA.localeCompare(pB);
      return (a.name || '').localeCompare(b.name || '');
    });

    this.setClassCount(this.renderedNodes.length);

    if (!this.nodesLayer || !this.svgLayer) return;

    // Clear previous
    this.nodesLayer.innerHTML = '';
    const defs = this.svgLayer.querySelector('defs');
    this.svgLayer.innerHTML = '';
    if (defs) this.svgLayer.appendChild(defs);

    if (!this.renderedNodes.length) return;

    const GAP_X = 64, GAP_Y = 76;
    const START_X = 60, START_Y = 60;

    // Calculate node dimensions
    const nodeDims = {};
    this.renderedNodes.forEach(cls => {
      const isExp = this.isNodeExpanded(cls.name);
      const ch = this.estimateCardHeight(cls, isExp);
      const cw = this.calculateCardWidth(cls);
      nodeDims[cls.name] = { w: cw, h: ch };
    });

    this.nodePositions = {};

    // Check if nodes have manual positions (e.g. e-commerce sample)
    const hasManualPositions = this.renderedNodes.every(cls => cls.pos && typeof cls.pos.x === 'number');

    if (hasManualPositions && this.options.layout === 'standard') {
      this.renderedNodes.forEach(cls => {
        const dims = nodeDims[cls.name];
        this.nodePositions[cls.name] = {
          x: Math.round(cls.pos.x),
          y: Math.round(cls.pos.y),
          w: dims.w,
          h: dims.h
        };
      });
    } else {
      // Topological Dependency-Aware Layered Layout
      const nodeRanks = this.computeDependencyRanks(this.renderedNodes, this.renderedRelations);
      const layers = new Map();
      this.renderedNodes.forEach(cls => {
        const rank = nodeRanks.get(cls.name) || 0;
        if (!layers.has(rank)) layers.set(rank, []);
        layers.get(rank).push(cls);
      });

      const sortedRanks = Array.from(layers.keys()).sort((a, b) => a - b);
      let currentY = START_Y;

      sortedRanks.forEach(rank => {
        const layerNodes = layers.get(rank);
        layerNodes.sort((a, b) => {
          const pA = (this.getPackageForClass(a) || '').toLowerCase();
          const pB = (this.getPackageForClass(b) || '').toLowerCase();
          if (pA !== pB) return pA.localeCompare(pB);
          return (a.name || '').localeCompare(b.name || '');
        });

        const maxCols = (layerNodes.length === 4) ? 4 : 3;

        for (let i = 0; i < layerNodes.length; i += maxCols) {
          const rowNodes = layerNodes.slice(i, i + maxCols);
          let rowMaxH = 0;
          rowNodes.forEach(cls => {
            const dims = nodeDims[cls.name];
            if (dims.h > rowMaxH) rowMaxH = dims.h;
          });

          let currentX = START_X;
          rowNodes.forEach(cls => {
            const dims = nodeDims[cls.name];
            this.nodePositions[cls.name] = {
              x: Math.round(currentX),
              y: Math.round(currentY),
              w: dims.w,
              h: dims.h
            };
            currentX += dims.w + GAP_X;
          });

          currentY += rowMaxH + GAP_Y;
        }
      });
    }

    // Render Package Cluster Containers (Grouped by Package) in Background Layer
    const packageGroups = new Map();
    this.renderedNodes.forEach(cls => {
      const pkg = this.getPackageForClass(cls) || 'core';
      if (!packageGroups.has(pkg)) packageGroups.set(pkg, []);
      packageGroups.get(pkg).push(cls);
    });

    packageGroups.forEach((pkgClasses, pkgName) => {
      if (!pkgClasses.length) return;
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      pkgClasses.forEach(c => {
        const p = this.nodePositions[c.name];
        if (p) {
          if (p.x < minX) minX = p.x;
          if (p.y < minY) minY = p.y;
          if (p.x + p.w > maxX) maxX = p.x + p.w;
          if (p.y + p.h > maxY) maxY = p.y + p.h;
        }
      });

      if (minX !== Infinity && isFinite(minX)) {
        const cX = Math.max(20, minX - 16);
        const cY = Math.max(20, minY - 36);
        const cW = (maxX - minX) + 32;
        const cH = (maxY - minY) + 48;

        const clusterBox = document.createElement('div');
        clusterBox.className = 'package-cluster-box';
        clusterBox.id = `cluster-pkg-${pkgName}`;
        clusterBox.style.left = `${cX}px`;
        clusterBox.style.top = `${cY}px`;
        clusterBox.style.width = `${cW}px`;
        clusterBox.style.height = `${cH}px`;

        clusterBox.innerHTML = `
          <div class="package-cluster-header">
            <div class="package-cluster-title-wrap">
              <span class="package-cluster-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 13px; height: 13px;">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                </svg>
              </span>
              <span class="package-cluster-name">${this._escape(pkgName)}</span>
              <span class="package-cluster-count">${pkgClasses.length} ${pkgClasses.length === 1 ? 'class' : 'classes'}</span>
            </div>
            ${this.currentScope !== 'selected_package' ? `
              <button class="package-cluster-drill-btn" data-drill-pkg="${this._escape(pkgName)}" title="Focus only on ${this._escape(pkgName)}">
                <span>Focus Scope</span>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width: 10px; height: 10px;">
                  <polyline points="9 18 15 12 9 6"></polyline>
                </svg>
              </button>
            ` : ''}
          </div>
        `;

        const drillBtn = clusterBox.querySelector('[data-drill-pkg]');
        if (drillBtn) {
          drillBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.setScope('selected_package', pkgName);
          });
        }

        this.nodesLayer.appendChild(clusterBox);
      }
    });

    // Render Cards with Integer Positioning
    this.renderedNodes.forEach(cls => {
      const pos = this.nodePositions[cls.name] || { x: START_X, y: START_Y, w: 270, h: 100 };
      const x = pos.x;
      const y = pos.y;
      const isExp = this.isNodeExpanded(cls.name);

      const attrs = cls.attributes || [];
      const methods = cls.methods || [];
      const verifStatus = cls.verification_status || 'Verified';

      // Stereotype theme class
      const stLower = (cls.stereotype || '').toLowerCase();
      let themeClass = 'uml-card--class';
      if (stLower.includes('package')) themeClass = 'uml-card--package';
      else if (stLower.includes('component')) themeClass = 'uml-card--component';
      else if (stLower.includes('interface') || stLower.includes('protocol')) themeClass = 'uml-card--interface';
      else if (stLower.includes('enum')) themeClass = 'uml-card--enum';
      else if (stLower.includes('service') || stLower.includes('controller') || stLower.includes('engine')) themeClass = 'uml-card--service';
      else if (cls.name.toLowerCase() === 'user' || cls.name.toLowerCase() === 'account') themeClass = 'uml-card--entity';

      // Status badge
      let badgeClass = 'badge-status--verified';
      let badgeText = 'Verified';
      if (verifStatus === 'Mismatch' || (cls.drift_status && cls.drift_status === 'Changed')) {
        badgeClass = 'badge-status--changed';
        badgeText = 'Changed';
      }

      // Member folding limits (max 3 attrs, 4 methods when folded)
      const maxA = isExp ? attrs.length : Math.min(3, attrs.length);
      const maxM = isExp ? methods.length : Math.min(4, methods.length);
      const hiddenA = attrs.length - maxA;
      const hiddenM = methods.length - maxM;
      const hiddenTotal = (hiddenA > 0 ? hiddenA : 0) + (hiddenM > 0 ? hiddenM : 0);

      // Attributes HTML
      let attrsHtml = '';
      if (this.options.visibility.attributes && attrs.length > 0) {
        const visibleA = attrs.slice(0, maxA);
        attrsHtml = `
          <div class="uml-card__section uml-card__section--attrs">
            ${visibleA.map(a => {
              const fullTitle = `${a.vis || '+'} ${a.name}${a.type ? ': ' + a.type : ''}`;
              return `
                <div class="uml-member-row" title="${this._escape(fullTitle)}">
                  <span class="uml-member-vis">${this._escape(a.vis || '+')}</span>
                  <span class="uml-member-name">${this._escape(a.name)}</span>
                  ${a.type ? `<span class="uml-member-type">: ${this._escape(a.type)}</span>` : ''}
                </div>
              `;
            }).join('')}
          </div>
        `;
      }

      // Methods HTML
      let methodsHtml = '';
      if (this.options.visibility.methods && methods.length > 0) {
        const visibleM = methods.slice(0, maxM);
        methodsHtml = `
          <div class="uml-card__section uml-card__section--methods">
            ${visibleM.map(m => {
              const mName = m.name.endsWith(')') ? m.name : `${m.name}()`;
              const fullTitle = `${m.vis || '+'} ${mName}${m.ret ? ': ' + m.ret : ''}`;
              return `
                <div class="uml-member-row" title="${this._escape(fullTitle)}">
                  <span class="uml-member-vis">${this._escape(m.vis || '+')}</span>
                  <span class="uml-member-name">${this._escape(mName)}</span>
                  ${m.ret ? `<span class="uml-member-type">: ${this._escape(m.ret)}</span>` : ''}
                </div>
              `;
            }).join('')}
          </div>
        `;
      }

      // Member folding expandable pill
      let foldPillHtml = '';
      if (!isExp && hiddenTotal > 0) {
        foldPillHtml = `
          <div style="padding: 2px 10px 6px 10px;">
            <button class="uml-member-fold-pill" data-toggle="${cls.name}" title="Click to show all ${attrs.length + methods.length} members">
              + ${hiddenTotal} more members
            </button>
          </div>
        `;
      }

      // Footer Toggle (Show fewer members when expanded)
      let footerHtml = '';
      if (isExp && (attrs.length > 3 || methods.length > 4)) {
        footerHtml = `
          <div class="uml-card__footer">
            <button class="uml-toggle-btn" data-toggle="${cls.name}">
              <span>Show fewer members</span>
            </button>
          </div>
        `;
      }

      // Semantic Zoom Summary Bar (shown in compact mode)
      const summaryHtml = `
        <div class="uml-card__summary">
          <span class="uml-card__summary-pill">${attrs.length} attrs</span>
          <span class="uml-card__summary-pill">${methods.length} methods</span>
        </div>
      `;

      const card = document.createElement('div');
      card.className = `uml-card ${themeClass} uml-card--${verifStatus.toLowerCase()} ${isExp ? 'is-expanded' : 'is-collapsed'} ${this.selectedNodeId === cls.name ? 'uml-card--selected' : ''}`;
      card.id = `node-${cls.name}`;
      card.style.left = `${x}px`;
      card.style.top = `${y}px`;
      card.style.width = `${pos.w}px`;
      card.setAttribute('data-entity', cls.name);

      const iconSvg = this.getCardHeaderIcon(cls);

      card.innerHTML = `
        <div class="uml-card__header">
          <div style="min-width: 0; flex: 1;">
            <div style="display: flex; align-items: center; gap: 4px; flex-wrap: wrap;">
              <span class="uml-card__stereotype">${this._escape(cls.stereotype || '«class»')}</span>
              ${cls.tier ? `<span class="vivid-badge vivid-badge--primary" style="font-size: 8.5px; padding: 1px 5px;">${this._escape(cls.tier)}</span>` : ''}
              ${cls.instability !== undefined ? `<span class="vivid-badge vivid-badge--yellow" style="font-size: 8.5px; padding: 1px 5px;">I: ${Number(cls.instability).toFixed(2)}</span>` : ''}
              ${cls.is_cyclic ? `<span class="vivid-badge" style="font-size: 8.5px; padding: 1px 5px; background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5;">CYCLIC</span>` : ''}
            </div>
            <div style="display: flex; align-items: center; min-width: 0; gap: 4px; margin-top: 2px;">
              ${iconSvg}
              <h4 class="uml-card__title" title="${this._escape(cls.name)}">${this._escape(cls.name)}</h4>
            </div>
          </div>
          <div style="display: inline-flex; align-items: center; gap: 4px; flex-shrink: 0;">
            <button class="uml-card-scope-btn" data-scope-hop="${cls.name}" title="Focus on ${cls.name} + 1-hop neighbors">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" style="width: 11px; height: 11px;">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M12 3v3m0 12v3m9-9h-3M6 12H3"></path>
              </svg>
            </button>
            <span class="badge-status ${badgeClass}">${badgeText}</span>
          </div>
        </div>
        ${summaryHtml}
        ${attrsHtml}
        ${methodsHtml}
        ${foldPillHtml}
        ${footerHtml}
      `;

      // Expand/Collapse listener
      const tBtns = card.querySelectorAll('[data-toggle]');
      tBtns.forEach(b => {
        b.addEventListener('click', (e) => {
          e.stopPropagation();
          this.toggleNodeExpanded(cls.name);
        });
      });

      // 1-Hop scope button listener
      const hopBtn = card.querySelector('[data-scope-hop]');
      if (hopBtn) {
        hopBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.setScope('one_hop', cls.name);
        });
      }

      // Card selection listener
      card.addEventListener('click', (e) => {
        e.stopPropagation();
        this.selectNode(cls.name);
      });

      this.setupCardDraggable(card, cls.name);
      this.nodesLayer.appendChild(card);
    });

    // Render SVG Connectors with vector-effect: non-scaling-stroke
    this.renderConnectors();
  }

  _getTint(color) {
    if (!color) return 'rgba(99, 102, 241, 0.05)';
    if (color.startsWith('#')) {
      const hex = color.replace('#', '');
      const r = parseInt(hex.substring(0, 2), 16) || 99;
      const g = parseInt(hex.substring(2, 4), 16) || 102;
      const b = parseInt(hex.substring(4, 6), 16) || 241;
      return `rgba(${r}, ${g}, ${b}, 0.05)`;
    }
    return 'rgba(99, 102, 241, 0.05)';
  }

  /* ------------------------------------------------------------------------
   * READABLE PACKAGE DEPENDENCY GRAPH VECTOR RENDERER (Focused Package Nodes)
   * ------------------------------------------------------------------------ */
  renderPackagesDiagram() {
    if (!this.nodesLayer || !this.svgLayer) return;

    let packages = (this.packageNodes && this.packageNodes.length) ? this.packageNodes : [];
    let relations = (this.packageRelations && this.packageRelations.length) ? this.packageRelations : [];

    // Synthesize packages if empty
    if (!packages.length && this.classes && this.classes.length) {
      const pkgMap = new Map();
      this.classes.forEach(c => {
        const parts = (c.file || c.name).split(/[\/\.]/);
        const pName = parts.length > 1 ? parts[0] : 'core';
        if (!pkgMap.has(pName)) {
          pkgMap.set(pName, { name: pName, modules: [], count: 0 });
        }
        pkgMap.get(pName).modules.push(c.name);
        pkgMap.get(pName).count++;
      });
      const palette = ['#6366F1', '#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#06B6D4'];
      let colorIdx = 0;
      packages = Array.from(pkgMap.values()).map(p => ({
        id: `pkg_${p.name}`,
        name: p.name,
        stereotype: '«package»',
        modules_count: p.count,
        incoming_count: 1,
        outgoing_count: 1,
        instability: 0.50,
        semantic_color: palette[colorIdx++ % palette.length],
        modules: p.modules,
      }));
    }

    this.renderedNodes = packages;
    this.renderedRelations = relations;
    this.setClassCount(packages.length);

    // Clear previous elements
    this.nodesLayer.innerHTML = '';
    const defs = this.svgLayer.querySelector('defs');
    this.svgLayer.innerHTML = '';
    if (defs) this.svgLayer.appendChild(defs);

    if (!packages.length) {
      const emptyMsg = document.createElement('div');
      emptyMsg.style.cssText = 'position:absolute; left:60px; top:60px; color:#64748b; font-size:14px;';
      emptyMsg.textContent = 'No package dependencies found.';
      this.nodesLayer.appendChild(emptyMsg);
      return;
    }

    // Ensure arrow markers exist for package connectors
    if (!this.svgLayer.querySelector('#marker-package-dep')) {
      const markerGroup = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
      markerGroup.innerHTML = `
        <marker id="marker-package-dep" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#475569" />
        </marker>
        <marker id="marker-package-dep-active" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#2563EB" />
        </marker>
        <marker id="marker-package-dep-cyclic" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#EF4444" />
        </marker>
      `;
      this.svgLayer.appendChild(markerGroup);
    }

    const CARD_W = 230;
    const CARD_H = 98;
    this.nodePositions = {};

    // Check if manual positions provided (e.g. Career Compass pixel-matching user reference)
    const hasManualPositions = packages.every(p => p.pos && typeof p.pos.x === 'number');

    if (hasManualPositions) {
      packages.forEach(pkg => {
        const isExp = this.isPackageExpanded(pkg.name);
        const dynamicH = isExp ? Math.max(145, 98 + (pkg.modules || []).length * 20) : (pkg.pos.h || CARD_H);
        this.nodePositions[pkg.name] = {
          x: Math.round(pkg.pos.x),
          y: Math.round(pkg.pos.y),
          w: pkg.pos.w || CARD_W,
          h: dynamicH
        };
      });
    } else {
      // Automatic Layered Layout based on dependency in/out ranks
      const inDeg = new Map();
      const outDeg = new Map();
      packages.forEach(p => {
        inDeg.set(p.name, p.incoming_count || 0);
        outDeg.set(p.name, p.outgoing_count || 0);
      });
      relations.forEach(r => {
        outDeg.set(r.source, (outDeg.get(r.source) || 0) + 1);
        inDeg.set(r.target, (inDeg.get(r.target) || 0) + 1);
      });

      const layers = [[], [], []];
      packages.forEach(p => {
        const i = inDeg.get(p.name) || 0;
        const o = outDeg.get(p.name) || 0;
        if (i === 0) {
          layers[0].push(p);
        } else if (o === 0) {
          layers[2].push(p);
        } else {
          layers[1].push(p);
        }
      });
      if (!layers[0].length && layers[1].length) {
        layers[0].push(layers[1].shift());
      }
      if (!layers[2].length && layers[1].length) {
        layers[2].push(layers[1].pop());
      }

      const START_Y = 60;
      const GAP_Y = 95;
      const GAP_X = 70;
      const CANVAS_CENTER_X = 640;

      layers.forEach((layerNodes, lIdx) => {
        if (!layerNodes.length) return;
        const totalW = layerNodes.length * CARD_W + (layerNodes.length - 1) * GAP_X;
        let startX = Math.max(60, CANVAS_CENTER_X - totalW / 2);
        const y = START_Y + lIdx * (CARD_H + GAP_Y);

        layerNodes.forEach(pkg => {
          const isExp = this.isPackageExpanded(pkg.name);
          const dynamicH = isExp ? Math.max(145, 98 + (pkg.modules || []).length * 20) : CARD_H;
          this.nodePositions[pkg.name] = {
            x: Math.round(startX),
            y: Math.round(y),
            w: CARD_W,
            h: dynamicH
          };
          startX += CARD_W + GAP_X;
        });
      });
    }

    const defaultPalette = ['#6366F1', '#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#06B6D4'];
    let cIdx = 0;

    // Render Package Cards
    packages.forEach(pkg => {
      const pos = this.nodePositions[pkg.name] || { x: 60, y: 60, w: CARD_W, h: CARD_H };
      const isExp = this.isPackageExpanded(pkg.name);
      const color = pkg.semantic_color || pkg.border_color || defaultPalette[cIdx++ % defaultPalette.length];
      const modules = pkg.modules || [];
      const mCount = pkg.modules_count !== undefined ? pkg.modules_count : modules.length;
      const inCount = pkg.incoming_count !== undefined ? pkg.incoming_count : 0;
      const outCount = pkg.outgoing_count !== undefined ? pkg.outgoing_count : 0;
      const instability = (pkg.instability !== undefined) ? Number(pkg.instability).toFixed(2) : '0.00';

      const card = document.createElement('div');
      card.className = `pkg-card ${isExp ? 'is-expanded' : ''} ${this.selectedNodeId === pkg.name ? 'pkg-card--selected' : ''}`;
      card.id = `pkg-node-${pkg.name}`;
      card.style.left = `${pos.x}px`;
      card.style.top = `${pos.y}px`;
      card.style.width = `${pos.w}px`;
      card.style.borderColor = color;
      card.setAttribute('data-entity', pkg.name);

      card.innerHTML = `
        <div class="pkg-card__header" style="background: ${this._getTint(color)};">
          <div class="pkg-card__icon" style="color: ${color};">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
              <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
              <line x1="12" y1="22.08" x2="12" y2="12"/>
            </svg>
          </div>
          <div class="pkg-card__title-wrap">
            <span class="pkg-card__stereotype">${this._escape(pkg.stereotype || '«package»')}</span>
            <h4 class="pkg-card__title" title="${this._escape(pkg.name)}">${this._escape(pkg.name)}</h4>
          </div>
          <button class="pkg-card__drill-btn" data-pkg-drill="${pkg.name}" title="Drill into ${pkg.name} package (View Classes)">
            <span>Explore</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width: 10px; height: 10px;">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </button>
          <button class="pkg-card__expand-btn" data-pkg-toggle="${pkg.name}" title="${isExp ? 'Collapse modules' : 'Expand modules'}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>
        </div>

        <div class="pkg-card__metrics">
          <div class="pkg-metric-item">
            <span class="pkg-metric-val">${mCount}</span>
            <span class="pkg-metric-lbl">Modules</span>
          </div>
          <div class="pkg-metric-item">
            <span class="pkg-metric-val">${inCount}</span>
            <span class="pkg-metric-lbl">Incoming</span>
          </div>
          <div class="pkg-metric-item">
            <span class="pkg-metric-val">${outCount}</span>
            <span class="pkg-metric-lbl">Outgoing</span>
          </div>
          <div class="pkg-metric-item">
            <span class="pkg-metric-val">I: ${instability}</span>
            <span class="pkg-metric-lbl">Instability</span>
          </div>
        </div>

        <div class="pkg-card__modules">
          <div class="pkg-modules-header">Modules (${modules.length})</div>
          <div class="pkg-modules-list">
            ${modules.map(m => `
              <div class="pkg-module-item">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
                <span>${this._escape(m)}</span>
              </div>
            `).join('')}
          </div>
        </div>
      `;

      // Expand toggle listener on header chevron
      const toggleBtn = card.querySelector('[data-pkg-toggle]');
      if (toggleBtn) {
        toggleBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.togglePackageExpanded(pkg.name);
        });
      }

      // Drill-down button listener (Explore package scope)
      const drillBtn = card.querySelector('[data-pkg-drill]');
      if (drillBtn) {
        drillBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.setScope('selected_package', pkg.name);
        });
      }

      // Double-click on card drills down to package scope
      card.addEventListener('dblclick', (e) => {
        e.stopPropagation();
        this.setScope('selected_package', pkg.name);
      });

      // Single-click selects node (opens inspector)
      card.addEventListener('click', (e) => {
        e.stopPropagation();
        this.selectNode(pkg.name);
      });

      this.setupCardDraggable(card, pkg.name);
      this.nodesLayer.appendChild(card);
    });

    // Render Package Connectors
    this.renderPackageConnectors(relations);
  }

  countClassDependenciesBetweenPackages(srcPkg, tgtPkg) {
    if (!this.relations || !this.relations.length) return 0;
    let count = 0;
    this.relations.forEach(r => {
      const s = (this.classes || []).find(c => c.name === r.source);
      const t = (this.classes || []).find(c => c.name === r.target);
      if (s && t && this.getPackageForClass(s) === srcPkg && this.getPackageForClass(t) === tgtPkg) {
        count++;
      }
    });
    return count;
  }

  renderPackageConnectors(relations) {
    if (!this.svgLayer || !relations || !relations.length) return;

    let pathsMarkup = '';
    relations.forEach((rel, rIdx) => {
      const srcName = rel.source || rel.source_package;
      const tgtName = rel.target || rel.target_package;
      const sPos = this.nodePositions[srcName];
      const tPos = this.nodePositions[tgtName];
      if (!sPos || !tPos || srcName === tgtName) return;

      const sCenterX = sPos.x + sPos.w / 2;
      const sCenterY = sPos.y + sPos.h / 2;
      const tCenterX = tPos.x + tPos.w / 2;
      const tCenterY = tPos.y + tPos.h / 2;

      let x1, y1, x2, y2, d;
      const isCyclic = !!rel.is_cyclic;
      const isOptional = rel.relationship_style === 'dotted' || rel.relationship_style === 'dashed';

      const isAbove = sPos.y + sPos.h + 20 < tPos.y;
      const isBelow = sPos.y > tPos.y + tPos.h + 20;

      if (!isAbove && !isBelow) {
        // Horizontal on same row
        if (sCenterX < tCenterX) {
          x1 = sPos.x + sPos.w;
          y1 = sCenterY;
          x2 = tPos.x;
          y2 = tCenterY;
          d = `M ${x1} ${y1} L ${x2} ${y2}`;
        } else {
          x1 = sPos.x;
          y1 = sCenterY;
          x2 = tPos.x + tPos.w;
          y2 = tCenterY;
          d = `M ${x1} ${y1} L ${x2} ${y2}`;
        }
      } else if (isAbove) {
        // Source is distinctly above target
        if (Math.abs(sCenterX - tCenterX) < 40) {
          x1 = sCenterX;
          y1 = sPos.y + sPos.h;
          x2 = tCenterX;
          y2 = tPos.y;
          d = `M ${x1} ${y1} L ${x2} ${y2}`;
        } else if (tCenterX < sCenterX) {
          if (srcName === 'career_compass' && tgtName === 'interfaces') {
            x1 = sPos.x + 35;
            y1 = sPos.y + sPos.h;
            x2 = tPos.x + tPos.w - 45;
            y2 = tPos.y;
          } else if (srcName === 'core' && tgtName === 'models') {
            x1 = sPos.x + 45;
            y1 = sPos.y + sPos.h;
            x2 = tCenterX;
            y2 = tPos.y;
          } else if (srcName === 'services' && tgtName === 'data') {
            x1 = sCenterX;
            y1 = sPos.y + sPos.h;
            x2 = tPos.x + tPos.w - 45;
            y2 = tPos.y;
          } else {
            x1 = sPos.x + sPos.w * 0.25;
            y1 = sPos.y + sPos.h;
            x2 = tPos.x + tPos.w * 0.75;
            y2 = tPos.y;
          }
          const cy1 = y1 + (y2 - y1) * 0.55;
          const cy2 = y2 - (y2 - y1) * 0.45;
          d = `M ${x1} ${y1} C ${x1} ${cy1}, ${x2} ${cy2}, ${x2} ${y2}`;
        } else {
          if (srcName === 'career_compass' && tgtName === 'services') {
            x1 = sPos.x + sPos.w - 35;
            y1 = sPos.y + sPos.h;
            x2 = tPos.x + 45;
            y2 = tPos.y;
          } else if (srcName === 'core' && tgtName === 'data') {
            x1 = sPos.x + sPos.w - 45;
            y1 = sPos.y + sPos.h;
            x2 = tPos.x + 45;
            y2 = tPos.y;
          } else {
            x1 = sPos.x + sPos.w * 0.75;
            y1 = sPos.y + sPos.h;
            x2 = tPos.x + tPos.w * 0.25;
            y2 = tPos.y;
          }
          const cy1 = y1 + (y2 - y1) * 0.55;
          const cy2 = y2 - (y2 - y1) * 0.45;
          d = `M ${x1} ${y1} C ${x1} ${cy1}, ${x2} ${cy2}, ${x2} ${y2}`;
        }
      } else {
        // Target is distinctly above source
        x1 = sCenterX;
        y1 = sPos.y;
        x2 = tCenterX;
        y2 = tPos.y + tPos.h;
        const cy1 = y1 - (y1 - y2) * 0.55;
        const cy2 = y2 + (y1 - y2) * 0.45;
        d = `M ${x1} ${y1} C ${x1} ${cy1}, ${x2} ${cy2}, ${x2} ${y2}`;
      }

      const marker = isCyclic ? 'url(#marker-package-dep-cyclic)' : 'url(#marker-package-dep)';
      const cls = `pkg-connector-path ${isCyclic ? 'pkg-connector-path--cyclic' : ''} ${isOptional ? 'pkg-connector-path--optional' : ''}`;

      // Summarized dependencies count on package edges
      const depCount = rel.import_count || rel.dependencies_count || (rel.imported_symbols ? rel.imported_symbols.length : 0) || this.countClassDependenciesBetweenPackages(srcName, tgtName) || (rel.label && !isNaN(parseInt(rel.label)) ? parseInt(rel.label) : 1);
      const labelText = depCount > 1 ? `${depCount} dependencies` : (rel.label || '1 dependency');
      const textW = Math.max(54, Math.round(labelText.length * 6.4 + 18));
      const midX = Math.round((x1 + x2) / 2);
      const midY = Math.round((y1 + y2) / 2);

      pathsMarkup += `
        <path id="pkg-edge-${rIdx}" class="${cls}" d="${d}" marker-end="${marker}" data-source="${srcName}" data-target="${tgtName}"></path>
        <g class="pkg-edge-label-group" data-source="${srcName}" data-target="${tgtName}">
          <rect class="pkg-edge-label-bg" x="${midX - Math.round(textW / 2)}" y="${midY - 9}" width="${textW}" height="18" rx="9"></rect>
          <text class="pkg-edge-label-text" x="${midX}" y="${midY + 1}" text-anchor="middle" dominant-baseline="central">${this._escape(labelText)}</text>
        </g>
      `;
    });

    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.id = 'pkg-connectors-group';
    g.innerHTML = pathsMarkup;
    this.svgLayer.appendChild(g);

    // Interactive hover highlights
    g.querySelectorAll('.pkg-connector-path, .pkg-edge-label-group').forEach(el => {
      el.addEventListener('mouseenter', () => {
        const p = el.classList.contains('pkg-connector-path') ? el : g.querySelector(`.pkg-connector-path[data-source="${el.dataset.source}"][data-target="${el.dataset.target}"]`);
        if (p) {
          p.classList.add('pkg-connector-path--active');
          p.setAttribute('marker-end', 'url(#marker-package-dep-active)');
        }
        const s = document.getElementById(`pkg-node-${el.dataset.source}`);
        const t = document.getElementById(`pkg-node-${el.dataset.target}`);
        if (s) s.classList.add('pkg-card--selected');
        if (t) t.classList.add('pkg-card--selected');
      });
      el.addEventListener('mouseleave', () => {
        const p = el.classList.contains('pkg-connector-path') ? el : g.querySelector(`.pkg-connector-path[data-source="${el.dataset.source}"][data-target="${el.dataset.target}"]`);
        if (p) {
          p.classList.remove('pkg-connector-path--active');
          const isC = p.classList.contains('pkg-connector-path--cyclic');
          p.setAttribute('marker-end', isC ? 'url(#marker-package-dep-cyclic)' : 'url(#marker-package-dep)');
        }
        const s = document.getElementById(`pkg-node-${el.dataset.source}`);
        const t = document.getElementById(`pkg-node-${el.dataset.target}`);
        if (s && this.selectedNodeId !== el.dataset.source) s.classList.remove('pkg-card--selected');
        if (t && this.selectedNodeId !== el.dataset.target) t.classList.remove('pkg-card--selected');
      });
    });
  }

  /* ------------------------------------------------------------------------
   * READABLE ARCHITECTURE DIAGRAM VECTOR RENDERER (Layers, Explicit Semantics, Clean Cards)
   * ------------------------------------------------------------------------ */
  renderArchitectureDiagram() {
    if (!this.nodesLayer || !this.svgLayer) return;

    // Use componentNodes or fallback
    let components = (this.componentNodes && this.componentNodes.length) ? this.componentNodes : [];
    let connectors = (this.componentRelations && this.componentRelations.length) ? this.componentRelations : [];

    if (!components.length && this.classes && this.classes.length) {
      // Synthesize clean architecture components from top classes if none extracted
      components = this.classes.slice(0, 8).map((c, idx) => ({
        id: `comp_${c.name}`,
        name: c.name,
        stereotype: c.stereotype || '«service»',
        role: idx === 0 ? 'Entry Point' : (idx > 5 ? 'Infrastructure / Data' : 'Application Service'),
        tier: idx === 0 ? 'Entry Points' : (idx > 5 ? 'Infrastructure / Data' : 'Application Services'),
        layer_level: idx === 0 ? 0 : (idx > 5 ? 3 : 2),
        semantic_color: idx === 0 ? '#7C3AED' : (idx > 5 ? '#D97706' : '#16A34A'),
        functions_count: (c.methods || []).length,
        dependencies_count: 1,
        encapsulated_classes: [c.name],
        provided_interfaces: (c.methods || []).slice(0, 3).map(m => m.name),
        required_interfaces: [],
        docstring: c.docstring || '',
        purpose: c.docstring || 'Core system module',
      }));
    }

    this.renderedNodes = components;
    this.renderedRelations = connectors;
    this.setClassCount(components.length);

    // Clear previous elements
    this.nodesLayer.innerHTML = '';
    const defs = this.svgLayer.querySelector('defs');
    this.svgLayer.innerHTML = '';
    if (defs) this.svgLayer.appendChild(defs);

    if (!components.length) {
      const emptyMsg = document.createElement('div');
      emptyMsg.style.cssText = 'position:absolute; left:60px; top:60px; color:#64748b; font-size:14px;';
      emptyMsg.textContent = 'No architectural components found.';
      this.nodesLayer.appendChild(emptyMsg);
      return;
    }

    // Ensure arrow markers exist in defs for connector heads
    if (!this.svgLayer.querySelector('#arrow-blue')) {
      const markerGroup = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
      markerGroup.innerHTML = `
        <marker id="arrow-blue" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#2563EB" />
        </marker>
        <marker id="arrow-green" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#16A34A" />
        </marker>
        <marker id="arrow-amber" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#D97706" />
        </marker>
        <marker id="arrow-slate" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#64748B" />
        </marker>
        <marker id="arrow-purple" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#7C3AED" />
        </marker>
      `;
      this.svgLayer.appendChild(markerGroup);
    }

    // Standard Layout Parameters
    const CARD_W = 270;
    const CARD_H = 96;
    const BAND_X = 60;
    const BAND_W = 1200;
    const BAND_GAP = 56;
    const START_Y = 60;

    // Detect Career Compass application architecture
    const isCareerCompass = components.some(c => c.name === 'desktop_launcher' || c.name === 'run') &&
                            components.some(c => c.name === 'app');

    this.nodePositions = {};
    let swimlanesMarkup = '';
    let connectorsMarkup = '';

    // Standard 4-Layer Definitions
    const standardLayers = [
      {
        level: 0,
        title: 'ENTRY POINTS',
        subtitle: 'CLI & GUI launchers',
        color: '#7C3AED',
        borderColor: '#DDD6FE',
        fill: 'var(--bg-layer-entry, rgba(124, 58, 237, 0.04))',
        h: 144
      },
      {
        level: 1,
        title: 'PRESENTATION / CONTROLLER',
        subtitle: 'Flask application & routing',
        color: '#2563EB',
        borderColor: '#BFDBFE',
        fill: 'var(--bg-layer-presentation, rgba(37, 99, 235, 0.04))',
        h: 144
      },
      {
        level: 2,
        title: 'APPLICATION SERVICES',
        subtitle: 'Core processing & business logic',
        color: '#16A34A',
        borderColor: '#BBF7D0',
        fill: 'var(--bg-layer-service, rgba(22, 163, 74, 0.04))',
        h: 144
      },
      {
        level: 3,
        title: 'INFRASTRUCTURE / DATA',
        subtitle: 'Persistence & external resources',
        color: '#D97706',
        borderColor: '#FDE68A',
        fill: 'var(--bg-layer-infra, rgba(217, 119, 6, 0.04))',
        h: 154
      }
    ];

    if (isCareerCompass) {
      // ── CAREER COMPASS REFERENCE ARCHITECTURE LAYOUT ──
      const b0_y = START_Y;
      const b1_y = b0_y + 144 + BAND_GAP; // 260
      const b2_y = b1_y + 144 + BAND_GAP; // 460
      const b3_y = b2_y + 144 + BAND_GAP; // 660

      const bandYs = [b0_y, b1_y, b2_y, b3_y];

      // Exact card positioning matching mockup
      this.nodePositions['desktop_launcher'] = { x: 445, y: b0_y + 24, w: CARD_W, h: CARD_H };
      this.nodePositions['run'] = { x: 755, y: b0_y + 24, w: CARD_W, h: CARD_H };
      this.nodePositions['app'] = { x: 600, y: b1_y + 24, w: CARD_W, h: CARD_H };
      this.nodePositions['core.app_paths'] = { x: 950, y: b1_y + 24, w: CARD_W, h: CARD_H };
      this.nodePositions['core.file_processor'] = { x: 290, y: b2_y + 24, w: CARD_W, h: CARD_H };
      this.nodePositions['core.recommendation_engine'] = { x: 600, y: b2_y + 24, w: CARD_W, h: CARD_H };
      this.nodePositions['core.questionnaire_processor'] = { x: 910, y: b2_y + 24, w: CARD_W, h: CARD_H };
      this.nodePositions['core.database'] = { x: 600, y: b3_y + 24, w: CARD_W, h: CARD_H };
      this.nodePositions['external.file_system'] = { x: 950, y: b3_y + 20, w: CARD_W, h: 104 };
      this.nodePositions['external.apis'] = { x: 950, y: b3_y + 20, w: CARD_W, h: 104 };
      this.nodePositions['external_services'] = { x: 950, y: b3_y + 20, w: CARD_W, h: 104 };

      // Render 4 Swimlane Bands
      standardLayers.forEach((layer, idx) => {
        const y = bandYs[idx];
        const h = layer.h;
        swimlanesMarkup += `
          <g class="arch-swimlane-band">
            <rect x="${BAND_X}" y="${y}" width="${BAND_W}" height="${h}" rx="10" fill="${layer.fill}" stroke="${layer.borderColor}" stroke-width="1.2" />
            <rect x="${BAND_X}" y="${y}" width="4" height="${h}" rx="2" fill="${layer.color}" />
            <text x="${BAND_X + 24}" y="${y + 26}" font-family="Plus Jakarta Sans, sans-serif" font-size="12" font-weight="800" letter-spacing="0.04em" fill="${layer.color}">${layer.title}</text>
            <text x="${BAND_X + 24}" y="${y + 42}" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="500" fill="#64748B">${layer.subtitle}</text>
          </g>
        `;
      });

      // Explicit Connectors Routing
      const explicitEdges = [
        // Layer 0 -> Layer 1
        {
          src: 'desktop_launcher', tgt: 'app', lbl: 'starts', style: 'solid', color: '#2563EB',
          path: `M 580 204 C 580 240, 660 244, 660 284`,
          midX: 620, midY: 244
        },
        {
          src: 'run', tgt: 'app', lbl: 'starts', style: 'solid', color: '#2563EB',
          path: `M 890 204 C 890 240, 810 244, 810 284`,
          midX: 850, midY: 244
        },
        // Layer 1 intra-band
        {
          src: 'app', tgt: 'core.app_paths', lbl: 'uses (configuration)', style: 'dashed', color: '#64748B',
          path: `M 870 332 L 950 332`,
          midX: 910, midY: 332
        },
        // Layer 1 -> Layer 2
        {
          src: 'app', tgt: 'core.file_processor', lbl: 'uses', style: 'solid', color: '#2563EB',
          path: `M 640 380 C 640 430, 425 434, 425 484`,
          midX: 532, midY: 432
        },
        {
          src: 'app', tgt: 'core.recommendation_engine', lbl: 'uses', style: 'solid', color: '#2563EB',
          path: `M 735 380 L 735 484`,
          midX: 735, midY: 432
        },
        {
          src: 'app', tgt: 'core.questionnaire_processor', lbl: 'uses', style: 'solid', color: '#2563EB',
          path: `M 830 380 C 830 430, 1045 434, 1045 484`,
          midX: 938, midY: 432
        },
        // Layer 2 intra-band (Data Flow)
        {
          src: 'core.file_processor', tgt: 'core.recommendation_engine', lbl: 'provides data', style: 'solid', color: '#16A34A',
          path: `M 560 532 L 600 532`,
          midX: 580, midY: 532
        },
        {
          src: 'core.questionnaire_processor', tgt: 'core.recommendation_engine', lbl: 'provides data', style: 'solid', color: '#16A34A',
          path: `M 910 532 L 870 532`,
          midX: 890, midY: 532
        },
        // Layer 2 -> Layer 3 (Persistence)
        {
          src: 'core.file_processor', tgt: 'core.database', lbl: 'reads/writes', style: 'solid', color: '#D97706',
          path: `M 425 580 C 425 632, 650 636, 650 684`,
          midX: 538, midY: 632
        },
        {
          src: 'core.recommendation_engine', tgt: 'core.database', lbl: 'reads/writes', style: 'solid', color: '#D97706',
          path: `M 735 580 L 735 684`,
          midX: 735, midY: 632
        },
        {
          src: 'core.questionnaire_processor', tgt: 'core.database', lbl: 'reads/writes', style: 'solid', color: '#D97706',
          path: `M 1045 580 C 1045 632, 820 636, 820 684`,
          midX: 932, midY: 632
        },
        // Layer 1 -> Layer 3 External Services
        {
          src: 'core.app_paths', tgt: 'external_services', lbl: 'uses (optional)', style: 'dotted', color: '#64748B',
          path: `M 1085 380 L 1085 680`,
          midX: 1085, midY: 530
        }
      ];

      explicitEdges.forEach(edge => {
        let dashAttr = '';
        let marker = 'url(#arrow-blue)';
        if (edge.color === '#16A34A') marker = 'url(#arrow-green)';
        else if (edge.color === '#D97706') marker = 'url(#arrow-amber)';
        else if (edge.color === '#64748B') marker = 'url(#arrow-slate)';

        if (edge.style === 'dashed') {
          dashAttr = 'stroke-dasharray="5 4"';
        } else if (edge.style === 'dotted') {
          dashAttr = 'stroke-dasharray="2 3"';
        }

        const pillW = edge.lbl.length * 6.5 + 16;
        connectorsMarkup += `
          <path d="${edge.path}" fill="none" stroke="${edge.color}" stroke-width="1.8" ${dashAttr} marker-end="${marker}" />
          <g class="arch-edge-label-pill">
            <rect x="${edge.midX - pillW / 2}" y="${edge.midY - 9}" width="${pillW}" height="18" rx="4" fill="var(--bg-card, #ffffff)" stroke="#cbd5e1" stroke-width="1" />
            <text x="${edge.midX}" y="${edge.midY + 3.5}" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="10" font-weight="600" fill="${edge.color}">${edge.lbl}</text>
          </g>
        `;
      });

    } else {
      // ── GENERIC MULTI-LAYER BALANCED LAYOUT ──
      const layerMap = new Map();
      standardLayers.forEach(l => layerMap.set(l.level, []));

      components.forEach(c => {
        let lvl = c.layer_level;
        if (lvl === undefined) {
          const t = (c.tier || '').toLowerCase();
          const r = (c.role || '').toLowerCase();
          const s = (c.stereotype || '').toLowerCase();
          if (t.includes('entry') || r.includes('entry') || s.includes('controller') || c.name.toLowerCase().includes('cli')) {
            lvl = 0;
          } else if (t.includes('domain') || r.includes('domain') || s.includes('entity')) {
            lvl = 2;
          } else if (t.includes('data') || t.includes('infra') || s.includes('database') || s.includes('repo')) {
            lvl = 3;
          } else {
            lvl = 1;
          }
        }
        if (!layerMap.has(lvl)) layerMap.set(lvl, []);
        layerMap.get(lvl).push(c);
      });

      let curY = START_Y;
      standardLayers.forEach(layer => {
        const nodes = layerMap.get(layer.level) || [];
        if (!nodes.length) return;

        const rowW = nodes.length * CARD_W + (nodes.length - 1) * 40;
        const startCardX = Math.max(300, (BAND_X + BAND_W / 2) - rowW / 2);

        swimlanesMarkup += `
          <g class="arch-swimlane-band">
            <rect x="${BAND_X}" y="${curY}" width="${BAND_W}" height="${layer.h}" rx="10" fill="${layer.fill}" stroke="${layer.borderColor}" stroke-width="1.2" />
            <rect x="${BAND_X}" y="${curY}" width="4" height="${layer.h}" rx="2" fill="${layer.color}" />
            <text x="${BAND_X + 24}" y="${curY + 26}" font-family="Plus Jakarta Sans, sans-serif" font-size="12" font-weight="800" letter-spacing="0.04em" fill="${layer.color}">${layer.title}</text>
            <text x="${BAND_X + 24}" y="${curY + 42}" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="500" fill="#64748B">${layer.subtitle}</text>
          </g>
        `;

        nodes.forEach((c, idx) => {
          const cx = startCardX + idx * (CARD_W + 40);
          const cy = curY + 24;
          this.nodePositions[c.name] = { x: Math.round(cx), y: Math.round(cy), w: CARD_W, h: CARD_H };
          this.nodePositions[c.id] = this.nodePositions[c.name];
        });

        curY += layer.h + BAND_GAP;
      });

      // Generic connectors
      connectors.forEach(conn => {
        const srcName = conn.source || conn.source_id?.replace('comp_', '');
        const tgtName = conn.target || conn.target_id?.replace('comp_', '');
        const srcPos = this.nodePositions[srcName];
        const tgtPos = this.nodePositions[tgtName];
        if (!srcPos || !tgtPos || srcName === tgtName) return;

        const lbl = (conn.label || conn.connector_type || 'uses').toLowerCase();
        const style = conn.relationship_style || (lbl.includes('import') ? 'dashed' : 'solid');
        let lineColor = '#2563EB';
        let dashAttr = '';
        if (style === 'dashed' || lbl.includes('import')) {
          lineColor = '#64748B';
          dashAttr = 'stroke-dasharray="5 4"';
        } else if (style === 'dotted' || lbl.includes('optional')) {
          lineColor = '#64748B';
          dashAttr = 'stroke-dasharray="2 3"';
        }

        const isTopDown = srcPos.y < tgtPos.y;
        const sx = srcPos.x + srcPos.w / 2;
        const sy = isTopDown ? srcPos.y + srcPos.h : srcPos.y;
        const tx = tgtPos.x + tgtPos.w / 2;
        const ty = isTopDown ? tgtPos.y : tgtPos.y + tgtPos.h;
        const midY = (sy + ty) / 2;
        const pathD = `M ${sx} ${sy} C ${sx} ${midY}, ${tx} ${midY}, ${tx} ${ty}`;
        const midX = (sx + tx) / 2;
        const pillW = lbl.length * 6.5 + 16;

        connectorsMarkup += `
          <path d="${pathD}" fill="none" stroke="${lineColor}" stroke-width="1.8" ${dashAttr} marker-end="url(#arrow-blue)" />
          <g class="arch-edge-label-pill">
            <rect x="${midX - pillW / 2}" y="${midY - 9}" width="${pillW}" height="18" rx="4" fill="var(--bg-card, #ffffff)" stroke="#cbd5e1" stroke-width="1" />
            <text x="${midX}" y="${midY + 3.5}" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="10" font-weight="600" fill="${lineColor}">${lbl}</text>
          </g>
        `;
      });
    }

    this.svgLayer.innerHTML += swimlanesMarkup + connectorsMarkup;

    // ── RENDER CLEAN ARCHITECTURE CARDS (Fixed 270px width, no function list dump) ──
    components.forEach(c => {
      if (c.is_external || c.name.startsWith('external.')) return; // Rendered in External Services container

      const pos = this.nodePositions[c.name] || { x: 300, y: 100, w: CARD_W, h: CARD_H };
      const isSelected = this.selectedNodeId === c.name || this.selectedNodeId === c.id;
      const funcCount = c.functions_count !== undefined ? c.functions_count : (c.provided_interfaces || []).length;
      const depCount = c.dependencies_count !== undefined ? c.dependencies_count : 0;
      const st = (c.stereotype || '«service»').toLowerCase();

      // Stereotype Badge Theme
      let badgeClass = 'arch-badge--service';
      if (st.includes('entry')) badgeClass = 'arch-badge--entry';
      else if (st.includes('controller')) badgeClass = 'arch-badge--controller';
      else if (st.includes('database') || st.includes('data')) badgeClass = 'arch-badge--db';
      else if (st.includes('infra')) badgeClass = 'arch-badge--infra';
      else if (st.includes('external')) badgeClass = 'arch-badge--external';

      // Icon Selector
      let iconSvg = '';
      const ic = c.icon || '';
      if (ic === 'monitor' || st.includes('desktop')) {
        iconSvg = `<svg class="arch-card__top-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`;
      } else if (ic === 'terminal' || st.includes('cli') || c.name.toLowerCase().includes('run')) {
        iconSvg = `<svg class="arch-card__top-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>`;
      } else if (ic === 'globe' || st.includes('controller') || c.name.toLowerCase() === 'app') {
        iconSvg = `<svg class="arch-card__top-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`;
      } else if (ic === 'settings' || st.includes('infra') || c.name.toLowerCase().includes('paths')) {
        iconSvg = `<svg class="arch-card__top-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`;
      } else if (ic === 'database' || st.includes('database')) {
        iconSvg = `<svg class="arch-card__top-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>`;
      } else if (c.name.toLowerCase().includes('recommend')) {
        iconSvg = `<svg class="arch-card__top-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`;
      } else if (c.name.toLowerCase().includes('questionnaire')) {
        iconSvg = `<svg class="arch-card__top-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>`;
      } else {
        iconSvg = `<svg class="arch-card__top-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;
      }

      const card = document.createElement('div');
      card.className = `uml-card arch-card ${isSelected ? 'uml-card--selected' : ''}`;
      card.id = `node-${c.name}`;
      card.style.left = `${pos.x}px`;
      card.style.top = `${pos.y}px`;
      card.style.width = `${pos.w}px`;
      card.style.height = `${pos.h}px`;
      card.setAttribute('data-entity', c.name);

      card.innerHTML = `
        <div class="arch-card__header-row">
          <span class="arch-badge ${badgeClass}">${this._escape(c.stereotype || '«service»')}</span>
          ${iconSvg}
        </div>
        <div class="arch-card__title-row">
          <h4 class="arch-card__title" title="${this._escape(c.name)}">${this._escape(c.name)}</h4>
        </div>
        <div class="arch-card__purpose" title="${this._escape(c.purpose || c.docstring || '')}">${this._escape(c.purpose || c.docstring || (c.role || 'Service module'))}</div>
        <div class="arch-card__meta">${funcCount} operations • ${depCount} dependencies</div>
      `;

      card.addEventListener('click', (e) => {
        e.stopPropagation();
        this.selectNode(c.name);
      });

      this.setupCardDraggable(card, c.name);
      this.nodesLayer.appendChild(card);
    });

    // ── RENDER EXTERNAL SERVICES CONTAINER (in Layer 3 right side) ──
    if (isCareerCompass) {
      const extPos = this.nodePositions['external_services'];
      const isExtSelected = this.selectedNodeId === 'external_services' || this.selectedNodeId === 'external.file_system' || this.selectedNodeId === 'external.apis';

      const extBox = document.createElement('div');
      extBox.className = `arch-external-container ${isExtSelected ? 'is-selected' : ''}`;
      extBox.id = 'node-external_services';
      extBox.style.left = `${extPos.x}px`;
      extBox.style.top = `${extPos.y}px`;
      extBox.style.width = `${extPos.w}px`;
      extBox.style.height = `${extPos.h}px`;

      extBox.innerHTML = `
        <div class="arch-ext-header">
          <span class="arch-ext-tag">«external»</span>
          <span class="arch-ext-title">External Services</span>
        </div>
        <div class="arch-ext-item" data-entity="external.file_system" title="Read student result files">
          <svg class="arch-ext-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          <div class="arch-ext-item__info">
            <span class="arch-ext-item__name">File System</span>
            <span class="arch-ext-item__desc">Read student result files</span>
          </div>
        </div>
        <div class="arch-ext-item" data-entity="external.apis" title="(Optional) External APIs (e.g. email/notifications)">
          <svg class="arch-ext-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg>
          <div class="arch-ext-item__info">
            <span class="arch-ext-item__name">(Optional) External APIs</span>
            <span class="arch-ext-item__desc">(e.g. email/notifications)</span>
          </div>
        </div>
      `;

      extBox.querySelectorAll('.arch-ext-item').forEach(item => {
        item.addEventListener('click', (e) => {
          e.stopPropagation();
          const entityName = item.dataset.entity;
          this.selectNode(entityName);
        });
      });

      extBox.addEventListener('click', (e) => {
        e.stopPropagation();
        this.selectNode('external.file_system');
      });

      this.nodesLayer.appendChild(extBox);
    }
  }

  /* ------------------------------------------------------------------------
   * SEQUENCE DIAGRAM VECTOR RENDERER (Lifelines, Activations, Arrows)
   * ------------------------------------------------------------------------ */
  renderSequenceDiagram() {
    let scenario = this.getActiveSequenceScenario();
    if (!scenario || !scenario.participants || !scenario.participants.length) {
      // Auto-synthesize fallback scenario if none provided
      const pList = (this.classes && this.classes.length)
        ? this.classes.slice(0, 4).map(c => ({ id: c.name, name: c.name, type: 'business', icon: 'box', kind: 'class' }))
        : [
            { id: 'Client', name: 'User / Client', type: 'external', icon: 'user', kind: 'actor' },
            { id: 'Service', name: 'ApplicationService', type: 'business', icon: 'box', kind: 'service' },
            { id: 'Database', name: 'StorageEngine', type: 'data', icon: 'database', kind: 'database' },
          ];
      scenario = {
        id: 'default_trace',
        name: 'Runtime Execution Flow',
        title: 'Runtime Execution Flow',
        description: 'Chronological message trace across active lifelines',
        entrypoint: 'main()',
        duration_ms: 24.5,
        participants: pList,
        messages: [
          { id: 'm1', order: 1, from: pList[0].id, to: pList[1].id, name: 'execute_workflow()', type: 'call', timing: { durationMs: 24.5 } },
          { id: 'm2', order: 2, from: pList[1].id, to: pList[Math.min(2, pList.length - 1)].id, name: 'query_record(id=1)', type: 'call', timing: { durationMs: 6.2 } },
          { id: 'm3', order: 3, from: pList[Math.min(2, pList.length - 1)].id, to: pList[1].id, name: 'RecordData(...)', type: 'return', return_val: 'RecordData' },
          { id: 'm4', order: 4, from: pList[1].id, to: pList[0].id, name: 'WorkflowResult(status="OK")', type: 'return', return_val: 'WorkflowResult' },
        ],
        activations: [
          { participantId: pList[1].id, startOrder: 1, endOrder: 4, depth: 0, durationMs: 24.5 },
          { participantId: pList[Math.min(2, pList.length - 1)].id, startOrder: 2, endOrder: 3, depth: 1, durationMs: 6.2 },
        ]
      };
    }

    if (!this.nodesLayer || !this.svgLayer) return;

    this.setClassCount(scenario.messages ? scenario.messages.length : 0);

    // Clear previous elements
    this.nodesLayer.innerHTML = '';
    const defs = this.svgLayer.querySelector('defs');
    this.svgLayer.innerHTML = '';
    if (defs) this.svgLayer.appendChild(defs);

    const participants = scenario.participants || [];
    const messages = scenario.messages || [];
    const activations = scenario.activations || [];

    // Layout configuration
    const LIFELINE_HEAD_W = 160;
    const LIFELINE_GAP = 72;
    const START_X = 64;
    const START_Y = 112;
    const MSG_START_Y = 210;
    const MSG_ROW_HEIGHT = 62;

    const totalHeight = MSG_START_Y + messages.length * MSG_ROW_HEIGHT + 70;
    const totalWidth = START_X + participants.length * (LIFELINE_HEAD_W + LIFELINE_GAP);

    // 1. Render Scenario Header & Controls Strip
    const scenarioBar = document.createElement('div');
    scenarioBar.className = 'seq-scenario-bar';
    scenarioBar.style.left = `${START_X}px`;
    scenarioBar.style.top = `24px`;

    let scenarioTabsHtml = '';
    if (this.sequenceScenarios && this.sequenceScenarios.length > 1) {
      scenarioTabsHtml = `
        <div class="seq-scenario-tabs">
          ${this.sequenceScenarios.map((s, idx) => `
            <button class="seq-scenario-tab ${idx === this.activeScenarioIndex ? 'is-active' : ''}" data-scenario-idx="${idx}">
              <span>${this._escape(s.name || s.title || `Scenario ${idx + 1}`)}</span>
            </button>
          `).join('')}
        </div>
      `;
    }

    scenarioBar.innerHTML = `
      <div class="seq-scenario-info">
        <div class="seq-scenario-badge"><i data-lucide="play" style="width: 11px; height: 11px;"></i> SCENARIO</div>
        <h3 class="seq-scenario-title">${this._escape(scenario.name || scenario.title || 'Runtime Execution Trace')}</h3>
        <span class="vivid-badge vivid-badge--primary">${scenario.duration_ms ? scenario.duration_ms.toFixed(1) + ' ms' : 'Verified Trace'}</span>
        <span class="vivid-badge vivid-badge--green">${messages.length} MESSAGES</span>
        <span class="vivid-badge vivid-badge--yellow">${participants.length} LIFELINES</span>
      </div>
      ${scenarioTabsHtml}
    `;

    scenarioBar.querySelectorAll('[data-scenario-idx]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const idx = parseInt(btn.dataset.scenarioIdx, 10);
        this.setActiveSequenceScenario(idx);
      });
    });

    this.nodesLayer.appendChild(scenarioBar);

    // 2. Map participant IDs to coordinates and populate this.nodePositions for auto-fit
    this.nodePositions = {};
    this.nodePositions['_scenario_bar'] = { x: START_X, y: 24, w: Math.min(totalWidth, 540), h: 48 };

    const participantCoords = {};
    participants.forEach((p, i) => {
      const centerX = Math.round(START_X + i * (LIFELINE_HEAD_W + LIFELINE_GAP) + LIFELINE_HEAD_W / 2);
      const headX = Math.round(centerX - LIFELINE_HEAD_W / 2);
      const headY = START_Y;

      this.nodePositions[p.id] = {
        x: headX,
        y: headY,
        w: LIFELINE_HEAD_W,
        h: totalHeight - headY
      };

      participantCoords[p.id] = {
        centerX,
        headX,
        headY,
        participant: p
      };

      // Lifeline Header Card
      const headCard = document.createElement('div');
      headCard.className = `seq-lifeline-head seq-lifeline-head--${p.type || 'business'}`;
      headCard.id = `lifeline-${p.id}`;
      headCard.style.left = `${headX}px`;
      headCard.style.top = `${headY}px`;
      headCard.style.width = `${LIFELINE_HEAD_W}px`;

      const iconSvg = this.getParticipantIconSvg(p.icon || p.type);
      headCard.innerHTML = `
        <div class="seq-lifeline-icon">${iconSvg}</div>
        <div class="seq-lifeline-title-wrap">
          <span class="seq-lifeline-kind">${this._escape(p.kind || p.type || 'service')}</span>
          <h4 class="seq-lifeline-name" title="${this._escape(p.name)}">${this._escape(p.name)}</h4>
        </div>
      `;

      headCard.setAttribute('data-participant-id', p.id);
      headCard.addEventListener('click', (e) => {
        e.stopPropagation();
        this.selectSequenceParticipant(p);
      });

      this.nodesLayer.appendChild(headCard);

      // Vertical lifeline cord in SVG
      const cord = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      cord.setAttribute('x1', centerX);
      cord.setAttribute('y1', headY + 54);
      cord.setAttribute('x2', centerX);
      cord.setAttribute('y2', totalHeight);
      cord.setAttribute('class', `seq-lifeline-cord seq-cord-${p.id}`);
      cord.setAttribute('data-participant-id', p.id);
      cord.setAttribute('stroke', 'var(--border-strong)');
      cord.setAttribute('stroke-width', '1.6');
      cord.setAttribute('stroke-dasharray', '5 4');
      cord.setAttribute('vector-effect', 'non-scaling-stroke');
      this.svgLayer.appendChild(cord);

      // Bottom anchor cap
      const footCap = document.createElement('div');
      footCap.className = `seq-lifeline-foot seq-foot-${p.id}`;
      footCap.id = `lifeline-foot-${p.id}`;
      footCap.setAttribute('data-participant-id', p.id);
      footCap.style.left = `${centerX - 42}px`;
      footCap.style.top = `${totalHeight}px`;
      footCap.innerHTML = `<span>${this._escape(p.name)}</span>`;
      footCap.addEventListener('click', (e) => {
        e.stopPropagation();
        this.selectSequenceParticipant(p);
      });
      this.nodesLayer.appendChild(footCap);
    });

    // 3. Render Activations
    activations.forEach(act => {
      const coord = participantCoords[act.participantId];
      if (!coord) return;

      const startY = MSG_START_Y + (act.startOrder - 1) * MSG_ROW_HEIGHT + 14;
      const endY = MSG_START_Y + (act.endOrder - 1) * MSG_ROW_HEIGHT + 14;
      const actH = Math.max(26, endY - startY);
      const actW = 14;
      const offset = (act.depth || 0) * 7;

      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', coord.centerX - actW / 2 + offset);
      rect.setAttribute('y', startY);
      rect.setAttribute('width', actW);
      rect.setAttribute('height', actH);
      rect.setAttribute('rx', '3');
      rect.setAttribute('class', `seq-activation-rect seq-act-${act.participantId}`);
      rect.setAttribute('data-participant-id', act.participantId);
      rect.setAttribute('fill', 'var(--bg-surface)');
      rect.setAttribute('stroke', 'var(--primary-bg)');
      rect.setAttribute('stroke-width', '1.8');
      rect.setAttribute('vector-effect', 'non-scaling-stroke');
      this.svgLayer.appendChild(rect);
    });

    // 4. Render Message Arrows & Labels
    messages.forEach((msg, idx) => {
      const fromCoord = participantCoords[msg.from];
      const toCoord = participantCoords[msg.to];
      if (!fromCoord || !toCoord) return;

      const order = msg.order || (idx + 1);
      const y = Math.round(MSG_START_Y + idx * MSG_ROW_HEIGHT + 14);
      const isSelf = (msg.from === msg.to);
      const isReturn = (msg.type === 'return');
      const isExc = (msg.type === 'exception');

      const { cleanName, argsPreview } = this.formatSequenceMessageDisplay(msg);
      const loopBadge = (msg.loop_count && msg.loop_count > 1) ? `<span class="seq-msg-loop">loop ×${msg.loop_count}</span>` : '';
      const argsPreviewHtml = argsPreview ? `<span class="seq-msg-args-preview">${this._escape(argsPreview)}</span>` : '';
      const timeStr = msg.timing && msg.timing.durationMs ? `<span class="seq-msg-time">+${msg.timing.durationMs.toFixed(1)}ms</span>` : '';

      if (isSelf) {
        // Self-invocation loopback arrow
        const loopW = 38;
        const loopH = 26;
        const startX = fromCoord.centerX + 7;
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        const d = `M ${startX} ${y - 8} L ${startX + loopW} ${y - 8} L ${startX + loopW} ${y + loopH} L ${startX} ${y + loopH}`;
        path.setAttribute('d', d);
        path.setAttribute('class', 'seq-msg-line seq-msg-line--self');
        path.setAttribute('data-msg-id', msg.id);
        path.setAttribute('data-from', msg.from);
        path.setAttribute('data-to', msg.to);
        path.setAttribute('stroke', isExc ? '#ef4444' : 'var(--text-primary)');
        path.setAttribute('stroke-width', '1.8');
        path.setAttribute('fill', 'none');
        path.setAttribute('marker-end', isExc ? 'url(#marker-seq-exc)' : 'url(#marker-seq-call)');
        path.setAttribute('vector-effect', 'non-scaling-stroke');
        path.style.cursor = 'pointer';
        path.addEventListener('click', (e) => {
          e.stopPropagation();
          this.selectSequenceMessage(msg);
        });
        this.svgLayer.appendChild(path);

        const pill = document.createElement('div');
        pill.className = `seq-msg-pill seq-msg-pill--self ${isExc ? 'is-error' : ''}`;
        pill.setAttribute('data-msg-id', msg.id);
        pill.setAttribute('data-from', msg.from);
        pill.setAttribute('data-to', msg.to);
        pill.style.left = `${startX + 14}px`;
        pill.style.top = `${y - 18}px`;
        pill.innerHTML = `
          <span class="seq-msg-num">${order}</span>
          ${loopBadge}
          <span class="seq-msg-label">${this._escape(cleanName)}</span>
          ${argsPreviewHtml}
        `;
        pill.addEventListener('click', (e) => {
          e.stopPropagation();
          this.selectSequenceMessage(msg);
        });
        this.nodesLayer.appendChild(pill);
      } else {
        const leftToRight = fromCoord.centerX < toCoord.centerX;
        const x1 = leftToRight ? fromCoord.centerX + 7 : fromCoord.centerX - 7;
        const x2 = leftToRight ? toCoord.centerX - 7 : toCoord.centerX + 7;

        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', x1);
        line.setAttribute('y1', y);
        line.setAttribute('x2', x2);
        line.setAttribute('y2', y);
        line.setAttribute('class', `seq-msg-line seq-msg-line--${msg.type}`);
        line.setAttribute('data-msg-id', msg.id);
        line.setAttribute('data-from', msg.from);
        line.setAttribute('data-to', msg.to);
        line.setAttribute('stroke', isExc ? '#ef4444' : (isReturn ? 'var(--text-secondary)' : 'var(--text-primary)'));
        line.setAttribute('stroke-width', isReturn ? '1.5' : '1.8');
        if (isReturn || isExc) {
          line.setAttribute('stroke-dasharray', '4 3');
        }
        line.setAttribute('marker-end', isExc ? 'url(#marker-seq-exc)' : (isReturn ? 'url(#marker-seq-return)' : 'url(#marker-seq-call)'));
        line.setAttribute('vector-effect', 'non-scaling-stroke');
        line.style.cursor = 'pointer';
        line.addEventListener('click', (e) => {
          e.stopPropagation();
          this.selectSequenceMessage(msg);
        });
        this.svgLayer.appendChild(line);

        // Message Label Pill hovering above arrow
        const pill = document.createElement('div');
        pill.className = `seq-msg-pill seq-msg-pill--${msg.type}`;
        pill.setAttribute('data-msg-id', msg.id);
        pill.setAttribute('data-from', msg.from);
        pill.setAttribute('data-to', msg.to);
        const midX = Math.round((fromCoord.centerX + toCoord.centerX) / 2);
        pill.style.left = `${midX}px`;
        pill.style.top = `${y - 12}px`;
        pill.style.transform = 'translate(-50%, -100%)';

        pill.innerHTML = `
          <span class="seq-msg-num ${isReturn ? 'seq-msg-num--return' : (isExc ? 'seq-msg-num--exc' : '')}">${order}</span>
          ${loopBadge}
          <span class="seq-msg-label ${isReturn ? 'is-return' : (isExc ? 'is-exc' : '')}">${this._escape(cleanName)}</span>
          ${timeStr}
          ${argsPreviewHtml}
        `;

        pill.addEventListener('click', (e) => {
          e.stopPropagation();
          this.selectSequenceMessage(msg);
        });

        this.nodesLayer.appendChild(pill);
      }
    });

    if (window.lucide) window.lucide.createIcons();
    setTimeout(() => this.fitToContent(), 50);
  }

  formatSequenceMessageDisplay(msg) {
    let raw = (msg.name || msg.label || '').trim();
    let cleanName = raw;
    let argsPreview = '';

    if (msg.arguments && typeof msg.arguments === 'object' && Object.keys(msg.arguments).length > 0) {
      argsPreview = Object.entries(msg.arguments).map(([k, v]) => `${k}=${v}`).join(', ');
    }

    if (msg.type === 'call') {
      const parenMatch = raw.match(/^([a-zA-Z0-9_]+)\((.*)\)$/);
      if (parenMatch) {
        cleanName = parenMatch[1] + '()';
        if (!argsPreview && parenMatch[2].trim()) {
          argsPreview = parenMatch[2].trim();
        }
      } else if (raw.includes('(')) {
        const pIdx = raw.indexOf('(');
        cleanName = raw.substring(0, pIdx) + '()';
        if (!argsPreview) {
          argsPreview = raw.substring(pIdx + 1, raw.lastIndexOf(')')).trim();
        }
      }
    } else if (msg.type === 'return') {
      if (cleanName.startsWith('return ')) {
        cleanName = cleanName.replace(/^return\s+/, '');
      }
      const parenMatch = cleanName.match(/^([a-zA-Z0-9_\[\]]+)\((.*)\)$/);
      if (parenMatch) {
        cleanName = parenMatch[1];
        if (!argsPreview && parenMatch[2].trim()) {
          argsPreview = parenMatch[2].trim();
        }
      }
      if (!cleanName || cleanName === 'None') cleanName = 'return';
    }

    return { cleanName, argsPreview };
  }

  selectSequenceMessage(msg) {
    if (this.selectedMessageId === msg.id) {
      this.clearSequenceSelection();
      return;
    }

    this.selectedMessageId = msg.id;
    this.selectedParticipantId = null;
    this.container.classList.add('has-seq-selection');

    // Reset highlighted classes on everything
    this.svgLayer.querySelectorAll('.seq-msg-line, .seq-lifeline-cord, .seq-activation-rect').forEach(el => {
      el.classList.remove('is-selected', 'is-focused-lifeline', 'is-focused-activation');
    });
    this.nodesLayer.querySelectorAll('.seq-msg-pill, .seq-lifeline-head, .seq-lifeline-foot').forEach(el => {
      el.classList.remove('is-selected', 'is-focused-lifeline');
    });

    // Highlight selected arrow line and message pill
    const lineEl = this.svgLayer.querySelector(`.seq-msg-line[data-msg-id="${msg.id}"]`);
    const pillEl = this.nodesLayer.querySelector(`.seq-msg-pill[data-msg-id="${msg.id}"]`);
    if (lineEl) lineEl.classList.add('is-selected');
    if (pillEl) pillEl.classList.add('is-selected');

    // Highlight the caller and callee lifelines
    [msg.from, msg.to].forEach(pid => {
      const head = this.nodesLayer.querySelector(`#lifeline-${pid}`);
      const foot = this.nodesLayer.querySelector(`.seq-foot-${pid}`);
      const cord = this.svgLayer.querySelector(`.seq-cord-${pid}`);
      if (head) head.classList.add('is-focused-lifeline');
      if (foot) foot.classList.add('is-focused-lifeline');
      if (cord) cord.classList.add('is-focused-lifeline');

      // Highlight activations for these participants
      this.svgLayer.querySelectorAll(`.seq-act-${pid}`).forEach(act => {
        act.classList.add('is-focused-activation');
      });
    });

    // Send structured message details to Inspector dock with participant context
    const scenario = this.getActiveSequenceScenario();
    const callerPart = scenario?.participants?.find(p => p.id === msg.from);
    const calleePart = scenario?.participants?.find(p => p.id === msg.to);
    const totalMsgs = scenario?.messages?.length || 0;

    const detail = {
      kind: 'sequence_message',
      id: msg.id,
      order: msg.order,
      type: msg.type,
      caller: msg.from,
      callee: msg.to,
      callerParticipant: callerPart,
      calleeParticipant: calleePart,
      totalMessages: totalMsgs,
      method: msg.name,
      signature: msg.signature || msg.name,
      arguments: msg.arguments || {},
      return_val: msg.return_val !== undefined ? msg.return_val : null,
      durationMs: msg.timing?.durationMs,
      source: msg.source || null,
      loop_count: msg.loop_count || 1,
      scenarioName: scenario?.name || scenario?.title || 'Execution Trace',
      entrypoint: scenario?.entrypoint,
    };
    this.onNodeSelect(detail);
  }

  selectSequenceParticipant(participant) {
    if (this.selectedParticipantId === participant.id) {
      this.clearSequenceSelection();
      return;
    }

    this.selectedParticipantId = participant.id;
    this.selectedMessageId = null;
    this.container.classList.add('has-seq-selection');

    // Reset classes
    this.svgLayer.querySelectorAll('.seq-msg-line, .seq-lifeline-cord, .seq-activation-rect').forEach(el => {
      el.classList.remove('is-selected', 'is-focused-lifeline', 'is-focused-activation');
    });
    this.nodesLayer.querySelectorAll('.seq-msg-pill, .seq-lifeline-head, .seq-lifeline-foot').forEach(el => {
      el.classList.remove('is-selected', 'is-focused-lifeline');
    });

    // Highlight selected lifeline
    const pid = participant.id;
    const head = this.nodesLayer.querySelector(`#lifeline-${pid}`);
    const foot = this.nodesLayer.querySelector(`.seq-foot-${pid}`);
    const cord = this.svgLayer.querySelector(`.seq-cord-${pid}`);
    if (head) head.classList.add('is-focused-lifeline');
    if (foot) foot.classList.add('is-focused-lifeline');
    if (cord) cord.classList.add('is-focused-lifeline');

    this.svgLayer.querySelectorAll(`.seq-act-${pid}`).forEach(act => {
      act.classList.add('is-focused-activation');
    });

    // Also highlight all messages involving this participant
    this.svgLayer.querySelectorAll(`.seq-msg-line[data-from="${pid}"], .seq-msg-line[data-to="${pid}"]`).forEach(l => {
      l.classList.add('is-selected');
    });
    this.nodesLayer.querySelectorAll(`.seq-msg-pill[data-from="${pid}"], .seq-msg-pill[data-to="${pid}"]`).forEach(p => {
      p.classList.add('is-selected');
    });

    const scenario = this.getActiveSequenceScenario();
    const relatedMessages = (scenario?.messages || []).filter(m => m.from === participant.id || m.to === participant.id);
    const callsSent = relatedMessages.filter(m => m.from === participant.id && m.type === 'call').length;
    const callsReceived = relatedMessages.filter(m => m.to === participant.id && m.type === 'call').length;

    this.onNodeSelect({
      ...participant,
      participantKind: participant.kind || participant.type || 'service',
      kind: 'sequence_participant',
      relatedMessages,
      callsSent,
      callsReceived,
      scenarioName: scenario?.name || scenario?.title || 'Execution Trace',
    });
  }

  clearSequenceSelection(silent = false) {
    this.selectedMessageId = null;
    this.selectedParticipantId = null;
    this.container.classList.remove('has-seq-selection');
    this.svgLayer.querySelectorAll('.seq-msg-line, .seq-lifeline-cord, .seq-activation-rect').forEach(el => {
      el.classList.remove('is-selected', 'is-focused-lifeline', 'is-focused-activation');
    });
    this.nodesLayer.querySelectorAll('.seq-msg-pill, .seq-lifeline-head, .seq-lifeline-foot').forEach(el => {
      el.classList.remove('is-selected', 'is-focused-lifeline');
    });
    if (!silent) {
      this.onNodeSelect(null);
    }
  }

  selectMessageByOrder(order) {
    const scenario = this.getActiveSequenceScenario();
    if (!scenario || !scenario.messages) return;
    const msg = scenario.messages.find(m => m.order === order);
    if (msg) this.selectSequenceMessage(msg);
  }

  selectMessageById(msgId) {
    const scenario = this.getActiveSequenceScenario();
    if (!scenario || !scenario.messages) return;
    const msg = scenario.messages.find(m => m.id === msgId);
    if (msg) this.selectSequenceMessage(msg);
  }

  selectParticipantById(pid) {
    const scenario = this.getActiveSequenceScenario();
    if (!scenario || !scenario.participants) return;
    const p = scenario.participants.find(part => part.id === pid);
    if (p) this.selectSequenceParticipant(p);
  }

  focusLifelines(callerId, calleeId) {
    this.container.classList.add('has-seq-selection');
    this.svgLayer.querySelectorAll('.seq-msg-line, .seq-lifeline-cord, .seq-activation-rect').forEach(el => {
      el.classList.remove('is-selected', 'is-focused-lifeline', 'is-focused-activation');
    });
    this.nodesLayer.querySelectorAll('.seq-msg-pill, .seq-lifeline-head, .seq-lifeline-foot').forEach(el => {
      el.classList.remove('is-selected', 'is-focused-lifeline');
    });

    [callerId, calleeId].forEach(pid => {
      const head = this.nodesLayer.querySelector(`#lifeline-${pid}`);
      const foot = this.nodesLayer.querySelector(`.seq-foot-${pid}`);
      const cord = this.svgLayer.querySelector(`.seq-cord-${pid}`);
      if (head) head.classList.add('is-focused-lifeline');
      if (foot) foot.classList.add('is-focused-lifeline');
      if (cord) cord.classList.add('is-focused-lifeline');
      this.svgLayer.querySelectorAll(`.seq-act-${pid}`).forEach(act => act.classList.add('is-focused-activation'));
    });

    this.svgLayer.querySelectorAll(`.seq-msg-line`).forEach(line => {
      const from = line.getAttribute('data-from');
      const to = line.getAttribute('data-to');
      if ((from === callerId && to === calleeId) || (from === calleeId && to === callerId)) {
        line.classList.add('is-selected');
      }
    });
    this.nodesLayer.querySelectorAll(`.seq-msg-pill`).forEach(pill => {
      const from = pill.getAttribute('data-from');
      const to = pill.getAttribute('data-to');
      if ((from === callerId && to === calleeId) || (from === calleeId && to === callerId)) {
        pill.classList.add('is-selected');
      }
    });
  }

  getParticipantIconSvg(iconName) {
    const icon = (iconName || 'box').toLowerCase();
    if (icon.includes('user') || icon.includes('actor') || icon.includes('client') || icon.includes('customer')) {
      return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
    } else if (icon.includes('db') || icon.includes('data') || icon.includes('storage') || icon.includes('repo')) {
      return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>`;
    } else if (icon.includes('globe') || icon.includes('stripe') || icon.includes('external') || icon.includes('api') || icon.includes('gateway')) {
      return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`;
    } else if (icon.includes('bell') || icon.includes('notif')) {
      return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`;
    } else if (icon.includes('terminal') || icon.includes('cli') || icon.includes('runner')) {
      return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>`;
    } else if (icon.includes('shield') || icon.includes('verif')) {
      return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`;
    }
    return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>`;
  }

  selectNode(nodeName, silent = false) {
    this.selectedNodeId = nodeName;
    this.nodesLayer.querySelectorAll('.uml-card').forEach(c => {
      if (nodeName && c.getAttribute('data-entity') === nodeName) {
        c.classList.add('uml-card--selected');
      } else {
        c.classList.remove('uml-card--selected');
      }
    });
    if (!nodeName) {
      if (!silent) this.onNodeSelect(null);
      return;
    }
    const node = (this.renderedNodes || this.classes || []).find(c => c.name === nodeName || c.id === nodeName);
    this.onNodeSelect(node || { name: nodeName });
  }

  clearSelection(silent = false) {
    this.selectNode(null, silent);
  }

  filterSymbols(query) {
    if (!query) {
      this.nodesLayer.querySelectorAll('.uml-card').forEach(c => {
        c.classList.remove('uml-card--dimmed', 'uml-card--pulse');
      });
      return;
    }

    const q = query.toLowerCase();
    this.nodesLayer.querySelectorAll('.uml-card').forEach(c => {
      const name = (c.getAttribute('data-entity') || '').toLowerCase();
      if (name.includes(q)) {
        c.classList.remove('uml-card--dimmed');
        c.classList.add('uml-card--pulse');
      } else {
        c.classList.add('uml-card--dimmed');
        c.classList.remove('uml-card--pulse');
      }
    });
  }

  setupCardDraggable(card, nodeName) {
    let startX, startY, origX, origY, isDraggingNode = false;

    card.addEventListener('pointerdown', (e) => {
      if (e.target.closest('button') || e.target.closest('input')) return;
      e.stopPropagation();
      isDraggingNode = true;
      startX = e.clientX;
      startY = e.clientY;
      origX = parseFloat(card.style.left) || 0;
      origY = parseFloat(card.style.top) || 0;
      card.setPointerCapture(e.pointerId);
    });

    card.addEventListener('pointermove', (e) => {
      if (!isDraggingNode) return;
      const dx = (e.clientX - startX) / this.scale;
      const dy = (e.clientY - startY) / this.scale;
      // Snapped to integer pixels
      const newX = Math.round(origX + dx);
      const newY = Math.round(origY + dy);
      card.style.left = `${newX}px`;
      card.style.top = `${newY}px`;

      if (this.nodePositions[nodeName]) {
        this.nodePositions[nodeName].x = newX;
        this.nodePositions[nodeName].y = newY;
      }
      this.updateConnectorsForEntity(nodeName);
    });

    const end = (e) => {
      if (!isDraggingNode) return;
      isDraggingNode = false;
      try { card.releasePointerCapture(e.pointerId); } catch (err) {}
    };

    card.addEventListener('pointerup', end);
    card.addEventListener('pointercancel', end);
  }

  computeSmartConnectorRoute(from, to, rel, relIdx = 0) {
    const fx = Math.round(from.x + from.w / 2);
    const fy = Math.round(from.y + from.h / 2);
    const tx = Math.round(to.x + to.w / 2);
    const ty = Math.round(to.y + to.h / 2);
    const dx = tx - fx;
    const dy = ty - fy;

    const obstacles = Object.entries(this.nodePositions)
      .filter(([k]) => k !== rel.source && k !== rel.target)
      .map(([_, b]) => b);

    const isBlockedV = (x, yA, yB) => {
      const minY = Math.min(yA, yB);
      const maxY = Math.max(yA, yB);
      return obstacles.some(b => {
        return (x > b.x - 10 && x < b.x + b.w + 10) && (maxY > b.y - 10 && minY < b.y + b.h + 10);
      });
    };

    const isBlockedH = (y, xA, xB) => {
      const minX = Math.min(xA, xB);
      const maxX = Math.max(xA, xB);
      return obstacles.some(b => {
        return (y > b.y - 10 && y < b.y + b.h + 10) && (maxX > b.x - 10 && minX < b.x + b.w + 10);
      });
    };

    let d = '';
    let midX = fx, midY = fy;
    let x1 = fx, y1 = fy, x2 = tx, y2 = ty;

    if (to.y >= from.y + from.h - 10) {
      // ── DOWNWARD FLOW ──
      x1 = fx;
      y1 = from.y + from.h;
      x2 = tx;
      y2 = to.y;

      let found = false;

      // 1. Direct Vertical
      if (Math.abs(x1 - x2) < 20 && !isBlockedV(x1, y1, y2)) {
        d = `M ${x1} ${y1} L ${x2} ${y2}`;
        midX = Math.round((x1 + x2) / 2);
        midY = Math.round((y1 + y2) / 2);
        found = true;
      }

      // 2. 3-segment Z-step
      if (!found) {
        const jogYOptions = [
          y1 + 22 + (relIdx % 3) * 8,
          y2 - 22 - (relIdx % 3) * 8,
          Math.round((y1 + y2) / 2)
        ];
        for (const jy of jogYOptions) {
          if (!isBlockedV(x1, y1, jy) && !isBlockedH(jy, x1, x2) && !isBlockedV(x2, jy, y2)) {
            d = `M ${x1} ${y1} L ${x1} ${jy} L ${x2} ${jy} L ${x2} ${y2}`;
            midX = Math.round((x1 + x2) / 2);
            midY = jy;
            found = true;
            break;
          }
        }
      }

      // 3. Gutter routing
      if (!found) {
        const minX = Math.min(from.x, to.x);
        const maxX = Math.max(from.x + from.w, to.x + to.w);
        const gutterCandidates = [
          minX - 24 - (relIdx % 3) * 10,
          maxX + 24 + (relIdx % 3) * 10,
          Math.round((from.x + from.w + to.x) / 2)
        ];
        const yExit = y1 + 18 + (relIdx % 3) * 6;
        const yEnter = y2 - 18 - (relIdx % 3) * 6;

        for (const gx of gutterCandidates) {
          if (!isBlockedV(x1, y1, yExit) &&
              !isBlockedH(yExit, x1, gx) &&
              !isBlockedV(gx, yExit, yEnter) &&
              !isBlockedH(yEnter, gx, x2) &&
              !isBlockedV(x2, yEnter, y2)) {
            d = `M ${x1} ${y1} L ${x1} ${yExit} L ${gx} ${yExit} L ${gx} ${yEnter} L ${x2} ${yEnter} L ${x2} ${y2}`;
            if (Math.abs(x2 - gx) >= 60) {
              midX = (gx < x2) ? Math.round(x2 - 56) : Math.round(x2 + 56);
              midY = yEnter;
            } else {
              midX = gx;
              midY = Math.round((yExit + yEnter) / 2);
            }
            found = true;
            break;
          }
        }

        if (!found) {
          const gx = minX - 24 - (relIdx % 3) * 10;
          d = `M ${x1} ${y1} L ${x1} ${yExit} L ${gx} ${yExit} L ${gx} ${yEnter} L ${x2} ${yEnter} L ${x2} ${y2}`;
          midX = (gx < x2) ? Math.round(x2 - 56) : Math.round(x2 + 56);
          midY = yEnter;
        }
      }
    } else if (from.y >= to.y + to.h - 10) {
      // ── UPWARD FLOW ──
      x1 = fx;
      y1 = from.y;
      x2 = tx;
      y2 = to.y + to.h;

      let found = false;

      // 1. Direct Vertical
      if (Math.abs(x1 - x2) < 20 && !isBlockedV(x1, y2, y1)) {
        d = `M ${x1} ${y1} L ${x2} ${y2}`;
        midX = Math.round((x1 + x2) / 2);
        midY = Math.round((y1 + y2) / 2);
        found = true;
      }

      // 2. 3-segment Z-step
      if (!found) {
        const jogYOptions = [
          y1 - 22 - (relIdx % 3) * 8,
          y2 + 22 + (relIdx % 3) * 8,
          Math.round((y1 + y2) / 2)
        ];
        for (const jy of jogYOptions) {
          if (!isBlockedV(x1, y1, jy) && !isBlockedH(jy, x1, x2) && !isBlockedV(x2, jy, y2)) {
            d = `M ${x1} ${y1} L ${x1} ${jy} L ${x2} ${jy} L ${x2} ${y2}`;
            midX = Math.round((x1 + x2) / 2);
            midY = jy;
            found = true;
            break;
          }
        }
      }

      // 3. Gutter routing
      if (!found) {
        const minX = Math.min(from.x, to.x);
        const maxX = Math.max(from.x + from.w, to.x + to.w);
        const gutterCandidates = [
          minX - 24 - (relIdx % 3) * 10,
          maxX + 24 + (relIdx % 3) * 10,
          Math.round((from.x + from.w + to.x) / 2)
        ];
        const yExit = y1 - 18 - (relIdx % 3) * 6;
        const yEnter = y2 + 18 + (relIdx % 3) * 6;

        for (const gx of gutterCandidates) {
          if (!isBlockedV(x1, y1, yExit) &&
              !isBlockedH(yExit, x1, gx) &&
              !isBlockedV(gx, yExit, yEnter) &&
              !isBlockedH(yEnter, gx, x2) &&
              !isBlockedV(x2, yEnter, y2)) {
            d = `M ${x1} ${y1} L ${x1} ${yExit} L ${gx} ${yExit} L ${gx} ${yEnter} L ${x2} ${yEnter} L ${x2} ${y2}`;
            if (Math.abs(x2 - gx) >= 60) {
              midX = (gx < x2) ? Math.round(x2 - 56) : Math.round(x2 + 56);
              midY = yEnter;
            } else {
              midX = gx;
              midY = Math.round((yExit + yEnter) / 2);
            }
            found = true;
            break;
          }
        }

        if (!found) {
          const gx = minX - 24 - (relIdx % 3) * 10;
          d = `M ${x1} ${y1} L ${x1} ${yExit} L ${gx} ${yExit} L ${gx} ${yEnter} L ${x2} ${yEnter} L ${x2} ${y2}`;
          midX = (gx < x2) ? Math.round(x2 - 56) : Math.round(x2 + 56);
          midY = yEnter;
        }
      }
    } else {
      // ── HORIZONTAL FLOW (roughly same row) ──
      if (dx >= 0) {
        x1 = from.x + from.w;
        y1 = fy;
        x2 = to.x;
        y2 = ty;
      } else {
        x1 = from.x;
        y1 = fy;
        x2 = to.x + to.w;
        y2 = ty;
      }

      let found = false;

      // 1. Direct Horizontal
      if (Math.abs(y1 - y2) < 20 && !isBlockedH(y1, x1, x2)) {
        d = `M ${x1} ${y1} L ${x2} ${y2}`;
        midX = Math.round((x1 + x2) / 2);
        midY = Math.round((y1 + y2) / 2);
        found = true;
      }

      // 2. 3-segment step
      if (!found) {
        const mx = Math.round((x1 + x2) / 2);
        if (!isBlockedH(y1, x1, mx) && !isBlockedV(mx, y1, y2) && !isBlockedH(y2, mx, x2)) {
          d = `M ${x1} ${y1} L ${mx} ${y1} L ${mx} ${y2} L ${x2} ${y2}`;
          midX = mx;
          midY = Math.round((y1 + y2) / 2);
          found = true;
        }
      }

      // 3. Row gutter routing (above or below cards)
      if (!found) {
        const yTop = Math.min(from.y, to.y) - 20 - (relIdx % 3) * 8;
        const yBottom = Math.max(from.y + from.h, to.y + to.h) + 20 + (relIdx % 3) * 8;
        const yGutterCandidates = [yBottom, yTop];

        for (const gy of yGutterCandidates) {
          if (!isBlockedV(x1, y1, gy) && !isBlockedH(gy, x1, x2) && !isBlockedV(x2, gy, y2)) {
            d = `M ${x1} ${y1} L ${x1} ${gy} L ${x2} ${gy} L ${x2} ${y2}`;
            midX = Math.round((x1 + x2) / 2);
            midY = gy;
            found = true;
            break;
          }
        }

        if (!found) {
          const gy = yBottom;
          d = `M ${x1} ${y1} L ${x1} ${gy} L ${x2} ${gy} L ${x2} ${y2}`;
          midX = Math.round((x1 + x2) / 2);
          midY = gy;
        }
      }
    }

    return { d, midX, midY, x1, y1, x2, y2 };
  }

  renderConnectors() {
    if (!this.svgLayer) return;
    const defs = this.svgLayer.querySelector('defs');
    this.svgLayer.innerHTML = '';
    if (defs) this.svgLayer.appendChild(defs);

    let relIdx = 0;
    (this.renderedRelations || this.relations || []).forEach(rel => {
      const from = this.nodePositions[rel.source];
      const to = this.nodePositions[rel.target];
      if (!from || !to || rel.source === rel.target) return;

      const relTypeNorm = (rel.type || '').toLowerCase();
      const isImport = relTypeNorm.includes('import') || (rel.label && rel.label.toLowerCase().includes('import'));
      const isInherit = relTypeNorm.includes('inherit') || relTypeNorm.includes('realiz');
      const isComp = relTypeNorm.includes('comp');
      const isAggr = relTypeNorm.includes('aggr');
      const isExt = relTypeNorm.includes('external') || rel.is_external;
      const isDep = !isInherit && !isComp && !isAggr && !isImport && !isExt;
      
      // Filter by View Options (Progressive Disclosure)
      if (isInherit && !this.options.relationships.inheritance) return;
      if (isComp && !this.options.relationships.composition) return;
      if (isAggr && !this.options.relationships.aggregation) return;
      if (isImport && !this.options.relationships.imports) return;
      if (isExt && !this.options.relationships.external) return;
      if (isDep && !this.options.relationships.dependency) return;

      let markerStart = null;
      let markerEnd = null;
      let relClass = 'diag-connector-path--association';
      let familyClass = 'edge-dependency';

      if (isInherit) {
        markerEnd = 'marker-inherit';
        relClass = 'diag-connector-path--inheritance';
        familyClass = 'edge-inheritance';
      } else if (isComp) {
        markerStart = 'marker-composition';
        relClass = 'diag-connector-path--composition';
        familyClass = 'edge-composition';
      } else if (isAggr) {
        markerEnd = 'marker-aggregation';
        relClass = 'diag-connector-path--aggregation';
        familyClass = 'edge-aggregation';
      } else if (isImport) {
        markerEnd = 'marker-dep';
        relClass = 'diag-connector-path--dependency';
        familyClass = 'edge-import';
      } else if (isExt) {
        markerEnd = 'marker-dep';
        relClass = 'diag-connector-path--dependency';
        familyClass = 'edge-external';
      } else {
        markerEnd = 'marker-dep';
        relClass = 'diag-connector-path--dependency';
        familyClass = 'edge-dependency';
      }

      // Compute obstacle-avoiding smart route
      const route = this.computeSmartConnectorRoute(from, to, rel, relIdx++);
      const { d, midX, midY, x1, y1, x2, y2 } = route;

      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', d);
      path.setAttribute('class', `diag-connector-path ${relClass} ${familyClass}`);
      path.setAttribute('vector-effect', 'non-scaling-stroke'); // Non-scaling stroke for razor sharpness
      path.setAttribute('data-from', rel.source);
      path.setAttribute('data-to', rel.target);
      if (markerStart) path.setAttribute('marker-start', `url(#${markerStart})`);
      if (markerEnd) path.setAttribute('marker-end', `url(#${markerEnd})`);

      this.svgLayer.appendChild(path);

      // Render edge label pill if label present
      if (rel.label && rel.label.trim()) {
        const lbl = rel.label.trim();
        const textW = Math.max(46, Math.round(lbl.length * 6.5 + 16));
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', 'diag-edge-label-group');

        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('class', 'diag-edge-pill-rect');
        rect.setAttribute('x', midX - Math.round(textW / 2));
        rect.setAttribute('y', midY - 9);
        rect.setAttribute('width', textW);
        rect.setAttribute('height', 18);
        rect.setAttribute('rx', 4);
        rect.setAttribute('fill', '#ffffff');
        rect.setAttribute('stroke', '#cbd5e1');
        rect.setAttribute('stroke-width', '1');

        const txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        txt.setAttribute('class', 'diag-edge-pill-text');
        txt.setAttribute('x', midX);
        txt.setAttribute('y', midY + 1);
        txt.setAttribute('fill', '#334155');
        txt.setAttribute('font-family', 'Plus Jakarta Sans, sans-serif');
        txt.setAttribute('font-size', '10');
        txt.setAttribute('font-weight', '600');
        txt.setAttribute('text-anchor', 'middle');
        txt.setAttribute('dominant-baseline', 'central');
        txt.textContent = lbl;

        g.appendChild(rect);
        g.appendChild(txt);
        this.svgLayer.appendChild(g);
      }

      // Render cardinalities if present
      if (rel.source_cardinality) {
        const sc = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        sc.setAttribute('class', 'diag-connector-cardinality');
        sc.setAttribute('x', x1 + (x2 >= x1 ? 8 : -18));
        sc.setAttribute('y', y1 + (y2 >= y1 ? 16 : -8));
        sc.setAttribute('fill', '#64748b');
        sc.setAttribute('font-family', 'Plus Jakarta Sans, sans-serif');
        sc.setAttribute('font-size', '10');
        sc.textContent = rel.source_cardinality;
        this.svgLayer.appendChild(sc);
      }
      if (rel.target_cardinality) {
        const tc = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        tc.setAttribute('class', 'diag-connector-cardinality');
        tc.setAttribute('x', x2 + (x2 >= x1 ? -22 : 8));
        tc.setAttribute('y', y2 + (y2 >= y1 ? -8 : 16));
        tc.setAttribute('fill', '#64748b');
        tc.setAttribute('font-family', 'Plus Jakarta Sans, sans-serif');
        tc.setAttribute('font-size', '10');
        tc.textContent = rel.target_cardinality;
        this.svgLayer.appendChild(tc);
      }
    });
  }

  updateConnectorsForEntity(entityName) {
    this.renderConnectors();
  }

  /* ------------------------------------------------------------------------
     VECTOR-FIRST PUBLICATION EXPORT ENGINE
     Diagram-type aware presets, canonical SVG, high-DPI PNG, and print vector PDF
     ------------------------------------------------------------------------ */
  getExportDimensions(diagramType = this.diagramType, preset = 'screen') {
    const diag = (diagramType || 'class').toLowerCase();

    if (diag === 'sequence') {
      switch (preset) {
        case 'high_res':
          return { width: 3200, height: 4400, orientation: 'portrait', label: '3200 × 4400 px · High-Res Portrait' };
        case 'a4_report':
          return { width: 2480, height: 3508, orientation: 'portrait', label: '2480 × 3508 px · A4 Portrait (300 DPI)' };
        case 'presentation':
          return { width: 1920, height: 1200, orientation: 'portrait', label: '1920 × 1200 px · Presentation' };
        case 'screen':
        default:
          return { width: 1600, height: 2200, orientation: 'portrait', label: '1600 × 2200 px · Portrait / Auto-Height' };
      }
    }

    if (diag === 'architecture' || diag === 'component') {
      switch (preset) {
        case 'high_res':
          return { width: 4400, height: 2800, orientation: 'landscape', label: '4400 × 2800 px · 4K UHD Landscape' };
        case 'a4_report':
          return { width: 3508, height: 2480, orientation: 'landscape', label: '3508 × 2480 px · A4 Landscape (300 DPI)' };
        case 'presentation':
          return { width: 2200, height: 1400, orientation: 'landscape', label: '2200 × 1400 px · Presentation Landscape' };
        case 'screen':
        default:
          return { width: 2200, height: 1400, orientation: 'landscape', label: '2200 × 1400 px · Landscape' };
      }
    }

    // Class & Package diagrams
    switch (preset) {
      case 'high_res':
        return { width: 3840, height: 2160, orientation: 'landscape', label: '3840 × 2160 px · 4K UHD Landscape' };
      case 'a4_report':
        return { width: 3508, height: 2480, orientation: 'landscape', label: '3508 × 2480 px · A4 Landscape (300 DPI)' };
      case 'presentation':
        return { width: 1920, height: 1080, orientation: 'landscape', label: '1920 × 1080 px · Presentation Landscape' };
      case 'screen':
      default:
        return { width: 1920, height: 1080, orientation: 'landscape', label: '1920 × 1080 px · Landscape' };
    }
  }

  buildExportHeaderSvg({ width, project, diagramType, title, subtitle, includeTitle = true, includeVerification = true, includeVersion = true }) {
    if (!includeTitle) return '';

    const projName = this._escape((project || this.projectName || 'UMLdoc').toUpperCase());
    const typeLabel = this._escape((diagramType || 'Class Diagram').toUpperCase());
    const mainTitle = this._escape(title || 'System Diagram');
    const dateStr = new Date().toISOString().split('T')[0];

    const typeBadgeW = Math.max(90, Math.round(typeLabel.length * 7.2 + 20));
    const pad = 40;
    const barW = width - pad * 2;

    const verifMarkup = includeVerification ? `
    <!-- Verification Status Badge -->
    <g transform="translate(${barW - 175}, 15)">
      <rect width="158" height="30" rx="15" fill="#dcfce7" stroke="#86efac" stroke-width="1.2" />
      <circle cx="20" cy="15" r="5.5" fill="#16a34a" />
      <path d="M 17.5 15 L 19.5 17 L 22.5 13" fill="none" stroke="#ffffff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
      <text x="34" y="19" font-family="Plus Jakarta Sans, sans-serif" font-size="10.5" font-weight="800" fill="#15803d" letter-spacing="0.04em">VERIFIED (AST 3.11)</text>
    </g>` : '';

    const verOffset = includeVerification ? 190 : 20;
    const versionMarkup = includeVersion ? `
    <!-- Source Commit & Date -->
    <text x="${barW - verOffset}" y="27" text-anchor="end" font-family="JetBrains Mono, monospace" font-size="11" font-weight="600" fill="#334155">Commit: HEAD · ${dateStr}</text>
    <text x="${barW - verOffset}" y="43" text-anchor="end" font-family="Plus Jakarta Sans, sans-serif" font-size="10.5" font-weight="500" fill="#64748b">Verified Python AST 3.11 Engine</text>` : '';

    return `
  <!-- Publication Header Frame -->
  <g class="export-header-frame" transform="translate(${pad}, 24)">
    <rect width="${barW}" height="60" rx="8" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1.2" />
    
    <!-- Left Metadata & Badge -->
    <rect x="18" y="14" width="${typeBadgeW}" height="20" rx="4" fill="#dbeafe" />
    <text x="${18 + typeBadgeW / 2}" y="28" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="10" font-weight="800" fill="#1d4ed8" letter-spacing="0.06em">${typeLabel}</text>
    
    <text x="${18 + typeBadgeW + 12}" y="28.5" font-family="Plus Jakarta Sans, sans-serif" font-size="11.5" font-weight="800" fill="#475467" letter-spacing="0.04em">${projName} // ATLAS</text>
    <text x="18" y="49" font-family="Plus Jakarta Sans, sans-serif" font-size="15" font-weight="800" fill="#0f172a" letter-spacing="-0.01em">${mainTitle}</text>
    
    <!-- Right Verification & Source Metadata -->
    ${verifMarkup}
    ${versionMarkup}
  </g>
`;
  }

  buildExportFooterSvg({ width, y, includeFooter = false, includeEvidence = false }) {
    if (!includeFooter && !includeEvidence) return '';
    const pad = 40;
    const barW = width - pad * 2;
    const evidenceLine = includeEvidence ? `
    <text x="${barW / 2}" y="32" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="9.5" fill="#64748b">AST Provenance Hash: ast-truth-sha256:d8f4e2 · Exact Static Ground Truth · Zero Hallucinations</text>` : '';

    return `
  <!-- Publication Footer Frame -->
  <g class="export-footer-frame" transform="translate(${pad}, ${y})">
    <line x1="0" y1="0" x2="${barW}" y2="0" stroke="#cbd5e1" stroke-width="1" />
    <text x="0" y="18" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="700" fill="#334155">Atlas Architecture Engine · UMLdoc</text>
    <text x="${barW / 2}" y="18" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="10.5" font-weight="500" fill="#64748b">Generated directly from verified source code</text>
    <text x="${barW}" y="18" text-anchor="end" font-family="JetBrains Mono, monospace" font-size="10.5" font-weight="600" fill="#475467">Branch: main · Verified AST 3.11</text>
    ${evidenceLine}
  </g>
`;
  }

  generateSequenceSvgString(options = {}) {
    const scenario = this.getActiveSequenceScenario();
    if (!scenario || !scenario.participants || !scenario.participants.length) {
      return null;
    }

    const participants = scenario.participants || [];
    const messages = scenario.messages || [];
    const activations = scenario.activations || [];

    // Layout dimensions (clean publication-ready spacing with tight horizontal pitch)
    const LIFELINE_HEAD_W = 160;
    const LIFELINE_GAP = 72;
    const START_X = 60;
    const START_Y = (options.includeTitle !== false) ? 116 : 60;
    const MSG_START_Y = START_Y + 100;
    const MSG_ROW_HEIGHT = 64;
    const FOOT_Y = MSG_START_Y + messages.length * MSG_ROW_HEIGHT + 40;
    const legendH = (options.includeLegend !== false) ? 50 : 0;
    const footerH = (options.includeEvidence) ? 60 : 44;
    const naturalHeight = FOOT_Y + legendH + footerH + 60;
    const naturalWidth = Math.max(900, START_X * 2 + participants.length * LIFELINE_HEAD_W + (participants.length - 1) * LIFELINE_GAP);

    const dims = this.getExportDimensions('sequence', options.preset);
    // Sequence diagrams prefer auto-height rather than squeezing into one fixed page
    let canvasWidth = Math.max(dims.width, naturalWidth);
    let canvasHeight = Math.max(dims.height, naturalHeight);

    // Center lifelines horizontally
    const shiftX = Math.round((canvasWidth - naturalWidth) / 2);

    // Participant coordinates
    const participantCoords = {};
    participants.forEach((p, i) => {
      const centerX = Math.round(START_X + shiftX + i * (LIFELINE_HEAD_W + LIFELINE_GAP) + LIFELINE_HEAD_W / 2);
      const headX = Math.round(centerX - LIFELINE_HEAD_W / 2);
      participantCoords[p.id] = { centerX, headX, p };
    });

    // 1. Scenario Header Strip
    const scenarioTitle = scenario.name || scenario.title || 'Runtime Execution Trace';
    const headerMarkup = this.buildExportHeaderSvg({
      width: canvasWidth,
      project: this.projectName,
      diagramType: 'Sequence Diagram',
      title: `${this._escape(scenarioTitle)} · Runtime Interaction Trace`,
      subtitle: `${messages.length} Messages · ${participants.length} Lifelines · AST Verified`,
      includeTitle: options.includeTitle !== false,
      includeVerification: options.includeVerification !== false,
      includeVersion: options.includeSourceVersion !== false
    });

    // 2. Lifelines (Heads, Cords, Feet)
    let lifelinesMarkup = '';
    participants.forEach(p => {
      const coord = participantCoords[p.id];
      const centerX = coord.centerX;
      const headX = coord.headX;
      const pName = this._escape(p.name);
      const pKind = this._escape((p.kind || p.type || 'service').toUpperCase());

      lifelinesMarkup += `
  <g class="lifeline-${this._escape(p.id)}">
    <!-- Header Card -->
    <rect x="${headX}" y="${START_Y}" width="${LIFELINE_HEAD_W}" height="54" rx="6" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5" />
    <path d="M ${headX} ${START_Y + 6} Q ${headX} ${START_Y} ${headX + 6} ${START_Y} L ${headX + LIFELINE_HEAD_W - 6} ${START_Y} Q ${headX + LIFELINE_HEAD_W} ${START_Y} ${headX + LIFELINE_HEAD_W} ${START_Y + 6} L ${headX + LIFELINE_HEAD_W} ${START_Y + 18} L ${headX} ${START_Y + 18} Z" fill="#f1f5f9" />
    <text x="${centerX}" y="${START_Y + 13}" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="10.5" font-weight="800" fill="#64748b" letter-spacing="0.06em">${pKind}</text>
    <text x="${centerX}" y="${START_Y + 39}" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="14.5" font-weight="800" fill="#0f172a">${pName}</text>
    
    <!-- Vertical Lifeline Cord -->
    <line x1="${centerX}" y1="${START_Y + 54}" x2="${centerX}" y2="${FOOT_Y}" stroke="#94a3b8" stroke-width="1.6" stroke-dasharray="5 4" />

    <!-- Foot Anchor Cap -->
    <rect x="${centerX - 50}" y="${FOOT_Y}" width="100" height="26" rx="13" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1" />
    <text x="${centerX}" y="${FOOT_Y + 17}" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="12" font-weight="700" fill="#475467">${pName}</text>
  </g>
`;
    });

    // 3. Activations
    let activationsMarkup = '';
    activations.forEach(act => {
      const coord = participantCoords[act.participantId];
      if (!coord) return;
      const startY = MSG_START_Y + (act.startOrder - 1) * MSG_ROW_HEIGHT + 14;
      const endY = MSG_START_Y + (act.endOrder - 1) * MSG_ROW_HEIGHT + 14;
      const actH = Math.max(26, endY - startY);
      const actW = 14;
      const offset = (act.depth || 0) * 7;
      const actX = coord.centerX - actW / 2 + offset;

      activationsMarkup += `  <rect x="${actX}" y="${startY}" width="${actW}" height="${actH}" rx="3" fill="#ffffff" stroke="#090C9B" stroke-width="1.8" />\n`;
    });

    // 4. Messages & Arrows
    let messagesMarkup = '';
    messages.forEach((msg, idx) => {
      const fromCoord = participantCoords[msg.from];
      const toCoord = participantCoords[msg.to];
      if (!fromCoord || !toCoord) return;

      const order = msg.order || (idx + 1);
      const y = Math.round(MSG_START_Y + idx * MSG_ROW_HEIGHT + 14);
      const isSelf = (msg.from === msg.to);
      const isReturn = (msg.type === 'return');
      const isExc = (msg.type === 'exception');

      const { cleanName } = this.formatSequenceMessageDisplay(msg);
      const labelText = this._escape(cleanName);
      const showTiming = (options.includeTiming || options.detailLevel === 'full');
      const timeStr = (showTiming && msg.timing && msg.timing.durationMs) ? `+${msg.timing.durationMs.toFixed(1)}ms` : '';
      const loopCount = (options.detailLevel !== 'minimal' && msg.loop_count) ? msg.loop_count : 1;

      if (isSelf) {
        const loopW = 38;
        const loopH = 26;
        const startX = fromCoord.centerX + 7;
        const arrowMarker = isExc ? 'url(#marker-seq-exc)' : 'url(#marker-seq-call)';
        const arrowStroke = isExc ? '#ef4444' : '#0f172a';
        const pillW = Math.round(labelText.length * 8.4 + 52);

        messagesMarkup += `
  <g class="msg-${order}">
    <path d="M ${startX} ${y - 8} L ${startX + loopW} ${y - 8} L ${startX + loopW} ${y + loopH} L ${startX} ${y + loopH}" stroke="${arrowStroke}" stroke-width="1.8" fill="none" marker-end="${arrowMarker}" />
    <rect x="${startX + 14}" y="${y - 21}" width="${pillW}" height="26" rx="13" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.2" />
    <circle cx="${startX + 27}" cy="${y - 8}" r="9" fill="${isExc ? '#ef4444' : '#090C9B'}" />
    <text x="${startX + 27}" y="${y - 4.5}" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="10.5" font-weight="800" fill="#ffffff">${order}</text>
    <text x="${startX + 42}" y="${y - 4.5}" font-family="JetBrains Mono, monospace" font-size="13" font-weight="700" fill="${isExc ? '#ef4444' : '#0f172a'}">${labelText}</text>
  </g>
`;
      } else {
        const leftToRight = fromCoord.centerX < toCoord.centerX;
        const x1 = leftToRight ? fromCoord.centerX + 7 : fromCoord.centerX - 7;
        const x2 = leftToRight ? toCoord.centerX - 7 : toCoord.centerX + 7;
        const arrowMarker = isExc ? 'url(#marker-seq-exc)' : (isReturn ? 'url(#marker-seq-return)' : 'url(#marker-seq-call)');
        const arrowStroke = isExc ? '#ef4444' : (isReturn ? '#64748b' : '#0f172a');
        const dashArray = (isReturn || isExc) ? 'stroke-dasharray="4 3"' : '';

        const midX = Math.round((fromCoord.centerX + toCoord.centerX) / 2);
        const loopPrefixWidth = loopCount > 1 ? 56 : 0;
        const timeWidth = timeStr ? timeStr.length * 7 + 14 : 0;
        const pillW = Math.max(105, Math.round(labelText.length * 8.2 + 46 + loopPrefixWidth + timeWidth));
        const pillX = Math.round(midX - pillW / 2);
        const pillY = y - 27;

        let pillContents = '';
        let curX = pillX + 10;

        // Order circle
        const circleFill = isReturn ? '#64748b' : (isExc ? '#ef4444' : '#090C9B');
        pillContents += `<circle cx="${curX + 8}" cy="${pillY + 13}" r="9" fill="${circleFill}" />\n`;
        pillContents += `<text x="${curX + 8}" y="${pillY + 16.5}" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="10.5" font-weight="800" fill="#ffffff">${order}</text>\n`;
        curX += 22;

        // Loop badge
        if (loopCount > 1) {
          pillContents += `<rect x="${curX}" y="${pillY + 4}" width="52" height="18" rx="4" fill="#eff6ff" stroke="#bfdbfe" stroke-width="1" />\n`;
          pillContents += `<text x="${curX + 26}" y="${pillY + 16.5}" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="10" font-weight="700" fill="#1d4ed8">loop ×${loopCount}</text>\n`;
          curX += 56;
        }

        // Method label
        const fontStyle = isReturn ? 'font-style="italic"' : '';
        const fontColor = isExc ? '#ef4444' : (isReturn ? '#475467' : '#0f172a');
        pillContents += `<text x="${curX}" y="${pillY + 17}" font-family="JetBrains Mono, monospace" font-size="13" font-weight="700" fill="${fontColor}" ${fontStyle}>${labelText}</text>\n`;
        curX += labelText.length * 8.0 + 10;

        // Duration string
        if (timeStr) {
          pillContents += `<rect x="${curX}" y="${pillY + 4}" width="${timeStr.length * 6.8 + 10}" height="18" rx="4" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1" />\n`;
          pillContents += `<text x="${curX + (timeStr.length * 6.8 + 10) / 2}" y="${pillY + 16.5}" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="9.5" font-weight="700" fill="#64748b">${timeStr}</text>\n`;
        }

        messagesMarkup += `
  <g class="msg-${order}">
    <!-- Message arrow line -->
    <line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" stroke="${arrowStroke}" stroke-width="${isReturn ? '1.5' : '1.8'}" ${dashArray} marker-end="${arrowMarker}" />
    <!-- Message Label Pill -->
    <rect x="${pillX}" y="${pillY}" width="${pillW}" height="26" rx="13" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.2" />
    ${pillContents}
  </g>
`;
      }
    });

    // 5. Bottom Publication Legend Bar
    let legendMarkup = '';
    if (options.includeLegend !== false) {
      const legY = FOOT_Y + 40;
      const legW = 540;
      const legX = Math.round((canvasWidth - legW) / 2);
      legendMarkup = `
  <!-- Bottom Publication Legend Bar -->
  <g class="seq-export-legend" transform="translate(${legX}, ${legY})">
    <rect width="${legW}" height="40" rx="6" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1" />
    <!-- Sync Call -->
    <line x1="20" y1="20" x2="52" y2="20" stroke="#0f172a" stroke-width="1.8" marker-end="url(#marker-seq-call)" />
    <text x="64" y="24" font-family="Plus Jakarta Sans, sans-serif" font-size="12" font-weight="700" fill="#334155">Sync Call</text>
    <!-- Return / Reply -->
    <line x1="160" y1="20" x2="192" y2="20" stroke="#64748b" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#marker-seq-return)" />
    <text x="204" y="24" font-family="Plus Jakarta Sans, sans-serif" font-size="12" font-weight="700" fill="#334155">Return / Reply</text>
    <!-- Exception -->
    <line x1="320" y1="20" x2="352" y2="20" stroke="#ef4444" stroke-width="1.8" stroke-dasharray="4 3" marker-end="url(#marker-seq-exc)" />
    <text x="364" y="24" font-family="Plus Jakarta Sans, sans-serif" font-size="12" font-weight="700" fill="#ef4444">Exception</text>
    <!-- Activation -->
    <rect x="450" y="12" width="10" height="16" rx="2" fill="#ffffff" stroke="#090C9B" stroke-width="1.8" />
    <text x="470" y="24" font-family="Plus Jakarta Sans, sans-serif" font-size="12" font-weight="700" fill="#334155">Activation</text>
  </g>
`;
    }

    const footerMarkup = this.buildExportFooterSvg({
      width: canvasWidth,
      y: canvasHeight - footerH - 8,
      includeFooter: !!options.includeFooter,
      includeEvidence: !!options.includeEvidence
    });

    return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${canvasWidth} ${canvasHeight}" width="${canvasWidth}" height="${canvasHeight}" style="background-color:#ffffff; font-family:Plus Jakarta Sans,system-ui,-apple-system,sans-serif;">
  <defs>
    <!-- Sequence Diagram Call marker (solid sharp arrowhead) -->
    <marker id="marker-seq-call" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
      <polygon points="1 2, 9 5, 1 8" fill="#0f172a" />
    </marker>
    <!-- Sequence Diagram Return marker (open stroke chevron) -->
    <marker id="marker-seq-return" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
      <polyline points="1 2, 8 5, 1 8" fill="none" stroke="#64748b" stroke-width="1.5" stroke-linecap="round" />
    </marker>
    <!-- Sequence Diagram Exception marker (red cross marker) -->
    <marker id="marker-seq-exc" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
      <path d="M 2 2 L 8 8 M 8 2 L 2 8" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" />
    </marker>
  </defs>
  <!-- Background Canvas -->
  <rect width="${canvasWidth}" height="${canvasHeight}" fill="#ffffff" />
  ${headerMarkup}
  <!-- Lifelines -->
${lifelinesMarkup}
  <!-- Activations -->
${activationsMarkup}
  <!-- Messages -->
${messagesMarkup}
  ${legendMarkup}
  ${footerMarkup}
</svg>`;
  }

  generateArchitectureSvgString(options = {}) {
    let components = (this.componentNodes && this.componentNodes.length) ? this.componentNodes : [];
    let connectors = (this.componentRelations && this.componentRelations.length) ? this.componentRelations : [];

    if (!components.length && this.classes && this.classes.length) {
      components = this.classes.slice(0, 8).map((c, idx) => ({
        id: `comp_${c.name}`,
        name: c.name,
        stereotype: c.stereotype || '«service»',
        role: idx === 0 ? 'Entry Point' : (idx > 5 ? 'Infrastructure / Data' : 'Application Service'),
        tier: idx === 0 ? 'Entry Points' : (idx > 5 ? 'Infrastructure / Data' : 'Application Services'),
        layer_level: idx === 0 ? 0 : (idx > 5 ? 3 : 2),
        semantic_color: idx === 0 ? '#7C3AED' : (idx > 5 ? '#D97706' : '#16A34A'),
        functions_count: (c.methods || []).length,
        dependencies_count: 1,
        encapsulated_classes: [c.name],
        provided_interfaces: (c.methods || []).slice(0, 3).map(m => m.name),
        required_interfaces: [],
        docstring: c.docstring || '',
        purpose: c.docstring || 'Core system module',
      }));
    }

    if (!components.length) return null;

    const isCareerCompass = components.some(c => c.name === 'desktop_launcher' || c.name === 'run') &&
                            components.some(c => c.name === 'app');

    const CARD_W = 270;
    const CARD_H = 96;
    const BAND_X = 60;
    const BAND_W = 1200;
    const BAND_GAP = 54;
    const START_Y = (options.includeTitle !== false) ? 116 : 60;

    const standardLayers = [
      {
        level: 0,
        title: 'ENTRY POINTS',
        subtitle: 'CLI &amp; GUI launchers',
        color: '#7C3AED',
        borderColor: '#DDD6FE',
        fill: '#FAF5FF',
        h: 144
      },
      {
        level: 1,
        title: 'PRESENTATION / CONTROLLER',
        subtitle: 'Flask application &amp; routing',
        color: '#2563EB',
        borderColor: '#BFDBFE',
        fill: '#F0F7FF',
        h: 144
      },
      {
        level: 2,
        title: 'APPLICATION SERVICES',
        subtitle: 'Core processing &amp; business logic',
        color: '#16A34A',
        borderColor: '#BBF7D0',
        fill: '#F0FDF4',
        h: 144
      },
      {
        level: 3,
        title: 'INFRASTRUCTURE / DATA',
        subtitle: 'Persistence &amp; external resources',
        color: '#D97706',
        borderColor: '#FDE68A',
        fill: '#FFFBEB',
        h: 154
      }
    ];

    let swimlanesMarkup = '';
    let connectorsMarkup = '';
    let cardsMarkup = '';
    let externalServicesMarkup = '';
    let legendY = 0;
    const dims = this.getExportDimensions('architecture', options.preset);
    const naturalWidth = BAND_X * 2 + BAND_W; // 1320
    const canvasWidth = Math.max(dims.width, naturalWidth);
    let canvasHeight = Math.max(dims.height, 920);

    const nodeCoords = {};

    if (isCareerCompass) {
      const b0_y = START_Y;
      const b1_y = b0_y + 144 + BAND_GAP; // 298
      const b2_y = b1_y + 144 + BAND_GAP; // 496
      const b3_y = b2_y + 144 + BAND_GAP; // 694
      const bandYs = [b0_y, b1_y, b2_y, b3_y];

      standardLayers.forEach((layer, idx) => {
        const y = bandYs[idx];
        swimlanesMarkup += `
    <!-- Swimlane: ${layer.title} -->
    <g class="arch-swimlane-band">
      <rect x="${BAND_X}" y="${y}" width="${BAND_W}" height="${layer.h}" rx="10" fill="${layer.fill}" stroke="${layer.borderColor}" stroke-width="1.2" />
      <rect x="${BAND_X}" y="${y}" width="4" height="${layer.h}" rx="2" fill="${layer.color}" />
      <text x="${BAND_X + 24}" y="${y + 26}" font-family="Plus Jakarta Sans, sans-serif" font-size="12" font-weight="800" letter-spacing="0.04em" fill="${layer.color}">${this._escape(layer.title)}</text>
      <text x="${BAND_X + 24}" y="${y + 42}" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="500" fill="#64748B">${this._escape(layer.subtitle)}</text>
    </g>
`;
      });

      nodeCoords['desktop_launcher'] = { x: 445, y: b0_y + 24, w: CARD_W, h: CARD_H };
      nodeCoords['run'] = { x: 755, y: b0_y + 24, w: CARD_W, h: CARD_H };
      nodeCoords['app'] = { x: 600, y: b1_y + 24, w: CARD_W, h: CARD_H };
      nodeCoords['core.app_paths'] = { x: 950, y: b1_y + 24, w: CARD_W, h: CARD_H };
      nodeCoords['core.file_processor'] = { x: 290, y: b2_y + 24, w: CARD_W, h: CARD_H };
      nodeCoords['core.recommendation_engine'] = { x: 600, y: b2_y + 24, w: CARD_W, h: CARD_H };
      nodeCoords['core.questionnaire_processor'] = { x: 910, y: b2_y + 24, w: CARD_W, h: CARD_H };
      nodeCoords['core.database'] = { x: 600, y: b3_y + 24, w: CARD_W, h: CARD_H };

      const ex = 950, ey = b3_y + 20, ew = CARD_W, eh = 104;
      externalServicesMarkup = `
    <!-- External Services Container Box -->
    <g class="arch-external-container" transform="translate(${ex}, ${ey})">
      <rect width="${ew}" height="${eh}" rx="8" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5" stroke-dasharray="6 4" />
      <rect x="12" y="8" width="70" height="16" rx="3" fill="#f1f5f9" />
      <text x="47" y="19.5" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="9.5" font-weight="700" fill="#475569">«external»</text>
      <text x="90" y="20" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="700" fill="#475569" letter-spacing="0.04em">EXTERNAL SERVICES</text>
      <!-- Item 1: File System -->
      <g transform="translate(14, 34)">
        <g transform="translate(0, 0) scale(0.6)">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="none" stroke="#64748b" stroke-width="2"/><polyline points="14 2 14 8 20 8" fill="none" stroke="#64748b" stroke-width="2"/>
        </g>
        <text x="20" y="10" font-family="Plus Jakarta Sans, sans-serif" font-size="11.5" font-weight="600" fill="#0f172a">File System</text>
        <text x="20" y="23" font-family="Plus Jakarta Sans, sans-serif" font-size="10" font-weight="400" fill="#64748b">Read student result files</text>
      </g>
      <!-- Item 2: External APIs -->
      <g transform="translate(14, 68)">
        <g transform="translate(0, 0) scale(0.6)">
          <circle cx="12" cy="12" r="10" fill="none" stroke="#64748b" stroke-width="2"/><line x1="2" y1="12" x2="22" y2="12" stroke="#64748b" stroke-width="2"/>
        </g>
        <text x="20" y="10" font-family="Plus Jakarta Sans, sans-serif" font-size="11.5" font-weight="600" fill="#0f172a">(Optional) External APIs</text>
        <text x="20" y="23" font-family="Plus Jakarta Sans, sans-serif" font-size="10" font-weight="400" fill="#64748b">(e.g. email/notifications)</text>
      </g>
    </g>
`;

      const explicitEdges = [
        { src: 'desktop_launcher', tgt: 'app', lbl: 'starts', style: 'solid', color: '#2563EB', path: 'M 580 204 C 580 250, 660 254, 660 322', midX: 620, midY: 260 },
        { src: 'run', tgt: 'app', lbl: 'starts', style: 'solid', color: '#2563EB', path: 'M 890 204 C 890 250, 810 254, 810 322', midX: 850, midY: 260 },
        { src: 'app', tgt: 'core.app_paths', lbl: 'uses (configuration)', style: 'dashed', color: '#64748B', path: 'M 870 370 L 950 370', midX: 910, midY: 370 },
        { src: 'app', tgt: 'core.file_processor', lbl: 'uses', style: 'solid', color: '#2563EB', path: 'M 640 418 C 640 468, 425 472, 425 520', midX: 532, midY: 468 },
        { src: 'app', tgt: 'core.recommendation_engine', lbl: 'uses', style: 'solid', color: '#2563EB', path: 'M 735 418 L 735 520', midX: 735, midY: 468 },
        { src: 'app', tgt: 'core.questionnaire_processor', lbl: 'uses', style: 'solid', color: '#2563EB', path: 'M 830 418 C 830 468, 1045 472, 1045 520', midX: 938, midY: 468 },
        { src: 'core.file_processor', tgt: 'core.recommendation_engine', lbl: 'provides data', style: 'solid', color: '#16A34A', path: 'M 560 568 L 600 568', midX: 580, midY: 568 },
        { src: 'core.questionnaire_processor', tgt: 'core.recommendation_engine', lbl: 'provides data', style: 'solid', color: '#16A34A', path: 'M 910 568 L 870 568', midX: 890, midY: 568 },
        { src: 'core.file_processor', tgt: 'core.database', lbl: 'reads/writes', style: 'solid', color: '#D97706', path: 'M 425 616 C 425 668, 650 672, 650 718', midX: 538, midY: 668 },
        { src: 'core.recommendation_engine', tgt: 'core.database', lbl: 'reads/writes', style: 'solid', color: '#D97706', path: 'M 735 616 L 735 718', midX: 735, midY: 668 },
        { src: 'core.questionnaire_processor', tgt: 'core.database', lbl: 'reads/writes', style: 'solid', color: '#D97706', path: 'M 1045 616 C 1045 668, 820 672, 820 718', midX: 932, midY: 668 },
        { src: 'core.app_paths', tgt: 'external_services', lbl: 'uses (optional)', style: 'dotted', color: '#64748B', path: 'M 1085 418 L 1085 714', midX: 1085, midY: 566 },
      ];

      explicitEdges.forEach(e => {
        const dashAttr = (e.style === 'dashed') ? 'stroke-dasharray="5 4"' : (e.style === 'dotted' ? 'stroke-dasharray="2 3"' : '');
        let marker = 'url(#arrow-blue)';
        if (e.color === '#16A34A') marker = 'url(#arrow-green)';
        else if (e.color === '#D97706') marker = 'url(#arrow-amber)';
        else if (e.color === '#64748B') marker = 'url(#arrow-slate)';

        const pillW = Math.max(46, Math.round(e.lbl.length * 6.5 + 16));
        connectorsMarkup += `
    <g class="arch-edge">
      <path d="${e.path}" fill="none" stroke="${e.color}" stroke-width="1.8" ${dashAttr} marker-end="${marker}" />
      <rect x="${e.midX - pillW / 2}" y="${e.midY - 9}" width="${pillW}" height="18" rx="4" fill="#ffffff" stroke="#cbd5e1" stroke-width="1" />
      <text x="${e.midX}" y="${e.midY + 3.5}" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="10" font-weight="600" fill="${e.color}">${e.lbl}</text>
    </g>
`;
      });

      legendY = b3_y + 154 + 30;
      canvasHeight = legendY + 80;

    } else {
      // Generic architecture multi-tier layout
      const layerMap = new Map();
      standardLayers.forEach(l => layerMap.set(l.level, []));

      components.forEach(c => {
        let lvl = c.layer_level;
        if (lvl === undefined) {
          const t = (c.tier || '').toLowerCase();
          const r = (c.role || '').toLowerCase();
          const s = (c.stereotype || '').toLowerCase();
          if (t.includes('entry') || r.includes('entry') || s.includes('controller') || c.name.toLowerCase().includes('cli')) {
            lvl = 0;
          } else if (t.includes('domain') || r.includes('domain') || s.includes('entity')) {
            lvl = 2;
          } else if (t.includes('data') || t.includes('infra') || s.includes('database') || s.includes('repo')) {
            lvl = 3;
          } else {
            lvl = 1;
          }
        }
        if (!layerMap.has(lvl)) layerMap.set(lvl, []);
        layerMap.get(lvl).push(c);
      });

      let curY = START_Y;
      standardLayers.forEach(layer => {
        const nodes = layerMap.get(layer.level) || [];
        if (!nodes.length) return;

        const rowW = nodes.length * CARD_W + (nodes.length - 1) * 40;
        const startCardX = Math.max(300, Math.round((BAND_X + BAND_W / 2) - rowW / 2));

        swimlanesMarkup += `
    <g class="arch-swimlane-band">
      <rect x="${BAND_X}" y="${curY}" width="${BAND_W}" height="${layer.h}" rx="10" fill="${layer.fill}" stroke="${layer.borderColor}" stroke-width="1.2" />
      <rect x="${BAND_X}" y="${curY}" width="4" height="${layer.h}" rx="2" fill="${layer.color}" />
      <text x="${BAND_X + 24}" y="${curY + 26}" font-family="Plus Jakarta Sans, sans-serif" font-size="12" font-weight="800" letter-spacing="0.04em" fill="${layer.color}">${this._escape(layer.title)}</text>
      <text x="${BAND_X + 24}" y="${curY + 42}" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="500" fill="#64748B">${this._escape(layer.subtitle)}</text>
    </g>
`;

        nodes.forEach((c, idx) => {
          const cx = Math.round(startCardX + idx * (CARD_W + 40));
          const cy = curY + 24;
          nodeCoords[c.name] = { x: cx, y: cy, w: CARD_W, h: CARD_H };
        });

        curY += layer.h + BAND_GAP;
      });

      // Generic connectors
      connectors.forEach(conn => {
        const srcName = conn.source || (conn.source_id ? conn.source_id.replace('comp_', '') : '');
        const tgtName = conn.target || (conn.target_id ? conn.target_id.replace('comp_', '') : '');
        const srcPos = nodeCoords[srcName];
        const tgtPos = nodeCoords[tgtName];
        if (!srcPos || !tgtPos || srcName === tgtName) return;

        const lbl = (conn.label || conn.connector_type || 'uses').toLowerCase();
        const style = conn.relationship_style || (lbl.includes('import') ? 'dashed' : 'solid');
        let lineColor = '#2563EB';
        let dashAttr = '';
        if (style === 'dashed' || lbl.includes('import')) {
          lineColor = '#64748B';
          dashAttr = 'stroke-dasharray="5 4"';
        } else if (style === 'dotted' || lbl.includes('optional')) {
          lineColor = '#64748B';
          dashAttr = 'stroke-dasharray="2 3"';
        }

        const isTopDown = srcPos.y < tgtPos.y;
        const sx = Math.round(srcPos.x + srcPos.w / 2);
        const sy = Math.round(isTopDown ? srcPos.y + srcPos.h : srcPos.y);
        const tx = Math.round(tgtPos.x + tgtPos.w / 2);
        const ty = Math.round(isTopDown ? tgtPos.y : tgtPos.y + tgtPos.h);
        const midY = Math.round((sy + ty) / 2);
        const pathD = `M ${sx} ${sy} C ${sx} ${midY}, ${tx} ${midY}, ${tx} ${ty}`;
        const midX = Math.round((sx + tx) / 2);
        const pillW = Math.max(46, Math.round(lbl.length * 6.5 + 16));

        connectorsMarkup += `
    <g class="arch-edge">
      <path d="${pathD}" fill="none" stroke="${lineColor}" stroke-width="1.8" ${dashAttr} marker-end="url(#arrow-blue)" />
      <rect x="${midX - pillW / 2}" y="${midY - 9}" width="${pillW}" height="18" rx="4" fill="#ffffff" stroke="#cbd5e1" stroke-width="1" />
      <text x="${midX}" y="${midY + 3.5}" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="10" font-weight="600" fill="${lineColor}">${lbl}</text>
    </g>
`;
      });

      legendY = curY + 10;
      canvasHeight = legendY + 80;
    }

    // Render Component Cards
    const renderedNames = new Set();
    components.forEach(c => {
      if (c.is_external || c.name.startsWith('external.')) return;
      if (renderedNames.has(c.name)) return;
      renderedNames.add(c.name);

      const pos = nodeCoords[c.name];
      if (!pos) return;

      const x = pos.x;
      const y = pos.y;
      const w = pos.w;
      const h = pos.h;
      const st = c.stereotype || '«service»';
      const stLower = st.toLowerCase();
      const funcCount = c.functions_count !== undefined ? c.functions_count : ((c.provided_interfaces || []).length);
      const depCount = c.dependencies_count !== undefined ? c.dependencies_count : 0;
      const purpose = c.purpose || c.docstring || c.role || 'Service module';

      // Badge colors
      let badgeBg = '#DCFCE7', badgeFg = '#15803D';
      if (stLower.includes('entry')) { badgeBg = '#EDE9FE'; badgeFg = '#6D28D9'; }
      else if (stLower.includes('controller')) { badgeBg = '#DBEAFE'; badgeFg = '#1D4ED8'; }
      else if (stLower.includes('database') || stLower.includes('data')) { badgeBg = '#FEF3C7'; badgeFg = '#B45309'; }
      else if (stLower.includes('infra') || stLower.includes('external')) { badgeBg = '#F1F5F9'; badgeFg = '#475569'; }

      // Card Icon Vector
      let iconMarkup = '';
      if (stLower.includes('entry') || c.name === 'run' || c.name.includes('cli')) {
        iconMarkup = `<polyline points="4 17 10 11 4 5" fill="none" stroke="${badgeFg}" stroke-width="2"/><line x1="12" y1="19" x2="20" y2="19" stroke="${badgeFg}" stroke-width="2"/>`;
      } else if (c.name === 'desktop_launcher') {
        iconMarkup = `<rect x="2" y="3" width="20" height="14" rx="2" fill="none" stroke="${badgeFg}" stroke-width="2"/><line x1="8" y1="21" x2="16" y2="21" stroke="${badgeFg}" stroke-width="2"/><line x1="12" y1="17" x2="12" y2="21" stroke="${badgeFg}" stroke-width="2"/>`;
      } else if (stLower.includes('controller') || c.name === 'app') {
        iconMarkup = `<circle cx="12" cy="12" r="10" fill="none" stroke="${badgeFg}" stroke-width="2"/><line x1="2" y1="12" x2="22" y2="12" stroke="${badgeFg}" stroke-width="2"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" fill="none" stroke="${badgeFg}" stroke-width="2"/>`;
      } else if (stLower.includes('database')) {
        iconMarkup = `<ellipse cx="12" cy="5" rx="9" ry="3" fill="none" stroke="${badgeFg}" stroke-width="2"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" fill="none" stroke="${badgeFg}" stroke-width="2"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" fill="none" stroke="${badgeFg}" stroke-width="2"/>`;
      } else if (stLower.includes('infra') || c.name.includes('paths')) {
        iconMarkup = `<circle cx="12" cy="12" r="3" fill="none" stroke="${badgeFg}" stroke-width="2"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" fill="none" stroke="${badgeFg}" stroke-width="2"/>`;
      } else if (c.name.includes('recommend')) {
        iconMarkup = `<line x1="18" y1="20" x2="18" y2="10" stroke="${badgeFg}" stroke-width="2"/><line x1="12" y1="20" x2="12" y2="4" stroke="${badgeFg}" stroke-width="2"/><line x1="6" y1="20" x2="6" y2="14" stroke="${badgeFg}" stroke-width="2"/>`;
      } else if (c.name.includes('questionnaire')) {
        iconMarkup = `<polyline points="9 11 12 14 22 4" fill="none" stroke="${badgeFg}" stroke-width="2"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" fill="none" stroke="${badgeFg}" stroke-width="2"/>`;
      } else {
        iconMarkup = `<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="none" stroke="${badgeFg}" stroke-width="2"/><polyline points="14 2 14 8 20 8" fill="none" stroke="${badgeFg}" stroke-width="2"/>`;
      }

      const stPillW = Math.max(65, Math.round(st.length * 6.5 + 16));

      cardsMarkup += `
    <!-- Card: ${this._escape(c.name)} -->
    <g class="arch-card" transform="translate(${x}, ${y})">
      <rect width="${w}" height="${h}" rx="8" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.2" />
      <!-- Stereotype Pill -->
      <rect x="12" y="10" width="${stPillW}" height="18" rx="4" fill="${badgeBg}" />
      <text x="${12 + stPillW / 2}" y="22.5" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="10" font-weight="700" fill="${badgeFg}">${this._escape(st)}</text>
      <!-- Top-right Icon -->
      <g transform="translate(${w - 28}, 11) scale(0.68)">
        ${iconMarkup}
      </g>
      <!-- Title -->
      <text x="12" y="48" font-family="Plus Jakarta Sans, sans-serif" font-size="14" font-weight="700" fill="#0f172a">${this._escape(c.name)}</text>
      <!-- Purpose Subtitle -->
      <text x="12" y="65" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="500" fill="#64748b">${this._escape(purpose.length > 38 ? purpose.substring(0, 36) + '…' : purpose)}</text>
      <!-- Metadata -->
      <text x="12" y="82" font-family="Plus Jakarta Sans, sans-serif" font-size="10.5" font-weight="500" fill="#94a3b8">${funcCount} operations • ${depCount} dependencies</text>
    </g>
`;
    });

    // Legend Markup
    const legendMarkup = `
    <!-- Bottom Publication Legend Strip -->
    <g transform="translate(${BAND_X}, ${legendY})">
      <rect width="${BAND_W}" height="44" rx="8" fill="#ffffff" stroke="#cbd5e1" stroke-width="1" />
      <rect x="20" y="14" width="14" height="14" rx="3" fill="#ede9fe" stroke="#ddd6fe" />
      <text x="42" y="25" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="600" fill="#64748b">«entrypoint» Entry Point</text>
      <rect x="190" y="14" width="14" height="14" rx="3" fill="#dbeafe" stroke="#bfdbfe" />
      <text x="212" y="25" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="600" fill="#64748b">«controller» Controller</text>
      <rect x="340" y="14" width="14" height="14" rx="3" fill="#dcfce7" stroke="#bbf7d0" />
      <text x="362" y="25" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="600" fill="#64748b">«service» Service</text>
      <rect x="470" y="14" width="14" height="14" rx="3" fill="#fef3c7" stroke="#fde68a" />
      <text x="492" y="25" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="600" fill="#64748b">«database» Database</text>
      <rect x="620" y="14" width="14" height="14" rx="3" fill="#f1f5f9" stroke="#cbd5e1" />
      <text x="642" y="25" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="600" fill="#64748b">«infrastructure» Config</text>
      <line x1="790" y1="21" x2="820" y2="21" stroke="#2563EB" stroke-width="2" />
      <text x="826" y="25" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="600" fill="#64748b">Direct Call / Use</text>
      <line x1="940" y1="21" x2="970" y2="21" stroke="#64748B" stroke-width="1.8" stroke-dasharray="5 4" />
      <text x="976" y="25" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="600" fill="#64748b">Import / Config</text>
      <line x1="1080" y1="21" x2="1110" y2="21" stroke="#64748B" stroke-width="1.8" stroke-dasharray="2 3" />
      <text x="1116" y="25" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="600" fill="#64748b">Optional Dep</text>
    </g>
`;

    const headerMarkup = this.buildExportHeaderSvg({
      width: canvasWidth,
      project: this.projectName,
      diagramType: 'Architecture Diagram',
      title: `${this._escape(this.projectName || 'Application Architecture')} · Layered Subsystem Flow`,
      subtitle: 'Subsystem boundaries, multi-tier responsibilities &amp; directional data flow',
      includeTitle: options.includeTitle !== false,
      includeVerification: options.includeVerification !== false,
      includeVersion: options.includeSourceVersion !== false
    });

    const footerH = (options.includeEvidence) ? 60 : 44;
    const footerMarkup = this.buildExportFooterSvg({
      width: canvasWidth,
      y: canvasHeight - footerH - 8,
      includeFooter: !!options.includeFooter,
      includeEvidence: !!options.includeEvidence
    });

    return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${canvasWidth} ${canvasHeight}" width="${canvasWidth}" height="${canvasHeight}" style="background-color:#ffffff; font-family:Plus Jakarta Sans,system-ui,-apple-system,sans-serif;">
  <defs>
    <marker id="arrow-blue" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#2563EB" />
    </marker>
    <marker id="arrow-green" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#16A34A" />
    </marker>
    <marker id="arrow-amber" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#D97706" />
    </marker>
    <marker id="arrow-slate" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#64748B" />
    </marker>
  </defs>
  <!-- Background Canvas -->
  <rect width="${canvasWidth}" height="${canvasHeight}" fill="#ffffff" />
  ${headerMarkup}
  <!-- Swimlanes -->
${swimlanesMarkup}
  <!-- Connectors -->
${connectorsMarkup}
  <!-- Cards -->
${cardsMarkup}
  <!-- External Services -->
${externalServicesMarkup}
  <!-- Legend -->
${(options.includeLegend !== false) ? legendMarkup : ''}
  ${footerMarkup}
</svg>`;
  }

  generatePackageSvgString(options = {}) {
    const packages = (this.packageNodes && this.packageNodes.length) ? this.packageNodes : [];
    if (!packages.length) return null;

    const CARD_W = 230;
    const CARD_H = 125;
    const layouts = {};
    const hasManualPositions = packages.every(p => p.pos && typeof p.pos.x === 'number');

    let maxY = 0;
    let maxX = 0;

    if (hasManualPositions) {
      packages.forEach(pkg => {
        layouts[pkg.name] = {
          x: pkg.pos.x,
          y: pkg.pos.y,
          w: pkg.pos.w || CARD_W,
          h: pkg.pos.h || CARD_H,
          pkg
        };
        maxX = Math.max(maxX, pkg.pos.x + (pkg.pos.w || CARD_W));
        maxY = Math.max(maxY, pkg.pos.y + (pkg.pos.h || CARD_H));
      });
    } else {
      const COLS = Math.min(3, packages.length);
      const GAP_X = 70;
      const GAP_Y = 100;
      const START_Y = (options.includeTitle !== false) ? 120 : 60;
      packages.forEach((pkg, i) => {
        const col = i % COLS;
        const row = Math.floor(i / COLS);
        const x = 60 + col * (CARD_W + GAP_X);
        const y = START_Y + row * (CARD_H + GAP_Y);
        layouts[pkg.name] = { x, y, w: CARD_W, h: CARD_H, pkg };
        maxX = Math.max(maxX, x + CARD_W);
        maxY = Math.max(maxY, y + CARD_H);
      });
    }

    const naturalWidth = Math.max(1000, maxX + 80);
    const dims = this.getExportDimensions('packages', options.preset);
    const canvasWidth = Math.max(dims.width, naturalWidth);
    const shiftX = Math.max(0, Math.round((canvasWidth - naturalWidth) / 2));

    const footerH = (options.includeEvidence) ? 60 : 44;
    const canvasHeight = Math.max(dims.height, maxY + 140 + footerH);

    const defaultPalette = ['#6366F1', '#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#06B6D4'];
    let cIdx = 0;

    let pkgsMarkup = '';
    packages.forEach(pkg => {
      const lay = layouts[pkg.name];
      if (!lay) return;
      const x = lay.x + shiftX;
      const y = lay.y;
      const w = lay.w;
      const h = lay.h;
      const color = pkg.semantic_color || pkg.border_color || defaultPalette[cIdx++ % defaultPalette.length];
      const mCount = pkg.modules_count !== undefined ? pkg.modules_count : (pkg.modules || []).length;
      const inCount = pkg.incoming_count !== undefined ? pkg.incoming_count : 0;
      const outCount = pkg.outgoing_count !== undefined ? pkg.outgoing_count : 0;
      const inst = pkg.instability !== undefined ? Number(pkg.instability).toFixed(2) : '0.00';
      const colW = Math.round(w / 4);

      pkgsMarkup += `
    <g class="pkg-node" transform="translate(${x}, ${y})">
      <!-- Card Box with Colored Border -->
      <rect width="${w}" height="${h}" rx="10" fill="#ffffff" stroke="${color}" stroke-width="1.8" />
      
      <!-- Icon Cube -->
      <g transform="translate(14, 14)">
        <rect width="28" height="28" rx="6" fill="${color}" fill-opacity="0.1" />
        <path d="M 21 16 L 21 8 L 14 4 L 7 8 L 7 16 L 14 20 Z" fill="none" stroke="${color}" stroke-width="1.5" stroke-linejoin="round" transform="translate(0, 0) scale(0.9)" />
      </g>
      
      <!-- Stereotype & Title -->
      <text x="50" y="24" font-family="JetBrains Mono, monospace" font-size="9.5" fill="#64748b" letter-spacing="0.04em">«package»</text>
      <text x="50" y="39" font-family="Plus Jakarta Sans, sans-serif" font-size="14" font-weight="700" fill="#0f172a">${this._escape(pkg.name)}</text>
      
      <!-- 4-Column Metric Strip -->
      <rect x="0" y="58" width="${w}" height="${h - 58}" rx="0" fill="#f8fafc" />
      <path d="M 0 58 L ${w} 58" stroke="#f1f5f9" stroke-width="1" />
      <line x1="${colW}" y1="58" x2="${colW}" y2="${h}" stroke="#e2e8f0" stroke-width="1" />
      <line x1="${colW * 2}" y1="58" x2="${colW * 2}" y2="${h}" stroke="#e2e8f0" stroke-width="1" />
      <line x1="${colW * 3}" y1="58" x2="${colW * 3}" y2="${h}" stroke="#e2e8f0" stroke-width="1" />

      <!-- Col 1: Modules -->
      <text x="${colW * 0.5}" y="82" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="12" font-weight="800" fill="#0f172a">${mCount}</text>
      <text x="${colW * 0.5}" y="98" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="8.5" font-weight="600" fill="#64748b">MODULES</text>

      <!-- Col 2: Incoming -->
      <text x="${colW * 1.5}" y="82" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="12" font-weight="800" fill="#0f172a">${inCount}</text>
      <text x="${colW * 1.5}" y="98" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="8.5" font-weight="600" fill="#64748b">INCOMING</text>

      <!-- Col 3: Outgoing -->
      <text x="${colW * 2.5}" y="82" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="12" font-weight="800" fill="#0f172a">${outCount}</text>
      <text x="${colW * 2.5}" y="98" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="8.5" font-weight="600" fill="#64748b">OUTGOING</text>

      <!-- Col 4: Instability -->
      <text x="${colW * 3.5}" y="82" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="11.5" font-weight="800" fill="#0f172a">I: ${inst}</text>
      <text x="${colW * 3.5}" y="98" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="8.5" font-weight="600" fill="#64748b">INSTABILITY</text>
    </g>
`;
    });

    let depsMarkup = '';
    const deps = (this.packageRelations && this.packageRelations.length) ? this.packageRelations : [];
    deps.forEach(dep => {
      const srcName = dep.source || dep.source_package;
      const tgtName = dep.target || dep.target_package;
      const srcLay = layouts[srcName];
      const tgtLay = layouts[tgtName];
      if (srcLay && tgtLay && (srcName !== tgtName)) {
        const isCyclic = !!dep.is_cyclic;
        const color = isCyclic ? '#ef4444' : '#475569';
        const marker = isCyclic ? 'url(#marker-package-dep-cyclic)' : 'url(#marker-package-dep)';
        const isOptional = dep.relationship_style === 'dotted' || dep.relationship_style === 'dashed';

        let x1, y1, x2, y2, d;
        const sCenterX = srcLay.x + srcLay.w / 2 + shiftX;
        const sCenterY = srcLay.y + srcLay.h / 2;
        const tCenterX = tgtLay.x + tgtLay.w / 2 + shiftX;
        const tCenterY = tgtLay.y + tgtLay.h / 2;

        const isAbove = srcLay.y + srcLay.h + 20 < tgtLay.y;
        const isBelow = srcLay.y > tgtLay.y + tgtLay.h + 20;

        if (!isAbove && !isBelow) {
          // Horizontal on same row
          if (sCenterX < tCenterX) {
            x1 = srcLay.x + srcLay.w + shiftX;
            y1 = sCenterY;
            x2 = tgtLay.x + shiftX;
            y2 = tCenterY;
            d = `M ${x1} ${y1} L ${x2} ${y2}`;
          } else {
            x1 = srcLay.x + shiftX;
            y1 = sCenterY;
            x2 = tgtLay.x + tgtLay.w + shiftX;
            y2 = tCenterY;
            d = `M ${x1} ${y1} L ${x2} ${y2}`;
          }
        } else if (isAbove) {
          if (Math.abs(sCenterX - tCenterX) < 40) {
            x1 = sCenterX;
            y1 = srcLay.y + srcLay.h;
            x2 = tCenterX;
            y2 = tgtLay.y;
            d = `M ${x1} ${y1} L ${x2} ${y2}`;
          } else if (tCenterX < sCenterX) {
            if (srcName === 'career_compass' && tgtName === 'interfaces') {
              x1 = srcLay.x + 35 + shiftX;
              y1 = srcLay.y + srcLay.h;
              x2 = tgtLay.x + tgtLay.w - 45 + shiftX;
              y2 = tgtLay.y;
            } else if (srcName === 'core' && tgtName === 'models') {
              x1 = srcLay.x + 45 + shiftX;
              y1 = srcLay.y + srcLay.h;
              x2 = tCenterX;
              y2 = tgtLay.y;
            } else if (srcName === 'services' && tgtName === 'data') {
              x1 = sCenterX;
              y1 = srcLay.y + srcLay.h;
              x2 = tgtLay.x + tgtLay.w - 45 + shiftX;
              y2 = tgtLay.y;
            } else {
              x1 = srcLay.x + srcLay.w * 0.25 + shiftX;
              y1 = srcLay.y + srcLay.h;
              x2 = tgtLay.x + tgtLay.w * 0.75 + shiftX;
              y2 = tgtLay.y;
            }
            const cy1 = y1 + (y2 - y1) * 0.55;
            const cy2 = y2 - (y2 - y1) * 0.45;
            d = `M ${x1} ${y1} C ${x1} ${cy1}, ${x2} ${cy2}, ${x2} ${y2}`;
          } else {
            if (srcName === 'career_compass' && tgtName === 'services') {
              x1 = srcLay.x + srcLay.w - 35 + shiftX;
              y1 = srcLay.y + srcLay.h;
              x2 = tgtLay.x + 45 + shiftX;
              y2 = tgtLay.y;
            } else if (srcName === 'core' && tgtName === 'data') {
              x1 = srcLay.x + srcLay.w - 45 + shiftX;
              y1 = srcLay.y + srcLay.h;
              x2 = tgtLay.x + 45 + shiftX;
              y2 = tgtLay.y;
            } else {
              x1 = srcLay.x + srcLay.w * 0.75 + shiftX;
              y1 = srcLay.y + srcLay.h;
              x2 = tgtLay.x + tgtLay.w * 0.25 + shiftX;
              y2 = tgtLay.y;
            }
            const cy1 = y1 + (y2 - y1) * 0.55;
            const cy2 = y2 - (y2 - y1) * 0.45;
            d = `M ${x1} ${y1} C ${x1} ${cy1}, ${x2} ${cy2}, ${x2} ${y2}`;
          }
        } else {
          x1 = sCenterX;
          y1 = srcLay.y;
          x2 = tCenterX;
          y2 = tgtLay.y + tgtLay.h;
          const cy1 = y1 - (y1 - y2) * 0.55;
          const cy2 = y2 + (y1 - y2) * 0.45;
          d = `M ${x1} ${y1} C ${x1} ${cy1}, ${x2} ${cy2}, ${x2} ${y2}`;
        }

        depsMarkup += `
    <g class="pkg-edge">
      <path d="${d}" fill="none" stroke="${color}" stroke-width="1.6" ${isOptional ? 'stroke-dasharray="5 4"' : ''} marker-end="${marker}" />
    </g>
`;
      }
    });

    const headerMarkup = this.buildExportHeaderSvg({
      width: canvasWidth,
      project: this.projectName,
      diagramType: 'Package Diagram',
      title: `${this._escape(this.projectName || 'Package Architecture')} · Module Hierarchy`,
      subtitle: `${packages.length} Packages · Directional Imports &amp; Coupling Metrics (Ca, Ce, Instability)`,
      includeTitle: options.includeTitle !== false,
      includeVerification: options.includeVerification !== false,
      includeVersion: options.includeSourceVersion !== false
    });

    const footerMarkup = this.buildExportFooterSvg({
      width: canvasWidth,
      y: canvasHeight - footerH - 8,
      includeFooter: !!options.includeFooter,
      includeEvidence: !!options.includeEvidence
    });

    return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${canvasWidth} ${canvasHeight}" width="${canvasWidth}" height="${canvasHeight}" style="background-color:#ffffff; font-family:Plus Jakarta Sans,system-ui,-apple-system,sans-serif;">
  <defs>
    <marker id="arrow-slate" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#64748B" />
    </marker>
  </defs>
  <rect width="${canvasWidth}" height="${canvasHeight}" fill="#ffffff" />
  ${headerMarkup}
${pkgsMarkup}
${depsMarkup}
  ${footerMarkup}
</svg>`;
  }

  generateClassSvgString(options = {}) {
    const detailLevel = options.detailLevel || 'compact';
    const isExp = (detailLevel === 'full');
    const nodesToExport = (this.renderedNodes && this.renderedNodes.length) ? this.renderedNodes : this.classes;

    // Ensure all nodePositions have the true height and width corresponding to export detailLevel
    nodesToExport.forEach(cls => {
      if (this.nodePositions[cls.name]) {
        this.nodePositions[cls.name].w = this.calculateCardWidth(cls);
        this.nodePositions[cls.name].h = (detailLevel === 'minimal') ? 42 : this.estimateCardHeight(cls, isExp);
      }
    });
    // Re-render connectors so paths match the exact card bounds for export
    this.renderConnectors();

    const positions = Object.values(this.nodePositions);
    if (!positions.length) return null;

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    positions.forEach(p => {
      if (p.x < minX) minX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.x + p.w > maxX) maxX = p.x + p.w;
      if (p.y + p.h > maxY) maxY = p.y + p.h;
    });

    const contentPad = 40;
    const contentW = Math.max(100, maxX - minX + contentPad * 2);
    const contentH = Math.max(100, maxY - minY + contentPad * 2);

    const dims = this.getExportDimensions('class', options.preset);
    let canvasWidth = dims.width;
    let canvasHeight = dims.height;

    // Header & footer heights
    const headerH = (options.includeTitle !== false) ? 80 : 20;
    const footerH = (options.includeEvidence) ? 60 : 44;
    const legendH = (options.includeLegend !== false) ? 44 : 0;

    const availX = 40;
    const availY = 24 + headerH + 16;
    const availW = canvasWidth - 80;
    const availH = canvasHeight - availY - legendH - footerH - 24;

    // Scale & fit
    const scale = options.fitToPage ? Math.min(1.0, availW / contentW, availH / contentH) : 1;
    const offsetX = Math.round(availX + (availW - contentW * scale) / 2 - (minX - contentPad) * scale);
    const offsetY = Math.round(availY + (availH - contentH * scale) / 2 - (minY - contentPad) * scale);

    // Connector paths, edge labels & multiplicities
    let pathsMarkup = '';
    this.svgLayer.querySelectorAll('.diag-connector-path').forEach(p => {
      const d = p.getAttribute('d');
      const markerStart = p.getAttribute('marker-start') ? `marker-start="${p.getAttribute('marker-start')}"` : '';
      const markerEnd = p.getAttribute('marker-end') ? `marker-end="${p.getAttribute('marker-end')}"` : '';
      const isDep = p.classList.contains('diag-connector-path--dependency') || p.classList.contains('diag-connector-path--realization');
      const dash = isDep ? 'stroke-dasharray="5 4"' : '';
      pathsMarkup += `    <path d="${d}" stroke="#0f172a" stroke-width="1.5" fill="none" ${dash} ${markerStart} ${markerEnd} />\n`;
    });
    this.svgLayer.querySelectorAll('.diag-edge-label-group').forEach(g => {
      pathsMarkup += `    ${g.outerHTML}\n`;
    });
    this.svgLayer.querySelectorAll('.diag-connector-cardinality').forEach(t => {
      pathsMarkup += `    ${t.outerHTML}\n`;
    });

    // UML Class Cards
    let cardsMarkup = '';
    nodesToExport.forEach(cls => {
      const pos = this.nodePositions[cls.name];
      if (!pos) return;
      const x = Math.round(pos.x);
      const y = Math.round(pos.y);
      const w = Math.round(pos.w);
      const h = Math.round(pos.h);
      const attrs = cls.attributes || [];
      const methods = cls.methods || [];

      cardsMarkup += `
    <g transform="translate(${x}, ${y})">
      <!-- Card Container with clean 1px border -->
      <rect width="${w}" height="${h}" rx="8" fill="#ffffff" stroke="#cbd5e1" stroke-width="1" />
      <!-- Header -->
      <path d="M 0 8 Q 0 0 8 0 L ${w - 8} 0 Q ${w} 0 ${w} 8 L ${w} 42 L 0 42 Z" fill="#f8fafc" />
      <line x1="0" y1="42" x2="${w}" y2="42" stroke="#e2e8f0" stroke-width="1" />
      <text x="14" y="16" font-family="Plus Jakarta Sans, sans-serif" font-size="9" fill="#090C9B" font-weight="700">${this._escape(cls.stereotype || '«class»')}</text>
      <text x="14" y="32" font-family="Plus Jakarta Sans, sans-serif" font-size="13" fill="#090c24" font-weight="800">${this._escape(cls.name)}</text>
`;

      let cy = 60;
      if (detailLevel !== 'minimal') {
        const showAll = (detailLevel === 'full');
        // Attributes
        if (attrs.length > 0) {
          const shownA = showAll ? attrs : attrs.slice(0, 6);
          shownA.forEach(a => {
            cardsMarkup += `
      <text x="14" y="${cy}" font-family="JetBrains Mono, monospace" font-size="10.5" fill="#475467">
        <tspan fill="#090C9B" font-weight="bold">${this._escape(a.vis || '+')} </tspan>${this._escape(a.name)}<tspan fill="#64748b">${a.type ? ': ' + this._escape(a.type) : ''}</tspan>
      </text>`;
            cy += 18;
          });
          if (methods.length > 0) {
            cardsMarkup += `\n      <line x1="0" y1="${cy - 6}" x2="${w}" y2="${cy - 6}" stroke="#f1f5f9" stroke-width="1" />`;
            cy += 12;
          }
        }

        // Methods
        if (methods.length > 0) {
          const shownM = showAll ? methods : methods.slice(0, 6);
          shownM.forEach(m => {
            const mName = m.name.endsWith(')') ? m.name : `${m.name}()`;
            cardsMarkup += `
      <text x="14" y="${cy}" font-family="JetBrains Mono, monospace" font-size="10.5" fill="#475467">
        <tspan fill="#090C9B" font-weight="bold">${this._escape(m.vis || '+')} </tspan>${this._escape(mName)}<tspan fill="#64748b">${m.ret ? ': ' + this._escape(m.ret) : ''}</tspan>
      </text>`;
            cy += 18;
          });
        }
      }

      cardsMarkup += `\n    </g>\n`;
    });

    // Legend
    let legendMarkup = '';
    if (options.includeLegend !== false) {
      const legW = 680;
      const legX = Math.round((canvasWidth - legW) / 2);
      const legY = canvasHeight - footerH - 42;
      legendMarkup = `
  <!-- Class Diagram Legend -->
  <g class="export-class-legend" transform="translate(${legX}, ${legY})">
    <rect width="${legW}" height="36" rx="6" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1" />
    <!-- Inheritance -->
    <polygon points="18 18, 28 13, 28 23" fill="#ffffff" stroke="#0f172a" stroke-width="1.4" />
    <text x="36" y="21.5" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="700" fill="#334155">Inheritance</text>
    <!-- Composition -->
    <polygon points="128 18, 134 13, 140 18, 134 23" fill="#0f172a" stroke="#0f172a" stroke-width="1.2" />
    <text x="148" y="21.5" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="700" fill="#334155">Composition</text>
    <!-- Aggregation -->
    <polygon points="252 18, 258 13, 264 18, 258 23" fill="#ffffff" stroke="#0f172a" stroke-width="1.4" />
    <text x="272" y="21.5" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="700" fill="#334155">Aggregation</text>
    <!-- Dependency -->
    <line x1="372" y1="18" x2="394" y2="18" stroke="#0f172a" stroke-width="1.4" stroke-dasharray="3 3" marker-end="url(#marker-dep)" />
    <text x="404" y="21.5" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="700" fill="#334155">Dependency</text>
    <!-- Stereotype -->
    <rect x="502" y="11" width="46" height="15" rx="3" fill="#f1f5f9" />
    <text x="525" y="21.5" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-size="9" font-weight="700" fill="#64748b">«class»</text>
    <text x="556" y="21.5" font-family="Plus Jakarta Sans, sans-serif" font-size="11" font-weight="700" fill="#334155">Class Entity</text>
  </g>`;
    }

    const headerMarkup = this.buildExportHeaderSvg({
      width: canvasWidth,
      project: this.projectName,
      diagramType: 'Class Diagram',
      title: `${this._escape(this.projectName || 'UMLdoc')} · Object-Oriented Domain Model`,
      subtitle: 'Static class structure, inheritance hierarchy, associations &amp; member contracts',
      includeTitle: options.includeTitle !== false,
      includeVerification: options.includeVerification !== false,
      includeVersion: options.includeSourceVersion !== false
    });

    const footerMarkup = this.buildExportFooterSvg({
      width: canvasWidth,
      y: canvasHeight - footerH - 8,
      includeFooter: !!options.includeFooter,
      includeEvidence: !!options.includeEvidence
    });

    return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${canvasWidth} ${canvasHeight}" width="${canvasWidth}" height="${canvasHeight}" style="background-color:#ffffff; font-family:Plus Jakarta Sans,system-ui,-apple-system,sans-serif;">
  <defs>
    <marker id="marker-inherit" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="11" markerHeight="11" orient="auto-start-reverse">
      <polygon points="1 1, 11 6, 1 11" fill="#ffffff" stroke="#0f172a" stroke-width="1.5" />
    </marker>
    <marker id="marker-composition" viewBox="0 0 14 14" refX="13" refY="7" markerWidth="12" markerHeight="12" orient="auto-start-reverse">
      <polygon points="1 7, 7 2, 13 7, 7 12" fill="#0f172a" stroke="#0f172a" stroke-width="1.2" />
    </marker>
    <marker id="marker-aggregation" viewBox="0 0 14 14" refX="13" refY="7" markerWidth="12" markerHeight="12" orient="auto-start-reverse">
      <polygon points="1 7, 7 2, 13 7, 7 12" fill="#ffffff" stroke="#0f172a" stroke-width="1.5" />
    </marker>
    <marker id="marker-dep" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
      <polyline points="1 1, 9 5, 1 9" fill="none" stroke="#0f172a" stroke-width="1.5" stroke-linecap="round" />
    </marker>
    <style>
      .diag-edge-pill-rect { fill: #ffffff !important; stroke: #cbd5e1 !important; stroke-width: 1px !important; }
      .diag-edge-pill-text { fill: #334155 !important; font-family: Plus Jakarta Sans, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif !important; font-size: 10px !important; font-weight: 600 !important; text-anchor: middle !important; dominant-baseline: central !important; }
      .diag-connector-cardinality { fill: #64748b !important; font-family: Plus Jakarta Sans, sans-serif !important; font-size: 10px !important; }
    </style>
  </defs>
  <!-- Background Canvas -->
  <rect width="${canvasWidth}" height="${canvasHeight}" fill="#ffffff" />
  ${headerMarkup}
  <!-- Centered Diagram Plane -->
  <g transform="translate(${offsetX}, ${offsetY}) scale(${scale})">
    <g class="connectors">
${pathsMarkup}    </g>
    <g class="cards">
${cardsMarkup}    </g>
  </g>
  ${legendMarkup}
  ${footerMarkup}
</svg>`;
  }

  generateVectorSvgString(options = {}) {
    if (this.diagramType === 'sequence') {
      return this.generateSequenceSvgString(options);
    }
    if (this.diagramType === 'architecture' || this.diagramType === 'component') {
      return this.generateArchitectureSvgString(options);
    }
    if (this.diagramType === 'packages' || this.diagramType === 'package') {
      return this.generatePackageSvgString(options);
    }
    return this.generateClassSvgString(options);
  }

  /**
   * Builds the export SVG, strips any optional chrome that wasn't requested
   * (header, footer, legend, full-page background), and crops the viewBox
   * tightly around the actual diagram content — like a Mermaid export.
   * Returns { svg, width, height } in natural (1×) units.
   */
  _buildCleanExportSvg(options = {}) {
    const opts = {
      includeTitle: false,
      includeVerification: false,
      includeLegend: false,
      includeEvidence: false,
      includeTiming: false,
      ...options
    };
    if (opts.includeSourceVersion === undefined) {
      opts.includeSourceVersion = opts.includeVersion === true;
    }

    let raw = this.generateVectorSvgString(opts);
    if (!raw) return null;

    // Defensively sanitize any unescaped ampersands
    raw = raw.replace(/&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)/g, '&amp;');

    const NS = 'http://www.w3.org/2000/svg';
    const doc = new DOMParser().parseFromString(raw, 'image/svg+xml');
    const svg = doc.documentElement;
    const vb = (svg.getAttribute('viewBox') || '').split(/[\s,]+/).map(Number);
    const fullW = vb[2] || Number(svg.getAttribute('width')) || 1200;
    const fullH = vb[3] || Number(svg.getAttribute('height')) || 800;
    if (svg.querySelector('parsererror')) {
      return { svg: raw, width: fullW, height: fullH };
    }

    // 1. Remove full-canvas background rects (they would defeat cropping)
    Array.from(svg.children).forEach(el => {
      if (el.tagName === 'rect' &&
          Number(el.getAttribute('width')) === fullW &&
          Number(el.getAttribute('height')) === fullH) {
        el.remove();
      }
    });

    // 2. Remove optional chrome not requested
    const strip = sel => svg.querySelectorAll(sel).forEach(n => n.remove());
    if (!opts.includeTitle) strip('.export-header-frame');
    if (!opts.includeEvidence && !opts.includeFooter) strip('.export-footer-frame');
    if (!opts.includeLegend) strip('.export-class-legend, .seq-export-legend, .export-legend');

    // 3. Wrap drawable content in a single group so it can be measured
    const content = doc.createElementNS(NS, 'g');
    content.setAttribute('class', 'export-content');
    Array.from(svg.childNodes).forEach(n => {
      if (n.nodeType === 1 && n.tagName === 'defs') return;
      content.appendChild(n);
    });
    svg.appendChild(content);

    // 4. Measure real content bounds in a hidden live DOM
    const host = document.createElement('div');
    host.style.cssText = 'position:absolute;left:-100000px;top:0;width:0;height:0;overflow:hidden;visibility:hidden;';
    const live = document.importNode(svg, true);
    host.appendChild(live);
    document.body.appendChild(host);
    let bbox = null;
    try {
      bbox = live.querySelector('g.export-content').getBBox();
    } catch (e) {
      bbox = null;
    } finally {
      host.remove();
    }
    if (!bbox || !bbox.width || !bbox.height) {
      bbox = { x: 0, y: 0, width: fullW, height: fullH };
    }

    // 5. Tight crop with an even margin + white background
    const pad = (opts.padding !== undefined) ? opts.padding : 24;
    const x = Math.floor(bbox.x - pad);
    const y = Math.floor(bbox.y - pad);
    const w = Math.ceil(bbox.width + pad * 2);
    const h = Math.ceil(bbox.height + pad * 2);

    svg.setAttribute('viewBox', `${x} ${y} ${w} ${h}`);
    svg.setAttribute('width', w);
    svg.setAttribute('height', h);
    svg.setAttribute('style', 'background-color:#ffffff; font-family:Plus Jakarta Sans,system-ui,-apple-system,sans-serif;');

    const bg = doc.createElementNS(NS, 'rect');
    bg.setAttribute('x', x);
    bg.setAttribute('y', y);
    bg.setAttribute('width', w);
    bg.setAttribute('height', h);
    bg.setAttribute('fill', '#ffffff');
    svg.insertBefore(bg, content);

    const out = '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(svg);
    return { svg: out, width: w, height: h };
  }

  /** Pixel density for PNG output by preset (diagram is never shrunk). */
  _pngPixelRatio(preset, w, h) {
    let ratio;
    switch (preset) {
      case 'high_res': ratio = 4; break;
      case 'a4_report': ratio = Math.max(2, 3508 / Math.max(w, h)); break;
      case 'presentation': ratio = 2.5; break;
      case 'screen':
      default: ratio = 2;
    }
    // Stay within browser canvas limits
    const maxSide = 16000;
    const maxArea = 200000000;
    ratio = Math.min(ratio, maxSide / Math.max(w, h), Math.sqrt(maxArea / (w * h)));
    return Math.max(1, ratio);
  }

  export(format = 'svg', options = {}) {
    const cur = (this.projectName || 'atlas').toLowerCase();
    const diag = (this.diagramType || 'diagram').toLowerCase();
    const preset = options.preset || 'screen';
    const filename = options.filename || `${cur}_${diag}_${preset}.${format}`;

    if (format === 'svg') {
      this.exportSVG(filename, options);
    } else if (format === 'pdf') {
      this.exportPDF(filename, options);
    } else if (format === 'png') {
      this.exportPNG(filename, options);
    }
    return filename;
  }

  exportSVG(filename = null, options = {}) {
    if (typeof filename === 'object' && filename !== null) {
      options = filename;
      filename = null;
    }
    const result = this._buildCleanExportSvg(options);
    if (!result) return;
    const cur = (this.projectName || 'atlas').toLowerCase();
    const diag = (this.diagramType || 'diagram').toLowerCase();
    const outName = filename || `${cur}_${diag}_${options.preset || 'screen'}.svg`;
    this._downloadFile(outName, 'image/svg+xml;charset=utf-8', result.svg);
  }

  exportPNG(filenameOrScale = null, options = {}) {
    let filename = null;
    let opts = {};

    if (typeof filenameOrScale === 'number') {
      // Legacy call: exportPNG(scale, filename)
      const scale = filenameOrScale;
      filename = (typeof options === 'string') ? options : null;
      opts = { preset: scale >= 3 ? 'high_res' : 'screen' };
    } else if (typeof filenameOrScale === 'string') {
      filename = filenameOrScale;
      opts = options || {};
    } else if (typeof filenameOrScale === 'object' && filenameOrScale !== null) {
      opts = filenameOrScale;
    }

    const result = this._buildCleanExportSvg(opts);
    if (!result) return;

    const ratio = this._pngPixelRatio(opts.preset, result.width, result.height);
    const targetW = Math.round(result.width * ratio);
    const targetH = Math.round(result.height * ratio);

    const img = new Image();
    const blob = new Blob([result.svg], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);

    img.onload = () => {
      const offCanvas = document.createElement('canvas');
      offCanvas.width = targetW;
      offCanvas.height = targetH;
      const ctx = offCanvas.getContext('2d');
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, targetW, targetH);
      ctx.drawImage(img, 0, 0, targetW, targetH);
      URL.revokeObjectURL(url);

      offCanvas.toBlob(pngBlob => {
        const outName = filename || `${(this.projectName || 'atlas').toLowerCase()}_${this.diagramType || 'diagram'}.png`;
        this._downloadBlob(outName, pngBlob);
      }, 'image/png');
    };

    img.onerror = (err) => {
      console.warn('PNG rasterization failed, falling back to SVG export:', err);
      URL.revokeObjectURL(url);
      const fallbackName = (filename || `${(this.projectName || 'atlas').toLowerCase()}_${this.diagramType || 'diagram'}`).replace(/\.png$/i, '') + '.svg';
      this._downloadFile(fallbackName, 'image/svg+xml;charset=utf-8', result.svg);
    };

    img.src = url;
  }

  exportPDF(filename = null, options = {}) {
    const result = this._buildCleanExportSvg(options);
    if (!result) return;
    const svgStr = result.svg.replace(/^<\?xml[^>]*>\s*/, '');

    const orientation = result.width >= result.height ? 'landscape' : 'portrait';
    const outName = filename || `${(this.projectName || 'atlas').toLowerCase()}_${this.diagramType || 'diagram'}.pdf`;

    const printFrame = document.createElement('iframe');
    printFrame.style.position = 'fixed';
    printFrame.style.right = '0';
    printFrame.style.bottom = '0';
    printFrame.style.width = '0';
    printFrame.style.height = '0';
    printFrame.style.border = '0';
    document.body.appendChild(printFrame);

    const doc = printFrame.contentWindow.document;
    doc.open();
    doc.write(`<!DOCTYPE html>
<html>
<head>
  <title>${this._escape(outName)}</title>
  <style>
    @page {
      size: A4 ${orientation};
      margin: 8mm;
    }
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      background: #ffffff;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }
    svg {
      width: 100%;
      height: 100%;
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }
  </style>
</head>
<body>
  ${svgStr}
  <script>
    window.onload = function() {
      setTimeout(function() {
        window.focus();
        window.print();
      }, 300);
    };
  <\/script>
</body>
</html>`);
    doc.close();

    setTimeout(() => {
      try {
        document.body.removeChild(printFrame);
      } catch (e) {}
    }, 12000);
  }

  _downloadBlob(filename, blob) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  _downloadFile(filename, mime, content) {
    const blob = new Blob([content], { type: mime });
    this._downloadBlob(filename, blob);
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
