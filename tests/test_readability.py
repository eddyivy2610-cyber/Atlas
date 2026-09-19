"""Unit tests for DiagramDistiller and LLM prompt generation."""

from pathlib import Path
from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.extractors.dynamic_trace import ExecutionTracer
from umldoc.readability.distiller import DiagramDistiller
from tests.sample_codebase.models import InMemoryStorage
from tests.sample_codebase.service import UserService


def test_static_distillation_and_prompt_formatting():
    """Verify static model distillation filters private members and builds LLM prompts."""
    sample_dir = Path(__file__).parent / "sample_codebase"
    extractor = ASTStaticExtractor(project_name="SampleApp", root_path=str(sample_dir))
    ground_truth = extractor.extract_directory(target_dir=str(sample_dir))

    # Distill only focus classes
    distilled = DiagramDistiller.distill_static_model(
        ground_truth,
        focus_classes={"UserService", "UserProfile"},
        public_only=True,
    )

    class_names = {c.name for c in distilled.classes}
    assert "UserService" in class_names
    assert "UserProfile" in class_names
    assert "InMemoryStorage" not in class_names

    # Verify prompt generation
    prompt_payload = DiagramDistiller.format_class_prompt(distilled, focus_area="User Management")
    assert "system_prompt" in prompt_payload
    assert "user_prompt" in prompt_payload
    assert "UserService" in prompt_payload["user_prompt"]
    assert "User Management" in prompt_payload["user_prompt"]


def test_dynamic_distillation_and_prompt_formatting():
    """Verify sequence distillation and prompt formatting on execution trace."""
    storage = InMemoryStorage()
    service = UserService(storage=storage)

    tracer = ExecutionTracer(
        scenario_name="TestDistillationTrace",
        entrypoint_name="workflow",
        include_prefixes={"tests.sample_codebase"},
    )
    with tracer:
        service.register_user("u1", "alice", "alice@example.com")

    session = tracer.get_session_ir()
    distilled_session = DiagramDistiller.distill_trace_session(session, max_events=5)

    assert len(distilled_session.interactions) <= 5
    prompt_payload = DiagramDistiller.format_sequence_prompt(distilled_session)
    assert "system_prompt" in prompt_payload
    assert "register_user" in prompt_payload["user_prompt"]
