"""Evaluates DriftAnalyzer on two real releases of TinyDB (v3.15.2 vs v4.0.0)."""

import subprocess
from pathlib import Path
from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.verifier.drift import DriftAnalyzer
from umldoc.verifier.html_report import HTMLReportGenerator
from umldoc.ir.schema import DocumentIR


def run_git_command(repo_dir: Path, args: list[str]) -> str:
    res = subprocess.run(["git", "-C", str(repo_dir)] + args, capture_output=True, text=True, check=True)
    return res.stdout


def main():
    repo_dir = Path("data/repos/tinydb").resolve()
    if not repo_dir.exists():
        print("TinyDB repository not found.")
        return

    print("Checking out TinyDB v3.15.2...")
    run_git_command(repo_dir, ["checkout", "v3.15.2"])
    pkg_dir_v3 = repo_dir / "tinydb" if (repo_dir / "tinydb").exists() else repo_dir

    extractor_v3 = ASTStaticExtractor(project_name="tinydb", root_path=str(pkg_dir_v3))
    model_v3 = extractor_v3.extract_directory(target_dir=str(pkg_dir_v3))
    print(f"v3.15.2: Extracted {len(model_v3.classes)} classes, {len(model_v3.relations)} relations.")

    print("Checking out TinyDB v4.0.0...")
    run_git_command(repo_dir, ["checkout", "v4.0.0"])
    pkg_dir_v4 = repo_dir / "tinydb" if (repo_dir / "tinydb").exists() else repo_dir

    extractor_v4 = ASTStaticExtractor(project_name="tinydb", root_path=str(pkg_dir_v4))
    model_v4 = extractor_v4.extract_directory(target_dir=str(pkg_dir_v4))
    print(f"v4.0.0: Extracted {len(model_v4.classes)} classes, {len(model_v4.relations)} relations.")

    # Return git repo to main branch
    run_git_command(repo_dir, ["checkout", "master"])

    print("Running DriftAnalyzer across v3.15.2 -> v4.0.0...")
    drift_report = DriftAnalyzer.analyze_drift(
        base_model=model_v3,
        target_model=model_v4,
        base_commit="v3.15.2",
        target_commit="v4.0.0",
    )

    print("\n--- Drift Analysis Results ---")
    print(f"Total Drifted Elements: {drift_report.total_drift_count}")
    print(f"Breaking Changes: {drift_report.breaking_changes_count}")
    print(f"Summary: {drift_report.summary_notes}\n")

    for d in drift_report.drifted_elements:
        impact = "BREAKING" if d.is_breaking else "SAFE"
        print(f" - [{impact}] {d.element_name} ({d.change_type.value}): {d.diff_description}")

    # Generate HTML Report
    doc = DocumentIR(
        project_name="TinyDB_v3_to_v4_Evolution",
        static_model=model_v4,
        drift_report=drift_report,
    )
    out_file = Path("output/tinydb_v3_to_v4_drift_report.html")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    html = HTMLReportGenerator.generate_report(doc, title="TinyDB Release Drift: v3.15.2 -> v4.0.0")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nSaved HTML Drift Report to: {out_file}")


if __name__ == "__main__":
    main()
