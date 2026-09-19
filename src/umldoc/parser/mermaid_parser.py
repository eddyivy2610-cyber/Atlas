"""Parser converting Mermaid markup into candidate StaticModelIR and TraceSessionIR."""

import re
from typing import Dict, List, Optional
from umldoc.ir.base import (
    ElementKind,
    MemberVisibility,
    RelationType,
    ValueSnapshot,
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


class MermaidParser:
    """Parses Mermaid.js class and sequence diagrams into candidate IR models."""

    @classmethod
    def parse_class_diagram(cls, mmd_text: str, project_name: str = "CandidateModel") -> StaticModelIR:
        """Parse Mermaid classDiagram text into candidate StaticModelIR."""
        classes: Dict[str, Dict] = {}
        relations: List[RelationIR] = []
        current_class: Optional[str] = None
        rel_counter = 0

        lines = mmd_text.splitlines()
        for line in lines:
            trimmed = line.strip()
            if not trimmed or trimmed.startswith("classDiagram") or trimmed.startswith("%%"):
                continue

            # Class header: class Name {
            cls_header = re.match(r'^class\s+(\w+)\s*\{?$', trimmed)
            if cls_header:
                cname = cls_header.group(1)
                current_class = cname
                if cname not in classes:
                    classes[cname] = {
                        "id": cname,
                        "name": cname,
                        "qualified_name": cname,
                        "kind": ElementKind.CLASS,
                        "bases": [],
                        "attributes": [],
                        "methods": [],
                        "is_abstract": False,
                        "is_protocol": False,
                        "is_dataclass": False,
                        "is_enum": False,
                    }
                continue

            if trimmed == "}" and current_class is not None:
                current_class = None
                continue

            # Class body: attributes and methods
            if current_class is not None:
                cdata = classes[current_class]

                # Stereotype: <<interface>>, <<dataclass>>, <<protocol>>, <<enum>>
                st_match = re.match(r'^<<(\w+)>>$', trimmed)
                if st_match:
                    st = st_match.group(1).lower()
                    if "interface" in st:
                        cdata["kind"] = ElementKind.INTERFACE
                        cdata["is_abstract"] = True
                    elif "dataclass" in st:
                        cdata["kind"] = ElementKind.DATACLASS
                        cdata["is_dataclass"] = True
                    elif "protocol" in st:
                        cdata["kind"] = ElementKind.PROTOCOL
                        cdata["is_protocol"] = True
                    elif "enum" in st:
                        cdata["kind"] = ElementKind.ENUM
                        cdata["is_enum"] = True
                    continue

                # Method: [+|-|#]? name(params) ret
                m_match = re.match(r'^([\+\-#])?\s*(\w+)\s*\((.*?)\)(?:\s*(.+))?$', trimmed)
                if m_match:
                    vis_sym, m_name, params_str, ret_str = m_match.groups()
                    vis = MemberVisibility.PUBLIC
                    if vis_sym == "-":
                        vis = MemberVisibility.PRIVATE
                    elif vis_sym == "#":
                        vis = MemberVisibility.PROTECTED

                    params = [
                        ParameterIR(name=p.strip()) for p in params_str.split(",") if p.strip()
                    ]
                    cdata["methods"].append(
                        MethodIR(
                            id=f"{current_class}.{m_name}",
                            name=m_name,
                            parameters=params,
                            return_type=ret_str.strip() if ret_str else None,
                            visibility=vis,
                        )
                    )
                    continue

                # Attribute: [+|-|#]? type name
                a_match = re.match(r'^([\+\-#])?\s*(?:([\w\[\],\s\.]+)\s+)?(\w+)$', trimmed)
                if a_match:
                    vis_sym, a_type, a_name = a_match.groups()
                    vis = MemberVisibility.PUBLIC
                    if vis_sym == "-":
                        vis = MemberVisibility.PRIVATE
                    elif vis_sym == "#":
                        vis = MemberVisibility.PROTECTED

                    cdata["attributes"].append(
                        AttributeIR(
                            id=f"{current_class}.{a_name}",
                            name=a_name,
                            type_annotation=a_type.strip() if a_type else None,
                            visibility=vis,
                        )
                    )
                    continue

            # Relations: A <|-- B, A <|.. B, A *-- B, A o-- B, A --> B, A ..> B
            rel_match = re.match(r'^([\w\.]+)\s*(<\|--|<\|\.\.|\*--|o--|-->|\.\.>)\s*([\w\.]+)(?:\s*:\s*(.+))?$', trimmed)
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
                elif arrow == "*--":
                    rel_type = RelationType.COMPOSITION
                elif arrow == "o--":
                    rel_type = RelationType.AGGREGATION
                elif arrow == "..>":
                    rel_type = RelationType.DEPENDENCY

                relations.append(
                    RelationIR(
                        id=f"mmd_rel_{rel_counter}",
                        source_id=src,
                        target_id=tgt,
                        relation_type=rel_type,
                        label=label.strip() if label else None,
                    )
                )

        class_objects = [
            ClassIR(
                id=c["id"],
                name=c["name"],
                qualified_name=c["qualified_name"],
                kind=c["kind"],
                bases=c["bases"],
                attributes=c["attributes"],
                methods=c["methods"],
                is_abstract=c["is_abstract"],
                is_protocol=c["is_protocol"],
                is_dataclass=c["is_dataclass"],
                is_enum=c["is_enum"],
            )
            for c in classes.values()
        ]

        return StaticModelIR(
            project_name=project_name,
            classes=class_objects,
            relations=relations,
            metadata={"source_format": "Mermaid"},
        )

    @classmethod
    def parse_sequence_diagram(cls, mmd_text: str, scenario_name: str = "CandidateSequence") -> TraceSessionIR:
        """Parse Mermaid sequenceDiagram text into TraceSessionIR."""
        participants: Dict[str, ParticipantIR] = {}
        interactions: List[InteractionIR] = []
        seq_counter = 0

        lines = mmd_text.splitlines()
        for line in lines:
            trimmed = line.strip()
            if not trimmed or trimmed.startswith("sequenceDiagram") or trimmed.startswith("autonumber") or trimmed.startswith("%%"):
                continue

            # participant id as "Name"
            part_match = re.match(r'^participant\s+(\w+)(?:\s+as\s+"([^"]+)")?$', trimmed)
            if part_match:
                p_id = part_match.group(1)
                disp = part_match.group(2) or p_id
                cls_name = disp.split(":")[-1].strip() if ":" in disp else None
                participants[p_id] = ParticipantIR(id=p_id, name=disp, class_name=cls_name)
                continue

            # Call: caller->>+callee: method(args)
            call_match = re.match(r'^(\w+)->>\+?(\w+):\s*(\w+)\((.*?)\)$', trimmed)
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
                        event_id=f"mmd_evt_{seq_counter}",
                        event_type=InteractionEventType.CALL,
                        caller_id=caller,
                        callee_id=callee,
                        method_name=m_name,
                        arguments=args_dict,
                        sequence_order=seq_counter,
                    )
                )
                continue

            # Return: caller-->>-callee: return val
            ret_match = re.match(r'^(\w+)-->>-?(\w+):\s*return\s*(.*)$', trimmed)
            if ret_match:
                caller, callee, ret_val = ret_match.groups()
                seq_counter += 1
                interactions.append(
                    InteractionIR(
                        event_id=f"mmd_ret_{seq_counter}",
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
            session_id="mmd_parsed_session",
            scenario_name=scenario_name,
            entrypoint="parsed_entrypoint",
            participants=list(participants.values()),
            interactions=interactions,
        )
