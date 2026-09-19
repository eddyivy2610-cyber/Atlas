"""Tests for the UMLdoc standalone CLI."""

import json
from pathlib import Path
import pytest
from umldoc.cli import run_cli
from umldoc.ir.schema import DocumentIR


def test_cli_execution_on_sample_codebase(tmp_path: Path):
    sample_dir = Path(__file__).parent / "sample_codebase"
    out_dir = tmp_path / "cli_bundle"

    code = run_cli(
        path=str(sample_dir),
        output=str(out_dir),
        name="SampleTest",
        output_format="all",
        as_json=False,
    )
    assert code == 0
    assert (out_dir / "architecture.svg").exists()
    assert (out_dir / "architecture.puml").exists()
    assert (out_dir / "architecture.mmd").exists()
    assert (out_dir / "index.html").exists()


def test_cli_json_output(capsys, monkeypatch):
    sample_dir = Path(__file__).parent / "sample_codebase"

    code = run_cli(
        path=str(sample_dir),
        as_json=True,
    )
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    doc_ir = DocumentIR.model_validate(data)
    assert doc_ir.project_name == "sample_codebase"
    assert doc_ir.static_model is not None
    assert len(doc_ir.static_model.classes) >= 5


def test_cli_invalid_path():
    code = run_cli(path="non_existent_folder_xyz_123")
    assert code == 1
