import * as vscode from 'vscode';
import * as path from 'path';
import { DiagramPanel } from './diagramPanel';
import { PythonBridge } from './pythonBridge';

export function activate(context: vscode.ExtensionContext) {
  let refreshTimer: NodeJS.Timeout | undefined;

  function getWorkspaceRoot(): string | undefined {
    const folders = vscode.workspace.workspaceFolders;
    return folders && folders.length > 0 ? folders[0].uri.fsPath : undefined;
  }

  function getTargetDirectory(): string | undefined {
    const editor = vscode.window.activeTextEditor;
    if (editor && editor.document.uri.scheme === 'file') {
      return path.dirname(editor.document.uri.fsPath);
    }
    return getWorkspaceRoot();
  }

  // 1. Command: Open Architecture Diagram
  const openCmd = vscode.commands.registerCommand('umldoc.openDiagram', async () => {
    const workspaceRoot = getWorkspaceRoot();
    if (!workspaceRoot) {
      vscode.window.showErrorMessage('UMLdoc: Please open a workspace folder to view architecture diagrams.');
      return;
    }

    const targetDir = getTargetDirectory() || workspaceRoot;
    DiagramPanel.createOrShow(context.extensionUri, workspaceRoot, targetDir);
  });

  // 2. Command: Refresh Architecture Diagram
  const refreshCmd = vscode.commands.registerCommand('umldoc.refreshDiagram', () => {
    if (DiagramPanel.currentPanel) {
      DiagramPanel.currentPanel.refresh();
    } else {
      vscode.commands.executeCommand('umldoc.openDiagram');
    }
  });

  // 3. Command: Export Architecture Dossier Bundle
  const exportCmd = vscode.commands.registerCommand('umldoc.exportBundle', async () => {
    const workspaceRoot = getWorkspaceRoot();
    if (!workspaceRoot) {
      vscode.window.showErrorMessage('UMLdoc: Please open a workspace folder to export bundles.');
      return;
    }

    const targetDir = getTargetDirectory() || workspaceRoot;
    const projectName = path.basename(targetDir);
    const outputDir = path.join(workspaceRoot, 'output', 'bundles', projectName);

    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: `UMLdoc: Packaging architecture dossier for ${projectName}...`,
        cancellable: false,
      },
      async () => {
        try {
          const dossierPath = await PythonBridge.exportBundle(workspaceRoot, targetDir, outputDir);
          const choice = await vscode.window.showInformationMessage(
            `Dossier bundle successfully generated at output/bundles/${projectName}/`,
            'Open Dossier',
            'View Folder'
          );

          if (choice === 'Open Dossier') {
            await vscode.env.openExternal(vscode.Uri.file(dossierPath));
          } else if (choice === 'View Folder') {
            await vscode.commands.executeCommand('revealFileInOS', vscode.Uri.file(dossierPath));
          }
        } catch (err: any) {
          vscode.window.showErrorMessage(`Export failed: ${err.message || String(err)}`);
        }
      }
    );
  });

  // 4. Auto-refresh on Save (if enabled in settings)
  const saveListener = vscode.workspace.onDidSaveTextDocument((doc) => {
    if (doc.languageId !== 'python') return;
    const autoRefresh = vscode.workspace
      .getConfiguration('umldoc')
      .get<boolean>('autoRefreshOnSave', true);

    if (autoRefresh && DiagramPanel.currentPanel) {
      if (refreshTimer) clearTimeout(refreshTimer);
      refreshTimer = setTimeout(() => {
        DiagramPanel.currentPanel?.refresh();
      }, 500);
    }
  });

  context.subscriptions.push(openCmd, refreshCmd, exportCmd, saveListener);
}

export function deactivate() {}
