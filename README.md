# UMLdoc: Drift-Aware, Verified UML Documentation

A developer tool that bridges the gap between code reality and software architecture models. `UMLdoc` generates static class and dynamic sequence UML diagrams from Python codebases, runs an automated verifier scoring each diagram element's fidelity against AST and execution traces, and flags hallucinated, missing, or drifted elements across Git revisions.

---

## Key Features

- 🔍 **Hybrid Architecture Ground Truth**: Combines static AST analysis with runtime execution tracing (`sys.settrace`).
- 📐 **Unified Intermediate Representation (IR)**: A canonical, strongly typed JSON schema covering classes, interfaces, attributes, methods, relations, participants, call interactions, and verification states.
- 🛡️ **Automated Verification Engine**: Scores diagram elements against AST ground truth and execution traces to eliminate hallucinations and detect missing symbols.
- ⏱️ **Drift & Staleness Detection**: Compares IR graphs across Git commits to pinpoint modified signatures, dropped methods, changed call flows, or outdated documentation.
- 📦 **Portable Multi-Format Bundles**: Emits PlantUML (`.puml`), Mermaid (`.mmd`), rendered SVG/PDF, and interactive verification HTML reports.

---

## Phase 0 Evaluation & Architectural Decisions

### 1. Target Evaluation Repositories

| Repository | Domain | Characteristics |
| :--- | :--- | :--- |
| [`tinydb`](https://github.com/msiemens/tinydb) | Document Database | Compact pure Python OOP, Table/Storage composition, query evaluation |
| [`click`](https://github.com/pallets/click) | CLI Framework | Command inheritance hierarchies, decorator-based dispatch, execution lifecycle |
| [`marshmallow`](https://github.com/marshmallow-code/marshmallow) | Serialization & Schemas | Complex class hierarchies, descriptor fields, pre/post hooks |
| [`httpx`](https://github.com/encode/httpx) | HTTP Networking | Client/transport layers, async/sync dispatch, request lifecycle sequences |
| [`rich`](https://github.com/Textualize/rich) | Terminal Rendering & UI | Protocol polymorphism, nested renderable tree traversals |

### 2. Static Extraction Decision
- **Decision**: Custom AST extractor (`ast` + `inspect`) as primary, generating canonical `StaticModelIR` with exact source spans (`lineno`, `end_lineno`), type annotations, and docstrings.
- **Pyreverse comparison**: Pyreverse is used as a benchmark/cross-validation source.

### 3. Dynamic Tracing Decision
- **Decision**: Custom `sys.settrace` execution tracer as primary, capturing participant lifelines, call depths, argument/return snapshots, exceptions, and call durations directly into `DynamicModelIR`.
- **Pydoctrace comparison**: Stack management and error propagation insights incorporated cleanly into the structured event model.

---

## Project Structure

```
UMLdoc/
├── .github/workflows/ci.yml     # Multi-OS CI pipeline (Ubuntu, Windows, macOS)
├── pyproject.toml               # Package configuration & dependencies
├── src/
│   └── umldoc/
│       ├── ir/                  # Intermediate Representation Schema (Pydantic v2)
│       │   ├── base.py          # Shared types, SourceLocation, enums
│       │   ├── static_model.py  # Static architecture IR
│       │   ├── dynamic_model.py # Dynamic trace & sequence IR
│       │   ├── verification.py  # Element verification & drift IR
│       │   └── schema.py        # Root DocumentIR & schema utilities
│       ├── extractors/          # Extractors
│       │   ├── static_ast.py    # AST static extractor
│       │   └── dynamic_trace.py # sys.settrace dynamic tracer
│       ├── generators/          # Diagram emitters
│       │   ├── plantuml.py      # PlantUML class & sequence generator
│       │   └── mermaid.py       # Mermaid class & sequence generator
│       └── verifier/            # Verification & drift engine
│           ├── comparator.py    # Ground truth vs diagram comparator
│           └── drift.py         # Commit drift analyzer
└── tests/
    ├── sample_codebase/         # Embedded testing repository
    ├── test_ir_schema.py
    ├── test_static_ast.py
    ├── test_dynamic_trace.py
    └── test_generators.py
```

---

## Quickstart

```bash
# Setup virtual environment with uv
uv venv
uv pip install -e ".[dev]"

# Run test suite
uv run pytest
```

---

## How to Use on Any Repository

### 1. Command Line Interface (CLI)

Generate a complete, self-contained architecture bundle (HTML dossier, PlantUML, Mermaid, SVG diagrams, and canonical IR JSON) for any Python codebase:

```bash
python scripts/package_bundle.py --path /path/to/any/repo --name my_project
```

Outputs will be saved in `output/bundles/<name>/`:
- `index.html`: Interactive, offline architecture dossier
- `architecture.puml`: PlantUML class diagram
- `architecture.mmd`: Mermaid.js class diagram
- `architecture.svg`: Vector SVG diagram
- `document_ir.json`: Canonical Intermediate Representation JSON
- `<name>.zip`: Distributable zero-dependency zip archive

### 2. Python API

#### Static Class Diagram & IR Extraction
```python
from pathlib import Path
from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.packaging.bundler import BundlePackager
from umldoc.ir.schema import DocumentIR

# 1. Extract static AST architecture
repo_path = Path("/path/to/your/repo")
extractor = ASTStaticExtractor(project_name="MyProject", root_path=str(repo_path))
static_model = extractor.extract_directory(str(repo_path))

# 2. Package into interactive bundle (HTML, SVG, PUML, MMD)
doc_ir = DocumentIR(project_name="MyProject", static_model=static_model)
BundlePackager.package_document(doc_ir, output_dir=Path("./output/bundles/my_project"))
```

#### Dynamic Runtime Sequence Tracing
Capture function and method interactions in real time:
```python
from umldoc.extractors.dynamic_trace import ExecutionTracer
from umldoc.generators.mermaid import MermaidGenerator

tracer = ExecutionTracer(
    scenario_name="UserFlow",
    entrypoint_name="run",
    include_prefixes={"my_package"},
)

with tracer:
    import my_package
    my_package.run()

session = tracer.get_session()
sequence_mmd = MermaidGenerator.generate_sequence_diagram(session)
print(sequence_mmd)
```

#### Git Drift & Evolution Analysis
Compare architecture between two Git revisions or folders:
```python
from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.verifier.drift import DriftAnalyzer

model_v1 = ASTStaticExtractor("App", "/path/to/v1").extract_directory("/path/to/v1")
model_v2 = ASTStaticExtractor("App", "/path/to/v2").extract_directory("/path/to/v2")

drift_report = DriftAnalyzer.analyze_evolution(
    model_v1, model_v2, base_commit="v1.0.0", target_commit="v2.0.0"
)
print(f"Added classes: {drift_report.added_classes}")
print(f"Removed classes: {drift_report.removed_classes}")
print(f"Modified classes: {len(drift_report.modified_classes)}")
```

