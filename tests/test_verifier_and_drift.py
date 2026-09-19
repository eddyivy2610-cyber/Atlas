"""Unit tests for DiagramVerifier and DriftAnalyzer."""

from pathlib import Path
from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.ir.base import ElementKind, MemberVisibility, VerificationStatus
from umldoc.ir.static_model import (
    AttributeIR,
    ClassIR,
    MethodIR,
    ParameterIR,
    StaticModelIR,
)
from umldoc.ir.verification import DriftChangeType
from umldoc.verifier.comparator import DiagramVerifier
from umldoc.verifier.drift import DriftAnalyzer


def test_diagram_verifier_matching_and_hallucination():
    """Test DiagramVerifier detecting verified ground truth vs hallucinated classes."""
    sample_dir = Path(__file__).parent / "sample_codebase"
    extractor = ASTStaticExtractor(project_name="SampleTest", root_path=str(sample_dir))
    ground_truth = extractor.extract_directory(target_dir=str(sample_dir))

    verifier = DiagramVerifier(ground_truth=ground_truth)

    # Candidate with 1 legitimate class, 1 hallucinated class, and omitting others
    candidate = StaticModelIR(
        project_name="CandidateModel",
        classes=[
            ClassIR(
                id="tests.sample_codebase.models.UserProfile",
                name="UserProfile",
                qualified_name="tests.sample_codebase.models.UserProfile",
                kind=ElementKind.DATACLASS,
                methods=[],
            ),
            ClassIR(
                id="fake.FakePaymentGateway",
                name="FakePaymentGateway",
                qualified_name="fake.FakePaymentGateway",
                kind=ElementKind.CLASS,
                methods=[],
            ),
        ],
    )

    summary = verifier.verify_candidate_model(candidate)
    assert summary.total_elements > 0
    assert summary.verified_count >= 1
    assert summary.hallucinated_count >= 1
    assert summary.missing_count >= 1
    assert 0.0 < summary.overall_confidence < 1.0

    verif_map = {v.element_name: v for v in summary.verifications}
    assert verif_map["UserProfile"].status == VerificationStatus.MATCH
    assert verif_map["FakePaymentGateway"].status == VerificationStatus.HALLUCINATED
    assert verif_map["UserService"].status == VerificationStatus.MISSING


def test_drift_analyzer_evolution():
    """Test DriftAnalyzer identifying additions, removals, and signature changes."""
    base_model = StaticModelIR(
        project_name="EvolvingProject",
        classes=[
            ClassIR(
                id="pkg.Order",
                name="Order",
                qualified_name="pkg.Order",
                bases=["BaseModel"],
                methods=[
                    MethodIR(
                        id="pkg.Order.calculate_total",
                        name="calculate_total",
                        parameters=[ParameterIR(name="discount")],
                        return_type="float",
                    )
                ],
            ),
            ClassIR(
                id="pkg.LegacyPayment",
                name="LegacyPayment",
                qualified_name="pkg.LegacyPayment",
                methods=[],
            ),
        ],
    )

    target_model = StaticModelIR(
        project_name="EvolvingProject",
        classes=[
            ClassIR(
                id="pkg.Order",
                name="Order",
                qualified_name="pkg.Order",
                bases=["BaseModel", "Taxable"],  # Modified inheritance
                methods=[
                    MethodIR(
                        id="pkg.Order.calculate_total",
                        name="calculate_total",
                        parameters=[ParameterIR(name="discount"), ParameterIR(name="tax_rate")],  # Signature changed
                        return_type="float",
                    ),
                    MethodIR(
                        id="pkg.Order.refund",
                        name="refund",
                        parameters=[],
                        return_type="bool",
                    ),  # New method added
                ],
            ),
            ClassIR(
                id="pkg.ModernPayment",  # New class added, LegacyPayment removed
                name="ModernPayment",
                qualified_name="pkg.ModernPayment",
                methods=[],
            ),
        ],
    )

    drift_report = DriftAnalyzer.analyze_drift(
        base_model=base_model,
        target_model=target_model,
        base_commit="v1.0.0",
        target_commit="v2.0.0",
    )

    assert drift_report.total_drift_count >= 4
    assert drift_report.breaking_changes_count >= 1

    drift_types = [d.change_type for d in drift_report.drifted_elements]
    assert DriftChangeType.REMOVED in drift_types
    assert DriftChangeType.ADDED in drift_types
    assert DriftChangeType.MODIFIED_SIGNATURE in drift_types
    assert DriftChangeType.MODIFIED_RELATION in drift_types
