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
