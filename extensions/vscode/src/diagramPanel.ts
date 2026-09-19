import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { PythonBridge, DocumentIRData } from './pythonBridge';

export class DiagramPanel {
  public static currentPanel: DiagramPanel | undefined;
  public static readonly viewType = 'umldoc.diagramView';

  private readonly _panel: vscode.WebviewPanel;
  private readonly _workspaceRoot: string;
  private _targetPath: string;
  private _disposables: vscode.Disposable[] = [];

  public static createOrShow(extensionUri: vscode.Uri, workspaceRoot: string, targetPath: string) {
    const column = vscode.window.activeTextEditor
      ? vscode.ViewColumn.Beside
      : vscode.ViewColumn.One;

    if (DiagramPanel.currentPanel) {
      DiagramPanel.currentPanel._targetPath = targetPath;
      DiagramPanel.currentPanel._panel.reveal(column);
      DiagramPanel.currentPanel.refresh();
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      DiagramPanel.viewType,
      'UMLdoc: Architecture Diagram',
      column,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [extensionUri],
      }
    );

    DiagramPanel.currentPanel = new DiagramPanel(panel, workspaceRoot, targetPath);
  }

  private constructor(
    panel: vscode.WebviewPanel,
    workspaceRoot: string,
    targetPath: string
  ) {
    this._panel = panel;
    this._workspaceRoot = workspaceRoot;
    this._targetPath = targetPath;

    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

    this._panel.webview.onDidReceiveMessage(
      async (message) => {
        switch (message.command) {
          case 'jumpToSource':
            await this._handleJumpToSource(message.filePath, message.line);
            break;
          case 'refresh':
            await this.refresh();
            break;
          case 'export':
            await vscode.commands.executeCommand('umldoc.exportBundle');
            break;
        }
      },
      null,
      this._disposables
    );

    this.refresh();
  }

  public async refresh() {
    this._panel.webview.html = this._getLoadingHtml();
    try {
      // 1. Extract DocumentIR for structured statistics
      const docIr = await PythonBridge.extractDocumentIR(this._workspaceRoot, this._targetPath);

      // 2. Generate SVG Diagram
      const tempDir = path.join(this._workspaceRoot, 'output', '.cache');
      fs.mkdirSync(tempDir, { recursive: true });
      const svgContent = await PythonBridge.generateSVG(this._workspaceRoot, this._targetPath, tempDir);

      this._panel.webview.html = this._getWebviewHtml(svgContent, docIr);
    } catch (err: any) {
      this._panel.webview.html = this._getErrorHtml(err.message || String(err));
    }
  }

  private async _handleJumpToSource(filePath?: string, line?: number) {
    if (!filePath) {
      vscode.window.showWarningMessage('No source file location available for this element.');
      return;
    }

    let resolvedPath = filePath;
    if (!path.isAbsolute(resolvedPath)) {
      resolvedPath = path.resolve(this._targetPath, filePath);
      if (!fs.existsSync(resolvedPath)) {
        resolvedPath = path.resolve(this._workspaceRoot, filePath);
      }
    }

    if (!fs.existsSync(resolvedPath)) {
      vscode.window.showErrorMessage(`Source file not found: ${resolvedPath}`);
      return;
    }

    const doc = await vscode.workspace.openTextDocument(resolvedPath);
    const editor = await vscode.window.showTextDocument(doc, vscode.ViewColumn.One);

    const targetLine = Math.max(0, (line || 1) - 1);
    const pos = new vscode.Position(targetLine, 0);
    editor.selection = new vscode.Selection(pos, pos);
    editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
  }

  private _getLoadingHtml(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>UMLdoc · Loading architecture</title>
  <style>
    :root {
      --bg: #030611;
      --surface: rgba(11, 18, 35, .82);
      --ink: #f4f1e8;
      --muted: #9297a9;
      --cyan: #65c8ff;
      --cream: #ffe9c2;
      --line: rgba(207, 225, 255, .13);
      --font-ui: Manrope, ui-sans-serif, system-ui, sans-serif;
      --font-mono: "DM Mono", ui-monospace, Consolas, monospace;
    }
    * { box-sizing: border-box; }
    html, body { width: 100%; height: 100%; margin: 0; }
    body {
      display: grid;
      place-items: center;
      overflow: hidden;
      background:
        radial-gradient(70% 80% at 50% 44%, rgba(18, 30, 62, .62), transparent 64%),
        radial-gradient(rgba(196, 212, 255, .16) .7px, transparent .8px),
        var(--bg);
      background-size: auto, 24px 24px, auto;
      color: var(--ink);
      font-family: var(--font-ui);
    }
    .loading-shell { display: grid; justify-items: center; gap: 16px; padding: 30px; text-align: center; }
    .brand-mark { display: flex; height: 22px; align-items: center; gap: 3px; }
    .brand-mark span { display: block; width: 2px; border-radius: 99px; background: var(--ink); box-shadow: 0 0 8px rgba(188, 220, 255, .38); }
    .brand-mark span:nth-child(1), .brand-mark span:nth-child(6) { height: 7px; opacity: .52; }
    .brand-mark span:nth-child(2), .brand-mark span:nth-child(5) { height: 13px; opacity: .7; }
    .brand-mark span:nth-child(3), .brand-mark span:nth-child(4) { height: 20px; }
    .spinner { width: 38px; height: 38px; border: 1px solid var(--line); border-top-color: var(--cyan); border-right-color: var(--cream); border-radius: 50%; animation: spin .8s linear infinite; box-shadow: 0 0 24px rgba(101, 200, 255, .16); }
    h1 { margin: 0; font-size: 15px; font-weight: 600; }
    p { margin: 0; color: var(--muted); font-family: var(--font-mono); font-size: 10px; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @media (prefers-reduced-motion: reduce) { .spinner { animation-duration: 1.8s; } }
  </style>
</head>
<body>
  <main class="loading-shell" aria-live="polite">
    <div class="brand-mark" aria-label="UMLdoc" role="img"><span></span><span></span><span></span><span></span><span></span><span></span></div>
    <div class="spinner" aria-hidden="true"></div>
    <h1>Preparing the verified architecture view</h1>
    <p>Extracting AST architecture · rendering source graph</p>
  </main>
</body>
</html>`;
  }

  private _getErrorHtml(errorMessage: string): string {
    const safeError = this._escapeHtml(errorMessage);
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>UMLdoc · Architecture error</title>
  <style>
    :root {
      --bg: #030611;
      --surface: rgba(10, 16, 30, .92);
      --ink: #f4f1e8;
      --muted: #9297a9;
      --red: #ff858f;
      --cream: #ffe9c2;
      --line: rgba(207, 225, 255, .13);
      --font-ui: Manrope, ui-sans-serif, system-ui, sans-serif;
      --font-mono: "DM Mono", ui-monospace, Consolas, monospace;
    }
    * { box-sizing: border-box; }
    html, body { min-height: 100%; margin: 0; }
    body { padding: 28px; background: radial-gradient(70% 80% at 50% 44%, rgba(18, 30, 62, .62), transparent 64%), var(--bg); color: var(--ink); font-family: var(--font-ui); }
    .error-card { max-width: 760px; margin: 0 auto; padding: 22px; border: 1px solid rgba(255, 133, 143, .3); border-radius: 15px; background: var(--surface); box-shadow: 0 20px 50px rgba(0, 0, 0, .38); }
    .eyebrow { color: var(--red); font-family: var(--font-mono); font-size: 9px; letter-spacing: .08em; text-transform: uppercase; }
    h1 { margin: 9px 0 8px; font-size: 18px; font-weight: 600; }
    p { margin: 0 0 14px; color: var(--muted); font-size: 12px; }
    pre { margin: 0; padding: 12px; overflow: auto; border: 1px solid var(--line); border-radius: 9px; background: rgba(2, 7, 17, .55); color: #ffc2c7; font-family: var(--font-mono); font-size: 10px; line-height: 1.5; white-space: pre-wrap; }
    button { margin-top: 16px; padding: 9px 14px; border: 1px solid rgba(255, 233, 194, .7); border-radius: 8px; background: var(--cream); color: #161522; font: 600 11px var(--font-ui); cursor: pointer; }
    button:hover, button:focus-visible { outline: none; box-shadow: 0 0 22px rgba(255, 225, 169, .28); transform: translateY(-1px); }
  </style>
</head>
<body>
  <main class="error-card" role="alert">
    <div class="eyebrow">UMLdoc · architecture explorer</div>
    <h1>Unable to render the verified architecture view</h1>
    <p>The Python extraction or SVG renderer returned an error. Try the refresh action again after checking the workspace.</p>
    <pre>${safeError}</pre>
    <button id="retryButton" type="button">Try again</button>
  </main>
  <script>
    const vscode = acquireVsCodeApi();
    document.getElementById('retryButton').addEventListener('click', () => vscode.postMessage({ command: 'refresh' }));
  </script>
</body>
</html>`;
  }

  private _getWebviewHtml(svgContent: string, docIr: DocumentIRData): string {
    const classes = docIr.static_model?.classes || [];
    const relations = docIr.static_model?.relations || [];
    const projectName = docIr.project_name || path.basename(this._targetPath);
    const safeProjectName = this._escapeHtml(projectName);

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>UMLdoc · ${safeProjectName}</title>
  <style>
    :root {
      --bg: #030611;
      --surface: rgba(11, 18, 35, .78);
      --surface-strong: rgba(10, 16, 30, .92);
      --surface-warm: rgba(57, 47, 37, .92);
      --ink: #f4f1e8;
      --ink-soft: #d8dbea;
      --muted: #9297a9;
      --faint: #5b6174;
      --line: rgba(207, 225, 255, .13);
      --line-strong: rgba(216, 226, 253, .22);
      --cream: #ffe9c2;
      --cyan: #65c8ff;
      --cyan-soft: rgba(101, 200, 255, .13);
      --copper: #c78c5d;
      --green: #76e6a0;
      --amber: #f2c276;
      --red: #ff858f;
      --shadow-lg: 0 20px 50px rgba(0, 0, 0, .38);
      --shadow-dock: 0 15px 28px rgba(0, 0, 0, .35);
      --font-ui: Manrope, ui-sans-serif, system-ui, sans-serif;
      --font-mono: "DM Mono", ui-monospace, Consolas, monospace;
    }
    *, *::before, *::after { box-sizing: border-box; }
    html, body { width: 100%; height: 100%; margin: 0; }
    body { overflow: hidden; background: var(--bg); color: var(--ink); font-family: var(--font-ui); -webkit-font-smoothing: antialiased; }
    button, input { font: inherit; }
    button { color: inherit; }
    #app { position: relative; width: 100%; height: 100%; min-width: 620px; overflow: hidden; background: radial-gradient(70% 80% at 48% 46%, rgba(18, 30, 62, .52), transparent 62%), radial-gradient(44% 55% at 61% 69%, rgba(16, 68, 104, .14), transparent 72%), var(--bg); }
    #app::before { position: absolute; inset: 0; opacity: .42; pointer-events: none; background-image: radial-gradient(rgba(196, 212, 255, .18) .7px, transparent .8px); background-size: 24px 24px; mask-image: linear-gradient(90deg, transparent, #000 12%, #000 88%, transparent); content: ''; }
    #app::after { position: absolute; inset: 0; opacity: .2; pointer-events: none; background: linear-gradient(115deg, transparent 0 20%, rgba(255, 255, 255, .025) 40%, transparent 66%); content: ''; }
    #topbar { position: absolute; inset: 0 0 auto; z-index: 10; display: flex; height: 56px; align-items: center; justify-content: space-between; padding: 0 18px; border-bottom: 1px solid rgba(205, 220, 255, .11); background: rgba(5, 9, 19, .86); box-shadow: 0 14px 30px rgba(0, 0, 0, .18); }
    .top-left, .top-right, .brand-lockup, .center-title { display: flex; align-items: center; }
    .top-left { min-width: 250px; gap: 12px; }.top-right { min-width: 250px; justify-content: flex-end; gap: 7px; }.brand-lockup { gap: 8px; }.brand-name { color: var(--ink); font-size: 12px; font-weight: 600; }.brand-mark { display: flex; height: 22px; align-items: center; gap: 3px; opacity: .88; }.brand-mark span { display: block; width: 2px; border-radius: 99px; background: #eef2ff; box-shadow: 0 0 7px rgba(188, 220, 255, .38); }.brand-mark span:nth-child(1), .brand-mark span:nth-child(6) { height: 7px; opacity: .52; }.brand-mark span:nth-child(2), .brand-mark span:nth-child(5) { height: 13px; opacity: .7; }.brand-mark span:nth-child(3), .brand-mark span:nth-child(4) { height: 20px; }
    .mode-pill, .badge, .btn { border: 1px solid var(--line); border-radius: 8px; background: rgba(18, 25, 43, .7); }.mode-pill { padding: 6px 9px; color: var(--muted); font-family: var(--font-mono); font-size: 9px; }.mode-pill::before { display: inline-block; width: 5px; height: 5px; margin-right: 6px; border-radius: 50%; background: var(--cyan); box-shadow: 0 0 7px var(--cyan); content: ''; }.center-title { position: absolute; left: 50%; gap: 8px; padding: 7px 10px; border-radius: 8px; transform: translateX(-50%); font-size: 11px; }.center-title strong { color: var(--ink); font-weight: 600; }.slash { color: #677086; }.center-title span:last-child { color: var(--muted); }.badge { padding: 5px 8px; color: var(--muted); font-family: var(--font-mono); font-size: 8px; }.badge strong { color: var(--ink-soft); font-weight: 500; }.btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 9px; color: var(--ink-soft); font-size: 9px; cursor: pointer; }.btn:hover, .btn:focus-visible { outline: none; border-color: rgba(101, 200, 255, .5); background: var(--cyan-soft); color: var(--cyan); }.btn-primary { border-color: rgba(255, 233, 194, .55); background: var(--cream); color: #161522; font-weight: 700; }.btn-primary:hover, .btn-primary:focus-visible { border-color: var(--cream); background: var(--cream); color: #161522; box-shadow: 0 0 24px rgba(255, 225, 169, .28); }
    #viewport { position: absolute; inset: 56px 0 0; overflow: hidden; cursor: grab; }.is-dragging { cursor: grabbing !important; }#canvas { position: absolute; top: 36px; left: 36px; transform-origin: 0 0; transition: transform .05s linear; }#canvas svg { display: block; max-width: none; overflow: visible; }#canvas .umldoc-class-node { cursor: pointer; transition: opacity .2s ease, filter .2s ease; outline: none; }#canvas .umldoc-class-node:hover, #canvas .umldoc-class-node:focus, #canvas .umldoc-class-node.highlighted { filter: drop-shadow(0 0 9px rgba(101, 200, 255, .75)); }#canvas .umldoc-class-node.dimmed { opacity: .14 !important; }#canvas .umldoc-class-node.highlighted rect { stroke: var(--cyan) !important; stroke-width: 3px !important; }
    #tip-banner, #canvas-status, .zoom-controls { position: absolute; z-index: 5; border: 1px solid var(--line); border-radius: 8px; background: rgba(10, 18, 34, .76); box-shadow: var(--shadow-dock); backdrop-filter: blur(16px); }.tip-copy { color: var(--muted); font-family: var(--font-mono); font-size: 9px; }.tip-copy strong { color: var(--ink-soft); font-weight: 500; }#tip-banner { bottom: 18px; left: 20px; padding: 7px 10px; }.tip-dot { display: inline-block; width: 5px; height: 5px; margin-right: 6px; border-radius: 50%; background: var(--cyan); box-shadow: 0 0 7px var(--cyan); }#canvas-status { right: 86px; bottom: 18px; padding: 7px 10px; color: var(--faint); font-family: var(--font-mono); font-size: 8px; }.status-dot { display: inline-block; width: 5px; height: 5px; margin-right: 6px; border-radius: 50%; background: var(--green); box-shadow: 0 0 7px var(--green); }.zoom-controls { right: 20px; bottom: 18px; display: flex; gap: 4px; padding: 4px; }.zoom-btn { display: grid; width: 27px; height: 27px; place-items: center; border: 0; border-radius: 6px; background: transparent; color: var(--muted); cursor: pointer; }.zoom-btn:hover, .zoom-btn:focus-visible { outline: none; background: var(--cyan-soft); color: var(--cyan); }.zoom-btn.reset { color: var(--cream); }
    @media (max-width: 900px) { #app { min-width: 560px; }.top-left, .top-right { min-width: 180px; }.center-title { font-size: 10px; }.top-right .badge { display: none; }.btn { padding: 7px; }.btn .label { display: none; }.top-left { gap: 8px; } }
    @media (max-width: 680px) { .center-title span, .center-title .slash { display: none; }.top-right { min-width: auto; }.brand-name { display: none; }#tip-banner { right: 20px; max-width: calc(100% - 40px); }.tip-copy { font-size: 8px; }.canvas-status { display: none; } }
    @media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; } }
  </style>
</head>
<body>
  <main id="app" aria-label="UMLdoc verified architecture explorer">
    <header id="topbar">
      <div class="top-left">
        <div class="brand-lockup">
          <div class="brand-mark" aria-label="UMLdoc" role="img"><span></span><span></span><span></span><span></span><span></span><span></span></div>
          <span class="brand-name">UMLdoc</span>
        </div>
        <span class="mode-pill">Logical</span>
      </div>
      <div class="center-title"><strong>${safeProjectName}</strong><span class="slash">/</span><span>Architecture explorer</span></div>
      <div class="top-right">
        <span class="badge">Classes: <strong>${classes.length}</strong></span>
        <span class="badge">Relations: <strong>${relations.length}</strong></span>
        <button class="btn" id="refreshBtn" type="button" title="Re-extract AST and redraw"><span aria-hidden="true">↻</span><span class="label">Refresh</span></button>
        <button class="btn btn-primary" id="exportBtn" type="button" title="Export HTML, SVG, PUML, and MMD bundle"><span aria-hidden="true">⇩</span><span class="label">Export</span></button>
      </div>
    </header>

    <section id="viewport" aria-label="Interactive architecture diagram">
      <div id="canvas">${svgContent}</div>
      <div id="tip-banner"><span class="tip-dot" aria-hidden="true"></span><span class="tip-copy"><strong>Source jump ready.</strong> Click any class node to open its Python definition.</span></div>
      <div id="canvas-status"><span class="status-dot" aria-hidden="true"></span>verified source model</div>
      <div class="zoom-controls" role="group" aria-label="Diagram zoom controls">
        <button class="zoom-btn" id="zoomIn" type="button" title="Zoom in" aria-label="Zoom in">+</button>
        <button class="zoom-btn" id="zoomOut" type="button" title="Zoom out" aria-label="Zoom out">−</button>
        <button class="zoom-btn reset" id="zoomReset" type="button" title="Reset view" aria-label="Reset view">⊙</button>
      </div>
    </section>
  </main>

  <script>
    const vscode = acquireVsCodeApi();
    const viewport = document.getElementById('viewport');
    const canvas = document.getElementById('canvas');
    const searchLabel = document.querySelector('.center-title strong');

    const postSourceJump = (node) => {
      const filePath = node.getAttribute('data-file');
      const line = parseInt(node.getAttribute('data-line') || '1', 10);
      vscode.postMessage({ command: 'jumpToSource', filePath, line, name: node.getAttribute('data-name') });
    };

    document.querySelectorAll('.umldoc-class-node').forEach((node) => {
      node.setAttribute('tabindex', '0');
      node.setAttribute('role', 'button');
      node.addEventListener('click', (event) => {
        event.stopPropagation();
        postSourceJump(node);
      });
      node.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          postSourceJump(node);
        }
      });
    });

    document.getElementById('refreshBtn').addEventListener('click', () => vscode.postMessage({ command: 'refresh' }));
    document.getElementById('exportBtn').addEventListener('click', () => vscode.postMessage({ command: 'export' }));

    const searchInput = document.createElement('input');
    searchInput.type = 'search';
    searchInput.placeholder = 'Filter classes…';
    searchInput.setAttribute('aria-label', 'Filter classes');
    searchInput.style.cssText = 'position:absolute;top:66px;right:20px;z-index:6;width:190px;padding:7px 10px;border:1px solid rgba(207,225,255,.13);border-radius:8px;background:rgba(10,16,30,.92);color:#f4f1e8;font:10px "DM Mono",ui-monospace,monospace;outline:none;';
    document.getElementById('app').appendChild(searchInput);
    searchInput.addEventListener('input', (event) => {
      const query = event.target.value.toLowerCase().trim();
      document.querySelectorAll('.umldoc-class-node').forEach((node) => {
        const name = (node.getAttribute('data-name') || '').toLowerCase();
        const matches = !query || name.includes(query);
        node.classList.toggle('dimmed', !matches);
        node.classList.toggle('highlighted', Boolean(query && matches));
      });
      if (searchLabel) searchLabel.textContent = query ? 'Filtered architecture' : '${safeProjectName}';
    });

    let scale = .85;
    let translateX = 32;
    let translateY = 32;
    let isDragging = false;
    let pointerId = null;
    let startX = 0;
    let startY = 0;

    function updateTransform() {
      canvas.style.transform = 'translate(' + translateX + 'px, ' + translateY + 'px) scale(' + scale + ')';
    }

    function updateZoom(nextScale, center) {
      const boundedScale = Math.min(Math.max(nextScale, .2), 4.0);
      if (center) {
        const ratio = boundedScale / scale;
        translateX = center.x - (center.x - translateX) * ratio;
        translateY = center.y - (center.y - translateY) * ratio;
      }
      scale = boundedScale;
      updateTransform();
    }

    viewport.addEventListener('pointerdown', (event) => {
      if (event.target.closest('.umldoc-class-node, button, input')) return;
      isDragging = true;
      pointerId = event.pointerId;
      viewport.setPointerCapture(pointerId);
      viewport.classList.add('is-dragging');
      startX = event.clientX - translateX;
      startY = event.clientY - translateY;
    });
    viewport.addEventListener('pointermove', (event) => {
      if (!isDragging) return;
      translateX = event.clientX - startX;
      translateY = event.clientY - startY;
      updateTransform();
    });
    function stopDragging(event) {
      if (!isDragging) return;
      isDragging = false;
      viewport.releasePointerCapture?.(pointerId || event.pointerId);
      pointerId = null;
      viewport.classList.remove('is-dragging');
    }
    viewport.addEventListener('pointerup', stopDragging);
    viewport.addEventListener('pointercancel', stopDragging);
    viewport.addEventListener('wheel', (event) => {
      event.preventDefault();
      const rect = viewport.getBoundingClientRect();
      updateZoom(scale * (event.deltaY < 0 ? 1.12 : .87), { x: event.clientX - rect.left, y: event.clientY - rect.top });
    }, { passive: false });

    document.getElementById('zoomIn').addEventListener('click', () => updateZoom(scale * 1.25));
    document.getElementById('zoomOut').addEventListener('click', () => updateZoom(scale / 1.25));
    document.getElementById('zoomReset').addEventListener('click', () => {
      scale = .85;
      translateX = 32;
      translateY = 32;
      updateTransform();
    });

    updateTransform();
  </script>
</body>
</html>`;
  }

  private _escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  public dispose() {
    DiagramPanel.currentPanel = undefined;
    this._panel.dispose();
    while (this._disposables.length) {
      const d = this._disposables.pop();
      if (d) d.dispose();
    }
  }
}
