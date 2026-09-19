"""LLM readability and diagram distillation layer for UMLdoc."""

from umldoc.readability.distiller import DiagramDistiller
from umldoc.readability.prompts import (
    CLASS_DISTILLATION_PROMPT_TEMPLATE,
    SEQUENCE_DISTILLATION_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_CLASS_DIAGRAM,
    SYSTEM_PROMPT_SEQUENCE_DIAGRAM,
)

__all__ = [
    "DiagramDistiller",
    "SYSTEM_PROMPT_CLASS_DIAGRAM",
    "SYSTEM_PROMPT_SEQUENCE_DIAGRAM",
    "CLASS_DISTILLATION_PROMPT_TEMPLATE",
    "SEQUENCE_DISTILLATION_PROMPT_TEMPLATE",
]
