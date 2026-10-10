"""PlantUML diagram generator from Static and Dynamic IR."""

from typing import Optional
from umldoc.ir.base import ElementKind, MemberVisibility, RelationType
from umldoc.ir.dynamic_model import InteractionEventType, TraceSessionIR
from umldoc.ir.static_model import ClassIR, StaticModelIR


def _visibility_symbol(vis: MemberVisibility) -> str:
    if vis == MemberVisibility.PUBLIC:
        return "+"
    elif vis == MemberVisibility.PROTECTED:
        return "#"
    elif vis == MemberVisibility.PRIVATE:
        return "-"
    return "+"


class PlantUMLGenerator:
    """Generates valid PlantUML (.puml) code for class and sequence diagrams."""

    @classmethod
    def generate_class_diagram(cls, static_model: StaticModelIR, title: Optional[str] = None) -> str:
        """Generate PlantUML class diagram string from StaticModelIR."""
        lines = [
            "@startuml",
            "skinparam classAttributeIconSize 0",
            "skinparam monochrome false",
            "skinparam shadowing false",
            "skinparam defaultFontName Arial",
        ]
        if title:
            lines.append(f"title {title}")
        elif static_model.project_name:
            lines.append(f"title Class Architecture: {static_model.project_name}")

        lines.append("")

        # 1. Classes
        for class_ir in static_model.classes:
            lines.extend(cls._render_class(class_ir))
            lines.append("")

        # 2. Relationships
        for rel in static_model.relations:
            src = rel.source_id.replace(".", "_")
            tgt = rel.target_id.replace(".", "_")
            label_str = f" : {rel.label}" if rel.label else ""

            if rel.relation_type == RelationType.INHERITANCE:
                lines.append(f"{tgt} <|-- {src}{label_str}")
            elif rel.relation_type == RelationType.REALIZATION:
                lines.append(f"{tgt} <|.. {src}{label_str}")
            elif rel.relation_type == RelationType.COMPOSITION:
                lines.append(f"{src} *-- {tgt}{label_str}")
            elif rel.relation_type == RelationType.AGGREGATION:
                lines.append(f"{src} o-- {tgt}{label_str}")
            elif rel.relation_type == RelationType.ASSOCIATION:
                lines.append(f"{src} --> {tgt}{label_str}")
            elif rel.relation_type == RelationType.DEPENDENCY:
                lines.append(f"{src} ..> {tgt}{label_str}")

        lines.append("")
        lines.append("@enduml")
        return "\n".join(lines)

    @classmethod
    def _render_class(cls, class_ir: ClassIR) -> list[str]:
        lines = []
        stereotype = ""
        if class_ir.kind == ElementKind.MODULE:
            stereotype = " <<module>>"
        elif class_ir.kind == ElementKind.INTERFACE or class_ir.is_abstract:
            stereotype = " <<interface>>"
        elif class_ir.kind == ElementKind.PROTOCOL or class_ir.is_protocol:
            stereotype = " <<protocol>>"
        elif class_ir.kind == ElementKind.DATACLASS or class_ir.is_dataclass:
            stereotype = " <<dataclass>>"
        elif class_ir.kind == ElementKind.ENUM or class_ir.is_enum:
            stereotype = " <<enum>>"

        safe_name = class_ir.name.replace(".", "_")
        if safe_name != class_ir.name:
            lines.append(f'class "{class_ir.name}" as {safe_name}{stereotype} {{')
        else:
            lines.append(f"class {safe_name}{stereotype} {{")

        # Attributes
        for attr in class_ir.attributes:
            vis = _visibility_symbol(attr.visibility)
            type_str = f": {attr.type_annotation}" if attr.type_annotation else ""
            default_str = f" = {attr.default_value}" if attr.default_value else ""
            lines.append(f"  {vis}{attr.name}{type_str}{default_str}")

        if class_ir.attributes and class_ir.methods:
            lines.append("  __")

        # Methods
        for method in class_ir.methods:
            vis = _visibility_symbol(method.visibility)
            param_strs = []
            for p in method.parameters:
                p_ann = f": {p.type_annotation}" if p.type_annotation else ""
                param_strs.append(f"{p.name}{p_ann}")
            param_joined = ", ".join(param_strs)
            ret_str = f": {method.return_type}" if method.return_type else ""
            prefix = "{static} " if method.is_static else "{abstract} " if method.is_abstract else ""
            lines.append(f"  {vis}{prefix}{method.name}({param_joined}){ret_str}")

        lines.append("}")
        return lines

    @classmethod
    def generate_sequence_diagram(cls, session: TraceSessionIR) -> str:
        """Generate PlantUML sequence diagram string from TraceSessionIR."""
        lines = [
            "@startuml",
            "autonumber",
            "skinparam shadowing false",
            "skinparam defaultFontName Arial",
            f"title Sequence Trace: {session.scenario_name} ({session.entrypoint})",
            "",
        ]

        # Declare participants
        for p in session.participants:
            lines.append(f'participant "{p.name}" as {p.id}')

        lines.append("")

        for evt in session.interactions:
            caller = evt.caller_id
            callee = evt.callee_id

            if evt.event_type == InteractionEventType.CALL:
                arg_list = []
                for k, v in evt.arguments.items():
                    arg_list.append(f"{k}={v.repr_value}")
                arg_str = ", ".join(arg_list)
                lines.append(f"{caller} -> {callee} : {evt.method_name}({arg_str})")
                lines.append(f"activate {callee}")

            elif evt.event_type == InteractionEventType.RETURN:
                ret_val = evt.return_value.repr_value if evt.return_value else "None"
                lines.append(f"{caller} --> {callee} : return {ret_val}")
                lines.append(f"deactivate {caller}")

            elif evt.event_type == InteractionEventType.EXCEPTION:
                exc_msg = evt.exception.message if evt.exception else "Error"
                exc_type = evt.exception.type_name if evt.exception else "Exception"
                lines.append(f"{caller} --x {callee} : raise {exc_type}({exc_msg})")
                lines.append(f"deactivate {caller}")

        lines.append("")
        lines.append("@enduml")
        return "\n".join(lines)

    @classmethod
    def generate_package_diagram(cls, static_model: StaticModelIR, title: Optional[str] = None) -> str:
        """Generate PlantUML package dependency diagram (.puml)."""
        pkg_model = static_model.packages
        lines = [
            "@startuml",
            "skinparam monochrome false",
            "skinparam shadowing false",
            "skinparam defaultFontName Arial",
            "skinparam packageStyle folder",
        ]
        if title:
            lines.append(f"title {title}")
        elif static_model.project_name:
            lines.append(f"title Package Dependencies: {static_model.project_name}")
        lines.append("")

        if not pkg_model or not pkg_model.packages:
            lines.append("' No package hierarchy extracted")
            lines.append("@enduml")
            return "\n".join(lines)

        for pkg in pkg_model.packages:
            safe_id = f"pkg_{pkg.name.replace('.', '_')}"
            n_mods = len(pkg.modules)
            n_cls = len(pkg.classes)
            lines.append(f'package "{pkg.name} ({n_mods} modules, {n_cls} classes)" as {safe_id} {{')
            lines.append(f'  note as note_{safe_id}')
            lines.append(f"    Ca: {pkg.afferent_coupling} | Ce: {pkg.efferent_coupling} | Instability: {pkg.instability}")
            lines.append(f'  end note')
            for m in pkg.modules[:6]:
                m_short = m.split(".")[-1]
                lines.append(f'  class "{m_short}" as {safe_id}_{m_short} <<module>>')
            lines.append("}")
            lines.append("")

        for dep in pkg_model.dependencies:
            src = f"pkg_{dep.source_package.replace('.', '_')}"
            tgt = f"pkg_{dep.target_package.replace('.', '_')}"
            cyc_marker = " [CIRCULAR]" if dep.is_cyclic else ""
            lines.append(f"{src} ..> {tgt} : imports ({dep.import_count}){cyc_marker}")

        lines.append("")
        lines.append("@enduml")
        return "\n".join(lines)

    @classmethod
    def generate_component_diagram(cls, static_model: StaticModelIR, title: Optional[str] = None) -> str:
        """Generate PlantUML component architecture diagram (.puml)."""
        comp_model = static_model.components
        lines = [
            "@startuml",
            "skinparam monochrome false",
            "skinparam shadowing false",
            "skinparam defaultFontName Arial",
            "skinparam componentStyle uml2",
        ]
        if title:
            lines.append(f"title {title}")
        elif static_model.project_name:
            lines.append(f"title Component Architecture: {static_model.project_name}")
        lines.append("")

        if not comp_model or not comp_model.components:
            lines.append("' No architectural components extracted")
            lines.append("@enduml")
            return "\n".join(lines)

        from collections import defaultdict
        tier_map = defaultdict(list)
        for comp in comp_model.components:
            tier_map[comp.tier].append(comp)

        for tier in comp_model.tiers:
            comps = tier_map.get(tier, [])
            if not comps:
                continue
            safe_tier = tier.replace(" / ", "_").replace(" & ", "_").replace(" ", "_")
            lines.append(f'package "{tier}" as tier_{safe_tier} {{')
            for c in comps:
                safe_id = c.id.replace(".", "_")
                st_clean = c.stereotype.replace("«", "").replace("»", "")
                f_cnt = getattr(c, "functions_count", 0)
                d_cnt = getattr(c, "dependencies_count", 0)
                role_txt = getattr(c, "role", "Service")
                lines.append(f'  [{c.name}\\n<size:10>«{st_clean}» · {role_txt}</size>\\n<size:9>{f_cnt} functions • {d_cnt} deps</size>] as {safe_id} <<{st_clean}>>')
                if c.provided_interfaces:
                    for iface in c.provided_interfaces[:2]:
                        iface_id = f"iface_{safe_id}_{iface}"
                        lines.append(f'  () "{iface}()" as {iface_id}')
                        lines.append(f'  {safe_id} -0- {iface_id}')
            lines.append("}")
            lines.append("")

        for conn in comp_model.connectors:
            src = conn.source_id.replace(".", "_")
            tgt = conn.target_id.replace(".", "_")
            label_str = f" : {conn.label}" if conn.label else " : uses"
            arrow = "-->" if getattr(conn, "relationship_style", "solid") == "solid" else "..>"
            lines.append(f"{src} {arrow} {tgt}{label_str}")

        lines.append("")
        lines.append("@enduml")
        return "\n".join(lines)
