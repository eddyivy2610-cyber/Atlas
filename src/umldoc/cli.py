"""UMLdoc CLI Entrypoint.

Usage:
    python -m umldoc.cli --path /path/to/repo --output output/bundles/my_repo
    python -m umldoc.cli --path /path/to/repo --json
    umldoc --path . --name MyProject
"""

import argparse
import json
import sys
import webbrowser
from pathlib import Path
from typing import Optional

from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.ir.schema import DocumentIR
from umldoc.packaging.bundler import BundlePackager
from umldoc.generators.mermaid import MermaidGenerator
from umldoc.generators.plantuml import PlantUMLGenerator
from umldoc.generators.svg_renderer import SVGDiagramRenderer


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

    # 1. Extract static architecture from target path
    extractor = ASTStaticExtractor(project_name=project_name, root_path=str(target_path))
    static_model = extractor.extract_directory(target_dir=str(target_path))

    doc_ir = DocumentIR(
        project_name=project_name,
        static_model=static_model,
    )

    # If --json requested, print JSON directly to stdout
    if as_json:
        print(doc_ir.model_dump_json(indent=2))
        return 0

    # Determine destination directory
    out_dir = Path(output).resolve() if output else Path("output") / "bundles" / project_name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"UMLdoc: Extracted {len(static_model.classes)} classes and {len(static_model.relations)} relations from {target_path}")

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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="umldoc",
        description="Drift-aware, verified UML documentation generator and analyzer for Python codebases.",
    )
    parser.add_argument("--path", "-p", default=".", help="Path to Python codebase/directory (default: current directory)")
    parser.add_argument("--output", "-o", default=None, help="Output destination folder for bundles")
    parser.add_argument("--name", "-n", default=None, help="Project name (defaults to directory name)")
    parser.add_argument(
        "--format",
        "-f",
        choices=["all", "html", "svg", "puml", "mmd", "json"],
        default="all",
        help="Diagram format to emit (default: all)",
    )
    parser.add_argument("--json", action="store_true", help="Output canonical DocumentIR JSON directly to stdout")
    parser.add_argument("--open", action="store_true", help="Open generated HTML dossier in default web browser")

    args = parser.parse_args()
    code = run_cli(
        path=args.path,
        output=args.output,
        name=args.name,
        output_format=args.format,
        as_json=args.json,
        open_browser=args.open,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
