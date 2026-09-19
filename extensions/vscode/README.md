# UMLdoc VS Code Extension

Interactive, verified UML architecture diagrams, class hierarchies, and documentation dossiers directly inside Visual Studio Code.

---

## Features

- 📐 **Live Interactive Architecture**: Visualizes class hierarchies, protocols, attributes, and relationships with crisp, standalone vector diagrams.
- ⚡ **Bi-Directional Navigation**: Click any class box or method in the diagram to instantly jump to its definition in your editor (`revealRange`).
- 🔄 **Auto-Refresh on Save**: Diagram automatically updates when Python files are edited and saved.
- 🔍 **Real-Time Filtering**: Filter classes on the fly with fuzzy search highlighting.
- 🖱️ **Pan & Zoom Controls**: Smooth canvas panning, mouse-wheel zooming, and reset view.
- 📦 **One-Click Dossier Export**: Generate zero-dependency HTML dossiers, PlantUML (`.puml`), Mermaid (`.mmd`), and SVG bundles.

---

## Quick Start / Development

### 1. Install Dependencies & Compile
From the `extensions/vscode` directory:

```bash
cd extensions/vscode
npm install
npm run compile
```

### 2. Run & Debug in VS Code
1. Open the `UMLdoc` repository in VS Code.
2. Press `F5` (or go to **Run and Debug** -> **Launch Extension**).
3. In the new [Extension Development Host] window that opens:
   - Open any Python file.
   - Click the diagram icon in the top right of the editor toolbar, or run:
     `Ctrl+Shift+P` -> `UMLdoc: Open Architecture Diagram`

### 3. Package as .vsix Installer
To build a distributable `.vsix` file:

```bash
npx @vscode/vsce package
```

Install it into any VS Code instance:
```bash
code --install-extension umldoc-vscode-0.1.0.vsix
```

---

## Configuration

| Setting | Default | Description |
| :--- | :--- | :--- |
| `umldoc.pythonPath` | `""` (auto-detect) | Path to Python interpreter (defaults to active workspace virtualenv) |
| `umldoc.autoRefreshOnSave` | `true` | Automatically refresh diagram when saving `.py` files |
