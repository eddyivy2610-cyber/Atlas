"""Verification and drift detection models for diagram fidelity and evolution analysis."""

from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, ConfigDict, Field
from umldoc.ir.base import ElementKind, VerificationStatus


class DriftChangeType(str, Enum):
    """Classification of code/diagram divergence between revisions."""
    ADDED = "added"                          # Present in new commit, absent in base
    REMOVED = "removed"                      # Removed in new commit
    MODIFIED_SIGNATURE = "modified_signature"# Parameters, return types, or decorators altered
    MODIFIED_TYPE = "modified_type"          # Attribute or field type annotation changed
    MODIFIED_RELATION = "modified_relation"  # Inheritance or association target changed
    MODIFIED_BODY = "modified_body"          # Implementation changed (hash changed, signature same)
    RENAMED = "renamed"                      # Element renamed


class ElementVerificationIR(BaseModel):
    """Detailed verification record for a single diagram element."""
    model_config = ConfigDict(frozen=True)

    element_id: str = Field(..., description="Element identifier (class, method, or relation ID)")
    element_name: str = Field(..., description="Display name of the element")
    element_kind: ElementKind = Field(..., description="Kind of element being verified")
    status: VerificationStatus = Field(..., description="Verification verdict")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Verification confidence (0.0 to 1.0)")
    ground_truth_ref: Optional[str] = Field(default=None, description="Reference location in AST or trace")
    evidence: str = Field(default="", description="Detailed rationale and extracted evidence")
    issues: List[str] = Field(default_factory=list, description="Specific discrepancies found if any")


class VerificationSummaryIR(BaseModel):
    """Aggregated verification metrics across all diagram components."""
    model_config = ConfigDict(frozen=True)

    total_elements: int = Field(default=0, ge=0, description="Total diagram elements verified")
    verified_count: int = Field(default=0, ge=0, description="Count of fully verified ground-truth elements")
    hallucinated_count: int = Field(default=0, ge=0, description="Count of hallucinated/unbacked elements")
    missing_count: int = Field(default=0, ge=0, description="Count of ground truth elements omitted")
    drifted_count: int = Field(default=0, ge=0, description="Count of elements with drifted signatures/behavior")
    overall_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Overall fidelity score (0.0-1.0)")
    verifications: List[ElementVerificationIR] = Field(default_factory=list, description="Per-element records")


class ElementDriftIR(BaseModel):
    """Drift record for an element across two commit snapshots."""
    model_config = ConfigDict(frozen=True)

    element_id: str = Field(..., description="Unique element ID")
    element_name: str = Field(..., description="Element display name")
    element_kind: ElementKind = Field(..., description="Element kind")
    change_type: DriftChangeType = Field(..., description="Type of structural or semantic drift")
    base_snapshot: Optional[str] = Field(default=None, description="Representation in base commit")
    target_snapshot: Optional[str] = Field(default=None, description="Representation in target commit")
    diff_description: str = Field(..., description="Human-readable description of what drifted")
    is_breaking: bool = Field(default=False, description="True if change breaks public API contract")


class DriftReportIR(BaseModel):
    """Complete drift comparison report between two codebase versions."""
    model_config = ConfigDict(frozen=True)

    project_name: str = Field(..., description="Project name")
    base_commit: str = Field(..., description="Base commit SHA or tag")
    target_commit: str = Field(..., description="Target commit SHA or tag")
    drifted_elements: List[ElementDriftIR] = Field(default_factory=list, description="List of detected drifts")
    breaking_changes_count: int = Field(default=0, ge=0, description="Count of breaking API drifts")
    total_drift_count: int = Field(default=0, ge=0, description="Total number of drifted elements")
    summary_notes: Optional[str] = Field(default=None, description="High-level drift summary")
