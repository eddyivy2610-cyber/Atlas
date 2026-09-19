"""CLI tool to package a project run into a portable, zero-dependency distribution bundle.

Usage
-----
    python scripts/package_bundle.py --project tinydb
    python scripts/package_bundle.py --project click
    python scripts/package_bundle.py --all

Outputs
-------
    output/bundles/<project>/index.html
    output/bundles/<project>/architecture.puml
    output/bundles/<project>/architecture.mmd
    output/bundles/<project>/document_ir.json
    output/bundles/<project>/verification_metrics.json
    output/bundles/<project>.zip
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.ir.schema import DocumentIR
from umldoc.packaging.bundler import BundlePackager
from umldoc.parser.puml_parser import PlantUMLParser
from umldoc.verifier.comparator import DiagramVerifier
from umldoc.verifier.drift import DriftAnalyzer


REPOS = {
    "tinydb": REPO_ROOT / "data" / "repos" / "tinydb" / "tinydb",
    "click": REPO_ROOT / ".venv" / "Lib" / "site-packages" / "click",
}


def package_project(project_name: str, custom_path: Optional[Path] = None) -> None:
    if custom_path:
        repo_path = Path(custom_path).resolve()
    else:
        repo_path = REPOS.get(project_name)
    if not repo_path or not repo_path.exists():
        print(f"[error] Unknown or missing project path: {repo_path or project_name}")
        return

    print(f"\n========================================================")
    print(f"  PACKAGING PORTABLE BUNDLE: {project_name.upper()}")
    print(f"========================================================")

    # 1. Extract Ground Truth AST
    print(f"[1/4] Extracting ground truth AST from {repo_path} ...")
    extractor = ASTStaticExtractor(project_name=project_name, root_path=str(repo_path))
    static_model = extractor.extract_directory(target_dir=str(repo_path))
    print(f"      Found {len(static_model.classes)} classes, {len(static_model.relations)} relations.")

    # 2. Load Verification Summary (if LLM candidate exists)
    verif_summary = None
    metrics_data = None
    raw_puml_file = REPO_ROOT / "output" / f"{project_name}_llm_raw.puml"
    metrics_file = REPO_ROOT / "output" / f"{project_name}_llm_eval_metrics.json"

    if raw_puml_file.exists():
        print(f"[2/4] Verifying raw LLM PlantUML candidate ({raw_puml_file.name}) ...")
        candidate_model = PlantUMLParser.parse_class_diagram(raw_puml_file.read_text(encoding="utf-8"), project_name=f"{project_name}-LLM")
        verifier = DiagramVerifier(ground_truth=static_model)
        verif_summary = verifier.verify_candidate_model(candidate_model)
        print(f"      Verified: {verif_summary.verified_count} | Hallucinations: {verif_summary.hallucinated_count} | Drifted: {verif_summary.drifted_count}")

    if metrics_file.exists():
        try:
            metrics_data = json.loads(metrics_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 3. Load Drift Report (if tinydb git tags available)
    drift_report = None
    if project_name == "tinydb":
        v3_path = REPO_ROOT / "data" / "repos" / "tinydb_v3"
        v4_path = REPO_ROOT / "data" / "repos" / "tinydb_v4"
        if v3_path.exists() and v4_path.exists():
            print(f"[3/4] Computing Git release drift (v3.15.2 -> v4.0.0) ...")
            m_v3 = ASTStaticExtractor(project_name="TinyDB", root_path=str(v3_path)).extract_directory(str(v3_path))
            m_v4 = ASTStaticExtractor(project_name="TinyDB", root_path=str(v4_path)).extract_directory(str(v4_path))
            drift_report = DriftAnalyzer.analyze_evolution(m_v3, m_v4, base_commit="v3.15.2", target_commit="v4.0.0")

    # 4. Construct Canonical DocumentIR and Package Bundle
    print(f"[4/4] Generating zero-dependency portable bundle ...")
    doc_ir = DocumentIR(
        project_name=project_name,
        static_model=static_model,
        verification=verif_summary,
        drift_report=drift_report,
    )

    bundle_dir = REPO_ROOT / "output" / "bundles" / project_name
    index_path = BundlePackager.package_document(
        document_ir=doc_ir,
        output_dir=bundle_dir,
        include_zip=True,
        extra_metrics=metrics_data,
    )

    zip_path = REPO_ROOT / "output" / "bundles" / f"{project_name}.zip"
    zip_size_kb = zip_path.stat().st_size / 1024 if zip_path.exists() else 0

    print(f"\n  [SUCCESS] Portable Bundle Created:")
    print(f"    - Dossier HTML:  {index_path}")
    print(f"    - Zip Archive:   {zip_path} ({zip_size_kb:.1f} KB)")
    print(f"    - Included files: {', '.join(f.name for f in bundle_dir.iterdir())}")
    print(f"========================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Package UMLdoc run into a portable bundle.")
    parser.add_argument("--project", help="Pre-configured project to package (e.g. tinydb, click)")
    parser.add_argument("--path", type=str, help="Path to any Python codebase/repository directory")
    parser.add_argument("--name", type=str, help="Project name (defaults to folder name when using --path)")
    parser.add_argument("--all", action="store_true", help="Package all pre-configured projects")
    args = parser.parse_args()

    if args.path:
        target_path = Path(args.path)
        project_name = args.name or target_path.name
        package_project(project_name, custom_path=target_path)
    elif args.project:
        package_project(args.project)
    elif args.all:
        for p in ["tinydb", "click"]:
            package_project(p)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
