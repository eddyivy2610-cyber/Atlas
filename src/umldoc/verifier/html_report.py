"""HTML report generator for UML architecture documentation, verification, and drift analysis.

Generates a modern, standalone, 100% self-contained Executive Architecture Dossier
with zero external runtime dependencies.
"""

from typing import Optional
from umldoc.generators.mermaid import MermaidGenerator
from umldoc.generators.plantuml import PlantUMLGenerator
from umldoc.generators.svg_renderer import SVGDiagramRenderer
from umldoc.ir.base import VerificationStatus
from umldoc.ir.schema import DocumentIR


def _badge_color(status: VerificationStatus) -> str:
    if status in (VerificationStatus.MATCH, VerificationStatus.VERIFIED_GROUND_TRUTH):
        return "#10B981"  # Emerald green
    elif status == VerificationStatus.HALLUCINATED:
        return "#EF4444"  # Red
    elif status == VerificationStatus.DRIFTED:
        return "#F59E0B"  # Amber
    elif status == VerificationStatus.MISSING:
        return "#8B5CF6"  # Purple
    return "#6B7280"  # Gray


class HTMLReportGenerator:
    """Generates modern, standalone HTML architecture dossiers with zero external dependencies."""

    @classmethod
    def generate_report(
        cls,
        document_ir: DocumentIR,
        title: Optional[str] = None,
    ) -> str:
        """Render a complete DocumentIR into a self-contained, tabbed HTML dossier."""
        project = document_ir.project_name
        static_model = document_ir.static_model
        verif = document_ir.verification
        drift = document_ir.drift_report
        traces = document_ir.dynamic_model.sessions if document_ir.dynamic_model else []
        report_title = title or f"UMLdoc Architecture Dossier: {project}"

        # -------------------------------------------------------------------
        # Summary KPIs
        # -------------------------------------------------------------------
        class_count = len(static_model.classes) if static_model else 0
        relation_count = len(static_model.relations) if static_model else 0
        total_verif = verif.total_elements if verif else 0
        verified = verif.verified_count if verif else 0
        hallucinated = verif.hallucinated_count if verif else 0
        drifted = verif.drifted_count if verif else 0
        missing = verif.missing_count if verif else 0
        score = int((verif.overall_confidence if verif else 1.0) * 100)
        drift_count = len(drift.drifted_elements) if drift else 0
        trace_count = len(traces)

        # -------------------------------------------------------------------
        # Diagrams (PlantUML, Mermaid, and Native SVG)
        # -------------------------------------------------------------------
        puml_code = PlantUMLGenerator.generate_class_diagram(static_model, title=project) if static_model else "@startuml\n@enduml"
        mmd_code = MermaidGenerator.generate_class_diagram(static_model, title=project) if static_model else "classDiagram"
        svg_diagram = SVGDiagramRenderer.render_class_diagram(static_model, title=f"{project} System Architecture") if static_model else ""

        # -------------------------------------------------------------------
        # 1. Static Model Class Cards (Offline Visual Architecture Explorer)
        # -------------------------------------------------------------------
        class_cards_html = []
        if static_model:
            for cls_ir in static_model.classes:
                methods_list = []
                for m in cls_ir.methods:
                    params_str = ", ".join(p.name for p in m.parameters)
                    ret_str = f" <span class='ret'>: {m.return_type}</span>" if m.return_type else ""
                    methods_list.append(f"<div class='method-item'><span class='vis'>+</span> <span class='m-name'>{m.name}</span>({params_str}){ret_str}</div>")
                methods_html = "".join(methods_list) or "<div style='color:var(--text-muted); font-size:0.85em;'>No public methods declared</div>"

                attrs_list = []
                for a in cls_ir.attributes:
                    a_type_str = f" <span class='ret'>: {a.type_annotation}</span>" if a.type_annotation else ""
                    attrs_list.append(f"<div class='attr-item'><span class='vis'>-</span> <span class='a-name'>{a.name}</span>{a_type_str}</div>")
                attrs_html = "".join(attrs_list)

                bases_str = f" : {', '.join(cls_ir.bases)}" if cls_ir.bases else ""
                stereotype = f"&laquo;{cls_ir.kind.value}&raquo; " if cls_ir.kind.value != "class" else ""
                src_loc = ""
                if cls_ir.source_location and cls_ir.source_location.file_path:
                    raw_path = cls_ir.source_location.file_path.replace("\\", "/")
                    parts = [p for p in raw_path.split("/") if p]
                    rel_path = "/".join(parts[-2:]) if len(parts) >= 2 else (parts[0] if parts else "")
                    src_loc = f"{rel_path}:{cls_ir.source_location.start_line}"

                class_cards_html.append(f"""
                <div class="entity-card">
                    <div class="entity-header">
                        <div>
                            <span class="entity-kind">{stereotype}</span>
                            <span class="entity-title">{cls_ir.name}</span>
                            <span class="entity-bases">{bases_str}</span>
                        </div>
                        {f'<span class="source-tag">{src_loc}</span>' if src_loc else ''}
                    </div>
                    {f'<div class="entity-section">{attrs_html}</div>' if attrs_html else ''}
                    <div class="entity-section">
                        {methods_html}
                    </div>
                </div>
                """)
        class_grid_body = "\n".join(class_cards_html) if class_cards_html else "<p>No static model classes available.</p>"

        # -------------------------------------------------------------------
        # 2. Static Model Relationships Table
        # -------------------------------------------------------------------
        rel_rows = []
        if static_model and static_model.relations:
            for r in static_model.relations:
                label_cell = r.label if r.label else "<span style='color:#64748B;'>—</span>"
                rel_rows.append(f"""
                <tr>
                    <td style="font-family:monospace; font-weight:600;">{r.source_id.split('.')[-1]}</td>
                    <td><span class="badge" style="background:#0284C720; color:#38BDF8; border:1px solid #38BDF850;">{r.relation_type.value.upper()}</span></td>
                    <td style="font-family:monospace; font-weight:600;">{r.target_id.split('.')[-1]}</td>
                    <td>{label_cell}</td>
                </tr>
                """)
        rel_table_body = "\n".join(rel_rows) if rel_rows else "<tr><td colspan='4'>No relationships declared.</td></tr>"

        # -------------------------------------------------------------------
        # 3. Verification Table
        # -------------------------------------------------------------------
        verif_rows = []
        if verif:
            for item in verif.verifications:
                color = _badge_color(item.status)
                issues_str = "<br>".join(item.issues) if item.issues else "<span style='color:#64748B;'>None</span>"
                gt_ref = item.ground_truth_ref
                if gt_ref:
                    raw_gt = gt_ref.replace("\\", "/")
                    if ":" in raw_gt:
                        p_part, line_part = raw_gt.rsplit(":", 1)
                        p_parts = [p for p in p_part.split("/") if p]
                        p_clean = "/".join(p_parts[-2:]) if len(p_parts) >= 2 else (p_parts[0] if p_parts else p_part)
                        gt_ref = f"{p_clean}:{line_part}"
                else:
                    gt_ref = "<span style='color:#64748B;'>N/A</span>"

                verif_rows.append(f"""
                <tr>
                    <td style="font-weight:600; font-family:monospace;">{item.element_name}</td>
                    <td><span class="badge" style="background-color: {color}20; color: {color}; border: 1px solid {color}80;">{item.status.value.upper()}</span></td>
                    <td><strong>{int(item.confidence_score * 100)}%</strong></td>
                    <td style="font-family:monospace; font-size:0.85em;">{gt_ref}</td>
                    <td>{item.evidence}</td>
                    <td style="font-size:0.85em; color:#F87171;">{issues_str}</td>
                </tr>
                """)
        verif_table_body = "\n".join(verif_rows) if verif_rows else "<tr><td colspan='6'>No verification records available.</td></tr>"

        # -------------------------------------------------------------------
        # 4. Historical Drift Section
        # -------------------------------------------------------------------
        drift_rows = []
        if drift:
            for d in drift.drifted_elements:
                brk_badge = "<span class='badge' style='background-color:#EF444420; color:#EF4444; border:1px solid #EF444460;'>BREAKING</span>" if d.is_breaking else "<span class='badge' style='background-color:#10B98120; color:#10B981; border:1px solid #10B98160;'>SAFE</span>"
                drift_rows.append(f"""
                <tr>
                    <td style="font-family:monospace; font-weight:600;">{d.element_name}</td>
                    <td><span class="badge" style="background-color:#F59E0B20; color:#F59E0B; border:1px solid #F59E0B60;">{d.change_type.value.upper()}</span></td>
                    <td>{brk_badge}</td>
                    <td>{d.diff_description}</td>
                </tr>
                """)
        drift_table_body = "\n".join(drift_rows) if drift_rows else "<tr><td colspan='4'>No structural drift detected.</td></tr>"

        # -------------------------------------------------------------------
        # 5. Dynamic Trace Session (Sequence Events)
        # -------------------------------------------------------------------
        trace_sections_html = []
        if traces:
            for session in traces:
                seq_rows = []
                for evt in session.interactions:
                    ret_str = f" &rarr; {evt.return_value.repr_value}" if evt.return_value else ""
                    seq_rows.append(f"""
                    <tr>
                        <td>{evt.sequence_order}</td>
                        <td style="font-family:monospace; font-weight:600;">{evt.caller_id}</td>
                        <td>&rarr;</td>
                        <td style="font-family:monospace; font-weight:600;">{evt.callee_id}</td>
                        <td style="font-family:monospace; color:#38BDF8;">{evt.method_name}(){ret_str}</td>
                    </tr>
                    """)
                seq_table_body = "\n".join(seq_rows) if seq_rows else "<tr><td colspan='5'>No interaction events recorded.</td></tr>"
                trace_sections_html.append(f"""
                <div class="card" style="margin-bottom:1.5rem;">
                    <h3>Trace: {session.scenario_name} (Duration: {session.duration_ms:.2f}ms)</h3>
                    <p style="color:var(--text-muted); font-size:0.9em;">Entrypoint: <code>{session.entrypoint}</code> | Participants: {len(session.participants)}</p>
                    <table>
                        <thead>
                            <tr><th>#</th><th>Caller</th><th></th><th>Callee</th><th>Invocation</th></tr>
                        </thead>
                        <tbody>{seq_table_body}</tbody>
                    </table>
                </div>
                """)
        traces_body = "\n".join(trace_sections_html) if trace_sections_html else "<p>No dynamic trace sessions in this document.</p>"

        # -------------------------------------------------------------------
        # Complete Self-Contained HTML Document
        # -------------------------------------------------------------------
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title}</title>
    <style>
        :root {{
            --bg: #0F172A;
            --surface: #1E293B;
            --surface-card: #243248;
            --text: #F8FAFC;
            --text-muted: #94A3B8;
            --border: #334155;
            --accent: #38BDF8;
            --accent-hover: #0284C7;
            --green: #10B981;
            --red: #EF4444;
            --amber: #F59E0B;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            padding: 2rem;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}
        .container {{
            max-width: 1300px;
            margin: 0 auto;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
        }}
        .header-title h1 {{
            margin: 0;
            font-size: 1.85rem;
            letter-spacing: -0.02em;
        }}
        .header-meta {{
            margin: 0.25rem 0 0 0;
            color: var(--text-muted);
            font-size: 0.9em;
        }}
        .fidelity-pill {{
            background: rgba(56, 189, 248, 0.1);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 9999px;
            padding: 0.5rem 1.25rem;
            font-size: 1.15rem;
            font-weight: 700;
            color: var(--accent);
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .kpi-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.25rem;
            text-align: center;
        }}
        .kpi-label {{
            color: var(--text-muted);
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .kpi-num {{
            font-size: 2rem;
            font-weight: 700;
            margin-top: 0.25rem;
        }}
        .tabs-nav {{
            display: flex;
            gap: 0.5rem;
            border-bottom: 1px solid var(--border);
            margin-bottom: 1.5rem;
            overflow-x: auto;
        }}
        .tab-btn {{
            background: none;
            border: none;
            padding: 0.75rem 1.25rem;
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-muted);
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.15s ease;
        }}
        .tab-btn:hover {{
            color: var(--text);
        }}
        .tab-btn.active {{
            color: var(--accent);
            border-bottom: 2px solid var(--accent);
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}
        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            overflow-x: auto;
        }}
        .entity-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 1.25rem;
        }}
        .entity-card {{
            background: var(--surface-card);
            border: 1px solid var(--border);
            border-radius: 6px;
            overflow: hidden;
        }}
        .entity-header {{
            background: rgba(15, 23, 42, 0.6);
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .entity-kind {{
            font-size: 0.75em;
            color: var(--accent);
            font-weight: 600;
        }}
        .entity-title {{
            font-size: 1.05rem;
            font-weight: 700;
            margin-left: 0.25rem;
        }}
        .entity-bases {{
            font-size: 0.85em;
            color: var(--text-muted);
        }}
        .source-tag {{
            font-size: 0.75em;
            font-family: monospace;
            background: rgba(255, 255, 255, 0.05);
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            color: var(--text-muted);
        }}
        .entity-section {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            font-family: monospace;
            font-size: 0.85rem;
        }}
        .entity-section:last-child {{ border-bottom: none; }}
        .method-item, .attr-item {{
            margin-bottom: 0.35rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .vis {{ color: var(--accent); font-weight: bold; margin-right: 0.25rem; }}
        .m-name {{ font-weight: 600; }}
        .ret {{ color: var(--text-muted); }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}
        th, td {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            color: var(--text-muted);
            font-size: 0.8em;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .badge {{
            display: inline-block;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: 700;
            letter-spacing: 0.03em;
        }}
        pre {{
            background: #090D16;
            border: 1px solid var(--border);
            padding: 1rem;
            border-radius: 6px;
            overflow-x: auto;
            color: #E2E8F0;
            font-size: 0.9em;
        }}
        .download-btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: var(--surface-card);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 0.6rem 1rem;
            border-radius: 6px;
            text-decoration: none;
            font-size: 0.9em;
            font-weight: 600;
            margin-right: 0.75rem;
            margin-bottom: 0.75rem;
            transition: all 0.15s ease;
        }}
        .download-btn:hover {{
            background: var(--accent-hover);
            color: #fff;
        }}
        .tool-btn {{
            background: var(--surface-card);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 0.45rem 0.8rem;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .tool-btn:hover {{
            background: var(--accent);
            color: #0F172A;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Executive Header -->
        <div class="header">
            <div class="header-title">
                <h1>🛡️ {report_title}</h1>
                <p class="header-meta">Schema v{document_ir.schema_version} | Generated {document_ir.generated_at} | 100% Offline Portable Dossier</p>
            </div>
            <div class="fidelity-pill">
                Fidelity: {score}%
            </div>
        </div>

        <!-- Executive KPIs -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">Core Classes</div>
                <div class="kpi-num" style="color:var(--accent);">{class_count}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Relations</div>
                <div class="kpi-num">{relation_count}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Verified Ground Truth</div>
                <div class="kpi-num" style="color:var(--green);">{verified}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Hallucinations</div>
                <div class="kpi-num" style="color:var(--red);">{hallucinated}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Drifted Signatures</div>
                <div class="kpi-num" style="color:var(--amber);">{drifted}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Git Drift Diffs</div>
                <div class="kpi-num">{drift_count}</div>
            </div>
        </div>

        <!-- Tab Navigation -->
        <div class="tabs-nav">
            <button class="tab-btn active" onclick="switchTab('tab-architecture')">🏛️ Architecture Explorer</button>
            <button class="tab-btn" onclick="switchTab('tab-verification')">🔍 Verification Matrix</button>
            <button class="tab-btn" onclick="switchTab('tab-drift')">📈 Git Drift Evolution</button>
            <button class="tab-btn" onclick="switchTab('tab-traces')">⚡ Dynamic Traces ({trace_count})</button>
            <button class="tab-btn" onclick="switchTab('tab-sources')">📄 Raw Sources & Markup</button>
        </div>

        <!-- Tab 1: Architecture Explorer -->
        <div id="tab-architecture" class="tab-content active">
            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem; flex-wrap:wrap; gap:0.5rem;">
                    <h2 style="margin:0;">📊 Visual Architecture Diagram (Native Vector SVG)</h2>
                    <div style="display:flex; gap:0.5rem; align-items:center; flex-wrap:wrap;">
                        <button class="tool-btn" onclick="zoomDiagram(1.25)">🔍+ Zoom In</button>
                        <button class="tool-btn" onclick="zoomDiagram(0.8)">🔍- Zoom Out</button>
                        <button class="tool-btn" onclick="resetDiagram()">↺ Reset</button>
                        <a href="architecture.svg" class="download-btn" style="margin:0;" download>📥 Download SVG</a>
                    </div>
                </div>
                <div id="svg-viewport" style="overflow:hidden; height:650px; background:#0B1120; border-radius:8px; border:1px solid var(--border); position:relative; cursor:grab;">
                    <div id="svg-canvas" style="transform-origin: 0 0; position:absolute; left:0; top:0; transition: transform 0.05s ease-out;">
                        {svg_diagram}
                    </div>
                    <div style="position:absolute; bottom:12px; right:16px; background:rgba(15,23,42,0.85); padding:4px 10px; border-radius:4px; font-size:0.75em; color:var(--text-muted); pointer-events:none; border:1px solid var(--border);">
                        🖱️ Drag to Pan | Scroll to Zoom
                    </div>
                </div>
            </div>

            <div class="card">
                <h2 style="margin-top:0;">Domain Entities & Class Structures</h2>
                <div class="entity-grid">
                    {class_grid_body}
                </div>
            </div>

            <div class="card">
                <h2 style="margin-top:0;">Class Relationships & Hierarchies</h2>
                <table>
                    <thead>
                        <tr><th>Source Entity</th><th>Relationship Type</th><th>Target Entity</th><th>Label / Semantics</th></tr>
                    </thead>
                    <tbody>
                        {rel_table_body}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Tab 2: Verification Matrix -->
        <div id="tab-verification" class="tab-content">
            <div class="card">
                <h2 style="margin-top:0;">Element-Level Verification Confidence</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Element Name</th>
                            <th>Status</th>
                            <th>Confidence</th>
                            <th>Ground Truth Source</th>
                            <th>Evidence</th>
                            <th>Discrepancies / Issues</th>
                        </tr>
                    </thead>
                    <tbody>
                        {verif_table_body}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Tab 3: Git Drift Evolution -->
        <div id="tab-drift" class="tab-content">
            <div class="card">
                <h2 style="margin-top:0;">Git Drift Analysis {f'({drift.base_commit} &rarr; {drift.target_commit})' if drift else ''}</h2>
                <p style="color:var(--text-muted);">{drift.summary_notes if drift and drift.summary_notes else 'Comprehensive structural diff analysis tracking evolutionary drift across release commits.'}</p>
                <table>
                    <thead>
                        <tr>
                            <th>Element Name</th>
                            <th>Change Classification</th>
                            <th>API Stability Impact</th>
                            <th>Structural Diff Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        {drift_table_body}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Tab 4: Dynamic Traces -->
        <div id="tab-traces" class="tab-content">
            {traces_body}
        </div>

        <!-- Tab 5: Raw Sources & Downloads -->
        <div id="tab-sources" class="tab-content">
            <div class="card">
                <h2 style="margin-top:0;">Distributable Artifacts</h2>
                <a href="architecture.svg" class="download-btn" download>📥 Rendered Diagram (.svg)</a>
                <a href="architecture.puml" class="download-btn" download>📥 PlantUML Source (.puml)</a>
                <a href="architecture.mmd" class="download-btn" download>📥 Mermaid Source (.mmd)</a>
                <a href="document_ir.json" class="download-btn" download>📥 Canonical IR JSON</a>
                {f'<a href="verification_metrics.json" class="download-btn" download>📥 Metrics JSON</a>' if verif else ''}
            </div>

            <div class="card">
                <h3>PlantUML Source Specification</h3>
                <pre><code>{puml_code}</code></pre>
            </div>

            <div class="card">
                <h3>Mermaid.js Specification</h3>
                <pre><code>{mmd_code}</code></pre>
            </div>
        </div>
    </div>

    <!-- 100% Inline Zero-Dependency Tab Switcher and Pan/Zoom Controller -->
    <script>
        function switchTab(tabId) {{
            document.querySelectorAll('.tab-btn').forEach(function(btn) {{ btn.classList.remove('active'); }});
            document.querySelectorAll('.tab-content').forEach(function(content) {{ content.classList.remove('active'); }});
            
            var targetContent = document.getElementById(tabId);
            if (targetContent) {{
                targetContent.classList.add('active');
            }}
            
            var clickedBtn = Array.from(document.querySelectorAll('.tab-btn')).find(function(btn) {{
                return btn.getAttribute('onclick') && btn.getAttribute('onclick').indexOf(tabId) !== -1;
            }});
            if (clickedBtn) {{
                clickedBtn.classList.add('active');
            }}
        }}

        // Interactive Pan & Zoom Controller
        (function() {{
            var canvas = document.getElementById('svg-canvas');
            var viewport = document.getElementById('svg-viewport');
            if (!canvas || !viewport) return;

            var scale = 0.85;
            var translateX = 20;
            var translateY = 20;
            var isDragging = false;
            var startX = 0;
            var startY = 0;

            function applyTransform() {{
                canvas.style.transform = 'translate(' + translateX + 'px, ' + translateY + 'px) scale(' + scale + ')';
            }}
            applyTransform();

            window.zoomDiagram = function(factor) {{
                scale = Math.min(Math.max(scale * factor, 0.15), 4.0);
                applyTransform();
            }};

            window.resetDiagram = function() {{
                scale = 0.85;
                translateX = 20;
                translateY = 20;
                applyTransform();
            }};

            viewport.addEventListener('wheel', function(e) {{
                e.preventDefault();
                var factor = e.deltaY < 0 ? 1.15 : 0.87;
                var rect = viewport.getBoundingClientRect();
                var mouseX = e.clientX - rect.left;
                var mouseY = e.clientY - rect.top;
                
                var newScale = Math.min(Math.max(scale * factor, 0.15), 4.0);
                var scaleRatio = newScale / scale;
                
                translateX = mouseX - (mouseX - translateX) * scaleRatio;
                translateY = mouseY - (mouseY - translateY) * scaleRatio;
                scale = newScale;
                applyTransform();
            }});

            viewport.addEventListener('mousedown', function(e) {{
                if (e.target.closest('button') || e.target.closest('a')) return;
                isDragging = true;
                startX = e.clientX - translateX;
                startY = e.clientY - translateY;
                viewport.style.cursor = 'grabbing';
            }});

            window.addEventListener('mousemove', function(e) {{
                if (!isDragging) return;
                translateX = e.clientX - startX;
                translateY = e.clientY - startY;
                applyTransform();
            }});

            window.addEventListener('mouseup', function() {{
                if (isDragging) {{
                    isDragging = false;
                    viewport.style.cursor = 'grab';
                }}
            }});
        }})();
    </script>
</body>
</html>
"""
        return html
