import * as vscode from 'vscode';
import { spawn } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

export interface DocumentIRData {
  project_name: string;
  static_model?: {
    classes: Array<{
      name: string;
      kind: string;
      attributes: Array<{ name: string; type_annotation?: string; visibility: string }>;
      methods: Array<{ name: string; return_type?: string; visibility: string }>;
      source_location?: {
        file_path: string;
        start_line: number;
        end_line: number;
      };
    }>;
    relations: Array<{
      source_id: string;
      target_id: string;
      relation_type: string;
      label?: string;
    }>;
  };
}

export class PythonBridge {
  public static getPythonPath(workspaceRoot: string): string {
    const config = vscode.workspace.getConfiguration('umldoc');
    const customPath = config.get<string>('pythonPath');
    if (customPath && customPath.trim().length > 0) {
      return customPath.trim();
    }

    // Check workspace virtualenv
    const isWindows = process.platform === 'win32';
    const venvCandidates = isWindows
      ? [
          path.join(workspaceRoot, '.venv', 'Scripts', 'python.exe'),
          path.join(workspaceRoot, 'venv', 'Scripts', 'python.exe'),
          path.join(workspaceRoot, 'env', 'Scripts', 'python.exe'),
        ]
      : [
          path.join(workspaceRoot, '.venv', 'bin', 'python'),
          path.join(workspaceRoot, 'venv', 'bin', 'python'),
          path.join(workspaceRoot, 'env', 'bin', 'python'),
        ];

    for (const cand of venvCandidates) {
      if (fs.existsSync(cand)) {
        return cand;
      }
    }

    return isWindows ? 'python' : 'python3';
  }

  public static async executeCLI(
    workspaceRoot: string,
    args: string[]
  ): Promise<{ stdout: string; stderr: string }> {
    const pythonBin = this.getPythonPath(workspaceRoot);

    // Ensure umldoc source directory is on PYTHONPATH if running in development repo
    const parentSrc = path.resolve(workspaceRoot, 'src');
    const env = { ...process.env };
    if (fs.existsSync(parentSrc)) {
      env.PYTHONPATH = env.PYTHONPATH
        ? `${parentSrc}${path.delimiter}${env.PYTHONPATH}`
        : parentSrc;
    }

    return new Promise((resolve, reject) => {
      const fullArgs = ['-m', 'umldoc.cli', ...args];
      const proc = spawn(pythonBin, fullArgs, {
        cwd: workspaceRoot,
        env,
      });

      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      proc.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      proc.on('close', (code) => {
        if (code === 0) {
          resolve({ stdout, stderr });
        } else {
          reject(new Error(`UMLdoc CLI exited with code ${code}:\n${stderr || stdout}`));
        }
      });

      proc.on('error', (err) => {
        reject(new Error(`Failed to spawn Python process (${pythonBin}): ${err.message}`));
      });
    });
  }

  public static async extractDocumentIR(workspaceRoot: string, targetPath: string): Promise<DocumentIRData> {
    const { stdout } = await this.executeCLI(workspaceRoot, ['--path', targetPath, '--json']);
    return JSON.parse(stdout) as DocumentIRData;
  }

  public static async generateSVG(workspaceRoot: string, targetPath: string, outputDir: string): Promise<string> {
    await this.executeCLI(workspaceRoot, [
      '--path',
      targetPath,
      '--output',
      outputDir,
      '--format',
      'svg',
    ]);
    const svgPath = path.join(outputDir, 'architecture.svg');
    if (!fs.existsSync(svgPath)) {
      throw new Error(`SVG output not found at ${svgPath}`);
    }
    return fs.readFileSync(svgPath, 'utf-8');
  }

  public static async exportBundle(workspaceRoot: string, targetPath: string, outputDir: string): Promise<string> {
    await this.executeCLI(workspaceRoot, [
      '--path',
      targetPath,
      '--output',
      outputDir,
      '--format',
      'all',
    ]);
    return path.join(outputDir, 'index.html');
  }
}
