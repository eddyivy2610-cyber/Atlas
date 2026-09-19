"""Diagram distillation engine transforming verbose raw ground truth into readable architectural views."""

import json
from typing import Dict, List, Optional, Set
from umldoc.ir.base import MemberVisibility
from umldoc.ir.static_model import ClassIR, MethodIR, RelationIR, StaticModelIR
from umldoc.ir.dynamic_model import InteractionEventType, InteractionIR, ParticipantIR, TraceSessionIR
from umldoc.readability.prompts import (
    CLASS_DISTILLATION_PROMPT_TEMPLATE,
    RAW_CODE_DISTILLATION_PROMPT_TEMPLATE,
    RAW_CODE_SYSTEM_PROMPT_CLASS_DIAGRAM,
    SEQUENCE_DISTILLATION_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_CLASS_DIAGRAM,
    SYSTEM_PROMPT_SEQUENCE_DIAGRAM,
)


class DiagramDistiller:
    """Distills raw static and dynamic ground truth into human-readable architecture views."""

    @classmethod
    def distill_static_model(
        cls,
        static_model: StaticModelIR,
        focus_classes: Optional[Set[str]] = None,
        public_only: bool = True,
        max_methods_per_class: int = 8,
        include_abstract_only: bool = False,
    ) -> StaticModelIR:
        """Filter and simplify a StaticModelIR for architectural readability."""
        filtered_classes: List[ClassIR] = []
        selected_class_ids: Set[str] = set()

        for c in static_model.classes:
            if focus_classes and c.name not in focus_classes and c.id not in focus_classes:
                continue
            if include_abstract_only and not c.is_abstract and not c.is_protocol:
                continue

            # Filter attributes
            attrs = [
                a for a in c.attributes
                if not (public_only and a.visibility != MemberVisibility.PUBLIC)
            ]

            # Filter methods
            methods = [
                m for m in c.methods
                if not (public_only and m.visibility != MemberVisibility.PUBLIC)
                and not (m.name.startswith("__") and not m.name.endswith("__"))
            ]
            if len(methods) > max_methods_per_class:
                methods = methods[:max_methods_per_class]

            simplified_cls = ClassIR(
                id=c.id,
                name=c.name,
                qualified_name=c.qualified_name,
                kind=c.kind,
                bases=c.bases,
                is_abstract=c.is_abstract,
                is_protocol=c.is_protocol,
                is_dataclass=c.is_dataclass,
                is_enum=c.is_enum,
                docstring=c.docstring,
                attributes=attrs,
                methods=methods,
                source_location=c.source_location,
            )
            filtered_classes.append(simplified_cls)
            selected_class_ids.add(c.id)
            selected_class_ids.add(c.name)

        # Filter relationships to only connect retained classes
        filtered_relations: List[RelationIR] = []
        for r in static_model.relations:
            src_name = r.source_id.split(".")[-1]
            tgt_name = r.target_id.split(".")[-1]
            if (r.source_id in selected_class_ids or src_name in selected_class_ids) and (
                r.target_id in selected_class_ids or tgt_name in selected_class_ids
            ):
                filtered_relations.append(r)

        return StaticModelIR(
            project_name=static_model.project_name,
            classes=filtered_classes,
            relations=filtered_relations,
            metadata={"distilled": "true", "original_classes_count": str(len(static_model.classes))},
        )

    @classmethod
    def distill_trace_session(
        cls,
        session: TraceSessionIR,
        max_events: int = 25,
        min_depth: int = 0,
        max_depth: int = 3,
        keep_exceptions: bool = True,
    ) -> TraceSessionIR:
        """Filter noisy or deep call stacks in a TraceSessionIR into a concise sequence."""
        filtered_interactions: List[InteractionIR] = []
        active_participants: Set[str] = set()

        for evt in session.interactions:
            # Always retain exceptions
            if keep_exceptions and evt.event_type == InteractionEventType.EXCEPTION:
                filtered_interactions.append(evt)
                active_participants.add(evt.caller_id)
                active_participants.add(evt.callee_id)
                continue

            # Depth filter
            if not (min_depth <= evt.call_depth <= max_depth):
                continue

            filtered_interactions.append(evt)
            active_participants.add(evt.caller_id)
            active_participants.add(evt.callee_id)

            if len(filtered_interactions) >= max_events:
                break

        retained_participants = [
            p for p in session.participants if p.id in active_participants or p.name in active_participants
        ]

        return TraceSessionIR(
            session_id=f"distilled_{session.session_id}",
            scenario_name=session.scenario_name,
            entrypoint=session.entrypoint,
            duration_ms=session.duration_ms,
            participants=retained_participants,
            interactions=filtered_interactions,
            metadata={"distilled": "true", "original_events": str(len(session.interactions))},
        )

    @classmethod
    def format_class_prompt(
        cls,
        static_model: StaticModelIR,
        focus_area: str = "Core Domain Architecture",
        diagram_format: str = "PlantUML",
    ) -> Dict[str, str]:
        """Format an LLM prompt with ground truth context for class diagram generation."""
        classes_summary = [
            {
                "name": c.name,
                "kind": c.kind.value,
                "bases": c.bases,
                "methods": [f"{m.name}({', '.join(p.name for p in m.parameters)}) -> {m.return_type}" for m in c.methods],
                "attributes": [f"{a.name}: {a.type_annotation}" for a in c.attributes],
            }
            for c in static_model.classes
        ]

        relations_summary = [
            {"from": r.source_id.split(".")[-1], "to": r.target_id.split(".")[-1], "type": r.relation_type.value, "label": r.label}
            for r in static_model.relations
        ]

        user_prompt = CLASS_DISTILLATION_PROMPT_TEMPLATE.format(
            diagram_format=diagram_format,
            project_name=static_model.project_name,
            focus_area=focus_area,
            ground_truth_classes_json=json.dumps(classes_summary, indent=2),
            ground_truth_relations_json=json.dumps(relations_summary, indent=2),
        )

        return {
            "system_prompt": SYSTEM_PROMPT_CLASS_DIAGRAM,
            "user_prompt": user_prompt,
        }

    @classmethod
    def format_sequence_prompt(
        cls,
        session: TraceSessionIR,
        workflow_goal: str = "Demonstrate primary request lifecycle",
        diagram_format: str = "PlantUML",
    ) -> Dict[str, str]:
        """Format an LLM prompt with trace ground truth context for sequence diagram generation."""
        participants_data = [{"id": p.id, "name": p.name} for p in session.participants]
        events_data = [
            {
                "type": e.event_type.value,
                "caller": e.caller_id,
                "callee": e.callee_id,
                "method": e.method_name,
                "args": {k: v.repr_value for k, v in e.arguments.items()},
                "return": e.return_value.repr_value if e.return_value else None,
            }
            for e in session.interactions
        ]

        user_prompt = SEQUENCE_DISTILLATION_PROMPT_TEMPLATE.format(
            diagram_format=diagram_format,
            scenario_name=session.scenario_name,
            workflow_goal=workflow_goal,
            participants_json=json.dumps(participants_data, indent=2),
            events_summary_json=json.dumps(events_data, indent=2),
        )

        return {
            "system_prompt": SYSTEM_PROMPT_SEQUENCE_DIAGRAM,
            "user_prompt": user_prompt,
        }

    @classmethod
    def format_raw_code_prompt(
        cls,
        source_files: Dict[str, str],
        project_name: str,
        focus_area: str = "Core Domain Architecture",
        diagram_format: str = "PlantUML",
    ) -> Dict[str, str]:
        """Format an LLM prompt with raw Python source files and zero pre-extracted AST scaffolding."""
        blocks = []
        for file_name, file_content in sorted(source_files.items()):
            blocks.append(f"--- File: {file_name} ---\n{file_content}\n")

        raw_content = "\n".join(blocks)
        user_prompt = RAW_CODE_DISTILLATION_PROMPT_TEMPLATE.format(
            diagram_format=diagram_format,
            project_name=project_name,
            focus_area=focus_area,
            raw_source_files_content=raw_content,
        )

        return {
            "system_prompt": RAW_CODE_SYSTEM_PROMPT_CLASS_DIAGRAM,
            "user_prompt": user_prompt,
        }

