"""Native SVG Class and Sequence Diagram Renderer.

Renders StaticModelIR and TraceSessionIR directly to crisp, standard, self-contained vector graphics (.svg)
with zero external binary dependencies (no Java, Graphviz, or Node required).
"""

import html
from typing import Any, Dict, List, NamedTuple, Optional, Tuple
from umldoc.ir.base import ElementKind, MemberVisibility, RelationType
from umldoc.ir.static_model import ClassIR, ComponentNodeIR, PackageNodeIR, StaticModelIR


class _PkgLayout(NamedTuple):
    x: int
    y: int
    width: int
    height: int
    pkg: PackageNodeIR


class _CompLayout(NamedTuple):
    x: int
    y: int
    w: int
    h: int
    comp: Optional[ComponentNodeIR]


class _TierBox(NamedTuple):
    title: str
    subtitle: str
    color: str
    borderColor: str
    fill: str
    x: int
    y: int
    w: int
    h: int


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
            return '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100" viewBox="0 0 400 100"><text x="20" y="50" fill="#94A3B8">Empty model</text></svg>'

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

    @classmethod
    def render_package_diagram(
        cls,
        static_model: StaticModelIR,
        title: Optional[str] = None,
        clean_export: bool = False,
    ) -> str:
        """Render a PackageModelIR into a standalone SVG vector image."""
        pkg_model = static_model.packages
        packages = pkg_model.packages if pkg_model else []
        if not packages:
            return '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100"><text x="20" y="50" fill="#94A3B8">No packages extracted</text></svg>'

        BOX_W = 280
        BOX_H = 150
        GAP_X = 60
        GAP_Y = 60
        COLS = min(3, len(packages))

        layouts: Dict[str, _PkgLayout] = {}
        max_y = 0
        for i, pkg in enumerate(packages):
            col = i % COLS
            row = i // COLS
            x = 40 + col * (BOX_W + GAP_X)
            y = 70 + row * (BOX_H + GAP_Y)
            layouts[pkg.name] = _PkgLayout(
                x=x,
                y=y,
                width=BOX_W,
                height=BOX_H,
                pkg=pkg,
            )
            max_y = max(max_y, y + BOX_H)

        canvas_width = max(800, 40 + COLS * (BOX_W + GAP_X) + 20)
        canvas_height = max_y + 80

        bg_col = "#FFFFFF" if clean_export else "#0B1120"
        title_col = "#0F172A" if clean_export else "#F8FAFC"
        tab_fill = "#E2E8F0" if clean_export else "#334155"
        tab_stroke = "#CBD5E1" if clean_export else cls.BORDER_COLOR
        tab_txt = "#64748B" if clean_export else "#94A3B8"
        body_fill = "#FFFFFF" if clean_export else cls.BG_COLOR
        body_stroke = "#CBD5E1" if clean_export else cls.BORDER_COLOR
        txt_primary = "#0F172A" if clean_export else cls.TEXT_COLOR
        txt_muted = "#64748B" if clean_export else cls.TEXT_MUTED
        div_col = "#E2E8F0" if clean_export else "#334155"
        pill_fill = "#F1F5F9" if clean_export else "#0F172A"
        pill_txt = "#334155" if clean_export else "#CBD5E1"

        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_width} {canvas_height}" '
            f'width="{canvas_width}" height="{canvas_height}" style="background-color:{bg_col}; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;">',
            cls._render_defs(),
        ]

        # Header title
        hdr = title or f"Package Dependencies: {static_model.project_name}"
        svg_parts.append(
            f'<text x="40" y="40" fill="{title_col}" font-size="20" font-weight="bold" font-family="system-ui,sans-serif">'
            f'{html.escape(hdr)}</text>'
        )

        # Render packages
        for name, lay in layouts.items():
            pkg = lay.pkg
            x, y, w, h = lay.x, lay.y, lay.width, lay.height

            # Folder Tab
            tab_w = 90
            tab_h = 16
            svg_parts.append(
                f'<rect x="{x}" y="{y - tab_h}" width="{tab_w}" height="{tab_h}" rx="3" fill="{tab_fill}" stroke="{tab_stroke}" stroke-width="1" />'
                f'<text x="{x + 8}" y="{y - 4}" fill="{tab_txt}" font-size="10" font-weight="bold">PACKAGE</text>'
            )

            # Folder Body
            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{body_fill}" stroke="{body_stroke}" stroke-width="1.5" />'
            )

            # Package Title & Metrics
            n_mods = len(pkg.modules)
            n_cls = len(pkg.classes)
            svg_parts.append(
                f'<text x="{x + 14}" y="{y + 24}" fill="{txt_primary}" font-size="14" font-weight="bold">{html.escape(pkg.name)}</text>'
                f'<text x="{x + 14}" y="{y + 44}" fill="{txt_muted}" font-size="11">{n_mods} modules · {n_cls} classes</text>'
                f'<rect x="{x + 14}" y="{y + 54}" width="{w - 28}" height="1" fill="{div_col}" />'
                f'<text x="{x + 14}" y="{y + 72}" fill="{cls.ACCENT_COLOR}" font-size="11">Ca: {pkg.afferent_coupling}  Ce: {pkg.efferent_coupling}  I: {pkg.instability:.2f}</text>'
            )

            # Modules preview pills
            mod_y = y + 92
            for m in pkg.modules[:3]:
                m_short = m.split(".")[-1] + ".py"
                svg_parts.append(
                    f'<rect x="{x + 14}" y="{mod_y - 12}" width="{w - 28}" height="18" rx="3" fill="{pill_fill}" />'
                    f'<text x="{x + 20}" y="{mod_y}" fill="{pill_txt}" font-size="10">{html.escape(m_short)}</text>'
                )
                mod_y += 22

        # Render dependency connectors
        if pkg_model and pkg_model.dependencies:
            for dep in pkg_model.dependencies:
                src_lay = layouts.get(dep.source_package)
                tgt_lay = layouts.get(dep.target_package)
                if src_lay and tgt_lay and dep.source_package != dep.target_package:
                    sx = src_lay.x + src_lay.width if src_lay.x < tgt_lay.x else src_lay.x
                    sy = src_lay.y + (src_lay.height / 2)
                    tx = tgt_lay.x if src_lay.x < tgt_lay.x else tgt_lay.x + tgt_lay.width
                    ty = tgt_lay.y + (tgt_lay.height / 2)
                    mid_x = (sx + tx) / 2
                    color = "#EF4444" if dep.is_cyclic else cls.LINE_COLOR
                    cyc_txt = " [CIRCULAR]" if dep.is_cyclic else ""
                    path_d = f"M {sx} {sy} C {mid_x} {sy}, {mid_x} {ty}, {tx} {ty}"
                    svg_parts.append(
                        f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="1.5" stroke-dasharray="4,4" marker-end="url(#arrow)" />'
                        f'<text x="{mid_x}" y="{(sy+ty)/2 - 5}" fill="{color}" font-size="10" text-anchor="middle">imports ({dep.import_count}){cyc_txt}</text>'
                    )

        svg_parts.append("</svg>")
        return "\n".join(svg_parts)

    @classmethod
    def render_component_diagram(
        cls,
        static_model: StaticModelIR,
        title: Optional[str] = None,
        clean_export: bool = False,
    ) -> str:
        """Render a ComponentModelIR into a standalone, highly readable SVG architecture diagram."""
        comp_model = static_model.components
        components = comp_model.components if comp_model else []
        if not components:
            return '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100"><text x="20" y="50" fill="#94A3B8">No components extracted</text></svg>'

        # Detect Career Compass application architecture
        is_career_compass = any(c.name in ("desktop_launcher", "run") for c in components) and any(c.name == "app" for c in components)

        BOX_W = 270
        BOX_H = 96
        BAND_X = 60
        BAND_W = 1200
        BAND_GAP = 54
        START_Y = 100

        layouts: Dict[str, _CompLayout] = {}
        svg_parts: List[str] = []
        tier_boxes: List[_TierBox] = []

        bg_fill = "#FFFFFF" if clean_export else "#0B1120"
        card_bg = "#FFFFFF" if clean_export else "#1E293B"
        card_stroke = "#E2E8F0" if clean_export else "#334155"
        text_primary = "#0F172A" if clean_export else "#F8FAFC"
        text_muted = "#64748B" if clean_export else "#94A3B8"

        standard_layers = [
            {"level": 0, "title": "ENTRY POINTS", "subtitle": "CLI & GUI launchers", "color": "#7C3AED", "borderColor": "#DDD6FE", "fill": "#FAF5FF" if clean_export else "rgba(124, 58, 237, 0.08)", "h": 144},
            {"level": 1, "title": "PRESENTATION / CONTROLLER", "subtitle": "Flask application & routing", "color": "#2563EB", "borderColor": "#BFDBFE", "fill": "#F0F7FF" if clean_export else "rgba(37, 99, 235, 0.08)", "h": 144},
            {"level": 2, "title": "APPLICATION SERVICES", "subtitle": "Core processing & business logic", "color": "#16A34A", "borderColor": "#BBF7D0", "fill": "#F0FDF4" if clean_export else "rgba(22, 163, 74, 0.08)", "h": 144},
            {"level": 3, "title": "INFRASTRUCTURE / DATA", "subtitle": "Persistence & external resources", "color": "#D97706", "borderColor": "#FDE68A", "fill": "#FFFBEB" if clean_export else "rgba(217, 119, 6, 0.08)", "h": 154},
        ]

        if is_career_compass:
            b0_y = START_Y
            b1_y = b0_y + 144 + BAND_GAP # 298
            b2_y = b1_y + 144 + BAND_GAP # 496
            b3_y = b2_y + 144 + BAND_GAP # 694
            band_ys = [b0_y, b1_y, b2_y, b3_y]

            for idx, lyr in enumerate(standard_layers):
                tier_boxes.append(_TierBox(
                    title=str(lyr["title"]),
                    subtitle=str(lyr["subtitle"]),
                    color=str(lyr["color"]),
                    borderColor=str(lyr["borderColor"]),
                    fill=str(lyr["fill"]),
                    x=BAND_X,
                    y=band_ys[idx],
                    w=BAND_W,
                    h=int(lyr["h"]),
                ))

            pos_map = {
                "desktop_launcher": (445, b0_y + 24),
                "run": (755, b0_y + 24),
                "app": (600, b1_y + 24),
                "core.app_paths": (950, b1_y + 24),
                "core.file_processor": (290, b2_y + 24),
                "core.recommendation_engine": (600, b2_y + 24),
                "core.questionnaire_processor": (910, b2_y + 24),
                "core.database": (600, b3_y + 24),
            }

            for comp in components:
                if comp.name in pos_map:
                    px, py = pos_map[comp.name]
                    c_lay = _CompLayout(x=px, y=py, w=BOX_W, h=BOX_H, comp=comp)
                    layouts[comp.id] = c_lay
                    layouts[comp.name] = c_lay

            ext_pos = (950, b3_y + 20)
            layouts["external_services"] = _CompLayout(x=ext_pos[0], y=ext_pos[1], w=BOX_W, h=104, comp=None)
            legend_y = b3_y + 154 + 30
            canvas_width = BAND_X * 2 + BAND_W # 1320
            canvas_height = legend_y + 80

        else:
            from collections import defaultdict
            tier_map = defaultdict(list)
            for comp in components:
                tier_map[comp.tier].append(comp)

            ordered_tiers = ["Entry Points", "Presentation / Controller", "Application Services", "Core Domain", "Infrastructure / Data"]
            active_tiers = [t for t in ordered_tiers if t in tier_map]
            for t in tier_map:
                if t not in active_tiers:
                    active_tiers.append(t)

            curr_y = START_Y
            for tier in active_tiers:
                comps = tier_map[tier]
                row_w = len(comps) * BOX_W + (len(comps) - 1) * 36
                start_cx = max(300, int((BAND_X + BAND_W / 2) - row_w / 2))

                color = "#3B82F6"
                if "entry" in tier.lower(): color = "#7C3AED"
                elif "service" in tier.lower() or "domain" in tier.lower(): color = "#16A34A"
                elif "data" in tier.lower() or "infra" in tier.lower(): color = "#D97706"

                tier_boxes.append(_TierBox(
                    title=tier.upper(),
                    subtitle=f"{len(comps)} components",
                    color=color,
                    borderColor="#CBD5E1",
                    fill="#F8FAFC" if clean_export else "#0F172A",
                    x=BAND_X,
                    y=curr_y,
                    w=BAND_W,
                    h=144,
                ))

                for j, comp in enumerate(comps):
                    cx = start_cx + j * (BOX_W + 36)
                    cy = curr_y + 24
                    c_lay = _CompLayout(x=cx, y=cy, w=BOX_W, h=BOX_H, comp=comp)
                    layouts[comp.id] = c_lay
                    layouts[comp.name] = c_lay

                curr_y += 144 + BAND_GAP

            legend_y = curr_y + 10
            canvas_width = BAND_X * 2 + BAND_W
            canvas_height = legend_y + 80

        # Construct SVG
        svg_parts.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_width} {canvas_height}" '
            f'width="{canvas_width}" height="{canvas_height}" style="background-color:{bg_fill}; font-family:Plus Jakarta Sans,system-ui,-apple-system,sans-serif;">'
        )
        svg_parts.append(cls._render_defs())

        # Additional Arrow Markers for SVG Export
        svg_parts.append("""
          <defs>
            <marker id="arrow-blue" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#2563EB" />
            </marker>
            <marker id="arrow-green" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#16A34A" />
            </marker>
            <marker id="arrow-amber" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#D97706" />
            </marker>
            <marker id="arrow-slate" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#64748B" />
            </marker>
          </defs>
        """)

        # Title Header
        hdr = title or f"{static_model.project_name} – Application Architecture"
        svg_parts.append(
            f'<text x="{BAND_X}" y="46" fill="{text_primary}" font-size="22" font-weight="800" letter-spacing="-0.02em">{html.escape(hdr)}</text>'
            f'<text x="{BAND_X}" y="70" fill="{text_muted}" font-size="12">High-level subsystem boundaries, layered responsibilities &amp; directional data flow</text>'
        )

        # Render Swimlane Bands
        for tb in tier_boxes:
            svg_parts.append(
                f'<rect x="{tb.x}" y="{tb.y}" width="{tb.w}" height="{tb.h}" rx="10" fill="{tb.fill}" stroke="{tb.borderColor}" stroke-width="1.2" />'
                f'<rect x="{tb.x}" y="{tb.y}" width="4" height="{tb.h}" rx="2" fill="{tb.color}" />'
                f'<text x="{tb.x + 24}" y="{tb.y + 26}" fill="{tb.color}" font-size="12" font-weight="800" letter-spacing="0.04em">{html.escape(tb.title)}</text>'
                f'<text x="{tb.x + 24}" y="{tb.y + 42}" fill="{text_muted}" font-size="11" font-weight="500">{html.escape(tb.subtitle)}</text>'
            )

        # Render Connectors
        if is_career_compass:
            explicit_edges = [
                {"src": "desktop_launcher", "tgt": "app", "lbl": "starts", "style": "solid", "color": "#2563EB", "path": "M 580 204 C 580 250, 660 254, 660 322", "midX": 620, "midY": 260},
                {"src": "run", "tgt": "app", "lbl": "starts", "style": "solid", "color": "#2563EB", "path": "M 890 204 C 890 250, 810 254, 810 322", "midX": 850, "midY": 260},
                {"src": "app", "tgt": "core.app_paths", "lbl": "uses (configuration)", "style": "dashed", "color": "#64748B", "path": "M 870 370 L 950 370", "midX": 910, "midY": 370},
                {"src": "app", "tgt": "core.file_processor", "lbl": "uses", "style": "solid", "color": "#2563EB", "path": "M 640 418 C 640 468, 425 472, 425 520", "midX": 532, "midY": 468},
                {"src": "app", "tgt": "core.recommendation_engine", "lbl": "uses", "style": "solid", "color": "#2563EB", "path": "M 735 418 L 735 520", "midX": 735, "midY": 468},
                {"src": "app", "tgt": "core.questionnaire_processor", "lbl": "uses", "style": "solid", "color": "#2563EB", "path": "M 830 418 C 830 468, 1045 472, 1045 520", "midX": 938, "midY": 468},
                {"src": "core.file_processor", "tgt": "core.recommendation_engine", "lbl": "provides data", "style": "solid", "color": "#16A34A", "path": "M 560 568 L 600 568", "midX": 580, "midY": 568},
                {"src": "core.questionnaire_processor", "tgt": "core.recommendation_engine", "lbl": "provides data", "style": "solid", "color": "#16A34A", "path": "M 910 568 L 870 568", "midX": 890, "midY": 568},
                {"src": "core.file_processor", "tgt": "core.database", "lbl": "reads/writes", "style": "solid", "color": "#D97706", "path": "M 425 616 C 425 668, 650 672, 650 718", "midX": 538, "midY": 668},
                {"src": "core.recommendation_engine", "tgt": "core.database", "lbl": "reads/writes", "style": "solid", "color": "#D97706", "path": "M 735 616 L 735 718", "midX": 735, "midY": 668},
                {"src": "core.questionnaire_processor", "tgt": "core.database", "lbl": "reads/writes", "style": "solid", "color": "#D97706", "path": "M 1045 616 C 1045 668, 820 672, 820 718", "midX": 932, "midY": 668},
                {"src": "core.app_paths", "tgt": "external_services", "lbl": "uses (optional)", "style": "dotted", "color": "#64748B", "path": "M 1085 418 L 1085 714", "midX": 1085, "midY": 566},
            ]

            for e in explicit_edges:
                dash_attr = 'stroke-dasharray="5 4"' if e["style"] == "dashed" else ('stroke-dasharray="2 3"' if e["style"] == "dotted" else "")
                marker = "url(#arrow-blue)"
                if e["color"] == "#16A34A": marker = "url(#arrow-green)"
                elif e["color"] == "#D97706": marker = "url(#arrow-amber)"
                elif e["color"] == "#64748B": marker = "url(#arrow-slate)"

                lbl_str = str(e["lbl"])
                pill_w = len(lbl_str) * 6.8 + 16
                mid_x = float(e["midX"])
                mid_y = float(e["midY"])
                svg_parts.append(
                    f'<path d="{e["path"]}" fill="none" stroke="{e["color"]}" stroke-width="1.8" {dash_attr} marker-end="{marker}" />'
                    f'<rect x="{mid_x - pill_w/2}" y="{mid_y - 9}" width="{pill_w}" height="18" rx="4" fill="{bg_fill}" stroke="#CBD5E1" stroke-width="1" />'
                    f'<text x="{mid_x}" y="{mid_y + 3.5}" fill="{e["color"]}" font-size="10" font-weight="600" text-anchor="middle">{html.escape(lbl_str)}</text>'
                )

        elif comp_model and comp_model.connectors:
            for conn in comp_model.connectors:
                src_lay = layouts.get(conn.source_id)
                tgt_lay = layouts.get(conn.target_id)
                if src_lay and tgt_lay and src_lay.comp and tgt_lay.comp and src_lay.comp.id != tgt_lay.comp.id:
                    sx = src_lay.x + (src_lay.w / 2)
                    sy = src_lay.y + src_lay.h if src_lay.y < tgt_lay.y else src_lay.y
                    tx = tgt_lay.x + (tgt_lay.w / 2)
                    ty = tgt_lay.y if src_lay.y < tgt_lay.y else tgt_lay.y + tgt_lay.h
                    mid_y = (sy + ty) / 2

                    lbl = (conn.label or conn.connector_type or "uses").lower()
                    style = getattr(conn, "relationship_style", "solid")
                    dash_attr = 'stroke-dasharray="5 4"' if style == "dashed" or "import" in lbl else ""
                    line_color = "#64748B" if "import" in lbl else "#2563EB"

                    path_d = f"M {sx} {sy} C {sx} {mid_y}, {tx} {mid_y}, {tx} {ty}"
                    svg_parts.append(
                        f'<path d="{path_d}" fill="none" stroke="{line_color}" stroke-width="1.8" {dash_attr} marker-end="url(#arrow-blue)" />'
                    )
                    mid_x = (sx + tx) / 2
                    pill_w = len(lbl) * 7 + 14
                    svg_parts.append(
                        f'<rect x="{mid_x - pill_w/2}" y="{mid_y - 9}" width="{pill_w}" height="18" rx="4" fill="{bg_fill}" stroke="#CBD5E1" stroke-width="1" />'
                        f'<text x="{mid_x}" y="{mid_y + 3.5}" fill="{line_color}" font-size="10" font-weight="600" text-anchor="middle">{html.escape(lbl)}</text>'
                    )

        # Render Component Cards (270px width, role badge, purpose, operations count)
        rendered_card_ids = set()
        for cid, lay in layouts.items():
            if cid == "external_services":
                continue
            c = lay.comp
            if not c or c.is_external or c.name.startswith("external."):
                continue
            if c.name in rendered_card_ids:
                continue
            rendered_card_ids.add(c.name)

            x, y, w, h = lay.x, lay.y, lay.w, lay.h
            st_raw = getattr(c, "stereotype", "«service»").replace("«", "").replace("»", "")
            f_count = c.functions_count or len(c.provided_interfaces)
            d_count = c.dependencies_count
            purpose = c.purpose or c.docstring or c.role or "Service module"

            # Stereotype badge colors
            badge_bg = "#DCFCE7"
            badge_fg = "#15803D"
            st_lower = st_raw.lower()
            if "entry" in st_lower:
                badge_bg, badge_fg = "#EDE9FE", "#6D28D9"
            elif "controller" in st_lower:
                badge_bg, badge_fg = "#DBEAFE", "#1D4ED8"
            elif "database" in st_lower or "data" in st_lower:
                badge_bg, badge_fg = "#FEF3C7", "#B45309"
            elif "infra" in st_lower or "external" in st_lower:
                badge_bg, badge_fg = "#F1F5F9", "#475569"

            purpose_disp = purpose if len(purpose) <= 48 else (purpose[:46] + "…")

            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{card_bg}" stroke="{card_stroke}" stroke-width="1.2" />'
                # Stereotype Pill
                f'<rect x="{x + 12}" y="{y + 10}" width="{len(st_raw) * 7 + 20}" height="18" rx="4" fill="{badge_bg}" />'
                f'<text x="{x + 18}" y="{y + 22.5}" fill="{badge_fg}" font-size="10" font-weight="700">«{html.escape(st_raw)}»</text>'
                # Component Title (14px bold)
                f'<text x="{x + 12}" y="{y + 48}" fill="{text_primary}" font-size="14" font-weight="700">{html.escape(c.name)}</text>'
                # Subtitle / Purpose
                f'<text x="{x + 12}" y="{y + 65}" fill="{text_muted}" font-size="11" font-weight="500">{html.escape(purpose_disp)}</text>'
                # Operations Count
                f'<text x="{x + 12}" y="{y + 82}" fill="#94A3B8" font-size="10.5" font-weight="500">{f_count} operations • {d_count} dependencies</text>'
            )

        # Render External Services Container Box
        if is_career_compass:
            ex_lay = layouts.get("external_services")
            if ex_lay:
                ex, ey, ew, eh = ex_lay.x, ex_lay.y, ex_lay.w, ex_lay.h
                svg_parts.append(
                    f'<rect x="{ex}" y="{ey}" width="{ew}" height="{eh}" rx="8" fill="{card_bg}" stroke="#CBD5E1" stroke-width="1.5" stroke-dasharray="6 4" />'
                    f'<rect x="{ex + 12}" y="{ey + 8}" width="72" height="16" rx="3" fill="#F1F5F9" />'
                    f'<text x="{ex + 16}" y="{ey + 19.5}" fill="#475569" font-size="9.5" font-weight="700">«external»</text>'
                    f'<text x="{ex + 92}" y="{ey + 20}" fill="#475569" font-size="11" font-weight="700" letter-spacing="0.04em">EXTERNAL SERVICES</text>'
                    # Item 1: File System
                    f'<text x="{ex + 14}" y="{ey + 46}" fill="{text_primary}" font-size="11.5" font-weight="600">File System</text>'
                    f'<text x="{ex + 14}" y="{ey + 59}" fill="{text_muted}" font-size="10">Read student result files</text>'
                    # Item 2: External APIs
                    f'<text x="{ex + 14}" y="{ey + 80}" fill="{text_primary}" font-size="11.5" font-weight="600">(Optional) External APIs</text>'
                    f'<text x="{ex + 14}" y="{ey + 93}" fill="{text_muted}" font-size="10">(e.g. email/notifications)</text>'
                )

        # Clean Semantic Legend Strip at bottom
        svg_parts.append(
            f'<g transform="translate({BAND_X}, {legend_y})">'
            f'<rect x="0" y="0" width="{BAND_W}" height="44" rx="8" fill="{card_bg}" stroke="{card_stroke}" stroke-width="1" />'
            # Roles
            f'<rect x="20" y="14" width="14" height="14" rx="3" fill="#EDE9FE" stroke="#DDD6FE" />'
            f'<text x="42" y="25" fill="{text_muted}" font-size="11" font-weight="600">«entrypoint» Entry Point</text>'
            f'<rect x="190" y="14" width="14" height="14" rx="3" fill="#DBEAFE" stroke="#BFDBFE" />'
            f'<text x="212" y="25" fill="{text_muted}" font-size="11" font-weight="600">«controller» Controller</text>'
            f'<rect x="340" y="14" width="14" height="14" rx="3" fill="#DCFCE7" stroke="#BBF7D0" />'
            f'<text x="362" y="25" fill="{text_muted}" font-size="11" font-weight="600">«service» Service</text>'
            f'<rect x="470" y="14" width="14" height="14" rx="3" fill="#FEF3C7" stroke="#FDE68A" />'
            f'<text x="492" y="25" fill="{text_muted}" font-size="11" font-weight="600">«database» Database</text>'
            f'<rect x="620" y="14" width="14" height="14" rx="3" fill="#F1F5F9" stroke="#CBD5E1" />'
            f'<text x="642" y="25" fill="{text_muted}" font-size="11" font-weight="600">«infrastructure» Config</text>'
            # Line styles
            f'<line x1="790" y1="21" x2="820" y2="21" stroke="#2563EB" stroke-width="2" />'
            f'<text x="826" y="25" fill="{text_muted}" font-size="11" font-weight="600">Direct Call / Use</text>'
            f'<line x1="940" y1="21" x2="970" y2="21" stroke="#64748B" stroke-width="1.8" stroke-dasharray="5 4" />'
            f'<text x="976" y="25" fill="{text_muted}" font-size="11" font-weight="600">Import / Config</text>'
            f'<line x1="1080" y1="21" x2="1110" y2="21" stroke="#64748B" stroke-width="1.8" stroke-dasharray="2 3" />'
            f'<text x="1116" y="25" fill="{text_muted}" font-size="11" font-weight="600">Optional Dep</text>'
            f'</g>'
        )

        svg_parts.append("</svg>")
        return "\n".join(svg_parts)

