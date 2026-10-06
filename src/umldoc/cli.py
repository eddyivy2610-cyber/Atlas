"""ATLAS CLI Entrypoint.

Usage:
    # Static analysis (original)
    atlas run --path /path/to/repo --output output/bundles/my_repo
    atlas run --path /path/to/repo --json
    atlas run --path . --name MyProject

    # Runtime trace → Sequence Diagram
    atlas trace --file path/to/test_checkout.py --project e-commerce-service
    atlas trace --module myapp.tests.test_order --project my-app --scenario "Place Order"
    atlas trace --file tests/test_order.py --push http://127.0.0.1:8000
"""

import argparse
import importlib
import importlib.util
import json
import sys
import webbrowser
from pathlib import Path
from typing import Optional
from urllib import request as urllib_request
from urllib.error import URLError

from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.ir.schema import DocumentIR
from umldoc.packaging.bundler import BundlePackager
from umldoc.generators.mermaid import MermaidGenerator
from umldoc.generators.plantuml import PlantUMLGenerator
from umldoc.generators.svg_renderer import SVGDiagramRenderer


# ──────────────────────────────────────────────────────────────────────────────
# A) Static analysis pipeline  (atlas run)
# ──────────────────────────────────────────────────────────────────────────────

def run_cli(
    path: str,
    output: Optional[str] = None,
    name: Optional[str] = None,
    output_format: str = "all",
    as_json: bool = False,
    open_browser: bool = False,
) -> int:
    target_path = Path(path).resolve()
    if not target_path.exists():
        print(f"[error] Target path does not exist: {target_path}", file=sys.stderr)
        return 1

    project_name = name or target_path.name

    extractor = ASTStaticExtractor(project_name=project_name, root_path=str(target_path))
    static_model = extractor.extract_directory(target_dir=str(target_path))

    doc_ir = DocumentIR(
        project_name=project_name,
        static_model=static_model,
    )

    if as_json:
        print(doc_ir.model_dump_json(indent=2))
        return 0

    out_dir = Path(output).resolve() if output else Path("output") / "bundles" / project_name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"ATLAS: Extracted {len(static_model.classes)} classes and {len(static_model.relations)} relations from {target_path}")

    if output_format in ("all", "puml"):
        puml = PlantUMLGenerator.generate_class_diagram(static_model, title=f"{project_name} Architecture")
        (out_dir / "architecture.puml").write_text(puml, encoding="utf-8")

    if output_format in ("all", "mmd"):
        mmd = MermaidGenerator.generate_class_diagram(static_model, title=f"{project_name} Architecture")
        (out_dir / "architecture.mmd").write_text(mmd, encoding="utf-8")

    if output_format in ("all", "svg"):
        svg = SVGDiagramRenderer.render_class_diagram(static_model, title=f"{project_name} Architecture")
        (out_dir / "architecture.svg").write_text(svg, encoding="utf-8")

    if output_format in ("all", "html"):
        index_file = BundlePackager.package_document(
            document_ir=doc_ir,
            output_dir=out_dir,
            include_zip=True,
        )
        print(f"[success] Generated architecture dossier: {index_file}")
        if open_browser:
            webbrowser.open(index_file.as_uri())

    return 0


# ──────────────────────────────────────────────────────────────────────────────
# B) Runtime tracer CLI  (atlas trace)
# ──────────────────────────────────────────────────────────────────────────────

def _load_module_from_file(file_path: Path):
    """Import a .py file as a fresh module without it needing to be on sys.path."""
    spec = importlib.util.spec_from_file_location("_atlas_trace_target", str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {file_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_atlas_trace_target"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def run_trace(
    file: Optional[str],
    module: Optional[str],
    project: str,
    scenario: str,
    include: Optional[str],
    output: Optional[str],
    push: Optional[str],
    entrypoint: Optional[str],
) -> int:
    from umldoc.extractors.dynamic_trace import ExecutionTracer

    if not file and not module:
        print("[error] Supply --file <path.py> or --module <dotted.module.name>", file=sys.stderr)
        return 1

    include_prefixes = {include} if include else None

    tracer = ExecutionTracer(
        scenario_name=scenario,
        entrypoint_name=entrypoint or (Path(file).stem if file else (module or "trace")),
        include_prefixes=include_prefixes,
    )

    print(f"\n[atlas trace] Project   : {project}")
    print(f"[atlas trace] Scenario  : {scenario}")
    print(f"[atlas trace] Include   : {include or '(all user code)'}")

    # ── Execute under the tracer ──────────────────────────────────────────
    if file:
        target = Path(file).resolve()
        if not target.exists():
            print(f"[error] File not found: {target}", file=sys.stderr)
            return 1
        parent = str(target.parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        print(f"[atlas trace] Running   : {target}")
        with tracer:
            try:
                _load_module_from_file(target)
            except SystemExit:
                pass
            except Exception as exc:
                print(f"[atlas trace] ⚠  Module raised: {type(exc).__name__}: {exc}")

    elif module:
        print(f"[atlas trace] Running   : {module}")
        with tracer:
            try:
                importlib.import_module(module)
            except Exception as exc:
                print(f"[atlas trace] ⚠  Module raised: {type(exc).__name__}: {exc}")

    session = tracer.get_session_ir()
    n_parts = len(session.participants)
    n_events = len(session.interactions)
    print(f"\n[atlas trace] Captured  : {n_parts} participants, {n_events} events  ({session.duration_ms:.1f} ms)")

    if n_events == 0:
        print("[atlas trace] ⚠  No interactions captured. Try setting --include <your_package_name>")

    # ── Save TraceSessionIR to disk ───────────────────────────────────────
    out_dir = Path(output).resolve() if output else Path("output") / "traces"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{project}_{session.session_id}.json"
    out_file.write_text(session.model_dump_json(indent=2), encoding="utf-8")
    print(f"[atlas trace] Saved     : {out_file}")

    # ── Optionally POST to live ATLAS server ──────────────────────────────
    if push:
        server_url = push.rstrip("/")
        endpoint = f"{server_url}/api/trace"
        body = json.dumps({"project": project, "session": session.model_dump()}).encode("utf-8")
        req = urllib_request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                n_msg = len(payload.get("messages", []))
                print(f"[atlas trace] Pushed    : {endpoint}  ->  {n_msg} messages in sequence diagram")
                print(f"[atlas trace] Open      : {server_url}/?project={project}  (switch to Sequence tab)")
        except URLError as exc:
            print(f"[atlas trace] [WARN] Push failed: {exc}. Is the server running?", file=sys.stderr)

    print()
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="atlas",
        description="ATLAS — drift-aware UML documentation and runtime sequence tracer for Python codebases.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # ── atlas run ────────────────────────────────────────────────────────────
    run_p = subparsers.add_parser("run", help="Static analysis: extract class/package diagrams from source code")
    run_p.add_argument("--path", "-p", default=".", help="Path to Python codebase/directory (default: .)")
    run_p.add_argument("--output", "-o", default=None, help="Output destination folder for bundles")
    run_p.add_argument("--name", "-n", default=None, help="Project name (defaults to directory name)")
    run_p.add_argument(
        "--format", "-f",
        choices=["all", "html", "svg", "puml", "mmd", "json"],
        default="all",
        help="Diagram format to emit (default: all)",
    )
    run_p.add_argument("--json", action="store_true", help="Output canonical DocumentIR JSON to stdout")
    run_p.add_argument("--open", action="store_true", help="Open generated HTML dossier in browser")

    # ── atlas trace ──────────────────────────────────────────────────────────
    trace_p = subparsers.add_parser(
        "trace",
        help="Dynamic trace: run a Python file or test and generate a Sequence Diagram from real execution",
    )
    trace_src = trace_p.add_mutually_exclusive_group(required=True)
    trace_src.add_argument("--file", "-f", help="Python file to execute and trace (e.g. tests/test_order.py)")
    trace_src.add_argument("--module", "-m", help="Dotted module to import and trace (e.g. myapp.tests.test_order)")
    trace_p.add_argument("--project", "-p", required=True, help="Project name (matches ATLAS workspace)")
    trace_p.add_argument("--scenario", "-s", default="Execution Trace", help="Scenario label for the sequence diagram")
    trace_p.add_argument(
        "--include", "-i",
        default=None,
        help="Package prefix to include (e.g. 'myapp'). Strongly recommended.",
    )
    trace_p.add_argument("--output", "-o", default=None, help="Output directory for trace JSON (default: output/traces/)")
    trace_p.add_argument(
        "--push",
        default=None,
        help="Push trace to live ATLAS server, e.g. http://127.0.0.1:8000",
    )
    trace_p.add_argument("--entrypoint", "-e", default=None, help="Entrypoint label (cosmetic)")

    # ── legacy flat invocation (backwards compat: atlas --path .) ────────────
    parser.add_argument("--path", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--output", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--name", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--format", default="all", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--open", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.command == "trace":
        code = run_trace(
            file=args.file,
            module=args.module,
            project=args.project,
            scenario=args.scenario,
            include=args.include,
            output=args.output,
            push=args.push,
            entrypoint=args.entrypoint,
        )
    elif args.command == "run" or getattr(args, "path", None):
        path = getattr(args, "path", None) or "."
        output = getattr(args, "output", None)
        name = getattr(args, "name", None)
        fmt = getattr(args, "format", "all")
        as_json = getattr(args, "json", False)
        open_browser = getattr(args, "open", False)
        code = run_cli(
            path=path, output=output, name=name,
            output_format=fmt, as_json=as_json, open_browser=open_browser,
        )
    else:
        parser.print_help()
        code = 0

    sys.exit(code)


if __name__ == "__main__":
    main()
