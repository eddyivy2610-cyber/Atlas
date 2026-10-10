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

    n_pkgs = len(static_model.packages.packages) if static_model.packages else 0
    n_comps = len(static_model.components.components) if static_model.components else 0
    print(f"ATLAS: Extracted {len(static_model.classes)} classes, {n_pkgs} packages, and {n_comps} components from {target_path}")

    if output_format in ("all", "puml"):
        puml = PlantUMLGenerator.generate_class_diagram(static_model, title=f"{project_name} Architecture")
        (out_dir / "architecture.puml").write_text(puml, encoding="utf-8")
        puml_pkg = PlantUMLGenerator.generate_package_diagram(static_model, title=f"{project_name} Packages")
        (out_dir / "packages.puml").write_text(puml_pkg, encoding="utf-8")
        puml_comp = PlantUMLGenerator.generate_component_diagram(static_model, title=f"{project_name} Components")
        (out_dir / "components.puml").write_text(puml_comp, encoding="utf-8")

    if output_format in ("all", "mmd"):
        mmd = MermaidGenerator.generate_class_diagram(static_model, title=f"{project_name} Architecture")
        (out_dir / "architecture.mmd").write_text(mmd, encoding="utf-8")
        mmd_pkg = MermaidGenerator.generate_package_diagram(static_model, title=f"{project_name} Packages")
        (out_dir / "packages.mmd").write_text(mmd_pkg, encoding="utf-8")
        mmd_comp = MermaidGenerator.generate_component_diagram(static_model, title=f"{project_name} Components")
        (out_dir / "components.mmd").write_text(mmd_comp, encoding="utf-8")

    if output_format in ("all", "svg"):
        svg = SVGDiagramRenderer.render_class_diagram(static_model, title=f"{project_name} Architecture")
        (out_dir / "architecture.svg").write_text(svg, encoding="utf-8")
        svg_pkg = SVGDiagramRenderer.render_package_diagram(static_model, title=f"{project_name} Packages")
        (out_dir / "packages.svg").write_text(svg_pkg, encoding="utf-8")
        svg_comp = SVGDiagramRenderer.render_component_diagram(static_model, title=f"{project_name} Components")
        (out_dir / "components.svg").write_text(svg_comp, encoding="utf-8")

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


def _detect_project_name() -> str:
    """Auto-detect project name from pyproject.toml or current directory."""
    pyproj = Path("pyproject.toml")
    if pyproj.is_file():
        try:
            import tomllib
            with open(pyproj, "rb") as f:
                data = tomllib.load(f)
                name = data.get("project", {}).get("name")
                if name:
                    return str(name)
        except Exception:
            pass
    return Path.cwd().name


def run_trace(
    cmd: Optional[list] = None,
    file: Optional[str] = None,
    module: Optional[str] = None,
    project: Optional[str] = None,
    scenario: Optional[str] = None,
    include: Optional[str] = None,
    exclude: Optional[str] = None,
    output: Optional[str] = None,
    output_format: str = "all",
    push: Optional[str] = None,
    entrypoint: Optional[str] = None,
    open_browser: bool = False,
    project_name: Optional[str] = None,
) -> int:
    import runpy
    from umldoc.extractors.dynamic_trace import ExecutionTracer

    cmd = list(cmd) if cmd else []
    project = project or project_name

    # If first token of cmd is a file ending with .py or existing path, treat as file if not already set
    if cmd and not file and not module and (cmd[0].endswith(".py") or Path(cmd[0]).is_file()):
        file = cmd[0]
        cmd = cmd[1:]

    if not cmd and not file and not module:
        print("[error] Supply a command to trace (e.g. 'atlas trace pytest tests/'), --file, or --module", file=sys.stderr)
        return 1

    project_name = project or _detect_project_name()
    project_root = str(Path.cwd().resolve())

    # Detect if target script is outside cwd (e.g., in temp dir or external repo)
    target_script = None
    if file:
        target_script = Path(file).resolve()
    elif cmd:
        for token in cmd:
            if token.endswith(".py") or Path(token).is_file():
                target_script = Path(token).resolve()
                break
    if target_script and target_script.exists():
        cwd_resolved = Path.cwd().resolve()
        try:
            target_script.relative_to(cwd_resolved)
        except ValueError:
            # target is outside cwd, use its parent directory as project root
            project_root = str(target_script.parent)

    # Auto-detect scenario label
    if not scenario:
        if cmd:
            scenario = " ".join(cmd)
        elif file:
            scenario = f"Trace: {Path(file).stem}"
        elif module:
            scenario = f"Trace: {module}"
        else:
            scenario = "Runtime Trace"

    # Auto-detect entrypoint
    entry_label = entrypoint
    if not entry_label:
        if cmd:
            entry_label = " ".join(cmd[:2]) if len(cmd) > 1 else cmd[0]
        elif file:
            entry_label = Path(file).stem
        elif module:
            entry_label = module
        else:
            entry_label = "main"

    include_prefixes = {s.strip() for s in include.split(",") if s.strip()} if include else None
    exclude_prefixes = {s.strip() for s in exclude.split(",") if s.strip()} if exclude else None

    tracer = ExecutionTracer(
        scenario_name=scenario,
        entrypoint_name=entry_label,
        include_prefixes=include_prefixes,
        exclude_prefixes=exclude_prefixes,
        project_root=project_root,
    )

    target_desc = " ".join(cmd) if cmd else (file or module or "trace")
    print(f"\n[atlas trace] Dynamic Execution Tracer")
    print(f"[atlas trace] Project    : {project_name}")
    print(f"[atlas trace] Scenario   : {scenario}")
    print(f"[atlas trace] Target     : {target_desc}")
    print(f"[atlas trace] Root       : {project_root}")
    if include_prefixes:
        print(f"[atlas trace] Include    : {', '.join(sorted(include_prefixes))}")

    # ── Execute Target ────────────────────────────────────────────────────
    exit_code = 0
    if cmd:
        exe = cmd[0]
        if exe == "pytest":
            pytest_args = cmd[1:]
            print(f"[atlas trace] Running in-process pytest: {' '.join(pytest_args) if pytest_args else '.'}")
            try:
                import pytest
                with tracer:
                    exit_code = pytest.main(pytest_args)
            except Exception as exc:
                print(f"[atlas trace] [!] pytest raised: {type(exc).__name__}: {exc}")
                exit_code = 1

        elif exe in ("python", "python3", sys.executable):
            py_args = cmd[1:]
            if not py_args:
                print("[error] 'python' command requires a script path or -m module argument", file=sys.stderr)
                return 1
            if py_args[0] == "-m" and len(py_args) > 1:
                mod_name = py_args[1]
                sys.argv = py_args[1:]
                print(f"[atlas trace] Executing module: {mod_name}")
                with tracer:
                    try:
                        runpy.run_module(mod_name, run_name="__main__", alter_sys=True)
                    except SystemExit as se:
                        exit_code = se.code if isinstance(se.code, int) else 0
                    except Exception as exc:
                        print(f"[atlas trace] [!] Module raised: {type(exc).__name__}: {exc}")
                        exit_code = 1
            else:
                script_path = Path(py_args[0]).resolve()
                if not script_path.exists():
                    print(f"[error] Script not found: {script_path}", file=sys.stderr)
                    return 1
                sys.argv = py_args
                parent_dir = str(script_path.parent)
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                print(f"[atlas trace] Executing script: {script_path.name}")
                with tracer:
                    try:
                        runpy.run_path(str(script_path), run_name="__main__")
                    except SystemExit as se:
                        exit_code = se.code if isinstance(se.code, int) else 0
                    except Exception as exc:
                        print(f"[atlas trace] [!] Script raised: {type(exc).__name__}: {exc}")
                        exit_code = 1

        elif Path(exe).is_file() or exe.endswith(".py"):
            script_path = Path(exe).resolve()
            sys.argv = cmd
            parent_dir = str(script_path.parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            print(f"[atlas trace] Executing script: {script_path.name}")
            with tracer:
                try:
                    runpy.run_path(str(script_path), run_name="__main__")
                except SystemExit as se:
                    exit_code = se.code if isinstance(se.code, int) else 0
                except Exception as exc:
                    print(f"[atlas trace] [!] Script raised: {type(exc).__name__}: {exc}")
                    exit_code = 1

        else:
            # Fallback to runpy module execution
            sys.argv = cmd
            print(f"[atlas trace] Executing module: {exe}")
            with tracer:
                try:
                    runpy.run_module(exe, run_name="__main__", alter_sys=True)
                except SystemExit as se:
                    exit_code = se.code if isinstance(se.code, int) else 0
                except Exception as exc:
                    print(f"[atlas trace] [!] Execution failed: {exc}", file=sys.stderr)
                    exit_code = 1

    elif file:
        script_path = Path(file).resolve()
        if not script_path.exists():
            print(f"[error] File not found: {script_path}", file=sys.stderr)
            return 1
        sys.argv = [str(script_path)]
        parent_dir = str(script_path.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        print(f"[atlas trace] Running file: {script_path.name}")
        with tracer:
            try:
                runpy.run_path(str(script_path), run_name="__main__")
            except SystemExit as se:
                exit_code = se.code if isinstance(se.code, int) else 0
            except Exception as exc:
                print(f"[atlas trace] [!] Script raised: {type(exc).__name__}: {exc}")
                exit_code = 1

    elif module:
        print(f"[atlas trace] Running module: {module}")
        sys.argv = [module]
        with tracer:
            try:
                runpy.run_module(module, run_name="__main__", alter_sys=True)
            except SystemExit as se:
                exit_code = se.code if isinstance(se.code, int) else 0
            except Exception as exc:
                print(f"[atlas trace] [!] Module raised: {type(exc).__name__}: {exc}")
                exit_code = 1

    session = tracer.get_session_ir()
    n_parts = len(session.participants)
    n_events = len(session.interactions)

    print(f"\n[atlas trace] [+] Captured  : {n_parts} participants, {n_events} interactions ({session.duration_ms:.1f} ms)")

    # ── Save Artifacts ───────────────────────────────────────────────────
    out_dir = Path(output).resolve() if output else Path("output") / "traces"
    out_dir.mkdir(parents=True, exist_ok=True)

    base_name = f"{project_name}_{session.session_id}"

    # JSON Trace
    json_path = out_dir / f"{base_name}.json"
    json_path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
    print(f"[atlas trace] [json] Saved JSON   : {json_path}")

    # PlantUML Sequence Diagram
    if output_format in ("all", "puml"):
        puml_path = out_dir / f"{base_name}.puml"
        puml_code = PlantUMLGenerator.generate_sequence_diagram(session)
        puml_path.write_text(puml_code, encoding="utf-8")
        print(f"[atlas trace] [puml] Saved PlantUML: {puml_path}")

    # Mermaid Sequence Diagram
    if output_format in ("all", "mmd"):
        mmd_path = out_dir / f"{base_name}.mmd"
        mmd_code = MermaidGenerator.generate_sequence_diagram(session)
        mmd_path.write_text(mmd_code, encoding="utf-8")
        print(f"[atlas trace] [mmd]  Saved Mermaid : {mmd_path}")

    # Push to live server if requested
    if push:
        server_url = push.rstrip("/")
        endpoint = f"{server_url}/api/trace"
        body = json.dumps({"project": project_name, "session": session.model_dump()}).encode("utf-8")
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
                print(f"[atlas trace] [push] Pushed       : {endpoint} ({n_msg} sequence messages)")
                print(f"[atlas trace] [view] Open View    : {server_url}/?project={project_name} (Sequence tab)")
        except URLError as exc:
            print(f"[atlas trace] [WARN] Push to {endpoint} failed: {exc}", file=sys.stderr)

    if open_browser:
        target_web = f"{push or 'http://127.0.0.1:8000'}/?project={project_name}"
        webbrowser.open(target_web)

    print()
    return exit_code


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="atlas",
        description="ATLAS / UMLdoc — drift-aware UML documentation and runtime sequence tracer for Python codebases.",
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
        help="Dynamic trace: run a command (e.g. 'pytest tests/', 'python run.py') and generate a Sequence Diagram",
    )
    trace_p.add_argument("--file", "-f", default=None, help="Python file to execute and trace")
    trace_p.add_argument("--module", "-m", default=None, help="Dotted module to import and trace")
    trace_p.add_argument("--project", "-p", default=None, help="Project name (defaults to current directory name)")
    trace_p.add_argument("--scenario", "-s", default=None, help="Scenario label for sequence diagram")
    trace_p.add_argument(
        "--include", "-i",
        default=None,
        help="Package prefix to include (e.g. 'myapp'). Defaults to workspace code.",
    )
    trace_p.add_argument(
        "--exclude", "-x",
        default=None,
        help="Comma-separated package prefixes to exclude.",
    )
    trace_p.add_argument("--output", "-o", default=None, help="Output directory for trace files (default: output/traces/)")
    trace_p.add_argument(
        "--format",
        choices=["all", "json", "puml", "mmd"],
        default="all",
        help="Diagram format to emit (default: all)",
    )
    trace_p.add_argument(
        "--push",
        default=None,
        help="Push trace to live ATLAS server, e.g. http://127.0.0.1:8000",
    )
    trace_p.add_argument("--open", action="store_true", help="Open ATLAS live sequence viewer in browser")
    trace_p.add_argument("--entrypoint", "-e", default=None, help="Entrypoint label (cosmetic)")
    trace_p.add_argument(
        "cmd",
        nargs="*",
        help="Command to run under tracer (e.g. 'pytest tests/test_order.py', 'python app.py')",
    )

    # ── legacy flat invocation (backwards compat: atlas --path .) ────────────
    parser.add_argument("--path", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--output", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--name", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--format", default="all", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--open", action="store_true", help=argparse.SUPPRESS)

    args, unknown = parser.parse_known_args()

    if args.command == "trace":
        full_cmd = list(args.cmd) + unknown
        code = run_trace(
            cmd=full_cmd,
            file=args.file,
            module=args.module,
            project=args.project,
            scenario=args.scenario,
            include=args.include,
            exclude=args.exclude,
            output=args.output,
            output_format=args.format,
            push=args.push,
            entrypoint=args.entrypoint,
            open_browser=args.open,
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
