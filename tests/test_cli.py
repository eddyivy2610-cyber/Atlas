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
    assert (out_dir / "packages.svg").exists()
    assert (out_dir / "packages.puml").exists()
    assert (out_dir / "packages.mmd").exists()
    assert (out_dir / "components.svg").exists()
    assert (out_dir / "components.puml").exists()
    assert (out_dir / "components.mmd").exists()
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


def test_cli_trace_script(tmp_path: Path):
    from umldoc.cli import run_trace

    test_script = tmp_path / "simple_service.py"
    test_script.write_text(
        "class Calculator:\n"
        "    def add(self, a, b):\n"
        "        return a + b\n"
        "\n"
        "calc = Calculator()\n"
        "res = calc.add(10, 20)\n"
    )

    out_dir = tmp_path / "traces"
    code = run_trace(
        file=str(test_script),
        output=str(out_dir),
        project_name="SimpleCalc",
        output_format="all",
    )
    assert code == 0

    json_files = list(out_dir.glob("*.json"))
    puml_files = list(out_dir.glob("*.puml"))
    mmd_files = list(out_dir.glob("*.mmd"))

    assert len(json_files) == 1
    assert len(puml_files) == 1
    assert len(mmd_files) == 1

    trace_json = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert "simple_service" in trace_json["scenario_name"]
    participant_classes = [p["class_name"] for p in trace_json["participants"]]
    assert "Calculator" in participant_classes


def test_cli_trace_cmd_tokens(tmp_path: Path):
    from umldoc.cli import run_trace

    test_script = tmp_path / "worker.py"
    test_script.write_text(
        "class Worker:\n"
        "    def perform(self):\n"
        "        return 'done'\n"
        "\n"
        "w = Worker()\n"
        "w.perform()\n"
    )

    out_dir = tmp_path / "cmd_traces"
    code = run_trace(
        cmd=["python", str(test_script)],
        output=str(out_dir),
        project_name="WorkerProject",
        output_format="all",
    )
    assert code == 0

    json_files = list(out_dir.glob("*.json"))
    assert len(json_files) == 1
    trace_json = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert any(p["class_name"] == "Worker" for p in trace_json["participants"])
