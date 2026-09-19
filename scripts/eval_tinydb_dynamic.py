"""Evaluation script running dynamic execution trace on TinyDB insert and query workflows."""

import json
from pathlib import Path
from tinydb import TinyDB, Query
from tinydb.storages import MemoryStorage

from umldoc.extractors.dynamic_trace import ExecutionTracer
from umldoc.generators.plantuml import PlantUMLGenerator
from umldoc.generators.mermaid import MermaidGenerator
from umldoc.ir.schema import DocumentIR
from umldoc.ir.dynamic_model import DynamicModelIR


def run_tinydb_workflow():
    db = TinyDB(storage=MemoryStorage)
    table = db.table("users")
    table.insert({"name": "Alice", "role": "admin"})
    table.insert({"name": "Bob", "role": "developer"})

    User = Query()
    results = table.search(User.role == "admin")
    return results


def main():
    print("Tracing TinyDB in-memory database operations...")
    tracer = ExecutionTracer(
        scenario_name="TinyDB_InsertAndQuery",
        entrypoint_name="run_tinydb_workflow",
        include_prefixes={"tinydb"},
    )

    with tracer:
        res = run_tinydb_workflow()

    session = tracer.get_session_ir()
    print(f"Captured {len(session.participants)} lifelines and {len(session.interactions)} interaction events.")
    print(f"Results returned: {res}")

    out_dir = Path("output/tinydb")
    out_dir.mkdir(parents=True, exist_ok=True)

    dyn_model = DynamicModelIR(
        project_name="tinydb",
        sessions=[session],
    )
    doc = DocumentIR(
        project_name="tinydb",
        dynamic_model=dyn_model,
    )

    # 1. Save dynamic IR JSON
    with open(out_dir / "tinydb_dynamic_ir.json", "w", encoding="utf-8") as f:
        f.write(doc.to_json_str(indent=2))

    # 2. Save Sequence PlantUML
    puml_seq = PlantUMLGenerator.generate_sequence_diagram(session)
    with open(out_dir / "tinydb_sequence.puml", "w", encoding="utf-8") as f:
        f.write(puml_seq)
    print(f"Saved PlantUML sequence to: {out_dir / 'tinydb_sequence.puml'}")

    # 3. Save Sequence Mermaid
    mmd_seq = MermaidGenerator.generate_sequence_diagram(session)
    with open(out_dir / "tinydb_sequence.mmd", "w", encoding="utf-8") as f:
        f.write(mmd_seq)
    print(f"Saved Mermaid sequence to: {out_dir / 'tinydb_sequence.mmd'}")


if __name__ == "__main__":
    main()
