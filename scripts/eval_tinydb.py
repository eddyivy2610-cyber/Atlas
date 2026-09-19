"""Evaluation script extracting TinyDB architecture into Canonical IR and diagrams."""

import json
from pathlib import Path
import tinydb

from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.generators.plantuml import PlantUMLGenerator
from umldoc.generators.mermaid import MermaidGenerator
from umldoc.ir.schema import DocumentIR


def main():
    tinydb_dir = Path(tinydb.__file__).parent
    print(f"Extracting static architecture for TinyDB at: {tinydb_dir}")

    extractor = ASTStaticExtractor(project_name="tinydb", root_path=str(tinydb_dir))
    static_model = extractor.extract_directory(target_dir=str(tinydb_dir))

    print(f"Extracted {len(static_model.modules)} modules, {len(static_model.classes)} classes, {len(static_model.relations)} relations.")

    doc = DocumentIR(
        project_name="tinydb",
        static_model=static_model,
        metadata={"version": getattr(tinydb, "__version__", "unknown")},
    )

    out_dir = Path("output/tinydb")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save DocumentIR JSON
    ir_file = out_dir / "tinydb_ir.json"
    with open(ir_file, "w", encoding="utf-8") as f:
        f.write(doc.to_json_str(indent=2))
    print(f"Saved DocumentIR to: {ir_file}")

    # 2. Save PlantUML
    puml_file = out_dir / "tinydb_classes.puml"
    with open(puml_file, "w", encoding="utf-8") as f:
        f.write(PlantUMLGenerator.generate_class_diagram(static_model, title="TinyDB Architecture"))
    print(f"Saved PlantUML to: {puml_file}")

    # 3. Save Mermaid
    mmd_file = out_dir / "tinydb_classes.mmd"
    with open(mmd_file, "w", encoding="utf-8") as f:
        f.write(MermaidGenerator.generate_class_diagram(static_model, title="TinyDB Architecture"))
    print(f"Saved Mermaid to: {mmd_file}")

    # Display summary of extracted classes
    for cls in static_model.classes:
        methods_count = len(cls.methods)
        attrs_count = len(cls.attributes)
        bases = ", ".join(cls.bases) if cls.bases else "object"
        print(f" - {cls.name} ({cls.kind.value}) [extends: {bases}] -> {methods_count} methods, {attrs_count} attrs")


if __name__ == "__main__":
    main()
