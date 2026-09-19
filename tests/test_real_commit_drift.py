"""Integration test verifying DriftAnalyzer across real releases in git repository."""

import subprocess
from pathlib import Path
from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.verifier.drift import DriftAnalyzer
from umldoc.ir.verification import DriftChangeType


def test_real_git_drift_tinydb_releases():
    """Verify DriftAnalyzer on TinyDB v3.15.2 vs v4.0.0."""
    repo_dir = Path(__file__).parent.parent / "data" / "repos" / "tinydb"
    if not repo_dir.exists():
        return

    # Extract v3.15.2
    subprocess.run(["git", "-C", str(repo_dir), "checkout", "v3.15.2"], check=True, capture_output=True)
    pkg_dir = repo_dir / "tinydb" if (repo_dir / "tinydb").exists() else repo_dir
    extractor_v3 = ASTStaticExtractor(project_name="tinydb", root_path=str(pkg_dir))
    model_v3 = extractor_v3.extract_directory(target_dir=str(pkg_dir))

    # Extract v4.0.0
    subprocess.run(["git", "-C", str(repo_dir), "checkout", "v4.0.0"], check=True, capture_output=True)
    extractor_v4 = ASTStaticExtractor(project_name="tinydb", root_path=str(pkg_dir))
    model_v4 = extractor_v4.extract_directory(target_dir=str(pkg_dir))

    # Restore master
    subprocess.run(["git", "-C", str(repo_dir), "checkout", "master"], check=True, capture_output=True)

    report = DriftAnalyzer.analyze_drift(
        base_model=model_v3,
        target_model=model_v4,
        base_commit="v3.15.2",
        target_commit="v4.0.0",
    )

    assert report.total_drift_count > 10
    assert report.breaking_changes_count >= 1

    drifted_names = {d.element_name: d for d in report.drifted_elements}
    assert "TinyDB.purge_tables" in drifted_names
    assert drifted_names["TinyDB.purge_tables"].change_type == DriftChangeType.REMOVED
    assert drifted_names["TinyDB.purge_tables"].is_breaking is True

    assert "TinyDB.drop_tables" in drifted_names
    assert drifted_names["TinyDB.drop_tables"].change_type == DriftChangeType.ADDED
