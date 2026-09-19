"""Base models, enums, and foundational types for the UMLdoc IR schema."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class MemberVisibility(str, Enum):
    """Visibility specifier for methods and attributes."""
    PUBLIC = "public"
    PROTECTED = "protected"
    PRIVATE = "private"


class RelationType(str, Enum):
    """Types of static architectural relationships between elements."""
    INHERITANCE = "inheritance"       # Extends / Subclasses (is-a)
    REALIZATION = "realization"       # Implements Protocol / Abstract Interface
    COMPOSITION = "composition"       # Strong lifecycle ownership (part-of)
    AGGREGATION = "aggregation"       # Weak collection / reference (has-a)
    ASSOCIATION = "association"       # Structural usage connection
    DEPENDENCY = "dependency"         # Ephemeral dependency (parameter / return type / import)


class ElementKind(str, Enum):
    """Classifier of architectural elements."""
    MODULE = "module"
    CLASS = "class"
    INTERFACE = "interface"
    PROTOCOL = "protocol"
    DATACLASS = "dataclass"
    ENUM = "enum"
    METHOD = "method"
    FUNCTION = "function"
    ATTRIBUTE = "attribute"
    RELATION = "relation"
    PARTICIPANT = "participant"
    INTERACTION = "interaction"


class VerificationStatus(str, Enum):
    """Status indicating fidelity of a diagram element against ground truth."""
    VERIFIED_GROUND_TRUTH = "verified_ground_truth"  # Found in AST/Trace, perfectly matches
    MATCH = "match"                                  # Diagram element matches code
    HALLUCINATED = "hallucinated"                    # In diagram/LLM output but NOT in code
    MISSING = "missing"                              # In code ground truth but omitted from diagram
    DRIFTED = "drifted"                              # Signature, types, or structure changed across commits
    STALE = "stale"                                  # Deprecated or reference obsolete target
    UNVERIFIED = "unverified"                        # Not yet evaluated by verifier


class SourceLocation(BaseModel):
    """Precise source code coordinates for an architectural symbol."""
    model_config = ConfigDict(frozen=True)

    file_path: str = Field(..., description="Relative or absolute file path to the source file")
    start_line: int = Field(..., ge=1, description="1-indexed starting line number")
    end_line: int = Field(..., ge=1, description="1-indexed ending line number")
    start_col: Optional[int] = Field(default=0, ge=0, description="0-indexed start column offset")
    end_col: Optional[int] = Field(default=None, ge=0, description="0-indexed end column offset")
    commit_hash: Optional[str] = Field(default=None, description="Git commit SHA at extraction time")
    content_hash: Optional[str] = Field(default=None, description="SHA-256 hash of the node source/ast")


class ValueSnapshot(BaseModel):
    """Lightweight representation of a runtime argument or return value."""
    model_config = ConfigDict(frozen=True)

    type_name: str = Field(..., description="Qualified or short type name")
    repr_value: str = Field(default="", description="String representation truncated to safe length")
    is_truncated: bool = Field(default=False, description="Whether repr was truncated for brevity")


class ExceptionSnapshot(BaseModel):
    """Snapshot of an exception raised during dynamic execution."""
    model_config = ConfigDict(frozen=True)

    type_name: str = Field(..., description="Exception class name (e.g. ValueError)")
    message: str = Field(default="", description="Exception error message")
    line_number: Optional[int] = Field(default=None, description="Line number where exception occurred")
