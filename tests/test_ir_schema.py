"""Unit tests for Intermediate Representation (IR) schema and serialization."""

import json
from umldoc.ir.base import (
    ElementKind,
    MemberVisibility,
    RelationType,
    SourceLocation,
    VerificationStatus,
)
from umldoc.ir.dynamic_model import (
    DynamicModelIR,
    InteractionEventType,
    InteractionIR,
    ParticipantIR,
    TraceSessionIR,
)
from umldoc.ir.schema import DocumentIR
from umldoc.ir.static_model import (
    AttributeIR,
    ClassIR,
    MethodIR,
    ModuleIR,
    ParameterIR,
    RelationIR,
    StaticModelIR,
)
from umldoc.ir.verification import (
    DriftChangeType,
    DriftReportIR,
    ElementDriftIR,
    ElementVerificationIR,
    VerificationSummaryIR,
)


def test_json_schema_export():
    """Verify that DocumentIR exports a valid OpenAPI / JSON schema."""
    schema = DocumentIR.get_json_schema()
    assert "properties" in schema
    assert "static_model" in schema["properties"]
    assert "dynamic_model" in schema["properties"]
    assert "verification" in schema["properties"]
    assert "drift_report" in schema["properties"]
    assert schema["type"] == "object"


def test_full_document_ir_roundtrip():
    """Test building a complete DocumentIR, serializing to JSON, and validating deserialization."""
    static_model = StaticModelIR(
        project_name="SampleApp",
        root_path="/app",
        commit_hash="abc1234",
        modules=[
            ModuleIR(
                id="sample.models",
                name="models",
                qualified_name="sample.models",
                file_path="sample/models.py",
                docstring="Sample models module.",
                classes=[
                    ClassIR(
                        id="sample.models.User",
                        name="User",
                        qualified_name="sample.models.User",
                        kind=ElementKind.CLASS,
                        bases=[],
                        attributes=[
                            AttributeIR(
                                id="sample.models.User.name",
                                name="name",
                                type_annotation="str",
                                visibility=MemberVisibility.PUBLIC,
                            )
                        ],
                        methods=[
                            MethodIR(
                                id="sample.models.User.get_name",
                                name="get_name",
                                parameters=[],
                                return_type="str",
                                visibility=MemberVisibility.PUBLIC,
                            )
                        ],
                    )
                ],
            )
        ],
        classes=[],
        relations=[
            RelationIR(
                id="rel_1",
                source_id="sample.models.User",
                target_id="sample.models.BaseEntity",
                relation_type=RelationType.INHERITANCE,
            )
        ],
    )

    dynamic_model = DynamicModelIR(
        project_name="SampleApp",
        sessions=[
            TraceSessionIR(
                session_id="session_1",
                scenario_name="UserRegistration",
                entrypoint="register_user",
                participants=[
                    ParticipantIR(id="Client", name="Client"),
                    ParticipantIR(id="UserService", name="user_service: UserService"),
                ],
                interactions=[
                    InteractionIR(
                        event_id="evt_1",
                        event_type=InteractionEventType.CALL,
                        caller_id="Client",
                        callee_id="UserService",
                        method_name="register_user",
                        sequence_order=1,
                    )
                ],
            )
        ],
    )

    verification = VerificationSummaryIR(
        total_elements=1,
        verified_count=1,
        overall_confidence=1.0,
        verifications=[
            ElementVerificationIR(
                element_id="sample.models.User",
                element_name="User",
                element_kind=ElementKind.CLASS,
                status=VerificationStatus.MATCH,
                confidence_score=1.0,
                evidence="Matched AST node.",
            )
        ],
    )

    drift_report = DriftReportIR(
        project_name="SampleApp",
        base_commit="v1.0.0",
        target_commit="v1.1.0",
        drifted_elements=[
            ElementDriftIR(
                element_id="sample.models.User.email",
                element_name="User.email",
                element_kind=ElementKind.ATTRIBUTE,
                change_type=DriftChangeType.ADDED,
                diff_description="Added email field.",
            )
        ],
        breaking_changes_count=0,
        total_drift_count=1,
    )

    doc = DocumentIR(
        project_name="SampleApp",
        static_model=static_model,
        dynamic_model=dynamic_model,
        verification=verification,
        drift_report=drift_report,
    )

    json_str = doc.to_json_str()
    parsed_dict = json.loads(json_str)
    assert parsed_dict["project_name"] == "SampleApp"
    assert parsed_dict["static_model"]["project_name"] == "SampleApp"
    assert len(parsed_dict["verification"]["verifications"]) == 1

    # Deserialization test
    doc_reloaded = DocumentIR.from_json_str(json_str)
    assert doc_reloaded.project_name == doc.project_name
    assert doc_reloaded.static_model.modules[0].name == "models"
    assert doc_reloaded.dynamic_model.sessions[0].scenario_name == "UserRegistration"
    assert doc_reloaded.verification.verified_count == 1
    assert doc_reloaded.drift_report.total_drift_count == 1
