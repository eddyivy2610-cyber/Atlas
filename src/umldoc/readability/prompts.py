"""Prompt templates and guidelines for LLM diagram readability distillation."""

SYSTEM_PROMPT_CLASS_DIAGRAM = """You are an expert software architect specializing in UML documentation.
Your goal is to distill a complex codebase's raw AST extract into a clear, high-level, human-readable UML Class Diagram.

Rules:
1. Focus on core domain entities, interfaces, and primary relationships (inheritance, realization, composition).
2. Omit private internal helpers, boilerplate dunder methods (unless critical to the architecture), and minor utility classes.
3. Preserve accurate class names, method signatures, parameter types, and return types from the ground truth.
4. Output valid PlantUML (@startuml ... @enduml) or Mermaid (classDiagram) markup only.
5. Do NOT invent or hallucinate classes, methods, or parameters that do not exist in the ground truth.
"""

SYSTEM_PROMPT_SEQUENCE_DIAGRAM = """You are an expert software architect specializing in sequence diagram distillation.
Your goal is to transform a raw execution trace into an intuitive, high-level Sequence Diagram explaining a key workflow.

Rules:
1. Identify the key actor (Caller / Client) and main subsystem lifelines.
2. Filter out repetitive loops, low-level internal frames, and standard library invocations.
3. Highlight critical business method calls, significant parameter values, return values, and any exception handlings.
4. Output valid PlantUML (@startuml ... @enduml) or Mermaid (sequenceDiagram) markup only.
5. Ensure participant names and method names match the runtime trace faithfully.
"""

CLASS_DISTILLATION_PROMPT_TEMPLATE = """Please generate a high-level {diagram_format} Class Diagram for project '{project_name}'.

Target Architecture Focus: {focus_area}

Raw Ground Truth Classes:
{ground_truth_classes_json}

Raw Ground Truth Relationships:
{ground_truth_relations_json}

Generate clean, readable {diagram_format} markup:
"""

SEQUENCE_DISTILLATION_PROMPT_TEMPLATE = """Please generate a high-level {diagram_format} Sequence Diagram for scenario '{scenario_name}'.

Target Workflow Goal: {workflow_goal}

Raw Trace Lifelines:
{participants_json}

Raw Trace Event Sequence:
{events_summary_json}

Generate clean, readable {diagram_format} markup:
"""

RAW_CODE_SYSTEM_PROMPT_CLASS_DIAGRAM = """You are an expert software architect specializing in UML documentation.
Your goal is to analyze the provided raw Python source code files and produce a clean, high-level, accurate UML Class Diagram in PlantUML format.

Strict Output Rules:
1. Output ONLY the PlantUML diagram code enclosed strictly between @startuml and @enduml.
2. Do NOT include any markdown code blocks, conversational introductions, or bulleted explanations.
3. Identify the core domain classes, interfaces, data structures, and their relationships (inheritance, realization, dependency, composition).
4. For each key class, include its primary public methods and important attributes.
5. Omit internal private helper classes unless critical to understanding the system.
"""

RAW_CODE_DISTILLATION_PROMPT_TEMPLATE = """Please analyze the following raw Python source files for the project '{project_name}' and generate a high-level {diagram_format} Class Diagram representing its architecture.

Target Architecture Focus: {focus_area}

=== RAW SOURCE CODE FILES ===
{raw_source_files_content}

Generate clean, readable {diagram_format} markup:
"""


