"""Unit tests for PlantUML and Mermaid diagram generators."""

from pathlib import Path
from tests.sample_codebase.models import InMemoryStorage
from tests.sample_codebase.service import UserService
from umldoc.extractors.dynamic_trace import ExecutionTracer
from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.generators.mermaid import MermaidGenerator
from umldoc.generators.plantuml import PlantUMLGenerator


def test_plantuml_and_mermaid_generation():
    """Verify diagram emitter output syntax for both static and dynamic IR."""
    sample_dir = Path(__file__).parent / "sample_codebase"
    extractor = ASTStaticExtractor(project_name="SampleTest", root_path=str(sample_dir))
    static_model = extractor.extract_directory(target_dir=str(sample_dir))

    # Test PlantUML Class Diagram
    puml_class = PlantUMLGenerator.generate_class_diagram(static_model)
    assert "@startuml" in puml_class
    assert "@enduml" in puml_class
    assert "class UserService" in puml_class
    assert "class UserProfile <<dataclass>>" in puml_class
    assert "class StorageBackend <<interface>>" in puml_class

    # Test Mermaid Class Diagram
    mmd_class = MermaidGenerator.generate_class_diagram(static_model)
    assert "classDiagram" in mmd_class
    assert "class UserService" in mmd_class
    assert "<<dataclass>>" in mmd_class

    # Run dynamic trace
    storage = InMemoryStorage()
    service = UserService(storage=storage)
    tracer = ExecutionTracer(
        scenario_name="TestSequenceGen",
        entrypoint_name="workflow",
        include_prefixes={"tests.sample_codebase"},
    )
    with tracer:
        service.register_user("u1", "alice", "alice@example.com")

    session = tracer.get_session_ir()

    # Test PlantUML Sequence Diagram
    puml_seq = PlantUMLGenerator.generate_sequence_diagram(session)
    assert "@startuml" in puml_seq
    assert "autonumber" in puml_seq
    assert "register_user" in puml_seq
    assert "@enduml" in puml_seq

    # Test Mermaid Sequence Diagram
    mmd_seq = MermaidGenerator.generate_sequence_diagram(session)
    assert "sequenceDiagram" in mmd_seq
    assert "autonumber" in mmd_seq
    assert "register_user" in mmd_seq
