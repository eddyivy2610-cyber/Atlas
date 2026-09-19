"""Packaging engine producing zero-dependency distributable bundles and zip archives."""

import json
from pathlib import Path
from typing import Optional
import zipfile

from umldoc.generators.mermaid import MermaidGenerator
from umldoc.generators.plantuml import PlantUMLGenerator
from umldoc.generators.svg_renderer import SVGDiagramRenderer
from umldoc.ir.schema import DocumentIR
from umldoc.verifier.html_report import HTMLReportGenerator


class BundlePackager:
    """Packages UMLdoc outputs into a standalone, portable directory and zip archive."""

    @classmethod
    def package_document(
        cls,
        document_ir: DocumentIR,
        output_dir: Path,
        include_zip: bool = True,
        extra_metrics: Optional[dict] = None,
    ) -> Path:
        """Package a DocumentIR into a zero-dependency bundle folder and optional .zip archive.

        Outputs
        -------
        - index.html                   (100% offline self-contained Executive Dossier)
        - architecture.puml            (PlantUML class diagram specification)
        - architecture.mmd             (Mermaid.js class diagram specification)
        - document_ir.json             (Canonical JSON Schema IR)
        - verification_metrics.json    (Statistical fidelity metrics if available)
        - sequence.puml / sequence.mmd (Dynamic sequence diagrams if traces present)
        - <output_dir>.zip             (Distributable compressed archive)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        project_name = document_ir.project_name

        # 1. Write Standalone Executive Dossier (index.html)
        html_content = HTMLReportGenerator.generate_report(document_ir, title=f"Architecture Dossier: {project_name}")
        index_file = output_dir / "index.html"
        index_file.write_text(html_content, encoding="utf-8")

        # 2. Write PlantUML, Mermaid, and Native Vector SVG Class Diagrams
        if document_ir.static_model:
            puml_text = PlantUMLGenerator.generate_class_diagram(document_ir.static_model, title=f"{project_name} Architecture")
            (output_dir / "architecture.puml").write_text(puml_text, encoding="utf-8")

            mmd_text = MermaidGenerator.generate_class_diagram(document_ir.static_model, title=f"{project_name} Architecture")
            (output_dir / "architecture.mmd").write_text(mmd_text, encoding="utf-8")

            svg_text = SVGDiagramRenderer.render_class_diagram(document_ir.static_model, title=f"{project_name} Architecture")
            (output_dir / "architecture.svg").write_text(svg_text, encoding="utf-8")

        # 3. Write Sequence Diagrams if trace sessions exist
        if document_ir.dynamic_model and document_ir.dynamic_model.sessions:
            for idx, session in enumerate(document_ir.dynamic_model.sessions, 1):
                puml_seq = PlantUMLGenerator.generate_sequence_diagram(session, title=session.scenario_name)
                (output_dir / f"sequence_{idx}.puml").write_text(puml_seq, encoding="utf-8")

                mmd_seq = MermaidGenerator.generate_sequence_diagram(session, title=session.scenario_name)
                (output_dir / f"sequence_{idx}.mmd").write_text(mmd_seq, encoding="utf-8")

        # 4. Write Canonical DocumentIR JSON
        (output_dir / "document_ir.json").write_text(document_ir.to_json_str(indent=2), encoding="utf-8")

        # 5. Write Metrics JSON if available
        if extra_metrics:
            (output_dir / "verification_metrics.json").write_text(json.dumps(extra_metrics, indent=2), encoding="utf-8")
        elif document_ir.verification:
            verif_summary = {
                "total_elements": document_ir.verification.total_elements,
                "verified_count": document_ir.verification.verified_count,
                "hallucinated_count": document_ir.verification.hallucinated_count,
                "drifted_count": document_ir.verification.drifted_count,
                "missing_count": document_ir.verification.missing_count,
                "overall_confidence": document_ir.verification.overall_confidence,
            }
            (output_dir / "verification_metrics.json").write_text(json.dumps(verif_summary, indent=2), encoding="utf-8")

        # 6. Create Standalone .zip Archive
        if include_zip:
            zip_path = output_dir.parent / f"{output_dir.name}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in output_dir.rglob("*"):
                    if file_path.is_file() and not file_path.name.endswith(".zip"):
                        arcname = file_path.relative_to(output_dir)
                        zf.write(file_path, arcname=str(arcname))

        return index_file
