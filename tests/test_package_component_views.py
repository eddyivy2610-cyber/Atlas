"""Comprehensive tests for Package Dependency Graph and Component Architecture views."""

import xml.etree.ElementTree as ET
from pathlib import Path
import pytest

from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.generators.mermaid import MermaidGenerator
from umldoc.generators.plantuml import PlantUMLGenerator
from umldoc.generators.svg_renderer import SVGDiagramRenderer
from umldoc.ir.static_model import (
    ComponentConnectorIR,
    ComponentModelIR,
    ComponentNodeIR,
    PackageDependencyIR,
    PackageModelIR,
    PackageNodeIR,
    StaticModelIR,
)


def test_package_dependency_graph_extraction_sample():
    """Verify package graph extraction, Martin's coupling metrics, and instability on sample codebase."""
    sample_dir = Path(__file__).parent / "sample_codebase"
    extractor = ASTStaticExtractor(project_name="SampleTest", root_path=str(sample_dir))
    static_model = extractor.extract_directory(target_dir=str(sample_dir))

    assert static_model.packages is not None
    pkg_model = static_model.packages

    # Ensure package nodes exist
    assert len(pkg_model.packages) >= 1
    pkg_names = {p.name for p in pkg_model.packages}
    assert any("sample_codebase" in name or "models" in name or "service" in name or "core" in name for name in pkg_names)

    # Check metric ranges
    for pkg in pkg_model.packages:
        assert pkg.afferent_coupling >= 0
        assert pkg.efferent_coupling >= 0
        assert 0.0 <= pkg.instability <= 1.0


def test_circular_package_dependency_detection(tmp_path: Path):
    """Verify cycle detection algorithm marks circular dependencies between packages."""
    pkg_a = tmp_path / "pkg_alpha"
    pkg_b = tmp_path / "pkg_beta"
    pkg_a.mkdir()
    pkg_b.mkdir()

    # Circular import between pkg_alpha and pkg_beta
    (pkg_a / "__init__.py").write_text("import pkg_beta.worker\n")
    (pkg_a / "core.py").write_text("from pkg_beta.worker import Task\nclass AlphaTask: pass\n")

    (pkg_b / "__init__.py").write_text("import pkg_alpha.core\n")
    (pkg_b / "worker.py").write_text("from pkg_alpha.core import AlphaTask\nclass Task: pass\n")

    extractor = ASTStaticExtractor(project_name="CycleTest", root_path=str(tmp_path))
    model = extractor.extract_directory(target_dir=str(tmp_path))

    assert model.packages is not None
    assert model.packages.has_cycles is True
    assert len(model.packages.cycles) >= 1

    # Check that at least one dependency is flagged is_cyclic
    cyclic_deps = [d for d in model.packages.dependencies if d.is_cyclic]
    assert len(cyclic_deps) >= 1


def test_component_architecture_extraction():
    """Verify component architecture extraction, tiers, and connectors on UMLdoc engine."""
    repo_root = Path(__file__).parents[1] / "src" / "umldoc"
    extractor = ASTStaticExtractor(project_name="umldoc", root_path=str(repo_root))
    model = extractor.extract_directory(target_dir=str(repo_root))

    assert model.components is not None
    comp_model = model.components

    assert len(comp_model.components) >= 5
    comp_names = {c.name for c in comp_model.components}
    assert "ASTStaticExtractor" in comp_names or "BundlePackager" in comp_names

    # Verify architectural tiers
    tiers_present = {c.tier for c in comp_model.components}
    assert "Domain Service" in tiers_present or "Infrastructure" in tiers_present or "Presentation / API" in tiers_present or "Infrastructure / Data" in tiers_present or "Application Services" in tiers_present

    # Verify connectors
    assert len(comp_model.connectors) >= 1
    connector_types = {c.connector_type for c in comp_model.connectors}
    assert "uses" in connector_types or "realizes" in connector_types


def test_plantuml_package_and_component_generation():
    """Verify PlantUML code syntax for package and component diagrams."""
    pkg_model = PackageModelIR(
        packages=[
            PackageNodeIR(
                id="pkg_core",
                name="core",
                path="core/",
                modules=["core.engine"],
                classes=["Engine"],
                afferent_coupling=1,
                efferent_coupling=0,
                instability=0.0,
            ),
            PackageNodeIR(
                id="pkg_api",
                name="api",
                path="api/",
                modules=["api.router"],
                classes=["Router"],
                afferent_coupling=0,
                efferent_coupling=1,
                instability=1.0,
            ),
        ],
        dependencies=[
            PackageDependencyIR(
                id="dep_1",
                source_package="api",
                target_package="core",
                import_count=3,
                imported_symbols=["core.engine"],
            )
        ],
    )

    comp_model = ComponentModelIR(
        components=[
            ComponentNodeIR(
                id="comp_Router",
                name="Router",
                stereotype="«controller»",
                tier="Presentation / API",
                provided_interfaces=["handle_req"],
            ),
            ComponentNodeIR(
                id="comp_Engine",
                name="Engine",
                stereotype="«service»",
                tier="Domain Service",
                provided_interfaces=["compute"],
            ),
        ],
        connectors=[
            ComponentConnectorIR(
                id="conn_1",
                source_id="comp_Router",
                target_id="comp_Engine",
                connector_type="uses",
                label="delegates",
            )
        ],
    )

    model = StaticModelIR(
        project_name="TestApp",
        classes=[],
        relations=[],
        packages=pkg_model,
        components=comp_model,
    )

    # 1. PlantUML Package Diagram
    puml_pkg = PlantUMLGenerator.generate_package_diagram(model)
    assert "@startuml" in puml_pkg
    assert "packageStyle folder" in puml_pkg
    assert 'package "core' in puml_pkg
    assert 'package "api' in puml_pkg
    assert "pkg_api ..> pkg_core : imports (3)" in puml_pkg
    assert "@enduml" in puml_pkg

    # 2. PlantUML Component Diagram
    puml_comp = PlantUMLGenerator.generate_component_diagram(model)
    assert "@startuml" in puml_comp
    assert "as comp_Router <<controller>>" in puml_comp
    assert "as comp_Engine <<service>>" in puml_comp
    assert ("comp_Router --> comp_Engine : delegates" in puml_comp or "comp_Router ..> comp_Engine : delegates" in puml_comp)
    assert "@enduml" in puml_comp


def test_mermaid_package_and_component_generation():
    """Verify Mermaid markup for package and component diagrams."""
    pkg_model = PackageModelIR(
        packages=[
            PackageNodeIR(
                id="pkg_alpha",
                name="alpha",
                path="alpha/",
                modules=["alpha.mod"],
                classes=["ClassA"],
                afferent_coupling=0,
                efferent_coupling=1,
                instability=1.0,
            ),
            PackageNodeIR(
                id="pkg_beta",
                name="beta",
                path="beta/",
                modules=["beta.mod"],
                classes=["ClassB"],
                afferent_coupling=1,
                efferent_coupling=0,
                instability=0.0,
            ),
        ],
        dependencies=[
            PackageDependencyIR(
                id="dep_1",
                source_package="alpha",
                target_package="beta",
                import_count=1,
                is_cyclic=False,
            )
        ],
    )

    comp_model = ComponentModelIR(
        components=[
            ComponentNodeIR(
                id="comp_A",
                name="AlphaService",
                stereotype="«service»",
                tier="Domain Service",
            )
        ],
        connectors=[],
    )

    model = StaticModelIR(
        project_name="TestApp",
        classes=[],
        relations=[],
        packages=pkg_model,
        components=comp_model,
    )

    # Mermaid Package
    mmd_pkg = MermaidGenerator.generate_package_diagram(model)
    assert "flowchart TB" in mmd_pkg
    assert "subgraph pkg_alpha" in mmd_pkg
    assert "pkg_alpha -.->|imports (1)| pkg_beta" in mmd_pkg

    # Mermaid Component
    mmd_comp = MermaidGenerator.generate_component_diagram(model)
    assert "flowchart TB" in mmd_comp
    assert 'subgraph tier_Domain_Service ["Domain Service"]' in mmd_comp
    assert "comp_A" in mmd_comp


def test_svg_package_and_component_diagram_rendering():
    """Verify native SVG diagram rendering produces valid XML vector graphics."""
    pkg_model = PackageModelIR(
        packages=[
            PackageNodeIR(
                id="pkg_ui",
                name="ui",
                path="ui/",
                modules=["ui.view"],
                classes=["View"],
                afferent_coupling=0,
                efferent_coupling=1,
                instability=1.0,
            ),
            PackageNodeIR(
                id="pkg_db",
                name="db",
                path="db/",
                modules=["db.repo"],
                classes=["Repo"],
                afferent_coupling=1,
                efferent_coupling=0,
                instability=0.0,
            ),
        ],
        dependencies=[
            PackageDependencyIR(
                id="dep_1",
                source_package="ui",
                target_package="db",
                import_count=4,
                is_cyclic=False,
            )
        ],
    )

    comp_model = ComponentModelIR(
        components=[
            ComponentNodeIR(
                id="comp_View",
                name="View",
                stereotype="«controller»",
                tier="Presentation / API",
                provided_interfaces=["render"],
            ),
            ComponentNodeIR(
                id="comp_Repo",
                name="Repo",
                stereotype="«database»",
                tier="Data & Persistence",
                provided_interfaces=["find"],
            ),
        ],
        connectors=[
            ComponentConnectorIR(
                id="c1",
                source_id="comp_View",
                target_id="comp_Repo",
                label="queries",
            )
        ],
    )

    model = StaticModelIR(
        project_name="VisualTest",
        classes=[],
        relations=[],
        packages=pkg_model,
        components=comp_model,
    )

    # 1. Package SVG
    svg_pkg = SVGDiagramRenderer.render_package_diagram(model)
    root_pkg = ET.fromstring(svg_pkg)
    assert root_pkg.tag.endswith("svg")
    assert "PACKAGE" in svg_pkg
    assert "Ca: 0" in svg_pkg
    assert "imports (4)" in svg_pkg

    # 2. Component SVG
    svg_comp = SVGDiagramRenderer.render_component_diagram(model)
    root_comp = ET.fromstring(svg_comp)
    assert root_comp.tag.endswith("svg")
    assert "PRESENTATION / API" in svg_comp
    assert "DATA &amp; PERSISTENCE" in svg_comp or "DATA & PERSISTENCE" in svg_comp
    assert "«controller»" in svg_comp
    assert "«database»" in svg_comp
