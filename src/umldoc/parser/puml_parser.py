"""Parser converting PlantUML text into candidate StaticModelIR and TraceSessionIR."""

import re
from typing import List, Optional, Dict
from umldoc.ir.base import (
    ElementKind,
    MemberVisibility,
    RelationType,
    ValueSnapshot,
    ExceptionSnapshot,
)
from umldoc.ir.static_model import (
    AttributeIR,
    ClassIR,
    MethodIR,
    ParameterIR,
    RelationIR,
    StaticModelIR,
)
from umldoc.ir.dynamic_model import (
    InteractionEventType,
    InteractionIR,
    ParticipantIR,
    TraceSessionIR,
)


class PlantUMLParser:
    """Parses PlantUML class and sequence diagrams into candidate IR structures."""

    @classmethod
    def parse_class_diagram(cls, puml_text: str, project_name: str = "CandidateModel") -> StaticModelIR:
        """Parse PlantUML class diagram text into a candidate StaticModelIR."""
        classes: List[ClassIR] = []
        relations: List[RelationIR] = []
        current_class: Optional[Dict] = None
        rel_counter = 0

        lines = puml_text.splitlines()
        for line in lines:
            trimmed = line.strip()
            if not trimmed or trimmed.startswith("@startuml") or trimmed.startswith("@enduml") or trimmed.startswith("skinparam") or trimmed.startswith("set namespaceSeparator") or trimmed.startswith("title") or trimmed.startswith("shadowing") or trimmed.startswith("package "):
                continue

            # Class header: class "Name" as alias <<stereotype>> extends Base { or class Name extends Base {
            cls_match = re.match(r'^(?:abstract\s+class|class|interface|enum)\s+(?:"([^"]+)"|(\w+))(?:\s+as\s+([\w\.]+))?(?:\s+<<(\w+)>>)?(?:\s+(?:extends|implements)\s+([\w\.]+))?\s*\{?$', trimmed)
            if cls_match:
                name = cls_match.group(1) or cls_match.group(2)
                alias = cls_match.group(3) or name
                stereotype = (cls_match.group(4) or "").lower()
                base_cls = cls_match.group(5)

                kind = ElementKind.CLASS
                if "interface" in stereotype:
                    kind = ElementKind.INTERFACE
                elif "protocol" in stereotype:
                    kind = ElementKind.PROTOCOL
                elif "dataclass" in stereotype:
                    kind = ElementKind.DATACLASS
                elif "enum" in stereotype:
                    kind = ElementKind.ENUM

                current_class = {
                    "id": alias,
                    "name": name,
                    "qualified_name": alias,
                    "kind": kind,
                    "bases": [],
                    "attributes": [],
                    "methods": [],
                    "is_abstract": "interface" in stereotype or "abstract" in trimmed,
                    "is_protocol": "protocol" in stereotype,
                    "is_dataclass": "dataclass" in stereotype,
                    "is_enum": "enum" in stereotype,
                }
                continue

            if trimmed == "}" and current_class is not None:
                classes.append(
                    ClassIR(
                        id=current_class["id"],
                        name=current_class["name"],
                        qualified_name=current_class["qualified_name"],
                        kind=current_class["kind"],
                        bases=current_class["bases"],
                        attributes=current_class["attributes"],
                        methods=current_class["methods"],
                        is_abstract=current_class["is_abstract"],
                        is_protocol=current_class["is_protocol"],
                        is_dataclass=current_class["is_dataclass"],
                        is_enum=current_class["is_enum"],
                    )
                )
                current_class = None
                continue

            # Class body: attributes and methods
            if current_class is not None:
                if trimmed == "__":
                    continue

                # Method: [+|-|#]? {modifier}? name(params) : return_type
                method_match = re.match(r'^([\+\-#])?\s*(?:\{(\w+)\}\s*)?(\w+)\s*\((.*?)\)(?:\s*(?:->|:)\s*(.*))?$', trimmed)
                if method_match:
                    vis_sym, modifier, m_name, params_str, ret_str = method_match.groups()
                    vis = MemberVisibility.PUBLIC
                    if vis_sym == "-":
                        vis = MemberVisibility.PRIVATE
                    elif vis_sym == "#":
                        vis = MemberVisibility.PROTECTED

                    params = cls._parse_parameters(params_str)
                    current_class["methods"].append(
                        MethodIR(
                            id=f"{current_class['id']}.{m_name}",
                            name=m_name,
                            parameters=params,
                            return_type=ret_str.strip() if ret_str else None,
                            visibility=vis,
                            is_static=modifier == "static",
                            is_abstract=modifier == "abstract",
                        )
                    )
                    continue

                # Attribute: [+|-|#]? {modifier}? name : type = default
                attr_match = re.match(r'^([\+\-#])?\s*(?:\{(\w+)\}\s*)?(\w+)(?:\s*:\s*([^=]+))?(?:\s*=\s*(.+))?$', trimmed)
                if attr_match:
                    vis_sym, modifier, a_name, a_type, a_def = attr_match.groups()
                    vis = MemberVisibility.PUBLIC
                    if vis_sym == "-":
                        vis = MemberVisibility.PRIVATE
                    elif vis_sym == "#":
                        vis = MemberVisibility.PROTECTED

                    current_class["attributes"].append(
                        AttributeIR(
                            id=f"{current_class['id']}.{a_name}",
                            name=a_name,
                            type_annotation=a_type.strip() if a_type else None,
                            default_value=a_def.strip() if a_def else None,
                            visibility=vis,
                            is_class_variable=modifier == "static",
                        )
                    )
                    continue

            # Relationships: A <|-- B, A <|.. B, A *-- B, A o-- B, A --> B, A ..> B
            rel_match = re.match(r'^([\w\.]+)\s*(<\|--|<\|\.\.|\*--|o--|-->|\.\.>|--\|>|--o|--\*)\s*([\w\.]+)(?:\s*:\s*(.+))?$', trimmed)
            if rel_match:
                left, arrow, right, label = rel_match.groups()
                rel_counter += 1

                rel_type = RelationType.ASSOCIATION
                src = left
                tgt = right

                if arrow in ("<|--", "<|.."):
                    rel_type = RelationType.INHERITANCE if arrow == "<|--" else RelationType.REALIZATION
                    src = right
                    tgt = left
                elif arrow == "--|>":
                    rel_type = RelationType.INHERITANCE
                    src = left
                    tgt = right
                elif arrow in ("*--", "--*"):
                    rel_type = RelationType.COMPOSITION
                elif arrow in ("o--", "--o"):
                    rel_type = RelationType.AGGREGATION
                elif arrow == "..>":
                    rel_type = RelationType.DEPENDENCY

                relations.append(
                    RelationIR(
                        id=f"puml_rel_{rel_counter}",
                        source_id=src,
                        target_id=tgt,
                        relation_type=rel_type,
                        label=label.strip() if label else None,
                    )
                )

        return StaticModelIR(
            project_name=project_name,
            classes=classes,
            relations=relations,
            metadata={"source_format": "PlantUML"},
        )

    @classmethod
    def parse_sequence_diagram(cls, puml_text: str, scenario_name: str = "CandidateSequence") -> TraceSessionIR:
        """Parse PlantUML sequence diagram text into TraceSessionIR."""
        participants: Dict[str, ParticipantIR] = {}
        interactions: List[InteractionIR] = []
        seq_counter = 0

        lines = puml_text.splitlines()
        for line in lines:
            trimmed = line.strip()
            if not trimmed or trimmed.startswith("@") or trimmed.startswith("skinparam") or trimmed.startswith("autonumber") or trimmed.startswith("title"):
                continue

            # Participant declaration: participant "Display Name" as alias
            part_match = re.match(r'^participant\s+(?:"([^"]+)"|(\w+))(?:\s+as\s+(\w+))?$', trimmed)
            if part_match:
                disp = part_match.group(1) or part_match.group(2)
                p_id = part_match.group(3) or disp
                cls_name = disp.split(":")[-1].strip() if ":" in disp else None
                participants[p_id] = ParticipantIR(id=p_id, name=disp, class_name=cls_name)
                continue

            # Call interaction: caller -> callee : method(args)
            call_match = re.match(r'^(\w+)\s*->\s*(\w+)\s*:\s*(\w+)\((.*?)\)$', trimmed)
            if call_match:
                caller, callee, m_name, args_str = call_match.groups()
                seq_counter += 1
                if caller not in participants:
                    participants[caller] = ParticipantIR(id=caller, name=caller)
                if callee not in participants:
                    participants[callee] = ParticipantIR(id=callee, name=callee)

                args_dict = {}
                if args_str.strip():
                    for pair in args_str.split(","):
                        if "=" in pair:
                            k, v = pair.split("=", 1)
                            args_dict[k.strip()] = ValueSnapshot(type_name="str", repr_value=v.strip())

                interactions.append(
                    InteractionIR(
                        event_id=f"puml_evt_{seq_counter}",
                        event_type=InteractionEventType.CALL,
                        caller_id=caller,
                        callee_id=callee,
                        method_name=m_name,
                        arguments=args_dict,
                        sequence_order=seq_counter,
                    )
                )
                continue

            # Return interaction: caller --> callee : return val
            ret_match = re.match(r'^(\w+)\s*-->\s*(\w+)\s*:\s*return\s*(.*)$', trimmed)
            if ret_match:
                caller, callee, ret_val = ret_match.groups()
                seq_counter += 1
                interactions.append(
                    InteractionIR(
                        event_id=f"puml_ret_{seq_counter}",
                        event_type=InteractionEventType.RETURN,
                        caller_id=caller,
                        callee_id=callee,
                        method_name="return",
                        return_value=ValueSnapshot(type_name="Any", repr_value=ret_val.strip()),
                        sequence_order=seq_counter,
                    )
                )
                continue

        return TraceSessionIR(
            session_id="puml_parsed_session",
            scenario_name=scenario_name,
            entrypoint="parsed_entrypoint",
            participants=list(participants.values()),
            interactions=interactions,
        )

    @classmethod
    def _parse_parameters(cls, params_str: str) -> List[ParameterIR]:
        params = []
        if not params_str.strip():
            return params
        for item in params_str.split(","):
            p_trim = item.strip()
            if not p_trim:
                continue
            p_name = p_trim
            p_type = None
            if ":" in p_trim:
                parts = p_trim.split(":", 1)
                p_name = parts[0].strip()
                p_type = parts[1].strip()
            params.append(ParameterIR(name=p_name, type_annotation=p_type))
        return params
