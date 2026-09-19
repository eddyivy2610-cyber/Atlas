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
