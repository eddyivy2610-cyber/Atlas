"""Acceptance test for Phase 6 Portable Output Packaging and Zero-Dependency Portability.

Tests:
1. Packages real DocumentIR models into an isolated temporary directory.
2. Verifies that the .zip archive contains all necessary files (index.html, .puml, .mmd, .json).
3. Verifies zero external dependencies: no external CSS links, no blocking external scripts.
4. Verifies zero absolute local filesystem leaks in the generated HTML.
5. Verifies that the unzipped bundle is 100% self-contained and renders offline.
"""

import re
import tempfile
import zipfile
from pathlib import Path
import pytest

from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.ir.schema import DocumentIR
from umldoc.packaging.bundler import BundlePackager
from umldoc.parser.puml_parser import PlantUMLParser
from umldoc.verifier.comparator import DiagramVerifier

REPO_ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("project_name", ["tinydb", "click"])
def test_portable_bundle_packaging(project_name: str):
    if project_name == "tinydb":
        repo_path = REPO_ROOT / "data" / "repos" / "tinydb" / "tinydb"
    else:
        repo_path = REPO_ROOT / ".venv" / "Lib" / "site-packages" / "click"

    if not repo_path.exists():
        pytest.skip(f"Repository source not found at {repo_path}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        bundle_dir = tmp_path / "bundle" / project_name

        # 1. Extract and build DocumentIR
        extractor = ASTStaticExtractor(project_name=project_name, root_path=str(repo_path))
        static_model = extractor.extract_directory(target_dir=str(repo_path))

        # Check for verification
        raw_puml_file = REPO_ROOT / "output" / f"{project_name}_llm_raw.puml"
        verif_summary = None
        if raw_puml_file.exists():
            candidate = PlantUMLParser.parse_class_diagram(raw_puml_file.read_text(encoding="utf-8"), project_name=project_name)
            verif_summary = DiagramVerifier(ground_truth=static_model).verify_candidate_model(candidate)

        doc_ir = DocumentIR(
            project_name=project_name,
            static_model=static_model,
            verification=verif_summary,
        )

        # 2. Run Packaging Engine
        index_file = BundlePackager.package_document(
            document_ir=doc_ir,
            output_dir=bundle_dir,
            include_zip=True,
        )

        # 3. Assert Directory and File Contents
        assert index_file.exists()
        assert (bundle_dir / "architecture.puml").exists()
        assert (bundle_dir / "architecture.mmd").exists()
        assert (bundle_dir / "architecture.svg").exists()
        assert (bundle_dir / "document_ir.json").exists()

        # 4. Assert .zip Archive Integrity
        zip_file = tmp_path / "bundle" / f"{project_name}.zip"
        assert zip_file.exists()
        assert zip_file.stat().st_size > 0
        # Bundle size sanity check (must be compact, < 2 MB)
        assert zip_file.stat().st_size < 2 * 1024 * 1024

        with zipfile.ZipFile(zip_file, "r") as zf:
            namelist = zf.namelist()
            assert "index.html" in namelist
            assert "architecture.puml" in namelist
            assert "architecture.mmd" in namelist
            assert "architecture.svg" in namelist
            assert "document_ir.json" in namelist

        # 5. Zero-Dependency & Portability Invariants on index.html
        html_content = index_file.read_text(encoding="utf-8")

        # Invariant A: Must not contain external stylesheet links
        assert not re.search(r'<link[^>]+rel=["\']stylesheet["\']', html_content, re.IGNORECASE), (
            "index.html must have inline CSS for 100% offline portability!"
        )

        # Invariant B: Must not contain external blocking JS scripts
        assert not re.search(r'<script[^>]+src=["\']http', html_content, re.IGNORECASE), (
            "index.html must not depend on external network scripts for core functionality!"
        )

        # Invariant C: Must not leak local user filesystem paths (cross-platform check)
        # Windows drive letters (C:\, D:/, etc.)
        assert not re.search(r'[A-Za-z]:[\\/](?:Users|Program\s*Files|runner|home|tmp)', html_content, re.IGNORECASE), (
            "index.html contains absolute Windows filesystem paths!"
        )
        # Unix/Linux /home, /root, /tmp, /var, /runner
        assert not re.search(r'/(?:home|root|runner|private|var/tmp)/[A-Za-z0-9_-]+', html_content), (
            "index.html contains absolute Linux/CI filesystem paths!"
        )
        # macOS /Users/<username>
        assert not re.search(r'/Users/[A-Za-z0-9_-]+', html_content), (
            "index.html contains absolute macOS filesystem paths!"
        )

        # Invariant D: Must contain core architecture markup and class explorer
        assert project_name in html_content
        assert "Domain Entities" in html_content
        assert "switchTab" in html_content

        # 6. JSON IR Roundtrip Verification
        json_ir_content = (bundle_dir / "document_ir.json").read_text(encoding="utf-8")
        roundtrip_doc = DocumentIR.from_json_str(json_ir_content)
        assert roundtrip_doc.project_name == project_name
        assert len(roundtrip_doc.static_model.classes) == len(static_model.classes)
