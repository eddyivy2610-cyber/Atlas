"""Intermediate Representation (IR) models and schema for UMLdoc."""

from umldoc.ir.base import (
    ElementKind,
    MemberVisibility,
    RelationType,
    SourceLocation,
    ValueSnapshot,
    ExceptionSnapshot,
    VerificationStatus,
)
from umldoc.ir.static_model import (
    ParameterIR,
    AttributeIR,
    MethodIR,
    FunctionIR,
    ClassIR,
    RelationIR,
    ModuleIR,
    StaticModelIR,
)
from umldoc.ir.dynamic_model import (
    InteractionEventType,
    ParticipantIR,
    InteractionIR,
    TraceSessionIR,
    DynamicModelIR,
)
from umldoc.ir.verification import (
    DriftChangeType,
    ElementVerificationIR,
    VerificationSummaryIR,
    ElementDriftIR,
    DriftReportIR,
)
from umldoc.ir.schema import DocumentIR

__all__ = [
    # Base
    "ElementKind",
    "MemberVisibility",
    "RelationType",
    "SourceLocation",
    "ValueSnapshot",
    "ExceptionSnapshot",
    "VerificationStatus",
    # Static
    "ParameterIR",
    "AttributeIR",
    "MethodIR",
    "FunctionIR",
    "ClassIR",
    "RelationIR",
    "ModuleIR",
    "StaticModelIR",
    # Dynamic
    "InteractionEventType",
    "ParticipantIR",
    "InteractionIR",
    "TraceSessionIR",
    "DynamicModelIR",
    # Verification & Drift
    "DriftChangeType",
    "ElementVerificationIR",
    "VerificationSummaryIR",
    "ElementDriftIR",
    "DriftReportIR",
    # Document
    "DocumentIR",
]
