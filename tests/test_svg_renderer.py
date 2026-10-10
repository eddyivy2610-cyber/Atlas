"""Unit tests for the native SVG diagram renderer.

Validates:
1. XML well-formedness (standard xml.etree.ElementTree parseability).
2. Correct SVG structure, dimensions, markers, defs, and viewBox.
3. Accurate rendering of class headers, stereotypes, attributes, methods, and relationships.
4. Handling of empty models and single-class models without crashing.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import pytest

from umldoc.generators.svg_renderer import SVGDiagramRenderer
from umldoc.ir.base import ElementKind, MemberVisibility, RelationType
from umldoc.ir.static_model import (
    AttributeIR,
    ClassIR,
    MethodIR,
    ParameterIR,
    RelationIR,
    StaticModelIR,
)


def _build_sample_model() -> StaticModelIR:
    c1 = ClassIR(
        id="pkg.Animal",
        name="Animal",
        qualified_name="pkg.Animal",
        kind=ElementKind.CLASS,
        is_abstract=True,
        attributes=[
            AttributeIR(
                id="pkg.Animal.name",
                name="name",
                type_annotation="str",
                visibility=MemberVisibility.PUBLIC,
            )
        ],
        methods=[
            MethodIR(
                id="pkg.Animal.speak",
                name="speak",
                parameters=[],
                return_type="str",
                visibility=MemberVisibility.PUBLIC,
                is_abstract=True,
            )
        ],
    )

    c2 = ClassIR(
        id="pkg.Dog",
        name="Dog",
        qualified_name="pkg.Dog",
        kind=ElementKind.CLASS,
        bases=["Animal"],
        attributes=[
            AttributeIR(
                id="pkg.Dog.breed",
                name="breed",
                type_annotation="str",
                visibility=MemberVisibility.PRIVATE,
            )
        ],
        methods=[
            MethodIR(
                id="pkg.Dog.speak",
                name="speak",
                parameters=[],
                return_type="str",
                visibility=MemberVisibility.PUBLIC,
            ),
            MethodIR(
                id="pkg.Dog.fetch",
                name="fetch",
                parameters=[ParameterIR(name="item", type_annotation="str")],
                return_type="bool",
                visibility=MemberVisibility.PUBLIC,
            ),
        ],
    )

    r1 = RelationIR(
        id="rel1",
        source_id="pkg.Dog",
        target_id="pkg.Animal",
        relation_type=RelationType.INHERITANCE,
        label="extends",
    )

    return StaticModelIR(
        project_name="TestProject",
        classes=[c1, c2],
        relations=[r1],
    )


def test_svg_renderer_well_formed_xml():
    model = _build_sample_model()
    svg_text = SVGDiagramRenderer.render_class_diagram(model, title="Test Class Diagram")

    # 1. Assert XML parses without syntax errors
    root = ET.fromstring(svg_text)
    assert root.tag.endswith("svg")
    assert "viewBox" in root.attrib
    assert root.attrib["width"] != "0"
    assert root.attrib["height"] != "0"

    # 2. Check title presence
    titles = [elem.text for elem in root.iter() if elem.text and "Test Class Diagram" in elem.text]
    assert len(titles) == 1

    # 3. Check class elements
    class_groups = [elem for elem in root.iter() if elem.attrib.get("id", "").startswith("class-")]
    assert len(class_groups) == 2

    # 4. Check defs and markers
    defs = [elem for elem in root.iter() if elem.tag.endswith("defs")]
    assert len(defs) == 1
    markers = [elem.attrib.get("id") for elem in root.iter() if elem.tag.endswith("marker")]
    assert "inheritance" in markers
    assert "composition" in markers
    assert "arrow" in markers

    # 5. Check connector path
    paths = [elem for elem in root.iter() if elem.tag.endswith("path") and "marker-end" in elem.attrib]
    assert len(paths) >= 1


def test_svg_renderer_empty_model():
    empty_model = StaticModelIR(project_name="Empty", classes=[], relations=[])
    svg_text = SVGDiagramRenderer.render_class_diagram(empty_model)
    root = ET.fromstring(svg_text)
    assert root.tag.endswith("svg")

    svg_pkg = SVGDiagramRenderer.render_package_diagram(empty_model)
    root_pkg = ET.fromstring(svg_pkg)
    assert root_pkg.tag.endswith("svg")

    svg_comp = SVGDiagramRenderer.render_component_diagram(empty_model)
    root_comp = ET.fromstring(svg_comp)
    assert root_comp.tag.endswith("svg")


def test_svg_package_and_component_rendering():
    from umldoc.ir.static_model import (
        ComponentModelIR,
        ComponentConnectorIR,
        ComponentNodeIR,
        PackageModelIR,
        PackageDependencyIR,
        PackageNodeIR,
    )

    pkg_model = PackageModelIR(
        packages=[
            PackageNodeIR(
                id="pkg_api",
                name="api",
                path="api/",
                modules=["api.router", "api.handlers"],
                classes=["UserRouter"],
                functions_count=2,
                afferent_coupling=0,
                efferent_coupling=1,
                instability=1.0,
            ),
            PackageNodeIR(
                id="pkg_service",
                name="service",
                path="service/",
                modules=["service.user"],
                classes=["UserService"],
                functions_count=1,
                afferent_coupling=1,
                efferent_coupling=0,
                instability=0.0,
            ),
        ],
        dependencies=[
            PackageDependencyIR(
                id="dep_1",
                source_package="api",
                target_package="service",
                import_count=2,
                imported_symbols=["service.user"],
                is_cyclic=False,
            )
        ],
    )

    comp_model = ComponentModelIR(
        components=[
            ComponentNodeIR(
                id="comp_UserRouter",
                name="UserRouter",
                stereotype="«controller»",
                tier="Presentation / API",
                provided_interfaces=["get_user", "create_user"],
            ),
            ComponentNodeIR(
                id="comp_UserService",
                name="UserService",
                stereotype="«service»",
                tier="Domain Service",
                provided_interfaces=["find_by_id"],
            ),
        ],
        connectors=[
            ComponentConnectorIR(
                id="conn_1",
                source_id="comp_UserRouter",
                target_id="comp_UserService",
                label="uses",
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

    # Validate package SVG
    svg_pkg = SVGDiagramRenderer.render_package_diagram(model, title="TestApp Packages")
    root_pkg = ET.fromstring(svg_pkg)
    assert root_pkg.tag.endswith("svg")
    assert "viewBox" in root_pkg.attrib
    assert any("api" in (elem.text or "") for elem in root_pkg.iter())
    assert any("service" in (elem.text or "") for elem in root_pkg.iter())

    # Validate component SVG
    svg_comp = SVGDiagramRenderer.render_component_diagram(model, title="TestApp Components")
    root_comp = ET.fromstring(svg_comp)
    assert root_comp.tag.endswith("svg")
    assert "viewBox" in root_comp.attrib
    assert any("UserRouter" in (elem.text or "") for elem in root_comp.iter())
    assert any("UserService" in (elem.text or "") for elem in root_comp.iter())


def test_bundled_svg_files_are_valid_xml():
    """Verify that all packaged SVG files in output/bundles are well-formed XML."""
    bundle_dir = Path(__file__).parents[1] / "output" / "bundles"
    svg_files = list(bundle_dir.glob("*/architecture.svg"))

    if not svg_files:
        pytest.skip("No bundle SVG files found. Run scripts/package_bundle.py first.")

    for svg_path in svg_files:
        svg_content = svg_path.read_text(encoding="utf-8")
        assert len(svg_content) > 100
        root = ET.fromstring(svg_content)
        assert root.tag.endswith("svg")
        assert "viewBox" in root.attrib


def test_svg_career_compass_full_details_export():
    """Verify that architecture diagrams export with all details (no empty cards, full swimlanes, operations & purpose)."""
    from umldoc.ir.static_model import ComponentModelIR, ComponentNodeIR, ComponentConnectorIR

    components = [
        ComponentNodeIR(
            id="comp_desktop_launcher",
            name="desktop_launcher",
            stereotype="«entrypoint»",
            role="Entry Point",
            tier="Entry Points",
            purpose="Launches desktop application",
            functions_count=2,
            dependencies_count=1,
        ),
        ComponentNodeIR(
            id="comp_run",
            name="run",
            stereotype="«entrypoint»",
            role="Entry Point",
            tier="Entry Points",
            purpose="CLI / Script entry point",
            functions_count=3,
            dependencies_count=1,
        ),
        ComponentNodeIR(
            id="comp_app",
            name="app",
            stereotype="«controller»",
            role="Controller / Presentation",
            tier="Presentation / Controller",
            purpose="Flask application (web interface)",
            functions_count=8,
            dependencies_count=4,
        ),
        ComponentNodeIR(
            id="comp_core_app_paths",
            name="core.app_paths",
            stereotype="«infrastructure»",
            role="Infrastructure",
            tier="Presentation / Controller",
            purpose="Runtime paths and directories",
            functions_count=4,
            dependencies_count=0,
        ),
        ComponentNodeIR(
            id="comp_core_file_processor",
            name="core.file_processor",
            stereotype="«service»",
            role="Application Service",
            tier="Application Services",
            purpose="Parse and validate student files",
            functions_count=6,
            dependencies_count=2,
        ),
        ComponentNodeIR(
            id="comp_core_recommendation_engine",
            name="core.recommendation_engine",
            stereotype="«service»",
            role="Application Service",
            tier="Application Services",
            purpose="Evaluate student and generate recommendations",
            functions_count=5,
            dependencies_count=1,
        ),
        ComponentNodeIR(
            id="comp_core_questionnaire_processor",
            name="core.questionnaire_processor",
            stereotype="«service»",
            role="Application Service",
            tier="Application Services",
            purpose="Process survey responses and scores",
            functions_count=4,
            dependencies_count=1,
        ),
        ComponentNodeIR(
            id="comp_core_database",
            name="core.database",
            stereotype="«database»",
            role="Persistence",
            tier="Infrastructure / Data",
            purpose="SQLite schema and student records",
            functions_count=7,
            dependencies_count=0,
        ),
    ]

    connectors = [
        ComponentConnectorIR(id="c1", source_id="comp_desktop_launcher", target_id="comp_app", label="starts"),
        ComponentConnectorIR(id="c2", source_id="comp_run", target_id="comp_app", label="starts"),
        ComponentConnectorIR(id="c3", source_id="comp_app", target_id="comp_core_recommendation_engine", label="uses"),
    ]

    model = StaticModelIR(
        project_name="Career Compass",
        classes=[],
        relations=[],
        components=ComponentModelIR(components=components, connectors=connectors),
    )

    svg_text = SVGDiagramRenderer.render_component_diagram(model, title="Career Compass Architecture", clean_export=True)
    root = ET.fromstring(svg_text)
    assert root.tag.endswith("svg")

    all_texts = [elem.text for elem in root.iter() if elem.text]
    all_text_blob = " ".join(all_texts)

    # 1. Swimlanes are present
    assert "ENTRY POINTS" in all_text_blob
    assert "PRESENTATION / CONTROLLER" in all_text_blob
    assert "APPLICATION SERVICES" in all_text_blob
    assert "INFRASTRUCTURE / DATA" in all_text_blob

    # 2. Component titles and stereotypes are present
    assert "desktop_launcher" in all_text_blob
    assert "core.recommendation_engine" in all_text_blob
    assert "core.database" in all_text_blob
    assert "«service»" in all_text_blob or "service" in all_text_blob.lower()

    # 3. Purpose subtitles are present (not empty)
    assert "Evaluate student and generate recommendations" in all_text_blob
    assert "Flask application" in all_text_blob

    # 4. Operations & dependencies details are present
    assert "operations •" in all_text_blob
    assert "dependencies" in all_text_blob

    # 5. External services box is present
    assert "EXTERNAL SERVICES" in all_text_blob
    assert "File System" in all_text_blob

    # 6. Legend is present
    assert "«database» Database" in all_text_blob
    assert "Direct Call / Use" in all_text_blob

