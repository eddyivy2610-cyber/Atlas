"""Native SVG Class and Sequence Diagram Renderer.

Renders StaticModelIR and TraceSessionIR directly to crisp, standard, self-contained vector graphics (.svg)
with zero external binary dependencies (no Java, Graphviz, or Node required).
"""

import html
from typing import Dict, List, Optional, Tuple
from umldoc.ir.base import ElementKind, MemberVisibility, RelationType
from umldoc.ir.static_model import ClassIR, StaticModelIR


class SVGDiagramRenderer:
    """Pure-Python SVG vector graphics generator for UML Class Diagrams."""

    # Styling constants
    BOX_WIDTH = 280
    HEADER_HEIGHT = 44
    LINE_HEIGHT = 20
    PADDING = 12
    GRID_GAP_X = 60
    GRID_GAP_Y = 60
    COLS = 3

    BG_COLOR = "#1E293B"          # Slate surface
    HEADER_BG = "#0F172A"         # Darker slate header
    BORDER_COLOR = "#475569"      # Slate border
    TEXT_COLOR = "#F8FAFC"        # Bright text
    TEXT_MUTED = "#94A3B8"        # Muted text
    ACCENT_COLOR = "#38BDF8"      # Sky blue
    LINE_COLOR = "#64748B"        # Connector lines

    @classmethod
    def render_class_diagram(
        cls,
        static_model: StaticModelIR,
        title: Optional[str] = None,
    ) -> str:
        """Render a StaticModelIR into a standalone, beautiful SVG image string."""
        classes = static_model.classes
        if not classes:
            return '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100"><text x="20" y="50" fill="#94A3B8">Empty model</text></svg>'

        # 1. Compute dimensions for each class box
        box_layouts: Dict[str, Dict] = {}
        for i, c in enumerate(classes):
            num_attrs = len(c.attributes)
            num_methods = len(c.methods)
            attrs_h = (num_attrs * cls.LINE_HEIGHT) + (cls.PADDING if num_attrs > 0 else 0)
            methods_h = (num_methods * cls.LINE_HEIGHT) + (cls.PADDING if num_methods > 0 else 0)
            total_h = cls.HEADER_HEIGHT + attrs_h + methods_h + cls.PADDING

            box_layouts[c.name] = {
                "class_ir": c,
                "width": cls.BOX_WIDTH,
                "height": total_h,
                "attrs_height": attrs_h,
                "methods_height": methods_h,
            }

        # 2. Arrange boxes in grid
        max_row_height = 0
        current_x = cls.PADDING + 40
        current_y = cls.PADDING + 60
        row_heights: List[int] = []

        # Group into rows
        cols = min(cls.COLS, len(classes))
        for i, (c_name, layout) in enumerate(box_layouts.items()):
            col_idx = i % cols
            row_idx = i // cols

            if col_idx == 0 and i > 0:
                current_x = cls.PADDING + 40
                current_y += max_row_height + cls.GRID_GAP_Y
                max_row_height = 0

            layout["x"] = current_x
            layout["y"] = current_y
            layout["center_x"] = current_x + (layout["width"] / 2)
            layout["center_y"] = current_y + (layout["height"] / 2)

            max_row_height = max(max_row_height, layout["height"])
            current_x += layout["width"] + cls.GRID_GAP_X

        canvas_width = max(800, (cols * (cls.BOX_WIDTH + cls.GRID_GAP_X)) + 80)
        canvas_height = current_y + max_row_height + 80

        # 3. Build SVG Elements
        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_width} {canvas_height}" '
            f'width="{canvas_width}" height="{canvas_height}" style="background-color:#0B1120; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;">',
            cls._render_defs(),
        ]

        # Title
        if title:
            svg_parts.append(
                f'<text x="40" y="40" fill="#F8FAFC" font-size="20" font-weight="bold" font-family="system-ui,sans-serif">'
                f'{html.escape(title)}</text>'
            )

        # Draw Relationship Connectors first (behind boxes)
        for rel in static_model.relations:
            src_name = rel.source_id.split(".")[-1]
            tgt_name = rel.target_id.split(".")[-1]

            src_box = box_layouts.get(src_name)
            tgt_box = box_layouts.get(tgt_name)
            if src_box and tgt_box and src_box != tgt_box:
                svg_parts.append(cls._render_relation_connector(src_box, tgt_box, rel.relation_type, rel.label))

        # Draw Class Boxes
        for c_name, layout in box_layouts.items():
            svg_parts.append(cls._render_class_box(layout))

        svg_parts.append('</svg>')
        return "\n".join(svg_parts)

    @classmethod
    def _render_defs(cls) -> str:
        return """<defs>
    <style>
        .umldoc-class-node { cursor: pointer; transition: transform 0.15s ease; }
        .umldoc-class-node:hover rect { stroke: #38BDF8 !important; stroke-width: 2.2px !important; }
        .umldoc-class-node:hover path { fill: #1E3A5F !important; }
    </style>
    <!-- Inheritance / Realization Triangle Marker -->
    <marker id="inheritance" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">
        <polygon points="0,1 10,6 0,11" fill="#0B1120" stroke="#38BDF8" stroke-width="1.5" />
    </marker>
    <!-- Aggregation / Composition Diamond Marker -->
    <marker id="composition" markerWidth="14" markerHeight="12" refX="12" refY="6" orient="auto">
        <polygon points="0,6 6,1 12,6 6,11" fill="#38BDF8" stroke="#38BDF8" stroke-width="1.5" />
    </marker>
    <marker id="aggregation" markerWidth="14" markerHeight="12" refX="12" refY="6" orient="auto">
        <polygon points="0,6 6,1 12,6 6,11" fill="#0B1120" stroke="#38BDF8" stroke-width="1.5" />
    </marker>
    <!-- Association Arrow Marker -->
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
        <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#64748B" />
    </marker>
</defs>"""

    @classmethod
    def _render_class_box(cls, layout: Dict) -> str:
        c: ClassIR = layout["class_ir"]
        x = layout["x"]
        y = layout["y"]
        w = layout["width"]
        h = layout["height"]

        stereotype = f"«{c.kind.value}»" if c.kind != ElementKind.CLASS else ""
        header_title = c.name

        loc_attrs = ""
        if c.source_location and c.source_location.file_path:
            loc_attrs = (
                f' data-file="{html.escape(c.source_location.file_path)}" '
                f'data-line="{c.source_location.start_line}" '
                f'data-name="{html.escape(c.name)}" '
                f'class="umldoc-class-node"'
            )
        else:
            loc_attrs = f' data-name="{html.escape(c.name)}" class="umldoc-class-node"'

        box_parts = [
            f'<g id="class-{html.escape(c.name)}"{loc_attrs}>',
            # Outer Box
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{cls.BG_COLOR}" stroke="{cls.BORDER_COLOR}" stroke-width="1.5" />',
            # Header Background
            f'<path d="M {x} {y+6} Q {x} {y} {x+6} {y} L {x+w-6} {y} Q {x+w} {y} {x+w} {y+6} L {x+w} {y+cls.HEADER_HEIGHT} L {x} {y+cls.HEADER_HEIGHT} Z" fill="{cls.HEADER_BG}" />',
            f'<line x1="{x}" y1="{y+cls.HEADER_HEIGHT}" x2="{x+w}" y2="{y+cls.HEADER_HEIGHT}" stroke="{cls.BORDER_COLOR}" stroke-width="1" />',
        ]

        # Header Text
        if stereotype:
            box_parts.append(
                f'<text x="{x + w/2}" y="{y + 16}" fill="{cls.ACCENT_COLOR}" font-size="10" font-weight="600" text-anchor="middle">{stereotype}</text>'
            )
            box_parts.append(
                f'<text x="{x + w/2}" y="{y + 34}" fill="{cls.TEXT_COLOR}" font-size="13" font-weight="bold" text-anchor="middle">{html.escape(header_title)}</text>'
            )
        else:
            box_parts.append(
                f'<text x="{x + w/2}" y="{y + 26}" fill="{cls.TEXT_COLOR}" font-size="14" font-weight="bold" text-anchor="middle">{html.escape(header_title)}</text>'
            )

        # Attributes Compartment
        curr_y = y + cls.HEADER_HEIGHT + 14
        for a in c.attributes:
            vis = "+" if a.visibility == MemberVisibility.PUBLIC else "-"
            type_str = f" : {a.type_annotation}" if a.type_annotation else ""
            attr_label = html.escape(f"{vis} {a.name}{type_str}")
            box_parts.append(
                f'<text x="{x + 10}" y="{curr_y}" fill="{cls.TEXT_MUTED}" font-size="11">{attr_label}</text>'
            )
            curr_y += cls.LINE_HEIGHT

        if c.attributes and c.methods:
            # Separator between attributes and methods
            sep_y = y + cls.HEADER_HEIGHT + layout["attrs_height"]
            box_parts.append(
                f'<line x1="{x}" y1="{sep_y}" x2="{x+w}" y2="{sep_y}" stroke="{cls.BORDER_COLOR}" stroke-width="1" stroke-dasharray="2,2" />'
            )
            curr_y = sep_y + 14
        elif not c.attributes:
            curr_y = y + cls.HEADER_HEIGHT + 14

        # Methods Compartment
        for m in c.methods:
            vis = "+" if m.visibility == MemberVisibility.PUBLIC else "-"
            params_str = ", ".join(p.name for p in m.parameters)
            ret_str = f" : {m.return_type}" if m.return_type else ""
            method_label = html.escape(f"{vis} {m.name}({params_str}){ret_str}")
            box_parts.append(
                f'<text x="{x + 10}" y="{curr_y}" fill="{cls.TEXT_COLOR}" font-size="11">{method_label}</text>'
            )
            curr_y += cls.LINE_HEIGHT

        box_parts.append('</g>')
        return "\n".join(box_parts)

    @classmethod
    def _render_relation_connector(
        cls,
        src: Dict,
        tgt: Dict,
        rel_type: RelationType,
        label: Optional[str] = None,
    ) -> str:
        x1, y1 = src["center_x"], src["center_y"]
        x2, y2 = tgt["center_x"], tgt["center_y"]

        # Calculate bounding box edge intersections
        if x1 < x2:
            start_x = src["x"] + src["width"]
            end_x = tgt["x"]
        else:
            start_x = src["x"]
            end_x = tgt["x"] + tgt["width"]

        start_y = src["y"] + (src["height"] / 2)
        end_y = tgt["y"] + (tgt["height"] / 2)

        # Style based on relation type
        stroke_dash = 'stroke-dasharray="4,4"' if rel_type in (RelationType.REALIZATION, RelationType.DEPENDENCY) else ''
        marker = 'marker-end="url(#arrow)"'
        if rel_type in (RelationType.INHERITANCE, RelationType.REALIZATION):
            marker = 'marker-end="url(#inheritance)"'
        elif rel_type == RelationType.COMPOSITION:
            marker = 'marker-start="url(#composition)"'
        elif rel_type == RelationType.AGGREGATION:
            marker = 'marker-start="url(#aggregation)"'

        mid_x = (start_x + end_x) / 2
        path_d = f"M {start_x} {start_y} C {mid_x} {start_y}, {mid_x} {end_y}, {end_x} {end_y}"

        parts = [
            f'<path d="{path_d}" fill="none" stroke="{cls.LINE_COLOR}" stroke-width="1.5" {stroke_dash} {marker} />'
        ]

        if label:
            parts.append(
                f'<text x="{mid_x}" y="{(start_y + end_y)/2 - 6}" fill="{cls.ACCENT_COLOR}" font-size="10" text-anchor="middle">{html.escape(label)}</text>'
            )

        return "\n".join(parts)
