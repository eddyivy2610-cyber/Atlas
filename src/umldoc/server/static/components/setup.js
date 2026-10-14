/**
 * Setup Modal Controller (ATLAS / UMLdoc Modern Draft Studio)
 * 
 * Rebuilds the Project Onboarding & Setup form to match the theme tokens:
 * - Pure white / pure black backgrounds, #090C9B primary accent
 * - Real live scanning via /api/scan?path=...
 * - Live execution via POST /api/run and GET /api/classes
 * - Zero hardcoded mock results
 */

export class SetupModalComponent {
  constructor(options = {}) {
    this.container = options.container || options.modal || document.getElementById('setupCard') || document.getElementById('setupModal');
    this.backdrop = options.backdrop || document.getElementById('setupModalBackdrop');
    this.onWorkspaceCreated = options.onWorkspaceCreated || (() => {});
    this.onScan = options.onScan || (() => {});
    this.onLog = options.onLog || (() => {});

    this.scanDebounceTimer = null;
    this.currentMethod = 'upload'; // 'upload' | 'git'
    this.isAnalyzing = false;
    this.lastScanData = null;

    this.init();
  }

  init() {
    if (!this.container) {
      this.container = document.getElementById('setupCard') || document.getElementById('setupModal');
    }
    if (!this.container) return;
    this.bindEvents();
  }

  bindEvents() {
    // 1. Close triggers (in modal mode)
    const closeBtn = this.container.querySelector('#btnSetupClose');
    if (closeBtn) closeBtn.addEventListener('click', () => this.close());

    const cancelBtn = this.container.querySelector('#btnSetupCancel');
    if (cancelBtn) cancelBtn.addEventListener('click', () => this.close());

    if (this.backdrop) {
      this.backdrop.addEventListener('click', (e) => {
        if (e.target === this.backdrop && !this.isAnalyzing) {
          this.close();
        }
      });

      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.isOpen() && !this.isAnalyzing) {
          this.close();
        }
      });
    }

    // 2. Preset Chips (Real repositories)
    this.container.querySelectorAll('.preset-chip-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this.container.querySelectorAll('.preset-chip-btn').forEach(b => b.classList.remove('is-active'));
        btn.classList.add('is-active');

        const presetName = btn.dataset.preset;
        const presetPath = btn.dataset.path || '';

        const nameInput = this.container.querySelector('#setupWorkspaceName') || this.container.querySelector('#ghRepoName');
        const pathInput = this.container.querySelector('#setupFolderPath') || this.container.querySelector('#ghFolderPath');

        if (nameInput) nameInput.value = presetName;
        if (pathInput) {
          pathInput.value = presetPath;
          this.triggerScan(presetPath);
        }
      });
    });

    // 3. Source Method Switcher (Upload vs Git)
    const methodBtns = this.container.querySelectorAll('.setup-source-btn');
    const uploadArea = this.container.querySelector('#setupUploadArea');
    const gitArea = this.container.querySelector('#setupGitArea');

    const gitUrlInput = this.container.querySelector('#setupGitUrl') || this.container.querySelector('#gitCloneUrl');
    const gitTokenInput = this.container.querySelector('#setupGitToken');

    methodBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        methodBtns.forEach(b => b.classList.remove('is-active'));
        btn.classList.add('is-active');
        this.currentMethod = btn.dataset.method;

        if (this.currentMethod === 'upload') {
          if (uploadArea) uploadArea.style.display = 'flex';
          if (gitArea) gitArea.style.display = 'none';
          const pVal = pathInput ? pathInput.value.trim() : '';
          if (pVal) this.triggerScan(pVal);
        } else {
          if (uploadArea) uploadArea.style.display = 'none';
          if (gitArea) gitArea.style.display = 'flex';
          const gVal = gitUrlInput ? gitUrlInput.value.trim() : '';
          if (gVal) this.triggerScan(gVal);
        }
      });
    });

    // 4. Folder Dropzone & File Input
    const dropzone = this.container.querySelector('#setupDropzone');
    const fileInput = this.container.querySelector('#setupFolderInput');
    const pathInput = this.container.querySelector('#setupFolderPath') || this.container.querySelector('#ghFolderPath');
    const nameInput = this.container.querySelector('#setupWorkspaceName') || this.container.querySelector('#ghRepoName');
    const dropzoneTitle = this.container.querySelector('#setupDropzoneTitle');

    if (dropzone && fileInput) {
      dropzone.addEventListener('click', () => fileInput.click());

      fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
          const firstPath = e.target.files[0].webkitRelativePath || e.target.files[0].name;
          const folderName = firstPath.split('/')[0] || 'selected-project';
          
          if (dropzoneTitle) dropzoneTitle.textContent = `Folder: ${folderName}`;
          if (pathInput) pathInput.value = folderName;
          if (nameInput && !nameInput.value.trim()) {
            nameInput.value = folderName;
          }
          this.triggerScan(folderName);
        }
      });
    }

    // 5. Live Path Input with Debounce Scan
    if (pathInput) {
      pathInput.addEventListener('input', (e) => {
        const val = e.target.value.trim();
        clearTimeout(this.scanDebounceTimer);
        this.scanDebounceTimer = setTimeout(() => {
          this.triggerScan(val);
        }, 300);
      });
    }

    // 5b. Live Git URL Input with Auto-Naming & Debounce Scan
    if (gitUrlInput) {
      gitUrlInput.addEventListener('input', (e) => {
        const val = e.target.value.trim();
        if (nameInput && (!nameInput.value.trim() || nameInput.dataset.autoFilled === 'true')) {
          const clean = val.replace(/\.git$/i, '').replace(/\/$/, '');
          const segs = clean.split('/');
          const cand = segs[segs.length - 1];
          if (cand && !cand.includes(':') && !cand.startsWith('http')) {
            nameInput.value = cand;
            nameInput.dataset.autoFilled = 'true';
          }
        }
        clearTimeout(this.scanDebounceTimer);
        this.scanDebounceTimer = setTimeout(() => {
          this.triggerScan(val);
        }, 400);
      });
    }

    if (gitTokenInput) {
      gitTokenInput.addEventListener('input', () => {
        if (gitUrlInput && gitUrlInput.value.trim()) {
          clearTimeout(this.scanDebounceTimer);
          this.scanDebounceTimer = setTimeout(() => {
            this.triggerScan(gitUrlInput.value.trim());
          }, 500);
        }
      });
    }

    // 6. Submit Action (supports #btnSetupSubmit and #btnEnterWorkspace)
    const submitBtn = this.container.querySelector('#btnSetupSubmit') || this.container.querySelector('#btnEnterWorkspace');
    if (submitBtn) {
      submitBtn.addEventListener('click', () => this.submit());
    }
  }

  isOpen() {
    return this.backdrop && this.backdrop.classList.contains('is-open');
  }

  open(initialData = {}) {
    if (this.backdrop) {
      this.backdrop.classList.add('is-open');
    }

    const nameInput = this.container.querySelector('#setupWorkspaceName') || this.container.querySelector('#ghRepoName');
    const pathInput = this.container.querySelector('#setupFolderPath') || this.container.querySelector('#ghFolderPath');

    if (initialData.name && nameInput) nameInput.value = initialData.name;
    if (initialData.path && pathInput) {
      pathInput.value = initialData.path;
      this.triggerScan(initialData.path);
    } else if (pathInput && pathInput.value) {
      this.triggerScan(pathInput.value);
    }

    if (window.lucide) window.lucide.createIcons();
  }

  close() {
    if (!this.backdrop) return;
    this.backdrop.classList.remove('is-open');
  }

  /**
   * Run real dynamic scan via /api/scan?path=...
   */
  async triggerScan(pathVal) {
    const isGit = this.currentMethod === 'git';
    const badge = isGit
      ? (this.container.querySelector('#setupGitScanBadge') || this.container.querySelector('#setupScanBadge'))
      : (this.container.querySelector('#setupScanBadge') || this.container.querySelector('#ghDetectedBadge'));
    if (!badge) return;

    const trimmed = (pathVal || '').trim();
    if (!trimmed) {
      badge.style.display = 'none';
      this.lastScanData = null;
      return;
    }

    badge.style.display = 'inline-flex';
    badge.className = 'setup-scan-badge setup-scan-badge--info';
    badge.innerHTML = isGit
      ? '<i data-lucide="loader-2" class="spin"></i> Verifying repository…'
      : '<i data-lucide="loader-2" class="spin"></i> Scanning folder files…';
    if (window.lucide) window.lucide.createIcons();

    const tokenInput = this.container.querySelector('#setupGitToken');
    const branchInput = this.container.querySelector('#setupGitBranch');
    const tokenVal = (tokenInput?.value || '').trim();

    try {
      let scanUrl = `/api/scan?path=${encodeURIComponent(trimmed)}`;
      if (isGit && tokenVal) {
        scanUrl += `&token=${encodeURIComponent(tokenVal)}`;
      }
      const res = await fetch(scanUrl);
      const data = await res.json();

      if (res.ok && data.status === 'OK') {
        this.lastScanData = data;
        badge.className = 'setup-scan-badge setup-scan-badge--success';
        if (data.is_git && !data.is_cloned) {
          const branchCount = data.branches?.length ? ` (${data.branches.length} branches)` : '';
          badge.innerHTML = `<i data-lucide="check-circle-2"></i> Remote repository verified${branchCount}`;
          if (data.default_branch && branchInput && (!branchInput.value.trim() || branchInput.value === 'main')) {
            branchInput.value = data.default_branch;
          }
        } else if (data.is_git && data.is_cloned) {
          badge.innerHTML = `<i data-lucide="check-circle-2"></i> ${data.system_files_count} Python files (cached clone)`;
        } else {
          badge.innerHTML = `<i data-lucide="check-circle-2"></i> ${data.system_files_count} Python system files detected`;
        }

        // Auto-update workspace name if empty
        const nameInput = this.container.querySelector('#setupWorkspaceName') || this.container.querySelector('#ghRepoName');
        if (nameInput && (!nameInput.value.trim() || nameInput.dataset.autoFilled === 'true') && (data.folder_name || data.repo_name)) {
          nameInput.value = data.folder_name || data.repo_name;
          nameInput.dataset.autoFilled = 'true';
        }

        this.onLog('success', 'Scan Codebase', data.summary || `Live scan found ${data.system_files_count} files in '${data.folder_name}'.`);
        this.onScan(data);
      } else {
        this.lastScanData = null;
        badge.className = 'setup-scan-badge setup-scan-badge--error';
        badge.innerHTML = `<i data-lucide="alert-circle"></i> ${data.error || (isGit ? 'Repository inaccessible' : 'Folder not found on filesystem')}`;
        this.onLog('warn', 'Scan Codebase', data.error || `Path not found: ${trimmed}`);
      }
    } catch (err) {
      this.lastScanData = null;
      badge.className = 'setup-scan-badge setup-scan-badge--error';
      badge.innerHTML = `<i data-lucide="alert-triangle"></i> Scan connection error`;
    }

    if (window.lucide) window.lucide.createIcons();
  }

  /**
   * Submit and execute pipeline via POST /api/run & GET /api/classes
   */
  async submit() {
    if (this.isAnalyzing) return;

    const nameInput = this.container.querySelector('#setupWorkspaceName') || this.container.querySelector('#ghRepoName');
    const pathInput = this.container.querySelector('#setupFolderPath') || this.container.querySelector('#ghFolderPath');
    const gitUrlInput = this.container.querySelector('#setupGitUrl') || this.container.querySelector('#gitCloneUrl');
    const gitBranchInput = this.container.querySelector('#setupGitBranch');
    const gitTokenInput = this.container.querySelector('#setupGitToken');
    const submitBtn = this.container.querySelector('#btnSetupSubmit') || this.container.querySelector('#btnEnterWorkspace');
    const submitText = this.container.querySelector('#setupSubmitText');
    const statusDot = this.container.querySelector('#setupStatusDot');
    const statusText = this.container.querySelector('#setupStatusText');

    const projectName = (nameInput && nameInput.value.trim()) || 'custom-project';
    let targetPath = '';
    let gitUrl = '';
    let gitBranch = 'main';
    let gitToken = '';

    if (this.currentMethod === 'upload') {
      targetPath = (pathInput && pathInput.value.trim()) || '';
      // If path is blank, check if a preset chip is available to auto-default gracefully
      if (!targetPath) {
        const defaultPresetBtn = this.container.querySelector('.preset-chip-btn[data-path]');
        if (defaultPresetBtn) {
          targetPath = defaultPresetBtn.dataset.path;
          if (pathInput) pathInput.value = targetPath;
          if (nameInput && !nameInput.value.trim()) {
            nameInput.value = defaultPresetBtn.dataset.preset || 'umldoc';
          }
        }
      }
      if (!targetPath) {
        const badge = this.container.querySelector('#setupScanBadge') || this.container.querySelector('#ghDetectedBadge');
        if (badge) {
          badge.style.display = 'inline-flex';
          badge.className = 'setup-scan-badge setup-scan-badge--error';
          badge.innerHTML = '<i data-lucide="alert-circle"></i> Please enter a project folder or select a preset';
          if (window.lucide) window.lucide.createIcons();
        }
        if (pathInput) pathInput.focus();
        return;
      }
    } else {
      gitUrl = (gitUrlInput && gitUrlInput.value.trim()) || '';
      gitBranch = (gitBranchInput && gitBranchInput.value.trim()) || 'main';
      gitToken = (gitTokenInput && gitTokenInput.value.trim()) || '';
      targetPath = gitUrl;

      if (!gitUrl) {
        const badge = this.container.querySelector('#setupGitScanBadge') || this.container.querySelector('#setupScanBadge');
        if (badge) {
          badge.style.display = 'inline-flex';
          badge.className = 'setup-scan-badge setup-scan-badge--error';
          badge.innerHTML = '<i data-lucide="alert-circle"></i> Please enter a repository clone URL';
          if (window.lucide) window.lucide.createIcons();
        }
        if (gitUrlInput) gitUrlInput.focus();
        return;
      }
    }

    // Set busy state
    this.isAnalyzing = true;
    if (submitBtn) submitBtn.disabled = true;
    if (submitText) {
      submitText.innerHTML = this.currentMethod === 'git'
        ? '<i data-lucide="loader-2" class="spin"></i> Cloning & Analyzing…'
        : '<i data-lucide="loader-2" class="spin"></i> Analyzing AST…';
    }
    if (statusDot) statusDot.classList.add('is-busy');
    if (statusText) {
      statusText.textContent = this.currentMethod === 'git'
        ? `Cloning & analyzing ${projectName}…`
        : `Analyzing ${projectName}…`;
    }
    if (window.lucide) window.lucide.createIcons();

    this.onLog('running', 'Pipeline Runner', this.currentMethod === 'git'
      ? `Cloning Git repository '${gitUrl}' (branch: ${gitBranch || 'default'})...`
      : `Triggering AST analysis pipeline for '${projectName}' (path: ${targetPath || 'default'})...`
    );

    try {
      // 1. Run pipeline on backend
      const runRes = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project: projectName,
          path: targetPath || undefined,
          git_url: gitUrl || undefined,
          branch: gitBranch || undefined,
          token: gitToken || undefined
        })
      });

      const runData = await runRes.json();
      if (!runRes.ok || runData.status === 'ERROR') {
        throw new Error(runData.error || 'Failed to analyze project code.');
      }

      this.onLog('success', 'Pipeline Runner', `AST extracted ${runData.classes_extracted} classes in ${Math.round(runData.duration_ms)}ms.`);

      // 2. Fetch extracted classes and relations
      let classesUrl = `/api/classes?project=${encodeURIComponent(projectName)}`;
      if (targetPath) classesUrl += `&path=${encodeURIComponent(targetPath)}`;

      const classesRes = await fetch(classesUrl);
      const classesData = await classesRes.json();

      if (!classesRes.ok || classesData.error) {
        throw new Error(classesData.error || 'Failed to retrieve extracted UML model.');
      }

      // 3. Callback with real results
      this.onWorkspaceCreated({
        project: projectName,
        path: targetPath,
        runResult: runData,
        classesData: classesData,
        scanData: this.lastScanData
      });

      // 4. Close modal
      this.close();

    } catch (err) {
      const isGit = this.currentMethod === 'git';
      const badge = isGit
        ? (this.container.querySelector('#setupGitScanBadge') || this.container.querySelector('#setupScanBadge'))
        : (this.container.querySelector('#setupScanBadge') || this.container.querySelector('#ghDetectedBadge'));
      if (badge) {
        badge.style.display = 'inline-flex';
        badge.className = 'setup-scan-badge setup-scan-badge--error';
        badge.innerHTML = `<i data-lucide="alert-circle"></i> Pipeline error: ${err.message}`;
      }
      this.onLog('error', 'Pipeline Runner', `Setup analysis failed: ${err.message}`);
    } finally {
      this.isAnalyzing = false;
      if (submitBtn) submitBtn.disabled = false;
      if (submitText) submitText.innerHTML = '<i data-lucide="play"></i> Analyze & Open Workspace';
      if (statusDot) statusDot.classList.remove('is-busy');
      if (statusText) statusText.textContent = 'Ready';
      if (window.lucide) window.lucide.createIcons();
    }
  }
}
