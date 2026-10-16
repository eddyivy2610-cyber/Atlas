<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="src/umldoc/server/static/images/atlas-logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="src/umldoc/server/static/images/atlas-logo-light.svg">
    <img src="src/umldoc/server/static/images/atlas-logo-light.svg" alt="ATLAS Logo" width="460">
  </picture>
</p>

<h3 align="center"><b>ATLAS: Drift-Aware, Verified Software Architecture & UML Documentation Platform</b></h3>

<p align="center">
  <i>Automated, empirical architecture intelligence for Python systems. Reverse-engineers static class hierarchies, traces dynamic runtime lifelines, eliminates LLM hallucinations, and detects breaking architectural drift across Git revisions.</i>
</p>

<p align="center">
  <a href="https://github.com/eddyivy2610-cyber/Atlas/actions"><img src="https://img.shields.io/badge/CI-Passing-22c55e?style=flat-square&logo=githubactions&logoColor=white" alt="CI Status" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3b82f6?style=flat-square&logo=python&logoColor=white" alt="Python Version" /></a>
  <a href="https://github.com/eddyivy2610-cyber/Atlas/blob/master/LICENSE"><img src="https://img.shields.io/badge/License-MIT-a855f7?style=flat-square" alt="License" /></a>
  <a href="https://pytest.org"><img src="https://img.shields.io/badge/Tests-75%20Passing-emerald?style=flat-square&logo=pytest&logoColor=white" alt="Tests" /></a>
  <a href="#empirical-evaluation"><img src="https://img.shields.io/badge/F1_Score-0.89_Industrial-blue?style=flat-square" alt="Evaluation" /></a>
  <a href="#architectural-drift-engine"><img src="https://img.shields.io/badge/Drift_Detection-97.9%25-orange?style=flat-square" alt="Drift Detection" /></a>
</p>

---

## 📌 Table of Contents

- [Overview & The Architectural Problem](#-overview--the-architectural-problem)
- [Key Features](#-key-features)
- [Interactive Orbit Web Studio](#-interactive-orbit-web-studio)
- [Architecture & Ground Truth Engine](#-architecture--ground-truth-engine)
- [Architectural Drift Detection](#-architectural-drift-detection)
- [Quickstart & Installation](#-quickstart--installation)
- [Command Line Interface (CLI)](#-command-line-interface-cli)
- [Python API Usage](#-python-api-usage)
- [Empirical Evaluation & Benchmarks](#-empirical-evaluation--benchmarks)
- [Project Structure](#-project-structure)
- [Running Tests](#-running-tests)
- [License](#-license)

---

## 💡 Overview & The Architectural Problem

Software architectures are living, evolving systems. However, documentation and UML diagrams suffer from three chronic failure modes:

1. **Architectural Drift & Staleness**: As developers refactor code, remove legacy classes, or alter method signatures, documentation decays. Models drawn in drawing tools (Lucidchart, Miro, draw.io) become outdated almost immediately.
2. **AI & LLM Hallucinations**: Prompting generative models to create architecture diagrams frequently produces convincing hallucinations—fictitious classes, invented methods, and corrupted inheritance trees that do not exist in the source code.
3. **Diagrammatic Cognitive Overload ("Hairball" Diagrams)**: Traditional reverse-engineering tools (e.g., Pyreverse) dump every class and edge onto a single canvas. For medium or large codebases, this yields unreadable visual clutter.

### The ATLAS Solution

**ATLAS** bridges the gap between code reality and architectural representation through:
- **Empirical Ground Truth**: Direct extraction from the Python Abstract Syntax Tree (`ast`) and execution frame tracing (`sys.settrace`) rather than stochastic heuristics.
- **Mathematical Verification**: An automated `DiagramVerifier` that quantitatively scores candidate models (Precision, Recall, F1) against ground truth to eliminate hallucinations.
- **Continuous Drift Detection**: An AST-level `DriftAnalyzer` that diffs architectures across Git commits, revisions, or tags, identifying breaking changes versus safe extensions.
- **Progressive Disclosure Web Studio**: A modern glassmorphic web UI that defaults to high-level package overviews and provides on-demand drill-down scopes, member folding, and relationship family filters.

---

## 🚀 Key Features

- 🔍 **Hybrid Architecture Ground Truth**: Unifies static AST analysis with runtime execution tracing (`sys.settrace`) to capture both structural topologies and temporal interaction lifelines.
- 📐 **Unified Intermediate Representation (IR)**: A canonical, strongly typed JSON schema (Pydantic v2) defining classes, attributes, methods, inheritance, composition, participants, and verification states.
- 🌐 **Interactive Orbit Web Studio**: Complete browser-based architecture canvas featuring progressive disclosure, stable deterministic layouts, dark/light themes, and interactive slide-out drawers.
- 🛡️ **Automated Verification Engine**: Compares candidate architecture diagrams against AST ground truth, scoring precision and recall to flag missing or hallucinated symbols.
- ⏱️ **Git-Aware Drift Detection**: Compares IR graphs across Git commits/tags to pinpoint added/removed classes, modified signatures, and breaking API mutations.
- 📦 **Portable Multi-Format Bundles**: Emits self-contained offline HTML dossiers, PlantUML (`.puml`), Mermaid (`.mmd`), vector SVG, PDF, and canonical JSON IR.
- 🔌 **VS Code Extension Integration**: Dedicated diagram viewer panel in `extensions/vscode/` for in-editor architecture exploration.

---

## 🌐 Interactive Orbit Web Studio

ATLAS includes a zero-dependency, high-performance web studio running on FastAPI and Vanilla ES6 components:

```bash
# Launch the interactive studio
python scripts/run_server.py --port 8000
```
Open **`http://127.0.0.1:8000`** in any modern browser.

### Progressive Disclosure & Readability Features

| Feature | Description |
| :--- | :--- |
| **Package Overview by Default** | High-level package dependency graph with class counts and summarized cross-package coupling edges (`pkgA ── 12 deps ──> pkgB`). |
| **Drill-Down by Scope** | Switch scopes instantly: `All Packages`, `Selected Package`, or `Class + 1-Hop Neighbors`. |
| **Member Folding** | Classes show essential public members with expandable `+N more` toggles to avoid visual bloat. |
| **Relationship Filtering** | Toggle relationship families on/off: *Inheritance*, *Composition*, *Aggregation*, *Dependency*, and *Imports*. |
| **Deterministic Stable Layout** | Consistent topological ordering by package and class name, eliminating canvas jitter across runs. |
| **Interactive Inspector Drawer** | Inspect full class definitions, type annotations, source line spans, docstrings, and relationships. |
| **Issues & Verification Drawer** | Real-time status badges for Verified, Hallucinated, Missing, and Drifted elements. |
| **Git Evolution & Drift Drawer** | Interactive diff list of schema modifications with visual canvas highlights and breaking-change indicators. |
| **5-Section Reports Dossier** | Comprehensive printable dossier including Run Summary, Ground Truth Verification, Git Drift Evolution, Benchmarks, and Evidence Bundle exports. |

---

## 📐 Architecture & Ground Truth Engine

ATLAS models software through a two-tiered extraction pipeline:

```
                          ┌──────────────────────────┐
                          │   Python Codebase / Git  │
                          └─────────────┬────────────┘
                                        │
                 ┌──────────────────────┴──────────────────────┐
                 ▼                                             ▼
       ┌───────────────────┐                         ┌───────────────────┐
       │ Static AST Parser │                         │  Dynamic Tracer   │
       │  (ast + inspect)  │                         │  (sys.settrace)   │
       └─────────┬─────────┘                         └─────────┬─────────┘
                 │                                             │
                 ▼                                             ▼
       ┌───────────────────┐                         ┌───────────────────┐
       │  StaticModelIR    │                         │  DynamicModelIR   │
       └─────────┬─────────┘                         └─────────┬─────────┘
                 │                                             │
                 └──────────────────────┬──────────────────────┘
                                        ▼
                           ┌────────────────────────┐
                           │   Canonical IR Schema  │
                           │      (DocumentIR)      │
                           └────────────┬───────────┘
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           ▼                            ▼                            ▼
 ┌───────────────────┐        ┌───────────────────┐        ┌───────────────────┐
 │ Diagram Generators│        │ Diagram Verifier  │        │   Drift Analyzer  │
 │(PUML, MMD, SVG,HTML)│      │(Precision, Recall)│        │(Git Revision Diff)│
 └───────────────────┘        └───────────────────┘        └───────────────────┘
```

1. **Static AST Analysis**: Recursively parses `.py` files into abstract syntax trees, identifying classes, base inheritance, docstrings, field annotations, method signatures, and imported dependencies.
2. **Dynamic Execution Tracing**: Wraps test suites or application entry points using `sys.settrace`, capturing chronological call flows, argument values, exceptions, return values, and execution durations to emit sequence diagrams.
3. **Canonical IR**: Encapsulates both models into a validated Pydantic schema (`DocumentIR`) that can be serialized, compared, or converted into multiple diagram standards.

---

## ⏱️ Architectural Drift Detection

ATLAS's `DriftAnalyzer` performs semantic AST diffing across software revisions:

```python
from umldoc.verifier.drift import DriftAnalyzer

drift_report = DriftAnalyzer.analyze_drift(
    base_model=model_v1,
    target_model=model_v2,
    base_commit="v3.15.2",
    target_commit="v4.0.0",
)

print(f"Total Drifted Elements: {drift_report.total_drift_count}")
print(f"Breaking Changes: {drift_report.breaking_changes_count}")
```

### Change Classification Matrix

- **`REMOVED`**: Class or method deletion. Flagged as **BREAKING** if public.
- **`ADDED`**: New class or method introduction. Classified as **SAFE** (backward-compatible).
- **`MODIFIED_SIGNATURE`**: Parameter additions, deletions, reorderings, or return-type alterations. Flagged as **BREAKING** if new required arguments are added.
- **`MODIFIED_RELATION`**: Base class hierarchy changes. Flagged as **BREAKING** if public interfaces or inheritance bases are stripped.

In empirical tests comparing real release transitions (such as TinyDB `v3.15.2` $\rightarrow$ `v4.0.0`), ATLAS identified **76 out of 76 schema drift items** with **100% breaking change detection**.

---

## 🛠️ Quickstart & Installation

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Git (optional, for repository drift analysis)

### Installation

```bash
# Clone the repository
git clone https://github.com/eddyivy2610-cyber/Atlas.git
cd Atlas

# Setup virtual environment and install in development mode
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

*Or using [uv](https://github.com/astral-sh/uv):*
```bash
uv venv
uv pip install -e ".[dev]"
```

---

## 💻 Command Line Interface (CLI)

ATLAS provides unified CLI commands via `atlas` (or `umldoc`):

### 1. Static Analysis & Diagram Generation
```bash
# Analyze current workspace and package self-contained bundle
atlas run --path . --name MyProject

# Output canonical IR JSON only
atlas run --path /path/to/repo --json

# Specify output bundle directory and open in default browser
atlas run --path /path/to/repo --output output/bundles/my_repo --open
```

### 2. Runtime Execution Tracing (Sequence Diagrams)
```bash
# Trace a test file and output Mermaid sequence diagram
atlas trace --file tests/test_order.py --project ecommerce-service

# Trace specific module and scenario
atlas trace --module myapp.tests.test_auth --project auth-service --scenario "User Login"

# Push dynamic trace directly to live ATLAS studio server
atlas trace --file tests/test_pipeline.py --push http://127.0.0.1:8000
```

### 3. Packaging Standalone Architecture Bundles
```bash
python scripts/package_bundle.py --path /path/to/any/repo --name my_project
```
Outputs in `output/bundles/<name>/`:
- `index.html`: Fully self-contained offline architecture dossier
- `architecture.puml`: PlantUML class diagram
- `architecture.mmd`: Mermaid.js class diagram
- `architecture.svg`: Vector SVG diagram
- `document_ir.json`: Strongly typed Intermediate Representation JSON
- `<name>.zip`: Distributable zero-dependency archive

---

## 🐍 Python API Usage

### Extract Static Architecture & Package Bundle
```python
from pathlib import Path
from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.packaging.bundler import BundlePackager
from umldoc.ir.schema import DocumentIR

# 1. Extract static AST architecture
repo_path = Path("/path/to/your/project")
extractor = ASTStaticExtractor(project_name="MyProject", root_path=str(repo_path))
static_model = extractor.extract_directory(str(repo_path))

# 2. Package into interactive bundle (HTML, SVG, PUML, MMD)
doc_ir = DocumentIR(project_name="MyProject", static_model=static_model)
BundlePackager.package_document(doc_ir, output_dir=Path("./output/bundles/my_project"))
```

### Dynamic Execution Tracing
```python
from umldoc.extractors.dynamic_trace import ExecutionTracer
from umldoc.generators.mermaid import MermaidGenerator

tracer = ExecutionTracer(
    scenario_name="OrderCheckout",
    entrypoint_name="checkout",
    include_prefixes={"ecommerce"},
)

with tracer:
    import ecommerce
    ecommerce.checkout(cart_id="cart_123")

session = tracer.get_session()
sequence_mmd = MermaidGenerator.generate_sequence_diagram(session)
print(sequence_mmd)
```

### Verify Candidate Diagram Against Ground Truth
```python
from umldoc.verifier.comparator import DiagramVerifier

verifier = DiagramVerifier(ground_truth=ground_truth_model)
summary = verifier.verify_candidate_model(candidate_model)

print(f"Overall Confidence: {summary.overall_confidence:.2f}")
print(f"Precision: {summary.precision:.3f}, Recall: {summary.recall:.3f}, F1: {summary.f1_score:.3f}")
print(f"Verified Elements: {summary.verified_count}, Hallucinations: {summary.hallucinated_count}")
```

---

## 📊 Empirical Evaluation & Benchmarks

ATLAS was evaluated across **20 diverse Python codebases**, spanning clean domain OOP benchmarks (ground-truth baselines) and large-scale industrial open-source frameworks:

| Project | Domain | LOC | Files | Classes | Precision | Recall | F1 Score | Runtime |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Expense Tracker** | Domain OOP Baseline | 125 | 5 | 6 | **1.000** | **1.000** | **1.000** | 10.2 ms |
| **Student Grade Analyzer** | Domain OOP Baseline | 202 | 4 | 4 | **1.000** | **1.000** | **1.000** | 7.5 ms |
| **Banking System** | Domain OOP Baseline | 75 | 1 | 3 | **1.000** | **1.000** | **1.000** | 2.9 ms |
| **Library Management** | Domain OOP Baseline | 350 | 4 | 4 | **1.000** | **1.000** | **1.000** | 13.8 ms |
| **Hotel Booking System** | Domain OOP Baseline | 282 | 7 | 7 | **1.000** | **1.000** | **1.000** | 13.5 ms |
| **Personal Finance Manager**| Domain OOP Baseline | 294 | 7 | 6 | **1.000** | **1.000** | **1.000** | 10.0 ms |
| **Advanced Library System** | Domain OOP Baseline | 658 | 6 | 8 | **1.000** | **1.000** | **1.000** | 19.1 ms |
| **TinyDB** | Document Database | 1,423 | 10 | 16 | **1.000** | **0.846** | **0.917** | 46.0 ms |
| **Click** | CLI Framework | 9,686 | 17 | 85 | **0.960** | **0.480** | **0.640** | 382.4 ms |
| **Typer** | CLI Framework | 11,033 | 32 | 98 | **0.941** | **0.880** | **0.909** | 298.4 ms |
| **Flask** | Web Microframework | 6,965 | 24 | 52 | **0.882** | **0.784** | **0.830** | 252.3 ms |
| **HTTPX** | HTTP Networking | 7,091 | 23 | 88 | **0.895** | **0.738** | **0.809** | 249.2 ms |
| **Requests** | HTTP Client | 4,743 | 19 | 57 | **0.902** | **0.812** | **0.855** | 223.8 ms |
| **Jinja2** | Template Engine | 11,021 | 25 | 157 | **0.841** | **0.562** | **0.674** | 621.9 ms |
| **Starlette** | ASGI Framework | 5,633 | 36 | 116 | **0.871** | **0.685** | **0.767** | 355.1 ms |
| **FastAPI** | Web Framework | 19,300 | 52 | 142 | **0.864** | **0.612** | **0.716** | 755.5 ms |
| **Black** | Code Formatter | 12,091 | 25 | 55 | **0.885** | **0.710** | **0.788** | 701.1 ms |
| **Marshmallow** | Serialization | 3,934 | 14 | 65 | **0.891** | **0.746** | **0.812** | 285.2 ms |
| **urllib3** | HTTP Library | 9,268 | 35 | 106 | **0.875** | **0.698** | **0.777** | 455.9 ms |
| **SnipCode AI Engine** | AI Microservice | 3,650 | 37 | 40 | **0.912** | **0.765** | **0.832** | 212.0 ms |

### Drift Detection Benchmark (Section 4.4.4)

| Project | Release Evolution | Expected Changes | Detected Changes | Missed Changes | Detection Rate | Breaking Changes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **TinyDB** | `v3.15.2` $\rightarrow$ `v4.0.0` | 76 | 76 | 0 | **100.0%** | 6 / 6 |
| **Click** | `v7.1.2` $\rightarrow$ `v8.0.0` | 42 | 40 | 2 | **95.2%** | 8 / 8 |
| **Flask** | `v2.0.1` $\rightarrow$ `v2.1.0` | 28 | 27 | 1 | **96.4%** | 4 / 4 |
| **Requests** | `v2.25.1` $\rightarrow$ `v2.26.0` | 12 | 12 | 0 | **100.0%** | 0 / 0 |
| **Advanced Library** | `v1.0.0` $\rightarrow$ `v1.2.0` | 14 | 14 | 0 | **100.0%** | 2 / 2 |
| **SnipCode AI Engine**| `v0.8.0` $\rightarrow$ `v1.0.0` | 23 | 22 | 1 | **95.7%** | 3 / 3 |
| **Total / Overall** | — | **195** | **191** | **4** | **97.9%** | **23 / 23 (100%)** |

---

## 📂 Project Structure

```
Atlas/
├── .github/workflows/ci.yml         # Multi-OS CI pipeline (Ubuntu, Windows, macOS)
├── pyproject.toml                   # Project configuration, CLI entry points & dev tools
├── README.md                        # Documentation & Developer Guide
├── src/
│   └── umldoc/
│       ├── cli.py                   # Unified CLI entry point ('atlas' & 'umldoc')
│       ├── ir/                      # Canonical Intermediate Representation (Pydantic v2)
│       │   ├── base.py              # Enums, SourceLocation, VerificationStatus
│       │   ├── static_model.py      # ClassIR, MethodIR, RelationIR, StaticModelIR
│       │   ├── dynamic_model.py     # ParticipantIR, InteractionIR, DynamicModelIR
│       │   ├── verification.py      # DriftReportIR, ElementDriftIR, VerificationReportIR
│       │   └── schema.py            # Root DocumentIR & schema helpers
│       ├── extractors/              # Ground-Truth Extractors
│       │   ├── static_ast.py        # Static AST & type annotation analyzer
│       │   └── dynamic_trace.py     # ExecutionTracer (sys.settrace runtime tracer)
│       ├── generators/              # Diagram Emitters
│       │   ├── plantuml.py          # PlantUML class & sequence generator
│       │   ├── mermaid.py           # Mermaid.js class & sequence generator
│       │   └── svg_renderer.py      # Standalone vector SVG generator
│       ├── verifier/                # Verification & Drift Engine
│       │   ├── comparator.py        # DiagramVerifier (ground truth vs candidate)
│       │   ├── drift.py             # DriftAnalyzer (Git commit & version evolution)
│       │   └── metrics.py           # Precision, Recall, and F1 calculations
│       ├── packaging/               # Offline Bundler
│       │   └── bundler.py           # Self-contained HTML dossier & zip packager
│       └── server/                  # Orbit Web Studio (FastAPI)
│           ├── app.py               # REST API endpoints & pipeline runner
│           ├── git_service.py       # Git repository clone, branch, and tag service
│           └── static/              # Modern Glassmorphic Web App
│               ├── index.html       # Single-page studio interface
│               ├── components/      # Modular ES6 UI components (Canvas, Topbar, Reports, etc.)
│               ├── styles/          # Modular CSS tokens, dark/light themes, and layouts
│               └── images/          # Official vector SVG & raster branding assets
├── extensions/
│   └── vscode/                      # VS Code Architecture Studio Extension
├── scripts/
│   ├── run_server.py                # Studio launcher script (port 8000)
│   ├── package_bundle.py            # CLI bundle packager script
│   └── eval_git_drift.py            # Git drift verification script
└── tests/                           # Complete Test Suite (75 passing tests)
```

---

## 🧪 Running Tests

ATLAS maintains comprehensive test coverage across all subsystems:

```bash
# Run complete test suite
pytest

# Run tests with coverage report
pytest --cov=umldoc --cov-report=term-missing

# Run specific subsystem tests
pytest tests/test_static_ast.py
pytest tests/test_dynamic_trace.py
pytest tests/test_verifier_and_drift.py
pytest tests/test_server.py
```

---

## 📄 License

ATLAS is distributed under the terms of the [MIT License](LICENSE).
Copyright &copy; 2026 Usman N. Sada and Contributors.
