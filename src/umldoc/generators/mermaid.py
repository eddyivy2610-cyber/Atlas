"""Mermaid diagram generator from Static and Dynamic IR."""

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


class MermaidGenerator:
    """Generates valid Mermaid.js (.mmd) markup for class and sequence diagrams."""

    @classmethod
    def generate_class_diagram(cls, static_model: StaticModelIR, title: Optional[str] = None) -> str:
        """Generate Mermaid class diagram string from StaticModelIR."""
        lines = ["classDiagram"]
        if title:
            lines.append(f"    %% Title: {title}")

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
                lines.append(f"    {tgt} <|-- {src}{label_str}")
            elif rel.relation_type == RelationType.REALIZATION:
                lines.append(f"    {tgt} <|.. {src}{label_str}")
            elif rel.relation_type == RelationType.COMPOSITION:
                lines.append(f"    {src} *-- {tgt}{label_str}")
            elif rel.relation_type == RelationType.AGGREGATION:
                lines.append(f"    {src} o-- {tgt}{label_str}")
            elif rel.relation_type == RelationType.ASSOCIATION:
                lines.append(f"    {src} --> {tgt}{label_str}")
            elif rel.relation_type == RelationType.DEPENDENCY:
                lines.append(f"    {src} ..> {tgt}{label_str}")

        return "\n".join(lines)

    @classmethod
    def _render_class(cls, class_ir: ClassIR) -> list[str]:
        lines = []
        safe_name = class_ir.name.replace(".", "_")
        lines.append(f"    class {safe_name} {{")

        if class_ir.kind == ElementKind.MODULE:
            lines.append("        <<module>>")
        elif class_ir.kind == ElementKind.INTERFACE or class_ir.is_abstract:
            lines.append("        <<interface>>")
        elif class_ir.kind == ElementKind.PROTOCOL or class_ir.is_protocol:
            lines.append("        <<protocol>>")
        elif class_ir.kind == ElementKind.DATACLASS or class_ir.is_dataclass:
            lines.append("        <<dataclass>>")
        elif class_ir.kind == ElementKind.ENUM or class_ir.is_enum:
            lines.append("        <<enum>>")

        # Attributes
        for attr in class_ir.attributes:
            vis = _visibility_symbol(attr.visibility)
            type_str = f"{attr.type_annotation} " if attr.type_annotation else ""
            lines.append(f"        {vis}{type_str}{attr.name}")

        # Methods
        for method in class_ir.methods:
            vis = _visibility_symbol(method.visibility)
            param_strs = [p.name for p in method.parameters]
            param_joined = ", ".join(param_strs)
            ret_str = f" {method.return_type}" if method.return_type else ""
            lines.append(f"        {vis}{method.name}({param_joined}){ret_str}")

        lines.append("    }")
        return lines

    @classmethod
    def generate_sequence_diagram(cls, session: TraceSessionIR) -> str:
        """Generate Mermaid sequence diagram string from TraceSessionIR."""
        lines = [
            "sequenceDiagram",
            "    autonumber",
        ]

        # Declare participants
        for p in session.participants:
            lines.append(f'    participant {p.id} as "{p.name}"')

        lines.append("")

        for evt in session.interactions:
            caller = evt.caller_id
            callee = evt.callee_id

            if evt.event_type == InteractionEventType.CALL:
                arg_list = []
                for k, v in evt.arguments.items():
                    clean_val = v.repr_value.replace('"', "'")
                    arg_list.append(f"{k}={clean_val}")
                arg_str = ", ".join(arg_list)
                lines.append(f"    {caller}->>+{callee}: {evt.method_name}({arg_str})")

            elif evt.event_type == InteractionEventType.RETURN:
                ret_val = evt.return_value.repr_value.replace('"', "'") if evt.return_value else "None"
                lines.append(f"    {caller}-->>-{callee}: return {ret_val}")

            elif evt.event_type == InteractionEventType.EXCEPTION:
                exc_type = evt.exception.type_name if evt.exception else "Exception"
                lines.append(f"    {caller}--x-{callee}: raise {exc_type}")

        return "\n".join(lines)
