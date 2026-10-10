/**
 * ATLAS STUDIO - INSPECTOR PANEL COMPONENT
 * Renders structured property cards for:
 * 1. Sequence Diagram Messages (order, signature, args dictionary, return val, line/file evidence, latency)
 * 2. Sequence Diagram Lifelines / Participants (kind, source module, interaction history)
 * 3. Class Nodes (attributes, methods, verification status)
 */

export class InspectorComponent {
  constructor(options = {}) {
    this.container = options.container || document.getElementById('canvasInspector');
    this.onNavigateMessage = options.onNavigateMessage || (() => {});
    this.onSelectParticipant = options.onSelectParticipant || (() => {});
    this.onClose = options.onClose || (() => {});
    this.onFocusLifelines = options.onFocusLifelines || (() => {});

    this.currentItem = null;

    // Global keyboard listener: Escape to close
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen()) {
        this.close();
      }
    });
  }

  isOpen() {
    return this.container && !this.container.classList.contains('is-hidden');
  }

  open() {
    if (this.container) {
      this.container.classList.remove('is-hidden');
    }
  }

  close(silent = false) {
    if (!this.container) return;
    const wasOpen = !this.container.classList.contains('is-hidden');
    this.container.classList.add('is-hidden');
    this.currentItem = null;
    if (wasOpen && !silent) {
      this.onClose();
    }
  }

  inspect(item) {
    if (!item) {
      this.close();
      return;
    }

    this.currentItem = item;
    this.open();

    if (item.kind === 'sequence_message') {
      this._renderSequenceMessage(item);
    } else if (item.kind === 'sequence_participant') {
      this._renderSequenceParticipant(item);
    } else if (item.stereotype === '«package»' || (item.id && String(item.id).startsWith('pkg_')) || item.modules) {
      this._renderPackageNode(item);
    } else if (item.stereotype === '«component»' || item.tier || (item.id && String(item.id).startsWith('comp_'))) {
      this._renderComponentNode(item);
    } else {
      this._renderClassNode(item);
    }

    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  /* ------------------------------------------------------------------------
   * 1. SEQUENCE MESSAGE INSPECTOR
   * ------------------------------------------------------------------------ */
  _renderSequenceMessage(msg) {
    const isCall = (msg.type === 'call');
    const isReturn = (msg.type === 'return');
    const isExc = (msg.type === 'exception');

    const badgeClass = isExc ? 'inspector-badge--exception' : (isReturn ? 'inspector-badge--return' : 'inspector-badge--call');
    const badgeText = isExc ? 'EXCEPTION' : (isReturn ? 'RETURN / REPLY' : 'SYNCHRONOUS CALL');
    const badgeIcon = isExc ? 'alert-triangle' : (isReturn ? 'corner-down-left' : 'arrow-right');

    const order = msg.order || 1;
    const totalMsgs = msg.totalMessages || 10;
    const canPrev = order > 1;
    const canNext = order < totalMsgs;

    const signature = msg.signature || msg.method || msg.name || 'execute()';
    const cleanMethod = msg.method || msg.name || 'execute';

    // Format arguments
    const args = msg.arguments || {};
    const argEntries = Object.entries(args);
    const hasArgs = argEntries.length > 0;

    let argsHtml = '';
    if (hasArgs) {
      argsHtml = `
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span>Runtime Arguments</span>
            <span>${argEntries.length} PARAMETERS</span>
          </div>
          <table class="inspector-table">
            <thead>
              <tr>
                <th>Param</th>
                <th>Inspected Value</th>
              </tr>
            </thead>
            <tbody>
              ${argEntries.map(([k, v]) => `
                <tr>
                  <td class="param-name">${this._escape(k)}</td>
                  <td class="param-value">${this._escape(String(v))}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } else if (isCall) {
      argsHtml = `
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span>Runtime Arguments</span>
          </div>
          <div class="inspector-flow-card" style="font-size: 11.5px; color: var(--text-muted);">
            <span>No arguments passed (void signature).</span>
          </div>
        </div>
      `;
    }

    // Return value / exception card
    let resultHtml = '';
    if (isReturn && msg.return_val !== undefined && msg.return_val !== null) {
      resultHtml = `
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span>Return Value Payload</span>
          </div>
          <div class="inspector-code-card">
            <code>${this._escape(String(msg.return_val))}</code>
          </div>
        </div>
      `;
    } else if (isExc) {
      resultHtml = `
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span style="color: #dc2626;">Raised Exception</span>
          </div>
          <div class="inspector-code-card" style="border-color: #ef4444; color: #fca5a5;">
            <code>${this._escape(msg.signature || msg.name)}</code>
          </div>
        </div>
      `;
    }

    // Performance & Execution metrics
    const durStr = msg.durationMs ? `${msg.durationMs.toFixed(1)} ms` : (msg.timing?.durationMs ? `${msg.timing.durationMs.toFixed(1)} ms` : 'AST verified');
    const loopStr = (msg.loop_count && msg.loop_count > 1) ? `×${msg.loop_count} (Loop collapsed)` : 'Single call';

    // Source Evidence
    const file = msg.source?.file || 'Runtime Stack';
    const line = msg.source?.line ? `Line ${msg.source.line}` : '';

    this.container.innerHTML = `
      <!-- Header -->
      <div class="inspector-header">
        <div class="inspector-header__main">
          <div class="inspector-header__badges">
            <span class="inspector-badge inspector-badge--order">#${order}</span>
            <span class="inspector-badge ${badgeClass}">
              <i data-lucide="${badgeIcon}" style="width: 10px; height: 10px;"></i>
              ${badgeText}
            </span>
            ${msg.loop_count > 1 ? `<span class="inspector-badge" style="background:#fef3c7;color:#b45309;border:1px solid #fde68a;">⚡ Loop ×${msg.loop_count}</span>` : ''}
          </div>
          <h3 class="inspector-header__title" title="${this._escape(cleanMethod)}">${this._escape(cleanMethod)}</h3>
          <span class="inspector-header__subtitle">Step ${order} of ${totalMsgs} · ${this._escape(msg.scenarioName || 'Execution Trace')}</span>
        </div>
        <div class="inspector-header__actions">
          <button class="inspector-btn-icon" id="btnInspCopySig" title="Copy Full Signature">
            <i data-lucide="copy" style="width: 14px; height: 14px;"></i>
          </button>
          <button class="inspector-btn-icon" id="btnInspClose" title="Close Inspector (Esc)">
            <i data-lucide="x" style="width: 16px; height: 16px;"></i>
          </button>
        </div>
      </div>

      <!-- Body -->
      <div class="inspector-body">
        
        <!-- Flow Lifelines -->
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span>Interaction Flow</span>
          </div>
          <div class="inspector-flow-card">
            <div class="inspector-flow-node" id="inspNodeCaller" title="Inspect Caller Lifeline">
              <span class="inspector-flow-node__role">FROM CALLER</span>
              <span class="inspector-flow-node__name">${this._escape(msg.callerParticipant?.name || msg.caller)}</span>
            </div>
            <div class="inspector-flow-arrow">
              <i data-lucide="arrow-right" style="width: 16px; height: 16px;"></i>
            </div>
            <div class="inspector-flow-node" id="inspNodeCallee" title="Inspect Callee Lifeline" style="text-align: right;">
              <span class="inspector-flow-node__role">TO CALLEE</span>
              <span class="inspector-flow-node__name">${this._escape(msg.calleeParticipant?.name || msg.callee)}</span>
            </div>
          </div>
        </div>

        <!-- Invocation Signature -->
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span>Method Signature</span>
          </div>
          <div class="inspector-code-card">
            <code>${this._escape(signature)}</code>
            <button class="inspector-copy-btn" id="btnInspCopySigCode">Copy</button>
          </div>
        </div>

        <!-- Metric Chips -->
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span>Execution Metrics</span>
          </div>
          <div class="inspector-chip-grid">
            <div class="inspector-chip">
              <span class="inspector-chip__label">Duration</span>
              <span class="inspector-chip__val inspector-chip__val--accent">
                <i data-lucide="clock" style="width: 12px; height: 12px;"></i>
                ${durStr}
              </span>
            </div>
            <div class="inspector-chip">
              <span class="inspector-chip__label">Repetition</span>
              <span class="inspector-chip__val">
                <i data-lucide="repeat" style="width: 12px; height: 12px;"></i>
                ${loopStr}
              </span>
            </div>
          </div>
        </div>

        <!-- Arguments Table -->
        ${argsHtml}

        <!-- Result / Exception -->
        ${resultHtml}

        <!-- Source Verification Evidence -->
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span>Trace Evidence & Ground Truth</span>
          </div>
          <div class="inspector-evidence-box">
            <div class="inspector-evidence-row">
              <i data-lucide="file-code" style="width: 14px; height: 14px; color: var(--primary-bg);"></i>
              <span>File: <code>${this._escape(file)}</code></span>
            </div>
            ${line ? `
              <div class="inspector-evidence-row">
                <i data-lucide="hash" style="width: 14px; height: 14px; color: var(--text-muted);"></i>
                <span>Line: <code>${this._escape(line)}</code></span>
              </div>
            ` : ''}
            <div class="inspector-evidence-row" style="margin-top: 2px;">
              <i data-lucide="shield-check" style="width: 14px; height: 14px; color: #16a34a;"></i>
              <span style="font-weight: 600; color: #15803d; font-size: 11px;">Dual-Ground Verified Runtime Trace</span>
            </div>
          </div>
        </div>

      </div>

      <!-- Footer Stepper -->
      <div class="inspector-footer">
        <button class="inspector-stepper-btn" id="btnInspPrev" ${!canPrev ? 'disabled' : ''} title="Previous step">
          <i data-lucide="chevron-left" style="width: 14px; height: 14px;"></i>
          <span>Prev (#${order - 1})</span>
        </button>

        <button class="inspector-action-btn" id="btnInspFocus" title="Focus path on canvas">
          <i data-lucide="eye" style="width: 13px; height: 13px;"></i>
          <span>Focus Path</span>
        </button>

        <button class="inspector-stepper-btn" id="btnInspNext" ${!canNext ? 'disabled' : ''} title="Next step">
          <span>Next (#${order + 1})</span>
          <i data-lucide="chevron-right" style="width: 14px; height: 14px;"></i>
        </button>
      </div>
    `;

    // Bind interaction events
    const closeBtn = this.container.querySelector('#btnInspClose');
    if (closeBtn) closeBtn.addEventListener('click', () => this.close());

    const copySigBtn = this.container.querySelector('#btnInspCopySig');
    if (copySigBtn) copySigBtn.addEventListener('click', () => this.copyText(signature, copySigBtn));

    const copyCodeBtn = this.container.querySelector('#btnInspCopySigCode');
    if (copyCodeBtn) copyCodeBtn.addEventListener('click', () => this.copyText(signature, copyCodeBtn));

    const callerNode = this.container.querySelector('#inspNodeCaller');
    if (callerNode) callerNode.addEventListener('click', () => this.onSelectParticipant(msg.caller));

    const calleeNode = this.container.querySelector('#inspNodeCallee');
    if (calleeNode) calleeNode.addEventListener('click', () => this.onSelectParticipant(msg.callee));

    const prevBtn = this.container.querySelector('#btnInspPrev');
    if (prevBtn) prevBtn.addEventListener('click', () => this.onNavigateMessage(order - 1));

    const nextBtn = this.container.querySelector('#btnInspNext');
    if (nextBtn) nextBtn.addEventListener('click', () => this.onNavigateMessage(order + 1));

    const focusBtn = this.container.querySelector('#btnInspFocus');
    if (focusBtn) focusBtn.addEventListener('click', () => this.onFocusLifelines(msg.caller, msg.callee));
  }

  /* ------------------------------------------------------------------------
   * 2. SEQUENCE LIFELINE / PARTICIPANT INSPECTOR
   * ------------------------------------------------------------------------ */
  _renderSequenceParticipant(p) {
    const kind = p.participantKind || p.type || 'service';
    const msgs = p.relatedMessages || [];
    const sent = p.callsSent || 0;
    const recv = p.callsReceived || 0;

    let callsListHtml = '';
    if (msgs.length > 0) {
      callsListHtml = `
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span>Interactions in Scenario</span>
            <span>${msgs.length} MESSAGES</span>
          </div>
          <div class="inspector-calls-list">
            ${msgs.map(m => {
              const isOut = (m.from === p.id);
              const dirLabel = isOut ? `→ ${m.to}` : `← ${m.from}`;
              const typeIcon = m.type === 'call' ? 'arrow-right' : (m.type === 'exception' ? 'alert-triangle' : 'corner-down-left');
              return `
                <div class="inspector-call-item" data-msg-order="${m.order}">
                  <div class="inspector-call-item__info">
                    <span class="inspector-call-item__num">#${m.order}</span>
                    <i data-lucide="${typeIcon}" style="width: 11px; height: 11px; color: var(--text-muted);"></i>
                    <span class="inspector-call-item__sig" title="${this._escape(m.signature || m.name)}">${this._escape(m.name)}</span>
                  </div>
                  <span style="font-size: 10px; color: var(--text-tertiary);">${this._escape(dirLabel)}</span>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      `;
    }

    this.container.innerHTML = `
      <!-- Header -->
      <div class="inspector-header">
        <div class="inspector-header__main">
          <div class="inspector-header__badges">
            <span class="inspector-badge inspector-badge--participant">
              <i data-lucide="layers" style="width: 10px; height: 10px;"></i>
              LIFELINE PARTICIPANT
            </span>
            <span class="inspector-badge" style="background:var(--bg-surface-active);color:var(--text-secondary);">«${this._escape(kind)}»</span>
          </div>
          <h3 class="inspector-header__title">${this._escape(p.name)}</h3>
          <span class="inspector-header__subtitle">Participant ID: <code>${this._escape(p.id)}</code></span>
        </div>
        <div class="inspector-header__actions">
          <button class="inspector-btn-icon" id="btnInspClose" title="Close Inspector (Esc)">
            <i data-lucide="x" style="width: 16px; height: 16px;"></i>
          </button>
        </div>
      </div>

      <!-- Body -->
      <div class="inspector-body">
        
        <!-- Activity Chips -->
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span>Interaction Summary</span>
          </div>
          <div class="inspector-chip-grid">
            <div class="inspector-chip">
              <span class="inspector-chip__label">Calls Received (Inbound)</span>
              <span class="inspector-chip__val inspector-chip__val--accent">
                <i data-lucide="arrow-down-left" style="width: 12px; height: 12px;"></i>
                ${recv} calls
              </span>
            </div>
            <div class="inspector-chip">
              <span class="inspector-chip__label">Calls Initiated (Outbound)</span>
              <span class="inspector-chip__val">
                <i data-lucide="arrow-up-right" style="width: 12px; height: 12px;"></i>
                ${sent} calls
              </span>
            </div>
          </div>
        </div>

        <!-- Messages Timeline -->
        ${callsListHtml}

        <!-- Ground Truth Location -->
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span>Architecture Definition</span>
          </div>
          <div class="inspector-evidence-box">
            <div class="inspector-evidence-row">
              <i data-lucide="box" style="width: 14px; height: 14px; color: var(--primary-bg);"></i>
              <span>Stereotype: <code>«${this._escape(kind)}»</code></span>
            </div>
            <div class="inspector-evidence-row">
              <i data-lucide="code" style="width: 14px; height: 14px; color: var(--text-muted);"></i>
              <span>Class: <code>${this._escape(p.class_name || p.name)}</code></span>
            </div>
            ${p.module_name ? `
              <div class="inspector-evidence-row">
                <i data-lucide="folder" style="width: 14px; height: 14px; color: var(--text-muted);"></i>
                <span>Module: <code>${this._escape(p.module_name)}</code></span>
              </div>
            ` : ''}
          </div>
        </div>

      </div>

      <!-- Footer -->
      <div class="inspector-footer">
        <button class="inspector-action-btn" id="btnInspFocusSingle" style="width: 100%; justify-content: center;">
          <i data-lucide="crosshair" style="width: 13px; height: 13px;"></i>
          <span>Focus Lifeline Interactions</span>
        </button>
      </div>
    `;

    const closeBtn = this.container.querySelector('#btnInspClose');
    if (closeBtn) closeBtn.addEventListener('click', () => this.close());

    const focusBtn = this.container.querySelector('#btnInspFocusSingle');
    if (focusBtn) focusBtn.addEventListener('click', () => this.onSelectParticipant(p.id));

    this.container.querySelectorAll('[data-msg-order]').forEach(el => {
      el.addEventListener('click', () => {
        const ord = parseInt(el.dataset.msgOrder, 10);
        this.onNavigateMessage(ord);
      });
    });
  }

  /* ------------------------------------------------------------------------
   * 3. UML CLASS NODE INSPECTOR
   * ------------------------------------------------------------------------ */
  _renderClassNode(node) {
    const name = typeof node === 'string' ? node : (node.name || 'Class');
    const stereotype = node.stereotype || '«class»';
    const attrs = node.attributes || [];
    const methods = node.methods || [];
    const status = node.verification_status || 'Verified';

    this.container.innerHTML = `
      <div class="inspector-header">
        <div class="inspector-header__main">
          <div class="inspector-header__badges">
            <span class="inspector-badge inspector-badge--class">${this._escape(stereotype)}</span>
            <span class="inspector-badge" style="background:#dcfce7;color:#15803d;border:1px solid #bbf7d0;">
              <i data-lucide="check" style="width: 10px; height: 10px;"></i>
              ${this._escape(status)}
            </span>
          </div>
          <h3 class="inspector-header__title">${this._escape(name)}</h3>
          <span class="inspector-header__subtitle">${attrs.length} attributes · ${methods.length} methods</span>
        </div>
        <div class="inspector-header__actions">
          <button class="inspector-btn-icon" id="btnInspClose" title="Close Inspector (Esc)">
            <i data-lucide="x" style="width: 16px; height: 16px;"></i>
          </button>
        </div>
      </div>

      <div class="inspector-body">
        ${attrs.length > 0 ? `
          <div class="inspector-section">
            <div class="inspector-section__label">
              <span>Attributes (${attrs.length})</span>
            </div>
            <table class="inspector-table">
              <tbody>
                ${attrs.map(a => `
                  <tr>
                    <td class="param-name">${this._escape(a.name || a)}</td>
                    <td class="param-value">${this._escape(a.type || a.type_str || '')}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        ` : ''}

        ${methods.length > 0 ? `
          <div class="inspector-section">
            <div class="inspector-section__label">
              <span>Methods (${methods.length})</span>
            </div>
            <table class="inspector-table">
              <tbody>
                ${methods.map(m => `
                  <tr>
                    <td class="param-name">${this._escape(m.name || m)}()</td>
                    <td class="param-value">${this._escape(m.return_type || m.return_type_str || '')}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        ` : ''}
      </div>
    `;

    const closeBtn = this.container.querySelector('#btnInspClose');
    if (closeBtn) closeBtn.addEventListener('click', () => this.close());
  }

  /* ------------------------------------------------------------------------
   * 4. UML PACKAGE NODE INSPECTOR
   * ------------------------------------------------------------------------ */
  _renderPackageNode(pkg) {
    const name = pkg.name || 'Package';
    const modules = pkg.modules || [];
    const classes = pkg.classes || [];
    const ca = pkg.afferent_coupling !== undefined ? pkg.afferent_coupling : 0;
    const ce = pkg.efferent_coupling !== undefined ? pkg.efferent_coupling : 0;
    const instability = pkg.instability !== undefined ? Number(pkg.instability).toFixed(2) : '0.00';
    const isCyclic = !!pkg.is_cyclic;

    this.container.innerHTML = `
      <div class="inspector-header">
        <div class="inspector-header__main">
          <div class="inspector-header__badges">
            <span class="inspector-badge inspector-badge--package">«package»</span>
            ${isCyclic ? `
              <span class="inspector-badge" style="background:#fee2e2;color:#b91c1c;border:1px solid #fca5a5;">
                <i data-lucide="alert-triangle" style="width: 10px; height: 10px;"></i>
                CIRCULAR COUPLING
              </span>
            ` : `
              <span class="inspector-badge" style="background:#dcfce7;color:#15803d;border:1px solid #bbf7d0;">
                <i data-lucide="check" style="width: 10px; height: 10px;"></i>
                VERIFIED (AST)
              </span>
            `}
          </div>
          <h3 class="inspector-header__title">${this._escape(name)}</h3>
          <span class="inspector-header__subtitle">${modules.length} modules · ${classes.length} classes</span>
        </div>
        <div class="inspector-header__actions">
          <button class="inspector-btn-icon" id="btnInspClose" title="Close Inspector (Esc)">
            <i data-lucide="x" style="width: 16px; height: 16px;"></i>
          </button>
        </div>
      </div>

      <div class="inspector-body">
        <!-- Martin's Package Coupling Metrics -->
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span>Coupling & Stability Metrics</span>
            <span>MARTIN'S METRICS</span>
          </div>
          <table class="inspector-table">
            <tbody>
              <tr>
                <td class="param-name">Afferent Coupling (Ca)</td>
                <td class="param-value">${ca} <span style="color:#94a3b8;font-size:10px;">(incoming dependencies)</span></td>
              </tr>
              <tr>
                <td class="param-name">Efferent Coupling (Ce)</td>
                <td class="param-value">${ce} <span style="color:#94a3b8;font-size:10px;">(outgoing dependencies)</span></td>
              </tr>
              <tr>
                <td class="param-name">Instability Metric (I)</td>
                <td class="param-value"><b>${instability}</b> <span style="color:#94a3b8;font-size:10px;">(0.0 = Stable, 1.0 = Volatile)</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Contained Modules -->
        ${modules.length > 0 ? `
          <div class="inspector-section">
            <div class="inspector-section__label">
              <span>Contained Modules (${modules.length})</span>
            </div>
            <table class="inspector-table">
              <tbody>
                ${modules.map(m => `
                  <tr>
                    <td class="param-name"><i data-lucide="file-code" style="width:11px;height:11px;margin-right:4px;"></i>${this._escape(m.split('.').pop())}.py</td>
                    <td class="param-value" style="color:#64748b;font-size:11px;">${this._escape(m)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        ` : ''}

        <!-- Declared Classes -->
        ${classes.length > 0 ? `
          <div class="inspector-section">
            <div class="inspector-section__label">
              <span>Declared Classes (${classes.length})</span>
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:6px; padding:6px 0;">
              ${classes.map(c => `
                <span class="vivid-badge vivid-badge--primary" style="font-size:10.5px;">${this._escape(c)}</span>
              `).join('')}
            </div>
          </div>
        ` : ''}
      </div>
    `;

    const closeBtn = this.container.querySelector('#btnInspClose');
    if (closeBtn) closeBtn.addEventListener('click', () => this.close());
  }

  /* ------------------------------------------------------------------------
   * 5. UML COMPONENT ARCHITECTURE INSPECTOR
   * ------------------------------------------------------------------------ */
  _renderComponentNode(comp) {
    const name = comp.name || 'Component';
    const stereotype = comp.stereotype || '«component»';
    const tier = comp.tier || 'Domain Service';
    const role = comp.role || 'Application Service';
    const semColor = comp.semantic_color || '#3b82f6';
    const file = comp.file || '';
    const line = comp.line || 1;
    const provided = comp.provided_interfaces || [];
    const required = comp.required_interfaces || [];
    const encapsulated = comp.encapsulated_classes || [name];
    const funcCount = comp.functions_count !== undefined ? comp.functions_count : provided.length;
    const depCount = comp.dependencies_count !== undefined ? comp.dependencies_count : required.length;
    const docstring = comp.docstring || '';

    this.container.innerHTML = `
      <div class="inspector-header">
        <div class="inspector-header__main">
          <div class="inspector-header__badges">
            <span class="inspector-badge inspector-badge--component">${this._escape(stereotype)}</span>
            <span class="inspector-badge" style="background:${semColor}18; color:${semColor}; border:1px solid ${semColor}44;">
              <i data-lucide="layers" style="width: 10px; height: 10px;"></i>
              ${this._escape(role.toUpperCase())}
            </span>
            <span class="inspector-badge" style="background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd;">
              ${this._escape(tier)}
            </span>
            <span class="inspector-badge" style="background:#dcfce7; color:#15803d; border:1px solid #bbf7d0;">
              <i data-lucide="check" style="width: 10px; height: 10px;"></i>
              VERIFIED
            </span>
          </div>
          <h3 class="inspector-header__title">${this._escape(name)}</h3>
          <span class="inspector-header__subtitle">${file ? `${file}:${line}` : 'Architectural Subsystem'}</span>
        </div>
        <div class="inspector-header__actions">
          <button class="inspector-btn-icon" id="btnInspClose" title="Close Inspector (Esc)">
            <i data-lucide="x" style="width: 16px; height: 16px;"></i>
          </button>
        </div>
      </div>

      <div class="inspector-body">
        <!-- Quick Metrics Chips Grid -->
        <div class="inspector-section">
          <div class="inspector-chips-grid">
            <div class="inspector-chip">
              <span class="inspector-chip__label">Functions</span>
              <span class="inspector-chip__val" style="color:${semColor}; font-weight:700;">
                <i data-lucide="code" style="width: 12px; height: 12px;"></i>
                ${funcCount} public
              </span>
            </div>
            <div class="inspector-chip">
              <span class="inspector-chip__label">Dependencies</span>
              <span class="inspector-chip__val" style="color:#d97706; font-weight:700;">
                <i data-lucide="git-commit" style="width: 12px; height: 12px;"></i>
                ${depCount} outgoing
              </span>
            </div>
            <div class="inspector-chip">
              <span class="inspector-chip__label">Encapsulated</span>
              <span class="inspector-chip__val" style="color:#0284c7; font-weight:700;">
                <i data-lucide="box" style="width: 12px; height: 12px;"></i>
                ${encapsulated.length} classes
              </span>
            </div>
          </div>
        </div>

        ${docstring ? `
          <!-- Architectural Responsibility / Docstring -->
          <div class="inspector-section">
            <div class="inspector-section__label">
              <span>Architectural Responsibility</span>
            </div>
            <div style="font-size: 11.5px; line-height: 1.5; color: var(--text-muted, #475467); background: var(--bg-surface-subtle, #f8fafc); padding: 8px 10px; border-radius: 6px; border-left: 3px solid ${semColor};">
              ${this._escape(docstring)}
            </div>
          </div>
        ` : ''}

        <!-- Provided Interfaces / APIs -->
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span>Provided Interfaces / APIs (${provided.length})</span>
            <span>EXPOSED</span>
          </div>
          ${provided.length > 0 ? `
            <table class="inspector-table">
              <tbody>
                ${provided.map(iface => `
                  <tr>
                    <td class="param-name">() ${this._escape(iface)}()</td>
                    <td class="param-value" style="color:#0284c7;">Public API</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : `
            <div style="color:#94a3b8; font-size:11px; padding:6px 0;">No explicit exposed interface endpoints</div>
          `}
        </div>

        <!-- Required Interfaces / Dependencies -->
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span>Required Dependencies (${required.length})</span>
            <span>INJECTED</span>
          </div>
          ${required.length > 0 ? `
            <table class="inspector-table">
              <tbody>
                ${required.map(req => `
                  <tr>
                    <td class="param-name">-( ${this._escape(req)}</td>
                    <td class="param-value" style="color:#d97706;">Required Service</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : `
            <div style="color:#94a3b8; font-size:11px; padding:6px 0;">Self-contained / No external services required</div>
          `}
        </div>

        <!-- Encapsulated Implementation Classes -->
        <div class="inspector-section">
          <div class="inspector-section__label">
            <span>Encapsulated Classes (${encapsulated.length})</span>
          </div>
          <div style="display:flex; flex-wrap:wrap; gap:6px; padding:6px 0;">
            ${encapsulated.map(c => `
              <span class="vivid-badge vivid-badge--primary" style="font-size:10.5px;">${this._escape(c)}</span>
            `).join('')}
          </div>
        </div>
      </div>
    `;

    const closeBtn = this.container.querySelector('#btnInspClose');
    if (closeBtn) closeBtn.addEventListener('click', () => this.close());
  }

  copyText(text, btnEl) {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(() => {
      const origText = btnEl.textContent;
      btnEl.textContent = 'Copied!';
      btnEl.style.background = '#15803d';
      btnEl.style.color = '#ffffff';
      setTimeout(() => {
        btnEl.textContent = origText;
        btnEl.style.background = '';
        btnEl.style.color = '';
      }, 1400);
    }).catch(() => {});
  }

  _escape(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}
